# TradeAdviser Architecture

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Layers](#architecture-layers)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Technology Stack](#technology-stack)
6. [Design Patterns](#design-patterns)
7. [Scalability & Performance](#scalability--performance)
8. [Security Architecture](#security-architecture)

---

## System Overview

TradeAdviser is a full-stack trading advisory application built on a modern, layered architecture. The system separates concerns into distinct layers: Presentation, API, Business Logic, and Data Access.

### High-Level Diagram

For detailed architecture diagrams with Mermaid visualizations, see [SYSTEM_ARCHITECTURE_DIAGRAMS.md](SYSTEM_ARCHITECTURE_DIAGRAMS.md).

```
┌─────────────────────────────────────────────────────────────┐
│                   Presentation Layer                        │
│          React + Vite Frontend (Port 5173/4173)             │
│                 - User Interface                            │
│                 - State Management                          │
│                 - Client-side Routing                       │
└────────────────────────┬──────────────────────────────────────┘
                         │ HTTP/WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│                   API Layer                                 │
│        FastAPI Backend (Port 8000)                          │
│    - RESTful API Endpoints                                  │
│    - WebSocket Connections                                 │
│    - Request/Response Validation                           │
│    - Error Handling                                        │
└─────────────────────────┬───────────────────────────────────┘
                         │
┌─────────────────────────▼───────────────────────────────────┐
│               Business Logic Layer                          │
│    - Service Classes                                        │
│    - AI Agent Framework                                    │
│    - Business Rules                                        │
│    - Domain Models                                         │
└─────────────────────────┬───────────────────────────────────┘
                         │
┌─────────────────────────▼───────────────────────────────────┐
│              Data Access & Infrastructure                   │
│    - Database Models (SQLAlchemy)                          │
│    - Repository Pattern                                    │
│    - Event Bus & Messaging                                 │
│    - Authentication & Authorization                       │
└─────────────────────────┬───────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Database │    │Kafka/   │    │External │
    │         │    │EventBus │    │Services │
    └─────────┘    └─────────┘    └─────────┘
```

---

## Architecture Layers

### 1. Presentation Layer

**Technology**: React 18, Vite, CSS Modules

**Responsibilities**:
- Render user interface components
- Manage client-side state (React Context)
- Handle user interactions
- Navigation and routing
- Form validation (client-side)
- WebSocket connections for real-time updates

**Key Directories**:
```
frontend/src/
├── components/        # Reusable React components
├── pages/            # Page-level components
├── context/          # React context providers
├── hooks/            # Custom React hooks
├── api/              # API client utilities
├── assets/           # Static assets
└── styles/           # Global and component styles
```

### 2. API Layer

**Technology**: FastAPI, Pydantic, CORS Middleware

**Responsibilities**:
- HTTP request routing
- Request/response validation
- Authentication & authorization
- Error handling and logging
- WebSocket management
- API documentation (auto-generated)

**Key Routes**:
```
/api/auth/              - Authentication endpoints
/api/trades/            - Trade management
/api/portfolio/         - Portfolio operations
/api/risk/              - Risk analysis
/api/signals/           - Signal generation
/api/performance/       - Performance metrics
/api/agents/            - Agent management
/api/admin/             - Admin operations
/api/workspace/         - Workspace management
```

**Key Files**:
```
backend/api/
├── routes/
│   ├── auth.py
│   ├── trades.py
│   ├── portfolio.py
│   ├── risk.py
│   ├── signals.py
│   ├── performance.py
│   ├── agents.py
│   ├── admin.py
│   └── ...
└── _auth_helpers.py    # Authentication utilities
```

### 3. Business Logic Layer

**Technology**: Python, Design Patterns (Service, Repository)

**Responsibilities**:
- Implement business rules
- Orchestrate services
- Process trading signals
- Risk calculations
- Performance tracking
- Agent decision-making

**Service Classes**:

```python
TradingService
├── execute_trade()
├── cancel_trade()
├── list_trades()
└── get_trade_details()

RiskService
├── analyze_portfolio_risk()
├── calculate_var()
├── calculate_sharpe_ratio()
└── get_risk_metrics()

PortfolioService
├── get_portfolio_overview()
├── get_positions()
├── rebalance_portfolio()
└── calculate_allocation()

DecisionService
├── generate_recommendation()
├── evaluate_signal()
└── validate_trade()

ExecutionService
├── execute_market_order()
├── execute_limit_order()
└── monitor_execution()

SignalService
├── generate_signals()
├── validate_signal()
└── backtest_signal()
```

**Key Directory**:
```
backend/services/
├── decision/
│   └── service.py
├── execution/
│   └── service.py
└── risk/
    └── service.py
```

### 4. Data Access Layer

**Technology**: SQLAlchemy ORM, Repository Pattern

**Responsibilities**:
- Database model definitions
- CRUD operations
- Query optimization
- Data persistence
- Transaction management

**Models**:
```
backend/models/
├── user.py           # User model
├── trade.py          # Trade model
├── signal.py         # Signal model
├── agent.py          # Agent execution log
├── audit.py          # Audit log
├── license.py        # License information
└── operations.py     # Operations log
```

### 5. Infrastructure Layer

**Technology**: Event Bus, Logging, Authentication

**Responsibilities**:
- Event publishing and subscription
- Logging and monitoring
- Authentication & authorization
- Rate limiting
- Session management
- WebSocket connection management

**Key Components**:
```
backend/infrastructure/
├── messaging/
│   └── event_bus.py          # Event publishing system
└── telemetry/
    └── logging.py            # Centralized logging

backend/utils/
├── security.py               # Security utilities
├── rate_limit.py            # Rate limiting
├── logger.py                # Logger configuration
└── ...

backend/core/
├── auth_service.py          # Authentication service
├── feature_gate.py          # Feature flags
├── learning_engine.py       # Learning capabilities
└── ...
```

---

## Core Components

### AI Agent Framework

**Components**:
- **RegimeAgent**: Analyzes market regimes and adapts strategies
- **FeedbackAgent**: Processes feedback and learns from past trades

**Location**: `backend/agents/`

```python
# Example agent workflow
regime_agent.analyze_market()
regime_agent.suggest_strategy()
feedback_agent.learn_from_trade(trade_result)
```

### Event Bus

**Purpose**: Decoupled communication between services

**Events**:
```
TradeExecutedEvent
RiskThresholdBreachedEvent
PortfolioRebalancedEvent
SignalGeneratedEvent
AgentDecisionEvent
```

**Location**: `backend/infrastructure/messaging/event_bus.py`

### Database

**ORM**: SQLAlchemy
**Databases Supported**:
- SQLite (development)
- PostgreSQL (production)

**Schema**:
```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255),
    role VARCHAR(50),
    created_at TIMESTAMP
);

-- Trades
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    symbol VARCHAR(50),
    quantity DECIMAL(18,8),
    entry_price DECIMAL(18,8),
    exit_price DECIMAL(18,8),
    status VARCHAR(50),
    executed_at TIMESTAMP
);

-- Signals
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    signal_type VARCHAR(50),
    symbol VARCHAR(50),
    strength FLOAT,
    confidence FLOAT,
    generated_at TIMESTAMP
);

-- And more...
```

---

## Data Flow

### User Authentication Flow

```
1. User submits credentials
   └─> Frontend sends POST /api/auth/login
       └─> FastAPI validates credentials
           └─> Database lookup for user
               └─> JWT token generation
                   └─> Return token + user data
                       └─> Frontend stores token in localStorage
```

### Trading Execution Flow

```
1. User submits trade order
   └─> Frontend validates form
       └─> POST /api/trades
           └─> API validates request
               └─> TradingService.execute_trade()
                   └─> DecisionService validates decision
                       └─> ExecutionService executes trade
                           └─> Database persists trade
                               └─> EventBus publishes TradeExecutedEvent
                                   └─> RiskService analyzes impact
                                       └─> WebSocket updates connected clients
```

### Signal Generation Flow

```
1. Market data received
   └─> SignalService.generate_signals()
       └─> Historical analysis
           └─> Technical indicators
               └─> ML model inference
                   └─> Signal ranking
                       └─> Database persistence
                           └─> EventBus publishes SignalGeneratedEvent
                               └─> WebSocket notifies subscribed users
```

### Risk Analysis Flow

```
1. Portfolio risk check (periodic)
   └─> RiskService.analyze_portfolio_risk()
       └─> Fetch current positions
           └─> Calculate VaR
               └─> Calculate Sharpe ratio
                   └─> Check risk thresholds
                       └─> If exceeded: EventBus publishes RiskThresholdBreachedEvent
                           └─> Notify user via WebSocket + email
```

---

## Technology Stack

### Backend

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | FastAPI | 0.100+ |
| ORM | SQLAlchemy | 2.0+ |
| Validation | Pydantic | 2.0+ |
| Database | PostgreSQL/SQLite | 13+/3.8+ |
| Async | AsyncIO | Built-in |
| Messaging | Kafka (optional) | 3.0+ |
| Authentication | OAuth2 + JWT | - |
| Testing | Pytest | 7.0+ |

### Frontend

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | React | 18.3+ |
| Build Tool | Vite | 5.0+ |
| HTTP Client | Axios | 1.4+ |
| State Management | React Context | Built-in |
| Styling | CSS Modules | Built-in |
| Testing | Jest/React Testing Library | Latest |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Containerization | Docker |
| Orchestration | Docker Compose |
| Web Server | Uvicorn |
| Reverse Proxy | Nginx (optional) |
| Monitoring | Application Insights (optional) |
| Logging | Python logging + ELK (optional) |

---

## Design Patterns

### 1. Service Layer Pattern

Encapsulates business logic in service classes:

```python
class TradingService:
    def execute_trade(self, trade_request: TradeRequest) -> Trade:
        # Validate
        # Process
        # Persist
        # Publish event
        pass
```

### 2. Repository Pattern

Abstracts data access:

```python
class TradeRepository:
    def save(self, trade: Trade) -> Trade
    def find_by_id(self, trade_id: int) -> Trade
    def find_all(self, user_id: int) -> List[Trade]
```

### 3. Event-Driven Architecture

Decouples services through events:

```python
event_bus.publish(TradeExecutedEvent(trade_id=123))
event_bus.subscribe(TradeExecutedEvent, risk_service.on_trade_executed)
```

### 4. Dependency Injection

FastAPI's dependency system:

```python
@router.post("/trades")
async def create_trade(
    trade_req: TradeRequest,
    service: TradingService = Depends(get_trading_service)
):
    pass
```

### 5. Middleware Pattern

CORS, Authentication, Logging:

```python
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(JWTMiddleware, ...)
```

---

## Scalability & Performance

### Horizontal Scaling

- **Stateless Services**: All services are stateless
- **Load Balancing**: Deploy behind Nginx/HAProxy
- **Database**: Connection pooling with SQLAlchemy
- **Caching**: Redis (optional) for session/token caching

### Vertical Scaling

- **Async Operations**: FastAPI uses asyncio for non-blocking I/O
- **Worker Processes**: Uvicorn with multiple workers
- **Database Optimization**: Indexed queries, connection pooling

### Performance Optimization

- **Query Optimization**: Strategic database indexes
- **Caching**: HTTP caching headers, Redis caching
- **Pagination**: Large result sets paginated
- **Rate Limiting**: Prevent abuse and ensure fair usage
- **Compression**: gzip compression for responses

### Monitoring & Observability

```
Application Insights (optional)
├── Request/Response times
├── Error rates
├── Database query performance
├── API endpoint metrics
└── User behavior tracking

Logging Strategy
├── Access logs (all requests)
├── Application logs (INFO, WARN, ERROR)
├── Audit logs (user actions, trades)
└── Performance logs (slow queries, slow endpoints)
```

---

## Security Architecture

### Authentication

**Method**: OAuth 2.0 + JWT

```python
# Flow
1. User credentials sent to /api/auth/login
2. Backend validates credentials
3. JWT token generated (access + refresh)
4. Token stored client-side
5. Subsequent requests include token in Authorization header
```

### Authorization

**Method**: Role-Based Access Control (RBAC)

```python
Roles:
- admin      # Full system access
- trader     # Trading operations
- viewer     # Read-only access
- agent      # AI agent operations
```

### API Security

```
Features:
- CORS validation (frontend URL whitelist)
- CSRF protection (if using sessions)
- Rate limiting (prevent abuse)
- Input validation (Pydantic)
- SQL injection prevention (SQLAlchemy ORM)
- XSS protection (React escapes by default)
```

### Data Security

```
- Passwords: bcrypt hashing
- Sensitive data: Encryption at rest (optional)
- API keys: Secure storage in environment variables
- Database: SSL/TLS connections
- Frontend: HTTPS only (production)
```

### License Management

```
License verification:
1. User provides license key
2. Backend validates license format
3. Check license expiration
4. Check feature entitlements
5. Persist license info
```

---

## Deployment Architecture

### Development

```
Local Machine
├── Backend (FastAPI on localhost:8000)
├── Frontend (Vite on localhost:5173)
└── SQLite Database
```

### Production

```
Cloud Provider (AWS/Azure/GCP)
├── Load Balancer
│   └─> Reverse Proxy (Nginx)
│       └─> Container Orchestration (Kubernetes or Docker Swarm)
│           ├─> Backend Instances (FastAPI in Docker)
│           └─> Frontend (Static hosting or CDN)
├── Managed Database (PostgreSQL)
├── Cache Layer (Redis) - optional
├── Message Queue (Kafka) - optional
└── Monitoring & Logging (CloudWatch/Application Insights)
```

### Docker Compose (Local Production-like)

```yaml
version: '3.8'
services:
  backend:
    build: ./docker/Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
  
  frontend:
    build: ./docker/Dockerfile.frontend
    ports:
      - "4173:4173"
  
  database:
    image: postgres:15
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

---

## Integration Points

### External Services

- **Authentication**: OAuth providers (Google, GitHub)
- **Payment**: Stripe, PayPal (future)
- **Email**: SendGrid, AWS SES
- **SMS**: Twilio (optional alerts)
- **Market Data**: Alpha Vantage, Yahoo Finance API
- **Charting**: Chart.js, TradingView Lightweight Charts

---

## API Contract

### Request/Response Format

```json
// Request
{
  "symbol": "AAPL",
  "quantity": 100,
  "price": 150.50,
  "trade_type": "BUY"
}

// Response
{
  "id": 123,
  "user_id": 45,
  "symbol": "AAPL",
  "quantity": 100,
  "entry_price": 150.50,
  "status": "EXECUTED",
  "executed_at": "2026-04-19T10:30:00Z"
}

// Error Response
{
  "detail": "Insufficient funds for trade",
  "error_code": "INSUFFICIENT_FUNDS",
  "status_code": 400
}
```

---

## Development Workflow

### Local Development

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn main:app --reload

# Terminal 2: Frontend (hot reload)
cd frontend
npm run dev

# Terminal 3: Database (if using PostgreSQL)
docker run -d -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15
```

### Testing

```bash
# Backend unit tests
pytest backend/tests/

# Frontend unit tests
npm test

# Integration tests
pytest backend/tests/integration/

# E2E tests (optional)
npx cypress run
```

---

## Future Improvements

- [ ] GraphQL API (alongside REST)
- [ ] Real-time market data integration
- [ ] Advanced ML models for predictions
- [ ] Multi-language support (i18n)
- [ ] Mobile app (React Native)
- [ ] Kubernetes deployment manifests
- [ ] Microservices architecture (if scaling beyond monolith)
- [ ] Advanced caching strategies
- [ ] Circuit breaker patterns
- [ ] Event sourcing for audit trails

---

**Last Updated**: April 2026
