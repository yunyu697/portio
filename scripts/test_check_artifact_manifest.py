#!/usr/bin/env python3
"""A48 单测：交付物溯源——记录自洽、盘上那份对得上、包体内版本串。

判据都是「盘上看得见的东西」，夹具在临时目录里搭：假 exe 用真字节拼出来，
PE 版本资源那一条把读出来的结果注入进去（不依赖真 exe、也不依赖 Windows）。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_artifact_manifest as cam  # noqa: E402

CUR = "1.0.10-RC5"
OLD = "1.0.10-RC4"


def write_manifest(root: Path, rows: list[dict]) -> Path:
    p = root / "docs" / "artifacts.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"artifacts": rows}, ensure_ascii=False), encoding="utf-8")
    return p


def write_cargo(root: Path, version: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Cargo.toml").write_text(f'[workspace]\nversion = "{version}"\n', encoding="utf-8")


def row(**kw) -> dict:
    base = {
        "version": CUR,
        "platform": "windows-x64",
        "source": "ci",
        "tag": f"v{CUR}",
        "asset": f"Portio_{CUR}_x64-setup.exe",
        "file": f"../Portio_{CUR}_x64-setup.exe",
        "bytes": 0,
        "sha256": "0" * 64,
        "delivered": "2026-11-21",
    }
    base.update(kw)
    return base


def make_fixture(root: Path, *, rows=None, payload: bytes | None = b"NOT-A-PE-BUT-BYTES", version=CUR,
                 manifest: Path | None = None) -> tuple[Path, Path]:
    """搭一份「仓库 + 仓库外那个包」。payload=None 表示那份包不在盘上。

    记录里的字节与 sha256 按真实文件算——夹具不写一份「字节写着 0」的记录，
    那种记录本来就会先被自查的判据判红，会把要测的那一条盖住。
    """
    write_cargo(root, version)
    rows = rows if rows is not None else []
    for r in rows:
        p = root.parent / r["asset"]
        if payload is None:
            r["bytes"] = 1024
            r["sha256"] = "0" * 63 + "1"
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(payload + r["asset"].encode("utf-8"))  # 各条内容不同，sha 才各不同
            r["bytes"] = p.stat().st_size
            r["sha256"] = cam.sha256_of(p)
    m = manifest or write_manifest(root, rows)
    return root, m


def fake_pe(versions: dict[str, str] | None):
    """注入一个假的 PE 版本资源读取：versions=None 表示读不出来。"""
    return lambda _path: versions


def tags_of(rows: list[dict], *, cargo: dict[str, str] | None = None,
            kind: str = "tag", ancestor: bool = True) -> dict[str, dict]:
    """按记录里的 tag 名搭一张「tag → 那次提交」的表。"""
    out: dict[str, dict] = {}
    for i, r in enumerate(rows):
        tag = str(r.get("tag"))
        out[tag] = {
            "kind": kind,
            "commit": f"{i + 1:07x}" + "0" * 33,
            "cargo": (cargo or {}).get(tag, str(r["version"])),
            "ancestor": ancestor,
        }
    return out


def fake_git(tags: dict[str, dict] | None = None, *, repo: bool = True, usable: bool = True):
    """假 git：只看命令行回答，不碰真仓库。tags=None 表示一个 tag 都没有。"""
    table = tags or {}

    def runner(args: list[str], cwd):
        if not usable:
            return 127, "", "git 用不了"
        if not repo:
            return 128, "", "fatal: not a git repository (or any of the parent directories): .git"
        if args[:2] == ["rev-parse", "--show-toplevel"]:
            return 0, str(cwd) + "\n", ""
        if args[:2] == ["cat-file", "-t"]:
            name = args[2].replace("refs/tags/", "")
            row = table.get(name)
            return (0, row["kind"] + "\n", "") if row else (1, "", f"fatal: not a valid object name: {name}")
        if args[:2] == ["rev-parse", "--verify"]:
            name = args[2].split("^{")[0].replace("refs/tags/", "")
            row = table.get(name)
            return (0, row["commit"] + "\n", "") if row else (1, "", "unknown revision")
        if args[:1] == ["show"]:
            spec, _, path = args[1].partition(":")
            hits = [v for v in table.values() if v["commit"] == spec]
            if not hits:
                return 128, "", "fatal: bad object"
            if path != "Cargo.toml":
                return 128, "", f"fatal: path '{path}' does not exist in '{spec[:7]}'"
            return 0, f'[workspace]\nversion = "{hits[0]["cargo"]}"\n', ""
        if args[:1] == ["merge-base"]:
            hits = [v for v in table.values() if v["commit"] == args[2]]
            ok = bool(hits) and hits[0].get("ancestor", True)
            return (0 if ok else 1), "", ""
        return 127, "", f"unexpected: {' '.join(args)}"

    return runner


def assets_for(rows: list[dict]) -> dict[str, list[dict]]:
    """按记录搭一张「tag → Release 资产清单」的表，大小跟记录写的一致。"""
    table: dict[str, list[dict]] = {}
    for r in rows:
        table.setdefault(str(r["tag"]), []).append({"name": r["asset"], "size": r["bytes"]})
    return table


def fake_gh(assets: dict[str, list[dict]] | None = None, *, usable: bool = True):
    """假 gh：只看命令行回答，不碰真 Release。usable=False 表示 gh 用不了。"""
    table = assets or {}

    def runner(args: list[str], cwd):
        if not usable:
            return 127, "", "gh 用不了"
        tag = args[2]
        if tag not in table:
            return 1, "", "release not found"
        return 0, json.dumps({"assets": table[tag]}), ""

    return runner


class VersionParseTest(unittest.TestCase):
    def test_final_release(self):
        self.assertEqual(cam.parse_version("1.0.0"), (1, 0, 0, 3, 0))

    def test_rc_and_alpha_order(self):
        self.assertLess(cam.parse_version("1.0.7-Alpha3"), cam.parse_version("1.0.7-RC1"))
        self.assertLess(cam.parse_version("1.0.7-RC10"), cam.parse_version("1.0.8"))

    def test_stage_number(self):
        self.assertEqual(cam.stage_number("1.0.10-RC5"), 5)
        self.assertEqual(cam.stage_number("1.0.0"), 0)

    def test_bad_version_is_none(self):
        self.assertIsNone(cam.parse_version("1.0"))
        self.assertIsNone(cam.parse_version("1.0.10-rc5"))
        self.assertIsNone(cam.parse_version("v1.0.10-RC5"))

    def test_reads_current_version_from_cargo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_cargo(root, CUR)
            self.assertEqual(cam.current_version(root), CUR)


class ShapeTest(unittest.TestCase):
    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = cam.run(Path(tmp) / "docs" / "artifacts.json", Path(tmp))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertIn("一次都没记下来", got["findings"][0])

    def test_broken_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "docs" / "artifacts.json"
            p.parent.mkdir(parents=True)
            p.write_text("{oops", encoding="utf-8")
            got = cam.run(p, root)
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertIn("读不成 JSON", got["findings"][0])

    def test_empty_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_cargo(root, CUR)
            p = root / "docs" / "artifacts.json"
            p.parent.mkdir(parents=True)
            p.write_text('{"artifacts": []}', encoding="utf-8")
            got = cam.run(p, root)
            self.assertEqual(got["code"], cam.EXIT_FAIL)

    def test_missing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, m = make_fixture(Path(tmp) / "portio", rows=[row()], payload=None)
            data = json.loads(m.read_text(encoding="utf-8"))
            del data["artifacts"][0]["sha256"]
            m.write_text(json.dumps(data), encoding="utf-8")
            got = cam.run(m, root)
            self.assertTrue(any("缺字段" in f and "sha256" in f for f in got["findings"]))
            self.assertEqual(got["code"], cam.EXIT_FAIL)


class EntryTest(unittest.TestCase):
    def test_stage_number_over_ten(self):
        findings = cam.check_entry(1, row(version="1.0.10-RC11", tag="v1.0.10-RC11"), CUR)
        self.assertTrue(any("只到 10" in f for f in findings))

    def test_ci_needs_matching_tag(self):
        findings = cam.check_entry(1, row(tag="v1.0.10-RC4"), CUR)
        self.assertTrue(any("tag" in f and f"v{CUR}" in f for f in findings))

    def test_local_needs_build_note(self):
        findings = cam.check_entry(1, row(source="local", tag="", build=""), CUR)
        self.assertTrue(any("怎么打出来的" in f for f in findings))

    def test_asset_must_carry_version(self):
        findings = cam.check_entry(1, row(asset="Portio_x64-setup.exe"), CUR)
        self.assertTrue(any("没有版本串" in f for f in findings))

    def test_asset_and_file_must_agree(self):
        findings = cam.check_entry(1, row(file=f"../other_{CUR}_x64-setup.exe"), CUR)
        self.assertTrue(any("不是同一个名字" in f for f in findings))

    def test_platform_whitelist(self):
        findings = cam.check_entry(1, row(platform="ios"), CUR)
        self.assertTrue(any("平台" in f for f in findings))

    def test_bad_sha_and_date(self):
        findings = cam.check_entry(1, row(sha256="ff08", delivered="2026/11/21"), CUR)
        self.assertTrue(any("sha256" in f for f in findings))
        self.assertTrue(any("交付日期" in f for f in findings))


class SetTest(unittest.TestCase):
    def test_duplicate_version_platform(self):
        findings = cam.check_set([row(), row()], CUR)
        self.assertTrue(any("只留一条" in f for f in findings))

    def test_future_version_is_red(self):
        findings = cam.check_set([row(version="1.0.11-RC1", tag="v1.0.11-RC1")], CUR)
        self.assertTrue(any("比当前版本" in f for f in findings))

    def test_history_is_fine(self):
        old = row(version=OLD, tag=f"v{OLD}", asset=f"Portio_{OLD}_x64-setup.exe",
                  file=f"../Portio_{OLD}_x64-setup.exe")
        self.assertEqual(cam.check_set([row(), old], CUR), [])


class PayloadTest(unittest.TestCase):
    def test_no_record_for_current_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = row(version=OLD, tag=f"v{OLD}", asset=f"Portio_{OLD}_x64-setup.exe",
                      file=f"../Portio_{OLD}_x64-setup.exe")
            root, m = make_fixture(Path(tmp) / "portio", rows=[old], payload=None)
            got = cam.run(m, root)
            self.assertEqual(got["code"], cam.EXIT_NOTHING)
            self.assertTrue(any("还没有交付记录" in n for n in got["notes"]))

    def test_file_not_on_disk_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, m = make_fixture(Path(tmp) / "portio", rows=[row()], payload=None)
            got = cam.run(m, root)
            self.assertEqual(got["code"], cam.EXIT_NOTHING)
            self.assertTrue(any("不在盘上" in n for n in got["notes"]))

    def test_bytes_mismatch_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, m = make_fixture(Path(tmp) / "portio", rows=[row()])
            data = json.loads(m.read_text(encoding="utf-8"))
            data["artifacts"][0]["bytes"] += 1
            m.write_text(json.dumps(data), encoding="utf-8")
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": CUR}))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("不是同一份" in f for f in got["findings"]))

    def test_sha_mismatch_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, m = make_fixture(Path(tmp) / "portio", rows=[row()])
            data = json.loads(m.read_text(encoding="utf-8"))
            data["artifacts"][0]["sha256"] = "f" * 64
            m.write_text(json.dumps(data), encoding="utf-8")
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": CUR}))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("不是我记的那份" in f for f in got["findings"]))

    def test_pe_inside_says_old_version(self):
        """字节与 sha256 都对得上，但包体内写着旧版本——改个文件名的旧包正是这个形状。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, m = make_fixture(Path(tmp) / "portio", rows=[row()])
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": OLD, "ProductVersion": OLD}))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("改不动" in f for f in got["findings"]))

    def test_pe_unreadable_is_note_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=fake_pe(None),
                          git_runner=fake_git(tags_of(rows)),
                          gh_runner=fake_gh(assets_for(rows)))
            self.assertEqual(got["code"], cam.EXIT_OK)
            self.assertTrue(any("PE 版本资源读不出来" in n for n in got["notes"]))

    def test_all_good(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": CUR, "ProductVersion": CUR}),
                          git_runner=fake_git(tags_of(rows)),
                          gh_runner=fake_gh(assets_for(rows)))
            self.assertEqual(got["code"], cam.EXIT_OK)
            self.assertEqual(got["findings"], [])


