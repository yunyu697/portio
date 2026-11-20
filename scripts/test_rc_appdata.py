"""A39 的单测：把「后端那几份文件先存、跑完收回、再核对」这件事逐条钉住。

这里钉四件事：
① 判据是分层的：自检过没过、它到底有没有在真后端上落盘、我有没有把落下去的收回来——
   少一层就等于「绿了但其实没核」或者「核了但把我的会话清单搞没了」；
② 收回的口径是字节级的：原来有就按原字节写回再读一遍核对，原来没有就把测试自己造的那份收走；
③ 跑之前必须先把字节存下来、而且必须在进程收掉之后才去量——进程还活着时后端可能正写在半截；
④ 后端目录换不了（APPDATA 白改）：这条得写进代码注释里，别人别以为能靠环境变量隔离。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


class VerdictTest(unittest.TestCase):
    def _rows(self, bad_index: int | None = None, title: str = "") -> list:
        rows = []
        for i, (hook, expect) in enumerate(rc.A39_SELFTESTS):
            rows.append((hook, expect, title if i == bad_index else expect))
        return rows

    def test_all_green_names_both_hooks(self):
        status, detail = rc.app_files_verdict(self._rows(), True, [])
        self.assertEqual(status, rc.PASS)
        self.assertIn(str(len(rc.A39_SELFTESTS)), detail)
        self.assertIn("sessions-test", detail)
        self.assertIn("hosts-test", detail)
        self.assertIn("收回", detail)

    def test_nothing_ran_is_red(self):
        status, detail = rc.app_files_verdict([], True, [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("一条自检都没跑", detail)

    def test_hook_err_is_red(self):
        status, detail = rc.app_files_verdict(self._rows(0, "ERR: 会话列表没画出来"), True, [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("sessions-test", detail)

    def test_wrong_prefix_is_red(self):
        rows = self._rows(1, "SESSIONS-SELFTEST-OK")
        status, detail = rc.app_files_verdict(rows, True, [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("hosts-test", detail)

    def test_not_written_is_red(self):
        # 两条都绿，但 sessions.json 一点没动：那说明它们跑在没有后端的无头页里，等于没核
        status, detail = rc.app_files_verdict(self._rows(), False, [])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("sessions.json", detail)
        self.assertIn("没核", detail)

    def test_restore_failure_is_red_and_names_file(self):
        status, detail = rc.app_files_verdict(self._rows(), True, ["sessions.json"])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("sessions.json", detail)
        self.assertIn("收回原样", detail)

    def test_failure_beats_restore_note(self):
        # 自检自己红了 + 有文件没收回：先说自检红，别被后半句带走注意力
        status, detail = rc.app_files_verdict(self._rows(0, "ERR: x"), True, ["known_hosts"])
        self.assertEqual(status, rc.FAIL)
        self.assertIn("ERR: x", detail)
        self.assertNotIn("收回原样", detail)


class StampTest(unittest.TestCase):
    def test_missing_file_has_empty_stamp(self):
        self.assertEqual(rc.file_stamp(None), {"exists": False, "size": 0, "sha": "", "mtime": 0})
        self.assertEqual(rc.file_stamp(Path(tempfile.gettempdir()) / "nope-rc-a39.txt"),
                         {"exists": False, "size": 0, "sha": "", "mtime": 0})

    def test_stamp_records_size_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sessions.json"
            p.write_bytes(b"[{\"host\":\"a\"}]")
            st = rc.file_stamp(p)
            self.assertTrue(st["exists"])
            self.assertEqual(st["size"], 14)
            self.assertEqual(len(st["sha"]), 16)
            self.assertTrue(st["mtime"] > 0)

    def test_same_bytes_same_hash(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a"
            b = Path(d) / "b"
            a.write_bytes(b"same")
            b.write_bytes(b"same")
            self.assertEqual(rc.file_stamp(a)["sha"], rc.file_stamp(b)["sha"])

    def test_different_bytes_different_hash(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a"
            b = Path(d) / "b"
            a.write_bytes(b"[]")
            b.write_bytes(b"[{\"host\":\"x\"}]")
            self.assertNotEqual(rc.file_stamp(a)["sha"], rc.file_stamp(b)["sha"])
            self.assertNotEqual(rc.file_stamp(a)["size"], rc.file_stamp(b)["size"])

    def test_collect_keeps_bytes_for_restore(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"APPDATA": d}
            folder = Path(d) / rc.APP_IDENTIFIER
            folder.mkdir(parents=True)
            (folder / "sessions.json").write_bytes(b"[1]")
            state = rc.collect_app_state(("sessions.json", "known_hosts"), env=env)
            self.assertEqual(state["sessions.json"]["bytes"], b"[1]")
            self.assertIsNone(state["known_hosts"]["bytes"])
            self.assertFalse(state["known_hosts"]["stamp"]["exists"])

    def test_collect_points_into_appdata(self):
        state = rc.collect_app_state(("theme.txt",), env={"APPDATA": r"C:\fake"})
        self.assertIn(rc.APP_IDENTIFIER, state["theme.txt"]["path"])
        self.assertTrue(state["theme.txt"]["path"].endswith("theme.txt"))


class RestoreTest(unittest.TestCase):
    def test_untouched_file_counts_as_restored(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "theme.txt"
            p.write_bytes(b"light")
            state = {"theme.txt": {"path": str(p), "bytes": b"light"}}
            p.write_bytes(b"dark")
            self.assertEqual(rc.restore_app_state(state), [])
            self.assertEqual(p.read_bytes(), b"light")

    def test_missing_file_is_not_created_out_of_thin_air(self):
        # 原来就没有、跑完也没有：不该凭空写一份空的上去
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "known_hosts"
            state = {"known_hosts": {"path": str(p), "bytes": None}}
            self.assertEqual(rc.restore_app_state(state), [])
            self.assertFalse(p.exists())

    def test_test_created_file_is_taken_away(self):
        # 原来没有、跑完冒出来一份：那是这两条自检自己造的，收走（不是删用户文件）
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sessions.json"
            state = {"sessions.json": {"path": str(p), "bytes": None}}
            p.write_bytes(b"[{\"host\":\"h44.example\"}]")
            self.assertEqual(rc.restore_app_state(state), [])
            self.assertFalse(p.exists())

    def test_restore_reports_when_it_cannot_put_it_back(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sessions.json"
            state = {"sessions.json": {"path": str(p), "bytes": b"[1]"}}
            p.write_bytes(b"[2]")
            p.chmod(0o444)  # 写不动了
            bad = rc.restore_app_state(state)
            p.chmod(0o666)
            self.assertEqual(bad, ["sessions.json"])

    def test_none_path_is_ignored(self):
        self.assertEqual(rc.restore_app_state({"theme.txt": {"path": None, "bytes": b"x"}}), [])

    def test_restore_verifies_bytes_after_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "theme.txt"
            p.write_bytes(b"light")
            state = {"theme.txt": {"path": str(p), "bytes": b"light"}}
            p.write_bytes(b"dark")
            rc.restore_app_state(state)
            self.assertEqual(p.read_bytes(), b"light")


class ResidueTest(unittest.TestCase):
    """收完再独立量一遍那件事：还原函数说自己收干净了，不算数。"""

    def _state(self, bytes_map):
        return {k: {"path": f"P:{k}", "bytes": v, "stamp": {"exists": v is not None}}
                for k, v in bytes_map.items()}

    def test_all_back_to_original(self):
        self.assertEqual(rc.residue_bad(self._state({"a": b"1"}), self._state({"a": b"1"})), [])

    def test_still_different_is_named(self):
        before = self._state({"sessions.json": None})
        settled = self._state({"sessions.json": b"[45]"})
        self.assertEqual(rc.residue_bad(before, settled), ["sessions.json"])

    def test_created_file_counts_as_residue(self):
        before = self._state({"known_hosts": None})
        settled = self._state({"known_hosts": b"k"})
        self.assertEqual(rc.residue_bad(before, settled), ["known_hosts"])

    def test_unmeasured_counts_as_residue(self):
        before = self._state({"theme.txt": b"light"})
        self.assertEqual(rc.residue_bad(before, None), ["theme.txt"])

    def test_missing_entry_in_settled_is_residue(self):
        before = self._state({"theme.txt": b"light", "sessions.json": None})
        settled = {"theme.txt": self._state({"theme.txt": b"light"})["theme.txt"]}
        self.assertEqual(rc.residue_bad(before, settled), ["sessions.json"])


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.text = RC_PY.read_text(encoding="utf-8")

    def test_plan_has_a39(self):
        self.assertIn('("A39"', self.text)

    def test_dispatch_has_elif(self):
        self.assertIn('elif code == "A39"', self.text)

    def test_both_hooks_listed(self):
        self.assertIn('("sessions-test", "SESSIONS-SELFTEST-OK")', self.text)
        self.assertIn('("hosts-test", "HOSTS-SELFTEST-OK")', self.text)

    def test_backup_covers_three_files(self):
        self.assertIn('APP_DATA_BACKUP = ("theme.txt", "sessions.json", "known_hosts")', self.text)

    def test_write_proof_is_sessions_json(self):
        self.assertIn('APP_WRITE_PROOF = "sessions.json"', self.text)

    def test_state_is_collected_before_launch(self):
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertLess(body.index("before = collect()"), body.index("proc = popen"))

    def test_measure_after_kill_and_sleep(self):
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertLess(body.index("kill(proc.pid)"), body.index("after = collect()"))

    def test_restore_runs_in_finally(self):
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertLess(body.index("finally:"), body.index("restore_bad = restore(before)"))

    def test_fresh_profile_still_used(self):
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertIn("WEBVIEW2_USER_DATA_FOLDER", body)
        self.assertIn("portio-appdata-", body)

    def test_env_only_for_child(self):
        # 只许把调试口与一次性 profile 塞进子进程的 env，绝不 setenv 到本进程
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertNotIn("os.environ[", body)

    def test_windows_only(self):
        body = self.text.split("def a39_appdata_selftests", 1)[1]
        self.assertIn("sys.platform != \"win32\"", body)

    def test_version_drift_is_skip_not_fail(self):
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertIn("return SKIP,", body)
        self.assertIn("不是本版构建", body)

    def test_profile_dir_removed(self):
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertIn("rmtree(prof", body)

    def test_appdata_env_override_attempt_is_documented_as_dead(self):
        # 这条是被人试死过的事实：换 APPDATA 不管用，别有人回头又去试一遍
        self.assertIn("Known Folder API", self.text)
        self.assertIn("不认进程环境变量", self.text)

    def test_probe_rechecks_residue_independently(self):
        # 只信还原函数的返回值是不够的：收完必须自己再读一遍
        body = self.text.split("def probe_app_selftests", 1)[1]
        self.assertIn("residue_bad(before, settled)", body)
        self.assertGreater(body.index("restore_bad = restore(before)"),
                           body.index("after = collect()"))


if __name__ == "__main__":
    unittest.main()
