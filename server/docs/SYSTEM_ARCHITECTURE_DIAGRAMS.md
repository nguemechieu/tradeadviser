# TradeAdviser System Architecture Diagram

This document contains detailed architecture diagrams for the TradeAdviser system.

## High-Level Architecture

```mermaid
graph TB
    User["👤 Users/Traders"]
    Browser["🌐 Web Browser"]
    
    subgraph Frontend["Frontend Layer (React + Vite)"]
        UI["UI Components"]
        State["State Management<br/>React Context"]
        API["API Client<br/>Axios"]
    end
    
    subgraph LoadBalancer["Load Balancer<br/>Nginx"]
        LB["Reverse Proxy<br/>Rate Limiting"]
    end
    
    subgraph Backend["Backend Layer (FastAPI)"]
        Routes["API Routes<br/>REST Endpoints"]
        Auth["Authentication<br/>JWT/OAuth2"]
        Services["Business Services<br/>Trading, Risk, Portfolio"]
        Agents["AI Agents<br/>Regime, Feedback"]
        EventBus["Event Bus<br/>Async Events"]
    end
    
    subgraph Infrastructure["Infrastructure Layer"]
        DB["PostgreSQL<br/>Database"]
        Cache["Redis<br/>Cache Layer"]
        Queue["Kafka/Queue<br/>Message Broker"]
    end
    
    User -->|Login/Browse| Browser
    Browser -->|HTTP/WebSocket| Frontend
    Frontend -->|REST API| LoadBalancer
    LoadBalancer -->|HTTP/WS| Backend
    
    Backend -->|Sync| Services
    Backend -->|Sync| Agents
    Services -->|Publish| EventBus
    Agents -->|Publish| EventBus
    
    Routes -->|Query/Update| DB
    Services -->|Query/Update| DB
    EventBus -->|Async| Queue
    Services -->|Cache| Cache
    
    EventBus -->|Subscribe| Services
```

## Component Interaction Diagram

```mermaid
graph LR
    Client["Client Request"]
    
    Client -->|1. HTTP Request| APIGateway["API Gateway"]
    APIGateway -->|2. Route| Auth{Auth Check}
    
    Auth -->|Invalid| Reject["❌ Reject"]
    Auth -->|Valid| Service["Service Layer"]
    
    Service -->|Validate| Business["Business Logic"]
    Business -->|Execute| Decision["Decision Making"]
    Decision -->|Agent| AI["AI Agent"]
    Decision -->|Persist| DB[("Database")]
    
    AI -->|Event| EventBus["Event Bus"]
    EventBus -->|Notify| RiskService["Risk Service"]
    EventBus -->|Notify| PortfolioService["Portfolio Service"]
    
    Service -->|Response| Client
    RiskService -->|WebSocket| Client
    PortfolioService -->|WebSocket| Client
```

## Data Flow Architecture

```mermaid
graph TB
    subgraph Input["Input Sources"]
        UserAction["User Actions"]
        MarketData["Market Data"]
        Events["System Events"]
    end
    
    subgraph Processing["Processing Layer"]
        APIEndpoint["API Endpoint"]
        Validator["Request Validator"]
        ServiceLogic["Service Logic"]
        AIEngine["AI Engine"]
    end
    
    subgraph Storage["Storage Layer"]
        PrimaryDB["Primary DB<br/>Trades, Users, Portfolio"]
        Cache["Cache<br/>Session, Signals"]
        Archive["Archive<br/>Historical Data"]
    end
    
    subgraph Output["Output Channels"]
        API["REST API Response"]
        WebSocket["WebSocket Events"]
        Email["Email Alerts"]
        Reports["Reports"]
    end
    
    UserAction -->|Form Submit| APIEndpoint
    MarketData -->|Feed| AIEngine
    Events -->|Trigger| ServiceLogic
    
    APIEndpoint -->|Sanitize| Validator
    Validator -->|Process| ServiceLogic
    ServiceLogic -->|Decision| AIEngine
    
    ServiceLogic -->|Write| PrimaryDB
    ServiceLogic -->|Cache| Cache
    PrimaryDB -->|Archive| Archive
    
    ServiceLogic -->|JSON| API
    AIEngine -->|Events| WebSocket
    ServiceLogic -->|Alert| Email
    PrimaryDB -->|Generate| Reports
    
    API -->|Response| UserAction
    WebSocket -->|Update| UserAction
    Email -->|Notification| UserAction
```

