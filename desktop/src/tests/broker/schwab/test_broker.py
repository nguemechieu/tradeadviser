import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.broker_factory import BrokerFactory
from broker.schwab.broker import SchwabBroker
from config.config import AppConfig, BrokerConfig, RiskConfig, SystemConfig


class _FakeAuth:
    def __init__(self):
        self.controller = None
        self.ensure_calls = 0

    async def ensure_session(self, *, interactive):
        self.ensure_calls += 1
        return {"interactive": interactive}

    async def refresh_tokens(self):
        return {"refreshed": True}

    def clear(self):
        return None


class _FakeClient:
    def __init__(self):
        self.closed = False

    async def open(self):
        return self

    async def close(self):
        self.closed = True

    async def get_accounts(self):
        return [
            {
                "broker": "schwab",
                "account_id": "123456789",
                "account_hash": "hash-123",
                "alias": "Primary",
                "raw": {},
            }
        ]

    async def get_account_balances(self, account_hash, *, account_id=None):
        return {
            "broker": "schwab",
            "account_id": account_id or "123456789",
            "account_hash": account_hash,
            "equity": 25000.0,
            "cash": 12000.0,
        }

    async def get_positions(self, account_hash, *, account_id=None):
        return [
            {
                "broker": "schwab",
                "account_id": account_id or "123456789",
                "account_hash": account_hash,
                "symbol": "AAPL",
                "quantity": 2.0,
                "side": "long",
            }
        ]

    async def get_quotes(self, symbols):
        return [
            {
                "broker": "schwab",
                "symbol": symbols[0],
                "bid": 189.1,
                "ask": 189.3,
                "last": 189.2,
            }
        ]


def test_broker_factory_routes_schwab_to_dedicated_broker():
    broker = BrokerFactory.create(
        AppConfig(
            broker=BrokerConfig(
                type="options",
                exchange="schwab",
                api_key="client-id",
                password="http://127.0.0.1:8182/callback",
            ),
            risk=RiskConfig(),
            system=SystemConfig(),
        )
    )

    assert isinstance(broker, SchwabBroker)


def test_schwab_broker_exposes_canonical_account_position_and_quote_methods():
    broker = SchwabBroker(
        BrokerConfig(
            type="options",
            exchange="schwab",
            api_key="client-id",
            password="http://127.0.0.1:8182/callback",
            options={"environment": "sandbox"},
        )
    )
    broker.auth = _FakeAuth()
    broker.client = _FakeClient()

    asyncio.run(broker.connect())
    balances = asyncio.run(broker.get_account_balances())
    positions = asyncio.run(broker.get_positions())
    quotes = asyncio.run(broker.get_quotes(["AAPL"]))

    assert broker.account_id == "123456789"
    assert broker.account_hash == "hash-123"
    assert balances["equity"] == 25000.0
    assert positions[0]["symbol"] == "AAPL"
    assert quotes[0]["symbol"] == "AAPL"
