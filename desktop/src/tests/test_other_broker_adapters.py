import asyncio
from datetime import datetime, timezone
import json as json_module
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import broker.paper_broker as paper_module
from broker.alpaca_broker import AlpacaBroker
from broker.oanda_broker import OandaBroker
from broker.paper_broker import PaperBroker
from market_data.ticker_buffer import TickerBuffer
from market_data.websocket.alpaca_web_socket import AlpacaWebSocket


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return self.payload


class FakeStreamingContent:
    def __init__(self, lines):
        self._lines = [line if isinstance(line, bytes) else str(line).encode("utf-8") for line in list(lines)]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)


class FakeStreamingResponse(FakeResponse):
    def __init__(self, lines, *, status=200, message="OK"):
        super().__init__({})
        self.content = FakeStreamingContent(lines)
        self.status = status
        self.message = message

    async def text(self):
        return ""


class FakeOandaSession:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self.last_order_payload = None
        self.last_close_payload = None
        self.last_candle_params = None
        self.last_stream_params = None

    def request(self, method, url, headers=None, params=None, json=None):
        if "/pricing/stream" in url:
            self.last_stream_params = dict(params or {})
            return FakeStreamingResponse(
                [
                    json_module.dumps({"type": "HEARTBEAT", "time": "2026-03-10T10:00:00Z"}),
                    json_module.dumps(
                        {
                            "type": "PRICE",
                            "instrument": "EUR_USD",
                            "time": "2026-03-10T10:00:01Z",
                            "tradeable": True,
                            "status": "tradeable",
                            "bids": [{"price": "1.1000", "liquidity": 100000}],
                            "asks": [{"price": "1.1002", "liquidity": 100000}],
                        }
                    ),
                ]
            )
        if url.endswith("/pricing"):
            return FakeResponse(
                {
                    "prices": [
                        {
                            "instrument": "EUR_USD",
                            "bids": [{"price": "1.1000", "liquidity": 100000}],
                            "asks": [{"price": "1.1002", "liquidity": 100000}],
                        }
                    ]
                }
            )
        if "/candles" in url:
            params = dict(params or {})
            self.last_candle_params = params
            price_component = str(params.get("price") or "M").upper()
            candle_key = {"B": "bid", "A": "ask", "M": "mid"}.get(price_component, "mid")
            candle_payloads = {
                "bid": [
                    {"complete": True, "time": "t1", "bid": {"o": "0.9998", "h": "1.9998", "l": "0.4998", "c": "1.4998"}, "volume": 10},
                    {"complete": True, "time": "t2", "bid": {"o": "1.4998", "h": "2.4998", "l": "0.9998", "c": "1.9998"}, "volume": 12},
                ],
                "ask": [
                    {"complete": True, "time": "t1", "ask": {"o": "1.0002", "h": "2.0002", "l": "0.5002", "c": "1.5002"}, "volume": 10},
                    {"complete": True, "time": "t2", "ask": {"o": "1.5002", "h": "2.5002", "l": "1.0002", "c": "2.0002"}, "volume": 12},
                ],
                "mid": [
                    {"complete": True, "time": "t1", "mid": {"o": "1.0", "h": "2.0", "l": "0.5", "c": "1.5"}, "volume": 10},
                    {"complete": True, "time": "t2", "mid": {"o": "1.5", "h": "2.5", "l": "1.0", "c": "2.0"}, "volume": 12},
                ],
            }
            return FakeResponse(
                {
                    "candles": candle_payloads[candle_key]
                }
            )
        if url.endswith("/summary"):
            return FakeResponse({"account": {"currency": "USD", "balance": "1000", "NAV": "1100", "marginUsed": "100"}})
        if url.endswith("/instruments"):
            return FakeResponse({"instruments": [{"name": "EUR_USD"}, {"name": "GBP_USD"}]})
        if url.endswith("/orders") and method == "GET":
            return FakeResponse({"orders": [{"id": "1", "instrument": "EUR_USD", "state": "PENDING"}]})
        if url.endswith("/orders") and method == "POST":
            self.last_order_payload = json
            return FakeResponse({"orderCreateTransaction": {"id": "2"}})
        if url.endswith("/openPositions"):
            return FakeResponse(
                {
                    "positions": [
                        {
                            "instrument": "EUR_USD",
                            "long": {"units": "3", "averagePrice": "1.2"},
                            "short": {"units": "2", "averagePrice": "1.3"},
                            "pl": "12",
                            "unrealizedPL": "8",
                            "marginUsed": "50",
                            "positionValue": "600",
                        }
                    ]
                }
            )
        if "/positions/" in url and url.endswith("/close"):
            self.last_close_payload = json
            if "shortUnits" in (json or {}):
                return FakeResponse({"shortOrderCreateTransaction": {"id": "3", "instrument": "EUR_USD", "type": "MARKET_ORDER"}})
            return FakeResponse({"longOrderCreateTransaction": {"id": "4", "instrument": "EUR_USD", "type": "MARKET_ORDER"}})
        if "/cancel" in url:
            return FakeResponse({"orderCancelTransaction": {"id": "1"}})
        if "/orders/" in url:
            return FakeResponse({"order": {"id": "1", "instrument": "EUR_USD"}})
        if url.endswith("/trades"):
            return FakeResponse({"trades": [{"instrument": "EUR_USD"}]})
        raise AssertionError(f"Unhandled Oanda URL: {method} {url}")

    async def close(self):
        self.closed = True


