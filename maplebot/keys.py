"""Key parsing helpers recovered from the PyInstaller MapleBot build."""

from __future__ import annotations

DEFAULT_LOOP_KEY_NAME = "space"
DEFAULT_LOOP_INTERVAL = 0.6
DEFAULT_SHUFFLE_INTERVAL = 60.0
DEFAULT_SHUFFLE_MIN_HOLD = 0.25
DEFAULT_SHUFFLE_MAX_HOLD = 0.5
DEFAULT_POTION_KEY_NAME = "7"
DEFAULT_POTION_INTERVAL_STEP = 5.0
MIN_POTION_INTERVAL = 5.0


try:
    from pynput.keyboard import Controller, Key, KeyCode

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

    class _NamedKey:
        def __init__(self, name: str):
            self.name = name

        def __repr__(self) -> str:
            return f"Key.{self.name}"

    class Key:
        space = _NamedKey("space")
        enter = _NamedKey("enter")
        tab = _NamedKey("tab")
        esc = _NamedKey("esc")
        left = _NamedKey("left")
        right = _NamedKey("right")
        up = _NamedKey("up")
        down = _NamedKey("down")
        home = _NamedKey("home")
        shift = _NamedKey("shift")
        ctrl = _NamedKey("ctrl")
        alt = _NamedKey("alt")
        f1 = _NamedKey("f1")
        f2 = _NamedKey("f2")
        f3 = _NamedKey("f3")
        f4 = _NamedKey("f4")
        f5 = _NamedKey("f5")
        f6 = _NamedKey("f6")
        f7 = _NamedKey("f7")
        f8 = _NamedKey("f8")
        f9 = _NamedKey("f9")
        f10 = _NamedKey("f10")
        f11 = _NamedKey("f11")
        f12 = _NamedKey("f12")

    class KeyCode:
        def __init__(self, char: str | None = None, vk: int | None = None):
            self.char = char
            self.vk = vk

        @classmethod
        def from_char(cls, char: str) -> "KeyCode":
            return cls(char=char)

        def __repr__(self) -> str:
            if self.char is not None:
                return f"KeyCode(char={self.char!r})"
            return f"KeyCode(vk={self.vk!r})"

    class Controller:
        def press(self, key) -> None:
            raise RuntimeError("pynput is required to send real keyboard input")

        def release(self, key) -> None:
            raise RuntimeError("pynput is required to send real keyboard input")

        def type(self, text: str) -> None:
            raise RuntimeError("pynput is required to send real keyboard input")


KEY_NAME_MAP = {
    "space": Key.space,
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "esc": Key.esc,
    "escape": Key.esc,
    "left": Key.left,
    "right": Key.right,
    "up": Key.up,
    "down": Key.down,
    "home": Key.home,
    "shift": Key.shift,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
}

COMMON_KEY_CHOICES = (
    "space",
    "enter",
    "tab",
    "left",
    "right",
    "up",
    "down",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "0",
    "-",
    "=",
)


def parse_loop_key(name: str):
    """Convert a human-readable key name into a pynput Key or KeyCode."""
    normalized = name.strip().lower()
    if normalized in KEY_NAME_MAP:
        return KEY_NAME_MAP[normalized]
    if len(normalized) == 1:
        return KeyCode.from_char(normalized)

    print(f"Unknown key name '{name}', defaulting to Space.")
    return Key.space


def parse_hotkey(name: str):
    """Convert a human-readable hotkey name into a pynput Key or KeyCode, or None if disabled."""
    normalized = name.strip().lower()
    if not normalized or normalized in ("none", "disabled", "null", "false"):
        return None
    if normalized in KEY_NAME_MAP:
        return KEY_NAME_MAP[normalized]
    if len(normalized) == 1:
        return KeyCode.from_char(normalized)
    return None
