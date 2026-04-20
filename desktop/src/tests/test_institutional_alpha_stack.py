import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpha import AlphaAggregator, AlphaContext, RegimeEngine
from core.sopotek_trading import SopotekTrading
from engines.risk_engine import RiskEngine
from quant.data_models import SymbolDatasetSnapshot
from quant.feature_pipeline import FeaturePipeline, FeaturePipelineConfig
from quant.signal_engine import SignalEngine
from strategy.strategy_registry import StrategyRegistry


def _trend_candles(symbol="BTC/USDT", bars=96):
    base = 1700000000000
    candles = []
    close = 100.0
    for index in range(bars):
        drift = 0.16 if index < (bars - 20) else 0.48
        seasonal = ((index % 6) - 2) * 0.035
        close = max(20.0, close + drift + seasonal)
        open_ = close - (0.20 if index % 2 else -0.10)
        high = max(open_, close) + 0.45
        low = min(open_, close) - 0.30
        volume = 100 + index * 2 + (20 if index >= (bars - 20) else 0)
        candles.append([base + index * 3600000, open_, high, low, close, volume])
    return candles


def _range_candles(symbol="ETH/USDT", bars=96):
    base = 1700000000000
    candles = []
    close = 100.0
    for index in range(bars):
        wave = ((index % 10) - 5) * 0.18
        close = 100.0 + wave
        open_ = close - 0.05
        high = close + 0.35
        low = close - 0.35
        volume = 80 + (index % 5) * 3
        candles.append([base + index * 3600000, open_, high, low, close, volume])
    return candles


def _feature_frame(candles):
    pipeline = FeaturePipeline()
    return pipeline.compute(
        candles,
        FeaturePipelineConfig(rsi_period=10, ema_fast=12, ema_slow=26, atr_period=10, breakout_lookback=20),
    )


def test_regime_engine_flags_high_volatility_and_low_liquidity_when_market_is_stressed():
    frame = _feature_frame(_trend_candles())
    frame.loc[frame.index[-1], "atr_pct"] = 0.041
    frame.loc[frame.index[-1], "volume_ratio"] = 0.52
    frame.loc[frame.index[-1], "order_book_spread_bps"] = 24.0

    regime = RegimeEngine().classify_frame(frame)

    assert "HIGH_VOLATILITY" in regime.active_regimes
    assert "LOW_LIQUIDITY" in regime.active_regimes


def test_alpha_aggregator_ranks_trending_symbol_above_flat_symbol():
    trend_frame = _feature_frame(_trend_candles("BTC/USDT"))
    range_frame = _feature_frame(_range_candles("ETH/USDT"))
    aggregator = AlphaAggregator()

    ranked = aggregator.rank_opportunities(
        [
            AlphaContext(symbol="BTC/USDT", timeframe="1h", feature_frame=trend_frame, frame=trend_frame),
            AlphaContext(symbol="ETH/USDT", timeframe="1h", feature_frame=range_frame, frame=range_frame),
        ]
    )

    assert ranked
    assert ranked[0].symbol == "BTC/USDT"
    assert ranked[0].side == "buy"
    assert ranked[0].alpha_score > 0
    assert ranked[0].selected_models


def test_sopotek_trading_process_symbol_uses_alpha_fusion_without_signal_override():
    class DummyBroker:
        async def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
            return []

        async def fetch_balance(self):
            return {"total": {"USDT": 10000}}

        async def create_order(self, *args, **kwargs):
            return {"status": "filled"}

    controller = SimpleNamespace(
        broker=DummyBroker(),
        symbols=["BTC/USDT"],
        time_frame="1h",
        limit=96,
        strategy_name="Trend Following",
        strategy_params={},
        max_signal_agents=1,
        minimum_signal_votes=1,
        assigned_strategies_for_symbol=lambda _symbol: [
            {"strategy_name": "Trend Following", "weight": 1.0, "score": 10.0, "rank": 1}
        ],
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
    )
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    strategy = trading.strategy.get("Trend Following")
    strategy.min_confidence = 0.0
    strategy.ema_fast = 12
    strategy.ema_slow = 26
    strategy.atr_period = 10
    strategy.breakout_lookback = 20

    dataset = SymbolDatasetSnapshot(
        symbol="BTC/USDT",
        timeframe="1h",
        exchange="paper",
        source="test",
        frame=FeaturePipeline().normalize_candles(_trend_candles()),
        metadata={},
    )
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "reason": "submitted"}

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="1h", limit=96, publish_debug=False))

    assert result["status"] == "filled"
    assert captured["symbol"] == "BTC/USDT"
    assert captured["strategy_name"] == "Trend Following"
    assert captured["alpha_models"]
    assert captured["expected_return"] > 0
    assert captured["risk_estimate"] > 0
