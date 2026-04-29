from __future__ import annotations

import logging

from fastapi import HTTPException, status

from server.app.backend.dependencies import ServerServiceContainer
from server.app.backend.models import User

logger = logging.getLogger(__name__)


def resolve_bearer_user(
    authorization: str | None,
    services: ServerServiceContainer,
) -> User:
    """Extract and validate bearer token from Authorization header.
    
    Expected format: Authorization: Bearer <48_char_hex_token>
    
    Raises HTTPException with 401 if:
    - Header is missing or empty
    - Format is not "Bearer <token>"
    - Token is invalid or expired
    """
    value = str(authorization or "").strip()
    
    if not value:
        logger.warning("Authorization header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )
    
    if not value.lower().startswith("bearer "):
        logger.warning(f"Invalid authorization format: {value[:30]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be in format: Bearer <token>",
        )
    
    # Extract token (everything after "Bearer ")
    token = value[7:].strip()
    
    if not token or len(token) < 20:
        logger.warning(f"Invalid token length: {len(token)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )
    
    # Resolve token to user
    user = services.resolve_token(token)
    
    if user is None:
        logger.warning(f"Token resolution failed for: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )
    
    if not user.is_active:
        logger.warning(f"User {user.email} is inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated.",
        )
    
    logger.debug(f"User authenticated: {user.email}")
    return user


def resolve_optional_bearer_user(
    authorization: str | None,
    services: ServerServiceContainer,
) -> User | None:
    """Optionally extract bearer token if provided.
    
    Returns None if header is empty, but raises 401 if header is present but invalid.
    """
    value = str(authorization or "").strip()
    
    if not value:
        logger.debug("No authorization header provided")
        return None
    
    if not value.lower().startswith("bearer "):
        logger.warning(f"Invalid authorization format: {value[:30]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be in format: Bearer <token>",
        )
    
    token = value[7:].strip()
    
    if not token or len(token) < 20:
        logger.warning(f"Invalid token length: {len(token)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )
    
    user = services.resolve_token(token)
    
    if user is None:
        logger.warning(f"Token resolution failed for: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )
    
    if not user.is_active:
        logger.warning(f"User {user.email} is inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated.",
        )
    
    logger.debug(f"Optional user authenticated: {user.email}")
    return user


def resolve_admin_user(
    authorization: str | None,
    services: ServerServiceContainer,
) -> User:
    """Extract bearer token and validate admin role.
    
    Raises HTTPException with:
    - 401 if token is invalid/missing
    - 403 if user role is not "admin"
    """
    user = resolve_bearer_user(authorization, services)
    
    if user.role != "admin":
        logger.warning(f"Non-admin user {user.email} attempted admin operation")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    
    logger.debug(f"Admin user authenticated: {user.email}")
    return user
