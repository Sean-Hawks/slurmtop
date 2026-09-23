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

    def test_linux_bond_and_vlan_not_double_counted(self):
        """bond0 = eth0 + eth1；eth0.100 是 VLAN、ib0.8001 是 IPoIB 子介面，只算上層那張卡。"""
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp)
        for nic in ("eth0", "eth1"):
            os.makedirs(os.path.join(tmp, "sys", nic))
            os.symlink("../bond0", os.path.join(tmp, "sys", nic, "master"))
        os.makedirs(os.path.join(tmp, "sys", "bond0"))
        dev = os.path.join(tmp, "dev")
        with open(dev, "w") as f:
            f.write(PROC_NET_DEV.splitlines()[0] + "\n" + PROC_NET_DEV.splitlines()[1] + "\n"
                    "  bond0: 3000 1 0 0 0 0 0 0 6000 1 0 0 0 0 0 0\n"
                    "   eth0: 1000 1 0 0 0 0 0 0 2000 1 0 0 0 0 0 0\n"
                    "   eth1: 2000 1 0 0 0 0 0 0 4000 1 0 0 0 0 0 0\n"
                    "eth0.100: 500 1 0 0 0 0 0 0 500 1 0 0 0 0 0 0\n"
                    "    ib0: 700 1 0 0 0 0 0 0 900 1 0 0 0 0 0 0\n"
                    "ib0.8001: 70 1 0 0 0 0 0 0 90 1 0 0 0 0 0 0\n")
        seg = self.net_segment().replace("/proc/net/dev", dev) \
                                .replace("/sys/class/net", os.path.join(tmp, "sys"))
        self.assertEqual(self.run_bash(seg), "%d %d" % (3000 + 700, 6000 + 900))

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


class AlertLine(unittest.TestCase):
    """第 3 步第 3 項：頂端警示列（斷線、磁碟 ≥90%、GPU 過熱、佔著卻閒置），沒問題就不顯示。"""

    def test_everything_listed_in_order(self):
        out = run("alerts", "--no-color", "--idle-samples", "1").stdout.splitlines()
        self.assertEqual(out[4].strip(),
                         "⚠ n3 unreachable · n1 G3,G5 hot 84°C · n1 disk 95% · "
                         "n2 G6 held but idle (886 wu)")

    def test_zh(self):
        out = run("alerts", "--no-color", "--idle-samples", "1", "--lang", "zh").stdout
        self.assertIn("n3 斷線 · n1 G3,G5 過熱 84°C · n1 磁碟 95%", out)

    def test_overflow_collapses(self):
        out = run("alerts", "--no-color", "--idle-samples", "1", cols=80).stdout.splitlines()
        self.assertTrue(out[4].rstrip().endswith("+1 more"), out[4])
        self.assertLessEqual(len(out[4]), 80)

    def test_hidden_when_fine(self):
        for scn in ("full2x8", "idle2x8", "nogpu"):
            out = run(scn, "--no-color", "--idle-samples", "1", "--nodes",
                      "mac,cpu1" if scn == "nogpu" else "n1,n2").stdout
            self.assertNotIn("⚠", out, scn)

    def test_thresholds(self):
        m = load()
        m._color = False
        g = lambda t: m.parse_gpu("0, GPU-a, 50, 1, 2, %s, 100" % t)
        base = {"cpu_pct": 0.0, "load": [0, 0, 0], "ncpu": 1, "mem_total": 1, "mem_used": 0,
                "procs": []}
        cool = dict(base, gpus=[g(77)], disk={"pct": 89.9, "total": 1, "used": 1})
        warm = dict(base, gpus=[g(78)], disk={"pct": 90.0, "total": 1, "used": 1})
        na = dict(base, gpus=[g("[N/A]")], disk=None)
        self.assertEqual(m.alerts(["a", "b"], [cool, na]), [])
        texts = [t for _, t in m.alerts(["a"], [warm])]
        self.assertEqual(texts, ["a G0 hot 78°C", "a disk 90%"])

    def test_stale_listed(self):
        m = load()
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("hang"),
                                          "SLURMTOP_FAKE_NOW": "1000",
                                          "COLUMNS": "150", "LINES": "40"}):
            with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("idle2x8")}):
                snap = m.snapshot("n2")
            m._last[("node", "n2")] = (snap, 1000 - 12)
            m._color = False
            out = m.render(["n1", "n2"], node_timeout=0.2).splitlines()
        self.assertEqual(out[4].strip(), "⚠ n2 stale 12s")


