"""User profile and broker configuration routes."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.backend.api.routes._auth_helpers import resolve_bearer_user
from app.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/users", tags=["Users"])


class ProfileUpdateRequest(BaseModel):
    """Profile update request."""
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    display_name: str | None = None


class BrokerConfigRequest(BaseModel):
    """Broker configuration request."""
    name: str = Field(min_length=1)
    broker: str = Field(min_length=1)
    config: dict = Field(default_factory=dict)
    description: str | None = None


class BrokerConnectionTestRequest(BaseModel):
    """Broker connection test request."""
    broker: str = Field(min_length=1)
    config: dict = Field(default_factory=dict)


# ==================== Profile ====================

@router.get("/profile")
async def get_profile(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Get current user profile."""
    user = resolve_bearer_user(authorization, services)
    return {
        "success": True,
        "profile": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
        }
    }


@router.put("/profile")
async def update_profile(
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Update current user profile."""
    user = resolve_bearer_user(authorization, services)
    
    try:
        updated_user = await services.update_user_profile(user, dict(payload or {}))
        return {
            "success": True,
            "profile": {
                "id": updated_user.id,
                "email": updated_user.email,
                "username": updated_user.username,
                "display_name": updated_user.display_name,
                "first_name": updated_user.first_name,
                "last_name": updated_user.last_name,
                "role": updated_user.role,
            }
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ==================== Broker Configuration ====================

@router.post("/broker-config")
async def save_broker_config(
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Save broker configuration."""
    user = resolve_bearer_user(authorization, services)
    
    try:
        result = await services.save_broker_config(user, dict(payload or {}))
        return {
            "success": True,
            "profile_id": result.get("profile_id", ""),
            "message": result.get("message", "Configuration saved")
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/broker-config/{name}")
async def get_broker_config(
    name: str,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Retrieve broker configuration by name."""
    user = resolve_bearer_user(authorization, services)
    
    try:
        config = await services.get_broker_config(user, name)
        return {
            "success": True,
            "broker": config.get("broker"),
            "config": config.get("config"),
            "name": config.get("name")
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/broker-configs")
async def list_broker_configs(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """List all broker configurations for user."""
    user = resolve_bearer_user(authorization, services)
    
    try:
        configs = await services.list_broker_configs(user)
        return {
            "success": True,
            "configs": configs
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/broker-config/{name}")
async def delete_broker_config(
    name: str,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Delete broker configuration."""
    user = resolve_bearer_user(authorization, services)
    
    try:
        await services.delete_broker_config(user, name)
        return {
            "success": True,
            "message": f"Configuration '{name}' deleted"
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/broker-config/test")
async def test_broker_connection(
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Test broker connection."""
    user = resolve_bearer_user(authorization, services)
    
    try:
        result = await services.test_broker_connection(user, dict(payload or {}))
        return {
            "success": result.get("success", True),
            "message": result.get("message", "Connection successful")
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
