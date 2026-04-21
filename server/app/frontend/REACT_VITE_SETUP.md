# React + Vite Setup Guide

## Overview

This frontend application uses **React 18** with **Vite** as the build tool. This provides:
- ⚡ Lightning-fast development with Hot Module Replacement (HMR)
- 📦 Optimized production builds with code splitting
- ⚛️ Modern React with hooks and functional components
- 🔌 Seamless integration with the FastAPI backend

## Project Structure

```
server/app/frontend/
├── src/
│   ├── main.jsx              # React entry point
│   ├── App.jsx               # Main App component
│   ├── AppAdmin.jsx          # Admin dashboard
│   ├── index.css             # Global styles
│   ├── app.css               # App-specific styles
│   ├── styles.css            # Additional styles
│   ├── router.jsx            # React Router configuration
│   ├── api/                  # API integration
│   │   ├── services.js       # API endpoint services
│   │   ├── axios.js          # Axios HTTP client setup
│   │   └── api.jsx           # API utilities
│   ├── components/           # Reusable React components
│   ├── pages/                # Page-level components
│   ├── context/              # React Context providers (Auth, etc.)
│   ├── hooks/                # Custom React hooks
│   ├── features/             # Feature modules
│   ├── config/               # Configuration files
│   ├── assets/               # Static assets (images, fonts)
│   └── public/               # Public static files
├── index.html                # HTML template
├── package.json              # Dependencies configuration
├── vite.config.js            # Vite build configuration
└── dist/                     # Production build output (generated)
```

## Installation & Setup

### 1. Install Dependencies

```bash
cd server/app/frontend
npm install
```

This installs:
- **react** (^18.2.0) - React library
- **react-dom** (^18.2.0) - React DOM rendering
- **react-router-dom** (^6.20.0) - Client-side routing
- **axios** (^1.4.0) - HTTP client
- **vite** (^4.4.0) - Build tool
- **@vitejs/plugin-react** (^4.2.0) - React JSX support for Vite

### 2. Environment Configuration

Create `.env.development` and `.env.production` files:

```bash
# .env.development
VITE_API_URL=http://localhost:8000/api

# .env.production
VITE_API_URL=https://api.tradeadviser.com/api
```

## Development

### Start Development Server

```bash
npm run dev
```

**Access**: http://localhost:5173

**Features**:
- Hot Module Replacement (HMR) - Changes reflect instantly
- Console errors and warnings displayed
- API proxy to backend at `/api` → `http://backend:8000`

### API Proxy

The Vite config automatically proxies `/api` requests:
```javascript
proxy: {
  '/api': {
    target: 'http://backend:8000',  // Backend URL
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, '/api')
  }
}
```

**Example API call:**
```javascript
// This request: /api/auth/login
// Goes to: http://backend:8000/api/auth/login
```

## Production Build

### Build for Production

```bash
npm run build
```

**Output**: Generated in `dist/` directory

**Optimizations**:
- Minified JavaScript and CSS
- Code splitting by route
- Asset fingerprinting (cache busting)
- Tree-shaking of unused code

### Preview Production Build

```bash
npm run preview
```

**Access**: http://localhost:4173

## Key Configuration Files

### vite.config.js

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],           // Enable React JSX support
  server: {
    host: '0.0.0.0',            // Listen on all interfaces
    port: 5173,                  // Dev server port
    strictPort: false,           // Allow fallback to different port
    proxy: {
      '/api': {                  // Proxy API calls
        target: 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api')
      }
    }
  },
  build: {
    outDir: 'dist',              // Output directory
    assetsDir: 'assets'          // Assets subdirectory
  }
})
```

### package.json

Dependencies:
- **react**: Core React library
- **react-dom**: React DOM rendering
- **react-router-dom**: Client-side routing (SPA navigation)
- **axios**: HTTP requests to backend API

Dev Dependencies:
- **vite**: Build tool and dev server
- **@vitejs/plugin-react**: React JSX compilation

## Routing

The app uses **React Router v6** for client-side navigation.

**Main routes** (see `router.jsx`):
```javascript
/                    // Landing page
/login               // Login
/register            // Registration
/home                // Dashboard (protected)
/dashboard           // Analytics dashboard (protected)
/trading             // Trading interface (protected)
/portfolio           // Portfolio management (protected)
/admin               // Admin panel (protected)
```

## API Integration

### Using the API Service

```javascript
import { apiService } from '@/api/services'

// Authentication
await apiService.auth.login(email, password)
await apiService.auth.register(userData)

// Portfolio
const portfolio = await apiService.portfolio.getDashboard()

// Trading
await apiService.trading.placeOrder(orderData)
```

### Axios Configuration

Axios is configured in `api/axios.js` with:
- Base URL: `/api`
- Authorization headers
- Response interceptors for error handling
- Token refresh logic

## Development Workflow

### 1. Component Development

Create components in `src/components/`:
```jsx
export default function MyComponent() {
  return <div>My Component</div>
}
```

### 2. Add Routes

Update `src/router.jsx`:
```jsx
import MyComponent from '@/components/MyComponent'

const routes = [
  { path: '/my-route', element: <MyComponent /> }
]
```

### 3. Use State & Effects

```jsx
import { useState, useEffect } from 'react'

export default function DataComponent() {
  const [data, setData] = useState(null)
  
  useEffect(() => {
    // Fetch data
  }, [])
  
  return <div>{data && <p>{data.name}</p>}</div>
}
```

### 4. Call Backend APIs

```jsx
import axios from 'axios'

async function fetchData() {
  const { data } = await axios.get('/api/endpoint')
  return data
}
```

## Docker Integration

The frontend is built and served by the FastAPI backend in production:

1. **Build frontend**:
   ```bash
   npm run build
   ```

2. **Backend serves dist**:
   - FastAPI serves `dist/index.html` for SPA routing
   - API routes handled at `/api/*`

3. **Docker setup** (see `docker-compose.yml`):
   ```yaml
   services:
     frontend:
       build: server/app/frontend
       ports:
         - "5173:5173"
     
     backend:
       build: server
       ports:
         - "8000:8000"
   ```

## Troubleshooting

### Port Already in Use
```bash
# Use different port
npm run dev -- --port 5174
```

### API Calls Failing
- Check backend is running: `http://localhost:8000/health`
- Check proxy config in `vite.config.js`
- Verify API endpoints in browser Network tab

### Build Errors
```bash
# Clear cache and reinstall
rm -rf node_modules dist
npm install
npm run build
```

### Hot Reload Not Working
- Restart dev server: `Ctrl+C` then `npm run dev`
- Check file is saved
- Clear browser cache

## Resources

- [React Documentation](https://react.dev)
- [Vite Guide](https://vitejs.dev)
- [React Router Documentation](https://reactrouter.com)
- [Axios Documentation](https://axios-http.com)

## Next Steps

1. ✅ Install dependencies: `npm install`
2. 🚀 Start dev server: `npm run dev`
3. 📝 Create components in `src/components/`
4. 🔗 Add routes to `src/router.jsx`
5. 🌐 Call APIs via `axios` or `apiService`
6. 📦 Build for production: `npm run build`
