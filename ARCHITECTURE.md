# System Architecture

This document describes the overall architecture of TradeAdviser system.

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Database Schema](#database-schema)
- [Security Architecture](#security-architecture)

## High-Level Overview

TradeAdviser is a three-tier distributed system:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                             │
├──────────────────┬──────────────────┬──────────────────────┤
│  Web Console     │  Desktop App     │  Mobile (Future)     │
│  (React 18)      │  (PySide6)       │                      │
└────────┬─────────┴──────────┬───────┴──────────────────────┘
         │ HTTP/WebSocket    │ HTTP/WebSocket
         │                    │
┌────────▼────────────────────▼──────────────────────────────┐
│                   API LAYER (FastAPI)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ REST Endpoints | WebSocket | Event Streaming        │  │
│  │ Auth | Trades | Portfolio | Risk | Signals | Ops    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
      ┌────▼──────────┐         ┌─────────────▼────┐
      │  PostgreSQL   │         │  Message Queue   │
      │  (State)      │         │  (Events)        │
      └───────────────┘         └──────────────────┘
```

## Component Architecture

### 1. Backend Server

**Location**: `/backend`

**Responsibilities**:
- REST API endpoint serving
- Business logic execution
- Data persistence
- Event management
- Session management

**Key Components**:

```
backend/
├── main.py                 # FastAPI app initialization
├── config.py              # Configuration management
├── api/
│   ├── routes/
│   │   ├── auth.py        # Authentication endpoints
│   │   ├── trades.py      # Trade management
│   │   ├── portfolio.py   # Portfolio analytics
│   │   ├── risk.py        # Risk management
│   │   ├── signals.py     # Signal management
│   │   ├── agents.py      # AI agent endpoints
│   │   ├── operations.py  # Operations endpoints
│   │   └── ...
│   └── dependencies.py    # Service dependencies
├── db/
│   ├── session.py         # Database session management
│   └── base.py            # Base model definition
├── models/                # SQLAlchemy ORM models
│   ├── user.py
│   ├── trade.py
│   ├── portfolio.py
│   ├── signal.py
│   ├── agent.py
│   └── ...
├── schemas/               # Pydantic request/response models
├── services/
│   ├── decision/          # Decision making service
│   ├── execution/         # Trade execution service
│   ├── risk/              # Risk calculation service
│   └── ...
├── core/
│   ├── auth_service.py    # Authentication logic
│   ├── signal_service.py  # Signal generation
│   ├── trade_service.py   # Trade management
│   ├── learning_engine.py # ML/AI engine
│   └── feature_gate.py    # Feature flags
├── utils/
│   ├── logger.py          # Structured logging
│   ├── security.py        # Security utilities
│   ├── rate_limit.py      # Rate limiting
│   └── ...
└── infrastructure/
    ├── messaging/         # Message queue
    ├── telemetry/         # Monitoring
    └── ...
```

### 2. Web Console

**Location**: `/server/frontend`

**Technology**: React 18 + Vite + Tailwind CSS

**Features**:
- Admin dashboard
- Trading console
- Performance analytics
- Risk monitoring
- User management

**Architecture**:

```
frontend/
├── src/
│   ├── App.jsx                      # Main app component
│   ├── AppAdmin.jsx                 # Admin dashboard
│   ├── main.jsx                     # Entry point
│   ├── api/
│   │   ├── api.jsx                  # API client
│   │   └── axios.js                 # Axios instance
│   ├── components/
│   │   ├── Dashboard.jsx            # Main dashboard
│   │   ├── TradingEditor.jsx        # Trading interface
│   │   ├── AdminPanel.jsx           # Admin controls
│   │   ├── Community.jsx            # Community features
│   │   ├── agents.jsx               # Agent management
│   │   ├── operations.jsx           # Operations dashboard
│   │   ├── risk.jsx                 # Risk monitoring
│   │   ├── performance_audit.jsx    # Performance analytics
│   │   ├── users_licenses.jsx       # User/license management
│   │   ├── Login.jsx                # Login page
│   │   ├── Layout.jsx               # Layout wrapper
│   │   └── ...
│   ├── context/                     # Global state management
│   ├── hooks/                       # Custom React hooks
│   └── styles/                      # Styling
├── dist/                            # Built assets (generated)
├── public/                          # Static assets
└── package.json
```

### 3. Desktop Application

**Location**: `/desktop`

**Technology**: PySide6 (Qt Python bindings)

**Features**:
- Advanced trading tools
- Local strategy execution
- Real-time market data visualization
- Advanced analytics

**Architecture**:

```
desktop/
├── main.py                          # Entry point
├── src/
│   ├── main/
│   │   ├── main.py                  # Main window
│   │   └── app.py                   # Application initialization
│   ├── ui/
│   │   ├── main_window.py           # Main UI window
│   │   ├── components/
│   │   │   ├── trading_panel.py     # Trading interface
│   │   │   ├── chart_widget.py      # Chart visualization
│   │   │   ├── portfolio_view.py    # Portfolio view
│   │   │   └── ...
│   │   └── dialogs/
│   │       ├── auth_dialog.py       # Authentication
│   │       ├── trade_dialog.py      # Trade entry
│   │       └── ...
│   ├── core/
│   │   ├── trading_engine.py        # Trading logic
│   │   ├── market_data.py           # Market data handling
│   │   ├── strategy.py              # Strategy management
│   │   └── ...
│   ├── config/
│   │   ├── settings.py              # Configuration
│   │   └── constants.py             # Constants
│   ├── services/
│   │   ├── broker_service.py        # Broker communication
│   │   └── server_api_client.py     # Server API client
│   ├── utils/
│   │   ├── logger.py                # Logging
│   │   ├── validators.py            # Data validation
│   │   └── ...
│   └── security/
│       ├── auth_manager.py          # Authentication
│       ├── encryption.py            # Encryption utilities
│       └── license_manager.py       # License management
└── requirements.txt
```

## Data Flow

### 1. Trade Execution Flow

```
┌─────────────────┐
│ User Action     │
│ (Desktop/Web)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ Client Interface        │
│ (React/PySide6 UI)      │
└────────┬────────────────┘
         │ HTTP POST /api/v1/trades
         │
         ▼
┌─────────────────────────┐
│ FastAPI Endpoint        │
│ (Trade creation route)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Request Validation      │
│ (Pydantic schema)       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Risk Check              │
│ (Risk service)          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Trade Execution         │
│ (Execution service)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Database Persistence    │
│ (SQLAlchemy → PostgreSQL)
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Event Emission          │
│ (Kafka → WebSocket)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Client Notification     │
│ (Real-time update)      │
└─────────────────────────┘
```

### 2. Risk Management Flow

```
Market Data ──┐
             ▼
Portfolio Data → Risk Calculation Service
             ▼
         Risk Metrics
             ▼
         Limit Check
             ▼
    ┌─────────┴─────────┐
    │                   │
    ▼ (OK)          ▼ (BREACH)
Execute Trade     Alert User
    │             + Prevent
    │             + Log Event
    │                   │
    └─────────┬─────────┘
              ▼
         Audit Log
```

## Technology Stack

### Backend
- **Framework**: FastAPI
- **Runtime**: Python 3.11
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy
- **Async**: asyncio
- **Validation**: Pydantic
- **Documentation**: Swagger/OpenAPI

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **State Management**: Context API
- **Charts**: Chart.js or Recharts

### Desktop
- **Framework**: PySide6 (Qt)
- **Python**: 3.11
- **HTTP**: aiohttp
- **Database**: SQLite (local cache)
- **Charts**: PyQtGraph or Plotly

### DevOps
- **Containerization**: Docker
- **Orchestration**: Docker Compose / Kubernetes
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus/Grafana (optional)

## Database Schema

### Core Tables

**Users**
```sql
id (UUID)
username (String)
email (String)
password_hash (String)
role (Enum: ADMIN, USER, OPERATOR)
permissions (JSON)
created_at (Timestamp)
updated_at (Timestamp)
```

**Trades**
```sql
id (UUID)
user_id (FK)
symbol (String)
side (Enum: BUY, SELL)
quantity (Decimal)
entry_price (Decimal)
exit_price (Decimal)
status (Enum: OPEN, CLOSED, CANCELLED)
pnl (Decimal)
created_at (Timestamp)
closed_at (Timestamp)
```

**Portfolio**
```sql
id (UUID)
user_id (FK)
total_value (Decimal)
cash (Decimal)
invested (Decimal)
total_pnl (Decimal)
last_updated (Timestamp)
```

**Signals**
```sql
id (UUID)
symbol (String)
direction (Enum: BUY, SELL)
confidence (Float)
source (String)
timestamp (Timestamp)
status (Enum: ACTIVE, EXECUTED, EXPIRED)
```

**Agents**
```sql
id (UUID)
user_id (FK)
name (String)
strategy (String)
status (Enum: ACTIVE, INACTIVE, ERROR)
config (JSON)
performance_metrics (JSON)
created_at (Timestamp)
```

### Relationships

```
User (1) ──── (N) Trades
User (1) ──── (N) Signals
User (1) ──── (N) Agents
User (1) ──── (1) Portfolio
Trades (N) ── (1) Signal (optional)
Agents (N) ── (N) Signals
```

## Security Architecture

### Authentication

```
Client Login
    ↓
Validate Credentials
    ↓
Generate JWT Token
    ↓
Return Access & Refresh Tokens
    ↓
Client stores in secure storage
```

### Authorization

```
Request with Token
    ↓
Validate Token Signature
    ↓
Extract Claims & Permissions
    ↓
Check Resource Access
    ↓
Grant/Deny Access
```

### Encryption

- **Transport**: TLS/SSL (HTTPS)
- **Credentials**: Password hashing (bcrypt)
- **Sensitive Data**: AES-256 encryption
- **API Keys**: Encrypted storage

### API Security

```
CORS Enabled ─────────────────> Allow trusted origins
Rate Limiting ────────────────> Prevent abuse
Input Validation ──────────────> Prevent injection
Output Escaping ───────────────> Prevent XSS
CSRF Protection ───────────────> Token validation
Audit Logging ─────────────────> Track actions
```

## Scalability Considerations

### Horizontal Scaling

```
Load Balancer
     │
     ├─────────────── API Instance 1
     ├─────────────── API Instance 2
     └─────────────── API Instance 3
     
     (Shared Database)
```

### Caching Strategy

- **In-Memory**: Redis for session/cache
- **Database**: Query result caching
- **HTTP**: ETag for static resources
- **CDN**: Static assets distribution

### Performance Optimization

- Connection pooling
- Query optimization
- Async operations
- Caching layer
- Database indexing

---

**Last Updated**: April 2026
