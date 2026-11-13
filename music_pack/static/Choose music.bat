@echo off
rem Blur Music pack: first run installs, then: pick playlists + game effects, build and install them.
chcp 65001 >nul
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'" & exit /b)
setlocal
cd /d "%~dp0"
title Blur Music

rem --- Python 3 (py launcher), numpy, ffmpeg ---
set "PY=py -3"
where py >nul 2>&1 || (
    echo Python 3 is not installed. It is needed to convert your music.
    choice /c YN /m "Install Python 3.12 now with winget (Microsoft's installer)"
    if errorlevel 2 goto :missing
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements || goto :missing
    echo.& echo Python installed. Close this window and run "Choose music.bat" again.& pause & exit /b 0
)
%PY% -c "import numpy, numba" >nul 2>&1 || (
    echo Installing numpy and numba for Python...
    %PY% -m pip install --disable-pip-version-check numpy numba || goto :missing
)
where ffmpeg >nul 2>&1 || (
    echo ffmpeg is not installed. It is needed to convert your music.
    choice /c YN /m "Install ffmpeg now with winget"
    if errorlevel 2 goto :missing
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements || goto :missing
    echo.& echo ffmpeg installed. Close this window and run "Choose music.bat" again.& pause & exit /b 0
)

set PYTHONIOENCODING=utf-8
%PY% "%~dp0tools\pack.py" menu
pause
exit /b 0

:missing
echo.
echo Could not continue: Python 3 (with numpy and numba) and ffmpeg are required. See README.txt.
pause
exit /b 1
