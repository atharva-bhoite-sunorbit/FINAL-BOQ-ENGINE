@echo off
cd /d "%~dp0"
echo Starting Construction BOQ Engine server...
py -3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
pause
