from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from config.settings import Settings
from jwt import InvalidTokenError



def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def create_access_token(subject: str, settings: Settings, extra_claims: dict[str, str] | None = None) -> tuple[str, datetime]:
    issued_at = utcnow()
    expires_at = issued_at + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: dict[str, object] = {
        "sub": subject,
        "aud": settings.ACCESS_TOKEN_AUDIENCE,
        "iat": issued_at,
        "exp": expires_at,
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, object]:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.ACCESS_TOKEN_AUDIENCE,
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token.") from exc
