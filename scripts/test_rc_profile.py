# -*- coding: utf-8 -*-
"""1.0.10-RC1：一次性 profile 自己建、自己删、删不掉要说出来。

钉住四件事：
1. `release_profile` 删不掉时不许静默——判 False、登记、点名（以前 ignore_errors 吞掉）；
2. `make_profile` 先核盘余量，不够就抛并说清差多少，且不往目录里写东西；
3. `sweep_stale_profiles` 只清「自己前缀 + 够旧」的目录，刚建的、别人的、同名文件一律不碰；
4. 整跑接线：四个探针都走这套函数、A44 在计划表与派发链里、main 先清再建、收尾数残留。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

RC_PY = Path(__file__).resolve().parent / "rc.py"


def _rmtree_clear(path, ignore_errors=False, onerror=None):
    """测试用：真删（跟 shutil.rmtree 同签名，方便替换）。"""
    shutil.rmtree(path, ignore_errors=ignore_errors)


def _refuse(path, ignore_errors=False, onerror=None):
    raise OSError("文件还被别的进程占着（测试故意）")


class TempCase(unittest.TestCase):
    def setUp(self):
        rc.CREATED_PROFILES.clear()
        rc.LEAKED_PROFILES.clear()
        self.root = Path(tempfile.mkdtemp(prefix="_t44_"))

    def tearDown(self):
        rc.CREATED_PROFILES.clear()
        rc.LEAKED_PROFILES.clear()
        shutil.rmtree(self.root, ignore_errors=True)

    def mk(self, name: str, size: int = 0, age_h: float = 0.0) -> Path:
        p = self.root / name
        p.mkdir()
        if size:
            (p / "x").write_bytes(b"x" * size)
        if age_h:
            stamp = time.time() - age_h * 3600
            for q in [p, *p.rglob("*")]:
                os.utime(q, (stamp, stamp))
        return p


class ReleaseTest(TempCase):
    def test_release_deletes_and_says_true(self):
        p = self.mk("portio-rc-a", 100)
        self.assertTrue(rc.release_profile(p))
        self.assertFalse(p.exists())
        self.assertEqual(rc.LEAKED_PROFILES, [])

    def test_missing_profile_is_not_a_leak(self):
        p = self.root / "portio-rc-gone"
        self.assertTrue(rc.release_profile(p))
        self.assertEqual(rc.LEAKED_PROFILES, [])

    def test_stuck_profile_is_false_and_registered(self):
        p = self.mk("portio-rc-stuck", 100)
        ok = rc.release_profile(p, rmtree=_refuse, sleep=lambda _s: None, tries=2)
        self.assertFalse(ok, "删不掉却报成功，等于又回到 ignore_errors")
        self.assertTrue(p.exists())
        self.assertIn(p, rc.LEAKED_PROFILES)

    def test_stuck_profile_is_named_once(self):
        p = self.mk("portio-rc-stuck2", 0)
        for _ in range(3):
            rc.release_profile(p, rmtree=_refuse, sleep=lambda _s: None, tries=1)
        self.assertEqual(rc.LEAKED_PROFILES.count(p), 1)

    def test_retries_before_giving_up(self):
        calls = []

        def flaky(path, ignore_errors=False, onerror=None):
            calls.append(path)
            if len(calls) < 3:
                raise OSError("还没松手")
            _rmtree_clear(path)

        p = self.mk("portio-rc-flaky", 0)
        self.assertTrue(rc.release_profile(p, rmtree=flaky, sleep=lambda _s: None, tries=5))
        self.assertEqual(len(calls), 3, "前三下都没删掉，第三下才成——所以重试必须真发生")
        self.assertEqual(rc.LEAKED_PROFILES, [])


class MakeTest(TempCase):
    def test_makes_inside_root_and_registers(self):
        p = rc.make_profile("portio-rc-", root=self.root, need_mb=1,
                            free=lambda _p: 9000.0)
        self.assertTrue(p.exists())
        self.assertEqual(p.parent, self.root)
        self.assertTrue(p.name.startswith("portio-rc-"))
        self.assertIn(p, rc.CREATED_PROFILES)

    def test_short_space_raises_with_the_gap(self):
        with self.assertRaises(rc.TempSpaceShort) as ctx:
            rc.make_profile("portio-rc-", root=self.root, need_mb=200,
                            free=lambda _p: 20.0)
        msg = str(ctx.exception)
        self.assertIn("差 180 MB", msg, "不说清差多少，人只知道「不够」却不知道要挪走多少")
        self.assertIn(str(self.root), msg)

    def test_short_space_writes_nothing(self):
        before = sorted(q.name for q in self.root.iterdir())
        with self.assertRaises(rc.TempSpaceShort):
            rc.make_profile("portio-rc-", root=self.root, need_mb=200, free=lambda _p: 1.0)
        self.assertEqual(sorted(q.name for q in self.root.iterdir()), before)
        self.assertEqual(rc.CREATED_PROFILES, [])

    def test_enough_space_and_no_raise(self):
        rc.require_temp_space(self.root, need_mb=1, free=lambda _p: 2.0)


class SweepTest(TempCase):
    def test_only_own_prefix_and_only_stale(self):
        old = self.mk("portio-fresh-old", 4096, age_h=30)
        young = self.mk("portio-rc-young", 10, age_h=0)
        foreign = self.mk("chrome-profile-old", 4096, age_h=30)
        lone = self.root / "portio-narrow-file"
        lone.write_bytes(b"not a dir")
        count, freed = rc.sweep_stale_profiles(
            root=self.root, prefixes=rc.PROFILE_PREFIXES, stale_hours=6,
            release=lambda p, **_k: rc.release_profile(p, sleep=lambda _s: None))
        self.assertEqual(count, 1, "只该清掉上一轮那份旧 profile")
        self.assertFalse(old.exists())
        self.assertTrue(young.exists(), "刚建的那份可能是另一个 rc.py 正在用的")
        self.assertTrue(foreign.exists(), "别人前缀的临时目录不许碰")
        self.assertTrue(lone.exists(), "同前缀的文件也不许删（只认目录）")
        self.assertGreaterEqual(freed, 4096)

    def test_all_ages_when_stale_is_none(self):
        self.mk("portio-rc-fresh", 0)
        self.assertEqual(len(rc.profile_dirs(self.root, stale_hours=None)), 1)

    def test_sweep_survives_missing_root(self):
        self.assertEqual(rc.sweep_stale_profiles(root=self.root / "nope"), (0, 0))

    def test_profile_dirs_ignores_plain_files(self):
        (self.root / "portio-rc-file").write_bytes(b"x")
        self.assertEqual(rc.profile_dirs(self.root, stale_hours=None), [])


class ProbeTest(TempCase):
    def test_probe_passes_on_a_clean_root(self):
        status, detail = rc.probe_profile_lifecycle(self.root, sleep=lambda _s: None)
        self.assertEqual(status, rc.PASS, detail)
        self.assertIn("差 180 MB", detail)
        self.assertIn("陈旧清理", detail)

    def test_probe_fails_when_silent_delete_is_back(self):
        # 反着来：万一有人把「删不掉」改回 ignore_errors，探针要红
        real = rc.release_profile
        rc.release_profile = lambda p, **k: (shutil.rmtree(p, ignore_errors=True) or True)
        try:
            status, detail = rc.probe_profile_lifecycle(self.root, sleep=lambda _s: None)
        finally:
            rc.release_profile = real
        self.assertEqual(status, rc.FAIL)
        self.assertIn("删不掉", detail)

    def test_probe_fails_when_sweep_eats_young_dirs(self):
        real = rc.profile_dirs

        def no_age(root=None, prefixes=rc.PROFILE_PREFIXES, now=None, stale_hours=None):
            return real(root, prefixes, now, None)

        rc.profile_dirs = no_age
        try:
            status, detail = rc.probe_profile_lifecycle(self.root, sleep=lambda _s: None)
        finally:
            rc.profile_dirs = real
        self.assertEqual(status, rc.FAIL)
        self.assertIn("刚建出来那份被当成陈旧", detail)


class WiringTest(unittest.TestCase):
    def setUp(self):
        self.src = RC_PY.read_text(encoding="utf-8")

    def test_in_plan_table(self):
        self.assertRegex(self.src, r'\("A44",\s*"一次性 profile 自己建自己删')

    def test_in_dispatch_chain(self):
        self.assertIn('elif code == "A44":', self.src)
        self.assertIn("a44_profile_lifecycle()", self.src)

    def test_four_probes_use_the_helpers(self):
        for head in ("def probe_fresh_selftests", "def probe_app_selftests",
                     "def probe_narrow", "def a34_payload"):
            body = self.src.split(head, 1)[1].split("\ndef ", 1)[0]
            self.assertIn("make_profile(", body, f"{head} 还是老办法建 profile")
            self.assertIn("release_profile(", body, f"{head} 还是老办法收 profile")

    def test_no_silent_rmtree_left(self):
        # 模块头里那句是「记录旧写法」，代码里才不许再有
        body = self.src.split('"""', 2)[2]
        for pat in ("shutil.rmtree(prof, ignore_errors=True)",
                    "shutil.rmtree(profile, ignore_errors=True)",
                    "shutil.rmtree(workdir, ignore_errors=True)"):
            self.assertNotIn(pat, body, "一处静默删除都不许留")

    def test_main_sweeps_then_makes_and_reports(self):
        body = self.src.split("def main(", 1)[1]
        self.assertIn("swept, freed = sweep_stale_profiles()", body)
        self.assertLess(body.find("sweep_stale_profiles()"),
                        body.find('make_profile("portio-rc-")'),
                        "先清上一轮、再建这一轮的")
        self.assertIn("不能开跑", body)
        self.assertIn("release_profile(profile)", body)
        self.assertIn("还留着 {len(left)} 份", body)
        self.assertIn("code = EXIT_FAIL", body, "盘上留了东西就不许算全绿")

    def test_old_silent_test_text_is_gone(self):
        # 老口径那句 `ignore_errors=True` 不许再出现在这三处探针里
        for head in ("def probe_fresh_selftests", "def probe_app_selftests", "def probe_narrow"):
            body = self.src.split(head, 1)[1].split("\ndef ", 1)[0]
            self.assertNotIn("ignore_errors=True", body)


if __name__ == "__main__":
    unittest.main()
