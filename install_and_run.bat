@echo off
title GoPro AutoDownload Setup
echo.
echo  GoPro AutoDownload
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Python not found. Opening download page...
    echo  Please install Python 3.8 or higher from python.org
    echo  IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    start https://www.python.org/downloads/
    echo  After installing Python, close this window and run this file again.
    pause
    exit
)

echo  Python found.
echo.
echo  Installing dependencies...
pip install requests google-auth-oauthlib google-api-python-client >nul 2>&1
echo  Dependencies installed.
echo.

:check_wifi
echo  Checking GoPro Wi-Fi connection...
ping -n 1 10.5.5.9 >nul 2>&1
if %errorlevel% neq 0 (
    echo  GoPro not found. Make sure your laptop is connected to GoPro Wi-Fi.
    echo  Retrying in 10 seconds...
    timeout /t 10 /nobreak >nul
    goto check_wifi
)

echo  GoPro connected. Starting download...
echo.
python "%~dp0gopro_downloader.py"
pause