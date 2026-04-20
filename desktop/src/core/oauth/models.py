from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


@dataclass(slots=True)
class OAuthTokenSet:
    provider: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "Bearer"
    scope: str | None = None
    access_token_expires_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None
    created_at: datetime = field(default_factory=_utc_now)
    environment: str = "production"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.provider = str(self.provider or "").strip().lower()
        if not self.provider:
            raise ValueError("OAuth provider is required")
        self.access_token = str(self.access_token or "").strip() or None
        self.refresh_token = str(self.refresh_token or "").strip() or None
        self.token_type = str(self.token_type or "Bearer").strip() or "Bearer"
        self.scope = str(self.scope or "").strip() or None
        self.environment = str(self.environment or "production").strip().lower() or "production"
        self.access_token_expires_at = _parse_datetime(self.access_token_expires_at)
        self.refresh_token_expires_at = _parse_datetime(self.refresh_token_expires_at)
        self.created_at = _parse_datetime(self.created_at) or _utc_now()

    def has_valid_access_token(self, *, skew_seconds: int = 120) -> bool:
        if not self.access_token:
            return False
        if self.access_token_expires_at is None:
            return True
        return self.access_token_expires_at > (_utc_now() + timedelta(seconds=max(0, int(skew_seconds))))

    def has_refresh_token(self) -> bool:
        if not self.refresh_token:
            return False
        if self.refresh_token_expires_at is None:
            return True
        return self.refresh_token_expires_at > _utc_now()

    def should_refresh(self, *, skew_seconds: int = 300) -> bool:
        if not self.access_token:
            return bool(self.refresh_token)
        if self.access_token_expires_at is None:
            return False
        return self.access_token_expires_at <= (_utc_now() + timedelta(seconds=max(0, int(skew_seconds))))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["access_token_expires_at"] = _isoformat(self.access_token_expires_at)
        payload["refresh_token_expires_at"] = _isoformat(self.refresh_token_expires_at)
        payload["created_at"] = _isoformat(self.created_at)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OAuthTokenSet":
        return cls(
            provider=value.get("provider") or "",
            access_token=value.get("access_token"),
            refresh_token=value.get("refresh_token"),
            token_type=value.get("token_type") or "Bearer",
            scope=value.get("scope"),
            access_token_expires_at=value.get("access_token_expires_at"),
            refresh_token_expires_at=value.get("refresh_token_expires_at"),
            created_at=value.get("created_at") or _utc_now(),
            environment=value.get("environment") or "production",
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass(slots=True)
class OAuthSessionState:
    provider: str
    profile_key: str
    environment: str = "production"
    status: str = "disconnected"
    authenticated: bool = False
    token_loaded: bool = False
    last_error: str = ""
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.provider = str(self.provider or "").strip().lower()
        self.profile_key = str(self.profile_key or "").strip()
        self.environment = str(self.environment or "production").strip().lower() or "production"
        self.updated_at = _parse_datetime(self.updated_at) or _utc_now()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["updated_at"] = _isoformat(self.updated_at)
        return payload
