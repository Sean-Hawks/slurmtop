"""假資料層與可重現性本身的測試。"""

import os
import platform
import sys
import time
import unittest
from unittest import mock

from tests.helpers import FAKE_NOW, SCRIPT, env, fixture, load, run, strip


class FixtureLayer(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_sh_reads_fixture_by_key(self):
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("full2x8")}):
            self.assertIn("hawks-mxp16", self.m.sh("squeue -h -o whatever", key="squeue"))
            # 沒給 key 時用指令的第一個字
            self.assertEqual(self.m.sh("hostname -s").strip(), "n1")

    def test_sh_missing_fixture_is_empty(self):
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("nogpu")}):
            self.assertEqual(self.m.sh("squeue -h", key="squeue"), "")

    def test_sh_never_runs_commands_in_fixture_mode(self):
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("nogpu")}), \
                mock.patch("subprocess.run") as r, mock.patch("subprocess.Popen") as po:
            self.m.sh("rm -rf /nonexistent", key="x")
            self.m.run_script("mac", self.m.REMOTE)
            r.assert_not_called()
            po.assert_not_called()

    def test_run_script_sequence(self):
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("seq")}):
            a = self.m.run_script("n1", self.m.REMOTE)
            b = self.m.run_script("n1", self.m.REMOTE)
            c = self.m.run_script("n1", self.m.REMOTE)
            d = self.m.run_script("n1", self.m.REMOTE)
        self.assertIn("cpu  1000", a)
        self.assertIn("cpu  1600", b)
        self.assertIn("cpu  2200", c)       # 沒有編號檔了，退回 n1.txt
        self.assertIn("cpu  2200", d)

    def test_hang_respects_timeout(self):
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("hang")}):
            t = time.monotonic()
            self.assertEqual(self.m.run_script("n2", self.m.REMOTE, timeout=0.2), "")
            self.assertLess(time.monotonic() - t, 2)

    def test_sections(self):
        secs = self.m.sections("junk\n@@cpu\nPCT 5\n@@gpu\n\n@@proc\n1, 2, x\n")
        self.assertEqual(secs, {"cpu": "PCT 5", "gpu": "", "proc": "1, 2, x"})

    def test_fake_clock(self):
        with mock.patch.dict(os.environ, {"SLURMTOP_FAKE_NOW": FAKE_NOW, "TZ": "UTC"}):
            time.tzset()
            self.assertEqual(self.m.clock(), "14:13:20")
        time.tzset()


class QRPlain(unittest.TestCase):
    def test_no_color_qr_round_trips(self):
        """--no-color 的 QR（字元畫亮模組）解回來的點陣要跟內嵌的一模一樣。"""
        m = load()
        m._color = False
        lines = m.qr_lines(m.QR_QUIET)
        top = {"█": 0, "▀": 0, "▄": 1, " ": 1}      # 字元 -> 上半格是不是暗模組
        bot = {"█": 0, "▀": 1, "▄": 0, " ": 1}
        grid = []
        for ln in lines:
            grid.append([top[c] for c in ln])
            grid.append([bot[c] for c in ln])
        q = m.QR_QUIET
        for r, hexrow in enumerate(m.QR_ROWS):
            bits = [int(b) for b in bin(int(hexrow, 16))[2:].zfill(m.QR_SIZE)]
            self.assertEqual(grid[q + r][q:q + m.QR_SIZE], bits)
        self.assertNotIn("\033", "".join(lines))


class Reproducible(unittest.TestCase):
    def test_same_output_twice(self):
        """PYTHONHASHSEED 不同也要畫出同一個畫面（以前 trace 用 hash() 會飄）。"""
        a = run("full2x8", PYTHONHASHSEED="1").stdout
        b = run("full2x8", PYTHONHASHSEED="2").stdout
        self.assertEqual(a, b)


class LocalSmoke(unittest.TestCase):
    """不用假資料，真的在這台機器上跑一次（macOS 或 Linux 都要能跑）。"""

    @unittest.skipUnless(platform.system() in ("Darwin", "Linux"), "needs a POSIX shell")
    def test_once_localhost(self):
        import subprocess
        e = env(None, 120, 40)
        e.pop("SLURMTOP_FAKE_NOW")
        p = subprocess.run([sys.executable, SCRIPT, "--once", "--nodes", "localhost", "--no-color"],
                           env=e, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("localhost", p.stdout)
        self.assertIn("CPU", p.stdout)
        self.assertNotIn("unreachable", p.stdout)


if __name__ == "__main__":
    unittest.main()
