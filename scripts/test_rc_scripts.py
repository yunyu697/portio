#!/usr/bin/env python3
"""rc.py 的 A35（「CI 里跑的那一步，整跑也得跑」）单测。

补的洞：`scripts/test_*.py` 这一批（154 条）只在 CI 的 ci.yml 里跑，
本地整跑 A1–A34 一条都没跑过。改完 `rc.py` 忘了跑对应的 `test_rc_*.py`，
本地全绿、推上去 CI 才红——跟 RC3 定下的「本地的绿要等于 CI 的绿」正相反。

判定上不许留「没查到问题就算过」的口子：`Ran 0 tests`、「压根没解析到条数」
都必须红，因为那正是「假装跑过」。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

P, F = rc.PASS, rc.FAIL

OK_154 = """
......................................................................s
----------------------------------------------------------------------
Ran 154 tests in 0.751s

OK (skipped=1)
"""


class VerdictTest(unittest.TestCase):
    def test_counts_what_actually_ran(self):
        status, detail = rc.script_test_verdict(0, OK_154)
        self.assertEqual(status, P)
        self.assertIn("154 条通过", detail)

    def test_skipped_is_named_not_swallowed(self):
        """按平台跳过的条数要写明，否则「154 条」会被读成「全跑过」。"""
        _, detail = rc.script_test_verdict(0, OK_154)
        self.assertIn("跳 1 条", detail)

    def test_no_skip_means_no_noise(self):
        _, detail = rc.script_test_verdict(0, "Ran 3 tests in 0.01s\n\nOK\n")
        self.assertNotIn("跳", detail)

    def test_failed_run_is_fail(self):
        out = "Ran 154 tests in 0.9s\n\nFAILED (failures=2)\n"
        status, detail = rc.script_test_verdict(1, out)
        self.assertEqual(status, F)
        self.assertIn("退出码 1", detail)

    def test_zero_tests_is_fail(self):
        """discover 一条都没找到，正是「假装跑过」的典型样子。"""
        status, detail = rc.script_test_verdict(0, "Ran 0 tests in 0.000s\n\nOK\n")
        self.assertEqual(status, F)
        self.assertIn("一条都没跑到", detail)

    def test_missing_ran_line_is_fail(self):
        status, detail = rc.script_test_verdict(0, "OK\n")
        self.assertEqual(status, F)
        self.assertIn("Ran N tests", detail)

    def test_crash_without_ok_is_fail(self):
        status, detail = rc.script_test_verdict(0, "Traceback (most recent call last):\nboom\n")
        self.assertEqual(status, F)
        self.assertIn("OK", detail)


class WiredTest(unittest.TestCase):
    def test_a35_is_actually_wired_into_the_plan(self):
        source = Path(rc.__file__).read_text(encoding="utf-8")
        self.assertIn('("A35",', source, "计划表里要有这一项")
        self.assertIn("a35_script_tests()", source.split('("A35",')[1])
        self.assertIn('elif code == "A35":', source, "分派链里真要有这一支")

    def test_same_discover_command_as_ci(self):
        """口径必须跟 CI 那一步一样，否则本地这块绿对不上 CI。"""
        source = Path(rc.__file__).read_text(encoding="utf-8")
        ci = Path(rc.__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
        want = 'unittest discover -s scripts -p "test_*.py"'
        self.assertIn("unittest", source)
        for piece in ('"-m"', '"unittest"', '"discover"', '"-s"', '"scripts"', '"test_*.py"'):
            self.assertIn(piece, source, f"discover 调用缺 {piece}")
        self.assertIn(want, ci.read_text(encoding="utf-8"), "CI 那边也得还是这一条")


if __name__ == "__main__":
    unittest.main(verbosity=2)
