#!/usr/bin/env python3
"""rc.py 的结论判定（`summarize`）单测。

这一项钉住的是「什么才算绿」：
- 每一项都真跑过且过 → 退出码 0；
- 有 FAIL → 1，先把失败项与怎么修说清楚；
- 没有 FAIL、但有**没跑**的项（安装包还没打 / 截图清单还没出 / 缺 Chrome /
  `--fast` 跳了 A1）→ 3，并且把每一项的「为什么没跑」逐条写出来。
以前这里是「没有 FAIL 就退出 0」，于是整跑的绿里含着一项从来没核过的东西。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

P, F, S = rc.PASS, rc.FAIL, rc.SKIP


def row(code: str, status: str, detail: str = "") -> tuple[str, str, str, str]:
    return (code, f"{code} 的说明", status, detail)


class LabelTest(unittest.TestCase):
    def test_skip_speaks_as_weiyan(self):
        """屏幕上的记号是「未验」，不是「跳过」——跳过听起来像可以不管。"""
        self.assertEqual(rc.LABEL[S], "未验")
        self.assertEqual(rc.LABEL[P], "PASS")
        self.assertEqual(rc.LABEL[F], "FAIL")

    def test_exit_codes_are_four_distinct_values(self):
        codes = {rc.EXIT_OK, rc.EXIT_FAIL, rc.EXIT_BAD_ID, rc.EXIT_PENDING}
        self.assertEqual(codes, {0, 1, 2, 3})


class SummaryTest(unittest.TestCase):
    def test_all_pass_is_green(self):
        code, lines = rc.summarize([row("A1", P), row("A2", P)], 12.5)
        self.assertEqual(code, rc.EXIT_OK)
        self.assertEqual(len(lines), 1)
        self.assertIn("2 通过 / 0 失败 / 0 未验", lines[0])
        self.assertIn("共 2 项", lines[0])
        self.assertIn("12.5s", lines[0])

    def test_empty_run_counts_zero(self):
        code, lines = rc.summarize([], 0.4)
        self.assertEqual(code, rc.EXIT_OK)
        self.assertIn("0 通过 / 0 失败 / 0 未验", lines[0])

    def test_fail_exits_one_and_names_items(self):
        code, lines = rc.summarize([row("A2", P), row("A5", F, "版本漂移")], 30.0)
        self.assertEqual(code, rc.EXIT_FAIL)
        self.assertTrue(any(line.startswith("失败项：A5") for line in lines))
        self.assertTrue(any("通过判据" in line for line in lines))

    def test_unverified_alone_exits_three(self):
        """没有失败、但有一项没核 → 3。这就是「整跑的绿里含着一项没跑」那条。"""
        code, lines = rc.summarize(
            [row("A1", P), row("A11", S, "还没构建 1.0.8-RC6 的安装包（要 Portio_1.0.8-RC6_x64-setup.exe）")],
            337.3,
        )
        self.assertEqual(code, rc.EXIT_PENDING)
        self.assertIn("1 通过 / 0 失败 / 1 未验", lines[0])
        self.assertTrue(any(line.startswith("未验项：A11") for line in lines))
        self.assertTrue(any(line.startswith("  - A11：还没构建") for line in lines))

    def test_unverified_says_how_to_close_it(self):
        code, lines = rc.summarize([row("A11", S, "还没构建安装包")], 1.0)
        self.assertEqual(code, rc.EXIT_PENDING)
        self.assertTrue(any("shots.py" in line for line in lines))

    def test_fail_wins_over_unverified(self):
        """两样都有时先修失败；未验的留到失败修完再补。"""
        code, lines = rc.summarize([row("A5", F, "漂移"), row("A11", S, "没包")], 5.0)
        self.assertEqual(code, rc.EXIT_FAIL)
        self.assertIn("1 失败 / 1 未验", lines[0])
        self.assertFalse(any(line.startswith("未验项：") for line in lines))

    def test_each_unverified_item_gets_its_own_reason(self):
        code, lines = rc.summarize(
            [row("A1", S, "本轮用 --fast 跳过"), row("A11", S, "还没构建安装包"), row("A31", S, "还没有截图清单")],
            3.0,
        )
        self.assertEqual(code, rc.EXIT_PENDING)
        self.assertTrue(any(line.startswith("未验项：A1、A11、A31") for line in lines))
        for code_id in ("A1", "A11", "A31"):
            self.assertTrue(any(line.startswith(f"  - {code_id}：") for line in lines))

    def test_long_reason_is_trimmed(self):
        long_reason = "还没构建 1.0.8-RC6 的安装包（要 Portio_1.0.8-RC6_x64-setup.exe）；这些是旧包、不算：" + "x" * 60
        code, lines = rc.summarize([row("A11", S, long_reason)], 1.0)
        reason_line = next(line for line in lines if line.startswith("  - A11："))
        self.assertTrue(reason_line.endswith("…"))
        self.assertLessEqual(len(reason_line) - len("  - A11："), 72)

    def test_missing_reason_does_not_print_empty(self):
        code, lines = rc.summarize([row("A11", S, "")], 1.0)
        self.assertTrue(any(line.startswith("  - A11：没说原因") for line in lines))


if __name__ == "__main__":
    unittest.main()
