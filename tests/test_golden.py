"""Golden frame 測試：用假資料跑 --once，整個畫面逐字比對 tests/golden/ 裡存好的結果。

畫面有意改變時重新產生（然後用 git diff 看一遍改了什麼）：

    SLURMTOP_UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden
"""

import os
import unittest

from tests.helpers import GOLDEN, run, strip

UPDATE = bool(os.environ.get("SLURMTOP_UPDATE_GOLDEN"))

# (名稱, 情境, 參數, 寬, 高)
CASES = [
    ("idle2x8", "idle2x8", ["--no-color"], 150, 60),
    ("full2x8", "full2x8", ["--no-color"], 150, 60),
    ("full2x8_proc", "full2x8", ["--no-color", "--proc"], 150, 70),
    ("full2x8_zh", "full2x8", ["--no-color", "--lang", "zh"], 150, 60),
    ("full2x8_ascii", "full2x8", ["--no-color", "--ascii"], 150, 60),
    ("full2x8_fit", "full2x8", ["--no-color", "--fit"], 120, 30),
    ("full2x8_stack", "full2x8", ["--no-color", "--stack"], 90, 60),
    ("unreachable", "unreachable", ["--no-color"], 150, 60),
    ("na_fields", "na_fields", ["--no-color", "--proc"], 150, 60),
    ("gres", "gres", ["--no-color"], 150, 50),
    ("hang", "hang", ["--no-color", "--node-timeout", "0.3"], 150, 50),
    ("nogpu", "nogpu", ["--no-color", "--nodes", "mac,cpu1"], 100, 40),
    ("longq", "longq", ["--no-color"], 150, 50),
]


class GoldenFrames(unittest.TestCase):
    maxDiff = None

    def check(self, name, scenario, args, cols, lines):
        p = run(scenario, *args, cols=cols, lines=lines)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, "")
        path = os.path.join(GOLDEN, name + ".txt")
        if UPDATE:
            with open(path, "w", encoding="utf-8") as f:
                f.write(p.stdout)
            return
        with open(path, encoding="utf-8") as f:
            self.assertEqual(p.stdout, f.read(), f"frame changed: {name}")

    def test_frames(self):
        for case in CASES:
            with self.subTest(case[0]):
                self.check(*case)

    def test_color_matches_plain(self):
        """加上顏色後，扣掉色碼的可見文字必須跟 --no-color 一模一樣（對齊不能被色碼弄歪）。

        QR 面板例外：彩色版用前景/背景色畫，純文字版用字元畫，本來就不一樣，所以關掉。
        """
        for name, scenario, args, cols, lines in CASES:
            with self.subTest(name):
                plain = run(scenario, *args, "--no-qr", cols=cols, lines=lines).stdout
                colored = run(scenario, *[a for a in args if a != "--no-color"], "--no-qr",
                              cols=cols, lines=lines).stdout
                self.assertEqual(strip(colored).splitlines(), plain.splitlines())

    def test_plain_has_no_escape_codes(self):
        for name, scenario, args, cols, lines in CASES:
            if "--no-color" in args:
                with self.subTest(name):
                    self.assertNotIn("\033", run(scenario, *args, cols=cols, lines=lines).stdout)


if __name__ == "__main__":
    unittest.main()
