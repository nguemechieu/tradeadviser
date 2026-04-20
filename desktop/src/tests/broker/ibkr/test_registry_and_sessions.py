import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.ibkr.broker import IBKRBroker
from broker.ibkr.config import IBKRTwsConfig, IBKRWebApiConfig
from broker.ibkr.models import IBKRSessionStatus
from broker.ibkr.tws.broker import IBKRTwsBroker
from broker.ibkr.tws.client import IBKRTwsClient
from broker.ibkr.tws.session import IBKRTwsSession
from broker.ibkr.webapi.auth import IBKRWebApiAuthenticator
from broker.ibkr.webapi.session import IBKRWebApiSession
from config.config import BrokerConfig


class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload or {}

    async def text(self):
        return json.dumps(self._payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeHttpClient:
    def __init__(self, payload=None):
        self.closed = False
        self.payload = payload or {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return _FakeResponse(payload=self.payload)


class _FakeTwsAdapter:
    def __init__(self):
        self.connected = False

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def request_account_summary(self, account_id=None):
        return {
            "account_id": account_id or "DU12345",
            "equity": 25000,
            "cashbalance": 12000,
            "buyingpower": 50000,
            "currency": "USD",
        }

    async def request_positions(self, account_id=None):
        return [
            {
                "account_id": account_id or "DU12345",
                "symbol": "ESM6",
                "quantity": 1,
                "avgPrice": 5200.0,
                "marketPrice": 5200.25,
                "marketValue": 520025.0,
                "unrealizedPnl": 25.0,
                "secType": "FUT",
            }
        ]

    async def request_quotes(self, symbols):
        return [{"symbol": symbols[0], "last": 5200.25, "bid": 5200.0, "ask": 5200.5}]

    async def request_historical_bars(self, symbol, timeframe, limit=None):
        _ = (symbol, timeframe, limit)
        return []

    async def place_order(self, account_id, order):
        return {"order_id": "1", "account_id": account_id, "symbol": order["symbol"], "status": "Submitted"}

    async def cancel_order(self, order_id):
        return {"id": order_id, "status": "canceled"}


def test_ibkr_broker_facade_selects_transport_delegate():
    webapi_broker = IBKRBroker(BrokerConfig(type="futures", exchange="ibkr", mode="paper", options={"connection_mode": "webapi"}))
    tws_broker = IBKRBroker(BrokerConfig(type="futures", exchange="ibkr", mode="paper", options={"connection_mode": "tws"}))

    assert webapi_broker.transport == "webapi"
    assert tws_broker.transport == "tws"


def test_webapi_session_injects_authorization_header_and_auth_state():
    session = IBKRWebApiSession(IBKRWebApiConfig(session_token="token-123"))
    fake_client = _FakeHttpClient(payload={"authenticated": True, "connected": True})
    session._client = fake_client

    payload = asyncio.run(session.request_json("GET", "/iserver/auth/status", expected_statuses=(200,)))
    auth = IBKRWebApiAuthenticator(session)
    status = asyncio.run(auth.bootstrap())

    assert payload["authenticated"] is True
    assert fake_client.calls[0]["headers"]["Authorization"] == "Bearer token-123"
    assert status["authenticated"] is True
    assert session.state.status is IBKRSessionStatus.AUTHENTICATED


def test_tws_client_updates_session_state_with_runtime_adapter():
    session = IBKRTwsSession(IBKRTwsConfig(host="127.0.0.1", port=7497, client_id=7))
    client = IBKRTwsClient(session, adapter_factory=lambda **_kwargs: _FakeTwsAdapter())

    asyncio.run(client.connect())

    assert session.state.status is IBKRSessionStatus.AUTHENTICATED
    assert session.state.connected is True

    summary = asyncio.run(client.request_account_summary("DU12345"))
    positions = asyncio.run(client.request_positions("DU12345"))

    assert summary["equity"] == 25000
    assert positions[0]["symbol"] == "ESM6"


def test_tws_broker_normalizes_transport_payloads_into_canonical_models():
    broker = IBKRTwsBroker(BrokerConfig(type="futures", exchange="ibkr", mode="paper", options={"connection_mode": "tws"}))
    broker.client.adapter = _FakeTwsAdapter()
    broker.account_id = "DU12345"
    broker.session_runtime.state.account_id = "DU12345"

    balances = asyncio.run(broker.get_account_balances("DU12345"))
    positions = asyncio.run(broker.get_positions("DU12345"))
    quotes = asyncio.run(broker.get_quotes(["ESM6"]))
    execution = asyncio.run(
        broker.place_order(
            "DU12345",
            {"symbol": "ESM6", "side": "buy", "amount": 1, "type": "market"},
        )
    )

    assert balances["broker"] == "ibkr"
    assert balances["account_id"] == "DU12345"
    assert balances["equity"] == 25000
    assert positions[0]["broker"] == "ibkr"
    assert positions[0]["symbol"] == "ESM6"
    assert positions[0]["instrument"]["type"] == "future"
    assert quotes[0]["broker"] == "ibkr"
    assert quotes[0]["symbol"] == "ESM6"
    assert execution["broker"] == "ibkr"
    assert execution["id"] == "1"
    assert execution["type"] == "market"
