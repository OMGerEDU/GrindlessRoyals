#SingleInstance Force
#NoEnv
SetWorkingDir %A_ScriptDir%

global targetPID := 38584

Loop
{
    if ProcessExist(targetPID)
    {
        ControlSend,, {F10}, ahk_pid %targetPID%
        Sleep 3000
        ControlSend,, {F11}, ahk_pid %targetPID%
        Sleep 4000
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