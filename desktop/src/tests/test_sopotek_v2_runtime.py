import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import Candle, Signal
from sopotek.core.orchestrator import SopotekRuntime
from sopotek.engines.strategy import BaseStrategy


class DummyBroker:
    def __init__(self):
        self.orders = []

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        return []

    async def place_order(self, order):
        self.orders.append(order)
        return {
            "id": f"order-{len(self.orders)}",
            "status": "filled",
            "price": order.price,
            "fill_price": order.price,
        }

    async def stream_ticks(self, symbol: str):
        if False:
            yield {"symbol": symbol, "price": 0.0}


class TrendStrategy(BaseStrategy):
    name = "trend"

    async def generate_signal(self, *, symbol: str, trigger: str, payload):
        if trigger != EventType.MARKET_TICK:
            return None
        price = float(payload["price"])
        return Signal(
            symbol=symbol,
            side="buy",
            quantity=10.0,
            price=price,
            confidence=0.82,
            strategy_name=self.name,
            reason="trend continuation",
        )


class DefensiveStrategy(BaseStrategy):
    name = "defensive"

    async def generate_signal(self, *, symbol: str, trigger: str, payload):
        if trigger != EventType.MARKET_TICK:
            return None
        price = float(payload["price"])
        return Signal(
            symbol=symbol,
            side="sell",
            quantity=10.0,
            price=price,
            confidence=0.40,
            strategy_name=self.name,
            reason="defensive hedge",
        )


async def _drain(bus):
    while not bus.queue.empty():
        await bus.dispatch_once()


def test_v2_event_bus_prioritizes_persists_and_replays_events():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        delivered = []
        replayed = []

        async def handler(event):
            delivered.append((event.type, event.data["value"], event.replayed))

        async def replay_handler(event):
            replayed.append((event.type, event.data["value"], event.replayed))

        bus.subscribe("normal", handler)
        bus.subscribe("urgent", handler)

        await bus.publish("normal", {"value": 1}, priority=100)
        await bus.publish("urgent", {"value": 2}, priority=1)
        await _drain(bus)
        await bus.replay(handler=replay_handler)
        return delivered, replayed

    delivered, replayed = asyncio.run(scenario())

    assert delivered == [("urgent", 2, False), ("normal", 1, False)]
    assert replayed == [("normal", 1, True), ("urgent", 2, True)]


def test_v2_runtime_uses_agents_to_select_strategy_then_executes_trade():
    async def scenario():
        runtime = SopotekRuntime(broker=DummyBroker(), starting_equity=100000.0)
        runtime.register_strategy(TrendStrategy(), active=True)
        runtime.register_strategy(DefensiveStrategy(), active=True)

        await runtime.bus.publish(
            EventType.CANDLE,
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open=100.0,
                high=103.0,
                low=99.0,
                close=102.0,
                volume=12.0,
            ),
            priority=40,
        )
        await _drain(runtime.bus)

        selected = [strategy.name for strategy in runtime.registry.get_active("BTC/USDT")]

        await runtime.market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 100.0})
        await _drain(runtime.bus)

        await runtime.market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 101.0})
        await _drain(runtime.bus)

        latest_snapshot = runtime.risk_engine.latest_snapshot
        execution_reports = list(runtime.execution_monitor.reports)
        order = runtime.broker.orders[0]

        return selected, latest_snapshot, execution_reports, order

    selected, latest_snapshot, execution_reports, order = asyncio.run(scenario())

    assert selected == ["trend"]
    assert order.side == "buy"
    assert execution_reports and execution_reports[0].strategy_name == "trend"
    assert latest_snapshot.equity > 100000.0


def test_v2_runtime_kill_switch_blocks_new_orders():
    async def scenario():
        broker = DummyBroker()
        runtime = SopotekRuntime(broker=broker, starting_equity=100000.0)
        runtime.register_strategy(TrendStrategy(), active=True)
        runtime.risk_engine.activate_kill_switch("Manual halt")

        await runtime.market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 100.0})
        await _drain(runtime.bus)
        return broker.orders, list(runtime.risk_manager.alerts)

    orders, alerts = asyncio.run(scenario())

    assert orders == []
    assert alerts
    assert alerts[-1]["kill_switch_active"] is True
