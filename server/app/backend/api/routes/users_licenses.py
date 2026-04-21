"""
Users & Licenses Pillar API Routes
Endpoints for user management and subscription control.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.backend.dependencies import get_db, get_current_user
from app.backend.models import User, UserRole, License, LicenseType, LicenseStatus, LicenseAudit, RiskLimit
from app.backend.schemas import UserSchema

router = APIRouter(prefix="/admin/users-licenses", tags=["users-licenses"])


class UserCreate(BaseModel):
    email: str
    username: str
    display_name: str | None = None
    password: str
    role: UserRole = UserRole.TRADER


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class LicenseCreate(BaseModel):
    user_id: str
    license_type: LicenseType
    product_name: str
    valid_days: int = 30
    max_agents: int = 1
    max_symbols: int = 100
    has_backtesting: bool = False
    has_live_trading: bool = False


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """List all users with their license status."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    users = db.query(User).all()
    
    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "username": u.username,
                "display_name": u.display_name,
                "role": u.role.value,
                "is_active": u.is_active,
                "license": {
                    "type": (db.query(License).filter(License.user_id == u.id).first().license_type.value
                             if db.query(License).filter(License.user_id == u.id).first() else None),
                    "status": (db.query(License).filter(License.user_id == u.id).first().status.value
                               if db.query(License).filter(License.user_id == u.id).first() else "none"),
                },
                "created_at": u.created_at,
                "last_activity": None  # Would track from audit logs
            }
            for u in users
        ],
        "total": len(users)
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get detailed user information."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    licenses = db.query(License).filter(License.user_id == user_id).all()
    
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "licenses": [
            {
                "id": str(l.id),
                "type": l.license_type.value,
                "status": l.status.value,
                "product": l.product_name,
                "valid_from": l.valid_from,
                "valid_until": l.valid_until,
            }
            for l in licenses
        ]
    }


@router.post("/users")
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Create a new user."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check if user exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user (would hash password in real implementation)
    user = User(
        email=user_data.email,
        username=user_data.username,
        display_name=user_data.display_name,
        password_hash=user_data.password,  # Should be hashed
        role=user_data.role,
        is_active=True
    )
    
    # Create default risk limit
    risk_limit = RiskLimit(user_id=user.id)
    
    db.add(user)
    db.add(risk_limit)
    db.commit()
    
    return {"id": str(user.id), "email": user.email, "message": "User created successfully"}


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Update user information."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if update.display_name is not None:
        user.display_name = update.display_name
    if update.role is not None:
        user.role = update.role
    if update.is_active is not None:
        user.is_active = update.is_active
    
    db.commit()
    
    return {"message": "User updated", "user_id": user_id}


@router.get("/licenses")
async def list_licenses(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """List all licenses with optional filtering."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = db.query(License)
    
    if status:
        query = query.filter(License.status == status)
    
    licenses = query.all()
    
    return {
        "licenses": [
            {
                "id": str(l.id),
                "user_id": str(l.user_id),
                "type": l.license_type.value,
                "status": l.status.value,
                "key": l.key,
                "product": l.product_name,
                "valid_from": l.valid_from,
                "valid_until": l.valid_until,
                "features": {
                    "backtesting": l.has_backtesting,
                    "live_trading": l.has_live_trading,
                    "multi_broker": l.has_multi_broker,
                    "api_access": l.has_api_access,
                }
            }
            for l in licenses
        ],
        "total": len(licenses)
    }


@router.post("/licenses")
async def create_license(
    license_data: LicenseCreate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Create or renew a license for a user."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user = db.query(User).filter(User.id == license_data.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create license
    valid_until = datetime.utcnow() + timedelta(days=license_data.valid_days)
    
    license_obj = License(
        user_id=user.id,
        license_type=license_data.license_type,
        product_name=license_data.product_name,
        key=f"LIC-{user.id}-{datetime.utcnow().timestamp()}",
        valid_from=datetime.utcnow(),
        valid_until=valid_until,
        max_agents=license_data.max_agents,
        max_symbols=license_data.max_symbols,
        has_backtesting=license_data.has_backtesting,
        has_live_trading=license_data.has_live_trading,
    )
    
    # Create audit entry
    audit = LicenseAudit(
        license_id=license_obj.id,
        action="created",
        triggered_by=current_user.email
    )
    
    db.add(license_obj)
    db.add(audit)
    db.commit()
    
    return {
        "id": str(license_obj.id),
        "key": license_obj.key,
        "valid_until": valid_until,
        "message": "License created successfully"
    }


@router.put("/licenses/{license_id}/status")
async def update_license_status(
    license_id: str,
    status: LicenseStatus,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Update license status (activate, suspend, revoke)."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    license_obj = db.query(License).filter(License.id == license_id).first()
    
    if not license_obj:
        raise HTTPException(status_code=404, detail="License not found")
    
    old_status = license_obj.status
    license_obj.status = status
    
    audit = LicenseAudit(
        license_id=license_obj.id,
        action=f"{old_status.value}_to_{status.value}",
        triggered_by=current_user.email
    )
    
    db.add(audit)
    db.commit()
    
    return {"message": f"License status updated to {status.value}"}
