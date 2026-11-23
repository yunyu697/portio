#!/usr/bin/env python3
"""交出去的那份包，记下来了没有、还对不对得上（A48）。

RC4 那轮的日志里我写了一句「本地交付的这份就是 Release 上那一份，3384941 B、sha256 前缀
ff080346」——可这句话没有一处是机械核过的，它只是我自己抄在纸上的。换一版那天，
盘上那份到底是不是 Release 上那份、包体内写的是哪个版本，谁也说不清：
**一份 RC3 的包只要改个文件名，字节与大小全对得上，可它装出来还是 RC3**。
所以「核的和交的是同一份」不能靠日志里的手抄，得有一条自己的门禁。

A48 核三件事：

1. **记录本身自洽**：`docs/artifacts.json` 里每条交付记录都得有版本、平台、来源、文件名、
   路径、字节、sha256、交付日期；同一版同一平台只能一条；不许把比当前版本还大的版本记进来
   （那是「记的是将来的版本」，说明这条记录不是我这一轮写的）；`source=ci` 时 tag 必须等于
   `v<版本>`、文件名里得带版本串；`source=local` 时必须写清是怎么打出来的。
2. **盘上那份跟记录对得上**：字节数与 sha256 两个都得对上——一个对不上就是「盘上这份不是我
   记的那份」。文件不在盘上（交付文件放在仓库外，换台机器就没有）报未验，不拿「没查到问题」冒充核过。
3. **包自己说自己是谁**：Windows exe 的 PE 版本资源里那个串（FileVersion / ProductVersion）
   必须等于当前版本——这条最要命，文件名和字节都能被改，包体内那个版本串不是随手改得动的。
   读不出来（不是 PE、或者碰上非 Windows）只留 NOTE，不当红。
4. **记录里那个 tag 指的是这一版的提交**（RC6 补上的一组）：tag 得真在仓库里；它指向的**那次提交**
   的根 `Cargo.toml` 里版本必须等于记录写的版本——不然「这份包是 CI 从 v1.0.10-RC5 编出来的」这句话
   就只是我抄了一个 tag 名；tag 提交不在当前 HEAD 的历史线上（比如从别的分支发的）只留 NOTE；
   tag 不是附注标签（没有「这一版做了什么」那段话）也只留 NOTE。
   git 用不了、或者这个目录不是 git 工作区，这一组**没得核**，整份报未验，不拿「没查到问题」冒充核过。
5. **Release 上挂着的那份跟记录写的大小对得上**（RC8 补上的一组）：非 Windows 的包不在本机盘上，
   字节与 sha256 这轮没法逐字节核；退一步拿 Release 资产清单对大小——记录里那个文件名得真挂在这一版
   tag 的 Release 上、大小一字不差。gh 用不了这一组**没得核**，整份报未验。

退出码：0 全对得上 / 1 对不上 / 4 这一版还没交过包、或者那几组里有一组没得核
（没有记录、那一份不在盘上、tag 或 Release 那一组核不了）。

用法：
    python scripts/check_artifact_manifest.py
    python scripts/check_artifact_manifest.py --manifest docs/artifacts.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "artifacts.json"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NOTHING = 4

# vMAJOR.MINOR.PATCH[-AlphaN|-RCN]：跟 scripts/set_version.py 认的是同一套写法
VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
                        r"(?:-(?P<stage>Alpha|RC)(?P<n>\d+))?$")
SOURCES = ("ci", "local")
PLATFORMS = ("windows-x64", "macos-universal", "linux-deb", "linux-appimage")
REQUIRED = ("version", "platform", "source", "asset", "file", "bytes", "sha256", "delivered")
# 预发布位只到 10：满 10 进 patch 再回 1，写 11 或 0 都是笔误
STAGE_MAX = 10
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_version(text: str) -> tuple[int, int, int, int, int] | None:
    """把版本串拆成可比较的元组：正式版排在所有预发布之后。"""
    m = VERSION_RE.match((text or "").strip())
    if not m:
        return None
    stage = m.group("stage")
    n = int(m.group("n")) if m.group("n") else 0
    rank = {"Alpha": 1, "RC": 2}.get(stage, 3) if stage else 3
    return int(m.group("major")), int(m.group("minor")), int(m.group("patch")), rank, n


def stage_number(text: str) -> int:
    """预发布位那个数字（正式版返回 0）。"""
    m = VERSION_RE.match((text or "").strip())
    if not m or not m.group("n"):
        return 0
    return int(m.group("n"))


def current_version(root: Path = ROOT) -> str:
    """当前版本：读根 Cargo.toml 的 `version = "…"`（set_version.py 写的第一处）。"""
    cargo = root / "Cargo.toml"
    if not cargo.is_file():
        return ""
    m = re.search(r'^version\s*=\s*"(.*?)"', cargo.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip() if m else ""


def load_manifest(path: Path) -> tuple[dict | None, list[str]]:
    """读记录文件。读不到 / 不是 JSON 都算判红——这份文件就是这一条凭据本身。"""
    if not path.is_file():
        return None, [f"没有 {path.name}：这一版交出去的包一次都没记下来（新建一份，把这一版那一份记上）"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, [f"{path.name} 读不成 JSON（{e}）——这份记录自己坏了，比没有记录更糟"]
    return data, []


def check_shape(data: dict) -> tuple[list[dict], list[str]]:
    """顶层得是 {"artifacts": [...]}，每条都得带齐那几个字段。"""
    findings: list[str] = []
    if not isinstance(data, dict):
        return [], ["记录文件顶层得是一个对象，里面放 artifacts 那一串"]
    rows = data.get("artifacts")
    if not isinstance(rows, list):
        return [], ["记录文件里没有 artifacts 这一串（顶层写成 {\"artifacts\": [...]}）"]
    if not rows:
        return [], ["artifacts 是空的：一条交付记录都没有，等于没记"]
    kept: list[dict] = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            findings.append(f"第 {i} 条不是一条对象")
            continue
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            findings.append(f"第 {i} 条缺字段：{'、'.join(missing)}")
            continue
        kept.append(row)
    return kept, findings


def check_entry(idx: int, row: dict, current: str) -> list[str]:
    """单条记录的自洽：版本串、预发布位、来源与 tag、文件名、字节、sha256、日期。"""
    findings: list[str] = []
    ver = str(row["version"]).strip()
    where = f"第 {idx} 条（{ver or '版本没写'} / {row.get('platform')}）"

    if parse_version(ver) is None:
        findings.append(f"{where} 版本串认不出：`{ver}`（得是 vMAJOR.MINOR.PATCH[-AlphaN|-RCN] 那套写法）")
    else:
        n = stage_number(ver)
        if n > STAGE_MAX:
            findings.append(f"{where} 预发布位写着 {n}，可它只到 {STAGE_MAX}（满 10 进 patch 再回 1）")

    platform = str(row.get("platform") or "").strip()
    if platform not in PLATFORMS:
        findings.append(f"{where} 平台写着 `{platform}`，只认 {' / '.join(PLATFORMS)}")

    source = str(row["source"]).strip()
    if source not in SOURCES:
        findings.append(f"{where} 来源写着 `{source}`，只认 {' / '.join(SOURCES)}")
    elif source == "ci":
        tag = str(row.get("tag") or "").strip()
        if tag != f"v{ver}":
            findings.append(f"{where} 说的是 CI 构建，可 tag 写着 `{tag or '（空）'}`——它得是 v{ver}，"
                            "不然这份包是从哪个 tag 上下的说不清")
    elif source == "local":
        if not str(row.get("build") or "").strip():
            findings.append(f"{where} 说的是本机构建，可没写怎么打出来的（build 那一栏留空，"
                            "下一轮我就不知道这份是 release 还是 debug 打的）")

    asset = str(row["asset"]).strip()
    if not asset:
        findings.append(f"{where} 文件名是空的")
    else:
        if ver and ver not in asset:
            findings.append(f"{where} 文件名 `{asset}` 里没有版本串 {ver}（旧包改名也能混进来）")
        if Path(str(row["file"])).name != asset:
            findings.append(f"{where} asset 与 file 写的不是同一个名字（`{asset}` vs "
                            f"`{Path(str(row['file'])).name}`）")

    if not isinstance(row["bytes"], int) or isinstance(row["bytes"], bool) or row["bytes"] <= 0:
        findings.append(f"{where} 字节数写着 `{row['bytes']}`，得是一个正整数")
    sha = str(row["sha256"]).strip().lower()
    if not SHA256_RE.match(sha):
        findings.append(f"{where} sha256 写着 `{row['sha256']}`，得是 64 位小写十六进制")
    try:
        date.fromisoformat(str(row["delivered"]).strip())
    except ValueError:
        findings.append(f"{where} 交付日期写着 `{row['delivered']}`，得是 YYYY-MM-DD")

    return findings


def check_set(rows: list[dict], current: str) -> list[str]:
    """整份记录之间：同版同平台不许重复，也不许记着比当前版本还大的版本。"""
    findings: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    cur = parse_version(current)
    for i, row in enumerate(rows, 1):
        key = (str(row["version"]).strip(), str(row["platform"]).strip())
        if key in seen:
            findings.append(f"第 {i} 条跟第 {seen[key]} 条都是 {key[0]} / {key[1]}："
                            "同一版同一平台只留一条，两条就分不清该信哪一条")
        else:
            seen[key] = i
        ver = parse_version(str(row["version"]).strip())
        if cur and ver and ver > cur:
            findings.append(f"第 {i} 条记着 {row['version']}，比当前版本 {current} 还大——"
                            "这不是我这一轮写的记录，先核一眼它哪来的")
    return findings


def default_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """跑一条 git 命令（只读）。git 不在、或者跑不起来时返回 127。"""
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                              timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)
    return proc.returncode, proc.stdout, proc.stderr


def check_tags(rows: list[dict], root: Path, git_runner=None) -> tuple[list[str], list[str], int]:
    """记录里那个 tag，指的到底是不是这一版的提交。

    只读四条命令：`rev-parse --show-toplevel`（是不是 git 工作区）、`cat-file -t`（附注标签还是
    轻量标签）、`rev-parse --verify <tag>^{commit}`（指向哪个提交）、`show <提交>:Cargo.toml`
    （那次提交里的版本）、`merge-base --is-ancestor`（在不在 HEAD 的历史线上）。

    返回（判红那几条，NOTE，真核过几条）。核过 0 条表示这一组没得核，调用方该报未验。
    """
    runner = git_runner or default_git
    findings: list[str] = []
    notes: list[str] = []
    verified = 0

    rc, _out, err = runner(["rev-parse", "--show-toplevel"], root)
    if rc != 0:
        first = err.strip().splitlines()[0] if err.strip() else "没有 .git"
        return [], [f"{root.name} 不是 git 工作区，或者这台机器上 git 用不了（{first}）："
                    "记录里那个 tag 指的是哪次提交，这一组没核"], 0

    for i, row in enumerate(rows, 1):
        tag = str(row.get("tag") or "").strip()
        where = f"第 {i} 条（{row.get('version')} / {row.get('platform')}）"
        if not tag:
            findings.append(f"{where} tag 那一栏是空的：这份包是从哪个提交编出来的，说不清")
            continue

        rc, out, _err = runner(["cat-file", "-t", f"refs/tags/{tag}"], root)
        if rc != 0 or not out.strip():
            findings.append(f"{where} 记着 tag `{tag}`，可仓库里没有这个 tag——"
                            "这份包是从哪个提交编出来的，现在没处可核")
            continue
        kind = out.strip()
        if kind != "tag":
            notes.append(f"`{tag}` 是{kind}（不是附注标签），它没有「这一版做了什么」那段话；"
                         "指向仍可核")

        rc, out, _err = runner(["rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"], root)
        commit = out.strip()
        if rc != 0 or not commit:
            findings.append(f"{where} 的 tag `{tag}` 解析不出它指向哪个提交")
            continue

        rc, out, _err = runner(["show", f"{commit}:Cargo.toml"], root)
        if rc != 0:
            findings.append(f"{where} 的 tag `{tag}` 指向 {commit[:7]}，可那次提交里没有根 "
                            "Cargo.toml——版本核不了，tag 可能打在了别的项目上")
            continue
        m = re.search(r'^version\s*=\s*"(.*?)"', out, re.MULTILINE)
        tagged = m.group(1).strip() if m else ""
        if tagged != str(row["version"]).strip():
            findings.append(f"{where} 说这份包是 {row['version']}，可 tag `{tag}` 指的提交"
                            f"（{commit[:7]}）里版本写着 `{tagged or '（没读到）'}`："
                            "tag 打到了别的提交上，或者记录写错了版本")
            continue

        rc, _out, _err = runner(["merge-base", "--is-ancestor", commit, "HEAD"], root)
        if rc == 1:
            notes.append(f"`{tag}` 指向的 {commit[:7]} 不在 HEAD 的历史线上（可能是从别的分支发的版）")
        verified += 1

    return findings, notes, verified


def default_gh(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """跑一条 gh 只读命令。gh 不在、或者跑不起来时返回 127。"""
    try:
        proc = subprocess.run(["gh", *args], cwd=str(cwd), capture_output=True, text=True,
                              timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)
    return proc.returncode, proc.stdout, proc.stderr


def check_release(rows: list[dict], root: Path, gh_runner=None) -> tuple[list[str], list[str], int]:
    """记录里那份包，Release 上挂着的大小跟记录对不对得上。

    只读一条命令：`gh release view <tag> --json assets`（资产名与大小）。本机盘上没有的
    dmg / deb / AppImage，字节与 sha256 没法逐字节核，先核到这一层。
    返回（判红那几条，NOTE，真核过几条）。核过 0 条表示这一组没得核，调用方该报未验。
    """
    runner = gh_runner or default_gh
    findings: list[str] = []
    notes: list[str] = []
    verified = 0

    by_tag: dict[str, dict[str, int]] = {}
    tags = sorted({str(r.get("tag") or "").strip() for r in rows if str(r.get("tag") or "").strip()})
    gh_ok = True
    for tag in tags:
        rc, out, err = runner(["release", "view", tag, "--json", "assets"], root)
        if rc != 0:
            first = err.strip().splitlines()[0] if err.strip() else "gh 用不了"
            notes.append(f"Release `{tag}` 取不到资产清单（{first}）：这一组没核")
            gh_ok = False
            continue
        try:
            data = json.loads(out)
            by_tag[tag] = {str(a.get("name")): int(a.get("size", -1))
                           for a in data.get("assets", [])}
        except (json.JSONDecodeError, ValueError, TypeError):
            notes.append(f"Release `{tag}` 的资产清单读不成 JSON：这一组没核")
            gh_ok = False

    if not gh_ok and not by_tag:
        return findings, notes, 0

    for i, row in enumerate(rows, 1):
        tag = str(row.get("tag") or "").strip()
        where = f"第 {i} 条（{row.get('version')} / {row.get('platform')}）"
        assets = by_tag.get(tag)
        if assets is None:
            continue
        asset = str(row["asset"]).strip()
        size = assets.get(asset)
        if size is None:
            findings.append(f"{where} 记着 `{asset}`，可 Release `{tag}` 上没有这个文件——"
                            "这份包是从哪个 Release 交出去的，说不清")
            continue
        if size != row["bytes"]:
            findings.append(f"{where} 记录写着 {row['bytes']} 字节，Release `{tag}` 上那份是 "
                            f"{size} 字节：记录跟 Release 不是同一份")
            continue
        verified += 1
    return findings, notes, verified


def resolve_file(row: dict, root: Path = ROOT) -> Path:
    """记录里的路径按「仓库目录」解：交付文件都在仓库外，`../x.exe` 这种写法不夹带本机用户名。"""
    p = Path(str(row["file"]))
    return p if p.is_absolute() else (root / p).resolve()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pe_versions(path: Path) -> dict[str, str] | None:
    """读 Windows exe 的 PE 版本资源（FileVersion / ProductVersion）。

    只有 Windows 上读得到；读不出来返回 None，由调用方记成 NOTE——不是 PE 的文件、
    或者碰上别的平台，这一条就没得核，但不能因此判红。
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        ver = ctypes.WinDLL("version")
        ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        ver.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           ctypes.c_void_p]
        ver.GetFileVersionInfoW.restype = wintypes.BOOL
        ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                       ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
        ver.VerQueryValueW.restype = wintypes.BOOL

        size = ver.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
            return None

        ptr, n = ctypes.c_void_p(), wintypes.UINT()
        if not ver.VerQueryValueW(buf, "\\VarFileInfo\\Translation",
                                  ctypes.byref(ptr), ctypes.byref(n)) or n.value < 4:
            return None
        lang, page = ctypes.cast(ptr, ctypes.POINTER(wintypes.WORD))[0], \
            ctypes.cast(ptr, ctypes.POINTER(wintypes.WORD))[1]

        out: dict[str, str] = {}
        for field in ("FileVersion", "ProductVersion"):
            q = f"\\StringFileInfo\\{lang:04x}{page:04x}\\{field}"
            ptr, n = ctypes.c_void_p(), wintypes.UINT()
            if ver.VerQueryValueW(buf, q, ctypes.byref(ptr), ctypes.byref(n)) and n.value:
                out[field] = ctypes.wstring_at(ptr, n.value).strip().rstrip("\x00")
        return out or None
    except Exception:
        return None


