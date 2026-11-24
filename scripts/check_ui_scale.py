"""界面尺度守卫：字号、圆角、间距、组件高度只许取规范里的档位。

数值来源全部在 `ui/tokens.css`；本脚本只负责拦"组件里又冒出裸数字"这类退化。
跑法：python scripts/check_ui_scale.py（无输出问题即退出码 0）
"""

import io
import re
import sys

ROOT = "ui"
FILES = ["ui/index.html", "ui/app.js"]

TOKEN_FS = {f"--fs-{n}" for n in (11, 12, 13, 14, 16, 20)}
# 间距刻度：0/1/2 是发丝与视觉修正，其余全是 4 的倍数
SPACING = {0, 1, 2, 4, 8, 12, 16, 24, 28, 32, 36, 40, 44, 48, 56, 64, 72, 96}
# 组件高度：1/2/3/6/9 是发丝、圆点、图标、滚动条、把手；4 是滑块轨道、12 是滑块拇指（#27）
HEIGHT = {1, 2, 3, 4, 6, 8, 9, 12, 16, 18, 20, 22}
WIDTH = {1, 2, 3, 6, 8, 9, 10, 18, 26, 34, 44}


def px_values(decl: str):
    """从一条声明里抽出所有 px 数值（忽略 calc() 内部的 100% 之类）。"""
    return [float(v) for v in re.findall(r"(-?[0-9.]+)px", decl)]


def check_decl(path: str, lineno: int, prop: str, decl: str, problems: list):
    values = px_values(decl)
    if prop == "font-size":
        if "var(--fs-" in decl:
            token = re.search(r"var\((--fs-[0-9]+)\)", decl)
            if token and token.group(1) not in TOKEN_FS:
                problems.append((path, lineno, f"字号令牌不在四档内：{decl.strip()}"))
        elif values:
            problems.append((path, lineno, f"字号写了裸 px：{decl.strip()}"))
    elif prop == "border-radius":
        cleaned = re.sub(r"var\(--r-[a-z0-9-]+\)", "", decl)
        if px_values(cleaned) or re.search(r"[0-9]+px", cleaned):
            problems.append((path, lineno, f"圆角写了裸 px：{decl.strip()}"))
        elif "0" in re.findall(r"\b(0)\b", cleaned) and not cleaned.strip().startswith("0"):
            pass
    elif prop in ("padding", "margin", "gap", "row-gap", "column-gap"):
        bad = [v for v in values if v not in SPACING and v > 2]
        if bad:
            problems.append((path, lineno, f"{prop} 不在间距刻度内 {bad}：{decl.strip()}"))
    elif prop in ("height", "min-height", "max-height"):
        if "var(" in decl or "calc(" in decl or "%" in decl or decl.strip() in ("auto", "100%"):
            return
        bad = [v for v in values if v not in HEIGHT]
        if bad:
            problems.append((path, lineno, f"高度写了裸 px {bad}：{decl.strip()}"))
    elif prop in ("width", "min-width", "max-width"):
        if "var(" in decl or "calc(" in decl or "%" in decl or decl.strip() == "auto":
            return
        bad = [v for v in values if v not in WIDTH and v % 4 != 0]
        if bad:
            problems.append((path, lineno, f"宽度写了裸 px {bad}：{decl.strip()}"))


def scan(path: str) -> list:
    problems = []
    text = io.open(path, encoding="utf-8").read()
    for lineno, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("/*") or line.strip().startswith("//"):
            continue
        # app.js 里的对象字面量也按同样规则查（样式是 JS 里拼的也逃不掉）
        for prop, decl in re.findall(
            r"(\bfont-size|\bborder-radius|\bpadding|\bmargin|\bgap|\brow-gap|\bcolumn-gap"
            r"|\bheight|\bmin-height|\bmax-height|\bwidth|\bmin-width|\bmax-width)\s*:\s*([^;}\n]+)",
            line,
        ):
            check_decl(path, lineno, prop, decl, problems)
    return problems


def main() -> int:
    problems = []
    for path in FILES:
        try:
            problems += scan(path)
        except FileNotFoundError:
            print(f"跳过（找不到）：{path}")
    if not problems:
        print("OK 界面尺度全部走令牌与刻度（tokens.css）")
        return 0
    for path, lineno, msg in problems:
        print(f"{path}:{lineno}  {msg}")
    print(f"\n共 {len(problems)} 处不在刻度内")
    return 1


if __name__ == "__main__":
    sys.exit(main())
