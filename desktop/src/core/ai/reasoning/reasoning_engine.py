from __future__ import annotations

"""
InvestPro ReasoningEngine

Provider-backed reasoning engine used by the trading runtime.

Responsibilities:
- Build sanitized reasoning context
- Build prompt messages
- Call primary provider
- Fall back to local/secondary provider
- Normalize provider result
- Return ReasoningEvaluation compatible with TradeFilter / DecisionEngine
"""

import asyncio
import inspect
import logging
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Optional

from core.ai.reasoning.context_builder import ReasoningContextBuilder
from core.ai.reasoning.prompt_engine import PromptEngine
from core.ai.reasoning.schema import ReasoningResult


def _risk_score_from_label(label: str) -> float:
    normalized = str(label or "").strip().lower()

    if normalized == "low":
        return 0.20

    if normalized in {"moderate", "medium"}:
        return 0.50

    if normalized == "high":
        return 0.80

    if normalized in {"critical", "extreme"}:
        return 0.95

    return 0.50


def _decision_to_action(decision: str) -> str:
    normalized = str(decision or "").strip().upper()

    if normalized == "APPROVE":
        return "APPROVE"

    if normalized == "REJECT":
        return "REJECT"

    if normalized == "NEUTRAL":
        return "NEUTRAL"

    return "NEUTRAL"


@dataclass(slots=True)
class ReasoningEvaluation:
    result: ReasoningResult
    context: dict[str, Any]
    market_regime: str | None = None
    vote_margin: float = 1.0
    risk_score: float = 0.5
    fallback_used: bool = False
    provider_errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def decision(self) -> str:
        return self.result.decision

    @property
    def confidence(self) -> float:
        return self.result.confidence

    @property
    def reasoning(self) -> str:
        return self.result.reasoning

    @property
    def risk(self) -> str:
        return self.result.risk

    @property
    def warnings(self) -> list[str]:
        return list(self.result.warnings or [])

    @property
    def provider(self) -> str:
        return self.result.provider

    @property
    def mode(self) -> str:
        return self.result.mode

    @property
    def should_execute(self) -> bool:
        return bool(self.result.should_execute)

    @property
    def latency_ms(self) -> float:
        return float(self.result.latency_ms or 0.0)

    @property
    def action(self) -> str:
        """Compatibility alias for AI/decision code."""
        return self.decision

    @property
    def approved(self) -> bool:
        return self.decision == "APPROVE" and self.should_execute

    def to_dict(self) -> dict[str, Any]:
        payload = self.result.to_dict()
        payload["market_regime"] = self.market_regime
        payload["vote_margin"] = self.vote_margin
        payload["risk_score"] = self.risk_score
        payload["fallback_used"] = self.fallback_used
        payload["provider_errors"] = list(self.provider_errors)
        payload["metadata"] = dict(self.metadata or {})
        return payload

    def __iter__(self):
        """Backward-compatible unpacking: result, context."""
        yield self.result
        yield dict(self.context or {})


