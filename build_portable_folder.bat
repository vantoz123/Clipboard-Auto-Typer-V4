@echo off
setlocal
cd /d "%~dp0"
call build_exe.bat
if not exist portable mkdir portable
if exist "dist\Clipboard Auto Typer v4.1.exe" copy /Y "dist\Clipboard Auto Typer v4.1.exe" "portable\Clipboard Auto Typer v4.1.exe"
copy /Y README.md portable\README.md
copy /Y USER_MANUAL.pdf portable\USER_MANUAL.pdf
if not exist portable\logs mkdir portable\logs
echo.
echo Portable folder prepared at: portable
echo You can copy the portable folder to another Windows computer.
pause
