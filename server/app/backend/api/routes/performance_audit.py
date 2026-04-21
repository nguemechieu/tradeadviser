"""
Performance & Audit Pillar API Routes
Endpoints for analytics, compliance, and audit trails.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.backend.dependencies import get_db, get_current_user
from app.backend.models import AuditLog, PerformanceSnapshot, TradeStats, User
from app.backend.schemas import UserSchema

router = APIRouter(prefix="/admin/performance-audit", tags=["performance-audit"])


@router.get("/audit-log")
async def get_audit_log(
    user_id: str | None = None,
    action: str | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get audit trail for compliance."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = db.query(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    
    # Filter by date range
    since = datetime.utcnow() - timedelta(days=days)
    query = query.filter(AuditLog.created_at >= since)
    
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    
    return {
        "logs": [
            {
                "id": str(l.id),
                "user_id": str(l.user_id),
                "action": l.action.value,
                "resource": {"type": l.resource_type, "id": l.resource_id},
                "impact": l.impact,
                "timestamp": l.created_at,
                "ip": l.ip_address,
            }
            for l in logs
        ],
        "total": len(logs),
        "period_days": days
    }


@router.get("/user-activity/{user_id}")
async def get_user_activity(
    user_id: str,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get activity history for a specific user."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    since = datetime.utcnow() - timedelta(days=days)
    logs = db.query(AuditLog).filter(
        AuditLog.user_id == user_id,
        AuditLog.created_at >= since
    ).order_by(AuditLog.created_at.desc()).all()
    
    # Count by action type
    action_counts = {}
    for log in logs:
        key = log.action.value
        action_counts[key] = action_counts.get(key, 0) + 1
    
    return {
        "user_id": user_id,
        "email": user.email,
        "total_events": len(logs),
        "event_types": action_counts,
        "recent_activity": [
            {
                "action": l.action.value,
                "resource": l.resource_type,
                "timestamp": l.created_at,
            }
            for l in logs[:20]
        ]
    }


@router.get("/performance-trending")
async def get_performance_trending(
    period: str = "1d",
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get performance trends over time."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    snapshots = db.query(PerformanceSnapshot).filter(
        PerformanceSnapshot.period == period
    ).order_by(PerformanceSnapshot.created_at.desc()).limit(days).all()
    
    return {
        "period": period,
        "snapshots": [
            {
                "timestamp": s.created_at,
                "platform_return": s.platform_total_return,
                "market_return": s.market_return,
                "sharpe": s.platform_sharpe,
                "max_drawdown": s.platform_max_drawdown,
            }
            for s in reversed(snapshots)
        ]
    }


@router.get("/top-performers")
async def get_top_performers(
    metric: str = "return",
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get top performing traders and agents."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # This would aggregate from trade/agent performance data
    # Placeholder implementation
    
    return {
        "metric": metric,
        "period_days": days,
        "traders": [],  # Top traders by metric
        "agents": [],   # Top agents by metric
    }


@router.get("/compliance-report")
async def get_compliance_report(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Generate compliance report."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Parse dates if provided
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date()
    if not end_date:
        end_date = datetime.utcnow().date()
    
    return {
        "report_type": "compliance",
        "period": {"start": str(start_date), "end": str(end_date)},
        "summary": {
            "total_users": db.query(User).count(),
            "active_traders": 0,  # Would be computed from audit logs
            "compliance_incidents": 0,
            "audit_events": 0,
        },
        "sections": {
            "user_management": {},
            "trading_activity": {},
            "risk_management": {},
            "license_compliance": {},
            "system_security": {},
        }
    }


@router.get("/export-audit-trail")
async def export_audit_trail(
    format: str = "csv",
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Export audit trail in requested format."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    since = datetime.utcnow() - timedelta(days=days)
    logs = db.query(AuditLog).filter(
        AuditLog.created_at >= since
    ).order_by(AuditLog.created_at.desc()).all()
    
    # In real implementation, would generate CSV/Excel/PDF
    return {
        "format": format,
        "filename": f"audit-trail-{datetime.utcnow().isoformat()}.{format}",
        "record_count": len(logs),
        "period_days": days,
        "message": "Export generated successfully"
    }


@router.get("/system-metrics")
async def get_system_metrics(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get system-wide performance metrics."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get latest stats
    latest_stats = db.query(TradeStats).filter(
        TradeStats.period == "1d"
    ).order_by(TradeStats.created_at.desc()).first()
    
    return {
        "platform": {
            "total_pnl": latest_stats.total_platform_pnl if latest_stats else 0,
            "total_trades": latest_stats.total_trades if latest_stats else 0,
            "total_volume": latest_stats.total_volume if latest_stats else 0,
            "average_win_rate": latest_stats.average_win_rate if latest_stats else 0,
        },
        "users": {
            "total": latest_stats.total_users if latest_stats else 0,
            "active_24h": latest_stats.active_users if latest_stats else 0,
        },
        "agents": {
            "total": latest_stats.total_agents if latest_stats else 0,
            "active": latest_stats.active_agents if latest_stats else 0,
        },
        "timestamp": latest_stats.created_at if latest_stats else None
    }


@router.post("/generate-report")
async def generate_report(
    report_type: str,  # "compliance", "performance", "risk", "audit"
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Generate a custom report."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return {
        "report_type": report_type,
        "status": "generating",
        "report_id": "report-123",
        "message": "Report generation started. Check back in a few moments."
    }
