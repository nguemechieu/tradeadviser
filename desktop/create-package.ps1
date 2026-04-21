#Requires -Version 5.0
<#
.SYNOPSIS
    TradeAdviser Desktop - Complete Packaging Script
.DESCRIPTION
    Builds executable and creates installation packages
.EXAMPLE
    .\create-package.ps1 -Version 1.0.0
    .\create-package.ps1 -Version 1.0.0 -CreateNSIS -CreatePortable
    .\create-package.ps1 -Version 1.0.0 -CreateNSIS -Sign -CertPath "path/to/cert.pfx"
#>

param(
    [string]$Version = "1.0.0",
    [switch]$CreatePortable = $false,
    [switch]$CreateNSIS = $false,
    [switch]$CreateZip = $false,
    [switch]$Sign = $false,
    [string]$CertPath = "",
    [string]$CertPassword = ""
)

# Configuration
$ErrorActionPreference = "Stop"
$DesktopRoot = $PSScriptRoot
$DistDir = Join-Path $DesktopRoot "dist"
$PackageDir = Join-Path $DesktopRoot "packages"
$BuildDir = Join-Path $DesktopRoot "build"
$SourceDir = Join-Path $DesktopRoot "src"

# Colors
$Colors = @{
    Success = 'Green'
    Error   = 'Red'
    Info    = 'Cyan'
    Warning = 'Yellow'
    Gray    = 'Gray'
}

# ============================================================
# Helper Functions
# ============================================================

function Write-Header {
    param([string]$Text, [string]$Color = 'Cyan')
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor $Color
    Write-Host "  $Text" -ForegroundColor $Color
    Write-Host ("=" * 70) -ForegroundColor $Color
    Write-Host ""
}

function Write-Status {
    param([string]$Text, [string]$Icon = '>', [string]$Color = 'Gray')
    Write-Host "  $Icon  $Text" -ForegroundColor $Color
}

function Test-Prerequisites {
    Write-Header "Checking Prerequisites" $Colors.Info
    
    # Python
    Write-Status "Checking Python..." -Color $Colors.Info
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Python not found" -ForegroundColor Red
        exit 1
    }
    python --version
    
    # PyInstaller
    Write-Status "Checking PyInstaller..." -Color $Colors.Info
    try {
        python -m pip show pyinstaller > $null 2>&1
        Write-Status "PyInstaller: OK" -Icon "+" -Color $Colors.Success
    } catch {
        Write-Status "Installing PyInstaller..." -Icon "!" -Color $Colors.Warning
        python -m pip install pyinstaller
    }
    
    # NSIS (if creating installer)
    if ($CreateNSIS) {
        Write-Status "Checking NSIS..." -Color $Colors.Info
        $nsisPath = "C:\Program Files (x86)\NSIS\makensis.exe"
        if (-not (Test-Path $nsisPath)) {
            Write-Host "ERROR: NSIS not found. Install from https://nsis.sourceforge.io/" -ForegroundColor Red
            exit 1
        }
        Write-Status "NSIS: OK" -Icon "+" -Color $Colors.Success
    }
}

function Build-Executable {
    Write-Header "Building PyInstaller Executable" $Colors.Info
    
    Write-Status "Creating build directories..." -Color $Colors.Info
    Remove-Item $DistDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $DistDir | Out-Null
    
    # Create PyInstaller spec file
    $specFile = Join-Path $DesktopRoot "TradeAdviser-build.spec"
    $specContent = @"
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['src/main/main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/assets', 'assets'), ('src/config', 'config')],
    hiddenimports=['PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 
                   'aiohttp', 'websockets', 'pandas', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TradeAdviser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/assets/logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TradeAdviser'
)
"@
    
    Set-Content -Path $specFile -Value $specContent
    
    Write-Status "Running PyInstaller..." -Color $Colors.Info
    Push-Location $DesktopRoot
    try {
        python -m PyInstaller $specFile --distpath $DistDir --workpath $BuildDir --specpath "." --onefile --windowed
        
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed with exit code $LASTEXITCODE"
        }
        
        $exePath = Join-Path $DistDir "TradeAdviser.exe"
        if (-not (Test-Path $exePath)) {
            throw "Executable not found at $exePath"
        }
        
        Write-Status "Executable created successfully" -Icon "+" -Color $Colors.Success
        Write-Status "Size: $([math]::Round((Get-Item $exePath).Length / 1MB, 2)) MB" -Icon "i" -Color $Colors.Gray
    } finally {
        Pop-Location
    }
}

function Sign-Executable {
    if (-not $Sign) {
        Write-Status "Code signing skipped" -Icon "-" -Color $Colors.Gray
        return
    }
    
    Write-Header "Signing Executable" $Colors.Info
    
    $exePath = Join-Path $DistDir "TradeAdviser.exe"
    
    if (-not (Test-Path $CertPath)) {
        Write-Status "Certificate not found: $CertPath" -Icon "!" -Color $Colors.Warning
        return
    }
    
    # Windows SDK signtool
    $signtoolPath = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
    
    if (-not (Test-Path $signtoolPath)) {
        Write-Status "signtool not found (optional)" -Icon "-" -Color $Colors.Gray
        return
    }
    
    Write-Status "Signing executable..." -Color $Colors.Info
    & $signtoolPath sign /f $CertPath /p $CertPassword $exePath
    
    Write-Status "Executable signed successfully" -Icon "+" -Color $Colors.Success
}

