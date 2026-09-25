@echo off
title ZZZ Achievement Scanner for StarDB
cd /d "%~dp0"
echo ========================================================
echo       Zenless Zone Zero - StarDB Achievement Scanner
echo ========================================================
echo.

python -c "import winsdk, PIL, pyperclip" 2>nul
if %errorlevel% neq 0 (
    echo [!] Missing required Python packages. Installing dependencies...
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
