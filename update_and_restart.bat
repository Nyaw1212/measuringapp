@echo off
setlocal
cd /d "%~dp0"
title Measuring App - Update and Restart
echo Waiting for old application to close...
timeout /t 2 /nobreak >nul
echo.
echo Updating from GitHub...
git pull origin main
if errorlevel 1 goto failed
echo.
echo Update successful. Restarting app...
start "" "%~dp0run.bat"
exit /b 0
:failed
echo.
echo Git update failed. The app was not restarted.
echo Check for local changes or network errors above.
pause
exit /b 1
