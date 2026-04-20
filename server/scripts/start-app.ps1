# TradeAdviser Application Startup Script
# Windows PowerShell Version
# Usage: .\scripts\start-app.ps1

param(
    [ValidateSet('dev', 'docker', 'full')]
    [string]$Mode = 'dev',
    
    [switch]$BuildFrontend = $false,
    [switch]$Help = $false
)

# Display help
if ($Help) {
    Write-Host @"
TradeAdviser Application Startup Script

USAGE:
    .\scripts\start-app.ps1 [OPTIONS]

OPTIONS:
    -Mode dev        Start in development mode (default)
                     - Backend: Uvicorn with auto-reload
                     - Frontend: Vite dev server
                     - Database: SQLite
    
    -Mode docker     Start with Docker Compose
                     - All services in containers
                     - PostgreSQL database
                     - Single command to start all
    
    -Mode full       Start all services (dev mode)
                     - Backend in one terminal window
                     - Frontend in another terminal window
    
    -BuildFrontend   Build frontend before starting backend
    
    -Help           Display this help message

EXAMPLES:
    # Start in development mode
    .\scripts\start-app.ps1 -Mode dev
    
    # Start with Docker
    .\scripts\start-app.ps1 -Mode docker
    
    # Start all services
    .\scripts\start-app.ps1 -Mode full
    
    # Build frontend first
    .\scripts\start-app.ps1 -BuildFrontend

URLS:
    Frontend:        http://localhost:5173 (Vite dev)
    Backend API:     http://localhost:8000
    API Docs:        http://localhost:8000/docs
    Docker:          http://localhost:8000 (frontend via backend)

REQUIREMENTS:
    - Python 3.10+
    - Node.js 18+
    - Docker & Docker Compose (for docker mode)

TROUBLESHOOTING:
    Port already in use:
        - Change port in configuration
        - Or: netstat -ano | findstr :8000
    
    Dependencies not found:
        - Ensure pip install -r requirements.txt is run
        - Ensure npm install is run

"@
    exit 0
}

# Colors for output
$InfoColor = "Cyan"
$SuccessColor = "Green"
$ErrorColor = "Red"
$WarningColor = "Yellow"

Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor $InfoColor
Write-Host "║       TradeAdviser Application Startup      ║" -ForegroundColor $InfoColor
Write-Host "║              Sopotek Inc (c) 2026          ║" -ForegroundColor $InfoColor
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor $InfoColor
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor $InfoColor
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python (\d+\.\d+)") {
    Write-Host "✓ Python $($matches[1]) found" -ForegroundColor $SuccessColor
} else {
    Write-Host "✗ Python 3.10+ not found" -ForegroundColor $ErrorColor
    exit 1
}

# Check Node.js
Write-Host "Checking Node.js..." -ForegroundColor $InfoColor
$nodeVersion = node --version 2>&1
if ($nodeVersion -match "v(\d+\.\d+)") {
    Write-Host "✓ Node.js $($matches[1]) found" -ForegroundColor $SuccessColor
} else {
    Write-Host "✗ Node.js 18+ not found" -ForegroundColor $ErrorColor
    exit 1
}

# Get project root
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Name "logs" | Out-Null
}

