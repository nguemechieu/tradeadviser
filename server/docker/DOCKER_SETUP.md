# TradeAdviser Docker Setup Guide

## Overview
This guide documents the Docker containerization of the TradeAdviser platform, including all services (PostgreSQL, FastAPI Backend, React Frontend, Nginx Reverse Proxy), and the integration of Control Tower and License Management services.

## Files Updated

### 1. **backend.Dockerfile** 
**Issue Fixed**: Incorrect path references
- Changed `COPY /app/backend/requirements.txt` → `COPY app/backend/requirements.txt`
- Build context is now correctly set to parent `server/` directory
- Multi-stage build optimizes image size (builder stage for compilation, slim production image)
- Includes health check endpoint on port 8000

### 2. **frontend.Dockerfile**
**Issues Fixed**: 
- Changed `COPY /package*.json ./` → `COPY app/frontend/package*.json ./`
- Changed `COPY . .` → `COPY app/frontend .`
- Fixed builder path from `/build/dist` → `/frontend/dist`
- Changed `COPY nginx.conf` → `COPY server/docker/nginx.conf`
- Ensures npm packages and frontend code are correctly copied from source

### 3. **nginx.Dockerfile**
**Issue Fixed**: Incorrect entrypoint path
- Changed `COPY docker/entrypoint-nginx.sh` → `COPY server/docker/entrypoint-nginx.sh`
- Changed `COPY nginx.conf` → `COPY server/docker/nginx.conf`
- Build context alignment with other services

### 4. **docker-compose.yml** (→ docker-compose-updated.yml)
**Status**: New comprehensive configuration created
- **Build Context**: All services now use `context: ..` (server/ directory)
- **Database Service**: PostgreSQL 15-alpine with health checks, security settings
- **Backend Service**: FastAPI with all Control Tower and License Management env vars
- **Frontend Service**: React/Vite on port 3000 (was 5173)
- **Nginx Service**: Reverse proxy with proper routing for API and WebSocket

**New Environment Variables**:
```yaml
# Control Tower
ENABLE_CONTROL_TOWER=true
CONTROL_TOWER_UPDATE_INTERVAL=2

# License Management
ENABLE_LICENSE_MANAGEMENT=true
TRIAL_DAYS=30

# Payment Processing
STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
PAYPAL_MODE, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET
COINBASE_API_KEY, COINBASE_WEBHOOK_SECRET

# Email
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
SMTP_FROM_NAME, SMTP_FROM_EMAIL, SMTP_USE_TLS
```

**Security Features**:
- `no-new-privileges: true` for all services
- Capability dropping (CAP_DROP: ALL, CAP_ADD: NET_BIND_SERVICE)
- Non-root user for database
- Resource limits (backend: 1GB memory, frontend: 512MB)
- Health checks for all services

### 5. **nginx.conf**
**Enhancements**:
- Added dedicated `/api/control-tower/feed` location for WebSocket support
- Added `/api/webhooks/` location for payment webhook endpoints (no auth)
- Enhanced proxy settings with proper timeout handling
- Security headers preserved (X-Frame-Options, X-Content-Type-Options, etc.)
- Static asset caching (30 days for JS/CSS/images)

### 6. **backend/requirements.txt**
**New Dependencies Added**:
```
# System Monitoring (Control Tower)
psutil>=6.0,<7.0

# Payment Processing
stripe>=10.0,<11.0
paypalrestsdk>=1.7,<2.0
coinbase-commerce>=3.0,<4.0

# HTTP Client for webhooks
requests>=2.31,<3.0
httpx>=0.25,<1.0

# Email delivery
Jinja2>=3.0,<4.0
```

### 7. **platform.env.example**
**Updated**: Complete environment variable template
- Database configuration (all vars matching docker-compose)
- JWT and security settings
- CORS configuration
- Control Tower settings
- License management settings
- Payment processing (Stripe, PayPal, Coinbase)
- Email configuration (SMTP, SendGrid, Mailgun examples)
- Usage instructions and warnings

## Build Context Fix

### Problem
Dockerfiles referenced paths like `/app/backend/requirements.txt` and `/build/dist` which don't exist in the build context.

### Solution
- All Dockerfiles now use relative paths from `server/` root directory
- Docker Compose specifies `context: ..` for backend and frontend builds
- Nginx Dockerfile correctly references `server/docker/nginx.conf`

