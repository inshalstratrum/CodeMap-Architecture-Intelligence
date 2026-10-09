@echo off
cd /d "%~dp0"

if not exist "codemap_app.py" (
    echo codemap_app.py was not found next to this file.
    echo Keep Run CodeMap.bat, codemap_app.py and codemap_core.py in the same folder.
    pause
    exit /b
)

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "codemap_app.py"
    exit /b
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "codemap_app.py"
    exit /b
)

echo Python was not found on this PC.
echo Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during install), then try again.
pause