class TagTest(unittest.TestCase):
    """记录里那个 tag，指的到底是不是这一版的提交（RC6 补上的一组）。"""

    def _ok_pe(self):
        return fake_pe({"FileVersion": CUR, "ProductVersion": CUR})

    def test_tag_points_at_a_commit_of_the_old_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=self._ok_pe(),
                          git_runner=fake_git(tags_of(rows, cargo={f"v{CUR}": OLD})))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("tag 打到了别的提交上" in f for f in got["findings"]))

    def test_tag_not_in_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=self._ok_pe(), git_runner=fake_git({}))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("仓库里没有这个 tag" in f for f in got["findings"]))

    def test_lightweight_tag_is_note_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=self._ok_pe(),
                          git_runner=fake_git(tags_of(rows, kind="commit")),
                          gh_runner=fake_gh(assets_for(rows)))
            self.assertEqual(got["code"], cam.EXIT_OK)
            self.assertTrue(any("不是附注标签" in n for n in got["notes"]))

    def test_no_git_repo_is_pending_not_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=self._ok_pe(),
                          git_runner=fake_git(tags_of(rows), repo=False))
            self.assertEqual(got["code"], cam.EXIT_NOTHING)
            self.assertTrue(any("不是 git 工作区" in n for n in got["notes"]))

    def test_git_unusable_is_pending_not_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=self._ok_pe(),
                          git_runner=fake_git(tags_of(rows), usable=False))
            self.assertEqual(got["code"], cam.EXIT_NOTHING)
            self.assertTrue(any("git 用不了" in n for n in got["notes"]))

    def test_tag_off_the_main_line_is_note_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=self._ok_pe(),
                          git_runner=fake_git(tags_of(rows, ancestor=False)),
                          gh_runner=fake_gh(assets_for(rows)))
            self.assertEqual(got["code"], cam.EXIT_OK)
            self.assertTrue(any("不在 HEAD 的历史线上" in n for n in got["notes"]))

    def test_commit_without_cargo_toml_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            tags = tags_of(rows)
            loop = fake_git(tags)

            def runner(args, cwd):
                if args[:1] == ["show"]:
                    return 128, "", "fatal: path 'Cargo.toml' does not exist"
                return loop(args, cwd)

            got = cam.run(m, root, pe_reader=self._ok_pe(), git_runner=runner)
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("没有根 Cargo.toml" in f for f in got["findings"]))

    def test_empty_tag_column_is_red(self):
        rows = [row(source="local", tag="", build="cargo build --release")]
        findings, notes, verified = cam.check_tags(rows, Path("."), fake_git({}))
        self.assertTrue(any("tag 那一栏是空的" in f for f in findings))
        self.assertEqual(verified, 0)

    def test_history_row_with_a_missing_tag_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = row(version=OLD, tag=f"v{OLD}", asset=f"Portio_{OLD}_x64-setup.exe",
                      file=f"../Portio_{OLD}_x64-setup.exe")
            rows = [row(), old]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            tags = tags_of(rows)
            del tags[f"v{OLD}"]
            got = cam.run(m, root, pe_reader=self._ok_pe(), git_runner=fake_git(tags))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("第 2 条" in f and "仓库里没有这个 tag" in f for f in got["findings"]))

    def test_check_tags_counts_verified(self):
        rows = [row()]
        findings, notes, verified = cam.check_tags(rows, Path("."), fake_git(tags_of(rows)))
        self.assertEqual((findings, notes, verified), ([], [], 1))


