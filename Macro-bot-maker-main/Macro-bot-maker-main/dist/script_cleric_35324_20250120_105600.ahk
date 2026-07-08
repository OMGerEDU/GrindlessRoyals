#SingleInstance Force
#NoEnv
SetWorkingDir %A_ScriptDir%

global targetPID := 35324

Loop
{
    if ProcessExist(targetPID)
    {
        ControlSend,, {F3}, ahk_pid %targetPID%
        Sleep 608000
        ControlSend,, {F4}, ahk_pid %targetPID%
        Sleep 606000
        ControlSend,, {F5}, ahk_pid %targetPID%
        Sleep 604000
        ControlSend,, {F6}, ahk_pid %targetPID%
        Sleep 600000
        ControlSend,, {F7}, ahk_pid %targetPID%
        Sleep 10000
        ControlSend,, {F8}, ahk_pid %targetPID%
        Sleep 15000
        ControlSend,, {F9}, ahk_pid %targetPID%
        Sleep 25000
        ControlSend,, {F10}, ahk_pid %targetPID%
        Sleep 35000
        ControlSend,, {F11}, ahk_pid %targetPID%
        Sleep 30000
        ControlSend,, {F12}, ahk_pid %targetPID%
        Sleep 20000
    }
}

ProcessExist(PID)
{
    Process, Exist, %PID%
    return ErrorLevel
}

^Esc::ExitApp