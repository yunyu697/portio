#!/usr/bin/env python3
"""开跑前的产物体检：0 字节的产物 + 还挂着的「新鲜」指纹 = 下一轮的假绿。

2026-11-21 的真事：A1 突然报 `E0463: can't find crate for portio_ssh`，代码一个字没坏。
上一轮 rustc 的 LLVM 被内存顶崩（`0xc0000409`）时，在 `target/debug/deps/` 留下一个
**0 字节**的 `libportio_ssh-<hash>.rmeta`，而 `.fingerprint/portio-ssh-<hash>/` 里的
`invoked.timestamp` 还在——cargo 认为这一格「编过了」，于是 `portio-app` 永远找不着那个 crate，
报出来的却长得像我的代码有问题。这类假绿比一次 OOM 难查得多：它长得像代码问题，其实是产物问题。

三条判据：

1. **零字节产物**：`<target>/<profile>/deps` 里 0 字节的 `.rmeta` / `.rlib` / `.o`——这三种是编译与链接
   要真读进去的东西，不一样长就必然炸；`.d` 这类只记源文件清单的不算（cargo 自己会发现它不对）。
2. **假新鲜**：那个 0 字节产物对应的指纹目录（同名 `<包>-<hash>`，hash 与产物文件名里那段一致）
   里还留着 `invoked.timestamp`——那就是「产物是空的、可 cargo 记着它编完了」。这一条判红并给出
   `cargo clean -p <包>`。指纹没了的那份不判红（cargo 会重编），但也会点名：垃圾该清。
3. **上一轮遗留的 rustc**：还挂着超过 `--rustc-age`（默认 1 小时）的 rustc 进程。单个 crate 编一小时
   在这台机器上只可能是被打断后没退干净的孤儿，它死死占着提交额度——上一轮就是这么崩的。

退出码：0 通过 / 1 判红 / 4 还没编过（找不到 target 目录，没得核——报「未验」，不拿「没查到」冒充「核过」）。

用法：
    python scripts/check_stale_artifacts.py
    python scripts/check_stale_artifacts.py --target-dir D:\\portio-target --profile release
    python scripts/check_stale_artifacts.py --rustc-age 600
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NOTHING = 4

# 这几种产物是编译 / 链接真读进去的：0 字节就一定会炸
ZERO_KINDS = (".rmeta", ".rlib", ".o")
# deps 里库产物的命名：lib<crate_with_underscores>-<16 位 hash>.<ext>
LIB_ARTIFACT = re.compile(r"^lib(?P<crate>[A-Za-z0-9_]+)-(?P<hash>[0-9a-f]{16})(?P<ext>\.rmeta|\.rlib|\.o)$")
# 指纹目录名：<包名>-<同一段 hash>
FINGERPRINT_MARK = "invoked.timestamp"
STALE_RUSTC_SECONDS = 3600
DEFAULT_PROFILE = "debug"


class Zero:
    """一份 0 字节产物，以及它属于哪个包、哪一格。"""

    __slots__ = ("path", "crate", "hash")

    def __init__(self, path: Path, crate: str, hash_: str):
        self.path = path
        self.crate = crate
        self.hash = hash_

    @property
    def pkg(self) -> str:
        """cargo 认的包名是连字符写法：portio_ssh → portio-ssh。"""
        return self.crate.replace("_", "-")


def parse_lib(path: Path) -> tuple[str, str] | None:
    """从 `libportio_ssh-35cc6d31580c4d0f.rmeta` 里拆出（crate, hash）；不是这种命名就 None。"""
    m = LIB_ARTIFACT.match(path.name)
    if not m:
        return None
    return m.group("crate"), m.group("hash")


def zero_artifacts(deps: Path) -> list[Zero]:
    """扫 deps 里的 0 字节产物。认不出命名的也点名——反正它是空的。"""
    hits: list[Zero] = []
    if not deps.is_dir():
        return hits
    for p in sorted(deps.iterdir()):
        if not p.is_file() or p.suffix not in ZERO_KINDS:
            continue
        try:
            if p.stat().st_size:
                continue
        except OSError:
            continue
        parsed = parse_lib(p)
        hits.append(Zero(p, parsed[0] if parsed else "", parsed[1] if parsed else ""))
    return hits


def fresh_fingerprint(profile_dir: Path, zero: Zero) -> Path | None:
    """产物的指纹还挂着吗？挂着就返回那个指纹目录。

    认法：`.fingerprint/<包>-<hash>`，hash 与产物文件名里那段一模一样（实测 cargo 两边同源）。
    目录里得有 `invoked.timestamp` 才算「记下这一格编完了」；只有空目录的不算。
    """
    if not zero.hash:
        return None
    fp = profile_dir / ".fingerprint"
    if not fp.is_dir():
        return None
    for d in fp.iterdir():
        if not d.is_dir() or not d.name.endswith("-" + zero.hash):
            continue
        if (d / FINGERPRINT_MARK).exists():
            return d
    return None


def rustc_processes() -> list[tuple[int, float]] | None:
    """还挂着的 rustc：（pid, 已活了多久）。数不出来就返回 None，不判红也不假装核过。"""
    try:
        if os.name == "nt":
            ps = shutil.which("powershell") or os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
            )
            # 直接在 PowerShell 里算年龄，省得跟 JSON 里的日期格式打交道
            code = (
                "Get-Process -Name rustc -ErrorAction SilentlyContinue | "
                "ForEach-Object { try { \"$($_.Id) $([int]((Get-Date) - $_.StartTime).TotalSeconds)\" } catch {} }"
            )
            proc = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", code],
                                  capture_output=True, text=True, timeout=120)
        else:
            proc = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True,
                                  text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    out = proc.stdout or ""
    if os.name != "nt":
        out = "\n".join(
            f"{ln.split()[0]} {ln.split()[1]}"
            for ln in out.splitlines()[1:]
            if "rustc" in ln and len(ln.split()) >= 2
        )
    found: list[tuple[int, float]] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            found.append((int(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return found


def scan(target_dir: Path, profile: str = DEFAULT_PROFILE, rustc_age: float = STALE_RUSTC_SECONDS,
         rustc_procs: "list[tuple[int, float]] | None | bool" = False) -> dict:
    """扫一个 target 目录，返回 findings（判红）/ notes（该说但不算红）/ stats。

    rustc_procs 可以注入（单测里不真去数进程）：False = 自己去数，None = 数不出来。
    """
    profile_dir = target_dir / profile
    deps = profile_dir / "deps"
    findings: list[str] = []
    notes: list[str] = []
    stats = {"rmeta": 0, "rlib": 0, "o": 0, "fingerprints": 0, "zero": 0, "fresh": 0, "rustc": 0,
             "rustc_old": 0}

    if deps.is_dir():
        for p in deps.iterdir():
            if p.is_file() and p.suffix in ZERO_KINDS:
                stats[p.suffix.lstrip(".")] += 1
    fp = profile_dir / ".fingerprint"
    if fp.is_dir():
        stats["fingerprints"] = sum(1 for d in fp.iterdir() if d.is_dir())

    zeroes = zero_artifacts(deps)
    stats["zero"] = len(zeroes)
    fresh: list[tuple[Zero, Path]] = []
    for z in zeroes:
        d = fresh_fingerprint(profile_dir, z)
        if d:
            fresh.append((z, d))
            findings.append(
                f"{profile}/deps/{z.path.name} 是 0 字节，可 {profile}/.fingerprint/{d.name} 还记着它编完了"
                f"（cargo 会认为这一格新鲜、不重编）——先清掉它：cargo clean -p {z.pkg or z.crate or '?'}"
            )
        else:
            notes.append(f"{profile}/deps/{z.path.name} 是 0 字节（指纹已经没了，cargo 会重编；这份垃圾顺手删掉）")
    stats["fresh"] = len(fresh)

    procs = rustc_processes() if rustc_procs is False else rustc_procs
    if procs is None:
        notes.append("rustc 进程没数成（这台机器上枚举失败），这条判据这轮没核")
    else:
        old = [p for p in procs if p[1] >= rustc_age]
        stats["rustc"] = len(procs)
        stats["rustc_old"] = len(old)
        for pid, age in old:
            findings.append(
                f"有个 rustc（pid {pid}）已经挂了 {age / 60:.0f} 分钟——上一轮被打断没退干净的孤儿，"
                "它白占着提交额度；先确认不是正在跑的那一轮，再结束它"
            )
    return {"findings": findings, "notes": notes, "stats": stats}


def target_dirs(argv_value: list[str] | None = None) -> list[Path]:
    """候选 target 根：命令行 > CARGO_TARGET_DIR > 仓库里的 target。"""
    if argv_value:
        return [Path(p) for p in argv_value]
    roots = [ROOT / "target"]
    env = os.environ.get("CARGO_TARGET_DIR")
    if env:
        roots.insert(0, Path(env))
    return roots


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="开跑前的产物体检（rc-checklist A47）")
    ap.add_argument("--target-dir", action="append", metavar="PATH",
                    help="target 根目录，可给多次；默认 CARGO_TARGET_DIR，再退到仓库里的 target")
    ap.add_argument("--profile", default=DEFAULT_PROFILE, help="哪一档构建（默认 debug）")
    ap.add_argument("--rustc-age", type=float, default=STALE_RUSTC_SECONDS,
                    help="rustc 挂多久算孤儿（秒，默认 3600）")
    args = ap.parse_args(argv)

    roots = target_dirs(args.target_dir)
    live = [r for r in roots if r.is_dir()]
    if not live:
        print(f"还没编过：{'、'.join(str(r) for r in roots)} 都不存在，没有产物可陈旧"
              "（首次编译，这一条没得核）")
        return EXIT_NOTHING

    result = {"findings": [], "notes": [], "stats": {k: 0 for k in
              ("rmeta", "rlib", "o", "fingerprints", "zero", "fresh", "rustc", "rustc_old")}}
    scanned: list[str] = []
    for r in live:
        one = scan(r, args.profile, args.rustc_age)
        for k, v in one["stats"].items():
            result["stats"][k] = result["stats"].get(k, 0) + v
        result["findings"] += [f"{r}：{msg}" for msg in one["findings"]]
        result["notes"] += [f"{r}：{msg}" for msg in one["notes"]]
        scanned.append(f"{r}\\{args.profile}")

    for msg in result["findings"]:
        print(f"FAIL {msg}")
    for msg in result["notes"]:
        print(f"NOTE {msg}")

    s = result["stats"]
    head = (f"{'、'.join(scanned)}：{s['rmeta']} 个 rmeta / {s['rlib']} 个 rlib / {s['o']} 个 .o，"
            f"指纹 {s['fingerprints']} 份")
    if result["findings"]:
        print(f"FAIL {head}；0 字节产物 {s['zero']} 份（其中 {s['fresh']} 份还挂着新鲜指纹），"
              f"超龄 rustc {s.get('rustc_old', 0)} 个——先按上面点名的那几份清干净再编")
        return EXIT_FAIL
    extra = f"，0 字节产物 {s['zero']} 份" if s["zero"] else ""
    tail = (f"；还挂着的 rustc {s.get('rustc', 0)} 个，没有一个超过 {args.rustc_age / 60:.0f} 分钟"
            if s.get("rustc") else "；没有还挂着的 rustc")
    print(f"OK {head}，没有一个空壳产物或假新鲜指纹{extra}{tail}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
