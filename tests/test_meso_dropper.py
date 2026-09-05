import unittest
from unittest.mock import MagicMock, patch
from maplebot.bot import MapleBot
from maplebot.keys import Key

class MesoDropperTests(unittest.TestCase):
    def test_meso_dropper_initial_state(self):
        bot = MapleBot(
            meso_dropper_enabled=True,
            meso_amount=100000,
            meso_delay=0.25,
            meso_x=500,
            meso_y=600,
            meso_disable_cursor=True,
            meso_start_delay=2.5
        )
        self.assertTrue(bot.meso_dropper_enabled)
        self.assertEqual(bot.meso_amount, 100000)
        self.assertEqual(bot.meso_delay, 0.25)
        self.assertEqual(bot.meso_x, 500)
        self.assertEqual(bot.meso_y, 600)
        self.assertTrue(bot.meso_disable_cursor)
        self.assertEqual(bot.meso_start_delay, 2.5)

    def test_meso_dropper_background_actions(self):
        bot = MapleBot(
            target_hwnd=123,
            background_loop=True,
            meso_amount=50000,
            meso_x=780,
            meso_y=580
        )
        bot.windows = [123]
        
        post_calls = []
        def mock_post_message_key(hwnd, key, down, is_repeat=False):
            post_calls.append((hwnd, key, down))
            return True
            
        bot._post_message_key = mock_post_message_key
        
        # Test amount transmission
        bot._send_meso_amount()
        # Expecting character by character posts (5 chars * 2 = 10 calls)
        self.assertEqual(len(post_calls), 10)
        for hwnd, key, down in post_calls:
            self.assertEqual(hwnd, 123)
            
        # Test enter key
        post_calls.clear()
        bot._send_meso_enter()
        self.assertEqual(len(post_calls), 2)
        self.assertEqual(post_calls[0][1], Key.enter)
        self.assertEqual(post_calls[0][0], 123)
        
    def test_meso_dropper_worker_loop_exits(self):
        bot = MapleBot(
            meso_dropper_enabled=True,
            meso_delay=0.1
        )
        bot.windows = [123]
        bot._click_meso_coin = MagicMock()
        bot._send_meso_amount = MagicMock()
        bot._send_meso_enter = MagicMock()
        
        bot.running = True
        
        # Wait for 3 sleeps inside the worker iteration before setting bot.running to False
        sleep_count = 0
        def side_effect_sleep(duration):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 3:
                bot.running = False
            
        with patch('time.sleep', side_effect=side_effect_sleep):
            bot._meso_dropper_worker()
            
        bot._click_meso_coin.assert_called_once()
        bot._send_meso_amount.assert_called_once()
        bot._send_meso_enter.assert_called_once()

    @patch('time.sleep')
    def test_meso_dropper_start_delay(self, mock_sleep):
        bot = MapleBot(
            meso_dropper_enabled=True,
            meso_start_delay=5.0
        )
        bot.windows = [123]
        bot._click_meso_coin = MagicMock()
        bot._send_meso_amount = MagicMock()
        bot._send_meso_enter = MagicMock()
        
        bot.running = True
        
        # First call to sleep should be the start delay
        # We make mock_sleep set bot.running to False so it exits immediately after the start delay sleep
        def side_effect_sleep(duration):
            bot.running = False
            
        mock_sleep.side_effect = side_effect_sleep
        
        bot._meso_dropper_worker()
        
        # Verify sleep was called with start delay
        mock_sleep.assert_any_call(5.0)

    @patch('ctypes.windll.user32.mouse_event')
    @patch('ctypes.windll.user32.SetCursorPos')
    def test_meso_dropper_disable_cursor_avoids_set_cursor(self, mock_set_cursor, mock_mouse_event):
        bot = MapleBot(
            target_hwnd=123,
            background_loop=False,
            meso_disable_cursor=True,
            meso_x=500,
            meso_y=600
        )
        bot.windows = [123]
        bot.activate_window = MagicMock(return_value=True)
        
        bot._click_meso_coin()
        
        # SetCursorPos should NOT be called because meso_disable_cursor is True
        mock_set_cursor.assert_not_called()
        # Mouse event should be called to click
        mock_mouse_event.assert_any_call(0x0002, 0, 0, 0, 0)
        mock_mouse_event.assert_any_call(0x0004, 0, 0, 0, 0)

if __name__ == "__main__":
    unittest.main()