## Database Schema Relationship

```mermaid
erDiagram
    USERS ||--o{ TRADES : places
    USERS ||--o{ PORTFOLIOS : manages
    USERS ||--o{ SIGNALS : receives
    USERS ||--o{ SESSIONS : creates
    USERS ||--o{ LICENSES : owns
    
    TRADES ||--o{ PERFORMANCE : affects
    TRADES ||--o{ AUDIT_LOG : logged_in
    
    PORTFOLIOS ||--o{ POSITIONS : contains
    PORTFOLIOS ||--o{ HOLDINGS : has
    
    SIGNALS ||--o{ TRADES : generates
    SIGNALS ||--o{ PERFORMANCE : affects
    
    AGENTS ||--o{ TRADES : recommends
    AGENTS ||--o{ SIGNALS : creates
    
    PERFORMANCE ||--o{ AUDIT_LOG : recorded_in

    USERS : int id
    USERS : string username
    USERS : string email
    USERS : string role
    USERS : datetime created_at

    TRADES : int id
    TRADES : int user_id
    TRADES : string symbol
    TRADES : decimal quantity
    TRADES : decimal price
    TRADES : string status
    TRADES : datetime executed_at

    PORTFOLIOS : int id
    PORTFOLIOS : int user_id
    PORTFOLIOS : decimal total_value
    PORTFOLIOS : decimal cash

    SIGNALS : int id
    SIGNALS : int user_id
    SIGNALS : string symbol
    SIGNALS : float strength
    SIGNALS : datetime generated_at

    PERFORMANCE : int id
    PERFORMANCE : int user_id
    PERFORMANCE : decimal roi
    PERFORMANCE : datetime period_end

    AGENTS : int id
    AGENTS : string name
    AGENTS : string type
    AGENTS : boolean enabled

    AUDIT_LOG : int id
    AUDIT_LOG : int user_id
    AUDIT_LOG : string action
    AUDIT_LOG : datetime timestamp

    LICENSES : int id
    LICENSES : int user_id
    LICENSES : string key
    LICENSES : datetime expires_at

    SESSIONS : int id
    SESSIONS : int user_id
    SESSIONS : string token
    SESSIONS : datetime expires_at

    POSITIONS : int id
    POSITIONS : int portfolio_id
    POSITIONS : string symbol
    POSITIONS : decimal quantity

    HOLDINGS : int id
    HOLDINGS : int portfolio_id
    HOLDINGS : string asset_type
    HOLDINGS : decimal amount
```

## Deployment Architecture

```mermaid
graph TB
    subgraph Dev["Development Environment"]
        DevFE["Frontend<br/>Vite Dev"]
        DevBE["Backend<br/>Uvicorn"]
        DevDB["Database<br/>SQLite"]
    end
    
    subgraph Staging["Staging Environment"]
        StagingLB["Load Balancer"]
        StagingFE["Frontend<br/>Nginx"]
        StagingBE["Backend<br/>Gunicorn"]
        StagingDB["PostgreSQL"]
        StagingCache["Redis"]
    end
    
    subgraph Production["Production Environment"]
        ProdCDN["CDN<br/>CloudFlare"]
        ProdLB["Load Balancer<br/>Application Gateway"]
        ProdFE["Frontend<br/>Multiple Instances"]
        ProdBE["Backend<br/>Multiple Instances"]
        ProdDB["PostgreSQL<br/>High Availability"]
        ProdCache["Redis Cluster"]
        ProdQueue["Kafka Cluster"]
        ProdMonitor["Monitoring<br/>Application Insights"]
    end
    
    Dev -->|Push to main| Staging
    Staging -->|Approval| Production
    
    ProdCDN -->|Cache| ProdFE
    ProdLB -->|Route| ProdFE
    ProdLB -->|Route| ProdBE
    ProdFE -->|API Calls| ProdBE
    ProdBE -->|Query| ProdDB
    ProdBE -->|Cache| ProdCache
    ProdBE -->|Events| ProdQueue
    ProdBE -->|Metrics| ProdMonitor
```

## Security Architecture

