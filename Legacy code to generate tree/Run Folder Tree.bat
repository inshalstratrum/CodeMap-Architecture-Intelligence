@echo off
cd /d "%~dp0"

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "folder_tree.py"
    exit /b
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "folder_tree.py"
    exit /b
)

echo Python was not found on this PC.
echo Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during install), then try again.
pause
