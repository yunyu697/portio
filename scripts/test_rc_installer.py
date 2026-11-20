#!/usr/bin/env python3
"""rc.py 的 A34（「包里那份 exe 跟我核的那份是同一份」）单测。

这一项补的是 A11 的洞：A11 只核「文件名对不对 + 体积像不像话」，
一个上一轮留下的、名字刚好的包它照样放行。A34 把包拆开，
拿里面那份 `portio-app.exe` 跟构建产物逐字节对。

唯一允许不一样的是 tauri 打包器写的那几位标记
（`__TAURI_BUNDLE_TYPE_VAR_UNK` → `__TAURI_BUNDLE_TYPE_VAR_NSS`），
所以判定必须先认出、抹平再比——但抹平只能抹那一位，别处差一个字节就得红。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

P, F, S = rc.PASS, rc.FAIL, rc.SKIP
M = rc.MARKER


def exe(marker: str, extra: bytes = b"") -> bytes:
    """造一份带标记的假 exe：前面一段壳、中间标记、后面一段代码。"""
    return b"MZ\x90\x00" + b"\x00" * 64 + M + marker.encode() + b"\x00" + b"CODE" * 8 + extra


class MarkerTest(unittest.TestCase):
    def test_reads_the_marker(self):
        self.assertEqual(rc.bundle_marker(exe("UNK")), "UNK")
        self.assertEqual(rc.bundle_marker(exe("NSS")), "NSS")

    def test_no_marker_is_empty(self):
        self.assertEqual(rc.bundle_marker(b"MZ" + b"\x00" * 100), "")

    def test_blanking_keeps_length_and_wipes_only_the_marker(self):
        a, b = rc.blank_marker(exe("UNK")), rc.blank_marker(exe("NSS"))
        self.assertEqual(len(a), len(exe("UNK")))
        self.assertEqual(a, b, "抹平之后两份必须一模一样")
        self.assertIn(b"CODE", a, "别处不许动")


class PayloadVerdictTest(unittest.TestCase):
    def test_same_bytes_is_pass(self):
        """两份一模一样（连标记都一样）当然算同一份——这里用非 UNK 的标记，
        因为包里那份写着 UNK 本身就是红的（打包器没改写它）。"""
        status, detail = rc.payload_verdict(exe("NSS"), exe("NSS"))
        self.assertEqual(status, P)
        self.assertIn("逐字节一致", detail)

    def test_only_the_marker_differs_is_still_pass(self):
        """真实情况：构建产物是 UNK，包里那份被打包器改成 NSS——这算同一份。"""
        status, detail = rc.payload_verdict(exe("UNK"), exe("NSS"))
        self.assertEqual(status, P)
        self.assertIn("UNK → NSS", detail, "得说清唯一不同的是哪几位")

    def test_payload_still_says_unk_is_fail(self):
        """包里那份还带 UNK，说明打包器没改写它——装上去的是打包前那份。"""
        bad = bytearray(exe("UNK"))
        bad[10] ^= 0xFF
        status, detail = rc.payload_verdict(exe("UNK"), bytes(bad))
        self.assertEqual(status, F)
        self.assertIn("UNK", detail)

    def test_different_size_is_fail(self):
        status, detail = rc.payload_verdict(exe("UNK"), exe("NSS", b"tail"))
        self.assertEqual(status, F)
        self.assertIn("大小", detail)

    def test_one_byte_elsewhere_is_fail(self):
        """不许放宽成「差几字节就算了」：别处差一个字节就不是同一份。"""
        good = bytearray(exe("NSS"))
        good[10] ^= 0xFF
        status, detail = rc.payload_verdict(exe("UNK"), bytes(good))
        self.assertEqual(status, F)
        self.assertIn("差 1 字节", detail)
        self.assertIn("0xa", detail)

    def test_missing_payload_is_fail(self):
        status, detail = rc.payload_verdict(exe("UNK"), None)
        self.assertEqual(status, F)
        self.assertIn("拆不出", detail)

    def test_no_build_to_compare_is_weiyan(self):
        status, detail = rc.payload_verdict(None, exe("NSS"))
        self.assertEqual(status, S)
        self.assertIn("没有构建产物", detail)


class ExtractTest(unittest.TestCase):
    def test_reports_why_when_the_exe_is_not_in_the_package(self):
        import tempfile
        workdir = Path(tempfile.mkdtemp())
        try:
            got, why = rc.extract_payload(Path("nope.exe"), sys.executable, workdir)
        finally:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
        self.assertIsNone(got)
        self.assertTrue(why, "拿不到东西时必须说清为什么，不能只返回空")


class WiredTest(unittest.TestCase):
    def test_a34_is_actually_wired_into_the_plan(self):
        """判定再好，没接进计划表也是白写。"""
        source = Path(rc.__file__).read_text(encoding="utf-8")
        self.assertIn('("A34",', source)
        self.assertIn("a34_payload()", source.split('("A34",')[1])
        self.assertIn('elif code == "A34":', source, "分派链里真要有这一支，别掉进兜底")

    def test_bundle_lookup_is_shared_with_a11(self):
        """A11 与 A34 认包必须是同一份文件，否则「核的」和「拆的」又能不是同一个包。"""
        source = Path(rc.__file__).read_text(encoding="utf-8")
        # 3 次 = 定义 1 次 + check_bundle 与 a34_payload 各调 1 次；多个调用方就说明又分了叉
        self.assertEqual(source.count("versioned_bundle("), 3, "只许 A11 与 A34 两处调用")


if __name__ == "__main__":
    unittest.main(verbosity=2)
