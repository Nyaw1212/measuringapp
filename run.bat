@echo off
setlocal
cd /d "%~dp0"
title Measuring App
where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON=py"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python was not found. Install Python 3 and try again.
    pause
    exit /b 1
  )
  set "PYTHON=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :failed
)
if not exist ".venv\installed.ok" (
  echo Installing dependencies (first run only)...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
  type nul > ".venv\installed.ok"
)
echo Starting Measuring App...
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto :failed
exit /b 0
:failed
echo.
echo Something went wrong. See the error above.
pause
exit /b 1
