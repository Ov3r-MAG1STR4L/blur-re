@echo off
rem Blur Music pack: puts the game back exactly as it was before the first "Choose music.bat".
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PY=py -3"
where py >nul 2>&1 || set "PY=python"
%PY% --version >nul 2>&1 || (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set PY="%%D\python.exe"
)
set PYTHONIOENCODING=utf-8
%PY% "%~dp0tools\pack.py" uninstall
pause
