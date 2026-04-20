import asyncio
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.brokers.paper import PaperBroker
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import FeatureVector, TradeReview
from sopotek.engines import ExecutionEngine, MarketDataEngine, PartialProfitLevel, PortfolioEngine, ProfitProtectionEngine


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class ConstantPredictor:
    def __init__(self, probability: float, *, is_fitted: bool = True) -> None:
        self.probability = float(probability)
        self.is_fitted = bool(is_fitted)

    def predict_probability(self, _features) -> float:
        return self.probability


def test_profit_protection_break_even_partial_and_trailing_stop_exit():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
        market_data = MarketDataEngine(broker, bus)
        PortfolioEngine(bus, starting_cash=100000.0)
        ExecutionEngine(broker, bus)
        engine = ProfitProtectionEngine(
            bus,
            trailing_stop_mode="percent",
            trailing_stop_pct=0.05,
            break_even_profit_pct=0.01,
            partial_profit_levels=[PartialProfitLevel(0.02, 0.5)],
            time_exit_seconds=3600.0,
        )
        close_requests = []
        order_updates = []
        decisions = []
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))
        bus.subscribe(EventType.ORDER_UPDATE, lambda event: order_updates.append(event.data))
        bus.subscribe(EventType.PROFIT_PROTECTION_DECISION, lambda event: decisions.append(event.data))

        await bus.publish(
            EventType.RISK_APPROVED,
            TradeReview(
                approved=True,
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                reason="entry",
                strategy_name="trend",
                stop_price=95.0,
            ),
            priority=70,
        )
        await _drain(bus)

        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 101.0})
        await _drain(bus)

        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 102.0})
        await _drain(bus)

        state_after_partial = engine.get_state("BTC/USDT")

        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 110.0})
        await _drain(bus)

        state_before_stop = engine.get_state("BTC/USDT")

        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 104.0})
        await _drain(bus)

        return {
            "orders": list(broker.order_log),
            "close_requests": close_requests,
            "order_updates": order_updates,
            "decisions": decisions,
            "state_after_partial": state_after_partial,
            "state_before_stop": state_before_stop,
            "final_state": engine.get_state("BTC/USDT"),
        }

    result = asyncio.run(scenario())

    assert len(result["orders"]) == 3
    assert result["orders"][0]["status"] == "filled"
    assert result["orders"][1]["filled_quantity"] == pytest.approx(0.5)
    assert result["orders"][2]["filled_quantity"] == pytest.approx(0.5)
    assert len(result["close_requests"]) == 2
    assert result["close_requests"][0].reason.startswith("Partial profit target reached")
    assert result["close_requests"][1].reason == "Protective stop triggered"
    assert any(isinstance(update, dict) and update.get("reason") == "break_even" for update in result["order_updates"])
    assert any(isinstance(update, dict) and "trailing_stop" in str(update.get("reason")) for update in result["order_updates"])
    assert result["state_after_partial"] is not None
    assert result["state_after_partial"].partial_closed is True
    assert result["state_before_stop"] is not None
    assert result["state_before_stop"].stop_loss == pytest.approx(104.5, rel=1e-3)
    assert result["final_state"] is None
    assert [decision.action for decision in result["decisions"]] == ["reduce", "exit"]


def test_profit_protection_time_exit_closes_stale_position():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
        market_data = MarketDataEngine(broker, bus)
        PortfolioEngine(bus, starting_cash=100000.0)
        ExecutionEngine(broker, bus)
        engine = ProfitProtectionEngine(
            bus,
            trailing_stop_mode="percent",
            trailing_stop_pct=0.10,
            break_even_profit_pct=0.05,
            partial_profit_levels=[],
            time_exit_seconds=5.0,
            time_exit_min_progress_pct=0.01,
        )
        close_requests = []
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))

        await bus.publish(
            EventType.RISK_APPROVED,
            TradeReview(
                approved=True,
                symbol="ETH/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                reason="entry",
                strategy_name="mean_reversion",
            ),
            priority=70,
        )
        await _drain(bus)

        state = engine.get_state("ETH/USDT")
        assert state is not None
        state.opened_at = state.updated_at - timedelta(seconds=30)

        await market_data.publish_tick("ETH/USDT", {"symbol": "ETH/USDT", "price": 100.2})
        await _drain(bus)

        return close_requests, list(broker.order_log), engine.get_state("ETH/USDT")

    close_requests, orders, final_state = asyncio.run(scenario())

    assert len(close_requests) == 1
    assert close_requests[0].reason == "Time-based stale trade exit"
    assert len(orders) == 2
    assert orders[-1]["filled_quantity"] == pytest.approx(1.0)
    assert final_state is None


def test_profit_protection_ai_reduce_position():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
        market_data = MarketDataEngine(broker, bus)
        PortfolioEngine(bus, starting_cash=100000.0)
        ExecutionEngine(broker, bus)
        ProfitProtectionEngine(
            bus,
            predictor=ConstantPredictor(0.55),
            trailing_stop_mode="percent",
            trailing_stop_pct=0.20,
            break_even_profit_pct=0.20,
            partial_profit_levels=[],
            volatility_reduce_threshold=1.0,
            volatility_exit_threshold=2.0,
            ai_exit_threshold=0.4,
            ai_reduce_threshold=0.7,
            ai_reduce_fraction=0.5,
        )
        close_requests = []
        decisions = []
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))
        bus.subscribe(EventType.PROFIT_PROTECTION_DECISION, lambda event: decisions.append(event.data))

        await bus.publish(
            EventType.RISK_APPROVED,
            TradeReview(
                approved=True,
                symbol="SOL/USDT",
                side="buy",
                quantity=2.0,
                price=100.0,
                reason="entry",
                strategy_name="ml_agent",
            ),
            priority=70,
        )
        await _drain(bus)

        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="SOL/USDT",
                timeframe="1m",
                values={"rsi": 58.0, "ema_fast": 101.0, "ema_slow": 99.0, "volatility": 0.01},
            ),
            priority=45,
        )
        await _drain(bus)

        await market_data.publish_tick("SOL/USDT", {"symbol": "SOL/USDT", "price": 101.0})
        await _drain(bus)

        return close_requests, decisions, list(broker.order_log)

    close_requests, decisions, orders = asyncio.run(scenario())

    assert len(close_requests) == 1
    assert close_requests[0].quantity == pytest.approx(1.0)
    assert close_requests[0].reason.startswith("AI reduce")
    assert decisions[0].action == "reduce"
    assert decisions[0].model_probability == pytest.approx(0.55)
    assert len(orders) == 2
    assert orders[-1]["filled_quantity"] == pytest.approx(1.0)
