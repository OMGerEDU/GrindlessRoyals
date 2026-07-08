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


if __name__ == "__main__":
    unittest.main()
