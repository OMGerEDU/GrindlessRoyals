"""Keyboard-listener CLI mode for MapleBot."""

from __future__ import annotations

from .bot import MapleBot
from .keys import DEFAULT_LOOP_INTERVAL, DEFAULT_LOOP_KEY_NAME, DEFAULT_POTION_INTERVAL_STEP, DEFAULT_POTION_KEY_NAME
from .keys import Key, KeyCode, parse_loop_key


def run_cli() -> None:
    try:
        from pynput import keyboard
    except ImportError:
        print("pynput is required for CLI hotkeys. Install dependencies with: pip install -r requirements.txt")
        return

    loop_key = parse_loop_key(DEFAULT_LOOP_KEY_NAME)
    potion_key = parse_loop_key(DEFAULT_POTION_KEY_NAME)
    bot = MapleBot(loop_key=loop_key, loop_interval=DEFAULT_LOOP_INTERVAL, potion_key=potion_key, potion_enabled=True)
    bot.refresh_windows()
    if bot.windows:
        print(f"Detected {len(bot.windows)} Maplestory window(s). Current HWND: {bot.hwnd}")
    else:
        print(f"No '{bot.window_title}' windows detected. Start the game and press F3 once it's running.")

    print("Controls: F3 toggles, F4 cycles windows, +/- adjust potion interval, F7 exits.")

    def on_press(key) -> bool | None:
        if key == Key.f3:
            bot.toggle_loop()
            return None
        if key == Key.f4:
            bot.cycle_window()
            return None
        if key == Key.f7:
            print("F7 pressed. Exiting.")
            bot.stop_loop()
            return False

        char = ""
        if isinstance(key, KeyCode):
            char = (key.char or "").lower()
        vk = getattr(key, "vk", None)
        if char == "+" or vk == 0x6B:
            bot.adjust_potion_interval(DEFAULT_POTION_INTERVAL_STEP)
        elif char == "-" or vk == 0x6D:
            bot.adjust_potion_interval(-DEFAULT_POTION_INTERVAL_STEP)
        return None

    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Shutting down.")
        bot.stop_loop()
