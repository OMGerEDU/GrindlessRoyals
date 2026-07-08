import unittest

from maplebot.gui import default_instance_name, format_tab_name


class InstanceLabelTests(unittest.TestCase):
    def test_default_instance_name_prefers_title(self):
        info = {"hwnd": 123, "title": "MapleRoyals", "process_name": "MapleRoyals.exe"}

        self.assertEqual(default_instance_name(info), "MapleRoyals")

    def test_default_instance_name_uses_process_name_without_title(self):
        info = {"hwnd": -21572, "title": "", "process_name": "MapleRoyals.exe"}

        self.assertEqual(default_instance_name(info), "MapleRoyals.exe")

    def test_default_instance_name_falls_back_to_hwnd(self):
        info = {"hwnd": 123, "title": "", "process_name": ""}

        self.assertEqual(default_instance_name(info), "HWND 123")

    def test_format_tab_name_uses_custom_name(self):
        self.assertEqual(format_tab_name("Main", 123), "Main")

    def test_format_tab_name_trims_long_names(self):
        self.assertEqual(format_tab_name("abcdefghijklmnopqrstuvwxyz", 123), "abcdefghijklmnopqrstu...")


if __name__ == "__main__":
    unittest.main()
