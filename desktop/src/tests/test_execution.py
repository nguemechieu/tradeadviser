import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.broker_errors import BrokerOperationError
from event_bus.event_bus import EventBus
from event_bus.event_types import EventType
from execution.execution_manager import ExecutionManager
from execution.order_router import OrderRouter
from execution.smart_execution import SmartExecution


class MockBroker:
    def __init__(self, balance=None, markets=None):
        self.orders = []
        self._balance = balance if balance is not None else {}

        exchange = type("Exchange", (), {})()
        exchange.markets = markets or {}
        exchange.amount_to_precision = lambda symbol, amount: amount
        self.exchange = exchange

    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        order_id = f"order-{len(self.orders) + 1}"
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": type,
            "price": price,
            "stop_price": stop_price,
            "status": "filled",
            "params": params or {},
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        self.orders.append(order)
        return order

    async def fetch_balance(self):
        return self._balance

    async def fetch_ticker(self, symbol):
        return {"symbol": symbol, "price": 100.0, "bid": 100.0, "ask": 100.0}


class RateLimitedBroker(MockBroker):
    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        raise RuntimeError("429 Too Many Requests")


class RejectedOrderBroker(MockBroker):
    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        raise RuntimeError("400 Bad Request: Order rejected | INSUFFICIENT_MARGIN")


class StructuredRateLimitedBroker(MockBroker):
    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        raise BrokerOperationError(
            "BINANCEUS rate limit hit while create order: 429 Too Many Requests",
            category="rate_limit",
            retryable=True,
            cooldown_seconds=300,
        )


class StructuredRejectedBroker(MockBroker):
    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        raise BrokerOperationError(
            "BINANCEUS rejected the order request: minimum notional not met",
            category="invalid_order",
            rejection=True,
            cooldown_seconds=180,
        )


class TrackingBroker(MockBroker):
    def __init__(self, balance=None, markets=None):
        super().__init__(balance=balance, markets=markets)
        self.fetch_order_calls = 0

    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        order = {
            "id": "tracked-1",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": type,
            "price": price,
            "stop_price": stop_price,
            "status": "submitted",
            "filled": 0.0,
            "params": params or {},
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        self.orders.append(order)
        return order

    async def fetch_order(self, order_id, symbol=None):
        self.fetch_order_calls += 1
        status = "open" if self.fetch_order_calls == 1 else "filled"
        filled = 0.0 if status == "open" else 0.5
        return {
            "id": order_id,
            "symbol": symbol or "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "amount": 0.5,
            "filled": filled,
            "price": 101.0,
            "status": status,
        }


class BlockingBehaviorGuard:
    def __init__(self):
        self.recorded_attempts = []
        self.trade_updates = []

    def evaluate_order(self, order):
        return False, "Behavior guard blocked trade: too many orders in the last hour (24/24)", {"state": "COOLDOWN"}

    def record_order_attempt(self, order, allowed=True, reason=""):
        self.recorded_attempts.append((dict(order), allowed, reason))

    def record_trade_update(self, trade):
        self.trade_updates.append(dict(trade))


def test_execute_accepts_keyword_order_arguments():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.01, price=42000)
    )

    assert order["symbol"] == "BTC/USDT"
    assert order["side"] == "buy"
    assert order["amount"] == 0.01
    assert order["source"] == "bot"

    fill_event = asyncio.run(bus.queue.get())
    assert fill_event.type == EventType.FILL
    assert fill_event.data["symbol"] == "BTC/USDT"
    assert fill_event.data["side"] == "BUY"
    assert fill_event.data["qty"] == 0.01


def test_execute_accepts_legacy_signal_payload():
    broker = MockBroker(balance={"free": {"ETH": 5}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(manager.execute({"symbol": "ETH/USDT", "signal": "SELL", "size": 2}))

    assert order["symbol"] == "ETH/USDT"
    assert order["side"] == "sell"
    assert order["amount"] == 2


def test_execute_scales_buy_order_to_available_quote_balance():
    broker = MockBroker(
        balance={"free": {"USDT": 250}},
        markets={"BTC/USDT": {"active": True, "limits": {"cost": {"min": 10}}}},
    )
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=5, price=100)
    )

    assert order["amount"] == 2.45


