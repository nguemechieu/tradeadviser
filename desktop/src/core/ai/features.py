from __future__ import annotations

import numpy as np

from ...models.candle import Candle

def build_features(candles: list[Candle]) -> np.ndarray:
    """Create a compact feature vector from recent candle data for use by AI models. Summarizes
    the latest price, recent volatility, short-term momentum, and average trading range.

    The function looks back over the most recent candles, computes simple derived statistics, and
    packs them into a fixed-length NumPy array suitable for model input. It assumes the input
    candles are ordered in time and represent a contiguous price history.

    Args:
        candles: A time-ordered list of Candle objects containing at least close, high, and low
            prices from which to derive features.

    Returns:
        np.ndarray: A 1D array containing the latest close, volatility estimate, momentum, and
            average high-low range.
    """
    closes = np.array([c.close for c in candles[-20:]])
    highs = np.array([c.high for c in candles[-20:]])
    lows = np.array([c.low for c in candles[-20:]])

    returns = np.diff(closes) / closes[:-1]

    volatility = np.std(returns)
    momentum = closes[-1] - closes[0]
    range_mean = np.mean(highs - lows)

    return np.array([
        closes[-1],
        volatility,
        momentum,
        range_mean,
    ])