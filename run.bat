@echo off
setlocal
cd /d "%~dp0"
title Measuring App
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if errorlevel 1 goto missing_python
set "PYTHON=python"
goto setup
:use_py
set "PYTHON=py"
:setup
if exist ".venv\Scripts\python.exe" goto install
echo Creating virtual environment...
%PYTHON% -m venv .venv
if errorlevel 1 goto failed
:install
if exist ".venv\installed.ok" goto launch
echo Installing dependencies on first run...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
type nul > ".venv\installed.ok"
:launch
echo Starting Measuring App...
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
exit /b 0
:missing_python
echo Python was not found. Install Python 3 and try again.
goto failed
:failed
echo.
echo Something went wrong. See the error above.
pause
exit /b 1
