@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_ui.ps1"
set "exit_code=%ERRORLEVEL%"
if not "%exit_code%"=="0" (
  echo.
  echo Sopotek Quant System desktop could not be launched.
  echo Check desktop_app\logs\host-ui-latest.txt for the newest log paths.
  echo.
  pause
)
exit /b %exit_code%
