@echo off
setlocal

cls
echo.
echo ============================================================
echo   TREMOR SEVERITY DETECTION - START APP
echo ============================================================
echo.

set "VENV="
for %%V in (.venv_run .venv_fixed .venv) do (
    if exist "%%V\Scripts\python.exe" (
        call :check_env "%%V"
        if not errorlevel 1 (
            set "VENV=%%V"
            goto :env_found
        )
    )
)

echo ERROR: No working virtual environment was found.
echo Checked: .venv_run, .venv_fixed, .venv
echo Create or repair the environment, then try again.
pause
exit /b 1

:env_found

echo Using environment: %VENV%
echo Starting backend API...
start "Tremor Backend API" cmd /k "cd /d %~dp0backend && ..\%VENV%\Scripts\python.exe main.py"
timeout /t 3 /nobreak >nul

echo Starting Flask web interface...
start "Tremor Web Server" cmd /k "cd /d %~dp0 && set PYTHONIOENCODING=utf-8 && %VENV%\Scripts\python.exe web_server.py"
timeout /t 3 /nobreak >nul

echo Opening http://localhost:5000 ...
start "" http://localhost:5000

echo.
echo Backend API:   http://localhost:8000
echo Web Interface: http://localhost:5000
echo.
echo Close the two command windows to stop the project.
pause
exit /b 0

:check_env
"%~1\Scripts\python.exe" -c "import sys" >nul 2>&1
exit /b %errorlevel%
