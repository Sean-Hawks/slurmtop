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


if __name__ == "__main__":
    unittest.main()
