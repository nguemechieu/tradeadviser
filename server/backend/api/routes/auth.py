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
    username: str = Field(min_length=3)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    middle_name: str | None = None
    phone_number: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class AdminCreateUserRequest(BaseModel):
    email: str = Field(min_length=3)
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    middle_name: str | None = None
    phone_number: str | None = None
    role: str = Field(default="trader")  # trader, editor, or admin
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
    """Public registration endpoint - always creates trader role users."""
    try:
        # Force trader role for public registration
        return await services.register_user(payload.model_dump(), role="trader")
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


@router.post("/admin/create-user", status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    payload: AdminCreateUserRequest,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Admin-only endpoint to create users with custom roles."""
    try:
        # Verify admin privileges
        admin_user = resolve_bearer_user(authorization, services)
        if admin_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create users")
        
        # Create user with specified role
        normalized_role = payload.role.lower() if payload.role else "trader"
        if normalized_role not in ("trader", "editor", "admin"):
            normalized_role = "trader"
        
        user_data = {
            "email": payload.email,
            "username": payload.username,
            "password": payload.password,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "middle_name": payload.middle_name,
            "phone_number": payload.phone_number,
        }
        
        return await services.register_user(user_data, role=normalized_role)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/admin/users/{user_id}/role")
async def admin_update_user_role(
    user_id: str,
    role: str,
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Admin-only endpoint to update user roles."""
    try:
        # Verify admin privileges
        admin_user = resolve_bearer_user(authorization, services)
        if admin_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update user roles")
        
        # Update user role
        normalized_role = role.lower() if role else "trader"
        if normalized_role not in ("trader", "editor", "admin"):
            normalized_role = "trader"
        
        user = services.find_user(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user.role = normalized_role
        return {
            "message": "User role updated successfully",
            "user": user.as_public_dict()
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/admin/users")
async def admin_list_users(
    authorization: str | None = Header(default=None),
    services: ServerServiceContainer = Depends(get_services),
) -> dict:
    """Admin-only endpoint to list all users."""
    try:
        # Verify admin privileges
        admin_user = resolve_bearer_user(authorization, services)
        if admin_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can list users")
        
        # Get all users
        users = [user.as_public_dict() for user in services.users.values()]
        return {
            "total": len(users),
            "users": users
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
