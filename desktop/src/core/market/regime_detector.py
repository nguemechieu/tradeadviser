from dataclasses import dataclass
from typing import List
import numpy as np

from models.candle import Candle


@dataclass(slots=True)
class MarketRegime:
    name: str  # "TRENDING", "RANGING", "VOLATILE"
    confidence: float


class MarketRegimeDetector:
    def __init__(self):
        self.window = 50

    def detect(self, candles: List[Candle]) -> MarketRegime:
        if len(candles) < 10:
            return MarketRegime("UNKNOWN", 0.0)

        closes = np.array([c.close for c in candles[-self.window:]])
        returns = np.diff(closes) / closes[:-1]

        volatility = np.std(returns)
        trend = self._trend_strength(closes)

        # =========================
        # Regime logic
        # =========================
        if volatility > 0.02:
            return MarketRegime("VOLATILE", min(volatility * 10, 1.0))

        if trend > 0.6:
            return MarketRegime("TRENDING", trend)

        return MarketRegime("RANGING", 1.0 - trend)

    # =========================
    # Trend strength (0 → 1)
    # =========================
    def _trend_strength(self, prices: np.ndarray) -> float:
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]

        normalized = abs(slope) / (np.mean(prices) + 1e-9)
        return float(min(normalized * 100, 1.0))