"""讓更多機器、更多介面用得上 slurmtop：--json、各種 GPU／作業系統、網頁、Prometheus、評估報告。"""

import json
import os
import unittest
from unittest import mock

from tests.helpers import FIXTURES, load, run


def as_json(scenario, *args, **kw):
    p = run(scenario, "--json", *args, **kw)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class JsonOutput(unittest.TestCase):
    def test_shape(self):
        d = as_json("idleheld", "--idle-samples", "1")
        self.assertEqual(d["cluster"], "hipac-team3")
        self.assertEqual(d["summary"]["gpus"], 16)
        self.assertEqual(d["summary"]["nodes_up"], 2)
        n1 = d["nodes"][0]
        self.assertEqual(n1["name"], "n1")
        self.assertEqual(len(n1["gpus"]), 8)
        g2 = n1["gpus"][2]
        self.assertEqual((g2["job"], g2["user"], g2["idle_held"]), ("881", "lin", True))
        self.assertEqual(n1["disk"]["pct"], 42.0)
        self.assertIsNone(n1["net"])                       # 只有一次取樣
        self.assertEqual([j["id"] for j in d["queue"]][:3], ["881", "882", "883"])
        self.assertEqual(d["queue"][3]["id"], "1006_3")
        self.assertEqual(d["queue"][3]["job_id"], "1009")
        self.assertEqual(d["queue"][0]["gpus"], 4)
        self.assertIn({"level": "warn", "text": "n1 G2,G3 held but idle (881 lin)"}, d["alerts"])

    def test_unreadable_is_null(self):
        d = as_json("na_fields")
        g0 = d["nodes"][0]["gpus"][0]
        self.assertIsNone(g0["util"])
        self.assertIsNone(g0["power_w"])
        self.assertEqual(g0["mem_used_mib"], 20480)

    def test_unreachable_and_alerts(self):
        d = as_json("alerts", "--idle-samples", "1")
        n3 = next(n for n in d["nodes"] if n["name"] == "n3")
        self.assertEqual(n3, {"name": "n3", "up": False, "stale_s": None})
        levels = [a["level"] for a in d["alerts"]]
        self.assertEqual(levels, ["red", "red", "red", "warn"])

    def test_me(self):
        d = as_json("idleheld", "--me", USER="lin", LOGNAME="lin")
        self.assertEqual([n["name"] for n in d["nodes"]], ["n1"])
        self.assertEqual([g["index"] for g in d["nodes"][0]["gpus"]], ["0", "1", "2", "3"])
        self.assertEqual([j["id"] for j in d["queue"]], ["881", "885"])
        self.assertEqual(d["summary"]["gpus"], 16)          # 總覽仍是整個叢集

    def test_no_gpu_machines(self):
        d = as_json("nogpu", "--nodes", "mac,cpu1")
        self.assertEqual(d["summary"]["gpus"], 0)
        self.assertIsNone(d["summary"]["gpu_util"])
        self.assertEqual(d["nodes"][0]["cpu_pct"], 23.4)

    def test_stdout_is_pure_json(self):
        p = run("full2x8", "--json")
        self.assertNotIn("\033", p.stdout)
        json.loads(p.stdout)


IOREG_INTEL_MAC = """\
+-o IntelAccelerator  <class IntelAccelerator, id 0x10000033b, registered, matched, active, busy 0 (3 ms), retain 30>
      "PerformanceStatistics" = {"Device Utilization %"=7,"In use system memory"=268435456,"Allocated system memory"=536870912}
      "model" = <"Intel(R) UHD Graphics 630">
+-o AMDRadeonX6000_AMDNavi14GraphicsAccelerator  <class AMDRadeonX6000_AMDNavi14GraphicsAccelerator, id 0x100000abc>
      "PerformanceStatistics" = {"GPU Activity(%)"=64,"vramUsedBytes"=2147483648,"vramFreeBytes"=2147483648,"Temperature(C)"=71,"Total Power(W)"=38}
      "model" = <"AMD Radeon Pro 5500M">
"""


class AppleGpu(unittest.TestCase):
    """macOS 的 GPU 用 ioreg 讀：Apple Silicon 的統一記憶體、Intel Mac 的內顯＋獨顯。"""

    def test_m3(self):
        m = load()
        from tests.fixtures.make_fixtures import IOREG_M3
        (g,) = m.parse_ioreg(IOREG_M3, 16384)
        self.assertEqual(g["vendor"], "apple")
        self.assertEqual(g["util"], 26)
        self.assertAlmostEqual(g["mem_used"], 862388224 / 1048576)
        self.assertEqual(g["mem_total"], 16384)             # 統一記憶體 = 整台 RAM
        self.assertIsNone(g["temp"])                        # 要 sudo powermetrics
        self.assertEqual(g["model"], "Apple M3 10-core")

    def test_intel_mac_two_gpus(self):
        m = load()
        igpu, dgpu = m.parse_ioreg(IOREG_INTEL_MAC, 32768)
        self.assertEqual((igpu["idx"], igpu["util"], igpu["model"]), ("0", 7, "Intel(R) UHD Graphics 630"))
        self.assertEqual((dgpu["util"], dgpu["temp"], dgpu["power"]), (64, 71, 38))
        self.assertEqual((dgpu["mem_used"], dgpu["mem_total"]), (2048, 4096))

    def test_nothing(self):
        self.assertEqual(load().parse_ioreg(""), [])

    def test_frame(self):
        d = as_json("applesilicon", "--nodes", "m3")
        g = d["nodes"][0]["gpus"][0]
        self.assertEqual((g["vendor"], g["util"], g["model"]), ("apple", 26, "Apple M3 10-core"))
        self.assertEqual(d["summary"]["gpus"], 1)
        out = run("applesilicon", "--no-color", "--nodes", "m3").stdout
        self.assertIn("Apple M3 10-core", out)
        self.assertIn("UTIL", out)                          # 頂端改用 GPU 當主指標

    @unittest.skipUnless(os.uname().sysname == "Darwin" and os.uname().machine == "arm64",
                         "needs an Apple Silicon Mac")
    def test_real_mac(self):
        """不用假資料，在這台 Mac 上真的讀一次。"""
        d = as_json(None, "--nodes", "localhost")
        gpus = d["nodes"][0]["gpus"]
        self.assertTrue(gpus and gpus[0]["vendor"] == "apple", gpus)
        self.assertIsNotNone(gpus[0]["util"])


if __name__ == "__main__":
    unittest.main()
