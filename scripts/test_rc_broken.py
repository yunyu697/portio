"""A42 的单测：把「读坏的会话清单不许被下一次存盘整份盖掉」这件事钉住。

这里钉三件事，都是这轮真会出错的地方：
① 前端只在「解析不出来」时才叫急救；好文件、空文件、`{"version":1}` 这种没写 records 的都不许另存；
   读不出来（文件系统/权限）也不许谎称清单坏了；
② 急救叫不到（后端写不了副本）时，话得说成「先别存新的」，不能让人以为已经救回来了；
③ 接线：后端的 `sessions_salvage` 得注册进 invoke_handler，`salvage_broken` 得真是「先拷后写」，
   计划表 / 分派链里有 A42，且 A42 走的是无头页那一条。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RC_PY = ROOT / "scripts" / "rc.py"
APP_JS = ROOT / "ui" / "app.js"
STORE_RS = ROOT / "crates" / "app" / "src" / "session_store.rs"
LIB_RS = ROOT / "crates" / "app" / "src" / "lib.rs"


class RcWiringTest(unittest.TestCase):
    def setUp(self):
        self.text = RC_PY.read_text(encoding="utf-8")

    def test_plan_has_a42(self):
        self.assertIn('("A42"', self.text)
        # 标签得写清判的是什么：「先另存再从头开始」
        label = self.text.split('("A42"', 1)[1].split("),", 1)[0]
        self.assertIn("另存", label)

    def test_dispatch_is_headless_page(self):
        body = self.text.split('elif code == "A42"', 1)[1].split("elif code", 1)[0]
        self.assertIn("#broken-store-test", body)
        self.assertIn("BROKEN-STORE-SELFTEST-OK", body)

    def test_header_counts_to_last_item(self):
        m = re.search(r"A1–A(\d+)", self.text)
        self.assertIsNotNone(m)
        last = max(int(n) for n in re.findall(r'\("A(\d+)"', self.text))
        self.assertEqual(int(m.group(1)), last)


class StoreWiringTest(unittest.TestCase):
    def setUp(self):
        self.lib = LIB_RS.read_text(encoding="utf-8")
        self.rs = STORE_RS.read_text(encoding="utf-8")

    def test_command_is_registered(self):
        # 命令写了但没注册进 invoke_handler，前端调就是「没这个命令」，谁都不会发现
        self.assertIn("session_store::sessions_salvage", self.lib)

    def test_copy_happens_before_any_write(self):
        body = self.rs.split("fn salvage_broken", 1)[1].split("fn ", 1)[0]
        self.assertIn("fs::copy", body, "另存必须是拷贝原字节")
        self.assertIn("sessions.json.broken-", self.rs)
        self.assertNotIn("remove_file", body, "另存不许动原文件")
        self.assertNotIn("write_store_atomic", body, "急救里不许写新清单")

    def test_reuses_the_single_parser(self):
        # 判定「读不懂」只能用 Core 那一套解析，别在前端另写一份规则
        self.assertIn("SessionStore::from_json", self.rs.split("fn store_text_is_readable", 1)[1])

    def test_tests_are_in_place(self):
        for name in (
            "salvage_copies_broken_store_before_it_gets_overwritten",
            "salvage_leaves_good_empty_and_missing_files_alone",
            "salvage_catches_garbage_bytes_and_future_version",
        ):
            self.assertIn(f"fn {name}", self.rs)


class FrontendWiringTest(unittest.TestCase):
    def setUp(self):
        self.js = APP_JS.read_text(encoding="utf-8")

    def test_selftest_hook_exists(self):
        self.assertIn('location.hash === "#broken-store-test"', self.js)

    def test_salvage_is_called_from_load(self):
        body = self.js.split("async function loadSessions", 1)[1].split("\n}", 1)[0]
        self.assertIn('tryInvoke("sessions_salvage"', body)

    def test_non_store_json_counts_as_broken(self):
        body = self.js.split("async function loadSessions", 1)[1].split("\n}", 1)[0]
        self.assertIn("Array.isArray(obj)", body)
        self.assertIn("obj && typeof obj === \"object\"", body)

    def test_write_goes_through_the_same_seam(self):
        body = self.js.split("function persistSessions", 1)[1].split("\n}", 1)[0]
        self.assertIn("fakeInvoke", body, "自检里要核得出「到底写了什么」")

    def test_selftest_restores_the_stub(self):
        body = self.js.split('location.hash === "#broken-store-test"', 1)[1].split("// ---------- 无头自检", 1)[0]
        self.assertIn("fakeInvoke = null", body, "自检收场必须把替身摘掉")
        self.assertIn("sessionStore.records = prevRecords", body)


if __name__ == "__main__":
    unittest.main()
