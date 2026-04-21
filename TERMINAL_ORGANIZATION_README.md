# TradeAdviser - Improved Terminal Organization

## 🚀 Quick Start

Launch all services with one command:

```powershell
.\LAUNCH_TERMINALS.ps1
```

Or using make:

```bash
make launch
```

---

## Available Launchers

### 1. **PowerShell Launcher** (Recommended)
```powershell
.\LAUNCH_TERMINALS.ps1
```
- ✅ Interactive menu
- ✅ Color-coded terminals
- ✅ Flexible options
- ✅ Help text in each terminal

### 2. **Makefile Commands**
```bash
make launch              # Interactive menu
make launch-full        # All services
make launch-backend     # Backend + Docker
make launch-frontend    # Frontend only
make launch-desktop     # Desktop only
```

### 3. **Batch Launcher** (Simple)
```cmd
LAUNCH_TERMINALS.cmd
```
- ✅ No dependencies
- ✅ Works with Command Prompt

### 4. **Windows Terminal Configuration** (Advanced)
See `WINDOWS_TERMINAL_SETTINGS.json` for custom profiles and shortcuts

---

## Menu Options

When you run `LAUNCH_TERMINALS.ps1`, you'll see:

```
[1] Full Stack       (Backend + Frontend + Desktop)
[2] Backend Only     (Docker + API)
[3] Frontend Only    (React dev server)
[4] Desktop Only     (PyQt application)
[5] Minimal          (Backend + Frontend)
[6] Custom           (Select components)
```

---

## Service URLs

Once services are running:

| Service | URL | Notes |
|---------|-----|-------|
| **Backend API** | http://localhost:8000 | FastAPI server |
| **API Docs** | http://localhost:8000/docs | Swagger documentation |
| **Frontend** | http://localhost:5173 | React dev server |
| **Desktop** | Native window | PyQt application |

---

## Common Commands by Service

### Backend (Docker)
```bash
make docker              # Start services
make docker-down        # Stop services
make docker-logs        # View logs
make docker-ps          # List containers
make test               # Run tests
make lint               # Code linting
```

### Frontend (React)
```bash
npm install             # Install dependencies
npm run dev             # Development server
npm run build           # Production build
npm run preview         # Preview build
```

### Desktop (PyQt)
```bash
python main.py          # Run application
pytest                  # Run tests
.\.venv\Scripts\activate.ps1  # Activate virtual environment
```

---

## Typical Workflow

### 1️⃣ Terminal 1 - Start Backend
```bash
make docker
```
This starts all Docker services (API, PostgreSQL, Redis, etc.)

### 2️⃣ Terminal 2 - Start Frontend
```bash
cd server/app/frontend
npm install
npm run dev
```

### 3️⃣ Terminal 3 - Development
```bash
# Use for git commands, debugging, etc.
```

---

## Files Included

| File | Purpose |
|------|---------|
| `LAUNCH_TERMINALS.ps1` | **Recommended** - PowerShell launcher with interactive menu |
| `LAUNCH_TERMINALS.cmd` | Alternative batch launcher |
| `WINDOWS_TERMINAL_SETTINGS.json` | Windows Terminal custom profiles |
| `Makefile` | Make commands for easy task running |
| `TERMINAL_LAUNCHER_GUIDE.md` | Detailed guide with troubleshooting |

---

## Installation & Setup

### First Time Setup

1. **Install Dependencies**
   ```bash
   make install
   ```

2. **Ensure Docker is Running**
   - Windows: Start Docker Desktop
   - Verify: `docker ps`

3. **Launch Services**
   ```powershell
   .\LAUNCH_TERMINALS.ps1
   ```

### Running Full Stack

**Option A: Using PowerShell**
```powershell
.\LAUNCH_TERMINALS.ps1
```
Then select option `[1] Full Stack`

**Option B: Using Make**
```bash
make launch-full
```

**Option C: Manual Launch**
```powershell
# Terminal 1
cd server
make docker-up

# Terminal 2
cd server/app/frontend
npm run dev

# Terminal 3
cd desktop
python main.py
```

---

## Troubleshooting

### "Port already in use" error

Find what's using the port:
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
```

Kill the process:
```powershell
Stop-Process -Id <PID> -Force
```

### PowerShell execution policy error

Allow local script execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Docker service won't start

Check if Docker Desktop is running:
```bash
docker ps
```

If not running, start Docker Desktop from your applications.

### Python virtual environment activation fails

Manually activate:
```powershell
cd desktop
.\.venv\Scripts\activate.ps1
```

---

## Pro Tips

### 1. Create Desktop Shortcut
Right-click desktop → New → Shortcut
```
C:\Windows\System32\cmd.exe /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\nguem\Documents\GitHub\tradeadviser\LAUNCH_TERMINALS.ps1"
```

### 2. Organize Window Layout
Pin terminals to screen positions:
- **Left (50%)**: Backend logs
- **Right-Top (25%)**: Frontend dev server  
- **Right-Bottom (25%)**: Development terminal

### 3. Watch Services Status
```bash
make status
```

### 4. Clean Everything
```bash
make clean
```

### 5. Quick Restart All
```bash
make clean
make launch-full
```

---

## Documentation

For detailed information, see:
- [`TERMINAL_LAUNCHER_GUIDE.md`](TERMINAL_LAUNCHER_GUIDE.md) - Complete guide with examples
- [`Makefile`](Makefile) - Available commands reference
- Project documentation in respective folders

---

## Next Steps

1. **Run the launcher:**
   ```powershell
   .\LAUNCH_TERMINALS.ps1
   ```

2. **Select Full Stack or preferred option**

3. **Access services at:**
   - Backend: http://localhost:8000
   - Frontend: http://localhost:5173

4. **Start developing!**

---

## Architecture Overview

```
TradeAdviser
├── Backend Services (Docker)
│   ├── FastAPI Server (port 8000)
│   ├── PostgreSQL Database
│   ├── Redis Cache
│   └── API Documentation (port 8000/docs)
│
├── Frontend (React + Vite)
│   ├── Development Server (port 5173)
│   ├── Components & Pages
│   └── Authentication & Icons
│
└── Desktop (PyQt)
    ├── Native Application
    ├── Trading Interface
    └── Local Database
```

---

## Questions or Issues?

1. Check [`TERMINAL_LAUNCHER_GUIDE.md`](TERMINAL_LAUNCHER_GUIDE.md) troubleshooting section
2. Review service-specific documentation in folders
3. Check logs in `server/logs` and `desktop/logs`
4. Verify ports 8000 and 5173 are available

---

**Happy coding! 🚀**
