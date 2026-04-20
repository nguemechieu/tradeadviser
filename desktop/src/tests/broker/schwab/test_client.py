import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.schwab.client import SchwabApiClient
from broker.schwab.config import SchwabConfig
from core.oauth.models import OAuthTokenSet


class _FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    async def text(self):
        return json.dumps(self._payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    async def close(self):
        self.closed = True


class _FakeAuth:
    def __init__(self):
        self.refresh_calls = 0

    async def ensure_session(self, *, interactive):
        token_value = "access-after-refresh" if self.refresh_calls else "access-before-refresh"
        return OAuthTokenSet(
            provider="schwab",
            access_token=token_value,
            refresh_token="refresh-token",
        )

    async def refresh_tokens(self):
        self.refresh_calls += 1
        return OAuthTokenSet(
            provider="schwab",
            access_token="access-after-refresh",
            refresh_token="refresh-token",
        )


def test_schwab_client_injects_oauth_header():
    fake_session = _FakeSession([_FakeResponse(payload={"accounts": []})])
    client = SchwabApiClient(
        SchwabConfig(client_id="client-id", redirect_uri="http://127.0.0.1:8182/callback"),
        _FakeAuth(),
        session=fake_session,
    )

    payload = asyncio.run(client.request("GET", "/accounts/accountNumbers"))

    assert payload["accounts"] == []
    assert fake_session.calls[0]["headers"]["Authorization"] == "Bearer access-before-refresh"
    assert fake_session.calls[0]["headers"]["X-Api-Key"] == "client-id"


def test_schwab_client_refreshes_once_after_401():
    fake_auth = _FakeAuth()
    fake_session = _FakeSession(
        [
            _FakeResponse(status=401, payload={"error": "expired"}),
            _FakeResponse(status=200, payload={"accounts": []}),
        ]
    )
    client = SchwabApiClient(
        SchwabConfig(client_id="client-id", redirect_uri="http://127.0.0.1:8182/callback"),
        fake_auth,
        session=fake_session,
    )

    payload = asyncio.run(client.request("GET", "/accounts/accountNumbers"))

    assert payload["accounts"] == []
    assert fake_auth.refresh_calls == 1
    assert fake_session.calls[0]["headers"]["Authorization"] == "Bearer access-before-refresh"
    assert fake_session.calls[1]["headers"]["Authorization"] == "Bearer access-after-refresh"
