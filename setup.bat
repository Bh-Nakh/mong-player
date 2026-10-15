@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem App name (Korean) lives in app.name so this file stays ASCII-only.
set /p APPNAME=<app.name
set /p VER=<VERSION
rem Package dist\<name>\ (made by build.bat) into setup\<name>-Setup-<version>.exe with Inno Setup.
if not exist "dist\%APPNAME%\%APPNAME%.exe" (
  echo dist\%APPNAME%\%APPNAME%.exe not found. Run build.bat first.
  exit /b 1
)
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
"%ISCC%" /DSrcDir="%~dp0dist\%APPNAME%" /DAppVersion=%VER% installer\%APPNAME%.iss || (echo SETUP FAILED & exit /b 1)
echo SETUP OK: setup\
exit /b 0
