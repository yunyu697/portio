"""A43 的单测：把「坏档急救在真 exe 上真跑一遍」这件事钉住。

A42 那套跑在无头页里、后端是自检自己扮的替身；A43 才是真 exe、真 app-data、真 `fs::copy`。
这里钉四层：
① 判据本身：每种不合格都得点名（没冒副本 / 冒了两份 / 副本字节不对 / 原文件被改写 /
   提示条没说清另存成什么 / 同一份坏档再拉一次又冒副本 / 复用的名字报错了 /
   好档那趟没进界面 / 好档也另存 / 没收干净），全对才 PASS；
② 盘上那几个小工具：副本只认 `.broken-` 前缀、按名字比新旧、种下去的就是那几字节；
③ 接线：计划表 / 分派链里有 A43，且走的是自定义探针，不是无头页；
④ 安全：这一项**故意不给**一次性 profile（要的就是我的真偏好），收场只删自己种出来的副本。
"""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RC_PY = ROOT / "scripts" / "rc.py"

GOOD_FACTS = {
    "title": "Portio",
    "toast": "会话清单读坏了，原文件已另存为 sessions.json.broken-1795209010083，这次从空清单开始",
    "load_err": "",
    "copies": ["sessions.json.broken-1795209010083"],
    "copy_bytes_ok": True,
    "original_intact": True,
    # 同一份坏档再拉一次：该复用先前那份副本，不再拷
    "reuse_ok": True,
    "reuse_new": [],
    "reuse_toast": "会话清单读坏了，原文件已另存为 sessions.json.broken-1795209010083，这次从空清单开始",
    "control_ok": True,
    "control_new": [],
    "restore_bad": [],
}


