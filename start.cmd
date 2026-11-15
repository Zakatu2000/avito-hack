@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -OpenBrowser %*
set "result=%errorlevel%"
if not "%result%"=="0" pause
exit /b %result%
