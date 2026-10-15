@echo off
rem 몽플레이어 개발용 실행 (콘솔 없이). 파일을 끌어다 놓으면 그 파일로 시작.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m noadplayer %*
