# Production Build & Deployment Quick Reference

## 📋 Quick Commands

```bash
# Prepare environment
cp .env.example .env
# Edit .env with production values

# Install dependencies
make install-prod      # Production only
make install-dev       # Development (includes prod)

# Quality checks
make test              # Run tests
make lint              # Code linting
make security          # Security scan
make check-all         # All checks

# Production build
make production-check  # Pre-deployment validation
make build-production  # Build executable
make production-deploy # Deployment guidance
```

---

## 🚀 Production Deployment Workflow

### Phase 1: Pre-Deployment (1-2 days before)

```bash
# 1. Update version
# Edit pyproject.toml
version = "1.0.1"

# 2. Update changelog
# Create or update CHANGELOG.md

# 3. Run all checks
make check-all

# 4. Create backups
# Backup database and settings
```

### Phase 2: Build (Deployment day morning)

```powershell
# 1. Clean build
make clean

# 2. Install production dependencies
make install-prod

# 3. Run pre-deployment validation
make production-check

# 4. Build production executable
make build-production
# Output: dist/TradeAdviser.exe (100-150 MB)

# 5. Verify build
dir dist/TradeAdviser.exe
# Check file hash: dist/TradeAdviser.exe.sha256
```

### Phase 3: Testing (Deployment day afternoon)

```powershell
# 1. Deploy to staging/test machine
Copy-Item "dist/TradeAdviser.exe" "C:\Test\TradeAdviser.exe"

# 2. Run application
& "C:\Test\TradeAdviser.exe"

# 3. Manual smoke tests
# - Verify UI loads
# - Test broker connections
# - Check market data feed
# - Execute test trade (paper)
# - Verify logging

# 4. If tests fail, fix and rebuild
make build-production
```

### Phase 4: Production Deployment (Evening)

```powershell
# 1. Notify team of deployment window

# 2. Create final backup
# Database and settings backup

# 3. Deploy executable
# Stop application (if running)
# Copy dist/TradeAdviser.exe to production location
# C:\Program Files\TradeAdviser\TradeAdviser.exe

# 4. Start application
& "C:\Program Files\TradeAdviser\TradeAdviser.exe"

# 5. Verify production
# - Check logs for errors
# - Verify broker connections
# - Monitor for 24 hours
```

---

## 🔍 Pre-Deployment Checklist

- [ ] Version bumped in pyproject.toml
- [ ] Changelog updated
- [ ] All tests passing
- [ ] Code review completed
- [ ] Security audit passed
- [ ] Backup created
- [ ] .env file configured
- [ ] Team notified
- [ ] Rollback plan documented
- [ ] Build script tested

---

## 🛠️ Troubleshooting

### Build Fails

```powershell
# Check prerequisites
python --version  # Should be 3.10+
pip --version

# Check for errors
make production-check

# Clean and retry
make clean
make build-production
```

### Application Won't Start

```powershell
# Check logs
Get-Content logs/app.log -Tail 50

# Verify .env configuration
# Test broker connections
# Check database connectivity
```

### Performance Issues

```powershell
# Check system resources
Get-Process TradeAdviser | Select-Object CPU, Memory

# Reduce market data symbols
# Disable unnecessary features
# Check network connectivity
```

---

## 📊 Build Output

```
dist/
├── TradeAdviser.exe            # Main application (150 MB)
├── TradeAdviser.exe.sha256     # Checksum for verification
├── RELEASE_NOTES.md            # Release documentation
└── build/                      # Build artifacts (can delete)
    └── PyInstaller files...
```

---

## ✅ Verification Checklist

After successful build:

```bash
# 1. File exists
ls -la dist/TradeAdviser.exe

# 2. File size reasonable (100-200 MB)
file dist/TradeAdviser.exe

# 3. Checksum generated
cat dist/TradeAdviser.exe.sha256

# 4. Release notes created
cat RELEASE_NOTES.md

# 5. No build errors
# Review build output for warnings
```

---

## 📞 Support

| Issue | Solution |
|-------|----------|
| Python not found | Install Python 3.10+ |
| Dependencies fail | Run `make install-prod` again |
| PyInstaller error | Run `pip install --upgrade pyinstaller` |
| Build takes too long | This is normal (5-15 minutes) |
| Executable won't run | Check .env file exists and is configured |

---

## 🔐 Security Checklist

- [ ] .env file contains no hardcoded secrets
- [ ] API keys loaded from environment variables
- [ ] Database credentials secured
- [ ] SSL/TLS configured for remote connections
- [ ] Logging does not expose sensitive data
- [ ] Code signing enabled (optional)

---

## 📝 Version Management

```
Version Format: MAJOR.MINOR.PATCH

Examples:
1.0.0 - Initial release
1.0.1 - Hotfix
1.1.0 - New features
2.0.0 - Major overhaul

Update in:
- pyproject.toml (line 8)
- build-production.ps1 (line 50)
- .env (VERSION=...)
```

---

## 🎯 Release Checklist

**Before Release:**
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Version bumped
- [ ] Changelog created
- [ ] Build tested on staging

**During Release:**
- [ ] Build executable
- [ ] Verify checksum
- [ ] Sign if required
- [ ] Test on staging
- [ ] Deploy to production

**After Release:**
- [ ] Monitor logs 24h
- [ ] Confirm backups
- [ ] Document any issues
- [ ] Notify users

---

## 💾 File Locations

```
Windows:
- App: C:\Program Files\TradeAdviser\
- Config: C:\Program Files\TradeAdviser\.env
- Logs: C:\Program Files\TradeAdviser\logs\
- Backups: C:\Backups\TradeAdviser\
- User Data: %APPDATA%\TradeAdviser\

Linux:
- App: /opt/tradeadviser/
- Config: /opt/tradeadviser/.env
- Logs: /opt/tradeadviser/logs/
- Backups: /backup/tradeadviser/
- User Data: ~/.tradeadviser/
```

---

## 🔄 Rollback Procedure

If deployment fails:

```powershell
# 1. Stop application
Get-Process TradeAdviser | Stop-Process -Force

# 2. Restore from backup
Copy-Item "C:\Backups\TradeAdviser_backup.exe" `
          "C:\Program Files\TradeAdviser\TradeAdviser.exe" -Force

# 3. Restart application
& "C:\Program Files\TradeAdviser\TradeAdviser.exe"

# 4. Verify restoration
# Check logs for errors
# Confirm functionality

# 5. Investigate issue
# Review build logs
# Check for errors
# Fix and retry
```

---

**Last Updated**: 2024
**Status**: Production Ready