```mermaid
graph TB
    Client["Client Request"]
    
    Client -->|1. HTTPS| WAF["Web Application<br/>Firewall"]
    WAF -->|2. Validate| CORS["CORS Policy<br/>Check"]
    CORS -->|3. Check| RateLimit["Rate Limiter<br/>DDoS Protection"]
    RateLimit -->|4. Extract| JWT["JWT Token<br/>Extraction"]
    JWT -->|5. Validate| AuthService["Authentication<br/>Service"]
    
    AuthService -->|Invalid| Reject["❌ Reject"]
    AuthService -->|Valid| RBAC["RBAC Check<br/>Authorization"]
    
    RBAC -->|No Access| Forbidden["❌ Forbidden"]
    RBAC -->|Allowed| Service["Service Layer"]
    
    Service -->|Query| DB[("Database<br/>Encrypted")]
    Service -->|Audit| AuditLog["Audit Log"]
    
    Service -->|Response| Encrypt["Encrypt<br/>Response"]
    Encrypt -->|Return| Client
    
    AuthService -->|Store| SecureToken["Secure Token<br/>Storage"]
```

## Scaling Strategy

```mermaid
graph TB
    subgraph Horizontal["Horizontal Scaling"]
        LB["Load Balancer"]
        BE1["Backend 1"]
        BE2["Backend 2"]
        BE3["Backend N"]
        
        LB -->|Round Robin| BE1
        LB -->|Round Robin| BE2
        LB -->|Round Robin| BE3
    end
    
    subgraph Vertical["Vertical Scaling"]
        Memory["Increase Memory"]
        CPU["Increase CPU"]
        Storage["Increase Storage"]
    end
    
    subgraph Caching["Caching Strategy"]
        L1["L1: Browser Cache"]
        L2["L2: CDN Cache"]
        L3["L3: Redis Cache"]
        L4["L4: DB Cache"]
    end
    
    Horizontal -->|For APIs| Vertical
    Vertical -->|Improves| Caching
    Caching -->|Reduces| DBLoad["Database Load"]
```

## Event Flow Architecture

```mermaid
graph LR
    subgraph Events["System Events"]
        TradeEvent["Trade Executed"]
        SignalEvent["Signal Generated"]
        RiskEvent["Risk Threshold"]
        PortfolioEvent["Portfolio Updated"]
    end
    
    subgraph EventBus["Event Bus<br/>Kafka"]
        TopicTrade["trades-topic"]
        TopicSignal["signals-topic"]
        TopicRisk["risk-topic"]
    end
    
    subgraph Subscribers["Event Subscribers"]
        RiskService["Risk Service"]
        PortfolioService["Portfolio Service"]
        AuditService["Audit Service"]
        NotificationService["Notification Service"]
    end
    
    subgraph Actions["Triggered Actions"]
        Rebalance["Portfolio Rebalance"]
        Alert["Risk Alert"]
        Log["Audit Log"]
        Notify["Send Notification"]
    end
    
    TradeEvent -->|Publish| TopicTrade
    SignalEvent -->|Publish| TopicSignal
    RiskEvent -->|Publish| TopicRisk
    
    TopicTrade -->|Subscribe| RiskService
    TopicTrade -->|Subscribe| AuditService
    TopicRisk -->|Subscribe| NotificationService
    TopicSignal -->|Subscribe| PortfolioService
    
    RiskService -->|Execute| Rebalance
    RiskService -->|Trigger| Alert
    AuditService -->|Create| Log
    NotificationService -->|Send| Notify
```

---

## Architecture Decisions

### Why This Architecture?

1. **Separation of Concerns**: Frontend, API, Business Logic, and Data Access are clearly separated
2. **Scalability**: Stateless services can be scaled horizontally
3. **Maintainability**: Clear module boundaries and responsibilities
4. **Testability**: Each layer can be tested independently
5. **Performance**: Caching and async processing optimize throughput
6. **Security**: Multiple layers of security (WAF, CORS, RBAC, encryption)
7. **Reliability**: Load balancing, redundancy, and failover capabilities

### Technology Choices

| Component | Technology | Reason |
|-----------|-----------|--------|
| Frontend | React + Vite | Modern, fast build tool, great DX |
| Backend | FastAPI | High performance, async support, auto docs |
| Database | PostgreSQL | Robust ACID compliance, JSON support |
| Cache | Redis | High performance, many data structures |
| Queue | Kafka | Distributed, fault-tolerant event streaming |
| Container | Docker | Consistency across environments |
| Reverse Proxy | Nginx | High performance, flexible routing |

---

**Last Updated**: April 2026
