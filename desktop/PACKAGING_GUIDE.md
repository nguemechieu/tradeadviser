# TradeAdviser Desktop - Installation Package Guide

## Overview

This guide explains how to create installation packages for TradeAdviser Desktop in different formats:

- **Portable ZIP** - Self-contained executable, no installation needed
- **Windows Installer (.EXE)** - Professional installer using NSIS
- **Standalone Executable** - Single EXE file with all dependencies

---

## Quick Start

### Build Portable Package (Fastest)

```powershell
cd c:\Users\nguem\Documents\GitHub\tradeadviser\desktop
.\create-package.ps1 -Version 1.0.0 -CreatePortable
```

This creates: `TradeAdviser-v1.0.0-portable.zip`

---

## Complete Packaging Workflow

### Step 1: Install Prerequisites

**NSIS (for Windows Installer)** - Optional
```powershell
# Download and install from: https://nsis.sourceforge.io/download
# Or use Chocolatey:
choco install nsis
```

**PyInstaller** (automatically installed if missing)
```powershell
pip install pyinstaller
```

### Step 2: Create All Packages

```powershell
cd c:\Users\nguem\Documents\GitHub\tradeadviser\desktop

# Create all package types
.\create-package.ps1 -Version 1.0.0 -CreatePortable -CreateNSIS

# Output:
# packages/
#   ├── TradeAdviser-v1.0.0-portable.zip
#   ├── TradeAdviser-v1.0.0-installer.exe
#   ├── SHA256SUMS.txt
#   └── RELEASE-v1.0.0.md
```

### Step 3: (Optional) Sign the Executable

If you have a code signing certificate:

```powershell
.\create-package.ps1 -Version 1.0.0 -CreatePortable -Sign `
  -CertPath "path/to/certificate.pfx" `
  -CertPassword "your-password"
```

---

## Package Types Explained

### 1. Portable ZIP Package

**Use Case**: End users who want a quick download without installation

```powershell
.\create-package.ps1 -Version 1.0.0 -CreatePortable
```

**Output**: `TradeAdviser-v1.0.0-portable.zip` (~400-500 MB)

**Installation**:
```
1. Extract ZIP to desired location
2. Run TradeAdviser.exe
3. Done!
```

**Pros**: No admin rights needed, portable across USB drives
**Cons**: Larger file size

---

### 2. Windows Installer (.EXE)

**Use Case**: Professional distribution, creates Start Menu shortcuts

**Requirements**: NSIS installed

```powershell
choco install nsis
.\create-package.ps1 -Version 1.0.0 -CreateNSIS
```

**Output**: `TradeAdviser-v1.0.0-installer.exe` (~300-400 MB)

**Installation**:
```
1. Run installer executable
2. Follow wizard
3. Choose installation location
4. Application installed to C:\Program Files\TradeAdviser
5. Start Menu shortcuts created
6. Desktop shortcut created
```

**Pros**: Professional look, registry entries, uninstaller, shortcuts
**Cons**: Requires admin rights

**Customize**: Edit `tradeadviser-installer.nsi` file:
- Change company name
- Modify install location
- Add custom shortcuts
- Add files/folders to include

---

### 3. Standalone Executable (One-File)

**Use Case**: Maximum simplicity, everything in one EXE

```powershell
.\create-package.ps1 -Version 1.0.0
```

**Output**: `dist/TradeAdviser.exe` (~450+ MB)

**Pros**: Single file, easy to distribute
**Cons**: Slower startup, larger file

---

## Build Script Usage

```powershell
# Syntax
.\create-package.ps1 -Version <version> [options]

# Options
-Version "1.0.0"          # Version number (default: 1.0.0)
-CreatePortable           # Create portable ZIP
-CreateNSIS              # Create Windows installer
-CreateZip               # Create ZIP archive
-Sign                    # Sign executable with certificate
-CertPath "path/cert.pfx"   # Path to code signing certificate
-CertPassword "password"    # Certificate password
```

### Examples

**Create portable package only**:
```powershell
.\create-package.ps1 -Version 1.0.0 -CreatePortable
```

**Create all packages**:
```powershell
.\create-package.ps1 -Version 1.0.0 -CreatePortable -CreateNSIS
```

