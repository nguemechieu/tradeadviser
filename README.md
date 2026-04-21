# TradeAdviser - Institutional Trading Platform

A comprehensive, institutional-grade AI trading platform featuring automated trading strategies, risk management, real-time portfolio monitoring, and multi-broker support. TradeAdviser combines a powerful backend server with a professional desktop application and web console.
![logo](./server/frontend/src/assets/logo.png)

## 🎯 Overview

TradeAdviser is a full-stack trading ecosystem designed for institutional traders and algorithmic trading teams. It provides:

- **Real-time Market Data Processing** - Stream market data and execute trades with minimal latency
- **Multi-Broker Support** - Seamlessly integrate with multiple brokers (local and remote)
- **Advanced Risk Management** - Portfolio risk monitoring, position limits, and automated breach detection
- **AI-Powered Trading Agents** - Deploy and manage intelligent trading agents
- **Professional Dashboard** - Real-time trading console with comprehensive analytics
- **Institutional Compliance** - License management, audit trails, and security features

## 🏗️ System Architecture

TradeAdviser is built with two independent software components:

### TradeAdviser Server (`tradeadviser_server` / `/server`)
Full-stack backend and web console serving institutional trading infrastructure.

- **Backend API**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15
- **Messaging**: Kafka for event streaming
- **Web Console**: React 18 with Vite
- **Deployment**: Docker containerized
- **Services**: Includes Nginx, Redis, Zookeeper, and PgAdmin

### TradeAdviser Desktop (`tradeadviser_desktop` / `/desktop`)
Standalone professional trading application for institutional traders.

- **Framework**: PySide6 (Qt Python bindings)
- **Features**: Advanced trading tools, local strategy execution, portfolio monitoring
- **Platform**: Windows, macOS, Linux
- **Distribution**: Standalone executable or Python package

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 15 (for local development)

### Docker Deployment (Recommended)

```bash
cd server
docker-compose up -d --build
```

**Access the platform:**
- Frontend: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Local Development

**TradeAdviser Server** (`tradeadviser_server`)
```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run backend
cd backend && uvicorn main:app --reload

# In another terminal, run frontend
cd server/frontend && npm install && npm run dev
```

**TradeAdviser Desktop** (`tradeadviser_desktop`)
```bash
cd desktop
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [SETUP.md](./SETUP.md) | Installation and environment configuration |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Production deployment guide |
| [API_REFERENCE.md](./API_REFERENCE.md) | Complete API documentation |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design and components |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Common issues and solutions |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Development guidelines |

## 🔑 Key Features

### Trading Management
- Multi-strategy execution
- Real-time position tracking
- Automated order management
- Trade history and analytics

### Risk Management
- Portfolio risk calculations
- Automated breach detection
- Position limit enforcement
- Historical risk analysis

### Administration
- User and license management
- System health monitoring
- Operational oversight
- Performance auditing

### AI & Automation
- Intelligent trading agents
- Signal generation
- Strategy optimization
- Automated decision support

## 🔐 Security & Compliance

- **Authentication**: JWT token-based with refresh tokens
- **Authorization**: Role-based access control (RBAC)
- **Encryption**: TLS for transport, encrypted credentials storage
- **Compliance**: Audit logging, license enforcement, compliance reporting
- **Data Protection**: Encrypted database connections, secure credential management

## 📊 API Endpoints

Core API structure:
```
/api/v1/
├── /auth              - Authentication
├── /users             - User management
├── /trades            - Trade management
├── /portfolio         - Portfolio analytics
├── /risk              - Risk management
├── /signals           - Signal generation
├── /workspace         - Workspace configuration
├── /agents            - AI agent management
├── /operations        - System operations
└── /performance       - Performance analytics
```

See [API_REFERENCE.md](./API_REFERENCE.md) for complete endpoint documentation.

## 🌐 Component Integration

### TradeAdviser Desktop ↔ TradeAdviser Server Communication
- **Protocol**: HTTP/WebSocket
- **Default Server URL**: http://localhost:8000
- **Authentication**: Bearer token in Authorization header
- **Real-time Events**: WebSocket connections for live data

### Web Console ↔ Backend API Communication
- **API Protocol**: REST/HTTP
- **Data Format**: JSON
- **CORS**: Configured for localhost and production domains
- **Base URL**: http://localhost:8000/api/v1

### Backend Data Persistence
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Connection Pool**: Async connection management
- **Database**: PostgreSQL 15+ with async support

## 🐳 Docker Deployment

### Services

**TradeAdviser Server Backend Service**
```yaml
- Image: tradeadviser_server-backend:latest
- Port: 8000
- Database: PostgreSQL 15
- Assets: Mounts frontend dist folder
```

**TradeAdviser Server Frontend Service**
```yaml
- Image: tradeadviser_server-frontend:latest
- Port: 3000
- Build: React Vite dev/prod server
```

**Database Service**
```yaml
- Image: postgres:15
- Port: 5432
- Volume: Persistent data storage
- Initialization: SQL schema setup
```

### Supporting Services
- **Redis**: In-memory data cache (port 6379)
- **Kafka**: Event streaming (port 9092)
- **Zookeeper**: Kafka coordination (port 2181)
- **Nginx**: Reverse proxy (port 80/443)
- **PgAdmin**: Database management UI (port 5050)

### Environment Variables

See `.env.example` for all available configuration options:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/tradeadviser

# API
API_HOST=0.0.0.0
API_PORT=8000

# CORS
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5173
```

