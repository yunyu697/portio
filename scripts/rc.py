#!/usr/bin/env python3
"""一条命令跑完 Portio 的自动化回归项，逐项打印 PASS / FAIL / 未验。

对应 docs/rc-checklist.md §1 的 A1–A49。以前这些步骤散在日志里，每轮都要手打一遍命令，
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
**CI 里跑的那一步，本地整跑也得跑**：A35 跑 `scripts/test_*.py` 这一批（CI 的 ci.yml 就是拿
`python -m unittest discover -s scripts` 跑的）。以前整跑 A1–A34 一条都没跑过它们：
改完 `rc.py` 忘了跑对应的 `test_rc_*.py`，本地照样全绿、推上去 CI 才红。
**窗口在，不等于界面画出来了**：A36 走 WebView2 自己的调试口进真 webview 读 DOM——
标题栏里的版本串是不是这一版、`app.js` 顶部那个函数在不在、终端对象建没建、DOM 有没有肉。
A33 只核「进程没退 + 标题带 Portio」，而那个标题是配置文件里写死的，
界面一根筋没加载也照样成立。
**自检只在无头里跑过，等于没在真窗口里跑过**：A37 把其中不动设置的那几条搬进真 webview 跑一遍
（真 localStorage、真后端）。跑前先把 localStorage 存下来，跑完一字不差写回去——
实测这些自检会把 `portio.drawer` 从 2 改成 3，那是我自己的偏好，不该被回归挪动。
**要改设置的那批，靠「跑完写回」不如靠「别碰我的」**：A38 只给子进程一份一次性 WebView2 profile
（进程级环境变量），那批要改主题 / 字号 / 密度 / 强调色 / 终端配色 / 启动布局 / 权限列 / 开局格数 /
面板宽度 的九条都在里面跑；跑完连目录一起删，再核我自己的偏好库文件数 / 字节 / 时间戳一个没变。
会话与已知主机两条不搬——它们在真后端上起手就把会话清单清空。
**后端那两份文件换不了目录，那就「先存字节、跑完收回、再读一遍核对」**：A39 把最后两条
（`#sessions-test` / `#hosts-test`）也搬进真窗口。给子进程换 `APPDATA` 没用——Tauri 取的是
Known Folder API，不认进程环境变量（实测新目录里什么都没长出来，真目录照样被改写），
所以只能：跑前把 `theme.txt` / `sessions.json` / `known_hosts` 按字节存下 → 跑 → 收进程 →
按原字节写回（原本没有的那份收走）→ 再读一遍逐字节核对。同时还得证明确实写了：
跑完 `sessions.json` 没冒出来、没变化，说明这两条根本没走真后端，那还是「没核」。
**窄窗那条得真能在真窗口里变窄，而视口命令是会话级的**：A40 用调试口的
`Emulation.setDeviceMetricsOverride` 把布局视口换成 1024 / 900 两档再跑 `#narrow-test`——
这条命令一断连接就失效（`cdp_call` 每次都是新会话），所以两档得在一根长连的会话里跑完。
判据拿界面自报的 innerWidth 跟要求的对：对不上就是拿一档宽窗冒充窄窗，自检再绿也不算核过。
**最后两条自检搬进真窗口，还得证明不是在一份空偏好里跑的**：A41 跑 `#net-fail-test` 与
`#connect-entry-test`（后者起手会把内存里的会话清单清空），沿用 A39 的存 / 收 / 核，
另加一层 A39 没有的：页面里真有 Tauri 桥、localStorage 里真有我的偏好、界面底色跟真 app-data 的
`theme.txt` 对得上、后端真回了一次 `sessions_read`。否则这两条在一份一次性 profile 里跑得再绿，
也跟我的会话清单一句话都没说上。
**读坏了不许当空清单用**：A42 钉住 `#broken-store-test`——`sessions.json` 半截写入 / 版本比程序新 /
合法 JSON 但不是一份清单，这几种「读不懂」都得先让后端把原文件另存成 `sessions.json.broken-<毫秒>`，
再让界面从空清单起步。不然用户随后随手存一条会话，`sessions_write` 就把整份盖掉，原来那些记录
再也找不回来。反向验证两处：去掉另存那一步、把写盘口子改回只认真桥，都各自翻红。
**可 A42 的后端是自检自己扮的**：A42 跑在无头页里、后端是 `fakeInvoke` 替身，`salvage_broken`
真去 `fs::copy` 一次这件事一条真路径都没走过——1.0.9-RC8 我亲手换过一截坏 JSON 验过一次，
那是一把一次性手活，不进每轮。A43 把那次手活写成门禁：把真 app-data 的 `sessions.json` 先按字节存下、
种一截「断电写到一半」的 JSON、拉起 release 那份 exe，核真后端有没有另存出 `.broken-<毫秒>`、
副本跟种下去的一字不差、种下去那份有没有被反手写成空清单，再拿「还没有这份清单」跑一趟对照
（好档一个副本都不许冒），跑完按原字节收回、独立复量。
**那四份一次性 profile 以前是「删不掉也别吭声」**：A38–A43 每个探针都 mkdtemp 一份 WebView2
profile，收尾一句 `shutil.rmtree(prof, ignore_errors=True)`——库文件还占着的那一份就留在盘上，
日志里一个字不提。2026-11 那轮 C 盘被顶到 0 字节，翻出来是我自己攒下的 113 个 `portio-*`
目录、1.3 GB。A44 钉住四件事：建之前先核目标盘余量（不够就拦、并说清差多少）、建了就登记、
收的时候重试几次（真删不掉判 False 并点名、整跑按失败算）、跑前只清**自己前缀且够旧的**残留
（刚建那份可能是另一个 rc.py 正在用的，别人的目录与同名文件一律不碰）。
**可我把「这一版改了什么」写走形了**：GitHub Release 的正文只有一句「这一版改了什么，看仓库里的
CHANGELOG.md」，所以那一段就是用户读到的东西。1.0.10-RC1 那一节被写成「每一行之间夹一个空行、
续行再缩进两格」——渲染出来是七截互不相连的碎段，一个条目读成七个段落，而且没人看得出来是排版坏了。
A45 钉住六件事：`## [Unreleased]` 排在最前；每个版本标题都带 `YYYY-MM-DD`、版本串能解析；
**当前版本必须有自己那一节、排在最前、且不是空的**（先写更新内容再打包）；当前那节里不许连着两个空行、
不许空行后面跟缩进续行、行尾不许留空白；每节都得有白名单里的 `### ` 子标题。
历史小节只查「有没有子标题」这类硬伤，不重排 —— 已经发出去的十几段没有回头改的必要。
**可排版整齐不等于话是真的**：A45 只管形状，我完全能把一句「我把 X 修了」写得漂漂亮亮，而这一版的
代码里压根没动过 X —— 读的人看不出，我自己事后也看不出。A46 补这一半，六条判据：点到的仓库路径得真
在仓库里（写成 `check_sites.py` 那种笔误，读的人点开是空）；写了「改 / 修 / 加了某个代码文件」时那个
文件得真在这一版的改动集里；提到门禁编号时 `rc.py` 计划表里得真有这一项；反过来这一版新冒出来的
编号必须写进更新内容（加了道闸不吭声，读的人不知道）；这一版新增的脚本（单测除外）要点名，或它上场的
那道门禁被点名；计划表里写「会跑」的，分发处就得有对应分支。
「这一版」取「版本号严格小于当前版本的那个最大的 `v*` tag」到工作区（含未提交改动），所以提交前、
提交后、打完 tag 再跑都对得上；本地没有更早的 tag（浅克隆）报未验，不拿「没查到问题」冒充「核过了」。
**可要是盘上那份产物本身就是空壳呢**：2026-11-21 A1 报 `E0463: can't find crate for portio_ssh`，
代码一个字没坏——上一轮 rustc 的 LLVM 被内存顶崩时在 `deps` 里留下一个 0 字节的 `.rmeta`，
而 `.fingerprint` 里那格的 `invoked.timestamp` 还在，cargo 认为「编过了」，于是永远不重编。
它长得像代码问题，其实是产物问题，比一次 OOM 难查得多。A47 排在 A1 **前面**（顺序有意为之：
排在编译之后就没用了），三条判据：`deps` 里 0 字节的 `.rmeta` / `.rlib` / `.o`；其中指纹还挂着的那几份
判红并给出 `cargo clean -p <包>`；还挂着超过一小时的 rustc（被打断没退干净的孤儿，白占提交额度）。
一个 target 目录都没有时报未验。
**可「核的和交的是同一份」这句话，之前只活在我自己抄的日志里**：RC4 那次我写「本地交付的就是
Release 上那份，3384941 B、sha256 ff080346 开头」，没有一个字是机械核过的。换一版那天，
盘上那份到底是什么、包体内写的是哪个版本，谁也说不清——**一份 RC3 的包改个文件名，字节与大小
全对得上，装出来还是 RC3**。A48 把这条变成门禁：`docs/artifacts.json` 里记这一版交付出去的那一份
（来源、tag、文件名、字节、sha256），三条判据——记录自己得自洽（同版同平台一条、不许记将来的版本、
说 CI 就得写清 tag 且与版本一致、文件名里得带版本串）；盘上那份字节与 sha256 都得对上；Windows exe
PE 版本资源里那个串（FileVersion / ProductVersion）得是当前版本（文件名与字节都改得动，包体内
这个串改不动）。记录没有、或者那份包不在盘上报未验（交付文件在仓库外，换台机器就找不着）。
**后来又补了一格（RC6）：记录里那个 tag 到底指的哪次提交。** 光写一个 tag 名，等于我又抄了一句
「这份包是从 v1.0.10-RC6 编出来的」——tag 打到了哪次提交、那次提交里版本写着什么，都得去问仓库：
tag 得真在；它指向的那次提交里根 `Cargo.toml` 的版本必须等于记录写的版本（不是附注标签、或者那次提交
不在 HEAD 线上只留 NOTE）；git 用不了就报未验，不报绿。
**又补一格（RC8）：Release 资产大小。** 记录以前只钉 Windows 那一份，dmg / deb / AppImage 不在本机
盘上，字节与 sha256 没法逐字节核；退一步拿 `gh release view --json assets` 对大小——记录里那个文件名
得真挂在这一版 tag 的 Release 上、大小一字不差。平台白名单四条；gh 用不了这一组报未验，不报绿。
**再往下一格（RC7）：成绩单。** 每一轮整跑最后那行「34 通过 / 0 失败 / 12 未验，124.8s，退出码 3」以前
只活在屏幕上，抄进 `docs/rc-checklist.md` 首部的那一串是我一个字一个字打进去的——打错一个数字，
读的人没有任何办法发现；下一轮再打一遍，错的就被对的盖过来。现在 `--record` 会让这一跑自己落一份
`docs/rc-last-run.json`（逐项状态 / 耗时 / 理由，汇总是从逐项数出来的），A49 拿它去对清单首部：
纸面自洽、版本只许当前这一版或紧挨着的上一版（不许记将来、也不许攒旧）、编号真在计划表且不重复、
首部那串数字与成绩单一字不差、未验的每一条都在首部点到名。
环境变量可覆盖探测结果：PORTIO_CHROME、PORTIO_NODE、PORTIO_CARGO、PORTIO_7Z、PORTIO_GIT。
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime
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

# A1 第一次没跑成，可能压根不是代码的事：rustc 的 LLVM 会直接报 `out of memory` /
# `页面文件太小，无法完成操作 (os error 1455)`——这台机器 C 盘只剩 0.2 GB、页面文件长不大，
# 提交量顶到上限时多路并行编译就编不动。这既不能当代码坏了，也不能就此放过：
# 记下证据、降并行度重跑；降下来还挂，或者报的是别的原因，那才判红。
RESOURCE_SPOTS = ("out of memory", "页面文件太小", "os error 1455",
                  "cannot allocate memory", "STATUS_STACK_BUFFER_OVERRUN")
A1_RETRY_JOBS = (2, 1)
# 2026-11-21 实测：整跑里 A1 撞红（rustc 退出码 0xc0000409），同一份代码趁机器空下来 `-j 1`
# 单跑 0 退出。差别就是重跑时机器还没缓过来——所以降并行度之前先歇一会儿，别一格接一格地撞。
A1_RETRY_SLEEP = 15


def resource_bad(out: str) -> bool:
    """这段输出像不像「机器扛不住」而不是「代码不对」。"""
    low = (out or "").lower()
    return any(s.lower() in low for s in RESOURCE_SPOTS)


def resource_reason(out: str) -> str:
    """把到底是哪种资源不足写成一句话，别让人以为是自己改坏了。"""
    text = out or ""
    low = text.lower()
    if "out of memory" in low:
        return "rustc 的 LLVM 报 out of memory（这台机器提交量顶到上限了）"
    if "os error 1455" in low or "页面文件太小" in text:
        return "页面文件太小（os error 1455，C 盘没地方让它再长）"
    return "编译时资源不足"


def a1_cargo_test() -> tuple[str, str]:
    cargo = find_cargo()
    if not cargo:
        return SKIP, "找不到 cargo（设 PORTIO_CARGO 或用 --fast 跳过）"
    env = with_path(str(Path(cargo).parent))
    note = ""
    proc = run([cargo, "test", "--workspace"], timeout=1200, env=env)
    for jobs in A1_RETRY_JOBS:
        if proc.returncode == 0 or not resource_bad(proc.stdout + proc.stderr):
            # 过了，或者报的是代码问题：后一种绝不拿「降并行度重跑」糊过去
            break
        note = f"第一次是机器扛不住（{resource_reason(proc.stdout + proc.stderr)}），歇 {A1_RETRY_SLEEP}s 再降到 {jobs} 路重跑"
        time.sleep(A1_RETRY_SLEEP)
        proc = run([cargo, "test", "--workspace", "-j", str(jobs)], timeout=1200, env=env)
    passed = failed = 0
    for m in re.finditer(r"test result: \w+\. (\d+) passed; (\d+) failed", proc.stdout):
        passed += int(m.group(1))
        failed += int(m.group(2))
    if proc.returncode != 0 or failed:
        return FAIL, f"returncode={proc.returncode}, failed={failed}; {tail(proc.stdout + proc.stderr, 8)}"
    if not passed:
        return FAIL, "没有解析到测试结果，可能编译就没过"
    # 各 crate 的分布不进摘要行，太长；失败时要看全文就回滚到手动跑
    return PASS, f"{passed} passed, {failed} failed" + (f"；{note}" if note else "")


def a2_node_syntax(node: str | None) -> tuple[str, str]:
    if not node:
        return SKIP, "找不到 node（设 PORTIO_NODE）"
    proc = run([node, "--check", "ui/app.js"], timeout=120)
    if proc.returncode != 0:
        return FAIL, tail(proc.stderr)
    return PASS, "ui/app.js 语法通过"


def a_script(script: str, label: str, skip_exit: int | None = None) -> tuple[str, str]:
    """跑一个只读脚本。skip_exit 是「这一条这一轮没得核」时脚本自己的退出码（A46 用它报未验）。"""
    path = ROOT / "scripts" / script
    if not path.exists():
        return SKIP, f"脚本不存在：scripts/{script}"
    proc = run([sys.executable, str(path)], timeout=180)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        if skip_exit is not None and proc.returncode == skip_exit:
            # 没得核 ≠ 核过了：按未验算，整跑退出码也就不是 0
            return SKIP, (out.splitlines()[-1] if out else label) or label
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


# ---------- 一次性 profile：自己建、自己删、删不掉要说出来 -------------------
#
# A38–A43 每个探针都 mkdtemp 一份 WebView2 profile，收尾一句
# `rmtree(..., ignore_errors=True)`。ignore_errors 的字面意思就是「删不掉也别吭声」：
# 库文件还没松手、目录被占住，那一份就留在盘上，日志里一个字都不会提。
# 2026-11 那轮 C 盘被顶到 0 字节，翻出来是 %LOCALAPPDATA%\Temp 里攒了我自己留下的
# 113 个 `portio-*` 目录、1.3 GB——每跑一轮多一份，全靠这句静默。
# 于是四件事：① 建之前先看目标盘还剩多少，不够就别开跑，并说清差多少；
# ② 建出来登记在册；③ 收的时候重试几次，真删不掉就点名报出来、算「本轮有残留」；
# ④ 跑前把上一轮留下的清掉——只认自己的前缀，只认够旧的。
PROFILE_PREFIXES = ("portio-fresh-", "portio-appdata-", "portio-narrow-",
                    "portio-rc-", "portio-payload-")
# 一份新 profile 首启就要写几十上百兆；快没地方时开跑只是把盘顶穿，不如先停下来说清楚
PROFILE_FLOOR_MB = 150
PROFILE_RELEASE_TRIES = 10
PROFILE_RELEASE_SLEEP = 0.5
# 够旧才清：另一个 rc.py 可能正拿着它手上的 profile 在跑，按前缀无差别清把人家的删了更糟
PROFILE_STALE_HOURS = 6
CREATED_PROFILES: list[Path] = []
LEAKED_PROFILES: list[Path] = []


def temp_root() -> Path:
    """本轮的临时目录根（跟着 TEMP 走；本机把它指到 D 盘）。"""
    return Path(tempfile.gettempdir())


def free_space_mb(path: Path) -> float:
    """目标盘还剩多少 MB；量不到给 inf——不拦人，但也不因此把「没核」说成「核过」。"""
    try:
        return shutil.disk_usage(str(path)).free / (1024 * 1024)
    except OSError:
        return float("inf")


class TempSpaceShort(Exception):
    """目标盘不够跑一份一次性 profile。"""


def require_temp_space(root: Path, need_mb: float = PROFILE_FLOOR_MB,
                       free=free_space_mb) -> None:
    """开跑前核一眼盘：不够就抛，话里带上还差多少。"""
    got = free(root)
    if got < need_mb:
        raise TempSpaceShort(
            f"{root} 只剩 {got:.0f} MB，跑一份一次性 profile 至少要 {need_mb:.0f} MB"
            f"（差 {need_mb - got:.0f} MB）——先清点临时目录再开跑，"
            "别让回归把盘写满：1.0.9 那轮 C 盘被顶到 0 字节走的就是这条路")


def profile_bytes(path: Path) -> int:
    """这份 profile 占多大（删之前量一次，好说清放回多少）。"""
    total = 0
    for p in Path(path).rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def profile_dirs(root: Path | None = None, prefixes: tuple[str, ...] = PROFILE_PREFIXES,
                 now: float | None = None,
                 stale_hours: float | None = PROFILE_STALE_HOURS) -> list[Path]:
    """临时目录里「我自己的」那几类 profile 目录。

    只认前缀、且只认目录：别人的临时目录一个都不碰，同名文件也不动
    （这个函数只负责认，删不删是 sweep 的事）。
    stale_hours 给 None 就返回所有岁数的（收尾盘点用）。
    """
    root = Path(root) if root is not None else temp_root()
    now = time.time() if now is None else now
    out: list[Path] = []
    try:
        entries = list(Path(root).iterdir())
    except OSError:
        return out
    for p in entries:
        if not p.is_dir() or not p.name.startswith(prefixes):
            continue
        if stale_hours is None:
            out.append(p)
            continue
        try:
            age_h = (now - p.stat().st_mtime) / 3600
        except OSError:
            continue
        if age_h >= stale_hours:
            out.append(p)
    return out


def make_profile(prefix: str, root: Path | None = None,
                 need_mb: float = PROFILE_FLOOR_MB, mkdtemp=tempfile.mkdtemp,
                 free=free_space_mb) -> Path:
    """建一份一次性 profile：盘不够就不建，建了就登记，收尾才有据可查。"""
    root = Path(root) if root is not None else temp_root()
    require_temp_space(root, need_mb, free)
    path = Path(mkdtemp(prefix=prefix, dir=str(root)))
    CREATED_PROFILES.append(path)
    return path


def release_profile(path: Path, rmtree=shutil.rmtree, sleep=time.sleep,
                    tries: int = PROFILE_RELEASE_TRIES) -> bool:
    """删一份一次性 profile：重试几次，真删不掉就点名登记。

    返回 False 不是「小事」——它是本轮往盘上留了东西这件事唯一的痕迹，
    所以每处调用都拿它算进 LEAKED_PROFILES，摘要里单独说一行。
    """
    p = Path(path)
    for _ in range(max(1, tries)):
        if not p.exists():
            return True
        try:
            rmtree(p, ignore_errors=False)
        except OSError:
            pass
        if not p.exists():
            return True
        sleep(PROFILE_RELEASE_SLEEP)
    if p not in LEAKED_PROFILES:
        LEAKED_PROFILES.append(p)
    print(f"  ! 删不掉这份临时 profile，已登记：{p}（{profile_bytes(p) // 1024} KB 留在盘上）")
    return False


def sweep_stale_profiles(root: Path | None = None, now: float | None = None,
                         prefixes: tuple[str, ...] = PROFILE_PREFIXES,
                         stale_hours: float = PROFILE_STALE_HOURS,
                         release=release_profile) -> tuple[int, int]:
    """跑前把上一轮留下的 profile 清掉，返回（清掉几个 / 放回多少字节）。"""
    root = Path(root) if root is not None else temp_root()
    count = freed = 0
    for p in profile_dirs(root, prefixes, now, stale_hours):
        size = profile_bytes(p)
        if release(p, sleep=lambda _s: None):
            count += 1
            freed += size
    return count, freed


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
    try:
        workdir = make_profile("portio-payload-")
    except TempSpaceShort as e:
        # 盘不够是「没核」，不是「核过」：不许拿它当通过
        return SKIP, f"临时目录不够拆包：{e}"
    try:
        got, why = extract_payload(pkg, seven, workdir)
        built = exe.read_bytes() if exe is not None else None
        payload = got.read_bytes() if got is not None else None
        if payload is None:
            return FAIL, f"拆 {pkg.name} 时没拿到 portio-app.exe：{why}"
        status, detail = payload_verdict(built, payload)
        return status, f"{detail} ← {pkg.name}（{kind_label(kind)}）"
    finally:
        release_profile(workdir)


# ---------- A35：CI 里跑的那一步，整跑也得跑 -------------------------------

RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.M)
SKIP_RE = re.compile(r"^OK \(skipped=(\d+)\)", re.M)
SCRIPT_TESTS_TIMEOUT = 600


def script_test_verdict(code: int, out: str) -> tuple[str, str]:
    """把「跑完 scripts 那批单测」的成败翻成一句结论（纯函数，好测）。

    这一批是回归脚本自己的测试：`test_rc_*.py` 核的是「A34 有没有真的接进计划表」
    「编号写错会不会装作跑过」这类事。CI 在 ci.yml 里拿
    `python -m unittest discover -s scripts -p "test_*.py"` 跑它，
    可本地整跑 A1–A34 一条都没跑过——改完 `rc.py` 忘了跑对应的单测，
    整跑照样全绿，推上去 CI 才红，正好和「本地的绿要等于 CI 的绿」相反。

    判定上不留「没查到问题就算过」的口子：`Ran 0 tests` 或压根没解析到条数，
    都当红——那说明 discover 一条都没找到，等于没跑。
    """
    text = out or ""
    if code != 0:
        return FAIL, f"退出码 {code}；{tail(text, 6)}"
    if not re.search(r"^OK", text, re.M):
        return FAIL, f"没看到 OK 收尾（可能崩在半路）：{tail(text, 6)}"
    m = RAN_RE.search(text)
    if not m:
        return FAIL, "没解析到「Ran N tests」——discover 可能一条都没找到，等于没跑"
    ran = int(m.group(1))
    if ran == 0:
        return FAIL, "discover 一条都没跑到（scripts 下没有 test_*.py？），等于没跑"
    s = SKIP_RE.search(text)
    skipped = int(s.group(1)) if s else 0
    detail = f"{ran} 条通过"
    if skipped:
        detail += f"（按平台跳 {skipped} 条，清单里算未验的那几条）"
    return PASS, detail


def a35_script_tests() -> tuple[str, str]:
    """跑 scripts/test_*.py 这一批，跟 CI ci.yml 里的 discover 同一个口径。"""
    if not sorted((ROOT / "scripts").glob("test_*.py")):
        return FAIL, "scripts 下面一个 test_*.py 都没有——回归脚本自己没测试，等于没核"
    proc = run([sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"],
               SCRIPT_TESTS_TIMEOUT)
    return script_test_verdict(proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


# ---------- A36：窗口标题是 Portio，不代表界面画出来了 ---------------------

# A33 核的是「进程没退 + 有个标题带 Portio 的窗口」。可那个标题是 tauri.conf.json
# 里写死的，窗口一开就挂着——界面里到底加载出东西没有，标题一个字都不说。
# 真加载失败的样子是：WebView2 起不来、资源路径错、app.js 语法炸，窗口照样在、标题照样对。
# 这里走 WebView2 自己的调试口（CDP）：等它从 about:blank 导航到 tauri.localhost，
# 再进真 webview 读 DOM——标题栏里的版本串、app.js 顶上那个函数、终端对象在不在。
WEBVIEW_WAIT = 20.0        # 等它从 about:blank 导航到界面，最多多少秒
WEBVIEW_READY_WAIT = 10.0  # 导航到了之后，等它把 DOM 解析完（readyState=complete）最多多少秒
WEBVIEW_MIN_DOM = 20000    # 真界面渲染出来 DOM 有九万多字节；只剩一副骨架到不了两万
WEBVIEW_EXPR = (
    "JSON.stringify({"
    "title:document.title,"
    "ver:(document.querySelector('.ver')||{}).textContent,"
    "bodyLen:(document.body?document.body.innerHTML.length:0),"
    "ready:document.readyState,"
    "tabs:document.querySelectorAll('.tab').length,"
    "hasScan:typeof window.findScan,"
    "xterm:document.querySelectorAll('.xterm').length"
    "})"
)


def free_port() -> int:
    """从系统要一个空端口给调试口用——写死端口会被别的进程占掉，整项就误红了。"""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def cdp_targets(port: int, timeout: float = 1.0) -> list[dict]:
    """调试口的页面列表（还没开就是这个样子：拿不到）。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - 口没开 / 还没起来，都走这条路
        return []


