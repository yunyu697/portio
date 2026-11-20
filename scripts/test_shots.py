"""A31「发布截图是本版本那一套」的判据。

图本身没法自检，只能靠 shots.py 出图时写下的清单来对：哪一版、几张、每张多少字节。
这里钉的就是这几种情形——没清单、清单写着旧版本、图少了、图被人换过、清单全对。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.rc import FAIL, PASS, SHOTS_MIN, SKIP, check_shots

VER = "1.0.8-RC2"


def manifest(ver: str = VER, files: list[tuple[str, int]] | None = None) -> dict:
    if files is None:
        files = [(f"portio-dark-s{i}.png", 1000 + i) for i in range(SHOTS_MIN)]
    return {
        "version": ver,
        "generated": "2026-11-20T09:12:00+08:00",
        "window": [1180, 690],
        "scale": 2,
        "shots": [
            {"file": name, "scene": "main", "theme": "dark", "label": "x",
             "width": 2360, "height": 1380, "bytes": size}
            for name, size in files
        ],
    }


class CheckShotsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="portio-shots-test-")
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def lay_out(self, files: list[tuple[str, int]]) -> None:
        for name, size in files:
            (self.dir / name).write_bytes(b"\0" * size)

    def test_no_manifest_is_skip(self) -> None:
        status, detail = check_shots(None, VER, self.dir)
        self.assertEqual(status, SKIP)
        self.assertIn("shots.py", detail)

    def test_empty_version_fails(self) -> None:
        status, detail = check_shots(manifest(), "", self.dir)
        self.assertEqual(status, FAIL)
        self.assertIn("读不出", detail)

    def test_old_version_is_skip_and_named(self) -> None:
        status, detail = check_shots(manifest("1.0.7-RC9"), VER, self.dir)
        self.assertEqual(status, SKIP)
        self.assertIn("1.0.7-RC9", detail)
        self.assertIn(VER, detail)

    def test_all_good_passes(self) -> None:
        files = [(f"portio-light-s{i}.png", 2000 + i) for i in range(SHOTS_MIN)]
        self.lay_out(files)
        status, detail = check_shots(manifest(files=files), VER, self.dir)
        self.assertEqual(status, PASS)
        self.assertIn(VER, detail)
        self.assertIn(f"{SHOTS_MIN} 张", detail)

    def test_missing_image_fails_and_named(self) -> None:
        files = [(f"portio-dark-s{i}.png", 1000 + i) for i in range(SHOTS_MIN)]
        self.lay_out(files[:-1])
        status, detail = check_shots(manifest(files=files), VER, self.dir)
        self.assertEqual(status, FAIL)
        self.assertIn(files[-1][0], detail)

    def test_changed_bytes_fail(self) -> None:
        files = [(f"portio-dark-s{i}.png", 1000 + i) for i in range(SHOTS_MIN)]
        self.lay_out(files)
        (self.dir / files[0][0]).write_bytes(b"\0" * (files[0][1] + 7))
        status, detail = check_shots(manifest(files=files), VER, self.dir)
        self.assertEqual(status, FAIL)
        self.assertIn(files[0][0], detail)
        self.assertIn("字节", detail)

    def test_too_few_shots_fail(self) -> None:
        files = [(f"portio-dark-s{i}.png", 1000 + i) for i in range(SHOTS_MIN - 2)]
        self.lay_out(files)
        status, detail = check_shots(manifest(files=files), VER, self.dir)
        self.assertEqual(status, FAIL)
        self.assertIn("2 张", detail)

    def test_empty_shot_list_fails(self) -> None:
        data = manifest(files=[])
        status, detail = check_shots(data, VER, self.dir)
        self.assertEqual(status, FAIL)
        self.assertIn("一张图都没记", detail)


if __name__ == "__main__":
    unittest.main()