class FakeOandaEmptyBidSession(FakeOandaSession):
    def request(self, method, url, headers=None, params=None, json=None):
        if "/candles" in url:
            params = dict(params or {})
            self.last_candle_params = params
            if str(params.get("price") or "M").upper() == "B":
                return FakeResponse({"candles": []})
        return super().request(method, url, headers=headers, params=params, json=json)


class FakeAlpacaREST:
    def __init__(self, api_key, secret, base_url, api_version="v2"):
        self.api_key = api_key
        self.secret = secret
        self.base_url = base_url
        self.latest_trade_feed = None
        self.latest_quote_feed = None
        self.bars_feed = None

    def get_account(self):
        return SimpleNamespace(
            status="ACTIVE",
            cash="5000",
            equity="5200",
            buying_power="7000",
            initial_margin="1200",
            maintenance_margin="900",
            portfolio_value="5200",
            long_market_value="4000",
            short_market_value="0",
        )

    def get_latest_trade(self, symbol, feed=None):
        self.latest_trade_feed = feed
        return SimpleNamespace(price=201.5)

    def get_latest_quote(self, symbol, feed=None):
        self.latest_quote_feed = feed
        return SimpleNamespace(bid_price=201.0, ask_price=202.0)

    def get_bars(self, symbol, timeframe, limit=100, feed=None):
        self.bars_feed = feed
        return [
            SimpleNamespace(t="t1", o=1.0, h=2.0, l=0.5, c=1.5, v=10),
            SimpleNamespace(t="t2", o=1.5, h=2.5, l=1.0, c=2.0, v=11),
        ]

    def list_assets(self, status="active"):
        return [
            SimpleNamespace(symbol="AAPL", tradable=True, status="active", marginable=True, shortable=True, fractionable=True),
            SimpleNamespace(symbol="TSLA", tradable=True, status="active", marginable=True, shortable=True, fractionable=True),
        ]

    def submit_order(self, **kwargs):
        return SimpleNamespace(
            id="alp-1",
            symbol=kwargs["symbol"],
            side=kwargs["side"],
            type=kwargs["type"],
            status="accepted",
            qty=str(kwargs["qty"]),
            filled_qty="0",
            limit_price=str(kwargs.get("limit_price", 0)),
            stop_price=str(kwargs.get("stop_price", 0)),
            filled_avg_price="0",
        )

    def cancel_order(self, order_id):
        return {"id": order_id, "status": "canceled"}

    def cancel_all_orders(self):
        return [{"status": "canceled"}]

    def get_order(self, order_id):
        return SimpleNamespace(
            id=order_id,
            symbol="AAPL",
            side="buy",
            type="market",
            status="filled",
            qty="2",
            filled_qty="2",
            filled_avg_price="200",
            filled_at="2026-03-31T10:00:00Z",
        )

    def list_orders(self, status="all", limit=None):
        orders = [
            SimpleNamespace(
                id="1",
                symbol="AAPL",
                side="buy",
                type="market",
                status="new",
                qty="2",
                filled_qty="0",
                filled_avg_price="0",
                submitted_at="2026-03-31T09:55:00Z",
            ),
            SimpleNamespace(
                id="2",
                symbol="TSLA",
                side="sell",
                type="limit",
                status="filled",
                qty="1",
                filled_qty="1",
                limit_price="300",
                filled_avg_price="300",
                filled_at="2026-03-31T10:01:00Z",
            ),
        ]
        return orders[:limit] if limit else orders

    def list_positions(self):
        return [SimpleNamespace(symbol="AAPL", qty="2", avg_entry_price="199", market_value="402")]

    def close(self):
        return None


