import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.schwab.models import SchwabTokenSet
from broker.schwab.token_store import SchwabTokenStore
from security.encryption import EncryptionManager


def _workspace_path(name: str) -> Path:
    root = Path(__file__).resolve().parents[4] / ".test_tmp_schwab"
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    if path.exists():
        path.unlink()
    return path


def test_schwab_token_store_roundtrip_encrypts_sensitive_values():
    path = _workspace_path("token_store_roundtrip.json")
    store = SchwabTokenStore(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=path,
    )
    tokens = SchwabTokenSet(
        access_token="access-secret",
        refresh_token="refresh-secret",
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        refresh_token_expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        environment="sandbox",
    )

    store.save_tokens("profile-alpha", tokens)
    loaded = store.load_tokens("profile-alpha")

    assert loaded is not None
    assert loaded.access_token == "access-secret"
    assert loaded.refresh_token == "refresh-secret"
    assert store.has_valid_access_token("profile-alpha") is True
    assert store.should_refresh("profile-alpha", skew_seconds=7200) is True

    raw_text = path.read_text(encoding="utf-8")
    assert "access-secret" not in raw_text
    assert "refresh-secret" not in raw_text
