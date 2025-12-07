@echo off
title Roadmap Tracer Launcher
echo ===================================================
echo [1/3] Starting Backend Server...
cd /d "e:\antigravity\roadmap_web\backend"
start "Roadmap Backend" cmd /c "uvicorn main:app --reload --port 8000"

echo [2/3] Starting Frontend Server...
cd /d "e:\antigravity\roadmap_web\frontend"
start "Roadmap Frontend" cmd /c "npm run dev"

echo [3/3] Opening Application...
echo Waiting for servers to initialize...
timeout /t 5 >nul
start http://localhost:5173

echo ===================================================
echo Roadmap Tracer is running!
echo You can minimize the backend/frontend windows.
echo ===================================================
timeout /t 5
exit