## 📈 Monitoring & Health

### Health Check Endpoint
```bash
curl http://localhost:8000/health
```

Response includes:
- Service status
- User count
- Active sessions
- Trade counts
- System statistics

### Logging

- **Backend**: Structured logging with timestamps
- **Desktop**: Application logs stored in user config directory
- **Frontend**: Browser console and debug toolbar

## 🎓 Usage by Role

### For Traders
1. Log in to the web console or desktop app
2. Configure broker connections
3. Deploy trading strategies
4. Monitor portfolio in real-time
5. Adjust risk parameters as needed

### For Administrators
1. Access admin dashboard (default: /admin)
2. Manage user accounts and licenses
3. Monitor system health and operations
4. Review compliance and audit logs
5. Configure system settings

### For Developers
1. Set up local development environment (see SETUP.md)
2. Review API documentation
3. Create custom strategies or agents
4. Contribute improvements via git workflow
5. Deploy to staging/production (see DEPLOYMENT.md)

## 🔧 Configuration

### Backend Configuration
- Location: `backend/config.py`
- Environment-based settings using Pydantic
- Supports `.env` files for secrets

### Frontend Configuration
- Location: `server/frontend/vite.config.js`
- Build output: `server/frontend/dist`
- Environment files: `.env.development`, `.env.production`

### Desktop Configuration
- Location: `desktop/src/config/`
- Session storage: `~/.tradeadviser/session.json`
- Profiles storage: `~/.tradeadviser/profiles/profiles.json`

## 📦 Project Structure

