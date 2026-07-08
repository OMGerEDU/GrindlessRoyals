# MapleBot Remake

Faithful Python source rebuild of the recovered `MapleBot.exe` PyInstaller app.

## What It Does

- Detects visible windows with `Maplestory` in the title.
- Provides a Tkinter GUI titled `MapleBot Controller`.
- Creates one tab per detected window.
- Sends a configurable loop key on a configurable interval.
- Can use foreground input through `pynput` or ordinary Windows `PostMessage` background key events through `pywin32`.
- Supports optional left/right walking and optional potion/key taps after walk cycles.
- Includes a CLI hotkey mode: F3 toggles, F4 cycles windows, plus/minus changes interval, F7 exits.

This remake does not include stealth behavior, anti-cheat bypasses, process injection, memory editing, or driver techniques.

## Setup

```powershell
python -m pip install -r requirements.txt
```

`tkinter` is part of the standard Windows Python installer. If it is missing, reinstall Python with Tcl/Tk support enabled.

## Run

```powershell
python main.py
```

CLI mode:

```powershell
python main.py --cli
```

## Package

```powershell
pyinstaller --onefile --windowed --name MapleBot main.py
```

The packaged executable will be written under `dist\MapleBot.exe`.

## Tests

```powershell
python -B -m unittest discover -v
python -B tools/check_syntax.py
```

The tests avoid real keyboard input and real MapleStory windows, so they can run on a development machine without the game open.
