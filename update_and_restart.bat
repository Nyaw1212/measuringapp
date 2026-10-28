@echo off
setlocal
cd /d "%~dp0"
title Measuring App - Update and Restart
echo Waiting for the old app to exit...
timeout /t 3 /nobreak >nul
echo.
where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git was not found on PATH.
  goto failed
)
echo Updating from GitHub...
git pull --ff-only origin main
if errorlevel 1 goto failed
echo.
echo Update complete. Launching Measuring App...
if not exist "%~dp0run.bat" (
  echo ERROR: run.bat was not found.
  goto failed
)
start "" cmd.exe /c ""%~dp0run.bat""
exit /b 0
:failed
echo.
echo Update or restart failed. Review the error above.
echo Your project cache remains saved.
pause
exit /b 1
