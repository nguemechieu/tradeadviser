import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import ccxt.async_support as ccxt
import jwt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.ccxt_broker import CCXTBroker
from broker.broker_errors import BrokerOperationError
from event_bus.event_bus import EventBus
from market_data.websocket.coinbase_web_socket import CoinbaseWebSocket


class FakeSession:
    def __init__(self, connector=None):
        self.connector = connector
        self.closed = False

    async def close(self):
        self.closed = True


class FakeHTTPResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)

    async def json(self, content_type=None):
        if isinstance(self.payload, str):
            return json.loads(self.payload)
        return self.payload


class FakeCoinbaseApiSession(FakeSession):
    def __init__(self, connector=None, responses=None):
        super().__init__(connector=connector)
        self.responses = dict(responses or {})
        self.requested_methods = []
        self.requested_urls = []
        self.requested_headers = []
        self.requested_json = []

    def request(self, method, url, headers=None, json=None):
        normalized_method = str(method or "GET").upper()
        self.requested_methods.append(normalized_method)
        self.requested_urls.append(url)
        self.requested_headers.append(dict(headers or {}))
        self.requested_json.append(json)
        payload = self.responses.get(f"{normalized_method} {url}", self.responses.get(url, {}))
        status = 200
        if isinstance(payload, tuple):
            status, payload = payload
        return FakeHTTPResponse(payload, status=status)

    def get(self, url, headers=None):
        return self.request("GET", url, headers=headers)


class FakeCoinbaseExchange:
    def __init__(self, cfg):
        self.cfg = cfg
        self.closed = False
        self.sandbox_mode = None
        self.id = "coinbase"
        self.urls = {"api": {"rest": "https://api.coinbase.com"}}
        self.fetch_ticker_calls = []
        self.fetch_balance_calls = 0
        self.fetch_open_orders_calls = []
        self.has = {
            "fetchTicker": True,
            "fetchTickers": True,
            "fetchOrderBook": True,
            "fetchOHLCV": True,
            "fetchTrades": True,
            "fetchMyTrades": True,
            "fetchStatus": True,
            "fetchOrders": True,
            "fetchOpenOrders": True,
            "fetchClosedOrders": True,
            "fetchOrder": True,
            "fetchBalance": True,
            "cancelOrder": True,
            "cancelAllOrders": True,
            "createOrder": True,
        }
        self.markets = {}
        self.currencies = {"USD": {"code": "USD"}}

    def set_sandbox_mode(self, enabled):
        self.sandbox_mode = enabled

    async def load_time_difference(self):
        return 0

    async def load_markets(self):
        self.markets = {
            "BTC/USD": {"symbol": "BTC/USD", "active": True},
            "ETH/USD": {"symbol": "ETH/USD", "active": True},
        }
        return self.markets

    async def fetch_ticker(self, symbol):
        self.fetch_ticker_calls.append(symbol)
        return {"symbol": symbol, "last": 65000.0, "bid": 64999.0, "ask": 65001.0}

    async def fetch_tickers(self, symbols=None):
        return {symbol: {"symbol": symbol, "last": 1 + idx} for idx, symbol in enumerate(symbols or [])}

    async def fetch_order_book(self, symbol, limit=100):
        return {"symbol": symbol, "bids": [[64999.0, 1.0]], "asks": [[65001.0, 1.5]], "limit": limit}

    async def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=100, params=None):
        return [[1710000000000 + i, 1, 2, 0.5, 1.5, 10] for i in range(limit)]

    async def fetch_trades(self, symbol, limit=None):
        return [{"symbol": symbol, "limit": limit}]

    async def fetch_my_trades(self, symbol=None, limit=None):
        return [{"symbol": symbol, "limit": limit, "private": True}]

    async def fetch_status(self):
        return {"status": "ok"}

    async def create_order(self, symbol, order_type, side, amount, price, params):
        return {
            "id": "cb-1",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "open",
            "params": params,
        }

    async def cancel_order(self, order_id, symbol=None):
        return {"id": order_id, "symbol": symbol, "status": "canceled"}

    async def cancel_all_orders(self, symbol=None):
        return [{"symbol": symbol, "status": "canceled"}]

    async def fetch_balance(self):
        self.fetch_balance_calls += 1
        return {"free": {"USD": 500.0, "BTC": 0.25}}

    async def fetch_order(self, order_id, symbol=None):
        return {"id": order_id, "symbol": symbol, "status": "filled", "filled": 0.01, "price": 65000.0}

    async def fetch_orders(self, symbol=None, limit=None):
        return [{"id": "cb-1", "symbol": symbol, "limit": limit}]

    async def fetch_open_orders(self, symbol=None, limit=None):
        self.fetch_open_orders_calls.append({"symbol": symbol, "limit": limit})
        return [{"id": "cb-1", "symbol": symbol, "limit": limit, "status": "open"}]

    async def fetch_closed_orders(self, symbol=None, limit=None):
        return [{"id": "cb-2", "symbol": symbol, "limit": limit, "status": "closed"}]

    def amount_to_precision(self, symbol, amount):
        return f"{amount:.8f}"

    def price_to_precision(self, symbol, price):
        return f"{price:.2f}"

    async def close(self):
        self.closed = True


