@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set /p APPNAME=<app.name
rem Build dist\<name>\<name>.exe with PyInstaller (App name lives in app.name so this file stays ASCII-only).
if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Create it first and install requirements.txt.
  exit /b 1
)
".venv\Scripts\python.exe" tools\build.py
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
echo BUILD OK: dist\%APPNAME%\%APPNAME%.exe
