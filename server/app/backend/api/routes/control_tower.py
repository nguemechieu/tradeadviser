"""
Control Tower API Routes - REST endpoints for system monitoring and management.

Provides real-time dashboards, metrics, alerts, and feeds for desktop AI agents.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import asyncio
import logging

from server.app.backend.dependencies import get_db, get_current_user
from server.app.backend.schemas import UserSchema
from server.app.backend.services.control_tower import get_control_tower

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v3/control-tower", tags=["control-tower"])

# Track WebSocket connections for real-time feeds
ws_connections: list[WebSocket] = []


@router.get("/dashboard")
async def get_dashboard(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Get comprehensive control tower dashboard.
    
    Returns:
    - System metrics (CPU, memory, disk)
    - Active sessions and brokers
    - Trade queue status
    - Active alerts
    - Uptime and health status
    """
    # Check permissions
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    return control_tower.get_dashboard_snapshot()


@router.get("/metrics")
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Get real-time system metrics.
    
    Returns:
    - CPU, memory, disk usage percentages
    - Active sessions and brokers
    - Pending trades count
    - Database and API latencies
    - Active alerts
    """
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    metrics = control_tower.get_system_metrics()
    return metrics.to_dict()


@router.get("/health")
async def get_health_status(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Get overall health status.
    
    Returns: "healthy", "attention", "warning", or "critical"
    """
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    metrics = control_tower.get_system_metrics()
    
    return {
        "status": metrics._calculate_health_status(),
        "timestamp": metrics.timestamp.isoformat(),
        "alerts": metrics.alerts,
    }


@router.get("/api/sessions")
async def list_sessions(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """List all active trading sessions."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    return {
        "active_count": len(control_tower.session_manager),
        "sessions": list(control_tower.session_manager.values()),
    }


@router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get details of a specific trading session."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    session = control_tower.session_manager.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@router.get("/api/brokers")
async def list_brokers(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """List all broker connections."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    connected = [b for b in control_tower.broker_connections.values() if b["status"] == "connected"]
    
    return {
        "connected_count": len(connected),
        "total_count": len(control_tower.broker_connections),
        "brokers": list(control_tower.broker_connections.values()),
    }


@router.get("/api/trades/pending")
async def get_pending_trades(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
):
    """Get pending trades in queue."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    pending = [t for t in control_tower.trade_queue if t.get("status") == "pending"]
    
    return {
        "count": len(pending),
        "trades": pending[:limit],
    }


@router.get("/api/alerts")
async def get_alerts(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
    severity: str | None = Query(None, pattern="^(critical|warning|info)$"),
):
    """Get system alerts."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    metrics = control_tower.get_system_metrics()
    alerts = metrics.alerts
    
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    
    return {
        "count": len(alerts),
        "alerts": alerts,
        "timestamp": metrics.timestamp.isoformat(),
    }


@router.get("/api/ai-feed")
async def get_ai_feed(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Get data feed for desktop AI agents.
    
    Includes system health, trading status, alerts, and recommendations
    for AI-driven decisions.
    """
    # Allow AI agents and operations staff
    if current_user.role not in ["agent", "operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    return control_tower.get_desktop_ai_feed()


@router.post("/api/sessions/{session_id}/register")
async def register_session(
    session_id: str,
    user_id: str,
    broker: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Register a new trading session."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    control_tower.register_session(session_id, user_id, broker)
    
    return {
        "session_id": session_id,
        "status": "registered",
        "message": f"Session {session_id} registered for user {user_id}",
    }


@router.post("/api/sessions/{session_id}/unregister")
async def unregister_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Unregister a trading session."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    control_tower.unregister_session(session_id)
    
    return {
        "session_id": session_id,
        "status": "unregistered",
        "message": f"Session {session_id} closed",
    }


@router.post("/api/brokers/{broker_id}/register")
async def register_broker(
    broker_id: str,
    broker_type: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Register a broker connection."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    control_tower.register_broker(broker_id, broker_type, status="connected")
    
    return {
        "broker_id": broker_id,
        "type": broker_type,
        "status": "registered",
    }


@router.post("/api/brokers/{broker_id}/status")
async def update_broker_status(
    broker_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Update broker connection status."""
    if status not in ["connected", "disconnected", "reconnecting", "error"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    control_tower = get_control_tower(db)
    control_tower.update_broker_status(broker_id, status)
    
    return {
        "broker_id": broker_id,
        "status": status,
        "updated_at": control_tower.broker_connections[broker_id]["last_heartbeat"],
    }


@router.post("/api/trades/queue")
async def queue_trade(
    trade_data: dict,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Queue a trade for processing."""
    if current_user.role not in ["agent", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    control_tower.queue_trade(trade_data)
    
    return {
        "status": "queued",
        "trade_id": trade_data.get("trade_id"),
        "message": "Trade queued for processing",
    }


@router.websocket("/api/feed")
async def websocket_feed(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for real-time control tower feed.
    
    Streams:
    - System metrics updates
    - New alerts
    - Session changes
    - Trade queue updates
    - Broker status changes
    
    Authentication token should be provided in query parameter: ?token=<jwt_token>
    """
    await websocket.accept()
    ws_connections.append(websocket)
    control_tower = get_control_tower(db)
    
    try:
        while True:
            # Send updates every 2 seconds
            await asyncio.sleep(2)
            
            snapshot = control_tower.get_dashboard_snapshot()
            await websocket.send_json({
                "type": "dashboard_update",
                "data": snapshot,
            })
    
    except WebSocketDisconnect:
        ws_connections.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        ws_connections.remove(websocket)


@router.get("/api/status/summary")
async def get_status_summary(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get quick status summary for dashboard header."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    control_tower = get_control_tower(db)
    metrics = control_tower.get_system_metrics()
    
    return {
        "health": metrics._calculate_health_status(),
        "active_sessions": metrics.active_sessions,
        "active_brokers": metrics.active_brokers,
        "pending_trades": metrics.pending_trades,
        "cpu_percent": metrics.cpu_percent,
        "memory_percent": metrics.memory_percent,
        "alert_count": len(metrics.alerts),
        "timestamp": metrics.timestamp.isoformat(),
    }
