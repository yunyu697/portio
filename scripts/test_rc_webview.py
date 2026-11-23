"""A36 的单测：真 webview 里读回来那几个信号怎么判，以及它有没有真接进计划表。

判据必须自己也能被核——所以这里一条条喂假信号：
少了 DOM、版本对不上、app.js 没跑完、终端对象没建、只剩骨架，
每一种都得红，且点名差在哪。再钉住「它真接进 rc.py 的计划表与分派链」，
不然 A36 写了却没人跑，等于没有。
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"
GOOD = {
    "title": "Portio",
    "ver": "1.2.3-RC1",
    "bodyLen": 94334,
    "ready": "complete",
    "tabs": 1,
    "hasScan": "function",
    "xterm": 1,
}


class VerdictTest(unittest.TestCase):
    def test_green_names_what_it_saw(self):
        status, detail = rc.webview_verdict(dict(GOOD), "1.2.3-RC1", 1.1)
        self.assertEqual(status, rc.PASS)
        self.assertIn("1.2.3-RC1", detail)
        self.assertIn("94334", detail)
        self.assertIn("1 个标签", detail)

    def test_no_page_is_red_and_says_it_never_got_in(self):
        status, detail = rc.webview_verdict(None, "1.2.3-RC1", 20.0,
                                            "调试口里的页面一直是 about:blank")
        self.assertEqual(status, rc.FAIL)
        self.assertIn("没进到界面", detail)
        self.assertIn("about:blank", detail)

    def test_not_complete_is_red(self):
        sig = dict(GOOD, ready="loading")
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("loading", detail)

    def test_err_title_is_red(self):
        sig = dict(GOOD, title="ERR: something broke")
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("ERR:", detail)

    def test_version_drift_is_untested_not_red(self):
        # 不是本版构建出来的 exe：界面在真 webview 里对不对，这轮压根没核到。
        # 按 RC6 的口径要报「未验」——红的意思是功能坏了，这里只是手上这份不是本版。
        sig = dict(GOOD, ver="1.2.2-RC10")
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.SKIP)
        self.assertIn("1.2.2-RC10", detail)
        self.assertIn("1.2.3-RC1", detail)
        self.assertIn("没核到", detail)

    def test_empty_version_is_red(self):
        sig = dict(GOOD, ver="")
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("span.ver", detail)

    def test_empty_version_carries_site_signals(self):
        # 空版本串要分清是旧骨架还是 app.js 炸了：失败结论里得带上 ready / DOM / xterm 现场
        sig = dict(GOOD, ver="", ready="complete", bodyLen=4096, xterm=0)
        _, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertIn("complete", detail)
        self.assertIn("4096", detail)
        self.assertIn("xterm 0", detail)

    def test_app_js_not_run_is_red(self):
        sig = dict(GOOD, hasScan="undefined")
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("app.js", detail)

    def test_no_terminal_is_red(self):
        sig = dict(GOOD, xterm=0)
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("终端对象", detail)

    def test_skeleton_dom_is_red(self):
        sig = dict(GOOD, bodyLen=4096)
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn(str(rc.WEBVIEW_MIN_DOM), detail)

    def test_probe_exception_is_red(self):
        sig = dict(GOOD, exception="SyntaxError: Unexpected identifier")
        status, detail = rc.webview_verdict(sig, "1.2.3-RC1", 3.0)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("SyntaxError", detail)


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.src = RC_PY.read_text(encoding="utf-8")

    def test_in_plan_table(self):
        self.assertRegex(self.src, r'\("A36",\s*"窗口起来了')

    def test_in_dispatch_chain(self):
        self.assertIn('elif code == "A36":', self.src)
        self.assertIn("a36_webview()", self.src)

    def test_waits_for_real_navigation_not_about_blank(self):
        # 等的是真导航到 tauri.localhost：about:blank 那份 target 一开始就在
        self.assertIn("tauri.localhost", self.src)

    def test_opens_debug_port_only_for_the_child(self):
        self.assertIn("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", self.src)
        # 端口不许写死：占上了就整项误红
        self.assertIn("def free_port(", self.src)
        self.assertIn("port = port or free_port()", self.src)

    def test_compares_against_repo_version(self):
        self.assertRegex(self.src, r"probe_webview\(exe, current_version\(\)")

    def test_expr_reads_the_signals_the_verdict_uses(self):
        for key in ("title", "ver", "bodyLen", "ready", "tabs", "hasScan", "xterm"):
            self.assertIn(f"{key}:", self.src, f"表达式里少了 {key}")

    def test_waits_for_ready_state_before_judging(self):
        # 导航到了 ≠ 解析完了：不带这个等待，第一眼看到的就是 interactive，会假红
        self.assertIn("WEBVIEW_READY_WAIT", self.src)
        self.assertIn('sig.get("ready") == "complete"', self.src)

    def test_kills_the_tree_after_probe(self):
        # 拉起过就必须收干净（RC7 立的规矩）
        body = self.src.split("def probe_webview(", 1)[1].split("def a36_webview", 1)[0]
        self.assertRegex(body, r"finally:\s*\n\s*if proc.poll\(\) is None:\s*\n\s*kill\(proc.pid\)")


if __name__ == "__main__":
    unittest.main()
