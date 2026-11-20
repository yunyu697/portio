#!/usr/bin/env python3
"""rc.py 的 A33（「这份 exe 真能起来」）单测。

这一项钉住的是「起身」这件事本身，不是「文件长得像程序」：
- A10 只读 PE 头里的 Subsystem 字段，只说明这份 exe 被标记成 GUI；
  A33 把它真拉起来，看窗口有没有、标题对不对、进程撑没撑住。
- 所以判定必须能分开这几种：
  ① 进程自己退了（跑不起来）；
  ② 进程在、窗口没画出来（卡首帧）；
  ③ 窗口有、标题不对（起错了东西）；
  ④ 标题里带 ERR:（前端起来就炸）；
  ⑤ 标题带 Portio 且撑住了（这才算过）。
另外钉住「用完要收掉」：不许在人家桌面上留下一个关不掉的窗口。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc  # noqa: E402

P, F, S = rc.PASS, rc.FAIL, rc.SKIP


class VerdictTest(unittest.TestCase):
    def test_title_with_portio_and_alive_is_pass(self):
        status, detail = rc.launch_verdict(["Portio 1.0.8-RC7"], True, 6.0)
        self.assertEqual(status, P)
        self.assertIn("Portio 1.0.8-RC7", detail)
        self.assertIn("6s", detail)

    def test_process_gone_is_fail(self):
        status, detail = rc.launch_verdict([], False, 2.0)
        self.assertEqual(status, F)
        self.assertIn("退出", detail)

    def test_alive_without_window_is_fail_not_pass(self):
        """进程活着但一个窗口都没画出来，不能算过——这就是「没核到」。"""
        status, detail = rc.launch_verdict([], True, 10.0)
        self.assertEqual(status, F)
        self.assertIn("窗口", detail)

    def test_wrong_title_is_fail(self):
        status, detail = rc.launch_verdict(["Untitled - Notepad"], True, 10.0)
        self.assertEqual(status, F)
        self.assertIn("Portio", detail)

    def test_err_in_title_is_fail(self):
        status, detail = rc.launch_verdict(["ERR: TypeError x is not a function"], True, 5.0)
        self.assertEqual(status, F)
        self.assertIn("ERR:", detail)

    def test_err_beats_a_good_title_in_the_same_list(self):
        """同一个进程可能开了好几个窗：只要有一个带 ERR: 就是红，不许挑好看的那个报。"""
        status, _ = rc.launch_verdict(["Portio 1.0.8-RC7", "ERR: boom"], True, 5.0)
        self.assertEqual(status, F)

    def test_any_window_carrying_portio_counts(self):
        status, _ = rc.launch_verdict(["", "Portio 1.0.8-RC7"], True, 5.0)
        self.assertEqual(status, P)


class FakeProc:
    def __init__(self, alive: bool, code: int = 0):
        self.alive = alive
        self.code = code
        self.pid = 4242

    def poll(self):
        return None if self.alive else self.code


class ProbeTest(unittest.TestCase):
    def run_probe(self, proc, titles):
        killed = []
        status, detail = rc.probe_launch(
            Path("portio-app.exe"),
            wait_window=0.02,
            hold=0.02,
            window_fn=lambda pid: titles,
            popen=lambda *a, **k: proc,
            kill=killed.append,
        )
        return status, detail, killed

    def test_alive_with_portio_title_is_pass_and_gets_killed(self):
        status, detail, killed = self.run_probe(FakeProc(True), ["Portio 1.0.8-RC7"])
        self.assertEqual(status, P)
        self.assertEqual(killed, [4242], "拉起过就必须收掉，不许留在桌面上")

    def test_early_exit_is_fail_and_nothing_left_to_kill(self):
        status, detail, killed = self.run_probe(FakeProc(False, 101), [])
        self.assertEqual(status, F)
        self.assertIn("退出", detail)
        self.assertEqual(killed, [])

    def test_non_windows_is_weiyan_not_pass(self):
        """mac / linux 上没有 user32，这一项只能是「未验」，不许静悄悄算过。"""
        if sys.platform == "win32":
            self.skipTest("本机是 Windows，走不到那条分支")
        self.assertEqual(rc.a33_launch()[0], S)


class WiredTest(unittest.TestCase):
    def test_a33_is_actually_wired_into_the_plan(self):
        """判定写得再好，没接进计划表也是白写——清单里承诺的项必须真跑。"""
        source = (Path(rc.__file__)).read_text(encoding="utf-8")
        self.assertIn('("A33",', source)
        self.assertIn("a33_launch()", source.split('("A33",')[1])

    def test_launch_budgets_are_sane(self):
        self.assertGreater(rc.LAUNCH_WAIT, 2.0)
        self.assertGreater(rc.LAUNCH_HOLD, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