def check_payload(row: dict, path: Path, current: str, pe_reader=pe_versions) -> tuple[
        list[str], list[str], bool]:
    """盘上那份跟记录对得上吗：字节、sha256、以及包里那个版本串。

    返回（判红那几条，NOTE，文件在不在）。
    """
    findings: list[str] = []
    notes: list[str] = []
    if not path.is_file():
        return findings, notes, False

    size = path.stat().st_size
    if size != row["bytes"]:
        findings.append(f"{path.name} 盘上是 {size} 字节，记录写着 {row['bytes']}：不是同一份")
    sha = sha256_of(path)
    rec = str(row["sha256"]).strip().lower()
    if sha != rec:
        findings.append(f"{path.name} 的 sha256 是 {sha[:8]}…{sha[-4:]}，记录写着 "
                        f"{rec[:8]}…{rec[-4:]}：盘上这份不是我记的那份")

    if path.suffix.lower() in (".exe", ".msi"):
        got = pe_reader(path) if pe_reader else None
        if got is None:
            notes.append(f"{path.name} 的 PE 版本资源读不出来（不是 PE、或这台机器上读不了），"
                         "「包里写的是哪个版本」这一条这轮没核")
        else:
            for field in ("FileVersion", "ProductVersion"):
                val = got.get(field)
                if not val:
                    notes.append(f"{path.name} 的 PE 里没有 {field}，这一条跳过")
                    continue
                if val != current:
                    findings.append(f"{path.name} 体内 {field} 写着 `{val}`，当前版本是 {current}"
                                    "——文件名能改，包体内这个串改不动，这份不是这一版的")
    return findings, notes, True


