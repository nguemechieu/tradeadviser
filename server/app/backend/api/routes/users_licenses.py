"""
Users & Licenses Pillar API Routes.

Endpoints for:
- admin user management
- license creation/renewal
- license status control
- license audit history
- risk-limit bootstrap for new users
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.app.backend.dependencies import get_current_user, get_db
from server.app.backend.models import (
    License,
    LicenseAudit,
    LicenseStatus,
    LicenseType,
    RiskLimit,
    User,
    UserRole,
)
from server.app.backend.schemas import UserSchema


router = APIRouter(
    prefix="/api/admin/users-licenses",
    tags=["users-licenses"],
)

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=64)
    firstname : str = Field(..., min_length=3, max_length=64)
    lastname: str = Field(..., min_length=3, max_length=64)
    middlename:str = Field(..., min_length=3, max_length=64)
    phonenumber: str = Field(..., min_length=3, max_length=64)
    display_name: str | None = Field(default=None, max_length=120)
    password: str = Field(..., min_length=8, max_length=256)
    role: UserRole = UserRole.TRADER


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    is_banned :bool |None=None


class LicenseCreate(BaseModel):
    user_id: str
    license_type: LicenseType
    product_name: str = Field(..., min_length=1, max_length=120)
    valid_days: int = Field(default=30, ge=1, le=3650)
    max_agents: int = Field(default=1, ge=1, le=10_000)
    max_symbols: int = Field(default=100, ge=1, le=100_000)

    has_backtesting: bool = False
    has_live_trading: bool = False
    has_multi_broker: bool = False
    has_api_access: bool = False
    has_ai_signals: bool = False
    has_advanced_risk: bool = False


class LicenseStatusUpdate(BaseModel):
    status: LicenseStatus


class LicenseRenewRequest(BaseModel):
    valid_days: int = Field(default=30, ge=1, le=3650)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _role_value(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)
    return str(role or "").strip()


def _require_admin(current_user: UserSchema) -> None:
    role = _role_value(getattr(current_user, "role", None)).lower()

    if role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


def _parse_uuid(value: str, field_name: str = "id") -> UUID:
    try:
        return UUID(str(value))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}",
        )


def _hash_password(password: str) -> str:
    return password_context.hash(password)


def _generate_license_key(product_name: str) -> str:
    product_prefix = "".join(
        char for char in str(product_name or "TRADEADVISER").upper() if char.isalnum()
    )[:8] or "TRADEADV"

    return f"{product_prefix}-{secrets.token_urlsafe(24)}"


def _serialize_user(user: User, license_obj: License | None = None) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "firstname":user.firstname,
        "lastname":user.lastname,
        "middlename":user.middlename,
        "phonenumber": user.phonenumber,
        "display_name": user.display_name,
        "role": _role_value(user.role),
        "is_active": bool(user.is_active),
        "created_at": user.created_at,
        "license": (
            {
                "id": str(license_obj.id),
                "type": license_obj.license_type.value,
                "status": license_obj.status.value,
                "product": license_obj.product_name,
                "valid_from": license_obj.valid_from,
                "valid_until": license_obj.valid_until,
            }
            if license_obj is not None
            else {
                "type": None,
                "status": "none",
            }
        ),
    }


def _serialize_license(license_obj: License) -> dict[str, Any]:
    return {
        "id": str(license_obj.id),
        "user_id": str(license_obj.user_id),
        "type": license_obj.license_type.value,
        "status": license_obj.status.value,
        "key": license_obj.key,
        "product": license_obj.product_name,
        "valid_from": license_obj.valid_from,
        "valid_until": license_obj.valid_until,
        "limits": {
            "max_agents": license_obj.max_agents,
            "max_symbols": license_obj.max_symbols,
        },
        "features": {
            "backtesting": bool(getattr(license_obj, "has_backtesting", False)),
            "live_trading": bool(getattr(license_obj, "has_live_trading", False)),
            "multi_broker": bool(getattr(license_obj, "has_multi_broker", False)),
            "api_access": bool(getattr(license_obj, "has_api_access", False)),
            "ai_signals": bool(getattr(license_obj, "has_ai_signals", False)),
            "advanced_risk": bool(getattr(license_obj, "has_advanced_risk", False)),
        },
    }


def _latest_license_by_user(db: Session, user_ids: list[Any]) -> dict[Any, License]:
    if not user_ids:
        return {}

    licenses = (
        db.query(License)
        .filter(License.user_id.in_(user_ids))
        .order_by(License.user_id.asc(), License.valid_until.desc())
        .all()
    )

    latest: dict[Any, License] = {}

    for item in licenses:
        if item.user_id not in latest:
            latest[item.user_id] = item

    return latest


def _add_license_audit(
        db: Session,
        *,
        license_id: Any,
        action: str,
        current_user: UserSchema,
        metadata: dict[str, Any] | None = None,
) -> LicenseAudit:
    audit = LicenseAudit(
        license_id=license_id,
        action=action,
        triggered_by=getattr(current_user, "email", None),
    )

    if metadata is not None and hasattr(audit, "metadata"):
        setattr(audit, "metadata", metadata)

    db.add(audit)
    return audit


# ---------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------


@router.get("/users")
async def list_users(
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """List all users with latest license status."""

    _require_admin(current_user)

    users = db.query(User).order_by(User.created_at.desc()).all()
    latest_licenses = _latest_license_by_user(db, [user.id for user in users])

    return {
        "users": [
            {
                **_serialize_user(user, latest_licenses.get(user.id)),
                "last_activity": None,
            }
            for user in users
        ],
        "total": len(users),
    }


@router.get("/users/{user_id}")
async def get_user(
        user_id: str,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Get detailed user information."""

    _require_admin(current_user)

    user_uuid = _parse_uuid(user_id, "user_id")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    licenses = (
        db.query(License)
        .filter(License.user_id == user.id)
        .order_by(License.valid_until.desc())
        .all()
    )

    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "role": _role_value(user.role),
        "is_active": bool(user.is_active),
        "created_at": user.created_at,
        "licenses": [_serialize_license(item) for item in licenses],
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
        user_data: UserCreate,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Create a new user."""

    _require_admin(current_user)

    existing = (
        db.query(User)
        .filter(
            (User.email == str(user_data.email).lower())
            | (User.username == user_data.username)
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )

    user = User(
        email=str(user_data.email).lower(),
        username=user_data.username.strip(),
        display_name=user_data.display_name,
        password_hash=_hash_password(user_data.password),
        role=user_data.role,
        is_active=True,
    )

    db.add(user)
    db.flush()

    risk_limit = RiskLimit(user_id=user.id)
    db.add(risk_limit)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )
    except Exception:
        db.rollback()
        raise

    db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "message": "User created successfully",
    }


@router.put("/users/{user_id}")
async def update_user(
        user_id: str,
        update: UserUpdate,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Update user information."""

    _require_admin(current_user)

    user_uuid = _parse_uuid(user_id, "user_id")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if update.display_name is not None:
        user.display_name = update.display_name

    if update.role is not None:
        user.role = update.role

    if update.is_active is not None:
        user.is_active = update.is_active

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "User updated",
        "user_id": user_id,
    }


