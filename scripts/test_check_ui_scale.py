#!/usr/bin/env python3
"""check_ui_scale.py 的单元测试：档位对照表与状态族覆盖。

2026-11-24 之前这个脚本只拦"裸 px / 裸数字"，圆角用错档（r-4 写成 r-6）、
按钮缺按压态 / 焦点环都能一路绿过去。这里钉住：对照表内组件档位漂移会被点名，
按钮缺 active / focus-visible、输入缺 focus 也会被点名；合成修饰选择器
（.btn.primary:active、.set .hz-del:hover）能正确归到同族。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_ui_scale as cu  # noqa: E402


class RadiusTierTest(unittest.TestCase):
    def test_mismatched_tier_is_reported(self):
        css = ".sess-row{border-radius:var(--r-4)}"
        problems = cu.scan_radius(css)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("--r-6", problems[0])
        self.assertIn("--r-4", problems[0])

    def test_correct_tier_is_clean(self):
        css = ".sess-row{border-radius:var(--r-6)}"
        self.assertEqual(cu.scan_radius(css), [])

    def test_panel_and_overlay_tiers(self):
        self.assertEqual(cu.scan_radius(".fp-block{border-radius:var(--r-8)}"), [])
        self.assertEqual(cu.scan_radius(".sheet{border-radius:var(--r-12)}"), [])
        self.assertTrue(cu.scan_radius(".sheet{border-radius:var(--r-8)}"))

    def test_longer_selector_wins_over_generic(self):
        # 勾选框是 r-4，不能被通用 .field input 的 r-6 吃掉
        css = ".field .remember input{border-radius:var(--r-4)}"
        self.assertEqual(cu.scan_radius(css), [])
        bad = ".field .remember input{border-radius:var(--r-6)}"
        self.assertTrue(cu.scan_radius(bad))

    def test_top_only_radius_expression(self):
        # 标签上两角：--r-8 --r-8 0 0，令牌档位仍算 r-8
        css = ".tab{border-radius:var(--r-8) var(--r-8) 0 0}"
        self.assertEqual(cu.scan_radius(css), [])

    def test_collapsed_zero_radius_passes(self):
        css = ".drawer.collapsed{border-radius:0}"
        self.assertEqual(cu.scan_radius(css), [])

    def test_unknown_component_not_policed(self):
        # 不在对照表里的组件，脚本不臆造档位（仍受"必须用令牌"的旧规则约束）
        css = ".my-widget{border-radius:var(--r-4)}"
        self.assertEqual(cu.scan_radius(css), [])


class StateFamilyTest(unittest.TestCase):
    @staticmethod
    def _selectors(css):
        return [sel for sel, _ in cu.parse_rules(css)]

    def test_button_missing_active(self):
        css = ".btn{color:var(--text)} .btn:focus-visible{box-shadow:0 0 0 3px var(--accent-ring)}"
        self.assertIn("active", cu.missing_states(self._selectors(css), ".btn"))

    def test_button_missing_focus_visible(self):
        css = ".btn{color:var(--text)} .btn:active{background:var(--surface-3)}"
        self.assertIn("focus-visible", cu.missing_states(self._selectors(css), ".btn"))

    def test_button_with_both_states_clean(self):
        css = (
            ".btn{color:var(--text)}"
            ".btn:active{background:var(--surface-3)}"
            ".btn:focus-visible{box-shadow:0 0 0 3px var(--accent-ring)}"
        )
        self.assertEqual(cu.missing_states(self._selectors(css), ".btn"), [])

    def test_composite_selector_counts_as_family(self):
        css = (
            ".btn.primary{background:var(--accent)}"
            ".btn.primary:active{filter:brightness(.97)}"
            ".btn:focus-visible{box-shadow:0 0 0 3px var(--accent-ring)}"
        )
        self.assertEqual(cu.missing_states(self._selectors(css), ".btn"), [])

    def test_input_requires_focus(self):
        bad = ".field input{color:var(--text)}"
        self.assertIn("focus", cu.missing_states(self._selectors(bad), ".field input"))
        good = ".field input{color:var(--text)} .field input:focus{border-color:var(--accent)}"
        self.assertEqual(cu.missing_states(self._selectors(good), ".field input"), [])

    def test_icon_button_family(self):
        css = (
            ".fp-btn{color:var(--text-3)}"
            ".fp-btn:active{background:var(--surface-2)}"
            ".fp-btn:focus-visible{box-shadow:0 0 0 3px var(--accent-ring)}"
        )
        self.assertEqual(cu.missing_states(self._selectors(css), ".fp-btn"), [])
        self.assertIn("active", cu.missing_states(self._selectors(".fp-btn{}"), ".fp-btn"))

    def test_import_item_only_requires_active(self):
        # 下拉条目不是逐键可达的主按钮，不强制 focus-visible
        css = ".sess-import .item{color:var(--text-2)} .sess-import .item:active{background:var(--surface-3)}"
        self.assertEqual(cu.missing_states(self._selectors(css), ".sess-import .item"), [])


class ParseRulesTest(unittest.TestCase):
    def test_comma_group_split(self):
        rules = dict(cu.parse_rules(".a, .b{color:var(--text)}"))
        self.assertIn(".a", rules)
        self.assertIn(".b", rules)

    def test_comments_stripped(self):
        css = "/* 注释 .x{--r-4} */\n.btn{border-radius:var(--r-6)}"
        self.assertEqual(cu.scan_radius(css), [])


class RealUiIntegrationTest(unittest.TestCase):
    """仓库真实 index.html 必须一次过（防止对照表与代码悄悄脱节）。"""

    def test_real_html_clean(self):
        html = (Path(__file__).resolve().parents[1] / "ui/index.html").read_text(encoding="utf-8")
        self.assertEqual(cu.scan_radius(html), [])
        self.assertEqual(cu.scan_states(html), [])


if __name__ == "__main__":
    unittest.main()
