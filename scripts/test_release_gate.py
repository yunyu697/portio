#!/usr/bin/env python3
"""release_gate.py 的单元测试：Alpha 只打 tag、RC 发预发布、正式版发正式包、
以及 tag 与仓库版本不一致或后缀不认识时必须判失败（不能静默按正式版发包）。
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_gate as rg  # noqa: E402
import version as vt  # noqa: E402


def make_root(ver: str) -> str:
    """造一个只有 ui/index.html 的最小仓库根。"""
    d = tempfile.mkdtemp(prefix="portio_gate_")
    (Path(d) / "ui").mkdir(parents=True, exist_ok=True)
    (Path(d) / "ui" / "index.html").write_text(
        f'<span class="verchip">{ver}</span><span class="ver">{ver}</span>',
        encoding="utf-8",
    )
    return d


class ClassifyTest(unittest.TestCase):
    def test_alpha_does_not_publish(self):
        for v in ("1.0.0-Alpha1", "1.0.5-Alpha10", "2.0.0-Alpha3"):
            self.assertEqual(rg.classify(v)[:2], (False, False), v)

    def test_rc_publishes_as_prerelease(self):
        for v in ("1.0.5-RC1", "1.0.6-RC10", "1.1.0-RC2"):
            self.assertEqual(rg.classify(v)[:2], (True, True), v)

    def test_final_publishes_as_latest(self):
        for v in ("1.0.0", "1.0.6", "2.3.4"):
            self.assertEqual(rg.classify(v)[:2], (True, False), v)

    def test_unknown_stage_rejected(self):
        # 以前的 bash 用 * 兜底，Beta 会被当成正式版发出去——现在必须报错
        with self.assertRaises(vt.VersionError):
            rg.classify("1.0.6-Beta1")

    def test_patch_eleven_rejected(self):
        with self.assertRaises(vt.VersionError):
            rg.classify("1.0.11-RC1")


class GateTest(unittest.TestCase):
    def test_matching_alpha_tag(self):
        r = rg.gate("v1.0.5-Alpha10", "1.0.5-Alpha10")
        self.assertEqual((r["version"], r["publish"], r["prerelease"]),
                         ("1.0.5-Alpha10", False, False))
        self.assertIn("只打 tag", r["reason"])

    def test_matching_rc_tag(self):
        r = rg.gate("v1.0.6-RC1", "1.0.6-RC1")
        self.assertEqual((r["version"], r["publish"], r["prerelease"]),
                         ("1.0.6-RC1", True, True))

    def test_matching_final_tag(self):
        r = rg.gate("v1.0.6", "1.0.6")
        self.assertEqual((r["version"], r["publish"], r["prerelease"]),
                         ("1.0.6", True, False))

    def test_mismatch_fails(self):
        with self.assertRaises(rg.GateError):
            rg.gate("v1.0.6-RC1", "1.0.6-RC2")

    def test_tag_without_v_fails(self):
        with self.assertRaises(rg.GateError):
            rg.gate("1.0.6-RC1", "1.0.6-RC1")

    def test_unknown_stage_never_silently_publishes(self):
        with self.assertRaises(vt.VersionError):
            rg.gate("v1.0.6-Beta1", "1.0.6-Beta1")


class RepoVersionTest(unittest.TestCase):
    def test_reads_current_version(self):
        root = make_root("9.9.9-RC7")
        self.assertEqual(rg.repo_version(Path(root)), "9.9.9-RC7")

    def test_missing_span_fails(self):
        d = tempfile.mkdtemp(prefix="portio_gate_")
        (Path(d) / "ui").mkdir(parents=True, exist_ok=True)
        (Path(d) / "ui" / "index.html").write_text("<p>没有版本号</p>", encoding="utf-8")
        with self.assertRaises(rg.GateError):
            rg.repo_version(Path(d))

    def test_real_repo_version_matches_check_versions(self):
        # 真仓库：gate 读到的版本必须能被 version.py 解析
        ver = rg.repo_version(rg.ROOT)
        vt.parse(ver)


class CliTest(unittest.TestCase):
    def test_cli_writes_github_output(self):
        root = make_root("1.0.6-RC1")
        out = os.path.join(root, "gh_out.txt")
        rc = rg.main(["--tag", "v1.0.6-RC1", "--root", root, "--github-output", out])
        self.assertEqual(rc, 0)
        got = io.open(out, encoding="utf-8").read()
        self.assertIn("version=1.0.6-RC1", got)
        self.assertIn("publish=true", got)
        self.assertIn("prerelease=true", got)

    def test_cli_rejects_mismatch(self):
        root = make_root("1.0.6-RC2")
        self.assertEqual(rg.main(["--tag", "v1.0.6-RC1", "--root", root]), 1)

    def test_cli_alpha_prints_false(self):
        root = make_root("1.0.6-Alpha1")
        self.assertEqual(rg.main(["--tag", "v1.0.6-Alpha1", "--root", root]), 0)


if __name__ == "__main__":
    unittest.main()