def test_oanda_broker_normalizes_common_methods(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        ticker = await broker.fetch_ticker("EUR/USD")
        assert ticker["symbol"] == "EUR/USD"
        assert ticker["instrument"] == "EUR_USD"
        assert ticker["ask"] == 1.1002
        assert (await broker.fetch_orderbook("EUR/USD"))["bids"][0][0] == 1.1
        assert len(await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=2)) == 2
        assert broker.session.last_candle_params["price"] == "B"
        assert (await broker.fetch_balance())["equity"] == 1100.0
        assert await broker.fetch_symbols() == ["EUR/USD", "GBP/USD"]
        positions = await broker.fetch_positions()
        assert len(positions) == 2
        assert positions[0]["symbol"] == "EUR/USD"
        assert positions[0]["instrument"] == "EUR_USD"
        assert {item["position_side"] for item in positions} == {"long", "short"}
        assert len(await broker.fetch_open_orders("EUR/USD")) == 1
        assert len(await broker.fetch_closed_orders("EUR/USD")) == 0
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_stream_ticks_uses_pricing_stream(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        stream = broker.stream_ticks("EUR/USD")
        tick = await anext(stream)
        await stream.aclose()
        return broker, tick

    broker, tick = asyncio.run(scenario())

    assert tick["symbol"] == "EUR/USD"
    assert tick["instrument"] == "EUR_USD"
    assert tick["bid"] == 1.1
    assert tick["ask"] == 1.1002
    assert tick["price"] == pytest.approx(1.1001)
    assert broker.stream_base_url == "https://stream-fxpractice.oanda.com"


def test_oanda_broker_rebuilds_session_after_closing_transport(monkeypatch):
    import broker.oanda_broker as oanda_module

    created_sessions = []

    class FlakyPricingSession(FakeOandaSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fail_pricing_once = not created_sessions

        def request(self, method, url, headers=None, params=None, json=None):
            if url.endswith("/pricing") and self.fail_pricing_once:
                self.fail_pricing_once = False
                raise RuntimeError("Cannot write to closing transport")
            return super().request(method, url, headers=headers, params=params, json=json)

    def session_factory(*args, **kwargs):
        session = FlakyPricingSession(*args, **kwargs)
        created_sessions.append(session)
        return session

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", session_factory)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        ticker = await broker.fetch_ticker("EUR/USD")

        assert ticker["ask"] == 1.1002
        assert len(created_sessions) == 2
        assert created_sessions[0].closed is True
        assert created_sessions[1].closed is False

        await broker.close()

        assert created_sessions[1].closed is True

    asyncio.run(scenario())


def test_oanda_broker_supports_switching_between_bid_and_mid_candles(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(
            SimpleNamespace(
                api_key="token",
                account_id="acct-1",
                mode="practice",
                options={"candle_price_component": "mid"},
            )
        )

        mid_candles = await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=2)
        assert broker.session.last_candle_params["price"] == "M"
        assert mid_candles[0][1:5] == [1.0, 2.0, 0.5, 1.5]

        broker.set_candle_price_component("bid")
        bid_candles = await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=2)
        assert broker.session.last_candle_params["price"] == "B"
        assert bid_candles[0][1:5] == [0.9998, 1.9998, 0.4998, 1.4998]
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_falls_back_to_midpoint_candles_when_bid_history_is_empty(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaEmptyBidSession)

    async def scenario():
        broker = OandaBroker(
            SimpleNamespace(
                api_key="token",
                account_id="acct-1",
                mode="practice",
                options={"candle_price_component": "bid"},
            )
        )

        candles = await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=2)

        assert broker.session.last_candle_params["price"] == "M"
        assert candles[0][1:5] == [1.0, 2.0, 0.5, 1.5]
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_falls_back_to_recent_time_window_when_latest_count_history_is_empty(monkeypatch):
    import broker.oanda_broker as oanda_module

    class EmptyCountOandaSession:
        def __init__(self, *args, **kwargs):
            self.closed = False
            self.calls = []

        def request(self, method, url, headers=None, params=None, json=None):
            params = dict(params or {})
            self.calls.append(params)
            if "/candles" not in url:
                raise AssertionError(f"Unhandled Oanda URL: {method} {url}")
            if "count" in params:
                candles = [
                    {
                        "complete": False,
                        "time": "2026-01-04T12:00:00Z",
                        "bid": {"o": "1.3", "h": "1.4", "l": "1.2", "c": "1.35"},
                        "volume": 3,
                    }
                ]
            else:
                candles = [
                    {
                        "complete": True,
                        "time": "2026-01-04T10:00:00Z",
                        "bid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"},
                        "volume": 11,
                    },
                    {
                        "complete": True,
                        "time": "2026-01-04T11:00:00Z",
                        "bid": {"o": "1.15", "h": "1.25", "l": "1.1", "c": "1.2"},
                        "volume": 12,
                    },
                ]
            return FakeResponse({"candles": candles})

        async def close(self):
            self.closed = True

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", EmptyCountOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        broker._utc_now = lambda: datetime(2026, 1, 4, 12, 0, tzinfo=timezone.utc)

        candles = await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=2)

        assert [row[0] for row in candles] == [
            "2026-01-04T10:00:00Z",
            "2026-01-04T11:00:00Z",
        ]
        assert "count" in broker.session.calls[0]
        assert "from" in broker.session.calls[1]
        assert "to" in broker.session.calls[1]
        await broker.close()

    asyncio.run(scenario())


