import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.schwab.auth import SchwabOAuthService
from broker.schwab.config import SchwabConfig
from core.oauth.local_callback_server import parse_oauth_callback_url
from core.oauth.models import OAuthTokenSet
from core.oauth.session import OAuthSessionManager
from core.oauth.token_store import EncryptedOAuthTokenStore
from security.encryption import EncryptionManager


def _workspace_path(name: str) -> Path:
    root = Path(__file__).resolve().parents[4] / ".test_tmp_schwab"
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    if path.exists():
        path.unlink()
    return path


def _session_manager(storage_name: str):
    store = EncryptedOAuthTokenStore(
        provider="schwab",
        encryption=EncryptionManager(Fernet.generate_key()),
        path=_workspace_path(storage_name),
    )
    return OAuthSessionManager(
        provider="schwab",
        profile_key="schwab_main",
        environment="sandbox",
        token_store=store,
    )


def test_schwab_authorization_url_contains_redirect_state_and_scope():
    service = SchwabOAuthService(
        SchwabConfig(
            client_id="client-id",
            redirect_uri="http://127.0.0.1:8182/callback",
            environment="sandbox",
            scopes=("account:read", "trading"),
        ),
        session_manager=_session_manager("auth_url_tokens.json"),
    )

    url = service.build_authorization_url(state="state-123")
    query = parse_qs(urlsplit(url).query)

    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8182/callback"]
    assert query["state"] == ["state-123"]
    assert query["scope"] == ["account:read trading"]


def test_oauth_callback_parser_extracts_code_and_validates_state():
    payload = parse_oauth_callback_url(
        "http://127.0.0.1:8182/callback?code=auth-code-1&state=state-123"
    )

    payload.validate_state("state-123")

    assert payload.code == "auth-code-1"
    assert payload.state == "state-123"


def test_oauth_session_restore_marks_expired_tokens_for_refresh():
    manager = _session_manager("expired_tokens.json")
    manager.save(
        OAuthTokenSet(
            provider="schwab",
            access_token="expired-access",
            refresh_token="refresh-token",
            access_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            refresh_token_expires_at=datetime.now(timezone.utc) + timedelta(days=10),
            environment="sandbox",
        )
    )

    restored = manager.restore()

    assert restored is not None
    assert manager.state.status == "session_expired"
    assert manager.should_refresh() is True
