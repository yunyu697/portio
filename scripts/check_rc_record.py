#!/usr/bin/env python3
"""整跑的成绩单，和我抄进清单首部的那串数字，现在是同一份了吗（A49）。

上一格（A48）把「交出去的包」接到了记录与 tag 上；可每一轮整跑最后那行
「34 通过 / 0 失败 / 12 未验，124.8s，退出码 3」一直只活在屏幕上。抄进
`docs/rc-checklist.md` 首部的那一串，是我一个字一个字打进去的——打错一个数字，
读的人没有任何办法发现；下一轮整跑再打一遍，错的那串就被对的那串盖过去，
**错的留在纸面上，对的留在屏幕上，两者从此互不相干**。

A49 干的事：让那串数字有出处。`python scripts/rc.py --record docs/rc-last-run.json`
把这一轮整跑落成一份机器读的成绩单，这道门禁拿它去对清单。

1. **成绩单自己得是自洽的**：`summary` 不是另写一遍数字，是从 `items` 数出来的；
   逐项的通过 / 失败 / 未验与汇总对得上、三项之和等于总项数、状态只许 PASS / FAIL / SKIP、
   退出码只许 0 / 1 / 3，而且必须与逐项状态推得出来的一致（有失败退 1；没失败但有未验退 3；
   都没有才退 0）。一条 FAIL 底下写着「0 失败」，就是这张纸在骗人。
2. **不许拿旧成绩单冒充这一轮**：成绩单的版本只许是**当前版本**、或者**紧挨着的上一版**
   （每轮收尾整跑都会重写一份，攒着几版之前那份不动的，说明这一轮压根没整跑就抄了数字）；
   也绝不许写比当前版本还大的版本（那是记了将来）。`when` 得是能解析、且带时区的时刻。
3. **编号得真在计划表里、且不重复**：成绩单上的 `A<n>` 必须是 `scripts/rc.py` 里真有的那一项；
   同一项记两遍，说明这张纸不是一次跑出来的。
4. **清单首部那串数字必须等于成绩单**：项数 / 通过 / 失败 / 未验 / 耗时（一位小数带 `s`）/
   退出码，一处对不上就红。这一条才是这一版真正要立的规矩。
5. **未验的每一条都得在首部点到名**，不许把没核过的那几条从纸面上漏掉；
   清单里说「跳过 A1 / A32」的，成绩单里就不能记着那两项跑过了（说了跳过却记着成绩，
   说明这句话是上一版留下来的）；记成未验、理由里也写着跳过，那算对得上。
   首部那句版本串也得等于成绩单里的版本——两边不许各说各的。

退出码：0 全对得上 / 1 对不上 / 4 没东西可核（成绩单不存在，或者清单首部找不到那段）。

用法：
    python scripts/check_rc_record.py
    python scripts/check_rc_record.py --record docs/rc-last-run.json --checklist docs/rc-checklist.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "docs" / "rc-last-run.json"
CHECKLIST = ROOT / "docs" / "rc-checklist.md"
RC = ROOT / "scripts" / "rc.py"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NOTHING = 4

DOC_MARK = "**最近一次整跑**"
STATUSES = ("PASS", "FAIL", "SKIP")
# 与 scripts/set_version.py 同一套写法
VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
                        r"(?:(?:-(?P<stage>Alpha|RC)(?P<n>\d+)))?$")
STAGE_MAX = 10
# 清单首部那串数字的固定形状：「46 项」…「34 通过 / 0 失败 / 12 未验，124.8s，退出码 3」
TOTAL_RE = re.compile(r"（(\d+) 项")
NUMBERS_RE = re.compile(r"(\d+) 通过 / (\d+) 失败 / (\d+) 未验，([\d.]+)s，退出码 (\d+)")
SKIPPED_RE = re.compile(r"跳过 ([^，。；)\n]+)")
CODE_RE = re.compile(r"A\d+")
PLAN_RE = re.compile(r'\("(A\d+)",')
HEADER_VERSION_RE = re.compile(r"`v([^`]+)`")


def parse_version(text: str) -> tuple[int, int, int, int, int] | None:
    """把版本串拆成可比较的元组：Alpha 排 1、RC 排 2、正式版排 3。"""
    m = VERSION_RE.match((text or "").strip())
    if not m:
        return None
    stage = m.group("stage")
    n = int(m.group("n")) if m.group("n") else 0
    rank = 3 if not stage else (1 if stage == "Alpha" else 2)
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")), rank, n)


def successor(v: tuple[int, int, int, int, int]) -> tuple[int, int, int, int, int] | None:
    """下一格是哪一版：预发布位满 10 进 patch、回到 1；正式版没有下一格。"""
    major, minor, patch, rank, n = v
    if rank == 3:
        return None
    if n >= STAGE_MAX:
        return (major, minor, patch + 1, rank, 1)
    return (major, minor, patch, rank, n + 1)


def current_version(root: Path) -> str:
    """根 `Cargo.toml` 里 `[package]` 那个版本——跟 `set_version.py` 写的是同一处。"""
    text = (Path(root) / "Cargo.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1) if m else ""


def plan_codes(rc_path: Path = RC) -> set[str]:
    """计划表里真有的编号。不 import rc.py：那一下会把它整份模块拉起来。"""
    text = Path(rc_path).read_text(encoding="utf-8")
    return {m.group(1) for m in PLAN_RE.finditer(text)}


def load_record(path: Path) -> tuple[dict | None, str]:
    path = Path(path)
    if not path.exists():
        return None, f"还没有成绩单：{path.name} 不在盘上"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return None, f"成绩单读不出来：{e}"
    if not isinstance(data, dict):
        return None, "成绩单顶层不是一份对象"
    return data, ""


def header_paragraph(text: str) -> str:
    """清单首部那段「最近一次整跑」：从标记行起，到空行 / `>` / `---` / 下一个标题为止。

    那段话是排过版的（一句话会被折成三行），所以核的时候按**去掉换行**的一整串来认。
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(DOC_MARK):
            start = i
            break
    if start is None:
        return ""
    out: list[str] = []
    for line in lines[start:]:
        if out and (not line.strip() or line.lstrip().startswith(">")
                    or line.startswith("---") or line.startswith("## ")):
            break
        out.append(line)
    return "".join(out)


