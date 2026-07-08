# MapleBot Faithful Clone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `MapleBot.exe` as runnable, maintainable Python source that faithfully matches the recovered GUI, CLI, and automation behavior.

**Architecture:** Keep the recovered behavior but split the original one-file PyInstaller app into focused modules. OS-specific Windows calls live behind small functions so tests can mock them without requiring MapleStory or real window handles.

**Tech Stack:** Python 3.12+, Tkinter, pynput, pywin32 on Windows, unittest, PyInstaller-compatible entry point.

---

## File Structure

- Create `main.py`: command-line entry point with `--cli`.
- Create `maplebot/__init__.py`: package metadata.
- Create `maplebot/keys.py`: key constants and `parse_loop_key`.
- Create `maplebot/windows.py`: visible window enumeration and foreground activation helpers.
- Create `maplebot/bot.py`: `MapleBot` runtime, key sending, loop worker, walking, potion timing, lifecycle.
- Create `maplebot/gui.py`: Tkinter GUI matching recovered labels and defaults.
- Create `maplebot/cli.py`: keyboard-listener mode with recovered hotkeys.
- Create `tests/test_keys.py`: parser tests.
- Create `tests/test_windows.py`: mocked enumeration tests.
- Create `tests/test_bot.py`: state/timing tests using fake senders and no real keyboard.
- Create `README.md`: setup, run, CLI, packaging, and safety notes.

## Task 1: Project Skeleton

**Files:**
- Create: `maplebot/__init__.py`
- Create: `main.py`
- Create: `README.md`

- [ ] **Step 1: Create package and entry point**

```python
# main.py
from maplebot.cli import run_cli
from maplebot.gui import run_gui


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MapleBot controller")
    parser.add_argument("--cli", action="store_true", help="Run in keyboard-listener CLI mode.")
    args = parser.parse_args()

    if args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run import check**

Run: `python -m compileall main.py maplebot`

Expected: fails only because `maplebot.cli` and `maplebot.gui` are not created yet.

## Task 2: Key Parsing

**Files:**
- Create: `maplebot/keys.py`
- Test: `tests/test_keys.py`

- [ ] **Step 1: Write parser tests**

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing test**

Run: `python -m unittest tests.test_keys -v`

Expected: fail because `maplebot.keys` does not exist.

- [ ] **Step 3: Implement parser**

Implement constants recovered from the binary:

```python
DEFAULT_LOOP_KEY_NAME = "space"
DEFAULT_LOOP_INTERVAL = 0.6
DEFAULT_SHUFFLE_INTERVAL = 60.0
DEFAULT_SHUFFLE_MIN_HOLD = 0.25
DEFAULT_SHUFFLE_MAX_HOLD = 0.5
DEFAULT_POTION_KEY_NAME = "7"
DEFAULT_POTION_INTERVAL_STEP = 5.0
MIN_POTION_INTERVAL = 5.0
```

Map known names `space`, `enter`, `tab`, `esc`, `left`, `right`, `up`, `down`, and `home` to `pynput.keyboard.Key`. Single-character names become `KeyCode.from_char(value)`. Unknown names print a warning and return `Key.space`.

- [ ] **Step 4: Run passing test**

Run: `python -m unittest tests.test_keys -v`

Expected: all parser tests pass.

## Task 3: Window Enumeration

**Files:**
- Create: `maplebot/windows.py`
- Test: `tests/test_windows.py`

- [ ] **Step 1: Write mocked window tests**

```python
import unittest

from maplebot.windows import filter_window_title


