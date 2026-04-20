from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from broker.ibkr.models import IBKRTransport


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalized_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _derive_websocket_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = parsed.path.rstrip("/")
    if not path.endswith("/ws"):
        path = f"{path}/ws"
    return f"{scheme}://{parsed.netloc}{path}"


@dataclass(slots=True)
class IBKRWebApiConfig:
    base_url: str = "https://127.0.0.1:5000/v1/api"
    environment: str = "gateway"
    websocket_url: str | None = None
    session_token: str | None = None
    session_secret: str | None = None
    account_id: str | None = None
    profile_name: str | None = None
    verify_ssl: bool = False
    timeout_seconds: float = 15.0
    websocket_enabled: bool = True
    auto_reconnect: bool = True
    readonly: bool = False
    session_check_path: str = "/iserver/auth/status"
    tickle_path: str = "/tickle"
    reauthenticate_path: str = "/iserver/reauthenticate"
    validate_sso_path: str = "/sso/validate"
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_websocket_url(self) -> str:
        return str(self.websocket_url or _derive_websocket_url(self.base_url)).rstrip("/")


@dataclass(slots=True)
class IBKRTwsConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    account_id: str | None = None
    profile_name: str | None = None
    readonly: bool = False
    paper: bool = True
    reconnect_interval_seconds: float = 5.0
    connect_timeout_seconds: float = 10.0
    startup_sync_timeout_seconds: float = 10.0
    market_data_type: int = 1
    auto_reconnect: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IBKRConfig:
    transport: IBKRTransport = IBKRTransport.WEBAPI
    execution_mode: str = "paper"
    exchange_name: str = "ibkr"
    account_id: str | None = None
    profile_name: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    webapi: IBKRWebApiConfig = field(default_factory=IBKRWebApiConfig)
    tws: IBKRTwsConfig = field(default_factory=IBKRTwsConfig)

    @property
    def transport_config(self) -> IBKRWebApiConfig | IBKRTwsConfig:
        return self.webapi if self.transport is IBKRTransport.WEBAPI else self.tws


def resolve_ibkr_transport_value(config: Any) -> IBKRTransport:
    options = dict(getattr(config, "options", None) or {})
    params = dict(getattr(config, "params", None) or {})
    candidates = (
        options.get("connection_mode"),
        options.get("ibkr_mode"),
        params.get("connection_mode"),
        params.get("ibkr_mode"),
    )
    raw_mode = str(getattr(config, "mode", "") or "").strip().lower()
    if raw_mode in {IBKRTransport.WEBAPI.value, IBKRTransport.TWS.value}:
        return IBKRTransport(raw_mode)
    for candidate in candidates:
        normalized = str(candidate or "").strip().lower()
        if normalized in {IBKRTransport.WEBAPI.value, IBKRTransport.TWS.value}:
            return IBKRTransport(normalized)
    return IBKRTransport.WEBAPI


def build_ibkr_config(config: Any) -> IBKRConfig:
    options = dict(getattr(config, "options", None) or {})
    params = dict(getattr(config, "params", None) or {})
    transport = resolve_ibkr_transport_value(config)
    execution_mode = str(getattr(config, "mode", "paper") or "paper").strip().lower()
    if execution_mode not in {"live", "paper"}:
        execution_mode = str(options.get("execution_mode") or "paper").strip().lower() or "paper"

    common_account_id = _normalized_text(
        getattr(config, "account_id", None)
        or options.get("account_id")
        or params.get("account_id")
        or options.get("account")
    )
    profile_name = _normalized_text(options.get("profile_name") or params.get("profile_name"))

    webapi = IBKRWebApiConfig(
        base_url=str(options.get("base_url") or params.get("base_url") or "https://127.0.0.1:5000/v1/api").rstrip("/"),
        environment=str(options.get("environment") or params.get("environment") or "gateway").strip().lower() or "gateway",
        websocket_url=_normalized_text(options.get("websocket_url") or params.get("websocket_url")),
        session_token=_normalized_text(
            options.get("session_token")
            or params.get("session_token")
            or getattr(config, "api_key", None)
        ),
        session_secret=_normalized_text(
            options.get("session_secret")
            or params.get("session_secret")
            or getattr(config, "secret", None)
        ),
        account_id=common_account_id,
        profile_name=profile_name,
        verify_ssl=_coerce_bool(options.get("verify_ssl"), False),
        timeout_seconds=_coerce_float(options.get("timeout_seconds") or getattr(config, "timeout", 15), 15.0),
        websocket_enabled=_coerce_bool(options.get("websocket_enabled"), True),
        auto_reconnect=_coerce_bool(options.get("auto_reconnect"), True),
        readonly=_coerce_bool(options.get("readonly"), False),
        metadata={
            key: value
            for key, value in options.items()
            if key in {"base_url", "websocket_url", "environment", "session_token", "readonly"}
        },
    )

    default_tws_port = 7497 if execution_mode == "paper" else 7496
    tws = IBKRTwsConfig(
        host=str(options.get("host") or params.get("host") or "127.0.0.1").strip() or "127.0.0.1",
        port=_coerce_int(options.get("port") or params.get("port"), default_tws_port),
        client_id=_coerce_int(options.get("client_id") or params.get("client_id"), 1),
        account_id=common_account_id,
        profile_name=profile_name,
        readonly=_coerce_bool(options.get("readonly"), False),
        paper=_coerce_bool(options.get("paper"), execution_mode != "live"),
        reconnect_interval_seconds=_coerce_float(options.get("reconnect_interval_seconds"), 5.0),
        connect_timeout_seconds=_coerce_float(options.get("connect_timeout_seconds"), 10.0),
        startup_sync_timeout_seconds=_coerce_float(options.get("startup_sync_timeout_seconds"), 10.0),
        market_data_type=_coerce_int(options.get("market_data_type"), 1),
        auto_reconnect=_coerce_bool(options.get("auto_reconnect"), True),
        metadata={
            key: value
            for key, value in options.items()
            if key in {"host", "port", "client_id", "paper", "readonly"}
        },
    )

    return IBKRConfig(
        transport=transport,
        execution_mode=execution_mode,
        exchange_name=str(getattr(config, "exchange", "ibkr") or "ibkr").strip().lower() or "ibkr",
        account_id=common_account_id,
        profile_name=profile_name,
        options=options,
        params=params,
        webapi=webapi,
        tws=tws,
    )
