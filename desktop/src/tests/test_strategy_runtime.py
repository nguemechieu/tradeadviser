import pandas as pd

from strategy.strategy import Strategy
from strategy.strategy_registry import StrategyRegistry


def test_compute_features_returns_empty_frame_for_invalid_candles():
    strategy = Strategy()

    df = strategy.compute_features([{"bad": "shape"}, ["too", "short"]])

    assert df.empty
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


def test_generate_signal_skips_short_ohlcv_history():
    strategy = Strategy()
    candles = [
        [1700000000000 + i * 3600000, 100 + i, 101 + i, 99 + i, 100.5 + i, 10 + i]
        for i in range(10)
    ]

    assert strategy.generate_signal(candles) is None


def test_strategy_registry_can_switch_active_strategy():
    registry = StrategyRegistry()

    registry.set_active("Mean Reversion")

    resolved = registry._resolve_strategy()

    assert resolved.strategy_name == "Mean Reversion"


def test_strategy_registry_includes_expanded_strategy_library():
    registry = StrategyRegistry()

    available = set(registry.list())

    assert {
        "Trend Following",
        "Mean Reversion",
        "Breakout",
        "AI Hybrid",
        "EMA Cross",
        "Momentum Continuation",
        "Pullback Trend",
        "Volatility Breakout",
        "MACD Trend",
        "Range Fade",
        "Donchian Trend",
        "Bollinger Squeeze",
        "ATR Compression Breakout",
        "RSI Failure Swing",
        "Volume Spike Reversal",
    }.issubset(available)
    assert len(available) >= 6100
    assert "Trend Following | Scalp Conservative" in available
    assert "Trend Following | Scalp Conservative FX Core" in available
    assert "Trend Following | Scalp Conservative Equities Macro" in available
    assert "AI Hybrid | Institutional Prime" in available


def test_strategy_registry_lazily_instantiates_variants():
    registry = StrategyRegistry()

    assert registry.strategies == {}

    selected = registry.get("Trend Following | Scalp Conservative Equities Macro")

    assert selected is not None
    assert selected.strategy_name == "Trend Following | Scalp Conservative Equities Macro"
    assert len(registry.strategies) == 1


def test_strategy_variant_names_resolve_to_base_signal_family():
    resolved = Strategy.resolve_signal_strategy_name("EMA Cross | London Session Aggressive")

    assert resolved == "EMA Cross"


def test_strategy_registry_applies_variant_parameters():
    registry = StrategyRegistry()

    strategy = registry.get("Trend Following | Scalp Conservative")

    assert strategy is not None
    assert strategy.strategy_name == "Trend Following | Scalp Conservative"
    assert strategy.ema_fast == 8
    assert strategy.ema_slow == 21
    assert strategy.min_confidence == 0.64
    assert strategy.signal_amount == 0.50


def test_breakout_strategy_generates_buy_signal_on_range_break():
    strategy = Strategy(strategy_name="Breakout")
    strategy.rsi_period = 2
    strategy.breakout_lookback = 5
    strategy.ema_fast = 3
    strategy.ema_slow = 5
    strategy.atr_period = 2

    candles = []
    base = 1700000000000
    rows = [
        (100, 101, 99, 100.0),
        (100, 101, 99.5, 100.3),
        (100.2, 101.2, 99.8, 100.6),
        (100.4, 101.4, 100.0, 100.9),
        (100.8, 101.6, 100.4, 101.1),
        (101.2, 105.0, 101.0, 104.8),
    ]
    for index, (open_, high, low, close) in enumerate(rows):
        candles.append([base + index * 3600000, open_, high, low, close, 10 + index])

    signal = strategy.generate_signal(candles)

    assert signal is not None
    assert signal["side"] == "buy"


def test_ema_cross_strategy_generates_buy_signal_on_bullish_cross():
    strategy = Strategy(strategy_name="EMA Cross")
    strategy.rsi_period = 2
    strategy.ema_fast = 2
    strategy.ema_slow = 4
    strategy.atr_period = 2

    candles = []
    base = 1700000000000
    closes = [105.0, 104.0, 103.0, 102.0, 103.0, 104.5]
    prev_close = closes[0]
    for index, close in enumerate(closes):
        open_ = prev_close
        high = max(open_, close) + 0.6
        low = min(open_, close) - 0.6
        candles.append([base + index * 3600000, open_, high, low, close, 10 + index])
        prev_close = close

    signal = strategy.generate_signal(candles)

    assert signal is not None
    assert signal["side"] == "buy"
    assert "EMA fast crossed above EMA slow" in signal["reason"]


def test_bollinger_squeeze_strategy_generates_buy_signal_after_compression_breakout():
    strategy = Strategy(strategy_name="Bollinger Squeeze")
    feature_frame = pd.DataFrame(
        [
            {
                "close": 100.0,
                "rsi": 49.0,
                "ema_fast": 100.1,
                "ema_slow": 100.0,
                "upper_band": 101.5,
                "lower_band": 98.7,
                "breakout_high": 100.8,
                "breakout_low": 98.9,
                "volume_ratio": 0.98,
                "momentum": 0.0,
                "pullback_gap": 0.0,
                "atr_pct": 0.012,
                "trend_strength": 0.001,
                "band_position": 0.52,
                "macd_line": 0.02,
                "macd_signal": 0.01,
                "regime": "range",
            },
            {
                "close": 102.6,
                "rsi": 61.0,
                "ema_fast": 101.8,
                "ema_slow": 100.9,
                "upper_band": 103.2,
                "lower_band": 99.8,
                "breakout_high": 101.0,
                "breakout_low": 98.9,
                "volume_ratio": 1.22,
                "momentum": 0.021,
                "pullback_gap": 0.3,
                "atr_pct": 0.018,
                "trend_strength": 0.009,
                "band_position": 0.92,
                "macd_line": 0.35,
                "macd_signal": 0.18,
                "regime": "trending_up",
            },
        ]
    )

    signal = strategy.generate_signal_from_features(feature_frame)

    assert signal is not None
    assert signal["side"] == "buy"
    assert "Bollinger squeeze expansion resolved upward" in signal["reason"]


