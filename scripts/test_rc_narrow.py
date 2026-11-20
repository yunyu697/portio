"""A40 的单测：把「窄窗那条自检在真窗口里按两档视口跑」这件事逐条钉住。

这里钉五件事：
① 判据第一层是「视口真换过来了」：界面自报的 innerWidth 与我要求的那档对不上，
   就是拿一档宽窗冒充窄窗——自检再绿也不算核过（反向验证就是这么翻红的）；
② 第二层是「两档真是两个宽度」：几何一模一样说明压根没重排，那也只核了一档；
③ 换视口是会话级命令：断一次就失效，所以两档得在同一根会话里跑完；
④ 隔离照旧：一次性 profile，跑完核我自己的偏好库一个字节没动、底色文件写回原样；
⑤ 计划表 / 分派链 / 只 Windows / 删临时目录这些接线别漏。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


def title_of(width: int, term: int, rows_extra: dict | None = None) -> str:
    rows = {
        "menu": {"sideW": 180},
        "drawer": {"h": 28},
        "fold": {"split": term + 11, "files": 0, "term": term, "gutter": 10},
    }
    rows.update(rows_extra or {})
    return f"{rc.NARROW_EXPECT} w={width} " + json.dumps(rows)


def rows_of(*specs) -> list:
    """按 (tag, title, seen) 拼出 run_narrow 的那一行四元组。"""
    out = []
    for tag, title, seen in specs:
        out.append((tag, rc.NARROW_EXPECT, title, seen))
    return out


class NarrowRowsTest(unittest.TestCase):
    def test_pulls_json_out_of_title(self):
        rows = rc.narrow_rows(title_of(1024, 834))
        self.assertEqual(rows["fold"]["term"], 834)

    def test_no_json_gives_empty(self):
        self.assertEqual(rc.narrow_rows("NARROW-SELFTEST-FAIL 导入下拉右侧越出侧栏 3px"), {})

    def test_broken_json_gives_empty(self):
        self.assertEqual(rc.narrow_rows("NARROW-SELFTEST-OK w=900 {oops"), {})

    def test_empty_title_gives_empty(self):
        self.assertEqual(rc.narrow_rows(""), {})


class ReportedWidthTest(unittest.TestCase):
    def test_reads_the_w(self):
        self.assertEqual(rc.reported_width("NARROW-SELFTEST-OK w=1024 {}"), 1024)

    def test_reads_the_big_one(self):
        self.assertEqual(rc.reported_width("NARROW-SELFTEST-FAIL w=1180 []"), 1180)

    def test_none_when_absent(self):
        self.assertIsNone(rc.reported_width("ERR: 炸了"))


class VerdictTest(unittest.TestCase):
    def _green(self):
        return rows_of(
            ("1024x620", title_of(1024, 834), 1024),
            ("900x620", title_of(900, 710), 900),
        )

    def test_two_widths_green(self):
        status, detail = rc.narrow_verdict(self._green(), True, True, True)
        self.assertEqual(status, rc.PASS)
        self.assertIn("1024 宽 834px", detail)
        self.assertIn("900 宽 710px", detail)
        self.assertIn("视口是真换过来的", detail)
        self.assertIn("一个字节没动", detail)

    def test_nothing_ran_is_red(self):
        status, detail = rc.narrow_verdict([], True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("没跑齐", detail)

    def test_one_width_only_is_red(self):
        status, detail = rc.narrow_verdict(self._green()[:1], True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("没跑齐", detail)

    def test_engine_err_is_red(self):
        rows = self._green()
        rows[0] = ("1024x620", rc.NARROW_EXPECT, "ERR: 导入下拉越界", 1024)
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("1024x620", detail)

    def test_wrong_prefix_is_red(self):
        rows = self._green()
        rows[1] = ("900x620", rc.NARROW_EXPECT, "NARROW-SELFTEST-FAIL w=900 []", 900)
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("期望以", detail)

    def test_measured_at_wider_window_is_red(self):
        # 关键那层：界面还停在 1180，自检照样报绿——这档根本没在窄窗里跑
        rows = self._green()
        rows[0] = ("1024x620", rc.NARROW_EXPECT, title_of(1180, 950), 1180)
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("1180 宽里量的", detail)
        self.assertIn("没在窄窗里跑", detail)

    def test_viewport_not_applied_is_red(self):
        # 自检嘴上说自己 1024，界面实际视口却是 1180：视口命令没生效，这是假核
        rows = self._green()
        rows[0] = ("1024x620", rc.NARROW_EXPECT, title_of(1024, 834), 1180)
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("视口没换过来", detail)

    def test_same_geometry_is_red(self):
        # 两档都报绿、宽度也都对，但几何一模一样：说明界面对着同一个宽度量的，只核了一档
        rows = rows_of(
            ("1024x620", title_of(1024, 834), 1024),
            ("900x620", title_of(900, 834), 900),
        )
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("两档没真重排", detail)

    def test_wider_terminal_on_narrower_viewport_is_red(self):
        rows = rows_of(
            ("1024x620", title_of(1024, 710), 1024),
            ("900x620", title_of(900, 834), 900),
        )
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("两档没真重排", detail)

    def test_missing_term_geometry_is_red(self):
        rows = rows_of(
            ("1024x620", f"{rc.NARROW_EXPECT} w=1024 " + json.dumps({"fold": {"files": 0}}), 1024),
            ("900x620", title_of(900, 710), 900),
        )
        status, detail = rc.narrow_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("量不到折叠态终端宽度", detail)

    def test_fresh_profile_missing_is_red(self):
        status, detail = rc.narrow_verdict(self._green(), False, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("隔离没生效", detail)

    def test_real_profile_touched_is_red(self):
        status, detail = rc.narrow_verdict(self._green(), True, False, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("隔离没挡住", detail)

    def test_unmeasured_real_profile_is_red(self):
        # 量不到「有没有被动」不算核过：宁可红，也不许含糊成通过
        status, detail = rc.narrow_verdict(self._green(), True, None, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("量不到", detail)

    def test_theme_not_restored_is_red(self):
        status, detail = rc.narrow_verdict(self._green(), True, True, False)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("theme.txt", detail)


class FakeWs:
    """假 websocket：记下发出去的字、按顺序吐回预置的帧。"""

    def __init__(self, replies):
        self.sent = []
        self.replies = list(replies)
        self.closed = False

    def close(self):
        self.closed = True


class CdpSessionTest(unittest.TestCase):
    def _session(self, replies):
        ws = FakeWs(replies)
        old = (rc.ws_open, rc.ws_send_text, rc.ws_recv_frame)
        rc.ws_open = lambda url, timeout=8.0: ws
        rc.ws_send_text = lambda sock, payload: sock.sent.append(payload)
        rc.ws_recv_frame = lambda sock: (True, sock.replies.pop(0))
        sess = rc.CdpSession("ws://x")
        return sess, ws, old

    def tearDown(self):
        if getattr(self, "_old", None):
            rc.ws_open, rc.ws_send_text, rc.ws_recv_frame = self._old

    def test_sends_incrementing_ids(self):
        sess, ws, self._old = self._session([
            json.dumps({"id": 1, "result": {}}).encode(),
            json.dumps({"id": 2, "result": {}}).encode(),
        ])
        sess.call("Emulation.setDeviceMetricsOverride", {"width": 1024})
        sess.call("Page.navigate", {"url": "http://tauri.localhost/"})
        ids = [json.loads(p.decode())["id"] for p in ws.sent]
        self.assertEqual(ids, [1, 2])
        self.assertEqual(json.loads(ws.sent[0].decode())["method"],
                         "Emulation.setDeviceMetricsOverride")

    def test_skips_events_and_waits_for_own_id(self):
        sess, ws, self._old = self._session([
            json.dumps({"method": "Page.loadEventFired", "params": {}}).encode(),
            json.dumps({"id": 1, "result": {"value": "ok"}}).encode(),
        ])
        msg = sess.call("Runtime.evaluate", {"expression": "1"})
        self.assertEqual(msg["id"], 1)

    def test_value_unwraps_and_raises(self):
        sess, ws, self._old = self._session([
            json.dumps({"id": 1, "result": {"result": {"value": 1180}}}).encode(),
            json.dumps({"id": 2, "result": {},
                        "exceptionDetails": {"text": "炸了",
                                              "exception": {"description": "ReferenceError: x"}}}).encode(),
        ])
        self.assertEqual(sess.value("window.innerWidth"), 1180)
        with self.assertRaises(RuntimeError) as cm:
            sess.value("boom()")
        self.assertIn("ReferenceError", str(cm.exception))

    def test_close_closes_socket(self):
        sess, ws, self._old = self._session([])
        sess.close()
        self.assertTrue(ws.closed)


class FakeSess:
    """记下调用顺序的假会话。"""

    def __init__(self, titles, widths):
        self.calls = []
        self._titles = list(titles)
        self._widths = list(widths)

    def call(self, method, params, timeout=8.0):
        self.calls.append((method, params))
        return {"id": len(self.calls), "result": {}}

    def value(self, expr, timeout=8.0):
        if not self._titles:
            return "{}"
        title = self._titles.pop(0)
        w = self._widths.pop(0)
        return json.dumps({"hash": "#narrow-test", "ready": "complete", "title": title, "w": w})


class RunNarrowTest(unittest.TestCase):
    def test_viewport_set_before_navigate(self):
        sess = FakeSess([title_of(1024, 834)], [1024])
        tag, expect, title, seen = rc.run_narrow(sess, 1024, 620, wait=1.0)
        self.assertEqual(tag, "1024x620")
        self.assertEqual(seen, 1024)
        self.assertTrue(title.startswith(rc.NARROW_EXPECT))
        methods = [m for m, _ in sess.calls]
        self.assertEqual(methods[0], "Emulation.setDeviceMetricsOverride")
        self.assertEqual(methods[1], "Page.navigate")

    def test_navigate_url_carries_query_and_hash(self):
        sess = FakeSess([title_of(900, 710)], [900])
        rc.run_narrow(sess, 900, 620, wait=1.0)
        url = sess.calls[1][1]["url"]
        self.assertIn("?nw=900x620", url)
        self.assertIn("#narrow-test", url)

    def test_times_out_with_empty_title(self):
        # 一直读不到结果：不许悄悄算过，回一个空标题让判据去红
        sess = FakeSess([], [])
        tick = [0.0]

        def clock():
            tick[0] += 5.0
            return tick[0]

        tag, expect, title, seen = rc.run_narrow(sess, 1024, 620, wait=1.0,
                                                 sleep=lambda s: None, clock=clock)
        self.assertEqual(title, "")
        self.assertEqual(seen, 0)


class SetViewportTest(unittest.TestCase):
    def test_accepted_when_no_error(self):
        class S:
            def call(self, method, params, timeout=8.0):
                return {"id": 1, "result": {}}

        self.assertTrue(rc.set_viewport(S(), 1024, 620))

    def test_rejected_when_error(self):
        class S:
            def call(self, method, params, timeout=8.0):
                return {"id": 1, "error": {"code": -32000, "message": "nope"}}

        self.assertFalse(rc.set_viewport(S(), 1024, 620))


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.text = RC_PY.read_text(encoding="utf-8")

    def test_plan_has_a40(self):
        self.assertIn('("A40"', self.text)

    def test_dispatch_has_elif(self):
        self.assertIn('elif code == "A40"', self.text)

    def test_two_viewports_1024_and_900(self):
        self.assertEqual(rc.NARROW_VIEWPORTS[0][0], 1024)
        self.assertEqual(rc.NARROW_VIEWPORTS[1][0], 900)

    def test_header_counts_to_last_item(self):
        # 别写死编号：每加一项就得改一次测试，改漏了这条测试反而替错误背书
        import re

        m = re.search(r"A1–A(\d+)", self.text)
        self.assertIsNotNone(m, "头部那句「对应 A1–A<最后一项>」不见了")
        last = max(int(n) for n in re.findall(r'\("A(\d+)"', self.text))
        self.assertEqual(int(m.group(1)), last)

    def test_uses_emulation_command(self):
        self.assertIn("Emulation.setDeviceMetricsOverride", self.text)

    def test_session_is_long_lived(self):
        # 视口命令是会话级的：两档必须在一根会话里跑完，不许每次都开新会话
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertLess(body.index("sess = opener("), body.index("for width, height in views"))
        self.assertNotIn("run_narrow(ws", body)

    def test_session_closed_in_finally(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertLess(body.index("finally:"), body.index("sess.close()"))

    def test_fresh_profile_used_and_removed(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertIn("WEBVIEW2_USER_DATA_FOLDER", body)
        self.assertIn("portio-narrow-", body)
        self.assertIn("rmtree(prof", body)

    def test_real_profile_checked(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertIn("profile_stamp(db)", body)
        self.assertIn("restore_bytes(theme, theme_before)", body)

    def test_kill_after_runs(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertLess(body.index("for width, height in views"), body.index("kill(proc.pid)"))

    def test_env_only_for_child(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertNotIn("os.environ[", body)

    def test_windows_only(self):
        body = self.text.split("def a40_narrow_viewports", 1)[1]
        self.assertIn('sys.platform != "win32"', body)

    def test_version_drift_is_skip_not_fail(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertIn("return SKIP,", body)
        self.assertIn("不是本版构建", body)

    def test_verdict_receives_four_layers(self):
        body = self.text.split("def probe_narrow", 1)[1]
        self.assertIn("narrow_verdict(rows, fresh_used, db_before == db_after, theme_ok)", body)


if __name__ == "__main__":
    unittest.main()
