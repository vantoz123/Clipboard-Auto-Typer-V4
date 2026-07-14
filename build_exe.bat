@echo off
setlocal
cd /d "%~dp0"
echo Building Clipboard Auto Typer v4.1 executable...
if not exist .venv (
    py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "Clipboard Auto Typer v4.1" main.py
if exist "dist\Clipboard Auto Typer v4.1.exe" (
    echo.
    echo Build complete: dist\Clipboard Auto Typer v4.1.exe
) else (
    echo.
    echo Build may have failed. Check the output above.
)
pause
