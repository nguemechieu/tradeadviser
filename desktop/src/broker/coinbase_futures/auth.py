from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization

from ..coinbase_jwt_auth import require_coinbase_jwt
from .models import CoinbaseConfig


class CoinbaseJWTAuth:
    """JWT signer for Coinbase Advanced Trade REST and WebSocket requests."""

    def __init__(self, config: CoinbaseConfig | Any) -> None:
        self.config = CoinbaseConfig.from_broker_config(config)
        self._private_key = None

    @property
    def issuer(self) -> str:
        return str(self.config.jwt_issuer or "coinbase-cloud").strip()

    @property
    def subject(self) -> str:
        return str(self.config.api_key).strip()

    @property
    def host(self) -> str:
        parsed = urlparse(self.config.rest_url)
        return parsed.netloc or "api.coinbase.com"

    def _load_private_key(self) -> Any:
        if self._private_key is not None:
            return self._private_key
        self._private_key = serialization.load_pem_private_key(
            self.config.api_secret.encode("utf-8"),
            password=None,
        )
        return self._private_key

    def _build_claims(self, *, ttl_seconds: int | None = None) -> dict[str, Any]:
        now = int(time.time())
        return {
            "iss": self.issuer,
            "sub": self.subject,
            "nbf": now,
            "exp": now + int(ttl_seconds or self.config.jwt_ttl_seconds),
        }

    def build_rest_token(self, method: str, request_path: str, *, ttl_seconds: int | None = None) -> str:
        path = str(request_path or "/").strip()
        if not path.startswith("/"):
            path = f"/{path}"
        claims = self._build_claims(ttl_seconds=ttl_seconds)
        claims["uri"] = f"{str(method or 'GET').strip().upper()} {self.host}{path}"
        headers = {
            "kid": self.subject,
            "nonce": secrets.token_hex(16),
        }
        jwt_module = require_coinbase_jwt()
        token = jwt_module.encode(
            claims,
            self._load_private_key(),
            algorithm="ES256",
            headers=headers,
        )
        return token if isinstance(token, str) else token.decode("utf-8")

    def build_ws_token(self, *, ttl_seconds: int | None = None) -> str:
        headers = {
            "kid": self.subject,
            "nonce": secrets.token_hex(16),
        }
        jwt_module = require_coinbase_jwt()
        token = jwt_module.encode(
            self._build_claims(ttl_seconds=ttl_seconds),
            self._load_private_key(),
            algorithm="ES256",
            headers=headers,
        )
        return token if isinstance(token, str) else token.decode("utf-8")

    def auth_headers(self, method: str, request_path: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.build_rest_token(method, request_path)}",
            "Content-Type": "application/json",
        }


__all__ = ["CoinbaseJWTAuth"]
