#!/usr/bin/env python3
"""一条命令跑完 Portio 的自动化回归项，逐项打印 PASS / FAIL / SKIP。

对应 docs/rc-checklist.md §1 的 A1–A21。以前这些步骤散在日志里，每轮都要手打一遍命令，
容易漏项也难对照；这里固定成一个入口，输出可以原样贴进清单的「回归记录」表。

用法：
    python scripts/rc.py              # 全跑（A1 最慢，其余十几秒）
    python scripts/rc.py --fast       # 跳过 A1 的 cargo test（只改前端时够用）
    python scripts/rc.py --list       # 只列出会跑哪些项

退出码：全部 PASS 或 SKIP 为 0；有任何一项 FAIL 为 1。
环境变量可覆盖探测结果：PORTIO_CHROME、PORTIO_NODE、PORTIO_CARGO。
"""

from __future__ import annotations

import argparse
import glob
import hashlib
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
APP_EXE = ROOT / "target" / "debug" / "portio-app.exe"
BUNDLE_DIR = ROOT / "target" / "debug" / "bundle" / "nsis"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


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


def a10_pe_subsystem() -> tuple[str, str]:
    if not APP_EXE.exists():
        return SKIP, "还没构建 target/debug/portio-app.exe（先 npm run build 或 tauri build）"
    with APP_EXE.open("rb") as f:
        head = f.read(0x400)
    if head[:2] != b"MZ":
        return FAIL, "不是有效的 PE 文件"
    e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
    if head[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return FAIL, "PE 签名缺失"
    subsystem = struct.unpack_from("<H", head, e_lfanew + 4 + 20 + 68)[0]
    if subsystem != 2:
        return FAIL, f"Subsystem={subsystem}，GUI 应为 2（否则启动会带控制台黑窗）"
    return PASS, "Subsystem=2（GUI，启动不带控制台）"


def a11_bundle() -> tuple[str, str]:
    if not BUNDLE_DIR.exists():
        return SKIP, "还没打过 NSIS 包"
    exes = sorted(BUNDLE_DIR.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not exes:
        return SKIP, "bundle/nsis 里没有 exe"
    newest = exes[0]
    size = newest.stat().st_size
    mib = size / 1024 / 1024
    if mib < 2 or mib > 30:
        return FAIL, f"{newest.name} 体积 {mib:.2f} MiB 不在 2–30 MiB 的合理区间"
    return PASS, f"{newest.name} {size} 字节（{mib:.2f} MiB）"


# ---------- 主流程 --------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Portio 自动化回归（rc-checklist §1）")
    ap.add_argument("--fast", action="store_true", help="跳过 A1 的 cargo test")
    ap.add_argument("--list", action="store_true", help="只列出会跑的项")
    args = ap.parse_args(argv)

    plan = [
        ("A1", "cargo test --workspace", not args.fast),
        ("A2", "node --check ui/app.js", True),
        ("A3", "check_design_tokens.py（无硬编码色值）", True),
        ("A4", "check_ui_scale.py（尺度走令牌）", True),
        ("A5", "check_versions.py（四处版本一致）", True),
        ("A6", "默认页 title 无 ERR:", True),
        ("A7", "#split-test = SELFTEST-OK", True),
        ("A8", "#clip-test = CLIP-SELFTEST-OK 10", True),
        ("A9", "#fold-test = FOLD-SELFTEST-OK", True),
        ("A10", "portio-app.exe 子系统 = GUI", True),
        ("A11", "NSIS 安装包体积与文件名", True),
        ("A12", "#ctx-test = CTX-SELFTEST-OK 9（九处面板右键菜单）", True),
        ("A13", "#narrow-test 两档窄窗（1024 / 900）几何", True),
        ("A14", "#theme-test = THEME-SELFTEST-OK（深浅两套几何一致 + 令牌对比度）", True),
        ("A15", "#find-test = FIND-SELFTEST-OK（900 宽下查找：计数/坐标/环回/无命中/几何 + 800 行长 buffer、宽字符、emoji、组合字符、ANSI、居中、贴底）", True),
        ("A16", "#density-test = DENSITY-SELFTEST-OK（标准/紧凑两档：九处行高严丝合缝等于 --row、两档只差 4px、切档不横向错位）", True),
        ("A17", "#find-pane-test = FIND-PANE-SELFTEST-OK（分屏后查找只认当前格：计数/命中/选区/高亮跟着换格走）", True),
        ("A18", "#connect-entry-test = CONNECT-ENTRY-SELFTEST-OK（新建连接/快速连接回车/双击会话三条入口，外加\"新建连接从空白起\"与括号 IPv6 解析）", True),
        ("A19", "#sessions-test = SESSIONS-SELFTEST-OK（会话增删改/分组/折叠/搜索，以及磁盘上的 last_used 读回来还认不认\"最近用过\"）", True),
        ("A20", "#hosts-test = HOSTS-SELFTEST-OK（已知主机：列出/指纹截断/按端口删/删空后的空态）", True),
        ("A21", "#accent-test = ACCENT-SELFTEST-OK（强调色六套：主色与色片同源/按钮跟着走/深浅各一档/认不出的回默认/ANSI 语义色不被拐）", True),
    ]
    if args.list:
        for code, label, on in plan:
            print(f"{code:4} {'run ' if on else 'skip'} {label}")
        return 0

    node = find_node()
    chrome = find_chrome()
    profile = tempfile.mkdtemp(prefix="portio-rc-")

    # 版本号：把标题栏 span 读出来，报告头里直接用
    ver = ""
    m = re.search(r'<span class="ver"[^>]*>(.*?)</span>', (UI / "index.html").read_text(encoding="utf-8"))
    if m:
        ver = m.group(1).strip()

    print(f"Portio 自动化回归  v{ver}  ({ROOT})")
    print("-" * 72)

    results: list[tuple[str, str, str, str]] = []
    started = time.time()
    for code, label, on in plan:
        if not on:
            results.append((code, label, SKIP, "本轮用 --fast 跳过"))
            print(f"[SKIP] {code}  {label}  ← --fast")
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
        else:
            # 强调色六套轮着换、还要切深浅主题，给 8s 虚拟时间
            status, detail = a_page(chrome, profile, "#accent-test", "ACCENT-SELFTEST-OK", "1180,690", 8000)
        results.append((code, label, status, detail))
        print(f"[{status}] {code}  {label}  ({time.time() - t0:.1f}s)  {detail}")

    shutil.rmtree(profile, ignore_errors=True)

    counts = {s: sum(1 for r in results if r[2] == s) for s in (PASS, FAIL, SKIP)}
    elapsed = time.time() - started
    print("-" * 72)
    print(f"汇总：{counts[PASS]} 通过 / {counts[FAIL]} 失败 / {counts[SKIP]} 跳过，共 {len(results)} 项，{elapsed:.1f}s")
    if counts[FAIL]:
        print("失败项：" + "、".join(r[0] for r in results if r[2] == FAIL))
        print("逐项照 docs/rc-checklist.md §1 的「通过判据」修。")
        return 1
    if counts[SKIP] and ver:
        print("有跳过项时，回归记录里要写清跳过原因，别写成通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
