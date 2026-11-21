#!/usr/bin/env python3
"""A47 单测：0 字节产物 + 假新鲜指纹 + 超龄 rustc。

判据都是「盘上看得见的东西」，所以夹具直接在临时目录里搭出来，
不碰真的 target、不数真的进程（进程那一条把结果注入进去）。
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_stale_artifacts as csa  # noqa: E402

HASH = "35cc6d31580c4d0f"
OTHER = "9b1f2a3c4d5e6f70"


def make_tree(root: Path, *, artifacts=(), fingerprints=(), profile="debug") -> Path:
    """搭一个 target/<profile>：artifacts = [(文件名, 字节数)]，fingerprints = [(目录名, [文件名])]。"""
    prof = root / profile
    (prof / "deps").mkdir(parents=True)
    for name, size in artifacts:
        p = prof / "deps" / name
        p.write_bytes(b"" if size == 0 else b"x" * size)
    for dirname, files in fingerprints:
        d = prof / ".fingerprint" / dirname
        d.mkdir(parents=True)
        for f in files:
            (d / f).write_bytes(b"0" * 8)
    return root


class ParseTest(unittest.TestCase):
    def test_lib_artifact_naming(self):
        got = csa.parse_lib(Path("libportio_ssh-35cc6d31580c4d0f.rmeta"))
        self.assertEqual(got, ("portio_ssh", HASH))

    def test_no_hash_is_not_lib_artifact(self):
        self.assertIsNone(csa.parse_lib(Path("libfoo.rlib")))

    def test_other_suffix_is_not_lib_artifact(self):
        self.assertIsNone(csa.parse_lib(Path(f"portio_app-{HASH}.exe")))

    def test_pkg_name_uses_dash(self):
        z = csa.Zero(Path("x"), "portio_ssh", HASH)
        self.assertEqual(z.pkg, "portio-ssh")


class ZeroTest(unittest.TestCase):
    def test_counts_zero_byte_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp), artifacts=[
                (f"libalpha-{HASH}.rmeta", 0),
                (f"libbeta-{HASH}.rlib", 0),
                (f"libgamma-{HASH}.rmeta", 1024),
            ])
            hits = csa.zero_artifacts(root / "debug" / "deps")
            self.assertEqual([h.path.name for h in hits],
                             [f"libalpha-{HASH}.rmeta", f"libbeta-{HASH}.rlib"])

    def test_depinfo_not_counted(self):
        """`.d` 只记源文件清单，0 字节也不算空壳产物——cargo 自己会发现它不对。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp), artifacts=[(f"libalpha-{HASH}.d", 0)])
            self.assertEqual(csa.zero_artifacts(root / "debug" / "deps"), [])

    def test_exe_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp), artifacts=[(f"portio_app-{HASH}.exe", 0)])
            self.assertEqual(csa.zero_artifacts(root / "debug" / "deps"), [])

    def test_unparsable_zero_still_counted(self):
        """名字认不出的空文件也是空壳，照样点名（crate 留空，修法写「?」）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp), artifacts=[("weird.rmeta", 0)])
            hits = csa.zero_artifacts(root / "debug" / "deps")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].crate, "")
            self.assertEqual(hits[0].pkg, "")

    def test_missing_deps_dir_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(csa.zero_artifacts(Path(tmp) / "nope"), [])


class FreshTest(unittest.TestCase):
    def test_zero_artifact_with_fresh_fingerprint_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libportio_ssh-{HASH}.rmeta", 0)],
                fingerprints=[("portio-ssh-" + HASH, [csa.FINGERPRINT_MARK, "lib-portio_ssh"])],
            )
            res = csa.scan(root, "debug", rustc_procs=[])
            self.assertEqual(len(res["findings"]), 1)
            self.assertIn("cargo clean -p portio-ssh", res["findings"][0])
            self.assertEqual(res["stats"]["fresh"], 1)

    def test_fingerprint_without_timestamp_is_only_a_note(self):
        """指纹目录还在、可没有 `invoked.timestamp`：那一格没记成「编完了」，cargo 会重编，不判红。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libalpha-{HASH}.rmeta", 0)],
                fingerprints=[("alpha-" + HASH, ["lib-alpha"])],
            )
            res = csa.scan(root, "debug", rustc_procs=[])
            self.assertEqual(res["findings"], [])
            self.assertEqual(len(res["notes"]), 1)
            self.assertIn("libalpha", res["notes"][0])
            self.assertEqual(res["stats"]["fresh"], 0)

    def test_fingerprint_of_another_unit_does_not_match(self):
        """hash 对不上就是别的那一格，不能拿它当这格的证据。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libalpha-{HASH}.rmeta", 0)],
                fingerprints=[("alpha-" + OTHER, [csa.FINGERPRINT_MARK])],
            )
            res = csa.scan(root, "debug", rustc_procs=[])
            self.assertEqual(res["findings"], [])

    def test_fingerprint_in_another_profile_does_not_match(self):
        """debug 的空壳不许拿 release 的指纹来判。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libalpha-{HASH}.rmeta", 0)],
                fingerprints=[("alpha-" + HASH, [csa.FINGERPRINT_MARK])],
                profile="release",
            )
            res = csa.scan(root, "debug", rustc_procs=[])
            self.assertEqual(res["findings"], [])

    def test_healthy_artifact_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libalpha-{HASH}.rmeta", 4096)],
                fingerprints=[("alpha-" + HASH, [csa.FINGERPRINT_MARK])],
            )
            res = csa.scan(root, "debug", rustc_procs=[])
            self.assertEqual(res["findings"], [])
            self.assertEqual(res["notes"], [])
            self.assertEqual(res["stats"]["rmeta"], 1)
            self.assertEqual(res["stats"]["fingerprints"], 1)


