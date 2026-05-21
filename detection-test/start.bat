@echo off
chcp 65001 >nul
title CloakBrowser Detection Test Server

echo ============================================
echo   CloakBrowser Detection Test
echo   Windows Server Deployment
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

cd /d "%~dp0"
echo [INFO] Starting server on port 8088 ...
echo [INFO] Detection page:  http://YOUR_SERVER_IP:8088
echo [INFO] Results page:    http://YOUR_SERVER_IP:8088/results.html
echo [INFO] API endpoint:    http://YOUR_SERVER_IP:8088/api/results
echo [INFO] Press Ctrl+C to stop
echo.
python server.py --port 8088 --bind 0.0.0.0