class FakeFastBootstrapCoinbaseExchange(FakeCoinbaseExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.has["fetchMarkets"] = True
        self.fetch_markets_calls = 0
        self.load_markets_calls = 0

    async def fetch_markets(self):
        self.fetch_markets_calls += 1
        return [
            {"id": "BTC-USD", "symbol": "BTC/USD", "base": "BTC", "quote": "USD", "spot": True, "active": True},
            {"id": "ETH-USD", "symbol": "ETH/USD", "base": "ETH", "quote": "USD", "spot": True, "active": True},
        ]

    async def load_markets(self):
        self.load_markets_calls += 1
        raise AssertionError("Coinbase fast bootstrap should avoid load_markets")


class FakeSocket:
    def __init__(self, messages):
        self._messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, payload):
        self.sent = payload

    async def recv(self):
        if not self._messages:
            raise asyncio.CancelledError()
        return self._messages.pop(0)


class FakeCoinbaseHistoryExchange(FakeCoinbaseExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.fetch_ohlcv_calls = []

    async def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=100, params=None):
        params = dict(params or {})
        self.fetch_ohlcv_calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "since": since,
                "limit": limit,
                "params": params,
            }
        )
        timeframe_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }.get(timeframe, 3600)
        if since is None:
            count = min(int(limit or 5), 5)
            start_seconds = 1_710_000_000
        else:
            start_seconds = int(params.get("start") or int(since / 1000))
            end_seconds = int(params.get("end") or (start_seconds + (timeframe_seconds * int(limit or 300))))
            count = min(max(int((end_seconds - start_seconds) / timeframe_seconds), 0), 300)
        return [
            [(start_seconds + (index * timeframe_seconds)) * 1000, 1, 2, 0.5, 1.5, 10]
            for index in range(count)
        ]


class FakeCoinbaseCrossValuationExchange(FakeCoinbaseExchange):
    async def load_markets(self):
        self.markets = {
            "AAVE/EUR": {"symbol": "AAVE/EUR", "active": True},
            "BTC/EUR": {"symbol": "BTC/EUR", "active": True},
            "BTC/USD": {"symbol": "BTC/USD", "active": True},
        }
        return self.markets

    async def fetch_ticker(self, symbol):
        self.fetch_ticker_calls.append(symbol)
        prices = {
            "AAVE/EUR": {"last": 100.0, "bid": 99.5, "ask": 100.5},
            "BTC/EUR": {"last": 50000.0, "bid": 49950.0, "ask": 50050.0},
            "BTC/USD": {"last": 65000.0, "bid": 64950.0, "ask": 65050.0},
        }
        quote = prices[str(symbol)]
        return {"symbol": symbol, **quote}

    async def fetch_balance(self):
        return {"total": {"EUR": 1000.0, "AAVE": 2.0}}


class FakeStrictCoinbaseExchange(FakeCoinbaseExchange):
    async def load_markets(self):
        self.markets = {
            "BTC/USD": {"symbol": "BTC/USD", "active": True},
            "ETH/USD": {"symbol": "ETH/USD", "active": True},
        }
        return self.markets

    async def fetch_ticker(self, symbol):
        if symbol not in self.markets:
            raise ccxt.BadSymbol(f"coinbase does not have market symbol {symbol}")
        return await super().fetch_ticker(symbol)

    async def fetch_order_book(self, symbol, limit=100):
        if symbol not in self.markets:
            raise ccxt.BadSymbol(f"coinbase does not have market symbol {symbol}")
        return await super().fetch_order_book(symbol, limit=limit)

    async def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=100, params=None):
        if symbol not in self.markets:
            raise ccxt.BadSymbol(f"coinbase does not have market symbol {symbol}")
        return await super().fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit, params=params)

    async def fetch_trades(self, symbol, limit=None):
        if symbol not in self.markets:
            raise ccxt.BadSymbol(f"coinbase does not have market symbol {symbol}")
        return await super().fetch_trades(symbol, limit=limit)


