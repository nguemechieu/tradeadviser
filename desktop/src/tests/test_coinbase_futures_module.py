import asyncio
import json
import sys
from pathlib import Path

import aiohttp
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.broker_factory import BrokerFactory
from broker.coinbase_futures import (
    CoinbaseConfig,
    CoinbaseFuturesBroker,
    CoinbaseFuturesExecutionService,
    CoinbaseFuturesMarketDataService,
    CoinbaseFuturesProductService,
    normalize_symbol,
)
from config.config import AppConfig, BrokerConfig, RiskConfig, SystemConfig


def _future_product(
    product_id: str,
    *,
    base: str,
    quote: str,
    settlement: str,
    expiry_type: str,
    expiration_time: str | None = None,
    contract_size: str = "1",
    status: str = "online",
):
    details = {
        "contract_expiry_type": expiry_type,
        "settlement_currency_id": settlement,
        "contract_size": contract_size,
    }
    if expiration_time:
        details["expiration_time"] = expiration_time
    return {
        "product_id": product_id,
        "product_type": "FUTURE",
        "base_currency_id": base,
        "quote_currency_id": quote,
        "settlement_currency_id": settlement,
        "status": status,
        "future_product_details": details,
    }


class RecordingEventBus:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, data=None, **kwargs):
        self.events.append((event_type, data, kwargs))
        return {"type": event_type, "data": data, "kwargs": kwargs}


class FakeAuth:
    def build_ws_token(self, *, ttl_seconds=None):
        del ttl_seconds
        return "test-jwt"


class FakeWebSocketMessage:
    def __init__(self, msg_type, data=None):
        self.type = msg_type
        self.data = data


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent_payloads = []
        self.closed = False

    async def send_json(self, payload):
        self.sent_payloads.append(dict(payload))

    async def receive(self):
        if self.messages:
            return self.messages.pop(0)
        await asyncio.sleep(0)
        return FakeWebSocketMessage(aiohttp.WSMsgType.CLOSED)

    async def close(self):
        self.closed = True


class FakeCoinbaseClient:
    def __init__(self, *, products, websocket_payloads=None):
        self.config = CoinbaseConfig(
            api_key="organizations/test/apiKeys/test",
            api_secret="-----BEGIN EC PRIVATE KEY-----\nTEST\n-----END EC PRIVATE KEY-----",
            ws_reconnect_delay_seconds=0.01,
            ws_max_reconnect_delay_seconds=0.02,
            product_refresh_interval_seconds=60.0,
        )
        self._products = list(products)
        self._websocket_payloads = list(websocket_payloads or [])
        self.websocket_connections = []

    async def get_products(self, *, product_type="FUTURE"):
        return {
            "products": [
                row
                for row in self._products
                if str(row.get("product_type") or "").upper() == str(product_type).upper()
            ]
        }

    async def get_public_ticker(self, product_id):
        return {
            "product_id": product_id,
            "price": "64000.25",
            "best_bid": "64000.00",
            "best_ask": "64000.50",
            "volume_24_h": "125.4",
        }

    async def get_product_book(self, product_id, *, limit=50):
        del limit
        return {
            "pricebook": {
                "product_id": product_id,
                "bids": [{"price": "63999.5", "size": "4"}],
                "asks": [{"price": "64000.5", "size": "3"}],
            }
        }

    async def get_futures_balance_summary(self):
        return {
            "balance_summary": {
                "total_usd_balance": {"value": "150000.0", "currency": "USD"},
                "futures_buying_power": {"value": "90000.0", "currency": "USD"},
                "available_margin": {"value": "75000.0", "currency": "USD"},
                "cfm_usd_balance": {"value": "60000.0", "currency": "USD"},
                "unrealized_pnl": {"value": "1250.5", "currency": "USD"},
            }
        }

    async def get_futures_positions(self):
        return {"positions": []}

    async def create_order(self, payload):
        return {
            "success": True,
            "success_response": {
                "order_id": "cbf-order-1",
                "client_order_id": payload.get("client_order_id"),
                "status": "SUBMITTED",
            },
        }

    async def cancel_orders(self, order_ids):
        return {"results": [{"order_id": order_ids[0], "success": True}]}

    async def get_order(self, order_id):
        return {"order": {"order_id": order_id, "product_id": "BTC-PERP", "side": "BUY", "status": "FILLED"}}

    async def list_orders(self, *, symbol=None, limit=None):
        del limit
        return {"orders": [{"order_id": "cbf-order-1", "product_id": symbol or "BTC-PERP", "side": "BUY", "status": "OPEN"}]}

    async def open_websocket(self):
        messages = self._websocket_payloads.pop(0) if self._websocket_payloads else []
        websocket = FakeWebSocket(messages)
        self.websocket_connections.append(websocket)
        return websocket


def test_fetch_products():
    bus = RecordingEventBus()
    client = FakeCoinbaseClient(
        products=[
            _future_product(
                "BTC-PERP",
                base="BTC",
                quote="USDC",
                settlement="USDC",
                expiry_type="PERPETUAL",
            ),
            _future_product(
                "BIT-28JUL23",
                base="BIT",
                quote="USD",
                settlement="USD",
                expiry_type="EXPIRING",
                expiration_time="2023-07-28T00:00:00Z",
            ),
        ]
    )
    service = CoinbaseFuturesProductService(client, client.config, event_bus=bus)

    products = asyncio.run(service.fetch_products())
    perpetuals = asyncio.run(service.fetch_products(contract_expiry_type="PERPETUAL"))

    assert sorted(product.normalized_symbol for product in products) == [
        "BTC/USD:2023-07-28",
        "BTC/USDC:PERP",
    ]
    assert [product.normalized_symbol for product in perpetuals] == ["BTC/USDC:PERP"]
    assert any(event_type == "broker.products.updated" for event_type, _data, _kwargs in bus.events)


