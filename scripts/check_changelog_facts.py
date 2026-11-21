#!/usr/bin/env python3
"""核对「这一版写的话」跟「这一版真改的东西」对不对得上。

A45 管的是形状：顺序、日期、排版、子标题——一段话写成七截碎段它会红，可它管不了内容。
我完全可以把一句「我把 X 修了」写得漂漂亮亮，而这一版的代码里压根没动过 X：读的人看不出，
我自己事后也看不出。所以补这一半，六条判据：

1. 小节里点到的仓库路径得真在仓库里——`scripts/check_site.py` 写成 `check_sites.py`，读的人点开是空；
2. 写了「改 / 修 / 加了某个代码文件」时，那个文件得真在这一版的改动集里；
3. 提到门禁编号（A45、A46…）时，`rc.py` 的计划表里得真有这一项，不许提一个不存在的编号；
4. 反过来，这一版在 `rc.py` 里新冒出来的编号，必须写进这一版的更新内容——加了门禁不吭声，
   读的人就不知道多了这道闸；
5. 这一版新增的脚本（`scripts/*.py`，单测 `test_*` 除外）必须在更新内容里点名，或者它上场的那道门禁
   被点名——脚本悄悄多出来而更新内容一字不提，是最常见的漏项；
6. 计划表里写「这一项会跑」的，分发处就得有对应分支，否则一跑就炸。

「这一版」= 版本号严格小于当前版本的那个最大的 `v*` tag 到工作区（含未提交改动），
所以提交前跑、提交后跑、打完 tag 再跑，三种时候都对得上。
本地没有更早的 tag（浅克隆 / 还没打过 tag）就报**未验**（退出码 4），不拿「没查到问题」冒充「核过了」。

用法：
    python scripts/check_changelog_facts.py
    python scripts/check_changelog_facts.py --tag v1.0.10-RC1   # 指定对照的上一版（默认自动找）
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_changelog as cc  # noqa: E402
from version import VersionError, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RC_SCRIPT = ROOT / "scripts" / "rc.py"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_UNVERIFIED = 4

# 反引号里这么多字数以上、带斜杠、首段是个真目录，才算「点了一个仓库路径」
TOKEN_MIN, TOKEN_MAX = 2, 80
# `.py` 这类才要求「真动过」；`.md` / `.png` 只要求存在（文档提一句参考资料很正常）
CODE_SUFFIXES = (".py", ".rs", ".js", ".css", ".html", ".toml", ".json", ".yml", ".yaml")
# 判断「这句话是不是在声称改了它」的动词；窗口窄一点，免得隔壁从句里的动词把判据带偏
CHANGE_VERBS = (
    "改", "修", "加", "删", "重写", "换成", "换", "挪", "补", "拆", "重排", "重出", "抽",
)
VERB_WINDOW_BEFORE, VERB_WINDOW_AFTER = 48, 16
# 这些目录里的东西不算「我点名的仓库路径」
SKIP_SEGMENTS = {".git", "node_modules", "target", "__pycache__"}

GATE_REF = re.compile(r"\bA(\d{1,2})\b")
# 计划表一行：("A1", "标签", 开关)，开关可能是 `True` / `False`，也可能是 `not args.fast`
PLAN_ROW = re.compile(r'^\s*\("(A\d+)",\s*"(.*)",\s*([^,)]+)\),?\s*$', re.M)
# 分发处第一支是 `if code ==`，后面才是 `elif code ==`——只认 elif 会把 A1 判成没有分支
DISPATCH = re.compile(r'(?:if|elif)\s+code\s*==\s*"(A\d+)"')
SCRIPT_IN_LABEL = re.compile(r"([A-Za-z0-9_]+\.py)")


class Facts:
    """核这一节要用到的外部事实，攒成一个对象，好单测（单测里不碰 git）。"""

    def __init__(self, *, top_dirs: set[str], exists, changed: set[str], added: set[str],
                 codes_now: set[str], codes_prev: set[str], dispatch: set[str],
                 plan_scripts: dict[str, set[str]]):
        self.top_dirs = top_dirs
        self.exists = exists
        self.changed = changed
        self.added = added
        self.codes_now = codes_now
        self.codes_prev = codes_prev
        self.dispatch = dispatch
        self.plan_scripts = plan_scripts


def extract_paths(text: str, top_dirs: set[str]) -> list[str]:
    """把反引号里像仓库路径的词挑出来（去重、保持出现次序）。"""
    found: list[str] = []
    for tok in re.findall(r"`([^`\n]*)`", text):
        tok = tok.strip()
        if not (TOKEN_MIN <= len(tok) <= TOKEN_MAX) or "/" not in tok:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.\-/]+", tok):
            continue
        segs = [s for s in tok.split("/") if s not in ("", ".")]
        if not segs or any(s in SKIP_SEGMENTS for s in segs) or ".." in segs:
            continue
        if segs[0] not in top_dirs:  # 首段不是仓库里的一级目录，就不算「点了一个文件」
            continue
        norm = "/".join(segs)
        if norm not in found:
            found.append(norm)
    return found


def claims_change(flat: str, path: str) -> bool:
    """这句话里有没有在「改 / 修 / 加」它。flat 是小节正文拼成的一行（折行会断句子）。"""
    start = 0
    while True:
        idx = flat.find(path, start)
        if idx < 0:
            return False
        window = flat[max(0, idx - VERB_WINDOW_BEFORE): idx + len(path) + VERB_WINDOW_AFTER]
        if any(v in window for v in CHANGE_VERBS):
            return True
        start = idx + 1


def mentioned_gates(text: str) -> set[str]:
    return {f"A{m.group(1)}" for m in GATE_REF.finditer(text)}


def check_text(body_text: str, facts: Facts) -> list[str]:
    """把当前版本的更新内容过一遍，返回所有问题；空列表就是通过。"""
    problems: list[str] = []
    flat = re.sub(r"\s+", " ", body_text)

    # 1 / 2：点到的路径得存在；点了代码文件又说改了，就得真改过。
    for path in extract_paths(body_text, facts.top_dirs):
        if not facts.exists(path):
            problems.append(
                f"更新内容里点的 `{path}` 在仓库里不存在——路径写错了，或者这一版还没把它提交进来"
            )
            continue
        if not path.lower().endswith(CODE_SUFFIXES):
            continue
        if claims_change(flat, path) and path not in facts.changed:
            problems.append(
                f"更新内容里说改了 `{path}`，可这一版的改动里没有它——"
                "要么这一版真没动它、别写成改了它；要么把它补进这一版"
            )

    gates = mentioned_gates(body_text)

    # 3：提到的门禁编号得真在计划表里。
    for gate in sorted(gates, key=lambda g: int(g[1:])):
        if gate not in facts.codes_now:
            problems.append(f"更新内容提到门禁 {gate}，可 `rc.py` 的计划表里没有这一项")

    # 4：这一版新加的门禁，得写进这一版的更新内容。
    for gate in sorted(facts.codes_now - facts.codes_prev, key=lambda g: int(g[1:])):
        if gate not in gates:
            problems.append(
                f"这一版往 `rc.py` 里加了门禁 {gate}，更新内容里一个字没提——"
                "加了道闸不吭声，读的人不知道"
            )

    # 5：新增的脚本（单测除外）要么被点名，要么它上场的那道门禁被点名。
    for path in sorted(p for p in facts.added if is_new_script(p)):
        name = Path(path).name
        if path in extract_paths(body_text, facts.top_dirs) or name in body_text:
            continue
        owners = {code for code, scripts in facts.plan_scripts.items() if name in scripts}
        if owners & gates:
            continue
        where = f"（它上场的是 {'、'.join(sorted(owners))}）" if owners else ""
        problems.append(
            f"这一版新增了 `{path}`，更新内容里没点名{where}——新加的脚本得交代一句它在做什么"
        )

    # 6：计划表说会跑的，分发处得有分支。
    for gate in sorted(facts.codes_now, key=lambda g: int(g[1:])):
        if gate not in facts.dispatch:
            problems.append(
                f"`rc.py` 计划表里有 {gate}，分发处却没有 `elif code == \"{gate}\"` 分支——"
                "列出来会跑、跑起来没这一支，绿的就不是真绿"
            )

    return problems


def is_new_script(path: str) -> bool:
    """这一版新增的脚本：`scripts/*.py`，单测不算（单测跟着主脚本一起提就够了）。"""
    if not (path.startswith("scripts/") and path.endswith(".py")):
        return False
    return not Path(path).name.startswith("test_")


# ---------- git 与 rc.py 的事实收集 -----------------------------------------

def find_git() -> str | None:
    """git 装哪儿不固定（本机在 Program Files），所以三处都看：环境变量、PATH、默认路径。"""
    env = os.environ.get("PORTIO_GIT")
    if env and Path(env).exists():
        return env
    found = shutil.which("git")
    if found:
        return found
    cand = Path(r"C:\Program Files\Git\cmd\git.exe")
    return str(cand) if cand.exists() else None


def git(git_bin: str, *args: str, timeout: int = 60) -> str:
    proc = subprocess.run(
        [git_bin, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise GitError((proc.stderr or "").strip() or f"git {' '.join(args)} 失败")
    return proc.stdout


class GitError(RuntimeError):
    pass


def version_key(text: str) -> tuple[int, int, int, int, int]:
    """比大小用：正式版 > RC > Alpha，同阶段比计数。"""
    major, minor, patch, stage, counter = parse(text)
    rank = 2 if stage is None else (1 if stage == "RC" else 0)
    return major, minor, patch, rank, counter


def previous_tag(git_bin: str, current: str) -> str | None:
    """版本号严格小于当前版本的那个最大的 v* tag —— 就是「上一版」。"""
    cur = version_key(current)
    best: tuple[tuple[int, int, int, int, int], str] | None = None
    for line in git(git_bin, "tag", "-l", "v*").splitlines():
        tag = line.strip()
        if not tag:
            continue
        try:
            key = version_key(tag.lstrip("v"))
        except VersionError:
            continue
        if key >= cur:
            continue  # 自己这一版的 tag、或比它新的，都不算上一版
        if best is None or key > best[0]:
            best = (key, tag)
    return best[1] if best else None


def changed_files(git_bin: str, tag: str) -> tuple[set[str], set[str]]:
    """「这一版改了什么」：tag 到工作区（含未提交、含新增未跟踪的文件）。"""
    changed = sorted({ln.strip() for ln in git(git_bin, "diff", "--name-only", tag).splitlines() if ln.strip()})
    untracked = sorted({
        ln.strip() for ln in git(git_bin, "ls-files", "--others", "--exclude-standard").splitlines() if ln.strip()
    })
    added = {
        ln.strip() for ln in git(git_bin, "diff", "--name-only", "--diff-filter=A", tag).splitlines() if ln.strip()
    }
    return set(changed) | set(untracked), added | set(untracked)


def parse_plan(src: str) -> tuple[set[str], dict[str, set[str]]]:
    """计划表里的编号，以及每一项的标签里点到的脚本（`check_changelog.py` 这种）。"""
    codes: set[str] = set()
    scripts: dict[str, set[str]] = {}
    for code, label, _on in PLAN_ROW.findall(src):
        codes.add(code)
        named = set(SCRIPT_IN_LABEL.findall(label))
        if named:
            scripts.setdefault(code, set()).update(named)
    return codes, scripts


def parse_dispatch(src: str) -> set[str]:
    return set(DISPATCH.findall(src))


def main(argv: list[str]) -> int:
    current = cc.read_current_version()
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = [s for s in cc.split_sections(text) if s[1] == current]
    if not sections:
        print(f"CHANGELOG 里找不到「{current}」那一节，无从对照（这一条 A45 管）")
        return EXIT_UNVERIFIED
    body = "\n".join(ln for _i, ln in sections[0][3])

    git_bin = find_git()
    if not git_bin:
        print("找不到 git，没法算「这一版改了什么」")
        return EXIT_UNVERIFIED

    if "--tag" in argv:
        tag = argv[argv.index("--tag") + 1]
        try:
            git(git_bin, "rev-parse", "--verify", f"refs/tags/{tag}")
        except (GitError, IndexError):
            print(f"指定的对照 tag「{tag}」本地没有")
            return EXIT_UNVERIFIED
    else:
        tag = previous_tag(git_bin, current)
        if not tag:
            print(f"本地没有比 v{current} 更早的 v* tag（浅克隆 / 还没打过 tag），这一轮没得比")
            return EXIT_UNVERIFIED

    try:
        changed, added = changed_files(git_bin, tag)
        rc_now = RC_SCRIPT.read_text(encoding="utf-8")
        rc_prev = git(git_bin, "show", f"{tag}:scripts/rc.py")
    except (GitError, OSError, subprocess.SubprocessError) as e:
        print(f"算不出这一版的改动集：{e}")
        return EXIT_UNVERIFIED

    codes_now, plan_scripts = parse_plan(rc_now)
    codes_prev, _ = parse_plan(rc_prev)
    top_dirs = {d.name for d in ROOT.iterdir() if d.is_dir()}

    facts = Facts(
        top_dirs=top_dirs,
        exists=lambda p: (ROOT / p).exists(),
        changed=changed,
        added=added,
        codes_now=codes_now,
        codes_prev=codes_prev,
        dispatch=parse_dispatch(rc_now),
        plan_scripts=plan_scripts,
    )

    problems = check_text(body, facts)
    if problems:
        print(f"「{current}」这段更新内容跟这一版改的东西对不上：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return EXIT_FAIL

    print(
        f"OK 「{current}」对得上这一版的改动（对照 {tag}：{len(changed)} 个文件有改动、"
        f"新增 {len(added)} 个；门禁 {len(codes_now)} 项都对得上分发处）"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
