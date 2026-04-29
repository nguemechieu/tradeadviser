from __future__ import annotations

"""
InvestPro ValidationEngine

Applies pre-vote validation to strategy signals.

Responsibilities:
- profile confidence filtering
- ML probability rejection/reduction/confirmation
- reasoning/LLM contribution adjustment
- signal lifecycle transitions
- validation notes and audit metadata

This layer should run before SignalFusionEngine / DecisionEngine.
"""

import math
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

try:
    from core.ai.reasoning.reasoning_decision import ReasoningDecision
except Exception:  # pragma: no cover
    ReasoningDecision = Any  # type: ignore

try:
    from models.signal import Signal, SignalStatus
except Exception:  # pragma: no cover
    Signal = Any  # type: ignore

    class SignalStatus:  # type: ignore
        CREATED = "created"
        FILTERED = "filtered"
        REJECTED = "rejected"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return float(default)

    try:
        number = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    number = _safe_float(value, low)
    return max(low, min(high, number))


def _clamp_confidence(value: Any) -> float:
    return _clamp(value, 0.0, 0.99)


@dataclass(slots=True)
class ValidationDecision:
    strategy_name: str
    side: str
    passed: bool
    reason: str
    original_confidence: float = 0.0
    final_confidence: float = 0.0
    model_probability: float | None = None
    quantity_multiplier: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "side": self.side,
            "passed": self.passed,
            "reason": self.reason,
            "original_confidence": self.original_confidence,
            "final_confidence": self.final_confidence,
            "model_probability": self.model_probability,
            "quantity_multiplier": self.quantity_multiplier,
            "metadata": _json_safe(self.metadata),
        }


@dataclass(slots=True)
class ValidationResult:
    validated_signals: list[Any] = field(default_factory=list)
    filtered_signals: list[Any] = field(default_factory=list)
    model_probability: float | None = None
    notes: list[str] = field(default_factory=list)
    decisions: list[ValidationDecision] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_count(self) -> int:
        return len(self.validated_signals)

    @property
    def filtered_count(self) -> int:
        return len(self.filtered_signals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validated_signals": [_signal_to_dict(signal) for signal in self.validated_signals],
            "filtered_signals": [_signal_to_dict(signal) for signal in self.filtered_signals],
            "model_probability": self.model_probability,
            "notes": list(self.notes),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "metadata": _json_safe(self.metadata),
            "passed_count": self.passed_count,
            "filtered_count": self.filtered_count,
        }


