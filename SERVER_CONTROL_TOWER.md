# Server Control Tower Architecture

## Overview

The **Server Control Tower** is the central hub for monitoring and managing all TradeAdviser operations. It:

- **Monitors** system health (CPU, memory, disk, database, API latency)
- **Manages** trading sessions and broker connections  
- **Feeds** real-time data to desktop AI agents for intelligent decision-making
- **Alerts** on critical issues and generates recommendations
- **Tracks** trades through their lifecycle (pending → executed → settled)

The server is the **source of truth** and the **control center**. The desktop AI agents consume data from the server and execute decisions based on recommendations.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         SERVER CONTROL TOWER                            │
│  (Central monitoring & management hub)                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  System Metrics Collector                        │  │
│  │  - CPU, Memory, Disk usage                       │  │
│  │  - Database connection pool status               │  │
│  │  - API endpoint latencies                        │  │
│  │  - WebSocket connection count                    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Session Manager                                 │  │
│  │  - Register/unregister trading sessions          │  │
│  │  - Track active sessions per user                │  │
│  │  - Monitor session health                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Broker Connection Manager                       │  │
│  │  - Track connected brokers (CCXT, OANDA, etc.)  │  │
│  │  - Monitor broker status & heartbeats            │  │
│  │  - Detect disconnections                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Trade Queue Manager                             │  │
│  │  - Queue trades for processing                   │  │
│  │  - Track pending trades                          │  │
│  │  - Mark trades as executed                       │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Alert Engine                                    │  │
│  │  - CPU/Memory/Disk thresholds                    │  │
│  │  - Broker connection failures                    │  │
│  │  - Database latency warnings                     │  │
│  │  - Trade queue buildup                           │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  AI Recommendation Engine                        │  │
│  │  - Reduce system load if CPU > 80%              │  │
│  │  - Process trade queue if pending > 100         │  │
│  │  - Reconnect brokers if disconnected            │  │
│  │  - Pause operations if health critical          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
          │
          │ REST API + WebSocket
          │
┌─────────────────────────────────────────────────────────┐
│         DESKTOP AI AGENTS                               │
│  (Consumer of control tower data)                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Polling: GET /api/control-tower/ai-feed (every 2s)    │
│  - System health status                                │
│  - Active sessions & brokers                           │
│  - Pending trades & recommendations                    │
│                                                         │
│  WebSocket: ws://server:8000/api/control-tower/feed    │
│  - Real-time dashboard updates                         │
│  - Alert notifications                                 │
│  - Trade queue changes                                 │
│                                                         │
│  Actions:                                               │
│  - POST /api/control-tower/trades/queue                │
│  - POST /api/control-tower/brokers/{id}/status         │
│  - POST /api/control-tower/sessions/{id}/register      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## REST API Endpoints

### Dashboard & Monitoring

**GET /api/control-tower/dashboard**
```json
{
  "timestamp": "2026-04-26T10:30:45.123Z",
  "health_status": "healthy",
  "metrics": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "disk_percent": 38.5,
    "database_latency_ms": 15.3,
    "api_latency_ms": 23.1,
    "active_sessions": 3,
    "active_brokers": 5,
    "pending_trades": 12,
    "ws_connections": 8,
    "alerts": []
  },
  "sessions": {
    "active": 3,
    "list": [...]
  },
  "brokers": {
    "connected": 5,
    "total": 6,
    "list": [...]
  },
  "trades": {
    "pending": 12,
    "total": 145,
    "recent": [...]
  }
}
```

**GET /api/control-tower/metrics**
Returns current system metrics (CPU, memory, disk, latencies, counts).

**GET /api/control-tower/health**
Returns overall health status: `"healthy"`, `"attention"`, `"warning"`, or `"critical"`.

**GET /api/control-tower/alerts**
```json
{
  "count": 2,
  "alerts": [
    {
      "type": "cpu_high",
      "severity": "warning",
      "message": "CPU usage at 85.2%",
      "timestamp": "2026-04-26T10:30:45Z"
    }
  ]
}
```

### Session Management

**GET /api/control-tower/sessions**
List all active trading sessions.

**GET /api/control-tower/sessions/{session_id}**
Get details of a specific session.

**POST /api/control-tower/sessions/{session_id}/register**
```json
{
  "user_id": "user123",
  "broker": "binance"
}
```

**POST /api/control-tower/sessions/{session_id}/unregister**
Close a trading session.

### Broker Management

**GET /api/control-tower/brokers**
List all broker connections with status.

**POST /api/control-tower/brokers/{broker_id}/register**
```json
{
  "broker_type": "ccxt_binance"
}
```

**POST /api/control-tower/brokers/{broker_id}/status**
```json
{
  "status": "connected|disconnected|reconnecting|error"
}
```

### Trade Queue

**GET /api/control-tower/trades/pending**
Get pending trades in execution queue.

**POST /api/control-tower/trades/queue**
```json
{
  "trade_id": "trade_abc123",
  "symbol": "BTC/USDT",
  "side": "buy",
  "amount": 0.5,
  "price": 45000.00,
  "broker": "binance"
}
```

### AI Feed

