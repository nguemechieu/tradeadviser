from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from . import endpoints


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _timeout_seconds(value: Any, default: float) -> float:
    normalized = _float(value, default)
    if normalized > 1000:
        normalized = normalized / 1000.0
    return max(1.0, normalized)


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class SchwabConfig:
    client_id: str
    redirect_uri: str
    environment: str = "production"
    client_secret: str | None = None
    auth_url: str = endpoints.AUTHORIZE_URL
    token_url: str = endpoints.TOKEN_URL
    trader_base_url: str = endpoints.TRADER_BASE_URL
    market_data_base_url: str = endpoints.MARKET_DATA_BASE_URL
    account_hash: str | None = None
    account_id: str | None = None
    profile_name: str | None = None
    scopes: tuple[str, ...] = ()
    use_local_callback: bool = True
    callback_timeout_seconds: float = 180.0
    timeout_seconds: float = 20.0
    max_read_retries: int = 2
    refresh_skew_seconds: int = 300
    orders_lookback_days: int = 7
    orders_limit: int = 50
    token_profile_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def callback_host(self) -> str:
        parsed = urlparse(self.redirect_uri)
        return str(parsed.hostname or "127.0.0.1").strip() or "127.0.0.1"

    @property
    def callback_port(self) -> int:
        parsed = urlparse(self.redirect_uri)
        if parsed.port is not None:
            return int(parsed.port)
        return 80 if parsed.scheme == "http" else 443

    @property
    def callback_path(self) -> str:
        parsed = urlparse(self.redirect_uri)
        return "/" + str(parsed.path or "/").lstrip("/")


def resolve_schwab_environment(value: Any, *, sandbox: bool = False) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"sandbox", "paper", "test"}:
        return "sandbox"
    if normalized in {"production", "prod", "live"}:
        return "production"
    return "sandbox" if sandbox else "production"


def build_schwab_config(config: Any) -> SchwabConfig:
    options = dict(getattr(config, "options", None) or {})
    params = dict(getattr(config, "params", None) or {})
    environment = resolve_schwab_environment(
        options.get("environment") or params.get("environment"),
        sandbox=bool(getattr(config, "sandbox", False)),
    )
    profile_name = _text(options.get("profile_name") or params.get("profile_name"))
    client_id = _text(getattr(config, "api_key", None) or options.get("client_id") or params.get("client_id")) or ""
    redirect_uri = _text(
        options.get("redirect_uri")
        or params.get("redirect_uri")
        or getattr(config, "password", None)
        or "http://127.0.0.1:8182/callback"
    ) or "http://127.0.0.1:8182/callback"
    token_profile_key = _text(
        options.get("token_profile_key")
        or params.get("token_profile_key")
        or profile_name
        or options.get("account_hash")
        or getattr(config, "account_id", None)
        or client_id
    )
    scopes = options.get("scopes") or params.get("scopes") or ()
    if isinstance(scopes, str):
        scopes = tuple(part.strip() for part in scopes.split() if part.strip())
    else:
        scopes = tuple(str(part).strip() for part in tuple(scopes or ()) if str(part).strip())
    return SchwabConfig(
        client_id=client_id,
        client_secret=_text(getattr(config, "secret", None) or options.get("client_secret") or params.get("client_secret")),
        redirect_uri=redirect_uri,
        environment=environment,
        auth_url=str(options.get("auth_url") or params.get("auth_url") or endpoints.AUTHORIZE_URL).rstrip("/"),
        token_url=str(options.get("token_url") or params.get("token_url") or endpoints.TOKEN_URL).rstrip("/"),
        trader_base_url=str(
            options.get("trader_base_url")
            or params.get("trader_base_url")
            or options.get("api_base_url")
            or params.get("api_base_url")
            or endpoints.TRADER_BASE_URL
        ).rstrip("/"),
        market_data_base_url=str(
            options.get("market_data_base_url")
            or params.get("market_data_base_url")
            or endpoints.MARKET_DATA_BASE_URL
        ).rstrip("/"),
        account_hash=_text(options.get("account_hash") or params.get("account_hash")),
        account_id=_text(getattr(config, "account_id", None) or options.get("account_id") or params.get("account_id")),
        profile_name=profile_name,
        scopes=scopes,
        use_local_callback=_bool(options.get("use_local_callback"), True),
        callback_timeout_seconds=_float(options.get("callback_timeout_seconds"), 180.0),
        timeout_seconds=_timeout_seconds(options.get("timeout_seconds") or getattr(config, "timeout", 20), 20.0),
        max_read_retries=_int(options.get("max_read_retries"), 2),
        refresh_skew_seconds=_int(options.get("refresh_skew_seconds"), 300),
        orders_lookback_days=_int(options.get("orders_lookback_days"), 7),
        orders_limit=_int(options.get("orders_limit"), 50),
        token_profile_key=token_profile_key,
        metadata={
            key: value
            for key, value in options.items()
            if key in {"environment", "redirect_uri", "account_hash", "orders_lookback_days", "orders_limit"}
        },
    )
