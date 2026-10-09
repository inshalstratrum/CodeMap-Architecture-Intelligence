@echo off
title CodeMap - Python Tkinter Desktop Interface
cd /d "%~dp0"
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
python "codemap_app.py"
