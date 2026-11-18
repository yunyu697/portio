#!/usr/bin/env python3
"""把同一个版本号写进清单文件，避免手工改漏。

规则见 docs/versioning.md：每完成一个交付单元，预发布位进一位——
Alpha 阶段 v1.0.0-Alpha1 → -Alpha2 → …；RC 阶段 v1.0.5-RC1 → -RC2 → …；
任一阶段满 10 则进到下一个 patch、重新从 1 开始；转正时去掉后缀。

用法：
    python scripts/set_version.py 1.0.0-Alpha3
    python scripts/set_version.py 1.0.5-RC1
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TARGETS = (
    (ROOT / "Cargo.toml", re.compile(r'(?m)^version = "[^"]*"$')),
    (ROOT / "package.json", re.compile(r'(?m)^(\s*)"version": "[^"]*",$')),
    (ROOT / "crates" / "app" / "tauri.conf.json", re.compile(r'(?m)^(\s*)"version": "[^"]*",$')),
    # 标题栏的版本标签是静态文本，容易写漏，一并在这里改。
    # span 上可能还挂着别的属性（如 data-tauri-drag-region），正则要容忍并原样保留。
    (ROOT / "ui" / "index.html", re.compile(r'<span class="ver"([^>]*)>[^<]*</span>')),
)


def patch(text: str, pattern: re.Pattern[str], version: str) -> str:
    if not pattern.search(text):
        raise SystemExit(f"没找到版本字段：{pattern.pattern}")
    if 'class="ver"' in pattern.pattern:
        return pattern.sub(lambda m: f'<span class="ver"{m.group(1)}>{version}</span>', text)
    if pattern.groups:
        return pattern.sub(lambda m: f'{m.group(1)}"version": "{version}",', text)
    return pattern.sub(f'version = "{version}"', text)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    version = argv[1].lstrip("v")

    # 借 version.py 的校验器兜底，避免写进不合规的号
    sys.path.insert(0, str(ROOT / "scripts"))
    from version import parse

    parse(version)

    changed = []
    for path, pattern in TARGETS:
        text = path.read_text(encoding="utf-8")
        new = patch(text, pattern, version)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())

    print(f"v{version} 已写入：" + "、".join(changed) if changed else f"v{version} 无需改动")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
