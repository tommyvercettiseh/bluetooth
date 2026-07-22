@echo off
setlocal
cd /d "%~dp0"

if exist "dist\Bluetooth Reset.exe" (
    start "" "dist\Bluetooth Reset.exe"
    exit /b 0
)

where py >nul 2>nul
if errorlevel 1 (
    echo Python is niet gevonden.
    echo Installeer Python 3.11 of nieuwer en vink "Add Python to PATH" aan.
    pause
    exit /b 1
)

py -3 app\bluetooth_reset.py
if errorlevel 1 pause
