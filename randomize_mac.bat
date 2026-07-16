@echo off
:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

:: Auto-create skipInit to bypass DevCon download reminder prompt
if not exist "MacChanger\chmac\Data\skipInit" (
    echo skipInit > "MacChanger\chmac\Data\skipInit"
)

echo ===================================================
echo             Randomize MAC Address
echo ===================================================
echo.
echo Listing available network adapters:
echo.

call "MacChanger\chmac\chmac.bat" /l

echo.
set /p adapter_num="Enter the adapter number to randomize (type 'all' to randomize all, default is 1): "
if "%adapter_num%"=="" set adapter_num=1

if /i "%adapter_num%"=="all" (
    echo.
    echo Randomizing MAC address for ALL network adapters...
    echo.
    setlocal enabledelayedexpansion
    set count=0
    for /f "usebackq tokens=1-4 delims=," %%i in (`getmac /v /nh /fo csv 2^>nul`) do (
        set /a count+=1
        echo ---------------------------------------------------
        echo Randomizing adapter !count!: %%~i ...
        call "MacChanger\chmac\chmac.bat" /n !count!
    )
    endlocal
) else (
    echo.
    echo Randomizing MAC address for adapter %adapter_num%...
    echo.
    call "MacChanger\chmac\chmac.bat" /n %adapter_num%
)

echo.
echo Operation finished.
echo.
pause
