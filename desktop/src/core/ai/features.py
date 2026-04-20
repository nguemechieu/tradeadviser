import numpy as np
from models.candle import Candle


def build_features(candles: list[Candle]) -> np.ndarray:
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