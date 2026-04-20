from __future__ import annotations

from urllib.parse import urlparse

from broker.ibkr.config import IBKRConfig
from broker.ibkr.exceptions import IBKRConfigurationError
from broker.ibkr.models import IBKRTransport


def _validate_webapi(config: IBKRConfig) -> None:
    webapi = config.webapi
    parsed = urlparse(str(webapi.base_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IBKRConfigurationError("IBKR Web API base_url must be a valid http(s) URL.")
    if webapi.websocket_url:
        ws_parsed = urlparse(str(webapi.websocket_url))
        if ws_parsed.scheme not in {"ws", "wss"} or not ws_parsed.netloc:
            raise IBKRConfigurationError("IBKR Web API websocket_url must be a valid ws(s) URL.")
    if float(webapi.timeout_seconds) <= 0:
        raise IBKRConfigurationError("IBKR Web API timeout_seconds must be positive.")


def _validate_tws(config: IBKRConfig) -> None:
    tws = config.tws
    if not str(tws.host or "").strip():
        raise IBKRConfigurationError("IBKR TWS host is required.")
    if int(tws.port) <= 0 or int(tws.port) > 65535:
        raise IBKRConfigurationError("IBKR TWS port must be between 1 and 65535.")
    if int(tws.client_id) < 0:
        raise IBKRConfigurationError("IBKR TWS client_id must be zero or greater.")
    if float(tws.connect_timeout_seconds) <= 0:
        raise IBKRConfigurationError("IBKR TWS connect_timeout_seconds must be positive.")


def validate_ibkr_config(config: IBKRConfig) -> IBKRConfig:
    if config.transport is IBKRTransport.WEBAPI:
        _validate_webapi(config)
    elif config.transport is IBKRTransport.TWS:
        _validate_tws(config)
    else:
        raise IBKRConfigurationError(f"Unsupported IBKR transport: {config.transport!r}")
    return config
