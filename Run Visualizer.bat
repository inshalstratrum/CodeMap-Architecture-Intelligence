@echo off
cd /d "%~dp0"
title CodeMap React Visualizer & Control Center

echo ================================================================
echo  Starting CodeMap React Visualizer & Full-Stack Control Center
echo  Port: 5273 (Independent from port 5173)
echo ================================================================

where py >nul 2>nul
if %errorlevel%==0 (
    start "CodeMap Visualizer (Port 5273)" py "codemap_api.py"
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "CodeMap Visualizer (Port 5273)" python "codemap_api.py"
    exit /b
)

echo Python not found on PATH. Falling back to pnpm preview...
cd visualizer-ui
pnpm preview --port 5273 --open
pause
