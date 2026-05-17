@echo off
setlocal

title Roadmap Tracer Launcher
set "ROOT=%~dp0"
set "GUI_LAUNCHER=%ROOT%launcher.ps1"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "APP_URL=http://127.0.0.1:5173"

if exist "%GUI_LAUNCHER%" (
    powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%GUI_LAUNCHER%"
    if not errorlevel 1 exit /b 0
    echo GUI launcher failed. Falling back to console launcher.
    echo.
)

echo ==================================================
echo Roadmap Tracer
echo ==================================================

if not exist "%BACKEND_DIR%\main.py" (
    echo Backend folder not found: %BACKEND_DIR%
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo Frontend folder not found: %FRONTEND_DIR%
    pause
    exit /b 1
)

echo [1/4] Checking frontend dependencies...
if not exist "%FRONTEND_DIR%\node_modules" (
    pushd "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        echo npm install failed.
        pause
        exit /b 1
    )
    popd
)

echo [2/4] Checking backend dependencies...
python -c "import fastapi, sqlalchemy, pypdf" >nul 2>nul
if errorlevel 1 (
    pushd "%BACKEND_DIR%"
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Backend dependency install failed.
        pause
        exit /b 1
    )
    popd
)

echo [3/4] Starting backend...
start "Roadmap Tracer Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && python -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo [4/4] Starting frontend...
start "Roadmap Tracer Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev -- --host 127.0.0.1 --port 5173"

echo Waiting for the app to start...
timeout /t 5 >nul
start "" "%APP_URL%"

echo.
echo App opened at %APP_URL%
echo Keep the backend and frontend windows open while using it.
echo.
pause