class WindowFilteringTests(unittest.TestCase):
    def test_filter_is_case_insensitive(self):
        self.assertTrue(filter_window_title("MapleStory", "maplestory"))
        self.assertTrue(filter_window_title("MY MAPLESTORY CLIENT", "Maplestory"))

    def test_filter_rejects_empty_or_unmatched_titles(self):
        self.assertFalse(filter_window_title("", "Maplestory"))
        self.assertFalse(filter_window_title("Notepad", "Maplestory"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Implement Windows helpers**

Create `WindowInfo = dict[str, int | str]`, `filter_window_title(title, window_filter)`, `enumerate_maple_windows(window_filter="Maplestory")`, and `activate_window(hwnd)`. Import `win32gui`, `win32con`, `win32api`, and `win32process` inside guarded module-level try/except so tests run when pywin32 is missing.

- [ ] **Step 3: Run window tests**

Run: `python -m unittest tests.test_windows -v`

Expected: all tests pass without a real MapleStory client.

## Task 4: Bot Runtime

**Files:**
- Create: `maplebot/bot.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write state tests**

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Implement `MapleBot`**

Implement constructor defaults, `refresh_windows`, `hwnd`, `cycle_window`, `_force_foreground`, `activate_window`, `send_key`, `send_string`, `send_key_combination`, `_key_to_vk`, `_send_background_key`, `_post_message_key`, `_loop_worker`, `_tap_key`, `_hold_key`, `_hold_key_background`, `_hold_key_foreground`, `_perform_shuffle_move`, `adjust_potion_interval`, `start_loop`, `stop_loop`, and `toggle_loop`.

- [ ] **Step 3: Run bot tests**

Run: `python -m unittest tests.test_bot -v`

Expected: all tests pass without sending keys.

## Task 5: GUI

**Files:**
- Create: `maplebot/gui.py`

- [ ] **Step 1: Implement recovered GUI shell**

Implement `MapleBotGUI` with title `MapleBot Controller`, minimum size `780x520`, toolbar buttons `↻ Refresh` and `⏹ Stop All`, auto-refresh controls, status bar, notebook, and placeholder text `No Maplestory windows detected.\nLaunch the client and hit Refresh.`

- [ ] **Step 2: Implement per-window tabs**

For each window, create controls with recovered labels: `Attack loop`, `Loop key`, `Interval (s)`, `Send keys in background`, `Potion`, `Enable potion auto-use`, `Potion key`, `Walk`, `Enable walk (strafing)`, `Hold min/max (s)`, `Start Loop`, `Stop Loop`, `Tap Potion`, `Focus Window`, and `Quick skills`.

- [ ] **Step 3: Wire GUI actions**

Wire `start_bot`, `stop_bot`, `focus_window`, `tap_potion`, `send_skill`, `_ensure_bot`, `stop_all`, `on_close`, and `run` to the bot runtime.

- [ ] **Step 4: Compile GUI**

Run: `python -m compileall maplebot/gui.py`

Expected: compile succeeds.

## Task 6: CLI

**Files:**
- Create: `maplebot/cli.py`
- Modify: `main.py`

- [ ] **Step 1: Implement CLI mode**

Implement `run_cli()` to create a default `MapleBot`, print detected windows, and listen with `pynput.keyboard.Listener`. Hotkeys: F3 toggles loop, F4 cycles windows, F7 exits, `+` or numpad add increases interval by `DEFAULT_POTION_INTERVAL_STEP`, `-` or numpad subtract decreases it.

- [ ] **Step 2: Compile entry point**

Run: `python -m compileall main.py maplebot`

Expected: compile succeeds.

## Task 7: Documentation and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document setup and usage**

Document Python dependencies, `python main.py`, `python main.py --cli`, GUI controls, and optional PyInstaller packaging command.

- [ ] **Step 2: Run full tests**

Run: `python -m unittest discover -v`

Expected: all tests pass.

- [ ] **Step 3: Run compile check**

Run: `python -m compileall main.py maplebot tests`

Expected: compile succeeds.

- [ ] **Step 4: Report limitations**

Report whether pywin32/pynput were available locally, whether GUI launch was tested, and whether any original executable execution was avoided.

## Self-Review

- Spec coverage: all scoped GUI, CLI, key parsing, window enumeration, bot loop, walking, potion timing, quick skills, docs, and tests are represented.
- Placeholder scan: no task depends on an undefined future placeholder.
- Type consistency: module names, function names, class names, and constants match across tasks.
