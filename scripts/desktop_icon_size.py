"""在桌面截图里量 Portio 图标到底占多少像素，和邻居对比，别靠眼睛。

做法：把近黑的像素（图标底板 #0E2427 一类的深色块）打成连通区域，
在左侧图标区里找出面积最大的几块，打印包围盒，再算它占桌面图标格子的比例。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_fit as f


def dark_mask(w, h, px, threshold=60):
    mask = bytearray(w * h)
    for i in range(w * h):
        r, g, b, a = px[i * 4 : i * 4 + 4]
        if a > 120 and max(r, g, b) < threshold:
            mask[i] = 1
    return mask


def components(w, h, mask, region, min_area=300):
    x0, y0, x1, y1 = region
    label = 0
    boxes = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = y * w + x
            if not mask[i]:
                continue
            # 洪水填充，四邻域；用栈代替递归
            stack, cells = [(x, y)], []
            mask[i] = 0
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if x0 <= nx < x1 and y0 <= ny < y1 and mask[ny * w + nx]:
                        mask[ny * w + nx] = 0
                        stack.append((nx, ny))
            if len(cells) < min_area:
                continue
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            boxes.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1, len(cells)))
            label += 1
    return boxes


def report(path, region, expect_near=None):
    w, h, px = f.read_png(path)
    boxes = components(w, h, dark_mask(w, h, px), region)
    boxes.sort(key=lambda b: (b[1], b[0]))
    print(f"\n{Path(path).name}  区域 {region}")
    for bx0, by0, bx1, by1, area in boxes:
        print(f"  深色块 {bx1 - bx0}x{by1 - by0}px  左上({bx0},{by0})  面积{area}")
    # 桌面图标一格是 92px（本机 100% 缩放下的大图标间距），拿来当参照
    for bx0, by0, bx1, by1, _ in boxes:
        if expect_near and abs(bx0 - expect_near[0]) < 40 and abs(by0 - expect_near[1]) < 40:
            print(f"  → Portio 图标底板 {bx1 - bx0}px 宽 / 格子约 92px = {(bx1 - bx0) / 92:.0%}")


if __name__ == "__main__":
    # 屏幕左侧图标列，避开右侧的窗口
    report("_desktop_after.png", (0, 700, 420, 900))
    report("_desktop_after2.png", (0, 700, 420, 900))
