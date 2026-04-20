"""
Operations Pillar API Routes
Endpoints for system monitoring, broker connectivity, deployment status.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.backend.dependencies import get_db, get_current_user
from server.backend.models import User, SystemHealth, TradeStats
from server.backend.schemas import UserSchema

router = APIRouter(prefix="/admin/operations", tags=["operations"])


@router.get("/health")
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get current system health status."""
    # Check user has operations role
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    health = db.query(SystemHealth).order_by(SystemHealth.created_at.desc()).first()
    
    return {
        "status": health.overall_status if health else "offline",
        "services": {
            "database": {"status": health.database_status, "response_ms": health.database_response_ms} if health else None,
            "api": {"status": health.api_status, "response_ms": health.api_response_ms, "connections": health.active_connections} if health else None,
            "websocket": {"status": health.ws_status, "clients": health.connected_clients} if health else None,
            "broker": health.broker_details if health else None,
            "cache": health.cache_status if health else None,
            "queue": {"status": health.queue_status, "pending": health.pending_messages} if health else None,
        },
        "resources": {
            "cpu_percent": health.cpu_percent if health else 0,
            "memory_percent": health.memory_percent if health else 0,
            "disk_percent": health.disk_percent if health else 0,
        },
        "message": health.status_message if health else "No health data available"
    }


@router.get("/broker-status")
async def get_broker_status(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get broker connectivity status for each configured broker."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    health = db.query(SystemHealth).order_by(SystemHealth.created_at.desc()).first()
    
    return {
        "overall": health.broker_status if health else "offline",
        "brokers": health.broker_details if health else {},
        "last_update": health.created_at if health else None
    }


@router.get("/active-connections")
async def get_active_connections(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get count of active API and WebSocket connections."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    health = db.query(SystemHealth).order_by(SystemHealth.created_at.desc()).first()
    
    return {
        "api_connections": health.active_connections if health else 0,
        "websocket_clients": health.connected_clients if health else 0,
        "timestamp": health.created_at if health else None
    }


@router.get("/trade-stats")
async def get_trade_statistics(
    period: str = "1h",
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get aggregate trading statistics for the platform."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    stats = db.query(TradeStats).filter(TradeStats.period == period).order_by(
        TradeStats.created_at.desc()
    ).first()
    
    return {
        "period": period,
        "trades": {
            "total": stats.total_trades if stats else 0,
            "average_pnl": stats.average_trade_pnl if stats else 0,
            "win_rate": stats.average_win_rate if stats else 0,
        },
        "users": {
            "total": stats.total_users if stats else 0,
            "active_24h": stats.active_users if stats else 0,
        },
        "volume": {
            "total": stats.total_volume if stats else 0,
            "average_trade_size": stats.average_trade_size if stats else 0,
        },
        "agents": {
            "active": stats.active_agents if stats else 0,
            "total": stats.total_agents if stats else 0,
        },
        "platform_pnl": stats.total_platform_pnl if stats else 0,
        "timestamp": stats.created_at if stats else None
    }


@router.get("/deployment-status")
async def get_deployment_status(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get deployment and infrastructure status."""
    if current_user.role not in ["operations", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    health = db.query(SystemHealth).order_by(SystemHealth.created_at.desc()).first()
    
    return {
        "backend": health.overall_status if health else "offline",
        "frontend": "online",  # Would come from separate health check
        "database": health.database_status if health else "offline",
        "cache": health.cache_status if health else "offline",
        "queue": health.queue_status if health else "offline",
        "timestamp": health.created_at if health else None
    }
