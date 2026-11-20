#!/usr/bin/env python3
"""set_version.py 的单元测试：四处清单 + 说明页那几处版本串。

说明页的版本串一直是手改的，于是「改了版本号、忘了改页面」这种漏法每轮都可能重演：
2026-11-20 就是进位到 `1.0.8-RC3` 之后，回归 A28 报「说明页版本串过期：1.0.8-RC2 ≠ 1.0.8-RC3」
才发现。这里钉住：说明页跟着一起改、更长的号（`1.0.8-RC20`）不被误伤、空版本号不动作。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import set_version as sv  # noqa: E402


class CurrentTest(unittest.TestCase):
    def test_reads_span_text(self):
        html = '<span class="ver" data-tauri-drag-region>1.0.8-RC2</span>'
        self.assertEqual(sv.current(html), "1.0.8-RC2")

    def test_empty_when_absent(self):
        self.assertEqual(sv.current("<html></html>"), "")


class RewriteSiteTest(unittest.TestCase):
    def test_all_occurrences_replaced(self):
        page = "<p>v1.0.8-RC2 装好之后</p><p>Portio_1.0.8-RC2_x64-setup.exe</p><p>v1.0.8-RC2</p>"
        out = sv.rewrite_site(page, "1.0.8-RC3")
        self.assertEqual(out.count("1.0.8-RC3"), 3)
        self.assertNotIn("1.0.8-RC2", out)

    def test_two_digit_stage_suffix_also_replaced(self):
        """`RC10` 这种两位序号也是版本号，一起换。"""
        self.assertEqual(sv.rewrite_site("v1.0.7-RC10", "1.0.8-RC3"), "v1.0.8-RC3")

    def test_number_not_part_of_version_untouched(self):
        """`1024` 这种数字里没有三段点号，不会被当成版本号。"""
        page = "字号 9–24，字号上限 1024，比例 2.5"
        self.assertEqual(sv.rewrite_site(page, "1.0.8-RC3"), page)

    def test_plain_and_staged_both_replaced(self):
        page = "1.0.5 与 1.0.5-RC4"
        self.assertEqual(sv.rewrite_site(page, "1.0.8-RC3"), "1.0.8-RC3 与 1.0.8-RC3")

    def test_empty_version_is_noop(self):
        page = "v1.0.8-RC2"
        self.assertEqual(sv.rewrite_site(page, ""), page)

    def test_no_version_looking_text_is_noop(self):
        page = "这一页没有版本号，只有 1024 与 2.5 这样的数字"
        self.assertEqual(sv.rewrite_site(page, "1.0.8-RC3"), page)


class RewriteLockTest(unittest.TestCase):
    """Cargo.lock 以前只能等下次构建才刷新，这里改成跟着进位一起写。"""

    LOCK = """\
version = 4

[[package]]
name = "portio-app"
version = "1.0.8-RC4"
dependencies = ["portio-core"]

[[package]]
name = "portio-core"
version = "1.0.8-RC4"

[[package]]
name = "portio-ssh"
version = "1.0.8-RC4"

[[package]]
name = "serde"
version = "1.0.200"
"""

    def test_three_crates_replaced(self):
        out, hit = sv.rewrite_lock(self.LOCK, "1.0.8-RC5")
        self.assertEqual(hit, ["portio-app", "portio-core", "portio-ssh"])
        self.assertEqual(out.count('version = "1.0.8-RC5"'), 3)
        self.assertNotIn("1.0.8-RC4", out)

    def test_other_packages_untouched(self):
        out, _ = sv.rewrite_lock(self.LOCK, "1.0.8-RC5")
        self.assertIn('name = "serde"\nversion = "1.0.200"', out)

    def test_missing_crate_skipped_not_invented(self):
        text = self.LOCK.split('[[package]]\nname = "portio-ssh"')[0]
        out, hit = sv.rewrite_lock(text, "1.0.8-RC5")
        self.assertEqual(hit, ["portio-app", "portio-core"])
        self.assertNotIn("portio-ssh", out)

    def test_already_current_is_noop(self):
        out, hit = sv.rewrite_lock(self.LOCK, "1.0.8-RC4")
        self.assertEqual(out, self.LOCK)
        self.assertEqual(len(hit), 3)

    def test_two_digit_stage_suffix_written(self):
        """满 10 之后进 patch 再回 RC1，锁文件同样跟着走。"""
        out, _ = sv.rewrite_lock(self.LOCK, "1.0.9-RC1")
        self.assertEqual(out.count('version = "1.0.9-RC1"'), 3)


class RealRepoTest(unittest.TestCase):
    def test_site_agrees_with_ui_version(self):
        """仓库现状：说明页里写的版本串与界面那个一致（不一致时 A28 会红，这里先兜一层）。"""
        ver = sv.current((sv.ROOT / "ui" / "index.html").read_text(encoding="utf-8"))
        page = sv.SITE.read_text(encoding="utf-8") if sv.SITE.is_file() else ""
        if not page:
            self.skipTest("没有说明页")
        self.assertIn(ver, page, f"说明页里没写当前版本 {ver}")
        self.assertGreaterEqual(page.count(ver), 3, "署名 / 安装 / 版本段至少三处")


if __name__ == "__main__":
    unittest.main()