class RustcTest(unittest.TestCase):
    def test_old_rustc_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp))
            res = csa.scan(root, "debug", rustc_age=600, rustc_procs=[(1234, 5000.0)])
            self.assertEqual(len(res["findings"]), 1)
            self.assertIn("1234", res["findings"][0])
            self.assertEqual(res["stats"]["rustc_old"], 1)

    def test_young_rustc_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp))
            res = csa.scan(root, "debug", rustc_age=600, rustc_procs=[(1234, 120.0)])
            self.assertEqual(res["findings"], [])
            self.assertEqual(res["stats"]["rustc"], 1)
            self.assertEqual(res["stats"]["rustc_old"], 0)

    def test_unknown_process_list_is_a_note_not_a_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp))
            res = csa.scan(root, "debug", rustc_procs=None)
            self.assertEqual(res["findings"], [])
            self.assertIn("没数成", res["notes"][0])


class MainTest(unittest.TestCase):
    def run_main(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = csa.main(list(argv))
        return code, buf.getvalue()

    def test_no_target_dir_is_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_main("--target-dir", str(Path(tmp) / "gone"))
            self.assertEqual(code, csa.EXIT_NOTHING)
            self.assertIn("还没编过", out)

    def test_clean_tree_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libalpha-{HASH}.rmeta", 4096)],
                fingerprints=[("alpha-" + HASH, [csa.FINGERPRINT_MARK])],
            )
            code, out = self.run_main("--target-dir", str(root))
            self.assertEqual(code, csa.EXIT_OK)
            self.assertTrue(out.strip().splitlines()[-1].startswith("OK "))

    def test_empty_shell_with_fresh_fingerprint_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(
                Path(tmp),
                artifacts=[(f"libportio_ssh-{HASH}.rmeta", 0)],
                fingerprints=[("portio-ssh-" + HASH, [csa.FINGERPRINT_MARK])],
            )
            code, out = self.run_main("--target-dir", str(root))
            self.assertEqual(code, csa.EXIT_FAIL)
            self.assertIn("FAIL ", out)
            self.assertIn("cargo clean -p portio-ssh", out)

    def test_two_target_dirs_both_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = make_tree(Path(tmp) / "a")
            dirty = make_tree(Path(tmp) / "b", artifacts=[(f"libalpha-{HASH}.rmeta", 0)],
                              fingerprints=[("alpha-" + HASH, [csa.FINGERPRINT_MARK])])
            code, out = self.run_main("--target-dir", str(clean), "--target-dir", str(dirty))
            self.assertEqual(code, csa.EXIT_FAIL)
            self.assertIn("b", out)


if __name__ == "__main__":
    unittest.main()
