from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from server.backend.api.routes._auth_helpers import resolve_bearer_user
from server.backend.dependencies import ServerServiceContainer, get_services


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember_me: bool = True


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    username: str | None = None
    display_name: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
    remember_me: bool = True


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        return await services.register_user(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login")
async def login(
    payload: LoginRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        return await services.authenticate_access(
            payload.identifier,
            payload.password,
            remember_me=bool(payload.remember_me),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me")
async def me(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    user = resolve_bearer_user(authorization, services)
    return user.as_public_dict()


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        return await services.refresh_access(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        return await services.issue_reset_token(payload.identifier)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    try:
        return await services.reset_password(payload.reset_token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
