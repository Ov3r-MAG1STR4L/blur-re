@echo off
rem Blur Music pack: first run installs, then: pick playlists + game effects, build and install them.
rem Python 3 and ffmpeg are installed by the player (see README.txt); numpy and numba come from pip.
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Blur Music

rem ffmpeg: also looked for inside the pack (tools\ffmpeg, no PATH needed) and where winget puts it.
rem Python: also looked for where its installer puts it, even when it is not in PATH (a player's PATH edits
rem kept dropping one or the other, 2026-11-14).
set "PATH=%~dp0tools\ffmpeg;%~dp0tools\ffmpeg\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
set "PY=py -3"
where py >nul 2>&1 || set "PY=python"
%PY% --version >nul 2>&1 || (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set PY="%%D\python.exe"
)
%PY% --version >nul 2>&1 || (
    echo Python 3 is not installed: see "REQUIREMENTS" in README.txt.
    goto :end
)
where ffmpeg >nul 2>&1 || (
    echo ffmpeg is not installed: see "REQUIREMENTS" in README.txt.
    goto :end
)
%PY% -c "import numpy, numba" >nul 2>&1 || (
    echo Installing the Python modules numpy and numba ^(pip^)...
    %PY% -m pip install --disable-pip-version-check numpy numba || (
        echo pip could not install numpy and numba: see "REQUIREMENTS" in README.txt.
        goto :end
    )
)

set PYTHONIOENCODING=utf-8
%PY% "%~dp0tools\pack.py" menu

:end
pause
