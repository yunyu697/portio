#!/usr/bin/env python3
"""check_versions.py 的单元测试：每一处写版本号的地方都要被读到、被比对。

2026-11-20 之前它只核三处，标题栏那个 `<span class="ver">` 与 `Cargo.lock` 里三个 crate
根本没人管——界面自己写错了版本、锁文件停在上一个版本，两边都能一路绿过去。这里钉住：
两处都读得出来、读不出来时给出空串而不是瞎猜、任何一处漂移都会让 main 返回 1 并点名。
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_versions as cv  # noqa: E402


class UiVersionTest(unittest.TestCase):
    def test_reads_span_with_extra_attr(self):
        html = '<span class="ver" data-tauri-drag-region>1.0.8-RC5</span>'
        self.assertEqual(cv.ui_version(html), "1.0.8-RC5")

    def test_strips_surrounding_space(self):
        html = '<span class="ver"> 1.0.8-RC5 </span>'
        self.assertEqual(cv.ui_version(html), "1.0.8-RC5")

    def test_absent_returns_empty(self):
        self.assertEqual(cv.ui_version("<html><body>没有版本标签</body></html>"), "")

    def test_other_span_not_mistaken(self):
        html = '<span class="verchip">1.0.8-RC5</span>'
        self.assertEqual(cv.ui_version(html), "")


LOCK = """\
version = 4

[[package]]
name = "portio-app"
version = "1.0.8-RC5"
dependencies = ["portio-core"]

[[package]]
name = "portio-core"
version = "1.0.8-RC5"

[[package]]
name = "portio-ssh"
version = "1.0.8-RC5"

[[package]]
name = "serde"
version = "1.0.200"
"""


class LockVersionsTest(unittest.TestCase):
    def test_three_crates_read(self):
        got = cv.lock_versions(LOCK)
        self.assertEqual(set(got), {"portio-app", "portio-core", "portio-ssh"})
        self.assertEqual(got["portio-ssh"], "1.0.8-RC5")

    def test_dependency_named_like_crate_not_confused(self):
        """依赖列表里出现同名不算 package 块——只认 [[package]] 那个块。"""
        text = LOCK.replace('dependencies = ["portio-core"]', 'dependencies = []')
        self.assertIn("portio-core", cv.lock_versions(text))

    def test_missing_crate_absent(self):
        text = LOCK.split('[[package]]\nname = "portio-ssh"')[0]
        self.assertNotIn("portio-ssh", cv.lock_versions(text))

    def test_stale_version_visible(self):
        stale = LOCK.replace('version = "1.0.8-RC5"\n\n[[package]]\nname = "portio-ssh"',
                             'version = "1.0.8-RC4"\n\n[[package]]\nname = "portio-ssh"')
        self.assertEqual(cv.lock_versions(stale)["portio-core"], "1.0.8-RC4")


class MainTest(unittest.TestCase):
    def test_repo_now_agrees(self):
        with mock.patch("sys.stdout"):
            self.assertEqual(cv.main(), 0)

    def test_any_drift_fails_and_names_spot(self):
        sources = {
            "Cargo.toml [workspace.package]": "1.0.8-RC5",
            "package.json": "1.0.8-RC5",
            "crates/app/tauri.conf.json": "1.0.8-RC5",
            "ui/index.html 标题栏": "1.0.8-RC5",
            "Cargo.lock portio-app": "1.0.8-RC5",
            "Cargo.lock portio-core": "1.0.8-RC5",
            "Cargo.lock portio-ssh": "1.0.8-RC4",
        }
        err = []
        with mock.patch.object(cv, "collect", return_value=sources), \
                mock.patch("sys.stderr", new=type("E", (), {"write": lambda s, t: err.append(t),
                                                             "flush": lambda s: None})()):
            self.assertEqual(cv.main(), 1)
        joined = "".join(err)
        self.assertIn("Cargo.lock portio-ssh", joined)
        self.assertIn("1.0.8-RC4", joined)

    def test_illegal_number_rejected(self):
        bad = {k: "1.11.0-RC5" for k in
               ("Cargo.toml [workspace.package]", "package.json",
                "crates/app/tauri.conf.json", "ui/index.html 标题栏")}
        with mock.patch.object(cv, "collect", return_value=bad), \
                mock.patch("sys.stderr"), mock.patch("sys.stdout"):
            self.assertEqual(cv.main(), 1)


if __name__ == "__main__":
    unittest.main()
