@echo off
rem 32-bit DLL with Visual Studio (x86 tools). Output: railgun.dll here.
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /W4 /LD /MT railgun.c /link /DLL /OUT:railgun.dll kernel32.lib || exit /b 1
del /q railgun.obj railgun.exp railgun.lib 2>nul