### Correct Structure
```
server/
├── app/
│   ├── backend/
│   │   └── requirements.txt  (now correctly COPY'd as app/backend/requirements.txt)
│   └── frontend/
│       ├── package.json      (now correctly COPY'd as app/frontend/package*.json)
│       └── dist/             (now correctly referenced as /frontend/dist)
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── nginx.Dockerfile
│   ├── nginx.conf
│   ├── entrypoint.sh
│   ├── entrypoint-nginx.sh
│   ├── docker-compose.yml    (original)
│   ├── docker-compose-updated.yml (new)
│   └── platform.env.example
├── main.py
└── ...
```

## Service Architecture

### Database (PostgreSQL)
- **Image**: `postgres:15-alpine`
- **Port**: 5432
- **Health Check**: pg_isready
- **Credentials**: User: tradeadviser, Password: (from DB_PASSWORD env var)
- **Volumes**: postgres_data (persistent)

### Backend (FastAPI)
- **Dockerfile**: `docker/backend.Dockerfile`
- **Port**: 8000
- **Health Check**: GET /health
- **Key Services**:
  - Control Tower (system metrics, sessions, trades)
  - License Management (key generation, verification)
  - Payment Processing (Stripe, PayPal, Coinbase)
  - Email Service (SMTP-based)
- **Depends On**: database (with health check)

### Frontend (React)
- **Dockerfile**: `docker/frontend.Dockerfile`
- **Port**: 3000 (via Nginx)
- **Health Check**: wget to /
- **Build**: Multi-stage Vite build → Nginx serve
- **Depends On**: backend

### Nginx (Reverse Proxy)
- **Dockerfile**: `docker/nginx.Dockerfile`
- **Ports**: 80 (HTTP), 443 (HTTPS - ready for SSL)
- **Routes**:
  - `/` → Frontend (React)
  - `/api/` → Backend (FastAPI)
  - `/api/control-tower/feed` → WebSocket (2-sec updates)
  - `/api/webhooks/` → Payment webhooks
- **Health Check**: GET /api/health

## Deployment Instructions

### 1. Prepare Environment File
```bash
cd server/docker
cp platform.env.example .env
# Edit .env with your actual credentials
```

### 2. Build and Start Services
```bash
# From server/docker directory
docker-compose -f docker-compose-updated.yml up -d --build

# Or using the newer docker compose (single command)
docker compose -f docker-compose-updated.yml up -d --build
```

### 3. Verify Services
```bash
# Check status
docker-compose -f docker-compose-updated.yml ps

# View logs
docker-compose -f docker-compose-updated.yml logs -f backend
docker-compose -f docker-compose-updated.yml logs -f frontend
docker-compose -f docker-compose-updated.yml logs -f database

# Check health
curl http://localhost:8000/health
curl http://localhost:3000/health
curl http://localhost/api/health
```

### 4. Access Services
- **API Documentation**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **Database**: localhost:5432

## Control Tower Integration

The Control Tower service monitors:
- CPU, Memory, Disk usage
- Database latency
- API response times
- Active sessions
- Broker connections
- Trade queue status

**Access Control Tower**:
```bash
# Real-time metrics
curl http://localhost:8000/api/control-tower/metrics

# Dashboard snapshot
curl http://localhost:8000/api/control-tower/dashboard

# WebSocket feed (2-second updates)
wscat -c ws://localhost:8000/api/control-tower/feed
```

## License Management Integration

The License Service manages:
- License key generation (TRADE-XXXXX-XXXXX-XXXXX-XXXXX format)
- License verification and activation
- 30-day free trial with full feature access
- Feature tier management (Basic, Pro, Enterprise)

**Purchase License**:
```bash
# Via Stripe (card)
curl -X POST http://localhost:8000/api/licenses/purchase \
  -H "Content-Type: application/json" \
  -d '{"license_type":"basic","payment_method":"card","card_token":"tok_visa"}'

# Via PayPal
curl -X POST http://localhost:8000/api/licenses/purchase \
  -H "Content-Type: application/json" \
  -d '{"license_type":"pro","payment_method":"paypal"}'

# Via Crypto
curl -X POST http://localhost:8000/api/licenses/purchase \
  -H "Content-Type: application/json" \
  -d '{"license_type":"enterprise","payment_method":"crypto","crypto_currency":"btc"}'
```

