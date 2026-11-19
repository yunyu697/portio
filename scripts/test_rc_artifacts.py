#!/usr/bin/env python3
"""rc.py 里「检查产物」的两项（A10 可执行文件、A11 安装包）的单元测试。

这两项都曾经拿「本地留下的旧东西」交差：A11 取目录里 mtime 最新的 `.exe`，
于是仓库根上两个版本前的包也能判过；A10 死盯仓库里的 `target/debug`，
而本机构建其实落在 `CARGO_TARGET_DIR`（D 盘），判的是上一次留下的旧 exe。
下面这些用例钉住：只认当前版本的文件名、旧包必须明说「不算」、体积越界要 FAIL、
构建目录跟着 `CARGO_TARGET_DIR` 走且取最新的那一份。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402


def touch(dirpath: Path, name: str, size: int) -> Path:
    p = dirpath / name
    with p.open("wb") as f:
        f.write(b"\0" * size)
    return p


VER = "1.0.7-RC10"
WANT = f"Portio_{VER}_x64-setup.exe"
SANE = 3 * 1024 * 1024  # 落在 2–30 MiB 的区间里


class CheckBundleTest(unittest.TestCase):
    """A11：按当前版本号找安装包。"""

    def test_current_version_in_bundle_dir_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            touch(bundle, WANT, SANE)
            status, detail = rc.check_bundle(VER, [bundle])
            self.assertEqual(status, rc.PASS, detail)
            self.assertIn(WANT, detail)
            self.assertIn(str(SANE), detail)
            self.assertIn(str(bundle), detail)

    def test_only_old_packages_do_not_pass(self):
        """旧包在眼前，也不能算过——要说清「还没构建当前版本」。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root, "Portio_1.0.7-RC3_x64-setup.exe", SANE)
            touch(root, "Portio_1.0.0-Alpha10_x64-setup.exe", SANE)
            status, detail = rc.check_bundle(VER, [root])
            self.assertEqual(status, rc.SKIP, detail)
            self.assertIn(WANT, detail)
            self.assertIn("不算", detail)
            self.assertIn("Portio_1.0.7-RC3_x64-setup.exe", detail)

    def test_no_package_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, detail = rc.check_bundle(VER, [Path(tmp)])
            self.assertEqual(status, rc.SKIP, detail)
            self.assertNotIn("不算", detail)

    def test_package_in_repo_root_also_counts(self):
        """包放仓库根（交付时就是这样）也该认。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root, WANT, SANE)
            status, detail = rc.check_bundle(VER, [root / "target" / "nsis", root])
            self.assertEqual(status, rc.PASS, detail)

    def test_too_big_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root, WANT, 31 * 1024 * 1024)
            status, detail = rc.check_bundle(VER, [root])
            self.assertEqual(status, rc.FAIL, detail)
            self.assertIn("31.00 MiB", detail)

    def test_too_small_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root, WANT, 1024)
            status, detail = rc.check_bundle(VER, [root])
            self.assertEqual(status, rc.FAIL, detail)

    def test_empty_version_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, detail = rc.check_bundle("  ", [Path(tmp)])
            self.assertEqual(status, rc.FAIL, detail)
            self.assertIn("版本号", detail)

    def test_newest_wins_when_both_copies_exist(self):
        """bundle 与仓库根各有一份当前版本：取 mtime 新的那个。

        mtime 用 os.utime 钉死，不靠两次 touch 的先后——文件系统的时间分辨率
        在测试里是噪音，判据要稳。
        """
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            root = Path(tmp)
            bundle.mkdir()
            older = touch(root, WANT, SANE)
            newer = touch(bundle, WANT, SANE)
            os.utime(older, (1000, 1000))
            os.utime(newer, (2000, 2000))
            status, detail = rc.check_bundle(VER, [bundle, root])
            self.assertEqual(status, rc.PASS, detail)
            self.assertIn(str(bundle), detail)

    def test_real_repo_version_is_parseable(self):
        """仓库里的版本串读得出来（读不出就该 FAIL，不能静悄悄）。"""
        self.assertRegex(rc.current_version(), r"^\d+\.\d+\.\d+(-(Alpha|RC)\d+)?$")


class FindAppExeTest(unittest.TestCase):
    """A10：可执行文件得跟着构建目录走，并且取最新的那一份。"""

    def test_none_when_both_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(rc.find_app_exe([Path(tmp), Path(tmp) / "nope"]))

    def test_repo_target_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            touch(repo, "portio-app.exe", 4096)
            self.assertEqual(rc.find_app_exe([repo]), repo / "portio-app.exe")

    def test_newest_build_wins(self):
        """仓库里那份是上一次的、D 盘那份才是这一轮的：必须取 D 盘。"""
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "repo"
            fresh = Path(tmp) / "drive-d"
            stale.mkdir()
            fresh.mkdir()
            old = touch(stale, "portio-app.exe", 4096)
            new = touch(fresh, "portio-app.exe", 4096)
            os.utime(old, (1000, 1000))
            os.utime(new, (2000, 2000))
            self.assertEqual(rc.find_app_exe([stale, fresh]), fresh / "portio-app.exe")

    def test_dirs_follow_cargo_target_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.get("CARGO_TARGET_DIR")
            os.environ["CARGO_TARGET_DIR"] = tmp
            try:
                dirs = rc.app_exe_dirs()
            finally:
                if saved is None:
                    os.environ.pop("CARGO_TARGET_DIR", None)
                else:
                    os.environ["CARGO_TARGET_DIR"] = saved
            self.assertEqual(dirs[0], rc.ROOT / "target" / "debug")
            self.assertEqual(dirs[1], Path(tmp) / "debug")


if __name__ == "__main__":
    unittest.main()
