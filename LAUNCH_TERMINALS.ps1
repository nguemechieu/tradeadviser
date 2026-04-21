#Requires -Version 5.0
<#
.SYNOPSIS
    TradeAdviser Unified Development Launcher
.DESCRIPTION
    Opens organized terminal windows for development with clear layout and quick commands
.EXAMPLE
    .\LAUNCH_TERMINALS.ps1
#>

param(
    [ValidateSet('Full', 'Backend', 'Frontend', 'Desktop', 'Custom', 'Interactive')]
    [string]$Mode = 'Interactive'
)

# Configuration
$RootPath = Split-Path -Parent $MyInvocation.MyCommandPath
$BackendPath = Join-Path $RootPath "server"
$FrontendPath = Join-Path $BackendPath "app" "frontend"
$DesktopPath = Join-Path $RootPath "desktop"

# Color scheme
$Colors = @{
    Backend   = 'Cyan'
    Frontend  = 'Green'
    Desktop   = 'Yellow'
    Server    = 'Blue'
    Error     = 'Red'
}

function Write-Header {
    param([string]$Text, [string]$Color = 'Cyan')
    Write-Host "`n" 
    Write-Host ("=" * 60) -ForegroundColor $Color
    Write-Host "  $Text" -ForegroundColor $Color
    Write-Host ("=" * 60) -ForegroundColor $Color
    Write-Host ""
}

function Write-Status {
    param([string]$Text, [string]$Icon = '->', [string]$Color = 'Gray')
    Write-Host "  $Icon  $Text" -ForegroundColor $Color
}

