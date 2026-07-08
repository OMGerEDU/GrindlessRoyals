import unittest
from unittest.mock import call, patch

from maplebot import windows
from maplebot.bot import MapleBot


class IdentifyWindowTests(unittest.TestCase):
    def test_identify_window_rejects_process_only_handles(self):
        self.assertFalse(windows.identify_window(-21572))

    def test_identify_window_moves_and_restores_window(self):
        with (
            patch("maplebot.windows.activate_window", return_value=True),
            patch("maplebot.windows.get_window_rect", return_value=(10, 20, 110, 220)),
            patch("maplebot.windows.move_window", return_value=True) as move_window,
            patch("maplebot.windows.time.sleep"),
        ):
            self.assertTrue(windows.identify_window(123, offset=30, pause=0))

        move_window.assert_has_calls(
            [
                call(123, 40, 20, 100, 200),
                call(123, 10, 20, 100, 200),
            ]
        )

    def test_bot_identify_window_uses_current_hwnd(self):
        bot = MapleBot(target_hwnd=123)
        bot.windows = [123]

        with patch("maplebot.bot.window_api.identify_window", return_value=True) as identify_window:
            self.assertTrue(bot.identify_window())

        identify_window.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