def col(line, needle):
    import unicodedata
    i = line.index(needle)
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line[:i])


class DenseView(unittest.TestCase):
    """第 3 步第 4 項：節點多到放不下（或 --dense）時一台一行。"""

    def node_rows(self, out):
        lines = out.splitlines()
        start = next(i for i, ln in enumerate(lines) if "NODES" in ln or "節點" in ln)
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("╰"))
        return lines[start + 1:end]

    def test_auto_when_too_many(self):
        out = run("many", "--no-color", cols=150, lines=45).stdout
        self.assertNotIn("NODE gpu01", out)               # 沒有一般的節點面板
        rows = self.node_rows(out)
        self.assertEqual(len(rows), 16)
        self.assertIn("unreachable", rows[6])            # gpu07
        cpu_cols = set(col(r, "CPU") for r in rows if "CPU" in r)
        self.assertEqual(len(cpu_cols), 1)                # 各欄對齊
        self.assertEqual(len(set(col(r, "DSK") for r in rows if "DSK" in r)), 1)

    def test_not_dense_when_it_fits(self):
        for scn in ("full2x8", "idle2x8"):
            out = run(scn, "--no-color", cols=150, lines=45).stdout
            self.assertIn("NODE n1", out)
            self.assertNotIn("NODES", out)

    def test_flag(self):
        out = run("idleheld", "--no-color", "--dense", "--idle-samples", "1").stdout
        rows = self.node_rows(out)
        self.assertEqual(len(rows), 2)
        self.assertIn("IDLE 6", rows[0])                  # n1 有 6 張佔著卻閒置
        self.assertIn("GPU 2/8", rows[0])

    def test_tall_terminal_goes_back_to_panels(self):
        out = run("many", "--no-color", cols=150, lines=200).stdout
        self.assertIn("NODE gpu01", out)

    def test_threshold(self):
        m = load()
        with mock.patch.dict(os.environ, {"SLURMTOP_FIXTURES": fixture("full2x8")}):
            snaps = [m.snapshot("n1"), m.snapshot("n2")]
        h = m.panels_height(["n1", "n2"], snaps, None, 150, False, False, True)
        opt = m.options()
        self.assertFalse(m.want_dense(opt, ["n1", "n2"], snaps, None, 150, h + m.DENSE_RESERVE, True))
        self.assertTrue(m.want_dense(opt, ["n1", "n2"], snaps, None, 150, h + m.DENSE_RESERVE - 1, True))
        self.assertFalse(m.want_dense(opt, ["n1"], snaps[:1], None, 150, 5, True))   # 只有一台不算
        self.assertTrue(m.want_dense(m.options(dense=True), ["n1"], snaps[:1], None, 150, 99, True))

    def test_zh_and_nogpu(self):
        out = run("nogpu", "--no-color", "--dense", "--lang", "zh", "--nodes", "mac,cpu1,ghost",
                  cols=100).stdout
        rows = self.node_rows(out)
        self.assertIn("無 GPU", rows[0])
        self.assertIn("連不上", rows[2])

    def test_short_queue_stays_single_column(self):
        out = run("many", "--no-color", cols=150, lines=45).stdout
        header = next(ln for ln in out.splitlines() if "USER" in ln)
        self.assertEqual(header.count("USER"), 1)


if __name__ == "__main__":
    unittest.main()