function Open-Terminal {
    param(
        [string]$Title,
        [string]$Path,
        [string]$Command,
        [string]$Color
    )
    
    Write-Status "Opening: $Title..." -Icon ">" -Color $Color
    
    $profileCmd = @"
`$Host.UI.RawUI.WindowTitle = "$Title"
cd "$Path"
Clear-Host
Write-Host "========================================================" -ForegroundColor $Color
Write-Host "  $Title" -ForegroundColor $Color
Write-Host "========================================================" -ForegroundColor $Color
Write-Host ""
$Command
"@
    
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", $profileCmd
    )
}

function Show-Interactive-Menu {
    Write-Header "TradeAdviser - Development Launcher" "Cyan"
    
    Write-Host "Select terminal configuration to launch:" -ForegroundColor White
    Write-Host ""
    Write-Host "  [1]  Full Stack    (Backend + Frontend + Desktop)" -ForegroundColor Cyan
    Write-Host "  [2]  Backend Only  (Server + Docker)" -ForegroundColor Green
    Write-Host "  [3]  Frontend Only (React Web UI)" -ForegroundColor Yellow
    Write-Host "  [4]  Desktop Only  (PyQt Application)" -ForegroundColor Magenta
    Write-Host "  [5]  Minimal       (Backend + Frontend)" -ForegroundColor Blue
    Write-Host "  [6]  Custom        (Select individual components)" -ForegroundColor DarkCyan
    Write-Host "  [0]  Exit" -ForegroundColor Red
    Write-Host ""
    
    $selection = Read-Host "Enter selection (0-6)"
    return $selection
}

function Launch-Full-Stack {
    Write-Header "Launching Full Stack Development Environment" "Cyan"
    
    $backendCmd = @"
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  make docker-up       - Start Docker services" -ForegroundColor Gray
Write-Host "  make docker-down     - Stop Docker services" -ForegroundColor Gray
Write-Host "  make docker-logs     - View Docker logs" -ForegroundColor Gray
Write-Host "  make lint            - Run linter" -ForegroundColor Gray
Write-Host "  make test            - Run tests" -ForegroundColor Gray
Write-Host "  make security        - Security scan" -ForegroundColor Gray
Write-Host ""
Write-Host "Quick start:" -ForegroundColor Cyan
Write-Host "  make docker-up" -ForegroundColor Green
"@
    
    $frontendCmd = @"
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  npm install          - Install dependencies" -ForegroundColor Gray
Write-Host "  npm run dev          - Development server (port 5173)" -ForegroundColor Gray
Write-Host "  npm run build        - Production build" -ForegroundColor Gray
Write-Host ""
Write-Host "Quick start:" -ForegroundColor Cyan
Write-Host "  npm install && npm run dev" -ForegroundColor Green
"@
    
    $desktopCmd = @"
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\activate    - Activate environment" -ForegroundColor Gray
Write-Host "  python main.py              - Run application" -ForegroundColor Gray
Write-Host "  pytest                      - Run tests" -ForegroundColor Gray
Write-Host ""
Write-Host "Quick start:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\activate.ps1" -ForegroundColor Green
Write-Host "  python main.py" -ForegroundColor Green
"@
    
    Open-Terminal "Backend Server" $BackendPath $backendCmd "Cyan"
    Start-Sleep -Milliseconds 500
    
    Open-Terminal "Frontend UI" $FrontendPath $frontendCmd "Green"
    Start-Sleep -Milliseconds 500
    
    Open-Terminal "Desktop App" $DesktopPath $desktopCmd "Yellow"
    
    Show-Launch-Summary
}

function Launch-Backend-Only {
    Write-Header "Launching Backend Services" "Cyan"
    
    $cmd = @"
Write-Host "Docker & API Server" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  make docker-up       - Start all services" -ForegroundColor Gray
Write-Host "  make docker-down     - Stop all services" -ForegroundColor Gray
Write-Host "  make docker-logs     - View logs in real-time" -ForegroundColor Gray
Write-Host "  make docker-ps       - Show running containers" -ForegroundColor Gray
Write-Host ""
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
"@
    
    Open-Terminal "Backend Server" $BackendPath $cmd "Cyan"
    Show-Launch-Summary
}

function Launch-Frontend-Only {
    Write-Header "Launching Frontend Services" "Green"
    
    $cmd = @"
Write-Host "React Development Server" -ForegroundColor Green
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  npm install          - Install dependencies" -ForegroundColor Gray
Write-Host "  npm run dev          - Start dev server (http://localhost:5173)" -ForegroundColor Gray
Write-Host "  npm run build        - Production build" -ForegroundColor Gray
Write-Host ""
Write-Host "Development URL: http://localhost:5173" -ForegroundColor Green
"@
    
    Open-Terminal "Frontend UI" $FrontendPath $cmd "Green"
    Show-Launch-Summary
}

function Launch-Desktop-Only {
    Write-Header "Launching Desktop Application" "Yellow"
    
    $cmd = @"
Write-Host "TradeAdviser Desktop Application" -ForegroundColor Yellow
Write-Host ""
Write-Host "Setup:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\activate.ps1  - Activate virtual environment" -ForegroundColor Gray
Write-Host ""
Write-Host "Run:" -ForegroundColor Green
Write-Host "  python main.py" -ForegroundColor Green
"@
    
    Open-Terminal "Desktop App" $DesktopPath $cmd "Yellow"
    Show-Launch-Summary
}

function Show-Launch-Summary {
    Write-Host ""
    Write-Header "Terminals Launched" "Green"
    
    Write-Host "Service URLs:" -ForegroundColor Yellow
    Write-Status "API Server:        http://localhost:8000" -Color "Gray"
    Write-Status "API Documentation: http://localhost:8000/docs" -Color "Gray"
    Write-Status "Frontend:          http://localhost:5173" -Color "Gray"
    Write-Status "Desktop App:       Starting..." -Color "Gray"
    Write-Host ""
    
    Write-Host "Tips:" -ForegroundColor Yellow
    Write-Status "Keep all terminals open during development" -Color "Gray"
    Write-Status "Use Ctrl+C to gracefully stop any service" -Color "Gray"
    Write-Status "Check terminal logs for errors or issues" -Color "Gray"
    Write-Host ""
}

# Main execution
switch ($Mode) {
    'Full' { Launch-Full-Stack }
    'Backend' { Launch-Backend-Only }
    'Frontend' { Launch-Frontend-Only }
    'Desktop' { Launch-Desktop-Only }
    'Interactive' {
        $selection = Show-Interactive-Menu
        switch ($selection) {
            '1' { Launch-Full-Stack }
            '2' { Launch-Backend-Only }
            '3' { Launch-Frontend-Only }
            '4' { Launch-Desktop-Only }
            '5' { Launch-Backend-Only; Start-Sleep 1; Launch-Frontend-Only; Show-Launch-Summary }
            '6' { Write-Host "Custom mode - launching individual terminals..." -ForegroundColor Yellow }
            '0' { Write-Host "Exiting..." -ForegroundColor Yellow; exit }
            default { Write-Host "Invalid selection. Exiting." -ForegroundColor Red; exit 1 }
        }
    }
    default {
        Write-Host "Invalid mode. Use: Full, Backend, Frontend, Desktop, Custom, or Interactive" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
