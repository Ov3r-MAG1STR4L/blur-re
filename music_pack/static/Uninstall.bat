@echo off
rem Blur Music pack: puts the game back exactly as it was before the first "Choose music.bat".
chcp 65001 >nul
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'" & exit /b)
setlocal
cd /d "%~dp0"
set "PY=py -3"
where py >nul 2>&1 || set "PY=python"
set PYTHONIOENCODING=utf-8
%PY% "%~dp0tools\pack.py" uninstall
pause
