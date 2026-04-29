from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from server.app.backend.api.routes._auth_helpers import resolve_bearer_user
from server.app.backend.dependencies import ServerServiceContainer, get_services
from server.app.backend.models.utils import (
    CreateApiKeyRequest,
    TwoFactorDisableRequest,
    TwoFactorSetupRequest,
    TwoFactorVerifyRequest,
    UpdateApiKeyRequest,
)


router = APIRouter(prefix="/api/v3/auth", tags=["Authentication"])


# ============================================================
# Base Schemas
# ============================================================

class AuthBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# ============================================================
# Request Schemas
# ============================================================

class LoginRequest(AuthBaseModel):
    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember_me: bool = True
    device_name: str | None = None
    device_id: str | None = None


class RegisterRequest(AuthBaseModel):
    email: EmailStr
    password: str = Field(min_length=6)

    username: str | None = None
    display_name: str | None = None

    firstname: str | None = None
    middlename: str | None = None
    lastname: str | None = None

    phone: str | None = None
    birthdate: str | None = None


class RefreshRequest(AuthBaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(AuthBaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(AuthBaseModel):
    identifier: str = Field(min_length=1)


class ResetPasswordRequest(AuthBaseModel):
    reset_token: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class ChangePasswordRequest(AuthBaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class VerifyEmailRequest(AuthBaseModel):
    verification_token: str = Field(min_length=1)


class ResendVerificationRequest(AuthBaseModel):
    email: EmailStr


class UpdateProfileRequest(AuthBaseModel):
    username: str | None = None
    display_name: str | None = None

    firstname: str | None = None
    middlename: str | None = None
    lastname: str | None = None

    phone: str | None = None
    birthdate: str | None = None


class DeactivateAccountRequest(AuthBaseModel):
    password: str = Field(min_length=1)
    reason: str | None = None


class DeleteAccountRequest(AuthBaseModel):
    password: str = Field(min_length=1)
    confirmation: str = Field(min_length=1)
    reason: str | None = None


# ============================================================
# Helpers
# ============================================================

def _current_user_from_header(
        authorization: str | None,
        services: ServerServiceContainer,
) -> Any:
    return resolve_bearer_user(authorization, services)


def _user_id(user: Any) -> str:
    value = getattr(user, "id", None) or getattr(user, "user_id", None)

    if value is None and isinstance(user, dict):
        value = user.get("id") or user.get("user_id")

    if value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user.",
        )

    return str(value)


def _public_user(user: Any) -> dict[str, Any]:
    if hasattr(user, "as_public_dict"):
        return user.as_public_dict()

    if hasattr(user, "model_dump"):
        data = user.model_dump()
    elif isinstance(user, dict):
        data = dict(user)
    else:
        data = dict(vars(user))

    data.pop("password", None)
    data.pop("password_hash", None)
    data.pop("hashed_password", None)

    return data


# ============================================================
# Registration / Login
# ============================================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
        payload: RegisterRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        return await services.register_user(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/login")
async def login(
        payload: LoginRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        return await services.authenticate_access(
            identifier=payload.identifier,
            password=payload.password,
            remember_me=payload.remember_me,
            device_name=payload.device_name,
            device_id=payload.device_id,
        )
    except TypeError:
        # Backward compatible fallback if your current service does not yet
        # support device_name/device_id.
        try:
            return await services.authenticate_access(
                payload.identifier,
                payload.password,
                remember_me=payload.remember_me,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/refresh")
async def refresh(
        payload: RefreshRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        return await services.refresh_access(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/logout")
async def logout(
        payload: LogoutRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        return await services.logout_user(
            user_id=_user_id(user),
            refresh_token=payload.refresh_token,
        )
    except AttributeError:
        return {"message": "Logout accepted."}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/logout-all")
async def logout_all(
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        return await services.logout_all_sessions(user_id=_user_id(user))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# Current User / Profile
# ============================================================

@router.get("/me")
async def me(
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)
    return _public_user(user)


@router.get("/profile")
async def get_profile(
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        return await services.get_user_profile(user_id=_user_id(user))
    except AttributeError:
        return _public_user(user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch("/profile")
async def update_profile(
        payload: UpdateProfileRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)
    update_data = payload.model_dump(exclude_unset=True)

    try:
        return await services.update_user_profile(
            user_id=_user_id(user),
            data=update_data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# Availability Checks
# ============================================================

@router.get("/username-available")
async def username_available(
        username: str = Query(min_length=1),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        available = await services.is_username_available(username)
        return {"username": username, "available": bool(available)}
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Username availability service is not implemented.",
        )


@router.get("/email-available")
async def email_available(
        email: EmailStr,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        available = await services.is_email_available(str(email))
        return {"email": str(email), "available": bool(available)}
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Email availability service is not implemented.",
        )


# ============================================================
# Password Management
# ============================================================

@router.post("/forgot-password")
async def forgot_password(
        payload: ForgotPasswordRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        await services.issue_reset_token(payload.identifier)
    except ValueError:
        # Do not leak whether the account exists.
        pass

    return {
        "message": "If the account exists, password reset instructions were generated."
    }


@router.post("/reset-password")
async def reset_password(
        payload: ResetPasswordRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        return await services.reset_password(
            payload.reset_token,
            payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/change-password")
async def change_password(
        payload: ChangePasswordRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        return await services.change_password(
            user_id=_user_id(user),
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# Email Verification
# ============================================================

@router.post("/verify-email")
async def verify_email(
        payload: VerifyEmailRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        return await services.verify_email(payload.verification_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/resend-verification")
async def resend_verification(
        payload: ResendVerificationRequest,
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    try:
        await services.resend_email_verification(str(payload.email))
    except ValueError:
        # Do not leak whether the account exists.
        pass

    return {
        "message": "If the account exists and is unverified, a verification email was generated."
    }


# ============================================================
# Sessions / Devices
# ============================================================

@router.get("/sessions")
async def list_sessions(
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        sessions = await services.list_user_sessions(user_id=_user_id(user))
        return {"sessions": sessions}
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Session listing service is not implemented.",
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
        session_id: str,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        return await services.revoke_user_session(
            user_id=_user_id(user),
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/validate-token")
async def validate_token(
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    return {
        "valid": True,
        "user": _public_user(user),
    }


# ============================================================
# Account Lifecycle
# ============================================================

@router.post("/deactivate")
async def deactivate_account(
        payload: DeactivateAccountRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    try:
        return await services.deactivate_account(
            user_id=_user_id(user),
            password=payload.password,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/delete-account")
async def delete_account(
        payload: DeleteAccountRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    user = _current_user_from_header(authorization, services)

    if payload.confirmation.strip().upper() not in {"DELETE", "DELETE MY ACCOUNT"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid deletion confirmation.",
        )

    try:
        return await services.delete_account(
            user_id=_user_id(user),
            password=payload.password,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# Two-Factor Authentication
# ============================================================

@router.post("/2fa/setup")
async def setup_two_factor(
        payload: TwoFactorSetupRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Start 2FA setup for the authenticated user.

    Expected service behavior:
    - Verify the user's password.
    - Generate a TOTP secret.
    - Store it temporarily until verification.
    - Return QR provisioning URI or QR image data.
    """

    user = _current_user_from_header(authorization, services)

    try:
        return await services.setup_two_factor(
            user_id=_user_id(user),
            password=payload.password,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Two-factor setup service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/2fa/verify")
async def verify_two_factor(
        payload: TwoFactorVerifyRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Verify a 2FA code.

    This can be used for:
    - completing initial 2FA setup
    - verifying a login challenge
    - confirming sensitive actions
    """

    user = _current_user_from_header(authorization, services)

    try:
        return await services.verify_two_factor(
            user_id=_user_id(user),
            code=payload.code,
            remember_device=payload.remember_device,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Two-factor verification service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/2fa/disable")
async def disable_two_factor(
        payload: TwoFactorDisableRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Disable 2FA for the authenticated user.

    Requires both password and a valid 2FA code.
    """

    user = _current_user_from_header(authorization, services)

    try:
        return await services.disable_two_factor(
            user_id=_user_id(user),
            password=payload.password,
            code=payload.code,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Two-factor disable service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ============================================================
# API Keys
# ============================================================

@router.get("/api-keys")
async def list_api_keys(
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    List API keys for the authenticated user.

    Do not return raw key secrets here.
    Only return metadata such as id, name, scopes, created_at, last_used_at.
    """

    user = _current_user_from_header(authorization, services)

    try:
        keys = await services.list_api_keys(user_id=_user_id(user))
        return {"api_keys": keys}
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key listing service is not implemented.",
        )


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
        payload: CreateApiKeyRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Create a new API key.

    The raw API key should only be returned once.
    Store only a hash of the key in the database.
    """

    user = _current_user_from_header(authorization, services)

    try:
        return await services.create_api_key(
            user_id=_user_id(user),
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key creation service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/api-keys/{key_id}")
async def get_api_key(
        key_id: str,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Get API key metadata.

    Never return the raw key secret.
    """

    user = _current_user_from_header(authorization, services)

    try:
        return await services.get_api_key(
            user_id=_user_id(user),
            key_id=key_id,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key detail service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch("/api-keys/{key_id}")
async def update_api_key(
        key_id: str,
        payload: UpdateApiKeyRequest,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Update API key metadata.

    Useful for renaming, changing scopes, or disabling without deleting.
    """

    user = _current_user_from_header(authorization, services)
    update_data = payload.model_dump(exclude_unset=True)

    try:
        return await services.update_api_key(
            user_id=_user_id(user),
            key_id=key_id,
            data=update_data,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key update service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
        key_id: str,
        authorization: str | None = Header(default=None),
        services: ServerServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    """
    Revoke/delete an API key.

    For financial software, soft revoke is usually better than hard delete.
    """

    user = _current_user_from_header(authorization, services)

    try:
        return await services.revoke_api_key(
            user_id=_user_id(user),
            key_id=key_id,
        )
    except AttributeError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key revoke service is not implemented.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc