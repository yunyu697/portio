"""量桌面图标：先估格子背景色，再把"不是背景"的像素圈出来求包围盒。

只靠深色阈值会把圆角渐变和阴影算漏，所以改成"和四角背景色差多少"。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_fit as f


def median_color(px, w, x, y, r=3):
    vals = []
    for yy in range(y - r, y + r + 1):
        for xx in range(x - r, x + r + 1):
            i = (yy * w + xx) * 4
            vals.append(px[i : i + 3])
    vals.sort(key=lambda v: v[0] + v[1] + v[2])
    return vals[len(vals) // 2]


def ink_box(path, cell, diff=40):
    w, h, px = f.read_png(path)
    x0, y0, x1, y1 = cell
    bg = median_color(px, w, x0 + 4, y0 + 4)
    minx, miny, maxx, maxy = x1, y1, -1, -1
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * w + x) * 4
            d = max(abs(px[i] - bg[0]), abs(px[i + 1] - bg[1]), abs(px[i + 2] - bg[2]))
            if d > diff:
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    if maxx < 0:
        return None
    return minx, miny, maxx + 1, maxy + 1


CELL = 92  # 本机桌面图标格（100% 缩放、大图标）
ICONS = {
    # 名字: (左上角坐标, 截图) —— 同一张桌面截图里取，坐标系一致
    "Portio": (334, 808, "_desktop_after2.png"),
    "Glovius": (332, 574, "_desktop_after2.png"),   # 深色底板，和 Portio 同类型，做参照
    "SQX": (214, 808, "_desktop_after2.png"),       # 彩色铺满，做参照
    "Excel": (32, 908, "_desktop_after2.png"),
}

print(f"参照格子按 {CELL}px 算\n")
for name, (x, y, img) in ICONS.items():
    box = ink_box(img, (x, y, x + CELL, y + CELL))
    if not box:
        print(f"{name}: 没测到")
        continue
    iw, ih = box[2] - box[0], box[3] - box[1]
    print(f"{name:8s} 图形 {iw}x{ih}px  占格子 {iw / CELL:.0%} / {ih / CELL:.0%}  左上({box[0]},{box[1]})")
