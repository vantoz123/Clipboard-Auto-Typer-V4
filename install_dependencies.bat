@echo off
setlocal
cd /d "%~dp0"
echo Installing Clipboard Auto Typer v4.1 dependencies...
if not exist .venv (
    py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Done. You can now run run_app.bat
pause