def test_alpaca_broker_normalizes_common_methods(monkeypatch):
    import broker.alpaca_broker as alpaca_module

    monkeypatch.setattr(alpaca_module, "tradeapi", SimpleNamespace(REST=FakeAlpacaREST))

    async def scenario():
        broker = AlpacaBroker(SimpleNamespace(api_key="key", secret="secret", mode="paper", sandbox=False))
        assert (await broker.fetch_ticker("AAPL"))["bid"] == 201.0
        assert broker.exchange_name == "alpaca"
        assert (await broker.fetch_orderbook("AAPL"))["asks"][0][0] == 202.0
        assert len(await broker.fetch_ohlcv("AAPL", timeframe="1h", limit=2)) == 2
        assert "AAPL" in await broker.fetch_symbols()
        markets = await broker.fetch_markets()
        assert markets["AAPL"]["quote"] == "USD"
        balance = await broker.fetch_balance()
        assert balance["cash"] == 5000.0
        assert balance["buying_power"] == 7000.0
        assert balance["available_funds"] == 7000.0
        assert balance["free"]["USD"] == 7000.0
        assert balance["raw"]["status"] == "ACTIVE"
        assert (await broker.fetch_positions())[0]["symbol"] == "AAPL"
        order = await broker.create_order("AAPL", "buy", 2, type="limit", price=200)
        assert order["symbol"] == "AAPL"
        stop_limit = await broker.create_order("AAPL", "buy", 1, type="stop_limit", price=200, stop_price=201)
        assert stop_limit["type"] == "stop_limit"
        assert stop_limit["stop_price"] == 201.0
        trade_rows = await broker.fetch_trades("AAPL", limit=5)
        assert trade_rows[0]["symbol"] == "AAPL"
        assert trade_rows[0]["price"] == 201.5
        my_trades = await broker.fetch_my_trades(limit=5)
        assert my_trades[0]["status"] == "filled"
        assert len(await broker.fetch_closed_orders(limit=5)) == 1
        assert broker.api.latest_trade_feed == "iex"
        assert broker.api.latest_quote_feed == "iex"
        assert broker.api.bars_feed == "iex"
        await broker.close()

    asyncio.run(scenario())


def test_alpaca_entity_value_prefers_raw_payload_before_lazy_attributes():
    class LazyTimestampEntity:
        def __init__(self):
            self._raw = {"submitted_at": "2026-03-31T09:55:00Z"}

        def __getattr__(self, name):
            raise AssertionError(f"lazy attribute access should not be triggered for {name}")

    entity = LazyTimestampEntity()

    assert AlpacaBroker._entity_value(entity, "filled_at", "submitted_at") == "2026-03-31T09:55:00Z"


def test_alpaca_open_orders_snapshot_lists_orders_once_for_multiple_symbols(monkeypatch):
    import broker.alpaca_broker as alpaca_module

    class CountingAlpacaREST(FakeAlpacaREST):
        def __init__(self, api_key, secret, base_url, api_version="v2"):
            super().__init__(api_key, secret, base_url, api_version=api_version)
            self.list_orders_calls = []

        def list_orders(self, status="all", limit=None):
            self.list_orders_calls.append({"status": status, "limit": limit})
            return super().list_orders(status=status, limit=limit)

    monkeypatch.setattr(alpaca_module, "tradeapi", SimpleNamespace(REST=CountingAlpacaREST))

    async def scenario():
        broker = AlpacaBroker(SimpleNamespace(api_key="key", secret="secret", mode="paper", sandbox=False))

        orders = await broker.fetch_open_orders_snapshot(symbols=["AAPL", "TSLA", "MSFT"], limit=200)

        assert {order["symbol"] for order in orders} == {"AAPL", "TSLA"}
        assert broker.api.list_orders_calls == [{"status": "open", "limit": 200}]
        await broker.close()

    asyncio.run(scenario())


def test_non_ccxt_brokers_report_supported_market_venues(monkeypatch):
    import broker.oanda_broker as oanda_module
    import broker.alpaca_broker as alpaca_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)
    monkeypatch.setattr(alpaca_module, "tradeapi", SimpleNamespace(REST=FakeAlpacaREST))

    oanda = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
    alpaca = AlpacaBroker(SimpleNamespace(api_key="key", secret="secret", mode="paper", sandbox=False))
    paper = PaperBroker(SimpleNamespace(logger=None, paper_balance=1000.0, initial_balance=1000.0, mode="paper", params={}))

    assert oanda.supported_market_venues() == ["auto", "otc"]
    assert alpaca.supported_market_venues() == ["auto", "spot"]
    assert paper.supported_market_venues() == ["auto", "spot", "derivative", "option", "otc"]


def test_alpaca_websocket_defaults_to_iex_and_limits_symbols_for_basic_feed():
    ws = AlpacaWebSocket(
        api_key="key",
        secret_key="secret",
        symbols=["AAPL", "TSLA", "MSFT"] * 20,
        event_bus=SimpleNamespace(),
    )

    assert ws.feed == "iex"
    assert ws.max_symbols == 30
    assert ws.url.endswith("/v2/iex")
    assert len(ws.symbols) >= 3


