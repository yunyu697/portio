#!/usr/bin/env python3
"""一条命令跑完 Portio 的自动化回归项，逐项打印 PASS / FAIL / 未验。

对应 docs/rc-checklist.md §1 的 A1–A34。以前这些步骤散在日志里，每轮都要手打一遍命令，
容易漏项也难对照；这里固定成一个入口，输出可以原样贴进清单的「回归记录」表。

用法：
    python scripts/rc.py              # 全跑（A1 与 A32 最慢，其余几十秒）
    python scripts/rc.py --fast       # 跳过 A1 的 cargo test（只改前端时够用）
    python scripts/rc.py --list       # 只列出会跑哪些项
    python scripts/rc.py A11          # 只跑这一项（改一项时可边改边核）
    python scripts/rc.py A10 A11      # 只跑这几项（也认 A10,A11 这种写法）

退出码：0 = 每一项都真跑过且过；1 = 有 FAIL；2 = 编号写错；3 = 没有 FAIL 但有未验项
（安装包还没打、截图清单还没出、缺 Chrome、`--fast` 跳了 A1 都算）。
未验和通过分开算的理由：绿的意思是「核过了」，不是「没查到问题」。
**核的和交的得是同一份**：A10 / A11 / A33 都按「哪一档构建」走（release 优先、结论里点名），
只核 debug 就等于只核了自己手上那份，用户装的是 release。
**包里那份也得是我核的那份**：A34 把安装包拆开（不安装、不写注册表），拿包里的 `portio-app.exe`
跟构建产物逐字节对——只放过打包器自己改写的那几位 `__TAURI_BUNDLE_TYPE_VAR_` 标记。
环境变量可覆盖探测结果：PORTIO_CHROME、PORTIO_NODE、PORTIO_CARGO、PORTIO_7Z。
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui"
EXE_KINDS = ("release", "debug")  # 「用户装的那份」排前：release 才是真交付物


def target_roots() -> list[Path]:
    """构建产物可能在仓库里，也可能在 CARGO_TARGET_DIR（本机放 D 盘，C 盘紧）。"""
    roots = [ROOT / "target"]
    target = os.environ.get("CARGO_TARGET_DIR")
    if target:
        roots.insert(0, Path(target))
    return roots


def bundle_dirs(kind: str = "") -> list[Path]:
    """安装包目录：要哪一档构建就只认哪一档。

    A11 原来只认 `target/debug/bundle/nsis`，于是它认的是 debug 包、我交付的也是 debug 包
    （4591521 B），而用户从 Releases 下到的是 release 构建出来的那份（3380393 B）。
    核的、交的、用户装的得是同一份，否则「核过了」这句话就只核到了自己手上那份。
    """
    kinds = [kind] if kind in EXE_KINDS else list(EXE_KINDS)
    return [r / k / "bundle" / "nsis" for k in kinds for r in target_roots()]

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
# 屏幕上报的记号。内部状态仍叫 SKIP（老日志与清单按这个字找），
# 但对人要说清它是「没核」，不是「核过」。
LABEL = {PASS: "PASS", FAIL: "FAIL", SKIP: "未验"}
EXIT_OK, EXIT_FAIL, EXIT_BAD_ID, EXIT_PENDING = 0, 1, 2, 3


# ---------- 环境探测 -------------------------------------------------------

def find_cargo() -> str | None:
    env = os.environ.get("PORTIO_CARGO")
    if env and Path(env).exists():
        return env
    found = shutil.which("cargo")
    if found:
        return found
    guess = Path(os.environ.get("USERPROFILE", "")) / (
        ".rustup/toolchains/stable-x86_64-pc-windows-msvc/bin/cargo.exe"
    )
    return str(guess) if guess.exists() else None


def find_node() -> str | None:
    env = os.environ.get("PORTIO_NODE")
    if env and Path(env).exists():
        return env
    found = shutil.which("node")
    if found:
        return found
    # 豆包运行时自带一份 node，本机没装 node 时用它
    pattern = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Doubao", "User Data", "sandbox_runtime", "bases", "*", "node", "node.exe",
    )
    for cand in sorted(glob.glob(pattern), reverse=True):
        if Path(cand).exists():
            return cand
    return None


def find_chrome() -> str | None:
    env = os.environ.get("PORTIO_CHROME")
    if env and Path(env).exists():
        return env
    for cand in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ):
        if Path(cand).exists():
            return cand
    found = shutil.which("chrome")
    return found or None


def find_7z() -> str | None:
    """拆安装包要用 7-Zip（NSIS 的压缩体它能读）。没有就报「未验」，不假装核过。"""
    env = os.environ.get("PORTIO_7Z")
    if env and Path(env).exists():
        return env
    for cand in (
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ):
        if Path(cand).exists():
            return cand
    return shutil.which("7z") or None


# ---------- 通用执行 -------------------------------------------------------

def run(cmd: list[str], timeout: int, cwd: Path = ROOT, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def tail(text: str, n: int = 4) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return " / ".join(lines[-n:])[:300]


def with_path(bin_dir: str | None) -> dict:
    env = dict(os.environ)
    if bin_dir:
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


# ---------- 各项检查 -------------------------------------------------------

def a1_cargo_test() -> tuple[str, str]:
    cargo = find_cargo()
    if not cargo:
        return SKIP, "找不到 cargo（设 PORTIO_CARGO 或用 --fast 跳过）"
    env = with_path(str(Path(cargo).parent))
    proc = run([cargo, "test", "--workspace"], timeout=1200, env=env)
    passed = failed = 0
    for m in re.finditer(r"test result: \w+\. (\d+) passed; (\d+) failed", proc.stdout):
        passed += int(m.group(1))
        failed += int(m.group(2))
    if proc.returncode != 0 or failed:
        return FAIL, f"returncode={proc.returncode}, failed={failed}; {tail(proc.stdout + proc.stderr)}"
    if not passed:
        return FAIL, "没有解析到测试结果，可能编译就没过"
    # 各 crate 的分布不进摘要行，太长；失败时要看全文就回滚到手动跑
    return PASS, f"{passed} passed, {failed} failed"


def a2_node_syntax(node: str | None) -> tuple[str, str]:
    if not node:
        return SKIP, "找不到 node（设 PORTIO_NODE）"
    proc = run([node, "--check", "ui/app.js"], timeout=120)
    if proc.returncode != 0:
        return FAIL, tail(proc.stderr)
    return PASS, "ui/app.js 语法通过"


def a_script(script: str, label: str) -> tuple[str, str]:
    path = ROOT / "scripts" / script
    if not path.exists():
        return SKIP, f"脚本不存在：scripts/{script}"
    proc = run([sys.executable, str(path)], timeout=180)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return FAIL, tail(proc.stdout + proc.stderr)
    return PASS, (out.splitlines()[-1] if out else label)


def chrome_title(chrome: str, url: str, profile: str, window: str | None = None,
                 budget: int = 4000) -> tuple[int, str]:
    args = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        f"--virtual-time-budget={budget}",
        f"--user-data-dir={profile}",
        "--dump-dom",
    ]
    if window:
        args.insert(5, f"--window-size={window}")
    args.append(url)
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    m = re.search(r"<title>(.*?)</title>", proc.stdout or "", re.S)
    return proc.returncode, (m.group(1).strip() if m else "")


def a_narrow(chrome: str | None, profile: str) -> tuple[str, str]:
    """A13：同一页在两档窄窗（1024 / 900）各量一遍几何，两档都得 OK。"""
    if not chrome:
        return SKIP, "找不到 Chrome（设 PORTIO_CHROME）"
    url = (UI / "index.html").as_uri() + "#narrow-test"
    details = []
    for win in ("1024,620", "900,620"):
        code, title = chrome_title(chrome, url, profile, window=win)
        if code != 0:
            return FAIL, f"{win}: Chrome 退出码 {code}"
        if "ERR:" in title:
            return FAIL, f"{win}: 标题里出现 ERR: → {title}"
        if not title.startswith("NARROW-SELFTEST-OK"):
            return FAIL, f"{win}: {title or '抓不到 title'}"
        details.append(f"{win.split(',')[0]} OK")
    return PASS, " / ".join(details)


def a_page(chrome: str | None, profile: str, frag: str, expect: str,
           window: str | None = None, budget: int = 4000) -> tuple[str, str]:
    """expect 是标题必须以之开头的字符串；默认页允许标题里带别的，只要不出现 ERR:。"""
    if not chrome:
        return SKIP, "找不到 Chrome（设 PORTIO_CHROME）"
    url = (UI / "index.html").as_uri() + frag
    code, title = chrome_title(chrome, url, profile, window, budget)
    if code != 0:
        return FAIL, f"Chrome 退出码 {code}"
    if "ERR:" in title:
        return FAIL, f"标题里出现 ERR: → {title}"
    if frag and not title.startswith(expect):
        return FAIL, f"标题是 {title!r}，期望以 {expect!r} 开头"
    if not frag and not title:
        return FAIL, "抓不到 <title>，页面可能没起来"
    return PASS, f"title = {title}"


def app_exe_dirs() -> list[Path]:
    """候选 exe 目录：release 在前、debug 在后，两处 target 根都算。"""
    return [r / k for k in EXE_KINDS for r in target_roots()]


def exe_kind(path: Path) -> str:
    """这份 exe 是哪一档构建——按它所在目录的档名认，认不出就给空串。"""
    for part in reversed(Path(path).parts):
        if part in EXE_KINDS:
            return part
    return ""


def kind_label(kind: str) -> str:
    """写进结论里的档名：光写「Portio 起来了」不够，得写清起的是哪一份。"""
    return f"{kind} 构建" if kind in EXE_KINDS else "不知道哪一档构建"


def find_app_exe(dirs: list[Path]) -> tuple[Path | None, str]:
    """挑要核的那份 portio-app.exe，连同它是哪一档构建一起返回。

    取 mtime 最新的那份（跟 A11 认包同一个口径：不许拿上一轮留下的旧 exe 充数），
    但把档一起带出来——结论里必须写着核的是 release 还是 debug，
    否则「我核的是 debug、用户装的是 release」这件事又藏回去了。
    """
    hits = [d / "portio-app.exe" for d in dirs if (d / "portio-app.exe").is_file()]
    if not hits:
        return None, ""
    newest = max(hits, key=lambda q: q.stat().st_mtime)
    return newest, exe_kind(newest)


def a10_pe_subsystem() -> tuple[str, str]:
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    with exe.open("rb") as f:
        head = f.read(0x400)
    if head[:2] != b"MZ":
        return FAIL, "不是有效的 PE 文件"
    e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
    if head[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return FAIL, "PE 签名缺失"
    subsystem = struct.unpack_from("<H", head, e_lfanew + 4 + 20 + 68)[0]
    if subsystem != 2:
        return FAIL, f"Subsystem={subsystem}，GUI 应为 2（否则启动会带控制台黑窗）"
    return PASS, f"Subsystem=2（GUI，启动不带控制台）← {exe.parent}（{kind_label(kind)}）"


def current_version() -> str:
    """界面标题栏里那个版本串——所有判据跟它同一个口径。"""
    m = re.search(r'<span class="ver"[^>]*>(.*?)</span>', (UI / "index.html").read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def versioned_bundle(ver: str, dirs: list[Path]) -> Path | None:
    """按版本号找当前这一版的安装包；找不到返回 None（A11 与 A34 共用这一个口径）。"""
    ver = (ver or "").strip()
    if not ver:
        return None
    want = f"Portio_{ver}_x64-setup.exe"
    hits = [d / want for d in dirs if (d / want).is_file()]
    return max(hits, key=lambda q: q.stat().st_mtime) if hits else None


def check_bundle(ver: str, dirs: list[Path]) -> tuple[str, str]:
    """按当前版本号找安装包：只认 Portio_<当前版本>_x64-setup.exe。

    这里原来取「目录里 mtime 最新的那个 .exe」，于是仓库根上留着一个两个版本前的包
    也能让这项判过——这一项就退化成「本地有没有留下过安装包」，而不是
    「当前版本的包在不在、体积像不像话」。版本号对不上就 SKIP 并点名旧包，别报 PASS。
    """
    ver = (ver or "").strip()
    if not ver:
        return FAIL, "读不出界面里的版本号，没法判断该认哪一个包"
    newest = versioned_bundle(ver, dirs)
    if newest is None:
        want = f"Portio_{ver}_x64-setup.exe"
        stale = sorted({q.name for d in dirs if d.is_dir() for q in d.glob("Portio_*.exe")})
        tail = ""
        if stale:
            tail = "；这些是旧包、不算：" + "、".join(stale[:3]) + ("…" if len(stale) > 3 else "")
        return SKIP, f"还没构建 {ver} 的安装包（要 {want}）{tail}"
    size = newest.stat().st_size
    mib = size / 1024 / 1024
    if mib < 2 or mib > 30:
        return FAIL, f"{newest.name} 体积 {mib:.2f} MiB 不在 2–30 MiB 的合理区间"
    return PASS, f"{newest.name} {size} 字节（{mib:.2f} MiB）← {newest.parent}"


def a11_bundle() -> tuple[str, str]:
    """认安装包时跟 A33 认同一档：核的是 release，就只认 release 打出来的包。"""
    exe, kind = find_app_exe(app_exe_dirs())
    return check_bundle(current_version(), bundle_dirs(kind) + [ROOT])


SHOTS_DIR = ROOT / "docs" / "shots"
SHOTS_MANIFEST = SHOTS_DIR / "manifest.json"
SHOTS_MIN = 10  # scripts/shots.py 是五场景 × 深浅两套


def load_manifest(path: Path) -> dict | None:
    """读截图清单。文件不在、读不动、不是 JSON 对象，一律当「没有清单」。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def check_shots(manifest: dict | None, ver: str, out_dir: Path) -> tuple[str, str]:
    """发布截图得是本版本的那一套。

    图不会说话：`docs/shots/` 里躺着十张仍是 1.0.7-RC9 界面的图，过了一个月也没人发现，
    press-kit 还指着它们当真值。现在 shots.py 出图时顺手记下版本号与每张的字节数，
    这里就照清单核：版本对不上 → SKIP 并点名是哪一版（不报 PASS），
    版本对上但图少了一张、或字节数变了（有人换过图/改过尺寸）→ FAIL 并点名。
    """
    if not manifest:
        return SKIP, "还没有截图清单（跑 python scripts/shots.py 会顺手写一份）"
    if not ver:
        return FAIL, "读不出界面里的版本号，没法判断这套图是不是本版本的"
    shoot_ver = str(manifest.get("version") or "").strip()
    if shoot_ver != ver:
        return SKIP, (
            f"这套图是 {shoot_ver or '（清单里没写版本）'} 那一版的，当前是 {ver}；"
            "要重出就跑 python scripts/shots.py（不算通过，别拿旧界面当本版物料）"
        )
    shots = manifest.get("shots")
    if not isinstance(shots, list) or not shots:
        return FAIL, "清单里一张图都没记，这份清单替不了任何东西"
    if len(shots) < SHOTS_MIN:
        return FAIL, f"清单只记了 {len(shots)} 张，十张物料里少了 {SHOTS_MIN - len(shots)} 张"
    missing: list[str] = []
    drifted: list[str] = []
    total = 0
    for item in shots:
        name = str((item or {}).get("file") or "").strip() if isinstance(item, dict) else ""
        if not name:
            missing.append("（清单里有一条没写文件名）")
            continue
        path = out_dir / name
        if not path.is_file():
            missing.append(name)
            continue
        size = path.stat().st_size
        want = (item or {}).get("bytes")
        if isinstance(want, int) and want != size:
            drifted.append(f"{name}（清单 {want} 字节 / 现在 {size} 字节）")
            continue
        total += size
    if missing:
        more = f" 等 {len(missing)} 张" if len(missing) > 3 else ""
        return FAIL, "清单里的图在 docs/shots/ 里找不到：" + "、".join(missing[:3]) + more
    if drifted:
        return FAIL, "图跟清单记的对不上（换过图或改过尺寸？）：" + "、".join(drifted[:2])
    mib = total / 1024 / 1024
    return PASS, f"{len(shots)} 张全是 {ver} 的（{mib:.2f} MiB，清单与图逐张对上）"