class FakeBuggyCoinbaseCreateOrderExchange(FakeCoinbaseExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.id = "coinbase"

    async def create_order(self, symbol, order_type, side, amount, price, params):
        self.id = 123456789
        return await super().create_order(symbol, order_type, side, amount, price, params)


class FakeBuggyCoinbaseErrorHandlingExchange(FakeCoinbaseExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.id = "coinbase"

    def handle_errors(
        self,
        code,
        reason,
        url,
        method,
        headers,
        body,
        response,
        request_headers,
        request_body,
    ):
        raise RuntimeError(self.id + " " + body)

    async def create_order(self, symbol, order_type, side, amount, price, params):
        self.id = 123456789
        self.handle_errors(
            400,
            "Bad Request",
            "https://api.coinbase.com/api/v3/brokerage/orders",
            "POST",
            {},
            '{"error":"bad request"}',
            {},
            {},
            "{}",
        )


class FakeCoinbaseDerivativeExchange(FakeCoinbaseExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.fetch_positions_calls = []
        self.has["fetchPositions"] = True

    async def load_markets(self):
        self.markets = {
            "BTC/USD:USD": {
                "symbol": "BTC/USD:USD",
                "active": True,
                "base": "BTC",
                "quote": "USD",
                "settle": "USD",
                "spot": False,
                "contract": True,
                "future": True,
            },
            "ETH/USD:USD": {
                "symbol": "ETH/USD:USD",
                "active": True,
                "base": "ETH",
                "quote": "USD",
                "settle": "USD",
                "spot": False,
                "contract": True,
                "future": True,
            },
        }
        return self.markets

    async def fetch_positions(self, symbols=None):
        self.fetch_positions_calls.append(symbols)
        return [{"symbol": "BTC/USD:USD", "contracts": 1.0, "side": "long"}]


class FakeCoinbaseRawFuturesExchange(FakeCoinbaseExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.has["fetchMarkets"] = True
        self.has["fetchPositions"] = False
        self.fetch_markets_calls = 0

    async def fetch_markets(self):
        self.fetch_markets_calls += 1
        return [
            {
                "id": "SLP-20DEC30-CDE",
                "symbol": "SLP/USD",
                "base": "SLP",
                "quote": "USD",
                "type": "future",
                "spot": False,
                "future": False,
                "swap": False,
                "contract": False,
                "active": True,
                "info": {
                    "product_id": "SLP-20DEC30-CDE",
                    "product_type": "FUTURE",
                    "product_venue": "FCM",
                    "base_currency_id": "SLP",
                    "quote_currency_id": "USD",
                    "future_product_details": {
                        "contract_expiry_type": "EXPIRING",
                        "expiration_time": "2030-12-20T17:00:00Z",
                    },
                },
            },
            {
                "id": "ETH-USD-20241227",
                "symbol": "ETH/USD",
                "base": "ETH",
                "quote": "USD",
                "type": "future",
                "spot": False,
                "future": False,
                "swap": False,
                "contract": False,
                "active": True,
                "info": {
                    "product_id": "ETH-USD-20241227",
                    "product_type": "FUTURE",
                    "product_venue": "FCM",
                    "base_currency_id": "ETH",
                    "quote_currency_id": "USD",
                    "future_product_details": {
                        "contract_expiry_type": "EXPIRING",
                        "expiration_time": "2024-12-27T17:00:00Z",
                    },
                },
            },
        ]

    async def load_markets(self):
        raise AssertionError("Coinbase futures bootstrap should use fetch_markets")


def test_coinbase_ccxt_broker_supports_market_data_and_order_methods(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        config = SimpleNamespace(
            exchange="coinbase",
            api_key="key",
            secret="secret",
            password="passphrase",
            uid=None,
            mode="live",
            sandbox=False,
            timeout=15000,
            options={},
            params={"clientOrderId": "coinbase-client"},
        )
        broker = CCXTBroker(config)

        await broker.connect()

        assert broker.session.connector["resolver"] == "threaded-resolver"
        assert "BTC/USD" in await broker.fetch_symbols()
        assert broker.supported_market_venues() == ["auto", "spot", "derivative"]
        assert (await broker.fetch_ticker("BTC/USD"))["bid"] == 64999.0
        assert len(await broker.fetch_ohlcv("BTC/USD", limit=3)) == 3
        assert (await broker.fetch_orderbook("BTC/USD"))["asks"][0][0] == 65001.0
        assert (await broker.fetch_balance())["free"]["USD"] == 500.0
        assert (await broker.fetch_open_orders("BTC/USD", limit=5))[0]["status"] == "open"

        order = await broker.create_order(
            symbol="BTC/USD",
            side="buy",
            amount=0.010000123,
            type="limit",
            price=65000.129,
            params={"timeInForce": "GTC"},
        )
        assert order["amount"] == 0.01000012
        assert order["price"] == 65000.13
        assert order["params"]["clientOrderId"] == "coinbase-client"
        assert order["params"]["timeInForce"] == "GTC"

        stop_limit_order = await broker.create_order(
            symbol="BTC/USD",
            side="buy",
            amount=0.01,
            type="stop_limit",
            price=64950.12,
            stop_price=65010.0,
        )
        assert stop_limit_order["type"] == "stop_limit"
        assert stop_limit_order["stop_price"] == 65010.0
        assert stop_limit_order["params"]["stopPrice"] == 65010.0

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_uses_fast_market_bootstrap_when_fetch_markets_is_available(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeFastBootstrapCoinbaseExchange, raising=False)

    async def scenario():
        broker = CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="key",
                secret="secret",
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        assert broker.symbols == ["BTC/USD", "ETH/USD"]
        assert broker.exchange.fetch_markets_calls == 1
        assert broker.exchange.load_markets_calls == 0

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_restores_exchange_id_after_create_order(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeBuggyCoinbaseCreateOrderExchange, raising=False)

    async def scenario():
        broker = CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()
        assert broker.exchange.id == "coinbase"

        order = await broker.create_order(
            symbol="BTC/USD",
            side="buy",
            amount=0.01,
            type="limit",
            price=65000.0,
        )

        assert order["id"] == "cb-1"
        assert broker.exchange.id == "coinbase"

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_preserves_exchange_id_during_error_handling(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeBuggyCoinbaseErrorHandlingExchange, raising=False)

    async def scenario():
        broker = CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()
        assert broker.exchange.id == "coinbase"

        try:
            await broker.create_order(
                symbol="BTC/USD",
                side="buy",
                amount=0.01,
                type="limit",
                price=65000.0,
            )
        except BrokerOperationError as exc:
            assert exc.raw_message == 'coinbase {"error":"bad request"}'
            assert str(exc) == 'COINBASE failed while create order: coinbase {"error":"bad request"}'
        else:
            raise AssertionError("Expected create_order to surface the exchange error")

        assert broker.exchange.id == "coinbase"
        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_exposes_advanced_trade_helpers():
    broker = CCXTBroker(SimpleNamespace(exchange="coinbase", options={}, params={}))

    expected_methods = [
        "fetch_coinbase_accounts",
        "fetch_coinbase_account",
        "create_coinbase_order",
        "cancel_coinbase_orders",
        "fetch_coinbase_orders",
        "fetch_coinbase_fills",
        "fetch_coinbase_historical_order",
        "preview_coinbase_order",
        "fetch_coinbase_best_bid_ask",
        "fetch_coinbase_product_book",
        "fetch_coinbase_products",
        "fetch_coinbase_product",
        "fetch_coinbase_product_candles",
        "fetch_coinbase_market_trades",
        "fetch_coinbase_transaction_summary",
        "create_coinbase_convert_quote",
        "commit_coinbase_convert_trade",
        "fetch_coinbase_convert_trade",
        "fetch_coinbase_portfolios",
        "create_coinbase_portfolio",
        "move_coinbase_portfolio_funds",
        "fetch_coinbase_portfolio_breakdown",
        "delete_coinbase_portfolio",
        "edit_coinbase_portfolio",
        "fetch_coinbase_futures_balance_summary",
        "fetch_coinbase_futures_positions",
        "fetch_coinbase_futures_position",
        "schedule_coinbase_futures_sweep",
        "fetch_coinbase_futures_sweeps",
        "cancel_coinbase_futures_sweep",
        "fetch_coinbase_intraday_margin_setting",
        "set_coinbase_intraday_margin_setting",
        "fetch_coinbase_current_margin_window",
        "fetch_coinbase_perpetuals_portfolio_summary",
        "fetch_coinbase_perpetuals_positions",
        "fetch_coinbase_perpetuals_position",
        "fetch_coinbase_perpetuals_balances",
        "opt_in_coinbase_multi_asset_collateral",
        "allocate_coinbase_portfolio",
        "fetch_coinbase_payment_methods",
        "fetch_coinbase_payment_method",
        "fetch_coinbase_key_permissions",
        "fetch_coinbase_server_time",
        "fetch_coinbase_public_product_book",
        "fetch_coinbase_public_products",
        "fetch_coinbase_public_product",
        "fetch_coinbase_public_product_candles",
        "fetch_coinbase_public_market_trades",
    ]

    missing = [name for name in expected_methods if not callable(getattr(broker, name, None))]
    assert missing == []


def test_coinbase_ccxt_broker_routes_advanced_trade_requests(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    api_session = FakeCoinbaseApiSession(
        responses={
            "GET https://api.coinbase.com/api/v3/brokerage/accounts": {"accounts": [{"uuid": "acct-1"}]},
            "POST https://api.coinbase.com/api/v3/brokerage/orders/preview": {"preview_id": "preview-1"},
            "GET https://api.coinbase.com/api/v3/brokerage/orders/historical/batch?product_id=BTC-USD&limit=25": {
                "orders": [{"order_id": "order-1"}]
            },
            "GET https://api.coinbase.com/api/v3/brokerage/key_permissions": {"permissions": ["view", "trade"]},
            "GET https://api.coinbase.com/api/v3/brokerage/market/products?limit=2": {"products": [{"product_id": "BTC-USD"}]},
            "GET https://api.coinbase.com/api/v3/brokerage/time": {"iso": "2026-04-07T08:15:53Z"},
        }
    )
    monkeypatch.setattr(
        broker_mod.aiohttp,
        "ClientSession",
        lambda connector=None, **kwargs: api_session,
    )
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        accounts = await broker.fetch_coinbase_accounts()
        preview = await broker.preview_coinbase_order({"product_id": "BTC-USD", "side": "BUY"})
        orders = await broker.fetch_coinbase_orders(params={"product_id": "BTC-USD", "limit": 25})
        permissions = await broker.fetch_coinbase_key_permissions()
        public_products = await broker.fetch_coinbase_public_products(params={"limit": 2})
        server_time = await broker.fetch_coinbase_server_time()

        assert accounts["accounts"][0]["uuid"] == "acct-1"
        assert preview["preview_id"] == "preview-1"
        assert orders["orders"][0]["order_id"] == "order-1"
        assert permissions["permissions"] == ["view", "trade"]
        assert public_products["products"][0]["product_id"] == "BTC-USD"
        assert server_time["iso"] == "2026-04-07T08:15:53Z"

        assert api_session.requested_methods == ["GET", "POST", "GET", "GET", "GET", "GET"]
        assert api_session.requested_urls == [
            "https://api.coinbase.com/api/v3/brokerage/accounts",
            "https://api.coinbase.com/api/v3/brokerage/orders/preview",
            "https://api.coinbase.com/api/v3/brokerage/orders/historical/batch?product_id=BTC-USD&limit=25",
            "https://api.coinbase.com/api/v3/brokerage/key_permissions",
            "https://api.coinbase.com/api/v3/brokerage/market/products?limit=2",
            "https://api.coinbase.com/api/v3/brokerage/time",
        ]
        assert api_session.requested_json[1] == {"product_id": "BTC-USD", "side": "BUY"}
        assert api_session.requested_headers[0]["Authorization"].startswith("Bearer ")
        assert api_session.requested_headers[1]["Authorization"].startswith("Bearer ")
        assert "Authorization" not in api_session.requested_headers[4]
        assert "Authorization" not in api_session.requested_headers[5]

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_skips_unsupported_symbols(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeStrictCoinbaseExchange, raising=False)

    async def scenario():
        broker = CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        assert broker.supports_symbol("BTC/USD") is True
        assert broker.supports_symbol("EUR/USD") is False
        assert await broker.fetch_ticker("EUR/USD") is None
        assert await broker.fetch_orderbook("EUR/USD") == {"bids": [], "asks": []}
        assert await broker.fetch_ohlcv("EUR/USD", timeframe="1h", limit=50) == []
        assert await broker.fetch_trades("EUR/USD", limit=20) == []

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_derivative_mode_uses_native_positions(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseDerivativeExchange, raising=False)

    async def scenario():
        broker = CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={"market_type": "derivative", "defaultSubType": "future"},
                params={},
            )
        )

        await broker.connect()
        positions = await broker.fetch_positions()

        assert broker.exchange.cfg["options"]["defaultType"] == "future"
        assert broker.symbols == ["BTC/USD:USD", "ETH/USD:USD"]
        assert broker.supported_market_venues() == ["auto", "spot", "derivative"]
        assert broker._supports_positions_endpoint() is True
        assert positions[0]["symbol"] == "BTC/USD:USD"
        assert broker.exchange.fetch_positions_calls == [None]

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_hydrates_futures_markets_from_coinbase_products(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseRawFuturesExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={"market_type": "derivative"},
                params={},
            )
        )

        await broker.connect()

        assert broker.exchange.cfg["options"]["defaultType"] == "future"
        assert sorted(broker.symbols) == ["ETH-USD-20241227", "SLP-20DEC30-CDE"]
        assert broker.supported_market_venues() == ["auto", "spot", "derivative"]
        assert broker._supports_positions_endpoint() is True
        assert broker.exchange.fetch_markets_calls == 1
        assert broker.exchange.markets["SLP-20DEC30-CDE"]["future"] is True
        assert broker.exchange.markets["SLP-20DEC30-CDE"]["contract"] is True
        assert broker.exchange.markets["SLP-20DEC30-CDE"]["underlying_symbol"] == "SLP/USD"
        assert broker.exchange.markets["SLP-20DEC30-CDE"]["native_symbol"] == "SLP-20DEC30-CDE"

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_fetches_futures_balance_and_positions_via_direct_cfm_api(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    api_session = FakeCoinbaseApiSession(
        responses={
            "https://api.coinbase.com/api/v3/brokerage/cfm/balance_summary": {
                "balance_summary": {
                    "total_usd_balance": "12500.50",
                    "cfm_usd_balance": "8200.25",
                    "available_margin": "3500.00",
                    "futures_buying_power": "4000.00",
                    "unrealized_pnl": "125.50",
                }
            },
            "https://api.coinbase.com/api/v3/brokerage/cfm/positions": {
                "positions": [
                    {
                        "product_id": "SLP-20DEC30-CDE",
                        "side": "LONG",
                        "number_of_contracts": "2",
                        "avg_entry_price": "62000.0",
                        "current_price": "63000.0",
                        "unrealized_pnl": "200.0",
                        "daily_realized_pnl": "50.0",
                        "expiration_time": "2024-12-27T17:00:00Z",
                    }
                ]
            },
        }
    )
    monkeypatch.setattr(
        broker_mod.aiohttp,
        "ClientSession",
        lambda connector=None, **kwargs: api_session,
    )
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseRawFuturesExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={"market_type": "derivative"},
                params={},
            )
        )

        await broker.connect()
        balance = await broker.fetch_balance()
        positions = await broker.fetch_positions()

        assert balance["equity"] == 12500.5
        assert balance["cash"] == 8200.25
        assert balance["free"]["USD"] == 3500.0
        assert positions[0]["symbol"] == "SLP-20DEC30-CDE"
        assert positions[0]["product_id"] == "SLP-20DEC30-CDE"
        assert positions[0]["contracts"] == 2.0
        assert positions[0]["side"] == "long"
        assert positions[0]["instrument"]["type"] == "future"
        assert api_session.requested_urls == [
            "https://api.coinbase.com/api/v3/brokerage/cfm/balance_summary",
            "https://api.coinbase.com/api/v3/brokerage/cfm/positions",
        ]
        assert api_session.requested_headers[0]["Authorization"].startswith("Bearer ")

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_fetches_perpetual_balance_and_positions_via_direct_intx_api(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    api_session = FakeCoinbaseApiSession(
        responses={
            "https://api.coinbase.com/api/v3/brokerage/intx/portfolio": {
                "summary": {
                    "buying_power": {"value": "4000.00", "currency": "USDC"},
                    "total_balance": {"value": "5250.50", "currency": "USDC"},
                    "unrealized_pnl": {"value": "125.50", "currency": "USDC"},
                },
                "portfolios": [
                    {
                        "collateral": "3000.00",
                        "portfolio_initial_margin": "750.00",
                        "portfolio_maintenance_margin": "500.00",
                        "liquidation_buffer": "0.25",
                        "total_balance": {"value": "5250.50", "currency": "USDC"},
                    }
                ],
            },
            "https://api.coinbase.com/api/v3/brokerage/intx/positions": {
                "positions": [
                    {
                        "product_id": "BTC-PERP",
                        "side": "LONG",
                        "number_of_contracts": "0.25",
                        "avg_entry_price": "64000.0",
                        "mark_price": "65000.0",
                        "unrealized_pnl": "250.0",
                    }
                ]
            },
        }
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: api_session)
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={"market_type": "derivative", "defaultSubType": "swap"},
                params={},
            )
        )

        await broker.connect()
        balance = await broker.fetch_balance()
        positions = await broker.fetch_positions()

        assert balance["currency"] == "USDC"
        assert balance["equity"] == 5250.5
        assert balance["cash"] == 3000.0
        assert balance["available_margin"] == 4000.0
        assert positions[0]["symbol"] == "BTC-PERP"
        assert positions[0]["product_id"] == "BTC-PERP"
        assert positions[0]["contracts"] == 0.25
        assert positions[0]["instrument_type"] == "perpetual"
        assert api_session.requested_urls == [
            "https://api.coinbase.com/api/v3/brokerage/intx/portfolio",
            "https://api.coinbase.com/api/v3/brokerage/intx/positions",
        ]

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_places_perpetual_orders_via_advanced_trade_api(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    api_session = FakeCoinbaseApiSession(
        responses={
            "https://api.coinbase.com/api/v3/brokerage/portfolios?portfolio_type=INTX": {
                "portfolios": [{"uuid": "intx-1", "type": "INTX", "deleted": False}]
            },
            "https://api.coinbase.com/api/v3/brokerage/products": {
                "products": [
                    {
                        "product_id": "BTC-PERP",
                        "product_type": "FUTURE",
                        "status": "ONLINE",
                        "price": "65000.0",
                        "future_product_details": {"contract_expiry_type": "PERPETUAL"},
                    }
                ]
            },
            "https://api.coinbase.com/api/v3/brokerage/intx/portfolio": {
                "summary": {
                    "buying_power": {"value": "5000.00", "currency": "USDC"},
                    "total_balance": {"value": "6500.00", "currency": "USDC"},
                },
                "portfolios": [{"collateral": "2500.00", "total_balance": {"value": "6500.00", "currency": "USDC"}}],
            },
            "POST https://api.coinbase.com/api/v3/brokerage/orders": {
                "success": True,
                "success_response": {
                    "order_id": "perp-1",
                    "product_id": "BTC-PERP",
                    "side": "BUY",
                    "client_order_id": "perp-client-1",
                },
            },
        }
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: api_session)
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={"market_type": "derivative", "defaultSubType": "swap"},
                params={},
            )
        )

        await broker.connect()
        broker.set_leverage("BTC", 3)
        order = await broker.place_order(
            symbol="BTC",
            side="buy",
            size=0.001,
            is_perpetual=True,
            client_order_id="perp-client-1",
        )

        assert order["id"] == "perp-1"
        assert order["product_id"] == "BTC-PERP"
        assert order["status"] == "open"
        assert order["leverage"] == 3.0
        assert api_session.requested_urls == [
            "https://api.coinbase.com/api/v3/brokerage/portfolios?portfolio_type=INTX",
            "https://api.coinbase.com/api/v3/brokerage/products",
            "https://api.coinbase.com/api/v3/brokerage/intx/portfolio",
            "https://api.coinbase.com/api/v3/brokerage/orders",
        ]
        assert api_session.requested_json[-1] == {
            "client_order_id": "perp-client-1",
            "product_id": "BTC-PERP",
            "side": "BUY",
            "order_configuration": {"market_market_ioc": {"base_size": "0.001"}},
        }

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_rejects_small_perpetual_orders_before_posting(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    api_session = FakeCoinbaseApiSession(
        responses={
            "https://api.coinbase.com/api/v3/brokerage/portfolios?portfolio_type=INTX": {
                "portfolios": [{"uuid": "intx-1", "type": "INTX", "deleted": False}]
            },
            "https://api.coinbase.com/api/v3/brokerage/products": {
                "products": [
                    {
                        "product_id": "BTC-PERP",
                        "product_type": "FUTURE",
                        "status": "ONLINE",
                        "price": "6500.0",
                        "future_product_details": {"contract_expiry_type": "PERPETUAL"},
                    }
                ]
            },
        }
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: api_session)
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={"market_type": "derivative", "defaultSubType": "swap"},
                params={},
            )
        )

        await broker.connect()
        order = await broker.place_order(symbol="BTC", side="buy", size=0.001, is_perpetual=True)

        assert order["status"] == "rejected"
        assert "10 USDC" in order["reason"]
        assert "https://api.coinbase.com/api/v3/brokerage/orders" not in api_session.requested_urls

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_derives_spot_positions_and_equity(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        balances = await broker.fetch_balance()
        positions = await broker.fetch_positions()

        assert balances["cash"] == 500.0
        assert balances["position_value"] == 16250.0
        assert balances["equity"] == 16750.0
        assert len(positions) == 1
        assert positions[0]["asset_code"] == "BTC"
        assert positions[0]["symbol"] == "BTC/USD"
        assert positions[0]["amount"] == 0.25
        assert positions[0]["value"] == 16250.0

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_caches_spot_account_snapshot_between_balance_and_positions(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        balances = await broker.fetch_balance()
        positions = await broker.fetch_positions()

        assert balances["equity"] == 16750.0
        assert positions[0]["symbol"] == "BTC/USD"
        assert broker.exchange.fetch_balance_calls == 1
        assert broker.exchange.fetch_ticker_calls == ["BTC/USD"]

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_caches_open_orders_snapshot(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        first = await broker.fetch_open_orders_snapshot(symbols=["BTC/USD"], limit=10)
        second = await broker.fetch_open_orders_snapshot(symbols=["BTC/USD"], limit=10)

        assert first == second
        assert broker.exchange.fetch_open_orders_calls == [{"symbol": None, "limit": 10}]

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_values_cash_and_assets_through_cross_pairs(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseCrossValuationExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()

        balances = await broker.fetch_balance()
        positions = await broker.fetch_positions()

        assert round(balances["cash"], 2) == 1300.0
        assert round(balances["position_value"], 2) == 260.0
        assert round(balances["equity"], 2) == 1560.0
        assert balances["asset_balances"]["EUR"] == 1000.0
        assert balances["asset_balances"]["AAVE"] == 2.0
        assert len(positions) == 1
        assert positions[0]["asset_code"] == "AAVE"
        assert positions[0]["symbol"] == "AAVE/EUR"
        assert round(positions[0]["value"], 2) == 260.0

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_normalizes_private_key_newlines(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        config = SimpleNamespace(
            exchange="coinbase",
            api_key="organizations/test/apiKeys/key-1",
            secret="-----BEGIN EC PRIVATE KEY-----\\nline-1\\nline-2\\n-----END EC PRIVATE KEY-----\\n",
            password=None,
            uid=None,
            mode="live",
            sandbox=False,
            timeout=15000,
            options={},
            params={},
        )
        broker = CCXTBroker(config)

        await broker.connect()

        assert broker.secret == "-----BEGIN EC PRIVATE KEY-----\nline-1\nline-2\n-----END EC PRIVATE KEY-----\n"
        assert broker.exchange.cfg["secret"] == broker.secret

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_normalizes_single_line_pem_from_ui(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        config = SimpleNamespace(
            exchange="coinbase",
            api_key='"organizations/test/apiKeys/key-1"',
            secret='"-----BEGIN EC PRIVATE KEY----- line-1 line-2 -----END EC PRIVATE KEY-----"',
            password=None,
            uid=None,
            mode="live",
            sandbox=False,
            timeout=15000,
            options={},
            params={},
        )
        broker = CCXTBroker(config)

        await broker.connect()

        assert broker.api_key == "organizations/test/apiKeys/key-1"
        assert broker.secret == "-----BEGIN EC PRIVATE KEY-----\nline-1line-2\n-----END EC PRIVATE KEY-----\n"
        assert broker.exchange.cfg["secret"] == broker.secret

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_accepts_uuid_id_and_json_private_key_bundle(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(broker_mod.aiohttp, "ClientSession", lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs))
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseExchange, raising=False)

    async def scenario():
        config = SimpleNamespace(
            exchange="coinbase",
            api_key="",
            secret='{"id":"2ffe3f58-d600-47a8-a147-1c55854eddc8","privateKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}',
            password=None,
            uid=None,
            mode="live",
            sandbox=False,
            timeout=15000,
            options={},
            params={},
        )
        broker = CCXTBroker(config)

        await broker.connect()

        assert broker.api_key == "2ffe3f58-d600-47a8-a147-1c55854eddc8"
        assert broker.secret == "-----BEGIN EC PRIVATE KEY-----\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n-----END EC PRIVATE KEY-----\n"
        assert broker.exchange.cfg["secret"] == broker.secret

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_ccxt_broker_signs_private_requests_with_bearer_jwt():
    import broker.ccxt_broker as broker_mod

    broker = broker_mod.CCXTBroker(
        SimpleNamespace(
            exchange="coinbase",
            api_key="organizations/test/apiKeys/key-1",
            secret=(
                "-----BEGIN EC PRIVATE KEY-----\n"
                "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                "-----END EC PRIVATE KEY-----\n"
            ),
            password=None,
            uid=None,
            mode="live",
            sandbox=False,
            timeout=15000,
            options={},
            params={},
        )
    )
    broker._normalize_credentials()
    exchange_class = broker._exchange_class()
    exchange = exchange_class({"apiKey": broker.api_key, "secret": broker.secret, "options": {}})

    signed = exchange.sign("brokerage/accounts", api=["v3", "private"], method="GET", params={})

    assert "Authorization" in signed["headers"]
    assert "CB-ACCESS-KEY" not in signed["headers"]
    token = signed["headers"]["Authorization"].split(" ", 1)[1]
    headers = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})

    assert headers["kid"] == "organizations/test/apiKeys/key-1"
    assert payload["sub"] == "organizations/test/apiKeys/key-1"
    assert payload["iss"] == "coinbase-cloud"
    assert payload["uri"] == "GET api.coinbase.com/api/v3/brokerage/accounts"


def test_coinbase_jwt_builder_reports_missing_pyjwt(monkeypatch):
    import broker.coinbase_jwt_auth as auth_mod

    monkeypatch.setattr(auth_mod, "_JWT_MODULE", None)
    monkeypatch.setattr(auth_mod, "_JWT_IMPORT_ERROR", ModuleNotFoundError("No module named 'jwt'"))

    with pytest.raises(BrokerOperationError) as exc:
        auth_mod.build_coinbase_rest_jwt(
            request_method="GET",
            request_host="api.coinbase.com",
            request_path="/api/v3/brokerage/accounts",
            api_key="organizations/test/apiKeys/key-1",
            api_secret=(
                "-----BEGIN EC PRIVATE KEY-----\n"
                "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                "-----END EC PRIVATE KEY-----\n"
            ),
        )

    assert "PyJWT" in str(exc.value)


def test_coinbase_ccxt_broker_backfills_requested_ohlcv_limit(monkeypatch):
    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(
        broker_mod.aiohttp,
        "TCPConnector",
        lambda family=None, resolver=None, ttl_dns_cache=None: {
            "family": family,
            "resolver": resolver,
            "ttl_dns_cache": ttl_dns_cache,
        },
    )
    monkeypatch.setattr(broker_mod.aiohttp, "ThreadedResolver", lambda: "threaded-resolver")
    monkeypatch.setattr(
        broker_mod.aiohttp,
        "ClientSession",
        lambda connector=None, **kwargs: FakeSession(connector=connector, **kwargs),
    )
    monkeypatch.setattr(broker_mod.ccxt, "coinbase", FakeCoinbaseHistoryExchange, raising=False)

    async def scenario():
        broker = broker_mod.CCXTBroker(
            SimpleNamespace(
                exchange="coinbase",
                api_key="organizations/test/apiKeys/key-1",
                secret=(
                    "-----BEGIN EC PRIVATE KEY-----\n"
                    "MHcCAQEEIAqSV4qAfY1Nm0xd6k95EZ39suUWAuze5Vuhn671kB9OoAoGCCqGSM49\n"
                    "AwEHoUQDQgAEcgYO1ly0wyz23wipRFpoM6Oyvh6WB1wy9EB8PHhrNw5VSJsAqsb7\n"
                    "gc1E+mZ1HVX3H8eKNlw8GrQCQJsZ5ExllA==\n"
                    "-----END EC PRIVATE KEY-----\n"
                ),
                password=None,
                uid=None,
                mode="live",
                sandbox=False,
                timeout=15000,
                options={},
                params={},
            )
        )

        await broker.connect()
        candles_240 = await broker.fetch_ohlcv("BTC/USD", timeframe="1h", limit=240)
        candles_500 = await broker.fetch_ohlcv("BTC/USD", timeframe="1h", limit=500)
        cached_240 = await broker.fetch_ohlcv("BTC/USD", timeframe="1h", limit=240)

        assert len(candles_240) == 240
        assert len(candles_500) == 500
        assert len(cached_240) == 240
        assert all(call["since"] is not None for call in broker.exchange.fetch_ohlcv_calls)
        assert any(int(call["limit"]) == 300 for call in broker.exchange.fetch_ohlcv_calls)
        assert len([call for call in broker.exchange.fetch_ohlcv_calls if int(call["limit"]) == 240]) == 1

        await broker.close()

    asyncio.run(scenario())


def test_coinbase_websocket_uses_advanced_trade_ticker_messages(monkeypatch):
    import market_data.websocket.coinbase_web_socket as ws_mod

    payload = json.dumps(
        {
            "channel": "ticker",
            "timestamp": "2026-03-10T10:00:00Z",
            "events": [
                {
                    "type": "snapshot",
                    "tickers": [
                        {
                            "product_id": "SLP-20DEC30-CDE",
                            "price": "65000.10",
                            "best_bid": "64999.50",
                            "best_ask": "65000.50",
                            "volume_24_h": "120.5",
                        }
                    ],
                }
            ],
        }
    )
    socket = FakeSocket([payload])
    monkeypatch.setattr(ws_mod.websockets, "connect", lambda url: socket)

    async def scenario():
        bus = EventBus()
        client = CoinbaseWebSocket(symbols=["SLP-20DEC30-CDE"], event_bus=bus)

        try:
            await client.connect()
        except asyncio.CancelledError:
            pass

        event = await bus.queue.get()
        assert json.loads(socket.sent) == {
            "type": "subscribe",
            "channel": "ticker",
            "product_ids": ["SLP-20DEC30-CDE"],
        }
        assert event.data["symbol"] == "SLP-20DEC30-CDE"
        assert event.data["bid"] == 64999.5
        assert event.data["ask"] == 65000.5

    asyncio.run(scenario())
