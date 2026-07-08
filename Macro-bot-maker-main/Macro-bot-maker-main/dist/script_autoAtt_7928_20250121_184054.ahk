#SingleInstance Force
#NoEnv
SetWorkingDir %A_ScriptDir%

global targetPID := 7928

Loop
{
    if ProcessExist(targetPID)
    {
        ControlSend,, {F7}, ahk_pid %targetPID%
        Sleep 8000
        ControlSend,, {F8}, ahk_pid %targetPID%
        Sleep 9000
        ControlSend,, {F9}, ahk_pid %targetPID%
        Sleep 10000
        ControlSend,, {F10}, ahk_pid %targetPID%
        Sleep 7000
        ControlSend,, {F11}, ahk_pid %targetPID%
        Sleep 6000
        ControlSend,, {F12}, ahk_pid %targetPID%
        Sleep 5000
    }
}

ProcessExist(PID)
{
    Process, Exist, %PID%
    return ErrorLevel
}

^Esc::ExitApp