**Create and sign**:
```powershell
.\create-package.ps1 -Version 1.0.0 -CreatePortable -Sign `
  -CertPath "C:\certs\tradeadviser.pfx" `
  -CertPassword "mypassword123"
```

---

## Output Structure

After running the build script:

```
desktop/
├── dist/
│   └── TradeAdviser.exe              # Standalone executable
├── packages/
│   ├── TradeAdviser-v1.0.0-portable.zip    # Portable package
│   ├── TradeAdviser-v1.0.0-installer.exe   # Windows installer
│   ├── SHA256SUMS.txt                      # Integrity checksums
│   └── RELEASE-v1.0.0.md                   # Release notes
├── build/                             # Build artifacts (temp)
├── create-package.ps1                 # Packaging script
└── tradeadviser-installer.nsi         # NSIS installer config
```

---

## Verification & Testing

### 1. Verify Package Integrity

```powershell
cd packages
Get-FileHash TradeAdviser-v1.0.0-portable.zip -Algorithm SHA256
# Compare with SHA256SUMS.txt
```

### 2. Test Portable Package

```powershell
# Extract and test
Expand-Archive TradeAdviser-v1.0.0-portable.zip -DestinationPath test-portable
cd test-portable
.\TradeAdviser.exe
```

### 3. Test Windows Installer

```powershell
# Run installer in test environment
Start-Process packages\TradeAdviser-v1.0.0-installer.exe
# Follow wizard and verify installation
```

---

## Distribution Checklist

- [ ] Build packages successfully
- [ ] Verify checksums match SHA256SUMS.txt
- [ ] Test portable extraction and launch
- [ ] Test installer installation
- [ ] Test uninstaller removes files
- [ ] Create release on GitHub/website
- [ ] Upload packages to distribution server
- [ ] Update version number for next release

---

## Version Management

Update version in create-package.ps1:

```powershell
.\create-package.ps1 -Version 1.0.1  # For hotfix
.\create-package.ps1 -Version 1.1.0  # For minor release
.\create-package.ps1 -Version 2.0.0  # For major release
```

---

## Troubleshooting

### Error: "PyInstaller failed"
```powershell
# Verify dependencies are installed
pip install -r requirements.txt

# Clear build cache
Remove-Item dist -Recurse -Force
Remove-Item build -Recurse -Force

# Retry build
.\create-package.ps1 -Version 1.0.0
```

### Error: "NSIS not found"
```powershell
# Install NSIS
choco install nsis

# Or download from: https://nsis.sourceforge.io/download
```

### Large executable size (>500 MB)
This is normal for PyQt6/PySide6 applications. To reduce:

1. Use UPX compression (already enabled)
2. Exclude unnecessary modules in `.spec` file
3. Use `--onedir` instead of `--onefile` for smaller initial file

---

## Advanced Customization

### Modify NSIS Installer

Edit `tradeadviser-installer.nsi`:

```nsis
; Change installation directory
InstallDir "$PROGRAMFILES\MyCompany\TradeAdviser"

; Add custom files
File "docs\README.txt"
File "config\default-settings.ini"

; Add registry entries
WriteRegStr HKLM "Software\TradeAdviser" "InstallPath" "$INSTDIR"
```

### Customize PyInstaller Build

Edit `create-package.ps1` and modify the spec file generation:

```powershell
# Add hidden imports
hiddenimports=['your_module1', 'your_module2']

# Add data files
datas=[('your_folder', 'dest_folder')]

# Exclude modules
excludedimports=['unwanted_module']
```

---

## Next Steps

1. **Create your first package**:
   ```powershell
   .\create-package.ps1 -Version 1.0.0 -CreatePortable
   ```

2. **Test the portable package**

3. **Set up distribution**:
   - GitHub Releases
   - Your website
   - Cloud storage (AWS, Azure)

4. **Set up auto-update** (optional):
   - Implement update checking in the app
   - Use tools like Squirrel.Windows for auto-updates

---

## References

- [NSIS Documentation](https://nsis.sourceforge.io/Docs/)
- [PyInstaller Docs](https://pyinstaller.readthedocs.io/)
- [WiX Toolset](https://github.com/wixtoolset/wix3/) (alternative to NSIS)
- [Squirrel.Windows](https://github.com/Squirrel/Squirrel.Windows) (auto-updates)

---

**Last Updated**: 2026-04-20
**TradeAdviser Desktop Version**: 1.0.0
