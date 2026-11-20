"""A41 的单测：把「最后两条自检也进真窗口」这件事逐条钉住。

这里钉四件事：
① 判据第一层是「这轮真跑在我的真后端 / 真偏好上」：没有 Tauri 桥、偏好是空的（一次性 profile）、
   底色跟真 app-data 的 `theme.txt` 对不上、后端一问不回话——任一条都算「没核」，不许报绿；
② 第二层是两条自检自己的标题，拿各自前缀对，堵死「读到上一条标题」那个坑；
③ 第三层是后端三份文件（theme.txt / sessions.json / known_hosts）跑完必须回到跑前字节，
   而且「量不到」也算没收干净（只信还原函数返回值那次就是被这条判据救回来的）；
④ 接线：不得给子进程换 profile（要的就是真偏好）、计划表与分派链里有 A41、只 Windows 上跑。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


def rows_of(*specs) -> list:
    return [(hook, expect, title) for hook, expect, title in specs]


class BackendAliveTest(unittest.TestCase):
    def test_number_means_alive(self):
        ok, why = rc.backend_alive(12)
        self.assertTrue(ok)
        self.assertIn("12 字节", why)

    def test_zero_bytes_still_alive(self):
        # 空会话清单也是「回话了」：后端活着比回了多少更要紧
        ok, _ = rc.backend_alive(0)
        self.assertTrue(ok)

    def test_err_prefix_is_dead(self):
        ok, why = rc.backend_alive("ERR 后端没开")
        self.assertFalse(ok)
        self.assertIn("后端没开", why)

    def test_none_is_dead(self):
        ok, why = rc.backend_alive(None)
        self.assertFalse(ok)
        self.assertIn("没回话", why)

    def test_garbage_is_dead(self):
        ok, why = rc.backend_alive("随便一句")
        self.assertFalse(ok)
        self.assertIn("说不清", why)


class RealProofTest(unittest.TestCase):
    def _proof(self, **kw):
        base = {"bridge": True, "keys": 6, "themePref": "light", "themeNow": "light"}
        base.update(kw)
        return base

    def test_all_good_gives_empty(self):
        self.assertEqual(rc.real_proof_bad(self._proof(), b"light", (True, "0 字节")), [])

    def test_missing_proof_is_bad(self):
        bad = rc.real_proof_bad(None, b"light", (True, "0 字节"))
        self.assertEqual(len(bad), 1)
        self.assertIn("量不到现场", bad[0])

    def test_no_tauri_bridge_is_bad(self):
        bad = rc.real_proof_bad(self._proof(bridge=False), b"light", (True, "0 字节"))
        self.assertIn("没有 Tauri 桥", bad[0])

    def test_empty_localstorage_is_bad(self):
        bad = rc.real_proof_bad(self._proof(keys=0, themePref=None), b"light", (True, "0 字节"))
        text = "；".join(bad)
        self.assertIn("一次性 profile", text)

    def test_missing_theme_pref_is_bad(self):
        bad = rc.real_proof_bad(self._proof(themePref=None), b"light", (True, "0 字节"))
        self.assertIn("portio.theme", "；".join(bad))

    def test_theme_mismatch_is_bad(self):
        bad = rc.real_proof_bad(self._proof(themeNow="dark"), b"light", (True, "0 字节"))
        self.assertIn("对不上", "；".join(bad))

    def test_missing_theme_file_is_bad(self):
        bad = rc.real_proof_bad(self._proof(), None, (True, "0 字节"))
        self.assertIn("theme.txt", "；".join(bad))

    def test_backend_silent_is_bad(self):
        bad = rc.real_proof_bad(self._proof(), b"light", (False, "后端没回话"))
        self.assertIn("后端没回话", "；".join(bad))

    def test_backend_not_asked_is_bad(self):
        bad = rc.real_proof_bad(self._proof(), b"light", None)
        self.assertIn("没敢问后端", "；".join(bad))

    def test_theme_file_with_trailing_newline_still_matches(self):
        # theme.txt 是后端写的，末尾可能带一个换行；比的是主题名不是字节数
        self.assertEqual(rc.real_proof_bad(self._proof(), b"light\n", (True, "0 字节")), [])


class QuietVerdictTest(unittest.TestCase):
    def _green(self):
        return rows_of(
            ("net-fail-test", "NET-FAIL-SELFTEST-OK", 'NET-FAIL-SELFTEST-OK {"failed":2}'),
            ("connect-entry-test", "CONNECT-ENTRY-SELFTEST-OK",
             'CONNECT-ENTRY-SELFTEST-OK {"fresh":{"port":"22"}}'),
        )

    def test_both_green(self):
        status, detail = rc.quiet_verdict(self._green(), [], [])
        self.assertEqual(status, rc.PASS)
        self.assertIn("真窗口", detail)
        self.assertIn("net-fail-test", detail)
        self.assertIn("connect-entry-test", detail)

    def test_untouched_says_so_instead_of_overclaiming(self):
        # 这两条本来就不写盘：别把「什么都没动」说成「收回来了」，那是替它们担了不该担的保
        status, detail = rc.quiet_verdict(self._green(), [], [], [])
        self.assertEqual(status, rc.PASS)
        self.assertIn("一个字节没动", detail)
        self.assertIn("护栏", detail)

    def test_changed_files_are_named(self):
        status, detail = rc.quiet_verdict(self._green(), [], [], ["sessions.json"])
        self.assertEqual(status, rc.PASS)
        self.assertIn("sessions.json", detail)
        self.assertIn("收回", detail)

    def test_empty_rows_is_fail(self):
        status, detail = rc.quiet_verdict([], [], [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("一条自检都没跑", detail)

    def test_wrong_prefix_is_fail(self):
        rows = rows_of(("net-fail-test", "NET-FAIL-SELFTEST-OK", "SESSIONS-SELFTEST-OK {}"))
        status, detail = rc.quiet_verdict(rows, [], [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("net-fail-test", detail)

    def test_selftest_fail_listed(self):
        rows = rows_of(("connect-entry-test", "CONNECT-ENTRY-SELFTEST-OK",
                        'CONNECT-ENTRY-SELFTEST-FAIL ["双击会话 端口：8022 ≠ 22"] {}'))
        status, detail = rc.quiet_verdict(rows, [], [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("8022", detail)

    def test_proof_failure_blocks_green(self):
        # 自检全绿但没证明跑在我的真偏好上：这就是「没核」，不许混进通过
        status, detail = rc.quiet_verdict(self._green(), ["localStorage 是空的"], [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("没证明", detail)
        self.assertIn("localStorage 是空的", detail)

    def test_residue_blocks_green(self):
        status, detail = rc.quiet_verdict(self._green(), [], ["sessions.json"])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("sessions.json", detail)

    def test_err_title_is_fail(self):
        rows = rows_of(("net-fail-test", "NET-FAIL-SELFTEST-OK", "ERR: 炸在启动里"))
        status, _ = rc.quiet_verdict(rows, [], [])
        self.assertEqual(status, rc.FAIL)


class FakeProc:
    def __init__(self):
        self.pid = 4242
        self.killed = False

    def poll(self):
        return None


class ProbeRunTest(unittest.TestCase):
    """真跑一遍 probe（后端、调试口、进程全拿假的），核它的顺序与判据。"""

    def setUp(self):
        self.old_targets = rc.cdp_targets
        self.old_port = rc.free_port
        rc.cdp_targets = lambda port, timeout=1.0: [
            {"url": "http://tauri.localhost/", "webSocketDebuggerUrl": "ws://x"}]
        rc.free_port = lambda: 65535
        self.proc = FakeProc()
        self.killed = []
        self.env = {}
        self.before = {
            "theme.txt": {"path": "t", "stamp": {}, "bytes": b"light"},
            "sessions.json": {"path": "s", "stamp": {}, "bytes": None},
            "known_hosts": {"path": "k", "stamp": {}, "bytes": b"h"},
        }
        self.settled = {k: {"path": v["path"], "stamp": {}, "bytes": v["bytes"]}
                        for k, v in self.before.items()}

    def tearDown(self):
        rc.cdp_targets = self.old_targets
        rc.free_port = self.old_port

    def _value(self, ws, expr, timeout=8.0):
        if expr == rc.VER_EXPR:
            return "1.0.9-RC6"
        if expr == rc.A41_PROOF_EXPR:
            return json.dumps({"bridge": True, "keys": 6, "themePref": "light",
                               "themeNow": "light"})
        if expr == rc.WEBVIEW_BACKUP_EXPR:
            return "{}"
        return "complete"

    def _call(self, ws, method, params, timeout=8.0):
        return {"id": 1, "result": {"result": {"value": 5}}}

    def _runner(self, ws, hook, expect, wait=None):
        return hook, expect, f"{expect} {{}}"

    def _popen(self, cmd, **kw):
        self.env = kw.get("env") or {}
        return self.proc

    def _kill(self, pid):
        self.killed.append(pid)

    def _collect(self):
        return self.before if not self.killed else self.settled

    def test_changed_detected_before_restore(self):
        """收之前那一量：这次跑到底动没动我的盘，得量出来再收（收好了也该如实写「动过」）。"""
        touched = {k: {"path": v["path"], "stamp": {}, "bytes": v["bytes"]}
                   for k, v in self.before.items()}
        touched["sessions.json"] = {"path": "s", "stamp": {}, "bytes": b"[]"}
        state = {"done": False, "n": 0}

        def collect():
            state["n"] += 1
            if state["done"]:
                return self.before
            # 第一次（跑前）是真的原样，第二次（收之前）模拟「有东西动了」
            return self.before if state["n"] == 1 else touched

        def kill(pid):
            state["done"] = True
            self.killed.append(pid)

        status, detail = rc.probe_quiet_selftests(
            Path("x.exe"), "1.0.9-RC6", wait=5.0, popen=self._popen, kill=kill,
            value=self._value, call=self._call, runner=self._runner, sleep=lambda s: None,
            collect=collect, restore=lambda b: [])
        self.assertEqual(status, rc.PASS, detail)
        self.assertIn("sessions.json", detail)
        self.assertIn("收回", detail)

    def _run(self, restore=lambda before: []):
        return rc.probe_quiet_selftests(
            Path("x.exe"), "1.0.9-RC6", wait=5.0, popen=self._popen, kill=self._kill,
            value=self._value, call=self._call, runner=self._runner,
            sleep=lambda s: None, collect=self._collect, restore=restore)

    def test_green_path(self):
        status, detail = self._run()
        self.assertEqual(status, rc.PASS, detail)
        self.assertIn("真窗口", detail)

    def test_no_fresh_profile_given_to_child(self):
        # 这一条是 A41 的立身之本：要的就是我的真偏好，不能再给一次性 profile
        self._run()
        self.assertNotIn("WEBVIEW2_USER_DATA_FOLDER", self.env)
        self.assertIn("--remote-debugging-port", self.env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"])

    def test_process_killed(self):
        self._run()
        self.assertEqual(self.killed, [4242])

    def test_residue_blocks_green(self):
        status, detail = self._run(restore=lambda before: ["sessions.json"])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("sessions.json", detail)

    def test_version_drift_is_skip(self):
        status, detail = rc.probe_quiet_selftests(
            Path("x.exe"), "1.0.9-RC7", wait=5.0, popen=self._popen, kill=self._kill,
            value=lambda ws, expr, timeout=8.0: "1.0.9-RC6" if expr == rc.VER_EXPR else "{}",
            call=self._call, runner=self._runner, sleep=lambda s: None,
            collect=self._collect, restore=lambda b: [])
        self.assertEqual(status, rc.SKIP)
        self.assertIn("不是本版构建", detail)

    def test_selftest_failure_is_fail(self):
        status, detail = rc.probe_quiet_selftests(
            Path("x.exe"), "1.0.9-RC6", wait=5.0, popen=self._popen, kill=self._kill,
            value=self._value, call=self._call, sleep=lambda s: None,
            collect=self._collect, restore=lambda b: [],
            runner=lambda ws, hook, expect, wait=None: (hook, expect, "ERR: 启动就炸"))
        self.assertEqual(status, rc.FAIL)


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.text = RC_PY.read_text(encoding="utf-8")

    def test_plan_has_a41(self):
        self.assertIn('("A41"', self.text)

    def test_dispatch_has_elif(self):
        self.assertIn('elif code == "A41"', self.text)

    def test_header_counts_to_last_item(self):
        # 同上：不写死编号，按计划表里最大的那个编号比
        import re

        m = re.search(r"A1–A(\d+)", self.text)
        self.assertIsNotNone(m)
        last = max(int(n) for n in re.findall(r'\("A(\d+)"', self.text))
        self.assertEqual(int(m.group(1)), last)

    def test_two_hooks_are_the_leftovers(self):
        hooks = [h for h, _ in rc.A41_SELFTESTS]
        self.assertEqual(hooks, ["net-fail-test", "connect-entry-test"])

    def test_uses_a39_backup_set(self):
        body = self.text.split("def probe_quiet_selftests", 1)[1]
        self.assertIn("collect_app_state", body.split("->")[0])
        self.assertIn("restore_app_state", body.split("->")[0])
        self.assertEqual(rc.A41_SELFTESTS and rc.APP_DATA_BACKUP,
                         ("theme.txt", "sessions.json", "known_hosts"))

    def test_reads_backend_once(self):
        self.assertIn("sessions_read", rc.A41_BACKEND_EXPR)

    def test_proof_expression_is_readonly(self):
        # 证明层只许读：拿 localStorage.length / getItem / dataset 这几样
        self.assertIn("localStorage.length", rc.A41_PROOF_EXPR)
        self.assertNotIn("setItem", rc.A41_PROOF_EXPR)
        self.assertNotIn("clear", rc.A41_PROOF_EXPR)

    def test_windows_only(self):
        body = self.text.split("def a41_real_selftests", 1)[1]
        self.assertIn('sys.platform != "win32"', body)

    def test_restore_before_settle(self):
        body = self.text.split("def probe_quiet_selftests", 1)[1]
        self.assertLess(body.index("restore(before)"), body.index("residue_bad(before, settled)"))

    def test_no_global_env_mutation(self):
        body = self.text.split("def probe_quiet_selftests", 1)[1]
        self.assertNotIn("os.environ[", body)


if __name__ == "__main__":
    unittest.main()
