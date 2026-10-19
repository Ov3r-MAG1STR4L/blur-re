@echo off
rem Lance la copie de test (mod) en protegeant la sauvegarde Blur, partagee avec le jeu en ligne :
rem   1. sauvegarde %APPDATA%\bizarre creations\blur (save + settings.xml) dans blur_save_backups\avant_test
rem   2. lance Blur_test\Blur.exe et attend sa fermeture
rem   3. remet la sauvegarde d'avant le test
rem Si un test precedent n'a pas ete restaure (marqueur EN_COURS), on restaure d'abord, sans ecraser la copie.
chcp 65001 >nul
setlocal
set "TEST=C:\Users\sanqu\Jeux_WII\Blur_test"
set "SAVE=%APPDATA%\bizarre creations\blur"
set "BK=C:\Users\sanqu\Jeux_WII\blur_save_backups\avant_test"

tasklist /fi "imagename eq Blur.exe" | "%SystemRoot%\System32\find.exe" /i "Blur.exe" >nul && (echo Blur est deja lance : ferme-le d'abord. & pause & exit /b 1)
if not exist "%TEST%\COPIE_DE_TEST_HORS_LIGNE.txt" (echo Copie de test introuvable : %TEST% & pause & exit /b 1)
if exist "%TEST%\amax\dlls\amax_auth.asi" (echo La copie contient amax_auth.asi : elle pourrait aller en ligne. Arret. & pause & exit /b 1)

if exist "%BK%\EN_COURS" (
    echo Un test precedent n'a pas ete restaure : je remets d'abord la sauvegarde d'avant ce test.
    call :restore || (pause & exit /b 1)
)

echo Sauvegarde de ta progression...
robocopy "%SAVE%\save" "%BK%\save" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo Echec de la sauvegarde. Arret. & pause & exit /b 1)
copy /y "%SAVE%\settings.xml" "%BK%\settings.xml" >nul || (echo Echec de la sauvegarde. Arret. & pause & exit /b 1)
echo %date% %time%> "%BK%\EN_COURS"

echo Lancement de la copie de test (hors ligne). Ferme le jeu pour revenir ici.
cd /d "%TEST%"
start "" /wait "%TEST%\Blur.exe"

call :restore || (pause & exit /b 1)
echo Termine : ta progression d'avant le test est remise.
timeout /t 5 >nul
exit /b 0

:restore
robocopy "%BK%\save" "%SAVE%\save" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo ECHEC de la restauration : ta sauvegarde est dans %BK% & exit /b 1)
copy /y "%BK%\settings.xml" "%SAVE%\settings.xml" >nul || (echo ECHEC de la restauration : ta sauvegarde est dans %BK% & exit /b 1)
del "%BK%\EN_COURS"
echo Sauvegarde remise.
exit /b 0