switch ($Mode) {
    'dev' {
        Write-Host ""
        Write-Host "Starting TradeAdviser in Development Mode..." -ForegroundColor $SuccessColor
        Write-Host ""
        
        # Build frontend if requested
        if ($BuildFrontend) {
            Write-Host "Building frontend..." -ForegroundColor $InfoColor
            Set-Location "$projectRoot\frontend"
            npm run build
            if ($LASTEXITCODE -ne 0) {
                Write-Host "✗ Frontend build failed" -ForegroundColor $ErrorColor
                exit 1
            }
            Write-Host "✓ Frontend build successful" -ForegroundColor $SuccessColor
            Set-Location $projectRoot
        }
        
        # Check and create virtual environment
        if (-not (Test-Path "backend\venv")) {
            Write-Host "Creating Python virtual environment..." -ForegroundColor $InfoColor
            Set-Location backend
            python -m venv venv
            & ".\venv\Scripts\Activate.ps1"
            pip install -r requirements.txt -q
            if ($LASTEXITCODE -ne 0) {
                Write-Host "✗ Failed to install backend dependencies" -ForegroundColor $ErrorColor
                exit 1
            }
            Write-Host "✓ Virtual environment created and dependencies installed" -ForegroundColor $SuccessColor
            Set-Location $projectRoot
        } else {
            Set-Location backend
            & ".\venv\Scripts\Activate.ps1"
            Set-Location $projectRoot
        }
        
        # Check frontend dependencies
        if (-not (Test-Path "frontend\node_modules")) {
            Write-Host "Installing frontend dependencies..." -ForegroundColor $InfoColor
            Set-Location frontend
            npm install -q
            if ($LASTEXITCODE -ne 0) {
                Write-Host "✗ Failed to install frontend dependencies" -ForegroundColor $ErrorColor
                exit 1
            }
            Write-Host "✓ Frontend dependencies installed" -ForegroundColor $SuccessColor
            Set-Location $projectRoot
        }
        
        # Copy env file if not exists
        if (-not (Test-Path ".env.local")) {
            Copy-Item ".env.example" ".env.local"
            Write-Host "✓ Created .env.local from template" -ForegroundColor $SuccessColor
        }
        
        Write-Host ""
        Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor $SuccessColor
        Write-Host "║  Development Mode - Single Terminal        ║" -ForegroundColor $SuccessColor
        Write-Host "║  Backend will serve both API and Frontend  ║" -ForegroundColor $SuccessColor
        Write-Host "╠════════════════════════════════════════════╣" -ForegroundColor $SuccessColor
        Write-Host "║ Frontend:   http://localhost:8000          ║" -ForegroundColor $SuccessColor
        Write-Host "║ Backend:    http://localhost:8000/api      ║" -ForegroundColor $SuccessColor
        Write-Host "║ API Docs:   http://localhost:8000/docs     ║" -ForegroundColor $SuccessColor
        Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor $SuccessColor
        Write-Host ""
        Write-Host "Starting backend (auto-reload enabled)..." -ForegroundColor $InfoColor
        Write-Host ""
        
        Set-Location backend
        & ".\venv\Scripts\Activate.ps1"
        python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
    }
    
    'docker' {
        Write-Host ""
        Write-Host "Starting TradeAdviser with Docker Compose..." -ForegroundColor $SuccessColor
        Write-Host ""
        
        # Check Docker
        $docker = Get-Command docker -ErrorAction SilentlyContinue
        if (-not $docker) {
            Write-Host "✗ Docker not found" -ForegroundColor $ErrorColor
            Write-Host "  Please install Docker from https://www.docker.com/products/docker-desktop" -ForegroundColor $WarningColor
            exit 1
        }
        Write-Host "✓ Docker found" -ForegroundColor $SuccessColor
        
        # Copy env file if not exists
        if (-not (Test-Path ".env.local")) {
            Copy-Item ".env.example" ".env.local"
            Write-Host "✓ Created .env.local from template" -ForegroundColor $SuccessColor
        }
        
        Write-Host ""
        Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor $SuccessColor
        Write-Host "║  Docker Compose Mode                       ║" -ForegroundColor $SuccessColor
        Write-Host "╠════════════════════════════════════════════╣" -ForegroundColor $SuccessColor
        Write-Host "║ Frontend:   http://localhost:8000          ║" -ForegroundColor $SuccessColor
        Write-Host "║ Backend:    http://localhost:8000/api      ║" -ForegroundColor $SuccessColor
        Write-Host "║ Database:   localhost:5432                 ║" -ForegroundColor $SuccessColor
        Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor $SuccessColor
        Write-Host ""
        
        docker-compose up --build
    }
    
    'full' {
        Write-Host ""
        Write-Host "Starting TradeAdviser in Full Mode (Multiple Windows)..." -ForegroundColor $SuccessColor
        Write-Host ""
        Write-Host "This will open separate terminal windows for:" -ForegroundColor $InfoColor
        Write-Host "  1. Backend (FastAPI)"
        Write-Host "  2. Frontend (Vite dev server)"
        Write-Host ""
        
        # Build frontend if requested
        if ($BuildFrontend) {
            Write-Host "Building frontend..." -ForegroundColor $InfoColor
            Set-Location "$projectRoot\frontend"
            npm run build
            if ($LASTEXITCODE -ne 0) {
                Write-Host "✗ Frontend build failed" -ForegroundColor $ErrorColor
                exit 1
            }
            Write-Host "✓ Frontend build successful" -ForegroundColor $SuccessColor
            Set-Location $projectRoot
        }
        
        # Setup backend if needed
        if (-not (Test-Path "backend\venv")) {
            Write-Host "Setting up backend..." -ForegroundColor $InfoColor
            Set-Location backend
            python -m venv venv
            & ".\venv\Scripts\Activate.ps1"
            pip install -r requirements.txt -q
            Set-Location $projectRoot
        }
        
        # Setup frontend if needed
        if (-not (Test-Path "frontend\node_modules")) {
            Write-Host "Setting up frontend..." -ForegroundColor $InfoColor
            Set-Location frontend
            npm install -q
            Set-Location $projectRoot
        }
        
        # Copy env file if not exists
        if (-not (Test-Path ".env.local")) {
            Copy-Item ".env.example" ".env.local"
        }
        
        Write-Host ""
        Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor $SuccessColor
        Write-Host "║  Full Mode - Separate Terminal Windows     ║" -ForegroundColor $SuccessColor
        Write-Host "╠════════════════════════════════════════════╣" -ForegroundColor $SuccessColor
        Write-Host "║ Frontend:   http://localhost:5173          ║" -ForegroundColor $SuccessColor
        Write-Host "║ Backend:    http://localhost:8000          ║" -ForegroundColor $SuccessColor
        Write-Host "║ API Docs:   http://localhost:8000/docs     ║" -ForegroundColor $SuccessColor
        Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor $SuccessColor
        Write-Host ""
        
        # Start backend in new window
        $backendCmd = @"
        `$projectRoot = '$projectRoot'
        Set-Location "`$projectRoot\backend"
        & ".\venv\Scripts\Activate.ps1"
        Write-Host "Starting TradeAdviser Backend..." -ForegroundColor Green
        python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
"@
        Start-Process powershell -ArgumentList "-NoExit -Command $backendCmd" -WindowStyle Normal
        
        Start-Sleep -Seconds 3
        
        # Start frontend in new window
        $frontendCmd = @"
        `$projectRoot = '$projectRoot'
        Set-Location "`$projectRoot\frontend"
        Write-Host "Starting TradeAdviser Frontend..." -ForegroundColor Green
        npm run dev
"@
        Start-Process powershell -ArgumentList "-NoExit -Command $frontendCmd" -WindowStyle Normal
        
        Write-Host ""
        Write-Host "✓ Backend and Frontend servers launched in separate windows" -ForegroundColor $SuccessColor
        Write-Host "  Close the terminal windows to stop the servers" -ForegroundColor $InfoColor
        Write-Host ""
    }
}

exit 0
