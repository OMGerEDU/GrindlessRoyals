#SingleInstance Force
#Persistent
#NoEnv
SetWorkingDir %A_ScriptDir%
CoordMode, Mouse, Window

WinGet, target_window, ID, ahk_pid 25392
SetTitleMatchMode, 2
SetKeyDelay, 10, 10

; Script Info:
; Profile: s
; Process PID: 25392
; Generated: 2025-01-19 13:21:19

running := true

F12::
    running := false
    ExitApp
return

Loop {
    if (!running)
        ExitApp

    ControlGet, isActive, Visible,,, ahk_id %target_window%
    if (!isActive) {
        continue
    }

    WinActivate, ahk_id %target_window%
    WinWaitActive, ahk_id %target_window%

    if (!running)
        ExitApp
    ControlSend,, {F10}}, ahk_id %target_window%
    Sleep, 35000
    if (!running)
        ExitApp
    ControlSend,, {F11}}, ahk_id %target_window%
    Sleep, 30000
    if (!running)
        ExitApp
    ControlSend,, {F12}}, ahk_id %target_window%
    Sleep, 40000
    if (!running)
        ExitApp
}
ExitApp