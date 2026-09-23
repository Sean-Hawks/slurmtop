"""第 3 步：一般伺服器（--ssh-config、磁碟與網路、警示列、密集檢視）。"""

import os
import tempfile
import unittest
from unittest import mock

from tests.helpers import fixture, load, run

SSH_CONFIG = """\
# 我的機器
Host gpu1 gpu2
    HostName 10.0.0.1
    User hawks

host=lab-box   # 等號寫法、小寫
  Port 2222

Host *.internal
    ProxyJump bastion
Host gpu? !gpu3 "quoted-box"
Host *
    ServerAliveInterval 30

Match host foo exec "true"
    User nobody

  Host gpu1
Include ~/.ssh/config.d/*
"""


class SshConfig(unittest.TestCase):
    def setUp(self):
        self.m = load()
        fd, self.path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(SSH_CONFIG)
        self.addCleanup(os.remove, self.path)

    def test_hosts(self):
        self.assertEqual(self.m.ssh_config_hosts(self.path),
                         ["gpu1", "gpu2", "lab-box", "quoted-box"])

    def test_missing_file(self):
        self.assertEqual(self.m.ssh_config_hosts("/nonexistent/ssh_config"), [])

    def test_pick_nodes(self):
        m = self.m
        self.assertEqual(m.pick_nodes(m.parse_args(["--ssh-config", self.path])),
                         ["gpu1", "gpu2", "lab-box", "quoted-box"])
        # 跟 --nodes 合併、去重，--nodes 的在前面
        self.assertEqual(m.pick_nodes(m.parse_args(["--nodes", "x,gpu2", "--ssh-config", self.path])),
                         ["x", "gpu2", "gpu1", "lab-box", "quoted-box"])
        self.assertEqual(m.pick_nodes(m.parse_args(["--nodes", "a,b"])), ["a", "b"])

    def test_default_path(self):
        self.assertEqual(self.m.parse_args(["--ssh-config"]).ssh_config, "~/.ssh/config")
        self.assertIsNone(self.m.parse_args([]).ssh_config)

    def test_slurm_discovery_kept(self):
        m = self.m
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("full2x8")}):
            self.assertEqual(m.pick_nodes(m.parse_args([])), ["n1", "n2"])

    def test_cli(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write("Host n1\nHost n2\nHost *\n")
        self.addCleanup(os.remove, path)
        out = run("idle2x8", "--no-color", "--ssh-config", path).stdout
        self.assertIn("NODE n1", out)
        self.assertIn("NODE n2", out)



PROC_NET_DEV = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 99999999  100    0    0    0     0          0         0 99999999  100    0    0    0     0       0          0
  eth0: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0
enp1s0f0:123456789012 5 0 0 0 0 0 0 98765432109 6 0 0 0 0 0 0
   ib0: 500 1 0 0 0 0 0 0 700 1 0 0 0 0 0 0
docker0: 88888 1 0 0 0 0 0 0 88888 1 0 0 0 0 0 0
vethab12: 77777 1 0 0 0 0 0 0 77777 1 0 0 0 0 0 0
"""

NETSTAT_IBN = """\
Name       Mtu   Network       Address            Ipkts Ierrs     Ibytes    Opkts Oerrs     Obytes  Coll
lo0        16384 <Link#1>                         62273     0   14830358    62273     0   14830358     0
lo0        16384 127           127.0.0.1          62273     -   14830358    62273     -   14830358     -
en0        1500  <Link#11>   a4:83:e7:00:00:01  9000000     0 7000000000  4000000     0  500000000     0
en0        1500  192.168.1     192.168.1.20     9000000     -     700000  4000000     -      50000     -
en5        1500  <Link#14>                          10     0       1000       10     0       2000     0
utun0      1500  <Link#13>                            0     0          0        1     0        100     0
bridge0    1500  <Link#12>   36:25:8c:fe:6b:80        5     0     555555        5     0     555555     0
"""


class DiskAndNet(unittest.TestCase):
    """第 3 步第 2 項：根目錄磁碟使用率和網路收發速度。"""

    def setUp(self):
        self.m = load()

    def net_segment(self):
        return self.m.REMOTE.split("echo '@@net'")[1]      # 最後一段

    def run_bash(self, script):
        import subprocess
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stderr, "")
        return p.stdout.strip()

    def test_linux_proc_net_dev(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(PROC_NET_DEV)
        self.addCleanup(os.remove, path)
        seg = self.net_segment().replace("/proc/net/dev", path)
        # 只算實體網卡：eth0 + enp1s0f0（名字長到冒號黏在數字上）+ ib0
        self.assertEqual(self.run_bash(seg), "%d %d" % (1000 + 123456789012 + 500,
                                                        2000 + 98765432109 + 700))

    def test_macos_netstat(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(NETSTAT_IBN)
        self.addCleanup(os.remove, path)
        seg = self.net_segment().replace("[ -r /proc/net/dev ]", "false") \
                                .replace("netstat -ibn 2>/dev/null", "cat " + path)
        # en0 的 <Link> 行（11 欄）+ en5（沒有 MAC，10 欄）；lo0、utun、bridge 不算
        self.assertEqual(self.run_bash(seg), "%d %d" % (7000000000 + 1000, 500000000 + 2000))

    def test_parse(self):
        m = self.m
        d = m.parse_disk("1000 900 50")
        self.assertAlmostEqual(d["pct"], 100 * 900 / 950)
        self.assertEqual(d["total"], 1000 * 1024)
        self.assertIsNone(m.parse_disk(""))
        self.assertIsNone(m.parse_disk("0 0 0"))
        self.assertIsNone(m.parse_disk("x y z"))
        self.assertEqual(m.parse_net("10 20"), (10.0, 20.0))
        self.assertIsNone(m.parse_net(""))

    def test_rate(self):
        m = self.m
        self.assertEqual(m.net_rate((0, 0), (2048, 1024), 2), (1024, 512))
        self.assertIsNone(m.net_rate((5000, 0), (10, 10), 2))      # 計數器歸零
        self.assertIsNone(m.net_rate((0, 0), (10, 10), 0))

    def test_fmt_bytes(self):
        f = self.m.fmt_bytes
        self.assertEqual(f(512), "512")
        self.assertEqual(f(1536), "1.5K")
        self.assertEqual(f(1024 ** 3 * 1.7), "1.7G")
        self.assertEqual(f(1024 ** 2 * 300, "/s"), "300M/s")
        self.assertEqual(f(None), "-")

    def test_rate_from_two_snapshots(self):
        m = self.m
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("seq")}), \
                mock.patch.object(m.time, "monotonic", side_effect=[100.0, 102.0]):
            a = m.snapshot("n1")
            b = m.snapshot("n1")
        self.assertIsNone(a["net"])
        self.assertEqual(b["net"], ((3097152 - 1000000) / 2, (2204800 - 2000000) / 2))

    def test_panel_line(self):
        out = run("full2x8", "--no-color").stdout
        dsk = [ln for ln in out.splitlines() if "DSK" in ln]
        self.assertEqual(len(dsk), 1)                    # 兩台並排在同一行
        self.assertIn("42.0%", dsk[0])
        self.assertIn("NET -", dsk[0])                   # --once 只有一次取樣

    def test_macos_data_volume(self):
        out = run("nogpu", "--no-color", "--nodes", "mac,cpu1").stdout
        self.assertIn("52.1%", out)


if __name__ == "__main__":
    unittest.main()
