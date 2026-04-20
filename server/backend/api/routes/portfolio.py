from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from server.backend.api.routes._auth_helpers import resolve_bearer_user
from server.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get("/dashboard")
async def get_dashboard(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return services.get_portfolio_dashboard(user)


@router.get("/positions")
async def get_positions(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> list[dict]:
    user = resolve_bearer_user(authorization, services)
    return services.list_positions(user)


@router.get("/orders")
async def get_orders(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> list[dict]:
    user = resolve_bearer_user(authorization, services)
    return services.list_orders(user)
