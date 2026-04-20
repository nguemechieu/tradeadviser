"""Session and authentication routes for the server core."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/api/v1/session", tags=["session"])


class SessionLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class SessionResumeRequest(BaseModel):
    session_id: str = Field(min_length=1)


@router.post("/login")
async def login(
    payload: SessionLoginRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        return await services.authenticate(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/resume")
async def resume_session(
    payload: SessionResumeRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    response = await services.resume(payload.session_id)
    if response.get("success"):
        return response
    error = dict(response.get("error") or {})
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error.get("message") or "Session not found or expired."),
    )
