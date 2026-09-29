@echo off
cd /d "%~dp0"
echo Installing dependencies for Final BOQ Engine...
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    echo Installation failed.
    pause
    exit /b 1
)
echo Dependencies installed successfully.
pause
