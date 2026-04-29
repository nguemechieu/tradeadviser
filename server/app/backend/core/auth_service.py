from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.backend.config import get_settings
from server.app.backend.db.session import get_db_session
from server.app.backend.models.user import User
from server.app.backend.schemas.auth import TokenResponse, UserCreate, UserRead
from server.app.backend.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    utcnow,
    verify_password,
)


bearer_scheme = HTTPBearer(auto_error=False)


async def register_user(session: AsyncSession, payload: UserCreate) -> User:
    existing_user = await session.scalar(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email or username already exists.",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, identifier: str, password: str) -> User:
    user = await session.scalar(
        select(User).where(or_(User.email == identifier, User.username == identifier))
    )
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )
    return user


def create_token_response(user: User) -> TokenResponse:
    settings = get_settings()
    token, expires_at = create_access_token(
        user.id,
        settings,
        extra_claims={"email": user.email},
    )
    expires_in = int((expires_at - utcnow()).total_seconds())
    return TokenResponse(
        access_token=token,
        expires_in=max(expires_in, 1),
        user=UserRead.model_validate(user),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    settings = get_settings()
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed access token.",
        )

    user = await session.get(User, subject)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token is unavailable.",
        )
    return user
