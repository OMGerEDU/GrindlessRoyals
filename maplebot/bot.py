"""Core MapleBot runtime recovered from the PyInstaller build."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import random
import threading
import time

from .keys import (
    Controller,
    DEFAULT_LOOP_INTERVAL,
    DEFAULT_LOOP_KEY_NAME,
    DEFAULT_POTION_KEY_NAME,
    DEFAULT_SHUFFLE_INTERVAL,
    DEFAULT_SHUFFLE_MAX_HOLD,
    DEFAULT_SHUFFLE_MIN_HOLD,
    Key,
    KeyCode,
    MIN_POTION_INTERVAL,
    parse_loop_key,
)
from . import windows as window_api


# Set up ctypes function signatures for 64-bit safe execution without pywin32
try:
    user32 = ctypes.windll.user32
    user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
    user32.VkKeyScanW.restype = wintypes.SHORT

    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT

    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
except Exception:
    pass



class MapleBot:
    def __init__(
        self,
        loop_key=Key.space,
        loop_interval: float = DEFAULT_LOOP_INTERVAL,
        background_loop: bool = True,
        shuffle_interval: float = DEFAULT_SHUFFLE_INTERVAL,
        shuffle_min_hold: float = DEFAULT_SHUFFLE_MIN_HOLD,
        shuffle_max_hold: float = DEFAULT_SHUFFLE_MAX_HOLD,
        potion_key=None,
        potion_enabled: bool = False,
        walk_enabled: bool = False,
        window_title: str = "Maplestory",
        target_hwnd: int | None = None,
        potion_interval: float | None = None,
        walk_interval: float | None = None,
        walk_min_hold: float | None = None,
        walk_max_hold: float | None = None,
        skills_interval: float = 180.0,
        skills_to_use: list | None = None,
        anti_afk_enabled: bool = False,
        anti_afk_interval: float | None = None,
        run_duration: float | None = None,
        walk_direction_mode: str = "alternate",
    ):
        self.keyboard = Controller()
        self.window_title = window_title
        self.windows: list[int] = []
        self.active_index = 0
        self.loop_key = loop_key
        self.loop_interval = loop_interval
        self.background_loop = background_loop
        self.shuffle_interval = shuffle_interval
        self.shuffle_min_hold = shuffle_min_hold
        self.shuffle_max_hold = shuffle_max_hold

        self.potion_interval = potion_interval if potion_interval is not None else shuffle_interval
        self.walk_interval = walk_interval if walk_interval is not None else shuffle_interval
        self.walk_min_hold = walk_min_hold if walk_min_hold is not None else shuffle_min_hold
        self.walk_max_hold = walk_max_hold if walk_max_hold is not None else shuffle_max_hold

        self.potion_key = potion_key if potion_key is not None else parse_loop_key(DEFAULT_POTION_KEY_NAME)
        self.potion_enabled = potion_enabled
        self.walk_enabled = walk_enabled
        # walk_direction_mode: 'alternate' | 'always_left' | 'always_right'
        self.walk_direction_mode = walk_direction_mode
        self.walk_left = True

        self.skills_interval = skills_interval
        # skills_to_use: list of (key, delay_seconds) tuples
        self.skills_to_use = skills_to_use if skills_to_use is not None else []

        self.next_potion = time.time() + self.potion_interval
        self.next_walk = time.time() + self.walk_interval
        self.next_skills = time.time() + self.skills_interval
        self.anti_afk_enabled = anti_afk_enabled
        self.anti_afk_interval = anti_afk_interval if anti_afk_interval is not None else 60.0
        self.last_known_direction = "left"
        self.is_simulating_movement = False
        self.next_anti_afk = time.time() + self.anti_afk_interval
        # run_duration: seconds to run before auto-stop (None = run forever)
        self.run_duration = run_duration
        self.running = False
        self.loop_thread: threading.Thread | None = None
        self.target_hwnd = target_hwnd

    def refresh_windows(self) -> None:
        """Refresh list of Maplestory windows."""
        if self.target_hwnd is not None:
            try:
                if window_api.is_window(self.target_hwnd):
                    self.windows = [self.target_hwnd]
                    self.active_index = 0
                    return
            except Exception:
                pass

        infos = window_api.enumerate_maple_windows(self.window_title)
        self.windows = [int(info["hwnd"]) for info in infos]
        if self.windows:
            self.active_index = min(self.active_index, len(self.windows) - 1)
        else:
            self.active_index = 0

    @property
    def hwnd(self) -> int | None:
        if not self.windows:
            return None
        return self.windows[self.active_index]

    def cycle_window(self) -> None:
        """Switch to the next Maplestory window if multiple exist."""
        if not self.windows:
            self.refresh_windows()
        if not self.windows:
            print("No Maplestory windows found to cycle.")
            return
        self.active_index = (self.active_index + 1) % len(self.windows)
        print(f"Switched to window {self.active_index + 1}/{len(self.windows)} (HWND: {self.hwnd})")
        self.activate_window()

    def _force_foreground(self) -> bool:
        target = self.hwnd
        if target is None:
            return False
        return window_api.force_foreground(target)

    def activate_window(self) -> bool:
        """Bring the Maplestory window to foreground."""
        target = self.hwnd
        if target is None:
            self.refresh_windows()
            target = self.hwnd
        if target is None:
            print(f"Window '{self.window_title}' not found!")
            return False
        result = window_api.activate_window(target)
        time.sleep(0.05)
        return result

    def identify_window(self) -> bool:
        target = self.hwnd
        if target is None:
            self.refresh_windows()
            target = self.hwnd
        if target is None:
            print(f"Window '{self.window_title}' not found!")
            return False
        return window_api.identify_window(target)
    def send_key(self, key) -> bool:
        """Send a single keystroke."""
        try:
            if not self.activate_window():
                return False
            self.keyboard.press(key)
            self.keyboard.release(key)
            return True
        except Exception as err:
            print(f"Error sending key: {err}")
            return False

    def send_string(self, text: str) -> bool:
        """Send a string of characters."""
        try:
            if not self.activate_window():
                return False
            self.keyboard.type(text)
            return True
        except Exception as err:
            print(f"Error sending string: {err}")
            return False

    def send_key_combination(self) -> bool:
        """Send a key combination (e.g., Ctrl+C)."""
        keys = [Key.ctrl, KeyCode.from_char("c")]
        try:
            if not self.activate_window():
                return False
            for key in keys:
                self.keyboard.press(key)
            for key in reversed(keys):
                self.keyboard.release(key)
            return True
        except Exception as err:
            print(f"Error sending key combination: {err}")
            return False

    def _key_to_vk(self, key) -> int | None:
        """Translate pynput Key/KeyCode/str into a virtual-key code."""
        con = window_api.win32con
        key_map = {}
        if con is not None:
            key_map = {
                Key.space: con.VK_SPACE,
                Key.enter: con.VK_RETURN,
                Key.tab: con.VK_TAB,
                Key.up: con.VK_UP,
                Key.down: con.VK_DOWN,
                Key.left: con.VK_LEFT,
                Key.right: con.VK_RIGHT,
                Key.esc: con.VK_ESCAPE,
                Key.shift: con.VK_SHIFT,
                Key.ctrl: con.VK_CONTROL,
                Key.alt: con.VK_MENU,
            }
        else:
            key_map = {
                Key.space: 0x20,
                Key.enter: 0x0D,
                Key.tab: 0x09,
                Key.up: 0x26,
                Key.down: 0x28,
                Key.left: 0x25,
                Key.right: 0x27,
                Key.esc: 0x1B,
                Key.shift: 0x10,
                Key.ctrl: 0x11,
                Key.alt: 0x12,
            }

        if key in key_map:
            return key_map[key]
        if isinstance(key, KeyCode) and getattr(key, "vk", None):
            return key.vk

        char = getattr(key, "char", None)
        if char is None and isinstance(key, str):
            char = key
        if char:
            if window_api.win32api is not None:
                vk = window_api.win32api.VkKeyScan(char)
                if vk == -1:
                    return None
                return vk & 0xFF
            else:
                try:
                    vk = ctypes.windll.user32.VkKeyScanW(char)
                    if vk == -1:
                        return None
                    return vk & 0xFF
                except Exception:
                    return ord(char.upper()) if len(char) == 1 else None
        return None

    def _send_background_key(self, key) -> bool:
        """Send key via PostMessage so MapleStory can stay in the background."""
        target = self.hwnd
        if target is None:
            self.refresh_windows()
            target = self.hwnd
        if target is None:
            print("No window available for background key send.")
            return False
        return self._post_message_key(target, key, True) and self._post_message_key(target, key, False)

    def _post_message_key(self, hwnd: int, key, is_down: bool, is_repeat: bool = False) -> bool:
        vk = self._key_to_vk(key)
        if vk is None:
            print(f"Unsupported key for background send: {key}")
            return False

        has_pywin32 = (window_api.win32api is not None and 
                       window_api.win32con is not None and 
                       window_api.win32gui is not None)

        try:
            if has_pywin32:
                scan_code = window_api.win32api.MapVirtualKey(vk, 0)
            else:
                scan_code = ctypes.windll.user32.MapVirtualKeyW(vk, 0)

            lparam = 1 | (scan_code << 16)
            is_extended = vk in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E)
            if is_extended:
                lparam |= 0x01000000

            WM_KEYDOWN = 0x0100
            WM_KEYUP = 0x0101
            message = WM_KEYDOWN
            if not is_down:
                lparam |= 0xC0000000
                message = WM_KEYUP
            elif is_repeat:
                lparam |= 0x40000000

            if has_pywin32:
                window_api.win32gui.PostMessage(hwnd, message, vk, lparam)
            else:
                ctypes.windll.user32.PostMessageW(hwnd, message, vk, lparam)
            return True
        except Exception as err:
            print(f"Background key send failed: {err}")
            return False

    def _loop_worker(self) -> None:
        print("Action loop started. (Walk in foreground, others in background)")
        if self.walk_enabled:
            print(f"Walk enabled: interval {self.walk_interval:.1f}s, hold {self.walk_min_hold:.2f}s - {self.walk_max_hold:.2f}s, mode={self.walk_direction_mode}")
        if self.potion_enabled:
            print(f"Potion enabled: interval {self.potion_interval:.1f}s")
        if self.skills_to_use:
            print(f"Auto buff enabled: interval {self.skills_interval:.1f}s, casting {len(self.skills_to_use)} skills")
        if self.run_duration is not None:
            print(f"Run timer: will auto-stop after {self.run_duration:.0f}s ({self.run_duration/60:.1f} min)")
        self.next_potion = time.time() + self.potion_interval
        self.next_walk = time.time() + self.walk_interval
        self.next_skills = time.time() + self.skills_interval
        self.next_anti_afk = time.time() + self.anti_afk_interval
        loop_start = time.time()
        while self.running:
            current_time = time.time()

            # 0. Run-duration timer check
            if self.run_duration is not None and (current_time - loop_start) >= self.run_duration:
                print(f"Run timer expired ({self.run_duration:.0f}s). Auto-stopping loop.")
                self.running = False
                break

            # 1. Potion auto-use check
            if self.potion_enabled and self.potion_interval > 0 and current_time >= self.next_potion:
                self._perform_potion_use()
                self.next_potion = current_time + self.potion_interval

            # 2. Anti-AFK check
            if self.anti_afk_enabled and self.anti_afk_interval > 0 and current_time >= self.next_anti_afk:
                self._perform_anti_afk()
                self.next_anti_afk = time.time() + self.anti_afk_interval
                current_time = time.time()

            # 3. Walk check / Buffs check / Attack loop
            if self.skills_to_use and self.skills_interval > 0 and current_time >= self.next_skills:
                self._perform_skills_cast()
                self.next_skills = time.time() + self.skills_interval
            elif self.walk_enabled and self.walk_interval > 0 and current_time >= self.next_walk:
                self._perform_walk_move()
                self.next_walk = time.time() + self.walk_interval
            else:
                self._send_background_key(self.loop_key)
            time.sleep(self.loop_interval)
        print("Action loop stopped.")

    def _tap_key(self, key) -> bool:
        return self._send_background_key(key)

    def _hold_key(self, key, duration: float) -> bool:
        return self._hold_key_foreground(key, duration)

    def _hold_key_background(self, key, duration: float) -> bool:
        target = self.hwnd
        if target is None:
            self.refresh_windows()
            target = self.hwnd
        if target is None:
            return False
        if not self._post_message_key(target, key, True):
            return False
        
        start_time = time.time()
        end_time = start_time + duration
        interval = 0.05
        while time.time() < end_time:
            time.sleep(min(interval, max(0.001, end_time - time.time())))
            self._post_message_key(target, key, True, is_repeat=True)
            
        return self._post_message_key(target, key, False)

    def _hold_key_foreground(self, key, duration: float) -> bool:
        try:
            if not self.activate_window():
                return False
            self.keyboard.press(key)
            time.sleep(duration)
            self.keyboard.release(key)
            return True
        except Exception as err:
            print(f"Foreground hold failed: {err}")
            return False

    def _perform_potion_use(self) -> None:
        print("Potion auto-use: tapping potion key")
        if not self._tap_key(self.potion_key):
            print("Failed to tap potion key.")

    def _perform_walk_move(self) -> None:
        self.is_simulating_movement = True
        try:
            hold_time = random.uniform(self.walk_min_hold, self.walk_max_hold)
            # Determine which direction to move based on mode
            if self.walk_direction_mode == "always_left":
                go_left = True
            elif self.walk_direction_mode == "always_right":
                go_left = False
            else:  # alternate
                go_left = self.walk_left

            if go_left:
                print(f"Walk move: pausing attack, strafing left for {hold_time:.2f}s")
                if not self._hold_key(Key.left, hold_time):
                    print("Failed to move left during walk.")
                # Update alternating tracker only in alternate mode
                if self.walk_direction_mode == "alternate":
                    self.walk_left = False
                self.last_known_direction = "left"
            else:
                print(f"Walk move: pausing attack, strafing right for {hold_time:.2f}s")
                if not self._hold_key(Key.right, hold_time):
                    print("Failed to move right during walk.")
                if self.walk_direction_mode == "alternate":
                    self.walk_left = True
                self.last_known_direction = "right"
        finally:
            self.is_simulating_movement = False

    def _perform_anti_afk(self) -> None:
        self.is_simulating_movement = True
        try:
            print(f"Anti-AFK: performing jitter movement (mode={self.walk_direction_mode})")
            if self.walk_direction_mode == "always_left":
                # Jitter left then restore left
                self._hold_key(Key.left, 0.15)
                time.sleep(0.05)
                self._hold_key(Key.left, 0.10)
                restore_key = Key.left
                self.last_known_direction = "left"
            elif self.walk_direction_mode == "always_right":
                # Jitter right then restore right
                self._hold_key(Key.right, 0.15)
                time.sleep(0.05)
                self._hold_key(Key.right, 0.10)
                restore_key = Key.right
                self.last_known_direction = "right"
            else:
                # Alternate: left then right, restore to last known
                self._hold_key(Key.left, 0.15)
                time.sleep(0.05)
                self._hold_key(Key.right, 0.15)
                restore_key = Key.left if self.last_known_direction == "left" else Key.right

            time.sleep(0.05)
            try:
                self.keyboard.press(restore_key)
                time.sleep(0.05)
                self.keyboard.release(restore_key)
                print(f"Anti-AFK: restored facing direction in foreground to {self.last_known_direction}")
            except Exception as err:
                print(f"Failed to restore direction in foreground: {err}")
        finally:
            self.is_simulating_movement = False

    def _perform_skills_cast(self) -> None:
        print(f"Skills cast: pausing attack, casting {len(self.skills_to_use)} skills")
        for entry in self.skills_to_use:
            # Support both (key, delay) tuples and bare keys for backward compat
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                key, delay = entry
            else:
                key, delay = entry, 1.0
            print(f"Casting skill key: {key} (delay: {delay:.2f}s)")
            if not self._tap_key(key):
                print(f"Failed to tap skill key: {key}")
            time.sleep(delay)

    def adjust_potion_interval(self, delta: float) -> None:
        if self.shuffle_interval <= 0:
            print("Potion interval controls disabled because shuffle interval is off.")
            return

        new_interval = max(MIN_POTION_INTERVAL, self.shuffle_interval + delta)
        if new_interval == self.shuffle_interval and delta < 0:
            print(f"Potion interval already at minimum ({MIN_POTION_INTERVAL:.1f}s).")
            return
        self.shuffle_interval = new_interval
        self.potion_interval = new_interval
        direction = "longer" if delta > 0 else "shorter"
        self.next_potion = time.time() + self.potion_interval
        print(f"Potion interval {direction}: now {self.potion_interval:.1f}s between potion key presses.")

    def start_loop(self) -> None:
        if self.running:
            return
        self.refresh_windows()
        if not self.windows:
            print(f"No '{self.window_title}' windows found. Cannot start loop.")
            return
        self.running = True
        self.next_potion = time.time() + self.potion_interval
        self.next_walk = time.time() + self.walk_interval
        self.next_skills = time.time() + self.skills_interval
        self.loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self.loop_thread.start()
        print("F3: loop ON")

    def stop_loop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.loop_thread is not None:
            self.loop_thread.join(timeout=1.0)
        print("F3: loop OFF")

    def toggle_loop(self) -> None:
        if self.running:
            self.stop_loop()
        else:
            self.start_loop()