def check_shape(rec: dict) -> list[str]:
    """第 1 条：这张纸自己得说得圆。"""
    items = rec.get("items")
    if not isinstance(items, list) or not items:
        return ["成绩单里没有逐项记录（items 空着），这张纸核不了什么"]
    summary = rec.get("summary")
    if not isinstance(summary, dict):
        return ["成绩单里没有汇总（summary），逐项与汇总无从对照"]

    findings: list[str] = []
    codes = [str(it.get("code") or "") for it in items if isinstance(it, dict)]
    statuses = [str(it.get("status") or "") for it in items if isinstance(it, dict)]
    if len(codes) != len(items):
        findings.append(f"items 里有 {len(items) - len(codes)} 条不是对象")

    unknown = sorted({s for s in statuses if s not in STATUSES})
    if unknown:
        findings.append(f"状态只许 PASS / FAIL / SKIP，成绩单里还有：{'、'.join(unknown)}")

    counts = {s: statuses.count(s) for s in STATUSES}
    for key, status, word in (("pass", "PASS", "通过"), ("fail", "FAIL", "失败"),
                              ("pending", "SKIP", "未验")):
        wrote = summary.get(key)
        if wrote != counts[status]:
            findings.append(f"汇总写「{wrote} 条{word}」，逐项里数出来 {counts[status]} 条")

    total = summary.get("total")
    if total != len(items):
        findings.append(f"汇总说共 {total} 项，items 里是 {len(items)} 条")
    if sum(counts.values()) != total:
        findings.append(f"通过 + 失败 + 未验 = {sum(counts.values())}，跟总项数 {total} 对不上")

    exit_code = rec.get("exit")
    if exit_code not in (EXIT_OK, EXIT_FAIL, 3):
        findings.append(f"退出码只许 0 / 1 / 3，成绩单写的是 {exit_code!r}")
    else:
        want = EXIT_FAIL if counts["FAIL"] else (3 if counts["SKIP"] else EXIT_OK)
        if exit_code != want:
            findings.append(f"退出码写 {exit_code}，按逐项状态该是 {want}"
                            f"（失败 {counts['FAIL']} / 未验 {counts['SKIP']}）")

    seconds = summary.get("seconds")
    if not isinstance(seconds, (int, float)) or seconds < 0:
        findings.append(f"汇总里的耗时不是个数：{seconds!r}")
    for it in items:
        if not isinstance(it, dict):
            continue
        if not isinstance(it.get("seconds"), (int, float)) or it["seconds"] < 0:
            findings.append(f"{it.get('code') or '?'} 那条没有耗时")
    return findings


