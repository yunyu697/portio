"""把图标画布里的透明留白裁掉，让图形真正铺满图标块。

Windows / macOS 都不给图标额外加内边距，所以 PNG 里有多少透明边，桌面上就少多少面积。
本工具：读 PNG → 按 alpha 求内容包围盒 → 按目标留白比例重排 → 输出各尺寸 + .ico。

只用标准库（zlib + struct），不引入 Pillow，避免为了改图标去动用户环境。
用法：
    python scripts/icon_fit.py --inspect <png>             # 只报包围盒占比
    python scripts/icon_fit.py --fix <src> <outdir>        # 生成 icon.png/.ico 与各尺寸
"""
import argparse
import struct
import sys
import zlib
from pathlib import Path

MARGIN = 0.02  # 图形四周留 2%，再多就会显得"缩在里面"


# ---------- PNG 读写 ----------
def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} 不是 PNG")
    pos, idat, width, height, depth, ctype = 8, b"", 0, 0, 8, 6
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", body[:10])
            if depth != 8 or ctype not in (2, 6):
                raise SystemExit(f"只支持 8 位 RGB/RGBA，当前 depth={depth} ctype={ctype}")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length
    channels = 4 if ctype == 6 else 3
    raw = zlib.decompress(idat)
    stride = width * channels
    pixels = bytearray(width * height * 4)
    prev = bytearray(stride)
    off = 0
    for y in range(height):
        f = raw[off]
        line = bytearray(raw[off + 1 : off + 1 + stride])
        off += 1 + stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif f != 0:
            raise SystemExit(f"未知的行过滤类型 {f}")
        prev = line
        row = y * width * 4
        if channels == 4:
            pixels[row : row + width * 4] = line
        else:
            for x in range(width):
                pixels[row + x * 4 : row + x * 4 + 3] = line[x * 3 : x * 3 + 3]
                pixels[row + x * 4 + 3] = 255
    return width, height, pixels


def write_png(path, width, height, pixels):
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride : (y + 1) * stride]

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    Path(path).write_bytes(out)


# ---------- 几何 ----------
def bbox(width, height, pixels):
    minx, miny, maxx, maxy = width, height, -1, -1
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            if pixels[row + x * 4 + 3] > 8:  # 极淡的半透明像素不参与，避免描边阴影撑大包围盒
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < 0:
        raise SystemExit("整张图都是透明的")
    return minx, miny, maxx + 1, maxy + 1


def sample(width, pixels, x, y):
    # 双线性采样，先在 premultiplied alpha 下插值，避免透明边缘发黑
    x0, y0 = int(x), int(y)
    fx, fy = x - x0, y - y0
    x1, y1 = min(x0 + 1, width - 1), min(y0 + 1, width - 1)
    out = [0.0, 0.0, 0.0, 0.0]
    for (px, py, w) in (
        (x0, y0, (1 - fx) * (1 - fy)),
        (x1, y0, fx * (1 - fy)),
        (x0, y1, (1 - fx) * fy),
        (x1, y1, fx * fy),
    ):
        i = (py * width + px) * 4
        a = pixels[i + 3] / 255.0
        out[0] += pixels[i] * a * w
        out[1] += pixels[i + 1] * a * w
        out[2] += pixels[i + 2] * a * w
        out[3] += a * w
    alpha = out[3]
    if alpha > 0:
        return (
            min(255, int(out[0] / alpha + 0.5)),
            min(255, int(out[1] / alpha + 0.5)),
            min(255, int(out[2] / alpha + 0.5)),
            min(255, int(alpha * 255 + 0.5)),
        )
    return (0, 0, 0, 0)


def fit_to_square(src, size, margin=MARGIN):
    """把 src（已被裁到内容）等比缩放并居中放进 size×size 画布，四周留 margin。"""
    sw, sh, sp = src
    inner = size * (1 - 2 * margin)
    scale = min(inner / sw, inner / sh)
    dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
    ox, oy = (size - dw) // 2, (size - dh) // 2
    out = bytearray(size * size * 4)
    for y in range(dh):
        sy = (y + 0.5) / scale - 0.5
        sy = min(max(sy, 0), sh - 1)
        for x in range(dw):
            sx = (x + 0.5) / scale - 0.5
            sx = min(max(sx, 0), sw - 1)
            r, g, b, a = sample(sw, sp, sx, sy)
            i = ((oy + y) * size + ox + x) * 4
            out[i : i + 4] = bytes((r, g, b, a))
    return out


def crop(width, height, pixels, box):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    out = bytearray(w * h * 4)
    for y in range(h):
        src_row = (y0 + y) * width * 4
        out[y * w * 4 : (y + 1) * w * 4] = pixels[src_row + x0 * 4 : src_row + x1 * 4]
    return w, h, out


def write_ico(path, frames):
    """ICO 里直接塞 PNG 帧——Vista 以后都认，比 BMP 老格式省事也省体积。"""
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries, blob = b"", b""
    offset = 6 + 16 * len(frames)
    for size, png in frames:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(blob))
        blob += png
    Path(path).write_bytes(header + entries + blob)


def main():
    global MARGIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", metavar="PNG")
    ap.add_argument("--fix", nargs=2, metavar=("SRC", "OUTDIR"))
    ap.add_argument(
        "--margin",
        type=float,
        default=MARGIN,
        help="四周留白比例，0 表示图形贴到画布边缘（Windows 邻居图标多是这个效果）",
    )
    args = ap.parse_args()
    MARGIN = args.margin

    if args.inspect:
        w, h, px = read_png(args.inspect)
        x0, y0, x1, y1 = bbox(w, h, px)
        print(
            f"{w}x{h} 内容包围盒 {x1 - x0}x{y1 - y0} "
            f"= 宽 {(x1 - x0) / w:.1%} / 高 {(y1 - y0) / h:.1%}"
        )
        return

    if not args.fix:
        ap.print_help()
        return

    src_path, outdir = args.fix
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    w, h, px = read_png(src_path)
    box = bbox(w, h, px)
    x0, y0, x1, y1 = box
    print(f"源 {w}x{h}，内容 {x1 - x0}x{y1 - y0}，开始重排…")
    content = crop(w, h, px, box)

    frames = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixels = fit_to_square(content, size, MARGIN)
        frames.append((size, pixels))
    for size in (32, 64, 128, 256, 512, 1024):
        pixels = fit_to_square(content, size, MARGIN)
        name = "icon.png" if size == 1024 else (
            "32x32.png" if size == 32 else
            "128x128.png" if size == 128 else
            "128x128@2x.png" if size == 256 else f"icon-{size}.png"
        )
        tmp = outdir / f".tmp-{name}"
        write_png(tmp, size, size, pixels)
        if size == 32 or size == 128 or size == 256 or size == 1024:
            write_png(outdir / name, size, size, pixels)
        print(f"  {name} {size}x{size}")

    # .ico：把每帧写成独立 PNG 再塞进容器
    import io

    png_frames = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixels = fit_to_square(content, size, MARGIN)
        buf = Path(outdir / f".tmp-ico-{size}.png")
        write_png(buf, size, size, pixels)
        png_frames.append((size, buf.read_bytes()))
        buf.unlink()
    write_ico(outdir / "icon.ico", png_frames)
    print("  icon.ico（16/24/32/48/64/128/256）")
    for f in outdir.glob(".tmp-*"):
        f.unlink()


if __name__ == "__main__":
    main()


