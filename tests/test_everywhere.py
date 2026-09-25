"""讓更多機器、更多介面用得上 slurmtop：--json、各種 GPU／作業系統、網頁、Prometheus、評估報告。"""

import json
import os
import re
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


NETSTAT_E_EN = """\
Interface Statistics

                           Received            Sent

Bytes                    3987654321       123456789
Unicast packets             1234567          654321
Non-unicast packets            4321             123
"""

NETSTAT_E_ZH = """\
介面統計資料

                           已接收              已傳送

位元組                    3987654321       123456789
單點傳播封包                 1234567          654321
"""


class Windows(unittest.TestCase):
    """Windows 本機：ctypes 讀 CPU／記憶體、netstat -e 讀網路，排成 REMOTE 的格式。

    這台是 macOS，Win32 API 的部分都用 mock 代替，需在 Windows 上實測。
    """

    def test_netstat_e(self):
        m = load()
        self.assertEqual(m.parse_netstat_e(NETSTAT_E_EN), (3987654321, 123456789))
        self.assertEqual(m.parse_netstat_e(NETSTAT_E_ZH), (3987654321, 123456789))
        self.assertIsNone(m.parse_netstat_e(""))

    def test_sections_parse_like_remote(self):
        import collections
        m = load()
        du = collections.namedtuple("du", "total used free")(512 * 1024 ** 3, 200 * 1024 ** 3,
                                                            312 * 1024 ** 3)
        gpu = "0, GPU-w, 35, 4096, 24576, 51, 120.5"
        a = m.win_sections((1000, 500, 8500), 16, (32 * 1024 ** 3, 12 * 1024 ** 3), gpu, "",
                           du, (1000, 2000))
        b = m.win_sections((1600, 700, 8700), 16, (32 * 1024 ** 3, 12 * 1024 ** 3), gpu, "",
                           du, (3000, 2500))
        with mock.patch.object(m, "run_script", side_effect=[a, b]), \
                mock.patch.object(m.time, "monotonic", side_effect=[10.0, 12.0]):
            m.snapshot("win")
            d = m.snapshot("win")
        self.assertAlmostEqual(d["cpu_pct"], 100.0 * 800 / 1000)   # 忙 (600+200) / 總 1000
        self.assertEqual((d["ncpu"], d["mem_total"], d["mem_used"]), (16, 32768, 12288))
        self.assertAlmostEqual(d["disk"]["pct"], 100 * 200 / 512)
        self.assertEqual(d["net"], (1000.0, 250.0))
        self.assertEqual(d["gpus"][0]["util"], 35)

    def test_local_windows_with_mocked_api(self):
        m = load()
        with mock.patch.object(m, "_win_cpu", return_value=(1, 2, 3)), \
                mock.patch.object(m, "_win_mem", side_effect=OSError("no windll")), \
                mock.patch.object(m.shutil, "which", return_value=None), \
                mock.patch.object(m, "_run", return_value=NETSTAT_E_EN):
            out = m.local_windows()
        secs = m.sections(out)
        self.assertEqual(secs["cpu"], "CPUTIME 1 0 2 0 3")
        self.assertEqual(secs["mem"], "0 0")                     # 讀失敗也不能讓整台掛掉
        self.assertEqual(secs["net"], "3987654321 123456789")
        self.assertEqual(secs["gpu"], "")

    def test_dispatch_and_ssh_args(self):
        m = load()
        with mock.patch.object(m.os, "name", "nt"), \
                mock.patch.object(m, "local_windows", return_value="@@gpu\n") as lw:
            self.assertEqual(m.run_script("localhost", m.REMOTE), "@@gpu\n")
        lw.assert_called_once()
        seen = []
        getuid = os.getuid
        try:
            del os.getuid                                        # Windows 沒有 getuid
            with mock.patch.object(m, "_run", side_effect=lambda argv, **kw: seen.append(argv) or ""), \
                    mock.patch.object(m, "is_local", return_value=False):
                m.run_script("gpu01", m.REMOTE)
        finally:
            os.getuid = getuid
        self.assertEqual(seen[0][0], "ssh")
        self.assertFalse(any("ControlMaster" in a for a in seen[0]))
        self.assertEqual(seen[0][-2], "gpu01")

    def test_hostname_on_windows(self):
        m = load()
        with mock.patch.object(m.os, "name", "nt"), \
                mock.patch.object(m.socket, "gethostname", return_value="WORKSTATION.corp.local"), \
                mock.patch.object(m, "sh") as sh:
            self.assertEqual(m.local_host(), "WORKSTATION")
        sh.assert_not_called()                               # 不能跑 "hostname -s"