def ws_open(ws_url: str, timeout: float = 8.0):
    """最小 WebSocket 握手：只为了往里发一句 Runtime.evaluate，不为它引依赖。

    http 那层的 `/json/list` 只给标题与 URL，读不到 DOM；要读 DOM 只能连
    `webSocketDebuggerUrl`。这里只用一条文本帧，手写握手比装个库更省。
    """
    host_port, path = ws_url.split("//", 1)[1].split("/", 1)
    host, port = host_port.split(":")
    sock = socket.create_connection((host, int(port)), timeout=timeout)
    key = base64.b64encode(uuid.uuid4().bytes).decode()
    sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\n"
                  f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                  f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("调试口握手中途断开")
        head += chunk
    first = head.split(b"\r\n")[0].decode("utf-8", "replace")
    if "101" not in first:
        raise RuntimeError(f"调试口不认升级：{first}")
    return sock


def ws_send_text(sock, payload: bytes) -> None:
    """发一条带掩码的文本帧（客户端帧必须掩码，否则调试口直接断）。"""
    head = bytearray([0x81])
    n = len(payload)
    if n < 126:
        head.append(0x80 | n)
    elif n < 65536:
        head.append(0x80 | 126)
        head += struct.pack(">H", n)
    else:
        head.append(0x80 | 127)
        head += struct.pack(">Q", n)
    mask = os.urandom(4)
    head += mask
    sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def ws_recv_frame(sock) -> tuple[bool, bytes]:
    """读一帧，回 (是不是末帧, 内容)。分片就把内容拼起来由调用方判断。"""
    b = sock.recv(2)
    if len(b) < 2:
        raise RuntimeError("调试口把连接关掉了")
    fin = bool(b[0] & 0x80)
    n = b[1] & 0x7F
    if n == 126:
        n = struct.unpack(">H", sock.recv(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", sock.recv(8))[0]
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise RuntimeError("调试口把连接关掉了")
        buf += chunk
    return fin, buf


def cdp_eval(ws_url: str, expr: str, timeout: float = 8.0) -> dict:
    """在真 webview 里跑一句话，回它那一帧（成没成由调用方判）。"""
    return cdp_call(ws_url, "Runtime.evaluate",
                    {"expression": expr, "returnByValue": True}, timeout)


def webview_verdict(sig: dict | None, version: str, waited: float,
                    why: str = "") -> tuple[str, str]:
    """把真 webview 里读回来的几个信号逐条判（纯函数，好测）。

    顺序是有意的：先问「进到界面没有」，再问「界面是不是加载完了」，
    然后才是「加载出来的东西对不对」。每一档都点名差在哪，
    免得「窗口在」被读成「界面好」。
    """
    if sig is None:
        return FAIL, (f"{waited:.0f}s 内没进到界面（{why or '调试口没给出页面'}）"
                      "——窗口在也不等于界面画出来了")
    exc = sig.get("exception")
    if exc:
        return FAIL, f"界面里那句探针自己炸了：{tail(str(exc), 2)}"
    ready = str(sig.get("ready") or "")
    if ready != "complete":
        return FAIL, f"界面没加载完（readyState={ready or '空'}）——还在解析或者卡在资源上"
    title = str(sig.get("title") or "")
    if "ERR:" in title:
        return FAIL, f"窗口标题成了 {title!r}——前端一进去就炸了"
    ver = str(sig.get("ver") or "").strip()
    if not ver:
        return FAIL, "界面里压根没找到标题栏那个版本串（span.ver 空着）——DOM 不是这一份"
    if version and ver != version:
        # 不是这一版构建出来的 exe：界面在真 webview 里对不对，这轮压根没核到。
        # 按 RC6 的口径，这种要报「未验」，不能算红也不能算绿——
        # 红的意思是这个功能坏了，而这里只是「我手上这份不是本版」。
        return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                      "界面在真 webview 里对不对这轮没核到（先 npm run build 再来）")
    if sig.get("hasScan") != "function":
        return FAIL, (f"app.js 没跑完（window.findScan 是 {sig.get('hasScan')!r}）"
                      "——语法错或中途抛了东西")
    if int(sig.get("xterm") or 0) < 1:
        return FAIL, "界面里一个终端对象都没有（xterm 没初始化）"
    if int(sig.get("bodyLen") or 0) < WEBVIEW_MIN_DOM:
        return FAIL, (f"界面 DOM 只有 {sig.get('bodyLen')} 字节（少于 {WEBVIEW_MIN_DOM}）"
                      "——像只剩一副骨架")
    return PASS, (f"界面已加载：标题 {title!r}、版本 {ver}、DOM {sig.get('bodyLen')} 字节、"
                  f"{sig.get('tabs')} 个标签、xterm {sig.get('xterm')} 个")


def probe_webview(exe: Path, version: str, wait: float = WEBVIEW_WAIT, port: int | None = None,
                  popen=subprocess.Popen, kill=kill_tree) -> tuple[str, str]:
    """把 exe 拉起来、等 webview 导航到界面、进它肚子里读 DOM、再收干净。"""
    port = port or free_port()
    env = dict(os.environ)
    # 只给这一个子进程开调试口（进程级环境变量，不改机器上的任何设置）
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        page = None
        seen: list[str] = []
        while time.time() - started < wait:
            if proc.poll() is not None:
                return FAIL, f"{time.time() - started:.0f}s 内进程自己退了（码 {proc.returncode}）"
            targets = cdp_targets(port)
            if targets:
                seen = [t.get("url") or "" for t in targets]
            page = next((t for t in targets
                         if "tauri.localhost" in (t.get("url") or "")), None)
            if page:
                break
            time.sleep(0.5)
        waited = time.time() - started
        if not page:
            why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
            return webview_verdict(None, version, waited, why)
        try:
            sig: dict = {}
            deadline = time.time() + WEBVIEW_READY_WAIT
            while True:
                msg = cdp_eval(page["webSocketDebuggerUrl"], WEBVIEW_EXPR)
                det = msg.get("exceptionDetails")
                raw = ((msg.get("result") or {}).get("result") or {}).get("value")
                sig = json.loads(raw) if raw else {}
                if det:
                    exc = ((det.get("exception") or {}).get("description")) or det.get("text")
                    sig["exception"] = exc
                # 导航到了不等于解析完了：这里会先看到 interactive，判早了就会假红
                if sig.get("exception") or sig.get("ready") == "complete":
                    break
                if time.time() > deadline:
                    break
                time.sleep(0.3)
            return webview_verdict(sig, version, time.time() - started)
        except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
            return FAIL, f"进了界面但读不到 DOM：{e}"
    finally:
        if proc.poll() is None:
            kill(proc.pid)


def a36_webview() -> tuple[str, str]:
    """A36：窗口起来之后，界面里到底有没有东西。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_webview(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A37：无头里跑过的自检，在真窗口里也跑一遍 ---------------------

# 那 21 条自检一直跑在 file:// 上：没有真后端，localStorage 是临时 profile。
# 真窗口是另一回事——真后端、真偏好。真要在这儿跑，得先认清两件事：
# ① 有些自检会写我的设置（实测把 portio.drawer 从 2 改成了 3），
#    还有些要动主题 / 字号 / 会话 / 已知主机，那就碰到真文件了；
# ② `/json/list` 里的标题比页面慢一拍（实测 ctx-test 读到的是上一条 fold 的）。
# 所以这里只跑「只动内存」的那几条，跑前把 localStorage 存下来、跑完一字不差写回去，
# 标题从页面自己嘴里读、而且只在 location.hash 对上之后才认。
SELFTEST_WAIT = 20.0
SELFTESTS = (
    ("split-test", "SELFTEST-OK"),
    ("clip-test", "CLIP-SELFTEST-OK 10"),
    ("fold-test", "FOLD-SELFTEST-OK"),
    ("ctx-test", "CTX-SELFTEST-OK 9"),
    ("find-test", "FIND-SELFTEST-OK"),
    ("find-pane-test", "FIND-PANE-SELFTEST-OK"),
    ("transfer-test", "TRANSFER-SELFTEST-OK"),
)
SELFTEST_SIG_EXPR = ("JSON.stringify({hash:location.hash,ready:document.readyState,"
                     "title:document.title})")
WEBVIEW_BACKUP_EXPR = (
    # 键排过序再拼：键序在 localStorage 里本来就会变（clear 之后重写就不是原顺序），
    # 不排序的话「内容一样」会被假的字符串比对判成「动过了」
    "(()=>{const ks=[];for(let i=0;i<localStorage.length;i++)ks.push(localStorage.key(i));"
    "ks.sort();const o={};for(const k of ks)o[k]=localStorage.getItem(k);"
    "return JSON.stringify(o);})()"
)


def settings_same(a: str, b: str) -> bool:
    """两份偏好快照是不是同一份——比内容，不比字面顺序。"""
    try:
        return json.loads(a or "{}") == json.loads(b or "{}")
    except (json.JSONDecodeError, TypeError):
        return (a or "") == (b or "")


def localstorage_restore_expr(dump: str) -> str:
    """把存下来的那份 localStorage 原样写回去的那句话（跑前存、跑完还）。"""
    return ("(()=>{const o=" + (dump or "{}") + ";localStorage.clear();"
            "for(const k in o)localStorage.setItem(k,o[k]);return localStorage.length;})()")


def selftest_verdict(rows: list[tuple[str, str, str]],
                     restored: bool | None = None) -> tuple[str, str]:
    """把每条自检「真跑出来的标题」逐条判（纯函数，好测）。

    认的是「这条钩子自己的标题」而不是「随便一个 SELFTEST-OK」——
    拿前缀比对就等于顺手堵死了「读到上一条的标题」那个坑。
    """
    if not rows:
        return FAIL, "一条自检都没跑（等于没核）"
    bad = rows_bad(rows)
    if bad:
        return FAIL, "；".join(bad)
    if restored is False:
        return FAIL, "跑完没把设置写回去——我的偏好被自检挪动了"
    return PASS, (f"{len(rows)} 条在真窗口里跑过（{'、'.join(h for h, _, _ in rows)}）；"
                  "跑前存下、跑完写回的偏好一字没动")


def cdp_call(ws_url: str, method: str, params: dict, timeout: float = 8.0) -> dict:
    """发一条 CDP 命令、等它那一帧回来（Runtime.evaluate / Page.navigate 都走这里）。"""
    sock = ws_open(ws_url, timeout)
    try:
        ws_send_text(sock, json.dumps({"id": 1, "method": method,
                                       "params": params}).encode())
        whole = b""
        while True:
            fin, buf = ws_recv_frame(sock)
            whole += buf
            if not fin:
                continue
            msg = json.loads(whole.decode("utf-8"))
            if msg.get("id") == 1:
                return msg
            whole = b""
    finally:
        sock.close()


def cdp_value(ws_url: str, expr: str, timeout: float = 8.0):
    """跑一句只读的话并把值取出来；这话自己在界面里炸了就抛出去，由调用方报。"""
    msg = cdp_call(ws_url, "Runtime.evaluate",
                   {"expression": expr, "returnByValue": True}, timeout)
    det = msg.get("exceptionDetails")
    if det:
        exc = ((det.get("exception") or {}).get("description")) or det.get("text")
        raise RuntimeError(exc or "界面里那句话炸了")
    return ((msg.get("result") or {}).get("result") or {}).get("value")


def run_selftest(ws_url: str, hook: str, expect: str, wait: float = SELFTEST_WAIT,
                 call=cdp_call, value=cdp_value, sleep=time.sleep,
                 clock=time.time) -> tuple[str, str, str]:
    """真的导航到某个自检钩子，等它把结果写进标题，回（钩子, 期望前缀, 标题）。"""
    # 带个不一样的查询串才叫真重载：只改 fragment 是同文档导航，启动那段自检不会跑
    call(ws_url, "Page.navigate", {"url": f"http://tauri.localhost/?st={hook}#{hook}"})
    deadline = clock() + wait
    title = ""
    while True:
        sig = json.loads(value(ws_url, SELFTEST_SIG_EXPR) or "{}")
        if sig.get("hash") == f"#{hook}" and sig.get("ready") == "complete":
            title = str(sig.get("title") or "")
            if "SELFTEST-OK" in title or "ERR:" in title:
                break
        if clock() > deadline:
            break
        sleep(0.25)
    return hook, expect, title


def probe_selftests(exe: Path, version: str, wait: float = WEBVIEW_WAIT, port: int | None = None,
                    popen=subprocess.Popen, kill=kill_tree,
                    hooks=SELFTESTS, runner=run_selftest,
                    value=cdp_value) -> tuple[str, str]:
    """拉起 exe，在真 webview 里把这几条自检跑一遍，再把偏好原样写回去、收干净。"""
    port = port or free_port()
    env = dict(os.environ)
    # 同 A36：调试口只给这一个子进程开，机器上的设置一个字不动
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        page = None
        seen: list[str] = []
        while time.time() - started < wait:
            if proc.poll() is not None:
                return FAIL, f"{time.time() - started:.0f}s 内进程自己退了（码 {proc.returncode}）"
            targets = cdp_targets(port)
            if targets:
                seen = [t.get("url") or "" for t in targets]
            page = next((t for t in targets
                         if "tauri.localhost" in (t.get("url") or "")), None)
            if page:
                break
            time.sleep(0.5)
        if not page:
            why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
            return FAIL, f"{time.time() - started:.0f}s 内没进到界面（{why}）——自检没跑过，等于没核"
        ws = page["webSocketDebuggerUrl"]
        deadline = time.time() + WEBVIEW_READY_WAIT
        while time.time() < deadline and value(ws, "document.readyState") != "complete":
            time.sleep(0.3)
        ver = str(value(ws, "(document.querySelector('.ver')||{}).textContent") or "").strip()
        if version and ver and ver != version:
            # 跟 A36 一个口径：手上这份不是本版构建，「没核到」不是「坏了」
            return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                          "自检在真窗口里跑没跑得动这轮没核到")
        before = value(ws, WEBVIEW_BACKUP_EXPR) or "{}"
        rows = []
        for hook, expect in hooks:
            rows.append(runner(ws, hook, expect))
        after = value(ws, WEBVIEW_BACKUP_EXPR) or "{}"
        restored = True
        if not settings_same(after, before):
            # 自检把偏好挪了：原样写回去，再确认一次真的回去了
            value(ws, localstorage_restore_expr(before))
            restored = settings_same(value(ws, WEBVIEW_BACKUP_EXPR) or "{}", before)
        return selftest_verdict(rows, restored)
    except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
        return FAIL, f"进了界面但自检没跑成：{e}"
    finally:
        if proc.poll() is None:
            kill(proc.pid)


def a37_selftests() -> tuple[str, str]:
    """A37：那几条自检，在真窗口里跑得动吗。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_selftests(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A38：会改设置的那批自检，换一份一次性 profile 去跑 -----------------

# A37 只搬了「不动设置」的七条。剩下那批要改主题 / 界面字号 / 密度 / 强调色 / 终端配色 /
# 启动布局 / 权限列 / 开局格数 / 面板宽度——在真 profile 里跑，改的就是我自己的偏好。
# 对这批复用「跑完写回去」不可靠：中途崩了、超时被杀、进程还在后台写，就写不回去。
# 换个办法：只给这个子进程一份**一次性**的 WebView2 profile（进程级环境变量），
# 它的 localStorage 是空的、首启默认，全不心疼；跑完连目录一起删。
# 隔离成没成不靠嘴说：真 profile 的 localStorage 库（文件数 / 总字节 / 最新时间）跑前跑后必须一模一样。
# 唯一绕不过去的是窗口底色文件 theme.txt——它落在真 app-data 里，新 profile 一起启动就按首启偏好
# 重写一遍，所以跑完把它原字节写回、再核对一遍。
# 会动真文件的会话与已知主机两条（#sessions-test / #hosts-test）不在这儿跑：
# 它们起手就把 sessionStore.records 清空，在真后端上等于把我存过的会话清单抹掉。
APP_IDENTIFIER = "io.portio.desktop"
FRESH_PROFILE_WAIT = 30.0  # 新 profile 首启要先建库，比老 profile 慢
VER_EXPR = "(document.querySelector('.ver')||{}).textContent"
FRESH_SELFTESTS = (
    ("panes-test", "PANES-SELFTEST-OK"),
    ("layout-test", "LAYOUT-SELFTEST-OK"),
    ("density-test", "DENSITY-SELFTEST-OK"),
    ("accent-test", "ACCENT-SELFTEST-OK"),
    ("term-theme-test", "TERM-THEME-SELFTEST-OK"),
    ("boot-test", "BOOT-SELFTEST-OK"),
    ("perm-test", "PERM-SELFTEST-OK"),
    ("font-test", "FONT-SELFTEST-OK"),
    ("theme-test", "THEME-SELFTEST-OK"),
)
# 这两条在真后端上会落到真文件，不搬；写进 backlog 等「后端数据也能精确还原」再说。
FRESH_EXCLUDED = ("sessions-test", "hosts-test")


def profile_stamp(root: Path | None) -> dict:
    """一份 profile 里所有文件的「指纹」：文件数、总字节、最新改动时间（秒）。"""
    if root is None or not root.exists():
        return {"files": 0, "bytes": 0, "newest": 0}
    files = [p for p in root.rglob("*") if p.is_file()]
    return {
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "newest": int(max((p.stat().st_mtime for p in files), default=0)),
    }


def localStorage_dir(identifier: str = APP_IDENTIFIER, env=None) -> Path | None:
    """真 profile 的 localStorage 库在哪儿：Windows 上是 %LOCALAPPDATA%\\<id>\\EBWebView\\Default\\…。"""
    base = (env if env is not None else os.environ).get("LOCALAPPDATA")
    if not base:
        return None
    return Path(base) / identifier / "EBWebView" / "Default" / "Local Storage" / "leveldb"


def app_data_file(name: str, identifier: str = APP_IDENTIFIER, env=None) -> Path | None:
    """真 app-data 里的某一份文件（`theme.txt` 这种窗口底色提示就放在这里）。"""
    base = (env if env is not None else os.environ).get("APPDATA")
    if not base:
        return None
    return Path(base) / identifier / name


def fresh_profile_db(prof: Path | None) -> Path | None:
    """一次性 profile 里 localStorage 库落在哪儿。

    给的那层目录下 WebView2 会再套一层 `EBWebView`（实测 `…\\_p38d_prof\\EBWebView\\Default\\…`），
    所以这里不拼死路径，直接找「哪儿真的建出了库」。
    """
    if prof is None or not prof.exists():
        return None
    for d in prof.rglob("leveldb"):
        if d.is_dir() and d.parent.name == "Local Storage" and any(d.iterdir()):
            return d
    return None


def restore_bytes(path: Path | None, data: bytes | None) -> bool | None:
    """把一份真文件写回原样，回「回没回去」。

    本来就该没有、现在也没有 = 不用还原（回 None，由调用方当「没事」）。
    原来有、现在被我写坏了 = 写回再核对；原来没有、现在冒出来一份 = 不替你删，报红。
    """
    if path is None:
        return None
    now = path.read_bytes() if path.exists() else None
    if now == data:
        return True
    if data is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path.read_bytes() == data


def rows_bad(rows: list[tuple[str, str, str]]) -> list[str]:
    """逐条核「这条钩子自己的标题」：报红 / 前缀不够都算没跑出结果。"""
    bad = []
    for hook, expect, title in rows:
        title = title or ""
        if "ERR:" in title:
            bad.append(f"{hook} 自己报了红：{title}")
        elif not title.startswith(expect):
            bad.append(f"{hook} 没跑出结果（标题 {title or '空'}，期望以 {expect} 开头）")
    return bad


def fresh_verdict(rows: list[tuple[str, str, str]], fresh_used: bool,
                  real_untouched: bool | None, theme_ok: bool | None) -> tuple[str, str]:
    """把「一次性 profile 里跑的这批」逐层判（纯函数，好测）。

    四层各自独立：自检本身过没过、隔离到底生不生效、我的偏好库动没动、底色文件回没回去。
    少核一层就等于这次跑可能改了我自己的东西而我不知道。
    """
    if not rows:
        return FAIL, "一条自检都没跑（等于没核）"
    bad = rows_bad(rows)
    if bad:
        return FAIL, "；".join(bad)
    if not fresh_used:
        return FAIL, "一次性 profile 里没冒出 localStorage 库——隔离没生效，这批是在我自己的偏好里跑的"
    if real_untouched is False:
        return FAIL, "跑完我自己的偏好库被动过（文件数 / 字节 / 时间戳变了）——隔离没挡住"
    if real_untouched is None:
        # 量不到「有没有被动」不算核过：宁可红，也不许含糊成通过
        return FAIL, "量不到我自己的偏好库在哪儿，隔离有没有挡住这轮没核到"
    if theme_ok is False:
        return FAIL, "窗口底色文件没写回原样（theme.txt 跟我跑前存的那份不一样）"
    return PASS, (f"{len(rows)} 条在一次性 profile 里跑过（{'、'.join(h for h, _, _ in rows)}）；"
                  "我自己的偏好库一个字节没动，底色文件写回原样")


def probe_fresh_selftests(exe: Path, version: str, wait: float = FRESH_PROFILE_WAIT,
                          port: int | None = None, popen=subprocess.Popen, kill=kill_tree,
                          hooks=FRESH_SELFTESTS, runner=run_selftest, value=cdp_value,
                          mkdtemp=tempfile.mkdtemp, sleep=time.sleep) -> tuple[str, str]:
    """拉起 exe（配一份一次性 profile），把这批会改设置的自检跑一遍，收干净并核隔离。"""
    port = port or free_port()
    prof = make_profile("portio-fresh-", mkdtemp=mkdtemp)
    db = localStorage_dir()
    theme = app_data_file("theme.txt")
    db_before = profile_stamp(db)
    theme_before = theme.read_bytes() if theme and theme.exists() else None
    env = dict(os.environ)
    # 两个都只给这一个子进程：调试口与一次性偏好目录，机器上的设置一个字不动
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    env["WEBVIEW2_USER_DATA_FOLDER"] = str(prof)
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows: list[tuple[str, str, str]] = []
    err: Exception | None = None
    try:
        page = None
        seen: list[str] = []
        while time.time() - started < wait:
            if proc.poll() is not None:
                return FAIL, f"{time.time() - started:.0f}s 内进程自己退了（码 {proc.returncode}）"
            targets = cdp_targets(port)
            if targets:
                seen = [t.get("url") or "" for t in targets]
            page = next((t for t in targets
                         if "tauri.localhost" in (t.get("url") or "")), None)
            if page:
                break
            time.sleep(0.5)
        if not page:
            why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
            return FAIL, f"{time.time() - started:.0f}s 内没进到界面（{why}）——自检没跑过，等于没核"
        ws = page["webSocketDebuggerUrl"]
        # 空 profile 首启时，导航之前那一帧也是 readyState=complete（那是 about:blank），
        # 光等 complete 会读到空白页。所以等的是「标题栏那个版本串真的出现」。
        deadline = time.time() + wait
        ver = ""
        while time.time() < deadline:
            ver = str(value(ws, VER_EXPR) or "").strip()
            if ver:
                break
            sleep(0.3)
        if not ver:
            return FAIL, (f"{time.time() - started:.0f}s 内那个版本串还没出现——"
                          "界面没进到本应用（空白页也算加载完了，别被它骗）")
        if version and ver != version:
            return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                          "这批自检在一次性 profile 里跑不跑得动这轮没核到")
        for hook, expect in hooks:
            rows.append(runner(ws, hook, expect))
    except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
        err = e
    finally:
        if proc.poll() is None:
            kill(proc.pid)
            sleep(1.5)  # 等它把库文件关掉、时间戳落地，不然「有没有动」量不准
        fresh_used = fresh_profile_db(prof) is not None
        db_after = profile_stamp(db)
        theme_ok = restore_bytes(theme, theme_before)
        release_profile(prof)
    if err is not None:
        return FAIL, f"进了界面但自检没跑成：{err}"
    return fresh_verdict(rows, fresh_used, db_before == db_after, theme_ok)


def a38_fresh_selftests() -> tuple[str, str]:
    """A38：会改设置的那几条自检，在一份一次性 profile 里跑得动吗。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_fresh_selftests(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A39：最后两条会动真文件的自检，进真窗口 + 后端数据「先存、跑完收回、再核」 ----

# A38 之后只剩 #sessions-test / #hosts-test 还只在无头里跑：它们走真后端，
# 会话清单落到 %APPDATA%\<id>\sessions.json，已知主机落到同目录的 known_hosts。
# 想给后端也换一份一次性目录没戏——实测给子进程改 `APPDATA` 没用：Tauri 取的是 Known Folder API，
# 不认进程环境变量，新目录里什么都没长出来，真 app-data 照样被启动改写。
# 所以后端那几份文件只能「先按字节存下 → 跑 → 收进程 → 按原字节写回（原本没有的那份收走）→ 再读一遍核对」，
# 同时还得证明**它确实写了**：跑完 sessions.json 没冒出来也没变，说明这两条根本没走真后端，那还是「没核」。
APP_DATA_BACKUP = ("theme.txt", "sessions.json", "known_hosts")
A39_SELFTESTS = (
    ("sessions-test", "SESSIONS-SELFTEST-OK"),
    ("hosts-test", "HOSTS-SELFTEST-OK"),
)
APP_WRITE_PROOF = "sessions.json"  # 这两条里只有它落盘；它没动静就等于没核


def file_stamp(path: Path | None) -> dict:
    """一份文件的长相：在不在、多少字节、内容哈希、改动时间（秒）。

    只比字节不够：同一次写回大小一样、时间戳却变了，说明中途还有人动过它。
    """
    if path is None or not path.exists():
        return {"exists": False, "size": 0, "sha": "", "mtime": 0}
    data = path.read_bytes()
    return {
        "exists": True,
        "size": len(data),
        "sha": hashlib.sha256(data).hexdigest()[:16],
        "mtime": int(path.stat().st_mtime),
    }


def collect_app_state(names=APP_DATA_BACKUP, env=None) -> dict:
    """把后端那几份文件的字节与指纹一起存下来（跑前跑后各存一份用）。"""
    state = {}
    for name in names:
        p = app_data_file(name, env=env)
        state[name] = {
            "path": str(p) if p else None,
            "stamp": file_stamp(p),
            "bytes": (p.read_bytes() if p is not None and p.exists() else None),
        }
    return state


def restore_app_state(state: dict) -> list[str]:
    """把后端那几份文件收回原样，回「没收回去」的名字清单。

    原来有 → 按原字节写回；原来没有 → 那份是这两条自检自己造出来的，收走。
    （这不叫删用户文件：用户本来就没有，收走的只是测试自己写下去的。）
    收完都再读一遍核对，回不去的一律报出来，不许静默算过。
    """
    bad: list[str] = []
    for name, item in state.items():
        path = Path(item["path"]) if item.get("path") else None
        if path is None:
            continue
        want = item.get("bytes")
        if want is None:
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
                if path.exists():
                    bad.append(name)
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(want)
        except OSError:
            pass
        if not path.exists() or path.read_bytes() != want:
            bad.append(name)
    return bad


def residue_bad(before: dict, settled: dict | None) -> list[str]:
    """收完之后独立再读一遍：还跟跑前存的字节不一样的，就是没收干净。

    这条判据不能省：`restore_app_state` 说自己收回去了，不代表真收回去了——
    反向验证时就撞过「还原函数什么都不做、却照样回空清单」，判据要是只信它的返回值，
    那次跑会照样报绿，而我的会话清单其实已经被换成测试那 45 条了。
    量不到（settled 为 None）也算没收干净：量不到不算核过。
    """
    if settled is None:
        return list(before)
    bad = []
    for name, item in before.items():
        if name not in settled:
            # 那份文件这次根本没量到（不是「量到没有」），同样算没收干净
            bad.append(name)
            continue
        got = (settled.get(name) or {}).get("bytes")
        if got != item.get("bytes"):
            bad.append(name)
    return bad


def app_files_verdict(rows: list[tuple[str, str, str]], wrote: bool,
                      restore_bad: list[str]) -> tuple[str, str]:
    """把这批「走真后端」的自检逐层判（纯函数，好测）。

    三层缺一不可：自检本身过没过、它到底有没有在真后端上落盘、我有没有把落下去的收回来。
    最后那层是我自己的会话清单，收不回来就等于这次跑改了我的东西。
    """
    if not rows:
        return FAIL, "一条自检都没跑（等于没核）"
    bad = rows_bad(rows)
    if bad:
        return FAIL, "；".join(bad)
    if not wrote:
        return FAIL, (f"跑完 {APP_WRITE_PROOF} 没冒出来也没变——这说明这两条没在真后端上跑过，"
                      "还只是无头里那份，等于没核")
    if restore_bad:
        return FAIL, "这几份后端文件没收回原样：" + "、".join(restore_bad)
    return PASS, (f"{len(rows)} 条在真窗口 + 真后端里跑过（{'、'.join(h for h, _, _ in rows)}）；"
                  f"会话清单确实落了盘（{APP_WRITE_PROOF} 变了），跑完按原字节收回、逐字节核对一致")


def probe_app_selftests(exe: Path, version: str, wait: float = FRESH_PROFILE_WAIT,
                        port: int | None = None, popen=subprocess.Popen, kill=kill_tree,
                        hooks=A39_SELFTESTS, runner=run_selftest, value=cdp_value,
                        mkdtemp=tempfile.mkdtemp, sleep=time.sleep,
                        collect=collect_app_state, restore=restore_app_state) -> tuple[str, str]:
    """拉起 exe（一次性 profile），把这两条会写盘的自检跑一遍，跑完把后端文件收回原样。"""
    port = port or free_port()
    prof = make_profile("portio-appdata-", mkdtemp=mkdtemp)
    before = collect()
    env = dict(os.environ)
    # 调试口与一次性 profile 只给这一个子进程；后端目录换不了（见段首），靠存/收兜
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    env["WEBVIEW2_USER_DATA_FOLDER"] = str(prof)
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows: list[tuple[str, str, str]] = []
    err: Exception | None = None
    try:
        page = None
        seen: list[str] = []
        while time.time() - started < wait:
            if proc.poll() is not None:
                return FAIL, f"{time.time() - started:.0f}s 内进程自己退了（码 {proc.returncode}）"
            targets = cdp_targets(port)
            if targets:
                seen = [t.get("url") or "" for t in targets]
            page = next((t for t in targets
                         if "tauri.localhost" in (t.get("url") or "")), None)
            if page:
                break
            time.sleep(0.5)
        if not page:
            why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
            return FAIL, f"{time.time() - started:.0f}s 内没进到界面（{why}）——自检没跑过，等于没核"
        ws = page["webSocketDebuggerUrl"]
        deadline = time.time() + wait
        ver = ""
        while time.time() < deadline:
            ver = str(value(ws, VER_EXPR) or "").strip()
            if ver:
                break
            sleep(0.3)
        if not ver:
            return FAIL, (f"{time.time() - started:.0f}s 内那个版本串还没出现——"
                          "界面没进到本应用（空白页也算加载完了，别被它骗）")
        if version and ver != version:
            return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                          "这两条在真后端上跑不跑得动这轮没核到")
        for hook, expect in hooks:
            rows.append(runner(ws, hook, expect))
    except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
        err = e
    finally:
        if proc.poll() is None:
            # 后端落盘是「先写 .tmp 再改名」，收进程后多等一会儿再量，不然量到半截
            kill(proc.pid)
            sleep(2.0)
        after = collect()
        wrote = after[APP_WRITE_PROOF]["stamp"] != before[APP_WRITE_PROOF]["stamp"]
        restore_bad = restore(before)
        # 还原函数自己说的不算：收完再独立读一遍，跟跑前存的字节逐份对
        try:
            settled = collect()
        except Exception:  # noqa: BLE001 - 量不到就当没收干净，不许含糊成通过
            settled = None
        for name in residue_bad(before, settled):
            if name not in restore_bad:
                restore_bad.append(name)
        release_profile(prof)
    if err is not None:
        return FAIL, f"进了界面但自检没跑成：{err}"
    return app_files_verdict(rows, wrote, restore_bad)


def a39_appdata_selftests() -> tuple[str, str]:
    """A39：会写盘的那两条自检，在真窗口 + 真后端上跑得动吗，跑完后端文件收得回来吗。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_app_selftests(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A40：窄窗那条自检，在真窗口里按两档宽度跑 ---------------------

# `#narrow-test` 量的是真实几何，可它到现在只在无头里按 `--window-size` 跑过两档（A13）。
# 真窗口只有一个宽度（tauri.conf 固定 1180×690），要它能窄，得先能给这个子进程换宽度。
# 不用动 Rust：调试口自己就带着换视口的命令 `Emulation.setDeviceMetricsOverride`——
# 把布局视口改成 1024 / 900，CSS 跟着重排，量的还是真实几何。
# 坑在**这是会话级命令**：开一条新 websocket 发一次、连接一断就失效。而 `cdp_call` 每次都是新会话，
# 照它的写法「这条会话里设视口、那条会话里读标题」，读到的会是退回 1180 的那份。
# 所以两档必须在一根长连的会话里跑完：设视口 → 导航 → 读标题 → 再设视口 → 再导航。
# 判据里最要命的一层是「视口到底换没换」：命令失效时界面照样 1180 宽、自检照样报绿，
# 那就是拿一档宽窗冒充窄窗。所以拿界面自己报的 innerWidth 跟我要的对，对不上就红。
NARROW_VIEWPORTS = ((1024, 620), (900, 620))
NARROW_EXPECT = "NARROW-SELFTEST-OK"
NARROW_WAIT = 20.0
NARROW_SIG_EXPR = ("JSON.stringify({hash:location.hash,ready:document.readyState,"
                   "title:document.title,w:window.innerWidth,h:window.innerHeight})")


class CdpSession:
    """一根长连的调试会话。视口这类命令是会话级的：断一次就回原样。"""

    def __init__(self, ws_url: str, timeout: float = 8.0):
        self.sock = ws_open(ws_url, timeout)
        self._id = 0

    def call(self, method: str, params: dict, timeout: float = 8.0) -> dict:
        self._id += 1
        mine = self._id
        ws_send_text(self.sock, json.dumps({"id": mine, "method": method,
                                            "params": params}).encode())
        whole = b""
        while True:
            fin, buf = ws_recv_frame(self.sock)
            whole += buf
            if not fin:
                continue
            msg = json.loads(whole.decode("utf-8"))
            whole = b""
            if msg.get("id") == mine:
                return msg

    def value(self, expr: str, timeout: float = 8.0):
        """在这条会话里跑一句只读的话；它自己炸了就把原因抛出去。"""
        msg = self.call("Runtime.evaluate",
                        {"expression": expr, "returnByValue": True}, timeout)
        det = msg.get("exceptionDetails")
        if det:
            exc = ((det.get("exception") or {}).get("description")) or det.get("text")
            raise RuntimeError(exc or "界面里那句话炸了")
        return ((msg.get("result") or {}).get("result") or {}).get("value")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def set_viewport(sess, width: int, height: int) -> bool:
    """把这条会话的布局视口改成 width×height，回「调试口收下了没」。"""
    msg = sess.call("Emulation.setDeviceMetricsOverride",
                    {"width": width, "height": height,
                     "deviceScaleFactor": 0, "mobile": False})
    return not msg.get("error")


def run_narrow(sess, width: int, height: int, wait: float = NARROW_WAIT,
               sleep=time.sleep, clock=time.time) -> tuple[str, str, str, int]:
    """换视口 → 导航跑窄窗自检，回（档位, 期望前缀, 标题, 界面实际视口宽）。"""
    tag = f"{width}x{height}"
    set_viewport(sess, width, height)
    # 带查询串才叫真重载：只改 fragment 是同文档导航，启动那段自检不会跑
    sess.call("Page.navigate", {"url": f"http://tauri.localhost/?nw={tag}#narrow-test"})
    deadline = clock() + wait
    title, seen = "", 0
    while True:
        try:
            sig = json.loads(sess.value(NARROW_SIG_EXPR) or "{}")
        except (RuntimeError, OSError, ValueError):
            # 导航那一瞬间执行环境会被换掉，读一句会失手；这是轮询里正常的一下，
            # 真失手到底的话下面会超时、标题空着、判红——不许在这儿悄悄当通过
            sig = {}
        if sig.get("hash") == "#narrow-test" and sig.get("ready") == "complete":
            title = str(sig.get("title") or "")
            seen = int(sig.get("w") or 0)
            if NARROW_EXPECT in title or "ERR:" in title:
                break
        if clock() > deadline:
            break
        sleep(0.25)
    return tag, NARROW_EXPECT, title, seen


def narrow_rows(title: str) -> dict:
    """把自检写进标题的那串几何捞出来（标题后半截就是 JSON）。"""
    i = (title or "").find("{")
    if i < 0:
        return {}
    try:
        return json.loads(title[i:])
    except (json.JSONDecodeError, ValueError):
        return {}


def reported_width(title: str) -> int | None:
    """自检自己说它是在多宽的窗口里量的（标题里那个 `w=`）。"""
    m = re.search(r"w=(\d+)", title or "")
    return int(m.group(1)) if m else None


def narrow_verdict(rows: list[tuple[str, str, str, int]], fresh_used: bool,
                   real_untouched: bool | None, theme_ok: bool | None) -> tuple[str, str]:
    """把两档窄窗逐层判（纯函数，好测）。

    隔离与「别碰我的」这层跟 A38 一样，多出来的是「视口真换了」：
    界面自报的 innerWidth 跟我要的不一致，就是拿宽窗冒充窄窗，自检再绿也不算核过；
    两档几何一模一样，说明压根没重排，那也只算核了一档。
    """
    if len(rows) < 2:
        return FAIL, "两档窄窗没跑齐（等于没核）"
    bad: list[str] = []
    geo: dict[int, dict] = {}
    for tag, expect, title, seen in rows:
        want = int(str(tag).split("x")[0])
        if "ERR:" in (title or ""):
            bad.append(f"{tag}：界面自己报了红：{title}")
            continue
        if not (title or "").startswith(expect):
            bad.append(f"{tag}：没跑出结果（标题 {title or '空'}，期望以 {expect} 开头）")
            continue
        said = reported_width(title)
        if said != want:
            bad.append(f"{tag}：自检说自己在 {said} 宽里量的，它不是 {want}——这档没在窄窗里跑")
            continue
        if seen != want:
            bad.append(f"{tag}：界面实际的视口是 {seen} 宽，不是 {want}——视口没换过来，这档等于没核")
            continue
        geo[want] = narrow_rows(title)
    if bad:
        return FAIL, "；".join(bad)
    for w, g in geo.items():
        got = (g.get("fold") or {}).get("term")
        if not isinstance(got, int) or got <= 0:
            bad.append(f"{w} 宽那档量不到折叠态终端宽度")
    if bad:
        return FAIL, "；".join(bad)
    # 从宽往窄排：视口收窄一档，终端就得跟着窄一点。反过来排的话，
    # 判据本身就成了「窄的这档要比宽的那档更宽」，第一跑就自己撞红
    order = sorted(geo, reverse=True)
    for a, b in zip(order, order[1:]):
        ta = (geo[a].get("fold") or {}).get("term")
        tb = (geo[b].get("fold") or {}).get("term")
        if not tb < ta:
            bad.append(f"视口从 {a} 收窄到 {b}，终端宽度却从 {ta} 变到 {tb}——两档没真重排")
    if bad:
        return FAIL, "；".join(bad)
    if not fresh_used:
        return FAIL, "一次性 profile 里没冒出 localStorage 库——隔离没生效，这两档是在我自己的偏好里跑的"
    if real_untouched is False:
        return FAIL, "跑完我自己的偏好库被动过（文件数 / 字节 / 时间戳变了）——隔离没挡住"
    if real_untouched is None:
        return FAIL, "量不到我自己的偏好库在哪儿，隔离有没有挡住这轮没核到"
    if theme_ok is False:
        return FAIL, "窗口底色文件没写回原样（theme.txt 跟我跑前存的那份不一样）"
    terms = "、".join(f"{w} 宽 {int((geo[w].get('fold') or {}).get('term'))}px" for w in order)
    return PASS, (f"{len(rows)} 档在真窗口里跑过（{'、'.join(r[0] for r in rows)}）；"
                  f"折叠态终端宽度按档收窄（{terms}），视口是真换过来的；"
                  "我自己的偏好库一个字节没动，底色文件写回原样")


def probe_narrow(exe: Path, version: str, wait: float = FRESH_PROFILE_WAIT,
                 port: int | None = None, popen=subprocess.Popen, kill=kill_tree,
                 views=NARROW_VIEWPORTS, runner=run_narrow, opener=CdpSession,
                 mkdtemp=tempfile.mkdtemp, sleep=time.sleep) -> tuple[str, str]:
    """拉起 exe（一次性 profile），在一根长连会话里换两档视口把窄窗自检跑完，收干净并核隔离。"""
    port = port or free_port()
    prof = make_profile("portio-narrow-", mkdtemp=mkdtemp)
    db = localStorage_dir()
    theme = app_data_file("theme.txt")
    db_before = profile_stamp(db)
    theme_before = theme.read_bytes() if theme and theme.exists() else None
    env = dict(os.environ)
    # 同一份隔离：调试口与一次性偏好目录只给这一个子进程
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    env["WEBVIEW2_USER_DATA_FOLDER"] = str(prof)
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows: list[tuple[str, str, str, int]] = []
    sess = None
    err: Exception | None = None
    try:
        page = None
        seen: list[str] = []
        while time.time() - started < wait:
            if proc.poll() is not None:
                return FAIL, f"{time.time() - started:.0f}s 内进程自己退了（码 {proc.returncode}）"
            targets = cdp_targets(port)
            if targets:
                seen = [t.get("url") or "" for t in targets]
            page = next((t for t in targets
                         if "tauri.localhost" in (t.get("url") or "")), None)
            if page:
                break
            time.sleep(0.5)
        if not page:
            why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
            return FAIL, f"{time.time() - started:.0f}s 内没进到界面（{why}）——自检没跑过，等于没核"
        sess = opener(page["webSocketDebuggerUrl"])
        # 同 A38：空 profile 首启那帧也报 complete（那是 about:blank），等的是版本串
        deadline = time.time() + wait
        ver = ""
        while time.time() < deadline:
            ver = str(sess.value(VER_EXPR) or "").strip()
            if ver:
                break
            sleep(0.3)
        if not ver:
            return FAIL, (f"{time.time() - started:.0f}s 内那个版本串还没出现——"
                          "界面没进到本应用（空白页也算加载完了，别被它骗）")
        if version and ver != version:
            return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                          "窄窗两档在真窗口里跑不跑得动这轮没核到")
        for width, height in views:
            rows.append(runner(sess, width, height))
    except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
        err = e
    finally:
        if sess is not None:
            sess.close()
        if proc.poll() is None:
            kill(proc.pid)
            sleep(1.5)  # 等它把库文件关掉、时间戳落地，不然「有没有动」量不准
        fresh_used = fresh_profile_db(prof) is not None
        db_after = profile_stamp(db)
        theme_ok = restore_bytes(theme, theme_before)
        release_profile(prof)
    if err is not None:
        return FAIL, f"进了界面但自检没跑成：{err}"
    return narrow_verdict(rows, fresh_used, db_before == db_after, theme_ok)


def a40_narrow_viewports() -> tuple[str, str]:
    """A40：窄窗那条自检，在真窗口里按两档视口跑得动吗。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_narrow(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A41：最后两条自检也进真窗口，并证明它们没落到我的盘上 -------------

# A37–A40 之后只剩这两条：#net-fail-test 塞一个会抛错的后端替身，核「后端出事时界面有没有话说」；
# #connect-entry-test 把三条连接入口逐个点一遍，还钉住「新建连接必须从空白起」。
# 两条在真窗口里都会摸到真后端，而第二条起手就把内存里的会话清单清空（`sessionStore.records = []`）——
# 盘上那份要是跟着被写空，我存过的会话就没了。所以复用 A39 那套：
# 跑前把 theme.txt / sessions.json / known_hosts 按字节存下 → 跑 → 收进程 → 按原字节写回 → 独立再读一遍核对。
# A39 没有的一层是「证明这轮真跑在我的真后端 / 真偏好上」：要是错跑进 A38 那种一次性 profile，
# 两条自检照样能绿（界面画得出来），可它们根本没碰我的会话清单，那叫「没核」。
# 认的凭据三样：页面里真有 Tauri 桥、localStorage 里真有我的偏好（空 profile 是空的）、
# 界面底色跟真 app-data 里 theme.txt 的字节对得上；再真读一次后端（sessions_read），回的字节数记进结论。
A41_SELFTESTS = (
    ("net-fail-test", "NET-FAIL-SELFTEST-OK"),
    ("connect-entry-test", "CONNECT-ENTRY-SELFTEST-OK"),
)
A41_PROOF_EXPR = (
    "JSON.stringify({bridge:!!(window.__TAURI__&&window.__TAURI__.core&&"
    "typeof window.__TAURI__.core.invoke==='function'),"
    "keys:localStorage.length,"
    "themePref:localStorage.getItem('portio.theme'),"
    "themeNow:document.documentElement.dataset.theme})"
)
# 只读一次真后端：能回出字节数，说明后端是活的；回 ERR 开头就是没应答，不许含糊成通过
A41_BACKEND_EXPR = ("window.__TAURI__.core.invoke('sessions_read',{})"
                    ".then(t=>(''+(t||'')).length).catch(e=>'ERR '+(e&&e.message?e.message:e))")


def backend_alive(value) -> tuple[bool, str]:
    """那次只读调用到底回了什么：回数字就是后端活着，回了 ERR / 空的就不是。"""
    if value is None or isinstance(value, bool):
        return False, "后端没回话（sessions_read 一句都没回来）"
    text = str(value)
    if text.startswith("ERR "):
        return False, "后端回了个错：" + text[4:]
    try:
        n = int(text)
    except ValueError:
        return False, f"后端回的说不清：{text[:40]}"
    return True, f"{n} 字节"


def real_proof_bad(proof: dict | None, theme_bytes: bytes | None,
                   alive: tuple[bool, str] | None) -> list[str]:
    """这轮到底有没有跑在我的真后端 / 真偏好上（纯函数，好测）。

    这条判据不是形式主义：A38 起就在用一次性 profile，写错一个环境变量，
    这两条自检会在一份空偏好里跑得照样漂亮，可它们跟我的会话清单一句话都没说上。
    """
    if not proof:
        return ["页面里量不到现场（真后端、真偏好一个都没读到）"]
    if not proof.get("bridge"):
        return ["这个页面没有 Tauri 桥——跑的是浏览器预览，不是真窗口"]
    bad: list[str] = []
    if alive is None:
        bad.append("没敢问后端一句（sessions_read 那次没跑到）")
    elif not alive[0]:
        bad.append(alive[1])
    if int(proof.get("keys") or 0) <= 0:
        bad.append("localStorage 是空的——这轮跑在一次性 profile 上，不是我的真偏好")
    if not proof.get("themePref"):
        bad.append("偏好里没有 portio.theme——我的真偏好没读进来")
    if theme_bytes is None:
        bad.append("真 app-data 里没有 theme.txt 可对")
    else:
        want = theme_bytes.decode("utf-8", "ignore").strip()
        if str(proof.get("themeNow") or "") != want:
            bad.append(f"界面底色是「{proof.get('themeNow')}」、真 app-data 里是「{want}」——"
                       "两边对不上，这轮没读我的真偏好")
    return bad


def quiet_verdict(rows: list[tuple[str, str, str]], proof_bad: list[str],
                  restore_bad: list[str], changed: list[str] | None = None) -> tuple[str, str]:
    """把这两条自检逐层判（纯函数，好测）：过没过、是不是真窗口、有没有留下东西。

    `changed` 是「跑完到底有没有东西被动过」的实测清单。它有用是因为这两条自检**本来就不该写盘**：
    实测它们一张纸都不写，那「收得回来」这条就永远成立、永远绿的——把「没动过」跟「动过但收回来了」
    分开写，才不至于让人以为这条判据在替它们担什么保。
    """
    if not rows:
        return FAIL, "一条自检都没跑（等于没核）"
    bad = rows_bad(rows)
    if bad:
        return FAIL, "；".join(bad)
    if proof_bad:
        return FAIL, "没证明这轮跑在我的真后端 / 真偏好上：" + "；".join(proof_bad)
    if restore_bad:
        return FAIL, "这几份后端文件没收回原样：" + "、".join(restore_bad)
    if changed:
        return PASS, (f"{len(rows)} 条在真窗口 + 真后端里跑过（{'、'.join(h for h, _, _ in rows)}）；"
                      f"跑完这几份被动过（{'、'.join(changed)}），已按跑前状态收回、独立复量一致")
    return PASS, (f"{len(rows)} 条在真窗口 + 真后端里跑过（{'、'.join(h for h, _, _ in rows)}）；"
                  "跑完 theme.txt / sessions.json / known_hosts 一个字节没动"
                  "（这两条自检这回没写盘——收回这套是护栏，不是它们的证据）")


def probe_quiet_selftests(exe: Path, version: str, wait: float = FRESH_PROFILE_WAIT,
                          port: int | None = None, popen=subprocess.Popen, kill=kill_tree,
                          hooks=A41_SELFTESTS, runner=run_selftest, value=cdp_value,
                          call=cdp_call, sleep=time.sleep, collect=collect_app_state,
                          restore=restore_app_state) -> tuple[str, str]:
    """拉起 exe（真 profile、真 app-data），把这两条自检跑一遍，跑完把后端文件收回原样。"""
    port = port or free_port()
    before = collect()
    theme_before = (before.get("theme.txt") or {}).get("bytes")
    env = dict(os.environ)
    # 只给调试口；**故意不给** WEBVIEW2_USER_DATA_FOLDER——这一轮要的就是我的真偏好
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    started = time.time()
    proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows: list[tuple[str, str, str]] = []
    proof: dict | None = None
    alive: tuple[bool, str] | None = None
    restored: bool | None = None
    changed: list[str] = []
    err: Exception | None = None
    restore_bad: list[str] = []
    try:
        page = None
        seen: list[str] = []
        while time.time() - started < wait:
            if proc.poll() is not None:
                return FAIL, f"{time.time() - started:.0f}s 内进程自己退了（码 {proc.returncode}）"
            targets = cdp_targets(port)
            if targets:
                seen = [t.get("url") or "" for t in targets]
            page = next((t for t in targets
                         if "tauri.localhost" in (t.get("url") or "")), None)
            if page:
                break
            time.sleep(0.5)
        if not page:
            why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
            return FAIL, f"{time.time() - started:.0f}s 内没进到界面（{why}）——自检没跑过，等于没核"
        ws = page["webSocketDebuggerUrl"]
        deadline = time.time() + wait
        ver = ""
        while time.time() < deadline:
            ver = str(value(ws, VER_EXPR) or "").strip()
            if ver:
                break
            sleep(0.3)
        if not ver:
            return FAIL, (f"{time.time() - started:.0f}s 内那个版本串还没出现——"
                          "界面没进到本应用（空白页也算加载完了，别被它骗）")
        if version and ver != version:
            return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                          "这两条在真窗口里跑不跑得动这轮没核到")
        try:
            proof = json.loads(value(ws, A41_PROOF_EXPR) or "{}")
        except (json.JSONDecodeError, TypeError, ValueError):
            proof = None
        try:
            raw = call(ws, "Runtime.evaluate",
                       {"expression": A41_BACKEND_EXPR, "returnByValue": True,
                        "awaitPromise": True})
            alive = backend_alive((((raw.get("result") or {}).get("result") or {}).get("value")))
        except Exception:  # noqa: BLE001 - 问不到后端就当没证到，绝不默认「活着」
            alive = None
        ls_before = value(ws, WEBVIEW_BACKUP_EXPR) or "{}"
        for hook, expect in hooks:
            rows.append(runner(ws, hook, expect))
        ls_after = value(ws, WEBVIEW_BACKUP_EXPR) or "{}"
        if not settings_same(ls_after, ls_before):
            # 这两条本来不该动偏好；真动了就原样写回去，再确认一次真回去了
            value(ws, localstorage_restore_expr(ls_before))
            restored = settings_same(value(ws, WEBVIEW_BACKUP_EXPR) or "{}", ls_before)
    except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
        err = e
    finally:
        if proc.poll() is None:
            # 后端落盘是「先写 .tmp 再改名」，收进程后多等一会儿再量，不然量到半截
            kill(proc.pid)
            sleep(2.0)
        # 收之前先量一遍：这两条到底动没动我的盘（不动就跟「动过但收回来了」分开记）
        try:
            touched = collect()
            changed = [name for name, item in before.items()
                       if (touched.get(name) or {}).get("bytes") != item.get("bytes")]
        except Exception:  # noqa: BLE001 - 量不到就当「不知道」，结论里不夸口
            changed = []
        restore_bad = restore(before)
        # 还原函数自己说的不算：收完再独立读一遍，跟跑前存的字节逐份对
        try:
            settled = collect()
        except Exception:  # noqa: BLE001 - 量不到就当没收干净
            settled = None
        for name in residue_bad(before, settled):
            if name not in restore_bad:
                restore_bad.append(name)
    if err is not None:
        return FAIL, f"进了界面但自检没跑成：{err}"
    bad = real_proof_bad(proof, theme_before, alive)
    if restored is False:
        bad.append("跑完没把偏好写回去——我的偏好被自检挪动了")
    return quiet_verdict(rows, bad, restore_bad, changed)


def a41_real_selftests() -> tuple[str, str]:
    """A41：最后两条自检，在真窗口 + 真后端里跑得动吗，跑完我的盘有没有被改。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_quiet_selftests(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


# ---------- A43：坏档急救在真 exe 上真跑一遍（A42 之前只在无头页 + 替身里核过） ----------

# A42 核的是「读不懂时要不要另存、另存之后还存不存得进新会话」这些前端决策，可它跑在无头页里、
# 后端是自检自己扮的 `fakeInvoke`：`salvage_broken` 真去 `fs::copy` 一次这件事，一条真路径都没走过。
# 1.0.9-RC8 我亲手把真 app-data 的清单换成一截坏 JSON 验过一次，可那是一把一次性手活，不进每轮。
# 这一项把那次手活写成门禁：先按字节存下真 app-data 的三份文件 → 种一截「断电写到一半」的清单 →
# 拉起 release 那份 exe → 看真后端有没有另存出 `.broken-<毫秒>`、内容跟种下去的一字不差、
# 种下去那份有没有被反手写成空清单（那是「下次存盘就整份盖掉」的前一步）→ 按原字节收回、独立复量。
# 再加一趟对照：把种下的收走、回到「还没有这份清单」再拉一次，核「一个副本都不许冒」——
# 没有这一趟，判据就退化成「看见副本就算过」；哪天急救连好文件也另存，照样绿。
# 1.0.9-RC10 又加了一层：种下的坏档**原封不动**再拉一次，副本数不许再涨、提示条报的还得是同一份——
# 急救改成「已有字节相同的副本就复用」，这层就是核它，否则每启动一次就又拷一份，盘上会越攒越多。
BROKEN_PLANT = b'{"version":1,"records":[{"id":'
BROKEN_COPY_GLOB = "sessions.json.broken-*"
BROKEN_TOAST_HINT = "另存为"
BROKEN_COPY_WAIT = 8.0
BROKEN_SETTLE = 2.0
BROKEN_EXPR = ("JSON.stringify({title:document.title,"
               "toast:(document.getElementById('toast')||{}).textContent||''})")


def app_data_dir(identifier: str = APP_IDENTIFIER, env=None) -> Path | None:
    """真 app-data 目录（`theme.txt` 就在这儿）。"""
    base = (env if env is not None else os.environ).get("APPDATA")
    if not base:
        return None
    return Path(base) / identifier


def broken_copies(root: Path | None) -> list[Path]:
    """真 app-data 里现成躺着的另存副本，按名字排，好跟跑前那份清单比。"""
    if root is None or not root.exists():
        return []
    return sorted(p for p in root.glob(BROKEN_COPY_GLOB) if p.is_file())


def plant_broken_store(root: Path | None, payload: bytes = BROKEN_PLANT) -> Path | None:
    """把一截半截写入的清单种进真 app-data，回种在哪。

    这是整个门禁里唯一会写我盘的一步，而且只写 `sessions.json` 这一份；
    种之前 `collect_app_state` 已经把原字节存下，收场按原字节收回。
    """
    if root is None:
        return None
    root.mkdir(parents=True, exist_ok=True)
    path = root / "sessions.json"
    path.write_bytes(payload)
    return path


def new_copies(root: Path | None, before_names: list[str]) -> list[Path]:
    """跑完冒出来的副本：名字不在跑前那份清单里就算新的。"""
    return [p for p in broken_copies(root) if p.name not in before_names]


def broken_store_verdict(facts: dict | None) -> tuple[str, str]:
    """把这一趟逐层判（纯函数，好测）。任一层不成立都点名，不许含糊成通过。"""
    if not facts:
        return FAIL, "这一轮什么都没量到（没跑到真 exe 上，等于没核）"
    why = str(facts.get("load_err") or "")
    if why:
        return FAIL, f"坏档那一趟没进到界面：{why}"
    if "ERR:" in str(facts.get("title") or ""):
        return FAIL, f"界面自己报了红：{facts.get('title')}"
    copies = list(facts.get("copies") or [])
    if not copies:
        return FAIL, ("把清单种成半截之后再拉起来，一个副本都没冒出来——"
                      "急救没在真后端上跑过，这条还是没核")
    if len(copies) > 1:
        return FAIL, f"一截坏清单冒出 {len(copies)} 份副本（{'、'.join(copies)}），说不清哪份算数"
    if not facts.get("copy_bytes_ok"):
        return FAIL, f"副本 {copies[0]} 的内容跟种下去那份按字节对不上——拷的不是原文件"
    if not facts.get("original_intact"):
        return FAIL, ("种下去那份 sessions.json 被改写了（下一步一存新会话就会整份盖掉）——"
                      "另存之后原文件得一个字不动")
    if BROKEN_TOAST_HINT not in str(facts.get("toast") or ""):
        return FAIL, (f"界面上没说清另存成了什么（提示条原话：{facts.get('toast') or '空'}）——"
                      "用户只会觉得「这次没会话」")
    # 1.0.9-RC10：同一份坏档再拉一次，急救该复用先前那份副本，不许再拷
    if not facts.get("reuse_ok"):
        return FAIL, (f"第二次拉起没进到界面（{facts.get('reuse_err') or '没说原因'}）——"
                      "「同一份坏档不再重复拷」这条没核到")
    if facts.get("reuse_new"):
        return FAIL, ("同一份坏档再拉一次又冒了新副本："
                      + "、".join(facts["reuse_new"])
                      + "——每启动一次拷一份，app-data 里会越堆越多")
    if copies[0] not in str(facts.get("reuse_toast") or ""):
        return FAIL, (f"第二次拉起没说复用的是哪份副本（提示条原话：{facts.get('reuse_toast') or '空'}）"
                      f"——该报的还是 {copies[0]}，别悄悄换个地方")
    if not facts.get("control_ok"):
        return FAIL, f"好档那一趟没进到界面：{facts.get('control_err') or '没说原因'}"
    if facts.get("restore_bad"):
        return FAIL, "这几份后端文件没收回原样：" + "、".join(facts["restore_bad"])
    if facts.get("control_new"):
        return FAIL, ("好档（还没有这份清单）拉起来又冒了副本："
                      + "、".join(facts["control_new"])
                      + "——要么急救把好文件也当坏档了，要么上一趟种下去的没收拾干净")
    return PASS, (f"坏档：真后端另存出 {copies[0]}，跟种下去那份逐字节一致；原文件一个字没动；"
                  f"提示条原话「{str(facts.get('toast')).strip()}」；"
                  f"同一份坏档再拉一次没再冒新副本（报的还是 {copies[0]}）；"
                  "好档对照那趟一个副本都没冒；跑完按跑前状态收回、独立复量一致")


def _await_webview_page(proc, port: int, wait: float, sleep=time.sleep,
                        targets=cdp_targets) -> tuple[str | None, str]:
    """等调试口里出现应用页，回（ws 地址, 没等到时的原因）。"""
    started = time.time()
    seen: list[str] = []
    while time.time() - started < wait:
        if proc.poll() is not None:
            return None, f"{wait:.0f}s 内进程自己退了（码 {proc.returncode}）"
        found = targets(port)
        if found:
            seen = [t.get("url") or "" for t in found]
        page = next((t for t in found if "tauri.localhost" in (t.get("url") or "")), None)
        if page:
            return page["webSocketDebuggerUrl"], ""
        sleep(0.5)
    why = f"调试口里的页面一直是 {seen[-1] or '空的'}" if seen else "调试口一直没开"
    return None, f"{wait:.0f}s 内没进到界面（{why}）"


def probe_broken_store(exe: Path, version: str, wait: float = WEBVIEW_WAIT,
                       port: int | None = None, popen=subprocess.Popen, kill=kill_tree,
                       value=cdp_value, sleep=time.sleep, collect=collect_app_state,
                       restore=restore_app_state, root: Path | None = None) -> tuple[str, str]:
    """拉起 release 那份 exe 两趟：先种一截坏清单，再跑一趟好档对照，跑完把盘收回原样。"""
    root = root if root is not None else app_data_dir()
    if root is None:
        return SKIP, "拿不到真 app-data 目录（APPDATA 没设）"
    before = collect()
    before_copies = [p.name for p in broken_copies(root)]
    facts: dict = {"copies": [], "control_new": [], "toast": "", "load_err": "",
                   "copy_bytes_ok": None, "original_intact": None,
                   "reuse_new": [], "reuse_toast": "", "reuse_ok": None, "reuse_err": ""}
    proc = None
    err: Exception | None = None
    try:
        # ---- 第一趟：种一截坏清单，看真后端会不会先另存再重开 ----------
        plant_broken_store(root)
        probe_port = port or free_port()
        env = dict(os.environ)
        # 这一项要的就是我的真偏好与真后端：**故意不给**一次性 profile
        env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={probe_port}"
        proc = popen([str(exe)], cwd=str(exe.parent), env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws, why = _await_webview_page(proc, probe_port, wait, sleep)
        facts["load_err"] = why
        if ws is not None:
            ver = ""
            found: list[Path] = []
            deadline = time.time() + BROKEN_COPY_WAIT
            while time.time() < deadline:
                try:
                    sig = json.loads(value(ws, BROKEN_EXPR) or "{}")
                except (json.JSONDecodeError, TypeError, ValueError):
                    sig = {}
                facts["title"] = str(sig.get("title") or "")
                toast_text = str(sig.get("toast") or "")
                if len(toast_text) > len(facts["toast"]):
                    facts["toast"] = toast_text
                if not ver:
                    ver = str(value(ws, VER_EXPR) or "").strip()
                found = new_copies(root, before_copies)
                if ver and found and BROKEN_TOAST_HINT in facts["toast"]:
                    break
                sleep(0.2)
            facts["title_ver"] = ver
            if version and ver and ver != version:
                return SKIP, (f"这份 exe 里的界面是 {ver}，仓库是 {version}——不是本版构建，"
                              "坏档急救在真 exe 上跑不跑得动这轮没核到")
            if version and not ver:
                return FAIL, (f"{BROKEN_COPY_WAIT:.0f}s 内那个版本串还没出现——"
                              "界面没进到本应用（空白页也算加载完了，别被它骗）")
            facts["copies"] = [p.name for p in found]
            if len(found) == 1:
                try:
                    facts["copy_bytes_ok"] = found[0].read_bytes() == BROKEN_PLANT
                except OSError:
                    facts["copy_bytes_ok"] = False
                try:
                    planted = root / "sessions.json"
                    facts["original_intact"] = bool(planted.exists()
                                                    and planted.read_bytes() == BROKEN_PLANT)
                except OSError:
                    facts["original_intact"] = False
        if proc.poll() is None:
            kill(proc.pid)
            sleep(BROKEN_SETTLE)
        proc = None

        # ---- 第一趟半：同一份坏档再拉一次，不许再拷一份 ----------------
        # 1.0.9-RC9 之前是「读不懂就拷一份新的」，可用户不去动那份坏文件的话，应用每启动一次
        # 就再拷一份（毫秒不同，名字也不同），十几次之后 app-data 里就躺着一堆没人看的文件。
        # 急救改成「已有字节相同的副本就复用那份」，这一趟就是核它：副本数不许再涨，
        # 提示条报的还得是同一份名字（复用不是悄悄换了个地方）。
        again_before = [p.name for p in broken_copies(root)]
        again_port = port or free_port()
        again_env = dict(env)
        again_env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={again_port}"
        proc = popen([str(exe)], cwd=str(exe.parent), env=again_env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws3, why3 = _await_webview_page(proc, again_port, wait, sleep)
        facts["reuse_err"] = why3
        facts["reuse_ok"] = ws3 is not None
        if ws3 is not None:
            ver3 = ""
            deadline = time.time() + BROKEN_COPY_WAIT
            while time.time() < deadline:
                try:
                    sig3 = json.loads(value(ws3, BROKEN_EXPR) or "{}")
                except (json.JSONDecodeError, TypeError, ValueError):
                    sig3 = {}
                toast3 = str(sig3.get("toast") or "")
                if len(toast3) > len(facts["reuse_toast"]):
                    facts["reuse_toast"] = toast3
                if not ver3:
                    ver3 = str(value(ws3, VER_EXPR) or "").strip()
                if ver3 and BROKEN_TOAST_HINT in facts["reuse_toast"]:
                    break
                sleep(0.2)
            if version and not ver3:
                return FAIL, (f"第二次拉起后 {BROKEN_COPY_WAIT:.0f}s 内版本串还没出现——"
                              "这一趟没进到本应用，复用没核到")
            facts["reuse_new"] = [p.name for p in broken_copies(root)
                                  if p.name not in again_before]
        if proc.poll() is None:
            kill(proc.pid)
            sleep(BROKEN_SETTLE)
        proc = None

        # ---- 第二趟：好档对照（把种下的收走，回到「还没有这份清单」）----
        restore(before)
        # 对照那趟的起点必须是确定的「还没有这份清单」。我自己的清单要是本来就在（哪怕是好的），
        # 这一趟就换成了另一种情形——更糟的是：上一轮要是有哪一次跑崩了、盘上留着一份读不懂的清单，
        # 每拉起一次应用就会又另存一份副本（实测整跑里就是这么把对照那趟弄红的）。
        # 所以这里先把那份临时挪走（字节已经存在 before 里，收场会写回去）。
        clean_start = root / "sessions.json"
        if clean_start.exists():
            try:
                clean_start.unlink()
            except OSError:
                pass
        ctl_before = [p.name for p in broken_copies(root)]
        ctl_port = port or free_port()
        ctl_env = dict(env)
        ctl_env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={ctl_port}"
        proc = popen([str(exe)], cwd=str(exe.parent), env=ctl_env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws2, why2 = _await_webview_page(proc, ctl_port, wait, sleep)
        facts["control_err"] = why2
        facts["control_ok"] = ws2 is not None
        if ws2 is not None:
            deadline = time.time() + wait
            ver2 = ""
            while time.time() < deadline:
                ver2 = str(value(ws2, VER_EXPR) or "").strip()
                if ver2:
                    break
                sleep(0.2)
            if version and ver2 and ver2 != version:
                return SKIP, (f"这份 exe 里的界面是 {ver2}，仓库是 {version}——不是本版构建，"
                              "好档那趟对照没核到")
            if version and not ver2:
                return FAIL, f"好档那趟 {wait:.0f}s 内版本串还没出现——界面没进到本应用"
            sleep(1.5)  # 启动那点异步落地：急救是挂在读清单之后的
            facts["control_new"] = [p.name for p in broken_copies(root)
                                    if p.name not in ctl_before]
    except Exception as e:  # noqa: BLE001 - 连不上就把原因报出来，不许当通过
        err = e
    finally:
        if proc is not None and proc.poll() is None:
            kill(proc.pid)
            sleep(BROKEN_SETTLE)
        # 收场：先删掉测试自己种出来的副本（原本没有，是这一趟写下去的），再按原字节收回三份文件
        for p in broken_copies(root):
            if p.name not in before_copies:
                try:
                    p.unlink()
                except OSError:
                    pass
        restore_bad = restore(before)
        # 还原函数自己说的不算：收完再独立读一遍，跟跑前存的字节逐份对
        try:
            settled = collect()
        except Exception:  # noqa: BLE001 - 量不到就当没收干净
            settled = None
        for name in residue_bad(before, settled):
            if name not in restore_bad:
                restore_bad.append(name)
        left = [p.name for p in broken_copies(root) if p.name not in before_copies]
        for name in left:
            if name not in restore_bad:
                restore_bad.append(name)
        facts["restore_bad"] = restore_bad
    if err is not None:
        return FAIL, f"这一趟没跑成：{err}"
    return broken_store_verdict(facts)


def a43_broken_store_real() -> tuple[str, str]:
    """A43：坏档急救在真 exe + 真后端上真跑一遍，跑完我的盘收得回来吗。"""
    if sys.platform != "win32":
        return SKIP, "只在 Windows 上核（mac / linux 没有 WebView2 这套调试口）"
    exe, kind = find_app_exe(app_exe_dirs())
    if exe is None:
        return SKIP, "还没构建 portio-app.exe（先 npm run build 或 tauri build）"
    status, detail = probe_broken_store(exe, current_version())
    return status, f"{detail}（{kind_label(kind)}）"


def refuse_rmtree(path, ignore_errors=False, onerror=None):
    """探针用：装作删不掉（库文件还被占着的样子）。"""
    raise OSError("文件还被别的进程占着（这是探针故意的）")


def probe_profile_lifecycle(root: Path, now: float | None = None,
                            mkdtemp=tempfile.mkdtemp, sleep=lambda _s: None) -> tuple[str, str]:
    """A44 的探针：在一份自己的临时目录里把建 / 收 / 拦 / 报 / 陈旧清理各走一遍。

    不碰真 profile、不拉窗口，一秒量级；但走的都是整跑里那四个探针用的同一批函数。
    """
    root = Path(root)
    bad: list[str] = []
    far = lambda _p: 9000.0  # noqa: E731 - 盘很空

    # 1) 够就建：建出来得在我的临时目录里，且登记在册
    made = make_profile("portio-rc-", root=root, need_mb=50, mkdtemp=mkdtemp, free=far)
    if made not in CREATED_PROFILES:
        bad.append("建出来的 profile 没登记——收尾盘点时会漏掉它")
    if not made.exists() or made.parent != root:
        bad.append("建出来的 profile 不在我的临时目录里")

    # 2) 收：删干净
    if not release_profile(made, sleep=sleep) or made.exists():
        bad.append("建出来这份没收干净")

    # 3) 盘不够：不建、不许写东西、话里得说清差多少
    before = len(list(root.iterdir()))
    try:
        make_profile("portio-rc-", root=root, need_mb=200, mkdtemp=mkdtemp, free=lambda _p: 20.0)
        bad.append("盘只剩 20 MB 也照样建了 profile（开跑就是把盘顶穿）")
    except TempSpaceShort as e:
        if "差 180 MB" not in str(e):
            bad.append(f"盘不够时没把差多少说清楚：{e}")
    if len(list(root.iterdir())) != before:
        bad.append("盘不够那一次还是往临时目录里写了东西")

    # 4) 删不掉：得判 False、得登记、得点名（以前 ignore_errors 让它一声不响）
    stuck = make_profile("portio-rc-", root=root, need_mb=50, mkdtemp=mkdtemp, free=far)
    LEAKED_PROFILES.clear()
    ok = release_profile(stuck, rmtree=refuse_rmtree, sleep=sleep, tries=2)
    if ok or not stuck.exists():
        bad.append("删不掉的那份被当成了「删掉了」")
    if stuck not in LEAKED_PROFILES:
        bad.append("删不掉却没登记——下一轮盘点又看不见它")
    shutil.rmtree(stuck, ignore_errors=True)  # 探针自己收尾
    LEAKED_PROFILES.clear()

    # 5) 陈旧清理：只清自己的前缀、只清够旧的、不改动同名文件与别人的目录
    stamp = time.time() if now is None else now
    young = root / "portio-rc-young"
    young.mkdir()
    (young / "x").write_bytes(b"x" * 10)
    old = root / "portio-fresh-old"
    old.mkdir()
    (old / "x").write_bytes(b"x" * 4096)
    foreign = root / "other-app-old"
    foreign.mkdir()
    (foreign / "x").write_bytes(b"x" * 4096)
    lone = root / "portio-fresh-file"
    lone.write_bytes(b"not a dir")
    for p in (old, foreign):
        os.utime(p, (stamp - 30 * 3600, stamp - 30 * 3600))
    swept, freed = sweep_stale_profiles(root=root, now=stamp, release=lambda q, **_k: release_profile(q, sleep=sleep))
    if swept != 1:
        bad.append(f"陈旧清理扫到 {swept} 份，应只清掉上一轮留下的那 1 份")
    if old.exists():
        bad.append("超过 6 小时的旧 profile 没被清掉（盘就是这么攒满的）")
    if not young.exists():
        bad.append("刚刚建出来那份被当成陈旧清了——另一个 rc.py 可能正拿着它在跑")
    if not foreign.exists():
        bad.append("把别人前缀的临时目录也清了")
    if not lone.exists():
        bad.append("把同前缀的文件也删了（只该认目录）")
    if swept and freed <= 0:
        bad.append("清掉的东西没算回放回了多少字节")

    if bad:
        return FAIL, "；".join(bad)
    return PASS, (f"盘不够会拦（「差 180 MB」说得出来，也没往里写东西）；建 2 份、收 1 份、"
                  f"删不掉那份判 False 并点名登记；陈旧清理清掉 1 份 / 放回 {freed // 1024} KB，"
                  "放过刚建的那份、别人的目录、同前缀的文件各 1 个")


def a44_profile_lifecycle() -> tuple[str, str]:
    """A44：一次性 profile 自己建、自己删、删不掉要报出来，盘不够先拦。"""
    keep_created, keep_leaked = list(CREATED_PROFILES), list(LEAKED_PROFILES)
    root = Path(tempfile.mkdtemp(prefix="portio-a44-"))
    try:
        return probe_profile_lifecycle(root)
    finally:
        # 探针自己建的别混进整跑的账，否则收尾那行会把它们算成本轮残留
        CREATED_PROFILES[:] = keep_created
        LEAKED_PROFILES[:] = keep_leaked
        shutil.rmtree(root, ignore_errors=True)


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


def write_record(path: Path, results: list[tuple[str, str, str, str]], timings: dict[str, float],
                 exit_code: int, version: str, elapsed: float) -> Path:
    """把这一轮的成绩单落成 JSON（A49 拿它去对清单首部那串数字）。

    以前整跑最后那行「34 通过 / 0 失败 / 12 未验，124.8s，退出码 3」只活在屏幕上，
    抄进 `docs/rc-checklist.md` 首部的那一串是我一个字一个字打进去的——打错一个数字，
    读的人没有任何办法发现。成绩单落盘之后，那串数字才有出处可对。
    summary 不是另写一遍数字，是**从 items 数出来的**：两处对不上就是记错了。
    """
    counts = {s: sum(1 for r in results if r[2] == s) for s in (PASS, FAIL, SKIP)}
    record = {
        "note": ("这一轮整跑的成绩单。逐项状态 / 耗时 / 理由都在 items 里，summary 是从 items 数出来的；"
                 "docs/rc-checklist.md 首部那串数字要对得上它（门禁 A49）。"),
        "version": version,
        "when": datetime.now().astimezone().isoformat(timespec="seconds"),
        "exit": exit_code,
        "summary": {
            "total": len(results),
            "pass": counts[PASS],
            "fail": counts[FAIL],
            "pending": counts[SKIP],
            "seconds": round(elapsed, 1),
        },
        "items": [
            {
                "code": code,
                "status": status,
                "seconds": round(timings.get(code, 0.0), 1),
                "detail": (detail or "").strip(),
            }
            for code, _label, status, detail in results
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Portio 自动化回归（rc-checklist §1）")
    ap.add_argument("--fast", action="store_true", help="跳过 A1 的 cargo test")
    ap.add_argument("--list", action="store_true", help="只列出会跑的项")
    ap.add_argument("--record", metavar="PATH",
                    help="把这一轮的成绩单落成 JSON（逐项状态 / 耗时 / 理由 + 汇总），"
                         "清单首部的数字以后要对得上它；只跑几项时不写")
    ap.add_argument("items", nargs="*", metavar="A<n>",
                    help="只跑这几项，如 A11 或 A10,A11；不写就全跑")
    args = ap.parse_args(argv)

    plan = [
        # A47 有意排在 A1 前头：它是开跑前的产物体检，等编译炸完再看这一格就没意义了
        ("A47", "check_stale_artifacts.py（deps 里 0 字节的空壳产物 / 指纹还挂着的假新鲜 / 超龄 rustc）", True),
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
        ("A48", "交出去的那份就是核的那份（docs/artifacts.json 里这一版那几条：记录自洽、盘上那份字节与 sha256 对得上、包体内版本串是这一版、记录里那个 tag 也真指在写着这一版的提交上、Release 上挂着的大小一字不差）", True),
        ("A35", "回归脚本自己那批单测（scripts/test_*.py 全跑，口径跟 CI 的 discover 一致；一条都没跑到也算红）", True),
        ("A36", "窗口起来了，界面也真画出来了（走 WebView2 调试口进真 webview：加载完没、版本串是不是这一版、app.js 跑完没、终端对象在不在、DOM 有没有肉）", True),
        ("A37", "那几条自检在真窗口里也跑得动（真后端 + 真偏好里跑 split/clip/fold/ctx/find/find-pane/transfer 七条；跑前存下偏好、跑完一字不差写回去）", True),
        ("A38", "会改设置的那批自检也在真窗口里跑（换一份一次性 profile 跑 panes/layout/density/accent/term-theme/boot/perm/font/theme 九条；跑完核我自己的偏好库一个字节没动、底色文件写回原样）", True),
        ("A39", "会写盘的那两条自检也在真窗口 + 真后端里跑（#sessions-test / #hosts-test；跑前把 theme.txt / sessions.json / known_hosts 按字节存下，跑完收进程再按原字节收回、逐字节核对；还要证明会话清单确实落了盘）", True),
        ("A40", "#narrow-test 在真窗口里按 1024 / 900 两档视口跑（调试口改布局视口，两档得一根长连胜跑完；判据拿界面自报的 innerWidth 对我要求的那档，对不上就是拿宽窗冒充窄窗；一次性 profile 里跑，核我自己的偏好库没被动）", True),
        ("A41", "最后两条自检也在真窗口 + 真后端里跑（#net-fail-test / #connect-entry-test；先证明这轮真在我的真偏好与真后端上（Tauri 桥、真偏好、底色对得上、sessions_read 真回话），跑前存下 theme.txt / sessions.json / known_hosts、跑完按原字节收回并独立复量）", True),
        ("A42", "#broken-store-test = BROKEN-STORE-SELFTEST-OK（会话清单读坏时先另存再从头开始：半截写入 / 版本比程序新 / 合法 JSON 但不是清单都算读不懂，好文件与空清单不许被另存；读失败与急救失败各有各的话；坏档之后还存得进新会话）", True),
        ("A43", "坏档急救在真 exe 上真跑一遍（把真 app-data 的 sessions.json 种成半截写入、拉起 release exe，核真后端有没有另存出 .broken-<毫秒>、副本逐字节对得上、原文件没被改写、提示条写清另存成了什么；再拿「还没有这份清单」跑一趟对照，好档一个副本都不许冒；跑完按原字节收回、独立复量）", True),
        ("A44", "一次性 profile 自己建自己删（盘不够先拦、并说清差多少；删不掉要判 False 并点名登记，不许再一声不响；跑前只清自己前缀且够旧的残留：刚建的那份、别人前缀的目录、同前缀的文件都不许动）", True),
        ("A45", "check_changelog.py（每个版本的更新内容能直接贴到 Release：`## [Unreleased]` 在最前、版本标题带日期且能解析、当前版本必须有自己那一节且排最前、那节里不许连续空行 / 不许空行切断续行 / 行尾不留空白、每节都得有白名单子标题；历史小节只查硬伤、不重排）", True),
        ("A46", "check_changelog_facts.py（这一版写的话对得上这一版真改的东西：点到的路径要存在；说改了代码文件就得真在改动集里；提到的门禁编号要在计划表里；新加的门禁要写进更新内容；新增脚本要点名或它上场的门禁被点名；计划表每一项都得有分发分支）", True),
        ("A49", "整跑成绩单与清单首部对表（docs/rc-last-run.json 自洽、版本只许当前或紧挨着的上一版、编号真在计划表且不重复、首部那串数字与它一字不差、未验的每一条都点到名）", True),
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

    if args.record and wanted:
        # 只跑几项还落一份「成绩单」，等于给「整跑过了」那句话递了个假凭据：
        # 清单首部写的是全量整跑，成绩单也得是全量整跑那一份
        print(f"只跑了 {len(plan)} 项，不是整跑：这一份不当成绩单（`--record` 只跟全量一起用）")
        return EXIT_BAD_ID

    node = find_node()
    chrome = find_chrome()
    # 跑前先把上一轮自己留下的 profile 清掉（只认自己的前缀、只认够旧的），
    # 再核一眼盘：不够就别开跑。以前这里直接 mkdtemp，盘满了才在别的步骤炸。
    swept, freed = sweep_stale_profiles()
    try:
        profile = make_profile("portio-rc-")
    except TempSpaceShort as e:
        print("-" * 72)
        print(f"不能开跑：{e}")
        return EXIT_FAIL

    # 版本号：把标题栏 span 读出来，报告头里直接用
    ver = ""
    m = re.search(r'<span class="ver"[^>]*>(.*?)</span>', (UI / "index.html").read_text(encoding="utf-8"))
    if m:
        ver = m.group(1).strip()

    print(f"Portio 自动化回归  v{ver}  ({ROOT})")
    if swept:
        print(f"临时目录：清掉上一轮留下的 {swept} 份 profile，放回 {freed / (1024 * 1024):.1f} MB")
    if wanted:
        print(f"只跑 {len(plan)} 项：{'、'.join(code for code, _, _ in plan)}")
    print("-" * 72)

    results: list[tuple[str, str, str, str]] = []
    timings: dict[str, float] = {}
    started = time.time()
    for code, label, on in plan:
        if not on:
            timings[code] = 0.0
            results.append((code, label, SKIP, "本轮用 --fast 跳过"))
            print(f"[{LABEL[SKIP]}] {code}  {label}  ← --fast")
            continue
        t0 = time.time()
        if code == "A47":
            # 开跑前的产物体检：0 字节的空壳 / 假新鲜指纹 / 超龄 rustc（纯 Python，不编译）
            status, detail = a_script("check_stale_artifacts.py", "产物空壳与假新鲜", skip_exit=4)
        elif code == "A1":
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
        elif code == "A45":
            # 更新内容那一段得是能直接贴到 Release 的形态（纯 Python，不开浏览器）
            status, detail = a_script("check_changelog.py", "更新内容格式")
        elif code == "A46":
            # 形状对还不够：写的话得对得上这一版真改的东西（纯 Python，读 git 的改动集）
            status, detail = a_script("check_changelog_facts.py", "更新内容对得上改动", skip_exit=4)
        elif code == "A49":
            # 清单首部那串数字得是这一跑真跑出来的那份成绩单（纯 Python，读 docs/rc-last-run.json）
            status, detail = a_script("check_rc_record.py", "整跑成绩单对表", skip_exit=4)
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
        elif code == "A48":
            # 交出去的那份有没有记下来、还对不对得上：记录 + 盘上字节/sha256 + 包体内版本串
            status, detail = a_script("check_artifact_manifest.py", "交付物溯源", skip_exit=4)
        elif code == "A35":
            # 回归脚本自己的单测：1s 量级，但以前整跑从没跑过
            status, detail = a35_script_tests()
        elif code == "A36":
            # 进真 webview 读 DOM：拉起、等导航、读一句话、收掉
            status, detail = a36_webview()
        elif code == "A37":
            # 在真窗口里把这七条自检跑一遍，跑完把偏好写回去
            status, detail = a37_selftests()
        elif code == "A38":
            # 会改设置的那批：换一份一次性 profile 跑，跑完核我自己的偏好库没被动
            status, detail = a38_fresh_selftests()
        elif code == "A39":
            # 会写盘的那两条：真窗口 + 真后端，跑前存字节、跑完收回、再读一遍核对
            status, detail = a39_appdata_selftests()
        elif code == "A40":
            # 窄窗那条：真窗口 + 两档视口（一根长连会话里设视口、导航、读标题）
            status, detail = a40_narrow_viewports()
        elif code == "A41":
            # 最后两条：真窗口 + 真后端，先证「真跑在我的真偏好上」，再存/收/核后端三份文件
            status, detail = a41_real_selftests()
        elif code == "A42":
            # 坏掉的清单不许被下一次存盘盖掉：无头里用后端替身跑（真 exe 那一版是 A43）
            status, detail = a_page(chrome, profile, "#broken-store-test", "BROKEN-STORE-SELFTEST-OK")
        elif code == "A43":
            # 坏档急救在真 exe + 真后端上真跑一遍：种半截清单、看副本与原文件、好档对照、收场收回
            status, detail = a43_broken_store_real()
        elif code == "A44":
            # 一次性 profile 自己建自己删：盘不够先拦、删不掉要点名、陈旧清理只认自己的且够旧
            status, detail = a44_profile_lifecycle()
        seconds = time.time() - t0
        timings[code] = seconds
        results.append((code, label, status, detail))
        print(f"[{LABEL[status]}] {code}  {label}  ({seconds:.1f}s)  {detail}")

    # 上一项多半刚跑完无头 Chrome，它的收尾进程还会短暂占着这个目录（实测 3 秒内松手），
    # 所以先歇一下再收：这不是「删不掉」，只是还没松手
    time.sleep(1.2)
    release_profile(profile)
    # 收完再独立数一遍：**本轮自己建的**那几份都该找不着了；留着的就点名，不许静默放过
    # （只认本轮建的，不把另一轮正在跑的那份算成自己的残留）
    left = [p for p in CREATED_PROFILES if p.exists()]

    elapsed = time.time() - started
    code, lines = summarize(results, elapsed)
    print("-" * 72)
    for line in lines:
        print(line)
    print(f"临时目录：本轮建了 {len(CREATED_PROFILES)} 份 profile，"
          f"{'一份都没留下' if not left else f'还留着 {len(left)} 份'}")
    if left:
        for p in left[:6]:
            print(f"  ! 还留着：{p}（{profile_bytes(p) // 1024} KB）")
        if code == EXIT_OK:
            # 盘上留下东西就不算全绿：这一条没有对应编号，但不能让「绿」盖过去
            code = EXIT_FAIL
            print("这一轮自己的临时目录没清干净，按失败算（先看上面那份路径为什么删不掉）")
    if args.record:
        # 成绩单写在最后一步：上面那些收尾如果翻转了退出码，纸面上也得跟着翻
        out = write_record(Path(args.record), results, timings, code, ver, elapsed)
        counts = {s: sum(1 for r in results if r[2] == s) for s in (PASS, FAIL, SKIP)}
        print(f"成绩单：{out}（{len(results)} 项 / {counts[PASS]} 通过 / {counts[FAIL]} 失败 / "
              f"{counts[SKIP]} 未验，退出码 {code}）")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
