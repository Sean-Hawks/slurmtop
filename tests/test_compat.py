"""slurmtop 必須是「單一檔案、只用標準函式庫、Python 3.8 相容」，install.sh 和 curl 安裝靠這個。

這台機器沒有 3.8 可跑，所以用 ast 的 feature_version=(3, 8) 檢查語法，再掃一遍
3.9 以後才有的 API。實際跑測試的最低版本是 macOS 內建的 /usr/bin/python3（3.9）。
"""

import ast
import sys
import unittest

from tests.helpers import SCRIPT

# 3.9 以後才加入、3.8 沒有的東西（屬性名 / 模組名 / 關鍵字參數）
NEW_ATTRS = {"removeprefix", "removesuffix", "bit_count", "randbytes", "to_thread",
             "lcm", "unparse", "cache", "is_relative_to", "with_stem", "readlink"}
NEW_MODULES = {"zoneinfo", "graphlib", "tomllib"}
STDLIB = {"argparse", "concurrent", "getpass", "math", "os", "re", "shutil", "subprocess",
          "sys", "threading", "time", "collections", "unicodedata", "signal", "shlex",
          "itertools", "functools", "json", "atexit", "platform", "socket", "errno"}


class Compat(unittest.TestCase):
    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as f:
            self.src = f.read()
        self.tree = ast.parse(self.src, feature_version=(3, 8))

    def test_py38_syntax(self):
        ast.parse(self.src, feature_version=(3, 8))

    def test_no_py39_apis(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, NEW_ATTRS, f"line {node.lineno}: .{node.attr} is 3.9+")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "zip" and any(k.arg == "strict" for k in node.keywords):
                self.fail(f"line {node.lineno}: zip(strict=) is 3.10+")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) \
                    else [node.module or ""]
                for n in names:
                    self.assertNotIn(n.split(".")[0], NEW_MODULES, f"line {node.lineno}: {n}")
            # list[int] 之類的內建泛型在 3.8 執行時會炸
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                    and node.value.id in ("list", "dict", "set", "tuple", "type"):
                self.fail(f"line {node.lineno}: builtin generic {node.value.id}[...] is 3.9+")

    def test_stdlib_only_single_file(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative import - must stay a single file")
                mods = [node.module]
            elif isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            else:
                continue
            for mod in mods:
                top = mod.split(".")[0]
                if hasattr(sys, "stdlib_module_names"):
                    self.assertIn(top, sys.stdlib_module_names, f"{mod} is not stdlib")
                else:
                    self.assertIn(top, STDLIB, f"{mod} is not in the known stdlib list")

    def test_install_sh_check_passes(self):
        """install.sh 下載後用 ast.parse 驗證，這裡做一樣的事。"""
        ast.parse(self.src)


if __name__ == "__main__":
    unittest.main()
