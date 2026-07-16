"""Tkinter GUI for the MapleBot faithful clone."""

from __future__ import annotations

import os
import sys
import re
import time
import json
import subprocess
import threading
import csv
import io
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .bot import MapleBot
from .keys import (
    DEFAULT_LOOP_INTERVAL,
    DEFAULT_LOOP_KEY_NAME,
    DEFAULT_POTION_KEY_NAME,
    DEFAULT_SHUFFLE_INTERVAL,
    DEFAULT_SHUFFLE_MAX_HOLD,
    DEFAULT_SHUFFLE_MIN_HOLD,
    MIN_POTION_INTERVAL,
    parse_loop_key,
    parse_hotkey,
    Key,
    KeyCode,
    PYNPUT_AVAILABLE,
)
from .windows import enumerate_maple_windows
MAX_TAB_NAME_LENGTH = 24

TK_TO_PYNPUT_MAP = {
    "space": "space",
    "Return": "enter",
    "Tab": "tab",
    "Escape": "esc",
    "Left": "left",
    "Right": "right",
    "Up": "up",
    "Down": "down",
    "Home": "home",
    "End": "end",
    "Prior": "page_up",
    "Next": "page_down",
    "Insert": "insert",
    "Delete": "delete",
    "BackSpace": "backspace",
    "Caps_Lock": "caps_lock",
    "Num_Lock": "num_lock",
    "Scroll_Lock": "scroll_lock",
    "Print": "print_screen",
    "Pause": "pause",
    "Shift_L": "shift",
    "Shift_R": "shift_r",
    "Control_L": "ctrl",
    "Control_R": "ctrl_r",
    "Alt_L": "alt",
    "Alt_R": "alt_r",
    "KP_0": "numpad_0",
    "KP_1": "numpad_1",
    "KP_2": "numpad_2",
    "KP_3": "numpad_3",
    "KP_4": "numpad_4",
    "KP_5": "numpad_5",
    "KP_6": "numpad_6",
    "KP_7": "numpad_7",
    "KP_8": "numpad_8",
    "KP_9": "numpad_9",
    "KP_Decimal": "numpad_decimal",
    "KP_Add": "numpad_add",
    "KP_Subtract": "numpad_subtract",
    "KP_Multiply": "numpad_multiply",
    "KP_Divide": "numpad_divide",
}


def map_tkinter_event_to_key(event) -> str:
    # On Windows, event.keycode corresponds to the Win32 Virtual Key code (VK)
    vk = getattr(event, "keycode", 0)
    numpad_vk_to_name = {
        96: "numpad_0",
        97: "numpad_1",
        98: "numpad_2",
        99: "numpad_3",
        100: "numpad_4",
        101: "numpad_5",
        102: "numpad_6",
        103: "numpad_7",
        104: "numpad_8",
        105: "numpad_9",
        106: "numpad_multiply",
        107: "numpad_add",
        108: "numpad_separator",
        109: "numpad_subtract",
        110: "numpad_decimal",
        111: "numpad_divide",
    }
    if vk in numpad_vk_to_name:
        return numpad_vk_to_name[vk]

    sym = event.keysym
    if sym in TK_TO_PYNPUT_MAP:
        return TK_TO_PYNPUT_MAP[sym]

    if len(sym) >= 2 and sym.startswith("F") and sym[1:].isdigit():
        return sym.lower()

    if event.char and len(event.char) == 1:
        return event.char.lower()

    return sym.lower()



def default_instance_name(info: dict[str, object]) -> str:
    title = str(info.get("title") or "").strip()
    if title:
        return title
    process_name = str(info.get("process_name") or "").strip()
    if process_name:
        return process_name
    return f"HWND {info.get('hwnd')}"




def filter_deleted_instances(infos: list[dict[str, object]], deleted_hwnds: set[int]) -> list[dict[str, object]]:
    return [info for info in infos if int(info["hwnd"]) not in deleted_hwnds]

def format_tab_name(name: str, hwnd: int) -> str:
    cleaned = name.strip() or f"HWND {hwnd}"
    if len(cleaned) <= MAX_TAB_NAME_LENGTH:
        return cleaned
    return cleaned[: MAX_TAB_NAME_LENGTH - 3] + "..."


class MapleBotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MapleBot Controller")
        self.root.minsize(780, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.style = ttk.Style()
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")

        self.bots: dict[int, MapleBot] = {}
        self.window_tabs: dict[int, ttk.Frame] = {}
        self.window_vars: dict[int, dict[str, tk.Variable]] = {}
        self.window_info: dict[int, dict[str, object]] = {}
        self.instance_name_vars: dict[int, tk.StringVar] = {}
        self.deleted_instance_ids: set[int] = set()
        self.status_var = tk.StringVar(value="Detecting windows...")
        self.hint_var = tk.StringVar(value="Ready.")
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.auto_refresh_interval = tk.DoubleVar(value=10.0)
        self.auto_refresh_job: str | None = None
        self.stop_all_key_var = tk.StringVar(value="f8")
        self.keyboard_listener = None
        self.active_binder: ttk.Button | None = None
        self.active_binder_var: tk.StringVar | None = None
        self._last_bind_time: float = 0.0  # timestamp of last key-bind; used to suppress the first hotkey fire

        # Profile management
        self.profiles: dict[str, dict] = {}
        self.default_profile: str = ""
        self.tab_profile_mappings: dict[str, str] = {}  # instance_name -> profile_name
        self.profile_comboboxes: dict[int, ttk.Combobox] = {}  # hwnd -> combobox
        self._profiles_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles.json")
        self.load_profiles_from_disk()

        self._ensure_chmac_skip_init()
        self._build_layout()
        self.refresh_window_list()
        self._toggle_auto_refresh()
        self._start_global_listener()

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(10, 10, 10, 2))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="↻ Refresh", command=self.refresh_window_list, width=12).pack(side="left")
        ttk.Button(toolbar, text="⏹ Stop All", command=self.stop_all, width=12).pack(side="left", padx=(4, 0))
        ttk.Button(toolbar, text="⚙ Settings", command=self._select_settings_tab, width=12).pack(side="left", padx=(4, 0))
        ttk.Label(toolbar, text="Stop All Key:").pack(side="left", padx=(10, 4))
        stop_all_binder = self._create_key_binder(toolbar, self.stop_all_key_var)
        stop_all_binder.pack(side="left")
        def clear_stop_all():
            self.stop_all_key_var.set("none")
            stop_all_binder.config(text="none")
        ttk.Button(toolbar, text="X", width=2, command=clear_stop_all).pack(side="left", padx=(2, 0))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Checkbutton(
            toolbar,
            text="Auto refresh",
            variable=self.auto_refresh_var,
            command=self._toggle_auto_refresh,
        ).pack(side="left")
        ttk.Label(toolbar, text="Every").pack(side="left", padx=(12, 4))
        interval_spin = ttk.Spinbox(
            toolbar,
            from_=2,
            to=120,
            width=6,
            textvariable=self.auto_refresh_interval,
            command=self._toggle_auto_refresh,
        )
        interval_spin.pack(side="left")
        ttk.Label(toolbar, text="sec").pack(side="left", padx=(4, 0))
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right")

        self.window_notebook = ttk.Notebook(self.root)
        self.window_notebook.pack(fill="both", expand=True, padx=10, pady=8)

        self.placeholder_tab = ttk.Frame(self.window_notebook)
        ttk.Label(
            self.placeholder_tab,
            text="No Maplestory windows detected.\nLaunch the client and hit Refresh.",
            anchor="center",
            justify="center",
        ).pack(fill="both", expand=True, padx=40, pady=40)
        self.window_notebook.add(self.placeholder_tab, text="Waiting for windows")

        self._build_settings_tab()

        status_bar = ttk.Frame(self.root, padding=(10, 2, 10, 10))
        status_bar.pack(fill="x", side="bottom")
        ttk.Label(status_bar, textvariable=self.hint_var).pack(side="left")

    def _show_placeholder(self) -> None:
        tab_id = str(self.placeholder_tab)
        if tab_id not in self.window_notebook.tabs():
            self.window_notebook.add(self.placeholder_tab, text="Waiting for windows")
        self.window_notebook.select(self.placeholder_tab)

    def _hide_placeholder(self) -> None:
        tab_id = str(self.placeholder_tab)
        if tab_id in self.window_notebook.tabs():
            self.window_notebook.forget(self.placeholder_tab)

    def _toggle_auto_refresh(self) -> None:
        if self.auto_refresh_job is not None:
            self.root.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None
        if self.auto_refresh_var.get():
            self._schedule_auto_refresh()

    def _schedule_auto_refresh(self) -> None:
        if not self.auto_refresh_var.get():
            return
        interval_ms = max(2000, int(self.auto_refresh_interval.get() * 1000))
        self.auto_refresh_job = self.root.after(interval_ms, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        self.refresh_window_list()
        self._schedule_auto_refresh()

    # ── Profile Management ────────────────────────────────────────────────────

    def load_profiles_from_disk(self) -> None:
        """Load all saved profiles from profiles.json."""
        try:
            if os.path.exists(self._profiles_file):
                with open(self._profiles_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.profiles = data.get("profiles", {})
                self.default_profile = data.get("default_profile", "")
                self.tab_profile_mappings = data.get("tab_profile_mappings", {})
        except Exception as e:
            print(f"[Profiles] Failed to load profiles: {e}")
            self.profiles = {}
            self.default_profile = ""
            self.tab_profile_mappings = {}

    def save_profiles_to_disk(self) -> None:
        """Persist profiles to profiles.json."""
        try:
            data = {
                "profiles": self.profiles,
                "default_profile": self.default_profile,
                "tab_profile_mappings": self.tab_profile_mappings,
            }
            with open(self._profiles_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Profiles] Failed to save profiles: {e}")

    _PROFILE_VARS = [
        "loop_key", "loop_interval", "background",
        "potion_enabled", "potion_key", "potion_interval",
        "walk_enabled", "walk_interval", "walk_min", "walk_max", "walk_direction_mode",
        "skill_1", "skill_1_enabled", "skill_1_delay",
        "skill_2", "skill_2_enabled", "skill_2_delay",
        "skill_3", "skill_3_enabled", "skill_3_delay",
        "skills_interval",
        "start_key", "stop_key",
        "anti_afk_enabled", "anti_afk_interval",
        "run_timer_enabled", "run_timer_minutes",
    ]

    def _extract_vars_to_dict(self, hwnd: int) -> dict:
        """Read current vars_map values into a plain dict."""
        vars_map = self.window_vars.get(hwnd, {})
        data = {}
        for key in self._PROFILE_VARS:
            var = vars_map.get(key)
            if var is not None:
                try:
                    data[key] = var.get()
                except Exception:
                    pass
        return data

    def _apply_dict_to_vars(self, hwnd: int, data: dict) -> None:
        """Write a plain dict of values into the current vars_map."""
        vars_map = self.window_vars.get(hwnd, {})
        for key, value in data.items():
            var = vars_map.get(key)
            if var is None:
                continue
            try:
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                elif isinstance(var, tk.DoubleVar):
                    var.set(float(value))
                elif isinstance(var, tk.StringVar):
                    var.set(str(value))
            except Exception:
                pass
        # Refresh binder button labels for key binds
        self._refresh_key_binder_labels(hwnd)

    def _refresh_key_binder_labels(self, hwnd: int) -> None:
        """After programmatically updating key vars, refresh any binder button texts."""
        # Binder buttons are stored with their var reference – we trigger a trace-like refresh
        # by re-setting the same value which fires the trace.
        vars_map = self.window_vars.get(hwnd, {})
        for key in ["loop_key", "potion_key", "start_key", "stop_key",
                    "skill_1", "skill_2", "skill_3"]:
            var = vars_map.get(key)
            if var is not None:
                try:
                    var.set(var.get())
                except Exception:
                    pass

    def save_profile_from_vars(self, hwnd: int, name: str) -> None:
        """Save current tab settings as a named profile."""
        name = name.strip()
        if not name:
            return
        self.profiles[name] = self._extract_vars_to_dict(hwnd)
        instance_name = self._get_instance_name(hwnd)
        if instance_name:
            self.tab_profile_mappings[instance_name] = name
        self.save_profiles_to_disk()
        self._refresh_all_profile_comboboxes()

    def apply_profile_to_vars(self, hwnd: int, name: str) -> None:
        """Apply a named profile to the current tab."""
        if name not in self.profiles:
            messagebox.showwarning("Profile not found", f"Profile '{name}' does not exist.")
            return
        self._apply_dict_to_vars(hwnd, self.profiles[name])
        instance_name = self._get_instance_name(hwnd)
        if instance_name:
            self.tab_profile_mappings[instance_name] = name
        self.save_profiles_to_disk()

    def delete_profile(self, name: str) -> None:
        """Delete a saved profile by name."""
        if name not in self.profiles:
            return
        confirmed = messagebox.askyesno(
            "Delete profile",
            f"Delete profile '{name}'?\n\nThis cannot be undone.",
            parent=self.root,
        )
        if not confirmed:
            return
        del self.profiles[name]
        if self.default_profile == name:
            self.default_profile = ""
        # Remove from tab mappings too
        self.tab_profile_mappings = {
            k: v for k, v in self.tab_profile_mappings.items() if v != name
        }
        self.save_profiles_to_disk()
        self._refresh_all_profile_comboboxes()

    def set_default_profile(self, name: str) -> None:
        """Set a profile as the default for newly detected windows."""
        self.default_profile = name if name in self.profiles else ""
        self.save_profiles_to_disk()

    def _get_instance_name(self, hwnd: int) -> str:
        var = self.instance_name_vars.get(hwnd)
        return var.get().strip() if var else ""

    def _refresh_all_profile_comboboxes(self) -> None:
        """Update all profile dropdown lists to reflect current profile names."""
        names = sorted(self.profiles.keys())
        for combo in self.profile_comboboxes.values():
            try:
                combo["values"] = names
            except Exception:
                pass

    def _update_default_label(self, lbl: ttk.Label) -> None:
        """Refresh a label widget to show the current default profile name."""
        if self.default_profile:
            lbl.config(text=f"Default: {self.default_profile}")
        else:
            lbl.config(text="No default set")

    def _on_profile_load(self, hwnd: int, combo: ttk.Combobox) -> None:
        name = combo.get()
        if not name:
            messagebox.showwarning("No profile selected", "Please select a profile from the dropdown first.")
            return
        self.apply_profile_to_vars(hwnd, name)
        self._update_hint(hwnd, f"Profile '{name}' loaded")

    def _on_profile_save(self, hwnd: int, combo: ttk.Combobox) -> None:
        """Save As: prompt for a new name and create/overwrite that profile."""
        default = combo.get() or ""
        name = simpledialog.askstring("Save Profile", "Profile name:", initialvalue=default, parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        self.save_profile_from_vars(hwnd, name)
        combo.set(name)
        self._update_hint(hwnd, f"Profile '{name}' saved")

    def _on_profile_overwrite(self, hwnd: int, combo: ttk.Combobox) -> None:
        """Overwrite the currently selected profile without asking for a new name."""
        name = combo.get()
        if not name:
            messagebox.showwarning("No profile selected", "Please select a profile to overwrite.")
            return
        self.save_profile_from_vars(hwnd, name)
        self._update_hint(hwnd, f"Profile '{name}' overwritten")

    def _auto_apply_profile_on_tab_create(self, hwnd: int, instance_title: str) -> None:
        """Called shortly after a tab is created to restore its last-used or default profile."""
        mapped = self.tab_profile_mappings.get(instance_title, "")
        if mapped and mapped in self.profiles:
            self._apply_dict_to_vars(hwnd, self.profiles[mapped])
        elif self.default_profile and self.default_profile in self.profiles:
            self._apply_dict_to_vars(hwnd, self.profiles[self.default_profile])

    def refresh_window_list(self) -> None:
        detected_infos = enumerate_maple_windows("Maplestory")
        infos = filter_deleted_instances(detected_infos, self.deleted_instance_ids)
        self.window_info = {int(info["hwnd"]): info for info in infos}
        if self.deleted_instance_ids:
            self.status_var.set(f"{len(infos)} visible / {len(detected_infos)} detected")
        else:
            self.status_var.set(f"{len(infos)} window(s) detected")

        current_hwnds = set(self.window_tabs.keys())
        new_hwnds = set(self.window_info.keys())

        for hwnd in current_hwnds - new_hwnds:
            self._remove_instance_tab(hwnd)

        if not infos:
            self._show_placeholder()
            return

        self._hide_placeholder()
        for info in infos:
            hwnd = int(info["hwnd"])
            if hwnd not in self.window_tabs:
                self._create_window_tab(info)

    def _cancel_active_binder(self) -> None:
        if self.active_binder is not None and self.active_binder_var is not None:
            try:
                self.active_binder.config(text=self.active_binder_var.get(), state="normal")
            except Exception:
                pass
            self.root.unbind("<Key>")
            self.active_binder = None
            self.active_binder_var = None

    def _create_key_binder(self, parent: ttk.Frame, var: tk.StringVar) -> ttk.Button:
        btn = ttk.Button(parent, text=var.get(), width=12)

        def on_var_change(*args):
            if self.active_binder != btn:
                try:
                    btn.config(text=var.get())
                except Exception:
                    pass
        var.trace_add("write", on_var_change)

        def start_listening():
            self._cancel_active_binder()

            self.active_binder = btn
            self.active_binder_var = var
            btn.config(text="< Press Key >", state="disabled")

            old_focus = self.root.focus_get()
            self.root.focus_set()

            def on_key_press(event):
                self.root.unbind("<Key>")
                # Record bind time so the global listener ignores the next press
                self._last_bind_time = time.time()
                self.active_binder = None
                self.active_binder_var = None

                try:
                    btn.config(state="normal")
                except Exception:
                    pass

                key_name = map_tkinter_event_to_key(event)
                var.set(key_name)
                try:
                    btn.config(text=key_name)
                except Exception:
                    pass

                if old_focus:
                    try:
                        old_focus.focus_set()
                    except Exception:
                        pass
                return "break"

            self.root.bind("<Key>", on_key_press)

        btn.config(command=start_listening)
        return btn

    def _create_key_input(self, parent: ttk.Frame, label_text: str, var: tk.StringVar, allow_none: bool = False) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label_text, width=14).pack(side="left")
        
        binder_btn = self._create_key_binder(row, var)
        binder_btn.pack(side="left")
        
        if allow_none:
            def clear_key():
                var.set("none")
                binder_btn.config(text="none")
            ttk.Button(row, text="X", width=2, command=clear_key).pack(side="left", padx=(4, 0))
            
        ttk.Label(row, text="Click to bind key", foreground="#888").pack(side="left", padx=(8, 0))

    def _create_window_tab(self, info: dict[str, int | str]) -> None:
        hwnd = int(info["hwnd"])
        title = default_instance_name(info)
        tab = ttk.Frame(self.window_notebook, padding=10)
        name_var = tk.StringVar(value=title)
        self.instance_name_vars[hwnd] = name_var
        self.window_notebook.add(tab, text=format_tab_name(name_var.get(), hwnd))
        self.window_tabs[hwnd] = tab

        vars_map: dict[str, tk.Variable] = {
            "loop_key": tk.StringVar(value=DEFAULT_LOOP_KEY_NAME),
            "loop_interval": tk.DoubleVar(value=DEFAULT_LOOP_INTERVAL),
            "background": tk.BooleanVar(value=True),
            "potion_enabled": tk.BooleanVar(value=False),
            "potion_key": tk.StringVar(value=DEFAULT_POTION_KEY_NAME),
            "potion_interval": tk.DoubleVar(value=DEFAULT_SHUFFLE_INTERVAL),
            "walk_enabled": tk.BooleanVar(value=False),
            "walk_interval": tk.DoubleVar(value=DEFAULT_SHUFFLE_INTERVAL),
            "walk_min": tk.DoubleVar(value=DEFAULT_SHUFFLE_MIN_HOLD),
            "walk_max": tk.DoubleVar(value=DEFAULT_SHUFFLE_MAX_HOLD),
            "walk_direction_mode": tk.StringVar(value="alternate"),
            "skill_1": tk.StringVar(value="1"),
            "skill_1_enabled": tk.BooleanVar(value=False),
            "skill_1_delay": tk.DoubleVar(value=1.0),
            "skill_2": tk.StringVar(value="2"),
            "skill_2_enabled": tk.BooleanVar(value=False),
            "skill_2_delay": tk.DoubleVar(value=1.0),
            "skill_3": tk.StringVar(value="3"),
            "skill_3_enabled": tk.BooleanVar(value=False),
            "skill_3_delay": tk.DoubleVar(value=1.0),
            "skills_interval": tk.DoubleVar(value=180.0),
            "status": tk.StringVar(value="Stopped"),
            "start_key": tk.StringVar(value="none"),
            "stop_key": tk.StringVar(value="none"),
            "anti_afk_enabled": tk.BooleanVar(value=False),
            "anti_afk_interval": tk.DoubleVar(value=60.0),
            "run_timer_enabled": tk.BooleanVar(value=False),
            "run_timer_minutes": tk.DoubleVar(value=60.0),
        }
        self.window_vars[hwnd] = vars_map

        # Trace variables to dynamically update the active bot instance in real-time
        def make_trace_callback(h=hwnd, name="", var=None):
            def callback(*args):
                bot = self.bots.get(h)
                if bot is None:
                    return
                try:
                    val = var.get()
                    if name == "loop_key":
                        bot.loop_key = parse_loop_key(str(val))
                    elif name == "loop_interval":
                        bot.loop_interval = max(0.05, float(val))
                    elif name == "background":
                        bot.background_loop = bool(val)
                    elif name == "potion_enabled":
                        bot.potion_enabled = bool(val)
                    elif name == "potion_key":
                        bot.potion_key = parse_loop_key(str(val))
                    elif name == "potion_interval":
                        bot.potion_interval = max(MIN_POTION_INTERVAL, float(val))
                    elif name == "walk_enabled":
                        bot.walk_enabled = bool(val)
                    elif name == "walk_interval":
                        bot.walk_interval = max(MIN_POTION_INTERVAL, float(val))
                    elif name == "walk_min":
                        bot.walk_min_hold = max(0.0, float(val))
                    elif name == "walk_max":
                        bot.walk_max_hold = max(bot.walk_min_hold, float(val))
                    elif name == "walk_direction_mode":
                        bot.walk_direction_mode = str(val)
                    elif name == "skills_interval":
                        bot.skills_interval = max(5.0, float(val))
                    elif name == "anti_afk_enabled":
                        bot.anti_afk_enabled = bool(val)
                    elif name == "anti_afk_interval":
                        bot.anti_afk_interval = max(5.0, float(val))
                    elif name in (
                        "skill_1",
                        "skill_2",
                        "skill_3",
                        "skill_1_enabled",
                        "skill_2_enabled",
                        "skill_3_enabled",
                        "skill_1_delay",
                        "skill_2_delay",
                        "skill_3_delay",
                    ):
                        skills_to_use = []
                        for idx in (1, 2, 3):
                            if bool(vars_map[f"skill_{idx}_enabled"].get()):
                                key = parse_loop_key(str(vars_map[f"skill_{idx}"].get()))
                                try:
                                    delay = max(0.1, float(vars_map[f"skill_{idx}_delay"].get()))
                                except (ValueError, tk.TclError):
                                    delay = 1.0
                                skills_to_use.append((key, delay))
                        bot.skills_to_use = skills_to_use
                    elif name in ("run_timer_enabled", "run_timer_minutes"):
                        if bool(vars_map["run_timer_enabled"].get()):
                            try:
                                mins = float(vars_map["run_timer_minutes"].get())
                                bot.run_duration = max(1.0, mins) * 60.0
                            except (ValueError, tk.TclError):
                                bot.run_duration = None
                        else:
                            bot.run_duration = None
                except Exception:
                    pass
            return callback

        for name, var in vars_map.items():
            var.trace_add("write", make_trace_callback(hwnd, name, var))

        # ── Fixed header (always visible) ────────────────────────────────────
        header = ttk.Frame(tab)
        header.pack(fill="x")
        ttk.Label(header, textvariable=self.instance_name_vars[hwnd], font=("", 14, "bold")).pack(side="left")
        ttk.Label(header, textvariable=vars_map["status"]).pack(side="right")
        ttk.Label(tab, text=f"HWND {hwnd}", foreground="#888").pack(anchor="w", pady=(0, 4))
        ttk.Separator(tab).pack(fill="x", pady=(0, 6))

        # ── Scrollable body ───────────────────────────────────────────────────
        scroll_outer = ttk.Frame(tab)
        scroll_outer.pack(fill="both", expand=True)

        _canvas = tk.Canvas(scroll_outer, borderwidth=0, highlightthickness=0)
        _vbar = ttk.Scrollbar(scroll_outer, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_vbar.set)
        _vbar.pack(side="right", fill="y")
        _canvas.pack(side="left", fill="both", expand=True)

        settings_frame = ttk.Frame(_canvas)
        canvas_window = _canvas.create_window((0, 0), window=settings_frame, anchor="nw")

        def _on_settings_configure(event, c=_canvas, cw=canvas_window):
            c.configure(scrollregion=c.bbox("all"))
            # Keep inner frame same width as canvas
            c.itemconfig(cw, width=c.winfo_width())

        def _on_canvas_resize(event, c=_canvas, cw=canvas_window):
            c.itemconfig(cw, width=event.width)

        settings_frame.bind("<Configure>", _on_settings_configure)
        _canvas.bind("<Configure>", _on_canvas_resize)

        # Mouse-wheel scroll (bind only while cursor is over canvas area)
        def _on_mousewheel(event, c=_canvas):
            c.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(event, c=_canvas):
            c.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(event, c=_canvas):
            c.unbind_all("<MouseWheel>")

        _canvas.bind("<Enter>", _bind_wheel)
        _canvas.bind("<Leave>", _unbind_wheel)
        settings_frame.bind("<Enter>", _bind_wheel)
        settings_frame.bind("<Leave>", _unbind_wheel)

        # ── Profile Manager ───────────────────────────────────────────────────
        profile_frame = ttk.LabelFrame(settings_frame, text="Profile Manager", padding=8)
        profile_frame.pack(fill="x", pady=(0, 8))

        profile_row1 = ttk.Frame(profile_frame)
        profile_row1.pack(fill="x", pady=(0, 4))
        ttk.Label(profile_row1, text="Profile:", width=10).pack(side="left")
        profile_names = sorted(self.profiles.keys())
        profile_combo = ttk.Combobox(profile_row1, values=profile_names, width=22, state="readonly")
        # Pre-select current profile for this tab if mapped
        instance_title = default_instance_name(info)
        mapped = self.tab_profile_mappings.get(instance_title, "")
        if mapped and mapped in self.profiles:
            profile_combo.set(mapped)
        elif self.default_profile and self.default_profile in self.profiles:
            profile_combo.set(self.default_profile)
        profile_combo.pack(side="left", padx=(4, 0))
        self.profile_comboboxes[hwnd] = profile_combo

        ttk.Button(
            profile_row1, text="Load",
            command=lambda h=hwnd, cb=profile_combo: self._on_profile_load(h, cb)
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            profile_row1, text="Save As",
            command=lambda h=hwnd, cb=profile_combo: self._on_profile_save(h, cb)
        ).pack(side="left", padx=(4, 0))
        ttk.Button(
            profile_row1, text="Overwrite",
            command=lambda h=hwnd, cb=profile_combo: self._on_profile_overwrite(h, cb)
        ).pack(side="left", padx=(4, 0))
        ttk.Button(
            profile_row1, text="Delete",
            command=lambda cb=profile_combo: self.delete_profile(cb.get())
        ).pack(side="left", padx=(4, 0))

        profile_row2 = ttk.Frame(profile_frame)
        profile_row2.pack(fill="x")
        def _on_set_default(cb=profile_combo):
            name = cb.get()
            if not name:
                messagebox.showwarning("No profile selected", "Please select a profile first.")
                return
            self.set_default_profile(name)
            self._update_default_label(default_lbl)
        ttk.Button(profile_row2, text="Set as Default", command=_on_set_default).pack(side="left")
        default_lbl = ttk.Label(profile_row2, foreground="#777", font=("", 8, "italic"))
        default_lbl.pack(side="left", padx=(8, 0))
        self._update_default_label(default_lbl)

        loop_frame = ttk.LabelFrame(settings_frame, text="Attack loop", padding=8)
        loop_frame.pack(fill="x", pady=(0, 8))
        self._create_key_input(loop_frame, "Loop key", vars_map["loop_key"])
        self._create_key_input(loop_frame, "Start key", vars_map["start_key"], allow_none=True)
        self._create_key_input(loop_frame, "Stop key", vars_map["stop_key"], allow_none=True)
        loop_controls = ttk.Frame(loop_frame)
        loop_controls.pack(fill="x", pady=2)
        ttk.Label(loop_controls, text="Interval (s)", width=14).pack(side="left")
        ttk.Scale(loop_controls, from_=0.1, to=5.0, orient="horizontal", variable=vars_map["loop_interval"]).pack(
            side="left", fill="x", expand=True
        )
        ttk.Entry(loop_controls, textvariable=vars_map["loop_interval"], width=8).pack(side="left", padx=(6, 0))
        ttk.Label(
            loop_frame,
            text="* Note: Attacks & potions run in the background; walking will briefly focus the window.",
            foreground="#555",
            font=("", 8, "italic"),
        ).pack(anchor="w", pady=(4, 0))

        potion_frame = ttk.LabelFrame(settings_frame, text="Potion", padding=8)
        potion_frame.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(potion_frame, text="Enable potion auto-use", variable=vars_map["potion_enabled"]).pack(
            anchor="w"
        )
        self._create_key_input(potion_frame, "Potion key", vars_map["potion_key"])
        potion_controls = ttk.Frame(potion_frame)
        potion_controls.pack(fill="x", pady=2)
        ttk.Label(potion_controls, text="Interval (s)", width=14).pack(side="left")
        ttk.Scale(
            potion_controls,
            from_=MIN_POTION_INTERVAL,
            to=300.0,
            orient="horizontal",
            variable=vars_map["potion_interval"],
        ).pack(side="left", fill="x", expand=True)
        ttk.Entry(potion_controls, textvariable=vars_map["potion_interval"], width=8).pack(side="left", padx=(6, 0))

        walk_frame = ttk.LabelFrame(settings_frame, text="Walk", padding=8)
        walk_frame.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(walk_frame, text="Enable walk (strafing)", variable=vars_map["walk_enabled"]).pack(anchor="w")
        walk_controls = ttk.Frame(walk_frame)
        walk_controls.pack(fill="x", pady=2)
        ttk.Label(walk_controls, text="Interval (s)", width=14).pack(side="left")
        ttk.Scale(
            walk_controls,
            from_=MIN_POTION_INTERVAL,
            to=300.0,
            orient="horizontal",
            variable=vars_map["walk_interval"],
        ).pack(side="left", fill="x", expand=True)
        ttk.Entry(walk_controls, textvariable=vars_map["walk_interval"], width=8).pack(side="left", padx=(6, 0))

        walk_hold_row = ttk.Frame(walk_frame)
        walk_hold_row.pack(fill="x", pady=2)
        ttk.Label(walk_hold_row, text="Hold min/max (s)", width=14).pack(side="left")
        ttk.Entry(walk_hold_row, textvariable=vars_map["walk_min"], width=8).pack(side="left")
        ttk.Entry(walk_hold_row, textvariable=vars_map["walk_max"], width=8).pack(side="left", padx=(4, 0))

        anti_afk_frame = ttk.LabelFrame(settings_frame, text="Anti-AFK", padding=8)
        anti_afk_frame.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(anti_afk_frame, text="Enable Anti-AFK jitter", variable=vars_map["anti_afk_enabled"]).pack(anchor="w")
        anti_afk_controls = ttk.Frame(anti_afk_frame)
        anti_afk_controls.pack(fill="x", pady=2)
        ttk.Label(anti_afk_controls, text="Interval (s)", width=14).pack(side="left")
        ttk.Scale(
            anti_afk_controls,
            from_=5.0,
            to=300.0,
            orient="horizontal",
            variable=vars_map["anti_afk_interval"],
        ).pack(side="left", fill="x", expand=True)
        ttk.Entry(anti_afk_controls, textvariable=vars_map["anti_afk_interval"], width=8).pack(side="left", padx=(6, 0))

        # Walk / Anti-AFK direction mode
        direction_frame = ttk.LabelFrame(settings_frame, text="Movement Direction", padding=8)
        direction_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(direction_frame, text="Walk & Anti-AFK direction:").pack(side="left", padx=(0, 8))
        for mode_val, mode_label in (("alternate", "Alternate L/R"), ("always_left", "Always Left"), ("always_right", "Always Right")):
            ttk.Radiobutton(
                direction_frame,
                text=mode_label,
                variable=vars_map["walk_direction_mode"],
                value=mode_val,
            ).pack(side="left", padx=(0, 10))

        # Run timer
        timer_frame = ttk.LabelFrame(settings_frame, text="Run Timer", padding=8)
        timer_frame.pack(fill="x", pady=(0, 8))
        timer_row = ttk.Frame(timer_frame)
        timer_row.pack(fill="x")
        ttk.Checkbutton(timer_row, text="Auto-stop after", variable=vars_map["run_timer_enabled"]).pack(side="left")
        ttk.Entry(timer_row, textvariable=vars_map["run_timer_minutes"], width=8).pack(side="left", padx=(6, 0))
        ttk.Label(timer_row, text="minutes  (leave unchecked = run forever)").pack(side="left", padx=(4, 0))

        # ── Controls bar + skill frame go INSIDE the scrollable settings_frame ──
        controls_frame = ttk.Frame(settings_frame)
        controls_frame.pack(fill="x", pady=(4, 6))
        ttk.Button(controls_frame, text="Start Loop", command=lambda h=hwnd: self.start_bot(h)).pack(side="left")
        ttk.Button(controls_frame, text="Stop Loop", command=lambda h=hwnd: self.stop_bot(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Tap Potion", command=lambda h=hwnd: self.tap_potion(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Focus Window", command=lambda h=hwnd: self.focus_window(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Identify Window", command=lambda h=hwnd: self.identify_window(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Auto Detect Info", command=lambda h=hwnd: self.auto_detect_name_job(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Rename", command=lambda h=hwnd: self.rename_instance(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Delete Instance", command=lambda h=hwnd: self.delete_instance(h)).pack(
            side="left", padx=(4, 0)
        )

        skill_frame = ttk.LabelFrame(settings_frame, text="Quick skills (Auto buff)", padding=8)
        skill_frame.pack(fill="x", pady=(0, 8))

        for idx, key_name in enumerate(("skill_1", "skill_2", "skill_3"), start=1):
            row = ttk.Frame(skill_frame)
            row.pack(fill="x", pady=2)
            ttk.Checkbutton(
                row,
                text=f"Auto Skill {idx}",
                variable=vars_map[f"{key_name}_enabled"],
            ).pack(side="left")
            binder_btn = self._create_key_binder(row, vars_map[key_name])
            binder_btn.pack(side="left", padx=(10, 0))
            ttk.Label(row, text="Delay (s):").pack(side="left", padx=(10, 2))
            ttk.Entry(row, textvariable=vars_map[f"{key_name}_delay"], width=6).pack(side="left")
            ttk.Button(row, text="Tap", command=lambda h=hwnd, k=key_name: self.send_skill(h, k)).pack(
                side="left", padx=(8, 0)
            )

        # Auto-apply profile after all widgets are created
        self.root.after(50, lambda h=hwnd, t=instance_title: self._auto_apply_profile_on_tab_create(h, t))

    def _remove_instance_tab(self, hwnd: int) -> None:
        tab = self.window_tabs.pop(hwnd, None)
        if tab is not None:
            self.window_notebook.forget(tab)
        self.window_vars.pop(hwnd, None)
        self.instance_name_vars.pop(hwnd, None)
        self.profile_comboboxes.pop(hwnd, None)
        bot = self.bots.pop(hwnd, None)
        if bot is not None:
            bot.stop_loop()

    def delete_instance(self, hwnd: int) -> None:
        name_var = self.instance_name_vars.get(hwnd)
        display_name = name_var.get() if name_var is not None else str(self.window_info.get(hwnd, {}).get("title", hwnd))
        confirmed = messagebox.askyesno(
            "Delete instance",
            f"Remove {display_name} from this list?\n\nThis will not close the game process.",
            parent=self.root,
        )
        if not confirmed:
            return
        self.deleted_instance_ids.add(hwnd)
        self._remove_instance_tab(hwnd)
        self.refresh_window_list()
        self.hint_var.set(f"Deleted {display_name} from the instance list.")
    def rename_instance(self, hwnd: int) -> None:
        info = self.window_info.get(hwnd, {"hwnd": hwnd})
        current = self.instance_name_vars.get(hwnd)
        initial = current.get() if current is not None else default_instance_name(info)
        old_name = initial  # capture before dialog
        new_name = simpledialog.askstring("Rename instance", "Instance name:", initialvalue=initial, parent=self.root)
        if new_name is None:
            return
        cleaned = new_name.strip() or default_instance_name(info)
        if hwnd not in self.instance_name_vars:
            self.instance_name_vars[hwnd] = tk.StringVar(value=cleaned)
        else:
            self.instance_name_vars[hwnd].set(cleaned)
        tab = self.window_tabs.get(hwnd)
        if tab is not None:
            self.window_notebook.tab(tab, text=format_tab_name(cleaned, hwnd))
        self._update_hint(hwnd, f"Renamed to {cleaned}")
        # Update tab->profile mapping to use the new name
        if old_name and old_name in self.tab_profile_mappings:
            self.tab_profile_mappings[cleaned] = self.tab_profile_mappings.pop(old_name)
            self.save_profiles_to_disk()



    def identify_window(self, hwnd: int) -> None:
        info = self.window_info.get(hwnd, {})
        if hwnd <= 0 or not bool(info.get("has_window", hwnd > 0)):
            messagebox.showwarning(
                "No window handle",
                "This instance was found as a process, but Windows has not exposed a controllable window handle yet.",
            )
            return

        bot = self._ensure_bot(hwnd)
        if bot.identify_window():
            self._update_hint(hwnd, "Window identified")
        else:
            messagebox.showwarning("Identify failed", "Could not move this window for identification.")

    def auto_detect_name_job(self, hwnd: int) -> None:
        import os
        import time
        import subprocess
        import re
        import tempfile
        import win32gui
        import win32ui
        import ctypes

        info = self.window_info.get(hwnd, {})
        if hwnd <= 0 or not bool(info.get("has_window", hwnd > 0)):
            messagebox.showwarning(
                "No window handle",
                "This instance was found as a process, but Windows has not exposed a controllable window handle yet.",
            )
            return

        bot = self._ensure_bot(hwnd)
        
        # 1. Bring window to foreground
        if not bot.activate_window():
            messagebox.showerror("OCR Error", "Could not bring the game window to the foreground.")
            return
        
        time.sleep(0.5)
        
        # 2. Press 's' to open Stat window
        if bot.keyboard:
            bot.is_simulating_movement = True
            try:
                from pynput.keyboard import KeyCode
                char_s = KeyCode.from_char('s')
                bot.keyboard.press(char_s)
                time.sleep(0.08)
                bot.keyboard.release(char_s)
            finally:
                bot.is_simulating_movement = False
                
        time.sleep(0.6)
        
        # 3. Take a screenshot
        import tempfile
        temp_bmp = os.path.join(tempfile.gettempdir(), "maplebot_ocr_capture.bmp")
        
        success = False
        try:
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bot_coord = rect
            w = right - left
            h = bot_coord - top
            
            if w > 0 and h > 0:
                # Capture from screen DC to capture hardware accelerated DirectX backbuffer
                import win32con
                hwndDC = win32gui.GetDC(0)
                mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
                saveDC = mfcDC.CreateCompatibleDC()
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
                saveDC.SelectObject(saveBitMap)
                
                # Copy from screen coordinates directly
                saveDC.BitBlt((0, 0), (w, h), mfcDC, (left, top), win32con.SRCCOPY)
                
                saveBitMap.SaveBitmapFile(saveDC, temp_bmp)
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(0, hwndDC)
                success = True
        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            messagebox.showerror(
                "Capture Failed",
                "Failed to capture a screenshot of the window.\n\n"
                "If your game client is running as Administrator, you must run this bot as Administrator as well so Windows allows it to capture and send keystrokes."
            )
            if os.path.exists(temp_bmp):
                try: os.remove(temp_bmp)
                except Exception: pass
            return
            
        # 4. Close 's' window immediately
        if bot.keyboard:
            bot.is_simulating_movement = True
            try:
                from pynput.keyboard import KeyCode
                char_s = KeyCode.from_char('s')
                bot.keyboard.press(char_s)
                time.sleep(0.08)
                bot.keyboard.release(char_s)
            finally:
                bot.is_simulating_movement = False
                
        if not success or not os.path.exists(temp_bmp):
            if os.path.exists(temp_bmp):
                try: os.remove(temp_bmp)
                except Exception: pass
            messagebox.showerror("OCR Error", "Failed to capture window screenshot.")
            return

        # 5. Run PowerShell OCR
        ps_script = f"""
        Add-Type -AssemblyName System.Drawing
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        
        # Scale the image to 3x using NearestNeighbor to make pixel fonts highly legible
        $img = [System.Drawing.Image]::FromFile("{temp_bmp}")
        $newBmp = New-Object System.Drawing.Bitmap ($img.Width * 3), ($img.Height * 3)
        $g = [System.Drawing.Graphics]::FromImage($newBmp)
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
        $g.DrawImage($img, 0, 0, $newBmp.Width, $newBmp.Height)
        $img.Dispose()
        
        # Save enhanced image back to the temp path
        $newBmp.Save("{temp_bmp}")
        $newBmp.Dispose()
        $g.Dispose()
        
        # Run standard WinRT OCR on the enhanced image
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -like 'IAsyncOperation*' }})[0]
        function Await-WinRt ($winRtTask, $resultType) {{
            $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
            $netTask = $asTask.Invoke($null, @($winRtTask))
            $netTask.Wait(-1) | Out-Null
            return $netTask.Result
        }}
        $file = Get-Item "{temp_bmp}"
        $stream = $file.OpenRead()
        $winrtStream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($stream)
        $decoderType = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
        $decoderOp = $decoderType::CreateAsync($winrtStream)
        $decoder = Await-WinRt $decoderOp $decoderType
        $bitmapOp = $decoder.GetSoftwareBitmapAsync()
        $bitmap = Await-WinRt $bitmapOp ([Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime])
        $ocrType = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
        $engine = $ocrType::TryCreateFromUserProfileLanguages()
        $resultOp = $engine.RecognizeAsync($bitmap)
        $result = Await-WinRt $resultOp ([Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime])
        foreach ($line in $result.Lines) {{
            Write-Output $line.Text
        }}
        $stream.Close()
        """
        
        try:
            proc = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            stdout, stderr = proc.communicate()
        except Exception as e:
            stdout = ""
            stderr = str(e)
            
        if stdout is None:
            stdout = ""
        if stderr is None:
            stderr = ""
            
        # Create diagnostic preview file
        try:
            preview_file = os.path.join(tempfile.gettempdir(), "maplebot_ocr_preview.md")
            temp_bmp_forward = temp_bmp.replace('\\', '/')
            with open(preview_file, "w", encoding="utf-8") as f:
                f.write(f"""# OCR Screen Capture Diagnostic Preview

Here is the screenshot captured by the bot when attempting to run OCR:

![OCR Capture](file:///{temp_bmp_forward})

### OCR Raw Output:
```
{stdout}
```
""")
            print(f"[OCR Diagnostic] Written preview to {preview_file}")
        except Exception as e:
            print(f"Failed to write diagnostic preview: {e}")
            
        if stderr and "OcrEngine" in stderr:
            messagebox.showerror("OCR Error", "Windows native OCR component is missing or failed.")
            return
            
        # 6. Parse Name and Job
        name = ""
        job = ""
        
        lines = [l.strip() for l in stdout.splitlines() if l.strip()]
        print(f"[OCR Raw Lines] Detected {len(lines)} lines: {lines}")
        
        # Search for Name (Label-based)
        for idx, line in enumerate(lines):
            match_indicator = re.search(r'\b(Name|Nane|Neme|Nare|Nerne|Name:)\b', line, re.IGNORECASE)
            if match_indicator:
                after_part = line[match_indicator.end():].strip()
                after_clean = re.sub(r'^[:;.\-=\s]+', '', after_part).strip()
                name_words = re.findall(r'[A-Za-z0-9_-]+', after_clean)
                if name_words and len(name_words[0]) >= 3:
                    name = name_words[0]
                    break
                
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    next_words = re.findall(r'^[A-Za-z0-9_-]{3,15}$', next_line)
                    if next_words:
                        name = next_words[0]
                        break

        # Search for Job
        job_idx = -1
        for idx, line in enumerate(lines):
            match_indicator = re.search(r'\b(Job|J0b|Jcb|Job:)\b', line, re.IGNORECASE)
            if match_indicator:
                job_idx = idx
                after_part = line[match_indicator.end():].strip()
                after_clean = re.sub(r'^[:;.\-=\s]+', '', after_part).strip()
                if len(after_clean) >= 3:
                    job = after_clean
                    break
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    if len(next_line) >= 3:
                        job = next_line
                        break

        # Fallback search for Job using known list
        known_jobs = [
            "beginner", "noblesse", "legend",
            "warrior", "fighter", "crusader", "hero", "spearman", "dragon knight", "dark knight", "page", "white knight", "paladin",
            "magician", "cleric", "priest", "bishop", "wizard", "mage", "arch mage", "archmage",
            "bowman", "archer", "hunter", "ranger", "bowmaster", "crossbowman", "sniper", "marksman",
            "thief", "rogue", "assassin", "hermit", "night lord", "bandit", "chief bandit", "shadower",
            "pirate", "brawler", "marauder", "buccaneer", "gunslinger", "outlaw", "corsair",
            "dawn warrior", "blaze wizard", "wind archer", "night walker", "thunder breaker", "aran",
            "swordman", "swordsman"
        ]
        if not job:
            for idx, line in enumerate(lines):
                line_lower = line.lower()
                for kj in known_jobs:
                    if kj in line_lower:
                        job_idx = idx
                        if "job" in line_lower:
                            m = re.search(r'\bjob\s*[:;.-]?\s*(.+)', line, re.IGNORECASE)
                            if m:
                                job = m.group(1).strip()
                            else:
                                job = kj.capitalize()
                        else:
                            job = kj.capitalize()
                        break
                if job:
                    break

        # Proximity-based name fallback: check around the Job line if name wasn't found
        if not name and job_idx != -1:
            name_labels = ["name", "nane", "neme", "nare", "nerne", "namo", "hame", "mame", "ability", "character", "stat", "stats", "lv", "level", "hp", "mp", "exp", "ap", "sp", "str", "dex", "int", "luk", "guild", "alliance"]
            candidates = []
            for offset in [-1, 1, -2, 2, -3, 3]:
                check_idx = job_idx + offset
                if 0 <= check_idx < len(lines):
                    candidate_line = lines[check_idx].strip()
                    
                    has_separator = any(char in candidate_line for char in [":", ";", "-", "="])
                    if has_separator:
                        parts = re.split(r'[:;\-=]', candidate_line, maxsplit=1)
                        potential_name = parts[1].strip()
                    else:
                        words = candidate_line.split()
                        if words and words[0].lower() in name_labels:
                            potential_name = " ".join(words[1:]).strip()
                        else:
                            potential_name = candidate_line.strip()
                    
                    clean_name = re.sub(r'[^A-Za-z0-9_-]', '', potential_name)
                    clean_name_lower = clean_name.lower()
                    
                    if 3 <= len(clean_name) <= 15 and clean_name_lower not in name_labels:
                        if clean_name_lower != job.lower() and clean_name_lower not in [kj.lower() for kj in known_jobs]:
                            # Scoring: Higher score for cleaner/closer candidate names
                            score = 10 - abs(offset) # closer is better
                            if has_separator:
                                score -= 3 # colons suggest key-value instead of character name
                            if " " in candidate_line:
                                score -= 2 # space suggests multiple words
                            candidates.append((score, clean_name))
            
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                name = candidates[0][1]
                print(f"[OCR Parser] Proximity-based name extraction matched: '{name}' (candidates evaluated: {candidates})")
                    
        if name or job:
            display_name = ""
            if name and job:
                display_name = f"{name} ({job})"
            elif name:
                display_name = name
            else:
                display_name = job
                
            self.instance_name_vars[hwnd].set(display_name)
            tab_widget = self.window_tabs.get(hwnd)
            if tab_widget is not None:
                self.window_notebook.tab(tab_widget, text=format_tab_name(display_name, hwnd))
            self._update_hint(hwnd, f"Detected: Name={name or '?'}, Job={job or '?'}")
            messagebox.showinfo("Detection Succeeded", f"Auto-detected character details:\n\nName: {name or 'Unknown'}\nJob: {job or 'Unknown'}")
        else:
            preview = "\n".join(lines[:10])
            messagebox.showwarning(
                "Detection Failed",
                f"Could not find 'Name' or 'Job' fields on the screen.\n\nMake sure your Stat (S) window is open and fully visible on the screen.\n\nOCR Raw Output Preview:\n{preview}"
            )

    def _update_hint(self, hwnd: int, message: str) -> None:
        name_var = self.instance_name_vars.get(hwnd)
        title = name_var.get() if name_var is not None else self.window_info.get(hwnd, {}).get("title", "Window")
        self.hint_var.set(f"{title}: {message}")

    def _get_float(self, var: tk.Variable, label: str, minimum: float) -> float:
        try:
            value = float(var.get())
        except (ValueError, tk.TclError):
            raise ValueError(f"{label} must be a number.")
        return max(minimum, value)

    def _build_bot_from_vars(self, hwnd: int) -> MapleBot:
        vars_map = self.window_vars[hwnd]
        loop_interval = self._get_float(vars_map["loop_interval"], "Loop interval", 0.05)
        potion_interval = self._get_float(vars_map["potion_interval"], "Potion interval", MIN_POTION_INTERVAL)
        walk_interval = self._get_float(vars_map["walk_interval"], "Walk interval", 5.0)
        walk_min = self._get_float(vars_map["walk_min"], "Walk min", 0.0)
        walk_max = self._get_float(vars_map["walk_max"], "Walk max", walk_min)

        skills_interval = self._get_float(vars_map["skills_interval"], "Skills interval", 5.0)
        skills_to_use = []
        for idx in (1, 2, 3):
            if bool(vars_map[f"skill_{idx}_enabled"].get()):
                key = parse_loop_key(str(vars_map[f"skill_{idx}"].get()))
                try:
                    delay = max(0.1, float(vars_map[f"skill_{idx}_delay"].get()))
                except (ValueError, tk.TclError):
                    delay = 1.0
                skills_to_use.append((key, delay))

        anti_afk_interval = self._get_float(vars_map["anti_afk_interval"], "Anti-AFK interval", 5.0)

        run_duration: float | None = None
        if bool(vars_map["run_timer_enabled"].get()):
            try:
                mins = float(vars_map["run_timer_minutes"].get())
                run_duration = max(1.0, mins) * 60.0
            except (ValueError, tk.TclError):
                run_duration = None

        return MapleBot(
            loop_key=parse_loop_key(str(vars_map["loop_key"].get())),
            loop_interval=loop_interval,
            background_loop=bool(vars_map["background"].get()),
            potion_key=parse_loop_key(str(vars_map["potion_key"].get())),
            potion_enabled=bool(vars_map["potion_enabled"].get()),
            potion_interval=potion_interval,
            walk_enabled=bool(vars_map["walk_enabled"].get()),
            walk_interval=walk_interval,
            walk_min_hold=walk_min,
            walk_max_hold=walk_max,
            walk_direction_mode=str(vars_map["walk_direction_mode"].get()),
            skills_interval=skills_interval,
            skills_to_use=skills_to_use,
            anti_afk_enabled=bool(vars_map["anti_afk_enabled"].get()),
            anti_afk_interval=anti_afk_interval,
            run_duration=run_duration,
            window_title=str(self.window_info.get(hwnd, {}).get("title", "Maplestory")),
            target_hwnd=hwnd,
        )

    def start_bot(self, hwnd: int) -> None:
        try:
            bot = self._build_bot_from_vars(hwnd)
        except ValueError as err:
            messagebox.showerror("Invalid value", str(err))
            return

        existing = self.bots.get(hwnd)
        if existing is not None:
            existing.stop_loop()
        self.bots[hwnd] = bot
        bot.refresh_windows()
        if not bot.windows:
            messagebox.showwarning("Window not found", "Target window no longer exists.")
            return
        bot.start_loop()
        self.window_vars[hwnd]["status"].set("Running")
        self._update_hint(hwnd, "Loop started")

    def stop_bot(self, hwnd: int) -> None:
        bot = self.bots.get(hwnd)
        if bot is not None:
            bot.stop_loop()
        if hwnd in self.window_vars:
            self.window_vars[hwnd]["status"].set("Stopped")
        self._update_hint(hwnd, "Loop stopped")

    def focus_window(self, hwnd: int) -> None:
        bot = self._ensure_bot(hwnd)
        if bot.activate_window():
            self._update_hint(hwnd, "Window focused")
        else:
            messagebox.showwarning("Focus failed", "Could not bring the window to front.")

    def tap_potion(self, hwnd: int) -> None:
        bot = self._ensure_bot(hwnd)
        if bot._tap_key(bot.potion_key):
            self._update_hint(hwnd, "Potion tapped")
        else:
            messagebox.showwarning("Action failed", "Could not tap potion key for this window.")

    def send_skill(self, hwnd: int, key_name: str) -> None:
        bot = self._ensure_bot(hwnd)
        vars_map = self.window_vars[hwnd]
        key = parse_loop_key(str(vars_map[key_name].get()))
        if bot._tap_key(key):
            self._update_hint(hwnd, f"{key_name.replace('_', ' ').capitalize()} tapped")
        else:
            messagebox.showwarning("Action failed", f"Could not tap {key_name} for this window.")

    def _ensure_bot(self, hwnd: int) -> MapleBot:
        bot = self.bots.get(hwnd)
        if bot is None:
            try:
                bot = self._build_bot_from_vars(hwnd)
            except ValueError as err:
                messagebox.showerror("Invalid value", str(err))
                raise
            bot.refresh_windows()
            self.bots[hwnd] = bot
        return bot

    def stop_all(self) -> None:
        for bot in list(self.bots.values()):
            bot.stop_loop()
        for vars_map in self.window_vars.values():
            vars_map["status"].set("Stopped")
        self.hint_var.set("All loops stopped.")

    def on_close(self) -> None:
        if self.auto_refresh_job is not None:
            self.root.after_cancel(self.auto_refresh_job)
        if self.keyboard_listener is not None:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
        self.stop_all()
        self.root.destroy()

    def _start_global_listener(self) -> None:
        if not PYNPUT_AVAILABLE:
            return

        from pynput import keyboard

        def match_key(event_key, config_key_str: str) -> bool:
            config_key = parse_hotkey(config_key_str)
            if config_key is None:
                return False
            if event_key == config_key:
                return True
            if isinstance(event_key, KeyCode) and isinstance(config_key, KeyCode):
                if event_key.char is not None and config_key.char is not None:
                    return event_key.char.lower() == config_key.char.lower()
                if event_key.vk is not None and config_key.vk is not None:
                    return event_key.vk == config_key.vk
            return False

        def get_active_tab_hwnd() -> int | None:
            try:
                selected_tab = self.window_notebook.select()
                if not selected_tab:
                    return None
                for h, tab in self.window_tabs.items():
                    if str(tab) == str(selected_tab):
                        return h
            except Exception:
                pass
            return None

        def on_press(key):
            try:
                # Ignore key events while actively choosing/binding a key in the GUI
                if self.active_binder is not None:
                    return
                # Ignore key events briefly after a key has been bound to prevent
                # the bound key from immediately triggering the action it was just assigned.
                if time.time() - self._last_bind_time < 0.5:
                    return
                print(f"[Listener] Key pressed: {key}")

                # Get the foreground (focused) window HWND and PID
                fg_hwnd = 0
                try:
                    import win32gui
                    fg_hwnd = win32gui.GetForegroundWindow()
                except Exception:
                    pass
                
                if not fg_hwnd:
                    try:
                        import ctypes
                        fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                    except Exception:
                        pass

                fg_pid = None
                if fg_hwnd:
                    try:
                        import win32process
                        _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
                    except Exception:
                        try:
                            import ctypes
                            pid_val = ctypes.c_ulong()
                            ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(pid_val))
                            fg_pid = pid_val.value
                        except Exception:
                            pass

                is_left = (key == keyboard.Key.left)
                is_right = (key == keyboard.Key.right)

                if is_left or is_right:
                    matched_bot = None
                    if fg_hwnd:
                        for h, bot in self.bots.items():
                            if not bot.running:
                                continue
                            if h == fg_hwnd:
                                matched_bot = bot
                                break
                            info = self.window_info.get(h)
                            if info and info.get("pid") == fg_pid:
                                matched_bot = bot
                                break

                    dir_str = "left" if is_left else "right"
                    if matched_bot:
                        if not matched_bot.is_simulating_movement:
                            matched_bot.last_known_direction = dir_str
                            print(f"[Listener] Matched active window (HWND: {fg_hwnd}, PID: {fg_pid}). Direction set to {dir_str}.")
                        else:
                            print(f"[Listener] Ignored bot-simulated movement keypress for matched bot (HWND: {fg_hwnd})")
                    else:
                        updated_any = False
                        for bot in self.bots.values():
                            if bot.running and not bot.is_simulating_movement:
                                bot.last_known_direction = dir_str
                                updated_any = True
                        if updated_any:
                            print(f"[Listener] Focused window did not match any bot (HWND: {fg_hwnd}, PID: {fg_pid}). Updated running bots to {dir_str}.")

                # 1. Check Stop All Hotkey
                if match_key(key, self.stop_all_key_var.get()):
                    self.root.after(0, self.stop_all)
                    return

                # 2. Check individual instance Start/Stop Keys (only affect the focused window)
                for hwnd, vars_map in list(self.window_vars.items()):
                    is_focused = False
                    if fg_hwnd:
                        if fg_hwnd == hwnd:
                            is_focused = True
                        else:
                            info = self.window_info.get(hwnd)
                            if info and info.get("pid") == fg_pid:
                                is_focused = True
                            elif fg_pid == os.getpid():
                                # Focused window is the GUI or its dialogs. Check if active tab matches.
                                active_tab_hwnd = get_active_tab_hwnd()
                                if active_tab_hwnd == hwnd:
                                    is_focused = True

                    if not is_focused:
                        continue

                    status = vars_map.get("status")
                    if status is not None:
                        if status.get() == "Running":
                            stop_key_str = vars_map.get("stop_key")
                            if stop_key_str is not None and match_key(key, stop_key_str.get()):
                                self.root.after(0, self.stop_bot, hwnd)
                        elif status.get() == "Stopped":
                            start_key_str = vars_map.get("start_key")
                            if start_key_str is not None and match_key(key, start_key_str.get()):
                                self.root.after(0, self.start_bot, hwnd)
            except RuntimeError:
                pass

        try:
            self.keyboard_listener = keyboard.Listener(on_press=on_press)
            self.keyboard_listener.start()
            print("Global keyboard listener started.")
        except Exception as e:
            print(f"Failed to start global keyboard listener: {e}")

    def _check_admin(self) -> bool:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _relaunch_as_admin(self) -> None:
        import ctypes
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                " ".join(sys.argv), 
                None, 
                1
            )
            self.root.destroy()
        except Exception as e:
            messagebox.showerror(
                "Elevation Failed", 
                f"Failed to relaunch as administrator: {e}"
            )

    def _get_chmac_path(self) -> tuple[str, str]:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chmac_dir = os.path.join(project_root, "MacChanger", "chmac")
        chmac_bat = os.path.join(chmac_dir, "chmac.bat")
        return chmac_dir, chmac_bat

    def _ensure_chmac_skip_init(self) -> None:
        chmac_dir, _ = self._get_chmac_path()
        data_dir = os.path.join(chmac_dir, "Data")
        skip_init_file = os.path.join(data_dir, "skipInit")
        if os.path.exists(data_dir) and not os.path.exists(skip_init_file):
            try:
                with open(skip_init_file, "w") as f:
                    f.write("skipInit\n")
                print("Created chmac skipInit file to bypass interactive prompts.")
            except Exception as e:
                print(f"Error creating skipInit file: {e}")

    def _load_adapters(self) -> list[dict[str, str]]:
        chmac_dir, chmac_bat = self._get_chmac_path()
        if not os.path.exists(chmac_bat):
            return []
            
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                [chmac_bat, "/l"],
                input="\n",
                capture_output=True,
                text=True,
                cwd=chmac_dir,
                startupinfo=startupinfo,
                timeout=15
            )
            output = result.stdout
        except Exception as e:
            self._log_mac_output(f"Failed to list network adapters: {e}")
            return []
            
        adapters = []
        lines = output.splitlines()
        current_adapter = None
        for line in lines:
            match_id = re.match(r'^\s*(\d+)\.\s*(.*)', line)
            if match_id:
                current_adapter = {
                    "id": match_id.group(1),
                    "name": match_id.group(2).strip(),
                    "interface": ""
                }
                continue
                
            if current_adapter:
                match_iface = re.match(r'^\s*\+\s*\[(.*)\]', line)
                if match_iface:
                    current_adapter["interface"] = match_iface.group(1).strip()
                    adapters.append(current_adapter)
                    current_adapter = None
                    
        return adapters

    def refresh_mac_adapters(self) -> None:
        self.mac_adapters = self._load_adapters()
        if not self.mac_adapters:
            if hasattr(self, "mac_adapter_combo") and self.mac_adapter_combo:
                self.mac_adapter_combo["values"] = ["No adapters found / ChMac not found"]
                self.mac_adapter_combo.current(0)
            if hasattr(self, "randomize_btn") and self.randomize_btn:
                self.randomize_btn.config(state="disabled")
            if hasattr(self, "restore_btn") and self.restore_btn:
                self.restore_btn.config(state="disabled")
            if hasattr(self, "randomize_all_btn") and self.randomize_all_btn:
                self.randomize_all_btn.config(state="disabled")
            if hasattr(self, "restore_all_btn") and self.restore_all_btn:
                self.restore_all_btn.config(state="disabled")
            if hasattr(self, "mac_display_label") and self.mac_display_label:
                self.mac_display_label.config(text="Current MAC Address: N/A")
        else:
            combo_values = []
            for adapter in self.mac_adapters:
                display = f"{adapter['id']}. {adapter['name']}"
                if adapter["interface"]:
                    display += f" ({adapter['interface']})"
                combo_values.append(display)
            if hasattr(self, "mac_adapter_combo") and self.mac_adapter_combo:
                self.mac_adapter_combo["values"] = combo_values
                self.mac_adapter_combo.current(0)
            if hasattr(self, "randomize_btn") and self.randomize_btn:
                self.randomize_btn.config(state="normal")
            if hasattr(self, "restore_btn") and self.restore_btn:
                self.restore_btn.config(state="normal")
            if hasattr(self, "randomize_all_btn") and self.randomize_all_btn:
                self.randomize_all_btn.config(state="normal")
            if hasattr(self, "restore_all_btn") and self.restore_all_btn:
                self.restore_all_btn.config(state="normal")
            if hasattr(self, "mac_display_label") and self.mac_display_label:
                self.on_adapter_selected()

    def _get_mac_addresses(self) -> dict[str, str]:
        mac_map = {}
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                ["getmac", "/v", "/fo", "csv"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=5
            )
            if result.returncode == 0:
                f = io.StringIO(result.stdout.strip())
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    for row in reader:
                        if len(row) >= 3:
                            conn_name = row[0].strip()
                            mac_addr = row[2].strip()
                            if conn_name:
                                mac_map[conn_name.lower()] = mac_addr
        except Exception as e:
            print(f"Error calling getmac: {e}")
        return mac_map

    def on_adapter_selected(self, event=None) -> None:
        idx = self.mac_adapter_combo.current()
        if idx < 0 or not self.mac_adapters:
            if hasattr(self, "mac_display_label"):
                self.mac_display_label.config(text="Current MAC Address: N/A")
            return
            
        adapter = self.mac_adapters[idx]
        iface = adapter["interface"].strip().lower()
        
        mac_map = self._get_mac_addresses()
        mac = mac_map.get(iface, "Unknown/Not found")
        if hasattr(self, "mac_display_label"):
            self.mac_display_label.config(text=f"Current MAC Address: {mac}")

    def randomize_mac(self) -> None:
        idx = self.mac_adapter_combo.current()
        if idx < 0 or not self.mac_adapters:
            messagebox.showerror("Error", "Please select a valid network adapter.")
            return
            
        adapter = self.mac_adapters[idx]
        adapter_id = adapter["id"]
        
        confirmed = messagebox.askyesno(
            "Confirm MAC Change",
            f"Are you sure you want to randomize the MAC address for:\n{adapter['name']}?",
            parent=self.root
        )
        if not confirmed:
            return
            
        self._run_mac_action_async(["/n", adapter_id])

    def restore_mac(self) -> None:
        idx = self.mac_adapter_combo.current()
        if idx < 0 or not self.mac_adapters:
            messagebox.showerror("Error", "Please select a valid network adapter.")
            return
            
        adapter = self.mac_adapters[idx]
        adapter_id = adapter["id"]
        
        confirmed = messagebox.askyesno(
            "Confirm MAC Restore",
            f"Are you sure you want to restore the original MAC address for:\n{adapter['name']}?",
            parent=self.root
        )
        if not confirmed:
            return
            
        self._run_mac_action_async(["/n", adapter_id, "/r"])

    def randomize_all_macs(self) -> None:
        if not self.mac_adapters:
            messagebox.showerror("Error", "No network adapters found.")
            return
            
        confirmed = messagebox.askyesno(
            "Confirm Randomize All MACs",
            "⚠️ WARNING: This will randomize the MAC addresses of ALL network adapters on this system.\n\nThis will temporarily disrupt network connections.\n\nDo you want to proceed?",
            parent=self.root
        )
        if not confirmed:
            return
            
        self._run_all_mac_action_async(action="randomize")

    def restore_all_macs(self) -> None:
        if not self.mac_adapters:
            messagebox.showerror("Error", "No network adapters found.")
            return
            
        confirmed = messagebox.askyesno(
            "Confirm Restore All MACs",
            "Are you sure you want to restore the original MAC addresses of ALL network adapters on this system?",
            parent=self.root
        )
        if not confirmed:
            return
            
        self._run_all_mac_action_async(action="restore")

    def _run_all_mac_action_async(self, action: str) -> None:
        self.randomize_btn.config(state="disabled")
        self.restore_btn.config(state="disabled")
        self.randomize_all_btn.config(state="disabled")
        self.restore_all_btn.config(state="disabled")
        self.refresh_adapters_btn.config(state="disabled")
        self._log_mac_output(f"Starting MAC operation: {action.upper()} ALL adapters...\n", clear=True)
        
        def run():
            chmac_dir, chmac_bat = self._get_chmac_path()
            
            for idx, adapter in enumerate(self.mac_adapters):
                adapter_id = adapter["id"]
                adapter_name = adapter["name"]
                
                args = ["/n", adapter_id]
                if action == "restore":
                    args.append("/r")
                    
                self.root.after(0, lambda name=adapter_name: self._log_mac_output(f"\nProcessing adapter: {name}...\n"))
                
                success = False
                output = ""
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    result = subprocess.run(
                        [chmac_bat] + args,
                        input="\n",
                        capture_output=True,
                        text=True,
                        cwd=chmac_dir,
                        startupinfo=startupinfo,
                        timeout=60
                    )
                    success = result.returncode == 0
                    output = result.stdout + "\n" + result.stderr
                except subprocess.TimeoutExpired as e:
                    output = f"Operation timed out.\nOutput so far:\n{e.stdout}\n{e.stderr}"
                except Exception as e:
                    output = f"Error: {e}"
                    
                def append_log(out=output, status=success, name=adapter_name):
                    self._log_mac_output(out)
                    if status:
                        self._log_mac_output(f"✅ Successfully processed {name}.\n")
                    else:
                        self._log_mac_output(f"❌ Failed to process {name}.\n")
                        
                self.root.after(0, append_log)
                
            def on_all_done():
                self._log_mac_output("\n=== Operations Completed on All Adapters ===\n")
                self.randomize_btn.config(state="normal")
                self.restore_btn.config(state="normal")
                self.randomize_all_btn.config(state="normal")
                self.restore_all_btn.config(state="normal")
                self.refresh_adapters_btn.config(state="normal")
                self.on_adapter_selected()
                
            self.root.after(0, on_all_done)
            
        threading.Thread(target=run, daemon=True).start()
        
    def _log_mac_output(self, text: str, clear: bool = False) -> None:
        self.mac_log_text.config(state="normal")
        if clear:
            self.mac_log_text.delete("1.0", "end")
        self.mac_log_text.insert("end", text)
        self.mac_log_text.see("end")
        self.mac_log_text.config(state="disabled")

    def _run_mac_action_async(self, args: list[str]) -> None:
        self.randomize_btn.config(state="disabled")
        self.restore_btn.config(state="disabled")
        self.refresh_adapters_btn.config(state="disabled")
        self._log_mac_output(f"Starting MAC address operation (chmac {' '.join(args)})... Please wait.\n", clear=True)
        
        def run():
            chmac_dir, chmac_bat = self._get_chmac_path()
            success = False
            output = ""
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                result = subprocess.run(
                    [chmac_bat] + args,
                    input="\n",
                    capture_output=True,
                    text=True,
                    cwd=chmac_dir,
                    startupinfo=startupinfo,
                    timeout=60
                )
                success = result.returncode == 0
                output = result.stdout + "\n" + result.stderr
            except subprocess.TimeoutExpired as e:
                output = f"Operation timed out.\nOutput so far:\n{e.stdout}\n{e.stderr}"
            except Exception as e:
                output = f"Error running MAC address changer: {e}"
                
            def on_done():
                self._log_mac_output(output)
                if success:
                    self._log_mac_output("\n✅ Operation completed successfully!")
                else:
                    self._log_mac_output("\n❌ Operation failed or completed with warnings.")
                
                self.randomize_btn.config(state="normal")
                self.restore_btn.config(state="normal")
                self.refresh_adapters_btn.config(state="normal")
                
                if hasattr(self, "mac_display_label"):
                    self.on_adapter_selected()
                
            self.root.after(0, on_done)
            
        threading.Thread(target=run, daemon=True).start()

    def _select_settings_tab(self) -> None:
        if hasattr(self, "settings_tab"):
            self.window_notebook.select(self.settings_tab)

    def _build_settings_tab(self) -> None:
        self.settings_tab = ttk.Frame(self.window_notebook, padding=10)
        self.window_notebook.add(self.settings_tab, text="Settings")
        
        # Title
        title_label = ttk.Label(self.settings_tab, text="Application Settings", font=("", 14, "bold"))
        title_label.pack(anchor="w", pady=(0, 4))
        ttk.Separator(self.settings_tab).pack(fill="x", pady=(0, 10))
        
        # 1. General Settings Group
        general_frame = ttk.LabelFrame(self.settings_tab, text="General Settings", padding=10)
        general_frame.pack(fill="x", pady=(0, 10))
        
        url_row = ttk.Frame(general_frame)
        url_row.pack(fill="x")
        ttk.Label(url_row, text="Current URL:").pack(side="left", padx=(0, 10))
        self.url_var = tk.StringVar(value="https://github.com/OMGerEDU/Royals")
        url_entry = ttk.Entry(url_row, textvariable=self.url_var, width=50)
        url_entry.pack(side="left", fill="x", expand=True)
        
        # 2. MAC Address Changer Group
        mac_frame = ttk.LabelFrame(self.settings_tab, text="MAC Address Changer (ChMac)", padding=10)
        mac_frame.pack(fill="both", expand=True)
        
        # Check admin privileges
        self.is_admin_mode = self._check_admin()
        
        if not self.is_admin_mode:
            # Admin warning inside the MAC frame
            ttk.Label(
                mac_frame, 
                text="⚠️ Changing MAC addresses requires administrator privileges to modify registry entries and restart network adapters.\n\nPlease relaunch MapleBot Controller as an administrator.",
                wraplength=700,
                justify="left"
            ).pack(anchor="w", pady=(0, 10))
            
            ttk.Button(
                mac_frame, 
                text="🛡 Relaunch as Administrator", 
                command=self._relaunch_as_admin,
                width=28
            ).pack(anchor="w")
        else:
            # If admin, show controls inside the MAC frame
            controls_frame = ttk.Frame(mac_frame)
            controls_frame.pack(fill="x", pady=(0, 10))
            
            ttk.Label(controls_frame, text="Select Network Adapter:").pack(side="left", padx=(0, 10))
            
            self.mac_adapter_combo = ttk.Combobox(controls_frame, width=50, state="readonly")
            self.mac_adapter_combo.pack(side="left", padx=(0, 10))
            self.mac_adapter_combo.bind("<<ComboboxSelected>>", self.on_adapter_selected)
            
            self.refresh_adapters_btn = ttk.Button(controls_frame, text="↻ Refresh List", command=self.refresh_mac_adapters)
            self.refresh_adapters_btn.pack(side="left")
            
            # MAC Address Display Row
            mac_display_row = ttk.Frame(mac_frame)
            mac_display_row.pack(fill="x", pady=(5, 5))
            self.mac_display_label = ttk.Label(mac_display_row, text="Current MAC Address: Loading...", font=("", 10, "bold"))
            self.mac_display_label.pack(side="left")
            
            # Action Buttons
            actions_frame = ttk.Frame(mac_frame, padding=(0, 5, 0, 5))
            actions_frame.pack(fill="x", pady=(0, 10))
            
            self.randomize_btn = ttk.Button(actions_frame, text="🎲 Randomize MAC", command=self.randomize_mac, width=20)
            self.randomize_btn.pack(side="left", padx=(0, 10))
            
            self.restore_btn = ttk.Button(actions_frame, text="⏪ Restore Original MAC", command=self.restore_mac, width=22)
            self.restore_btn.pack(side="left", padx=(0, 15))
            
            self.randomize_all_btn = ttk.Button(actions_frame, text="🎲 Randomize All MACs", command=self.randomize_all_macs, width=22)
            self.randomize_all_btn.pack(side="left", padx=(0, 10))
            
            self.restore_all_btn = ttk.Button(actions_frame, text="⏪ Restore All MACs", command=self.restore_all_macs, width=22)
            self.restore_all_btn.pack(side="left")
            
            # Log frame
            log_frame = ttk.LabelFrame(mac_frame, text="ChMac Execution Log", padding=5)
            log_frame.pack(fill="both", expand=True)
            
            # Scrollbar and text box for output
            log_scrollbar = ttk.Scrollbar(log_frame)
            log_scrollbar.pack(side="right", fill="y")
            
            self.mac_log_text = tk.Text(log_frame, wrap="word", yscrollcommand=log_scrollbar.set, height=8, font=("Consolas", 9))
            self.mac_log_text.pack(fill="both", expand=True)
            log_scrollbar.config(command=self.mac_log_text.yview)
            
            self.mac_log_text.config(state="disabled")
            
            # Initialize adapter list
            self.refresh_mac_adapters()

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    MapleBotGUI().run()
