# Setup & Installation Guide

This guide covers installation and configuration of TradeAdviser for development and production environments.

## Table of Contents

- [System Requirements](#system-requirements)
- [Quick Start (Docker)](#quick-start-docker)
- [Local Development Setup](#local-development-setup)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Testing](#testing)

## System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 10GB
- **OS**: Windows, macOS, Linux

### Software Requirements
- Python 3.11 or higher
- Node.js 18 or higher
- PostgreSQL 13+ (for local development)
- Docker & Docker Compose (for containerized deployment)
- Git

### Development Tools
- Git
- Visual Studio Code (recommended)
- Postman or Insomnia (for API testing)
- Python IDE (PyCharm, VS Code)

## Quick Start (Docker)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/tradeadviser.git
cd tradeadviser
```

### 2. Docker Setup

```bash
# Navigate to server directory
cd server

# Build and start containers
docker-compose up -d --build

# Verify containers are running
docker-compose ps
```

### 3. Verify Installation

```bash
# Check backend health
curl http://localhost:8000/health

# Access frontend
# Open browser: http://localhost:8000

# Access API documentation
# Open browser: http://localhost:8000/docs
```

### 4. Stop Containers

```bash
docker-compose down
```

## Local Development Setup

### Backend Setup

#### 1. Python Environment

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

#### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# Important variables:
# - DATABASE_URL: PostgreSQL connection string
# - API_HOST: Server host (default: 0.0.0.0)
# - API_PORT: Server port (default: 8000)
```

#### 4. Database Setup

```bash
# Create database (if using local PostgreSQL)
psql -U postgres -c "CREATE DATABASE tradeadviser;"

# Or use Docker for database
docker run -d \
  --name postgres-tradeadviser \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=tradeadviser \
  -p 5432:5432 \
  postgres:15
```

#### 5. Run Backend Server

```bash
# Development (with auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Backend will be available at: `http://localhost:8000`

### Frontend Setup

#### 1. Install Dependencies

```bash
cd server/frontend

npm install
```

#### 2. Development Server

```bash
# Start development server with hot reload
npm run dev
```

Frontend will be available at: `http://localhost:5173`

#### 3. Production Build

```bash
# Build for production
npm run build

# Output in: dist/
```

### Desktop Application Setup

#### 1. Python Environment

```bash
cd desktop

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

#### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Configuration

```bash
# Desktop loads configuration from:
# ~/.tradeadviser/session.json (after login)
# ~/.tradeadviser/profiles/profiles.json (broker profiles)

# Create config directory
mkdir -p ~/.tradeadviser/profiles
```

#### 4. Run Desktop Application

```bash
python main.py
```

On Windows, you can also:
```bash
# Double-click: "Launch TradeAdviser.cmd"
```

## Configuration

### Backend Configuration

**File**: `backend/config.py`

```python
class ServerSettings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/tradeadviser"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TITLE: str = "TradeAdviser API"
    
    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:8000", "http://localhost:5173"]
```

### Frontend Configuration

**File**: `server/frontend/vite.config.js`

```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

**Environment Files**:
- `.env.development` - Development variables
- `.env.production` - Production variables

### Desktop Configuration

**File**: `desktop/src/config/settings.py`

```python
class DesktopSettings:
    # Server URL
    SERVER_URL = "http://localhost:8000"
    
    # UI Settings
    THEME = "dark"
    WINDOW_SIZE = (1400, 900)
```

## Database Setup

### Using Docker

```bash
docker run -d \
  --name tradeadviser-db \
  -e POSTGRES_USER=tradeuser \
  -e POSTGRES_PASSWORD=securepassword \
  -e POSTGRES_DB=tradeadviser \
  -p 5432:5432 \
  -v tradeadviser-data:/var/lib/postgresql/data \
  postgres:15
```

### Using Local PostgreSQL

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE tradeadviser;
CREATE USER tradeuser WITH PASSWORD 'securepassword';
GRANT ALL PRIVILEGES ON DATABASE tradeadviser TO tradeuser;
```

### Database Migrations

```bash
# Using Alembic (if configured)
cd backend

# View current migration
alembic current

# Upgrade to latest migration
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add new table"
```

## Testing

### Backend Tests

```bash
cd backend

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_auth.py::test_login
```

### Frontend Tests

```bash
cd server/frontend

# Run Jest tests
npm test

# Run with coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```

### Integration Tests

```bash
cd backend

# Run backend with test database
TEST_DATABASE_URL="sqlite:///:memory:" pytest tests/integration/
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux

# Kill the process
kill -9 <PID>

# Windows PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

### Database Connection Issues

```bash
# Test connection
psql -h localhost -U tradeuser -d tradeadviser

# Check PostgreSQL is running
docker ps | grep postgres

# View logs
docker logs tradeadviser-db
```

### Permission Issues

```bash
# Fix permission on Unix-like systems
chmod -R 755 backend/
chmod -R 755 desktop/
chmod -R 755 server/

# Create log directory
mkdir -p logs
chmod 755 logs
```

### Python Module Not Found

```bash
# Ensure you're in activated virtual environment
which python  # Should show venv path

# Reinstall requirements
pip install --upgrade -r requirements.txt

# Clear pip cache
pip cache purge
```

## Next Steps

1. **Configure your environment** - Update `.env` files
2. **Start the services** - Use Docker or local setup
3. **Create admin user** - See API_REFERENCE.md
4. **Configure brokers** - Add broker connections
5. **Deploy trading strategies** - Start trading!

## Getting Help

- Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Review [API_REFERENCE.md](./API_REFERENCE.md)
- Check container logs: `docker-compose logs -f`
- Read documentation in `/docs`

---

**Last Updated**: April 2026
