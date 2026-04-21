# API Documentation Access Guide

## Quick Access

Once the backend is running, access the API documentation at:

### **Swagger UI (Interactive)**
```
http://localhost:8000/docs
```

### **ReDoc (Alternative)**
```
http://localhost:8000/redoc
```

### **OpenAPI Schema**
```
http://localhost:8000/openapi.json
```

---

## ✅ Solution Applied

The docs endpoint was disabled in production mode by default. This has been fixed:

### 1. **FastAPI Configuration** (`server/app/backend/main.py`)
- Updated to enable docs in development mode
- Added `SHOW_DOCS` environment variable to enable docs in production if needed
- Explicitly set `docs_url`, `redoc_url`, and `openapi_url` parameters

### 2. **Docker Configuration** (`server/docker-compose.yml`)
- Changed default `ENV` from `production` to `development`
- Added explicit `ENV` and `SHOW_DOCS=true` environment variables
- Ensures docs are accessible when running in Docker

---

## Starting the Backend

### Option 1: Docker (Recommended)
```bash
cd server
make docker-up
# or
docker-compose up -d --build
```

Access docs at: http://localhost:8000/docs

### Option 2: Local Development
```bash
cd server
# Install dependencies
pip install -r requirements.txt

# Start the server
ENV=development python main.py
# or
python main.py  # Uses development by default now
```

---

## Environment Variables

Control docs visibility:

```bash
# Show docs (development)
ENV=development python main.py

# Hide docs (production)
ENV=production python main.py

# Show docs anyway (production with docs enabled)
ENV=production SHOW_DOCS=true python main.py
```

In Docker:
```bash
# Default (development with docs)
docker-compose up

# Production without docs
ENV=production docker-compose up

# Production with docs
SHOW_DOCS=true docker-compose up
```

---

## Testing API Endpoints

Use Swagger UI to:

1. ✅ **Browse all available endpoints**
2. ✅ **Try out endpoints directly**
3. ✅ **View request/response schemas**
4. ✅ **Authenticate and test protected routes**

Example endpoints:
- `GET /health` - Health check
- `POST /api/auth/login` - User login
- `GET /api/portfolio/positions` - Get portfolio positions
- `GET /api/trades` - Get trades

---

## Troubleshooting

### Still getting "Route not found"?

1. **Verify backend is running**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check environment variables**
   ```bash
   # In Docker
   docker-compose ps
   docker logs tradeadviser_server-backend
   
   # Locally
   echo $ENV
   ```

3. **Restart the backend**
   ```bash
   # Docker
   docker-compose down
   docker-compose up -d --build
   
   # Local
   # Kill the process and restart
   python main.py
   ```

### Docs show but can't test endpoints?

- Ensure you're logged in (check `/api/auth/login`)
- Check CORS settings if requests are blocked
- Review browser console for errors

---

## API Usage Examples

### Using Swagger UI (No code needed)
1. Go to http://localhost:8000/docs
2. Click on an endpoint to expand it
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"

### Using curl
```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Get positions
curl -X GET http://localhost:8000/api/portfolio/positions \
  -H "Authorization: Bearer <token>"
```

### Using Python
```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Login
response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "user@example.com", "password": "password"}
)
token = response.json()["access_token"]

# Get positions
response = requests.get(
    "http://localhost:8000/api/portfolio/positions",
    headers={"Authorization": f"Bearer {token}"}
)
print(response.json())
```

---

## Files Modified

1. **`server/app/backend/main.py`**
   - Updated FastAPI initialization
   - Added docs_url, redoc_url parameters
   - Made docs always available in development

2. **`server/docker-compose.yml`**
   - Changed default ENV to development
   - Added ENV variable
   - Added SHOW_DOCS=true flag

---

## Next Steps

1. **Restart backend**: `docker-compose up -d --build`
2. **Access docs**: http://localhost:8000/docs
3. **Try some endpoints**: Test health check, login, portfolio endpoints
4. **Read the Swagger UI**: It documents all available endpoints and parameters

---

**Status**: ✅ Docs endpoint now accessible by default in development mode