def test_adaptive_momentum_pullback_generates_buy_signal_after_row_initialization():
    strategy = Strategy(strategy_name="Adaptive Momentum Pullback")
    feature_frame = pd.DataFrame(
        [
            {
                "close": 100.0,
                "rsi": 48.0,
                "ema_fast": 99.8,
                "ema_slow": 100.0,
                "upper_band": 101.0,
                "lower_band": 99.0,
                "breakout_high": 100.8,
                "breakout_low": 99.1,
                "volume_ratio": 0.96,
                "momentum": 0.001,
                "pullback_gap": 0.1,
                "atr_pct": 0.011,
                "trend_strength": 0.003,
                "band_position": 0.54,
                "macd_line": 0.01,
                "macd_signal": 0.0,
                "regime": "range",
            },
            {
                "close": 102.1,
                "rsi": 59.0,
                "ema_fast": 101.6,
                "ema_slow": 100.8,
                "upper_band": 103.0,
                "lower_band": 99.7,
                "breakout_high": 101.0,
                "breakout_low": 99.0,
                "volume_ratio": 1.18,
                "momentum": 0.012,
                "pullback_gap": 0.24,
                "atr_pct": 0.016,
                "trend_strength": 0.009,
                "band_position": 0.84,
                "macd_line": 0.22,
                "macd_signal": 0.12,
                "regime": "trending_up",
            },
        ]
    )

    signal = strategy.generate_signal_from_features(feature_frame)

    assert signal is not None
    assert signal["side"] == "buy"
    assert "Adaptive momentum pullback in uptrend" in signal["reason"]


def test_atr_compression_breakout_generates_sell_signal_on_volatility_release():
    strategy = Strategy(strategy_name="ATR Compression Breakout")
    feature_frame = pd.DataFrame(
        [
            {
                "close": 100.0,
                "rsi": 50.0,
                "ema_fast": 99.7,
                "ema_slow": 100.0,
                "upper_band": 101.2,
                "lower_band": 98.8,
                "breakout_high": 101.0,
                "breakout_low": 99.1,
                "volume_ratio": 0.94,
                "momentum": -0.002,
                "pullback_gap": -0.1,
                "atr_pct": 0.014,
                "trend_strength": 0.002,
                "band_position": 0.48,
                "macd_line": -0.02,
                "macd_signal": -0.01,
                "regime": "range",
            },
            {
                "close": 97.8,
                "rsi": 39.0,
                "ema_fast": 98.8,
                "ema_slow": 99.6,
                "upper_band": 100.9,
                "lower_band": 97.4,
                "breakout_high": 100.8,
                "breakout_low": 98.9,
                "volume_ratio": 1.18,
                "momentum": -0.028,
                "pullback_gap": -0.5,
                "atr_pct": 0.018,
                "trend_strength": 0.008,
                "band_position": 0.11,
                "macd_line": -0.24,
                "macd_signal": -0.13,
                "regime": "trending_down",
            },
        ]
    )

    signal = strategy.generate_signal_from_features(feature_frame)

    assert signal is not None
    assert signal["side"] == "sell"
    assert "ATR compression released into bearish breakout expansion" in signal["reason"]


def test_volume_spike_reversal_strategy_generates_sell_signal_on_exhaustion():
    strategy = Strategy(strategy_name="Volume Spike Reversal")
    feature_frame = pd.DataFrame(
        [
            {
                "close": 100.0,
                "rsi": 59.0,
                "ema_fast": 99.9,
                "ema_slow": 99.8,
                "upper_band": 101.0,
                "lower_band": 99.0,
                "breakout_high": 100.8,
                "breakout_low": 99.2,
                "volume_ratio": 1.02,
                "momentum": 0.003,
                "pullback_gap": 0.1,
                "atr_pct": 0.011,
                "trend_strength": 0.004,
                "band_position": 0.75,
                "macd_line": 0.04,
                "macd_signal": 0.03,
                "regime": "range",
            },
            {
                "close": 99.1,
                "rsi": 66.0,
                "ema_fast": 99.4,
                "ema_slow": 99.2,
                "upper_band": 100.7,
                "lower_band": 98.9,
                "breakout_high": 100.8,
                "breakout_low": 99.0,
                "volume_ratio": 1.48,
                "momentum": -0.014,
                "pullback_gap": -0.2,
                "atr_pct": 0.012,
                "trend_strength": 0.006,
                "band_position": 0.95,
                "macd_line": 0.02,
                "macd_signal": 0.04,
                "regime": "range",
            },
        ]
    )

    signal = strategy.generate_signal_from_features(feature_frame)

    assert signal is not None
    assert signal["side"] == "sell"
    assert "Volume spike reversal from upper band exhaustion" in signal["reason"]
