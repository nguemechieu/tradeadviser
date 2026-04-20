import secrets
import time
from typing import Optional
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

from broker.broker_errors import BrokerOperationError

try:
    import jwt as _JWT_MODULE
except ImportError as exc:  # pragma: no cover - depends on local environment
    _JWT_MODULE = None
    _JWT_IMPORT_ERROR = exc
else:
    _JWT_IMPORT_ERROR = None


def uses_coinbase_jwt_auth(api_key: str, api_secret: str) -> bool:
    key_text = str(api_key or "").strip()
    secret_text = str(api_secret or "").strip()
    return bool(key_text and "BEGIN" in secret_text and "PRIVATE KEY" in secret_text)


def resolve_coinbase_rest_host(rest_url: str) -> str:
    parsed = urlparse(str(rest_url or "").strip())
    return parsed.netloc or "api.coinbase.com"


def require_coinbase_jwt():
    if _JWT_MODULE is not None:
        return _JWT_MODULE
    raise BrokerOperationError(
        "Coinbase JWT signing requires PyJWT. Install project dependencies or run `pip install PyJWT` in the active environment.",
        category="authentication_error",
        rejection=True,
        raw_message=str(_JWT_IMPORT_ERROR or "PyJWT is not installed"),
    )


def build_coinbase_rest_jwt(
    request_method: str,
    request_host: str,
    request_path: str,
    api_key: str,
    api_secret: str,
    ttl_seconds: int = 120,
    issuer: str = "coinbase-cloud",
) -> str:
    method = str(request_method or "GET").strip().upper()
    host = str(request_host or "api.coinbase.com").strip()
    path = str(request_path or "/").strip()
    if not path.startswith("/"):
        path = f"/{path}"

    key_name = str(api_key or "").strip()
    secret_text = str(api_secret or "").strip()
    if not key_name:
        raise ValueError("Coinbase API key is missing")
    if not secret_text:
        raise ValueError("Coinbase API secret is missing")

    try:
        private_key = serialization.load_pem_private_key(secret_text.encode("utf-8"), password=None)
    except Exception as exc:
        raise ValueError(f"Invalid Coinbase private key format: {exc}") from exc

    if not isinstance(private_key, EllipticCurvePrivateKey):
        raise ValueError("Invalid Coinbase key: expected Elliptic Curve (ES256) private key")

    now = int(time.time())
    payload = {
        "sub": key_name,
        "iss": str(issuer or "coinbase-cloud").strip() or "coinbase-cloud",
        "nbf": now,
        "exp": now + int(ttl_seconds or 120),
        "uri": f"{method} {host}{path}",
    }
    headers = {
        "kid": key_name,
        "nonce": secrets.token_hex(16),
    }

    jwt_module = require_coinbase_jwt()
    token = jwt_module.encode(payload, private_key, algorithm="ES256", headers=headers)
    return token if isinstance(token, str) else token.decode("utf-8")


def masked_coinbase_key_id(api_key: Optional[str]) -> Optional[str]:
    text = str(api_key or "").strip()
    if not text:
        return None
    if len(text) <= 14:
        return text
    return f"{text[:8]}...{text[-6:]}"
