"""第 1 步修掉的 bug，每一個都有對應的測試。"""

import copy
import os
import unittest
from unittest import mock

from tests.helpers import fixture, load, run, strip


def fx_env(scenario, cols=150, lines=60, **extra):
    e = {"SLURMTOP_FIXTURES": fixture(scenario), "COLUMNS": str(cols), "LINES": str(lines)}
    e.update(extra)
    return mock.patch.dict(os.environ, e)


class HistoryOncePerRefresh(unittest.TestCase):
    """bug 1：render() 每次刷新會呼叫 _frame() 好幾次，歷史不可以跟著寫好幾筆。"""

    def test_one_sample_per_refresh(self):
        m = load()
        # 60 行高：預設模式會先畫一次、再為了拉高示波器重畫一次
        with fx_env("full2x8", lines=60):
            for _ in range(3):
                m.render(["n1", "n2"])
        self.assertEqual(len(m._hist[("all", "gpu")]), 3)
        self.assertEqual(len(m._hist[("n1", "gpu")]), 3)
        self.assertEqual(len(m._hist[("n1", "cpu")]), 3)
        self.assertEqual(len(m._hist[("n2", "g7")]), 3)

    def test_fit_mode_too(self):
        m = load()
        with fx_env("full2x8", cols=100, lines=20):   # 太小，--fit 會一路試到最後一個方案
            for _ in range(2):
                m.render(["n1", "n2"], fit=True)
        self.assertEqual(len(m._hist[("all", "gpu")]), 2)

    def test_drawing_does_not_touch_history(self):
        m = load()
        with fx_env("full2x8"):
            m.render(["n1", "n2"])
            snaps = [m.snapshot("n1"), m.snapshot("n2")]
            before = copy.deepcopy(dict(m._hist))
            m._frame(["n1", "n2"], snaps, 150, 60, False, False, True, False)
            m._frame(["n1", "n2"], snaps, 150, 60, False, False, True, True)
            m._frame(["n1", "n2"], [None, None], 150, 60, False, False, True, False)
        self.assertEqual(dict(m._hist), before)

    def test_frame_shows_sample_count(self):
        out = strip(run("full2x8", "--no-color").stdout)
        self.assertIn("last 1 samples", out)


class RobustGpuFields(unittest.TestCase):
    """bug 2：nvidia-smi 欄位是 [N/A] 或空的時候不能讓整個程式掛掉，讀不到就顯示 "-"。"""

    def setUp(self):
        self.m = load()

    def test_num(self):
        num = self.m.num
        self.assertEqual(num("42"), 42.0)
        self.assertEqual(num(" 118.20 "), 118.2)
        for bad in ("[N/A]", "N/A", "", "   ", None, "[Not Supported]", "[Unknown Error]",
                    "nan", "inf", "ERR!"):
            self.assertIsNone(num(bad), bad)

    def test_parse_gpu_line(self):
        g = self.m.parse_gpu("3, [N/A], , 143771, 41, [N/A]")
        self.assertEqual(g, {"idx": "3", "util": None, "mem_used": None, "mem_total": 143771.0,
                             "temp": 41.0, "power": None})
        # 欄位不夠也不能炸
        self.assertEqual(self.m.parse_gpu("5")["util"], None)
        self.assertIsNone(self.m.parse_gpu(""))

    def test_stats_skip_unknown(self):
        gpus = [self.m.parse_gpu(x) for x in ("0, [N/A], 1024, 2048, 40, [N/A]",
                                              "1, 50, 1024, 2048, [N/A], 100")]
        st = self.m.gpu_stats(gpus)
        self.assertEqual(st["util"], 50.0)
        self.assertEqual(st["power"], 100.0)
        self.assertEqual(st["tmax"], 40.0)
        allna = self.m.gpu_stats([self.m.parse_gpu("0, [N/A], [N/A], [N/A], [N/A], [N/A]")])
        self.assertIsNone(allna["util"])
        self.assertIsNone(allna["power"])
        self.assertIsNone(allna["tmax"])

    def test_fnum_keeps_width(self):
        self.assertEqual(self.m.fnum(None, "%3.0f%%"), "   -")
        self.assertEqual(self.m.fnum(7, "%3.0f%%"), "  7%")
        self.assertEqual(self.m.fnum(None, "%4.0fW"), "    -")

    def test_frame_with_na_fields(self):
        for extra in ([], ["--proc"], ["--fit"], ["--ascii"]):
            with self.subTest(extra):
                p = run("na_fields", "--no-color", *extra)
                self.assertEqual(p.returncode, 0, p.stderr)
                rows = [ln for ln in p.stdout.splitlines() if "G3 " in ln or "G0 " in ln]
                if "--fit" not in extra:
                    self.assertTrue(rows)
                    self.assertTrue(all(" -" in r for r in rows[:1]))

    def test_all_gpus_unreadable(self):
        """整台都讀不到使用率：節點和頂端都顯示 "-"，不是 0%，也不能除以零。"""
        m = self.m
        d = {"cpu_pct": 1.0, "load": [0, 0, 0], "ncpu": 8, "mem_total": 1024, "mem_used": 512,
             "procs": [], "gpus": [m.parse_gpu("0, [N/A], [N/A], [N/A], [N/A], [N/A]")]}
        m._color = False
        head = "\n".join(m.cluster_header([d], 120))
        self.assertIn("- UTIL", head)
        m.update_history(["x"], [d])
        self.assertEqual(len(m._hist[("all", "gpu")]), 0)
        panel = "\n".join(m.node_panel("x", d, 80, True, True))
        self.assertIn("G0", panel)


if __name__ == "__main__":
    unittest.main()
