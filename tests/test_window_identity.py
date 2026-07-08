import unittest

from maplebot.windows import DEFAULT_MAPLE_FILTERS, matches_maple_window


class WindowIdentityTests(unittest.TestCase):
    def test_default_filters_include_known_maple_clients(self):
        self.assertIn("mapleroyals", DEFAULT_MAPLE_FILTERS)
        self.assertIn("maplelauncher", DEFAULT_MAPLE_FILTERS)
        self.assertIn("maple", DEFAULT_MAPLE_FILTERS)

    def test_matches_mapleroyals_process_without_window_title(self):
        self.assertTrue(matches_maple_window("", "MapleRoyals.exe"))

    def test_matches_launcher_process_without_window_title(self):
        self.assertTrue(matches_maple_window("", "MapleLauncher.exe"))

    def test_rejects_non_maple_process_without_window_title(self):
        self.assertFalse(matches_maple_window("", "notepad.exe"))


if __name__ == "__main__":
    unittest.main()
