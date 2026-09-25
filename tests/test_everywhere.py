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


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class AmdGpu(unittest.TestCase):
    """Linux 上的 AMD 卡從 amdgpu 的 sysfs 讀。用假的 /sys/class/drm 真的跑一次 shell 段。"""

    def fake_drm(self):
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        c0 = os.path.join(tmp, "card0", "device")
        for name, v in (("vendor", "0x1002\n"), ("gpu_busy_percent", "87\n"),
                        ("mem_info_vram_used", "68719476736\n"),
                        ("mem_info_vram_total", "205822885888\n"), ("unique_id", "a1b2c3\n"),
                        ("hwmon/hwmon3/temp1_input", "61000\n"),
                        ("hwmon/hwmon3/power1_average", "512000000\n")):
            _write(os.path.join(c0, name), v)
        c1 = os.path.join(tmp, "card1", "device")                 # NVIDIA：不歸這段管
        _write(os.path.join(c1, "vendor"), "0x10de\n")
        c2 = os.path.join(tmp, "card2", "device")                 # 只有 power1_input、unique_id 是空的
        for name, v in (("vendor", "0x1002\n"), ("gpu_busy_percent", "0\n"),
                        ("mem_info_vram_used", "1048576\n"), ("mem_info_vram_total", "17179869184\n"),
                        ("unique_id", ""), ("hwmon/hwmon5/temp1_input", "40000\n"),
                        ("hwmon/hwmon5/power1_input", "15000000\n")):
            _write(os.path.join(c2, name), v)
        os.makedirs(os.path.join(tmp, "card0-DP-1"))
        os.symlink(c0, os.path.join(tmp, "card0-DP-1", "device"))  # 接頭，不能重複算
        return tmp

    def run_segment(self, drm):
        import subprocess
        m = load()
        seg = m.REMOTE.split("echo '@@amdgpu'")[1].split("echo '@@")[0]
        p = subprocess.run(["bash", "-c", seg.replace("/sys/class/drm", drm)],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stderr, "")
        return m, p.stdout

    def test_sysfs(self):
        m, out = self.run_segment(self.fake_drm())
        self.assertEqual(out.splitlines(), [
            "card0 87 68719476736 205822885888 61000 512000000 a1b2c3",
            "card2 0 1048576 17179869184 40000 15000000 -"])
        a, b = m.parse_amdgpu(out)
        self.assertEqual((a["idx"], a["util"], a["mem_used"], a["mem_total"], a["temp"], a["power"],
                          a["uuid"], a["vendor"]),
                         ("0", 87, 65536, 196288, 61, 512, "AMD-a1b2c3", "amd"))
        self.assertEqual((b["idx"], b["power"], b["uuid"]), ("1", 15, None))

    def test_no_amd(self):
        import tempfile
        m, out = self.run_segment(tempfile.mkdtemp())
        self.assertEqual(out, "")
        self.assertEqual(m.parse_amdgpu(""), [])

    def test_amd_node_frame(self):
        d = as_json("amd", "--idle-samples", "1")
        gpus = d["nodes"][0]["gpus"]
        self.assertEqual(len(gpus), 8)
        self.assertEqual({g["vendor"] for g in gpus}, {"amd"})
        self.assertEqual((gpus[0]["job"], gpus[0]["user"], gpus[0]["util"]), ("950", "hawks", 93))
        self.assertEqual([g["idle_held"] for g in gpus], [False] * 4 + [True, True, False, False])
        self.assertEqual(d["summary"]["power_w"], 4 * 650 + 4 * 140)

    def test_after_nvidia(self):
        m = load()
        (g,) = m.parse_amdgpu("card3 5 - - - - -", start=8)
        self.assertEqual((g["idx"], g["util"], g["mem_used"]), ("8", 5, None))


class Jetson(unittest.TestCase):
    """Jetson：GPU 負載在 sysfs，溫度在 thermal zone。用假的 Orin 目錄樹跑一次 shell 段。"""

    def run_segment(self, root):
        import subprocess
        m = load()
        seg = m.REMOTE.split("echo '@@jetson'")[1].split("echo '@@")[0]
        rd = m.REMOTE.split("echo '@@amdgpu'")[1].split("\n")
        rd = next(ln for ln in rd if ln.startswith("rd()"))      # jetson 段用到 amdgpu 段定義的 rd()
        seg = (rd + "\n" + seg).replace("/sys/devices", root + "/devices") \
            .replace("/sys/class/thermal", root + "/thermal") \
            .replace("/proc/device-tree/model", root + "/model")
        p = subprocess.run(["bash", "-c", seg], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stderr, "")
        return m, p.stdout

    def test_orin(self):
        import tempfile, shutil
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        _write(os.path.join(root, "devices/platform/17000000.ga10b/load"), "734\n")
        _write(os.path.join(root, "thermal/thermal_zone0/type"), "CPU-therm\n")
        _write(os.path.join(root, "thermal/thermal_zone0/temp"), "50000\n")
        _write(os.path.join(root, "thermal/thermal_zone1/type"), "gpu-thermal\n")
        _write(os.path.join(root, "thermal/thermal_zone1/temp"), "47500\n")
        with open(os.path.join(root, "model"), "wb") as f:
            f.write(b"NVIDIA Jetson AGX Orin Developer Kit\x00")
        m, out = self.run_segment(root)
        self.assertEqual(out.strip(), "734 47500 NVIDIA_Jetson_AGX_Orin_Developer_Kit")
        (g,) = m.parse_jetson(out, 65536, 12000)
        self.assertEqual((g["util"], g["temp"], g["mem_used"], g["mem_total"], g["model"], g["vendor"]),
                         (73.4, 47.5, 12000, 65536, "NVIDIA Jetson AGX Orin Developer Kit", "jetson"))

    def test_not_a_jetson(self):
        import tempfile
        m, out = self.run_segment(tempfile.mkdtemp())
        self.assertEqual(out, "")
        self.assertEqual(m.parse_jetson(""), [])

    def test_nvidia_smi_wins(self):
        """新版 JetPack 的 nvidia-smi 讀得到卡時，不再另外加一張 Jetson GPU。"""
        m = load()
        out = ("@@cpu\nPCT 5\n@@load\n1 1 1\n8\n@@mem\n100 50\n@@gpu\n"
               "0, GPU-x, 12, 1, 2, 40, 10\n@@proc\n@@jetson\n500 40000 Orin\n")
        with mock.patch.object(m, "run_script", return_value=out):
            d = m.snapshot("x")
        self.assertEqual([g["vendor"] if "vendor" in g else "nvidia" for g in d["gpus"]], ["nvidia"])


