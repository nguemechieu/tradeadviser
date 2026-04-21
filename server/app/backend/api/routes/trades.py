from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from app.backend.api.routes._auth_helpers import resolve_bearer_user
from app.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/trades", tags=["Trades"])


@router.get("")
async def list_trade_entries(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    services: ServerServiceContainer = Depends(get_services),
) -> list[dict]:
    user = resolve_bearer_user(authorization, services)
    return services.list_trades(user, limit=limit)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_trade_entry(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return services.record_trade(user, dict(payload or {}))
