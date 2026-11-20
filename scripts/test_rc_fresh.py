"""A38 的单测：把「一次性 profile 里跑」这件事的判据逐条钉住。

这里钉四件事：
① 判据是分层的：自检本身过没过、隔离到底生不生效、我的偏好库动没动、底色文件回没回去——
   少核一层就等于这次跑可能改了我自己的东西而我不知道；
② 「隔离生效」的凭据是物理的：一次性目录里真建出了 localStorage 库，且我真 profile 的库指纹一模一样；
③ 会话与已知主机两条不许混进来（它们在真后端上起手就把我的会话清单清空）；
④ 空 profile 首启时那一帧 about:blank 也是 `complete`，所以等的是版本串出现，不是等加载完。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


class VerdictTest(unittest.TestCase):
    def _rows(self, bad_index: int | None = None, title: str = "") -> list:
        rows = []
        for i, (hook, expect) in enumerate(rc.FRESH_SELFTESTS):
            rows.append((hook, expect, title if i == bad_index else expect))
        return rows

    def test_all_green_and_isolated_names_each_hook(self):
        status, detail = rc.fresh_verdict(self._rows(), True, True, True)
        self.assertEqual(status, rc.PASS)
        self.assertIn(str(len(rc.FRESH_SELFTESTS)), detail)
        self.assertIn("panes-test", detail)
        self.assertIn("一个字节没动", detail)

    def test_nothing_ran_is_red(self):
        status, detail = rc.fresh_verdict([], True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("一条自检都没跑", detail)

    def test_hook_reporting_err_is_red(self):
        rows = self._rows(0, "ERR: 开局格数只该作用于第一个标签")
        status, detail = rc.fresh_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("panes-test", detail)

    def test_wrong_prefix_is_red(self):
        rows = self._rows(1, "THEME-SELFTEST-OK")  # layout 那一条读到了 theme 的结果
        status, detail = rc.fresh_verdict(rows, True, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("layout-test", detail)

    def test_isolation_not_effective_is_red(self):
        # 一次性目录里压根没冒出库 = 那批是在我自己的偏好里跑的
        status, detail = rc.fresh_verdict(self._rows(), False, True, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("隔离没生效", detail)

    def test_real_prefs_touched_is_red(self):
        status, detail = rc.fresh_verdict(self._rows(), True, False, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("偏好库被动过", detail)

    def test_unmeasurable_real_prefs_is_not_green(self):
        # 量不到「有没有被动」不算核过——宁可红，也不许含糊成通过
        status, detail = rc.fresh_verdict(self._rows(), True, None, True)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("偏好库", detail)

    def test_theme_file_not_restored_is_red(self):
        status, detail = rc.fresh_verdict(self._rows(), True, True, False)
        self.assertEqual(status, rc.FAIL)
        self.assertIn("theme.txt", detail)

    def test_no_theme_file_is_fine(self):
        # 本来就没有这份底色文件、也没冒出新的 = 不用还原
        status, _ = rc.fresh_verdict(self._rows(), True, True, None)
        self.assertEqual(status, rc.PASS)


class StampTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="portio-stamp-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_dir_is_zeros(self):
        self.assertEqual(rc.profile_stamp(self.tmp / "nope"),
                         {"files": 0, "bytes": 0, "newest": 0})
        self.assertEqual(rc.profile_stamp(None), {"files": 0, "bytes": 0, "newest": 0})

    def test_counts_files_and_bytes(self):
        (self.tmp / "a").mkdir()
        (self.tmp / "a" / "x.log").write_bytes(b"12345")
        (self.tmp / "b.log").write_bytes(b"123")
        stamp = rc.profile_stamp(self.tmp)
        self.assertEqual(stamp["files"], 2)
        self.assertEqual(stamp["bytes"], 8)
        self.assertGreater(stamp["newest"], 0)

    def test_rewriting_a_file_changes_the_stamp(self):
        # 检测本身得有效：库被写过就必须判成「动过」
        f = self.tmp / "000003.log"
        f.write_bytes(b"abc")
        before = rc.profile_stamp(self.tmp)
        time.sleep(0.05)
        f.write_bytes(b"abcd")
        after = rc.profile_stamp(self.tmp)
        self.assertNotEqual(before, after)

    def test_fresh_db_found_one_level_deeper(self):
        # 实测：给的那层目录下 WebView2 会再套一层 EBWebView
        db = self.tmp / "EBWebView" / "Default" / "Local Storage" / "leveldb"
        db.mkdir(parents=True)
        (db / "000003.log").write_bytes(b"x")
        self.assertEqual(rc.fresh_profile_db(self.tmp), db)

    def test_empty_or_missing_profile_has_no_db(self):
        db = self.tmp / "EBWebView" / "Default" / "Local Storage" / "leveldb"
        db.mkdir(parents=True)
        self.assertIsNone(rc.fresh_profile_db(self.tmp))  # 空目录不算建出了库
        self.assertIsNone(rc.fresh_profile_db(self.tmp / "none"))

    def test_real_profile_path_is_the_identifier_one(self):
        p = rc.localStorage_dir("io.portio.desktop", env={"LOCALAPPDATA": r"C:\L"})
        self.assertEqual(p, Path(r"C:\L") / "io.portio.desktop" / "EBWebView"
                         / "Default" / "Local Storage" / "leveldb")
        self.assertIsNone(rc.localStorage_dir("io.portio.desktop", env={}))

    def test_app_data_file_is_roaming(self):
        p = rc.app_data_file("theme.txt", env={"APPDATA": r"C:\A"})
        self.assertEqual(p, Path(r"C:\A") / "io.portio.desktop" / "theme.txt")
        self.assertIsNone(rc.app_data_file("theme.txt", env={}))


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="portio-restore-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_untouched_file_is_fine(self):
        f = self.tmp / "theme.txt"
        f.write_bytes(b"light")
        self.assertTrue(rc.restore_bytes(f, b"light"))
        self.assertEqual(f.read_bytes(), b"light")

    def test_changed_file_is_written_back(self):
        f = self.tmp / "theme.txt"
        f.write_bytes(b"dark")  # 新 profile 启动时按首启偏好重写成了深色
        self.assertTrue(rc.restore_bytes(f, b"light"))
        self.assertEqual(f.read_bytes(), b"light")

    def test_file_that_should_not_exist_is_not_deleted(self):
        f = self.tmp / "theme.txt"
        f.write_bytes(b"dark")
        self.assertFalse(rc.restore_bytes(f, None))
        self.assertTrue(f.exists())  # 不替你删，报红让人看

    def test_missing_path_is_no_restore_needed(self):
        self.assertIsNone(rc.restore_bytes(None, b"light"))


class RowsTest(unittest.TestCase):
    def test_rows_bad_flags_err_and_prefix(self):
        rows = [("a", "A-OK", "A-OK"), ("b", "B-OK", "ERR: 炸了"), ("c", "C-OK", "B-OK")]
        bad = rc.rows_bad(rows)
        self.assertEqual(len(bad), 2)
        self.assertIn("b 自己报了红", bad[0])
        self.assertIn("c 没跑出结果", bad[1])

    def test_rows_bad_all_good_is_empty(self):
        self.assertEqual(rc.rows_bad([(h, e, e) for h, e in rc.FRESH_SELFTESTS]), [])


class WiredTest(unittest.TestCase):
    def setUp(self):
        self.src = RC_PY.read_text(encoding="utf-8")
        self.body = self.src.split("def probe_fresh_selftests(", 1)[1].split(
            "def a38_fresh_selftests", 1)[0]

    def test_in_plan_table(self):
        self.assertRegex(self.src, r'\("A38",\s*"会改设置的那批自检也在真窗口里跑')

    def test_in_dispatch_chain(self):
        self.assertIn('elif code == "A38":', self.src)
        self.assertIn("a38_fresh_selftests()", self.src)

    def test_nine_settings_changing_hooks(self):
        expects = dict(rc.FRESH_SELFTESTS)
        self.assertEqual(len(rc.FRESH_SELFTESTS), 9)
        for hook in ("theme-test", "density-test", "accent-test", "term-theme-test",
                     "font-test", "boot-test", "perm-test", "panes-test", "layout-test"):
            self.assertIn(hook, expects)
        self.assertEqual(expects["panes-test"], "PANES-SELFTEST-OK")
        self.assertEqual(expects["layout-test"], "LAYOUT-SELFTEST-OK")

    def test_session_and_host_hooks_are_excluded(self):
        # 这两条在真后端上起手就把我的会话清单清空，不许搬进来
        hooks = [h for h, _ in rc.FRESH_SELFTESTS]
        for bad in rc.FRESH_EXCLUDED:
            self.assertNotIn(bad, hooks, f"{bad} 会动真文件，不该进这张表")

    def test_profile_is_swapped_for_this_child_only(self):
        self.assertIn('env["WEBVIEW2_USER_DATA_FOLDER"] = str(prof)', self.body)
        self.assertIn("mkdtemp", self.body)
        self.assertNotIn("os.environ[\"WEBVIEW2_USER_DATA_FOLDER\"]", self.body)

    def test_waits_for_version_string_not_just_complete(self):
        # 空 profile 首启时 about:blank 那一帧也是 complete，等它等于把空白页当界面
        self.assertIn("VER_EXPR", self.body)
        self.assertIn("版本串还没出现", self.body)

    def test_version_drift_is_untested(self):
        self.assertIn("不是本版构建", self.body)
        self.assertIn("return SKIP", self.body)

    def test_checks_the_real_profile_stamp_before_and_after(self):
        self.assertIn("db_before = profile_stamp(db)", self.body)
        self.assertIn("db_after = profile_stamp(db)", self.body)
        self.assertIn("db_before == db_after", self.body)

    def test_restores_theme_bytes(self):
        self.assertIn("theme_before = theme.read_bytes()", self.body)
        self.assertIn("restore_bytes(theme, theme_before)", self.body)

    def test_kills_and_removes_the_profile_in_finally(self):
        self.assertRegex(self.body, r"finally:\s*\n\s*if proc.poll\(\) is None:\s*\n\s*kill\(proc.pid\)")
        self.assertIn("shutil.rmtree(prof, ignore_errors=True)", self.body)

    def test_port_not_hardcoded(self):
        self.assertIn("port = port or free_port()", self.body)

    def test_windows_only(self):
        body = self.src.split("def a38_fresh_selftests(", 1)[1].split("def split_ids", 1)[0]
        self.assertIn('sys.platform != "win32"', body)
        self.assertIn("return SKIP", body)


if __name__ == "__main__":
    unittest.main()
