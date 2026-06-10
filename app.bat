@echo off
REM ============================================================
REM Janan Project - Application Launcher
REM ============================================================
REM This script launches the Tremor Detection Web Application
REM ============================================================

setlocal enabledelayedexpansion

title Janan Project - Tremor Detection App

echo.
echo ============================================================
echo          JANAN PROJECT - TREMOR DETECTION APPLICATION
echo ============================================================
echo.

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [*] Project Directory: %SCRIPT_DIR%
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo [ERROR] Virtual environment not found!
    echo [*] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

echo [✓] Virtual environment activated
echo.

REM Install/update requirements
echo [*] Checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Some dependencies may not have installed correctly
)
echo [✓] Dependencies checked

echo.
echo ============================================================
echo [✓] Starting Flask Web Server (Admin Panel)
echo ============================================================
echo.
echo [INFO] Web Server will start on http://localhost:5000
echo [INFO] Admin Login: joel@gmail.com / Joel@123
echo [INFO] Press Ctrl+C to stop the server
echo.
echo ============================================================
echo.

REM Start the Flask web server
python web_server.py

REM If the script reaches here, it means web_server.py stopped
echo.
echo [*] Web server stopped
echo.
pause
