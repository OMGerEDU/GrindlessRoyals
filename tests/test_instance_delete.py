import unittest

from maplebot.gui import filter_deleted_instances


class InstanceDeleteTests(unittest.TestCase):
    def test_deleted_instances_are_removed_from_visible_list(self):
        infos = [
            {"hwnd": 101, "title": "Main"},
            {"hwnd": 202, "title": "Wrong"},
            {"hwnd": -303, "title": "Process-only"},
        ]

        visible = filter_deleted_instances(infos, {202, -303})

        self.assertEqual(visible, [{"hwnd": 101, "title": "Main"}])

    def test_no_deleted_instances_keeps_original_order(self):
        infos = [
            {"hwnd": 101, "title": "Main"},
            {"hwnd": 202, "title": "Second"},
        ]

        self.assertEqual(filter_deleted_instances(infos, set()), infos)


if __name__ == "__main__":
    unittest.main()
