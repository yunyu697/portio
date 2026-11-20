"""A37 的单测：真窗口里跑自检这件事，判据本身也得被核。

这里钉三件事：
① 认的是「这条钩子自己的标题」，读到上一条的结果必须红（实测 `/json/list` 慢一拍）；
② 只跑不动设置的几条——凡是要改主题 / 字号 / 会话 / 已知主机的都不许进这张表；
③ 偏好真的被挪过、又没写回去，必须红（实测自检会把 `portio.drawer` 改掉）。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


class VerdictTest(unittest.TestCase):
    def test_all_green_names_each_hook(self):
        rows = [(h, e, e) for h, e in rc.SELFTESTS]
        status, detail = rc.selftest_verdict(rows, True)
        self.assertEqual(status, rc.PASS)
        self.assertIn(str(len(rc.SELFTESTS)), detail)
        self.assertIn("split-test", detail)

    def test_nothing_ran_is_red(self):
        status, detail = rc.selftest_verdict([], True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("一条自检都没跑", detail)

    def test_self_test_reporting_err_is_red(self):
        rows = [("split-test", "SELFTEST-OK", "ERR: 四格关一格应成三格且补洞")]
        status, detail = rc.selftest_verdict(rows, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("split-test", detail)
        self.assertIn("补洞", detail)

    def test_empty_title_is_red(self):
        status, detail = rc.selftest_verdict([("find-test", "FIND-SELFTEST-OK", "")], True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("find-test", detail)
        self.assertIn("期望", detail)

    def test_stale_title_from_previous_hook_is_red(self):
        # 这就是实测撞到的那个坑：翻到 ctx-test，读到的却是 fold-test 的标题。
        # 只认「随便一个 SELFTEST-OK」会把它放过去，认前缀就不放。
        rows = [("ctx-test", "CTX-SELFTEST-OK 9", "FOLD-SELFTEST-OK [{...}]")]
        status, detail = rc.selftest_verdict(rows, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("ctx-test", detail)

    def test_prefix_not_sufficient_is_red(self):
        # 前缀对上但后面缺了数字：ctx 是九处，只写 CTX-SELFTEST-OK 不算数
        rows = [("ctx-test", "CTX-SELFTEST-OK 9", "CTX-SELFTEST-OK")]
        status, detail = rc.selftest_verdict(rows, True)
        self.assertEqual(status, rc.FAIL)

    def test_settings_not_restored_is_red(self):
        rows = [(h, e, e) for h, e in rc.SELFTESTS]
        status, detail = rc.selftest_verdict(rows, False)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("没把设置写回去", detail)

    def test_no_restore_needed_is_green(self):
        # 一条都没动设置的时候不用写回，这不算未验
        rows = [("split-test", "SELFTEST-OK", "SELFTEST-OK")]
        status, _ = rc.selftest_verdict(rows, None)
        self.assertEqual(status, rc.PASS)


class RunTest(unittest.TestCase):
    """run_selftest 得真的导航、真的等到 hash 对上才认标题。"""

    def _run(self, hook, expect, sigs, wait=2.0):
        seen_calls = []
        clock = {"t": 0.0}

        def call(ws, method, params):
            seen_calls.append((method, params))
            return {"id": 1, "result": {}}

        def value(ws, expr):
            return sigs.pop(0) if sigs else json.dumps(
                {"hash": f"#{hook}", "ready": "complete", "title": ""})

        def sleep(_):
            clock["t"] += 0.25

        def clock_fn():
            return clock["t"]

        out = rc.run_selftest("ws://x", hook, expect, wait, call=call, value=value,
                             sleep=sleep, clock=clock_fn)
        return out, seen_calls

    def test_navigates_with_query_string_not_just_fragment(self):
        # 只改 fragment 是同文档导航：页面不重载，启动那段自检压根不会跑
        _, calls = self._run("split-test", "SELFTEST-OK",
                             [json.dumps({"hash": "#split-test", "ready": "complete",
                                          "title": "SELFTEST-OK"})])
        method, params = calls[0]
        self.assertEqual(method, "Page.navigate")
        self.assertIn("?st=", params["url"])
        self.assertTrue(params["url"].endswith("#split-test"))

    def test_waits_for_its_own_hash_before_reading_title(self):
        # 上一次的页面还停在旧 hash 上、标题还是上一条的结果：这时候不许认
        stale = json.dumps({"hash": "#fold-test", "ready": "complete",
                            "title": "FOLD-SELFTEST-OK [{...}]"})
        fresh = json.dumps({"hash": "#ctx-test", "ready": "complete",
                            "title": "CTX-SELFTEST-OK 9"})
        (hook, expect, title), _ = self._run("ctx-test", "CTX-SELFTEST-OK 9", [stale, fresh])
        self.assertEqual(title, "CTX-SELFTEST-OK 9")

    def test_waits_for_ready_state(self):
        loading = json.dumps({"hash": "#split-test", "ready": "loading", "title": "Portio"})
        done = json.dumps({"hash": "#split-test", "ready": "complete", "title": "SELFTEST-OK"})
        _, _, title = self._run("split-test", "SELFTEST-OK", [loading, done])[0]
        self.assertEqual(title, "SELFTEST-OK")

    def test_timeout_returns_empty_title(self):
        never = json.dumps({"hash": "#split-test", "ready": "complete", "title": "Portio"})
        (_, _, title), _ = self._run("split-test", "SELFTEST-OK", [never, never, never], wait=1.0)
        self.assertEqual(title, "")


class SettingsTest(unittest.TestCase):
    def test_same_content_different_key_order_is_same(self):
        # 实测踩到的：clear 之后重写，键序变了，字面比对会把「没动过」判成「动过」
        a = json.dumps({"portio.drawer": "28", "portio.theme": "dark"})
        b = json.dumps({"portio.theme": "dark", "portio.drawer": "28"})
        self.assertTrue(rc.settings_same(a, b))

    def test_different_value_is_different(self):
        a = json.dumps({"portio.drawer": "28"})
        b = json.dumps({"portio.drawer": "172"})
        self.assertFalse(rc.settings_same(a, b))

    def test_restore_expr_carries_the_dump(self):
        dump = json.dumps({"portio.drawer": "28"})
        expr = rc.localstorage_restore_expr(dump)
        self.assertIn("localStorage.clear()", expr)
        self.assertIn('"portio.drawer"', expr)
        self.assertIn("localStorage.setItem", expr)


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.src = RC_PY.read_text(encoding="utf-8")

    def test_in_plan_table(self):
        self.assertRegex(self.src, r'\("A37",\s*"那几条自检在真窗口里')

    def test_in_dispatch_chain(self):
        self.assertIn('elif code == "A37":', self.src)
        self.assertIn("a37_selftests()", self.src)

    def test_only_memory_only_hooks(self):
        # 会写设置的（主题 / 字号 / 密度 / 强调色 / 终端配色 / 启动布局 / 权限列 /
        # 开局格数 / 面板宽度 / 会话 / 已知主机 / 窄窗）不许进真窗口这一轮：
        # 它们要动的是我的真偏好，甚至真文件。
        banned = ("sessions-test", "hosts-test", "theme-test", "density-test",
                  "accent-test", "term-theme-test", "font-test", "boot-test",
                  "perm-test", "panes-test", "layout-test", "net-fail-test",
                  "narrow-test")
        hooks = [h for h, _ in rc.SELFTESTS]
        for bad in banned:
            self.assertNotIn(bad, hooks, f"{bad} 会动我的设置，不该在真窗口里跑")

    def test_expected_prefixes_are_specific(self):
        # 每条都得带自己的前缀，不能都写成 SELFTEST-OK（那样上一条的结果会被认成本条）
        expects = dict(rc.SELFTESTS)
        self.assertEqual(expects["clip-test"], "CLIP-SELFTEST-OK 10")
        self.assertEqual(expects["ctx-test"], "CTX-SELFTEST-OK 9")
        self.assertNotEqual(expects["find-test"], expects["find-pane-test"])

    def test_version_drift_is_untested(self):
        self.assertIn("不是本版构建", self.src)
        body = self.src.split("def probe_selftests(", 1)[1].split("def a37_selftests", 1)[0]
        self.assertIn("return SKIP", body)

    def test_backs_up_and_restores_settings(self):
        body = self.src.split("def probe_selftests(", 1)[1].split("def a37_selftests", 1)[0]
        self.assertIn("WEBVIEW_BACKUP_EXPR", body)
        self.assertIn("localstorage_restore_expr", body)
        self.assertIn("settings_same", body)

    def test_kills_the_tree_after_tests(self):
        body = self.src.split("def probe_selftests(", 1)[1].split("def a37_selftests", 1)[0]
        self.assertRegex(body, r"finally:\s*\n\s*if proc.poll\(\) is None:\s*\n\s*kill\(proc.pid\)")

    def test_port_not_hardcoded(self):
        self.assertIn("port = port or free_port()", self.src)

    def test_windows_only(self):
        body = self.src.split("def a37_selftests(", 1)[1].split("def split_ids", 1)[0]
        self.assertIn("win32", body)


if __name__ == "__main__":
    unittest.main()