# ---------------------------------------------------------------------
# License endpoints
# ---------------------------------------------------------------------


@router.get("/licenses")
async def list_licenses(
        license_status: LicenseStatus | None = Query(default=None, alias="status"),
        user_id: str | None = None,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """List all licenses with optional filtering."""

    _require_admin(current_user)

    query = db.query(License)

    if license_status is not None:
        query = query.filter(License.status == license_status)

    if user_id:
        query = query.filter(License.user_id == _parse_uuid(user_id, "user_id"))

    licenses = query.order_by(License.valid_until.desc()).all()

    return {
        "licenses": [_serialize_license(item) for item in licenses],
        "total": len(licenses),
    }


@router.post("/licenses", status_code=status.HTTP_201_CREATED)
async def create_license(
        license_data: LicenseCreate,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Create a license for a user."""

    _require_admin(current_user)

    user_uuid = _parse_uuid(license_data.user_id, "user_id")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    now = _utc_now()
    valid_until = now + timedelta(days=license_data.valid_days)

    license_obj = License(
        user_id=user.id,
        license_type=license_data.license_type,
        product_name=license_data.product_name,
        key=_generate_license_key(license_data.product_name),
        valid_from=now,
        valid_until=valid_until,
        status=LicenseStatus.ACTIVE,
        max_agents=license_data.max_agents,
        max_symbols=license_data.max_symbols,
        has_backtesting=license_data.has_backtesting,
        has_live_trading=license_data.has_live_trading,
    )

    if hasattr(license_obj, "has_multi_broker"):
        license_obj.has_multi_broker = license_data.has_multi_broker

    if hasattr(license_obj, "has_api_access"):
        license_obj.has_api_access = license_data.has_api_access

    if hasattr(license_obj, "has_ai_signals"):
        license_obj.has_ai_signals = license_data.has_ai_signals

    if hasattr(license_obj, "has_advanced_risk"):
        license_obj.has_advanced_risk = license_data.has_advanced_risk

    db.add(license_obj)
    db.flush()

    _add_license_audit(
        db,
        license_id=license_obj.id,
        action="created",
        current_user=current_user,
        metadata={
            "valid_days": license_data.valid_days,
            "product_name": license_data.product_name,
        },
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License key collision or invalid license data",
        )
    except Exception:
        db.rollback()
        raise

    db.refresh(license_obj)

    return {
        "id": str(license_obj.id),
        "key": license_obj.key,
        "valid_until": license_obj.valid_until,
        "message": "License created successfully",
    }


@router.put("/licenses/{license_id}/status")
async def update_license_status(
        license_id: str,
        update: LicenseStatusUpdate,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Update license status: active, suspended, revoked, expired."""

    _require_admin(current_user)

    license_uuid = _parse_uuid(license_id, "license_id")

    license_obj = db.query(License).filter(License.id == license_uuid).first()

    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )

    old_status = license_obj.status
    license_obj.status = update.status

    _add_license_audit(
        db,
        license_id=license_obj.id,
        action=f"{old_status.value}_to_{update.status.value}",
        current_user=current_user,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": f"License status updated to {update.status.value}",
        "license_id": license_id,
    }


@router.post("/licenses/{license_id}/renew")
async def renew_license(
        license_id: str,
        renewal: LicenseRenewRequest,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Renew or extend an existing license."""

    _require_admin(current_user)

    license_uuid = _parse_uuid(license_id, "license_id")

    license_obj = db.query(License).filter(License.id == license_uuid).first()

    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )

    now = _utc_now()
    base_date = license_obj.valid_until if license_obj.valid_until and license_obj.valid_until > now else now
    old_valid_until = license_obj.valid_until
    license_obj.valid_until = base_date + timedelta(days=renewal.valid_days)

    if license_obj.status == LicenseStatus.EXPIRED:
        license_obj.status = LicenseStatus.ACTIVE

    _add_license_audit(
        db,
        license_id=license_obj.id,
        action="renewed",
        current_user=current_user,
        metadata={
            "old_valid_until": old_valid_until.isoformat() if old_valid_until else None,
            "new_valid_until": license_obj.valid_until.isoformat(),
            "valid_days": renewal.valid_days,
        },
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "License renewed successfully",
        "license_id": license_id,
        "valid_until": license_obj.valid_until,
        "status": license_obj.status.value,
    }


@router.get("/licenses/{license_id}/audit")
async def get_license_audit(
        license_id: str,
        db: Session = Depends(get_db),
        current_user: UserSchema = Depends(get_current_user),
):
    """Return audit history for one license."""

    _require_admin(current_user)

    license_uuid = _parse_uuid(license_id, "license_id")

    license_obj = db.query(License).filter(License.id == license_uuid).first()

    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )

    rows = (
        db.query(LicenseAudit)
        .filter(LicenseAudit.license_id == license_obj.id)
        .order_by(LicenseAudit.created_at.desc())
        .all()
    )

    return {
        "license_id": license_id,
        "audit": [
            {
                "id": str(row.id),
                "action": row.action,
                "triggered_by": row.triggered_by,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": len(rows),
    }