def load_rc():
    """按文件路径加载 rc.py：它跟脚本目录同名，import 会被同目录的脚本遮住。"""
    spec = importlib.util.spec_from_file_location("rc_under_test", RC_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.rc = load_rc()

    def verdict(self, **patch):
        facts = dict(GOOD_FACTS)
        facts.update(patch)
        return self.rc.broken_store_verdict(facts)

    def test_all_good_passes_and_names_the_copy(self):
        status, detail = self.verdict()
        self.assertEqual(status, self.rc.PASS, detail)
        self.assertIn("sessions.json.broken-1795209010083", detail)
        self.assertIn("逐字节一致", detail)
        self.assertIn("好档对照那趟一个副本都没冒", detail)
        self.assertIn("没再冒新副本", detail)

    def test_nothing_measured_is_red(self):
        status, detail = self.rc.broken_store_verdict(None)
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("没核", detail)

    def test_no_copy_is_red(self):
        status, detail = self.verdict(copies=[])
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("一个副本都没冒出来", detail)

    def test_two_copies_is_red(self):
        status, detail = self.verdict(copies=["sessions.json.broken-1", "sessions.json.broken-2"])
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("2 份副本", detail)

    def test_wrong_copy_bytes_is_red(self):
        status, detail = self.verdict(copy_bytes_ok=False)
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("对不上", detail)

    def test_overwritten_original_is_red(self):
        status, detail = self.verdict(original_intact=False)
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("整份盖掉", detail)

    def test_silent_toast_is_red(self):
        status, detail = self.verdict(toast="")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("另存", detail)

    def test_unloaded_page_is_red(self):
        status, detail = self.verdict(load_err="20s 内没进到界面（调试口一直没开）")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("没进到界面", detail)

    def test_err_title_is_red(self):
        status, detail = self.verdict(title="ERR: TypeError")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("ERR:", detail)

    def test_reuse_page_missing_is_red(self):
        status, detail = self.verdict(reuse_ok=False, reuse_err="调试口一直没开")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("第二次拉起", detail)

    def test_reuse_making_another_copy_is_red(self):
        # 1.0.9-RC10 的病根：用户不动那份坏文件，应用每启动一次就再拷一份
        status, detail = self.verdict(reuse_new=["sessions.json.broken-1795209064860"])
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("又冒了新副本", detail)
        self.assertIn("越堆越多", detail)

    def test_reuse_toast_must_name_the_same_copy(self):
        status, detail = self.verdict(
            reuse_toast="会话清单读坏了，原文件已另存为 sessions.json.broken-1795209064860，这次从空清单开始")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("sessions.json.broken-1795209010083", detail)

    def test_reuse_toast_silent_is_red(self):
        status, detail = self.verdict(reuse_toast="")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("第二次拉起没说", detail)

    def test_control_page_missing_is_red(self):
        status, detail = self.verdict(control_ok=False, control_err="调试口一直没开")
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("好档那一趟", detail)

    def test_control_salvaged_good_store_is_red(self):
        status, detail = self.verdict(control_new=["sessions.json.broken-1795209064860"])
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("又冒了副本", detail)

    def test_unrestored_files_are_named(self):
        status, detail = self.verdict(restore_bad=["sessions.json"])
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("sessions.json", detail)
        self.assertIn("没收回原样", detail)

    def test_unrestored_wins_over_control_noise(self):
        # 反向验证时撞到过：收场空转会连带让好档那趟又另存一份。根因是没收拾干净，
        # 报出来的话得先说根因，别把人引到「急救把好文件也当坏档了」上去。
        status, detail = self.verdict(restore_bad=["sessions.json"],
                                      control_new=["sessions.json.broken-1795209064860"])
        self.assertEqual(status, self.rc.FAIL)
        self.assertIn("没收回原样", detail)


class DiskHelperTest(unittest.TestCase):
    def setUp(self):
        self.rc = load_rc()
        self.tmp = Path(tempfile.mkdtemp(prefix="_t43_"))
        for name in ("sessions.json", "sessions.json.broken-111",
                     "sessions.json.broken-222", "theme.txt", "round.json.broken-9x"):
            (self.tmp / name).write_bytes(b"x")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_copies_only_match_the_prefix(self):
        names = [p.name for p in self.rc.broken_copies(self.tmp)]
        self.assertEqual(names, ["sessions.json.broken-111", "sessions.json.broken-222"])

    def test_new_copies_compare_by_name(self):
        fresh = self.rc.new_copies(self.tmp, ["sessions.json.broken-111"])
        self.assertEqual([p.name for p in fresh], ["sessions.json.broken-222"])

    def test_plant_writes_exactly_the_payload(self):
        path = self.rc.plant_broken_store(self.tmp)
        self.assertEqual(path.name, "sessions.json")
        self.assertEqual(path.read_bytes(), self.rc.BROKEN_PLANT)
        # 种下去的就是「断电写到一半」的样子：不是合法 JSON
        self.assertFalse(path.read_bytes().endswith(b"}"))

    def test_app_data_dir_follows_appdata(self):
        got = self.rc.app_data_dir(env={"APPDATA": r"C:\Users\x\AppData\Roaming"})
        self.assertEqual(str(got).replace("/", "\\"),
                         r"C:\Users\x\AppData\Roaming\io.portio.desktop")
        self.assertIsNone(self.rc.app_data_dir(env={}))


class WiringTest(unittest.TestCase):
    def setUp(self):
        self.text = RC_PY.read_text(encoding="utf-8")

    def test_plan_has_a43(self):
        self.assertIn('("A43"', self.text)
        label = self.text.split('("A43"', 1)[1].split("),", 1)[0]
        self.assertIn("副本", label)
        self.assertIn("真 exe", label)

    def test_dispatch_is_not_the_headless_page(self):
        body = self.text.split('elif code == "A43"', 1)[1].split("elif code", 1)[0]
        self.assertIn("a43_broken_store_real()", body)
        self.assertNotIn("a_page(", body)

    def test_header_counts_to_last_item(self):
        m = re.search(r"A1–A(\d+)", self.text)
        self.assertIsNotNone(m)
        last = max(int(n) for n in re.findall(r'\("A(\d+)"', self.text))
        self.assertEqual(int(m.group(1)), last)

    def test_probe_runs_three_rounds(self):
        body = self.text.split("def probe_broken_store", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("第一趟", body)
        self.assertIn("第一趟半", body, "同一份坏档得再拉一次，核它不重复拷")
        self.assertIn("第二趟", body, "得有好档对照，不然『看见副本就算过』")
        self.assertIn("ctl_before", body)
        self.assertIn("again_before", body, "第二次拉起前得记一份现有副本名，好按差集判")

    def test_no_one_off_profile_on_purpose(self):
        # 这一项要的就是我的真偏好与真后端：给一次性 profile 会让它在一份空偏好里绿得漂亮
        body = self.text.split("def probe_broken_store", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("WEBVIEW2_USER_DATA_FOLDER", body)
        self.assertIn("故意不给", body)

    def test_control_starts_from_a_clean_slate(self):
        # 撞过：盘上留着一份读不懂的清单时，每拉起一次应用又另存一份，对照那趟自己就触发了急救。
        body = self.text.split("def probe_broken_store", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("clean_start", body, "对照那趟的起点得清理成「还没有这份清单」")
        self.assertIn("临时挪走", body)

    def test_only_self_made_copies_get_removed(self):
        body = self.text.split("def probe_broken_store", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("p.name not in before_copies", body, "只许删自己种出来的副本")
        self.assertIn("restore(before)", body, "三份文件按原字节收回")
        self.assertIn("residue_bad", body, "收完得独立复量，不能只信还原函数")


if __name__ == "__main__":
    unittest.main()
