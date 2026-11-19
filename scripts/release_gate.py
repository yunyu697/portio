#!/usr/bin/env python3
"""按 tag 判定该不该发包。

规则（用户拍板）：只有 RC 与正式版发包；Alpha 只打 tag、不建 Release、不跑打包矩阵。

这条判定以前写在 release.yml 的 gate 作业里，是一段内联 bash——本地没法跑，也没测试，
改错了要等到真打 tag 才发现。现在搬到这里，workflow 只负责调用，判定有单测覆盖。

用法：
    python scripts/release_gate.py --tag v1.0.6-RC1
    python scripts/release_gate.py --tag v1.0.6-RC1 --github-output "$GITHUB_OUTPUT"

退出码：0 = 判定成功；1 = tag 与仓库版本不一致 / tag 格式不对（不该发，也不该静默改判）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import version as vt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VER_SPAN = re.compile(r'<span class="ver"[^>]*>(.*?)</span>', re.S)


class GateError(RuntimeError):
    pass


def repo_version(root: Path = ROOT) -> str:
    """读 ui/index.html 里标题栏那个版本号（与 check_versions.py 同一处）。"""
    html = (root / "ui" / "index.html").read_text(encoding="utf-8")
    m = VER_SPAN.search(html)
    if not m:
        raise GateError('ui/index.html 里找不到 <span class="ver">')
    return m.group(1).strip()


def classify(version_text: str) -> tuple[bool, bool, str]:
    """按版本号的后缀决定 (publish, prerelease, 说明)。"""
    _, _, _, stage, _ = vt.parse(version_text)  # 格式不对会抛 VersionError
    if stage == "Alpha":
        return False, False, "Alpha 版：只打 tag，不建 Release、不跑打包矩阵"
    if stage == "RC":
        return True, True, "RC 版：发预发布包"
    return True, False, "正式版：发正式包"


def gate(tag: str, current: str) -> dict:
    if not tag.startswith("v"):
        raise GateError(f"tag 必须以 v 开头：{tag!r}")
    version_text = tag[1:]
    publish, prerelease, reason = classify(version_text)
    if version_text != current:
        raise GateError(
            f"tag {tag} 与仓库里的版本 {current} 不一致，先改版本再打 tag"
        )
    return {
        "version": version_text,
        "publish": publish,
        "prerelease": prerelease,
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按 tag 判定该不该发包")
    parser.add_argument("--tag", required=True, help="形如 v1.0.6-RC1")
    parser.add_argument("--github-output", default=None, help="写 GITHUB_OUTPUT 的文件路径")
    parser.add_argument("--root", default=None, help="仓库根目录（默认按脚本位置推断）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else ROOT
    try:
        current = repo_version(root)
        result = gate(args.tag, current)
    except (GateError, vt.VersionError) as e:
        print(f"::error::{e}")
        return 1

    print(f"tag={args.tag} / 仓库版本={current}")
    print(result["reason"])
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            f.write(f"version={result['version']}\n")
            f.write(f"publish={'true' if result['publish'] else 'false'}\n")
            f.write(f"prerelease={'true' if result['prerelease'] else 'false'}\n")
    else:
        print(f"version={result['version']}")
        print(f"publish={result['publish']}")
        print(f"prerelease={result['prerelease']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
