import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.agents.market_analyst import MarketAnalystAgent
from sopotek.agents.reasoning_agent import ReasoningAgent
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import Candle, FeatureVector, OrderBookSnapshot, Signal
from sopotek.engines.features import FeatureEngine
from sopotek.ml.regime_engine import RegimeEngine
from sopotek.storage.feature_store import FeatureStore


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


def _candles(symbol: str, closes: list[float], *, timeframe: str = "1m") -> list[Candle]:
    rows = []
    for index, close in enumerate(closes):
        open_ = closes[index - 1] if index else close
        start = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
        rows.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=float(open_),
                high=float(max(open_, close) + 0.4),
                low=float(min(open_, close) - 0.4),
                close=float(close),
                volume=float(100 + index * 5),
                start=start,
                end=start + timedelta(minutes=1),
            )
        )
    return rows


def test_regime_engine_and_market_analyst_publish_bullish_snapshot():
    candles = _candles("BTC/USDT", [100 + index * 0.8 for index in range(32)])
    engine = RegimeEngine()
    snapshot = engine.classify_candles(candles)

    assert snapshot.regime == "bullish"
    assert snapshot.preferred_strategy in {"trend_following", "breakout"}
    assert snapshot.volatility_regime in {"low", "medium", "high"}

    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        analyst = MarketAnalystAgent()
        analyst.attach(bus)
        regimes = []
        insights = []
        bus.subscribe(EventType.REGIME, lambda event: regimes.append(event.data))
        bus.subscribe(EventType.ANALYST_INSIGHT, lambda event: insights.append(event.data))
        for candle in candles:
            await bus.publish(EventType.CANDLE, candle, priority=40)
            await _drain(bus)
        return regimes[-1], insights[-1]

    regime_event, insight = asyncio.run(scenario())

    assert regime_event.regime == "bullish"
    assert insight.regime == "bullish"
    assert insight.metadata["volatility_regime"] in {"low", "medium", "high"}


def test_feature_engine_merges_order_book_features_and_feature_store_persists(tmp_path):
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        feature_engine = FeatureEngine(bus, timeframe="1m", min_history=10)
        store = FeatureStore(bus, base_dir=tmp_path / "feature_store")
        emitted = []
        bus.subscribe(EventType.FEATURE_VECTOR, lambda event: emitted.append(event.data))

        for candle in _candles("ETH/USDT", [100 + index * 0.25 for index in range(12)]):
            await bus.publish(EventType.CANDLE, candle, priority=40)
            await _drain(bus)

        await bus.publish(
            EventType.ORDER_BOOK,
            OrderBookSnapshot(
                symbol="ETH/USDT",
                bids=[(101.0, 8.0), (100.9, 6.0), (100.8, 5.0)],
                asks=[(101.1, 3.0), (101.2, 2.0), (101.3, 2.0)],
            ),
            priority=30,
        )
        await _drain(bus)

        rows = store.read("feature_vectors")
        return feature_engine.latest["ETH/USDT"], emitted[-1], rows[-1]

    latest, emitted, stored = asyncio.run(scenario())

    assert latest.values["order_book_imbalance"] > 0
    assert latest.values["large_order_ratio"] >= 1.0
    assert latest.metadata["dominant_liquidity_side"] == "bid"
    assert emitted.values["order_book_spread_bps"] > 0
    assert stored["event_type"] == EventType.FEATURE_VECTOR
    assert stored["data"]["values"]["order_book_imbalance"] > 0


def test_reasoning_agent_publishes_explainable_trade_rationale():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        reasoning_agent = ReasoningAgent()
        reasoning_agent.attach(bus)
        decisions = []
        bus.subscribe(EventType.REASONING_DECISION, lambda event: decisions.append(event.data))

        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="SOL/USDT",
                timeframe="1m",
                values={
                    "rsi": 29.0,
                    "ema_gap": 0.02,
                    "volatility": 0.012,
                    "order_book_imbalance": 0.24,
                },
                metadata={"dominant_liquidity_side": "bid"},
            ),
            priority=45,
        )
        await bus.publish(
            EventType.ANALYST_INSIGHT,
            {
                "symbol": "SOL/USDT",
                "regime": "bullish",
                "momentum": 1.2,
                "volatility": 1.01,
                "preferred_strategy": "trend_following",
            },
            priority=50,
        )
        await bus.publish(
            EventType.SIGNAL,
            Signal(
                symbol="SOL/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.82,
                strategy_name="trend_following",
                reason="signal fired",
            ),
            priority=60,
        )
        await _drain(bus)
        return decisions[-1]

    decision = asyncio.run(scenario())

    assert decision.decision == "BUY"
    assert decision.regime == "bullish"
    assert "trend is bullish" in decision.reasoning
    assert "RSI is oversold" in decision.reasoning
    assert decision.risk in {"low", "medium", "high"}
