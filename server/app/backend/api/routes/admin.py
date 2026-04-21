from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.backend.api.routes._auth_helpers import resolve_admin_user
from app.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminCreateUserRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    username: str | None = None
    display_name: str | None = None
    role: str = "trader"


class UserStatusRequest(BaseModel):
    is_active: bool


class UserRoleRequest(BaseModel):
    role: str = Field(min_length=3)


class BulkRoleUpdateRequest(BaseModel):
    """Bulk update request for multiple users."""
    updates: list[dict[str, str]] = Field(
        ...,
        description="List of updates with user_id and role"
    )


class CreateAdminRequest(BaseModel):
    """Request to create admin user by super admin."""
    email: str = Field(min_length=5)
    username: str | None = None
    display_name: str | None = None


class CreateSuperAdminRequest(BaseModel):
    """Request to create super admin user by super admin."""
    email: str = Field(min_length=5)
    username: str | None = None
    display_name: str | None = None


@router.get("/overview")
async def get_admin_overview(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    admin_user = resolve_admin_user(authorization, services)
    return services.admin_overview(admin_user)


@router.get("/users")
async def get_admin_users(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> list[dict]:
    admin_user = resolve_admin_user(authorization, services)
    return services.admin_list_users(admin_user)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminCreateUserRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    admin_user = resolve_admin_user(authorization, services)
    try:
        return await services.admin_create_user(admin_user, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/users/{user_id}/status")
async def update_admin_user_status(
    user_id: str,
    payload: UserStatusRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    admin_user = resolve_admin_user(authorization, services)
    try:
        return services.admin_update_user_status(admin_user, user_id, payload.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/users/{user_id}/role")
async def update_admin_user_role(
    user_id: str,
    payload: UserRoleRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    admin_user = resolve_admin_user(authorization, services)
    try:
        return services.admin_update_user_role(admin_user, user_id, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/users/roles/bulk")
async def bulk_update_user_roles(
    payload: BulkRoleUpdateRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Bulk update roles for multiple users.
    
    Accepts list of updates with user_id and role:
    {
        "updates": [
            {"user_id": "user1", "role": "editor"},
            {"user_id": "user2", "role": "admin"},
        ]
    }
    """
    admin_user = resolve_admin_user(authorization, services)
    try:
        return services.admin_bulk_update_roles(admin_user, payload.updates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Get audit logs with pagination.
    
    Query params:
    - limit: Number of logs to return (default 100, max 1000)
    - offset: Number of logs to skip (for pagination)
    """
    admin_user = resolve_admin_user(authorization, services)
    limit = min(int(limit), 1000)
    offset = max(0, int(offset))
    return services.admin_get_audit_logs(admin_user, limit, offset)


@router.get("/audit-logs/user/{user_id}")
async def get_user_audit_logs(
    user_id: str,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Get all audit logs related to a specific user.
    
    Shows both actions performed BY this user and actions performed ON this user.
    """
    admin_user = resolve_admin_user(authorization, services)
    try:
        return services.admin_get_user_audit_logs(admin_user, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/create-admin", status_code=status.HTTP_201_CREATED)
async def super_admin_create_admin(
    payload: CreateAdminRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Super admin creates a new admin user.
    
    Only super_admin role can call this endpoint.
    Returns temporary password for the new admin.
    """
    admin_user = resolve_admin_user(authorization, services)
    try:
        return services.super_admin_create_admin(
            admin_user,
            payload.email,
            payload.username or "",
            payload.display_name or ""
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/create-super-admin", status_code=status.HTTP_201_CREATED)
async def super_admin_create_super_admin(
    payload: CreateSuperAdminRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Super admin creates another super admin user.
    
    Only super_admin role can call this endpoint.
    Returns temporary password for the new super admin.
    """
    admin_user = resolve_admin_user(authorization, services)
    try:
        return services.super_admin_create_super_admin(
            admin_user,
            payload.email,
            payload.username or "",
            payload.display_name or ""
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
