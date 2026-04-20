import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.agents.strategy_agents import BreakoutAgent, MLAgent, MeanReversionAgent, SignalAgent, TrendFollowingAgent
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import Candle, FeatureVector, Signal, TradeFeedback, TradeReview
from sopotek.ml import MLFilterEngine, TradeOutcomeTrainingPipeline
from sopotek.storage import QuantRepository
from sopotek.testing import run_paper_trading_session
from storage import database as storage_db


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


def _build_candles(
    symbol: str,
    closes: list[float],
    *,
    timeframe: str = "1m",
    base_ts: int = 1710000000,
    volume: float = 100.0,
    volumes: list[float] | None = None,
):
    candles = []
    previous = closes[0]
    for index, close in enumerate(closes):
        open_ = previous if index else close
        high = max(open_, close) + 0.3
        low = min(open_, close) - 0.3
        start = datetime.fromtimestamp(base_ts + (index * 60), tz=timezone.utc)
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volumes[index] if volumes is not None else volume + index * 5.0),
                start=start,
                end=start + timedelta(minutes=1),
            )
        )
        previous = close
    return candles


def _build_candle_rows(start_price: float, drift: float, *, count: int = 30, base_ts_ms: int = 1710000000000):
    rows = []
    close = start_price
    for index in range(count):
        open_ = close
        close = max(5.0, close + drift)
        high = max(open_, close) + 0.25
        low = min(open_, close) - 0.25
        volume = 100.0 + (index % 5) * 10.0
        rows.append([base_ts_ms + index * 60000, open_, high, low, close, volume])
    return rows


class ConstantPredictor:
    def __init__(self, probability: float) -> None:
        self.probability = float(probability)

    def predict_probability(self, _features) -> float:
        return self.probability


class RoundTripAgent(SignalAgent):
    name = "round_trip"

    def generate_signal(self, symbol: str, candles: list[Candle]) -> Signal | None:
        index = len(candles)
        last = candles[-1]
        if index == self.min_history:
            return Signal(
                symbol=symbol,
                side="buy",
                quantity=1.0,
                price=float(last.close),
                confidence=0.7,
                strategy_name=self.name,
                reason="entry leg",
                metadata={"timeframe": self.timeframe},
            )
        if index == self.min_history + 12:
            return Signal(
                symbol=symbol,
                side="sell",
                quantity=1.0,
                price=float(last.close),
                confidence=0.7,
                strategy_name=self.name,
                reason="exit leg",
                metadata={"timeframe": self.timeframe},
            )
        return None


def test_institutional_strategy_agents_emit_expected_signals():
    async def scenario():
        outputs = {}

        for name, agent, candles in (
            (
                "trend_following",
                TrendFollowingAgent(timeframe="1m", min_history=20, lookback=40, default_quantity=1.0),
                _build_candles("TREND", [100.0 + (index * 1.1) for index in range(26)]),
            ),
            (
                "mean_reversion",
                MeanReversionAgent(timeframe="1m", min_history=20, lookback=40, default_quantity=1.0),
                _build_candles("MEAN", ([100.0] * 20) + [95.0, 92.0, 89.0, 87.0, 86.0, 85.0]),
            ),
            (
                "breakout",
                BreakoutAgent(timeframe="1m", min_history=20, lookback=40, default_quantity=1.0),
                _build_candles(
                    "BREAK",
                    ([100.0] * 24) + [102.0, 110.0],
                    volume=100.0,
                    volumes=([100.0] * 24) + [120.0, 1200.0],
                ),
            ),
            (
                "ml_agent",
                MLAgent(ConstantPredictor(0.82), timeframe="1m", min_history=20, lookback=40, default_quantity=1.0),
                _build_candles("ML", [100.0 + (index * 0.7) for index in range(26)]),
            ),
        ):
            bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
            seen = []
            agent.attach(bus)
            bus.subscribe(EventType.SIGNAL, lambda event, bucket=seen: bucket.append(event.data))
            for candle in candles:
                await bus.publish(EventType.CANDLE, candle, priority=40)
                await _drain(bus)
            outputs[name] = seen[-1]

        return outputs

    outputs = asyncio.run(scenario())

    assert outputs["trend_following"].strategy_name == "trend_following"
    assert outputs["trend_following"].side == "buy"
    assert outputs["mean_reversion"].strategy_name == "mean_reversion"
    assert outputs["mean_reversion"].side == "buy"
    assert outputs["breakout"].strategy_name == "breakout"
    assert outputs["breakout"].side == "buy"
    assert outputs["ml_agent"].strategy_name == "ml_agent"
    assert outputs["ml_agent"].confidence >= 0.82


