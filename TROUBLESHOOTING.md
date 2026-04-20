# Troubleshooting Guide

Common issues and solutions for TradeAdviser.

## Table of Contents

- [Backend Issues](#backend-issues)
- [Frontend Issues](#frontend-issues)
- [Desktop Application Issues](#desktop-application-issues)
- [Docker Issues](#docker-issues)
- [Database Issues](#database-issues)
- [Network & Connectivity](#network--connectivity)
- [Performance Issues](#performance-issues)

## Backend Issues

### 1. Backend Won't Start

**Symptoms**: 
- `Connection refused`
- `Address already in use`
- `ImportError`

**Solutions**:

Check if port 8000 is in use:
```bash
# Windows
netstat -ano | findstr :8000

# macOS/Linux
lsof -i :8000
```

Kill the process:
```bash
# Windows
taskkill /PID <PID> /F

# macOS/Linux
kill -9 <PID>
```

Check Python installation:
```bash
python --version  # Should be 3.11+
pip list  # Check installed packages
```

Reinstall dependencies:
```bash
pip install --upgrade -r requirements.txt
```

### 2. Database Connection Error

**Symptoms**:
- `psycopg2.OperationalError`
- `Connection refused`
- `Database does not exist`

**Solutions**:

Test database connection:
```bash
psql -h localhost -U tradeuser -d tradeadviser -c "SELECT 1;"
```

Check connection string:
```bash
# Should be format:
postgresql+asyncpg://user:password@host:port/database

# Verify in .env
echo $DATABASE_URL
```

Start database if using Docker:
```bash
docker-compose up -d db
docker-compose logs db
```

Create database if missing:
```bash
psql -U postgres -c "CREATE DATABASE tradeadviser;"
```

### 3. API Returns 404 on All Routes

**Symptoms**:
- `{"detail":"Route not found"}`
- Frontend cannot connect

**Solutions**:

Verify CORS settings in `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Check API routes are registered:
```python
app.include_router(auth_router)
app.include_router(trades_router)
# ... all routers
```

Restart backend:
```bash
# Kill existing process
ps aux | grep uvicorn | grep -v grep | awk '{print $2}' | xargs kill -9

# Restart
uvicorn main:app --reload
```

### 4. Authentication Fails

**Symptoms**:
- `Invalid credentials`
- `Token expired`
- `Unauthorized`

**Solutions**:

Check database has users:
```bash
psql -U tradeuser -d tradeadviser -c "SELECT id, username FROM users;"
```

Create test user:
```bash
# Via API
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123"
  }'
```

Verify JWT secret is set:
```bash
echo $SECRET_KEY  # Should have a value
```

Check token expiration:
```bash
# Token should be valid for 24 hours
# Refresh if expired using refresh_token
```

### 5. Memory Leaks / High Memory Usage

**Symptoms**:
- Process grows to 1GB+
- Slow response times

**Solutions**:

Monitor memory:
```bash
# Linux
watch -n 1 'ps aux | grep uvicorn'

# macOS
while true; do ps aux | grep uvicorn; sleep 1; done
```

Check for database connection leaks:
```python
# In backend/db/session.py
# Ensure connections are properly closed
async with get_db() as db:
    # ... do work
    # Connection automatically closed
```

Enable profiling:
```bash
pip install py-spy
py-spy record -o profile.svg -- uvicorn main:app
```

## Frontend Issues

### 1. Frontend Won't Load

**Symptoms**:
- Blank white page
- Console errors
- 404 on assets

**Solutions**:

Check if development server is running:
```bash
cd server/frontend
npm run dev
```

Should be at: `http://localhost:5173`

Check network tab in browser DevTools for failed requests.

Clear browser cache:
```bash
# Chrome: Ctrl+Shift+Delete
# Firefox: Ctrl+Shift+Delete
# Safari: Develop > Empty Caches
```

Check for JavaScript errors:
```bash
# Open browser console (F12)
# Look for red error messages
```

### 2. Cannot Connect to Backend

**Symptoms**:
- API requests fail
- CORS errors
- `Failed to fetch`

**Solutions**:

Check backend is running:
```bash
curl http://localhost:8000/health
```

Check API URL in frontend:
```javascript
// src/api/axios.js
// Should be:
const BASE_URL = 'http://localhost:8000';
```

Check CORS headers in backend:
```bash
curl -H "Origin: http://localhost:5173" \
  -v http://localhost:8000/api/v1/auth/me
```

Look for `Access-Control-Allow-Origin` header in response.

### 3. Build Fails

**Symptoms**:
- `npm run build` errors
- `Cannot find module`
- `JSX syntax error`

**Solutions**:

Clear node modules and reinstall:
```bash
rm -rf node_modules
npm install
```

Check Node.js version:
```bash
node --version  # Should be 18+
npm --version   # Should be 9+
```

Check for JSX files with `.js` extension:
```bash
find src -name "*.js" -exec grep -l "return <" {} \;
# Rename to .jsx
```

Check vite config:
```javascript
// vite.config.js should have:
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
```

### 4. Slow Performance

**Symptoms**:
- Page loads slowly
- Laggy interactions
- High CPU usage

**Solutions**:

Check Network tab in DevTools:
- Look for large file downloads
- Check for long-running requests

Enable code splitting:
```javascript
// Use React.lazy for route-based splitting
const Dashboard = lazy(() => import('./components/Dashboard'))
```

Optimize images:
- Use appropriate formats (WebP)
- Compress images
- Use CDN

Use DevTools Profiler:
- Record performance
- Identify slow components

## Desktop Application Issues

### 1. Desktop App Won't Start

**Symptoms**:
- Application crashes on launch
- No GUI appears
- `ModuleNotFoundError`

**Solutions**:

Check Python version:
```bash
python --version  # Should be 3.11+
```

Activate virtual environment:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Verify which Python is being used:
```bash
which python
```

Check dependencies:
```bash
pip list | grep -i pyside
pip list | grep -i pyqt
```

Reinstall from requirements:
```bash
pip install -r requirements.txt --force-reinstall
```

### 2. Cannot Connect to Server

**Symptoms**:
- Login fails
- Connection refused
- Timeout

**Solutions**:

Verify server is running:
```bash
curl http://localhost:8000/health
```

Check server URL in config:
```python
# desktop/src/config/settings.py
SERVER_URL = "http://localhost:8000"
```

Check firewall:
```bash
# Windows
netsh advfirewall firewall show rule name="Python" | findstr /C:"Direction"

# macOS
pfctl -sr | grep 8000
```

Test connectivity:
```bash
curl -v http://localhost:8000/api/v1/auth/me
```

### 3. GUI Appears Corrupt/Misaligned

**Symptoms**:
- Elements overlap
- Text is cut off
- Buttons not visible

**Solutions**:

Check DPI scaling (Windows):
```python
# desktop/src/ui/main_window.py
# Set DPI awareness
os.environ['QT_SCALE_FACTOR'] = '1'
```

Check screen resolution:
- Try different window size
- Reset window position

Rebuild Qt resources:
```bash
# If using .qrc files
pyrcc5 resources.qrc -o resources_rc.py
```

### 4. Charts Not Displaying

**Symptoms**:
- Chart widgets show blank
- No data visualization
- Errors in chart library

**Solutions**:

Check chart library installed:
```bash
pip list | grep -i plotly
pip list | grep -i pyqtgraph
```

Verify data is being fetched:
```python
# Add debug logging
print(f"Chart data: {data}")
```

Check for missing dependencies:
```bash
pip install pyqtgraph --upgrade
```

## Docker Issues

### 1. Containers Won't Start

**Symptoms**:
- `docker-compose up` fails
- `Container exited`
- `Connection refused`

**Solutions**:

Check Docker is running:
```bash
docker ps
# or
docker version
```

View container logs:
```bash
docker-compose logs backend
docker-compose logs db
```

Check for port conflicts:
```bash
docker ps -a | grep 8000
```

Remove stopped containers:
```bash
docker-compose down
docker system prune -f
```

Rebuild images:
```bash
docker-compose build --no-cache
docker-compose up -d
```

### 2. Database Container Won't Initialize

**Symptoms**:
- `FATAL: database does not exist`
- Connection fails
- Database empty

**Solutions**:

Check PostgreSQL logs:
```bash
docker-compose logs db | tail -50
```

Verify volume permissions:
```bash
docker volume ls
docker volume inspect <volume-name>
```

Recreate volume:
```bash
docker-compose down -v  # Remove volume
docker-compose up -d db
```

Check initialization script:
```bash
# Verify init.sql exists and is readable
ls -la server/init.sql
```

### 3. Image Build Fails

**Symptoms**:
- `docker build` errors
- `COPY failed`
- `RUN failed`

**Solutions**:

Check Dockerfile syntax:
```bash
docker build --no-cache -t test .
```

View build output:
```bash
docker build --no-cache -v -t test .
```

Check file paths:
```bash
# Verify files exist
ls -la docker/Dockerfile.backend
ls -la backend/requirements.txt
```

## Database Issues

### 1. Database Connection Pool Exhausted

**Symptoms**:
- `QueuePool timeout`
- `pool_pre_ping` errors
- Cannot execute queries

**Solutions**:

Check pool size in config:
```python
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 10
SQLALCHEMY_POOL_RECYCLE = 3600
```

Monitor active connections:
```sql
SELECT count(*) FROM pg_stat_activity;
```

Kill idle connections:
```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE usename = 'tradeuser' AND state = 'idle';
```

### 2. Slow Queries

**Symptoms**:
- Database queries take > 1 second
- High CPU usage
- Timeouts

**Solutions**:

Enable query logging:
```sql
ALTER DATABASE tradeadviser SET log_min_duration_statement = 1000;
```

Check slow query log:
```bash
tail -f /var/log/postgresql/postgresql.log
```

Create indexes:
```sql
CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
```

Analyze query plan:
```sql
EXPLAIN ANALYZE SELECT * FROM trades WHERE user_id = '123';
```

## Network & Connectivity

### 1. Firewall Blocking Connections

**Symptoms**:
- `Connection refused`
- `Connection timeout`
- Remote cannot connect

**Solutions**:

Allow port in Windows Firewall:
```bash
netsh advfirewall firewall add rule name="TradeAdviser" dir=in action=allow protocol=tcp localport=8000
```

Allow port in macOS:
```bash
# System Preferences > Security & Privacy > Firewall Options
# or use:
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python
```

Check Linux firewall:
```bash
sudo ufw allow 8000
sudo ufw enable
```

### 2. CORS Errors

**Symptoms**:
- `CORS policy: No 'Access-Control-Allow-Origin'`
- Requests blocked

**Solutions**:

Update allowed origins:
```python
# backend/main.py
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://yourdomain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
)
```

Check browser CORS settings:
```bash
# Browser Dev Tools > Network
# Look for CORS preflight (OPTIONS) requests
```

## Performance Issues

### 1. High CPU Usage

**Symptoms**:
- CPU at 100%
- App unresponsive
- System slow

**Solutions**:

Identify bottleneck:
```bash
# Use profiler
python -m cProfile -s cumtime main:app

# Or use py-spy
py-spy record -o profile.svg -- python main.py
```

Check for infinite loops:
```bash
# Review recent code changes
git diff HEAD~1 HEAD | grep -A 5 -B 5 "while\|for"
```

Optimize queries:
- Add indexes
- Reduce N+1 queries
- Use pagination

### 2. Memory Leaks

**Symptoms**:
- Memory grows over time
- Application crashes
- Out of memory errors

**Solutions**:

Monitor memory:
```bash
# Linux
watch -n 1 'free -h'

# Python
import tracemalloc
tracemalloc.start()
```

Use memory profiler:
```bash
pip install memory-profiler
python -m memory_profiler main.py
```

Check for circular references:
```python
import gc
gc.collect()
print(len(gc.get_objects()))
```

## Getting Help

1. **Check logs**: Review application and system logs
2. **Search docs**: Look for existing solutions
3. **Ask community**: Open an issue with details
4. **Enable debug**: Set `DEBUG=True` for more details

## Debug Mode

Enable debug logging:

```python
# backend/main.py
import logging
logging.basicConfig(level=logging.DEBUG)

# frontend
localStorage.setItem('DEBUG', 'true')

# desktop
DEBUG = True
```

---

**Last Updated**: April 2026
