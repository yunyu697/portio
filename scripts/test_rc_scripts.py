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


class ResourceTest(unittest.TestCase):
    """A1 第一次挂在「机器扛不住」时要能认出来，别把环境问题报成代码问题。"""

    def test_llvm_oom_is_recognised(self):
        self.assertTrue(rc.resource_bad("rustc-LLVM ERROR: out of memory"))

    def test_windows_pagefile_error_is_recognised(self):
        self.assertTrue(rc.resource_bad(
            "failed to mmap file 'libtest.rlib': 页面文件太小，无法完成操作。 (os error 1455)"))

    def test_real_compile_error_is_not_a_resource_problem(self):
        self.assertFalse(rc.resource_bad(
            "error[E0308]: mismatched types --> crates/core/src/lib.rs:12:5"))

    def test_empty_output_is_not_a_resource_problem(self):
        self.assertFalse(rc.resource_bad(""))
        self.assertFalse(rc.resource_bad(None))

    def test_reason_names_the_runtime_problem(self):
        self.assertIn("out of memory", rc.resource_reason("rustc-LLVM ERROR: out of memory"))
        self.assertIn("os error 1455", rc.resource_reason("(os error 1455): 页面文件太小"))

    def test_reason_falls_back(self):
        self.assertIn("资源不足", rc.resource_reason("cannot allocate memory"))


class A1RetryWiredTest(unittest.TestCase):
    def setUp(self):
        self.text = Path(rc.__file__).read_text(encoding="utf-8")

    def test_retry_ladder_is_at_most_two_steps(self):
        self.assertEqual(rc.A1_RETRY_JOBS, (2, 1))

    def test_only_resource_failures_are_retried(self):
        body = self.text.split("def a1_cargo_test", 1)[1]
        self.assertIn("resource_bad(proc.stdout + proc.stderr)", body)
        self.assertIn("绝不拿「降并行度重跑」糊过去", body)

    def test_retry_keeps_the_same_command(self):
        body = self.text.split("def a1_cargo_test", 1)[1]
        self.assertIn('run([cargo, "test", "--workspace"]', body)
        self.assertIn('run([cargo, "test", "--workspace", "-j", str(jobs)]', body)

    def test_pass_detail_says_it_retried(self):
        body = self.text.split("def a1_cargo_test", 1)[1]
        self.assertIn("if note else", body)

    def test_failure_keeps_more_context(self):
        # 上一次就是因为 tail 只留 4 行，真正的错误被截没了，只剩一段 "^" 标记
        body = self.text.split("def a1_cargo_test", 1)[1]
        self.assertIn("tail(proc.stdout + proc.stderr, 8)", body)


OOM_OUT = """   Compiling portio-app v1.0.9-RC5
rustc-LLVM ERROR: out of memory
error[E0786]: found invalid metadata files for crate `test`
    = note: failed to mmap file 'libtest.rlib': 页面文件太小，无法完成操作。 (os error 1455)
error: could not compile `portio-ssh` (example "smoke")
"""

OK_OUT = """test result: ok. 47 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.38s
test result: ok. 25 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.73s
"""


class RetryFlowTest(unittest.TestCase):
    """撞上「机器扛不住」时真的会降并行度重跑，而且结论里会说明——整条链路跑一遍。"""

    def _fake_run(self, replies):
        calls = []

        class R:
            def __init__(self, code, out):
                self.returncode, self.stdout, self.stderr = code, out, ""

        def run(cmd, timeout, cwd=None, env=None):
            calls.append(cmd)
            reply = replies[min(len(calls) - 1, len(replies) - 1)]
            return R(*reply)

        return run, calls

    def test_oom_then_success_is_pass_with_note(self):
        run, calls = self._fake_run([(101, OOM_OUT), (0, OK_OUT)])
        old = rc.run
        rc.run = run
        try:
            status, detail = rc.a1_cargo_test()
        finally:
            rc.run = old
        self.assertEqual(status, rc.PASS)
        self.assertIn("72 passed, 0 failed", detail)
        self.assertIn("机器扛不住", detail)
        self.assertIn("降到 2 路重跑", detail)
        self.assertIn("-j", calls[1])

    def test_code_error_is_not_retried(self):
        # 报的是代码问题就不许重跑：否则等于拿重试把真的红糊过去
        run, calls = self._fake_run([
            (101, "error[E0308]: mismatched types --> crates/core/src/lib.rs:12:5\n"), (0, OK_OUT)])
        old = rc.run
        rc.run = run
        try:
            status, detail = rc.a1_cargo_test()
        finally:
            rc.run = old
        self.assertEqual(status, rc.FAIL)
        self.assertEqual(len(calls), 1)
        self.assertIn("mismatched types", detail)

    def test_oom_all_the_way_down_is_still_fail(self):
        run, calls = self._fake_run([(101, OOM_OUT), (101, OOM_OUT), (101, OOM_OUT)])
        old = rc.run
        rc.run = run
        try:
            status, _ = rc.a1_cargo_test()
        finally:
            rc.run = old
        self.assertEqual(status, rc.FAIL)
        self.assertEqual(len(calls), 3)  # 默认 → 2 路 → 1 路，不再往下拖


if __name__ == "__main__":
    unittest.main(verbosity=2)
