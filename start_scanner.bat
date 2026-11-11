@echo off
title Local Wi-Fi Book Scanner (Multi-Phone Enabled)
cd /d "%~dp0"
echo ========================================================
echo   Starting Multi-Phone Local Book Scanner...
echo ========================================================
start "" http://localhost:5000
py server.py
pause
