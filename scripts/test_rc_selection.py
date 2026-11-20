#!/usr/bin/env python3
"""rc.py 里「只跑其中几项」的单元测试。

以前 `python scripts/rc.py A11` 会被 argparse 当成不认识的参数直接退出，
于是「改一项、核一项」这条最常用的动作只能靠整跑几十秒到两三分钟的代餐；
更糟的是有人会随手改成「把没写全的编号静悄悄忽略」，那写错一个字母就等于
什么都没跑却看着像跑过了。下面这些用例钉住：拆分规则、只跑选中的、
顺序跟计划表一致、写错的编号必须点名而不是忽略。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402


PLAN = [
    ("A1", "cargo test", True),
    ("A2", "node --check", True),
    ("A10", "PE 子系统", True),
    ("A11", "安装包", True),
]


class SplitIdsTest(unittest.TestCase):
    """编号拆分：大小写、逗号（含全角）、空格、重复。"""

    def test_space_separated(self):
        self.assertEqual(rc.split_ids(["A10", "A11"]), ["A10", "A11"])

    def test_comma_separated(self):
        self.assertEqual(rc.split_ids(["A10,A11"]), ["A10", "A11"])

    def test_fullwidth_comma(self):
        """中文输入法下逗号是全角的，照收，不然报错会很莫名其妙。"""
        self.assertEqual(rc.split_ids(["A10，A11"]), ["A10", "A11"])

    def test_lowercase_and_blanks(self):
        self.assertEqual(rc.split_ids([" a10 ", ""]), ["A10"])

    def test_duplicates_collapse(self):
        self.assertEqual(rc.split_ids(["A10", "A10,A11"]), ["A10", "A11"])

    def test_empty_is_empty(self):
        self.assertEqual(rc.split_ids([]), [])


class SelectItemsTest(unittest.TestCase):
    """挑项：空 = 全跑；选中项按计划表顺序；写错的编号要报出来。"""

    def test_empty_runs_everything(self):
        chosen, unknown = rc.select_items(PLAN, [])
        self.assertEqual(chosen, PLAN)
        self.assertEqual(unknown, [])

    def test_single_item(self):
        chosen, unknown = rc.select_items(PLAN, ["A11"])
        self.assertEqual([code for code, _, _ in chosen], ["A11"])
        self.assertEqual(unknown, [])

    def test_order_follows_plan_not_input(self):
        """用户写 A11 A10 也按计划表顺序跑——报告顺序和清单一致才好对照。"""
        chosen, _ = rc.select_items(PLAN, ["A11", "A10"])
        self.assertEqual([code for code, _, _ in chosen], ["A10", "A11"])

    def test_unknown_ids_are_named(self):
        chosen, unknown = rc.select_items(PLAN, ["A10", "A31", "0011"])
        self.assertEqual([code for code, _, _ in chosen], ["A10"])
        self.assertEqual(unknown, ["A31", "0011"])

    def test_all_unknown_yields_nothing(self):
        chosen, unknown = rc.select_items(PLAN, ["A99"])
        self.assertEqual(chosen, [])
        self.assertEqual(unknown, ["A99"])

    def test_plan_shape_is_kept(self):
        """选中的项连 label 与开关状态一起带过去，主流程不用再拼。"""
        chosen, _ = rc.select_items(PLAN, ["A2"])
        self.assertEqual(chosen, [("A2", "node --check", True)])

    def test_real_plan_has_these_ids(self):
        """真实计划表里 A10 / A11 都在（防有人改名后这两条静悄悄消失）。

        直接拿脚本 `--list` 的输出核对，比在测试里复刻一份计划表可靠。
        """
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc.main(["--list"])
        listed = buf.getvalue().split()
        for code in ("A1", "A10", "A11", "A30"):
            self.assertIn(code, listed, f"--list 里没有 {code}")


if __name__ == "__main__":
    unittest.main()
