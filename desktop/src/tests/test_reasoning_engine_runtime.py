import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.system_trading import SopotekTrading
from engines.risk_engine import RiskEngine
from core.reasoning import HeuristicReasoningProvider, ReasoningEngine, ReasoningResult


class DummyBroker:
    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        return []

    async def fetch_balance(self):
        return {"total": {"USDT": 10000}}

    async def create_order(self, *args, **kwargs):
        return {"status": "filled"}


class FakeDataset:
    def __init__(self, frame):
        self.frame = frame
        self.empty = frame.empty

    def to_candles(self):
        rows = []
        for row in self.frame.itertuples(index=False):
            rows.append([row.timestamp, row.open, row.high, row.low, row.close, row.volume])
        return rows


class StaticProvider:
    def __init__(self, result):
        self.result = result

    async def evaluate(self, *, messages=None, context=None, mode="assistive"):
        return self.result


def _sample_frame():
    return pd.DataFrame(
        [
            {
                "timestamp": 1,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
                "rsi": 31.0,
                "trend_strength": 0.62,
                "atr_pct": 0.011,
            },
            {
                "timestamp": 2,
                "open": 100.5,
                "high": 103.0,
                "low": 100.0,
                "close": 102.0,
                "volume": 12.0,
                "rsi": 29.0,
                "trend_strength": 0.68,
                "atr_pct": 0.012,
            },
        ]
    )


def _controller(**overrides):
    payload = dict(
        broker=DummyBroker(),
        symbols=["BTC/USDT"],
        time_frame="1h",
        limit=200,
        strategy_name="Trend Following",
        strategy_params={},
        max_portfolio_risk=0.10,
        max_risk_per_trade=0.02,
        max_position_size_pct=0.10,
        max_gross_exposure_pct=2.0,
        balances={"total": {"USDT": 10000}},
        initial_capital=10000,
        market_data_repository=None,
        trade_repository=None,
        handle_trade_execution=lambda trade: None,
        publish_ai_signal=lambda *args, **kwargs: None,
        publish_strategy_debug=lambda *args, **kwargs: None,
        reasoning_enabled=True,
        reasoning_mode="assistive",
        reasoning_provider="heuristic",
        reasoning_min_confidence=0.75,
        reasoning_timeout_seconds=5.0,
    )
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_heuristic_reasoning_engine_returns_structured_explanation():
    dataset = FakeDataset(_sample_frame())
    engine = ReasoningEngine(
        provider=HeuristicReasoningProvider(),
        fallback_provider=HeuristicReasoningProvider(),
        mode="assistive",
        enabled=True,
        minimum_confidence=0.75,
    )

    result, context = asyncio.run(
        engine.evaluate(
            symbol="BTC/USDT",
            signal={
                "side": "buy",
                "amount": 0.5,
                "price": 102.0,
                "confidence": 0.81,
                "strategy_name": "Trend Following",
                "reason": "breakout setup",
            },
            dataset=dataset,
            timeframe="15m",
            regime_snapshot={"regime": "bullish", "volatility": "medium", "trend_strength": 0.68},
            portfolio_snapshot={"equity": 10000.0, "gross_exposure": 1500.0, "net_exposure": 750.0},
            risk_limits={"max_risk_per_trade": 0.02},
        )
    )

    assert context["symbol"] == "BTC/USDT"
    assert context["indicators"]["rsi"] == 29.0
    assert result.decision == "APPROVE"
    assert result.should_execute is True
    assert result.reasoning
    assert result.provider == "heuristic"


def test_review_signal_in_assistive_mode_adds_reasoning_and_persists_memory():
    published = []
    saved = []

    class Repo:
        def save_decision(self, **kwargs):
            saved.append(dict(kwargs))
            return SimpleNamespace(**kwargs)

    trading = SopotekTrading(
        controller=_controller(
            publish_ai_signal=lambda symbol, signal, candles=None: published.append((symbol, dict(signal), list(candles or []))),
            agent_decision_repository=Repo(),
        )
    )
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    trading.reasoning_engine = ReasoningEngine(
        provider=StaticProvider(
            ReasoningResult(
                decision="NEUTRAL",
                confidence=0.62,
                reasoning="The signal is valid but still trading against a fragile macro backdrop.",
                risk="Moderate",
                warnings=["Bearish macro trend still active."],
                provider="static",
                mode="assistive",
            )
        ),
        fallback_provider=HeuristicReasoningProvider(),
        mode="assistive",
        enabled=True,
        minimum_confidence=0.75,
    )

    review = asyncio.run(
        trading.review_signal(
            "BTC/USDT",
            {
                "decision_id": "dec-123",
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 2.0,
                "price": 100.0,
                "confidence": 0.78,
                "reason": "oversold breakout",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
            timeframe="15m",
        )
    )

    assert review["approved"] is True
    assert review["reasoning"]["decision"] == "NEUTRAL"
    assert "fragile macro backdrop" in review["reasoning"]["reasoning"]
    assert published and "Warnings:" in published[-1][1]["reason"]
    assert trading.agent_memory.latest("ReasoningEngine") is not None
    assert any(row["agent_name"] == "ReasoningEngine" for row in saved)


def test_process_signal_in_advisory_mode_blocks_trade_when_reasoning_rejects():
    trading = SopotekTrading(controller=_controller(reasoning_mode="advisory"))
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    trading.reasoning_engine = ReasoningEngine(
        provider=StaticProvider(
            ReasoningResult(
                decision="REJECT",
                confidence=0.31,
                reasoning="Trend conflict and elevated portfolio crowding make this setup too fragile.",
                risk="High",
                warnings=["Portfolio exposure is already elevated."],
                provider="static",
                mode="advisory",
            )
        ),
        fallback_provider=HeuristicReasoningProvider(),
        mode="advisory",
        enabled=True,
        minimum_confidence=0.75,
    )

    async def fail_execute(**kwargs):
        raise AssertionError("execution should not run when advisory reasoning rejects the trade")

    trading.execution_manager.execute = fail_execute

    result = asyncio.run(
        trading.process_signal(
            "BTC/USDT",
            {
                "decision_id": "dec-456",
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 2.0,
                "price": 100.0,
                "confidence": 0.82,
                "reason": "breakout setup",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
            timeframe="15m",
        )
    )

    assert result is None
    snapshot = trading.pipeline_status_snapshot()["BTC/USDT"]
    assert snapshot["stage"] == "reasoning_engine"
    assert snapshot["status"] == "rejected"
