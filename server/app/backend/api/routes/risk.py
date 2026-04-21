"""
Risk Pillar API Routes
Endpoints for portfolio risk monitoring, risk limits, and breach alerts.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.backend.dependencies import get_db, get_current_user
from app.backend.models import RiskLimit, RiskBreach, User, UserRole
from app.backend.schemas import UserSchema

router = APIRouter(prefix="/admin/risk", tags=["risk"])


class RiskLimitUpdate(BaseModel):
    max_position_size: float | None = None
    max_total_positions: int | None = None
    daily_loss_limit: float | None = None
    max_leverage: float | None = None


@router.get("/overview")
async def get_risk_overview(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get platform-wide risk overview."""
    if current_user.role not in ["risk_manager", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get recent breaches
    recent_breaches = db.query(RiskBreach).order_by(
        RiskBreach.created_at.desc()
    ).limit(10).all()
    
    # Get users near limits
    risk_limits = db.query(RiskLimit).all()
    
    return {
        "total_users": db.query(User).count(),
        "users_with_limits": len(risk_limits),
        "recent_breaches": len(recent_breaches),
        "breach_types": list(set(b.limit_type for b in recent_breaches)) if recent_breaches else [],
        "timestamp": recent_breaches[0].created_at if recent_breaches else None
    }


@router.get("/limits/{user_id}")
async def get_user_risk_limits(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get risk limits for a specific user."""
    if current_user.role not in ["risk_manager", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    limit = db.query(RiskLimit).filter(RiskLimit.user_id == user_id).first()
    
    if not limit:
        raise HTTPException(status_code=404, detail="Risk limit not found")
    
    return {
        "user_id": user_id,
        "position_limits": {
            "max_position_size": limit.max_position_size,
            "max_total_positions": limit.max_total_positions,
            "max_open_orders": limit.max_open_orders,
        },
        "daily_limits": {
            "loss_limit": limit.daily_loss_limit,
            "win_limit": limit.daily_win_limit,
            "max_trades": limit.max_trades_per_day,
        },
        "portfolio_limits": {
            "max_leverage": limit.max_leverage,
            "max_portfolio_value": limit.max_portfolio_value,
        },
        "trading_hours": {
            "start": f"{limit.trading_start_hour:02d}:00",
            "end": f"{limit.trading_end_hour:02d}:00",
        }
    }


@router.put("/limits/{user_id}")
async def update_user_risk_limits(
    user_id: str,
    update: RiskLimitUpdate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Update risk limits for a user."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    limit = db.query(RiskLimit).filter(RiskLimit.user_id == user_id).first()
    
    if not limit:
        raise HTTPException(status_code=404, detail="Risk limit not found")
    
    if update.max_position_size is not None:
        limit.max_position_size = update.max_position_size
    if update.max_total_positions is not None:
        limit.max_total_positions = update.max_total_positions
    if update.daily_loss_limit is not None:
        limit.daily_loss_limit = update.daily_loss_limit
    if update.max_leverage is not None:
        limit.max_leverage = update.max_leverage
    
    db.commit()
    
    return {"message": "Risk limits updated", "user_id": user_id}


@router.get("/breaches")
async def get_risk_breaches(
    user_id: str | None = None,
    limit_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get risk limit breaches."""
    if current_user.role not in ["risk_manager", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = db.query(RiskBreach).order_by(RiskBreach.created_at.desc())
    
    if user_id:
        query = query.filter(RiskBreach.user_id == user_id)
    if limit_type:
        query = query.filter(RiskBreach.limit_type == limit_type)
    
    breaches = query.limit(100).all()
    
    return {
        "breaches": [
            {
                "user_id": str(b.user_id),
                "limit_type": b.limit_type,
                "value": b.value,
                "limit": b.limit,
                "action": b.action_taken,
                "timestamp": b.created_at
            }
            for b in breaches
        ]
    }


@router.get("/portfolio-heat-map")
async def get_portfolio_heat_map(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get heat map of portfolio risk across all users."""
    if current_user.role not in ["risk_manager", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # This would aggregate positions, exposures, and risk metrics
    # across all active users for a heat map visualization
    
    return {
        "users": {},  # Placeholder for actual heat map data
        "timestamp": None
    }


@router.get("/exposure-by-symbol")
async def get_exposure_by_symbol(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get aggregate platform exposure by trading symbol."""
    if current_user.role not in ["risk_manager", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return {
        "exposures": {},  # Placeholder for symbol exposure data
        "total_platform_exposure": 0,
        "timestamp": None
    }
