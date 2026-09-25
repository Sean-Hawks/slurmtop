"""第 2 步：GPU 屬於哪個 job、佔著卻閒置、--me。全部用假資料；真的叢集要另外實測。"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.helpers import FIXTURES, load, run


class RemoteJobsSegment(unittest.TestCase):
    """REMOTE 的 jobs 段：把 /proc 換成假的目錄樹，真的用 bash 跑一次。"""

    def setUp(self):
        self.m = load()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        cg = {
            "4242": "0::/system.slice/slurmstepd.scope/job_871/step_0/user/task_0\n",   # cgroup v2
            "4343": "12:devices:/slurm/uid_1001/job_872/step_batch\n"                  # cgroup v1
                    "11:memory:/slurm/uid_1001/job_872/step_batch\n",
            "4444": "0::/user.slice/user-0.slice/session-3.scope\n",                   # 不是 Slurm
        }
        for pid, body in cg.items():
            os.makedirs(os.path.join(self.tmp, pid))
            with open(os.path.join(self.tmp, pid, "cgroup"), "w") as f:
                f.write(body)

    def run_segment(self, apps):
        seg = self.m.REMOTE.split("echo '@@jobs'")[1].split("echo '@@")[0]   # 只到下一段之前
        seg = seg.replace("/proc/", self.tmp + "/")
        script = "apps=%s\n%s" % ("'" + apps + "'", seg)
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stderr, "")
        return self.m.parse_pidjobs(p.stdout)

    def test_cgroup_v1_v2_and_plain(self):
        apps = ("GPU-a, 4242, 1000, python\nGPU-b, 4343, 10, pw.x\n"
                "GPU-b, 4343, 10, pw.x\nGPU-c, 4444, 5, Xorg\nGPU-d, 999999, 1, gone")
        got = self.run_segment(apps)
        self.assertEqual(got["4242"][0], "871")
        self.assertEqual(got["4343"][0], "872")
        self.assertIsNone(got["4444"][0])              # 非 Slurm 行程：job 是 "-"
        self.assertNotIn("999999", got)                # 行程已經結束：略過
        self.assertEqual(len(got), 3)                  # 同一個 pid 只查一次

    def test_no_apps(self):
        self.assertEqual(self.run_segment(""), {})


class Parsing(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_expand_hostlist(self):
        e = self.m.expand_hostlist
        self.assertEqual(e("n1"), ["n1"])
        self.assertEqual(e("n[1-3]"), ["n1", "n2", "n3"])
        self.assertEqual(e("gpu[01-03,07],cpu1"), ["gpu01", "gpu02", "gpu03", "gpu07", "cpu1"])
        self.assertEqual(e("r[1-2]n[1-2]"), ["r1n1", "r1n2", "r2n1", "r2n2"])
        self.assertEqual(e(""), [])

    def test_expand_idx(self):
        self.assertEqual(self.m.expand_idx("0-3,5"), ["0", "1", "2", "3", "5"])
        self.assertEqual(self.m.expand_idx("7"), ["7"])
        self.assertEqual(self.m.expand_idx("N/A"), [])

    def test_parse_alloc(self):
        text = "\n".join([
            # 新版：GRES=gpu:型號:N(IDX:...)，兩批節點各自的卡
            "JobId=10 JobName=a UserId=lin(1001) JobState=RUNNING Reason=None "
            "Nodes=n[1-2] CPU_IDs=0-7 Mem=0 GRES=gpu:h200:2(IDX:0-1) "
            "Nodes=n3 CPU_IDs=0-3 Mem=0 GRES=gpu:h200:1(IDX:6)",
            # 舊版：GRES_IDX=gpu(IDX:...)
            "JobId=11 JobName=b UserId=chen(1002) JobState=RUNNING Nodes=n4 CPU_IDs=0 "
            "Mem=0 GRES_IDX=gpu(IDX:2,4)",
            # 兩種型號混在一起
            "JobId=12 UserId=wu(1003) JobState=RUNNING Nodes=n5 CPU_IDs=0 Mem=0 "
            "GRES=gpu:a100:1(IDX:0),gpu:v100:2(IDX:1-2)",
            # 還在排隊的不算
            "JobId=13 UserId=wu(1003) JobState=PENDING Nodes=n5 CPU_IDs=0 Mem=0 GRES=gpu:1(IDX:3)",
            # 沒有 GPU 的 job
            "JobId=14 UserId=wu(1003) JobState=RUNNING Nodes=n6 CPU_IDs=0 Mem=0 GRES=",
        ])
        alloc, users = self.m.parse_alloc(text)
        self.assertEqual(alloc[("n1", "0")], ["10"])
        self.assertEqual(alloc[("n2", "1")], ["10"])
        self.assertEqual(alloc[("n3", "6")], ["10"])
        self.assertNotIn(("n3", "0"), alloc)
        self.assertEqual(alloc[("n4", "2")], ["11"])
        self.assertEqual(alloc[("n4", "4")], ["11"])
        self.assertEqual(sorted(k[1] for k in alloc if k[0] == "n5"), ["0", "1", "2"])
        self.assertNotIn(("n5", "3"), alloc)
        self.assertEqual(users, {"10": "lin", "11": "chen", "12": "wu", "14": "wu"})

    def test_link_procs(self):
        m = self.m
        gpus = [m.parse_gpu("0, GPU-a, 90, 1, 2, 30, 100"), m.parse_gpu("1, GPU-b, 0, 1, 2, 30, 100")]
        procs = [m.parse_proc("GPU-a, 1, 10, python"), m.parse_proc("GPU-a, 2, 10, python"),
                 m.parse_proc("GPU-b, 3, 10, Xorg"), m.parse_proc("GPU-zzz, 4, 10, ghost")]
        m.link_procs(gpus, procs, {"1": ("871", "hawks"), "2": ("871", "hawks"),
                                   "3": (None, "root")})
        self.assertEqual(gpus[0]["jobs"], ["871"])
        self.assertEqual(gpus[0]["users"], ["hawks"])
        self.assertEqual(gpus[1]["jobs"], [])
        self.assertEqual(gpus[1]["users"], ["root"])
        self.assertEqual(procs[2]["user"], "root")


def snap(m, utils, node="n1"):
    return {"cpu_pct": 0.0, "load": [0, 0, 0], "ncpu": 1, "mem_total": 1, "mem_used": 0,
            "procs": [], "gpus": [m.parse_gpu("%d, GPU-%d, %s, 1, 2, 30, 100" % (i, i, u))
                                  for i, u in enumerate(utils)]}


class IdleHeld(unittest.TestCase):
    """某 job 分到的卡最近 N 次取樣都 < 5% 才標示；換 job、用起來、沒人佔都要歸零。"""

    def setUp(self):
        self.m = load()
        self.alloc = ("", "", "JobId=7 UserId=lin(1) JobState=RUNNING Nodes=n1 CPU_IDs=0 Mem=0 "
                              "GRES=gpu:2(IDX:0-1)")

    def step(self, utils, alloc=None, age=None, n=3):
        m = self.m
        d = snap(m, utils)
        m.update_state(["n1"], [d], [age], alloc or self.alloc, n)
        return [m.idle_held("n1", g) for g in d["gpus"]]

    def test_needs_n_samples(self):
        self.assertEqual(self.step([0, 50, 0]), [False, False, False])
        self.assertEqual(self.step([0, 50, 0]), [False, False, False])
        self.assertEqual(self.step([4.9, 50, 0]), [True, False, False])   # G2 沒人佔
        self.assertEqual(self.step([0, 0, 0]), [True, False, False])

    def test_activity_resets(self):
        for _ in range(3):
            self.step([0, 0])
        self.assertEqual(self.step([30, 0]), [False, True])
        self.assertEqual(self.step([0, 0]), [False, True])

    def test_stale_and_unknown_do_not_count(self):
        self.step([0, 0])
        self.step([0, 0], age=10)                          # 舊資料不是新的取樣
        self.assertEqual(self.step(["[N/A]", 0]), [False, False])   # 讀不到不算閒置
        self.assertEqual(self.step([0, 0]), [False, True])

    def test_new_job_restarts_count(self):
        for _ in range(3):
            self.step([0, 0])
        other = ("", "", "JobId=8 UserId=chen(2) JobState=RUNNING Nodes=n1 CPU_IDs=0 Mem=0 "
                         "GRES=gpu:2(IDX:0-1)")
        self.assertEqual(self.step([0, 0], alloc=other), [False, False])

    def test_owner_label(self):
        m = self.m
        q = "7|x|R|1:00|1:00|1|1|gres/gpu:2|n1|2:00|lin|7\n"
        d = snap(m, [0])
        m.update_state(["n1"], [d], None, (q, "", self.alloc[2]), 1)
        self.assertEqual(m.gpu_owner("n1", d["gpus"][0]), ("7", "lin"))
        self.assertTrue(m.idle_held("n1", d["gpus"][0]))


class Frames(unittest.TestCase):
    def test_owner_in_gpu_row(self):
        out = run("full2x8", "--no-color").stdout
        g0 = [ln for ln in out.splitlines() if "G0 " in ln][0]
        self.assertIn("871 hawks", g0)
        self.assertIn("872 hawks", g0)

    def test_idle_flags(self):
        out = run("idleheld", "--no-color", "--idle-samples", "1").stdout
        rows = {}                                      # "G2" -> [n1 那格, n2 那格]
        for ln in out.splitlines():
            for cell in ln.split("││"):
                m = re.match(r"^│? (G\d) ", cell)
                if m:
                    rows.setdefault(m.group(1), []).append(cell)
        self.assertIn("IDLE 881 lin", rows["G2"][0])
        self.assertIn("IDLE 882 chen", rows["G7"][0])
        self.assertNotIn("IDLE", rows["G0"][0])
        self.assertNotIn("IDLE", rows["G5"][1])        # n2 G5：沒人佔就不算
        self.assertIn("(root)", rows["G7"][1])         # 非 Slurm 行程
        self.assertIn("1006_3 wu", rows["G4"][1])      # 陣列 job 用 %i 顯示
        top = out.splitlines()[4]
        self.assertIn("n1 G2,G3 held but idle (881 lin)", top)
        self.assertIn("n1 G4,G5,G6,G7 held but idle (882 chen)", top)

    def test_single_sample_is_not_idle_by_default(self):
        out = run("idleheld", "--no-color").stdout
        self.assertNotIn("IDLE", out)
        self.assertNotIn("held but idle", out)

    def test_no_alert_line_when_fine(self):
        for scn in ("full2x8", "idle2x8"):
            out = run(scn, "--no-color", "--idle-samples", "1").stdout
            self.assertNotIn("⚠", out)
            self.assertIn("LOAD", out.splitlines()[4])     # 頂端之後直接是示波器

    def test_me(self):
        out = run("idleheld", "--no-color", "--me", USER="lin", LOGNAME="lin").stdout
        self.assertIn("NODE n1", out)
        self.assertNotIn("NODE n2", out)
        self.assertNotIn("882", out.split("Slurm queue")[1])
        self.assertIn(" 885 ", out)
        self.assertNotIn("G4 ", out)                      # G4-7 是 chen 的
        self.assertIn("16 online", out)                   # 頂端的總覽仍是整個叢集

    def test_me_process_owner(self):
        out = run("idleheld", "--no-color", "--me", USER="root", LOGNAME="root").stdout
        self.assertIn("NODE n2", out)
        self.assertIn("G7 ", out)
        self.assertNotIn("G0 ", out)

    def test_me_nothing(self):
        out = run("idleheld", "--no-color", "--me", USER="nobody", LOGNAME="nobody").stdout
        self.assertIn("no GPUs in use by nobody", out)
        self.assertNotIn("NODE", out)


class ReviewFixes(unittest.TestCase):
    """夜間自我審查找到的問題。"""

    def test_nvidia_smi_messages_are_not_gpus(self):
        m = load()
        for msg in ("No devices were found",
                    "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA "
                    "driver. Make sure that the latest NVIDIA driver is installed and running.",
                    "Failed to initialize NVML: Driver/library version mismatch"):
            self.assertIsNone(m.parse_gpu(msg), msg)
        out = "@@cpu\nPCT 5\n@@load\n1 1 1\n8\n@@mem\n100 50\n@@gpu\nNo devices were found\n@@proc\n"
        with mock.patch.object(m, "run_script", return_value=out):
            d = m.snapshot("x")
        self.assertEqual(d["gpus"], [])                  # 照 CPU-only 機器顯示

    def test_strict_run(self):
        m = load()
        self.assertIsNone(m._run(["false"], strict=True))
        self.assertEqual(m._run(["false"]), "")
        self.assertIsNone(m._run(["sleep", "5"], timeout=0.2, strict=True))
        self.assertEqual(m._run(["echo", "hi"], strict=True), "hi\n")
        self.assertIsNone(m.sh("exit 3", strict=True))
        self.assertIsNone(m.sh("definitely-not-a-command-xyz", strict=True))

    def test_failed_squeue_keeps_last_queue_and_idle_state(self):
        m = load()
        m._color = False
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(os.path.join(FIXTURES, "idleheld"), os.path.join(tmp, "f"))
        fx = os.path.join(tmp, "f")
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fx, "SLURMTOP_FAKE_NOW": "1000",
                                          "COLUMNS": "150", "LINES": "45"}):
            for _ in range(2):
                m.render(["n1", "n2"], idle_samples=2, node_timeout=2)
            g2 = next(g for g in m._last[("node", "n1")][0]["gpus"] if g["idx"] == "2")
            self.assertTrue(m.idle_held("n1", g2))
            open(os.path.join(fx, "squeue.fail"), "w").close()     # 控制器沒回應
            self.assertIsNone(m.slurm_query())
            out = m.render(["n1", "n2"], idle_samples=2, node_timeout=2)
        self.assertTrue(m.idle_held("n1", g2))            # 分配紀錄還在，計數沒被清掉
        self.assertIn("train-lm", out)                    # 佇列沿用上一次
        self.assertNotIn("(no jobs)", out)
        self.assertIn("Slurm queue stale 0s", out)        # 並標明是舊的（假時鐘沒走，所以 0s）

    def test_no_slurm_at_all(self):
        m = load()
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": os.path.join(FIXTURES, "nogpu")}):
            open_fail = os.path.join(FIXTURES, "nogpu", "squeue.fail")
            self.assertFalse(os.path.exists(open_fail))
            self.assertEqual(m.slurm_query(), ("", "", ""))


if __name__ == "__main__":
    unittest.main()
