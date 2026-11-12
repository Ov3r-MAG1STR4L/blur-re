@echo off
rem Blur Music pack: new random order for the race music (asks for administrator rights: the game folder is
rem protected), then starts Blur normally. Refusing the prompt just starts Blur with the previous order.
chcp 65001 >nul
setlocal
set "PY=py"
where py >nul 2>&1 || set "PY=python"
powershell -NoProfile -Command "Start-Process -Verb RunAs -Wait -WindowStyle Hidden -FilePath '%PY%' -ArgumentList '\"%~dp0tools\pack.py\"','reshuffle'" 2>nul
cd /d "%~dp0.."
start "" "%~dp0..\Blur.exe"
