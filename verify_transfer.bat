@echo off
REM Verify all project files are present after transfer
REM Run this after extracting the ZIP file

setlocal enabledelayedexpansion

cls
echo.
echo ============================================================
echo   TREMOR PROJECT - POST-TRANSFER VERIFICATION
echo ============================================================
echo.

set critical_ok=0
set missing_count=0

REM Check Python
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python NOT found - Please install from https://www.python.org/
    set missing_count=!missing_count!+1
) else (
    echo ✅ Python found
    set critical_ok=!critical_ok!+1
)

echo.
echo Checking critical files...
echo.

REM Array of critical files
set "files[0]=setup.bat"
set "files[1]=launch.bat"
set "files[2]=web_server.py"
set "files[3]=requirements.txt"
set "files[4]=README.md"
set "files[5]=START_HERE.txt"
set "files[6]=backend\main.py"
set "files[7]=models\mobilenet_tremor_detector.pth"
set "files[8]=templates\index.html"

setlocal enabledelayedexpansion
for /l %%i in (0,1,8) do (
    set "file=!files[%%i]!"
    if exist "!file!" (
        echo ✅ !file!
        set critical_ok=!critical_ok!+1
    ) else (
        echo ❌ !file! - MISSING!
        set missing_count=!missing_count!+1
    )
)

echo.
echo ============================================================
echo   Checking optional folders...
echo ============================================================
echo.

if exist "datasets\essential_tremor" (
    echo ✅ datasets\essential_tremor\ found
) else (
    echo ❌ datasets\essential_tremor\ MISSING
)

if exist "frames" (
    echo ✅ frames\ folder found
) else (
    echo ⚠️  frames\ folder not found (optional - will be created on training)
)

if exist "frontend" (
    echo ✅ frontend\ folder found (optional for React)
) else (
    echo ⚠️  frontend\ folder not found (optional - using Flask UI)
)

echo.
echo ============================================================
echo.

if %missing_count% equ 0 (
    echo ✅ ALL CRITICAL FILES PRESENT!
    echo.
    echo Next steps:
    echo   1. Double-click: setup.bat
    echo   2. Wait for "SETUP COMPLETE" message
    echo   3. Double-click: launch.bat
    echo   4. Open: http://localhost:5000
    echo.
) else (
    echo ❌ ERROR: %missing_count% critical files missing!
    echo.
    echo Please verify:
    echo   1. ZIP file extracted completely
    echo   2. No files were excluded
    echo   3. Enough disk space available (7 GB required)
    echo.
    echo Try re-extracting the ZIP file to a different location.
    echo.
)

echo ============================================================
echo   VERIFICATION COMPLETE
echo ============================================================
echo.
pause
