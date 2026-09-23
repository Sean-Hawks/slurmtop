"""測試共用的小工具：載入 slurmtop 模組、用假資料跑一次 --once。"""

import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "slurmtop")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
GOLDEN = os.path.join(ROOT, "tests", "golden")
FAKE_NOW = "1790000000"          # 2026-09-21 14:13:20 UTC，畫面上的時鐘固定在這裡
ANSI = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")


def load():
    """每次載入一份全新的模組，模組層級的狀態（歷史、快取）不會在測試之間互相污染。"""
    loader = importlib.machinery.SourceFileLoader("slurmtop_under_test", SCRIPT)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def fixture(scenario):
    return os.path.join(FIXTURES, scenario)


def env(scenario=None, cols=150, lines=60, **extra):
    e = {k: v for k, v in os.environ.items()
         if not k.startswith("SLURMTOP_") and k not in ("LANG", "LC_ALL", "LC_CTYPE")}
    e.update(COLUMNS=str(cols), LINES=str(lines), TZ="UTC", LANG="C.UTF-8",
             PYTHONIOENCODING="utf-8", SLURMTOP_FAKE_NOW=FAKE_NOW, SLURMTOP_FAKE_TICK="0",
             USER="hawks", LOGNAME="hawks")
    if scenario:
        e["SLURMTOP_FIXTURES"] = fixture(scenario)
    e.update({k: str(v) for k, v in extra.items()})
    return e


def run(scenario, *args, cols=150, lines=60, timeout=60, python=None, **extra):
    """跑 `slurmtop --once <args>`，回傳 CompletedProcess。"""
    return subprocess.run([python or sys.executable, SCRIPT, "--once", *args],
                          env=env(scenario, cols, lines, **extra),
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout)


def strip(s):
    return ANSI.sub("", s)
