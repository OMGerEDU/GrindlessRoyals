import unittest

from maplebot.windows import filter_window_title


class WindowFilteringTests(unittest.TestCase):
    def test_filter_is_case_insensitive(self):
        self.assertTrue(filter_window_title("MapleStory", "maplestory"))
        self.assertTrue(filter_window_title("MY MAPLESTORY CLIENT", "Maplestory"))

    def test_filter_rejects_empty_or_unmatched_titles(self):
        self.assertFalse(filter_window_title("", "Maplestory"))
        self.assertFalse(filter_window_title("Notepad", "Maplestory"))


if __name__ == "__main__":
    unittest.main()
