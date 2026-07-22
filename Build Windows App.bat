@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python is niet gevonden.
    pause
    exit /b 1
)

if not exist .venv py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name "Bluetooth Reset" app\bluetooth_reset.py

if errorlevel 1 (
    echo Build mislukt. Bekijk de fout hierboven.
    pause
    exit /b 1
)

echo.
echo Klaar: dist\Bluetooth Reset.exe
pause
