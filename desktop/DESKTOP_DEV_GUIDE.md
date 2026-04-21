# Desktop Application Development Guide

## 🚀 Quick Start

### Option 1: Interactive Launcher (Recommended)
```powershell
.\LAUNCH_DESKTOP.ps1
```

Menu options:
- **[1] Development** - Run local PyQt application
- **[2] Test** - Run pytest suite  
- **[3] Docker** - Run in containers (noVNC)
- **[4] Setup** - Create/update virtual environment

### Option 2: Using Make
```bash
make launch          # Interactive menu
make dev             # Start app immediately
make setup           # Setup virtual environment
make install         # Install dependencies
```

### Option 3: Direct Command
```powershell
python main.py
```

---

## ⚡ Development Workflow

### First Time Setup

1. **Create Virtual Environment**
   ```bash
   make setup
   # or
   .\LAUNCH_DESKTOP.ps1 -Mode Dev  # Automatically sets up
   ```

2. **Activate Environment** (optional, auto-activated)
   ```powershell
   .\.venv\Scripts\activate.ps1
   ```

3. **Install Dependencies**
   ```bash
   make install
   ```

### Running the Application

```bash
# Using Make (recommended)
make dev

# Using launcher
.\LAUNCH_DESKTOP.ps1 -Mode Dev

# Direct command
python main.py

# Direct with activated venv
.\.venv\Scripts\activate.ps1
python main.py
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage report
make test-coverage

# Run specific test
.\.venv\Scripts\activate.ps1
pytest tests/test_specific.py -v
```

---

## 📋 Code Quality

```bash
# Check formatting
make format-check

# Auto-format code
make format

# Run linter
make lint

# Run security scan
make security

# Run all checks
make check-all
```

---

## 🐳 Docker Mode

Run the desktop app in a container with noVNC web interface.

```bash
# Start Docker
make docker-up
# Access: http://localhost:6080

# View logs
make docker-logs

# List containers
make docker-ps

# Stop Docker
make docker-down

# Clean up (remove volumes)
make docker-clean
```

---

## 🛠️ Utilities

```bash
# Clean build artifacts
make clean

# Show status
make status

# View recent logs
ls -lht logs/*.log

# Watch specific log
tail -f logs/host-ui-latest.txt
```

---

## 📁 Project Structure

```
desktop/
├── main.py                      # Entry point (bootstrap wrapper)
├── LAUNCH_DESKTOP.ps1          # PowerShell launcher (NEW)
├── Makefile                     # Development commands (UPDATED)
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project metadata
├── pytest.ini                  # Test configuration
├── .venv/                      # Virtual environment
├── src/
│   └── main.py                 # Application main logic
├── tests/                      # Test suite
├── logs/                       # Application logs
├── docs/                       # Documentation
└── tools/
    ├── lint.sh                 # Linting
    ├── format.sh               # Code formatting
    ├── test.sh                 # Testing
    └── security_scan.sh        # Security scanning
```

---

## 🎯 Common Tasks

### Debug the Application

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py

# Or with launcher
.\LAUNCH_DESKTOP.ps1 -NoVenv  # Keeps terminal open for debugging
```

### View Application Logs

```bash
# Last log file
tail -f logs/host-ui-latest.txt

# Get log path info
cat logs/host-ui-latest.txt
```

### Install New Package

```bash
.\.venv\Scripts\activate.ps1
pip install package-name
pip freeze > requirements.txt
```

### Run Single Test

```bash
.\.venv\Scripts\activate.ps1
pytest tests/test_module.py::test_function -v
```

---

## 🚨 Troubleshooting

### Virtual Environment Issues

**Problem:** "venv not found"
```bash
# Solution: Create it
make setup
```

**Problem:** "Module not found"
```bash
# Solution: Reinstall dependencies
.\.venv\Scripts\activate.ps1
pip install -r requirements.txt
```

### PyQt Issues

**Problem:** "No module named PyQt6"
```bash
# Solution
make install
# Or manually
pip install PyQt6
```

### Port Conflicts

**Problem:** Port 6080 already in use (Docker)
```powershell
# Find and kill process
Get-Process -Id (Get-NetTCPConnection -LocalPort 6080).OwningProcess
Stop-Process -Id <PID> -Force
```

### Logs Not Showing

**Problem:** Can't find logs
```bash
# Logs location
.\logs\

# Check latest
cat logs/host-ui-latest.txt
```

---

## 📊 Makefile Commands Reference

| Command | Purpose |
|---------|---------|
| `make help` | Show all commands |
| `make launch` | Interactive menu |
| `make dev` | Run app |
| `make setup` | Setup venv |
| `make install` | Install deps |
| `make test` | Run tests |
| `make test-coverage` | Tests + coverage |
| `make lint` | Code linting |
| `make format` | Auto-format |
| `make security` | Security scan |
| `make docker-up` | Start Docker |
| `make docker-logs` | View logs |
| `make docker-down` | Stop Docker |
| `make clean` | Clean artifacts |
| `make status` | App status |

---

## 🔑 Key Improvements

✅ **Interactive Launcher** - Choose mode (Dev/Test/Docker)  
✅ **Automatic venv** - Launcher creates/activates automatically  
✅ **Better Makefile** - Organized, colorized commands  
✅ **Dependency Check** - Validates Python packages  
✅ **Clear Logging** - Status messages and error handling  
✅ **Setup Wizard** - First-time setup is smooth  
✅ **Docker Support** - Containerized app with web UI  
✅ **Status Command** - Check app status quickly  

---

## 📝 Environment Variables

```bash
# Set environment
$env:ENV = "development"

# Set log level
$env:LOG_LEVEL = "DEBUG"

# Set Python path (optional)
$env:PYTHONPATH = "."
```

---

## 🔗 Integration with Full Stack

### Start Everything Together

From root directory:
```bash
# Use the main launcher
.\LAUNCH_TERMINALS.ps1

# Select option [1] Full Stack
# This starts:
# - Backend (Docker) at http://localhost:8000
# - Frontend (React) at http://localhost:5173
# - Desktop (PyQt) in new window
```

### Individual Services

```bash
# Backend (from server/)
make docker

# Frontend (from server/app/frontend/)
npm run dev

# Desktop (from desktop/)
make dev
```

---

## ✅ Next Steps

1. **First time?** Run: `make setup`
2. **Start developing:** `make dev`
3. **Run tests:** `make test`
4. **Check status:** `make status`

---

**Status**: ✅ Desktop terminal setup is now optimized with launcher and improved Makefile
