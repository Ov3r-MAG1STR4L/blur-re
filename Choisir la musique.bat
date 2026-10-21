@echo off
rem Choisit la ou les playlists de musique de course (dossiers dans C:\Users\sanqu\Jeux_WII\Blur_musiques),
rem les prepare et les installe dans la copie de test (Blur_test). Le jeu en ligne n'est jamais touche.
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python music_menu.py
echo.
pause
