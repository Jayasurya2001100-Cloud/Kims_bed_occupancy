@echo off
REM KIMS Bed Occupancy - Quick Start Script
REM This script helps you start the backend and frontend servers

echo.
echo ========================================
echo KIMS Bed Occupancy Forecasting System
echo ========================================
echo.

:menu
echo Choose an option:
echo.
echo [1] Train ML Models (Run this first!)
echo [2] Start Backend API (Port 8000)
echo [3] Start Frontend (Port 4200)
echo [4] Start Both (Backend + Frontend)
echo [5] View Setup Guide
echo [6] Check System Status
echo [0] Exit
echo.
set /p choice="Enter your choice: "

if "%choice%"=="1" goto train
if "%choice%"=="2" goto backend
if "%choice%"=="3" goto frontend
if "%choice%"=="4" goto both
if "%choice%"=="5" goto guide
if "%choice%"=="6" goto status
if "%choice%"=="0" goto end
goto menu

:train
echo.
echo ========================================
echo Training ML Models...
echo ========================================
echo.
echo Dataset: HSI-backend\data\hospital_enhanced_full_dataset.csv
echo Output: HSI-backend\output\
echo.
echo This may take 2-5 minutes...
echo.
cd HSI-backend
python ml_pipeline.py
if errorlevel 1 (
    echo.
    echo ERROR: Training failed!
    echo Check that Python and all dependencies are installed.
    echo Run: pip install -r requirements.txt
    pause
) else (
    echo.
    echo ========================================
    echo Training completed successfully!
    echo ========================================
    echo.
    echo Check the following files:
    echo - output\leaderboard.csv (model rankings)
    echo - output\best_model_*.pkl (saved model)
    echo - output\ward_*.png (forecast charts)
    echo.
    pause
)
cd ..
goto menu

:backend
echo.
echo ========================================
echo Starting Backend API Server...
echo ========================================
echo.
echo Server: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.
cd HSI-backend
python main.py
cd ..
goto menu

:frontend
echo.
echo ========================================
echo Starting Frontend Application...
echo ========================================
echo.
echo Server: http://localhost:4200
echo.
echo IMPORTANT: Make sure the backend is running first!
echo Backend should be at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.
cd HSI-frontend
call ng serve
cd ..
goto menu

:both
echo.
echo ========================================
echo Starting Backend and Frontend...
echo ========================================
echo.
echo Opening two command windows:
echo 1. Backend API (Port 8000)
echo 2. Frontend App (Port 4200)
echo.
echo Wait for both to start, then open:
echo http://localhost:4200
echo.

REM Start backend in new window
start "KIMS Backend API" cmd /k "cd HSI-backend && python main.py"

REM Wait a bit for backend to start
timeout /t 5 /nobreak >nul

REM Start frontend in new window
start "KIMS Frontend" cmd /k "cd HSI-frontend && ng serve"

echo.
echo Both servers are starting...
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:4200
echo.
echo Close the command windows to stop the servers.
echo.
pause
goto menu

:guide
echo.
echo ========================================
echo Opening Setup Guide...
echo ========================================
echo.
if exist SETUP_GUIDE.md (
    start SETUP_GUIDE.md
    echo Setup guide opened!
) else (
    echo ERROR: SETUP_GUIDE.md not found!
    echo Make sure you're in the project root directory.
)
echo.
pause
goto menu

:status
echo.
echo ========================================
echo System Status Check
echo ========================================
echo.

REM Check Python
echo Checking Python...
python --version 2>nul
if errorlevel 1 (
    echo [X] Python not found - Install Python 3.9 or higher
) else (
    echo [OK] Python installed
)

REM Check Node.js
echo.
echo Checking Node.js...
node --version 2>nul
if errorlevel 1 (
    echo [X] Node.js not found - Install Node.js 18 or higher
) else (
    echo [OK] Node.js installed
)

REM Check Angular CLI
echo.
echo Checking Angular CLI...
ng version 2>nul
if errorlevel 1 (
    echo [X] Angular CLI not found - Run: npm install -g @angular/cli
) else (
    echo [OK] Angular CLI installed
)

REM Check dataset
echo.
echo Checking dataset...
if exist "HSI-backend\data\hospital_enhanced_full_dataset.csv" (
    echo [OK] Dataset found
) else (
    echo [X] Dataset not found at HSI-backend\data\hospital_enhanced_full_dataset.csv
)

REM Check if backend packages are installed
echo.
echo Checking backend packages...
if exist "HSI-backend\venv\" (
    echo [OK] Virtual environment found
) else (
    echo [~] Virtual environment not found - consider creating one
)

REM Check if frontend packages are installed
echo.
echo Checking frontend packages...
if exist "HSI-frontend\node_modules\" (
    echo [OK] Node modules installed
) else (
    echo [X] Node modules not found - Run: npm install in HSI-frontend
)

REM Check if ports are available
echo.
echo Checking ports...
netstat -ano | findstr :8000 >nul
if errorlevel 1 (
    echo [OK] Port 8000 is available
) else (
    echo [~] Port 8000 is in use - Backend might already be running
)

netstat -ano | findstr :4200 >nul
if errorlevel 1 (
    echo [OK] Port 4200 is available
) else (
    echo [~] Port 4200 is in use - Frontend might already be running
)

echo.
echo ========================================
echo Status check complete!
echo ========================================
echo.
pause
goto menu

:end
echo.
echo Thank you for using KIMS Bed Occupancy Forecasting System!
echo.
exit /b

REM Quick reference:
REM This script is located in: C:\Users\Jayasurya\Downloads\kims_bed_occupancy\
REM 
REM To use this script:
REM 1. Double-click START.bat
REM 2. Choose option 1 to train models (first time only)
REM 3. Choose option 4 to start both servers
REM 4. Open http://localhost:4200 in your browser
