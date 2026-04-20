from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clamp_confidence(value) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = 0.0
    return max(0.0, min(1.0, numeric))


@dataclass
class ReasoningResult:
    decision: str = "NEUTRAL"
    confidence: float = 0.0
    reasoning: str = ""
    risk: str = "Unknown"
    warnings: list[str] = field(default_factory=list)
    provider: str = "heuristic"
    mode: str = "assistive"
    should_execute: bool = True
    latency_ms: float = 0.0
    prompt_version: str = "sopotek-reasoning-v1"
    fallback_used: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.decision = str(self.decision or "NEUTRAL").strip().upper() or "NEUTRAL"
        self.confidence = _clamp_confidence(self.confidence)
        self.reasoning = str(self.reasoning or "").strip()
        self.risk = str(self.risk or "Unknown").strip() or "Unknown"
        self.provider = str(self.provider or "heuristic").strip() or "heuristic"
        self.mode = str(self.mode or "assistive").strip().lower() or "assistive"
        self.should_execute = bool(self.should_execute)
        self.latency_ms = max(0.0, float(self.latency_ms or 0.0))
        self.prompt_version = str(self.prompt_version or "sopotek-reasoning-v1").strip() or "sopotek-reasoning-v1"
        self.warnings = [str(item).strip() for item in list(self.warnings or []) if str(item).strip()]
        self.payload = dict(self.payload or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk": self.risk,
            "warnings": list(self.warnings),
            "provider": self.provider,
            "mode": self.mode,
            "should_execute": self.should_execute,
            "latency_ms": self.latency_ms,
            "prompt_version": self.prompt_version,
            "fallback_used": self.fallback_used,
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_payload(cls, payload, **overrides):
        data = dict(payload or {})
        data.update(overrides)
        return cls(
            decision=data.get("decision", "NEUTRAL"),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            risk=data.get("risk", "Unknown"),
            warnings=data.get("warnings", []),
            provider=data.get("provider", "heuristic"),
            mode=data.get("mode", "assistive"),
            should_execute=data.get("should_execute", True),
            latency_ms=data.get("latency_ms", 0.0),
            prompt_version=data.get("prompt_version", "sopotek-reasoning-v1"),
            fallback_used=data.get("fallback_used", False),
            payload=data.get("payload", {}),
        )
