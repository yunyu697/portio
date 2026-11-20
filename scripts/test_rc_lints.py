#!/usr/bin/env python3
"""rc.py 的 A32（格式与 lint 闸）单元测试。

这项是为一个真发生过的事立的：2026-11-19 本地回归全过，推上去 CI 红在 clippy
（run 44505662151），补跑 `cargo fmt --all` 与 clippy 才平掉。A1 只跑 `cargo test`，
而 CI 那关是 `fmt → clippy → test` 三道。这里钉住：两道都干净才算过、说到点子上
（文件名与行号 / clippy 的位置），而且不许拿「跑不起来」当通过。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

FMT_DIRTY = """Diff in \\\\?\\C:\\repo\\crates\\app\\src\\main.rs:12:
 fn main() {
-    let a = 1;
+    let a = 1;
Diff in \\\\?\\C:\\repo\\crates\\core\\src\\lib.rs:40:
"""

FMT_DIRTY_SAME_FILE_TWICE = """Diff in \\\\?\\C:\\repo\\crates\\core\\src\\lib.rs:36:
-pub fn x( )->i32{1}
Diff in \\\\?\\C:\\repo\\crates\\core\\src\\lib.rs:36:
+}
"""

CLIPPY_WARN = """warning: unused variable: `x`
  --> crates\\app\\src\\main.rs:33:9
   |
33 |     let x = 1;
   |         ^ help: if this is intentional, prefix it with an underscore
error: could not compile `portio-app` (bin \"portio-app\") due to 1 previous error
"""


class LintVerdictTest(unittest.TestCase):
    """两道都跑干净才 PASS。"""

    def test_both_clean_passes(self):
        status, detail = rc.lint_verdict((0, ""), (0, "Finished dev profile"))
        self.assertEqual(status, rc.PASS, detail)
        self.assertIn("clippy", detail)

    def test_fmt_dirty_names_file_and_line(self):
        status, detail = rc.lint_verdict((1, FMT_DIRTY), (0, ""))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("main.rs:12", detail)
        self.assertIn("lib.rs:40", detail)
        self.assertNotIn("等 ", detail)  # 只有两处时全部列出来，不写「等 N 处」
        self.assertIn("CI", detail)

    def test_fmt_dirty_without_diff_lines_still_fails(self):
        """输出认不出来也得 FAIL，别因为解析不到就判过。"""
        status, detail = rc.lint_verdict((2, "error: no such file or directory"), (0, ""))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("退出码 2", detail)

    def test_clippy_warning_names_spot(self):
        status, detail = rc.lint_verdict((0, ""), (101, CLIPPY_WARN))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("main.rs:33", detail)
        self.assertIn("clippy", detail)

    def test_clippy_error_without_spot_still_fails(self):
        status, detail = rc.lint_verdict((0, ""), (101, "error: could not compile"))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("退出码 101", detail)

    def test_both_dirty_reports_both(self):
        status, detail = rc.lint_verdict((1, FMT_DIRTY), (101, CLIPPY_WARN))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("fmt", detail)
        self.assertIn("clippy", detail)
        self.assertEqual(detail.count("；"), 1, detail)

    def test_does_not_treat_finished_as_pass_when_code_nonzero(self):
        """clippy 输出里带 Finished，但退出码非 0：不许当通过。"""
        status, detail = rc.lint_verdict((0, ""), (101, "Finished dev profile\n" + CLIPPY_WARN))
        self.assertEqual(status, rc.FAIL, detail)

    def test_none_and_empty_are_clean(self):
        status, _ = rc.lint_verdict((0, None), (0, None))
        self.assertEqual(status, rc.PASS)

    def test_many_spots_summary_counts(self):
        text = "".join(f"Diff in \\\\?\\C:\\repo\\crates\\x{i}.rs:1:\n" for i in range(5))
        status, detail = rc.lint_verdict((1, text), (0, ""))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("等 5 处", detail)

    def test_same_file_twice_counts_once(self):
        """同一个文件的两个 hunk：只报一次，别让「等 N 处」虚高。"""
        status, detail = rc.lint_verdict((1, FMT_DIRTY_SAME_FILE_TWICE), (0, ""))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("lib.rs:36", detail)
        self.assertNotIn("等 ", detail)
        self.assertEqual(rc.fmt_spots(FMT_DIRTY_SAME_FILE_TWICE), [
            "C:\\repo\\crates\\core\\src\\lib.rs:36",
        ])


    def test_many_clippy_spots_summary_counts(self):
        text = "".join(f"warning: w{i}\n  --> crates/x.rs:{i}:1\n" for i in range(4))
        status, detail = rc.lint_verdict((0, ""), (101, text))
        self.assertEqual(status, rc.FAIL, detail)
        self.assertIn("等 4 条", detail)


class LintPlanTest(unittest.TestCase):
    """这一项得出现在回归计划里，并且能单跑。"""

    def test_plan_has_a32_and_it_is_last_code(self):
        plan = [("A1", "x", True), ("A31", "y", True), ("A32", "z", True)]
        codes = [c for c, _, _ in plan]
        self.assertEqual(codes[-1], "A32")
        chosen, unknown = rc.select_items(plan, ["A32"])
        self.assertEqual([c for c, _, _ in chosen], ["A32"])
        self.assertEqual(unknown, [])

    def test_wrong_code_still_rejected(self):
        plan = [("A32", "z", True)]
        _, unknown = rc.select_items(plan, ["A33"])
        self.assertEqual(unknown, ["A33"])


if __name__ == "__main__":
    unittest.main()
