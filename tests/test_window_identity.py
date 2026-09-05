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

    def test_choose_background_target_prefers_visible_render_child(self):
        from maplebot import windows
        candidates = [
            {"hwnd": 10, "parent": 0, "class_name": "Asteria", "title": "", "visible": True, "enabled": True},
            {"hwnd": 11, "parent": 10, "class_name": "Chrome_RenderWidgetHostHWND", "title": "", "visible": True, "enabled": True},
        ]
        self.assertEqual(windows.choose_background_target(10, candidates), 11)

    def test_choose_background_target_falls_back_to_top_level(self):
        from maplebot import windows
        candidates = [
            {"hwnd": 12, "parent": 10, "class_name": "Static", "title": "", "visible": False, "enabled": True},
        ]
        self.assertEqual(windows.choose_background_target(10, candidates), 10)


if __name__ == "__main__":
    unittest.main()
