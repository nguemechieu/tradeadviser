# TradeAdviser Quick Reference Guide

Quick reference for common tasks and operations with TradeAdviser.

## 🚀 Starting the Application

### Fastest Way (Development)
```bash
# Windows
.\scripts\start-app.ps1

# Unix/Linux/macOS
./scripts/start-app.sh
```

### With Docker
```bash
docker-compose up --build
```

### Specific Modes

| Mode | Command | Use Case |
|------|---------|----------|
| **Development** | `.\scripts\start-app.ps1 -Mode dev` | Quick local development |
| **Docker** | `.\scripts\start-app.ps1 -Mode docker` | Production-like environment |
| **Full** | `.\scripts\start-app.ps1 -Mode full` | Frontend + Backend separate |

## 🌐 Service URLs

```
Frontend:       http://localhost:8000
Backend API:    http://localhost:8000/api
API Docs:       http://localhost:8000/docs
API ReDoc:      http://localhost:8000/redoc

Frontend Dev:   http://localhost:5173  (dev mode only)
Database:       localhost:5432
```

## 📦 Installation Quick Start

### Windows
```powershell
# Clone repo
git clone https://github.com/sopotek/tradeadviser.git
cd tradeadviser

# Run startup script
.\scripts\start-app.ps1
```

### Unix/Linux/macOS
```bash
# Clone repo
git clone https://github.com/sopotek/tradeadviser.git
cd tradeadviser

# Make script executable
chmod +x scripts/start-app.sh

# Run startup script
./scripts/start-app.sh
```

## 📚 Key Documentation

| Document | Purpose |
|----------|---------|
| [README.md](./README.md) | Main documentation |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System design |
| [DEPLOYMENT.md](./docs/DEPLOYMENT.md) | Deployment guide |
| [CONTRIBUTING.md](./docs/CONTRIBUTING.md) | Development guidelines |
| [RESTRUCTURE_SUMMARY.md](./RESTRUCTURE_SUMMARY.md) | What was changed |

## 🛠️ Development Commands

### Backend (Python)

```bash
# Activate virtual environment
cd backend
source venv/bin/activate  # Unix
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
python -m uvicorn main:app --reload

# Format code
black .

# Lint
flake8 .

# Type checking
mypy .

# Run tests
pytest

# Run tests with coverage
pytest --cov=app tests/
```

### Frontend (JavaScript)

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint
npx eslint src/

# Format
npx prettier --write src/
```

## 🐳 Docker Commands

```bash
# Build all services
docker-compose build

# Start all services
docker-compose up

# Start with rebuild
docker-compose up --build

# Start in background
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend

# Execute command in container
docker-compose exec backend python -c "print('hello')"

# Rebuild specific service
docker-compose build backend
```

## 🔧 Configuration

### Environment Setup

```bash
# Copy template
cp .env.example .env.local

# Edit with your settings
# Key settings:
# - DATABASE_URL: Database connection string
# - JWT_SECRET_KEY: For authentication
# - ALLOWED_ORIGINS: For CORS
# - KAFKA settings (if using Kafka)
```

### Docker Profiles

```bash
# Start with Redis caching
docker-compose --profile with-redis up

# Start with Kafka messaging
docker-compose --profile with-kafka up

# Start with all services
docker-compose --profile with-redis --profile with-kafka --profile with-nginx --profile with-pgadmin up
```

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=app tests/

# Watch mode
ptw

# Frontend tests
cd frontend
npm test

# Watch mode
npm test -- --watch
```

## 📊 Database

### Initialize

```bash
cd backend
python -c "from app.backend.db.base import Base, engine; Base.metadata.create_all(engine)"
```

### Migration (with Alembic)

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Access Database (Docker)

```bash
# PostgreSQL
docker-compose exec database psql -U tradeadviser -d tradeadviser

# SQLite (development)
sqlite3 tradeadviser.db
```

## 🔍 Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

### Dependency Issues

```bash
# Backend
rm -rf backend/venv
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Frontend
rm -rf frontend/node_modules package-lock.json
cd frontend && npm install
```

### Docker Issues

```bash
# Remove dangling images
docker image prune

# Remove dangling containers
docker container prune

# Full cleanup
docker system prune

# Rebuild without cache
docker-compose build --no-cache
```

### Virtual Environment Not Activating

```bash
# Create new venv
python3 -m venv backend/venv

# Activate
source backend/venv/bin/activate  # Unix
# or
backend\venv\Scripts\activate  # Windows

# Verify
which python  # Unix
where python  # Windows
```

## 📖 API Quick Reference

```
# Authentication
POST /api/auth/login          - Login user
POST /api/auth/logout         - Logout user
GET  /api/auth/profile        - Get user profile

# Trades
GET  /api/trades              - List trades
POST /api/trades              - Create trade
GET  /api/trades/{id}         - Get trade details

# Portfolio
GET  /api/portfolio           - Portfolio overview
GET  /api/portfolio/positions - List positions
GET  /api/portfolio/holdings  - Get holdings

# Risk
GET  /api/risk/analysis       - Risk analysis
GET  /api/risk/metrics        - Risk metrics

# Signals
GET  /api/signals             - Get signals
POST /api/signals/generate    - Generate signals

# Performance
GET  /api/performance         - Performance metrics
GET  /api/performance/audit   - Audit log

# Admin
GET  /api/admin/dashboard     - Admin dashboard
GET  /api/admin/system/health - System health
```

## 🚢 Deployment

### Docker Deployment

```bash
# Build image
docker build -f docker/Dockerfile.backend -t tradeadviser-backend .

# Run container
docker run -p 8000:8000 -e DATABASE_URL=postgresql://... tradeadviser-backend
```

### Docker Compose (Full Stack)

```bash
docker-compose build
docker-compose up -d
```

### Cloud Deployment

See [DEPLOYMENT.md](./docs/DEPLOYMENT.md) for:
- AWS (Elastic Beanstalk, ECS, EC2)
- Azure (App Service, Container Instances)
- GCP (Cloud Run, App Engine)

## 💾 Backup & Restore

### Database Backup

```bash
# PostgreSQL
docker-compose exec database pg_dump -U tradeadviser tradeadviser > backup.sql

# Restore
docker-compose exec -T database psql -U tradeadviser tradeadviser < backup.sql
```

## 📝 Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and commit
git add .
git commit -m "feat: description of changes"

# Push to fork
git push origin feature/your-feature

# Create pull request on GitHub
```

## 🔐 Security

### Generate JWT Secret

```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### SSL Certificate (for development)

```bash
# Generate self-signed cert
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

## 📊 Monitoring

### Logs

```bash
# Application logs
tail -f logs/tradeadviser.log

# Docker logs
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

### Health Check

```bash
curl http://localhost:8000/health
```

## 🎯 Common Tasks

### Build Frontend

```bash
cd frontend
npm run build
# Output: dist/
```

### Update Dependencies

```bash
# Backend
pip install -U -r requirements.txt

# Frontend
npm update
```

### Format Code

```bash
# Backend
cd backend
black .
isort .

# Frontend
cd frontend
npx prettier --write src/
```

### Run Specific Test

```bash
# Backend
pytest tests/test_trading_service.py::test_execute_trade

# Frontend
npm test -- TradeForm.test.js
```

## 📞 Support

- **Documentation**: See docs/ folder
- **Issues**: GitHub Issues
- **Email**: support@sopotek.com
- **Website**: https://tradeadviser.org

---

**TradeAdviser Quick Reference**  
Last Updated: April 2026
