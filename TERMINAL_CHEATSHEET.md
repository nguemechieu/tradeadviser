# Terminal Launcher - Quick Reference Cheat Sheet

## 🚀 QUICK START

```powershell
# Option 1: Interactive Menu (Recommended)
.\LAUNCH_TERMINALS.ps1

# Option 2: Launch Specific Stack
.\LAUNCH_TERMINALS.ps1 -Mode Full      # All services
.\LAUNCH_TERMINALS.ps1 -Mode Backend   # Backend only
.\LAUNCH_TERMINALS.ps1 -Mode Frontend  # Frontend only
.\LAUNCH_TERMINALS.ps1 -Mode Desktop   # Desktop only

# Option 3: Make Command
make launch              # Interactive
make launch-full        # All services
```

---

## 📋 SERVICE SHORTCUTS

### Start Everything
```bash
make launch-full
```

### Start Backend Only
```bash
make docker              # In server/ directory
make docker-up           # Or use explicit command
```

### Start Frontend Only
```bash
cd server/app/frontend
npm run dev
```

### Start Desktop Only
```bash
cd desktop
python main.py
```

---

## 🔗 ACCESS SERVICES

| Service | URL | Command |
|---------|-----|---------|
| **API** | http://localhost:8000 | `make docker` |
| **API Docs** | http://localhost:8000/docs | Same as above |
| **Frontend** | http://localhost:5173 | `npm run dev` |
| **Desktop** | Native Window | `python main.py` |

---

## 🛠️ MAINTENANCE COMMANDS

```bash
# Testing
make test                # Run all tests
make lint                # Code linting
make format              # Auto-format code

# Docker Management
make docker              # Start Docker
make docker-down         # Stop Docker
make docker-logs         # View logs
make docker-clean        # Clean up

# Cleanup
make clean               # Remove all build artifacts
make status              # Check service status
```

---

## 📍 DIRECTORY SHORTCUTS

```bash
# Root (Launcher location)
C:\Users\nguem\Documents\GitHub\tradeadviser\

# Backend
C:\Users\nguem\Documents\GitHub\tradeadviser\server\

# Frontend
C:\Users\nguem\Documents\GitHub\tradeadviser\server\app\frontend\

# Desktop
C:\Users\nguem\Documents\GitHub\tradeadviser\desktop\
```

---

## 🔧 COMMON TASKS

### Install Dependencies
```bash
make install
```

### Full Stack Restart
```bash
make clean
make install
make launch-full
```

### Backend Only Restart
```bash
make docker-down
make docker-clean
make docker
```

### Frontend Only Restart
```bash
cd server/app/frontend
rm -r node_modules package-lock.json
npm install
npm run dev
```

### Desktop Only Restart
```bash
cd desktop
.\.venv\Scripts\activate.ps1
python main.py
```

---

## ⚠️ TROUBLESHOOTING QUICK FIXES

### Port Already in Use
```powershell
# Find process
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
# Kill it
Stop-Process -Id <PID> -Force
```

### Execution Policy Error
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Virtual Environment Issues
```powershell
cd desktop
.\.venv\Scripts\activate.ps1
```

### Docker Not Running
```bash
# Start Docker Desktop, then verify
docker ps
```

### NPM/Node Issues
```bash
cd server/app/frontend
npm cache clean --force
rm -r node_modules package-lock.json
npm install
```

---

## 💡 TIPS

1. **Keep terminals running** - Don't close any terminal while developing
2. **Watch backend logs** - Use `make docker-logs` in separate terminal
3. **Enable hot reload** - Frontend & backend both support hot reloading
4. **Test often** - Run `make test` before committing
5. **Check status** - Use `make status` to verify services

---

## 📦 TERMINAL MENU SELECTION GUIDE

```
[1] Full Stack
    → Use when: Starting fresh development session
    → Starts: Backend + Frontend + Desktop
    → Best for: Complete testing

[2] Backend Only
    → Use when: Only need API development
    → Starts: Docker services, API server
    → Best for: API debugging

[3] Frontend Only
    → Use when: Only need UI development
    → Starts: React dev server
    → Best for: UI/UX work

[4] Desktop Only
    → Use when: Only need desktop app
    → Starts: PyQt application
    → Best for: Desktop feature development

[5] Minimal
    → Use when: Want quick startup
    → Starts: Backend + Frontend
    → Best for: Most development work

[6] Custom
    → Use when: Need specific combination
    → Lets you: Select individual components
    → Best for: Advanced users
```

---

## 🎯 TYPICAL WORKFLOWS

### Workflow A: Web Development
```bash
# Terminal 1
make docker

# Terminal 2
cd server/app/frontend && npm run dev

# Terminal 3 (development/git)
```

### Workflow B: API Development
```bash
# Terminal 1
make docker

# Terminal 2 (development/testing)
cd server
make test --watch
```

### Workflow C: Desktop Development
```bash
# Terminal 1
cd desktop
.\.venv\Scripts\activate.ps1
python main.py
```

### Workflow D: Full Stack Testing
```bash
make launch-full
# Wait for all terminals to start
# Test via web frontend at http://localhost:5173
```

---

## 📝 NOTES

- **First run:** Always run `make install` first
- **Ports:** Ensure 8000 and 5173 are available
- **Docker:** Must be running before backend starts
- **Python:** Virtual environment auto-activated
- **Node:** npm dependencies auto-installed

---

## ⌨️ WINDOWS TERMINAL SHORTCUTS (If Using Config)

- `Alt+Shift+B` - New Backend terminal
- `Alt+Shift+F` - New Frontend terminal
- `Alt+Shift+D` - New Desktop terminal
- `Ctrl+Shift+T` - New tab

---

**Last Updated:** April 2026
**Status:** Ready for Production
