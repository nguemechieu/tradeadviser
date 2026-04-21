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
