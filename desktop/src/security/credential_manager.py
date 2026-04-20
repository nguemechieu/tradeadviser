from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from security.credential_models import Credential
from security.encryption import EncryptionManager


class FileCredentialManager:
    SENSITIVE_BROKER_FIELDS = (
        "api_key",
        "secret",
        "password",
        "passphrase",
        "account_id",
        "uid",
        "wallet",
    )

    def __init__(self, encryption: EncryptionManager | None = None, path: str | Path | None = None):
        self.encryption = encryption or EncryptionManager.from_environment()
        self.path = Path(path) if path else Path(__file__).resolve().parents[2] / "credentials.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_store({"accounts": {}, "index": []})

    def save_account(self, account_name: str, config: dict, validate: bool = False):
        if not str(account_name or "").strip():
            raise ValueError("Account name is required")

        payload = deepcopy(config or {})
        broker = payload.get("broker")
        if validate and isinstance(broker, dict) and broker.get("exchange"):
            Credential.from_broker_config(broker)

        store = self._read_store()
        store["accounts"][account_name] = self._encrypt_payload(payload)
        index = [name for name in store.get("index", []) if name != account_name]
        index.insert(0, account_name)
        store["index"] = index
        self._write_store(store)

    def load_account(self, account_name: str):
        store = self._read_store()
        payload = store.get("accounts", {}).get(account_name)
        if payload is None:
            return None
        return self._decrypt_payload(payload)

    def list_accounts(self):
        store = self._read_store()
        accounts = list(store.get("accounts", {}).keys())
        ordered = [name for name in store.get("index", []) if name in accounts]
        for name in accounts:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def touch_account(self, account_name: str):
        store = self._read_store()
        if account_name not in store.get("accounts", {}):
            return
        index = [name for name in store.get("index", []) if name != account_name]
        index.insert(0, account_name)
        store["index"] = index
        self._write_store(store)

    def delete_account(self, account_name: str):
        store = self._read_store()
        if account_name in store.get("accounts", {}):
            del store["accounts"][account_name]
        store["index"] = [name for name in store.get("index", []) if name != account_name]
        self._write_store(store)

    def _read_store(self):
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("accounts", {})
        payload.setdefault("index", [])
        if not isinstance(payload["accounts"], dict):
            payload["accounts"] = {}
        if not isinstance(payload["index"], list):
            payload["index"] = []
        return payload

    def _write_store(self, payload: dict):
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _encrypt_payload(self, payload: dict):
        encrypted = deepcopy(payload)
        broker = encrypted.get("broker")
        if isinstance(broker, dict):
            encrypted["broker"] = self._transform_broker_fields(broker, encrypt=True)
        return encrypted

    def _decrypt_payload(self, payload: dict):
        decrypted = deepcopy(payload)
        broker = decrypted.get("broker")
        if isinstance(broker, dict):
            decrypted["broker"] = self._transform_broker_fields(broker, encrypt=False)
        return decrypted

    def _transform_broker_fields(self, broker: dict, *, encrypt: bool):
        transformed = deepcopy(broker)
        for field in self.SENSITIVE_BROKER_FIELDS:
            value = transformed.get(field)
            if value in (None, ""):
                continue
            transformed[field] = self.encryption.encrypt(value) if encrypt else self.encryption.decrypt(value)
        return transformed
