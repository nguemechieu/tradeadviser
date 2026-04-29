from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from server.app.backend.api.routes._auth_helpers import resolve_bearer_user
from server.app.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/api/v3/portfolio", tags=["Portfolio"])


@router.get("/api/dashboard")
async def get_dashboard(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return services.get_portfolio_dashboard(user)


@router.get("/api/positions")
async def get_positions(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> list[dict]:
    user = resolve_bearer_user(authorization, services)
    return services.list_positions(user)


@router.get("/api/orders")
async def get_orders(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> list[dict]:
    user = resolve_bearer_user(authorization, services)
    return services.list_orders(user)
