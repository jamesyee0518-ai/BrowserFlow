@echo off
chcp 65001 >nul
title Install IIS Site - CloakBrowser Detection Test

echo ============================================
echo   IIS Deployment Script
echo   CloakBrowser Detection Test
echo ============================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script requires Administrator privileges.
    echo Please right-click and select "Run as administrator".
    pause
    exit /b 1
)

set APPCMD=%windir%\system32\inetsrv\appcmd.exe

where %APPCMD% >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing IIS ...
    dism /online /enable-feature /featurename:IIS-WebServer /all /NoRestart
    dism /online /enable-feature /featurename:IIS-StaticContent /all /NoRestart
    dism /online /enable-feature /featurename:IIS-DefaultDocument /all /NoRestart
    dism /online /enable-feature /featurename:IIS-HttpErrors /all /NoRestart
    dism /online /enable-feature /featurename:IIS-RequestFiltering /all /NoRestart
    echo [INFO] IIS installed.
)

set SITE_NAME=CloakBrowserDetection
set POOL_NAME=CloakBrowserDetectionPool
set SITE_PATH=%~dp0site

echo [INFO] Preparing site directory ...
if not exist "%SITE_PATH%" mkdir "%SITE_PATH%"
copy /y "%~dp0index.html" "%SITE_PATH%\index.html" >nul
copy /y "%~dp0results.html" "%SITE_PATH%\results.html" >nul
copy /y "%~dp0web.config" "%SITE_PATH%\web.config" >nul

echo [INFO] Setting directory permissions ...
icacls "%SITE_PATH%" /grant "IUSR:(OI)(CI)R" /T /Q >nul 2>&1
icacls "%SITE_PATH%" /grant "IIS_IUSRS:(OI)(CI)R" /T /Q >nul 2>&1

echo [INFO] Creating application pool (No Managed Code) ...
%APPCMD% list apppool "%POOL_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Pool already exists, updating ...
    %APPCMD% set apppool "%POOL_NAME%" /managedRuntimeVersion:"" /managedPipelineMode:Classic
) else (
    %APPCMD% add apppool /name:"%POOL_NAME%" /managedRuntimeVersion:"" /managedPipelineMode:Classic
    echo [INFO] Pool created with No Managed Code (static only).
)

echo [INFO] Configuring IIS site ...
%APPCMD% list site "%SITE_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Site already exists, updating ...
    %APPCMD% set site "%SITE_NAME%" -physicalPath:"%SITE_PATH%"
    %APPCMD% set app "%SITE_NAME%/" -applicationPool:"%POOL_NAME%"
) else (
    echo [INFO] Creating site on port 8088 ...
    %APPCMD% add site /name:"%SITE_NAME%" /physicalPath:"%SITE_PATH%" /bindings:http/*:8088: /applicationPool:"%POOL_NAME%"
)

%APPCMD% stop site "%SITE_NAME%" >nul 2>&1
%APPCMD% stop apppool "%POOL_NAME%" >nul 2>&1
timeout /t 2 /nobreak >nul
%APPCMD% start apppool "%POOL_NAME%" >nul 2>&1
%APPCMD% start site "%SITE_NAME%" >nul 2>&1

echo [INFO] Opening firewall port 8088 ...
netsh advfirewall firewall delete rule name="CloakBrowser Detection Test" >nul 2>&1
netsh advfirewall firewall add rule name="CloakBrowser Detection Test" dir=in action=allow protocol=TCP localport=8088 >nul 2>&1

echo.
echo ============================================
echo   Deployment Complete!
echo.
echo   URL: http://YOUR_SERVER_IP:8088
echo.
echo   Key fixes applied:
echo   - Application Pool: No Managed Code (static only)
echo   - Pipeline Mode: Classic (not Integrated)
echo   - ASP.NET modules cleared
echo   - Only StaticFile handler enabled
echo.
echo   If still seeing errors, try:
echo   1. Open IIS Manager, check the site is running
echo   2. Check Application Pool identity has read access
echo   3. Use Python server instead: python server.py
echo ============================================
echo.
pause
