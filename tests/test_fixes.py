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


if __name__ == "__main__":
    unittest.main()