class ValidationEngine:
    """Applies ML and LLM validation before weighted voting takes place."""

    def __init__(
        self,
        *,
        ml_reject_threshold: float = 0.40,
        ml_reduce_threshold: float = 0.70,
        ml_boost_cap: float = 0.12,
        reasoning_reject_on_skip: bool = True,
        min_quantity_multiplier: float = 0.25,
        max_confidence: float = 0.99,
    ) -> None:
        self.ml_reject_threshold = _clamp(ml_reject_threshold, 0.0, 1.0)
        self.ml_reduce_threshold = max(
            self.ml_reject_threshold,
            _clamp(ml_reduce_threshold, 0.0, 1.0),
        )
        self.ml_boost_cap = _clamp(ml_boost_cap, 0.0, 1.0)
        self.reasoning_reject_on_skip = bool(reasoning_reject_on_skip)
        self.min_quantity_multiplier = _clamp(
            min_quantity_multiplier, 0.0, 1.0)
        self.max_confidence = _clamp(max_confidence, 0.01, 1.0)

        self.total_validations = 0
        self.total_passed = 0
        self.total_filtered = 0
        self.last_result: ValidationResult | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        *,
        symbol: str,
        signals: list[Any],
        feature_context: dict[str, float] | None,
        minimum_confidence: float,
        model_probability: float | None,
        reasoning_lookup: Callable[[str, str], ReasoningDecision | None],
        reasoning_contributor: Callable[[str, str, str, ReasoningDecision | None], dict[str, Any]],
        reasoning_metadata: Callable[[ReasoningDecision | None, dict[str, Any]], dict[str, Any] | None],
    ) -> ValidationResult:
        normalized_symbol = str(symbol or "").strip().upper()
        features = dict(feature_context or {})
        minimum_confidence_value = _clamp(minimum_confidence, 0.0, 1.0)
        normalized_probability = self._normalize_probability(model_probability)

        result = ValidationResult(
            model_probability=normalized_probability,
            metadata={
                "symbol": normalized_symbol,
                "minimum_confidence": minimum_confidence_value,
                "ml_reject_threshold": self.ml_reject_threshold,
                "ml_reduce_threshold": self.ml_reduce_threshold,
                "started_at": _utc_now(),
                "input_count": len(list(signals or [])),
            },
        )

        for signal in list(signals or []):
            decision = self._validate_one(
                symbol=normalized_symbol,
                signal=signal,
                feature_context=features,
                minimum_confidence=minimum_confidence_value,
                model_probability=normalized_probability,
                reasoning_lookup=reasoning_lookup,
                reasoning_contributor=reasoning_contributor,
                reasoning_metadata=reasoning_metadata,
            )

            result.decisions.append(decision["decision"])

            if decision["passed"]:
                result.validated_signals.append(decision["signal"])
            else:
                result.filtered_signals.append(decision["signal"])

        if result.validated_signals:
            result.notes.append(
                f"{len(result.validated_signals)} signal(s) passed validation for {normalized_symbol}."
            )

        if result.filtered_signals:
            result.notes.append(
                f"{len(result.filtered_signals)} signal(s) were filtered for {normalized_symbol}."
            )

        if not result.validated_signals and list(signals or []):
            result.notes.append(
                f"No signal passed validation for {normalized_symbol}.")

        result.metadata["completed_at"] = _utc_now()
        result.metadata["passed_count"] = result.passed_count
        result.metadata["filtered_count"] = result.filtered_count

        self.total_validations += 1
        self.total_passed += result.passed_count
        self.total_filtered += result.filtered_count
        self.last_result = result

        return result

    # ------------------------------------------------------------------
    # Per-signal validation
    # ------------------------------------------------------------------

    def _validate_one(
        self,
        *,
        symbol: str,
        signal: Any,
        feature_context: dict[str, float],
        minimum_confidence: float,
        model_probability: float | None,
        reasoning_lookup: Callable[[str, str], ReasoningDecision | None],
        reasoning_contributor: Callable[[str, str, str, ReasoningDecision | None], dict[str, Any]],
        reasoning_metadata: Callable[[ReasoningDecision | None, dict[str, Any]], dict[str, Any] | None],
    ) -> dict[str, Any]:
        strategy_name = self._strategy_name(signal)
        side = self._side(signal)
        original_confidence = _clamp(
            self._confidence(signal), 0.0, self.max_confidence)

        working = self._transition(
            signal,
            stage="validation_start",
            metadata={
                "features": dict(feature_context or {}),
                "validation_started_at": _utc_now(),
            },
            note=f"Validation started for {strategy_name}",
        )

        # --------------------------------------------------------------
        # Profile confidence threshold
        # --------------------------------------------------------------
        if original_confidence < minimum_confidence:
            filtered = self._transition(
                working,
                stage="validation_confidence_filter",
                status=getattr(SignalStatus, "FILTERED", "filtered"),
                note=f"Confidence below profile threshold {minimum_confidence:.2f}",
                metadata={
                    "validation_reason": "profile_confidence_threshold",
                    "minimum_confidence": minimum_confidence,
                    "original_confidence": original_confidence,
                },
            )

            return self._decision_payload(
                signal=filtered,
                strategy_name=strategy_name,
                side=side,
                passed=False,
                reason="profile_confidence_threshold",
                original_confidence=original_confidence,
                final_confidence=self._confidence(filtered),
                model_probability=model_probability,
            )

        # --------------------------------------------------------------
        # ML probability validation
        # --------------------------------------------------------------
        if model_probability is not None:
            working = self._transition(
                working,
                stage="validation_ml_score",
                metadata={
                    "model_probability": model_probability,
                    "ml_reject_threshold": self.ml_reject_threshold,
                    "ml_reduce_threshold": self.ml_reduce_threshold,
                },
                note=f"ML probability scored at {model_probability:.2f}",
            )

            if model_probability < self.ml_reject_threshold:
                filtered = self._transition(
                    working,
                    stage="validation_ml_reject",
                    status=getattr(SignalStatus, "FILTERED", "filtered"),
                    note=f"ML rejected the signal at probability {model_probability:.2f}",
                    metadata={
                        "validation_reason": "ml_reject",
                        "model_probability": model_probability,
                    },
                )

                return self._decision_payload(
                    signal=filtered,
                    strategy_name=strategy_name,
                    side=side,
                    passed=False,
                    reason="ml_reject",
                    original_confidence=original_confidence,
                    final_confidence=self._confidence(filtered),
                    model_probability=model_probability,
                )

            if model_probability < self.ml_reduce_threshold:
                reduced_confidence = min(
                    self._confidence(working), model_probability)
                reduced_confidence = _clamp(
                    reduced_confidence, 0.0, self.max_confidence)

                working = self._transition(
                    working,
                    stage="validation_ml_reduce",
                    confidence=reduced_confidence,
                    note=f"ML reduced confidence to {reduced_confidence:.2f}",
                    metadata={
                        "validation_reason": "ml_reduce",
                        "model_probability": model_probability,
                    },
                )
            else:
                current_confidence = self._confidence(working)
                blended = (current_confidence + model_probability) / 2.0
                max_allowed = min(self.max_confidence,
                                  current_confidence + self.ml_boost_cap)
                boosted_confidence = min(
                    max(current_confidence, blended), max_allowed)

                working = self._transition(
                    working,
                    stage="validation_ml_confirm",
                    confidence=boosted_confidence,
                    note=f"ML confirmed the signal at {model_probability:.2f}",
                    metadata={
                        "validation_reason": "ml_confirm",
                        "model_probability": model_probability,
                    },
                )

        # --------------------------------------------------------------
        # Reasoning / LLM contribution
        # --------------------------------------------------------------
        seed = self._safe_reasoning_lookup(
            reasoning_lookup,
            symbol,
            strategy_name,
        )

        contribution = self._safe_reasoning_contribution(
            reasoning_contributor,
            symbol,
            strategy_name,
            side,
            seed,
        )

        contribution_payload = self._safe_reasoning_metadata(
            reasoning_metadata,
            seed,
            contribution,
        )

        skip_reason = str(contribution.get("skip_reason") or "").strip()

        if skip_reason and self.reasoning_reject_on_skip:
            filtered = self._transition(
                working,
                stage="validation_llm_reject",
                status=getattr(SignalStatus, "FILTERED", "filtered"),
                note=skip_reason or "Reasoning rejected the signal",
                metadata={
                    "validation_reason": "llm_reject",
                    "reasoning_contribution": contribution_payload,
                },
            )

            return self._decision_payload(
                signal=filtered,
                strategy_name=strategy_name,
                side=side,
                passed=False,
                reason="llm_reject",
                original_confidence=original_confidence,
                final_confidence=self._confidence(filtered),
                model_probability=model_probability,
                quantity_multiplier=_safe_float(
                    contribution.get("quantity_multiplier"), 1.0),
                metadata={"skip_reason": skip_reason},
            )

        confidence_delta = _safe_float(
            contribution.get("confidence_delta"), 0.0)
        quantity_multiplier = _safe_float(
            contribution.get("quantity_multiplier"), 1.0)
        quantity_multiplier = max(
            self.min_quantity_multiplier, min(2.0, quantity_multiplier))

        next_confidence = self._confidence(working) + confidence_delta
        next_confidence = _clamp(next_confidence, 0.0, self.max_confidence)

        if quantity_multiplier < 1.0:
            next_confidence = _clamp(
                next_confidence * quantity_multiplier, 0.0, self.max_confidence)

        if contribution_payload:
            working = self._transition(
                working,
                stage="validation_reasoning_adjustment",
                confidence=next_confidence,
                note=str(contribution.get("summary")
                         or "Reasoning reviewed the signal"),
                metadata={
                    "reasoning_contribution": contribution_payload,
                    "quantity_multiplier": quantity_multiplier,
                    "confidence_delta": confidence_delta,
                    "skip_reason": skip_reason,
                },
            )

        validated = self._transition(
            working,
            stage="validated",
            status=getattr(SignalStatus, "CREATED", "created"),
            note=f"Signal validated for decisioning by {strategy_name}",
            metadata={
                "validation_state": "passed",
                "validated_at": _utc_now(),
                "final_confidence": self._confidence(working),
                "model_probability": model_probability,
                "quantity_multiplier": quantity_multiplier,
            },
        )

        return self._decision_payload(
            signal=validated,
            strategy_name=strategy_name,
            side=side,
            passed=True,
            reason="passed",
            original_confidence=original_confidence,
            final_confidence=self._confidence(validated),
            model_probability=model_probability,
            quantity_multiplier=quantity_multiplier,
            metadata={
                "reasoning_contribution": contribution_payload,
                "confidence_delta": confidence_delta,
                "skip_reason": skip_reason,
            },
        )

    # ------------------------------------------------------------------
    # Safe reasoning callbacks
    # ------------------------------------------------------------------

    def _safe_reasoning_lookup(
        self,
        callback: Callable[[str, str], ReasoningDecision | None],
        symbol: str,
        strategy_name: str,
    ) -> ReasoningDecision | None:
        try:
            return callback(symbol, strategy_name)
        except Exception:
            return None

    def _safe_reasoning_contribution(
        self,
        callback: Callable[[str, str, str, ReasoningDecision | None], dict[str, Any]],
        symbol: str,
        strategy_name: str,
        side: str,
        seed: ReasoningDecision | None,
    ) -> dict[str, Any]:
        try:
            result = callback(symbol, strategy_name, side, seed)
            return dict(result or {}) if isinstance(result, dict) else {}
        except Exception as exc:
            return {
                "summary": f"Reasoning contributor failed: {type(exc).__name__}: {exc}",
                "confidence_delta": 0.0,
                "quantity_multiplier": 1.0,
            }

    def _safe_reasoning_metadata(
        self,
        callback: Callable[[ReasoningDecision | None, dict[str, Any]], dict[str, Any] | None],
        seed: ReasoningDecision | None,
        contribution: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            result = callback(seed, contribution)
            return dict(result or {}) if isinstance(result, dict) else {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------

    def _transition(self, signal: Any, **kwargs: Any) -> Any:
        transition = getattr(signal, "transition", None)

        if callable(transition):
            try:
                return transition(**kwargs)
            except Exception:
                pass

        # Fallback for mutable signal-like objects.
        metadata = dict(self._get(signal, "metadata", {}) or {})
        metadata.update(dict(kwargs.get("metadata") or {}))

        for key, value in {
            "stage": kwargs.get("stage"),
            "status": kwargs.get("status"),
            "confidence": kwargs.get("confidence", self._get(signal, "confidence")),
            "note": kwargs.get("note", self._get(signal, "note", self._get(signal, "reason", ""))),
            "metadata": metadata,
        }.items():
            if value is None:
                continue
            try:
                setattr(signal, key, value)
            except Exception:
                pass

        return signal

    def _decision_payload(
        self,
        *,
        signal: Any,
        strategy_name: str,
        side: str,
        passed: bool,
        reason: str,
        original_confidence: float,
        final_confidence: float,
        model_probability: float | None,
        quantity_multiplier: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = ValidationDecision(
            strategy_name=strategy_name,
            side=side,
            passed=passed,
            reason=reason,
            original_confidence=original_confidence,
            final_confidence=final_confidence,
            model_probability=model_probability,
            quantity_multiplier=quantity_multiplier,
            metadata=dict(metadata or {}),
        )

        return {
            "signal": signal,
            "passed": passed,
            "decision": decision,
        }

    def _normalize_probability(self, value: float | None) -> float | None:
        if value is None:
            return None
        return _clamp(value, 0.0, 1.0)

    def _strategy_name(self, signal: Any) -> str:
        value = (
            self._get(signal, "strategy_name")
            or self._get(signal, "source_strategy")
            or self._get(signal, "name")
            or "unknown"
        )
        return str(value or "unknown").strip() or "unknown"

    def _side(self, signal: Any) -> str:
        value = (
            self._get(signal, "side")
            or self._get(signal, "action")
            or self._get(signal, "decision")
            or "hold"
        )
        text = str(value or "").strip().lower()

        if text in {"buy", "long"}:
            return "buy"

        if text in {"sell", "short"}:
            return "sell"

        return "hold"

    def _confidence(self, signal: Any) -> float:
        return _clamp(self._get(signal, "confidence", 0.0), 0.0, self.max_confidence)

    def _get(self, signal: Any, key: str, default: Any = None) -> Any:
        if isinstance(signal, dict):
            return signal.get(key, default)
        return getattr(signal, key, default)

    # ------------------------------------------------------------------
    # Runtime status
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "ml_reject_threshold": self.ml_reject_threshold,
            "ml_reduce_threshold": self.ml_reduce_threshold,
            "ml_boost_cap": self.ml_boost_cap,
            "reasoning_reject_on_skip": self.reasoning_reject_on_skip,
            "min_quantity_multiplier": self.min_quantity_multiplier,
            "max_confidence": self.max_confidence,
            "total_validations": self.total_validations,
            "total_passed": self.total_passed,
            "total_filtered": self.total_filtered,
            "last_result": self.last_result.to_dict() if self.last_result else None,
        }

    def healthy(self) -> bool:
        return True


def _signal_to_dict(signal: Any) -> dict[str, Any]:
    if signal is None:
        return {}

    if isinstance(signal, dict):
        return _json_safe(signal)

    if is_dataclass(signal):
        try:
            return _json_safe(asdict(signal))
        except Exception:
            pass

    if hasattr(signal, "to_dict") and callable(signal.to_dict):
        try:
            result = signal.to_dict()
            if isinstance(result, dict):
                return _json_safe(result)
        except Exception:
            pass

    output: dict[str, Any] = {}

    for key in (
        "symbol",
        "side",
        "confidence",
        "strategy_name",
        "source_strategy",
        "status",
        "stage",
        "note",
        "reason",
        "metadata",
    ):
        if hasattr(signal, key):
            output[key] = getattr(signal, key)

    return _json_safe(output)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, datetime):
        return value.isoformat()

    if is_dataclass(value):
        try:
            return _json_safe(asdict(value))
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item)
            for item in value
        ]

    if hasattr(value, "value"):
        try:
            return _json_safe(value)
        except Exception:
            pass

    return str(value)
