# Asteria Background Input Design

## Goal

Allow MapleBot to discover Asteria without administrator privileges and make the strongest safe attempt to deliver automation keys while Asteria is unfocused. Normal automation must never steal focus or inject keyboard input into the application the user is actively using.

## Constraints

- Asteria may run elevated or restrict process inspection.
- Asteria may expose its keyboard receiver as a child or render window rather than its top-level window.
- Asteria may consume DirectInput or raw input instead of ordinary window messages. If so, Windows does not provide a general user-mode method for delivering hardware-like input exclusively to an unfocused window.
- A successful `PostMessage` call proves only that Windows accepted the message, not that Asteria acted on it.
- MapleBot must not silently fall back to `pynput` or `SendInput` during background automation.

## Process Discovery

Window enumeration will continue to match known titles and executable names. Process-name lookup will request only `PROCESS_QUERY_LIMITED_INFORMATION` and use `QueryFullProcessImageNameW`. It will not request `PROCESS_VM_READ` merely to identify an executable. Failure to inspect one process will not abort enumeration.

The implementation will retain process-only fallback entries when a matching process exists but no usable visible window is found.

## Background Input Target Discovery

For each selected Asteria top-level HWND, MapleBot will enumerate descendant windows and collect stable metadata:

- HWND
- parent HWND
- window class
- title
- visibility and enabled state

The top-level window remains the default target. Child targets will be ordered using conservative signals such as visibility, enabled state, and common render/input-host class names. No process memory inspection or code injection will be used.

## Input Strategy

Background key delivery will use a bounded strategy chain:

1. Send correctly formed `WM_KEYDOWN` and `WM_KEYUP` messages to the top-level HWND.
2. If configured diagnostic probing identifies a more plausible child receiver, send the same pair to that child HWND.
3. For printable character input where text semantics are intended, support `WM_CHAR`; gameplay keys will continue to use key-down/key-up semantics.

Normal operation will choose one resolved target and will not broadcast every key to every child window. This avoids duplicate actions if more than one target accepts the message.

Windows API success will be reported as "message accepted." MapleBot will not claim that Asteria processed the key without observable evidence.

## Focus Safety

The background path must not call:

- `SetForegroundWindow`
- `SetFocus`
- `BringWindowToTop`
- `pynput` keyboard injection
- `SendInput`

Foreground input remains available only through explicit foreground-oriented actions. The existing background setting will be honored: background mode uses only the safe message path; foreground mode may activate the selected game window before using the keyboard controller.

There will be no automatic foreground fallback after a failed or ignored background attempt.

## Diagnostics and Failure Handling

Diagnostic output will identify:

- selected process and top-level HWND
- whether executable-name lookup succeeded with limited rights
- candidate child HWNDs and class names
- selected message target and strategy
- API rejection and Windows error information

Repeated identical failures should be rate-limited during automation loops so logs remain usable.

If all safe message strategies are accepted by Windows but ignored by Asteria while unfocused, MapleBot will report that the client likely requires foreground, raw, or driver-level input. A virtual input driver or client-specific integration is outside this change because it is invasive and may conflict with anti-cheat protections.

## Testing

Automated tests will cover:

- process-name lookup uses limited query rights without `PROCESS_VM_READ`
- elevated/inaccessible process metadata does not break window enumeration
- child-window candidates are collected and ordered deterministically
- background sends target the resolved HWND without invoking focus APIs or the keyboard controller
- foreground and background settings select their intended paths
- message failures return false and expose useful diagnostics

Tests will mock Windows boundaries; they will not send real keyboard input. A live Asteria session remains necessary to determine whether the client consumes any safe background message strategy.

## Success Criteria

- A non-elevated MapleBot can identify Asteria when Windows permits limited process queries.
- Background automation never changes the foreground window or types into the user's active application.
- The configured background/foreground mode is respected.
- Logs show which Asteria HWND and message strategy were attempted.
- Tests protect the discovery and focus-safety behavior.
