import unittest

from maplebot.keys import COMMON_KEY_CHOICES, DEFAULT_LOOP_KEY_NAME, parse_loop_key


class KeyParsingTests(unittest.TestCase):
    def test_defaults_match_recovered_binary(self):
        self.assertEqual(DEFAULT_LOOP_KEY_NAME, "space")
        self.assertIn("space", COMMON_KEY_CHOICES)
        self.assertIn("7", COMMON_KEY_CHOICES)

    def test_single_character_becomes_keycode(self):
        key = parse_loop_key("a")
        self.assertEqual(key.char, "a")

    def test_known_named_key(self):
        key = parse_loop_key("space")
        self.assertEqual(key.name, "space")

    def test_unknown_key_falls_back_to_space(self):
        key = parse_loop_key("not-a-key")
        self.assertEqual(key.name, "space")

    def test_whitespace_is_ignored(self):
        key = parse_loop_key("  7  ")
        self.assertEqual(key.char, "7")

    def test_parse_hotkey_valid_and_disabled(self):
        from maplebot.keys import parse_hotkey

        self.assertIsNone(parse_hotkey("none"))
        self.assertIsNone(parse_hotkey("disabled"))
        self.assertIsNone(parse_hotkey(""))

        key_space = parse_hotkey("space")
        self.assertEqual(key_space.name, "space")

        key_f12 = parse_hotkey("f12")
        self.assertEqual(key_f12.name, "f12")

    def test_special_keys_parsed_correctly(self):
        from maplebot.keys import parse_loop_key
        key_home = parse_loop_key("home")
        if hasattr(key_home, "name"):
            self.assertEqual(key_home.name, "home")
        else:
            self.assertEqual(key_home.vk, 0x24)

        key_insert = parse_loop_key("insert")
        if hasattr(key_insert, "name"):
            self.assertEqual(key_insert.name, "insert")
        else:
            self.assertEqual(key_insert.vk, 0x2D)

    def test_key_to_vk_resolution(self):
        from maplebot.bot import MapleBot
        from maplebot.keys import parse_loop_key
        bot = MapleBot()
        
        key_home = parse_loop_key("home")
        self.assertEqual(bot._key_to_vk(key_home), 0x24)
        
        key_space = parse_loop_key("space")
        self.assertEqual(bot._key_to_vk(key_space), 0x20)
        
        key_f8 = parse_loop_key("f8")
        self.assertEqual(bot._key_to_vk(key_f8), 0x77)


if __name__ == "__main__":
    unittest.main()
