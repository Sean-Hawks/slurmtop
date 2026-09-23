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


if __name__ == "__main__":
    unittest.main()
