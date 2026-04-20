import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.broker_errors import BrokerOperationError
from broker.ccxt_broker import CCXTBroker


class FakeSession:
    def __init__(self, connector=None, **kwargs):
        self.connector = connector
        self.closed = False

    async def close(self):
        self.closed = True


class FakeExchange:
    def __init__(self, cfg):
        self.cfg = cfg
        self.closed = False
        self.sandbox_mode = None
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
            "fetchClosedOrders": False,
            "fetchOrder": True,
            "fetchBalance": True,
            "fetchPositions": True,
            "cancelOrder": True,
            "cancelAllOrders": True,
            "createOrder": True,
            "withdraw": True,
            "fetchDepositAddress": True,
        }
        self.markets = {}
        self.currencies = {"USDT": {"code": "USDT"}}
        self.fetch_positions_calls = []

    def set_sandbox_mode(self, enabled):
        self.sandbox_mode = enabled

    async def load_time_difference(self):
        return 123

    async def load_markets(self):
        self.markets = {
            "BTC/USDT": {"symbol": "BTC/USDT", "active": True},
            "ETH/USDT": {"symbol": "ETH/USDT", "active": True},
        }
        return self.markets

    async def fetch_ticker(self, symbol):
        return {"symbol": symbol, "last": 101.5}

    async def fetch_tickers(self, symbols=None):
        return {symbol: {"symbol": symbol, "last": index + 1} for index, symbol in enumerate(symbols or [])}

    async def fetch_order_book(self, symbol, limit=100):
        return {"symbol": symbol, "limit": limit, "bids": [[100, 1]], "asks": [[101, 2]]}

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        return [[1, 2, 3, 4, 5, 6] for _ in range(limit)]

    async def fetch_trades(self, symbol, limit=None):
        return [{"symbol": symbol, "limit": limit}]

    async def fetch_my_trades(self, symbol=None, limit=None):
        return [{"symbol": symbol, "limit": limit, "private": True}]

    async def fetch_status(self):
        return {"status": "ok"}

    async def create_order(self, symbol, order_type, side, amount, price, params):
        return {
            "id": "ord-1",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
            "params": params,
        }

    async def cancel_order(self, order_id, symbol=None):
        return {"id": order_id, "symbol": symbol, "status": "canceled"}

    async def cancel_all_orders(self, symbol=None):
        return [{"symbol": symbol, "status": "canceled"}]

    async def fetch_balance(self):
        return {"free": {"USDT": 1000}}

    async def fetch_positions(self, symbols=None):
        self.fetch_positions_calls.append(symbols)
        return [{"symbol": "BTC/USDT", "contracts": 0.25, "side": "long"}]

    async def fetch_order(self, order_id, symbol=None):
        return {"id": order_id, "symbol": symbol}

    async def fetch_orders(self, symbol=None, limit=None):
        return [{"symbol": symbol, "limit": limit}]

    async def fetch_open_orders(self, symbol=None, limit=None):
        self.fetch_open_orders_calls.append({"symbol": symbol, "limit": limit})
        return [{"symbol": symbol, "limit": limit, "status": "open"}]

    async def withdraw(self, code, amount, address, tag=None, params=None):
        return {"code": code, "amount": amount, "address": address, "tag": tag, "params": params or {}}

    async def fetch_deposit_address(self, code, params=None):
        return {"code": code, "address": "abc", "params": params or {}}

    def amount_to_precision(self, symbol, amount):
        return f"{amount:.4f}"

    def price_to_precision(self, symbol, price):
        return f"{price:.2f}"

    async def close(self):
        self.closed = True


class UnsupportedPrivateExchange(FakeExchange):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.has["fetchClosedOrders"] = False
        self.has["fetchDepositAddress"] = False


class RangeHistoryExchange(FakeExchange):
    async def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=100, params=None):
        base = int(since or 1710000000000)
        step_ms = 3600000 if timeframe == "1h" else 60000
        rows = []
        for index in range(int(limit or 100)):
            timestamp = base + (index * step_ms)
            rows.append([timestamp, 100 + index, 101 + index, 99 + index, 100.5 + index, 10 + index])
        return rows


class InsufficientFundsExchange(FakeExchange):
    async def create_order(self, symbol, order_type, side, amount, price, params):
        raise RuntimeError("400 Bad Request: INSUFFICIENT_FUNDS")


class RateLimitedExchange(FakeExchange):
    async def fetch_balance(self):
        raise RuntimeError("429 Too Many Requests")


