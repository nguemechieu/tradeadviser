from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.oauth.models import OAuthSessionState, OAuthTokenSet
from core.oauth.token_store import OAuthTokenStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OAuthSessionManager:
    """Reusable token/session state helper for OAuth-based broker flows."""

    def __init__(
        self,
        *,
        provider: str,
        profile_key: str,
        environment: str,
        token_store: OAuthTokenStore,
    ) -> None:
        self.provider = str(provider or "").strip().lower()
        self.profile_key = str(profile_key or "").strip()
        self.environment = str(environment or "production").strip().lower() or "production"
        self.token_store = token_store
        self.tokens: OAuthTokenSet | None = None
        self.state = OAuthSessionState(
            provider=self.provider,
            profile_key=self.profile_key,
            environment=self.environment,
        )

    def restore(self) -> OAuthTokenSet | None:
        self.tokens = self.token_store.load_tokens(self.profile_key)
        self.state.token_loaded = self.tokens is not None
        self.state.authenticated = bool(self.tokens and self.tokens.has_valid_access_token())
        if self.state.authenticated:
            self.state.status = "authenticated"
        elif self.tokens is not None:
            self.state.status = "session_expired"
        else:
            self.state.status = "disconnected"
        self.state.updated_at = _utc_now()
        return self.tokens

    def save(self, tokens: OAuthTokenSet) -> OAuthTokenSet:
        self.tokens = tokens
        self.token_store.save_tokens(self.profile_key, tokens)
        self.state.token_loaded = True
        self.state.authenticated = tokens.has_valid_access_token(skew_seconds=0)
        self.state.status = "authenticated" if self.state.authenticated else "connected"
        self.state.last_error = ""
        self.state.updated_at = _utc_now()
        return tokens

    def clear(self) -> None:
        self.tokens = None
        self.token_store.clear_tokens(self.profile_key)
        self.state.token_loaded = False
        self.state.authenticated = False
        self.state.status = "disconnected"
        self.state.last_error = ""
        self.state.updated_at = _utc_now()

    def has_valid_access_token(self, *, skew_seconds: int = 120) -> bool:
        tokens = self.tokens or self.restore()
        return bool(tokens and tokens.has_valid_access_token(skew_seconds=skew_seconds))

    def should_refresh(self, *, skew_seconds: int = 300) -> bool:
        tokens = self.tokens or self.restore()
        return bool(tokens and tokens.should_refresh(skew_seconds=skew_seconds))

    def mark_status(self, status: str, *, authenticated: bool | None = None, error: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.state.status = str(status or self.state.status).strip().lower() or self.state.status
        if authenticated is not None:
            self.state.authenticated = bool(authenticated)
        self.state.last_error = str(error or "").strip()
        if metadata:
            self.state.metadata.update(dict(metadata))
        self.state.updated_at = _utc_now()
