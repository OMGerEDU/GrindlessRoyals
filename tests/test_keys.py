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
    def test_function_keys_and_modifiers(self):
        key_f1 = parse_loop_key("f1")
        self.assertIsNotNone(key_f1)
        
        key_shift = parse_loop_key("shift")
        self.assertIsNotNone(key_shift)

if __name__ == "__main__":
    unittest.main()
