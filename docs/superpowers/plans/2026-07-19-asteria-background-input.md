# Asteria Background Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect elevated Asteria instances with limited process rights and safely route automation messages to the most plausible Asteria input HWND without stealing focus.

**Architecture:** Keep Windows-specific discovery in `maplebot/windows.py` and runtime policy in `maplebot/bot.py`. Add a small, deterministic child-window target resolver; the bot asks it for one background target and never broadcasts a key or silently falls back to foreground injection.

**Tech Stack:** Python 3, `ctypes`, pywin32 when available, `unittest`, `unittest.mock`.

---

## File Structure

- `maplebot/windows.py`: limited-rights process identity, child-window metadata, deterministic background target selection.
- `maplebot/bot.py`: background target use, background/foreground policy, and focus-safe automation helpers.
- `tests/test_window_identity.py`: process access and child-target resolver regressions.
- `tests/test_bot.py`: message target, mode routing, and no-focus-fallback regressions.

Existing staged edits are user work. Before every edit, inspect the staged and working-tree versions with `git diff --cached -- <file>` and `git diff -- <file>`, preserve all unrelated changes, and do not use broad restore/reset commands. Commits must name exact paths and must not include `profiles.json` or unrelated staged hunks.

### Task 1: Limited-rights Asteria process identity

**Files:**
- Modify: `maplebot/windows.py:213-250`
- Test: `tests/test_window_identity.py`

- [ ] **Step 1: Write the failing limited-rights test**

Add a test that patches `win32process.GetWindowThreadProcessId`, `win32api.OpenProcess`, and a new internal `_query_process_image_name` helper. Assert `OpenProcess` receives exactly `PROCESS_QUERY_LIMITED_INFORMATION`, never `PROCESS_VM_READ`, and that `Asteria.exe` is returned:

```python
@patch("maplebot.windows._query_process_image_name", return_value=r"C:\\Games\\Asteria.exe")
@patch("maplebot.windows.win32api")
@patch("maplebot.windows.win32process")
def test_window_process_uses_limited_query_rights(self, process, api, query):
    process.GetWindowThreadProcessId.return_value = (12, 345)
    api.OpenProcess.return_value = 99
    pid, name = windows._get_window_process(123)
    self.assertEqual((pid, name), (345, "Asteria.exe"))
    api.OpenProcess.assert_called_once_with(windows.PROCESS_QUERY_LIMITED_INFORMATION, False, 345)
    query.assert_called_once_with(99)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest tests.test_window_identity.WindowIdentityTests.test_window_process_uses_limited_query_rights -v`

Expected: FAIL because `_query_process_image_name` does not exist or because access includes `PROCESS_VM_READ`.

- [ ] **Step 3: Implement the shared image-name query**

Add a helper that calls `QueryFullProcessImageNameW` through the already configured `kernel32`, then change the pywin32 branch to open with limited rights only:

```python
def _query_process_image_name(handle: int) -> str:
    size = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        return buffer.value
    return ""
```

Use `_query_process_image_name(handle)` in both pywin32 and ctypes branches and retain handle cleanup in `finally`.

- [ ] **Step 4: Run the focused and identity tests**

Run: `python -m unittest tests.test_window_identity -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit only Task 1 hunks**

Use exact-path staging and inspect `git diff --cached` before committing. If the same files already contain unrelated staged hunks, leave the task uncommitted rather than committing user changes.

### Task 2: Deterministic child input-target discovery

**Files:**
- Modify: `maplebot/windows.py`
- Test: `tests/test_window_identity.py`

- [ ] **Step 1: Write failing target-order tests**

Define the desired public data shape and ordering with pure tests:

```python
def test_choose_background_target_prefers_visible_render_child(self):
    candidates = [
        {"hwnd": 10, "parent": 0, "class_name": "Asteria", "title": "", "visible": True, "enabled": True},
        {"hwnd": 11, "parent": 10, "class_name": "Chrome_RenderWidgetHostHWND", "title": "", "visible": True, "enabled": True},
    ]
    self.assertEqual(windows.choose_background_target(10, candidates), 11)

def test_choose_background_target_falls_back_to_top_level(self):
    candidates = [
        {"hwnd": 12, "parent": 10, "class_name": "Static", "title": "", "visible": False, "enabled": True},
    ]
    self.assertEqual(windows.choose_background_target(10, candidates), 10)
```

Add a mocked enumeration test asserting `enumerate_child_windows(10)` returns metadata sorted by HWND so diagnostics are stable.

- [ ] **Step 2: Run target tests and verify RED**

Run: `python -m unittest tests.test_window_identity -v`

Expected: FAIL because the resolver and enumerator do not exist.

- [ ] **Step 3: Implement metadata collection and resolver**

Add `WindowTargetInfo`, `_get_class_name`, `_is_window_enabled`, `enumerate_child_windows(top_hwnd)`, and `choose_background_target(top_hwnd, candidates=None)`. Use `EnumChildWindows` via pywin32 when present and ctypes otherwise. Rank only visible, enabled child classes containing one of:

```python
INPUT_CLASS_HINTS = ("render", "widget", "canvas", "game", "maple", "asteria")
```

Return the lowest-HWND highest-ranked candidate for determinism; return `top_hwnd` when no child qualifies.

- [ ] **Step 4: Run window tests**

Run: `python -m unittest tests.test_window_identity -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit only Task 2 hunks if isolation is safe**

Review exact staged content first. Do not include unrelated pre-existing changes.

### Task 3: Route background messages to the resolved HWND