def test_paper_broker_exposes_normalized_api(monkeypatch):
    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.symbols = ["BTC/USDT"]
            self.candle_buffers = {}
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None)
            self.time_frame = "1h"
            self.broker = None

            self.ticker_buffer.update(
                "BTC/USDT",
                {"symbol": "BTC/USDT", "price": 100.0, "bid": 99.9, "ask": 100.1},
            )

    async def fake_market_data_broker(self, symbol=None):
        return None

    monkeypatch.setattr(PaperBroker, "_ensure_market_data_broker", fake_market_data_broker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)
        controller.broker = broker
        await broker.connect()
        ticker = await broker.fetch_ticker("BTC/USDT")
        assert ticker["last"] == 100.0
        orderbook = await broker.fetch_orderbook("BTC/USDT")
        assert orderbook["bids"][0][0] == 100.0
        order = await broker.create_order("BTC/USDT", "buy", 1, type="market")
        assert order["status"] == "filled"
        stop_limit = await broker.create_order("BTC/USDT", "buy", 1, type="stop_limit", price=99.0, stop_price=101.0)
        assert stop_limit["status"] == "open"
        assert stop_limit["stop_price"] == 101.0
        assert (await broker.fetch_balance())["free"]["USDT"] == 900.0
        assert (await broker.fetch_positions())[0]["symbol"] == "BTC/USDT"
        assert (await broker.fetch_positions(symbols=["BTC/USDT"]))[0]["symbol"] == "BTC/USDT"
        await broker.close()

    asyncio.run(scenario())


def test_paper_broker_bootstraps_public_market_data(monkeypatch):
    class FakeMarketDataBroker:
        def __init__(self, config):
            self.config = config
            self.closed = False

        async def connect(self):
            return True

        async def close(self):
            self.closed = True

        async def fetch_ticker(self, symbol):
            return {"symbol": symbol, "last": 123.4, "bid": 123.3, "ask": 123.5}

        async def fetch_orderbook(self, symbol, limit=50):
            return {"symbol": symbol, "bids": [[123.3, 5.0]], "asks": [[123.5, 4.0]]}

        async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
            return [["t1", 120.0, 125.0, 119.0, 123.4, 42.0]]

        async def fetch_symbols(self):
            return ["BTC/USDT", "ETH/USDT"]

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.symbols = ["BTC/USDT"]
            self.candle_buffers = {}
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.time_frame = "1h"
            self.broker = None
            self.config = SimpleNamespace(
                broker=SimpleNamespace(params={"paper_data_exchange": "binanceus"})
            )

    monkeypatch.setattr(paper_module, "CCXTBroker", FakeMarketDataBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)
        controller.broker = broker
        market_data_config = broker._build_market_data_config()
        assert market_data_config.mode == "live"
        assert market_data_config.sandbox is False
        await broker.connect()

        ticker = await broker.fetch_ticker("BTC/USDT")
        assert ticker["last"] == 123.4
        assert controller.ticker_buffer.latest("BTC/USDT")["last"] == 123.4

        orderbook = await broker.fetch_orderbook("BTC/USDT")
        assert orderbook["asks"][0][0] == 123.5

        candles = await broker.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=1)
        assert candles[0][4] == 123.4

        symbols = await broker.fetch_symbols()
        assert "ETH/USDT" in symbols

        await broker.close()
        assert broker.market_data_broker is None

    asyncio.run(scenario())


def test_paper_broker_uses_selected_exchange_identity_when_configured(monkeypatch):
    class FakeMarketDataBroker:
        def __init__(self, config):
            self.config = config

        async def connect(self):
            return True

        async def close(self):
            return True

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.initial_balance = 1000.0
            self.mode = "paper"
            self.symbols = ["BTC/USDT"]
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.config = SimpleNamespace(
                broker=SimpleNamespace(exchange="coinbase", params={})
            )

    monkeypatch.setattr(paper_module, "CCXTBroker", FakeMarketDataBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)

        assert broker.exchange_name == "coinbase"
        assert broker.market_data_exchange == "coinbase"

        await broker.connect()
        status = await broker.fetch_status()

        assert status["broker"] == "coinbase"
        assert status["mode"] == "paper"
        assert status["market_data_exchange"] == "coinbase"

        await broker.close()

    asyncio.run(scenario())


def test_paper_broker_fetch_symbols_uses_broker_config_not_stale_controller_symbols(monkeypatch):
    class FakeMarketDataBroker:
        def __init__(self, config):
            self.config = config

        async def connect(self):
            return True

        async def close(self):
            return True

        async def fetch_symbols(self):
            return []

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.initial_balance = 1000.0
            self.mode = "paper"
            self.symbols = ["GBP/USD", "EUR/USD", "NZD/USD"]
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.config = SimpleNamespace(
                broker=SimpleNamespace(exchange="coinbase", params={"symbols": ["BTC/USD", "ETH/USD"]})
            )

    monkeypatch.setattr(paper_module, "CCXTBroker", FakeMarketDataBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)

        symbols = await broker.fetch_symbols()

        assert symbols == ["BTC/USD", "ETH/USD"]
        assert "GBP/USD" not in symbols
        await broker.close()

    asyncio.run(scenario())


