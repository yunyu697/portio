#!/usr/bin/env python3
"""check_site.py 的单元测试：说明页与代码对表必须真能拦住漂移，
而不是"两边都读一遍然后永远 OK"。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_site as cs  # noqa: E402

VER = "1.0.7-RC8"

UI = """
<div class="modal" id="settings-modal">
  <div class="field">
    <label>主题 <b id="theme-note">深色</b></label>
    <div class="seg" id="seg-theme">
      <button data-v="dark">深色</button>
      <button data-v="light">浅色</button>
    </div>
  </div>
  <div class="field">
    <label>界面密度</label>
    <div class="seg" id="seg-density">
      <button data-v="compact">紧凑</button>
      <button data-v="standard">标准</button>
      <button data-v="comfortable">宽松</button>
    </div>
  </div>
  <div class="field">
    <label>终端字号 <b id="font-val">13</b></label>
    <input type="range" id="set-font" min="9" max="24" step="1" value="13">
  </div>
  <div class="field">
    <label>会话栏 · 启动时</label>
    <div class="seg" id="seg-boot-side">
      <button data-v="remember">记住上次</button>
    </div>
  </div>
  <div class="field">
    <label>运行日志 <b id="log-bytes">—</b></label>
    <div class="acts"><button class="btn" id="btn-log-open">打开日志位置</button></div>
  </div>
</div>
<div class="modal" id="keys-modal"></div>
<span class="ver">1.0.7-RC8</span>
"""

GOOD_ROWS = """
      <tr><td class="w">主题</td><td>深色 / 浅色</td></tr>
      <tr><td class="w">界面密度</td><td>紧凑 / 标准 / 宽松，24 / 28 / 32</td></tr>
      <tr><td class="w">终端字号</td><td>9–24</td></tr>
      <tr><td class="w">会话栏 · 启动时</td><td>记住上次</td></tr>
      <tr><td class="w">运行日志</td><td>路径与体积</td></tr>
"""


def site(rows: str, ver: str = VER) -> str:
    return (f'<section id="look"><h2>自定义</h2><table>{rows}</table></section>'
            f'<p class="sub">当前 <span class="ver">{ver}</span></p>'
            f'<code>Portio_{ver}_x64-setup.exe</code>'
            f'<p>版本号形如 <code>v{ver}</code></p>')


def problems(rows: str = GOOD_ROWS, ver: str = VER) -> list[str]:
    items = cs.parse_settings(UI)
    text = site(rows, ver)
    return cs.compare(items, cs.parse_rows(text), text, VER)


class ParseTest(unittest.TestCase):
    def test_label_value_is_stripped(self):
        # <label>主题 <b>深色</b></label> 里的「深色」是当前值，不是项名
        names = [it["name"] for it in cs.parse_settings(UI)]
        self.assertIn("主题", names)
        self.assertNotIn("主题深色", names)

    def test_non_seg_buttons_are_not_labels(self):
        # 「打开日志位置」不带 data-v，不该被当成档位
        log = [it for it in cs.parse_settings(UI) if it["name"] == "运行日志"][0]
        self.assertEqual(log["labels"], [])

    def test_range_is_read(self):
        font = [it for it in cs.parse_settings(UI) if it["name"] == "终端字号"][0]
        self.assertEqual(font["range"], ("9", "24"))
        self.assertEqual(font["labels"], [])


class CompareTest(unittest.TestCase):
    def test_aligned_page_is_clean(self):
        self.assertEqual(problems(), [])

    def test_missing_setting_is_named(self):
        rows = GOOD_ROWS.replace('      <tr><td class="w">终端字号</td><td>9–24</td></tr>\n', "")
        self.assertIn("说明页没写这一项：「终端字号」", problems(rows))

    def test_missing_tier_is_named(self):
        rows = GOOD_ROWS.replace("紧凑 / 标准 / 宽松", "紧凑 / 标准")
        self.assertIn("「界面密度」漏了档位「宽松」", problems(rows))

    def test_wrong_range_is_named(self):
        rows = GOOD_ROWS.replace("9–24", "11–18")
        self.assertIn("「终端字号」的档没写对，代码里是 9–24", problems(rows))

    def test_phantom_setting_is_named(self):
        rows = GOOD_ROWS + '<tr><td class="w">终端透明度</td><td>0 / 50</td></tr>'
        self.assertIn("说明页写了一项界面里没有的：「终端透明度」", problems(rows))

    def test_stale_version_is_named(self):
        got = problems(ver="1.0.7-RC7")
        self.assertIn("说明页版本串过期：1.0.7-RC7 ≠ 1.0.7-RC8", got)

    def test_setting_count_claim_is_checked(self):
        text = site(GOOD_ROWS).replace("<h2>自定义</h2>", "<h2>自定义</h2><p>设置里十六项，分两批。</p>")
        items = cs.parse_settings(UI)  # 5 项，不是 16
        got = cs.compare(items, cs.parse_rows(text), text, VER)
        self.assertIn("说明页说设置里十六项，设置面板里其实是 5 项", got)

    def test_setting_count_claim_matches(self):
        text = site(GOOD_ROWS).replace("<h2>自定义</h2>", "<h2>自定义</h2><p>设置里五项。</p>")
        items = cs.parse_settings(UI)
        self.assertNotIn("项", "".join(cs.compare(items, cs.parse_rows(text), text, VER)))


class RepoTest(unittest.TestCase):
    """真的仓库现在必须是对齐的——这条既是测试，也是这一版的验收判据。"""

    def test_repo_is_aligned(self):
        ui_text = cs.UI.read_text(encoding="utf-8")
        site_text = cs.SITE.read_text(encoding="utf-8")
        ver = __import__("re").search(r'<span class="ver"[^>]*>(.*?)</span>', ui_text).group(1).strip()
        got = cs.compare(cs.parse_settings(ui_text), cs.parse_rows(site_text), site_text, ver)
        self.assertEqual(got, [], "\n".join(got))


if __name__ == "__main__":
    unittest.main(verbosity=2)
