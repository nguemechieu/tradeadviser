from __future__ import annotations

from pathlib import Path

from core.oauth.token_store import EncryptedOAuthTokenStore
from security.encryption import EncryptionManager


class SchwabTokenStore(EncryptedOAuthTokenStore):
    def __init__(self, *, encryption: EncryptionManager | None = None, path: str | Path | None = None) -> None:
        super().__init__(provider="schwab", encryption=encryption, path=path)
