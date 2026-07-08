import unittest

from maplebot.bot import MapleBot
from maplebot.keys import MIN_POTION_INTERVAL


class MapleBotStateTests(unittest.TestCase):
    def test_adjust_potion_interval_respects_minimum(self):
        bot = MapleBot(shuffle_interval=MIN_POTION_INTERVAL)
        bot.adjust_potion_interval(-999)
        self.assertEqual(bot.shuffle_interval, MIN_POTION_INTERVAL)

    def test_toggle_loop_calls_start_and_stop(self):
        bot = MapleBot()
        calls = []
        bot.start_loop = lambda: calls.append("start")
        bot.stop_loop = lambda: calls.append("stop")
        bot.running = False
        bot.toggle_loop()
        bot.running = True
        bot.toggle_loop()
        self.assertEqual(calls, ["start", "stop"])

    def test_walk_move_alternates_directions(self):
        from maplebot.keys import Key
        bot = MapleBot(walk_enabled=True, walk_min_hold=0.5, walk_max_hold=0.5)
        
        held_keys = []
        bot._hold_key = lambda key, duration: held_keys.append((key, duration)) or True
        
        self.assertTrue(bot.walk_left)
        
        # First walk move -> should go left
        bot._perform_walk_move()
        self.assertEqual(held_keys, [(Key.left, 0.5)])
        self.assertFalse(bot.walk_left)
        
        # Second walk move -> should go right
        bot._perform_walk_move()
        self.assertEqual(held_keys, [(Key.left, 0.5), (Key.right, 0.5)])
        self.assertTrue(bot.walk_left)

    def test_independent_timers_execution(self):
        from unittest.mock import patch, MagicMock
        
        bot = MapleBot(
            potion_enabled=True,
            potion_interval=10.0,
            walk_enabled=True,
            walk_interval=25.0,
            loop_interval=0.5
        )
        
        bot._perform_potion_use = MagicMock()
        bot._perform_walk_move = MagicMock()
        bot._send_background_key = MagicMock(return_value=True)
        bot.background_loop = True
        
        # time.time() sequence of calls:
        # 1. self.next_potion init: 1000.0 -> next_potion = 1010.0
        # 2. self.next_walk init: 1000.0 -> next_walk = 1025.0
        # 3. self.next_skills init: 1000.0 -> next_skills = 1180.0
        # 4. loop 1 current_time: 1000.0 -> attack key
        # 5. loop 2 current_time: 1005.0 -> attack key
        # 6. loop 3 current_time: 1011.0 -> potion, attack key
        # 7. loop 4 current_time: 1026.0 -> potion
        # 8. loop 4 next_walk time.time() update: 1026.0 -> next_walk = 1051.0
        # 9. loop 5 current_time: raises StopIteration (exits loop)
        timestamps = [1000.0, 1000.0, 1000.0, 1000.0, 1005.0, 1011.0, 1026.0, 1026.0]
        time_iter = iter(timestamps)
        
        class StopLoop(Exception):
            pass

        def mock_time():
            try:
                return next(time_iter)
            except StopIteration:
                raise StopLoop()
                
        def mock_sleep(duration):
            pass

        try:
            with patch('time.time', side_effect=mock_time), patch('time.sleep', side_effect=mock_sleep):
                bot.running = True
                bot._loop_worker()
        except StopLoop:
            pass
            
        self.assertEqual(bot._perform_potion_use.call_count, 2)
        self.assertEqual(bot._perform_walk_move.call_count, 1)
        self.assertEqual(bot._send_background_key.call_count, 3)

    def test_skills_cast_sequence(self):
        from maplebot.keys import Key
        from unittest.mock import patch
        bot = MapleBot(skills_to_use=[Key.f1, Key.f2])
        
        tapped_keys = []
        bot._tap_key = lambda key: tapped_keys.append(key) or True
        
        with patch('time.sleep') as mock_sleep:
            bot._perform_skills_cast()
            
        self.assertEqual(tapped_keys, [Key.f1, Key.f2])
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(1.0)

    def test_skills_cast_timer_in_loop(self):
        from unittest.mock import patch, MagicMock
        
        bot = MapleBot(
            skills_to_use=["f1"],
            skills_interval=15.0,
            loop_interval=0.5
        )
        
        bot._perform_skills_cast = MagicMock()
        bot._send_background_key = MagicMock(return_value=True)
        bot.background_loop = True
        
        # time.time() sequence of calls:
        # 1. self.next_potion init: 1000.0
        # 2. self.next_walk init: 1000.0
        # 3. self.next_skills init: 1000.0 -> next_skills = 1015.0
        # 4. loop 1 current_time: 1000.0 -> attack key
        # 5. loop 2 current_time: 1010.0 -> attack key
        # 6. loop 3 current_time: 1016.0 -> skills triggered (next_skills = 1031.0)
        # 7. loop 4 current_time: raises StopIteration (exits loop)
        timestamps = [1000.0, 1000.0, 1000.0, 1000.0, 1010.0, 1016.0]
        time_iter = iter(timestamps)
        
        class StopLoop(Exception):
            pass

        def mock_time():
            try:
                return next(time_iter)
            except StopIteration:
                raise StopLoop()
                
        def mock_sleep(duration):
            pass

        try:
            with patch('time.time', side_effect=mock_time), patch('time.sleep', side_effect=mock_sleep):
                bot.running = True
                bot._loop_worker()
        except StopLoop:
            pass
            
        self.assertEqual(bot._perform_skills_cast.call_count, 1)
        self.assertEqual(bot._send_background_key.call_count, 2)


if __name__ == "__main__":
    unittest.main()