@pytest.fixture
def broker_module(monkeypatch):
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
    monkeypatch.setattr(broker_mod.ccxt, "fakeexchange", FakeExchange, raising=False)
    monkeypatch.setattr(broker_mod.ccxt, "binanceus", FakeExchange, raising=False)
    monkeypatch.setattr(broker_mod.ccxt, "unsupportedexchange", UnsupportedPrivateExchange, raising=False)
    monkeypatch.setattr(broker_mod.ccxt, "rangehistoryexchange", RangeHistoryExchange, raising=False)
    monkeypatch.setattr(broker_mod.ccxt, "insufficientfundsexchange", InsufficientFundsExchange, raising=False)
    monkeypatch.setattr(broker_mod.ccxt, "ratelimitedexchange", RateLimitedExchange, raising=False)
    return broker_mod


def make_config(**overrides):
    base = {
        "exchange": "fakeexchange",
        "api_key": "key",
        "secret": "secret",
        "password": "passphrase",
        "uid": "uid-1",
        "mode": "paper",
        "sandbox": False,
        "timeout": 15000,
        "options": {"recvWindow": 9999},
        "params": {"clientOrderId": "abc-123"},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_ccxt_broker_connects_and_loads_symbols(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config())

        await broker.connect()

        assert broker._connected is True
        assert broker.symbols == ["BTC/USDT", "ETH/USDT"]
        assert broker.exchange.sandbox_mode is True
        assert broker.exchange.cfg["password"] == "passphrase"
        assert broker.exchange.cfg["uid"] == "uid-1"
        assert broker.exchange.cfg["options"]["recvWindow"] == 9999
        assert broker.session.connector["family"] is not None
        assert broker.session.connector["resolver"] == "threaded-resolver"

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_exposes_common_market_and_account_methods(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config())

        assert await broker.fetch_symbols() == ["BTC/USDT", "ETH/USDT"]
        assert (await broker.fetch_ticker("BTC/USDT"))["symbol"] == "BTC/USDT"
        assert "BTC/USDT" in await broker.fetch_tickers(["BTC/USDT"])
        assert (await broker.fetch_orderbook("BTC/USDT"))["bids"]
        assert len(await broker.fetch_ohlcv("BTC/USDT", limit=3)) == 3
        assert (await broker.fetch_balance())["free"]["USDT"] == 1000
        assert (await broker.fetch_status())["status"] == "ok"
        assert (await broker.fetch_orders("BTC/USDT", limit=10))[0]["limit"] == 10
        assert (await broker.fetch_open_orders("BTC/USDT", limit=5))[0]["status"] == "open"
        assert await broker.fetch_closed_orders("BTC/USDT", limit=5) == []

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_normalizes_order_precision_and_params(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config())

        order = await broker.create_order(
            symbol="BTC/USDT",
            side="BUY",
            amount=1.234567,
            type="limit",
            price=101.987,
            params={"timeInForce": "GTC"},
        )

        assert order["side"] == "buy"
        assert order["amount"] == 1.2346
        assert order["price"] == 101.99
        assert order["params"]["clientOrderId"] == "abc-123"
        assert order["params"]["timeInForce"] == "GTC"

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_returns_safe_defaults_for_unsupported_optional_methods(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="unsupportedexchange"))

        assert await broker.fetch_closed_orders("BTC/USDT") == []

        with pytest.raises(NotImplementedError):
            await broker.fetch_deposit_address("USDT")

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_supports_stop_limit_orders(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config())

        order = await broker.create_order(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            type="stop_limit",
            price=101.987,
            stop_price=102.5,
            params={"timeInForce": "GTC"},
        )

        assert order["type"] == "stop_limit"
        assert order["price"] == 101.99
        assert order["stop_price"] == 102.5
        assert order["params"]["stopPrice"] == 102.5

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_does_not_forward_attached_sl_tp_prices_by_default(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config())

        order = await broker.create_order(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            type="limit",
            price=101.987,
            stop_loss=99.5,
            take_profit=110.0,
        )

        assert "stopLossPrice" not in order["params"]
        assert "takeProfitPrice" not in order["params"]

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_fetches_date_range_history_for_backtests(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="rangehistoryexchange"))

        candles = await broker.fetch_ohlcv(
            "BTC/USDT",
            timeframe="1h",
            limit=6,
            start_time="2026-03-10T00:00:00+00:00",
            end_time="2026-03-10T05:00:00+00:00",
        )

        assert len(candles) == 6
        assert candles[0][0] == 1773100800000
        assert candles[-1][0] == 1773118800000

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_filters_symbols_for_selected_market_type(broker_module, monkeypatch):
    class MixedMarketExchange(FakeExchange):
        async def load_markets(self):
            self.markets = {
                "BTC/USDT": {"symbol": "BTC/USDT", "spot": True, "option": False},
                "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "spot": False, "contract": True, "swap": True},
                "BTC-29MAR24-50000-C": {"symbol": "BTC-29MAR24-50000-C", "spot": False, "option": True},
                "USDT_OTC": {"symbol": "USDT_OTC", "spot": False, "otc": True, "type": "otc"},
            }
            return self.markets

    import broker.ccxt_broker as broker_mod

    monkeypatch.setattr(broker_mod.ccxt, "mixedmarketexchange", MixedMarketExchange, raising=False)

    async def scenario():
        broker = CCXTBroker(make_config(exchange="mixedmarketexchange", options={"market_type": "option"}))
        await broker.connect()

        assert broker.symbols == ["BTC-29MAR24-50000-C"]
        assert broker.resolved_market_preference == "option"
        assert broker.supported_market_venues() == ["auto", "spot", "derivative", "option", "otc"]

        derivative_symbols = broker.apply_market_preference("derivative")
        assert derivative_symbols == ["BTC/USDT:USDT"]
        assert broker.resolved_market_preference == "derivative"

        otc_symbols = broker.apply_market_preference("otc")
        assert otc_symbols == ["USDT_OTC"]
        assert broker.resolved_market_preference == "otc"

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_binanceus_uses_symbol_aware_open_orders_defaults(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="binanceus", symbol="BTC/USDT"))
        await broker.connect()

        orders = await broker.fetch_open_orders(limit=25)

        assert broker.exchange.cfg["options"]["warnOnFetchOpenOrdersWithoutSymbol"] is False
        assert orders[0]["symbol"] == "BTC/USDT"
        assert orders[0]["limit"] == 25

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_binanceus_monitors_all_symbols_with_cached_snapshot(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="binanceus"))
        await broker.connect()

        first = await broker.fetch_open_orders_snapshot(symbols=["BTC/USDT", "ETH/USDT"], limit=10)
        second = await broker.fetch_open_orders_snapshot(symbols=["BTC/USDT", "ETH/USDT"], limit=10)

        assert [item["symbol"] for item in first] == ["BTC/USDT", "ETH/USDT"]
        assert first == second
        assert broker.exchange.fetch_open_orders_calls == [
            {"symbol": "BTC/USDT", "limit": 10},
            {"symbol": "ETH/USDT", "limit": 10},
        ]

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_binanceus_forces_spot_and_blocks_positions(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="binanceus", options={"defaultType": "future", "recvWindow": 9999}))
        await broker.connect()

        positions = await broker.fetch_positions()

        assert broker.exchange.cfg["options"]["defaultType"] == "spot"
        assert broker._exchange_has("fetch_positions") is False
        assert positions == []
        assert broker.exchange.fetch_positions_calls == []

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_normalizes_credentials_before_connect(broker_module):
    async def scenario():
        broker = CCXTBroker(
            make_config(
                exchange="binanceus",
                api_key="  demo-key  ",
                secret="  demo-secret  ",
                password="  demo-pass  ",
                uid="  uid-1  ",
            )
        )

        await broker.connect()

        assert broker.api_key == "demo-key"
        assert broker.secret == "demo-secret"
        assert broker.password == "demo-pass"
        assert broker.uid == "uid-1"
        assert broker.exchange.cfg["apiKey"] == "demo-key"
        assert broker.exchange.cfg["secret"] == "demo-secret"

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_rejects_binance_credentials_with_whitespace(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="binanceus", api_key="demo key", secret="secret"))

        with pytest.raises(ValueError) as exc:
            await broker.connect()

        assert "contains whitespace" in str(exc.value)

    asyncio.run(scenario())


def test_ccxt_broker_translates_order_rejections_into_structured_errors(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="insufficientfundsexchange"))

        with pytest.raises(BrokerOperationError) as exc:
            await broker.create_order("BTC/USDT", "buy", 1.0, type="market")

        assert exc.value.category == "insufficient_funds"
        assert exc.value.rejection is True
        assert "funds are insufficient" in str(exc.value).lower()

        await broker.close()

    asyncio.run(scenario())


def test_ccxt_broker_translates_rate_limits_into_retryable_errors(broker_module):
    async def scenario():
        broker = CCXTBroker(make_config(exchange="ratelimitedexchange"))

        with pytest.raises(BrokerOperationError) as exc:
            await broker.fetch_balance()

        assert exc.value.category == "rate_limit"
        assert exc.value.retryable is True
        assert exc.value.cooldown_seconds == 300.0

        await broker.close()

    asyncio.run(scenario())
