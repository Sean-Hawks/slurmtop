"""第 1 步修掉的 bug，每一個都有對應的測試。"""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.helpers import SCRIPT, env, fixture, load, run, strip


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


class HungNodeDoesNotFreeze(unittest.TestCase):
    """bug 3：一台節點卡住時其他節點照常更新，卡住的沿用上一筆並標 stale Ns。"""

    def test_once_returns_within_deadline(self):
        t = time.monotonic()
        p = run("hang", "--no-color", "--node-timeout", "0.5")
        self.assertLess(time.monotonic() - t, 5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("NODE n1", p.stdout)                # n1 照常
        self.assertIn("unreachable", p.stdout)           # n2 從來沒成功過

    def test_stale_reuses_last_reading(self):
        m = load()
        with fx_env("hang", SLURMTOP_FAKE_NOW="1000"):
            with fx_env("idle2x8"):
                snap = m.snapshot("n2")
            m._last[("node", "n2")] = (snap, 1000 - 12)
            m._color = False
            t = time.monotonic()
            out = m.render(["n1", "n2"], node_timeout=0.3)
            self.assertLess(time.monotonic() - t, 2)
        self.assertIn("stale 12s", out)
        self.assertEqual(out.count("stale"), 1)           # 只有 n2
        self.assertNotIn("unreachable", out)
        # 舊資料不寫進 n2 自己的歷史，n1 照寫
        self.assertEqual(len(m._hist[("n2", "gpu")]), 0)
        self.assertEqual(len(m._hist[("n1", "gpu")]), 1)

    def test_no_pile_up(self):
        """卡住的取樣還沒結束前，下一次刷新不會再開一個新的。"""
        m = load()
        with fx_env("hang"):
            for _ in range(3):
                m.render(["n1", "n2"], node_timeout=0.1)
        self.assertEqual(m._fx_calls["n2"], 1)
        self.assertEqual(m._fx_calls["n1"], 3)

    def test_stale_expires(self):
        m = load()
        with fx_env("hang", SLURMTOP_FAKE_NOW="1000"):
            with fx_env("idle2x8"):
                snap = m.snapshot("n2")
            m._last[("node", "n2")] = (snap, 1000 - m.STALE_MAX - 1)
            m._color = False
            out = m.render(["n1", "n2"], node_timeout=0.1)
        self.assertIn("unreachable", out)
        self.assertNotIn("stale", out)

    def test_failed_fetch_falls_back_too(self):
        """ssh 失敗（沒有輸出）也沿用上一筆，取代以前的「重試一次」。"""
        m = load()
        with fx_env("unreachable", SLURMTOP_FAKE_NOW="1000"):
            with fx_env("idle2x8"):
                snap = m.snapshot("n2")
            m._last[("node", "n2")] = (snap, 995)
            m._color = False
            out = m.render(["n1", "n2"], node_timeout=1)
        self.assertIn("stale 5s", out)

    def test_run_kills_hung_process(self):
        m = load()
        t = time.monotonic()
        self.assertEqual(m._run(["sleep", "30"], timeout=0.3), "")
        self.assertLess(time.monotonic() - t, 3)
        self.assertEqual(m._procs, set())

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_real_hung_ssh(self):
        """不用假資料：PATH 上放一個會卡住的假 ssh，--once 要準時結束，卡住的行程要被砍掉。"""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        marker = "slurmtop-test-hang-%d" % os.getpid()
        with open(os.path.join(tmp, "ssh"), "w") as f:
            f.write("#!/bin/sh\nexec -a %s sleep 30\n" % marker)
        os.chmod(os.path.join(tmp, "ssh"), 0o755)
        e = env(None, 150, 40)
        e["PATH"] = tmp + os.pathsep + e["PATH"]
        t = time.monotonic()
        p = subprocess.run([sys.executable, SCRIPT, "--once", "--no-color", "--nodes",
                            "stuck-node,localhost", "--node-timeout", "3"],
                           env=e, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertLess(time.monotonic() - t, 15)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("unreachable", p.stdout)
        self.assertIn("NODE localhost", p.stdout)
        time.sleep(0.3)
        left = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True).stdout
        self.assertEqual(left.strip(), "", "hung ssh was not killed")


class GresFormats(unittest.TestCase):
    """bug 4：squeue %b 的 GPU 數要認得 gres:gpu:N、gres/gpu:N、gres/gpu:型號:N。"""

    def test_gpu_count(self):
        gc = load().gpu_count
        cases = {
            "gres:gpu:8": 8, "gres/gpu:8": 8, "gres/gpu:h200:8": 8, "gres:gpu:h200:2": 2,
            "gpu:4": 4, "gpu:a100:2": 2, "gres/gpu": 1, "gres/gpu:h200": 1,
            "gres/gpu:h200:8(IDX:0-7)": 8, "gres:gpu:2(IDX:0,2)": 2,
            "gres/gpu:4,gres/shard:2": 4, "gres/shard:2,gres/gpu:a100:1,gres/gpu:v100:2": 3,
            "N/A": None, "": None, None: None, "gres/shard:4": None, "gres/gpumem:10G": None,
        }
        for gres, want in cases.items():
            self.assertEqual(gc(gres), want, gres)

    def test_queue_column(self):
        out = run("gres", "--no-color", "--no-qr").stdout
        rows = {ln.split()[1]: ln for ln in out.splitlines()
                if ln.startswith("│") and len(ln.split()) > 2 and ln.split()[1].isdigit()}
        for jid in ("1001", "1002", "1003"):
            self.assertIn(" 8 ", rows[jid], rows[jid])
        self.assertIn(" 2 ", rows["1004"])
        self.assertNotIn("gres", out)


def col_of(line, needle):
    """needle 在這行的顯示欄位（全形字算 2 格）。"""
    import unicodedata
    i = line.index(needle)
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line[:i])


