# TradeAdviser Desktop - Production Deployment Guide

## 📋 Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [System Requirements](#system-requirements)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Testing & Validation](#testing--validation)
6. [Troubleshooting](#troubleshooting)
7. [Post-Deployment](#post-deployment)
8. [Emergency Procedures](#emergency-procedures)

---

## Pre-Deployment Checklist

**Before deploying to production, ensure:**

- [ ] Version number updated in `pyproject.toml`
- [ ] All tests passing (`make test`)
- [ ] Code review completed
- [ ] Security audit completed
- [ ] Database backups created
- [ ] Rollback plan documented
- [ ] Team notified of maintenance window
- [ ] Monitoring configured and tested

---

## System Requirements

### Minimum Requirements
- **OS**: Windows 10 (Build 19041) or Windows 11 64-bit
- **RAM**: 4 GB
- **Disk Space**: 2 GB available
- **CPU**: Dual-core processor @ 2.0 GHz minimum
- **Internet**: Stable connection (10 Mbps recommended)

### Recommended Specifications
- **OS**: Windows 11 64-bit (latest patches)
- **RAM**: 16 GB
- **Disk Space**: 5 GB SSD
- **CPU**: Quad-core processor @ 2.5 GHz
- **Internet**: Fiber/Cable (50+ Mbps)

### Dependencies
- .NET Framework 4.8+ (for some integrations)
- Microsoft Visual C++ Redistributable 2022
- OpenSSL (installed with application)

---

## Installation Steps

### Step 1: Pre-Installation Checks

```powershell
# Run as Administrator
$systemRequirements = @{
    "Windows Version"   = [System.Environment]::OSVersion
    "RAM Available"     = (Get-WmiObject Win32_OperatingSystem).TotalVisibleMemorySize / 1GB
    "Disk Free Space"   = (Get-Volume C).SizeRemaining / 1GB
}

$systemRequirements | Format-Table
```

### Step 2: Download Application

```powershell
# Option 1: From GitHub Release
$releaseUrl = "https://github.com/nguemechieu/tradeadviser/releases/download/v1.0.0/TradeAdviser_1.0.0.exe"
Invoke-WebRequest -Uri $releaseUrl -OutFile "TradeAdviser_1.0.0.exe"

# Verify checksum
$downloaded = Get-FileHash "TradeAdviser_1.0.0.exe" -Algorithm SHA256
$expected = "YOUR_SHA256_HERE"

if ($downloaded.Hash -eq $expected) {
    Write-Host "✓ Checksum verification passed" -ForegroundColor Green
} else {
    throw "Checksum mismatch! File may be corrupted"
}

# Option 2: From Company Server
# Use your internal distribution method
```

### Step 3: Run Installer

```powershell
# Run installer with admin privileges
& ".\TradeAdviser_1.0.0.exe"

# Silent installation (for automation)
& ".\TradeAdviser_1.0.0.exe" /S /D="C:\Program Files\TradeAdviser"
```

### Step 4: Post-Installation Verification

```powershell
# Verify installation directory
$installPath = "C:\Program Files\TradeAdviser"
Get-ChildItem -Path $installPath -Recurse | Measure-Object | Select-Object -ExpandProperty Count

# Verify shortcuts created
$shortcuts = @{
    Desktop  = [System.Environment]::GetFolderPath("Desktop")
    StartMenu = [System.Environment]::GetFolderPath("StartMenu")
}

# Check registry entries
Get-ItemProperty -Path "HKLM:\Software\TradeAdviser" -ErrorAction SilentlyContinue
```

---

## Configuration

### Step 1: Set Up Environment Variables

Create `.env` file in installation directory:

```bash
# Copy template
Copy-Item "C:\Program Files\TradeAdviser\.env.example" "C:\Program Files\TradeAdviser\.env"

# Edit with secure values
notepad "C:\Program Files\TradeAdviser\.env"
```

### Step 2: Configure Brokers

#### Interactive Brokers

1. Install TWS (Trader Workstation)
2. Enable API access in TWS Settings:
   - Go to: Edit → Settings → API
   - Enable "Enable ActiveX and Socket Clients"
   - Socket Port: 7497 (live) or 7498 (paper)

3. Set in `.env`:
```
IBKR_ACCOUNT_ID=YOUR_ACCOUNT_ID
IBKR_TWS_PORT=7497
IBKR_API_PORT=7497
IBKR_PAPER_TRADING=false
```

#### Charles Schwab

1. Generate API credentials from Schwab Developer Portal
2. Set in `.env`:
```
SCHWAB_API_KEY=your_key
SCHWAB_API_SECRET=your_secret
SCHWAB_ACCOUNT_NUMBER=your_account
```

#### Other Brokers

Follow similar procedures for:
- Coinbase (Crypto)
- Binance (Crypto/Futures)
- Bybit (Derivatives)

### Step 3: Configure Database

If using local database:

```powershell
# Install PostgreSQL (if needed)
# https://www.postgresql.org/download/windows/

# Create database
psql -U postgres -c "CREATE DATABASE tradeadviser;"
psql -U postgres -c "CREATE USER tradeadviser WITH PASSWORD 'your_secure_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE tradeadviser TO tradeadviser;"
```

Or use cloud database:

```env
DB_HOST=your-cloud-db-host
DB_USER=your_username
DB_PASSWORD=your_secure_password
DB_NAME=tradeadviser
```

### Step 4: Enable Logging

Create logs directory:

```powershell
New-Item -ItemType Directory -Path "C:\Program Files\TradeAdviser\logs" -Force
New-Item -ItemType Directory -Path "$env:APPDATA\TradeAdviser\logs" -Force

# Set permissions (TradeAdviser app must write to logs)
icacls "C:\Program Files\TradeAdviser\logs" /grant:r "$env:USERNAME`:F"
```

---

## Testing & Validation

### Step 1: Basic Functionality Test

```powershell
# Launch application
& "C:\Program Files\TradeAdviser\TradeAdviser.exe"

# Verify:
# - Application starts without errors
# - UI renders correctly
# - No console errors in debug mode
```

### Step 2: Broker Connectivity Test

1. Open Settings → Brokers
2. Test connection for each configured broker
3. Verify credentials accepted
4. Check account information displays correctly

### Step 3: Data Feed Test

1. Go to Market Overview
2. Verify real-time quotes updating
3. Check multiple symbols
4. Verify no data gaps

### Step 4: Trading Test (Paper Trading)

1. Enable Paper Trading mode (default)
2. Place test trade
3. Verify trade appears in trades panel
4. Verify P&L calculation
5. Close trade and verify exit

### Step 5: Backup/Restore Test

```powershell
# Create backup
$backupPath = "C:\Backups\TradeAdviser_$(Get-Date -Format 'yyyyMMdd_HHmmss').bak"
New-Item -ItemType Directory -Path (Split-Path $backupPath) -Force

# Backup database and settings
# (Implementation depends on storage system)

# Test restore (non-production environment)
```

---

## Troubleshooting

### Common Issues

#### Application Won't Start

**Symptoms**: Application crashes immediately

**Solutions**:
```powershell
# Check .NET Framework
$netFramework = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP' -Recurse | 
    Get-ItemProperty -Name Version -EA 0 | 
    Where-Object {$_.PSChildName -match '^v[4-9]'} |
    Sort-Object Version -Descending | Select-Object -First 1

if ($netFramework.Version -lt "4.8") {
    Write-Host "⚠ .NET Framework 4.8+ required"
}

# Check Visual C++ Redistributable
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall' | 
    Where-Object {$_.GetValue('DisplayName') -match "Visual C"} |
    Select-Object -ExpandProperty PSChildName
```

#### Broker Connection Fails

**Symptoms**: "Cannot connect to broker" error

**Solutions**:
1. Verify .env configuration
2. Check broker service is running (TWS for IB)
3. Verify firewall allows outbound connections
4. Check API credentials are correct
5. Verify time is synchronized (crypto brokers are sensitive to time skew)

```powershell
# Verify connectivity to broker server
Test-NetConnection -ComputerName api.interactivebrokers.com -Port 7497
Test-NetConnection -ComputerName api.schwabapi.com -Port 443
```

#### Database Connection Fails

**Symptoms**: "Cannot connect to database" error

**Solutions**:
```powershell
# Test database connectivity
$testConnection = New-Object System.Data.SqlClient.SqlConnection
$testConnection.ConnectionString = "Server=YOUR_SERVER;Database=tradeadviser;Integrated Security=true"

try {
    $testConnection.Open()
    Write-Host "✓ Database connection successful"
    $testConnection.Close()
} catch {
    Write-Host "✗ Database connection failed: $_"
}
```

#### High Memory Usage

**Symptoms**: Application uses >50% RAM

**Solutions**:
1. Reduce market data symbols
2. Disable unnecessary features
3. Increase system RAM
4. Check for memory leaks in application logs

#### Slow Performance

**Symptoms**: UI lag, delayed updates

**Solutions**:
1. Verify system meets requirements
2. Check CPU and memory usage
3. Reduce screen refresh rate
4. Disable unnecessary panels
5. Check network connectivity

---

## Post-Deployment

### Step 1: Production Sign-Off

- [ ] All tests passed
- [ ] Performance acceptable
- [ ] No critical errors in logs
- [ ] User training completed
- [ ] Support team ready
- [ ] Escalation procedures defined

### Step 2: Monitoring Setup

```powershell
# Enable Windows event logging
$appPath = "C:\Program Files\TradeAdviser\TradeAdviser.exe"

# Create Windows event log source
New-EventLog -LogName Application -Source "TradeAdviser" -ErrorAction SilentlyContinue

# Verify
Get-EventLog -List | Where-Object {$_.Log -eq "Application"}
```

### Step 3: Automated Backup

```powershell
# Create scheduled task for daily backups
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00 AM"
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\backups\backup.ps1"
$settings = New-ScheduledTaskSettingsSet
Register-ScheduledTask -TaskName "TradeAdviser-DailyBackup" -Trigger $trigger -Action $action -Settings $settings
```

### Step 4: Documentation

Create post-deployment documentation:
- [ ] Actual system configuration
- [ ] Credentials storage location (secure!)
- [ ] Backup procedures
- [ ] Contact information for support
- [ ] Known issues and workarounds

---

## Emergency Procedures

### Immediate Stop (Emergency)

```powershell
# Force close application
Get-Process TradeAdviser -ErrorAction SilentlyContinue | Stop-Process -Force

# Or use Task Manager
# Ctrl+Shift+Esc → Find "TradeAdviser" → End Task
```

### Disable Trading (Emergency)

1. Open application Settings
2. Go to Risk Management
3. Set all position limits to 0
4. Disable all trading features

### Database Restore

```powershell
# Restore from backup
# Implementation depends on database system
# Typically: psql -U user -d db_name < backup.sql
```

### Rollback to Previous Version

```powershell
# Stop current version
Get-Process TradeAdviser -ErrorAction SilentlyContinue | Stop-Process -Force

# Restore from backup
$backupPath = "C:\Backups\TradeAdviser_previous.bak"
# Restore files from backup

# Restart
& "C:\Program Files\TradeAdviser\TradeAdviser.exe"
```

### Escalation Contacts

```
Level 1 Support:    support@tradeadviser.com
Level 2 Engineering: engineering@tradeadviser.com
Level 3 Emergency:   emergency@tradeadviser.com (24/7 hotline)
Management:         ops-manager@tradeadviser.com
```

---

## Support & Maintenance

### Regular Maintenance Tasks

**Daily**:
- Check application logs
- Verify broker connections
- Confirm backups completed

**Weekly**:
- Review error logs
- Check disk space
- Verify database integrity

**Monthly**:
- Update brokers & dependencies
- Security patches
- Performance review
- Capacity planning

### Version Updates

```powershell
# Check for updates
& "C:\Program Files\TradeAdviser\TradeAdviser.exe" --check-updates

# Install updates
# Application will download and install automatically
# Or install manually: .\TradeAdviser_1.0.1.exe

# Verify update
& "C:\Program Files\TradeAdviser\TradeAdviser.exe" --version
```

---

## Additional Resources

- **Documentation**: C:\Program Files\TradeAdviser\docs\
- **Configuration Template**: `.env.example`
- **Support Portal**: https://support.tradeadviser.com
- **GitHub Issues**: https://github.com/nguemechieu/tradeadviser/issues
- **Discord Community**: https://discord.gg/tradeadviser

---

**Last Updated**: 2024
**Version**: 1.0.0
**Status**: Production Ready
