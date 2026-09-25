@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0distribution\run_windows.ps1" %*
set "BRIDCT_EXIT=%ERRORLEVEL%"
echo.
echo Exit code: %BRIDCT_EXIT%
if not defined GITHUB_ACTIONS pause
exit /b %BRIDCT_EXIT%
