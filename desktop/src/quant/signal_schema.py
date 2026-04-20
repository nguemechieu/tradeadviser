from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignalDecision:
    """A normalized signal decision payload for trading and scoring.

    Attributes:
        side: The trading direction, e.g. "buy" or "sell".
        amount: The proposed trade size amount.
        confidence: The signal confidence score.
        reason: A human-readable explanation for the signal.
        price: Optional execution price for the signal.
        regime: Market regime label assigned by the signal engine.
        feature_version: Feature pipeline version metadata.
        metadata: Additional arbitrary metadata to include in the payload.
    """
    side: str
    amount: float
    confidence: float
    reason: str
    price: float | None = None
    regime: str = "unknown"
    feature_version: str = "quant-v1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the signal decision to a normalized dictionary."""
        payload = {
            "side": str(self.side or "").lower(),
            "amount": float(self.amount or 0.0),
            "confidence": float(self.confidence or 0.0),
            "reason": str(self.reason or "").strip(),
            "regime": str(self.regime or "unknown"),
            "feature_version": str(self.feature_version or "quant-v1"),
        }
        if self.price is not None:
            payload["price"] = float(self.price)
        if self.metadata:
            payload.update(dict(self.metadata))
        return payload
