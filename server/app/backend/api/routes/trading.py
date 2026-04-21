"""Trading command routes for the server core."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.backend.api.routes._auth_helpers import resolve_optional_bearer_user
from app.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


@router.post("/broker/connect")
async def connect_broker(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        user = resolve_optional_bearer_user(authorization, services)
        return await services.connect_broker(dict(payload or {}), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/subscriptions/market-data")
async def request_market_data_subscription(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        user = resolve_optional_bearer_user(authorization, services)
        return await services.update_market_subscription(dict(payload or {}), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/orders")
async def place_order(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        user = resolve_optional_bearer_user(authorization, services)
        return await services.place_order(dict(payload or {}), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/orders/cancel")
async def cancel_order(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        user = resolve_optional_bearer_user(authorization, services)
        return await services.cancel_order(dict(payload or {}), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/positions/close")
async def close_position(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        user = resolve_optional_bearer_user(authorization, services)
        return await services.close_position(dict(payload or {}), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/kill-switch")
async def trigger_kill_switch(
    payload: dict,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        user = resolve_optional_bearer_user(authorization, services)
        response = await services.trigger_kill_switch(dict(payload or {}), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if response.get("success"):
        return response
    error = dict(response.get("error") or {})
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error.get("message") or "Kill switch request failed."),
    )