```
tradeadviser/
├── backend/                    # FastAPI backend server
│   ├── main.py                # Application entry point
│   ├── config.py              # Configuration settings
│   ├── api/routes/            # API endpoint definitions
│   ├── db/                    # Database models and session
│   ├── models/                # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Business logic
│   └── utils/                 # Utilities and helpers
│
├── server/                    # Server-specific configuration
│   ├── frontend/              # React web console
│   │   ├── src/
│   │   ├── dist/              # Built assets (generated)
│   │   └── package.json
│   ├── backend/               # Server-specific backend code
│   └── docker-compose.yml     # Docker services definition
│
├── desktop/                   # PySide6 desktop application
│   ├── main.py                # Desktop entry point
│   ├── src/                   # Application source
│   │   ├── main/              # Main window and UI
│   │   ├── ui/                # UI components
│   │   ├── core/              # Business logic
│   │   └── config/            # Configuration
│   └── requirements.txt
│
├── docs/                      # Documentation
├── SETUP.md                   # Setup instructions
├── DEPLOYMENT.md              # Deployment guide
├── API_REFERENCE.md           # API documentation
├── ARCHITECTURE.md            # Architecture details
├── TROUBLESHOOTING.md         # Troubleshooting guide
└── CONTRIBUTING.md            # Contribution guidelines
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on:
- Code style and standards
- Pull request process
- Testing requirements
- Commit message format

## 📄 License

See LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Ask questions in Discussions
- **Docs**: Comprehensive documentation in `/docs`
- **Examples**: Code examples in `/docs/examples`

## 🗺️ Roadmap

- [ ] Advanced strategy backtesting framework
- [ ] Machine learning signal generation
- [ ] Real-time risk analytics dashboard
- [ ] Mobile app (iOS/Android)
- [ ] Advanced compliance reporting
- [ ] Multi-tenancy support

## 👥 Team

TradeAdviser is maintained by the development team. For questions or support, refer to the documentation or open an issue.

---

**Last Updated**: April 2026 | **Version**: 1.0.0
# TradeAdviser

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Website: tradeadviser.org](https://img.shields.io/badge/Website-tradeadviser.org-blue.svg)](https://www.tradeadviser.org)
[![Company: Sopotek Inc](https://img.shields.io/badge/Company-Sopotek%20Inc-green.svg)](https://sopotek.com)

### CI/CD Status

[![Test](https://github.com/sopotek/tradeadviser/actions/workflows/test.yml/badge.svg)](https://github.com/sopotek/tradeadviser/actions/workflows/test.yml)
[![Build](https://github.com/sopotek/tradeadviser/actions/workflows/build.yml/badge.svg)](https://github.com/sopotek/tradeadviser/actions/workflows/build.yml)
[![Deploy](https://github.com/sopotek/tradeadviser/actions/workflows/deploy.yml/badge.svg)](https://github.com/sopotek/tradeadviser/actions/workflows/deploy.yml)
[![Code Quality](https://github.com/sopotek/tradeadviser/actions/workflows/code-quality.yml/badge.svg)](https://github.com/sopotek/tradeadviser/actions/workflows/code-quality.yml)
[![codecov](https://codecov.io/gh/sopotek/tradeadviser/branch/main/graph/badge.svg)](https://codecov.io/gh/sopotek/tradeadviser)

**TradeAdviser** is an intelligent trading advisory platform that combines AI-powered agents, risk analysis, and portfolio management to provide traders and portfolio managers with actionable insights and automated trading recommendations.

---

## 📋 Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Development](#development)
- [CI/CD Pipeline](#cicd-pipeline)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## ✨ Features

### Core Capabilities

- **AI-Powered Agents**: Intelligent trading agents that analyze market signals and execute trading decisions
- **Risk Management**: Real-time risk assessment and portfolio risk analysis
- **Signal Analysis**: Advanced signal generation and interpretation engine
- **Performance Auditing**: Comprehensive performance tracking and historical analysis
- **Portfolio Management**: Multi-asset portfolio optimization and tracking
- **Session Management**: Secure user sessions with role-based access control
- **Trading Operations**: Streamlined trade execution with audit trails
- **Admin Dashboard**: Comprehensive admin interface for system management
- **WebSocket Support**: Real-time updates for market data and trading events

### Security Features

- OAuth 2.0 Authentication
- Role-Based Access Control (RBAC)
- API Key Management
- License-based Access Control
- Audit Logging
- Rate Limiting

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** for backend
- **Node.js 18+** for frontend
- **Docker & Docker Compose** (optional, for containerized setup)

### One-Command Setup

#### On Windows (PowerShell):
```powershell
.\scripts\start-app.ps1
```

#### On macOS/Linux (Bash):
```bash
./scripts/start-app.sh
```

#### Using Docker:
```bash
docker-compose up --build
```

The application will start on:
- **Frontend**: http://localhost:4173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

---

## 📁 Project Structure

```
tradeadviser/
├── backend/                          # FastAPI backend application
│   ├── main.py                      # Entry point, serves both API and frontend
│   ├── config.py                    # Configuration management
│   ├── requirements.txt              # Python dependencies
│   ├── api/                         # API routes and endpoints
│   │   └── routes/                  # Organized route modules
│   ├── agents/                      # AI trading agents
│   ├── core/                        # Core business logic services
│   ├── db/                          # Database models and session
│   ├── models/                      # SQLAlchemy ORM models
│   ├── schemas/                     # Pydantic request/response schemas
│   ├── services/                    # Business logic services
│   │   ├── decision/               # Trading decision service
│   │   ├── execution/              # Trade execution service
│   │   └── risk/                   # Risk analysis service
│   ├── shared/                     # Shared domain models
│   │   ├── commands/               # Domain commands
│   │   ├── contracts/              # Data contracts
│   │   ├── enums/                  # Shared enumerations
│   │   └── events/                 # Domain events
│   ├── infrastructure/              # Infrastructure services
│   │   ├── messaging/              # Event bus and messaging
│   │   └── telemetry/              # Logging and observability
│   ├── utils/                       # Utility functions
│   └── tests/                       # Unit tests
│
├── frontend/                        # React + Vite frontend application
│   ├── package.json                # Node.js dependencies
│   ├── vite.config.js              # Vite configuration
│   ├── index.html                  # HTML entry point
│   ├── src/
│   │   ├── main.jsx                # React application entry
│   │   ├── App.jsx                 # Main app component
│   │   ├── components/             # Reusable React components
│   │   ├── pages/                  # Page components
│   │   ├── context/                # React context providers
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── api/                    # API client utilities
│   │   └── assets/                 # Static assets
│   └── dist/                        # Built frontend (generated)
│
├── docker/                          # Docker configuration files
│   ├── Dockerfile.backend          # Backend container image
│   └── Dockerfile.frontend         # Frontend container image
│
├── scripts/                         # Utility and deployment scripts
│   ├── start-app.ps1               # Windows startup script
│   ├── start-app.sh                # Unix startup script
│   ├── deploy.sh                   # Deployment script
│   └── health-check.py             # Health check utility
│
├── docs/                            # Documentation
│   ├── ARCHITECTURE.md             # System architecture documentation
│   ├── DEPLOYMENT.md               # Deployment guide
│   ├── API.md                      # API documentation
│   ├── CONTRIBUTING.md             # Contributing guidelines
│   └── web-platform.md             # Platform documentation
│
├── docker-compose.yml              # Docker Compose configuration
├── .env.example                    # Environment variables template
├── .env.local                      # Local development environment (gitignored)
├── .gitignore                      # Git ignore rules
├── README.md                       # This file
├── LICENSE                         # MIT License
└── requirements.txt                # Root-level Python dependencies
```

---

## 🏗️ Architecture

TradeAdviser follows a **layered architecture** with clear separation of concerns:

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser/Client                           │
└────────────────────────┬──────────────────────────────────────┘
                         │ HTTP/WebSocket
         ┌───────────────▼───────────────┐
         │   React Frontend (Vite)       │
         │  - UI Components              │
         │  - State Management           │
         │  - API Client                 │
         └───────────────┬───────────────┘
                         │ REST/WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│               FastAPI Backend (Port 8000)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐   │
│  │        API Routes & Controllers                      │   │
│  │  (Auth, Trading, Portfolio, Risk, etc.)             │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │          Business Logic Services                    │    │
│  │  - TradingService     - RiskService                 │    │
│  │  - PortfolioService   - SignalService              │    │
│  │  - DecisionService    - ExecutionService           │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │     AI Agent Framework                              │    │
│  │  - RegimeAgent        - FeedbackAgent               │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │   Infrastructure & Shared Services                  │    │
│  │  - EventBus           - Logging                     │    │
│  │  - Authentication     - Rate Limiting               │    │
│  │  - WebSocket Manager  - Session Management         │    │
│  └──────────────────────┬──────────────────────────────┘    │
└─────────────────────────▼───────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Database │    │Kafka/   │    │External │
    │(SQLite/ │    │Message  │    │Services │
    │PostgreSQL)   │Broker   │    │         │
    └─────────┘    └─────────┘    └─────────┘
```

