#!/usr/bin/env python3
"""Portio 版本号工具：校验格式、按进位规则推算下一版。

规则来源：docs/versioning.md
    vMAJOR.MINOR.PATCH[-AlphaN|-RCN]
    MINOR 与 PATCH 取值 0–10，超过 10 向高位进位。
    预发布阶段统一写作 Alpha / RC（首字母大写），这样按字符串排序也保持 Alpha < RC。

用法：
    python scripts/version.py check 1.0.10
    python scripts/version.py next 1.0.10 patch          -> 1.1.0
    python scripts/version.py next 1.10.10 patch         -> 2.0.0
    python scripts/version.py next 1.2.3 stage Alpha     -> 1.2.3-Alpha1
    python scripts/version.py next 1.2.3-Alpha10 stage Alpha -> 1.2.4-Alpha1
    python scripts/version.py next 1.2.3-Alpha3 stage RC -> 1.2.3-RC1
    python scripts/version.py next 1.2.3-RC1 final       -> 1.2.3
"""

from __future__ import annotations

import re
import sys

MAX_PART = 10
STAGES = ("Alpha", "RC")

# 输入时容忍小写，输出一律规整成 Alpha / RC
_STAGE_ALIAS = {"alpha": "Alpha", "rc": "RC"}

PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z]+)(\d+))?$")


class VersionError(ValueError):
    pass


def parse(text: str) -> tuple[int, int, int, str | None, int]:
    m = PATTERN.match(text.strip())
    if not m:
        raise VersionError(
            f"格式不对：{text!r}，应为 v1.0.0 / v1.0.0-Alpha1 / v1.0.0-RC1"
        )
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    stage = _STAGE_ALIAS.get(m.group(4).lower()) if m.group(4) else None
    if m.group(4) and stage is None:
        raise VersionError(f"未知阶段 {m.group(4)!r}，只能是 Alpha 或 RC")
    counter = int(m.group(5)) if m.group(5) else 0
    for name, value in (("MINOR", minor), ("PATCH", patch)):
        if not 0 <= value <= MAX_PART:
            raise VersionError(f"{name} 必须在 0–{MAX_PART} 之间，当前 {value}；超过就该进位了")
    if stage and not 1 <= counter <= MAX_PART:
        raise VersionError(f"预发布计数必须在 1–{MAX_PART} 之间，当前 {counter}")
    return major, minor, patch, stage, counter


def render(major: int, minor: int, patch: int, stage: str | None, counter: int) -> str:
    base = f"{major}.{minor}.{patch}"
    return f"{base}-{stage}{counter}" if stage else base


def bump_patch(major: int, minor: int, patch: int) -> tuple[int, int, int]:
    patch += 1
    if patch > MAX_PART:
        patch = 0
        minor += 1
    if minor > MAX_PART:
        minor = 0
        major += 1
    return major, minor, patch


def bump_minor(major: int, minor: int) -> tuple[int, int, int]:
    minor += 1
    if minor > MAX_PART:
        minor = 0
        major += 1
    return major, minor, 0


def next_version(text: str, kind: str, stage: str | None = None) -> str:
    major, minor, patch, cur_stage, counter = parse(text)

    if kind == "patch":
        major, minor, patch = bump_patch(major, minor, patch)
        return render(major, minor, patch, None, 0)

    if kind == "minor":
        major, minor, patch = bump_minor(major, minor)
        return render(major, minor, patch, None, 0)

    if kind == "major":
        return render(major + 1, 0, 0, None, 0)

    if kind == "stage":
        target = _STAGE_ALIAS.get((stage or "").lower())
        if target is None:
            raise VersionError(f"阶段只能是 Alpha 或 RC，收到 {stage!r}")
        if cur_stage is None:
            return render(major, minor, patch, target, 1)
        if cur_stage == target:
            counter += 1
            if counter > MAX_PART:  # 预发布做满 10 次就进位到下一 patch，重新从 1 起
                major, minor, patch = bump_patch(major, minor, patch)
                return render(major, minor, patch, target, 1)
            return render(major, minor, patch, target, counter)
        if STAGES.index(target) < STAGES.index(cur_stage):
            raise VersionError(f"不能从 {cur_stage} 退回 {target}")
        return render(major, minor, patch, target, 1)

    if kind == "final":
        if cur_stage is None:
            raise VersionError(f"{render(major, minor, patch, None, 0)} 已经是正式版")
        return render(major, minor, patch, None, 0)

    raise VersionError(f"未知动作：{kind!r}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    try:
        if cmd == "check":
            if len(argv) != 3:
                print("用法：check <version>")
                return 2
            print(f"OK v{render(*parse(argv[2]))}")
            return 0
        if cmd == "next":
            if len(argv) < 4:
                print("用法：next <version> <patch|minor|major|stage|final> [Alpha|RC]")
                return 2
            stage = argv[4] if len(argv) > 4 else None
            print(next_version(argv[2], argv[3], stage))
            return 0
    except VersionError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"未知命令：{cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
