from __future__ import annotations

import unittest

from companion.release import is_newer_release, version_key


class DesktopReleaseTests(unittest.TestCase):
    def test_version_key_handles_release_prefixes(self) -> None:
        self.assertEqual(version_key("v0.5.2"), (0, 5, 2))
        self.assertEqual(version_key("invalid"), (0,))

    def test_newer_release_comparison(self) -> None:
        self.assertTrue(is_newer_release("0.5.3", "0.5.2"))
        self.assertTrue(is_newer_release("v1.0.0", "0.9.9"))
        self.assertFalse(is_newer_release("0.5.2", "0.5.2"))
        self.assertFalse(is_newer_release("0.5.1", "0.5.2"))
