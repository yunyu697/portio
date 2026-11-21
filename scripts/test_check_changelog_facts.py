#!/usr/bin/env python3
"""`check_changelog_facts.py` 的单测：六条判据各来几条，正反都打。

单测里不碰 git —— 事实都是拼出来的 Facts，好让每条判据单独红。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_changelog_facts as ccf  # noqa: E402


def facts(**over) -> ccf.Facts:
    """默认一份「这一版改过 ui/app.js 与 rc.py、A45 早就在、这一版没新增脚本」的事实。"""
    base = dict(
        top_dirs={"scripts", "crates", "ui", "docs", "assets"},
        exists=lambda p: p in {
            "ui/app.js", "scripts/rc.py", "scripts/check_changelog.py",
            "docs/versioning.md", "docs/shot/a.png", "crates/app/src/main.rs",
        },
        changed={"ui/app.js", "scripts/rc.py"},
        added=set(),
        codes_now={"A1", "A45"},
        codes_prev={"A1", "A45"},
        dispatch={"A1", "A45"},
        plan_scripts={"A45": {"check_changelog.py"}},
    )
    base.update(over)
    return ccf.Facts(**base)


class CleanTest(unittest.TestCase):
    def test_clean_section_passes(self):
        body = (
            "### Fixed\n\n"
            "- **改了一下终端面板的宽度。** `ui/app.js` 里那两处内联变量现在跟着设置走，"
            "顺带把 A45 那道门禁也接上了。"
        )
        self.assertEqual(ccf.check_text(body, facts()), [])

    def test_docs_mention_needs_no_change(self):
        body = "- 细节写在 `docs/versioning.md` 里，这一版没动它。"
        self.assertEqual(ccf.check_text(body, facts()), [])


class PathTest(unittest.TestCase):
    def test_missing_path_is_red(self):
        body = "- 我加了 `scripts/check_sites.py` 这个脚本。"
        problems = ccf.check_text(body, facts())
        self.assertTrue(any("不存在" in p and "check_sites.py" in p for p in problems), problems)

    def test_token_without_slash_is_not_a_path(self):
        body = "- 坏掉的清单会另存成 `sessions.json.broken-1795221182575`。"
        self.assertEqual(ccf.check_text(body, facts()), [])

    def test_ignored_segments(self):
        body = "- 翻了 `node_modules/x.js` 与 `target/debug/app.exe` 两处。"
        self.assertEqual(ccf.check_text(body, facts()), [])

    def test_non_top_dir_is_ignored(self):
        body = "- 用户目录里的 `Downloads/foo.py` 不算仓库路径。"
        self.assertEqual(ccf.check_text(body, facts()), [])

    def test_extract_keeps_order_and_dedups(self):
        text = "先 `ui/app.js`，再 `scripts/rc.py`，还是 `ui/app.js`。"
        self.assertEqual(
            ccf.extract_paths(text, {"scripts", "ui"}),
            ["ui/app.js", "scripts/rc.py"],
        )


class ClaimTest(unittest.TestCase):
    def test_claims_change_but_not_changed(self):
        body = "- 这一版我把 `scripts/rc.py` 里的分发口重写了。" # rc.py 在改动集里
        self.assertEqual(ccf.check_text(body, facts()), [])
        body2 = "- 这一版的 `crates/app/src/main.rs` 重写过了。"  # 存在但没改
        problems = ccf.check_text(body2, facts())
        self.assertTrue(any("这一版的改动里没有它" in p for p in problems), problems)

    def test_mention_without_verb_is_fine(self):
        body = "- 跟 `crates/app/src/main.rs` 里那套写法一致，这一版没碰它。"
        self.assertEqual(ccf.check_text(body, facts()), [])

    def test_verb_across_line_break_still_counts(self):
        # 折行：动词在前一行、路径在后一行——拼成一行之后仍该认出来
        body = "### Fixed\n\n- 这一版我把权限列那条的判断改了改，\n  `crates/app/src/main.rs` 里的取整也跟着换了。"
        problems = ccf.check_text(body, facts())
        self.assertTrue(any("crates/app/src/main.rs" in p for p in problems), problems)


class GateTest(unittest.TestCase):
    def test_unknown_gate_is_red(self):
        body = "- 新增门禁 A99。"
        problems = ccf.check_text(body, facts())
        self.assertTrue(any("A99" in p and "计划表里没有" in p for p in problems), problems)

    def test_known_gate_passes(self):
        body = "- 顺手把 A45 也接上了。"
        self.assertEqual(ccf.check_text(body, facts()), [])

    def test_new_gate_must_be_announced(self):
        body = "- 这一版把更新内容那段改成单倍行距。"
        problems = ccf.check_text(body, facts(codes_now={"A1", "A45"}, codes_prev={"A1", "A45"}))
        self.assertEqual(problems, [])
        problems = ccf.check_text(body, facts(codes_now={"A1", "A45", "A46"}, codes_prev={"A1", "A45"},
                                            dispatch={"A1", "A45", "A46"}))
        self.assertTrue(any("A46" in p and "一个字没提" in p for p in problems), problems)

    def test_new_gate_announced_passes(self):
        body = "- 新增门禁 A46，专门核「说法对得上实现」。"
        self.assertEqual(
            ccf.check_text(body, facts(codes_now={"A1", "A45", "A46"}, codes_prev={"A1", "A45"},
                                       dispatch={"A1", "A45", "A46"})),
            [],
        )

    def test_alpha_suffix_is_not_a_gate(self):
        self.assertEqual(ccf.mentioned_gates("Alpha1 到 Alpha10 那几版"), set())


class NewScriptTest(unittest.TestCase):
    def test_new_script_silent_is_red(self):
        body = "- 这一版把更新内容那段改成单倍行距。"
        problems = ccf.check_text(body, facts(added={"scripts/check_changelog.py"}))
        self.assertTrue(any("新增了 `scripts/check_changelog.py`" in p for p in problems), problems)

    def test_new_script_named_passes(self):
        body = "- 新脚本 `scripts/check_changelog.py` 六条判据。"
        self.assertEqual(ccf.check_text(body, facts(added={"scripts/check_changelog.py"})), [])

    def test_new_script_covered_by_its_gate(self):
        # 没点名脚本，但点了它上场的那道门禁：A45 本来就是它
        body = "- 新增门禁 A45，管更新内容的形状。"
        self.assertEqual(ccf.check_text(body, facts(added={"scripts/check_changelog.py"})), [])

    def test_unit_test_file_is_exempt(self):
        self.assertFalse(ccf.is_new_script("scripts/test_check_changelog.py"))
        self.assertTrue(ccf.is_new_script("scripts/check_changelog.py"))
        self.assertFalse(ccf.is_new_script("crates/app/src/foo.rs"))


class DispatchTest(unittest.TestCase):
    def test_plan_without_dispatch_is_red(self):
        problems = ccf.check_text("- 什么都不说。", facts(dispatch={"A1"}))
        self.assertTrue(any("A45" in p and "分发处却没有" in p for p in problems), problems)

    def test_plan_and_dispatch_agree(self):
        self.assertEqual(ccf.check_text("- 什么都不说。", facts()), [])


class ParseTest(unittest.TestCase):
    def test_parse_plan_on_real_file(self):
        src = (Path(__file__).resolve().parent / "rc.py").read_text(encoding="utf-8")
        codes, scripts = ccf.parse_plan(src)
        self.assertIn("A1", codes)
        self.assertIn("A45", codes)
        self.assertIn("A46", codes)
        self.assertEqual(scripts["A45"], {"check_changelog.py"})
        self.assertEqual(scripts["A46"], {"check_changelog_facts.py"})

    def test_parse_dispatch_on_real_file(self):
        src = (Path(__file__).resolve().parent / "rc.py").read_text(encoding="utf-8")
        dispatch = ccf.parse_dispatch(src)
        self.assertIn("A45", dispatch)
        self.assertIn("A46", dispatch)
        self.assertLessEqual(ccf.parse_plan(src)[0], dispatch, "计划表里每一项都得有分发分支")

    def test_version_key_orders_stages(self):
        self.assertLess(ccf.version_key("1.0.10-RC1"), ccf.version_key("1.0.10-RC2"))
        self.assertLess(ccf.version_key("1.0.10-RC2"), ccf.version_key("1.0.10"))
        self.assertLess(ccf.version_key("1.0.9-RC10"), ccf.version_key("1.0.10-RC1"))


if __name__ == "__main__":
    unittest.main()