For detailed architecture information, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 💾 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/sopotek/tradeadviser.git
cd tradeadviser
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

### 4. Environment Configuration

```bash
# Copy environment template
cp .env.example .env.local

# Edit with your configuration
# See Configuration section below
```

---

## 🏃 Running the Application

### Option 1: Local Development (Recommended)

#### Start Backend (from project root):
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -m uvicorn main:app --reload --port 8000
```

The backend will serve:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:8000 (serves built frontend)

#### Start Frontend (development with hot reload, from project root):
```bash
cd frontend
npm run dev
```

The frontend will run on http://localhost:5173 with hot module replacement.

### Option 2: Docker Compose (Full Stack)

```bash
docker-compose up --build
```

Services will be available at:
- **Frontend**: http://localhost:4173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Option 3: Startup Scripts

#### Windows PowerShell:
```powershell
.\scripts\start-app.ps1
```

#### Linux/macOS:
```bash
chmod +x scripts/start-app.sh
./scripts/start-app.sh
```

---

## 📚 API Documentation

### Interactive API Docs (Swagger UI)
Available at: http://localhost:8000/docs

### API Endpoints Overview

```
POST   /api/auth/login              - User authentication
POST   /api/auth/logout             - Logout user
GET    /api/auth/profile            - Get user profile

