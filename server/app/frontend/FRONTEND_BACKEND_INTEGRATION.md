# TradeAdviser Frontend-Backend Integration Guide

## Overview

The TradeAdviser application now has full frontend-backend connectivity with comprehensive API service integration and routing infrastructure.

## Architecture

### Backend (FastAPI)
- **Base URL**: `http://localhost:8000/api`
- **Health Check**: `GET /health`
- **API Routes**: See [Backend Endpoints](#backend-endpoints)

### Frontend (React + Vite)
- **Dev Server**: `http://localhost:5173`
- **Build Dist**: `/app/server/app/frontend/dist`
- **API Base**: `/api` (proxied to backend)

## Directory Structure

```
server/app/frontend/
├── src/
│   ├── pages/              # Page components (DashboardPage, PortfolioPage, etc.)
│   ├── components/         # Reusable components
│   ├── api/
│   │   ├── services.js     # All API endpoint services
│   │   ├── axios.js        # Axios configuration
│   │   └── api.jsx         # API utility functions
│   ├── context/            # React Context (AuthProvider)
│   ├── hooks/              # Custom React hooks
│   ├── features/           # Feature modules
│   ├── App.jsx             # Main App component
│   ├── main.jsx            # Entry point
│   └── router.jsx          # Router configuration
├── package.json
├── vite.config.js          # Vite configuration
└── index.html              # HTML template
```

## Backend Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user
- `POST /auth/refresh` - Refresh token
- `POST /auth/forgot-password` - Password reset request
- `POST /auth/reset-password` - Reset password

### Session
- `POST /session/login` - Session login
- `POST /session/resume` - Resume session

### Portfolio
- `GET /portfolio/dashboard` - Portfolio overview
- `GET /portfolio/positions` - Current positions
- `GET /portfolio/orders` - Orders list

### Trading
- `POST /trading/orders` - Place order
- `POST /trading/orders/cancel` - Cancel order
- `POST /trading/positions/close` - Close position
- `POST /trading/kill-switch` - Emergency kill switch
- `POST /trading/broker/connect` - Connect broker
- `POST /trading/subscriptions/market-data` - Market data subscription

### Trades & Signals
- `GET /trades` - Get all trades
- `POST /trades` - Create trade
- `GET /signals` - Get all signals
- `POST /signals` - Create signal

### Performance & Risk
- `GET /performance/dashboard` - Performance overview
- `GET /risk/dashboard` - Risk overview
- `GET /risk/metrics` - Risk metrics

### Admin
- `GET /admin/users` - List users
- `POST /admin/users` - Create user
- `GET /admin/licenses` - List licenses
- `POST /admin/licenses` - Create license

### Workspace
- `GET /workspace/settings` - Get workspace settings
- `PUT /workspace/settings` - Update settings

## Running the Application

### Docker Compose (Recommended)

```bash
cd server

# Clean up previous builds
docker-compose down -v

# Build and start all services
docker-compose build --no-cache
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Local Development

```bash
# Start backend
cd server
python main.py

# In another terminal, start frontend
cd server/app/frontend
npm install
npm run dev
```

## API Service Usage

The frontend provides comprehensive API services in `src/api/services.js`:

```javascript
import { 
  authService, 
  portfolioService, 
  tradingService,
  tradesService, 
  signalsService,
  agentsService,
  operationsService,
  performanceService,
  riskService,
  adminService,
  workspaceService
} from '@/api/services';

// Usage Example
const token = localStorage.getItem('tradeadviser-token');

// Fetch portfolio
const portfolio = await portfolioService.getDashboard(token);

// Place order
const order = await tradingService.placeOrder({
  symbol: 'AAPL',
  quantity: 10,
  price: 150.00
}, token);
```

## Authentication Flow

1. User logs in via `LoginPage` → `authService.login()`
2. Backend returns JWT `access_token`
3. Token is stored in localStorage as `tradeadviser-token`
4. All subsequent requests include token in `Authorization: Bearer <token>` header
5. Protected routes use `ProtectedRoute` component to verify authentication
6. If token expires (401), user is redirected to login

## Protected Routes

Routes are protected using the `ProtectedRoute` component:

- `/dashboard` - User dashboard
- `/portfolio` - Portfolio management
- `/trading` - Trading interface
- `/trades` - Trades history
- `/signals` - Trading signals
- `/performance` - Performance analytics
- `/risk` - Risk management
- `/agents` - Agent management
- `/admin` - Admin panel (admin only)
- `/settings` - User settings

## Available Pages

### User Pages
- **LoginPage** - Authentication
- **DashboardPage** - Main dashboard
- **PortfolioPage** - Position and portfolio management
- **TradingPage** - Trading controls
- **TradesPage** - Trades history and list
- **SignalsPage** - Trading signals
- **PerformancePage** - Performance analytics
- **RiskPage** - Risk management dashboard
- **AgentsPage** - Trading agent management
- **SettingsPage** - User and workspace settings

### Admin Pages
- **AdminPage** - System administration
- **NotFoundPage** - 404 error page

## Environment Configuration

### Frontend (`vite.config.js`)
```javascript
VITE_API_URL=http://localhost:8000/api
```

### Backend (Docker)
```
PYTHONPATH=/app
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/db
```

## Common Tasks

### Add New Route

1. Create page component in `src/pages/`
2. Add route to `src/router.jsx`
3. Update navigation links

### Add New API Service

1. Add endpoint to `src/api/services.js`
2. Use in component:
   ```javascript
   const data = await yourService.yourEndpoint(token);
   ```

### Handle API Errors

```javascript
try {
  const result = await apiService.someEndpoint(token);
} catch (error) {
  console.error('API Error:', error.message);
  // Handle error - show toast, retry, etc.
}
```

## Debugging

### Check Backend Connection
```bash
# Health check
curl http://localhost:8000/health

# Check API response
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/portfolio/dashboard
```

### Check Frontend Logs
```bash
# Browser console logs
# Network tab shows all API requests
```

### Docker Logs
```bash
docker-compose logs backend
docker-compose logs frontend
```

## Testing Integration

1. Start application with docker-compose
2. Open `http://localhost:5173`
3. Login with credentials
4. Navigate to Dashboard - should fetch data from backend
5. Check Network tab in browser dev tools for API calls
6. Check terminal for any errors

## Troubleshooting

### CORS Errors
- Backend has `CORSMiddleware` configured for all origins
- Check browser console for specific CORS rejection

### 401 Unauthorized
- Token may be expired
- Check localStorage for `tradeadviser-token`
- Try logging in again

### API Not Found (404)
- Check endpoint path matches backend routes
- Verify service.js has correct endpoint

### Connection Refused
- Ensure backend is running: `docker-compose logs backend`
- Check port 8000 is accessible
- Check frontend is trying to reach `/api` not full URL

## Next Steps

1. **UI/UX Enhancement**: Replace placeholder layouts with proper dashboard UI
2. **Real-time Updates**: Add WebSocket support for live data
3. **State Management**: Consider Redux or Zustand for complex state
4. **Error Handling**: Implement comprehensive error boundaries
5. **Testing**: Add unit and integration tests
6. **Analytics**: Add telemetry and monitoring

## Resources

- [React Router Docs](https://reactrouter.com/)
- [Vite Docs](https://vitejs.dev/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Axios Docs](https://axios-http.com/)
