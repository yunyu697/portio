"""RC9 单测：自家残留进程回收 + 早退归因。

整跑里 A37 撞过一次 WebView2 `0x800700AA 请求的资源在使用中`（码 101）：上一个探针
没退净的浏览器进程占着 EBWebView 目录，下一个探针拉起就炸。这里钉三件事：
① 只认命令行指向本应用的进程，别家 webview2 不碰；
② 残留先收掉、再等树退净，没收净的要点名；
③ 进程早退时从日志尾部把占用 / panic 翻成人话，不许只丢一个退出码。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


class OwnProcTest(unittest.TestCase):
    def test_parse_lines_keeps_pid_name_cmd(self):
        text = ("20604|portio-app.exe|D:\\portio-target\\release\\portio-app.exe\n"
                "43096|msedgewebview2.exe|--user-data-dir=C:\\Users\\x\\io.portio.desktop\\EBWebView\n")
        rows = rc._parse_own_proc_lines(text)
        self.assertEqual(rows[0]["pid"], 20604)
        self.assertEqual(rows[0]["name"], "portio-app.exe")
        self.assertEqual(rows[1]["name"], "msedgewebview2.exe")
        self.assertIn("io.portio.desktop", rows[1]["cmd"])

    def test_enum_none_is_empty(self):
        # 单测环境不真扫机器：不传 enum 就是空列表，不会去 shell PowerShell
        self.assertEqual(rc.own_processes(None), [])

    def test_enum_injected_rows_pass_through(self):
        rows = [{"pid": 7, "name": "msedgewebview2.exe", "cmd": "x"}]
        self.assertEqual(rc.own_processes(lambda: rows), rows)


class ReapTest(unittest.TestCase):
    def test_clean_machine_kills_nothing(self):
        killed = []
        left = rc.reap_own_processes(kill=killed.append, enum=lambda: [],
                                     sleep=lambda _: None)
        self.assertEqual(left, [])
        self.assertEqual(killed, [])

    def test_leftover_killed_then_drains(self):
        calls = iter([
            [{"pid": 11, "name": "portio-app.exe", "cmd": ""},
             {"pid": 12, "name": "msedgewebview2.exe", "cmd": ""}],
            [],
        ])
        killed = []
        left = rc.reap_own_processes(kill=killed.append, enum=lambda: next(calls),
                                     sleep=lambda _: None)
        self.assertEqual(left, [])
        self.assertEqual(sorted(killed), [11, 12])

    def test_still_alive_after_timeout_returns_survivors(self):
        alive = [{"pid": 11, "name": "portio-app.exe", "cmd": ""}]
        clock = {"t": 0.0}
        left = rc.reap_own_processes(
            kill=lambda _pid: None, enum=lambda: alive, wait=2.0,
            sleep=lambda _: clock.__setitem__("t", clock["t"] + 1),
            clock=lambda: clock["t"])
        self.assertEqual(left, [11])

    def test_kill_receives_pid_only(self):
        seen = []
        rows = [{"pid": 31337, "name": "portio-app.exe", "cmd": ""}]
        rc.reap_own_processes(kill=seen.append, enum=lambda: rows,
                              sleep=lambda _: None)
        self.assertEqual(seen, [31337])


class ClassifyTest(unittest.TestCase):
    def test_webview_lock_is_named(self):
        reason = rc.classify_panic("0x800700AA 请求的资源在使用中")
        self.assertIn("0x800700AA", reason)
        self.assertIn("占用", reason)

    def test_rust_panic_is_named(self):
        reason = rc.classify_panic("panicked at tauri-2.12.6/src/app.rs:1444")
        self.assertIn("panic", reason)

    def test_setup_window_failure_is_named(self):
        reason = rc.classify_panic(
            '[ERROR] [setup] 窗口 / WebView2 创建失败：Webview2 初始化失败 → 拒绝访问')
        self.assertIn("WebView2", reason)
        self.assertIn("setup", reason)

    def test_plain_log_is_empty_reason(self):
        self.assertEqual(rc.classify_panic("[INFO] [app] Portio 启动"), "")


class LogTailTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="portio-reap-"))
        log_dir = self.base / "io.portio.desktop" / "logs"
        log_dir.mkdir(parents=True)
        (log_dir / "portio.log").write_text(
            "\n".join(f"line-{i}" for i in range(30)), encoding="utf-8")

    def test_tail_only_last_n_lines(self):
        tail = rc.app_log_tail(lines=5, env={"LOCALAPPDATA": str(self.base)})
        self.assertEqual(tail.splitlines(), [f"line-{i}" for i in range(25, 30)])

    def test_missing_log_is_empty(self):
        self.assertEqual(rc.app_log_tail(env={"LOCALAPPDATA": str(self.base / "nope")}), "")


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.src = RC_PY.read_text(encoding="utf-8")

    def test_each_probe_reaps_before_and_after(self):
        for fn in ("probe_launch", "probe_webview", "probe_selftests"):
            body = self.src.split(f"def {fn}(", 1)[1].split("def ", 1)[0]
            self.assertIn("reap_own_processes", body, f"{fn} 没接残留回收")

    def test_real_call_sites_pass_system_enum(self):
        self.assertIn("enum=_win32_own_processes", self.src)

    def test_fast_exit_reads_log_reason(self):
        self.assertIn("classify_panic(app_log_tail())", self.src)

    def test_foreign_webview2_not_matched_by_name_alone(self):
        # 别家 webview2（clash-verge / GameViewer / SearchHost）命令行不带本应用标记，
        # 解析层只认行里给的标记；枚举匹配在 PS 那侧，这里钉死解析不按进程名瞎收。
        rows = rc._parse_own_proc_lines("999|msedgewebview2.exe|--user-data-dir=C:\\clash\\x")
        self.assertEqual(rows[0]["cmd"], "--user-data-dir=C:\\clash\\x")
        self.assertNotIn("io.portio", rows[0]["cmd"])


if __name__ == "__main__":
    unittest.main()
