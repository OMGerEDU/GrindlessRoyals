"""Tkinter GUI for the MapleBot faithful clone."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .bot import MapleBot
from .keys import (
    COMMON_KEY_CHOICES,
    DEFAULT_LOOP_INTERVAL,
    DEFAULT_LOOP_KEY_NAME,
    DEFAULT_POTION_KEY_NAME,
    DEFAULT_SHUFFLE_INTERVAL,
    DEFAULT_SHUFFLE_MAX_HOLD,
    DEFAULT_SHUFFLE_MIN_HOLD,
    MIN_POTION_INTERVAL,
    parse_loop_key,
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
}


def map_tkinter_event_to_key(event) -> str:
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
        self.active_binder: ttk.Button | None = None
        self.active_binder_var: tk.StringVar | None = None

        self._build_layout()
        self.refresh_window_list()
        self._toggle_auto_refresh()

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(10, 10, 10, 2))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="↻ Refresh", command=self.refresh_window_list, width=12).pack(side="left")
        ttk.Button(toolbar, text="⏹ Stop All", command=self.stop_all, width=12).pack(side="left", padx=(4, 0))
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

    def _create_key_input(self, parent: ttk.Frame, label_text: str, var: tk.StringVar) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label_text, width=14).pack(side="left")
        
        binder_btn = self._create_key_binder(row, var)
        binder_btn.pack(side="left")
        
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
            "skill_1": tk.StringVar(value="1"),
            "skill_1_enabled": tk.BooleanVar(value=False),
            "skill_2": tk.StringVar(value="2"),
            "skill_2_enabled": tk.BooleanVar(value=False),
            "skill_3": tk.StringVar(value="3"),
            "skill_3_enabled": tk.BooleanVar(value=False),
            "skills_interval": tk.DoubleVar(value=180.0),
            "status": tk.StringVar(value="Stopped"),
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
                    elif name == "skills_interval":
                        bot.skills_interval = max(5.0, float(val))
                    elif name in (
                        "skill_1",
                        "skill_2",
                        "skill_3",
                        "skill_1_enabled",
                        "skill_2_enabled",
                        "skill_3_enabled",
                    ):
                        skills_to_use = []
                        for idx in (1, 2, 3):
                            if bool(vars_map[f"skill_{idx}_enabled"].get()):
                                skills_to_use.append(parse_loop_key(str(vars_map[f"skill_{idx}"].get())))
                        bot.skills_to_use = skills_to_use
                except Exception:
                    pass
            return callback

        for name, var in vars_map.items():
            var.trace_add("write", make_trace_callback(hwnd, name, var))

        header = ttk.Frame(tab)
        header.pack(fill="x")
        ttk.Label(header, textvariable=self.instance_name_vars[hwnd], font=("", 14, "bold")).pack(side="left")
        ttk.Label(header, textvariable=vars_map["status"]).pack(side="right")
        ttk.Label(tab, text=f"HWND {hwnd}", foreground="#888").pack(anchor="w", pady=(0, 8))
        ttk.Separator(tab).pack(fill="x", pady=(0, 8))

        settings_frame = ttk.Frame(tab)
        settings_frame.pack(fill="both", expand=True)

        loop_frame = ttk.LabelFrame(settings_frame, text="Attack loop", padding=8)
        loop_frame.pack(fill="x", pady=(0, 8))
        self._create_key_input(loop_frame, "Loop key", vars_map["loop_key"])
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

        controls_frame = ttk.Frame(tab)
        controls_frame.pack(fill="x", pady=(4, 8))
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
        ttk.Button(controls_frame, text="Rename", command=lambda h=hwnd: self.rename_instance(h)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(controls_frame, text="Delete Instance", command=lambda h=hwnd: self.delete_instance(h)).pack(
            side="left", padx=(4, 0)
        )

        skill_frame = ttk.LabelFrame(tab, text="Quick skills (Auto buff)", padding=8)
        skill_frame.pack(fill="x")

        interval_row = ttk.Frame(skill_frame)
        interval_row.pack(fill="x", pady=(0, 6))
        ttk.Label(interval_row, text="Interval (s)", width=14).pack(side="left")
        ttk.Scale(interval_row, from_=10.0, to=600.0, orient="horizontal", variable=vars_map["skills_interval"]).pack(
            side="left", fill="x", expand=True
        )
        ttk.Entry(interval_row, textvariable=vars_map["skills_interval"], width=8).pack(side="left", padx=(6, 0))

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
            ttk.Button(row, text="Tap", command=lambda h=hwnd, k=key_name: self.send_skill(h, k)).pack(
                side="left", padx=(4, 0)
            )

    def _remove_instance_tab(self, hwnd: int) -> None:
        tab = self.window_tabs.pop(hwnd, None)
        if tab is not None:
            self.window_notebook.forget(tab)
        self.window_vars.pop(hwnd, None)
        self.instance_name_vars.pop(hwnd, None)
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
                skills_to_use.append(parse_loop_key(str(vars_map[f"skill_{idx}"].get())))

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
            skills_interval=skills_interval,
            skills_to_use=skills_to_use,
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
        self.stop_all()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    MapleBotGUI().run()