def test_institutional_ml_pipeline_filters_pre_trade_signals():
    feedback_rows = []
    for index in range(12):
        feedback_rows.append(
            TradeFeedback(
                symbol=f"WIN-{index}",
                strategy_name="trend_following",
                side="buy",
                quantity=1.0,
                entry_price=100.0,
                exit_price=103.0,
                pnl=3.0,
                success=True,
                features={"ema_gap": 0.03 + (index * 0.002), "rsi": 62.0 + index, "volatility": 0.01, "zscore": 0.2},
            )
        )
        feedback_rows.append(
            TradeFeedback(
                symbol=f"LOSS-{index}",
                strategy_name="trend_following",
                side="buy",
                quantity=1.0,
                entry_price=100.0,
                exit_price=97.0,
                pnl=-3.0,
                success=False,
                features={"ema_gap": -0.03 - (index * 0.002), "rsi": 35.0 - index, "volatility": 0.04, "zscore": -1.8},
            )
        )

    pipeline = TradeOutcomeTrainingPipeline(model_name="institutional_test_model")
    report = pipeline.fit_from_feedback(feedback_rows, model_family="tree")

    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        approved = []
        rejected = []
        MLFilterEngine(bus, pipeline, threshold=0.6, allow_passthrough=False)
        bus.subscribe(EventType.MODEL_APPROVED, lambda event: approved.append(event.data))
        bus.subscribe(EventType.MODEL_REJECTED, lambda event: rejected.append(event.data))

        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={"ema_gap": 0.08, "rsi": 68.0, "volatility": 0.01, "zscore": 0.1},
            ),
            priority=45,
        )
        await bus.publish(
            EventType.RISK_APPROVED,
            TradeReview(approved=True, symbol="BTC/USDT", side="buy", quantity=1.0, price=100.0, reason="risk ok", strategy_name="trend_following"),
            priority=70,
        )
        await _drain(bus)

        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="ETH/USDT",
                timeframe="1m",
                values={"ema_gap": -0.08, "rsi": 24.0, "volatility": 0.05, "zscore": -2.1},
            ),
            priority=45,
        )
        await bus.publish(
            EventType.RISK_APPROVED,
            TradeReview(approved=True, symbol="ETH/USDT", side="buy", quantity=1.0, price=100.0, reason="risk ok", strategy_name="trend_following"),
            priority=70,
        )
        await _drain(bus)
        return approved, rejected

    approved, rejected = asyncio.run(scenario())

    assert report.sample_count == 24
    assert report.metrics["accuracy"] >= 0.8
    assert len(approved) == 1
    assert len(rejected) == 1
    assert approved[0].metadata["model_probability"] >= 0.6
    assert rejected[0].metadata["model_probability"] < 0.6


def test_paper_runner_executes_multi_symbol_event_driven_stack_and_persists_feedback(tmp_path):
    upward = _build_candle_rows(100.0, 0.5, count=50)
    downward = _build_candle_rows(100.0, -0.5, count=50)
    candles = {
        "BTC/USDT": upward,
        "ETH/USDT": upward,
        "SOL/USDT": downward,
        "ADA/USDT": downward,
    }
    database_one = tmp_path / "institutional-one.sqlite3"
    database_two = tmp_path / "institutional-two.sqlite3"

    async def scenario(path):
        return await run_paper_trading_session(
            candles,
            timeframe="1m",
            database_url=f"sqlite:///{path.as_posix()}",
            random_seed=11,
            enable_default_agents=False,
            agents=[RoundTripAgent(timeframe="1m", min_history=26, lookback=64, default_quantity=1.0)],
            broker_kwargs={"partial_fill_probability": 0.0},
        )

    run_one = asyncio.run(scenario(database_one))
    repo = QuantRepository()
    feedback_rows = repo.load_feedback()
    feature_rows = repo.list_feature_vectors(limit=200)
    model_rows = repo.list_model_scores(limit=200)
    performance_rows = repo.list_performance_metrics(limit=200)

    run_two = asyncio.run(scenario(database_two))

    storage_db.engine.dispose()

    assert run_one.result.symbol_count == 4
    assert run_one.result.feedback_count >= 4
    assert run_one.result.performance.closed_trades >= 4
    assert len(feedback_rows) >= 4
    assert len(feature_rows) > 0
    assert len(model_rows) > 0
    assert len(performance_rows) > 0
    assert run_one.retraining_report is not None
    assert run_one.runtime.ml_pipeline.is_fitted is True
    assert run_one.runtime.trader_agent is not None
    assert any(run_one.runtime.trader_agent.recent_decisions.values())
    assert run_one.result.final_snapshot.equity == pytest.approx(run_two.result.final_snapshot.equity)
