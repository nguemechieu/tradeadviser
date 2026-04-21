#Requires -Version 5.0
<#
.SYNOPSIS
    TradeAdviser Desktop Application Launcher
.DESCRIPTION
    Start the desktop application with environment setup and error handling
.EXAMPLE
    .\LAUNCH_DESKTOP.ps1
    .\LAUNCH_DESKTOP.ps1 -Mode Dev
    .\LAUNCH_DESKTOP.ps1 -Mode Test
#>

param(
    [ValidateSet('Dev', 'Test', 'Docker', 'Interactive')]
    [string]$Mode = 'Interactive',
    [switch]$NoVenv
)

# Configuration - use PSScriptRoot for reliable path resolution
$DesktopRoot = $PSScriptRoot
$RepoRoot = Split-Path -Parent $DesktopRoot
$VenvPath = Join-Path $DesktopRoot ".venv"
$VenvActivate = Join-Path $VenvPath "Scripts\activate.ps1"
$LogDir = Join-Path $DesktopRoot "logs"
$MainScript = Join-Path $DesktopRoot "main.py"

# Colors
$Colors = @{
    Success = 'Green'
    Error   = 'Red'
    Info    = 'Cyan'
    Warning = 'Yellow'
}

function Write-Header {
    param([string]$Text, [string]$Color = 'Cyan')
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor $Color
    Write-Host "  $Text" -ForegroundColor $Color
    Write-Host ("=" * 60) -ForegroundColor $Color
    Write-Host ""
}

function Write-Status {
    param([string]$Text, [string]$Icon = '>', [string]$Color = 'Gray')
    Write-Host "  $Icon  $Text" -ForegroundColor $Color
}

function Test-VenvExists {
    if (-not (Test-Path $VenvActivate)) {
        Write-Host "ERROR: Virtual environment not found at $VenvPath" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please create virtual environment first:" -ForegroundColor Yellow
        Write-Host "  cd $DesktopRoot" -ForegroundColor Gray
        Write-Host "  python -m venv .venv" -ForegroundColor Gray
        Write-Host "  .\.venv\Scripts\activate" -ForegroundColor Gray
        Write-Host "  pip install -r requirements.txt" -ForegroundColor Gray
        Write-Host ""
        exit 1
    }
}

function Test-Dependencies {
    Write-Status "Checking dependencies..." -Color Cyan
    
    $missingDeps = @()
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Status "Python: $pythonVersion" -Icon "OK" -Color Green
    } catch {
        $missingDeps += "Python"
    }
    
    # Check pip packages using Python import instead of file system check
    $packagesToCheck = @("PySide6", "pyqtgraph", "qasync", "pandas")
    foreach ($package in $packagesToCheck) {
        try {
            $importName = $package -replace "-", "_"
            python -c "import $importName" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $statusMsg = $package + ": Installed"
                Write-Status $statusMsg -Icon "OK" -Color Green
            } else {
                $missingDeps += $package
            }
        } catch {
            $missingDeps += $package
        }
    }
    
    if ($missingDeps.Count -gt 0) {
        Write-Host ""
        Write-Host ("Missing dependencies: " + ($missingDeps -join ", ")) -ForegroundColor Red
        Write-Host "Run: pip install -r requirements.txt" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host ""
}

function Launch-Dev {
    Write-Header "TradeAdviser Desktop - Development Mode" "Cyan"
    
    if (-not $NoVenv) {
        Test-VenvExists
        Write-Status "Activating virtual environment..." -Color Cyan
        & $VenvActivate
    }
    
    Test-Dependencies
    
    Write-Status "Starting desktop application..." -Icon ">" -Color Green
    Write-Host ""
    
    # Create logs directory
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    
    # Run the app
    & python $MainScript
}

function Launch-Test {
    Write-Header "TradeAdviser Desktop - Test Mode" "Cyan"
    
    if (-not $NoVenv) {
        Test-VenvExists
        Write-Status "Activating virtual environment..." -Color Cyan
        & $VenvActivate
    }
    
    Test-Dependencies
    
    Write-Status "Running tests..." -Icon ">" -Color Green
    Write-Host ""
    
    & pytest -v --cov=src --cov-report=html
    
    Write-Host ""
    Write-Status "Test report: htmlcov/index.html" -Icon "=" -Color Cyan
}

function Launch-Docker {
    Write-Header "TradeAdviser Desktop - Docker Mode" "Green"
    
    Write-Status "Building and starting Docker containers..." -Icon ">" -Color Green
    
    Push-Location $DesktopRoot
    try {
        docker-compose up -d --build
        
        Write-Host ""
        Write-Status "Containers started!" -Icon "+" -Color Green
        Write-Status "Web UI: http://localhost:6080" -Icon "*" -Color Cyan
        
        Write-Host ""
        Write-Status "Available commands:" -Color Yellow
        Write-Status "make docker-logs    - View logs" -Color Gray
        Write-Status "make docker-down    - Stop containers" -Color Gray
        Write-Status "make docker-ps      - List containers" -Color Gray
    } finally {
        Pop-Location
    }
}

function Show-Interactive-Menu {
    Write-Header "TradeAdviser Desktop Application Launcher" "Cyan"
    
    Write-Host "Select launch mode:`n" -ForegroundColor White
    Write-Host "  [1]  Development    (Local PyQt application)" -ForegroundColor Green
    Write-Host "  [2]  Test           (Run pytest suite)" -ForegroundColor Blue
    Write-Host "  [3]  Docker         (Containerized with noVNC)" -ForegroundColor Yellow
    Write-Host "  [4]  Setup          (Create/update virtual environment)" -ForegroundColor Cyan
    Write-Host "  [0]  Exit" -ForegroundColor Red
    Write-Host ""
    
    $selection = Read-Host "Enter selection (0-4)"
    return $selection
}

function Show-Setup-Menu {
    Write-Header "Virtual Environment Setup" "Cyan"
    
    Write-Status "Creating virtual environment..." -Color Cyan
    Write-Host ""
    
    # Create venv
    python -m venv $VenvPath
    
    if (Test-Path $VenvActivate) {
        Write-Status "Virtual environment created" -Icon "+" -Color Green
        
        # Activate and install
        Write-Host ""
        Write-Status "Activating and installing dependencies..." -Color Cyan
        & $VenvActivate
        
        Write-Host ""
        pip install --upgrade pip setuptools wheel
        pip install -r (Join-Path $DesktopRoot "requirements.txt")
        
        Write-Host ""
        Write-Status "Setup complete!" -Icon "+" -Color Green
        Write-Status "Next: Run .\LAUNCH_DESKTOP.ps1 to start the app" -Color Cyan
    } else {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Main execution
switch ($Mode) {
    'Dev' { Launch-Dev }
    'Test' { Launch-Test }
    'Docker' { Launch-Docker }
    'Interactive' {
        $selection = Show-Interactive-Menu
        switch ($selection) {
            '1' { Launch-Dev }
            '2' { Launch-Test }
            '3' { Launch-Docker }
            '4' { Show-Setup-Menu }
            '0' { Write-Host "Exiting..." -ForegroundColor Yellow; exit }
            default { Write-Host "Invalid selection. Exiting." -ForegroundColor Red; exit 1 }
        }
    }
    default {
        Write-Host "Invalid mode. Use: Dev, Test, Docker, or Interactive" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
