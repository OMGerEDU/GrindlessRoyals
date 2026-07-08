# MapleBot Recovery Notes

## Source Artifact

- File: `MapleBot.exe`
- SHA256: `01A672DE173DC97AC80887F988699E3FFD03CE0C7DAA83DBE495CEFA72636906`
- Size: `11765748` bytes
- Last write time: `2026-01-24 19:13:38`

## Static Recovery Findings

- The executable is a PyInstaller one-file bundle.
- The bundled Python runtime is Python 3.12 (`python312.dll`).
- The top-level script is named `main.py`.
- The top-level script bundle entry is named `main`.
- The recovered top-level symbols are:
  - `parse_loop_key`
  - `MapleBot`
  - `enumerate_maple_windows`
  - `run_cli`
  - `MapleBotGUI`
  - `run_gui`
  - `main`

## Recovered Constants

- `DEFAULT_LOOP_KEY_NAME = "space"`
- `DEFAULT_LOOP_INTERVAL = 0.6`
- `DEFAULT_SHUFFLE_INTERVAL = 60.0`
- `DEFAULT_SHUFFLE_MIN_HOLD = 0.25`
- `DEFAULT_SHUFFLE_MAX_HOLD = 0.5`
- `DEFAULT_POTION_KEY_NAME = "7"`
- `DEFAULT_POTION_INTERVAL_STEP = 5.0`
- `MIN_POTION_INTERVAL = 5.0`

## Recovered GUI Signals

- Window title: `MapleBot Controller`
- Minimum size: `780x520`
- Toolbar labels: `↻ Refresh`, `⏹ Stop All`, `Auto refresh`, `Every`, `sec`
- Placeholder text: `No Maplestory windows detected.\nLaunch the client and hit Refresh.`
- Per-window sections: `Attack loop`, `Potion`, `Walk`, `Quick skills`
- Main actions: `Start Loop`, `Stop Loop`, `Tap Potion`, `Focus Window`

## Older Project Lineage

The `Macro-bot-maker-main` folder contains a separate Tkinter/PyInstaller automation project named `ROSE`. It targets processes, generates AutoHotkey scripts, and saves key-delay profiles. It is not the MapleBot source, but it confirms the earlier project style: small Python GUI, packaged with PyInstaller, focused on configurable keyboard automation.
