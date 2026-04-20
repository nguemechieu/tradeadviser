# API Reference

Complete reference for TradeAdviser REST API endpoints.

## Table of Contents

- [Base URL](#base-url)
- [Authentication](#authentication)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)

## Base URL

```
http://localhost:8000/api/v1
```

Or in production:
```
https://yourdomain.com/api/v1
```

## Authentication

### JWT Token Authentication

All endpoints require a Bearer token in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/trades
```

### Obtaining a Token

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "secure_password"
}
```

Response:
```json
{
  "access_token": "<your_jwt_token_here>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your_refresh_token"
}
```

## Response Format

### Success Response (200 OK)

```json
{
  "data": { /* endpoint-specific data */ },
  "meta": {
    "timestamp": "2026-04-20T10:30:00Z",
    "version": "1.0.0"
  }
}
```

### Paginated Response

```json
{
  "data": [
    { /* item 1 */ },
    { /* item 2 */ }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8
  },
  "meta": {
    "timestamp": "2026-04-20T10:30:00Z"
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  },
  "meta": {
    "timestamp": "2026-04-20T10:30:00Z"
  }
}
```

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created |
| 204 | No Content - Success, no content to return |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |

### Error Codes

| Code | Description |
|------|-------------|
| INVALID_REQUEST | Request parameters invalid |
| UNAUTHORIZED | Authentication failed |
| FORBIDDEN | Insufficient permissions |
| NOT_FOUND | Resource not found |
| DUPLICATE | Resource already exists |
| RATE_LIMIT | Rate limit exceeded |
| INTERNAL_ERROR | Server error |

## Endpoints

### Authentication

#### POST /auth/login
Login with credentials.

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password"
}
```

**Response**: `200 OK`
```json
{
  "access_token": "token...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### POST /auth/logout
Logout current session.

```http
POST /api/v1/auth/logout
Authorization: Bearer token
```

**Response**: `204 No Content`

#### GET /auth/me
Get current user information.

```http
GET /api/v1/auth/me
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "id": "user_123",
  "username": "user@example.com",
  "email": "user@example.com",
  "role": "ADMIN",
  "permissions": ["read", "write", "admin"]
}
```

### Users

#### GET /users
List all users (admin only).

```http
GET /api/v1/users?page=1&page_size=20
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "data": [
    {
      "id": "user_123",
      "username": "trader1",
      "email": "trader1@example.com",
      "role": "USER",
      "created_at": "2026-01-01T00:00:00Z",
      "active": true
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 50
  }
}
```

#### POST /users
Create new user (admin only).

```http
POST /api/v1/users
Authorization: Bearer token
Content-Type: application/json

{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "secure_password",
  "role": "USER"
}
```

**Response**: `201 Created`
```json
{
  "id": "user_456",
  "username": "newuser",
  "email": "newuser@example.com",
  "role": "USER"
}
```

#### GET /users/{user_id}
Get user by ID.

```http
GET /api/v1/users/user_123
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "id": "user_123",
  "username": "user@example.com",
  "email": "user@example.com",
  "role": "USER",
  "profile": {
    "phone": "+1-555-1234",
    "broker": "INTERACTIVE_BROKERS"
  }
}
```

### Trades

#### GET /trades
List trades with filtering.

```http
GET /api/v1/trades?status=OPEN&symbol=AAPL&limit=50
Authorization: Bearer token
```

**Query Parameters**:
- `status`: OPEN, CLOSED, CANCELLED
- `symbol`: Stock symbol
- `start_date`: ISO format date
- `end_date`: ISO format date
- `limit`: Max 100
- `offset`: Pagination offset

**Response**: `200 OK`
```json
{
  "data": [
    {
      "id": "trade_123",
      "symbol": "AAPL",
      "side": "BUY",
      "quantity": 100,
      "entry_price": 150.25,
      "current_price": 152.50,
      "status": "OPEN",
      "pnl": 225.00,
      "pnl_percent": 1.50,
      "entry_time": "2026-04-20T10:00:00Z",
      "exit_time": null
    }
  ],
  "pagination": {
    "total": 150,
    "limit": 50,
    "offset": 0
  }
}
```

#### POST /trades
Create new trade.

```http
POST /api/v1/trades
Authorization: Bearer token
Content-Type: application/json

{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "order_type": "LIMIT",
  "limit_price": 150.00,
  "stop_loss": 145.00,
  "take_profit": 160.00
}
```

**Response**: `201 Created`

#### GET /trades/{trade_id}
Get trade details.

```http
GET /api/v1/trades/trade_123
Authorization: Bearer token
```

**Response**: `200 OK`

#### PUT /trades/{trade_id}
Update trade.

```http
PUT /api/v1/trades/trade_123
Authorization: Bearer token
Content-Type: application/json

{
  "status": "CLOSED",
  "exit_price": 155.00
}
```

**Response**: `200 OK`

#### DELETE /trades/{trade_id}
Cancel trade.

```http
DELETE /api/v1/trades/trade_123
Authorization: Bearer token
```

**Response**: `204 No Content`

### Portfolio

#### GET /portfolio
Get portfolio overview.

```http
GET /api/v1/portfolio
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "total_value": 500000.00,
  "cash": 100000.00,
  "invested": 400000.00,
  "total_pnl": 25000.00,
  "total_pnl_percent": 5.33,
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "avg_cost": 150.00,
      "current_price": 152.50,
      "value": 15250.00,
      "pnl": 250.00,
      "pnl_percent": 1.67
    }
  ]
}
```

#### GET /portfolio/positions
List all positions.

```http
GET /api/v1/portfolio/positions
Authorization: Bearer token
```

**Response**: `200 OK`

#### GET /portfolio/history
Get portfolio value history.

```http
GET /api/v1/portfolio/history?period=1M
Authorization: Bearer token
```

**Query Parameters**:
- `period`: 1D, 1W, 1M, 3M, 1Y, ALL

**Response**: `200 OK`
```json
{
  "data": [
    {
      "timestamp": "2026-04-20T00:00:00Z",
      "value": 500000.00
    }
  ]
}
```

### Risk Management

#### GET /risk/metrics
Get risk metrics.

```http
GET /api/v1/risk/metrics
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "var_95": 5000.00,
  "sharpe_ratio": 1.25,
  "max_drawdown": 8.5,
  "beta": 0.95,
  "correlation": 0.75
}
```

#### GET /risk/limits
Get portfolio risk limits.

```http
GET /api/v1/risk/limits
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "max_position_size": 50000.00,
  "max_daily_loss": 10000.00,
  "max_leverage": 2.0,
  "max_sector_exposure": 30.0
}
```

#### PUT /risk/limits
Update risk limits.

```http
PUT /api/v1/risk/limits
Authorization: Bearer token
Content-Type: application/json

{
  "max_daily_loss": 15000.00,
  "max_leverage": 3.0
}
```

**Response**: `200 OK`

### Signals

#### GET /signals
List trading signals.

```http
GET /api/v1/signals?status=ACTIVE
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "data": [
    {
      "id": "signal_123",
      "symbol": "AAPL",
      "direction": "BUY",
      "confidence": 0.85,
      "timestamp": "2026-04-20T10:30:00Z",
      "source": "AI_AGENT",
      "status": "ACTIVE"
    }
  ]
}
```

#### POST /signals
Create manual signal.

```http
POST /api/v1/signals
Authorization: Bearer token
Content-Type: application/json

{
  "symbol": "AAPL",
  "direction": "BUY",
  "confidence": 0.75,
  "reason": "Technical breakout"
}
```

**Response**: `201 Created`

### Operations

#### GET /operations/health
System health status.

```http
GET /api/v1/operations/health
```

**Response**: `200 OK`
```json
{
  "status": "ok",
  "service": "TradeAdviser",
  "users": 50,
  "sessions": 5,
  "trades": 1250,
  "uptime_hours": 168
}
```

#### GET /operations/status
Detailed operation status.

```http
GET /api/v1/operations/status
Authorization: Bearer token
```

**Response**: `200 OK`
```json
{
  "api": "healthy",
  "database": "healthy",
  "brokers": "healthy",
  "memory_usage": 65.5,
  "cpu_usage": 25.3,
  "disk_usage": 45.2
}
```

### WebSocket Events

Connect to real-time events stream:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};
```

**Event Types**:
- `trade_update` - Trade status changed
- `position_update` - Position updated
- `market_data` - New market data
- `signal_alert` - New trading signal
- `risk_breach` - Risk limit breach
- `system_alert` - System alert

**Event Example**:
```json
{
  "type": "trade_update",
  "data": {
    "trade_id": "trade_123",
    "status": "CLOSED",
    "exit_price": 155.00,
    "pnl": 250.00
  },
  "timestamp": "2026-04-20T10:35:00Z"
}
```

## Rate Limiting

API rate limits:
- 1000 requests per hour per user
- 10 requests per second

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1624608000
```

When limit exceeded:
```
HTTP/1.1 429 Too Many Requests

{
  "error": {
    "code": "RATE_LIMIT",
    "message": "Rate limit exceeded",
    "retry_after": 60
  }
}
```

## Pagination

Query parameters for pagination:
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

Response includes:
```json
{
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 500,
    "total_pages": 25,
    "has_next": true,
    "has_prev": false
  }
}
```

## Sorting

Use `sort` parameter for sorting:
```
GET /api/v1/trades?sort=-created_at,symbol
```

- `-` prefix for descending order
- Default ascending order

## Filtering

Use query parameters for filtering:
```
GET /api/v1/trades?status=OPEN&symbol=AAPL&min_pnl=100
```

## API Documentation UI

Access interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

**Last Updated**: April 2026 | **API Version**: v1.0.0
