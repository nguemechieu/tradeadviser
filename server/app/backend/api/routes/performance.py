from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from server.app.backend.api.routes._auth_helpers import resolve_bearer_user
from server.app.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/api/v3/performance", tags=["Performance"])


@router.get("")
async def get_performance(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return services.performance(user)
