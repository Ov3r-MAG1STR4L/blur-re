@echo off
rem 32-bit DLL with Visual Studio (x86 tools). Output: b2gravity.dll here.
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /W4 /LD /MT b2gravity.c /link /DLL /OUT:b2gravity.dll kernel32.lib || exit /b 1
del /q b2gravity.obj b2gravity.exp b2gravity.lib 2>nul
