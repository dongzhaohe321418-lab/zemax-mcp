@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_local.ps1"
if errorlevel 1 (
  echo.
  echo Setup failed. Review the message above.
  pause
  exit /b 1
)
call "%~dp0launch_app.cmd"
