@echo off
REM ============================================
REM  Tremor Analysis App - Launch Script
REM ============================================
REM This script starts both the backend API and Flask web server

setlocal enabledelayedexpansion

REM Set the project directory
cd /d "%~dp0"

echo.
echo ============================================
echo   Starting Tremor Analysis App
echo ============================================
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call .\.venv\Scripts\activate.bat

REM Start Backend API on port 8001
echo [2/3] Starting Backend API on port 8001...
set API_PORT=8001
start "Backend API" cmd /k ".\.venv\Scripts\python.exe backend/main.py"

REM Wait a moment for backend to start
timeout /t 3 /nobreak

REM Start Flask Web Server on port 5000
echo [3/3] Starting Flask Web Server on port 5000...
start "Web Server" cmd /k ".\.venv\Scripts\python.exe web_server.py"

REM Wait for servers to fully start
timeout /t 2 /nobreak

echo.
echo ============================================
echo   ✓ App Started Successfully!
echo ============================================
echo.
echo   🌐 Web Server:  http://localhost:5000
echo   📡 Backend API: http://localhost:8001
echo.
echo   • Dashboard:    http://localhost:5000/dashboard
echo   • Analyze:      http://localhost:5000/analyze
echo   • Admin Panel:  http://localhost:5000/admin/login
echo.
echo   Press CTRL+C in either window to stop servers
echo.
echo ============================================
echo.

REM Optional: Open browser
echo Opening app in browser...
timeout /t 2 /nobreak
start http://localhost:5000/

endlocal
pause