NETSTAT_FREEBSD = """\
Name    Mtu Network       Address              Ipkts Ierrs Idrop     Ibytes    Opkts Oerrs     Obytes  Coll
em0    1500 <Link#1>      08:00:27:aa:bb:cc   500000     0     0  700000000   300000     0   40000000     0
em0       - 10.0.2.0/24   10.0.2.15           490000     -     -  690000000   290000     -   39000000     -
lo0   16384 <Link#2>      lo0                     10     0     0       1000       10     0       1000     0
pflog0 33160 <Link#3>                              0     0     0          0        0     0          0     0
ix0    9000 <Link#4>                            1000     0     0      12345     2000     0      67890     0
"""


class PosixShells(unittest.TestCase):
    """REMOTE 只能用 POSIX sh：Debian/Ubuntu 的 /bin/sh 是 dash，FreeBSD 沒有 bash。"""

    def remote(self):
        return load().REMOTE

    def test_runs_everywhere(self):
        import shutil, subprocess
        shells = [sh for sh in ("bash", "dash", "ksh", "sh") if shutil.which(sh)]
        self.assertTrue(shells)
        for sh in shells:
            with self.subTest(sh):
                p = subprocess.run([sh, "-s"], input=self.remote(), capture_output=True,
                                   text=True, timeout=60)
                self.assertEqual(p.stderr, "", sh)
                secs = load().sections(p.stdout)
                for k in ("cpu", "load", "mem", "gpu", "proc", "jobs", "disk", "net"):
                    self.assertIn(k, secs, sh)

    def test_login_shells(self):
        """ssh 會用對方的登入 shell 解讀指令：csh、tcsh、zsh、fish 都要能跑。"""
        import shutil, subprocess
        m = load()
        for login in ("csh", "tcsh", "zsh", "fish"):
            if not shutil.which(login):
                continue
            with self.subTest(login):
                cmd = "sh -c '%s'" % m.SHELL_PICK
                p = subprocess.run([login, "-c", cmd], input=m.REMOTE, capture_output=True,
                                   text=True, timeout=60)
                self.assertIn("gpu", m.sections(p.stdout), p.stderr)

    def test_freebsd_netstat(self):
        import subprocess, tempfile
        m = load()
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(NETSTAT_FREEBSD)
        self.addCleanup(os.remove, path)
        seg = m.REMOTE.split("echo '@@net'")[1].replace("[ -r /proc/net/dev ]", "false") \
                                              .replace("netstat -ibn 2>/dev/null", "cat " + path)
        out = subprocess.run(["sh", "-c", seg], capture_output=True, text=True).stdout.strip()
        # em0 的 <Link> 行 + 沒有 MAC 的 ix0（少一欄）；lo0、pflog0 不算
        self.assertEqual(out, "%d %d" % (700000000 + 12345, 40000000 + 67890))

    def test_freebsd_memory(self):
        """用假的 sysctl 跑 FreeBSD 的記憶體分支。"""
        import subprocess
        body = self.remote().split("elif sysctl -n vm.stats.vm.v_free_count >/dev/null 2>&1; then")[1] \
                            .split("else")[0]
        fake = ("sysctl() { case \"$2\" in hw.pagesize) echo 4096;; hw.physmem) echo 17179869184;;"
                " vm.stats.vm.v_free_count) echo 1048576;; vm.stats.vm.v_inactive_count) echo 262144;;"
                " esac; }\n")
        out = subprocess.run(["sh", "-c", fake + body], capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), "16384 %d" % (16384 - (1048576 + 262144) * 4096 // 1048576))

    def test_cputime(self):
        """FreeBSD 的 kern.cp_time：user nice sys intr idle，閒置只算第 5 欄。"""
        m = load()
        base = "@@load\n1 1 1\n4\n@@mem\n100 50\n@@gpu\n@@proc\n"
        outs = ["@@cpu\nCPUTIME 100 0 50 50 800\n" + base,
                "@@cpu\nCPUTIME 160 0 80 60 900\n" + base]
        with mock.patch.object(m, "run_script", side_effect=outs):
            m.snapshot("bsd")
            d = m.snapshot("bsd")
        self.assertAlmostEqual(d["cpu_pct"], 100.0 * (100 - 0) / 200 * 1)   # 忙 100 / 總 200


if __name__ == "__main__":
    unittest.main()
