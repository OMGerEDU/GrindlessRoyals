import unittest
from unittest.mock import MagicMock, patch
import time

from maplebot.gui import MapleBotGUI


class TestGuiListener(unittest.TestCase):
    @patch('maplebot.gui.PYNPUT_AVAILABLE', True)
    @patch('maplebot.gui.enumerate_maple_windows', return_value=[])
    @patch('maplebot.gui.os.path.exists', return_value=False)
    def test_global_listener_ignores_key_when_active_binder(self, mock_exists, mock_enumerate):
        with patch('pynput.keyboard.Listener') as mock_listener_cls:
            gui = MapleBotGUI()
            
            # Find the on_press handler passed to keyboard.Listener
            mock_listener_cls.assert_called_once()
            on_press_handler = mock_listener_cls.call_args[1]['on_press']
            
            gui.stop_all = MagicMock()
            gui.stop_all_key_var.set("f8")
            
            from pynput.keyboard import Key
            
            # Trigger 'f8' keypress with active_binder = None (should trigger stop_all)
            gui.active_binder = None
            gui._last_bind_time = 0.0
            
            on_press_handler(Key.f8)
            gui.root.update()
            gui.stop_all.assert_called_once()
            
            # Reset mock
            gui.stop_all.reset_mock()
            
            # Now set active_binder (simulating keybind mode)
            gui.active_binder = MagicMock()
            
            # Trigger 'f8' keypress (should be ignored)
            on_press_handler(Key.f8)
            gui.root.update()
            gui.stop_all.assert_not_called()
            
            gui.root.destroy()


if __name__ == "__main__":
    unittest.main()
