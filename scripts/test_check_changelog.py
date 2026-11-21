# -*- coding: utf-8 -*-
"""`scripts/check_changelog.py` 的单测。

判据都是「这一版的更新内容能不能直接贴到 Release」：当前版本得有自己那一节、排在最前、
段内不许被空行切成七截、子标题得在白名单里。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_changelog as cc  # noqa: E402

CLEAN = """# Changelog

## [Unreleased]

## 各版本的更新内容（GitHub Release 文案直接取自本节）

## [1.0.10-RC2] - 2026-11-21

### Fixed

- **一句话说清改了什么。** 后面接着写为什么，需要换行就缩两格接着写，
  不要中间插空行。

### Known limitations

- 真实 SSH 会话仍未验证。

## [1.0.10-RC1] - 2026-11-21

### Fixed

- 上一版的东西。
"""


def text_with_current(body: str, version: str = "1.0.10-RC2") -> str:
    """拼一份最小 CHANGELOG：Unreleased、当前版本那一节（正文由调用方给）。"""
    return f"""# Changelog

## [Unreleased]

## [{version}] - 2026-11-21

{body}"""


class CleanTest(unittest.TestCase):
    def test_clean_text_passes(self):
        self.assertEqual(cc.check_text(CLEAN, "1.0.10-RC2"), [])

    def test_real_changelog_passes(self):
        """仓库里这一份真文件也得过 —— 不然门禁一上去就红。"""
        text = (Path(cc.__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        current = cc.read_current_version()
        self.assertEqual(cc.check_text(text, current), [])


class OrderTest(unittest.TestCase):
    def test_unreleased_must_be_first(self):
        text = CLEAN.replace("## [Unreleased]", "## [1.0.10-RC2] - 2026-11-21", 1)
        problems = cc.check_text(text, "1.0.10-RC2")
        # 现在第一行二级标题是「## 各版本…」之后的版本小节，Unreleased 不见了。
        self.assertTrue(any("Unreleased" in p for p in problems), problems)

    def test_current_version_must_be_head_section(self):
        problems = cc.check_text(CLEAN, "1.0.9-RC10")
        self.assertTrue(any("排在最前的版本小节是" in p for p in problems), problems)

    def test_current_version_section_must_exist(self):
        problems = cc.check_text(CLEAN, "1.1.0-RC1")
        self.assertTrue(any("1.0.10-RC2" in p and "当前版本" in p for p in problems), problems)


class LayoutTest(unittest.TestCase):
    def test_double_blank_line_is_flagged(self):
        body = "### Fixed\n\n- 第一条\n\n\n- 第二条\n"
        problems = cc.check_text(text_with_current(body), "1.0.10-RC2")
        self.assertTrue(any("连着两个空行" in p for p in problems), problems)

    def test_blank_line_splitting_a_bullet_is_flagged(self):
        """RC1 那次就是这个形状：条目第一行、空行、缩进两格的续行。"""
        body = "### Fixed\n\n- 一句话开头，\n\n  后面接着写。\n"
        problems = cc.check_text(text_with_current(body), "1.0.10-RC2")
        self.assertTrue(any("被空行切断的续行" in p for p in problems), problems)

    def test_indented_continuation_without_blank_line_is_fine(self):
        body = "### Fixed\n\n- 第一行，\n  第二行接着。\n"
        self.assertEqual(cc.check_text(text_with_current(body), "1.0.10-RC2"), [])

    def test_trailing_whitespace_is_flagged(self):
        body = "### Fixed\n\n- 行尾有空格 \n"
        problems = cc.check_text(text_with_current(body), "1.0.10-RC2")
        self.assertTrue(any("行尾有多余空白" in p for p in problems), problems)

    def test_tab_is_flagged(self):
        body = "### Fixed\n\n- 前面有制表符\n\t缩进用空格。\n"
        problems = cc.check_text(text_with_current(body), "1.0.10-RC2")
        self.assertTrue(any("制表符" in p for p in problems), problems)

    def test_legacy_section_layout_is_not_repoliced(self):
        """历史小节不重排：1.0.5-RC7 里那两个空行不该让门禁红。"""
        legacy = "## [1.0.5-RC7] - 2026-11-01\n\n### Fixed\n\n- 老条目\n\n\n- 另一条\n"
        text = text_with_current("### Fixed\n\n- 新的。\n") + "\n" + legacy
        self.assertEqual(cc.check_text(text, "1.0.10-RC2"), [])


class ContentTest(unittest.TestCase):
    def test_missing_subsection_is_flagged(self):
        body = "- 只有一条，没有子标题。\n"
        problems = cc.check_text(text_with_current(body), "1.0.10-RC2")
        self.assertTrue(any("子标题都没有" in p for p in problems), problems)

    def test_subsection_outside_whitelist_is_flagged(self):
        body = "### 随手记\n\n- 一条。\n"
        problems = cc.check_text(text_with_current(body), "1.0.10-RC2")
        self.assertTrue(any("不在允许的集合里" in p for p in problems), problems)

    def test_empty_current_section_is_flagged(self):
        problems = cc.check_text(text_with_current(""), "1.0.10-RC2")
        self.assertTrue(any("小节是空的" in p for p in problems), problems)

    def test_missing_date_is_flagged(self):
        text = CLEAN.replace("## [1.0.10-RC2] - 2026-11-21", "## [1.0.10-RC2]")
        problems = cc.check_text(text, "1.0.10-RC2")
        self.assertTrue(any("缺日期" in p for p in problems), problems)

    def test_bad_date_shape_is_flagged(self):
        text = CLEAN.replace("## [1.0.10-RC2] - 2026-11-21", "## [1.0.10-RC2] - 2026/11/21")
        problems = cc.check_text(text, "1.0.10-RC2")
        self.assertTrue(any("不是 YYYY-MM-DD" in p for p in problems), problems)

    def test_legacy_heading_is_tolerated(self):
        """`1.0.1-Alpha5 … Alpha10` 这种合写小节是历史，不解析报错。"""
        text = CLEAN.replace(
            "## [1.0.10-RC1] - 2026-11-21",
            "## [1.0.1-Alpha5 … Alpha10] - 2026-10-10",
        )
        self.assertEqual(cc.check_text(text, "1.0.10-RC2"), [])

    def test_bad_version_string_is_flagged(self):
        text = CLEAN.replace(
            "## [1.0.10-RC1] - 2026-11-21",
            "## [1.0.10-rc0] - 2026-11-21",
        )
        problems = cc.check_text(text, "1.0.10-RC2")
        self.assertTrue(any("不合规则" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
