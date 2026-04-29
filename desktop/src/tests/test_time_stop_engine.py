import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.regime_engine_config import TimeStopConfig
from risk.time_stop_engine import TimeStopEngine
from sopotek.brokers.paper import PaperBroker
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import RegimeSnapshot, TradeReview
from sopotek.core.orchestrator import SopotekRuntime
from sopotek.engines import ExecutionEngine, MarketDataEngine, PortfolioEngine


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


def test_time_stop_engine_closes_on_signal_expiry_and_emits_order_topic():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
        market_data = MarketDataEngine(broker, bus)
        PortfolioEngine(bus, starting_cash=100000.0)
        ExecutionEngine(broker, bus)
        engine = TimeStopEngine(
            bus,
            time_stop_config=TimeStopConfig(
                strict_basic_time_stop=False,
                soft_time_stop_fraction=1.0,
                alert_before_close_seconds=5.0,
            ),
        )

        close_orders = []
        decisions = []
        bus.subscribe(EventType.ORDERS_CLOSE, lambda event: close_orders.append(event.data))
        bus.subscribe(EventType.TIME_STOP_DECISION, lambda event: decisions.append(event.data))

        entry_time = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)
        signal_expiry = entry_time + timedelta(seconds=30)
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
                metadata={
                    "expected_horizon": "short",
                    "signal_expiry_time": signal_expiry,
                    "confidence": 0.82,
                    "volatility_at_entry": 0.01,
                },
                timestamp=entry_time,
            ),
            priority=70,
        )
        await _drain(bus)

        assert engine.get_state("BTC/USDT") is not None

        await market_data.publish_tick(
            "BTC/USDT",
            {
                "symbol": "BTC/USDT",
                "price": 100.4,
                "timestamp": signal_expiry + timedelta(seconds=1),
            },
        )
        await _drain(bus)

        return close_orders, decisions, list(broker.order_log), engine.get_state("BTC/USDT")

    close_orders, decisions, orders, final_state = asyncio.run(scenario())

    assert len(close_orders) == 1
    assert close_orders[0].reason == "Alpha signal expired"
    assert len(decisions) == 1
    assert decisions[0].reason == "Alpha signal expired"
    assert len(orders) == 2
    assert orders[-1]["filled_quantity"] == pytest.approx(1.0)
    assert final_state is None


def test_time_stop_engine_emits_preclose_alert_and_respects_range_regime():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
        market_data = MarketDataEngine(broker, bus)
        PortfolioEngine(bus, starting_cash=100000.0)
        ExecutionEngine(broker, bus)
        engine = TimeStopEngine(
            bus,
            time_stop_config=TimeStopConfig(
                short_horizon_seconds=100.0,
                strict_basic_time_stop=True,
                soft_time_stop_fraction=0.85,
                range_regime_multiplier=0.50,
                alert_before_close_seconds=15.0,
                min_expected_return=0.002,
            ),
        )

        alerts = []
        close_orders = []
        bus.subscribe(EventType.ALERT_EVENT, lambda event: alerts.append(event.data))
        bus.subscribe(EventType.ORDERS_CLOSE, lambda event: close_orders.append(event.data))

        entry_time = datetime(2026, 4, 6, 13, 0, tzinfo=timezone.utc)
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
                metadata={
                    "expected_horizon": "short",
                    "confidence": 0.0,
                    "volatility_at_entry": 0.05,
                },
                timestamp=entry_time,
            ),
            priority=70,
        )
        await _drain(bus)

        await bus.publish(
            EventType.REGIME_UPDATES,
            RegimeSnapshot(
                symbol="ETH/USDT",
                timeframe="1m",
                regime="RANGE",
                timestamp=entry_time + timedelta(seconds=5),
            ),
            priority=48,
        )
        await _drain(bus)

        await market_data.publish_tick(
            "ETH/USDT",
            {
                "symbol": "ETH/USDT",
                "price": 100.0,
                "timestamp": entry_time + timedelta(seconds=40),
            },
        )
        await _drain(bus)

        await market_data.publish_tick(
            "ETH/USDT",
            {
                "symbol": "ETH/USDT",
                "price": 99.95,
                "timestamp": entry_time + timedelta(seconds=46),
            },
        )
        await _drain(bus)

        await market_data.publish_tick(
            "ETH/USDT",
            {
                "symbol": "ETH/USDT",
                "price": 99.90,
                "timestamp": entry_time + timedelta(seconds=53),
            },
        )
        await _drain(bus)

        return alerts, close_orders, list(broker.order_log), engine.get_state("ETH/USDT")

    alerts, close_orders, orders, final_state = asyncio.run(scenario())

    assert alerts
    assert "Time Stop Approaching" == alerts[-1].title
    assert len(close_orders) == 1
    assert close_orders[0].reason == "Soft time stop: underperforming stale position"
    assert len(orders) == 2
    assert final_state is None


def test_time_stop_engine_uses_backtest_event_time_in_runtime():
    async def scenario():
        broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
        runtime = SopotekRuntime(
            broker=broker,
            starting_equity=100000.0,
            enable_default_agents=False,
            enable_ml_filter=False,
            enable_profit_protection=False,
            enable_alerting=False,
            enable_mobile_dashboard=False,
            enable_trade_journal_ai=False,
            enable_feature_store=False,
            enable_market_hours=False,
            time_stop_kwargs={
                "short_horizon_seconds": 60.0,
                "strict_basic_time_stop": True,
                "soft_time_stop_fraction": 1.0,
                "alert_before_close_seconds": 5.0,
            },
        )
        close_orders = []
        decisions = []
        runtime.bus.subscribe(EventType.ORDERS_CLOSE, lambda event: close_orders.append(event.data))
        runtime.bus.subscribe(EventType.TIME_STOP_DECISION, lambda event: decisions.append(event.data))

        entry_time = datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc)
        await runtime.bus.publish(
            EventType.RISK_APPROVED,
            TradeReview(
                approved=True,
                symbol="SOL/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                reason="entry",
                strategy_name="trend",
                metadata={
                    "expected_horizon": "short",
                    "confidence": 0.25,
                    "volatility_at_entry": 0.03,
                },
                timestamp=entry_time,
            ),
            priority=70,
        )
        await _drain(runtime.bus)

        result = await runtime.backtest_engine.run(
            {
                "SOL/USDT": [
                    (entry_time + timedelta(seconds=30), 100.0, 100.5, 99.8, 100.1, 12.0),
                    (entry_time + timedelta(seconds=70), 100.1, 100.2, 99.9, 100.0, 10.0),
                ]
            },
            timeframe="1m",
        )

        return close_orders, decisions, list(broker.order_log), runtime.time_stop_engine.get_state("SOL/USDT"), result

    close_orders, decisions, orders, final_state, result = asyncio.run(scenario())

    assert close_orders
    assert close_orders[0].reason == "Basic time stop reached"
    assert decisions
    assert decisions[0].duration_seconds >= 60.0
    assert len(orders) == 2
    assert final_state is None
    assert result.processed_events == 6
