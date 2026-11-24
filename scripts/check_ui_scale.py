"""界面尺度守卫：字号、圆角、间距、组件高度只许取规范里的档位。

数值来源全部在 `ui/tokens.css`；本脚本负责拦"组件里又冒出裸数字"这类退化，
并按规范 §3 / §10 矩阵核对圆角档位与控件状态族（按压 / 焦点）。
跑法：python scripts/check_ui_scale.py（无输出问题即退出码 0）
"""

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["ui/index.html", "ui/app.js"]
HTML_FILE = "ui/index.html"

TOKEN_FS = {f"--fs-{n}" for n in (11, 12, 13, 14, 16, 20)}
# 间距刻度：0/1/2 是发丝与视觉修正，其余全是 4 的倍数
SPACING = {0, 1, 2, 4, 8, 12, 16, 24, 28, 32, 36, 40, 44, 48, 56, 64, 72, 96}
# 组件高度：1/2/3/6/8/9 是发丝、圆点、图标、滚动条、把手；4 是滑块轨道、12 是滑块拇指（#27）
HEIGHT = {1, 2, 3, 4, 6, 8, 9, 12, 16, 18, 20, 22}
WIDTH = {1, 2, 3, 6, 8, 9, 10, 18, 26, 34, 44}

# ---------- 圆角档位对照表（规范 §3 四档 + 胶囊/发丝/圆） ----------
# 只钉规范 §10 矩阵里写明档位的组件；未列出的圆角仍受"必须用令牌"约束。
# 选择器 → 允许出现的圆角令牌集合。
RADIUS_TIER = {
    ".tab": {"--r-8"},
    ".find": {"--r-6"},
    ".find-btn": {"--r-4"},
    ".fp-block": {"--r-8"},
    ".fp-btn": {"--r-4"},
    ".drawer": {"--r-8"},
    ".ctx": {"--r-8"},
    ".ctx-item": {"--r-4"},
    ".dd-menu": {"--r-8"},
    ".dd-trigger": {"--r-6"},
    ".dd-item": {"--r-4"},
    ".sheet": {"--r-12"},
    ".field .remember input": {"--r-4"},
    ".field input": {"--r-6"},
    ".field select": {"--r-6"},
    ".btn": {"--r-6"},
    ".sess-search": {"--r-6"},
    ".sess-quick input": {"--r-4"},
    ".sess-quick button": {"--r-4"},
    ".sess-import .trigger": {"--r-6"},
    ".sess-import .item": {"--r-4"},
    ".sess-row": {"--r-6"},
    ".set .acc-dot": {"--r-6"},
    ".set .hz": {"--r-6"},
    ".set .hz-del": {"--r-4"},
    ".set .hosts-empty": {"--r-6"},
    ".seg": {"--r-6"},
    ".seg button": {"--r-4"},
    ".toast div": {"--r-8"},
}

# ---------- 状态族覆盖（规范 §9） ----------
# 按钮 / 可点控件：按压 active + 键盘焦点 focus-visible；输入：焦点 focus。
BUTTON_STATES = {
    ".btn": ["active", "focus-visible"],
    ".tbtn": ["active", "focus-visible"],
    ".fp-btn": ["active", "focus-visible"],
    ".find-btn": ["active", "focus-visible"],
    ".seg button": ["active", "focus-visible"],
    ".dd-trigger": ["active", "focus-visible"],
    ".dd-item": ["active", "focus-visible"],
    ".sess-quick button": ["active", "focus-visible"],
    ".sess-import .trigger": ["active", "focus-visible"],
    ".sess-import .item": ["active"],
    ".set .hz-del": ["active", "focus-visible"],
    ".set .acc-dot": ["focus-visible"],
    ".field .remember input": ["focus-visible"],
}
INPUT_STATES = {
    ".field input": ["focus"],
    ".field select": ["focus"],
    ".sess-search": ["focus"],
    ".sess-quick input": ["focus"],
}
ALL_STATES = {**BUTTON_STATES, **INPUT_STATES}


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


def parse_rules(text: str):
    """拆出 CSS 规则：归一化后的选择器 → 规则体。注释先抹掉。"""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        for sel in m.group(1).split(","):
            yield sel.strip(), m.group(2)


def _sel_match(selector: str, key: str) -> bool:
    """选择器相等，或为带修饰类 / 伪类的同族（.btn.primary、.btn:hover、.set .hz-del:hover）。"""
    return (
        selector == key
        or selector.startswith(key + ".")
        or selector.startswith(key + ":")
    )


def scan_radius(text: str) -> list:
    """核对对照表内组件的圆角令牌档位。"""
    problems = []
    rules = list(parse_rules(text))
    # 长键优先：`.field .remember input` 不能被 `.field input` 先吃掉
    for selector, body in rules:
        m = re.search(r"border-radius:([^;}]+)", body)
        if not m:
            continue
        decl = m.group(1)
        for key, allowed in sorted(RADIUS_TIER.items(), key=lambda kv: -len(kv[0])):
            if _sel_match(selector, key):
                tokens = re.findall(r"var\((--r-[a-z0-9-]+)\)", decl)
                if tokens:
                    bad = [t for t in tokens if t not in allowed]
                    if bad:
                        problems.append(
                            f"{selector} 圆角档位应为 {sorted(allowed)}，实际 {tokens}"
                        )
                else:
                    bare = re.sub(r"var\(--r-[a-z0-9-]+\)", "", decl)
                    if not re.fullmatch(r"[\s0%]+", bare):
                        problems.append(f"{selector} 圆角未走令牌：{decl.strip()}")
                break
    return problems


def missing_states(selectors: list, key: str) -> list:
    """某个对照组件还缺哪些伪类状态。"""
    return [
        pseudo
        for pseudo in ALL_STATES[key]
        if not any(_sel_match(sel, key) and f":{pseudo}" in sel for sel in selectors)
    ]


def scan_states(text: str) -> list:
    """核对按钮 / 输入控件是否带齐规范 §9 要求的伪类状态。"""
    selectors = [sel for sel, _ in parse_rules(text)]
    return [
        f"{key} 缺 :{pseudo}"
        for key in ALL_STATES
        for pseudo in missing_states(selectors, key)
    ]


def main() -> int:
    problems = []
    for name in FILES:
        p = ROOT / name
        if not p.exists():
            print(f"跳过（找不到）：{name}")
            continue
        problems += scan(str(p))

    html = ROOT / HTML_FILE
    if html.exists():
        text = html.read_text(encoding="utf-8")
        problems += [("", 0, msg) for msg in scan_radius(text)]
        problems += [("", 0, msg) for msg in scan_states(text)]

    if not problems:
        print("OK 界面尺度全部走令牌与刻度（tokens.css），圆角档位与状态族齐备")
        return 0
    for path, lineno, msg in problems:
        where = f"{path}:{lineno}  " if path else ""
        print(f"{where}{msg}")
    print(f"\n共 {len(problems)} 处不在刻度内")
    return 1


if __name__ == "__main__":
    sys.exit(main())
