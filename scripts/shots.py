"""S14 首发截图素材：用现有前端在无头 Chrome 里按统一规格出图。

规格（五个场景 × 深浅两套，共 10 张）：
- 逻辑窗口 1180×690，`--force-device-scale-factor=2` → 实际 PNG 2360×1380（@2x）
- 场景全部走 app.js 里已有的 demo 钩子，不另画假界面：
  main=#sess-demo（三栏 + 双栏文件 + 传输队列三条）、split=#split-demo（2×2 分屏）、
  import=#import-demo（导入来源下拉展开）、settings=#settings-demo（设置面板顶部：自定义十六项）、
  hosts=#hosts-demo-tail（设置面板滚到底：已知主机 + 运行日志）
- 设置面板从十六项之后一屏放不下，所以拆成两张：顶部拍「自定义」，滚到底拍「已知主机」。
  一张图讲不完两件事，硬塞只会两件都看不清。
- 主题用 `?theme=light` / `?theme=dark` 附在 hash 后面，由 app.js 顶部那段参数解析落进 localStorage

每张出图前先用 `--dump-dom` 跑一遍看 `<title>`：出现 `ERR:` 就算失败，不出这张图。
产物落在 docs/shots/，进仓库（这是发布物料，不是 _*.png 那种临时核验图）。

用法：python scripts/shots.py
"""

from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui" / "index.html"
OUT = ROOT / "docs" / "shots"

WINDOW = "1180,690"
SCALE = 2
BUDGET = 6000

SCENES = {
    "main": ("#sess-demo", "三栏：会话栏 + 终端 + 双栏文件 + 传输队列"),
    "split": ("#split-demo", "终端 2×2 分屏"),
    "import": ("#import-demo", "导入来源下拉展开"),
    "settings": ("#settings-demo", "设置面板顶部：自定义十六项"),
    "hosts": ("#hosts-demo-tail", "设置面板滚到底：已知主机与运行日志"),
}

THEMES = ("dark", "light")


def find_chrome() -> str | None:
    env = os.environ.get("PORTIO_CHROME")
    if env and Path(env).exists():
        return env
    for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ):
        if Path(p).exists():
            return p
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def chrome(chrome_exe: str, url: str, profile: str, extra: list[str], timeout: int = 90):
    args = [
        chrome_exe,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        f"--force-device-scale-factor={SCALE}",
        f"--window-size={WINDOW}",
        f"--virtual-time-budget={BUDGET}",
        f"--user-data-dir={profile}",
        *extra,
        url,
    ]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def title_of(chrome_exe: str, url: str, profile: str) -> tuple[bool, str]:
    proc = chrome(chrome_exe, url, profile, ["--dump-dom"])
    m = re.search(r"<title>(.*?)</title>", proc.stdout or "", re.S)
    title = (m.group(1).strip() if m else "")
    return (proc.returncode == 0 and "ERR:" not in title, title)


def main() -> int:
    chrome_exe = find_chrome()
    if not chrome_exe:
        print("找不到 Chrome（设 PORTIO_CHROME）")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    base = UI.as_uri()
    failures: list[str] = []
    made: list[str] = []

    for theme in THEMES:
        for name, (frag, label) in SCENES.items():
            url = f"{base}{frag}?theme={theme}"
            out = OUT / f"portio-{theme}-{name}.png"
            with tempfile.TemporaryDirectory(prefix="portio-shot-") as profile:
                ok, title = title_of(chrome_exe, url, profile)
                if not ok:
                    failures.append(f"{theme}/{name}: 标题异常 → {title or '抓不到 title'}")
                    continue
                proc = chrome(chrome_exe, url, profile, [f"--screenshot={out}"])
                if proc.returncode != 0:
                    failures.append(f"{theme}/{name}: Chrome 退出码 {proc.returncode}")
                    continue
            if not out.exists():
                failures.append(f"{theme}/{name}: 没生成文件")
                continue
            w, h = png_size(out)
            if (w, h) != (1180 * SCALE, 690 * SCALE):
                failures.append(f"{theme}/{name}: 尺寸是 {w}×{h}，应为 {1180 * SCALE}×{690 * SCALE}")
                continue
            made.append(f"{out.relative_to(ROOT)} {w}×{h} {out.stat().st_size}B · {label}")

    for line in made:
        print("OK  " + line)
    for line in failures:
        print("FAIL " + line)
    print(f"共 {len(made)} 张通过 / {len(failures)} 条失败")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
