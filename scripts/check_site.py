#!/usr/bin/env python3
"""离线说明页与代码对表：`docs/site/index.html` 里写的每一项设置、每一个档位，
必须和 `ui/index.html` 设置面板里真有的对上，版本串也得是当前那个。

为什么要这么干：说明页是手写的，每加一个设置它就悄悄落后一版——RC8 这一版它还在写
「界面密度 两档」「终端字号 11–18」，而代码里早就是三档与 9–24。这一步不看渲染效果，
只做双向对表：产品加了设置而页面没跟上 → FAIL；页面写了一项产品里没有的 → 同样 FAIL。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui" / "index.html"
SITE = ROOT / "docs" / "site" / "index.html"

LABEL_RE = re.compile(r"<label>(.*?)</label>", re.S)
SEG_RE = re.compile(r'<button[^>]*data-v="([^"]*)"[^>]*>(.*?)</button>', re.S)
SW_RE = re.compile(r'<button[^>]*data-sw="[^"]*"[^>]*>', re.S)
RANGE_RE = re.compile(r'<input type="range"[^>]*min="(\d+)"[^>]*max="(\d+)"', re.S)
ROW_RE = re.compile(r'<tr><td class="w">(.*?)</td><td>(.*?)</td></tr>', re.S)
VER_RE = re.compile(r"\d+\.\d+\.\d+(?:-Alpha\d+|-RC\d+)?")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def norm(text: str) -> str:
    """比对口径：去标签、去全部空白（`会话栏 · 启动时` 与 `会话栏·启动时` 算同一个）。
    `<label>强调色 <b id="acc-name">青</b></label>` 里的 `<b>` 是当前值，不是项名，先摘掉。"""
    return re.sub(r"\s+", "", strip_tags(re.sub(r"<b\b[^>]*>.*?</b>", "", text, flags=re.S)))


def settings_block(ui_text: str) -> str:
    start = ui_text.find('id="settings-modal"')
    stop = ui_text.find('id="keys-modal"')
    if start < 0 or stop <= start:
        raise ValueError("ui/index.html 里找不到设置面板（settings-modal … keys-modal）")
    return ui_text[start:stop]


def parse_settings(ui_text: str) -> list[dict]:
    """按 <label> 切出设置面板里每一项：名字、可点的档位、滑块范围。"""
    block = settings_block(ui_text)
    marks = [(m.start(), m.end(), m.group(1)) for m in LABEL_RE.finditer(block)]
    items: list[dict] = []
    for i, (_start, end, label) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(block)
        body = block[end:stop]
        labels: list[str] = []
        for m in SEG_RE.finditer(body):
            text = norm(m.group(2))
            labels.append(text or m.group(1))  # 色片之类没有文字时退回 data-v 值
        for m in SW_RE.finditer(body):
            title = re.search(r'title="([^"]*)"', m.group(0))
            if title:
                labels.append(title.group(1).replace("（默认）", ""))
        rng = RANGE_RE.search(body)
        items.append({
            "name": norm(label),
            "labels": [lb for lb in labels if lb],
            "range": (rng.group(1), rng.group(2)) if rng else None,
        })
    return items


def look_section(site_text: str) -> str:
    """只看说明页里「设置与外观」那一节：别节的快捷键表、报错表也是两列，会串进来。"""
    start = site_text.find('<section id="look">')
    if start < 0:
        raise ValueError("docs/site/index.html 里找不到 <section id=\"look\">（设置与外观那一节）")
    stop = site_text.find("</section>", start)
    if stop < 0:
        raise ValueError("设置与外观那一节没有收尾的 </section>")
    return site_text[start:stop]


def parse_rows(site_text: str) -> list[dict]:
    """说明页「设置与外观」一节里两列的表行。"""
    return [{"name": norm(m.group(1)), "value": norm(m.group(2))}
            for m in ROW_RE.finditer(look_section(site_text))]


def count_claim(problems: list[str], look: str, n_items: int) -> None:
    """页面开头写「设置里十六项」这种话，数目也得跟设置面板里真有的项数对上。"""
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
          "十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16,
          "十七": 17, "十八": 18, "十九": 19, "二十": 20}
    m = re.search(r"设置里(\S{1,3}?)项", look)
    if not m:
        return
    word = m.group(1)
    if word.isdigit():
        claimed = int(word)
    elif word in cn:
        claimed = cn[word]
    else:
        problems.append(f"说明页里的项数写法认不出：设置里{word}项")
        return
    if claimed != n_items:
        problems.append(f"说明页说设置里{word}项，设置面板里其实是 {n_items} 项")


def compare(items: list[dict], rows: list[dict], site_text: str, ver: str) -> list[str]:
    problems: list[str] = []
    by_name = {r["name"]: r["value"] for r in rows}
    count_claim(problems, look_section(site_text), len(items))
    for it in items:
        value = by_name.get(it["name"])
        if value is None:
            problems.append(f"说明页没写这一项：「{it['name']}」")
            continue
        for lb in it["labels"]:
            if norm(lb) not in value:
                problems.append(f"「{it['name']}」漏了档位「{lb}」")
        if it["range"]:
            lo, hi = it["range"]
            if not any(f"{lo}{dash}{hi}" in value for dash in ("–", "-", "—", "~")):
                problems.append(f"「{it['name']}」的档没写对，代码里是 {lo}–{hi}")
    known = {it["name"] for it in items}
    for r in rows:
        if r["name"] not in known:
            problems.append(f"说明页写了一项界面里没有的：「{r['name']}」")
    for got in sorted(set(VER_RE.findall(site_text))):
        if got != ver:
            problems.append(f"说明页版本串过期：{got} ≠ {ver}")
    if site_text.count(ver) < 3:
        problems.append(f"说明页里当前版本 {ver} 只出现 {site_text.count(ver)} 次（署名/安装/版本段至少三处）")
    return problems


def main() -> int:
    ui_text = UI.read_text(encoding="utf-8")
    site_text = SITE.read_text(encoding="utf-8")
    m = re.search(r'<span class="ver"[^>]*>(.*?)</span>', ui_text)
    ver = (m.group(1).strip() if m else "")
    if not ver:
        print("FAIL 读不到 ui/index.html 里的版本串")
        return 1
    items = parse_settings(ui_text)
    rows = parse_rows(site_text)
    problems = compare(items, rows, site_text, ver)
    if problems:
        for p in problems:
            print(f"FAIL {p}")
        print(f"共 {len(problems)} 处对不上（说明页 docs/site/index.html 与设置面板不同步）")
        return 1
    labels = sum(len(it["labels"]) for it in items)
    print(f"OK 说明页 {len(items)} 项设置 / {labels} 个档位与代码对上，版本 v{ver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
