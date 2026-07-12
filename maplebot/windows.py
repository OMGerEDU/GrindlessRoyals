"""Windows enumeration helpers for MapleBot."""

from __future__ import annotations

import ctypes
import os
import time
from collections.abc import Sequence
from ctypes import wintypes
from typing import TypedDict


try:
    import win32api
    import win32con
    import win32gui
    import win32process

    PYWIN32_AVAILABLE = True
except ImportError:
    win32api = None
    win32con = None
    win32gui = None
    win32process = None
    PYWIN32_AVAILABLE = False


DEFAULT_MAPLE_FILTERS = ("MapleRoyals Jan","MapleRoyals Feb","MapleRoyals Mar","MapleRoyals Apr","MapleRoyals May","MapleRoyals Jun","MapleRoyals Jul","MapleRoyals Aug","MapleRoyals Sep","MapleRoyals Oct","MapleRoyals Nov","MapleRoyals Dec")

# Window titles that match a maple filter but should still be ignored
# (e.g. the MapleBot GUI itself is titled "MapleBot Controller").
MAPLE_TITLE_IGNORE = ("controller",)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
SW_RESTORE = 9
SW_SHOW = 5
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = -1


class WindowInfo(TypedDict):
    hwnd: int
    title: str
    pid: int | None
    process_name: str
    has_window: bool


def _coerce_filters(window_filter: str | Sequence[str] | None = None) -> tuple[str, ...]:
    if window_filter is None:
        return DEFAULT_MAPLE_FILTERS
    if isinstance(window_filter, str):
        normalized = window_filter.strip().lower()
        if not normalized or normalized == "maplestory":
            return DEFAULT_MAPLE_FILTERS
        return (normalized,)
    return tuple(item.strip().lower() for item in window_filter if item.strip())


def _contains_filter(value: str, filters: Sequence[str]) -> bool:
    normalized = value.lower()
    return any(item in normalized for item in filters)


def filter_window_title(title: str, window_filter: str | Sequence[str] | None = "Maplestory") -> bool:
    return matches_maple_window(title, "", window_filter)


def matches_maple_window(
    title: str,
    process_name: str = "",
    window_filter: str | Sequence[str] | None = None,
) -> bool:
    filters = _coerce_filters(window_filter)
    if not filters:
        return False
    return _contains_filter(title or "", filters) or _contains_filter(process_name or "", filters)


def _is_window_visible(hwnd: int) -> bool:
    if win32gui is not None:
        return bool(win32gui.IsWindowVisible(hwnd))
    return bool(ctypes.windll.user32.IsWindowVisible(wintypes.HWND(hwnd)))


def is_window(hwnd: int) -> bool:
    if hwnd <= 0:
        return False
    if win32gui is not None:
        return bool(win32gui.IsWindow(hwnd))
    return bool(ctypes.windll.user32.IsWindow(wintypes.HWND(hwnd)))


def _is_iconic(hwnd: int) -> bool:
    if win32gui is not None:
        return bool(win32gui.IsIconic(hwnd))
    return bool(ctypes.windll.user32.IsIconic(wintypes.HWND(hwnd)))


def _get_window_text(hwnd: int) -> str:
    if win32gui is not None:
        return win32gui.GetWindowText(hwnd)

    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, length + 1)
    return buffer.value


def _get_window_process(hwnd: int) -> tuple[int | None, str]:
    if win32process is not None:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return None, ""

        process_name = ""
        handle = None
        try:
            access = getattr(win32con, "PROCESS_QUERY_LIMITED_INFORMATION", PROCESS_QUERY_LIMITED_INFORMATION)
            access |= getattr(win32con, "PROCESS_VM_READ", PROCESS_VM_READ)
            handle = win32api.OpenProcess(access, False, pid)
            process_path = win32process.GetModuleFileNameEx(handle, 0)
            process_name = os.path.basename(process_path)
        except Exception:
            process_name = ""
        finally:
            if handle is not None:
                try:
                    win32api.CloseHandle(handle)
                except Exception:
                    pass
        return pid, process_name

    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if not pid.value:
        return None, ""

    process_name = ""
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                process_name = os.path.basename(buffer.value)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    return pid.value, process_name


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _iter_processes() -> list[tuple[int, str]]:
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []

    processes: list[tuple[int, str]] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return processes
        while True:
            processes.append((int(entry.th32ProcessID), entry.szExeFile))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return processes


def _enum_windows(callback) -> None:
    if win32gui is not None:
        win32gui.EnumWindows(callback, None)
        return

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @enum_proc
    def _callback(hwnd, lparam):
        callback(int(hwnd), None)
        return True

    ctypes.windll.user32.EnumWindows(_callback, 0)


