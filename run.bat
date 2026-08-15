@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting RaceHub 赛事日历...
python main.py
if errorlevel 1 pause
