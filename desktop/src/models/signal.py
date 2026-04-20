# src/core/models.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import time

from enum import Enum


class SignalStatus(str, Enum):
    CREATED = "CREATED"        # Signal just generated
    VALIDATED = "VALIDATED"    # Passed validation checks
    REJECTED = "REJECTED"      # Failed validation (risk, rules)

    QUEUED = "QUEUED"          # Waiting for execution
    EXECUTING = "EXECUTING"    # Order being placed

    FILLED = "FILLED"          # Order executed successfully
    PARTIALLY_FILLED = "PARTIALLY_FILLED"

    CANCELLED = "CANCELLED"    # Cancelled before execution
    FAILED = "FAILED"          # Execution error

    CLOSED = "CLOSED"          # Trade closed (TP/SL hit)
@dataclass(slots=True)
class Signal:
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"

    price: float
    confidence: float = 0.0  # 0 → 1

    strategy: Optional[str] = None
    timeframe: Optional[str] = None

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    timestamp: float = field(default_factory=lambda: time.time())

    # =========================
    # Helpers
    # =========================
    @property
    def is_buy(self) -> bool:
        return self.action.upper() == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.action.upper() == "SELL"

    @property
    def risk_reward_ratio(self) -> Optional[float]:
        if self.stop_loss is None or self.take_profit is None:
            return None
        risk = abs(self.price - self.stop_loss)
        reward = abs(self.take_profit - self.price)
        if risk == 0:
            return None
        return reward / risk

    def is_valid(self) -> bool:
        return (
                self.symbol is not None and
                self.action in {"BUY", "SELL", "HOLD"} and
                self.price > 0 and
                0.0 <= self.confidence <= 1.0
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "price": self.price,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "timeframe": self.timeframe,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        return cls(
            symbol=data["symbol"],
            action=data["action"],
            price=float(data["price"]),
            confidence=float(data.get("confidence", 0)),
            strategy=data.get("strategy"),
            timeframe=data.get("timeframe"),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            metadata=data.get("metadata", {}),
            timestamp=float(data.get("timestamp", time.time())),
        )