**Files:**
- Modify: `maplebot/bot.py:314-379`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write a failing resolved-target test**

```python
@patch("maplebot.bot.window_api.choose_background_target", return_value=777)
def test_background_key_posts_to_resolved_input_target(self, choose):
    bot = MapleBot(target_hwnd=123)
    bot.windows = [123]
    calls = []
    bot._post_message_key = lambda hwnd, key, down, is_repeat=False: calls.append((hwnd, down)) or True
    self.assertTrue(bot._send_background_key("a"))
    self.assertEqual(calls, [(777, True), (777, False)])
    choose.assert_called_once_with(123)
```

Add a second test where the key-down post fails and assert key-up is not attempted.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_bot.MapleBotStateTests.test_background_key_posts_to_resolved_input_target -v`

Expected: FAIL because messages still target the top-level HWND.

- [ ] **Step 3: Implement one-target background delivery**

Resolve once per send with `window_api.choose_background_target(target)`, log the top-level and selected target when they differ, and post down/up only to the selected HWND. Do not loop over candidates and do not invoke any focus API.

- [ ] **Step 4: Run bot tests**

Run: `python -m unittest tests.test_bot -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit only Task 3 hunks if isolation is safe**

Review exact staged content first and preserve user changes.

### Task 4: Enforce background/foreground policy throughout automation

**Files:**
- Modify: `maplebot/bot.py:395-560`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write failing policy tests**

Add tests for a new `_send_automation_key` policy helper and `_hold_key`:

```python
def test_background_mode_never_uses_foreground_sender(self):
    bot = MapleBot(background_loop=True)
    bot._send_background_key = MagicMock(return_value=True)
    bot.send_key = MagicMock(return_value=True)
    self.assertTrue(bot._send_automation_key("a"))
    bot._send_background_key.assert_called_once_with("a")
    bot.send_key.assert_not_called()

def test_foreground_mode_uses_explicit_foreground_sender(self):
    bot = MapleBot(background_loop=False)
    bot._send_background_key = MagicMock(return_value=True)
    bot.send_key = MagicMock(return_value=True)
    self.assertTrue(bot._send_automation_key("a"))
    bot.send_key.assert_called_once_with("a")
    bot._send_background_key.assert_not_called()

def test_background_hold_never_activates_window(self):
    bot = MapleBot(background_loop=True)
    bot._hold_key_background = MagicMock(return_value=True)
    bot._hold_key_foreground = MagicMock(return_value=True)
    self.assertTrue(bot._hold_key("left", 0.2))
    bot._hold_key_background.assert_called_once_with("left", 0.2)
    bot._hold_key_foreground.assert_not_called()
```

- [ ] **Step 2: Run policy tests and verify RED**

Run: `python -m unittest tests.test_bot -v`

Expected: FAIL because `_send_automation_key` is absent and `_hold_key` always uses foreground input.

- [ ] **Step 3: Implement and apply the policy helper**

```python
def _send_automation_key(self, key) -> bool:
    if self.background_loop:
        return self._send_background_key(key)
    return self.send_key(key)

def _hold_key(self, key, duration: float) -> bool:
    if self.background_loop:
        return self._hold_key_background(key, duration)
    return self._hold_key_foreground(key, duration)
```

Replace direct loop, potion, skill, and anti-AFK keyboard sends with these policy helpers. In particular, remove the anti-AFK restore block's direct `self.keyboard.press/release` calls and use `_send_automation_key(restore_key)`.

- [ ] **Step 4: Run all unit tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with no unexpected warnings or errors.

- [ ] **Step 5: Commit only Task 4 hunks if isolation is safe**

Review exact staged content first and do not commit unrelated staged changes.

### Task 5: Live-safe diagnostics and final verification

**Files:**
- Modify: `maplebot/windows.py`
- Modify: `maplebot/bot.py`
- Test: `tests/test_window_identity.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Add a failing diagnostic stability test**

Capture stdout for one resolved target and assert the diagnostic contains both `top-level HWND 123` and `input HWND 777`, while repeated sends do not print the same selection more than once per `MapleBot` instance.

- [ ] **Step 2: Run it and verify RED**

Run: `python -m unittest tests.test_bot -v`

Expected: FAIL until one-time target diagnostics exist.

- [ ] **Step 3: Implement one-time target diagnostics**

Cache only the last `(top_hwnd, input_hwnd)` diagnostic tuple. Re-resolve targets on later sends so recreated child windows are handled, but suppress identical log lines. Log API success as `message accepted`, never `key delivered`.

- [ ] **Step 4: Verify syntax, full tests, and diff scope**

Run:

```powershell
python -m compileall -q maplebot tests
python -m unittest discover -s tests -v
git diff --check
git diff -- maplebot/windows.py maplebot/bot.py tests/test_window_identity.py tests/test_bot.py
git diff --cached -- maplebot/windows.py maplebot/bot.py tests/test_window_identity.py tests/test_bot.py
```

Expected: compilation exit 0, all tests PASS, `git diff --check` exit 0, and every changed hunk is understood and attributable either to the user or this plan.

- [ ] **Step 5: Perform optional live Asteria probe only with the user present**

Launch MapleBot normally, refresh instances, and inspect diagnostics without starting foreground actions. Confirm Asteria remains unfocused while background keys are attempted. Record whether Asteria acts on accepted messages; do not interpret API acceptance as proof of in-game delivery.

- [ ] **Step 6: Final commit decision**

If task hunks can be isolated without altering user-staged work, commit them with exact paths/hunks. Otherwise leave changes uncommitted and report precisely why, along with the verification results.
