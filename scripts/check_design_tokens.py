"""界面颜色守卫：ui/index.html 与 ui/app.js 里不允许出现硬编码色值。

配色只有一个来源 ui/tokens.css（见 docs/design-spec.md 第 2 节）。
这个脚本在每轮 UI 改动后跑一次，退出码 1 表示有违规。

用法：python scripts/check_design_tokens.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["ui/index.html", "ui/app.js"]
TOKENS = "ui/tokens.css"

# #rgb / #rrggbb / #rrggbbaa，以及 rgb()/rgba()/hsl() 字面值
PATTERNS = [
    re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"),
    re.compile(r"\b(?:rgb|rgba|hsl|hsla)\("),
]


def scan(path: Path):
    hits = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        # 允许：纯注释行里提到色值（说明用），但不允许出现在生效的代码里
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        # HTML 实体（&#8212; 之类）不是颜色，先抹掉再匹配
        line = re.sub(r"&#\d+;", "", line)
        for pat in PATTERNS:
            m = pat.search(line)
            if m:
                hits.append((no, m.group(0), stripped))
    return hits


def main() -> int:
    bad = False
    for name in TARGETS:
        p = ROOT / name
        if not p.exists():
            print(f"跳过（不存在）：{name}")
            continue
        hits = scan(p)
        if hits:
            bad = True
            print(f"FAIL {name}：发现 {len(hits)} 处硬编码色值")
            for no, token, text in hits[:20]:
                print(f"  {name}:{no}  {token}   {text[:90]}")
    if not bad:
        print(f"OK 界面文件没有硬编码色值（令牌来源：{TOKENS}）")
        return 0
    print("\n修法：把色值搬进 ui/tokens.css 的 :root / html[data-theme=light]，这里改成 var(--xxx)。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