**GET /api/control-tower/ai-feed**
```json
{
  "timestamp": "2026-04-26T10:30:45.123Z",
  "source": "server_control_tower",
  "system": {
    "health": "healthy",
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "disk_percent": 38.5
  },
  "trading": {
    "active_sessions": 3,
    "active_brokers": 5,
    "pending_trades": 12
  },
  "alerts": [
    {
      "type": "database_slow",
      "severity": "warning",
      "message": "Database latency: 250ms"
    }
  ],
  "recommendations": [
    {
      "type": "trading",
      "priority": "medium",
      "action": "process_queue",
      "message": "Trade queue at 12. Prioritize execution."
    }
  ]
}
```

### WebSocket Feed

**WS /api/control-tower/feed**
Real-time streaming of dashboard updates (every 2 seconds):
```json
{
  "type": "dashboard_update",
  "data": { ... dashboard snapshot ... }
}
```

---

## Desktop AI Integration

### Polling Pattern

The desktop AI agent polls for new data every 2 seconds:

```python
# In desktop AI agent loop
while True:
    response = await client.get("/api/control-tower/ai-feed")
    feed = response.json()
    
    # Process alerts
    for alert in feed["alerts"]:
        if alert["severity"] == "critical":
            await handle_critical_alert(alert)
    
    # Process recommendations
    for rec in feed["recommendations"]:
        if rec["action"] == "reduce_load":
            await reduce_trading_load()
        elif rec["action"] == "process_queue":
            await execute_pending_trades()
        elif rec["action"] == "reconnect_brokers":
            await reconnect_brokers()
    
    await asyncio.sleep(2)
```

### WebSocket Pattern

For real-time updates, use the WebSocket feed:

```python
# In desktop AI agent
async with websockets.connect("ws://server:8000/api/control-tower/feed?token=...") as ws:
    while True:
        msg = await ws.recv()
        update = json.loads(msg)
        
        if update["type"] == "dashboard_update":
            dashboard = update["data"]
            
            # React to changes
            if dashboard["health_status"] == "critical":
                await emergency_shutdown()
```

### Actions AI Can Take

1. **Queue Trades**: POST `/api/control-tower/trades/queue`
   ```python
   await client.post(
       "/api/control-tower/trades/queue",
       json={
           "trade_id": "trade_xyz",
           "symbol": "ETH/USDT",
           "side": "sell",
           "amount": 2.5,
           "price": 2800.00,
           "broker": "binance"
       }
   )
   ```

2. **Update Broker Status**: POST `/api/control-tower/brokers/{broker_id}/status`
   ```python
   await client.post(
       f"/api/control-tower/brokers/binance/status",
       json={"status": "disconnected"}
   )
   ```

3. **Register Session**: POST `/api/control-tower/sessions/{session_id}/register`
   ```python
   await client.post(
       f"/api/control-tower/sessions/session_123/register",
       json={
           "user_id": "user_123",
           "broker": "binance"
       }
   )
   ```

---

## Data Flow Example

### Scenario: High CPU Usage Alert

1. **Server Control Tower** detects CPU at 92%
   - Metric: `cpu_percent = 92.0`
   - Alert generated: `{"type": "cpu_high", "severity": "critical"}`
   - Recommendation generated: `{"action": "reduce_load", "message": "System CPU high..."}`

2. **Desktop AI polls** `/api/control-tower/ai-feed`
   - Receives alert: CPU critical
   - Receives recommendation: reduce_load

3. **Desktop AI responds**:
   - Pauses new strategy launches
   - Reduces model inference frequency
   - Prioritizes essential operations

4. **Server Control Tower** continues monitoring
   - If CPU drops below 80%: Alert cleared
   - Desktop AI resumes normal operations

---

## Health Status Calculation

The control tower calculates health status as:

- **Critical**: CPU > 90% OR Memory > 90% OR Disk > 90% OR active_alerts exist
- **Warning**: CPU > 75% OR Memory > 75% OR Database latency > 1000ms OR API latency > 5000ms
- **Attention**: Any active alerts
- **Healthy**: All metrics normal, no alerts

---

## Metrics Collection

Metrics are collected every request using `psutil`:

```python
def get_system_metrics(self) -> ControlTowerMetrics:
    self.metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    self.metrics.memory_percent = memory.percent
    disk = psutil.disk_usage("/")
    self.metrics.disk_percent = disk.percent
    return self.metrics
```

---

## Database Schema (Optional)

For persistent storage of metrics history:

```sql
CREATE TABLE control_tower_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_percent FLOAT,
    memory_percent FLOAT,
    disk_percent FLOAT,
    database_latency_ms FLOAT,
    api_latency_ms FLOAT,
    active_sessions INT,
    active_brokers INT,
    pending_trades INT,
    health_status VARCHAR(20)
);

CREATE TABLE control_tower_alerts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    resolved_at TIMESTAMP NULL
);
```

---

## Summary

The **Server Control Tower** is:

✅ The single source of truth for system state  
✅ The control center for all trading operations  
✅ The data provider for desktop AI agents  
✅ The alert engine for critical issues  
✅ The recommendation generator for intelligent decisions  

Desktop AI agents consume this data and take actions autonomously, always guided by the server's recommendations and alerts.