def test_execute_skips_buy_order_when_safe_amount_is_below_market_minimum():
    broker = MockBroker(
        balance={"free": {"USDT": 5}},
        markets={"BTC/USDT": {"active": True, "limits": {"cost": {"min": 10}}}},
    )
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=1, price=100)
    )

    assert order is None
    assert broker.orders == []
    assert "below the venue minimum" in manager.last_skip_reason("BTC/USDT")


def test_execute_does_not_inflate_requested_order_to_exchange_minimum():
    broker = MockBroker(
        balance={"free": {"USDT": 100}},
        markets={"BTC/USDT": {"active": True, "limits": {"cost": {"min": 10}}}},
    )
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.05, price=100)
    )

    assert order is None
    assert broker.orders == []
    assert "below the venue minimum" in manager.last_skip_reason("BTC/USDT")


def test_execute_skips_inventory_balance_checks_for_oanda_fx_orders():
    broker = MockBroker(
        balance={"free": {"USD": 5000.0}, "currency": "USD"},
        markets={"AUD/CAD": {"active": True, "otc": True}},
    )
    broker.exchange_name = "oanda"
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="AUD/CAD", side="buy", amount=1000, price=0.9050, exchange="oanda")
    )

    assert order["symbol"] == "AUD/CAD"
    assert order["amount"] == 1000
    assert broker.orders[0]["symbol"] == "AUD/CAD"


def test_execute_skips_inactive_market():
    broker = MockBroker(
        balance={"free": {"USDT": 1000}},
        markets={"MKR/USDT": {"active": False}},
    )
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="MKR/USDT", side="buy", amount=1, price=100)
    )

    assert order is None
    assert broker.orders == []


def test_execute_cools_down_on_rate_limit():
    broker = RateLimitedBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.01, price=100)
    )

    assert order is None
    assert manager._cooldown_remaining("BTC/USDT") > 0


def test_execute_returns_rejected_order_for_insufficient_margin():
    broker = RejectedOrderBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    notifications = []
    manager = ExecutionManager(broker, bus, OrderRouter(broker), trade_notifier=notifications.append)

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.01, price=100)
    )

    assert order["status"] == "rejected"
    assert order["source"] == "bot"
    assert notifications[-1]["status"] == "rejected"
    assert notifications[-1]["source"] == "bot"
    assert manager._cooldown_remaining("BTC/USDT") > 0
    assert bus.queue.empty()


def test_execute_uses_structured_broker_rate_limit_metadata():
    broker = StructuredRateLimitedBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.01, price=100)
    )

    assert order is None
    assert manager._cooldown_remaining("BTC/USDT") > 0
    assert "rate limit hit" in (manager.last_skip_reason("BTC/USDT") or "").lower()


def test_execute_uses_structured_broker_rejection_metadata():
    broker = StructuredRejectedBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    notifications = []
    manager = ExecutionManager(broker, bus, OrderRouter(broker), trade_notifier=notifications.append)

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.01, price=100)
    )

    assert order["status"] == "rejected"
    assert order["error_category"] == "invalid_order"
    assert notifications[-1]["error_category"] == "invalid_order"
    assert manager._cooldown_remaining("BTC/USDT") > 0
    assert bus.queue.empty()


def test_execute_propagates_stop_loss_and_take_profit():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
            price=42000,
            stop_loss=41000,
            take_profit=45000,
        )
    )

    assert order["stop_loss"] == 41000
    assert order["take_profit"] == 45000
    assert broker.orders[0]["stop_loss"] == 41000
    assert broker.orders[0]["take_profit"] == 45000


def test_execute_propagates_stop_limit_trigger_and_type():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))

    order = asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
            type="stop_limit",
            price=42000,
            stop_price=42100,
        )
    )

    assert order["type"] == "stop_limit"
    assert order["stop_price"] == 42100
    assert broker.orders[0]["type"] == "stop_limit"
    assert broker.orders[0]["stop_price"] == 42100


def test_execute_notifier_receives_trade_log_fields():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    received = {}

    def notifier(trade):
        received.update(trade)

    manager = ExecutionManager(broker, bus, OrderRouter(broker), trade_notifier=notifier)

    asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
            price=42000,
            stop_loss=41000,
            take_profit=45000,
        )
    )

    assert received["symbol"] == "BTC/USDT"
    assert received["side"] == "BUY"
    assert received["source"] == "bot"
    assert received["order_type"] == "market"
    assert received["status"] == "filled"
    assert received["order_id"] == "order-1"
    assert received["stop_loss"] == 41000
    assert received["take_profit"] == 45000
    assert received["timestamp"]


