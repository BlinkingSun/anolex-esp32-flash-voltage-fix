@echo off
rem AnoleX controller flash-voltage fix - Windows launcher.
rem Double-click this file. It sets up Python's esptool (first run only, needs internet)
rem and starts the guided fix. It never moves the machine.
setlocal
cd /d "%~dp0"
title AnoleX controller fix (Windows)
echo AnoleX controller fix (Windows)
echo -------------------------------
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY goto nopython

set "VENV=%LOCALAPPDATA%\anolex-fix-venv"
if exist "%VENV%\Scripts\python.exe" goto havevenv
echo First run: setting up a private Python environment - needs internet, about a minute...
%PY% -m venv "%VENV%"
if errorlevel 1 goto venvfail
:havevenv

"%VENV%\Scripts\python.exe" -c "import esptool,sys; sys.exit(0 if int(esptool.__version__.split('.')[0]) >= 5 else 1)" >nul 2>&1
if not errorlevel 1 goto run
echo Installing esptool - one time, needs internet...
"%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check --upgrade esptool
if errorlevel 1 goto pipfail

:run
"%VENV%\Scripts\python.exe" "%~dp0anolex_flash_voltage_fix.py" --guided
echo.
pause
exit /b 0

:nopython
echo Python 3.8 or newer is not installed.
echo   1. Download it from https://www.python.org/downloads/windows/
echo   2. On the FIRST installer screen tick "Add python.exe to PATH", then Install Now.
echo   3. Double-click this file again.
echo.
pause
exit /b 1

:venvfail
echo Could not create the Python environment.
echo.
pause
exit /b 1

:pipfail
echo Installing esptool failed. Check the internet connection and try again.
echo.
pause
exit /b 1
