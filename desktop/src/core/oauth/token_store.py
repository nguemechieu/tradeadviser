from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Protocol

from core.oauth.models import OAuthTokenSet
from security.encryption import EncryptionManager


class OAuthTokenStore(Protocol):
    def save_tokens(self, profile_key: str, tokens: OAuthTokenSet) -> None: ...
    def load_tokens(self, profile_key: str) -> OAuthTokenSet | None: ...
    def clear_tokens(self, profile_key: str) -> None: ...
    def has_valid_access_token(self, profile_key: str, *, skew_seconds: int = 120) -> bool: ...
    def should_refresh(self, profile_key: str, *, skew_seconds: int = 300) -> bool: ...


class EncryptedOAuthTokenStore:
    """Reusable encrypted token store for OAuth-based brokers."""

    SENSITIVE_FIELDS = ("access_token", "refresh_token")

    def __init__(
        self,
        *,
        provider: str,
        encryption: EncryptionManager | None = None,
        path: str | Path | None = None,
    ) -> None:
        self.provider = str(provider or "").strip().lower()
        if not self.provider:
            raise ValueError("provider is required")
        self.encryption = encryption or EncryptionManager.from_environment()
        self.path = Path(path) if path else Path(__file__).resolve().parents[3] / "oauth_tokens.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_store({"providers": {}})

    def save_tokens(self, profile_key: str, tokens: OAuthTokenSet) -> None:
        key = str(profile_key or "").strip()
        if not key:
            raise ValueError("profile_key is required")
        payload = tokens.to_dict()
        store = self._read_store()
        provider_bucket = store.setdefault("providers", {}).setdefault(self.provider, {})
        provider_bucket[key] = self._encrypt_payload(payload)
        self._write_store(store)

    def load_tokens(self, profile_key: str) -> OAuthTokenSet | None:
        key = str(profile_key or "").strip()
        if not key:
            return None
        store = self._read_store()
        payload = store.get("providers", {}).get(self.provider, {}).get(key)
        if payload is None:
            return None
        return OAuthTokenSet.from_mapping(self._decrypt_payload(payload))

    def clear_tokens(self, profile_key: str) -> None:
        key = str(profile_key or "").strip()
        store = self._read_store()
        provider_bucket = store.get("providers", {}).get(self.provider, {})
        if key in provider_bucket:
            del provider_bucket[key]
            self._write_store(store)

    def has_valid_access_token(self, profile_key: str, *, skew_seconds: int = 120) -> bool:
        tokens = self.load_tokens(profile_key)
        return bool(tokens and tokens.has_valid_access_token(skew_seconds=skew_seconds))

    def should_refresh(self, profile_key: str, *, skew_seconds: int = 300) -> bool:
        tokens = self.load_tokens(profile_key)
        return bool(tokens and tokens.should_refresh(skew_seconds=skew_seconds))

    def _read_store(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("providers", {})
        if not isinstance(payload["providers"], dict):
            payload["providers"] = {}
        return payload

    def _write_store(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _encrypt_payload(self, payload: dict) -> dict:
        encrypted = deepcopy(payload)
        for field in self.SENSITIVE_FIELDS:
            value = encrypted.get(field)
            if value in (None, ""):
                continue
            encrypted[field] = self.encryption.encrypt(str(value))
        return encrypted

    def _decrypt_payload(self, payload: dict) -> dict:
        decrypted = deepcopy(payload)
        for field in self.SENSITIVE_FIELDS:
            value = decrypted.get(field)
            if value in (None, ""):
                continue
            decrypted[field] = self.encryption.decrypt(str(value))
        return decrypted