def enumerate_maple_windows(window_filter: str | Sequence[str] | None = "Maplestory") -> list[WindowInfo]:
    """Return visible Maple-related window handles and process-only fallbacks."""
    filters = _coerce_filters(window_filter)
    windows: list[WindowInfo] = []
    pids_with_windows: set[int] = set()

    def enum_handler(hwnd: int, _: object) -> None:
        if not _is_window_visible(hwnd):
            return
        title = _get_window_text(hwnd)
        pid, process_name = _get_window_process(hwnd)
        if matches_maple_window(title, process_name, filters):
            # Skip windows whose title contains an ignored keyword
            title_lower = (title or "").lower()
            if any(ign in title_lower for ign in MAPLE_TITLE_IGNORE):
                return
            if pid is not None:
                pids_with_windows.add(pid)
            windows.append(
                {
                    "hwnd": hwnd,
                    "title": title or process_name or f"HWND {hwnd}",
                    "pid": pid,
                    "process_name": process_name,
                    "has_window": True,
                }
            )

    _enum_windows(enum_handler)

    for pid, process_name in _iter_processes():
        if pid in pids_with_windows:
            continue
        if matches_maple_window("", process_name, filters):
            windows.append(
                {
                    "hwnd": -pid,
                    "title": f"{process_name} (process running, no window handle)",
                    "pid": pid,
                    "process_name": process_name,
                    "has_window": False,
                }
            )

    return windows


def force_foreground(hwnd: int) -> bool:
    """Attempt to force the target window to foreground using thread input attach."""
    if hwnd <= 0:
        return False
    if win32gui is not None and win32api is not None and win32process is not None and win32con is not None:
        try:
            user32 = ctypes.windll.user32
            foreground = win32gui.GetForegroundWindow()
            current_thread = win32api.GetCurrentThreadId()
            target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
            attach_threads = {target_thread, current_thread}

            if foreground:
                fg_thread, _ = win32process.GetWindowThreadProcessId(foreground)
                attach_threads.add(fg_thread)

            for thread_id in attach_threads:
                if thread_id != current_thread:
                    user32.AttachThreadInput(current_thread, thread_id, True)

            win32gui.BringWindowToTop(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetFocus(hwnd)
            return True
        except Exception as err:
            print(f"Error forcing foreground: {err}")
            return False
        finally:
            if "attach_threads" in locals():
                try:
                    user32 = ctypes.windll.user32
                    for thread_id in attach_threads:
                        if thread_id != current_thread:
                            user32.AttachThreadInput(current_thread, thread_id, False)
                except Exception:
                    pass

    try:
        user32 = ctypes.windll.user32
        user32.BringWindowToTop(wintypes.HWND(hwnd))
        user32.ShowWindow(wintypes.HWND(hwnd), SW_SHOW)
        return bool(user32.SetForegroundWindow(wintypes.HWND(hwnd)))
    except Exception as err:
        print(f"Error forcing foreground: {err}")
        return False


def activate_window(hwnd: int) -> bool:
    """Bring the Maple-related window to foreground."""
    if hwnd <= 0:
        return False
    try:
        if _is_iconic(hwnd):
            if win32gui is not None and win32con is not None:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                ctypes.windll.user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
        return force_foreground(hwnd)
    except Exception as err:
        print(f"Error activating window: {err}")
        return False

def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    if hwnd <= 0:
        return None
    try:
        if win32gui is not None:
            return tuple(win32gui.GetWindowRect(hwnd))

        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception as err:
        print(f"Error reading window position: {err}")
    return None


def move_window(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    if hwnd <= 0:
        return False
    try:
        if win32gui is not None:
            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            return True
        return bool(ctypes.windll.user32.MoveWindow(wintypes.HWND(hwnd), x, y, width, height, True))
    except Exception as err:
        print(f"Error moving window: {err}")
        return False


def identify_window(hwnd: int, offset: int = 80, pause: float = 0.25) -> bool:
    """Focus and briefly shift a real window so the user can identify it."""
    if hwnd <= 0:
        return False
    rect = get_window_rect(hwnd)
    if rect is None:
        return False

    left, top, right, bottom = rect
    width = max(1, right - left)
    height = max(1, bottom - top)

    activate_window(hwnd)
    if not move_window(hwnd, left + offset, top, width, height):
        return False
    time.sleep(pause)
    restored = move_window(hwnd, left, top, width, height)
    activate_window(hwnd)
    return restored