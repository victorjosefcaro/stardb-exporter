@echo off
title Build Standalone ZZZ Scanner Executable
cd /d "%~dp0..\.."

echo ========================================================
echo       Building Standalone zzz_scanner.exe
echo ========================================================
echo.

pip install pyinstaller winsdk pillow pyperclip
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b %errorlevel%
)

pyinstaller --noconfirm --clean --onefile ^
    --icon "icons/icon.ico" ^
    --name zzz_scanner ^
    --add-data "tools/zzz_scanner/stardb_zzz_achievements.json;." ^
    --collect-all winsdk ^
    tools/zzz_scanner/scanner.py

if %errorlevel% equ 0 (
    copy /y "dist\zzz_scanner.exe" "tools\zzz_scanner\zzz_scanner.exe"
    echo.
    echo ========================================================
    echo  BUILD SUCCESS! Standalone executable is ready at:
    echo  - dist\zzz_scanner.exe
    echo  - tools\zzz_scanner\zzz_scanner.exe
    echo ========================================================
) else (
    echo [ERROR] Build failed.
)

pause
