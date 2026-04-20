from quant.signal_engine import SignalEngine
from strategy.strategy_registry import StrategyRegistry


def _sample_candles():
    base = 1700000000000
    candles = []
    close = 100.0
    for index in range(96):
        drift = 0.18 if index < 70 else 0.44
        seasonal = ((index % 7) - 3) * 0.03
        close = max(10.0, close + drift + seasonal)
        open_ = close - (0.20 if index % 3 else -0.08)
        high = max(open_, close) + 0.40 + (0.02 * (index % 4))
        low = min(open_, close) - 0.32
        volume = 12 + index + (6 if index >= 70 else 0)
        candles.append([base + index * 3600000, open_, high, low, close, volume])
    return candles


def test_signal_engine_adds_regime_and_engine_metadata():
    registry = StrategyRegistry()
    strategy = registry.get("Trend Following")
    strategy.rsi_period = 10
    strategy.breakout_lookback = 20
    strategy.ema_fast = 12
    strategy.ema_slow = 26
    strategy.atr_period = 10
    strategy.min_confidence = 0.0

    engine = SignalEngine(registry)
    signal = engine.generate_signal(
        candles=_sample_candles(),
        strategy_name="Trend Following",
        symbol="BTC/USDT",
    )

    assert signal is not None
    assert signal["side"] == "buy"
    assert signal["symbol"] == "BTC/USDT"
    assert signal["regime"] in {"trending", "mean_reverting", "high_volatility", "low_liquidity"}
    assert signal["signal_engine_version"] == "signal-engine-v2"
    assert signal["expected_return"] > 0
    assert signal["risk_estimate"] > 0
    assert signal["alpha_score"] > 0
    assert signal["alpha_models"]
    assert "primary" in signal["regime_snapshot"]