**Verify License**:
```bash
curl http://localhost:8000/api/licenses/verify \
  -H "Content-Type: application/json" \
  -d '{"license_key":"TRADE-XXXXX-XXXXX-XXXXX-XXXXX"}'
```

## Environment Variables Reference

### Critical (Change for production)
- `JWT_SECRET_KEY`: JWT signing key (min 32 chars)
- `DB_PASSWORD`: Database password
- `STRIPE_API_KEY`: Stripe secret key (sk_test_* / sk_live_*)
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`: PayPal OAuth
- `COINBASE_API_KEY`: Coinbase Commerce API key
- `SMTP_PASSWORD`: Email service password (use app-specific password)

### Optional (Defaults work for local dev)
- `ENV`: production / development
- `DEBUG`: true / false
- `LOG_LEVEL`: info / debug / warning / error
- `CONTROL_TOWER_UPDATE_INTERVAL`: 2 (seconds)
- `TRIAL_DAYS`: 30

## Email Service Configuration

### Gmail (Recommended for Dev)
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password  # NOT your main password!
SMTP_USE_TLS=true
```

Steps:
1. Enable 2-factor authentication on Gmail
2. Create App Password (https://myaccount.google.com/apppasswords)
3. Use the generated 16-character password

### SendGrid (Recommended for Production)
```
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key
SMTP_USE_TLS=true
```

### Mailgun
```
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your_mailgun_api_key
```

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose -f docker-compose-updated.yml logs backend

# Verify health
docker inspect $(docker-compose -f docker-compose-updated.yml ps -q backend) --format='{{.State.Health.Status}}'
```

### Database Connection Fails
```bash
# Ensure database is healthy
docker-compose -f docker-compose-updated.yml exec database pg_isready -U tradeadviser

# Reset database
docker-compose -f docker-compose-updated.yml down -v
docker-compose -f docker-compose-updated.yml up -d database
```

### Build Fails with Path Errors
- Ensure `docker-compose-updated.yml` uses `context: ..`
- All COPY paths must be relative to server/ directory
- Verify file paths exist: `ls server/app/backend/requirements.txt`

### Payment Webhooks Not Received
- Verify `STRIPE_WEBHOOK_SECRET`, `PAYPAL_CLIENT_SECRET`, etc. are correct
- Check webhook URLs are exposed (Nginx routes `/api/webhooks/`)
- Verify payment provider can reach your domain

## Migration from Old Docker Setup

### Using New docker-compose-updated.yml
```bash
# Stop old services
docker-compose down

# Use new configuration (recommended)
docker-compose -f docker-compose-updated.yml up -d --build

# Or rename and replace original
mv docker-compose.yml docker-compose.original.yml
mv docker-compose-updated.yml docker-compose.yml
docker-compose up -d --build
```

### Clean Migration (Recommended)
```bash
# Stop and remove old setup
docker-compose down -v

# Start fresh with new setup
docker-compose -f docker-compose-updated.yml up -d --build

# Verify all services are healthy
docker-compose -f docker-compose-updated.yml ps
```

## Production Deployment Checklist

- [ ] Set `ENV=production` and `DEBUG=false`
- [ ] Use strong `JWT_SECRET_KEY` (32+ random characters)
- [ ] Configure real database with strong password
- [ ] Set up HTTPS/SSL certificates (update Nginx config)
- [ ] Configure all payment API keys (production versions)
- [ ] Set up email service (SendGrid recommended)
- [ ] Configure CORS origins for your domain
- [ ] Verify all services pass health checks
- [ ] Set up monitoring/alerting for Control Tower
- [ ] Test license purchase and activation flow
- [ ] Configure backup for PostgreSQL data
- [ ] Set up log aggregation
- [ ] Implement rate limiting on payment endpoints
- [ ] Test payment webhooks with real transactions

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| backend.Dockerfile | Fixed COPY path | Docker build now works |
| frontend.Dockerfile | Fixed multiple paths | Docker build now works |
| nginx.Dockerfile | Fixed entrypoint path | Docker build now works |
| docker-compose-updated.yml | New comprehensive config | Services properly networked |
| nginx.conf | Added WebSocket & webhook routes | Control Tower feed works |
| requirements.txt | Added 7 new dependencies | Services have required packages |
| platform.env.example | Complete env template | Easier deployment setup |

All changes are backward compatible; the original docker-compose.yml still exists.
