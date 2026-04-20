# Deployment Guide

**TradeAdviser** can be deployed in multiple environments. This guide covers local, cloud, and containerized deployments.

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Docker & Docker Compose](#docker--docker-compose)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Cloud Deployments](#cloud-deployments)
5. [Environment Configuration](#environment-configuration)
6. [Database Migration](#database-migration)
7. [Scaling & Load Balancing](#scaling--load-balancing)
8. [Monitoring & Logging](#monitoring--logging)
9. [Troubleshooting](#troubleshooting)

---

## Local Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git
- SQLite3 or PostgreSQL

### Step 1: Clone Repository

```bash
git clone https://github.com/sopotek/tradeadviser.git
cd tradeadviser
```

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m alembic upgrade head  # if using migrations

# Or create tables:
python -c "from app.backend.db.base import Base, engine; Base.metadata.create_all(engine)"
```

### Step 3: Frontend Setup

```bash
cd ../frontend
npm install
```

### Step 4: Environment Configuration

```bash
# From project root
cp .env.example .env.local

# Edit .env.local with your settings
# See Environment Configuration section
```

### Step 5: Run Application

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend (optional, for hot reload)
cd frontend
npm run dev
```

Access:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Docker & Docker Compose

### Docker Compose (Recommended for Local Production-like Environment)

#### Build and Run

```bash
docker-compose up --build
```

#### Services

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:4173
- **PostgreSQL**: localhost:5432 (if using PostgreSQL)

#### Stopping Services

```bash
docker-compose down
```

#### Rebuild Specific Service

```bash
docker-compose build backend
docker-compose up backend
```

### Individual Docker Images

#### Build Backend Image

```bash
docker build -f docker/Dockerfile.backend -t tradeadviser-backend:latest .
```

#### Build Frontend Image

```bash
docker build -f docker/Dockerfile.frontend -t tradeadviser-frontend:latest .
```

#### Run Backend Container

```bash
docker run -p 8000:8000 \
  -e DATABASE_URL="sqlite:///./test.db" \
  tradeadviser-backend:latest
```

#### Run Frontend Container

```bash
docker run -p 4173:4173 \
  tradeadviser-frontend:latest
```

---

## Cloud Deployments

### AWS Deployment

#### Option 1: Elastic Beanstalk (Easiest)

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 tradeadviser

# Create environment
eb create tradeadviser-env

# Deploy
eb deploy

# View logs
eb logs

# SSH into instance
eb ssh
```

#### Option 2: ECS with Fargate

```bash
# Create ECR repositories
aws ecr create-repository --repository-name tradeadviser-backend
aws ecr create-repository --repository-name tradeadviser-frontend

# Build and push images
docker build -f docker/Dockerfile.backend -t tradeadviser-backend:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
docker tag tradeadviser-backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/tradeadviser-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/tradeadviser-backend:latest

# Create ECS cluster and services (via AWS Console or CloudFormation)
```

#### Option 3: EC2 (Manual)

```bash
# SSH into EC2 instance
ssh -i your-key.pem ec2-user@your-instance.compute.amazonaws.com

# Install dependencies
sudo yum update
sudo yum install python3.11 nodejs npm git

# Clone and setup
git clone https://github.com/sopotek/tradeadviser.git
cd tradeadviser

# Setup backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup frontend
cd ../frontend
npm install
npm run build

# Run with PM2 for process management
npm install -g pm2
pm2 start "python -m uvicorn main:app --port 8000" --name "tradeadviser-api"
pm2 save

# Configure Nginx as reverse proxy
```

### Azure Deployment

#### Option 1: App Service

```bash
# Install Azure CLI
curl https://aka.ms/InstallAzureCLIDeb | bash

# Login
az login

# Create resource group
az group create -n tradeadviser-rg -l eastus

# Create App Service Plan
az appservice plan create -n tradeadviser-plan -g tradeadviser-rg --sku B1 --is-linux

# Create web app
az webapp create -n tradeadviser-app -g tradeadviser-rg --plan tradeadviser-plan -r "python|3.11"

# Configure deployment
git remote add azure https://tradeadviser-app.scm.azurewebsites.net/tradeadviser-app.git
git push azure main

# Set environment variables
az webapp config appsettings set -n tradeadviser-app -g tradeadviser-rg --settings WEBSITES_PORT=8000
```

#### Option 2: Container Instances

```bash
# Create ACR (Azure Container Registry)
az acr create -g tradeadviser-rg -n tradeadviserregistry --sku Basic

# Build and push image
az acr build --registry tradeadviserregistry --image tradeadviser:latest .

# Deploy container
az container create -g tradeadviser-rg -n tradeadviser-app \
  --image tradeadviserregistry.azurecr.io/tradeadviser:latest \
  --ports 8000 \
  --cpu 1 \
  --memory 1
```

### GCP Deployment

#### Option 1: Cloud Run

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Login
gcloud auth login
gcloud config set project tradeadviser-project

# Build and deploy backend
gcloud run deploy tradeadviser-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --port 8000

# Deploy frontend
gcloud run deploy tradeadviser-frontend \
  --source frontend \
  --platform managed \
  --region us-central1 \
  --port 4173
```

#### Option 2: App Engine

```bash
# Create app.yaml
gcloud app create --region=us-central

# Deploy
gcloud app deploy

# View logs
gcloud app logs read -n 100
```

---

## Environment Configuration

### .env.local Template

```bash
# Application
APP_NAME=TradeAdviser
APP_ENV=development
APP_DEBUG=true
APP_PORT=8000
FRONTEND_PORT=5173

# Database
DATABASE_URL=sqlite:///./test.db
# Or for PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/tradeadviser

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:4173,https://tradeadviser.org

# OAuth (if using external auth)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Kafka (optional)
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC_PREFIX=tradeadviser

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Feature Flags
ENABLE_KAFKA=false
ENABLE_ADVANCED_AGENTS=true
ENABLE_RISK_ALERTS=true

# Security
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Company Info
COMPANY_NAME=Sopotek Inc
COMPANY_WEBSITE=https://sopotek.com
```

### Production Environment (.env.production)

```bash
APP_ENV=production
APP_DEBUG=false

DATABASE_URL=postgresql://user:password@prod-db-host:5432/tradeadviser

JWT_SECRET_KEY=<random-secure-key>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

ALLOWED_ORIGINS=https://tradeadviser.org,https://www.tradeadviser.org

LOG_LEVEL=WARNING
LOG_FILE=/var/log/tradeadviser/app.log

RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW_SECONDS=60

ENABLE_KAFKA=true
KAFKA_BROKER=kafka-broker-host:9092
```

---

## Database Migration

### SQLAlchemy Alembic Setup

```bash
# Install alembic
pip install alembic

# Initialize migrations
alembic init alembic

# Create migration (auto-detect schema changes)
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Manual Database Setup

```bash
# Login to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE tradeadviser;
CREATE USER tradeadviser WITH PASSWORD 'your-password';
ALTER ROLE tradeadviser SET client_encoding TO 'utf8';
ALTER ROLE tradeadviser SET default_transaction_isolation TO 'read committed';
ALTER ROLE tradeadviser SET default_transaction_deferrable TO on;
ALTER ROLE tradeadviser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE tradeadviser TO tradeadviser;
\q

# Initialize tables via Python
python << EOF
from app.backend.db.base import Base, engine
Base.metadata.create_all(engine)
EOF
```

---

## Scaling & Load Balancing

### Horizontal Scaling with Docker Compose

```yaml
version: '3.8'
services:
  backend:
    build: ./docker/Dockerfile.backend
    ports:
      - "8000-8003:8000"
    deploy:
      replicas: 4
    environment:
      - DATABASE_URL=postgresql://...

  frontend:
    build: ./docker/Dockerfile.frontend
    ports:
      - "4173"
    deploy:
      replicas: 2

  database:
    image: postgres:15
    # ... config

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
```

### Nginx Configuration (nginx.conf)

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:4173;
}

server {
    listen 80;
    server_name tradeadviser.org;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name tradeadviser.org;
    
    ssl_certificate /etc/ssl/certs/tradeadviser.crt;
    ssl_certificate_key /etc/ssl/private/tradeadviser.key;
    
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
    }
}
```

---

## Monitoring & Logging

### Application Insights (Azure)

```python
# backend/main.py
from opencensus.trace.tracer import Tracer
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

tracer = Tracer(sampler=ProbabilitySampler(rate=0.5))
```

### Logging Configuration

```python
# backend/config.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
```

### Health Checks

```python
# backend/api/routes/health.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
```

---

## Troubleshooting

### Backend Won't Start

```bash
# Check Python version
python --version  # Should be 3.10+

# Check if port is in use
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Check dependencies
pip install -r requirements.txt

# Run with verbose logging
python -m uvicorn main:app --log-level debug --reload
```

### Frontend Build Issues

```bash
# Clear cache
rm -rf node_modules package-lock.json
npm install

# Check Node version
node --version  # Should be 18+

# Run with verbose
npm run build -- --debug
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -U user -h localhost -d tradeadviser

# Check DATABASE_URL
echo $DATABASE_URL

# Test with SQLite
sqlite3 test.db ".tables"
```

### Docker Issues

```bash
# Clear dangling images
docker image prune

# Remove containers
docker container prune

# Rebuild without cache
docker-compose build --no-cache

# View logs
docker-compose logs -f backend
```

---

## Performance Optimization

### Database Optimization

```python
# Enable connection pooling
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
)
```

### Caching

```python
# Redis caching
from functools import lru_cache
import redis

cache = redis.Redis(host='localhost', port=6379)

@router.get("/trades")
async def get_trades():
    cached = cache.get("trades")
    if cached:
        return json.loads(cached)
    # ... fetch and cache
```

### Compression

```python
# Enable gzip
from fastapi.middleware.gzip import GZIPMiddleware

app.add_middleware(GZIPMiddleware, minimum_size=1000)
```

---

**Last Updated**: April 2026
