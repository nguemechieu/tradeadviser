from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time

from models.signal import Signal


@dataclass(slots=True)
class ReasoningDecision:
    signal: Signal

    decision: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0 → 1

    # =========================
    # Core reasoning
    # =========================
    reasons: List[str] = field(default_factory=list)
    factors: Dict[str, float] = field(default_factory=dict)

    # =========================
    # Context (NEW 🔥)
    # =========================
    strategy_name: Optional[str] = None
    model_name: Optional[str] = None

    market_regime: Optional[str] = None
    regime_confidence: Optional[float] = None

    conflict_penalty: Optional[float] = None
    vote_margin: Optional[float] = None

    ai_override: Optional[bool] = None

    # =========================
    # Risk + metadata
    # =========================
    risk_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    timestamp: float = field(default_factory=lambda: time.time())

    # =========================
    # Helpers
    # =========================
    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.75

    @property
    def is_actionable(self) -> bool:
        return self.decision in {"BUY", "SELL"} and self.confidence > 0.5

    @property
    def is_ai_driven(self) -> bool:
        return bool(self.ai_override)

    def summary(self) -> str:
        return (
            f"{self.decision} {self.signal.symbol} @ {self.signal.price} "
            f"(confidence={self.confidence:.2f})"
        )

    def explain(self) -> str:
        lines = [
            f"Decision: {self.decision}",
            f"Confidence: {self.confidence:.2f}",
        ]

        if self.market_regime:
            lines.append(f"Market Regime: {self.market_regime}")

        if self.regime_confidence is not None:
            lines.append(f"Regime Confidence: {self.regime_confidence:.2f}")

        if self.strategy_name:
            lines.append(f"Strategy: {self.strategy_name}")

        if self.model_name:
            lines.append(f"Model: {self.model_name}")

        if self.ai_override:
            lines.append("⚠ AI Override Applied")

        if self.conflict_penalty is not None:
            lines.append(f"Conflict Penalty: {self.conflict_penalty:.2f}")

        if self.vote_margin is not None:
            lines.append(f"Vote Margin: {self.vote_margin:.2f}")

        if self.risk_score is not None:
            lines.append(f"Risk Score: {self.risk_score:.2f}")

        if self.reasons:
            lines.append("Reasons:")
            lines.extend(f"  - {r}" for r in self.reasons)

        if self.factors:
            lines.append("Factors:")
            for k, v in self.factors.items():
                lines.append(f"  - {k}: {v:.4f}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "signal": self.signal.to_dict(),
            "decision": self.decision,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "factors": self.factors,
            "strategy_name": self.strategy_name,
            "model_name": self.model_name,
            "market_regime": self.market_regime,
            "regime_confidence": self.regime_confidence,
            "conflict_penalty": self.conflict_penalty,
            "vote_margin": self.vote_margin,
            "ai_override": self.ai_override,
            "risk_score": self.risk_score,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReasoningDecision":
        return cls(
            signal=Signal.from_dict(data["signal"]),
            decision=data["decision"],
            confidence=float(data["confidence"]),
            reasons=data.get("reasons", []),
            factors=data.get("factors", {}),
            strategy_name=data.get("strategy_name"),
            model_name=data.get("model_name"),
            market_regime=data.get("market_regime"),
            regime_confidence=data.get("regime_confidence"),
            conflict_penalty=data.get("conflict_penalty"),
            vote_margin=data.get("vote_margin"),
            ai_override=data.get("ai_override"),
            risk_score=data.get("risk_score"),
            metadata=data.get("metadata", {}),
            timestamp=float(data.get("timestamp", time.time())),
        )