#!/usr/bin/env python3
"""A49 单测：整跑成绩单与清单首部对表。

判据都是「两份纸面上的东西对不对得上」，夹具全在临时目录里搭：一份成绩单 JSON、
一份清单的骨架（含「最近一次整跑」那段会折行的排法）、一份只放计划表的 rc.py。
不读真仓库、不跑真回归。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_rc_record as crr  # noqa: E402

CUR = "1.0.10-RC7"
PREV = "1.0.10-RC6"
WHEN = "2026-11-21T11:20:00+08:00"


def write_root(root: Path, version: str = CUR) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Cargo.toml").write_text(
        f'[workspace]\nmembers = []\n\n[package]\nname = "portio"\nversion = "{version}"\n',
        encoding="utf-8")
    return root


def write_rc(root: Path, codes: tuple[str, ...] = ("A1", "A2", "A3", "A10")) -> Path:
    """只放一张计划表——够 plan_codes 抓编号，不用真跑。"""
    p = root / "scripts" / "rc.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "plan = [\n" + "".join(f'    ("{c}", "说明", True),\n' for c in codes) + "]\n"
    p.write_text(body, encoding="utf-8")
    return p


def item(code: str, status: str = "PASS", seconds: float = 1.0, detail: str = "") -> dict:
    return {"code": code, "status": status, "seconds": seconds, "detail": detail}


def counts_of(items: list[dict]) -> dict:
    return {s: sum(1 for it in items if it["status"] == s) for s in ("PASS", "FAIL", "SKIP")}


def record(items: list[dict], *, version: str = CUR, exit_code: int | None = None,
           when: str = WHEN, summary: dict | None = None) -> dict:
    """按 items 算出汇总与退出码；要测「纸面撒谎」时把 summary / exit_code 传进来盖掉。"""
    c = counts_of(items)
    if exit_code is None:
        exit_code = 1 if c["FAIL"] else (3 if c["SKIP"] else 0)
    if summary is None:
        summary = {"total": len(items), "pass": c["PASS"], "fail": c["FAIL"],
                   "pending": c["SKIP"], "seconds": 12.3}
    return {"version": version, "when": when, "exit": exit_code, "summary": summary,
            "items": items}


def checklist(*, total: int, passed: int, failed: int, pending: int, seconds: str, exit_code: int,
              version: str = CUR, pending_codes: tuple[str, ...] = (), skipped: tuple[str, ...] = (),
              numbers: str | None = None) -> str:
    """照真清单的排法拼一段：一句话折成三行，中间夹一条说明与一个 `>` 行。"""
    tail = ""
    if pending_codes:
        tail = f"未验的是 {' / '.join(pending_codes)} 这几条，如实记下。"
    skip_note = f"，跳过 {' / '.join(skipped)}" if skipped else ""
    line2 = numbers if numbers is not None else \
        f"{passed} 通过 / {failed} 失败 / {pending} 未验，{seconds}s，退出码 {exit_code}"
    return (
        "# Portio RC 回归清单\n\n"
        "**状态口径**\n\n| 记号 | 含义 |\n|---|---|\n\n"
        "**最近一次整跑**：2026-11-21 · `v" + version + "` · `python scripts\\rc.py`（" +
        f"{total} 项{skip_note}）→ **\n" +
        line2 + "**。这一版收的是那句话。\n" + tail + "\n"
        "> 谁先有空，一次点完最好。\n"
    )


def make_fixture(tmp: Path, *, items=None, rec=None, header=None,
                 plan_codes_=("A1", "A2", "A3", "A10"),
                 version: str = CUR) -> tuple[Path, Path, Path, Path]:
    root = write_root(tmp / "portio", version)
    rc_path = write_rc(root, plan_codes_)
    items = items if items is not None else [item("A1"), item("A2"), item("A10", "SKIP", 0.0, "缺包")]
    rec = rec if rec is not None else record(items)
    record_path = root / "docs" / "rc-last-run.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    c = counts_of(rec["items"])
    header = header if header is not None else checklist(
        total=len(rec["items"]), passed=c["PASS"], failed=c["FAIL"], pending=c["SKIP"],
        seconds=f"{rec['summary']['seconds']:.1f}", exit_code=rec["exit"], version=rec["version"],
        pending_codes=tuple(it["code"] for it in rec["items"] if it["status"] == "SKIP"))
    checklist_path = root / "docs" / "rc-checklist.md"
    checklist_path.write_text(header, encoding="utf-8")
    return root, record_path, checklist_path, rc_path


class VersionTest(unittest.TestCase):
    def test_parse_alpha_rc_final(self):
        self.assertEqual(crr.parse_version("1.0.10-Alpha3"), (1, 0, 10, 1, 3))
        self.assertEqual(crr.parse_version("1.0.10-RC7"), (1, 0, 10, 2, 7))
        self.assertEqual(crr.parse_version("1.0.10"), (1, 0, 10, 3, 0))
        self.assertIsNone(crr.parse_version("1.0.10-Beta2"))
        self.assertIsNone(crr.parse_version(""))

    def test_successor_steps_stage(self):
        self.assertEqual(crr.successor((1, 0, 10, 2, 6)), (1, 0, 10, 2, 7))
        self.assertEqual(crr.successor((1, 0, 10, 1, 3)), (1, 0, 10, 1, 4))

    def test_successor_at_ten_goes_patch_and_back_to_one(self):
        # 满 10 进 patch、再回 1：RC10 的下一格是 1.0.11-RC1
        self.assertEqual(crr.successor((1, 0, 10, 2, 10)), (1, 0, 11, 2, 1))
        self.assertEqual(crr.successor((1, 0, 10, 1, 10)), (1, 0, 11, 1, 1))

    def test_successor_of_final_is_none(self):
        self.assertIsNone(crr.successor((1, 0, 10, 3, 0)))

    def test_current_version_reads_package_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = write_root(Path(td) / "portio", "1.0.10-RC7")
            self.assertEqual(crr.current_version(root), "1.0.10-RC7")


class ShapeTest(unittest.TestCase):
    """第 1 条：这张纸自己得说得圆。"""

    def test_clean_record_has_no_findings(self):
        self.assertEqual(crr.check_shape(record([item("A1"), item("A2")])), [])

    def test_fail_count_hidden(self):
        items = [item("A1"), item("A2", "FAIL")]
        rec = record(items, summary={"total": 2, "pass": 2, "fail": 0, "pending": 0, "seconds": 1.0})
        out = crr.check_shape(rec)
        self.assertTrue(any("失败" in f for f in out), out)

    def test_total_mismatch(self):
        rec = record([item("A1")], summary={"total": 3, "pass": 1, "fail": 0, "pending": 0,
                                           "seconds": 1.0})
        out = crr.check_shape(rec)
        self.assertTrue(any("共 3 项" in f for f in out), out)

    def test_status_whitelist(self):
        out = crr.check_shape(record([item("A1", "OK")]))
        self.assertTrue(any("PASS / FAIL / SKIP" in f for f in out), out)

    def test_exit_must_follow_items(self):
        # 纸上写着 0 失败、退出码 0，可逐项里有一条 FAIL——这正是「0 失败」最容易骗人的地方
        rec = record([item("A1", "FAIL")], exit_code=0)
        out = crr.check_shape(rec)
        self.assertTrue(any("退出码写 0" in f for f in out), out)

    def test_pending_forces_exit_three(self):
        rec = record([item("A1", "SKIP")], exit_code=0)
        out = crr.check_shape(rec)
        self.assertTrue(any("该是 3" in f for f in out), out)

    def test_empty_items(self):
        out = crr.check_shape(record([]))
        self.assertTrue(any("items 空着" in f for f in out), out)


class VersionCheckTest(unittest.TestCase):
    """第 2 条：不许拿旧成绩单、也不许记将来。"""

    def test_same_version(self):
        self.assertEqual(crr.check_version(record([item("A1")]), CUR), [])

    def test_previous_version_still_counts(self):
        # 版本刚进位、这一轮的整跑还没重写成绩单，上一版那份是合法的
        self.assertEqual(crr.check_version(record([item("A1")], version=PREV), CUR), [])

    def test_two_versions_back_reds(self):
        out = crr.check_version(record([item("A1")], version="1.0.10-RC5"), CUR)
        self.assertTrue(any("紧挨着的上一版" in f for f in out), out)

    def test_future_version_reds(self):
        out = crr.check_version(record([item("A1")], version="1.0.10-RC8"), CUR)
        self.assertTrue(any("记了将来" in f for f in out), out)

    def test_naive_timestamp_reds(self):
        out = crr.check_version(record([item("A1")], when="2026-11-21T11:20:00"), CUR)
        self.assertTrue(any("时区" in f for f in out), out)

    def test_unparsable_timestamp_reds(self):
        out = crr.check_version(record([item("A1")], when="昨天下午"), CUR)
        self.assertTrue(any("解析不了" in f for f in out), out)

    def test_bad_version_string(self):
        out = crr.check_version(record([item("A1")], version="RC7"), CUR)
        self.assertTrue(any("认不出" in f for f in out), out)


class CodesTest(unittest.TestCase):
    """第 3 条：编号得真在计划表里、且不许记两遍。"""

    def test_known_codes(self):
        self.assertEqual(crr.check_codes(record([item("A1"), item("A10")]), {"A1", "A10"}), [])

    def test_unknown_code(self):
        out = crr.check_codes(record([item("A99")]), {"A1"})
        self.assertTrue(any("计划表里没有" in f for f in out), out)

    def test_duplicate_code(self):
        out = crr.check_codes(record([item("A1"), item("A1")]), {"A1", "A2"})
        self.assertTrue(any("记了两遍" in f for f in out), out)

    def test_empty_plan_is_a_finding(self):
        out = crr.check_codes(record([item("A1")]), set())
        self.assertTrue(any("一个编号都没读出来" in f for f in out), out)


class HeaderTest(unittest.TestCase):
    """第 4 / 5 条：清单首部与成绩单得是同一份。"""

    def _check(self, items=None, *, header=None, rec=None):
        rec = rec or record(items or [item("A1"), item("A2", "SKIP", 0.0, "缺包")])
        c = counts_of(rec["items"])
        hdr = header if header is not None else checklist(
            total=len(rec["items"]), passed=c["PASS"], failed=c["FAIL"], pending=c["SKIP"],
            seconds=f"{rec['summary']['seconds']:.1f}", exit_code=rec["exit"],
            pending_codes=tuple(it["code"] for it in rec["items"] if it["status"] == "SKIP"))
        return crr.check_header(rec, crr.header_paragraph(hdr))

    def test_matching_header(self):
        self.assertEqual(self._check(), [])

    def test_pass_count_differs(self):
        items = [item("A1"), item("A2", "SKIP", 0.0, "缺包")]
        out = self._check(items, header=checklist(total=2, passed=2, failed=0, pending=1,
                                                 seconds="12.3", exit_code=3, pending_codes=("A2",)))
        self.assertTrue(any("2 条通过" in f for f in out), out)

    def test_seconds_differs(self):
        items = [item("A1"), item("A2", "SKIP", 0.0, "缺包")]
        out = self._check(items, header=checklist(total=2, passed=2, failed=0, pending=1,
                                                 seconds="124.8", exit_code=3, pending_codes=("A2",)))
        self.assertTrue(any("124.8s" in f for f in out), out)

    def test_total_differs(self):
        items = [item("A1"), item("A2", "SKIP", 0.0, "缺包")]
        out = self._check(items, header=checklist(total=46, passed=2, failed=0, pending=1,
                                                 seconds="12.3", exit_code=3, pending_codes=("A2",)))
        self.assertTrue(any("46 项" in f for f in out), out)

    def test_pending_not_named(self):
        items = [item("A1"), item("A2", "SKIP", 0.0, "缺包")]
        out = self._check(items, header=checklist(total=2, passed=2, failed=0, pending=1,
                                                 seconds="12.3", exit_code=3))
        self.assertTrue(any("没在首部点到名" in f and "A2" in f for f in out), out)

    def test_claimed_skip_but_recorded_pass(self):
        items = [item("A1", "PASS")]
        rec = record(items)
        out = self._check(items, rec=rec, header=checklist(
            total=1, passed=1, failed=0, pending=0, seconds="12.3", exit_code=0,
            skipped=("A1",)))
        self.assertTrue(any("跳过了 A1" in f for f in out), out)

    def test_claimed_skip_and_recorded_skip_is_fine(self):
        # 清单说跳过、成绩单记成未验并写着理由——这是「--fast 跳过」那条路，算对得上
        items = [item("A1", "SKIP", 0.0, "本轮用 --fast 跳过")]
        out = self._check(items, header=checklist(
            total=1, passed=0, failed=0, pending=1, seconds="12.3", exit_code=3,
            skipped=("A1",), pending_codes=("A1",)))
        self.assertEqual(out, [])

    def test_version_mismatch(self):
        items = [item("A1"), item("A2", "SKIP", 0.0, "缺包")]
        out = self._check(items, header=checklist(total=2, passed=2, failed=0, pending=1,
                                                 seconds="12.3", exit_code=3, pending_codes=("A2",),
                                                 version="1.0.10-RC6"))
        self.assertTrue(any("RC6" in f and "1.0.10-RC7" in f for f in out), out)

    def test_numbers_line_missing(self):
        items = [item("A1"), item("A2", "SKIP", 0.0, "缺包")]
        out = self._check(items, header=checklist(total=2, passed=2, failed=0, pending=1,
                                                 seconds="12.3", exit_code=3, pending_codes=("A2",),
                                                 numbers="全都过了，放心"))
        self.assertTrue(any("找不到" in f for f in out), out)


class RunTest(unittest.TestCase):
    """整条路：搭一份「仓库 + 成绩单 + 清单」跑一遍。"""

    def test_clean_everything(self):
        with tempfile.TemporaryDirectory() as td:
            root, rec, chk, rc_path = make_fixture(Path(td))
            res = crr.run(rec, chk, root, rc_path)
            self.assertEqual(res["code"], 0, res["findings"])
            self.assertIn(CUR, res["notes"][0])
            self.assertEqual(res["stats"]["items"], 3)

    def test_missing_record_is_nothing_to_check(self):
        with tempfile.TemporaryDirectory() as td:
            root, rec, chk, rc_path = make_fixture(Path(td))
            rec.unlink()
            res = crr.run(rec, chk, root, rc_path)
            self.assertEqual(res["code"], 4, res["findings"])

    def test_header_stripped_still_reports_hard_findings(self):
        # 清单那段被删了，只是「没得核」；可成绩单里藏着一条「0 失败，却有 FAIL」还得红
        with tempfile.TemporaryDirectory() as td:
            root, rec, chk, rc_path = make_fixture(
                Path(td), items=[item("A1", "FAIL")],
                rec=record([item("A1", "FAIL")],
                           summary={"total": 1, "pass": 1, "fail": 0, "pending": 0, "seconds": 1.0}))
            chk.write_text("# 只剩个标题\n", encoding="utf-8")
            res = crr.run(rec, chk, root, rc_path)
            self.assertEqual(res["code"], 1, res["findings"])

    def test_main_returns_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            root, rec, chk, rc_path = make_fixture(Path(td))
            code = crr.main(["--record", str(rec), "--checklist", str(chk),
                             "--root", str(root)], root=root, rc_path=rc_path)
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
