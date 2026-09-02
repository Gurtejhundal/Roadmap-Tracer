@echo off
setlocal

title Traqo Launcher
set "ROOT=%~dp0"
set "LAUNCHER=%ROOT%launcher.ps1"

if not exist "%LAUNCHER%" (
    echo Traqo launcher script not found:
    echo %LAUNCHER%
    pause
    exit /b 1
)

if /I "%~1"=="-Stop" (
    echo Stopping Traqo...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" -Stop
    if errorlevel 1 exit /b 1
    exit /b 0
)

echo Starting Traqo...
powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" -Start %*

if errorlevel 1 (
    echo.
    echo Traqo could not start. Read the error above, then press any key.
    pause >nul
    exit /b 1
)

echo Traqo is ready at http://127.0.0.1:5173
exit /b 0