def check_version(rec: dict, current: str) -> list[str]:
    """第 2 条：不许拿旧成绩单、也不许记将来。"""
    cur = parse_version(current)
    got = parse_version(str(rec.get("version") or ""))
    if got is None:
        return [f"成绩单上的版本 {rec.get('version')!r} 认不出（要 vMAJOR.MINOR.PATCH[-AlphaN|-RCN] 那一套）"]
    if cur is None:
        return [f"根 Cargo.toml 里读不出当前版本（读到 {current!r}）"]

    findings: list[str] = []
    if got > cur:
        findings.append(f"成绩单写的是 {rec.get('version')}，比当前版本 {current} 还新：那是记了将来")
    elif got != cur and successor(got) != cur:
        findings.append(f"成绩单是 {rec.get('version')} 的，眼下是 {current}："
                        f"只许当前这一版或紧挨着的上一版（攒着旧成绩单抄数字，等于这一轮没整跑过）")

    when = rec.get("when")
    try:
        stamp = datetime.fromisoformat(str(when))
    except ValueError:
        findings.append(f"成绩单上的时刻 {when!r} 解析不了")
    else:
        if stamp.tzinfo is None:
            findings.append(f"成绩单上的时刻 {when!r} 没带时区，换台机器看就说不清是哪一刻")
    return findings


def check_codes(rec: dict, known: set[str]) -> list[str]:
    """第 3 条：编号得真在计划表里、且不许记两遍。"""
    if not known:
        return ["rc.py 的计划表里一个编号都没读出来，这一条无从核"]
    codes = [str(it.get("code") or "") for it in rec.get("items") or [] if isinstance(it, dict)]
    findings: list[str] = []
    dup = sorted({c for c in codes if codes.count(c) > 1})
    if dup:
        findings.append(f"同一项记了两遍：{'、'.join(dup)}（一张纸不该是一次跑出来的）")
    unknown = [c for c in codes if c not in known]
    if unknown:
        findings.append(f"成绩单上有计划表里没有的项：{'、'.join(unknown)}")
    return findings


def check_header(rec: dict, flat: str) -> list[str]:
    """第 4 / 5 条：清单首部那串数字与成绩单得是同一份，未验的都得点到名。"""
    summary = rec.get("summary") or {}
    items = [it for it in rec.get("items") or [] if isinstance(it, dict)]
    findings: list[str] = []

    m = NUMBERS_RE.search(flat)
    if not m:
        return ["清单首部那段里找不到「x 通过 / y 失败 / z 未验，t s，退出码 n」这一串："
                "对不上就没得核（那串数字得原样写在首部）"]
    claimed = {"pass": int(m.group(1)), "fail": int(m.group(2)),
               "pending": int(m.group(3)), "seconds": float(m.group(4)),
               "exit": int(m.group(5))}
    for key, word in (("pass", "通过"), ("fail", "失败"), ("pending", "未验")):
        if claimed[key] != summary.get(key):
            findings.append(f"清单首部写 {claimed[key]} 条{word}，成绩单是 {summary.get(key)} 条")
    if round(float(summary.get("seconds") or 0), 1) != claimed["seconds"]:
        findings.append(f"清单首部写 {claimed['seconds']}s，成绩单是 {summary.get('seconds')}s")

    m_total = TOTAL_RE.search(flat)
    if m_total and int(m_total.group(1)) != summary.get("total"):
        findings.append(f"清单首部写 {m_total.group(1)} 项，成绩单是 {summary.get('total')} 项")
    if claimed["exit"] != rec.get("exit"):
        findings.append(f"清单首部写退出码 {claimed['exit']}，成绩单是 {rec.get('exit')}")

    m_ver = HEADER_VERSION_RE.search(flat)
    if m_ver and m_ver.group(1).strip() != str(rec.get("version") or "").strip():
        findings.append(f"清单首部说这是 v{m_ver.group(1)} 的那一跑，成绩单是 "
                        f"{rec.get('version')} 的")

    # 未验的每一条都得在首部点到名：漏一个，读的人就不知道这条没核过
    named = set(CODE_RE.findall(flat))
    pending = [str(it.get("code") or "") for it in items if it.get("status") == "SKIP"]
    missing = [c for c in pending if c not in named]
    if missing:
        findings.append(f"这些未验的没在首部点到名：{'、'.join(missing)}")

    # 说了跳过的那几项，成绩单里不许记着它跑过了
    m_skip = SKIPPED_RE.search(flat)
    if m_skip:
        by_code = {str(it.get("code") or ""): it for it in items}
        for code in CODE_RE.findall(m_skip.group(1)):
            it = by_code.get(code)
            if it and it.get("status") != "SKIP":
                findings.append(f"清单首部说跳过了 {code}，成绩单里却记着它{it.get('status')}")
    return findings


