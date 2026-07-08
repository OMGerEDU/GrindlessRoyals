#SingleInstance Force
#NoEnv
SetWorkingDir %A_ScriptDir%

global targetPID := 27956

Loop
{
    if ProcessExist(targetPID)
    {
        ControlSend,, {F1}, ahk_pid %targetPID%
        Sleep 6000
        ControlSend,, {F2}, ahk_pid %targetPID%
        Sleep 4000
    }
}

ProcessExist(PID)
{
    Process, Exist, %PID%
    return ErrorLevel
}

^Esc::ExitApp