# Frontend API Endpoints & Role Mapping

## Overview
All APIs use the backend base URL with `/api` prefix and are accessed through a single unified app with role-based routing.

### Base URL
- Development: `http://localhost:8000/api`
- Production: Proxy through Nginx (requests to `/api/*` are proxied to backend)

### Authentication Endpoints

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| POST | `/api/auth/login` | User login | None (public) |
| POST | `/api/auth/register` | User registration | None (public) |
| POST | `/api/auth/refresh` | Refresh access token | None (uses refresh_token) |
| GET | `/api/auth/me` | Get current user profile | Bearer token |
| POST | `/api/auth/forgot-password` | Request password reset | None (public) |
| POST | `/api/auth/reset-password` | Reset password | None (public) |

### User Profile Endpoints

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/users/profile` | Get current user profile | TRADER, RISK_MANAGER, OPERATIONS, ADMIN, SUPER_ADMIN |
| PUT | `/api/users/profile` | Update profile | TRADER, RISK_MANAGER, OPERATIONS, ADMIN, SUPER_ADMIN |

### Trader Dashboard Endpoints

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/portfolio/dashboard` | Portfolio overview | TRADER, ADMIN, SUPER_ADMIN |
| GET | `/api/portfolio/positions` | Current positions | TRADER, ADMIN, SUPER_ADMIN |
| GET | `/api/portfolio/orders` | Orders list | TRADER, ADMIN, SUPER_ADMIN |
| GET | `/api/trades` | Trades history | TRADER, ADMIN, SUPER_ADMIN |
| GET | `/api/signals` | Trading signals | TRADER, ADMIN, SUPER_ADMIN |
| GET | `/api/performance` | Performance analytics | TRADER, ADMIN, SUPER_ADMIN |

### Admin - Operations Pillar

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/admin/operations/health` | System health status | OPERATIONS, ADMIN, SUPER_ADMIN |
| GET | `/api/admin/operations/broker-status` | Broker connectivity | OPERATIONS, ADMIN, SUPER_ADMIN |
| GET | `/api/admin/operations/active-connections` | Active connections | OPERATIONS, ADMIN, SUPER_ADMIN |
| GET | `/api/admin/operations/deployment-status` | Deployment status | OPERATIONS, ADMIN, SUPER_ADMIN |

### Admin - Risk Pillar

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/admin/risk/overview` | Portfolio risk overview | RISK_MANAGER, ADMIN, SUPER_ADMIN |
| GET | `/api/admin/risk/breaches` | Risk breaches | RISK_MANAGER, ADMIN, SUPER_ADMIN |
| GET | `/api/admin/risk/limits/{user_id}` | User risk limits | RISK_MANAGER, ADMIN, SUPER_ADMIN |
| PUT | `/api/admin/risk/limits/{user_id}` | Update risk limits | ADMIN, SUPER_ADMIN |

### Admin - Users & Licenses Pillar

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/admin/users` | List all users | ADMIN, SUPER_ADMIN |
| POST | `/api/admin/users` | Create new user | ADMIN, SUPER_ADMIN |
| GET | `/api/admin/users/{user_id}` | Get user details | ADMIN, SUPER_ADMIN |
| PUT | `/api/admin/users/{user_id}/status` | Update user status | ADMIN, SUPER_ADMIN |
| PUT | `/api/admin/users/{user_id}/role` | Update user role | ADMIN, SUPER_ADMIN |
| GET | `/api/admin/users-licenses/licenses` | List licenses | ADMIN, SUPER_ADMIN |
| POST | `/api/admin/users-licenses/licenses` | Create license | ADMIN, SUPER_ADMIN |
| DELETE | `/api/admin/users-licenses/licenses/{license_id}` | Revoke license | ADMIN, SUPER_ADMIN |

### Admin - Agents & AI Pillar

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/admin/agents` | List agents | ADMIN, SUPER_ADMIN |
| POST | `/api/admin/agents` | Deploy agent | ADMIN, SUPER_ADMIN |
| PUT | `/api/admin/agents/{agent_id}` | Update agent | ADMIN, SUPER_ADMIN |
| DELETE | `/api/admin/agents/{agent_id}` | Remove agent | ADMIN, SUPER_ADMIN |

### Admin - Performance & Audit Pillar

| Method | Endpoint | Purpose | Role Required |
|--------|----------|---------|---------------|
| GET | `/api/admin/performance-audit/overview` | Audit overview | ADMIN, SUPER_ADMIN |
| GET | `/api/admin/performance-audit/audit-logs` | Audit logs | ADMIN, SUPER_ADMIN |
| GET | `/api/admin/performance-audit/audit-trail` | Audit trail | ADMIN, SUPER_ADMIN |

## Role Definitions

Backend roles (from `backend/models/user.py`):

| Role | Value | Purpose |
|------|-------|---------|
| TRADER | `trader` | Regular trading user |
| RISK_MANAGER | `risk_manager` | Risk monitoring access |
| OPERATIONS | `operations` | System operations access |
| ADMIN | `admin` | Administrative access |
| SUPER_ADMIN | `super_admin` | Full system access |

## Token Management

### Access Token
- Method: Bearer token in `Authorization` header
- Format: `Authorization: Bearer <access_token>`
- Duration: 30 minutes (configurable)
- Used for: All authenticated requests

### Refresh Token
- Stored in: localStorage as `refreshToken`
- Used for: Obtaining new access tokens when expired
- Duration: 30 days (or 1 day without "remember me")
- Endpoint: `POST /auth/refresh` with `{ refresh_token, remember_me }`

## Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | Success | Proceed |
| 201 | Created | Resource created |
| 400 | Bad Request | Fix request payload |
| 401 | Unauthorized | Refresh token or re-login |
| 403 | Forbidden | User lacks required role |
| 404 | Not Found | Resource not found |
| 500 | Server Error | Retry or contact support |

## Request Headers

All requests include:
```
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: application/json
```

## Response Format

Success response:
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful"
}
```

Error response:
```json
{
  "detail": "Error description",
  "status_code": 400
}
```

## Unified App Routes

### Public Routes
- `/login` - Login page
- `/register` - Registration page
- `/verify-link` - Email verification
- `/access-denied` - Access denied page
- `/tradeadviser` - Trade adviser info

### Protected Routes (All Authenticated Users)
- `/` - Dashboard (default route)
- `/community` - Community section

### Protected Routes (TRADER role)
- `/trading-editor` - Trading editor

### Protected Routes (RISK_MANAGER role)
- `/admin/risk` - Risk dashboard

### Protected Routes (OPERATIONS role)
- `/admin/operations` - Operations dashboard

### Protected Routes (ADMIN/SUPER_ADMIN role)
- `/admin-panel` - Legacy admin panel
- `/admin/users-licenses` - Users & Licenses management
- `/admin/agents` - Agents & AI management
- `/admin/performance-audit` - Performance & Audit logs

## Implementation Notes

1. **Token Refresh**: Automatically triggered when receiving 401 Unauthorized
2. **Role-Based Access**: All protected routes validate user role against allowedRoles
3. **Persistent Login**: Auth state restored from localStorage on app load
4. **Single App**: Unified routing system handles all user types and roles
5. **API Base URL**: Configured in `src/api/axios.ts` with environment-aware defaults