GET    /api/trades                  - List trades
POST   /api/trades                  - Create trade
GET    /api/trades/{trade_id}       - Get trade details

GET    /api/portfolio               - Get portfolio overview
GET    /api/portfolio/positions     - List positions
GET    /api/portfolio/holdings      - Get holdings

GET    /api/risk/analysis           - Perform risk analysis
GET    /api/risk/metrics            - Get risk metrics

GET    /api/signals                 - Get trading signals
POST   /api/signals/generate        - Generate new signals

GET    /api/performance             - Get performance metrics
GET    /api/performance/audit       - Performance audit log

POST   /api/agents/execute          - Execute agent
GET    /api/agents/status           - Get agent status

GET    /api/admin/dashboard         - Admin dashboard
GET    /api/admin/system/health     - System health check
```

For complete API documentation, see [API.md](docs/API.md).

---

## 👨‍💻 Development

### Development Environment

The application uses:
- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Frontend**: React 18, Vite, Axios
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Message Queue**: Kafka (optional)
- **Authentication**: OAuth 2.0 + JWT

### Development Server

Start both frontend and backend for live development:

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
python -m uvicorn main:app --reload

# Terminal 2: Frontend (optional for hot reload)
cd frontend
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

### Code Style & Linting

```bash
# Backend
cd backend
black .
flake8 .
mypy .

# Frontend
cd frontend
npx eslint src/
```

---

## � CI/CD Pipeline

TradeAdviser uses GitHub Actions for automated testing, security scanning, building, and deployment.

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **Test** | Push/PR | Run tests and security scans |
| **Build** | Push/Tag | Build Docker images |
| **Code Quality** | Push/PR | Code analysis and linting |
| **Deploy** | Push (staging), Tag (prod) | Deploy to environments |
| **Release** | Tag creation | Create releases |

### Quick Links

- **Full Documentation**: [CI/CD.md](docs/CI_CD.md)
- **GitHub Actions**: [View Workflows](https://github.com/sopotek/tradeadviser/actions)
- **Test Results**: [Test Reports](https://github.com/sopotek/tradeadviser/actions/workflows/test.yml)

### Running Tests Locally

```bash
# Backend
cd backend
pytest -v --cov=.

# Frontend
cd frontend
npm test
```

### Setting Up Deployment

To enable production deployment, configure these GitHub Secrets:

```
STAGING_DEPLOY_KEY       # SSH private key
STAGING_HOST             # Server hostname
STAGING_USER             # SSH user
PRODUCTION_DEPLOY_KEY    # SSH private key
PRODUCTION_HOST          # Server hostname
PRODUCTION_USER          # SSH user
SLACK_WEBHOOK            # For notifications
```

---

## �🚀 Deployment

### Docker Deployment

Build and run containers:
```bash
docker-compose build
docker-compose up -d
```

### Cloud Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for:
- **AWS Deployment** (ECS, Elastic Beanstalk)
- **Azure Deployment** (App Service, Container Instances)
- **GCP Deployment** (Cloud Run, App Engine)
- **Kubernetes Deployment** (Helm charts)

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on:
- Code of conduct
- Development setup
- Pull request process
- Coding standards
- Testing requirements

---

## 📝 License

TradeAdviser is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

---

## 🏢 About

**TradeAdviser** is developed and maintained by **Sopotek Inc**.

- **Website**: https://tradeadviser.org
- **Company**: Sopotek Inc
- **Email**: info@sopotek.com

---

## 📞 Support

For support, issues, or feature requests, please:
1. Check the [documentation](docs/)
2. Review [existing issues](https://github.com/sopotek/tradeadviser/issues)
3. Create a new issue with detailed information
4. Contact support@sopotek.com

---

## 🔗 Resources

- [Architecture Documentation](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Kubernetes Deployment](docs/KUBERNETES.md)
- [CI/CD Pipeline](docs/CI_CD.md)
- [Scheduled Cron Jobs](docs/CRONJOBS.md)
- [Operations Schedule](docs/OPERATIONS_SCHEDULE.md)
- [Code Coverage](docs/COVERAGE.md)
- [Contributing Guidelines](docs/CONTRIBUTING.md)
- [Platform Documentation](docs/web-platform.md)

---

**Last Updated**: April 2026  
**Version**: 1.0.0