def run(manifest: Path = MANIFEST, root: Path = ROOT, pe_reader=pe_versions,
        git_runner=None, gh_runner=None) -> dict:
    """整套判据。返回 {code, findings, notes, stats, current}。"""
    current = current_version(root)
    findings: list[str] = []
    notes: list[str] = []
    stats = {"records": 0, "checked": 0, "history": 0, "present": False, "tags": 0, "release": 0}

    data, bad = load_manifest(manifest)
    if data is None:
        return {"code": EXIT_FAIL, "findings": bad, "notes": notes, "stats": stats, "current": current}

    rows, shape = check_shape(data)
    findings += shape
    stats["records"] = len(rows)
    if not rows and not shape:
        findings.append("artifacts 是空的：一条交付记录都没有")

    for i, row in enumerate(rows, 1):
        findings += check_entry(i, row, current)
    findings += check_set(rows, current)

    tag_findings, tag_notes, stats["tags"] = check_tags(rows, root, git_runner)
    findings += tag_findings
    notes += tag_notes

    rel_findings, rel_notes, stats["release"] = check_release(rows, root, gh_runner)
    findings += rel_findings
    notes += rel_notes

    mine = [r for r in rows if str(r["version"]).strip() == current]
    stats["history"] = len(rows) - len(mine)

    if not mine:
        note = (f"这一版（{current}）还没有交付记录——包还没下来、或者下来忘了记；"
                "先把这一版那几条包记进 records，再核字节与 sha256")
        return {"code": EXIT_FAIL if findings else EXIT_NOTHING,
                "findings": findings, "notes": notes + [note], "stats": stats, "current": current}

    for row in mine:
        path = resolve_file(row, root)
        payload_findings, payload_notes, present = check_payload(row, path, current, pe_reader)
        findings += payload_findings
        notes += payload_notes
        if present:
            stats["checked"] += 1
        elif not findings:
            notes.append(f"{path.name} 不在盘上（交付文件放在仓库外，换台机器就找不着）："
                         "字节与 sha256 这轮没得核，只核了记录本身")
    stats["present"] = stats["checked"] > 0

    for r in rows:
        if r in mine:
            continue
        p = resolve_file(r, root)
        if not p.is_file():
            notes.append(f"历史那条 {r['version']} / {r['platform']} 的那份不在盘上，只核了记录本身")

    if findings:
        code = EXIT_FAIL
    elif stats["tags"] and stats["release"]:
        code = EXIT_OK
    else:
        if not stats["tags"]:
            notes.append("记录里那个 tag 指的是哪次提交，这一组没得核（所以不报绿）")
        if not stats["release"]:
            notes.append("Release 上挂着的那份大小对不对得上，这一组没得核（所以不报绿）")
        code = EXIT_NOTHING
    return {"code": code, "findings": findings, "notes": notes, "stats": stats, "current": current}