def test_paper_broker_forwards_backtest_time_range_to_public_market_data(monkeypatch):
    observed = {}

    class FakeMarketDataBroker:
        def __init__(self, config):
            self.config = config

        async def connect(self):
            return True

        async def close(self):
            return True

        async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
            observed.update(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "limit": limit,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            return [
                ["2024-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5, 10.0],
                ["2024-01-01T01:00:00Z", 100.5, 101.5, 100.0, 101.0, 12.0],
            ]

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.symbols = ["BTC/USDT"]
            self.candle_buffers = {}
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.time_frame = "1h"
            self.broker = None
            self.config = SimpleNamespace(
                broker=SimpleNamespace(params={"paper_data_exchange": "binanceus"})
            )

    monkeypatch.setattr(paper_module, "CCXTBroker", FakeMarketDataBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)
        controller.broker = broker
        await broker.connect()

        candles = await broker.fetch_ohlcv(
            "BTC/USDT",
            timeframe="1h",
            limit=5000,
            start_time="2024-01-01",
            end_time="2025-12-31",
        )

        assert len(candles) == 2
        assert observed == {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 5000,
            "start_time": "2024-01-01",
            "end_time": "2025-12-31",
        }
        await broker.close()

    asyncio.run(scenario())


def test_paper_broker_keeps_legacy_market_data_adapters_working_for_range_requests(monkeypatch):
    observed = {}

    class FakeLegacyMarketDataBroker:
        def __init__(self, config):
            self.config = config

        async def connect(self):
            return True

        async def close(self):
            return True

        async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
            observed.update(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "limit": limit,
                }
            )
            return [["2026-01-01T00:00:00Z", 120.0, 121.0, 119.0, 120.5, 42.0]]

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.symbols = ["BTC/USDT"]
            self.candle_buffers = {}
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.time_frame = "1h"
            self.broker = None
            self.config = SimpleNamespace(
                broker=SimpleNamespace(params={"paper_data_exchange": "binanceus"})
            )

    monkeypatch.setattr(paper_module, "CCXTBroker", FakeLegacyMarketDataBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)
        controller.broker = broker
        await broker.connect()

        candles = await broker.fetch_ohlcv(
            "BTC/USDT",
            timeframe="1h",
            limit=300,
            start_time="2024-01-01",
            end_time="2024-12-31",
        )

        assert candles[0][4] == 120.5
        assert observed == {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 300,
        }
        await broker.close()

    asyncio.run(scenario())


def test_base_broker_close_all_positions_uses_opposite_side():
    class DummyBroker(PaperBroker):
        def __init__(self):
            controller = SimpleNamespace(
                logger=None,
                paper_balance=1000.0,
                symbols=["BTC/USDT"],
                candle_buffers={},
                ticker_buffer=TickerBuffer(),
                ticker_stream=SimpleNamespace(get=lambda symbol: None),
                time_frame="1h",
                broker=None,
            )
            super().__init__(controller)
            self.orders_sent = []
            self.positions = {
                "BTC/USDT": {
                    "symbol": "BTC/USDT",
                    "amount": 2.0,
                    "entry_price": 100.0,
                    "side": "long",
                }
            }

        async def connect(self):
            return True

        async def close(self):
            return True

        async def create_order(self, symbol, side, amount, type="market", price=None, params=None, **kwargs):
            order = {
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "type": type,
            }
            self.orders_sent.append(order)
            return order

    async def scenario():
        broker = DummyBroker()
        results = await broker.close_all_positions()
        assert len(results) == 1
        assert broker.orders_sent[0]["symbol"] == "BTC/USDT"
        assert broker.orders_sent[0]["side"] == "sell"
        assert broker.orders_sent[0]["amount"] == 2.0

    asyncio.run(scenario())


def test_oanda_broker_formats_order_payload(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        created = await broker.create_order("EUR/USD", "buy", 1, type="market")
        assert created["symbol"] == "EUR/USD"
        assert created["instrument"] == "EUR_USD"
        payload = broker.session.last_order_payload["order"]
        assert payload["instrument"] == "EUR_USD"
        assert payload["type"] == "MARKET"
        assert payload["timeInForce"] == "FOK"
        assert payload["units"] == "1"

        await broker.create_order("EUR/USD", "sell", 2, type="limit", price=1.23456)
        payload = broker.session.last_order_payload["order"]
        assert payload["type"] == "LIMIT"
        assert payload["timeInForce"] == "GTC"
        assert payload["units"] == "-2"
        assert payload["price"] == "1.23456"

        await broker.create_order("EUR/USD", "buy", 1, type="stop_limit", price=1.24001, stop_price=1.23501)
        payload = broker.session.last_order_payload["order"]
        assert payload["type"] == "STOP"
        assert payload["price"] == "1.23501"
        assert payload["priceBound"] == "1.24001"

        await broker.create_order(
            "EUR/USD",
            "buy",
            1,
            type="market",
            stop_loss=1.21001,
            take_profit=1.26001,
        )
        payload = broker.session.last_order_payload["order"]
        assert payload["stopLossOnFill"]["price"] == "1.21001"
        assert payload["takeProfitOnFill"]["price"] == "1.26001"
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_cancels_orders(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        canceled = await broker.cancel_order("1", symbol="EUR/USD")
        assert canceled["id"] == "1"
        assert canceled["status"] == "canceled"
        assert canceled["symbol"] == "EUR/USD"
        assert canceled["instrument"] == "EUR_USD"

        all_canceled = await broker.cancel_all_orders(symbol="EUR/USD")
        assert len(all_canceled) == 1
        assert all_canceled[0]["status"] == "canceled"
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_closes_specific_hedge_leg(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        positions = await broker.fetch_positions(symbols=["EUR/USD"])
        short_leg = next(item for item in positions if item["position_side"] == "short")
        result = await broker.close_position("EUR/USD", position=short_leg)
        assert result["position_side"] == "short"
        assert broker.session.last_close_payload == {"shortUnits": "ALL"}
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_clamps_stale_partial_close_to_live_leg_size(monkeypatch):
    import broker.oanda_broker as oanda_module

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", FakeOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        stale_short_leg = {
            "symbol": "EUR_USD",
            "position_id": "EUR_USD:short",
            "position_side": "short",
            "amount": 10.0,
            "units": -10.0,
        }
        result = await broker.close_position("EUR/USD", amount=10.0, position=stale_short_leg)
        assert result["position_side"] == "short"
        assert result["amount"] == 2.0
        assert broker.session.last_close_payload == {"shortUnits": "ALL"}
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_surfaces_reject_reason(monkeypatch):
    import aiohttp
    import broker.oanda_broker as oanda_module

    class RejectResponse(FakeResponse):
        def __init__(self, payload, status=400, message="Bad Request"):
            super().__init__(payload)
            self.status = status
            self.message = message

        def raise_for_status(self):
            raise aiohttp.ClientResponseError(
                request_info=None,
                history=(),
                status=self.status,
                message=self.message,
                headers=None,
            )

        async def text(self):
            return json_module.dumps(self.payload)

    class RejectSession(FakeOandaSession):
        def request(self, method, url, headers=None, params=None, json=None):
            if url.endswith("/instruments"):
                return FakeResponse({"instruments": [{"name": "EUR_USD"}]})
            if url.endswith("/orders") and method == "POST":
                return RejectResponse(
                    {
                        "errorMessage": "The account has insufficient margin available.",
                        "orderRejectTransaction": {"rejectReason": "INSUFFICIENT_MARGIN"},
                    }
                )
            return super().request(method, url, headers=headers, params=params, json=json)

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", RejectSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="live"))
        try:
            await broker.create_order("EUR/USD", "buy", 1, type="market")
        except RuntimeError as exc:
            message = str(exc)
            assert "insufficient margin available" in message.lower()
            assert "insufficient_margin" in message.lower()
        else:
            raise AssertionError("Expected Oanda rejection to raise RuntimeError")
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_paginates_ohlcv_history(monkeypatch):
    import broker.oanda_broker as oanda_module

    class PagingOandaSession:
        def __init__(self, *args, **kwargs):
            self.closed = False
            self.calls = []

        def request(self, method, url, headers=None, params=None, json=None):
            if "/candles" in url:
                params = params or {}
                self.calls.append(dict(params))
                cursor = params.get("to")
                if not cursor:
                    candles = [
                        {"complete": True, "time": "2026-01-03T00:00:00Z", "mid": {"o": "1.3", "h": "1.4", "l": "1.2", "c": "1.35"}, "volume": 13},
                        {"complete": True, "time": "2026-01-04T00:00:00Z", "mid": {"o": "1.35", "h": "1.5", "l": "1.3", "c": "1.45"}, "volume": 14},
                    ]
                else:
                    candles = [
                        {"complete": True, "time": "2026-01-01T00:00:00Z", "mid": {"o": "1.0", "h": "1.2", "l": "0.9", "c": "1.1"}, "volume": 10},
                        {"complete": True, "time": "2026-01-02T00:00:00Z", "mid": {"o": "1.1", "h": "1.3", "l": "1.0", "c": "1.2"}, "volume": 11},
                        {"complete": True, "time": "2026-01-03T00:00:00Z", "mid": {"o": "1.3", "h": "1.4", "l": "1.2", "c": "1.35"}, "volume": 13},
                    ]
                return FakeResponse({"candles": candles})
            raise AssertionError(f"Unhandled Oanda URL: {method} {url}")

        async def close(self):
            self.closed = True

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", PagingOandaSession)

    async def scenario():
        broker = OandaBroker(
            SimpleNamespace(
                api_key="token",
                account_id="acct-1",
                mode="practice",
                options={"candle_price_component": "mid"},
            )
        )
        broker.MAX_OHLCV_COUNT = 2

        candles = await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=4)

        assert len(candles) == 4
        assert [row[0] for row in candles] == [
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            "2026-01-03T00:00:00Z",
            "2026-01-04T00:00:00Z",
        ]
        assert len(broker.session.calls) == 2
        assert broker.session.calls[1]["to"] == "2026-01-03T00:00:00Z"
        await broker.close()

    asyncio.run(scenario())


def test_oanda_broker_paginates_explicit_date_range(monkeypatch):
    import broker.oanda_broker as oanda_module

    class RangePagingOandaSession:
        def __init__(self, *args, **kwargs):
            self.closed = False
            self.calls = []

        def request(self, method, url, headers=None, params=None, json=None):
            if "/candles" not in url:
                raise AssertionError(f"Unhandled Oanda URL: {method} {url}")

            params = dict(params or {})
            self.calls.append(params)
            start = str(params.get("from") or "")
            if "2026-01-01" in start:
                candles = [
                    {"complete": True, "time": "2026-01-01T00:00:00Z", "bid": {"o": "1.0", "h": "1.1", "l": "0.9", "c": "1.05"}, "volume": 10},
                    {"complete": True, "time": "2026-01-02T00:00:00Z", "bid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"}, "volume": 11},
                ]
            else:
                candles = [
                    {"complete": True, "time": "2026-01-03T00:00:00Z", "bid": {"o": "1.2", "h": "1.3", "l": "1.1", "c": "1.25"}, "volume": 12},
                    {"complete": True, "time": "2026-01-04T00:00:00Z", "bid": {"o": "1.3", "h": "1.4", "l": "1.2", "c": "1.35"}, "volume": 13},
                ]
            return FakeResponse({"candles": candles})

        async def close(self):
            self.closed = True

    monkeypatch.setattr(oanda_module.aiohttp, "ClientSession", RangePagingOandaSession)

    async def scenario():
        broker = OandaBroker(SimpleNamespace(api_key="token", account_id="acct-1", mode="practice"))
        broker.MAX_OHLCV_COUNT = 2

        candles = await broker.fetch_ohlcv(
            "EUR/USD",
            timeframe="1d",
            limit=10,
            start_time="2026-01-01",
            end_time="2026-01-04",
        )

        assert [row[0] for row in candles] == [
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            "2026-01-03T00:00:00Z",
            "2026-01-04T00:00:00Z",
        ]
        assert len(broker.session.calls) == 2
        assert "count" not in broker.session.calls[0]
        assert broker.session.calls[0]["from"].startswith("2026-01-01T00:00:00")
        assert broker.session.calls[0]["to"].startswith("2026-01-02T00:00:00")
        assert broker.session.calls[1]["from"].startswith("2026-01-03T00:00:00")
        assert broker.session.calls[1]["to"].startswith("2026-01-04T23:59:59")
        await broker.close()

    asyncio.run(scenario())


def test_paper_broker_falls_back_for_xlm_usdt_daily_history(monkeypatch):
    class FakeMarketDataBroker:
        def __init__(self, config):
            self.config = config
            self.exchange = config.exchange

        async def connect(self):
            return True

        async def close(self):
            return True

        async def fetch_ticker(self, symbol):
            if self.exchange == "binanceus" and symbol == "XLM/USDT":
                raise RuntimeError("symbol not available")
            return {"symbol": symbol, "last": 0.125, "bid": 0.124, "ask": 0.126}

        async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
            if self.exchange == "binanceus" and symbol == "XLM/USDT":
                return []
            return [[1710000000000, 0.10, 0.13, 0.09, 0.125, 1000000.0]]

        async def fetch_symbols(self):
            if self.exchange == "binanceus":
                return ["BTC/USDT"]
            return ["BTC/USDT", "XLM/USDT"]

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.symbols = ["XLM/USDT"]
            self.candle_buffers = {}
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.time_frame = "1d"
            self.broker = None
            self.config = SimpleNamespace(
                broker=SimpleNamespace(params={"paper_data_exchanges": ["binanceus", "binance"]})
            )

    monkeypatch.setattr(paper_module, "CCXTBroker", FakeMarketDataBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)
        controller.broker = broker
        await broker.connect()

        candles = await broker.fetch_ohlcv("XLM/USDT", timeframe="1d", limit=300)
        ticker = await broker.fetch_ticker("XLM/USDT")

        assert candles[0][4] == 0.125
        assert ticker["last"] == 0.125
        assert broker.market_data_exchange == "binance"

        await broker.close()

    asyncio.run(scenario())


def test_paper_broker_uses_solana_adapter_for_native_market_data(monkeypatch):
    class FakeSolanaBroker:
        def __init__(self, config):
            self.config = config
            self.exchange_name = "solana"

        async def connect(self):
            return True

        async def close(self):
            return True

        async def fetch_ticker(self, symbol):
            return {"symbol": symbol, "last": 142.5, "bid": 142.0, "ask": 143.0}

    class DummyController:
        def __init__(self):
            self.logger = None
            self.paper_balance = 1000.0
            self.initial_balance = 1000.0
            self.mode = "paper"
            self.symbols = ["SOL/USDC"]
            self.ticker_buffer = TickerBuffer()
            self.ticker_stream = SimpleNamespace(get=lambda symbol: None, update=lambda symbol, ticker: None)
            self.config = SimpleNamespace(
                broker=SimpleNamespace(params={"paper_data_exchange": "solana"})
            )

    monkeypatch.setattr(
        paper_module,
        "CCXTBroker",
        lambda _config: (_ for _ in ()).throw(AssertionError("CCXTBroker should not bootstrap Solana market data")),
    )
    monkeypatch.setattr(paper_module, "SolanaBroker", FakeSolanaBroker)

    async def scenario():
        controller = DummyController()
        broker = PaperBroker(controller)
        await broker.connect()

        ticker = await broker.fetch_ticker("SOL/USDC")

        assert ticker["last"] == 142.5
        assert broker.market_data_exchange == "solana"
        assert isinstance(broker.market_data_broker, FakeSolanaBroker)

        await broker.close()

    asyncio.run(scenario())
