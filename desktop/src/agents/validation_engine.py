from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


from core.ai.reasoning.reasoning_decision import ReasoningDecision
from core.models import Signal, SignalStatus

def _clamp_confidence(value: float) -> float:
    return max(0.0, min(0.99, float(value or 0.0)))


@dataclass(slots=True)
class ValidationResult:
    validated_signals: list[Signal] = field(default_factory=list)
    filtered_signals: list[Signal] = field(default_factory=list)
    model_probability: float | None = None
    notes: list[str] = field(default_factory=list)


class ValidationEngine:
    """Applies ML and LLM validation before weighted voting takes place."""

    def __init__(
        self,
        *,
        ml_reject_threshold: float = 0.40,
        ml_reduce_threshold: float = 0.70,
    ) -> None:
        self.ml_reject_threshold = max(0.0, min(1.0, float(ml_reject_threshold)))
        self.ml_reduce_threshold = max(self.ml_reject_threshold, min(1.0, float(ml_reduce_threshold)))

    def validate(
        self,
        *,
        symbol: str,
        signals: list[Signal],
        feature_context: dict[str, float],
        minimum_confidence: float,
        model_probability: float | None,
        reasoning_lookup: Callable[[str, str], ReasoningDecision | None],
        reasoning_contributor: Callable[[str, str, str, ReasoningDecision | None], dict[str, Any]],
        reasoning_metadata: Callable[[ReasoningDecision | None, dict[str, Any]], dict[str, Any] | None],
    ) -> ValidationResult:
        result = ValidationResult(model_probability=model_probability)
        for signal in list(signals or []):
            working = signal.transition(
                stage="validation_start",
                metadata={"features": dict(feature_context or {})},
                note=f"Validation started for {signal.strategy_name}",
            )
            if float(working.confidence or 0.0) < float(minimum_confidence):
                result.filtered_signals.append(
                    working.transition(
                        stage="validation_confidence_filter",
                        status=SignalStatus.FILTERED,
                        note=f"Confidence below profile threshold {minimum_confidence:.2f}",
                        metadata={"validation_reason": "profile_confidence_threshold"},
                    )
                )
                continue

            if model_probability is not None:
                working = working.transition(
                    stage="validation_ml_score",
                    metadata={"model_probability": model_probability},
                    note=f"ML probability scored at {model_probability:.2f}",
                )
                if model_probability < self.ml_reject_threshold:
                    result.filtered_signals.append(
                        working.transition(
                            stage="validation_ml_reject",
                            status=SignalStatus.FILTERED,
                            note=f"ML rejected the signal at probability {model_probability:.2f}",
                            metadata={"validation_reason": "ml_reject"},
                        )
                    )
                    continue
                if model_probability < self.ml_reduce_threshold:
                    reduced_confidence = _clamp_confidence(min(working.confidence, model_probability))
                    working = working.transition(
                        stage="validation_ml_reduce",
                        confidence=reduced_confidence,
                        note=f"ML reduced confidence to {reduced_confidence:.2f}",
                        metadata={"validation_reason": "ml_reduce"},
                    )
                else:
                    boosted_confidence = _clamp_confidence(max(working.confidence, (working.confidence + model_probability) / 2.0))
                    working = working.transition(
                        stage="validation_ml_confirm",
                        confidence=boosted_confidence,
                        note=f"ML confirmed the signal at {model_probability:.2f}",
                        metadata={"validation_reason": "ml_confirm"},
                    )

            seed = reasoning_lookup(symbol, working.strategy_name)
            contribution = reasoning_contributor(symbol, working.strategy_name, working.side, seed)
            contribution_payload = reasoning_metadata(seed, contribution) or {}
            if contribution.get("skip_reason"):
                result.filtered_signals.append(
                    working.transition(
                        stage="validation_llm_reject",
                        status=SignalStatus.FILTERED,
                        note=str(contribution.get("skip_reason") or "LLM rejected the signal"),
                        metadata={
                            "validation_reason": "llm_reject",
                            "reasoning_contribution": contribution_payload,
                        },
                    )
                )
                continue

            confidence_delta = float(contribution.get("confidence_delta") or 0.0)
            quantity_multiplier = float(contribution.get("quantity_multiplier") or 1.0)
            next_confidence = _clamp_confidence(working.confidence + confidence_delta)
            if quantity_multiplier < 1.0:
                next_confidence = _clamp_confidence(next_confidence * max(quantity_multiplier, 0.5))
            if contribution_payload:
                working = working.transition(
                    stage="validation_llm_adjustment",
                    confidence=next_confidence,
                    note=str(contribution.get("summary") or "LLM reviewed the signal"),
                    metadata={"reasoning_contribution": contribution_payload},
                )

            result.validated_signals.append(
                working.transition(
                    stage="validated",
                    status=SignalStatus.CREATED,
                    note=f"Signal validated for decisioning by {working.strategy_name}",
                    metadata={"validation_state": "passed"},
                )
            )

        if result.validated_signals:
            result.notes.append(f"{len(result.validated_signals)} signal(s) passed validation for {symbol}.")
        if result.filtered_signals:
            result.notes.append(f"{len(result.filtered_signals)} signal(s) were filtered for {symbol}.")
        return result
