from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from backend.api.routes._auth_helpers import resolve_bearer_user
from backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


@router.get("/settings")
async def get_workspace_settings(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return services.get_workspace_settings(user)


@router.put("/settings")
async def update_workspace_settings(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return services.save_workspace_settings(user, dict(payload or {}))
