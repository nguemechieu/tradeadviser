from __future__ import annotations

from urllib.parse import urlparse

from .config import SchwabConfig
from .exceptions import SchwabConfigurationError


def validate_schwab_config(config: SchwabConfig) -> SchwabConfig:
    if not str(config.client_id or "").strip():
        raise SchwabConfigurationError("Schwab client_id / app key is required.")
    redirect = urlparse(str(config.redirect_uri or "").strip())
    if redirect.scheme not in {"http", "https"} or not redirect.netloc:
        raise SchwabConfigurationError("Schwab redirect_uri must be a valid http(s) URL.")
    for label, url in (
        ("auth_url", config.auth_url),
        ("token_url", config.token_url),
        ("trader_base_url", config.trader_base_url),
        ("market_data_base_url", config.market_data_base_url),
    ):
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SchwabConfigurationError(f"Schwab {label} must be a valid http(s) URL.")
    if float(config.timeout_seconds) <= 0:
        raise SchwabConfigurationError("Schwab timeout_seconds must be positive.")
    if int(config.max_read_retries) < 0:
        raise SchwabConfigurationError("Schwab max_read_retries must be zero or greater.")
    return config