def run(record_path: Path = RECORD, checklist_path: Path = CHECKLIST,
        root: Path = ROOT, rc_path: Path = RC) -> dict:
    """跑一遍五条判据，返回（退出码、发现、备注、统计）。"""
    findings: list[str] = []
    notes: list[str] = []
    stats = {"items": 0, "pending": 0, "version": ""}

    rec, why = load_record(record_path)
    if rec is None:
        return {"code": EXIT_NOTHING, "findings": [why], "notes": [], "stats": stats}

    summary = rec.get("summary") if isinstance(rec.get("summary"), dict) else {}
    stats["version"] = str(rec.get("version") or "")
    stats["items"] = summary.get("total") if isinstance(summary.get("total"), int) else 0
    stats["pending"] = summary.get("pending") if isinstance(summary.get("pending"), int) else 0

    for name, fn, args in (
        ("自洽", check_shape, (rec,)),
        ("版本", check_version, (rec, current_version(root))),
        ("编号", check_codes, (rec, plan_codes(rc_path))),
    ):
        for f in fn(*args):
            findings.append(f"{name}：{f}")

    flat = header_paragraph(Path(checklist_path).read_text(encoding="utf-8"))
    if not flat:
        # 清单那段找不到，只是「这一条没得核」；上面几条真红出来的还得算红
        unverifiable = "清单里找不到「最近一次整跑」那一段：那串数字没有落笔处，这一条没得核"
        if findings:
            return {"code": EXIT_FAIL, "findings": findings, "notes": notes, "stats": stats}
        return {"code": EXIT_NOTHING, "findings": [unverifiable], "notes": notes, "stats": stats}
    for f in check_header(rec, flat):
        findings.append(f"清单首部：{f}")

    code = EXIT_FAIL if findings else EXIT_OK
    if not findings:
        notes.append(f"成绩单 {stats['version']}：{stats['items']} 项 → "
                     f"{summary.get('pass')} 通过 / {summary.get('fail')} 失败 / "
                     f"{stats['pending']} 未验，{summary.get('seconds')}s，退出码 {rec.get('exit')}；"
                     f"清单首部那串数字与它一字不差")
    return {"code": code, "findings": findings, "notes": notes, "stats": stats}


def main(argv: list[str], root: Path = ROOT, rc_path: Path = RC) -> int:
    ap = argparse.ArgumentParser(description="整跑成绩单与清单首部对表（A49）")
    ap.add_argument("--record", default=str(RECORD), help="成绩单 JSON（默认 docs/rc-last-run.json）")
    ap.add_argument("--checklist", default=str(CHECKLIST), help="回归清单（默认 docs/rc-checklist.md）")
    ap.add_argument("--root", default=str(root), help="仓库根（读根 Cargo.toml 的当前版本）")
    args = ap.parse_args(argv)

    res = run(Path(args.record), Path(args.checklist), Path(args.root), rc_path)
    for note in res["notes"]:
        print(f"NOTE {note}")
    for f in res["findings"]:
        print(f"  ! {f}")
    if res["code"] == EXIT_OK:
        print(f"OK {res['notes'][0] if res['notes'] else '对得上'}")
    elif res["code"] == EXIT_NOTHING:
        print("未验：没东西可核（先 python scripts\\rc.py --record docs\\rc-last-run.json 整跑一遍）")
    return res["code"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
