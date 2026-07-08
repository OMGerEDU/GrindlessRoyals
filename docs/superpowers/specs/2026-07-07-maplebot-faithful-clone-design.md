# MapleBot Faithful Clone Design

## Goal

Rebuild the lost `MapleBot.exe` project as maintainable Python source while matching the recovered executable's behavior as closely as possible. The first milestone is a faithful clone, not a redesign.

## Evidence

- `MapleBot.exe` is a PyInstaller Python 3.12 bundle.
- Its top-level script is `main.py`.
- Recovered symbols include `MapleBot`, `MapleBotGUI`, `enumerate_maple_windows`, `run_cli`, `run_gui`, and `parse_loop_key`.
- The older `Macro-bot-maker-main` project is a Tkinter/PyInstaller automation utility that helps confirm the project lineage.
- The recovered app uses `tkinter`, `pynput`, `pywin32`, `ctypes`, `threading`, `time`, and `random`.

## Behavioral Scope

The clone will:

- Detect visible windows whose title contains `Maplestory` by default.
- Provide a Tkinter GUI titled `MapleBot Controller`.
- Show one tab per detected MapleStory window.
- Support manual refresh and optional auto-refresh.
- Support an attack/action loop with a configurable key and interval.
- Support foreground key sending through `pynput`.
- Support background key sending with ordinary Windows `PostMessage` key events.
- Support optional walking/strafing by holding left and right for a randomized hold duration.
- Support optional potion/key tapping after a walk cycle.
- Support quick skill key taps from per-window controls.
- Provide a CLI mode with hotkeys matching recovered behavior: F3 toggles, F4 cycles windows, plus/minus adjusts potion interval, and F7 exits.

The clone will not add stealth behavior, anti-cheat bypasses, process injection, memory reading/writing, or kernel/driver techniques.

## Architecture

The recovered executable appears to keep everything in one script. The remake will keep behavior faithful while splitting code into small modules:

- `maplebot.keys`: key-name constants and `parse_loop_key`.
- `maplebot.windows`: MapleStory window enumeration and foreground activation helpers.
- `maplebot.bot`: `MapleBot` runtime loop, background/foreground key sends, walking, potion interval adjustment, and lifecycle.
- `maplebot.gui`: `MapleBotGUI` Tkinter interface.
- `maplebot.cli`: CLI listener mode.
- `main.py`: entry point with `--cli`.

## Data Flow

The GUI enumerates windows, creates per-window Tk variables, and starts a `MapleBot` instance for a selected HWND. `MapleBot` owns the runtime state and worker thread. Each loop tick optionally performs a walk cycle when the walk interval elapses, otherwise sends the configured loop key, then sleeps for the loop interval.

## Error Handling

Failures to locate a target window, parse numeric inputs, map keys, send background messages, or focus the window are reported through GUI dialogs or console messages. Background send failures fall back to foreground sending where the recovered behavior did so.

## Testing

Tests will focus on logic that can run without a live MapleStory client:

- Key-name parsing for common keys, single characters, unknown values, and whitespace.
- Window filtering logic with mocked window API calls.
- Bot state transitions for start/stop/toggle without sending real keys.
- Potion interval minimum enforcement.

Manual verification will cover import/syntax checks and, if available in the environment, launching the GUI without starting loops.

## Completion Criteria

- Source project exists and is runnable with `python main.py`.
- CLI mode exists with `python main.py --cli`.
- GUI controls match the recovered labels and default values.
- Core bot behavior matches recovered bytecode-level behavior.
- Tests pass for non-OS-interactive logic.
- README explains setup, running, and packaging.