function Create-PortablePackage {
    if (-not $CreatePortable -and -not $CreateZip) {
        return
    }
    
    Write-Header "Creating Portable Package" $Colors.Info
    
    New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
    
    $packageName = "TradeAdviser-v${Version}-portable"
    $zipPath = Join-Path $PackageDir "${packageName}.zip"
    $exePath = Join-Path $DistDir "TradeAdviser.exe"
    
    Write-Status "Compressing files..." -Color $Colors.Info
    
    Compress-Archive -Path $exePath -DestinationPath $zipPath -Force
    
    $sizeKB = [math]::Round((Get-Item $zipPath).Length / 1KB, 2)
    Write-Status "Package created: $zipPath" -Icon "+" -Color $Colors.Success
    Write-Status "Size: $sizeKB KB" -Icon "i" -Color $Colors.Gray
}

function Create-NSISInstaller {
    if (-not $CreateNSIS) {
        return
    }
    
    Write-Header "Creating NSIS Installer" $Colors.Info
    
    $nsisFile = Join-Path $DesktopRoot "tradeadviser-installer.nsi"
    $nsisPath = "C:\Program Files (x86)\NSIS\makensis.exe"
    
    if (-not (Test-Path $nsisFile)) {
        Write-Status "NSIS script not found: $nsisFile" -Icon "!" -Color $Colors.Warning
        return
    }
    
    Write-Status "Building NSIS installer..." -Color $Colors.Info
    Push-Location $DesktopRoot
    try {
        & $nsisPath $nsisFile
        
        $installerPath = Join-Path $DesktopRoot "TradeAdviser-v${Version}-installer.exe"
        if (Test-Path $installerPath) {
            Move-Item -Path $installerPath -Destination (Join-Path $PackageDir (Split-Path -Leaf $installerPath)) -Force
            $packagePath = Join-Path $PackageDir (Split-Path -Leaf $installerPath)
            
            $sizeMB = [math]::Round((Get-Item $packagePath).Length / 1MB, 2)
            Write-Status "Installer created successfully" -Icon "+" -Color $Colors.Success
            Write-Status "Path: $packagePath" -Icon "i" -Color $Colors.Gray
            Write-Status "Size: $sizeMB MB" -Icon "i" -Color $Colors.Gray
        }
    } finally {
        Pop-Location
    }
}

function Create-Checksums {
    Write-Header "Creating Checksums" $Colors.Info
    
    $checksumFile = Join-Path $PackageDir "SHA256SUMS.txt"
    $checksums = @()
    
    Get-ChildItem -Path $PackageDir -Filter "TradeAdviser-v*" | ForEach-Object {
        $hash = (Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash
        $checksums += "$hash  $($_.Name)"
        Write-Status "$($_.Name)" -Icon "H" -Color $Colors.Gray
        Write-Host "    $hash" -ForegroundColor DarkGray
    }
    
    Set-Content -Path $checksumFile -Value ($checksums -join "`n")
    Write-Status "Checksums saved to SHA256SUMS.txt" -Icon "+" -Color $Colors.Success
}

function Create-ReleaseNotes {
    Write-Header "Creating Release Notes" $Colors.Info
    
    $releaseFile = Join-Path $PackageDir "RELEASE-v${Version}.md"
    
    $releaseContent = @"
# TradeAdviser Desktop v$Version - Release

**Release Date**: $(Get-Date -Format 'MMMM dd, yyyy')

## Installation

### Windows Installer (.EXE)
- Double-click `TradeAdviser-v${Version}-installer.exe`
- Follow the installation wizard
- Desktop shortcut will be created automatically

### Portable Version (.ZIP)
- Extract `TradeAdviser-v${Version}-portable.zip` to any directory
- Run `TradeAdviser.exe`
- No installation required

## System Requirements

- **OS**: Windows 10/11 (64-bit)
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 500MB free space
- **Network**: Internet connection required for live trading

## What's New

- Desktop application is now production-ready
- Integrated quant analytics engine
- Real-time market data streaming
- Multi-broker support (IBKR, Schwab, Coinbase, etc.)
- Advanced risk management tools
- Performance reporting and analytics

## Getting Started

1. Launch the application
2. Log in or create an account
3. Connect your broker account
4. Configure risk management settings
5. Start trading or backtesting

## Support

- Documentation: https://tradeadviser.io/docs
- Issues: https://github.com/tradeadviser/issues
- Community: https://discord.gg/tradeadviser

## License

See LICENSE file included in the package.

---
**Checksum**: See SHA256SUMS.txt for integrity verification
"@
    
    Set-Content -Path $releaseFile -Value $releaseContent
    Write-Status "Release notes created" -Icon "+" -Color $Colors.Success
}

function Show-Summary {
    Write-Header "Build Complete" $Colors.Success
    
    Write-Host ""
    Write-Host "Package Summary:" -ForegroundColor Cyan
    Write-Host ""
    
    Get-ChildItem -Path $PackageDir -Filter "TradeAdviser-v*" | ForEach-Object {
        $sizeMB = [math]::Round($_.Length / 1MB, 2)
        Write-Host "  * $($_.Name) ($sizeMB MB)" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "Location: $PackageDir" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================
# Main Execution
# ============================================================

try {
    Write-Host ""
    Write-Header "TradeAdviser Desktop v$Version - Package Builder" $Colors.Info
    
    Test-Prerequisites
    Build-Executable
    Sign-Executable
    Create-PortablePackage
    Create-NSISInstaller
    Create-Checksums
    Create-ReleaseNotes
    Show-Summary
    
    Write-Status "All packages created successfully!" -Icon "+" -Color $Colors.Success
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    exit 1
}
