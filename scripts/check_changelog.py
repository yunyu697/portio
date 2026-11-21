#!/usr/bin/env python3
"""核对 `CHANGELOG.md`：每个版本的更新内容，得是能直接贴到 GitHub Release 的形态。

为什么要有这一步：Release 页面正文只有一句「这一版改了什么，看仓库里的 CHANGELOG.md」，
所以那一段就是用户读到的东西。它坏过一次 —— `1.0.10-RC1` 整段被写成「每一行之间夹一个空行、
续行再缩进两格」，渲染出来是七截互不相连的碎段，一个条目读成七个段落。这种坏法没人看得出来
（是排版坏了，还是我本来就想分行写），只能靠机器盯：

1. `## [Unreleased]` 必须排在全篇第一个二级标题；
2. 每个版本小节标题写成 `## [版本] - YYYY-MM-DD`，版本串能按 `docs/versioning.md` 解析；
3. **当前版本**（读 `package.json`）必须有自己的小节、排在最前、且不是空的 —— 先写更新内容再打包；
4. **当前版本那一节**里：不许连着两个及以上空行、不许空行后面跟带缩进的续行（那是同一个条目被空行
   切成两截）、行尾不许留空白、不许用制表符；
5. 每个版本小节至少有一个 `### ` 子标题，且名字在 Keep a Changelog 那一套里。

第 4 条只查当前这一节：历史小节不重排 —— 已经发出去的十几段没有回头改的必要，
改了反而让「同一版本两处文本不一样」这种更难查的事出现。

CI 与回归门禁 A45 里都会跑这个脚本。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import VersionError, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

# 二级标题就是小节边界（文件里还有「## 各版本…」这种说明性二级标题，它之下不算任何版本小节）。
HEADING2 = re.compile(r"^##\s")
SECTION = re.compile(r"^## \[([^\]]+)\](?:\s*-\s*(\S+))?\s*$")
SUBSECTION = re.compile(r"^###\s+(.+?)\s*$")

# Keep a Changelog 的六类 + 我们一直用的 Known limitations；
# 后三个是历史小节里真实用过的名字，不改写历史，所以列进允许集合。
ALLOWED_SUBSECTIONS = (
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
    "Known limitations",
    "验证方式",
    "Docs",
    "Notes",
)

# 历史上确实存在、但解析不了的两个标题。不修历史写法的例外，写清理由。
LEGACY_HEADINGS = {
    "1.0.1-Alpha5 … Alpha10": "当年把 Alpha5–Alpha10 合成一小节写的",
    "0.0.1-skeleton": "骨架阶段，那会儿还没有版本号规则",
}


def read_current_version(root: Path = ROOT) -> str:
    """当前版本串，取自 `package.json`（它和其余六处由 check_versions.py 对齐）。"""
    return json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]


def split_sections(text: str) -> list[tuple[str, str | None, int, list[tuple[int, str]]]]:
    """按二级标题切开，返回 [(标题原文, 版本串或 None, 起始行号, 正文行)]。行号从 1 数。"""
    lines = text.split("\n")
    bounds = [(i, ln) for i, ln in enumerate(lines, 1) if HEADING2.match(ln)]
    out: list[tuple[str, str | None, int, list[tuple[int, str]]]] = []
    for idx, (start, ln) in enumerate(bounds):
        stop = bounds[idx + 1][0] if idx + 1 < len(bounds) else len(lines) + 1
        m = SECTION.match(ln)
        name = m.group(1) if m else None
        date = m.group(2) if m else None
        body = [(i, lines[i - 1]) for i in range(start + 1, stop)]
        out.append((ln.strip(), name, date, body) if m else (ln.strip(), None, None, body))
    return out


def check_text(text: str, current: str) -> list[str]:
    """把 CHANGELOG 全文过一遍，返回所有问题；空列表就是通过。"""
    sections = split_sections(text)
    problems: list[str] = []

    # 1. Unreleased 必须第一个。
    first = next((s for s in sections if s[1] == "Unreleased"), None)
    if first is None:
        problems.append("找不到「## [Unreleased]」小节")
    elif sections[0] is not first:
        problems.append(
            f"「## [Unreleased]」在第 {first[2]} 行，应当排在全篇第一个二级标题"
        )

    versions = [s for s in sections if s[1] and s[1] != "Unreleased"]
    if not versions:
        problems.append("一个版本小节都没有 —— Release 正文指着这里，里面得真有东西")

    # 2. 版本串、日期。
    for _head, name, date, _body in versions:
        if name in LEGACY_HEADINGS:
            continue
        try:
            parse(name)
        except VersionError as e:
            problems.append(f"版本小节「{name}」的版本串不合规则：{e}")
        if not date:
            problems.append(f"版本小节「{name}」缺日期，写成「## [{name}] - 2026-11-21」")
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            problems.append(f"「{name}」的日期「{date}」不是 YYYY-MM-DD")

    # 3. 当前版本必须在最前、且有内容。
    if versions:
        head, name, _date, body = versions[0]
        if name != current:
            problems.append(
                f"排在最前的版本小节是「{name}」，当前版本是「{current}」——"
                "先把这一版的更新内容写进 CHANGELOG，再打包"
            )
        elif not any(ln.strip() for _i, ln in body):
            problems.append(f"「{name}」小节是空的 —— 这一版改了什么都还没写")

    # 5. 每节都要有子标题（历史小节也查：它们本来就都有）。
    for _head, name, _date, body in versions:
        if not any(SUBSECTION.match(ln) for _i, ln in body):
            problems.append(f"「{name}」小节里一个「### 」子标题都没有（Added / Fixed / Known limitations…）")
        for i, ln in body:
            m = SUBSECTION.match(ln)
            if m and m.group(1) not in ALLOWED_SUBSECTIONS:
                problems.append(
                    f"第 {i} 行子标题「{m.group(1)}」不在允许的集合里："
                    + " / ".join(ALLOWED_SUBSECTIONS)
                )

    # 4. 当前版本那一节的排版（历史小节不重排）。
    if versions and versions[0][1] == current:
        problems.extend(check_layout(current, versions[0][3]))

    return problems


def check_layout(name: str, body: list[tuple[int, str]]) -> list[str]:
    """当前版本小节内部的排版检查：连续空行、空行切断续行、行尾空白。"""
    problems: list[str] = []
    prev_blank = 0
    for i, ln in body:
        if ln.strip() == "":
            prev_blank += 1
            if prev_blank == 2:
                problems.append(
                    f"第 {i} 行起在「{name}」里连着两个空行 —— 一段话要连着写，"
                    "空行会被吞掉或被渲染成一堆空段"
                )
            continue
        lead = len(ln) - len(ln.lstrip(" "))
        if lead and prev_blank >= 1:
            problems.append(
                f"第 {i} 行是「{name}」里被空行切断的续行（行首缩进 {lead} 格）——"
                "同一个条目中间不要插空行，续行直接跟在上一行下面"
            )
        if ln != ln.rstrip():
            problems.append(f"第 {i} 行行尾有多余空白（「{name}」）")
        if "\t" in ln:
            problems.append(f"第 {i} 行用了制表符（「{name}」）——缩进一律用空格")
        prev_blank = 0
    return problems


def main() -> int:
    if not CHANGELOG.is_file():
        print("找不到 CHANGELOG.md", file=sys.stderr)
        return 1
    text = CHANGELOG.read_text(encoding="utf-8")
    current = read_current_version()
    problems = check_text(text, current)
    if problems:
        print("CHANGELOG 有问题：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    sections = [s for s in split_sections(text) if s[1] and s[1] != "Unreleased"]
    print(f"OK {len(sections)} 个版本小节；当前 {current} 排在最前、排版干净")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
