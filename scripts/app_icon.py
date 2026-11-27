"""由 `crates/app/icons/icon.png` 生成全尺寸（full-bleed）图标，一次出齐四平台。

设计口径（用户定的）：图形直接铺满画布——不留透明边、不留底板、不留圆角描边。
圆角只在 macOS 由系统 squircle 蒙版负责切；Windows/Linux 就是实心方图。

为什么要这么改：
- macOS 26 起，只带 `CFBundleIconFile` 的传统 icns 会被系统当旧式位图，
  自动垫一层浅色 squircle 底板并把图形缩到板面约 68%。四边留透明就会露出那块板。
- Windows 侧原来的 1024 图带 8% 留白和一圈投影，任务栏/资源管理器看着像"图标背后还有背景"。

依赖：Pillow、icnsutil（`python -m pip install pillow icnsutil`）。

用法：
    python scripts/app_icon.py             # 生成并写回 crates/app/icons/
    python scripts/app_icon.py --preview   # 只输出预览，不动仓库文件
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
MASTER = ICON_DIR / "icon.png"
CANVAS = 1024

PNG_TARGETS = [
    ("128x128.png", 128),
    ("32x32.png", 32),
    ("128x128@2x.png", 256),
]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICNS_SLOTS = [
    ("ic07", 128),
    ("ic08", 256),
    ("ic09", 512),
    ("ic10", 1024),
    ("ic11", 32),
    ("ic12", 64),
    ("ic13", 512),
    ("ic14", 1024),
]


def full_bleed(source: pathlib.Path) -> Image.Image:
    """把母版拉成四边不透明的 1024 实心方图。已是满幅则只补透明像素。"""
    im = Image.open(source).convert("RGBA")
    bbox = im.getchannel("A").point(lambda v: 255 if v >= 254 else 0).getbbox()
    if not bbox:
        raise SystemExit(f"{source} 没有不透明像素")

    has_margin = (bbox[2] - bbox[0]) < int(CANVAS * 0.97) or (bbox[3] - bbox[1]) < int(CANVAS * 0.97)
    if has_margin:
        # 往里收 8px，避开母版边缘的投影晕与抗锯齿毛边
        inset = 8
        crop = im.crop((bbox[0] + inset, bbox[1] + inset, bbox[2] - inset, bbox[3] - inset))
        art = crop.resize((CANVAS, CANVAS), Image.LANCZOS)
    else:
        art = im.resize((CANVAS, CANVAS), Image.LANCZOS)

    px = art.load()
    # 逐行夹取：圆角处与边缘的透明像素，用这一行靠里的实心像素补色（避开毛边）
    for y in range(CANVAS):
        left = next((x for x in range(CANVAS) if px[x, y][3] >= 250), None)
        right = next((x for x in range(CANVAS - 1, -1, -1) if px[x, y][3] >= 250), None)
        if left is None or right is None:
            continue
        lx = min(left + 10, right)
        rx = max(right - 10, left)
        for x in range(left):
            px[x, y] = px[lx, y]
        for x in range(right + 1, CANVAS):
            px[x, y] = px[rx, y]
    return art.convert("RGB")


def write_pngs(art: Image.Image, out_dir: pathlib.Path) -> None:
    art.save(out_dir / "icon.png")
    for name, size in PNG_TARGETS:
        art.resize((size, size), Image.LANCZOS).save(out_dir / name)


def write_ico(art: Image.Image, target: pathlib.Path) -> None:
    art.save(target, format="ICO", sizes=[(s, s) for s in ICO_SIZES])


def write_icns(art: Image.Image, target: pathlib.Path, tmp: pathlib.Path) -> None:
    icns = IcnsFile()
    for label, size in ICNS_SLOTS:
        png = tmp / f"{label}.png"
        art.resize((size, size), Image.LANCZOS).save(png)
        icns.add_media(label, file=str(png))
    icns.write(str(target))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="只出预览 PNG，不动仓库")
    args = ap.parse_args()

    art = full_bleed(MASTER)
    if args.preview:
        out = pathlib.Path(tempfile.gettempdir()) / "app-icon-preview.png"
        art.save(out)
        print(f"preview -> {out} {art.size[0]}x{art.size[1]}")
        return 0

    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        write_pngs(art, ICON_DIR)
        write_ico(art, ICON_DIR / "icon.ico")
        write_icns(art, ICON_DIR / "icon.icns", tmp)
    finally:
        for f in tmp.glob("*.png"):
            f.unlink()
        tmp.rmdir()

    icns = IcnsFile(str(ICON_DIR / "icon.icns"))
    missing = [t for t, _ in ICNS_SLOTS if t not in icns.media]
    if missing:
        print(f"FAIL: icns 缺档 {missing}", file=sys.stderr)
        return 1
    for f in ["icon.png", "128x128.png", "32x32.png", "128x128@2x.png", "icon.ico", "icon.icns"]:
        print(f"  {f:16s} {(ICON_DIR / f).stat().st_size:>8d} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
