from __future__ import annotations

from collections.abc import Sequence
from math import nan
from typing import Any

import pandas as pd

from derivatives.core.live_market_cache import LiveMarketCache




FEATURE_COLUMNS = [
    "close",
    "ema_fast",
    "ema_slow",
    "ema_gap",
    "rsi",
    "atr",
    "volatility",
    "momentum_3",
    "momentum_10",
    "return_1",
    "return_5",
    "orderbook_imbalance",
]


def compute_ema(values: Sequence[float], *, span: int = 14) -> pd.Series:
    return pd.Series(list(values), dtype=float).ewm(span=span, adjust=False).mean()


def compute_rsi(values: Sequence[float], *, period: int = 14) -> pd.Series:
    close = pd.Series(list(values), dtype=float)
    delta = close.diff().fillna(0.0)
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    avg_gain = gains.rolling(period, min_periods=max(2, period // 2)).mean()
    avg_loss = losses.rolling(period, min_periods=max(2, period // 2)).mean()
    rs = avg_gain / avg_loss.replace(0.0, nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(~((avg_loss <= 1e-12) & (avg_gain > 0.0)), 100.0)
    rsi = rsi.where(~((avg_gain <= 1e-12) & (avg_loss > 0.0)), 0.0)
    return rsi.fillna(50.0)


def compute_atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], *, period: int = 14) -> pd.Series:
    high = pd.Series(list(highs), dtype=float)
    low = pd.Series(list(lows), dtype=float)
    close = pd.Series(list(closes), dtype=float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            (high - low).abs(),
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period, min_periods=max(2, period // 2)).mean().fillna(0.0)


def compute_volatility(values: Sequence[float], *, window: int = 20) -> pd.Series:
    close = pd.Series(list(values), dtype=float)
    return close.pct_change().rolling(window, min_periods=max(3, window // 2)).std(ddof=0).fillna(0.0)


def build_feature_frame(
    data: pd.DataFrame,
    *,
    fast_window: int = 8,
    slow_window: int = 21,
    rsi_window: int = 14,
    atr_window: int = 14,
    vol_window: int = 20,
) -> pd.DataFrame:
    frame = pd.DataFrame(data).copy()
    if frame.empty:
        return frame

    required = {"close", "high", "low"}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"Missing required columns for feature engineering: {sorted(missing)}")

    if "open" not in frame.columns:
        frame["open"] = frame["close"]
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    if "orderbook_imbalance" not in frame.columns:
        frame["orderbook_imbalance"] = 0.0

    for column in ("open", "high", "low", "close", "volume", "orderbook_imbalance"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    close = frame["close"].astype(float)
    frame["return_1"] = close.pct_change().fillna(0.0)
    frame["return_5"] = close.pct_change(5).fillna(0.0)
    frame["ema_fast"] = compute_ema(close, span=fast_window)
    frame["ema_slow"] = compute_ema(close, span=slow_window)
    frame["ema_gap"] = ((frame["ema_fast"] - frame["ema_slow"]) / frame["ema_slow"].replace(0.0, nan)).fillna(0.0)
    frame["rsi"] = compute_rsi(close, period=rsi_window)
    frame["atr"] = compute_atr(frame["high"], frame["low"], close, period=atr_window)
    frame["volatility"] = compute_volatility(close, window=vol_window)
    frame["momentum_3"] = close.diff(3).fillna(0.0)
    frame["momentum_10"] = close.diff(10).fillna(0.0)
    return frame


def build_feature_vector(symbol: str, cache: LiveMarketCache) -> dict[str, float]:
    prices = cache.price_series(symbol)
    if len(prices) < 5:
        latest = float(prices[-1]) if prices else 0.0
        return {
            "close": latest,
            "ema_fast": latest,
            "ema_slow": latest,
            "ema_gap": 0.0,
            "rsi": 50.0,
            "atr": 0.0,
            "volatility": 0.0,
            "momentum_3": 0.0,
            "momentum_10": 0.0,
            "return_1": 0.0,
            "return_5": 0.0,
            "orderbook_imbalance": cache.orderbook_imbalance(symbol),
        }

    frame = build_feature_frame(
        pd.DataFrame(
            {
                "open": prices,
                "high": cache.high_series(symbol) or prices,
                "low": cache.low_series(symbol) or prices,
                "close": prices,
                "volume": cache.volume_series(symbol) or [0.0] * len(prices),
                "orderbook_imbalance": [cache.orderbook_imbalance(symbol)] * len(prices),
            }
        )
    )
    row = frame.iloc[-1]
    return {column: float(row.get(column, 0.0) or 0.0) for column in FEATURE_COLUMNS}
