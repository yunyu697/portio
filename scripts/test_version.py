"""docs/versioning.md 的进位规则回归测试。CI 里用 unittest 跑。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version import VersionError, next_version, parse  # noqa: E402


class CarryRuleTest(unittest.TestCase):
    def test_patch_increments_normally(self):
        self.assertEqual(next_version("1.0.5", "patch"), "1.0.6")

    def test_patch_ten_carries_into_minor(self):
        self.assertEqual(next_version("1.0.10", "patch"), "1.1.0")

    def test_patch_carry_chains_into_major(self):
        self.assertEqual(next_version("1.10.10", "patch"), "2.0.0")

    def test_minor_carry_chains_into_major(self):
        self.assertEqual(next_version("1.10.3", "minor"), "2.0.0")

    def test_never_emits_eleven(self):
        for v in ("1.0.10", "1.5.10", "1.10.10", "0.0.10"):
            nxt = next_version(v, "patch")
            self.assertNotIn("11", nxt.split(".")[-1])

    def test_alpha_ladder_starts_at_one(self):
        self.assertEqual(next_version("1.2.3", "stage", "alpha"), "1.2.3-alpha1")

    def test_alpha_ladder_carries_after_ten(self):
        self.assertEqual(next_version("1.2.3-alpha10", "stage", "alpha"), "1.2.4-alpha1")

    def test_stage_promotes_to_rc(self):
        self.assertEqual(next_version("1.2.3-alpha3", "stage", "RC"), "1.2.3-RC1")

    def test_rc_promotes_to_final(self):
        self.assertEqual(next_version("1.2.3-RC1", "final"), "1.2.3")

    def test_reject_eleven_in_minor_or_patch(self):
        for bad in ("1.0.11", "1.11.0", "1.0.0-alpha11", "1.0.0-RC11"):
            with self.assertRaises(VersionError):
                parse(bad)

    def test_reject_going_backwards_in_stage(self):
        with self.assertRaises(VersionError):
            next_version("1.2.3-RC1", "stage", "alpha")

    def test_reject_final_on_final(self):
        with self.assertRaises(VersionError):
            next_version("1.2.3", "final")


if __name__ == "__main__":
    unittest.main()
