@echo off
rem Lance le jeu installe (en ligne via AMAX). Si un test du mod n'a pas ete restaure, remet d'abord la
rem sauvegarde d'avant le test (sinon la progression du test partirait en ligne).
chcp 65001 >nul
setlocal
set "GAME=C:\Program Files (x86)\Activision\Blur(TM)"
set "SAVE=%APPDATA%\bizarre creations\blur"
set "BK=C:\Users\sanqu\Jeux_WII\blur_save_backups\avant_test"

tasklist /fi "imagename eq Blur.exe" | "%SystemRoot%\System32\find.exe" /i "Blur.exe" >nul && (echo Blur est deja lance. & pause & exit /b 1)

if exist "%BK%\EN_COURS" (
    echo Un test du mod n'a pas ete restaure : je remets ta sauvegarde d'avant le test.
    robocopy "%BK%\save" "%SAVE%\save" /MIR /NFL /NDL /NJH /NJS /NP >nul
    if errorlevel 8 (echo ECHEC de la restauration : rien n'est lance. Sauvegarde dans %BK% & pause & exit /b 1)
    copy /y "%BK%\settings.xml" "%SAVE%\settings.xml" >nul || (echo ECHEC de la restauration : rien n'est lance. & pause & exit /b 1)
    del "%BK%\EN_COURS"
)

cd /d "%GAME%"
start "" "%GAME%\Blur.exe"
