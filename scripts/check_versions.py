#!/usr/bin/env python3
"""校验版本号写过的每一处都一致，且符合 docs/versioning.md 的规则。CI 与回归 A5 里必跑。

以前这里只核三处（Cargo.toml / package.json / tauri.conf.json），另外两处没人管：
- `ui/index.html` 标题栏那个 `<span class="ver">`：跑起来第一眼就能看到它，写错了界面就自己撒谎；
- `Cargo.lock` 里三个 workspace crate 的版本：构建时才刷新，进位后不构建它就停在上一个版本，
  下次谁跑 `cargo build --locked` 当场红。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import VersionError, parse, render  # noqa: E402

ROOT = str(Path(__file__).resolve().parent.parent)

# 三个 workspace crate 都在 lock 里各占一个 [[package]] 块。
LOCK_CRATES = ("portio-app", "portio-core", "portio-ssh")

VER_SPAN = re.compile(r'<span class="ver"[^>]*>\s*([^<]*?)\s*</span>')


def read_cargo_workspace_version() -> str:
    text = (Path(ROOT) / "Cargo.toml").read_text(encoding="utf-8")
    block = re.search(r"^\[workspace\.package\]\s*$([\s\S]*?)(?:^\[|\Z)", text, re.M)
    if not block:
        raise SystemExit("Cargo.toml 里找不到 [workspace.package]")
    m = re.search(r'^version\s*=\s*"([^"]+)"', block.group(1), re.M)
    if not m:
        raise SystemExit("Cargo.toml 的 [workspace.package] 里没有 version")
    return m.group(1)


def read_json_version(rel: str) -> str:
    return json.loads((Path(ROOT) / rel).read_text(encoding="utf-8"))["version"]


def ui_version(text: str) -> str:
    """标题栏版本标签里的那一串；页面没有这个标签时返回空串。"""
    m = VER_SPAN.search(text)
    return m.group(1).strip() if m else ""


def lock_versions(text: str) -> dict[str, str]:
    """Cargo.lock 里三个 workspace crate 各自的版本；缺哪个就不出现在结果里。"""
    found: dict[str, str] = {}
    for name in LOCK_CRATES:
        block = re.search(
            rf'\[\[package\]\]\s*\nname = "{re.escape(name)}"\s*\nversion = "([^"]*)"',
            text,
        )
        if block:
            found[name] = block.group(1)
    return found


def collect() -> dict[str, str]:
    """把每一处写版本号的地方都读出来，键就是给人看的「这是哪一处」。"""
    base = Path(ROOT)
    sources: dict[str, str] = {
        "Cargo.toml [workspace.package]": read_cargo_workspace_version(),
        "package.json": read_json_version("package.json"),
        "crates/app/tauri.conf.json": read_json_version("crates/app/tauri.conf.json"),
        "ui/index.html 标题栏": ui_version((base / "ui" / "index.html").read_text(encoding="utf-8")),
    }
    lock_path = base / "Cargo.lock"
    if lock_path.is_file():
        lock = lock_versions(lock_path.read_text(encoding="utf-8"))
        for name in LOCK_CRATES:
            # 锁文件在、块却不在，说明 lock 与工作区对不上（改名、删 crate），也要报出来。
            sources[f"Cargo.lock {name}"] = lock.get(name, "（找不到这个包）")
    return sources


def main() -> int:
    sources = collect()
    values = set(sources.values())
    if len(values) != 1:
        print("版本号不一致：", file=sys.stderr)
        for k, v in sources.items():
            print(f"  {k}: {v}", file=sys.stderr)
        return 1

    raw = values.pop()
    try:
        print(f"OK v{render(*parse(raw))}（{len(sources)} 处一致；最小与补丁位均在 0–10）")
    except VersionError as exc:
        print(f"不合规：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