class ReasoningEngine:
    """Provider-backed reasoning engine used by the trading runtime."""

    VALID_MODES = {"assistive", "advisory", "autonomous", "audit"}

    def __init__(
        self,
        provider: Any = None,
        fallback_provider: Any = None,
        timeout_seconds: float = 5.0,
        logger: logging.Logger | None = None,
        context_builder: ReasoningContextBuilder | None = None,
        prompt_engine: PromptEngine | None = None,
        *,
        enabled: bool = True,
        mode: str = "assistive",
        minimum_confidence: float = 0.5,
        fail_open: bool = True,
        neutral_should_execute: bool = True,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.fallback_provider = fallback_provider
        self.timeout_seconds = max(0.1, float(timeout_seconds or 5.0))
        self.logger = logger or logging.getLogger("ReasoningEngine")
        self.context_builder = context_builder or ReasoningContextBuilder()
        self.prompt_engine = prompt_engine or PromptEngine()

        self.enabled = bool(enabled if enabled is not None else kwargs.get("enabled", True))
        self.mode = self._normalize_mode(mode or kwargs.get("mode", "assistive"))
        self.minimum_confidence = self._clamp(float(minimum_confidence or 0.5), 0.0, 1.0)

        self.fail_open = bool(fail_open)
        self.neutral_should_execute = bool(neutral_should_execute)

        self.total_evaluations = 0
        self.success_count = 0
        self.failure_count = 0
        self.fallback_count = 0
        self.last_error: str = ""
        self.last_latency_ms: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        *,
        symbol: str,
        signal: dict[str, Any],
        dataset: Any = None,
        timeframe: str | None = None,
        regime_snapshot: dict[str, Any] | None = None,
        portfolio_snapshot: dict[str, Any] | None = None,
        risk_limits: dict[str, Any] | None = None,
        mode: str | None = None,
    ) -> ReasoningEvaluation:
        started = time.perf_counter()
        self.total_evaluations += 1

        active_mode = self._normalize_mode(mode or self.mode)

        context = self.context_builder.build(
            symbol=symbol,
            signal=signal,
            dataset=dataset,
            timeframe=timeframe or "1h",
            regime_snapshot=regime_snapshot,
            portfolio_snapshot=portfolio_snapshot,
            risk_limits=risk_limits,
        )

        market_regime = self._market_regime_from_context(context)
        signal_confidence = self._coerce_float(context.get("signal_confidence"), 0.0)
        vote_margin = self._vote_margin_from_context(context, signal_confidence)

        if not self.enabled:
            result = self._disabled_result(context=context, mode=active_mode)
            evaluation = self._build_evaluation(
                result=result,
                context=context,
                market_regime=market_regime,
                vote_margin=vote_margin,
                started=started,
                provider_errors=[],
                fallback_used=False,
            )
            self.success_count += 1
            return evaluation

        messages = self.prompt_engine.build_messages(context, mode=active_mode)

        result, provider_errors, fallback_used = await self._evaluate_with_providers(
            messages=messages,
            context=context,
            mode=active_mode,
        )

        evaluation = self._build_evaluation(
            result=result,
            context=context,
            market_regime=market_regime,
            vote_margin=vote_margin,
            started=started,
            provider_errors=provider_errors,
            fallback_used=fallback_used,
        )

        if provider_errors and fallback_used:
            self.fallback_count += 1

        if provider_errors and result.provider == "fallback":
            self.failure_count += 1
        else:
            self.success_count += 1

        return evaluation

    async def reason(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Compatibility helper for DecisionEngine-style calls.

        Accepts a compact payload containing signals/regime/ai/fusion and returns
        a dict with explanation-style keys.
        """
        signal = self._signal_from_reason_payload(payload)
        symbol = str(payload.get("symbol") or signal.get("symbol") or "").strip().upper()

        evaluation = await self.evaluate(
            symbol=symbol or "UNKNOWN",
            signal=signal,
            dataset=payload.get("dataset"),
            timeframe=payload.get("timeframe") or "1h",
            regime_snapshot=self._regime_snapshot_from_reason_payload(payload),
            portfolio_snapshot=payload.get("portfolio_snapshot"),
            risk_limits=payload.get("risk_limits"),
        )

        return {
            "decision": evaluation.decision,
            "confidence": evaluation.confidence,
            "explanation": evaluation.reasoning,
            "reasoning": evaluation.reasoning,
            "risk": evaluation.risk,
            "warnings": evaluation.warnings,
            "provider": evaluation.provider,
            "mode": evaluation.mode,
            "should_execute": evaluation.should_execute,
            "market_regime": evaluation.market_regime,
            "vote_margin": evaluation.vote_margin,
            "risk_score": evaluation.risk_score,
            "fallback_used": evaluation.fallback_used,
        }

    # ------------------------------------------------------------------
    # Provider execution
    # ------------------------------------------------------------------

    async def _evaluate_with_providers(
        self,
        *,
        messages: list[dict[str, Any]],
        context: dict[str, Any],
        mode: str,
    ) -> tuple[ReasoningResult, list[str], bool]:
        providers = [self.provider, self.fallback_provider]
        provider_errors: list[str] = []
        fallback_used = False

        for index, provider in enumerate(providers):
            if provider is None:
                continue

            provider_name = str(getattr(provider, "name", provider.__class__.__name__) or "provider")

            try:
                raw_result = provider.evaluate(
                    messages=messages,
                    context=context,
                    mode=mode,
                )

                raw_result = await asyncio.wait_for(
                    self._maybe_await(raw_result),
                    timeout=self.timeout_seconds,
                )

                result = self._coerce_result(raw_result)
                result.fallback_used = fallback_used

                if not result.provider:
                    result.provider = provider_name

                return result, provider_errors, fallback_used

            except Exception as exc:
                message = f"{provider_name}: {type(exc).__name__}: {exc}"
                provider_errors.append(message)
                self.last_error = message
                fallback_used = index == 0

                self.logger.debug(
                    "Reasoning provider failed; trying fallback.",
                    exc_info=True,
                )

        if provider_errors:
            self.logger.warning(
                "Reasoning providers failed; using neutral fallback: %s",
                provider_errors[-1],
            )

        fallback_result = self._provider_failure_result(
            context=context,
            mode=mode,
            provider_errors=provider_errors,
        )

        return fallback_result, provider_errors, True

    def _provider_failure_result(
        self,
        *,
        context: dict[str, Any],
        mode: str,
        provider_errors: list[str],
    ) -> ReasoningResult:
        signal_confidence = self._coerce_float(context.get("signal_confidence"), 0.0)

        if self.fail_open:
            decision = "NEUTRAL"
            should_execute = self.neutral_should_execute
            reasoning = "Reasoning provider fallback used; preserving the upstream signal for downstream risk controls."
        else:
            decision = "REJECT"
            should_execute = False
            reasoning = "Reasoning provider failed and fail_open is disabled."

        return ReasoningResult(
            decision=decision,
            confidence=signal_confidence,
            reasoning=reasoning,
            risk="Unknown",
            warnings=["Reasoning provider was unavailable.", *provider_errors[:2]],
            provider="fallback",
            mode=mode,
            should_execute=should_execute,
            fallback_used=True,
            payload={
                "context_symbol": context.get("symbol"),
                "provider_errors": list(provider_errors),
            },
        )

    def _disabled_result(self, *, context: dict[str, Any], mode: str) -> ReasoningResult:
        signal_confidence = self._coerce_float(context.get("signal_confidence"), 0.0)

        return ReasoningResult(
            decision="NEUTRAL",
            confidence=signal_confidence,
            reasoning="Reasoning engine disabled; preserving upstream signal for downstream risk controls.",
            risk="Unknown",
            warnings=["Reasoning engine is disabled."],
            provider="disabled",
            mode=mode,
            should_execute=self.neutral_should_execute,
            fallback_used=False,
            payload={
                "context_symbol": context.get("symbol"),
            },
        )

    def _coerce_result(self, value: Any) -> ReasoningResult:
        if isinstance(value, ReasoningResult):
            return value

        if hasattr(value, "to_dict") and callable(value.to_dict):
            try:
                return ReasoningResult.from_payload(value.to_dict())
            except Exception:
                pass

        if is_dataclass(value):
            try:
                return ReasoningResult.from_payload(asdict(value))
            except Exception:
                pass

        if isinstance(value, dict):
            return ReasoningResult.from_payload(value)

        raise TypeError(f"Unsupported reasoning result: {type(value)!r}")

    # ------------------------------------------------------------------
    # Evaluation shaping
    # ------------------------------------------------------------------

    def _build_evaluation(
        self,
        *,
        result: ReasoningResult,
        context: dict[str, Any],
        market_regime: str,
        vote_margin: float,
        started: float,
        provider_errors: list[str],
        fallback_used: bool,
    ) -> ReasoningEvaluation:
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.last_latency_ms = latency_ms

        if not result.latency_ms:
            result.latency_ms = latency_ms

        result.confidence = self._clamp(self._coerce_float(result.confidence, 0.0), 0.0, 1.0)

        if result.decision == "APPROVE" and result.confidence < self.minimum_confidence:
            result.decision = "NEUTRAL"
            result.should_execute = self.neutral_should_execute
            result.warnings = list(result.warnings or []) + [
                f"Reasoning confidence {result.confidence:.3f} is below minimum {self.minimum_confidence:.3f}."
            ]

        risk_score = _risk_score_from_label(result.risk)

        metadata = {
            "engine_enabled": self.enabled,
            "minimum_confidence": self.minimum_confidence,
            "fail_open": self.fail_open,
            "neutral_should_execute": self.neutral_should_execute,
            "context_symbol": context.get("symbol"),
            "signal_confidence": context.get("signal_confidence"),
        }

        return ReasoningEvaluation(
            result=result,
            context=context,
            market_regime=market_regime,
            vote_margin=vote_margin,
            risk_score=risk_score,
            fallback_used=bool(fallback_used or getattr(result, "fallback_used", False)),
            provider_errors=list(provider_errors or []),
            metadata=metadata,
        )

    def _market_regime_from_context(self, context: dict[str, Any]) -> str:
        regime = context.get("regime") or {}

        if not isinstance(regime, dict):
            return "UNKNOWN"

        value = (
            regime.get("state")
            or regime.get("regime")
            or regime.get("name")
            or regime.get("primary")
            or "unknown"
        )

        return str(value or "unknown").strip().upper() or "UNKNOWN"

    def _vote_margin_from_context(self, context: dict[str, Any], signal_confidence: float) -> float:
        raw = (
            context.get("vote_margin")
            or context.get("alpha_vote_margin")
            or context.get("fusion_vote_margin")
        )

        if raw is not None:
            return self._clamp(self._coerce_float(raw, signal_confidence), 0.0, 1.0)

        return self._clamp(max(0.10, signal_confidence), 0.0, 1.0)

    # ------------------------------------------------------------------
    # Compatibility payload helpers
    # ------------------------------------------------------------------

    def _signal_from_reason_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        signals = payload.get("signals")

        signal: dict[str, Any] = {}

        if isinstance(signals, list) and signals:
            first = signals[0]
            if isinstance(first, dict):
                signal.update(first)
            else:
                for key in ("symbol", "side", "action", "decision", "confidence", "reason", "strategy_name", "amount", "price"):
                    if hasattr(first, key):
                        signal[key] = getattr(first, key)

        ai = payload.get("ai")
        if isinstance(ai, dict):
            signal.setdefault("ai_action", ai.get("action"))
            signal.setdefault("confidence", ai.get("confidence", signal.get("confidence")))
        elif ai:
            signal.setdefault("ai_action", ai)

        fusion = payload.get("fusion")
        if isinstance(fusion, dict):
            signal.setdefault("side", fusion.get("decision") or fusion.get("side") or signal.get("side"))
            signal.setdefault("confidence", fusion.get("confidence", signal.get("confidence")))
            signal.setdefault("vote_margin", fusion.get("vote_margin"))

        if payload.get("symbol"):
            signal.setdefault("symbol", payload.get("symbol"))

        signal.setdefault("side", signal.get("action") or signal.get("decision") or signal.get("ai_action") or "HOLD")
        signal.setdefault("confidence", 0.0)
        signal.setdefault("strategy_name", "ReasoningPayload")

        return signal

    def _regime_snapshot_from_reason_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        regime = payload.get("regime")

        if isinstance(regime, dict):
            return regime

        if regime:
            return {
                "regime": str(regime).strip().lower(),
                "state": str(regime).strip().lower(),
            }

        return {}

    # ------------------------------------------------------------------
    # Runtime status
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "minimum_confidence": self.minimum_confidence,
            "timeout_seconds": self.timeout_seconds,
            "provider": str(getattr(self.provider, "name", None) or type(self.provider).__name__ if self.provider else "none"),
            "fallback_provider": str(getattr(self.fallback_provider, "name", None) or type(self.fallback_provider).__name__ if self.fallback_provider else "none"),
            "total_evaluations": self.total_evaluations,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "fallback_count": self.fallback_count,
            "last_error": self.last_error,
            "last_latency_ms": self.last_latency_ms,
            "fail_open": self.fail_open,
            "neutral_should_execute": self.neutral_should_execute,
        }

    def healthy(self) -> bool:
        if not self.enabled:
            return True

        if self.total_evaluations <= 0:
            return True

        return self.failure_count <= max(3, self.success_count * 2)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _normalize_mode(self, mode: str) -> str:
        normalized = str(mode or "assistive").strip().lower()
        if normalized not in self.VALID_MODES:
            return "assistive"
        return normalized

    def _coerce_float(self, value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return float(default)

        try:
            number = float(value)
        except Exception:
            return float(default)

        if number != number or number in {float("inf"), float("-inf")}:
            return float(default)

        return number

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))