class ReleaseTest(unittest.TestCase):
    """Release 上挂着的那份大小，跟记录写的对不对得上（RC8 补上的一组）。"""

    def _row(self, **kw):
        return row(**kw)

    def test_release_size_match_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": CUR, "ProductVersion": CUR}),
                          git_runner=fake_git(tags_of(rows)),
                          gh_runner=fake_gh(assets_for(rows)))
            self.assertEqual(got["code"], cam.EXIT_OK)
            self.assertEqual(got["stats"]["release"], 1)

    def test_release_asset_missing_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows, payload=None)
            got = cam.run(m, root, git_runner=fake_git(tags_of(rows)),
                          gh_runner=fake_gh({f"v{CUR}": []}))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("上没有这个文件" in f for f in got["findings"]))

    def test_release_size_mismatch_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows, payload=None)
            bad = {f"v{CUR}": [{"name": rows[0]["asset"], "size": rows[0]["bytes"] + 1}]}
            got = cam.run(m, root, git_runner=fake_git(tags_of(rows)),
                          gh_runner=fake_gh(bad))
            self.assertEqual(got["code"], cam.EXIT_FAIL)
            self.assertTrue(any("不是同一份" in f for f in got["findings"]))

    def test_gh_unusable_is_pending_not_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": CUR, "ProductVersion": CUR}),
                          git_runner=fake_git(tags_of(rows)), gh_runner=fake_gh(usable=False))
            self.assertEqual(got["code"], cam.EXIT_NOTHING)
            self.assertTrue(any("Release" in n and "没核" in n for n in got["notes"]))

    def test_multi_platform_manifest(self):
        """Windows 那份在盘上，dmg / deb / AppImage 只在 Release 上：四条记录都对得上才绿。"""
        with tempfile.TemporaryDirectory() as tmp:
            exe = self._row()
            dmg = self._row(platform="macos-universal",
                            asset=f"Portio_{CUR}_universal.dmg",
                            file=f"../Portio_{CUR}_universal.dmg")
            deb = self._row(platform="linux-deb", asset=f"Portio_{CUR}_amd64.deb",
                            file=f"../Portio_{CUR}_amd64.deb")
            app = self._row(platform="linux-appimage", asset=f"Portio_{CUR}_amd64.AppImage",
                             file=f"../Portio_{CUR}_amd64.AppImage")
            rows = [exe, dmg, deb, app]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows, payload=None)
            # exe 那份真落在盘上，其余三份不在
            exe_path = root.parent / exe["asset"]
            exe_path.parent.mkdir(parents=True, exist_ok=True)
            exe_path.write_bytes(b"EXE" + exe["asset"].encode("utf-8"))
            exe["bytes"] = exe_path.stat().st_size
            exe["sha256"] = cam.sha256_of(exe_path)
            m.write_text(json.dumps({"artifacts": rows}, ensure_ascii=False), encoding="utf-8")
            got = cam.run(m, root, pe_reader=fake_pe({"FileVersion": CUR, "ProductVersion": CUR}),
                          git_runner=fake_git(tags_of(rows)),
                          gh_runner=fake_gh(assets_for(rows)))
            self.assertEqual(got["code"], cam.EXIT_OK)
            self.assertEqual(got["stats"]["checked"], 1)
            self.assertEqual(got["stats"]["release"], 4)


class MainTest(unittest.TestCase):
    def test_cli_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [row()]
            root, m = make_fixture(Path(tmp) / "portio", rows=rows)
            self.assertEqual(cam.main(["--manifest", str(m), "--root", str(root)],
                                      git_runner=fake_git(tags_of(rows)),
                                      gh_runner=fake_gh(assets_for(rows))), cam.EXIT_OK)

    def test_cli_pending_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, m = make_fixture(Path(tmp) / "portio", rows=[row()], payload=None)
            self.assertEqual(cam.main(["--manifest", str(m), "--root", str(root)]),
                             cam.EXIT_NOTHING)

    def test_resolve_file_relative_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "portio"
            root.mkdir()
            p = cam.resolve_file(row(file="../a.exe"), root)
            self.assertEqual(p, (root / "../a.exe").resolve())


if __name__ == "__main__":
    unittest.main()
