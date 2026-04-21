@echo off
REM =========================================================
REM TradeAdviser Multi-Terminal Launcher
REM =========================================================
REM This script launches organized terminal windows for:
REM   - Server Backend (Docker/API)
REM   - Frontend Web UI  
REM   - Desktop Application
REM   - Development Tools
REM =========================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Color codes for console output
for /F %%a in ('echo prompt $H ^| cmd') do set "BS=%%a"

echo.
echo ============================================================
echo    TradeAdviser - Multi-Terminal Development Launcher
echo ============================================================
echo.

REM Ask user which terminals to launch
echo Select terminal windows to launch:
echo [1] Full Stack (All terminals)
echo [2] Backend Only (Server + Docker)
echo [3] Frontend Only (Web UI)
echo [4] Desktop Only
echo [5] Custom Selection
echo [6] Exit
echo.

set /p choice="Enter selection (1-6): "

if "%choice%"=="6" goto end
if "%choice%"=="5" goto custom
if "%choice%"=="4" goto desktop_only
if "%choice%"=="3" goto frontend_only
if "%choice%"=="2" goto backend_only
if "%choice%"=="1" goto full_stack

echo Invalid choice. Exiting.
timeout /t 2 >nul
goto end

:full_stack
echo.
echo Launching Full Stack...
echo.
call :launch_backend
call :launch_frontend
call :launch_desktop
call :launch_logs
goto stack_complete

:backend_only
echo.
echo Launching Backend Only...
echo.
call :launch_backend
goto stack_complete

:frontend_only
echo.
echo Launching Frontend Only...
echo.
call :launch_frontend
goto stack_complete

:desktop_only
echo.
echo Launching Desktop Only...
echo.
call :launch_desktop
goto stack_complete

:custom
echo.
echo Custom Selection:
echo [1] Backend (Docker + API)
echo [2] Frontend (React Web UI)
echo [3] Desktop (PyQt Application)
echo [4] Logs Viewer
echo.
set /p backend="Launch Backend? (y/n): "
set /p frontend="Launch Frontend? (y/n): "
set /p desktop="Launch Desktop? (y/n): "
set /p logs="Launch Logs Viewer? (y/n): "

if /i "%backend%"=="y" call :launch_backend
if /i "%frontend%"=="y" call :launch_frontend
if /i "%desktop%"=="y" call :launch_desktop
if /i "%logs%"=="y" call :launch_logs
goto stack_complete

:launch_backend
echo [Backend] Starting Docker + API Server...
start "TradeAdviser - Backend Server" cmd /k "cd /d "%CD%\server" && powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '🚀 Backend - Docker Compose' -ForegroundColor Cyan; Write-Host 'Available commands:' -ForegroundColor Yellow; Write-Host '  make docker-up      - Start services' -ForegroundColor Gray; Write-Host '  make docker-down    - Stop services' -ForegroundColor Gray; Write-Host '  make docker-logs    - View logs' -ForegroundColor Gray; Write-Host '  make test           - Run tests' -ForegroundColor Gray; Write-Host '  make lint           - Lint code' -ForegroundColor Gray; Write-Host ''; cmd.exe""
timeout /t 2 >nul
goto :eof

:launch_frontend
echo [Frontend] Starting Web UI...
start "TradeAdviser - Frontend UI" cmd /k "cd /d "%CD%\server\app\frontend" && powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '⚛️  Frontend - React Development Server' -ForegroundColor Cyan; Write-Host 'Available commands:' -ForegroundColor Yellow; Write-Host '  npm run dev         - Start dev server (port 5173)' -ForegroundColor Gray; Write-Host '  npm run build       - Production build' -ForegroundColor Gray; Write-Host '  npm install         - Install dependencies' -ForegroundColor Gray; Write-Host ''; npm run dev""
timeout /t 2 >nul
goto :eof

:launch_desktop
echo [Desktop] Starting PyQt Application...
start "TradeAdviser - Desktop App" cmd /k "cd /d "%CD%\desktop" && powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '🖥️  Desktop Application' -ForegroundColor Cyan; Write-Host 'Available commands:' -ForegroundColor Yellow; Write-Host '  .\.venv\Scripts\activate  - Activate virtual environment' -ForegroundColor Gray; Write-Host '  python main.py             - Run app' -ForegroundColor Gray; Write-Host '  pytest                     - Run tests' -ForegroundColor Gray; Write-Host ''; .\.venv\Scripts\activate.ps1; cmd.exe""
timeout /t 2 >nul
goto :eof

:launch_logs
echo [Logs] Starting Log Viewer...
start "TradeAdviser - Logs Viewer" cmd /k "cd /d "%CD%" && powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '📋 Log Files' -ForegroundColor Cyan; Write-Host ''; Write-Host 'Recent Logs:' -ForegroundColor Yellow; Get-ChildItem -Path '.\server\logs', '.\desktop\logs', '.\desktop\output\logs' -Recurse -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object { Write-Host ('  ' + $_.FullName) -ForegroundColor Gray }; Write-Host ''; cmd.exe""
timeout /t 2 >nul
goto :eof

:stack_complete
echo.
echo ============================================================
echo    %
echo ============================================================
echo.
echo All selected terminals have been launched!
echo.
echo Terminal Windows Summary:
echo   - Backend Server:      http://localhost:8000
echo   - Frontend Web UI:      http://localhost:5173
echo   - API Docs:           http://localhost:8000/docs
echo.
echo Tips:
echo   - Keep all terminals open during development
echo   - Check logs for errors if services fail to start
echo   - Use Ctrl+C to stop any service gracefully
echo.
timeout /t 5 >nul
goto end

:end
exit /b 0
