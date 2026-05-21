@echo off
chcp 65001 >nul
title Fix IIS - CloakBrowser Detection Test

echo ============================================
echo   IIS Fix Script
echo   CloakBrowser Detection Test
echo ============================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b 1
)

set APPCMD=%windir%\system32\inetsrv\appcmd.exe

echo [1/7] Removing old site and pool ...
%APPCMD% stop site "CloakBrowserDetection" >nul 2>&1
%APPCMD% delete site "CloakBrowserDetection" >nul 2>&1
%APPCMD% stop apppool "CloakBrowserDetectionPool" >nul 2>&1
%APPCMD% delete apppool "CloakBrowserDetectionPool" >nul 2>&1
echo Done.

echo [2/7] Creating application pool (No Managed Code, Classic Pipeline) ...
%APPCMD% add apppool /name:"CloakBrowserDetectionPool" /managedRuntimeVersion:"" /managedPipelineMode:Classic
echo Done.

echo [3/7] Preparing site directory ...
set SITE_PATH=%~dp0site
if exist "%SITE_PATH%" rd /s /q "%SITE_PATH%"
mkdir "%SITE_PATH%"
copy /y "%~dp0index.html" "%SITE_PATH%\index.html" >nul
copy /y "%~dp0results.html" "%SITE_PATH%\results.html" >nul
copy /y "%~dp0web.config" "%SITE_PATH%\web.config" >nul
echo Done.

echo [4/7] Setting permissions ...
icacls "%SITE_PATH%" /grant "IUSR:(OI)(CI)R" /T /Q >nul 2>&1
icacls "%SITE_PATH%" /grant "IIS_IUSRS:(OI)(CI)R" /T /Q >nul 2>&1
echo Done.

echo [5/7] Creating site on port 8088 ...
%APPCMD% add site /name:"CloakBrowserDetection" /physicalPath:"%SITE_PATH%" /bindings:http/*:8088: /applicationPool:"CloakBrowserDetectionPool"
echo Done.

echo [6/7] Starting site ...
%APPCMD% start apppool "CloakBrowserDetectionPool"
%APPCMD% start site "CloakBrowserDetection"
echo Done.

echo [7/7] Opening firewall ...
netsh advfirewall firewall delete rule name="CloakBrowser Detection Test" >nul 2>&1
netsh advfirewall firewall add rule name="CloakBrowser Detection Test" dir=in action=allow protocol=TCP localport=8088 >nul 2>&1
echo Done.

echo.
echo ============================================
echo   Done! Try: http://YOUR_SERVER_IP:8088
echo.
echo   If still failing, use Python instead:
echo   cd /d "%~dp0"
echo   python server.py --port 8088
echo ============================================
echo.
pause