def a31_shots() -> tuple[str, str]:
    return check_shots(load_manifest(SHOTS_MANIFEST), current_version(), SHOTS_DIR)


# ---------- A32：格式与 lint 闸 -------------------------------------------------

FMT_DIFF = re.compile(r"Diff in (.+?):(\d+):")
CLIPPY_SPOT = re.compile(r"--> (\S+:\d+):(\d+)")


def fmt_spots(text: str) -> list[str]:
    """把 rustfmt 的 `Diff in <文件>:<行>:` 收成 `文件:行`，去掉 `\\\\?\\` 前缀与重复。

    Windows 上 rustfmt 打的是 `Diff in \\\\?\\C:\\…\\lib.rs:36:`，同一个文件常出现两次
    （两个 hunk）——直接贴给人看既眼花又重复，顺手折一下。
    """
    out: list[str] = []
    for m in FMT_DIFF.finditer(text or ""):
        path = m.group(1).strip()
        if path.startswith("\\\\?\\"):
            path = path[4:]
        root = str(ROOT)
        if path.startswith(root + os.sep):
            path = os.path.relpath(path, root)
        spot = f"{path}:{m.group(2)}"
        if spot not in out:
            out.append(spot)
    return out



def lint_verdict(fmt: tuple[int, str], clippy: tuple[int, str]) -> tuple[str, str]:
    """`cargo fmt --check` 与 `cargo clippy -D warnings` 两份结果 → 三态。

    为什么单立一项：A1 只跑 `cargo test`，而 CI 那关是 `fmt → clippy → test`。
    本地一路全绿、CI 红在 clippy 这种事发生过一次（2026-11-19，run 44505662151），
    补跑一遍 `cargo fmt --all` 加 clippy 才平掉——本地的绿必须等于 CI 的绿，
    否则「回归全过」这句话就只对一半。
    """
    bad: list[str] = []
    fmt_code, fmt_text = int(fmt[0] or 0), fmt[1] or ""
    if fmt_code != 0:
        spots = fmt_spots(fmt_text)
        if spots:
            more = f" 等 {len(spots)} 处" if len(spots) > 2 else ""
            bad.append("fmt 有文件没格式化：" + "、".join(spots[:2]) + more)
        else:
            bad.append(f"fmt 没过（退出码 {fmt_code}）：{tail(fmt_text, 2)}")
    clippy_code, clippy_text = int(clippy[0] or 0), clippy[1] or ""
    if clippy_code != 0:
        spots = [m.group(1) for m in CLIPPY_SPOT.finditer(clippy_text)]
        if spots:
            more = f" 等 {len(spots)} 条" if len(spots) > 2 else ""
            bad.append("clippy 有警告：" + "、".join(spots[:2]) + more)
        else:
            bad.append(f"clippy 没过（退出码 {clippy_code}）：{tail(clippy_text, 2)}")
    if bad:
        return FAIL, "；".join(bad) + "（本地这一项跟 CI 的 fmt / clippy 关同一个口径，改完再推）"
    return PASS, "fmt 干净、clippy 零警告（与 CI 那关同口径）"


