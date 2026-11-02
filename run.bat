@echo off
chcp 65001 >nul
if not exist .env call setup.bat
echo Starting... press Ctrl+C to stop
python server.py
pause
