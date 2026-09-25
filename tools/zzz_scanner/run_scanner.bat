@echo off
title ZZZ Achievement Scanner for StarDB
cd /d "%~dp0"

:: Auto-elevate to Administrator (required by Windows to send mouse input to elevated game processes)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================================
    echo  Elevating to Administrator for hands-free automation...
    echo ========================================================
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================================
echo       Zenless Zone Zero - StarDB Achievement Scanner
echo ========================================================
echo.

python -c "import winsdk, PIL, pyperclip" 2>nul
if %errorlevel% neq 0 (
    echo [!] Installing required Python packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements. Please run 'pip install -r requirements.txt' manually.
        pause
        exit /b %errorlevel%
    )
    echo.
)

python scanner.py
pause