def test_execute_allows_manual_trade_source():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    received = {}

    def notifier(trade):
        received.update(trade)

    manager = ExecutionManager(broker, bus, OrderRouter(broker), trade_notifier=notifier)

    order = asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
            price=42000,
            source="manual",
        )
    )

    assert order["source"] == "manual"
    assert received["source"] == "manual"


async def _fast_sleep(_seconds):
    return None


def test_smart_execution_twap_aggregates_child_orders():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    executor = SmartExecution(broker, sleep_fn=_fast_sleep)

    result = asyncio.run(
        executor.execute(
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 4,
                "type": "market",
                "price": 100,
                "expected_price": 100,
                "params": {"execution_strategy": "twap", "twap_slices": 4, "twap_duration_seconds": 0},
            }
        )
    )

    assert result["execution_strategy"] == "twap"
    assert result["child_count"] == 4
    assert len(result["children"]) == 4
    assert result["filled"] == 4
    assert result["execution_quality"]["algorithm"] == "twap"


def test_execute_supports_twap_strategy_and_preserves_execution_quality():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))
    manager.router.smart_execution._sleep = _fast_sleep

    order = asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.04,
            price=100,
            execution_strategy="twap",
            params={"twap_slices": 2, "twap_duration_seconds": 0},
        )
    )

    assert order["execution_strategy"] == "twap"
    assert order["child_count"] == 2
    assert order["execution_quality"]["algorithm"] == "twap"

    fill_event = asyncio.run(bus.queue.get())
    assert fill_event.type == EventType.FILL
    assert fill_event.data["qty"] == 0.04


def test_execute_supports_iceberg_strategy():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    manager = ExecutionManager(broker, bus, OrderRouter(broker))
    manager.router.smart_execution._sleep = _fast_sleep

    order = asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.05,
            price=100,
            type="limit",
            execution_strategy="iceberg",
            params={"visible_size": 0.02, "iceberg_pause_seconds": 0},
        )
    )

    assert order["execution_strategy"] == "iceberg"
    assert order["child_count"] == 3
    assert len(broker.orders) == 3


def test_execute_tracks_submitted_order_until_filled():
    async def scenario():
        broker = TrackingBroker(balance={"free": {"USDT": 1000}})
        bus = EventBus()
        notifications = []
        manager = ExecutionManager(broker, bus, OrderRouter(broker), trade_notifier=notifications.append)
        manager._order_tracking_interval = 0.01
        manager._order_tracking_timeout = 0.25

        order = await manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.5,
            type="limit",
            price=100.0,
        )

        assert order["status"] == "submitted"

        await asyncio.sleep(0.05)

        fill_event = await asyncio.wait_for(bus.queue.get(), timeout=0.2)
        assert fill_event.type == EventType.FILL
        assert fill_event.data["qty"] == 0.5

        statuses = [update["status"] for update in notifications]
        assert "submitted" in statuses
        assert "filled" in statuses
        assert all(update["source"] == "bot" for update in notifications)

        await manager.stop()

    asyncio.run(scenario())


def test_execute_returns_guard_rejection_without_hitting_broker():
    broker = MockBroker(balance={"free": {"USDT": 1000}})
    bus = EventBus()
    notifications = []
    behavior_guard = BlockingBehaviorGuard()
    manager = ExecutionManager(
        broker,
        bus,
        OrderRouter(broker),
        trade_notifier=notifications.append,
        behavior_guard=behavior_guard,
    )

    order = asyncio.run(
        manager.execute(symbol="BTC/USDT", side="buy", amount=0.25, price=100, source="manual")
    )

    assert order["status"] == "rejected"
    assert order["blocked_by_guard"] is True
    assert "Behavior guard blocked trade" in order["reason"]
    assert broker.orders == []
    assert notifications[-1]["blocked_by_guard"] is True
    assert notifications[-1]["source"] == "manual"
    assert behavior_guard.recorded_attempts[-1][1] is False
    assert behavior_guard.trade_updates[-1]["status"] == "rejected"
