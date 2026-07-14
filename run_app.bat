@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
    echo Virtual environment not found. Running install_dependencies.bat first...
    call install_dependencies.bat
)
call .venv\Scripts\activate.bat
python main.py
