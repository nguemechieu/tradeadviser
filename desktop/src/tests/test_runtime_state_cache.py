import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import Candle, ExecutionReport, OrderBookSnapshot, PortfolioSnapshot, Position, PositionUpdate
from sopotek.core.orchestrator import SopotekRuntime
from sopotek.core.runtime_state_cache import RuntimeStateCache


class DummyBroker:
    def __init__(self):
        self.orders = []

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        return []

    async def place_order(self, order):
        self.orders.append(order)
        return {"id": f"order-{len(self.orders)}", "status": "filled", "price": order.price}

    async def stream_ticks(self, symbol: str):
        if False:
            yield {"symbol": symbol, "price": 0.0}


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


def test_runtime_state_cache_tracks_live_runtime_events():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        cache = RuntimeStateCache().attach(bus)

        await bus.publish(EventType.MARKET_TICK, {"symbol": "BTC/USDT", "price": 101.5}, priority=20)
        await bus.publish(
            EventType.CANDLE,
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.5,
                volume=12.0,
            ),
            priority=40,
        )
        await bus.publish(
            EventType.ORDER_BOOK,
            OrderBookSnapshot(
                symbol="BTC/USDT",
                bids=[(101.4, 1.2)],
                asks=[(101.6, 1.1)],
            ),
            priority=30,
        )
        await bus.publish(
            EventType.ORDER_SUBMITTED,
            {
                "order_id": "ord-1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": 0.5,
                "status": "submitted",
            },
            priority=75,
        )
        await bus.publish(
            EventType.EXECUTION_REPORT,
            ExecutionReport(
                order_id="ord-1",
                symbol="BTC/USDT",
                side="buy",
                quantity=0.5,
                requested_price=101.4,
                fill_price=101.5,
                status="filled",
                latency_ms=5.0,
                filled_quantity=0.5,
            ),
            priority=85,
        )
        await bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(
                symbol="BTC/USDT",
                quantity=0.5,
                average_price=101.5,
                current_price=101.5,
                unrealized_pnl=0.0,
                market_value=50.75,
            ),
            priority=88,
        )
        await bus.publish(
            EventType.PORTFOLIO_SNAPSHOT,
            PortfolioSnapshot(
                cash=9950.0,
                equity=10000.75,
                positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=0.5, average_price=101.5, last_price=101.5)},
                gross_exposure=50.75,
                net_exposure=50.75,
            ),
            priority=90,
        )
        await bus.publish(
            EventType.RISK_ALERT,
            {"symbol": "BTC/USDT", "reason": "volatility spike", "kill_switch_active": False},
            priority=5,
        )
        await _drain(bus)
        return cache

    cache = asyncio.run(scenario())

    assert cache.latest_price("BTC/USDT") == 101.5
    assert cache.latest_candles("BTC/USDT", "1m")[-1]["close"] == 101.5
    assert cache.latest_order("ord-1")["status"] == "filled"
    assert cache.latest_order("ord-1")["event_type"] == EventType.EXECUTION_REPORT
    assert cache.position("BTC/USDT")["market_value"] == 50.75
    assert cache.portfolio_snapshot["equity"] == 10000.75
    assert cache.risk_alerts[-1]["reason"] == "volatility spike"
    assert cache.snapshot()["market_ticks"]["BTC/USDT"]["price"] == 101.5


def test_runtime_state_cache_rebuilds_from_persisted_events_without_duplication():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        await bus.publish(EventType.MARKET_TICK, {"symbol": "ETH/USDT", "price": 2200.0}, priority=20)
        await bus.publish(
            EventType.CANDLE,
            Candle(
                symbol="ETH/USDT",
                timeframe="5m",
                open=2190.0,
                high=2210.0,
                low=2185.0,
                close=2200.0,
                volume=22.0,
            ),
            priority=40,
        )
        await bus.publish(
            EventType.EXECUTION_REPORT,
            ExecutionReport(
                order_id="eth-1",
                symbol="ETH/USDT",
                side="sell",
                quantity=1.0,
                requested_price=2201.0,
                fill_price=2200.0,
                status="filled",
                latency_ms=3.0,
                filled_quantity=1.0,
            ),
            priority=85,
        )

        cache = RuntimeStateCache()
        await cache.rebuild_from_bus(bus, clear=True)
        snapshot_once = cache.snapshot()
        await cache.rebuild_from_bus(bus, clear=False)
        snapshot_twice = cache.snapshot()
        return snapshot_once, snapshot_twice, cache

    snapshot_once, snapshot_twice, cache = asyncio.run(scenario())

    assert snapshot_once == snapshot_twice
    assert cache.latest_price("ETH/USDT") == 2200.0
    assert len(cache.latest_candles("ETH/USDT", "5m")) == 1
    assert len(cache.orders_for_symbol("ETH/USDT")) == 1


def test_runtime_can_restore_state_from_jsonl_event_store(tmp_path):
    async def scenario():
        store_path = tmp_path / "runtime-events.jsonl"
        runtime_a = SopotekRuntime(
            broker=DummyBroker(),
            enable_default_agents=False,
            enable_alerting=False,
            enable_mobile_dashboard=False,
            enable_trade_journal_ai=False,
            event_store_path=str(store_path),
            persist_events=True,
        )
        await runtime_a.bus.publish(
            EventType.EXECUTION_REPORT,
            ExecutionReport(
                order_id="btc-restore-1",
                symbol="BTC/USDT",
                side="buy",
                quantity=0.25,
                requested_price=100.0,
                fill_price=100.2,
                status="filled",
                latency_ms=4.0,
                filled_quantity=0.25,
            ),
            priority=85,
        )
        await runtime_a.bus.publish(
            EventType.PORTFOLIO_SNAPSHOT,
            PortfolioSnapshot(
                cash=9975.0,
                equity=10025.0,
                positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=0.25, average_price=100.2, last_price=100.2)},
                gross_exposure=25.05,
                net_exposure=25.05,
            ),
            priority=90,
        )

        runtime_b = SopotekRuntime(
            broker=DummyBroker(),
            enable_default_agents=False,
            enable_alerting=False,
            enable_mobile_dashboard=False,
            enable_trade_journal_ai=False,
            event_store_path=str(store_path),
            persist_events=True,
        )
        restored = await runtime_b.restore_runtime_state()
        return restored, runtime_b.state_cache

    restored, cache = asyncio.run(scenario())

    assert restored == 2
    assert cache.latest_order("btc-restore-1")["fill_price"] == 100.2
    assert cache.portfolio_snapshot["equity"] == 10025.0
