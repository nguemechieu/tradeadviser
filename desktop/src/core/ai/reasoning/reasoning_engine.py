from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from core.ai.reasoning.context_builder import ReasoningContextBuilder
from core.ai.reasoning.prompt_engine import PromptEngine
from core.ai.reasoning.schema import ReasoningResult


def _risk_score_from_label(label: str) -> float:
    normalized = str(label or "").strip().lower()
    if normalized == "low":
        return 0.2
    if normalized == "moderate":
        return 0.5
    if normalized == "high":
        return 0.8
    return 0.5


@dataclass(slots=True)
class ReasoningEvaluation:
    result: ReasoningResult
    context: dict[str, Any]
    market_regime: str | None = None
    vote_margin: float = 1.0
    risk_score: float = 0.5

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
        return self.result.should_execute

    @property
    def latency_ms(self) -> float:
        return self.result.latency_ms

    def to_dict(self) -> dict[str, Any]:
        payload = self.result.to_dict()
        payload["market_regime"] = self.market_regime
        payload["vote_margin"] = self.vote_margin
        payload["risk_score"] = self.risk_score
        return payload

    def __iter__(self):
        yield self.result
        yield dict(self.context or {})


class ReasoningEngine:
    """Provider-backed reasoning engine used by the trading runtime."""

    def __init__(
        self,
        provider=None,
        fallback_provider=None,
        timeout_seconds: int = 5,
        logger: logging.Logger | None = None,
        context_builder: ReasoningContextBuilder | None = None,
        prompt_engine: PromptEngine | None = None,
        **kwargs,
    ):
        self.provider = provider
        self.fallback_provider = fallback_provider
        self.timeout_seconds = timeout_seconds
        self.logger = logger or logging.getLogger("ReasoningEngine")
        self.context_builder = context_builder or ReasoningContextBuilder()
        self.prompt_engine = prompt_engine or PromptEngine()
        self.enabled = kwargs.get("enabled", True)
        self.mode = str(kwargs.get("mode", "assistive") or "assistive").strip().lower() or "assistive"
        self.minimum_confidence = float(kwargs.get("minimum_confidence", 0.5) or 0.5)

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
    ) -> ReasoningEvaluation:
        context = self.context_builder.build(
            symbol=symbol,
            signal=signal,
            dataset=dataset,
            timeframe=timeframe or "1h",
            regime_snapshot=regime_snapshot,
            portfolio_snapshot=portfolio_snapshot,
            risk_limits=risk_limits,
        )
        messages = self.prompt_engine.build_messages(context, mode=self.mode)
        result = await self._evaluate_with_providers(messages=messages, context=context)
        market_regime = str((context.get("regime") or {}).get("state") or "unknown").strip().upper() or "UNKNOWN"
        signal_confidence = float(context.get("signal_confidence") or 0.0)
        vote_margin = max(0.1, min(1.0, signal_confidence))
        return ReasoningEvaluation(
            result=result,
            context=context,
            market_regime=market_regime,
            vote_margin=vote_margin,
            risk_score=_risk_score_from_label(result.risk),
        )

    async def _evaluate_with_providers(self, *, messages, context) -> ReasoningResult:
        providers = [self.provider, self.fallback_provider]
        last_error = None
        used_fallback = False

        for index, provider in enumerate(providers):
            if provider is None:
                continue
            try:
                raw_result = await provider.evaluate(messages=messages, context=context, mode=self.mode)
                result = self._coerce_result(raw_result)
                result.fallback_used = used_fallback
                return result
            except Exception as exc:
                last_error = exc
                used_fallback = index == 0
                self.logger.debug("Reasoning provider failed; trying fallback.", exc_info=True)

        if last_error is not None:
            self.logger.warning("Reasoning providers failed; using neutral fallback: %s", last_error)

        return ReasoningResult(
            decision="NEUTRAL",
            confidence=float(context.get("signal_confidence") or 0.0),
            reasoning="Reasoning provider fallback used; preserving the upstream signal.",
            risk="Unknown",
            warnings=["Reasoning provider was unavailable."],
            provider="fallback",
            mode=self.mode,
            should_execute=True,
            fallback_used=True,
            payload={"context_symbol": context.get("symbol")},
        )

    def _coerce_result(self, value: Any) -> ReasoningResult:
        if isinstance(value, ReasoningResult):
            return value
        if hasattr(value, "to_dict") and callable(value.to_dict):
            try:
                return ReasoningResult.from_payload(value.to_dict())
            except Exception:
                pass
        if isinstance(value, dict):
            return ReasoningResult.from_payload(value)
        raise TypeError(f"Unsupported reasoning result: {type(value)!r}")