class PlainAscii(unittest.TestCase):
    """輸出編碼畫不出方塊字（Windows 導向檔案、LANG=C）時不能掛掉，整個畫面改成 ASCII。"""

    def test_ascii_stdout(self):
        for args in (["--no-color"], [], ["--lang", "zh", "--no-color"], ["--dense", "--no-color"]):
            with self.subTest(args):
                p = run("full2x8", *args, PYTHONIOENCODING="ascii")
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertTrue(all(ord(c) < 128 for c in p.stdout))
                self.assertIn("SLURMTOP", p.stdout)

    def test_json_with_ascii_stdout(self):
        p = run("full2x8", "--json", PYTHONIOENCODING="ascii")
        self.assertEqual(p.returncode, 0, p.stderr)
        json.loads(p.stdout)

    def test_utf8_untouched(self):
        self.assertIn("╭", run("full2x8", "--no-color").stdout)


class WebDashboard(unittest.TestCase):
    """--web：真的起一個伺服器（埠號 0 = 讓系統挑），用 urllib 打每個端點。"""

    def start(self, scenario, *args):
        import subprocess, sys, re as _re
        from tests.helpers import SCRIPT, env
        e = env(scenario, 150, 40)
        p = subprocess.Popen([sys.executable, SCRIPT, "--web", "127.0.0.1:0", "-n", "0.5", *args],
                             env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (p.kill(), p.wait(), p.stdout.close(), p.stderr.close()))
        line = p.stdout.readline()
        m = _re.search(r"(http://127\.0\.0\.1:\d+/)", line)
        self.assertTrue(m, line + p.stderr.read() if p.poll() is not None else line)
        return m.group(1)

    def get(self, url, host=None):
        import urllib.request, urllib.error
        req = urllib.request.Request(url, headers={"Host": host} if host else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode("utf-8")

    def wait_state(self, base):
        import time
        for _ in range(100):
            code, _, body = self.get(base + "api/state")
            if code == 200:
                return json.loads(body)
            time.sleep(0.1)
        self.fail("no sample")

    def test_endpoints(self):
        base = self.start("idleheld", "--idle-samples", "1")
        d = self.wait_state(base)
        self.assertEqual(d["summary"]["gpus"], 16)
        self.assertEqual(d["interval"], 0.5)
        self.assertEqual(d["ui"]["w_util"], "GPU utilisation")
        code, h, page = self.get(base)
        self.assertEqual(code, 200)
        self.assertIn('src="app.js"', page)
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("<script>", page)                    # 沒有內嵌腳本，CSP 才擋得住注入
        code, h, js = self.get(base + "app.js")
        self.assertEqual((code, h["Content-Type"].split(";")[0]), (200, "text/javascript"))
        # 叢集來的字串一律 textContent；不能用任何會解析 HTML 的寫法
        self.assertIsNone(re.search(r"\.innerHTML|outerHTML|insertAdjacentHTML|document\.write", js))
        self.assertEqual(self.get(base + "app.css")[0], 200)
        self.assertEqual(self.get(base + "healthz")[2], "ok\n")
        self.assertEqual(self.get(base + "nope")[0], 404)
        code, _, metrics = self.get(base + "metrics")
        self.assertEqual(code, 200)
        self.assertIn('slurmtop_gpu_utilization_percent{node="n1",gpu="0",vendor="nvidia"} 91.0', metrics)
        self.assertIn('slurmtop_gpu_idle_held{node="n1",gpu="2",vendor="nvidia"} 1', metrics)
        self.assertIn('slurmtop_gpu_owner_info{node="n2",gpu="4",vendor="nvidia",job="1006_3",user="wu"} 1',
                      metrics)
        self.assertIn('slurmtop_jobs{state="R"} 4', metrics)

    def test_dns_rebinding_blocked(self):
        base = self.start("idle2x8")
        self.assertEqual(self.get(base + "api/state", host="evil.example:80")[0], 403)
        self.assertEqual(self.get(base + "api/state", host="attacker.localhost.evil")[0], 403)
        for ok in ("localhost:8765", "127.0.0.1", "[::1]:8765"):
            self.assertIn(self.get(base + "healthz", host=ok)[0], (200,), ok)

    def test_loading_before_first_sample(self):
        base = self.start("hang", "--node-timeout", "3")       # 第一次取樣要等 3 秒
        code, _, body = self.get(base + "api/state")
        self.assertEqual(code, 503)
        self.assertIn("first sample", json.loads(body)["message"])
        self.assertEqual(self.get(base + "metrics")[0], 503)

    def test_prometheus_escaping_and_nulls(self):
        m = load()
        text = m.prometheus({"nodes": [
            {"name": 'we"ird\\node\nx', "up": True, "stale_s": None, "cpu_pct": None, "load": [1, 2, 3],
             "mem_used_mib": 1, "mem_total_mib": 2, "disk": None, "net": None, "gpus": []},
            {"name": "down", "up": False, "stale_s": None}], "queue": []})
        self.assertIn('slurmtop_node_up{node="we\\"ird\\\\node\\nx"} 1', text)
        self.assertIn('slurmtop_node_up{node="down"} 0', text)
        self.assertNotIn("cpu_utilization_percent{", text)       # 讀不到的值不輸出
        for ln in text.splitlines():
            self.assertTrue(ln.startswith("#") or ln.startswith("slurmtop_"), ln)

    def test_parse_listen(self):
        m = load()
        self.assertEqual(m.parse_listen("8765"), ("127.0.0.1", 8765))
        self.assertEqual(m.parse_listen("0.0.0.0:9000"), ("0.0.0.0", 9000))
        self.assertEqual(m.parse_listen("[::1]:80"), ("::1", 80))
        for bad in ("", "abc", "1.2.3.4:", "::1:80"):
            with self.assertRaises(ValueError):
                m.parse_listen(bad)

    def test_js_syntax(self):
        import shutil, subprocess, tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        fd, path = tempfile.mkstemp(suffix=".js")
        with os.fdopen(fd, "w") as f:
            f.write(load().WEB_JS)
        self.addCleanup(os.remove, path)
        p = subprocess.run([node, "--check", path], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)


class HostileStrings(unittest.TestCase):
    """別人取的 job 名稱／使用者／行程名稱不能對我們的終端機發控制序列。"""

    def test_terminal(self):
        for args in (["--no-color", "--proc"], ["--proc"], ["--dense"], ["--flair", "--proc"]):
            with self.subTest(args):
                out = run("hostile", *args).stdout
                self.assertNotIn("\x1b]", out)                 # 沒有任何 OSC（剪貼簿、標題）
                self.assertNotIn("\x1b[2J", out)
                self.assertNotIn("\x07", out)
                if "--no-color" in args:
                    self.assertNotIn("\x1b", out)
                self.assertIn("evil]52", out)                  # 名稱照樣看得到（會被欄寬截斷），只是無害

    def test_json(self):
        d = as_json("hostile")
        self.assertEqual(d["queue"][0]["name"], "evil]52;c;cm0gLXJmIH4=job")
        self.assertEqual(d["queue"][0]["user"], "mal]0;pwnedlory")
        self.assertNotIn("\x1b", json.dumps(d, ensure_ascii=False))


def _m(t, util, power, idle=False, cpu=10.0, stale=None, job="7"):
    """組一筆最小的 model()，給 summarize() 用。"""
    return {"time": t, "cluster": "c", "summary": {"gpu_util": util},
            "nodes": [{"name": "n1", "up": True, "stale_s": stale, "cpu_pct": cpu, "mem_used_mib": 100,
                       "mem_total_mib": 1000, "gpus": [
                           {"index": "0", "vendor": "nvidia", "model": None, "util": util,
                            "mem_used_mib": 500, "mem_total_mib": 1000, "temp_c": 60,
                            "power_w": power, "job": job, "user": "u", "idle_held": idle}]}]}


class Report(unittest.TestCase):
    """--report／--html／--log：效能評估。"""

    def test_summarize_math(self):
        m = load()
        s = [_m(0, 0, 100, idle=True), _m(10, 50, 200, idle=True), _m(20, 100, 300), _m(30, None, None)]
        r = m.summarize(s)
        g = r["gpus"][0]
        self.assertEqual(r["seconds"], 30)
        self.assertEqual(g["util_avg"], 50.0)
        self.assertEqual(g["util_max"], 100)
        self.assertEqual(g["util_p95"], 100)
        self.assertEqual(g["busy_pct"], round(100 * 2 / 3, 1))
        self.assertEqual(g["power_avg_w"], 200.0)
        # 梯形法：(100+200)/2*10 + (200+300)/2*10 = 4000 J = 1.11 Wh
        self.assertEqual(g["energy_wh"], round(4000 / 3600, 2))
        self.assertEqual(g["idle_held_s"], 20)                  # 2 次 × 每次 10 秒
        self.assertEqual(r["nodes"][0]["cpu_avg"], 10.0)
        self.assertEqual(m.fmt_secs(20), "20s")
        self.assertEqual(m.fmt_secs(3700), "1h01m")
        self.assertEqual(m.fmt_secs(0), "-")

    def test_stale_samples_skipped(self):
        m = load()
        r = m.summarize([_m(0, 80, 100), _m(10, 80, 100, stale=10)])
        self.assertEqual(len(r["gpus"][0]["util_series"]), 1)

    def test_cli_duration(self):
        import tempfile
        html = tempfile.mktemp(suffix=".html")
        self.addCleanup(lambda: os.path.exists(html) and os.remove(html))
        p = run("full2x8", "--report", "0.6", "-n", "0.2", "--html", html)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("n1 G0", p.stdout)
        self.assertIn("98%", p.stdout)
        self.assertIn("cluster GPU average: 99.2%", p.stdout)
        with open(html, encoding="utf-8") as f:
            page = f.read()
        self.assertIn("<svg", page)
        self.assertNotIn("<script", page)                       # 報告頁不需要 JavaScript

    def test_cli_json(self):
        # 報告要算時間長度，這裡不能用固定的假時鐘
        p = run("idleheld", "--report", "0.4", "-n", "0.2", "--json", "--idle-samples", "1",
                SLURMTOP_FAKE_NOW="")
        r = json.loads(p.stdout)
        self.assertGreaterEqual(r["samples"], 2)
        self.assertEqual(len(r["gpus"]), 16)
        self.assertGreater(next(g for g in r["gpus"] if g["gpu"] == "2")["idle_held_s"], 0)

    def test_wrap_command(self):
        import tempfile
        html = tempfile.mktemp(suffix=".html")
        self.addCleanup(lambda: os.path.exists(html) and os.remove(html))
        p = run("full2x8", "--report", "-n", "0.2", "--html", html, "--",
                "sh", "-c", "sleep 0.5; exit 7", "<script>x</script>", "--")
        self.assertEqual(p.returncode, 7, p.stderr)              # 照指令的結束碼離開
        self.assertIn("(exit 7)", p.stdout)
        with open(html, encoding="utf-8") as f:
            page = f.read()
        self.assertIn("&lt;script&gt;", page)                  # 指令字串有跳脫
        self.assertNotIn("<script>x", page)

    def test_bad_args(self):
        self.assertEqual(run("full2x8", "stray").returncode, 2)
        self.assertEqual(run("full2x8", "--html", "x.html").returncode, 2)

    def test_csv_log(self):
        import csv, tempfile
        path = tempfile.mktemp(suffix=".csv")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        for _ in range(2):                                     # 第二次附加在後面，不重寫標題
            p = run("idleheld", "--report", "0.2", "-n", "0.2", "--log", path, "--idle-samples", "1")
            self.assertEqual(p.returncode, 0, p.stderr)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read().count("time,node,kind"), 1)
        nodes = [r for r in rows if r["kind"] == "node"]
        gpus = [r for r in rows if r["kind"] == "gpu"]
        self.assertEqual(len(gpus), 8 * len(nodes))
        g2 = next(r for r in gpus if r["node"] == "n1" and r["gpu"] == "2")
        self.assertEqual((g2["job"], g2["user"], g2["idle_held"], g2["util_pct"]), ("881", "lin", "1", "0.0"))

    def test_log_in_live_view(self):
        import csv, signal, subprocess, sys, tempfile, time
        from tests.helpers import SCRIPT, env
        path = tempfile.mktemp(suffix=".csv")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        p = subprocess.Popen([sys.executable, SCRIPT, "-n", "0.2", "--log", path, "--no-color"],
                             env=env("full2x8", 150, 40), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(1.2)
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        with open(path, newline="", encoding="utf-8") as f:
            self.assertGreaterEqual(len(list(csv.DictReader(f))), 2 * 17)


class Docs(unittest.TestCase):
    def test_readme_flags_exist(self):
        """README 提到的每個 --參數 都要真的存在，文件和程式不能對不起來。"""
        from tests.helpers import ROOT, SCRIPT
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        with open(SCRIPT, encoding="utf-8") as f:
            src = f.read()
        known = set(re.findall(r'add_argument\((?:"-\w", )?"(--[a-z-]+)"', src))
        used = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", readme))
        self.assertEqual(sorted(used - known - {"--help"}), [])

    def test_installers_point_at_the_script(self):
        from tests.helpers import ROOT
        for name in ("install.sh", "install.ps1"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                self.assertIn("Sean-Hawks/slurmtop/main/slurmtop", f.read(), name)


class WithoutSlurm(unittest.TestCase):
    """工作站、筆電：沒有 Slurm 就不要擺一個空的佇列，標題用主機名稱。"""

    def test_terminal(self):
        out = run("applesilicon", "--no-color", "--nodes", "m3").stdout
        self.assertNotIn("Slurm queue", out)
        self.assertIn("SLURMTOP // m3", out)
        # 有 Slurm 但沒有 job 的叢集照舊顯示 "(no jobs)"
        self.assertIn("(no jobs)", run("idle2x8", "--no-color").stdout)

    def test_json_and_web_flag(self):
        self.assertFalse(as_json("nogpu", "--nodes", "mac,cpu1")["slurm"])
        self.assertTrue(as_json("idle2x8")["slurm"])
        self.assertIn("d.slurm === false", load().WEB_JS)

    def test_qr_panel_without_slurm(self):
        p = run("nogpu", "--no-color", "--qr-panel", "--nodes", "mac,cpu1", cols=150)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("SCAN", p.stdout)


class ReportRobustness(unittest.TestCase):
    """第二次審查找到的 --report 問題：中斷、訊號、寫不進去的檔案、耗電跨過斷線。"""

    def popen(self, scenario, *args):
        import subprocess, sys
        from tests.helpers import SCRIPT, env
        e = env(scenario, 150, 40)
        e["SLURMTOP_FAKE_NOW"] = ""
        return subprocess.Popen([sys.executable, SCRIPT, *args], env=e, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def test_ctrl_c_before_first_sample(self):
        import signal, time
        p = self.popen("hang", "--report", "30", "--node-timeout", "3")
        time.sleep(1)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertNotIn("Traceback", err)
        self.assertEqual(p.returncode, 0, err)
        self.assertIn("n1 G0", out)                            # 中斷後補取一筆，照樣出報告

    def test_second_ctrl_c_kills_stubborn_child(self):
        import signal, subprocess, time, uuid
        marker = "stubborn-%s" % uuid.uuid4().hex[:8]
        p = self.popen("full2x8", "--report", "-n", "0.2", "--", "sh", "-c",
                       "trap '' INT TERM; exec -a %s sleep 30" % marker)
        time.sleep(1)
        p.send_signal(signal.SIGINT)
        time.sleep(0.5)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        self.assertNotIn("Traceback", err)
        time.sleep(0.3)
        left = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True).stdout
        self.assertEqual(left.strip(), "", "child left running")

    def test_signal_exit_code(self):
        p = run("full2x8", "--report", "-n", "0.2", "--", "sh", "-c", "kill -TERM $$",
                SLURMTOP_FAKE_NOW="")
        self.assertEqual(p.returncode, 143)                    # 跟 shell 一樣：128 + 15
        self.assertIn("killed by signal 15", p.stdout)

    def test_bad_output_paths_fail_before_running(self):
        import tempfile
        marker = tempfile.mktemp()
        for flag in ("--log", "--html"):
            with self.subTest(flag):
                p = run("full2x8", "--report", flag, "/nonexistent/dir/x", "--", "touch", marker)
                self.assertNotEqual(p.returncode, 0)
                self.assertNotIn("Traceback", p.stderr)
                self.assertIn("/nonexistent/dir/x", p.stderr)
                self.assertFalse(os.path.exists(marker), "command ran anyway")

    def test_energy_not_bridged_across_gaps(self):
        m = load()
        s = [_m(0, 50, 100), _m(10, 50, 100), _m(20, 50, 100), _m(1000, 50, 100), _m(1010, 50, 100)]
        r = m.summarize(s)
        # 步距是 (1010-0)/4 ≈ 252 秒，990 秒的空檔超過 2.5 倍，不算進去
        self.assertEqual(r["gpus"][0]["energy_wh"], round((100 * 10 * 3) / 3600, 2))


class WebErrors(unittest.TestCase):
    """--web 的位址不對、埠被佔、紀錄檔開不了：一行錯誤訊息，不是 traceback。"""

    def check(self, *args):
        p = run("idle2x8", *args, timeout=20)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertNotIn("Traceback", p.stderr)
        self.assertIn("slurmtop: cannot serve on", p.stderr)
        return p.stderr

    def test_bad_address(self):
        self.check("--web", "abc")

    def test_port_in_use(self):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        self.addCleanup(s.close)
        self.check("--web", "127.0.0.1:%d" % s.getsockname()[1])

    def test_bad_log_path(self):
        self.assertIn("/nonexistent/x.csv", self.check("--web", "127.0.0.1:0", "--log", "/nonexistent/x.csv"))

    def test_idle_connections_time_out(self):
        m = load()
        self.assertEqual(m.web_handler({}, "127.0.0.1").timeout, 30)


if __name__ == "__main__":
    unittest.main()