def main(argv: list[str], git_runner=None, gh_runner=None) -> int:
    ap = argparse.ArgumentParser(description="交付物溯源（rc-checklist A48）")
    ap.add_argument("--manifest", default=str(MANIFEST), help="记录文件，默认 docs/artifacts.json")
    ap.add_argument("--root", default=str(ROOT), help="仓库目录（记录里的相对路径按它解），默认本仓库")
    args = ap.parse_args(argv)

    result = run(Path(args.manifest), Path(args.root), git_runner=git_runner, gh_runner=gh_runner)
    for msg in result["findings"]:
        print(f"FAIL {msg}")
    for msg in result["notes"]:
        print(f"NOTE {msg}")

    s, cur = result["stats"], result["current"]
    row = None
    if s["present"] and result["code"] == EXIT_OK:
        for r in json.loads(Path(args.manifest).read_text(encoding="utf-8"))["artifacts"]:
            if str(r["version"]).strip() == cur and str(r["platform"]).strip() == "windows-x64":
                row = r
                break
    if result["code"] == EXIT_OK:
        if row:
            head = (f"OK {cur} 那 {s['records'] - s['history']} 条记录里，盘上核过 "
                    f"{s['checked']} 份（{row['asset']}，{row['bytes']} 字节，sha256 "
                    f"{str(row['sha256'])[:12]}…），包体内版本串也是 {cur}；")
        else:
            head = f"OK {cur} 那 {s['records'] - s['history']} 条记录（本机盘上都没有那份包）；"
        print(f"{head}Release 大小对得上 {s['release']} 条；记录里那 {s['tags']} 个 tag "
              f"也都真指在写着这一版的那次提交上；另有 {s['history']} 条历史记录"
              "（历史那几份不在盘上时只核记录本身）")
    elif result["code"] == EXIT_FAIL:
        print(f"FAIL {cur}：记录跟盘上那份对不上，先照上面那几条核清，别把不是这一版的包交出去")
    else:
        print(f"未验 这一版（{cur}）还没有可核的那一份——没有记录，或者记录里那份不在盘上，"
              "或者 tag / Release 那一组没得核")
    return result["code"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
