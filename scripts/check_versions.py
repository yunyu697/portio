#!/usr/bin/env python3
"""校验三处版本号一致，且符合 docs/versioning.md 的规则。CI 里必跑。"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from version import VersionError, parse, render  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_cargo_workspace_version() -> str:
    text = open(os.path.join(ROOT, "Cargo.toml"), encoding="utf-8").read()
    block = re.search(r"^\[workspace\.package\]\s*$([\s\S]*?)(?:^\[|\Z)", text, re.M)
    if not block:
        raise SystemExit("Cargo.toml 里找不到 [workspace.package]")
    m = re.search(r'^version\s*=\s*"([^"]+)"', block.group(1), re.M)
    if not m:
        raise SystemExit("Cargo.toml 的 [workspace.package] 里没有 version")
    return m.group(1)


def read_json_version(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)["version"]


def main() -> int:
    sources = {
        "Cargo.toml [workspace.package]": read_cargo_workspace_version(),
        "package.json": read_json_version("package.json"),
        "crates/app/tauri.conf.json": read_json_version("crates/app/tauri.conf.json"),
    }
    values = set(sources.values())
    if len(values) != 1:
        print("三处版本号不一致：", file=sys.stderr)
        for k, v in sources.items():
            print(f"  {k}: {v}", file=sys.stderr)
        return 1
    raw = values.pop()
    try:
        print(f"OK v{render(*parse(raw))}（最小与补丁位均在 0–10）")
    except VersionError as exc:
        print(f"不合规：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