def test_symbol_normalization():
    assert normalize_symbol(
        _future_product(
            "BTC-PERP",
            base="BTC",
            quote="USDC",
            settlement="USDC",
            expiry_type="PERPETUAL",
        )
    ) == "BTC/USDC:PERP"
    assert normalize_symbol(
        _future_product(
            "BIT-28JUL23",
            base="BIT",
            quote="USD",
            settlement="USD",
            expiry_type="EXPIRING",
            expiration_time="2023-07-28T00:00:00Z",
        )
    ) == "BTC/USD:2023-07-28"


def test_market_data_stream():
    bus = RecordingEventBus()
    products = [
        _future_product(
            "BTC-PERP",
            base="BTC",
            quote="USDC",
            settlement="USDC",
            expiry_type="PERPETUAL",
        )
    ]
    ticker_message = FakeWebSocketMessage(
        aiohttp.WSMsgType.TEXT,
        json.dumps(
            {
                "channel": "ticker",
                "timestamp": "2026-04-07T12:00:00Z",
                "events": [
                    {
                        "type": "snapshot",
                        "tickers": [
                            {
                                "product_id": "BTC-PERP",
                                "price": "65000.5",
                                "best_bid": "65000.0",
                                "best_ask": "65001.0",
                                "volume_24_h": "10.2",
                            }
                        ],
                    }
                ],
            }
        ),
    )
    level2_message = FakeWebSocketMessage(
        aiohttp.WSMsgType.TEXT,
        json.dumps(
            {
                "channel": "level2",
                "timestamp": "2026-04-07T12:00:01Z",
                "sequence_num": 42,
                "events": [
                    {
                        "product_id": "BTC-PERP",
                        "type": "snapshot",
                        "updates": [
                            {"side": "bid", "price_level": "65000.0", "new_quantity": "4"},
                            {"side": "offer", "price_level": "65001.0", "new_quantity": "2"},
                        ],
                    }
                ],
            }
        ),
    )
    client = FakeCoinbaseClient(
        products=products,
        websocket_payloads=[
            [ticker_message, FakeWebSocketMessage(aiohttp.WSMsgType.CLOSED)],
            [level2_message, FakeWebSocketMessage(aiohttp.WSMsgType.CLOSED)],
        ],
    )
    product_service = CoinbaseFuturesProductService(client, client.config, event_bus=bus)
    asyncio.run(product_service.fetch_products(force_refresh=True))
    market_data = CoinbaseFuturesMarketDataService(
        client,
        product_service,
        event_bus=bus,
        auth=FakeAuth(),
    )

    async def _run_stream():
        ticker_task = await market_data.subscribe_ticker(["BTC/USDC:PERP"])
        orderbook_task = await market_data.subscribe_orderbook(["BTC/USDC:PERP"])
        await asyncio.sleep(0.05)
        await market_data.close()
        await asyncio.gather(ticker_task, orderbook_task, return_exceptions=True)

    asyncio.run(_run_stream())

    published_types = [event_type for event_type, _data, _kwargs in bus.events]
    assert "ticker_event" in published_types
    assert "market.ticker" in published_types
    assert "orderbook_event" in published_types
    assert "market.orderbook" in published_types
    assert market_data.latest_price_for("BTC/USDC:PERP") == pytest.approx(65000.5)
    assert client.websocket_connections[0].sent_payloads[0]["channel"] == "ticker"
    assert client.websocket_connections[1].sent_payloads[0]["channel"] == "level2"


def test_broker_factory_routes_coinbase_futures_exchange():
    config = AppConfig(
        broker=BrokerConfig(
            type="futures",
            exchange="coinbase_futures",
            api_key="organizations/test/apiKeys/test",
            secret="-----BEGIN EC PRIVATE KEY-----\nTEST\n-----END EC PRIVATE KEY-----",
        ),
        risk=RiskConfig(),
        system=SystemConfig(),
    )

    broker = BrokerFactory.create(config)

    assert isinstance(broker, CoinbaseFuturesBroker)


def test_broker_factory_routes_coinbase_futures_type_on_coinbase_exchange():
    config = AppConfig(
        broker=BrokerConfig(
            type="futures",
            exchange="coinbase",
            api_key="organizations/test/apiKeys/test",
            secret="-----BEGIN EC PRIVATE KEY-----\nTEST\n-----END EC PRIVATE KEY-----",
        ),
        risk=RiskConfig(),
        system=SystemConfig(),
    )

    broker = BrokerFactory.create(config)

    assert isinstance(broker, CoinbaseFuturesBroker)


def test_execution_parses_nested_balance_summary_and_places_order():
    bus = RecordingEventBus()
    client = FakeCoinbaseClient(
        products=[
            _future_product(
                "BTC-PERP",
                base="BTC",
                quote="USDC",
                settlement="USDC",
                expiry_type="PERPETUAL",
            )
        ]
    )
    product_service = CoinbaseFuturesProductService(client, client.config, event_bus=bus)
    asyncio.run(product_service.fetch_products(force_refresh=True))
    execution = CoinbaseFuturesExecutionService(
        client,
        product_service,
        event_bus=bus,
        config=client.config,
    )

    balances = asyncio.run(execution.fetch_balances())
    order = asyncio.run(execution.place_order("BTC/USDC:PERP", "buy", 1, order_type="market"))

    assert balances["equity"] == pytest.approx(150000.0)
    assert balances["available_margin"] == pytest.approx(75000.0)
    assert order["id"] == "cbf-order-1"
    assert order["risk"]["notional"] > 0
    assert any(event_type == "order.created" for event_type, _data, _kwargs in bus.events)