def a32_lints() -> tuple[str, str]:
    cargo = find_cargo()
    if not cargo:
        return SKIP, "找不到 cargo（设 PORTIO_CARGO）"
    env = with_path(str(Path(cargo).parent))
    fmt = run([cargo, "fmt", "--all", "--check"], timeout=300, env=env)
    clippy = run(
        [cargo, "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"],
        timeout=1800,
        env=env,
    )
    return lint_verdict((fmt.returncode, fmt.stdout + fmt.stderr),
                        (clippy.returncode, clippy.stdout + clippy.stderr))


# ---------- 只跑其中几项 ---------------------------------------------------

# ---------- A33：这份 exe 真能起来 ---------------------------------------

LAUNCH_WAIT = 10.0   # 等窗口出现最多多少秒（debug 版首帧通常 2–4s）
LAUNCH_HOLD = 4.0    # 窗口出来之后再盯多久，看首帧之后会不会当场崩


def top_windows(pid: int) -> list[str]:
    """某个进程名下带标题的顶层窗口（Windows 专用，走 user32）。

    A10 只读 PE 头里那个 Subsystem 字段：它只说明「这份 exe 被标记成 GUI 程序」，
    说明不了这份二进制跑起来会不会当场退出、WebView2 起不起来、标题对不对。
    RC6 立的规矩是「没核过的不许算通过」，那就在这里真拉一次起来。
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    out: list[str] = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            n = user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.strip():
                    out.append(buf.value.strip())
        return True

    user32.EnumWindows(proc_type(visit), 0)
    return out


def kill_tree(pid: int) -> None:
    """连 WebView2 子进程一起收掉——不许在人家桌面上留下一个关不掉的窗口。"""
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=20, check=False)
    except Exception:  # noqa: BLE001 - 收尾失败不该盖掉真正的结论
        pass


def launch_verdict(titles: list[str], alive: bool, waited: float) -> tuple[str, str]:
    """exe 拉起来之后看三件事：进程还在吗、有没有窗口、标题对不对（纯函数，好测）。"""
    if not alive:
        return FAIL, f"起来 {waited:.0f}s 内自己退出了（进程已经不在了）——这份二进制跑不起来"
    errs = [t for t in titles if "ERR:" in t]
    if errs:
        return FAIL, f"窗口标题里出现 ERR: → {errs[0]}（前端起来就炸了）"
    hits = [t for t in titles if "Portio" in t]
    if hits:
        return PASS, f"窗口标题 {hits[0]!r}，撑过 {waited:.0f}s 没退"
    if not titles:
        return FAIL, f"{waited:.0f}s 内一个窗口标题都没拿到——进程在，窗没画出来（卡在首帧？）"
    return FAIL, f"窗口标题是 {titles!r}，没有一条带 Portio"


def probe_launch(exe: Path, wait_window: float = LAUNCH_WAIT, hold: float = LAUNCH_HOLD,
                 window_fn=top_windows, popen=subprocess.Popen,
                 kill=kill_tree) -> tuple[str, str]:
    """把 exe 真拉起来、等窗口、再盯一会儿、然后收干净。"""
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent),
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    titles: list[str] = []
    try:
        while time.time() - started < wait_window:
            if proc.poll() is not None:
                break
            titles = window_fn(proc.pid)
            if titles:
                break
            time.sleep(0.4)
        while proc.poll() is None and time.time() - started < wait_window + hold:
            time.sleep(0.4)
        alive = proc.poll() is None
        if alive:
            titles = window_fn(proc.pid) or titles
        return launch_verdict(titles, alive, time.time() - started)
    finally:
        if proc.poll() is None:
            kill(proc.pid)


def a33_launch() -> tuple[str, str]:
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 的包由 CI 的 build 那关负责起来）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_launch(exe)
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A34：包里那份 exe 跟我核的那份是同一份 -------------------------

MARKER = b"__TAURI_BUNDLE_TYPE_VAR_"


def bundle_marker(data: bytes) -> str:
    """读 tauri 打包器写在 exe 里的那个标记（`__TAURI_BUNDLE_TYPE_VAR_XXX`）。

    构建产物里它是 `UNK`（还不知道会被打成什么包），打包器在做安装包时把它改成
    包型（NSIS 是 `NSS`）。这几位是**唯一**允许两份 exe 不一样的地方，所以得单独认出来、
    抹平了再比，否则「逐字节一致」这句话永远判不过，只能放宽成「差几字节就算了」。
    """
    i = data.find(MARKER)
    if i < 0:
        return ""
    start = i + len(MARKER)
    end = data.find(b"\x00", start)
    if end < 0:
        end = start + 8
    return data[start:end].decode("latin1", "replace")


def blank_marker(data: bytes) -> bytes:
    """把标记那几位抹成空格（长度不变），好让「打包前」与「打包后」逐字节可比。"""
    out = bytearray(data)
    i = out.find(MARKER)
    if i < 0:
        return bytes(out)
    start = i + len(MARKER)
    end = out.find(b"\x00", start)
    if end < 0:
        end = min(start + 8, len(out))
    out[start:end] = b" " * (end - start)
    return bytes(out)


def payload_verdict(built: bytes | None, payload: bytes | None) -> tuple[str, str]:
    """包里的 exe 跟构建产物比（纯函数，好测）。

    只放行打包器改写的那几位标记；别处差一个字节就不算同一份——A11 只核「文件名 + 体积」，
    查不出「装的是上一轮的 exe」这种事，这一项就是补那个洞。
    """
    if payload is None:
        return FAIL, "安装包里拆不出 portio-app.exe——这个包装完了也没程序可跑"
    if built is None:
        return SKIP, f"包里那份 {len(payload)} 字节，但没有构建产物可比（先构建再核）"
    if len(payload) != len(built):
        return FAIL, f"包里那份 {len(payload)} 字节、构建产物 {len(built)} 字节——大小都不一样，不是同一份"
    mark_built, mark_payload = bundle_marker(built), bundle_marker(payload)
    if mark_payload == "UNK":
        return FAIL, "包里那份还写着标记 UNK：打包器没改写它，装上去的是打包前那份"
    if blank_marker(payload) == blank_marker(built):
        if mark_built or mark_payload:
            return PASS, (f"包里那份 {len(payload)} 字节，跟构建产物逐字节一致"
                          f"（只差打包器写的标记：{mark_built or '无'} → {mark_payload or '无'}）")
        return PASS, f"包里那份 {len(payload)} 字节，跟构建产物逐字节一致"
    a, b = blank_marker(built), blank_marker(payload)
    idx = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    first = idx[0] if idx else 0
    return FAIL, f"包里那份跟构建产物差 {len(idx)} 字节（第一处在 0x{first:x}）——不是同一份"


def extract_payload(pkg: Path, seven: str, workdir: Path) -> tuple[Path | None, str]:
    """把包里那份 portio-app.exe 拆到临时目录。

    拆包不是安装：不写注册表、不进开始菜单、不碰用户目录，拆完整个临时目录删掉。
    """
    proc = run([seven, "x", str(pkg), f"-o{workdir}", "-y", "portio-app.exe"], 180)
    got = workdir / "portio-app.exe"
    if got.is_file():
        return got, ""
    return None, tail((proc.stdout or "") + (proc.stderr or "")) or f"7-Zip 退出码 {proc.returncode}"


def a34_payload() -> tuple[str, str]:
    """把 A11 认的那份安装包拆开，核里面装的到底是不是我核过的那份 exe。"""
    if sys.platform != "win32":
        return SKIP, "NSIS 包只在 Windows 上打，mac / linux 这边没有包可拆"
    seven = find_7z()
    if seven is None:
        return SKIP, "没装 7-Zip（可用 PORTIO_7Z 指路径），拆不开安装包就没法核包里那份"
    exe, kind = find_app_exe(app_exe_dirs())
    pkg = versioned_bundle(current_version(), bundle_dirs(kind) + [ROOT])
    if pkg is None:
        return SKIP, f"还没构建 {current_version()} 的安装包，没得拆"
    workdir = Path(tempfile.mkdtemp(prefix="portio-payload-"))
    try:
        got, why = extract_payload(pkg, seven, workdir)
        built = exe.read_bytes() if exe is not None else None
        payload = got.read_bytes() if got is not None else None
        if payload is None:
            return FAIL, f"拆 {pkg.name} 时没拿到 portio-app.exe：{why}"
        status, detail = payload_verdict(built, payload)
        return status, f"{detail} ← {pkg.name}（{kind_label(kind)}）"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def split_ids(items: list[str]) -> list[str]:
    """把 `A10 A11` / `A10,A11` 拆成编号列表：大写、去空、去重、按出现顺序。

    以前想单跑一项只能整跑几十秒到两三分钟——`rc.py A11` 还会被 argparse
    当成不认识的参数直接报错，于是改一项、核一项这条最常用的动作反而最贵。
    """
    out: list[str] = []
    for raw in items or []:
        for piece in str(raw).replace("，", ",").split(","):
            code = piece.strip().upper()
            if code and code not in out:
                out.append(code)
    return out


def select_items(plan: list[tuple], wanted: list[str]) -> tuple[list[tuple], list[str]]:
    """按编号从计划表里挑出要跑的项。

    `wanted` 为空 = 全跑。返回（选中的项，按计划表原有顺序；不认识的编号，按用户写的顺序）。
    不认识的编号不许静悄悄地忽略——写错一个字母就「跑过了」比直接报错危险得多。
    """
    if not wanted:
        return list(plan), []
    known = {code for code, _, _ in plan}
    unknown = [code for code in wanted if code not in known]
    chosen = [item for item in plan if item[0] in wanted]
    return chosen, unknown


# ---------- 主流程 --------------------------------------------------------

def summarize(results: list[tuple[str, str, str, str]], elapsed: float) -> tuple[int, list[str]]:
    """把逐项结果收成「退出码 + 要打印的几行」。

    以前这里是「没有 FAIL 就退出 0」，于是整跑里那项**没跑**的（安装包还没打、
    截图清单还没出、缺 Chrome、`--fast` 跳了 A1）也跟着混进了绿。
    绿的意思是「核过了」，不是「没查到问题」——没核的既不能算过，也不能算失败，
    所以单列成「未验」，并且给一个自己的退出码（3），让脚本没法把它当全绿收下。

    失败优先于未验：有 FAIL 时先把「该怎么修」说清楚，未验的留到失败修完再说。
    """
    counts = {s: sum(1 for r in results if r[2] == s) for s in (PASS, FAIL, SKIP)}
    summary = (
        f"汇总：{counts[PASS]} 通过 / {counts[FAIL]} 失败 / {counts[SKIP]} 未验，"
        f"共 {len(results)} 项，{elapsed:.1f}s"
    )
    failed = [r[0] for r in results if r[2] == FAIL]
    pending = [r for r in results if r[2] == SKIP]
    if failed:
        lines = [summary, "失败项：" + "、".join(failed), "逐项照 docs/rc-checklist.md §1 的「通过判据」修。"]
        return EXIT_FAIL, lines
    if pending:
        lines = [summary, "未验项：" + "、".join(r[0] for r in pending) + "（没核过，不许当通过记）"]
        for code, _label, _status, detail in pending:
            why = (detail or "没说原因").strip()
            if len(why) > 72:
                why = why[:71] + "…"
            lines.append(f"  - {code}：{why}")
        lines.append("补验后整体才算绿：缺包先打包、缺图先 python scripts\\shots.py、只是改了前端就重跑全量。")
        return EXIT_PENDING, lines
    return EXIT_OK, [summary]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Portio 自动化回归（rc-checklist §1）")
    ap.add_argument("--fast", action="store_true", help="跳过 A1 的 cargo test")
    ap.add_argument("--list", action="store_true", help="只列出会跑的项")
    ap.add_argument("items", nargs="*", metavar="A<n>",
                    help="只跑这几项，如 A11 或 A10,A11；不写就全跑")
    args = ap.parse_args(argv)

    plan = [
        ("A1", "cargo test --workspace", not args.fast),
        ("A2", "node --check ui/app.js", True),
        ("A3", "check_design_tokens.py（无硬编码色值）", True),
        ("A4", "check_ui_scale.py（尺度走令牌）", True),
        ("A5", "check_versions.py（七处版本一致：清单三处 + 标题栏 + Cargo.lock 三个 crate）", True),
        ("A6", "默认页 title 无 ERR:", True),
        ("A7", "#split-test = SELFTEST-OK", True),
        ("A8", "#clip-test = CLIP-SELFTEST-OK 10", True),
        ("A9", "#fold-test = FOLD-SELFTEST-OK", True),
        ("A10", "portio-app.exe 子系统 = GUI（沿 CARGO_TARGET_DIR 找这一轮构建出来的那份）", True),
        ("A11", "NSIS 安装包体积与文件名（只认当前版本的 Portio_<版本>_x64-setup.exe，旧包不算）", True),
        ("A12", "#ctx-test = CTX-SELFTEST-OK 9（九处面板右键菜单）", True),
        ("A13", "#narrow-test 两档窄窗（1024 / 900）几何", True),
        ("A14", "#theme-test = THEME-SELFTEST-OK（深浅两套几何一致 + 令牌对比度）", True),
        ("A15", "#find-test = FIND-SELFTEST-OK（900 宽下查找：计数/坐标/环回/无命中/几何 + 800 行长 buffer、宽字符、emoji、组合字符、ANSI、居中、贴底 + 跨折行命中与硬换行不许拼）", True),
        ("A16", "#density-test = DENSITY-SELFTEST-OK（三档 24/28/32：九处行高严丝合缝等于 --row、相邻两档只差 4px、切档不横向错位）", True),
        ("A17", "#find-pane-test = FIND-PANE-SELFTEST-OK（分屏后查找只认当前格：计数/命中/选区/高亮跟着换格走）", True),
        ("A18", "#connect-entry-test = CONNECT-ENTRY-SELFTEST-OK（新建连接/快速连接回车/双击会话三条入口，外加\"新建连接从空白起\"与括号 IPv6 解析）", True),
        ("A19", "#sessions-test = SESSIONS-SELFTEST-OK（会话增删改/分组/折叠/搜索，以及磁盘上的 last_used 读回来还认不认\"最近用过\"）", True),
        ("A20", "#hosts-test = HOSTS-SELFTEST-OK（已知主机：列出/指纹截断/按端口删/删空后的空态）", True),
        ("A21", "#accent-test = ACCENT-SELFTEST-OK（强调色六套：主色与色片同源/按钮跟着走/深浅各一档/认不出的回默认/ANSI 语义色不被拐）", True),
        ("A22", "#term-theme-test = TERM-THEME-SELFTEST-OK（终端配色三套：成套换/跟界面主题解耦/真终端对象也换了/与强调色互不干扰）", True),
        ("A23", "#font-test = FONT-SELFTEST-OK（界面字号两档与终端字号互不带动/字号越界回落/等宽字体四选落到真终端且带 monospace 兜底/密度三档各差 4px）", True),
        ("A24", "#boot-test = BOOT-SELFTEST-OK（启动布局三档：记住上次/总是展开/总是收起，改设置不动眼前布局也不污染记忆态，模拟启动后两处面板真的收放）", True),
        ("A25", "#perm-test = PERM-SELFTEST-OK（文件面板权限列：关掉后整条轨道收走、名字列吃掉那 68px、右对齐两列与行高一点不动，认不出的值回「显示」且不回写）", True),
        ("A26", "#panes-test = PANES-SELFTEST-OK（终端开局格数：只管打开应用时第一个标签、改设置不动眼前、第二标签仍一格、认不出的值回单屏且不回写）", True),
        ("A27", "#layout-test = LAYOUT-SELFTEST-OK（面板宽度两层：拖拽落记忆层、用默认按三档落宽度且分栏回 50/50 抽屉回一行、记忆层一个字不改，认不出的值各回各的默认且不回写）", True),
        ("A28", "check_site.py（说明页每一项设置与每个档位都跟设置面板对上）", True),
        ("A29", "#transfer-test = TRANSFER-SELFTEST-OK（空态随第一行消失、计数跟实际行数、43% 与完成/排队文案、行不出抽屉）", True),
        ("A30", "#net-fail-test = NET-FAIL-SELFTEST-OK（后端出错也要有话说：列目录失败留话、传输失败落红条而不是永远排队、错因翻成人话）", True),
        ("A31", "发布截图是本版本那一套（docs/shots/manifest.json 的版本串与当前一致、十张图逐张对得上字节数）", True),
        ("A32", "cargo fmt --check + cargo clippy -D warnings（本地的绿要等于 CI 的绿）", True),
        ("A33", "portio-app.exe 真的起得来（拉起这份 exe 等窗口、核标题带 Portio、再确认没当场退出，用完收干净）", True),
        ("A34", "包里那份就是核的那份（拆开安装包、拿里面的 portio-app.exe 跟构建产物逐字节对，只放过打包器写的标记）", True),
    ]
    if args.list:
        for code, label, on in plan:
            print(f"{code:4} {'run ' if on else 'skip'} {label}")
        return 0

    wanted = split_ids(args.items)
    chosen, unknown = select_items(plan, wanted)
    if unknown:
        print(f"不认识的编号：{'、'.join(unknown)}（`--list` 里能看到所有能跑的项）")
        return 2
    plan = chosen

    node = find_node()
    chrome = find_chrome()
    profile = tempfile.mkdtemp(prefix="portio-rc-")

    # 版本号：把标题栏 span 读出来，报告头里直接用
    ver = ""
    m = re.search(r'<span class="ver"[^>]*>(.*?)</span>', (UI / "index.html").read_text(encoding="utf-8"))
    if m:
        ver = m.group(1).strip()

    print(f"Portio 自动化回归  v{ver}  ({ROOT})")
    if wanted:
        print(f"只跑 {len(plan)} 项：{'、'.join(code for code, _, _ in plan)}")
    print("-" * 72)

    results: list[tuple[str, str, str, str]] = []
    started = time.time()
    for code, label, on in plan:
        if not on:
            results.append((code, label, SKIP, "本轮用 --fast 跳过"))
            print(f"[{LABEL[SKIP]}] {code}  {label}  ← --fast")
            continue
        t0 = time.time()
        if code == "A1":
            status, detail = a1_cargo_test()
        elif code == "A2":
            status, detail = a2_node_syntax(node)
        elif code == "A3":
            status, detail = a_script("check_design_tokens.py", "无硬编码色值")
        elif code == "A4":
            status, detail = a_script("check_ui_scale.py", "尺度走令牌")
        elif code == "A5":
            status, detail = a_script("check_versions.py", "版本一致")
        elif code == "A6":
            status, detail = a_page(chrome, profile, "", "Portio")
        elif code == "A7":
            status, detail = a_page(chrome, profile, "#split-test", "SELFTEST-OK")
        elif code == "A8":
            status, detail = a_page(chrome, profile, "#clip-test", "CLIP-SELFTEST-OK 10")
        elif code == "A9":
            status, detail = a_page(chrome, profile, "#fold-test", "FOLD-SELFTEST-OK")
        elif code == "A10":
            status, detail = a10_pe_subsystem()
        elif code == "A11":
            status, detail = a11_bundle()
        elif code == "A12":
            status, detail = a_page(chrome, profile, "#ctx-test", "CTX-SELFTEST-OK 9")
        elif code == "A13":
            status, detail = a_narrow(chrome, profile)
        elif code == "A14":
            status, detail = a_page(chrome, profile, "#theme-test", "THEME-SELFTEST-OK")
        elif code == "A15":
            # 800 行素材 + 80 次跳转比别的探针吃虚拟时间，预算给到 20s
            status, detail = a_page(chrome, profile, "#find-test", "FIND-SELFTEST-OK", "900,620", 20000)
        elif code == "A16":
            status, detail = a_page(chrome, profile, "#density-test", "DENSITY-SELFTEST-OK")
        elif code == "A17":
            # 四格各写素材再来回切格，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#find-pane-test", "FIND-PANE-SELFTEST-OK", "1180,690", 8000)
        elif code == "A18":
            # 三条入口一条条点，再钉住"新建连接从空白起"，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#connect-entry-test", "CONNECT-ENTRY-SELFTEST-OK", "1180,690", 8000)
        elif code == "A19":
            # 会话增删改与分组要反复重画列表，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#sessions-test", "SESSIONS-SELFTEST-OK", "1180,690", 8000)
        elif code == "A20":
            # 已知主机面板连点三次删除再重建，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#hosts-test", "HOSTS-SELFTEST-OK", "1180,690", 8000)
        elif code == "A21":
            # 强调色六套轮着换、还要切深浅主题，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#accent-test", "ACCENT-SELFTEST-OK", "1180,690", 8000)
        elif code == "A22":
            # 终端配色三套轮着换、还要切主题并核真终端对象，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#term-theme-test", "TERM-THEME-SELFTEST-OK", "1180,690", 8000)
        elif code == "A23":
            # 字号 / 字体 / 密度三套设置轮着换、每处都要读真终端对象，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#font-test", "FONT-SELFTEST-OK", "1180,690", 8000)
        elif code == "A24":
            # 启动布局三档来回切、还要模拟两次启动（收放面板会改终端宽高、要重量格子），给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#boot-test", "BOOT-SELFTEST-OK", "1180,690", 8000)
        elif code == "A25":
            # 权限列开关要在同一条真行上量「关前 / 关后」的列宽与右缘，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#perm-test", "PERM-SELFTEST-OK", "1180,690", 8000)
        elif code == "A26":
            # 开局格数要连着建四个标签（其中一个是四格摊开）再全关掉，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#panes-test", "PANES-SELFTEST-OK", "1180,690", 8000)
        elif code == "A27":
            # 面板宽度要连着落三次尺寸（拖动 / 用默认 / 换回记住上次）再逐项读内联变量，给 9s 虚拟时间
            status, detail = a_page(chrome, profile, "#layout-test", "LAYOUT-SELFTEST-OK", "1180,690", 9000)
        elif code == "A28":
            # 纯 Python 对表，不开浏览器
            status, detail = a_script("check_site.py", "说明页与代码对表")
        elif code == "A29":
            # 塞三条演示传输（一条在跑、一条完成、一条排队），量空态是否消失与计数、文案、几何
            status, detail = a_page(chrome, profile, "#transfer-test", "TRANSFER-SELFTEST-OK", "1180,690", 8000)
        elif code == "A30":
            # 塞一个会抛错的后端替身，量列目录失败有没有话说、传输失败落不落红条、错因翻没翻成人话
            status, detail = a_page(chrome, profile, "#net-fail-test", "NET-FAIL-SELFTEST-OK", "1180,690", 8000)
        elif code == "A31":
            # 纯 Python 读清单对图，不开浏览器
            status, detail = a31_shots()
        elif code == "A32":
            # 跑 cargo fmt / clippy，跟 CI 那关同一个口径
            status, detail = a32_lints()
        elif code == "A33":
            # A33：把 exe 真拉起来看一眼，用完收掉
            status, detail = a33_launch()
        elif code == "A34":
            # 拆包对字节：不开浏览器、不安装、不写注册表
            status, detail = a34_payload()
        results.append((code, label, status, detail))
        print(f"[{LABEL[status]}] {code}  {label}  ({time.time() - t0:.1f}s)  {detail}")

    shutil.rmtree(profile, ignore_errors=True)

    code, lines = summarize(results, time.time() - started)
    print("-" * 72)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