class UserColumn(unittest.TestCase):
    """bug 5：佇列要有 USER 欄（squeue %u）。"""

    def test_squeue_asks_for_user(self):
        self.assertTrue(load().SQUEUE.split('"')[1].split("|")[10] == "%u")

    def test_user_shown_and_aligned(self):
        for lang, head in (("en", "USER"), ("zh", "使用者")):
            with self.subTest(lang):
                out = run("full2x8", "--no-color", "--lang", lang).stdout.splitlines()
                header = next(ln for ln in out if head in ln)
                row871 = next(ln for ln in out if " 871 " in ln)
                row873 = next(ln for ln in out if " 873 " in ln)
                self.assertIn("hawks", row871)
                self.assertIn("lin", row873)
                self.assertEqual(col_of(header, head), col_of(row871, " hawks ") + 1)
                # 其他欄位也要對齊（以前中文標題會把後面的欄位推歪）
                gpu_h = "GPU"
                self.assertEqual(col_of(header, gpu_h) + len(gpu_h),
                                 col_of(row871, " 8 ") + 2)

    def test_multi_column_keeps_user(self):
        out = run("longq", "--no-color", "--no-qr", cols=150, lines=30).stdout
        header = next(ln for ln in out.splitlines() if "USER" in ln)
        self.assertGreaterEqual(header.count("USER"), 2)     # 多欄時每欄都有
        self.assertIn("chen", out)


class ProcOverflowString(unittest.TestCase):
    """bug 6：--proc 超過 8 個行程時的「還有 N 個」要走 STRINGS，英文介面不能冒出中文。"""

    def panel(self, lang):
        m = load()
        m._color, m._lang = False, lang
        d = {"cpu_pct": 1.0, "load": [0, 0, 0], "ncpu": 8, "mem_total": 1024, "mem_used": 512,
             "gpus": [m.parse_gpu("0, 90, 1024, 2048, 50, 300")],
             "procs": [m.parse_proc(f"{100 + i}, 512, /bin/python{i}") for i in range(11)]}
        return "\n".join(m.node_panel("x", d, 80, True, False))

    def test_en(self):
        out = self.panel("en")
        self.assertIn("… 3 more", out)
        self.assertNotIn("還有", out)

    def test_zh(self):
        self.assertIn("…還有 3 個", self.panel("zh"))

    def test_every_key_in_both_languages(self):
        m = load()
        self.assertEqual(set(m.STRINGS["en"]), set(m.STRINGS["zh"]))


class WideChars(unittest.TestCase):
    """bug 8：寬字判斷改用 unicodedata.east_asian_width。"""

    def test_wide(self):
        m = load()
        for ch in ("中", "使", "Ａ", "😀", "🔥", "\U00020000", "가", "ア"):
            self.assertTrue(m.unicodedata_wide(ch), repr(ch))
        for ch in ("a", "-", "─", "│", "▕", "█", "◉", "°", "ｱ", "…"):
            self.assertFalse(m.unicodedata_wide(ch), repr(ch))

    def test_vlen_and_clip(self):
        m = load()
        self.assertEqual(m.vlen("GPU 😀 燒"), 9)
        self.assertEqual(m.vlen("\U00020000x"), 3)            # 擴充 B：以前算成 1
        self.assertEqual(m.vlen(m.clip("😀😀😀", 5)), 4)       # 不會切出半個字
        self.assertEqual(m.vlen(m.pad("😀", 4)), 4)


if __name__ == "__main__":
    unittest.main()
