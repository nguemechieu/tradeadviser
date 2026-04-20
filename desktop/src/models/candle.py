from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass(slots=True)
class Candle:
    symbol: str
    timeframe: str  # "1m", "5m", "1h", etc.

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    timestamp: float = field(default_factory=lambda: time.time())

    # =========================
    # Derived Metrics
    # =========================
    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    # =========================
    # Validation
    # =========================
    def is_valid(self) -> bool:
        return (
                self.low <= self.open <= self.high and
                self.low <= self.close <= self.high and
                self.volume >= 0
        )

    # =========================
    # Serialization
    # =========================
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Candle":
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data.get("volume", 0)),
            timestamp=float(data.get("timestamp", time.time())),
        )