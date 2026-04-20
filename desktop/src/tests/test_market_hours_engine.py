import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.agents.trader_agent import InvestorProfile, TraderAgent
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.market_hours_engine import MarketHoursEngine
from sopotek.core.models import Signal, TradeReview
from sopotek.engines.execution import ExecutionEngine


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


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
            "filled_quantity": order.quantity,
        }

    async def stream_ticks(self, symbol: str):
        if False:
            yield {"symbol": symbol, "price": 0.0}


def test_market_hours_engine_market_status_and_sessions():
    engine = MarketHoursEngine(default_asset_type="stocks")

    assert engine.is_crypto_market_open(now=datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc))
    assert not engine.is_forex_market_open(now=datetime(2026, 1, 4, 21, 59, tzinfo=timezone.utc))
    assert engine.is_forex_market_open(now=datetime(2026, 1, 4, 22, 0, tzinfo=timezone.utc))
    assert not engine.is_forex_market_open(now=datetime(2026, 1, 9, 22, 0, tzinfo=timezone.utc))

    assert engine.get_forex_session(now=datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc)) == "tokyo"
    assert engine.get_forex_session(now=datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)) == "london"
    assert engine.get_forex_session(now=datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc)) == "overlap"
    assert engine.get_forex_session(now=datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc)) == "new_york"
    assert not engine.is_high_liquidity_session(now=datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc))
    assert engine.is_high_liquidity_session(now=datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc))

    assert engine.is_stock_market_open(now=datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc))
    assert not engine.is_stock_market_open(now=datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc))
    assert not engine.is_stock_market_open(now=datetime(2026, 12, 25, 15, 0, tzinfo=timezone.utc))


def test_market_hours_engine_blocks_trader_agent_when_market_closed():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["AAPL"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
            default_asset_type="stocks",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(
            EventType.MARKET_DATA_EVENT,
            {"symbol": "AAPL", "price": 198.0, "timestamp": datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc)},
            priority=19,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="AAPL",
                side="buy",
                quantity=1.0,
                price=198.0,
                confidence=0.82,
                strategy_name="trend_following",
                reason="trend continuation",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders

    decision, orders = asyncio.run(scenario())

    assert decision.action == "SKIP"
    assert "market is closed" in decision.reasoning.lower()
    assert "market_hours" in decision.applied_constraints
    assert orders == []


def test_market_hours_engine_blocks_execution_when_market_closed():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        broker = DummyBroker()
        engine = ExecutionEngine(
            broker,
            bus,
            market_hours_engine=MarketHoursEngine(default_asset_type="stocks"),
            default_asset_type="stocks",
        )
        report = await engine.execute(
            TradeReview(
                approved=True,
                symbol="AAPL",
                side="buy",
                quantity=5.0,
                price=198.0,
                reason="earnings breakout",
                strategy_name="breakout",
                metadata={"asset_type": "stocks"},
                timestamp=datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc),
            )
        )
        return report, broker.orders

    report, orders = asyncio.run(scenario())

    assert report.status == "rejected_market_hours"
    assert "market is closed" in report.metadata["error"].lower()
    assert orders == []
