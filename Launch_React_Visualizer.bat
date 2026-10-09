@echo off
title CodeMap - React Visualizer & Web Studio
cd /d "%~dp0"
echo Starting CodeMap React Visualizer on Port 5273...
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
