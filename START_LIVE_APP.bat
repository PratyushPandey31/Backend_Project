@echo off
title EstateIntel AI Portfolio Analyst - Live Runner
cd /d "D:\Backend"
echo =======================================================
echo   EstateIntel AI - Real Estate Portfolio Analyst
echo =======================================================
echo.
echo [1/2] Starting local FastAPI server on port 8000...
start "" /B python main.py
timeout /t 2 /nobreak >nul

echo [2/2] Launching Cloudflare Live Tunnel...
echo.
echo Press Ctrl+C anytime to stop.
echo =======================================================
.\cloudflared.exe tunnel --url http://127.0.0.1:8000
pause
