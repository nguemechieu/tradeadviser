# TradeAdviser Terminal Launcher Guide

## Overview

This guide explains the improved terminal organization system for TradeAdviser development. Choose your preferred launcher based on your setup.

---

## Option 1: PowerShell Launcher (Recommended)

### Quick Start

```powershell
cd C:\Users\nguem\Documents\GitHub\tradeadviser
.\LAUNCH_TERMINALS.ps1
```

### Features

✅ **Interactive Menu** - Choose what to launch  
✅ **Color-Coded** - Each service has distinct colors  
✅ **Help Text** - Each terminal shows available commands  
✅ **Flexible** - Full stack, backend, frontend, or custom  
✅ **Clean Layout** - ASCII borders and organized output  

### Usage Modes

```powershell
# Interactive menu (default)
.\LAUNCH_TERMINALS.ps1

# Launch specific configuration
.\LAUNCH_TERMINALS.ps1 -Mode Full        # All services
.\LAUNCH_TERMINALS.ps1 -Mode Backend     # Backend only
.\LAUNCH_TERMINALS.ps1 -Mode Frontend    # Frontend only
.\LAUNCH_TERMINALS.ps1 -Mode Desktop     # Desktop only
```

### Menu Options

1. **Full Stack** - Backend + Frontend + Desktop (Complete dev environment)
2. **Backend Only** - Docker + API server
3. **Frontend Only** - React dev server
4. **Desktop Only** - PyQt application
5. **Minimal** - Backend + Frontend (faster startup)
6. **Custom** - Select individual components
7. **Exit**

---

## Option 2: Batch Launcher (Simple Alternative)

### Quick Start

```cmd
C:\Users\nguem\Documents\GitHub\tradeadviser\LAUNCH_TERMINALS.cmd
```

### Features

✅ **No Prerequisites** - Works with plain Command Prompt  
✅ **Simple Menu** - Easy selection interface  
✅ **Organized Windows** - Each service in separate window  

---

## Option 3: Windows Terminal Configuration (Advanced)

### Setup

1. Copy `WINDOWS_TERMINAL_SETTINGS.json` to your Windows Terminal settings:
   ```
   %LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json
   ```

2. Or open Windows Terminal and use Settings → Open JSON file, then merge the custom profiles

### Features

✅ **Custom Profiles** - Pre-configured backend/frontend/desktop  
✅ **Keyboard Shortcuts**:
   - `Alt+Shift+B` - New Backend terminal
   - `Alt+Shift+F` - New Frontend terminal
   - `Alt+Shift+D` - New Desktop terminal
   - `Ctrl+Shift+T` - New tab

✅ **Color Scheme** - "One Half Dark" theme  
✅ **Persistent** - Settings saved in Windows Terminal

---

## Service Quick Reference

### Backend Server

**Start:**
```bash
make docker-up
```

**Access:**
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs

**Commands:**
```bash
make docker-up           # Start all services
make docker-down         # Stop all services
make docker-logs         # View real-time logs
make docker-ps           # List running containers
make docker-restart      # Restart services
make test                # Run tests
make lint                # Code linting
make security            # Security scan
```

---

### Frontend Server

**Start:**
```bash
npm install
npm run dev
```

**Access:**
- Frontend: http://localhost:5173

**Commands:**
```bash
npm install              # Install dependencies
npm run dev              # Development server
npm run build            # Production build
npm run preview          # Preview production build
```

---

### Desktop Application

**Setup:**
```powershell
.\.venv\Scripts\activate.ps1
```

**Start:**
```bash
python main.py
```

**Commands:**
```bash
python main.py           # Run application
pytest                   # Run tests
python -m pytest --cov   # Tests with coverage
```

---

## Recommended Workflow

### Complete Setup (Full Stack)

1. **Terminal 1 - Backend** (Stays running)
   ```bash
   make docker-up
   ```

2. **Terminal 2 - Frontend** (Stays running)
   ```bash
   npm run dev
   ```

3. **Terminal 3 - Development**
   ```bash
   # Use for git commands, file management, etc.
   cd C:\Users\nguem\Documents\GitHub\tradeadviser
   ```

4. **Terminal 4 - Desktop** (If needed)
   ```bash
   python main.py
   ```

### Minimal Setup (Backend + Frontend)

1. **Terminal 1 - Backend**
   ```bash
   make docker-up
   ```

2. **Terminal 2 - Frontend**
   ```bash
   npm run dev
   ```

---

## Troubleshooting

### Terminals Won't Open

**Solution:** Check execution policy
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port Already in Use

**Find what's using the port:**
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
```

**Kill the process:**
```powershell
Stop-Process -Id <PID> -Force
```

### Can't activate Python virtual environment

**Manually activate:**
```powershell
cd C:\Users\nguem\Documents\GitHub\tradeadviser\desktop
.\.venv\Scripts\activate.ps1
```

### Docker service won't start

**Check Docker is running:**
```bash
docker ps
docker logs <container-name>
```

---

## Directory Structure

```
tradeadviser/
├── LAUNCH_TERMINALS.ps1           ← PowerShell launcher (recommended)
├── LAUNCH_TERMINALS.cmd           ← Batch launcher (alternative)
├── WINDOWS_TERMINAL_SETTINGS.json ← Windows Terminal config
├── server/
│   ├── Makefile                   ← Backend commands
│   └── docker-compose.yml         ← Docker services
├── desktop/
│   ├── main.py                    ← Desktop app entry
│   └── .venv/                     ← Python environment
└── frontend/
    ├── package.json               ← Frontend dependencies
    └── vite.config.js             ← Vite configuration
```

---

## Tips & Tricks

### 1. Keep Terminal Windows Organized

- Arrange terminals side-by-side:
  - Left: Backend (docker logs)
  - Center: Frontend (dev server)
  - Right: Development terminal

### 2. Monitor All Services

Use a separate terminal to watch logs:
```bash
make docker-logs
```

### 3. Quick Restart

Stop and restart everything:
```bash
make docker-down
make docker-clean
make docker-up
npm run dev
```

### 4. Access Logs

```bash
# Backend logs
tail -f server/logs/*.log

# Desktop logs
tail -f desktop/logs/*.log

# Frontend (in browser console)
F12 → Console tab
```

### 5. Create Desktop Shortcut

Right-click desktop → New → Shortcut
```
C:\Windows\System32\cmd.exe /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\nguem\Documents\GitHub\tradeadviser\LAUNCH_TERMINALS.ps1"
```

---

## Next Steps

1. **Choose your launcher:**
   - PowerShell (recommended): `.\LAUNCH_TERMINALS.ps1`
   - Batch: `LAUNCH_TERMINALS.cmd`
   - Windows Terminal: Merge `WINDOWS_TERMINAL_SETTINGS.json`

2. **Set up Windows Terminal** (optional but nice):
   - Download: Microsoft Store → Windows Terminal
   - Merge the configuration file provided

3. **Create a desktop shortcut** for quick access

4. **Pin to taskbar** for easy launching

---

## Support

For issues with the launchers:
- Check execution policies
- Ensure Docker is installed and running
- Verify all paths are correct
- Check firewall settings for ports 8000, 5173
