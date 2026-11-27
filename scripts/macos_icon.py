"""由 `crates/app/icons/icon.png` 生成 macOS 用的 `icon.icns`（满幅版）。

为什么需要满幅：macOS 26 起（本机 macOS 27.2.1 / 26B131 实测），系统会把
`CFBundleIconFile` 指向的传统 icns 当成"旧式位图"，自动在下面垫一层浅色
squircle 底板，并把图形缩到板面约 68%。只要 icns 四边留透明（旧稿就是四周留
8.6%），用户看到的就是"图标背后还有一块底板"。Windows 侧 `icon.png`/`icon.ico`
一直是满幅的卡片设计，macOS 侧却是带留白的旧稿，两套不一致。

做法：把 `icon.png` 裁到不透明主体，等比拉伸铺满 1024，四角/四边用逐行夹取
补齐成实心方图，交给系统的 squircle 蒙版去切圆角。这样系统不再垫底板，也与
Windows/Linux 用同一份设计语言。

依赖：Pillow、icnsutil（`python -m pip install pillow icnsutil`）。

用法：
    python scripts/macos_icon.py            # 生成并把 icns 写回 crates/app/icons/
    python scripts/macos_icon.py --dry-run  # 只生成预览 PNG，不动仓库文件
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

from PIL import Image
from icnsutil import IcnsFile

ROOT = pathlib.Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "crates" / "app" / "icons"
SOURCE = ICON_DIR / "icon.png"
TARGET = ICON_DIR / "icon.icns"
CANVAS = 1024

# icns 类型 -> 位图边长（ic13/ic14 是 Retina 变体，与 ic08/ic09 同像素尺寸）
SLOTS = [
    ("ic07", 128),
    ("ic08", 256),
    ("ic09", 512),
    ("ic10", 1024),
    ("ic11", 32),
    ("ic12", 64),
    ("ic13", 512),
    ("ic14", 1024),
]


def make_full_bleed(source: pathlib.Path) -> Image.Image:
    """把 icon.png 拉成四边不透明的 1024 方图。"""
    im = Image.open(source).convert("RGBA")
    solid = im.getchannel("A").point(lambda v: 255 if v >= 254 else 0)
    bbox = solid.getbbox()
    if not bbox:
        raise SystemExit(f"{source} 没有不透明像素")

    art = im.crop(bbox).resize((CANVAS, CANVAS), Image.LANCZOS)
    px = art.load()
    # 逐行夹取：圆角与边缘的透明/半透明像素，用它这一行最近的实心像素补色
    for y in range(CANVAS):
        left = next((x for x in range(CANVAS) if px[x, y][3] >= 250), None)
        right = next((x for x in range(CANVAS - 1, -1, -1) if px[x, y][3] >= 250), None)
        if left is None or right is None:
            continue
        for x in range(left):
            px[x, y] = px[left, y]
        for x in range(right + 1, CANVAS):
            px[x, y] = px[right, y]
    return art.convert("RGB")


def build_icns(art: Image.Image, target: pathlib.Path, tmpdir: pathlib.Path) -> None:
    icns = IcnsFile()
    for label, size in SLOTS:
        png = tmpdir / f"{label}.png"
        art.resize((size, size), Image.LANCZOS).save(png)
        icns.add_media(label, file=str(png))
    icns.write(str(target))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只输出预览 PNG")
    args = ap.parse_args()

    art = make_full_bleed(SOURCE)
    if args.dry_run:
        out = pathlib.Path(tempfile.gettempdir()) / "icon-macos-preview.png"
        art.save(out)
        print(f"preview -> {out} ({art.size[0]}x{art.size[1]})")
        return 0

    tmp = ICON_DIR / ".icns-build"
    tmp.mkdir(exist_ok=True)
    try:
        build_icns(art, TARGET, tmp)
    finally:
        for f in tmp.glob("*.png"):
            f.unlink()
        tmp.rmdir()

    size = TARGET.stat().st_size
    readback = IcnsFile(str(TARGET))
    missing = [t for t, _ in SLOTS if t not in readback.media]
    if missing:
        print(f"FAIL: icns 缺档 {missing}", file=sys.stderr)
        return 1
    print(f"ok  {TARGET.relative_to(ROOT)}  {size} B  档位 {len(readback.media)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
