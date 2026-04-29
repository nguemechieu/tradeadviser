from __future__ import annotations

"""
InvestPro DecisionEngine

Hybrid decision engine that combines:

- strategy/fusion voting
- market regime detection
- ML/AI model prediction
- optional reasoning engine
- safe AI override rules
- output compatible with ReasoningDecision and TradeFilter

Pipeline:

    signals
        ↓
    market regime
        ↓
    fusion engine vote
        ↓
    AI model prediction
        ↓
    reasoning engine
        ↓
    final ReasoningDecision
"""

import inspect
import math
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

import numpy as np

try:
    from models.signal import Signal
except Exception:  # pragma: no cover
    Signal = Any  # type: ignore

try:
    from core.ai.reasoning.reasoning_decision import ReasoningDecision
except Exception:  # pragma: no cover
    @dataclass(slots=True)
    class ReasoningDecision:  # type: ignore
        signal: Any
        decision: str
        confidence: float
        reasons: list[str] = field(default_factory=list)
        factors: dict[str, float] = field(default_factory=dict)
        model_name: Optional[str] = None
        strategy_name: Optional[str] = None
        risk_score: Optional[float] = None
        metadata: dict[str, Any] = field(default_factory=dict)


try:
    from core.market.regime_detector import MarketRegimeDetector
except Exception:  # pragma: no cover
    MarketRegimeDetector = Any  # type: ignore

try:
    from core.ai.model import AIModel
except Exception:  # pragma: no cover
    AIModel = Any  # type: ignore

try:
    from core.ai.features import build_features
except Exception:  # pragma: no cover
    build_features = None  # type: ignore


@dataclass(slots=True)
class ReasoningContext:
    symbol: str = ""
    signals: list[Any] = field(default_factory=list)
    candles: list[Any] = field(default_factory=list)
    dataset: Any = None
    timeframe: str = "1h"
    portfolio_snapshot: dict[str, Any] = field(default_factory=dict)
    risk_limits: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DecisionOutcome:
    votes: dict[str, float] = field(default_factory=lambda: {
                                    "buy": 0.0, "sell": 0.0, "hold": 0.0})
    best_by_side: dict[str, Any] = field(default_factory=dict)

    winning_side: Optional[str] = None
    selected_signal: Optional[Any] = None
    selected_strategy: str = "none"

    confidence: float = 0.0
    vote_margin: float = 0.0
    risk_score: float = 0.5

    market_regime: str = "UNKNOWN"
    ai_action: str = "HOLD"
    ai_confidence: float = 0.0

    reasoning: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FusionEngineProtocol(Protocol):
    def fuse(self, signals: list[Any]) -> Any:
        ...


class DecisionEngine:
    """Hybrid fusion + AI + reasoning decision engine."""

    ACTIONS = {"BUY", "SELL", "HOLD"}

    def __init__(
        self,
        fusion_engine: Any,
        reasoning_engine: Any = None,
        regime_detector: Any = None,
        ai_model: Any = None,
        *,
        ai_override_confidence: float = 0.80,
        min_confidence: float = 0.0,
        allow_ai_hold_override: bool = False,
        allow_ai_opposite_override: bool = True,
        model_name: str = "HybridAI",
        strategy_name: str = "QuantFusion",
    ) -> None:
        self.fusion = fusion_engine
        self.reasoning = reasoning_engine
        self.regime = regime_detector or self._build_default_regime_detector()
        self.ai_model = ai_model

        self.ai_override_confidence = self._clamp(
            ai_override_confidence, 0.0, 1.0)
        self.min_confidence = self._clamp(min_confidence, 0.0, 1.0)
        self.allow_ai_hold_override = bool(allow_ai_hold_override)
        self.allow_ai_opposite_override = bool(allow_ai_opposite_override)

        self.model_name = str(model_name or "HybridAI")
        self.strategy_name = str(strategy_name or "QuantFusion")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decide(self, ctx: ReasoningContext | dict[str, Any]) -> ReasoningDecision:
        ctx = self._coerce_context(ctx)

        if not ctx.signals:
            return self._empty(ctx)

        regime = self._detect_regime(ctx)
        fusion_outcome = await self._fuse_signals(ctx.signals)
        ai_decision = self._predict_ai(ctx)
        reasoning_payload = await self._run_reasoning(ctx, regime, fusion_outcome, ai_decision)

        final_action = fusion_outcome.winning_side or "HOLD"
        final_confidence = fusion_outcome.confidence
        final_vote_margin = fusion_outcome.vote_margin
        selected_signal = fusion_outcome.selected_signal or self._best_signal(
            ctx.signals)

        override_reason = ""

        ai_action = self._normalize_action(
            getattr(ai_decision, "action", None))
        ai_confidence = self._safe_float(
            getattr(ai_decision, "confidence", 0.0), 0.0)

        if self._should_ai_override(
            fusion_action=final_action,
            ai_action=ai_action,
            ai_confidence=ai_confidence,
        ):
            final_action = ai_action
            final_confidence = max(final_confidence, ai_confidence)
            override_reason = f"AI override applied: {ai_action} confidence={ai_confidence:.3f}"

        if final_confidence < self.min_confidence:
            override_reason = (
                f"Confidence below minimum: {final_confidence:.3f} < {self.min_confidence:.3f}"
            )
            final_action = "HOLD"

        market_regime = self._regime_name(regime)
        risk_score = self._estimate_risk_score(
            regime=regime,
            signal=selected_signal,
            ai_confidence=ai_confidence,
            vote_margin=final_vote_margin,
        )

        reasons = self._build_reasons(
            regime=regime,
            ai_decision=ai_decision,
            reasoning_payload=reasoning_payload,
            override_reason=override_reason,
            fusion_outcome=fusion_outcome,
        )

        metadata = {
            "symbol": ctx.symbol,
            "timeframe": ctx.timeframe,
            "market_regime": market_regime,
            "regime": self._regime_to_dict(regime),
            "ai": self._ai_to_dict(ai_decision),
            "fusion": fusion_outcome.metadata,
            "votes": dict(fusion_outcome.votes),
            "selected_strategy": fusion_outcome.selected_strategy,
            "reasoning": reasoning_payload,
            "portfolio_snapshot": dict(ctx.portfolio_snapshot or {}),
            "risk_limits": dict(ctx.risk_limits or {}),
            "context_metadata": dict(ctx.metadata or {}),
            "override_reason": override_reason,
        }

        decision = ReasoningDecision(
            signal=selected_signal,
            decision=final_action,
            confidence=self._clamp(final_confidence, 0.0, 1.0),
            reasons=reasons,
            factors={
                "vote_margin": self._clamp(final_vote_margin, 0.0, 1.0),
                "risk_score": self._clamp(risk_score, 0.0, 1.0),
                "ai_confidence": self._clamp(ai_confidence, 0.0, 1.0),
                "regime_confidence": self._clamp(self._safe_float(getattr(regime, "confidence", 0.0), 0.0), 0.0, 1.0),
            },
            strategy_name=fusion_outcome.selected_strategy or self.strategy_name,
            model_name=self.model_name,
            risk_score=self._clamp(risk_score, 0.0, 1.0),
            metadata=metadata,
        )

        self._attach_compat_fields(
            decision,
            symbol=ctx.symbol,
            vote_margin=final_vote_margin,
            market_regime=market_regime,
            ai_action=ai_action,
            ai_confidence=ai_confidence,
            selected_strategy=fusion_outcome.selected_strategy,
        )

        return decision

    # ------------------------------------------------------------------
    # Empty / fallback
    # ------------------------------------------------------------------

    def _empty(self, ctx: ReasoningContext) -> ReasoningDecision:
        placeholder_signal = None

        decision = ReasoningDecision(
            signal=placeholder_signal,
            decision="HOLD",
            confidence=0.0,
            reasons=["No signals supplied."],
            factors={
                "vote_margin": 0.0,
                "risk_score": 0.5,
                "ai_confidence": 0.0,
                "regime_confidence": 0.0,
            },
            strategy_name=self.strategy_name,
            model_name=self.model_name,
            risk_score=0.5,
            metadata={
                "symbol": ctx.symbol,
                "timeframe": ctx.timeframe,
                "market_regime": "UNKNOWN",
                "votes": {"buy": 0.0, "sell": 0.0, "hold": 1.0},
            },
        )

        self._attach_compat_fields(
            decision,
            symbol=ctx.symbol,
            vote_margin=0.0,
            market_regime="UNKNOWN",
            ai_action="HOLD",
            ai_confidence=0.0,
            selected_strategy=self.strategy_name,
        )

        return decision

    # ------------------------------------------------------------------
    # Regime
    # ------------------------------------------------------------------

    def _build_default_regime_detector(self) -> Any:
        try:
            return MarketRegimeDetector()
        except Exception:
            return None

    def _detect_regime(self, ctx: ReasoningContext) -> Any:
        if self.regime is None or not hasattr(self.regime, "detect"):
            return {
                "name": "UNKNOWN",
                "confidence": 0.0,
            }

        try:
            return self.regime.detect(ctx.candles)
        except Exception as exc:
            return {
                "name": "UNKNOWN",
                "confidence": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            }

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    async def _fuse_signals(self, signals: list[Any]) -> DecisionOutcome:
        if self.fusion is None or not hasattr(self.fusion, "fuse"):
            return self._fallback_fusion(signals)

        try:
            result = self.fusion.fuse(signals)
            result = await self._maybe_await(result)
        except Exception as exc:
            outcome = self._fallback_fusion(signals)
            outcome.metadata["fusion_error"] = f"{type(exc).__name__}: {exc}"
            return outcome

        return self._normalize_fusion_result(result, signals)

    def _fallback_fusion(self, signals: list[Any]) -> DecisionOutcome:
        votes = {"buy": 0.0, "sell": 0.0, "hold": 0.0}
        best_by_side: dict[str, Any] = {}

        for signal in signals:
            side = self._normalize_action(self._get(signal, "side", self._get(
                signal, "decision", self._get(signal, "action", "HOLD"))))
            confidence = self._clamp(self._safe_float(
                self._get(signal, "confidence", 0.0), 0.0), 0.0, 1.0)
            weight = self._safe_float(
                self._get(signal, "weight", self._get(signal, "strategy_weight", 1.0)), 1.0)
            score = confidence * max(weight, 0.0)

            key = side.lower()
            if key not in votes:
                key = "hold"

            votes[key] = votes.get(key, 0.0) + score

            current_best = best_by_side.get(key)
            current_conf = self._safe_float(self._get(
                current_best, "confidence", -1.0), -1.0) if current_best is not None else -1.0
            if confidence > current_conf:
                best_by_side[key] = signal

        buy_vote = votes.get("buy", 0.0)
        sell_vote = votes.get("sell", 0.0)
        hold_vote = votes.get("hold", 0.0)

        if buy_vote <= 0 and sell_vote <= 0:
            winning_side = "HOLD"
            selected_signal = best_by_side.get(
                "hold") or self._best_signal(signals)
        elif buy_vote >= sell_vote:
            winning_side = "BUY"
            selected_signal = best_by_side.get(
                "buy") or self._best_signal(signals)
        else:
            winning_side = "SELL"
            selected_signal = best_by_side.get(
                "sell") or self._best_signal(signals)

        total_directional = buy_vote + sell_vote + hold_vote
        confidence = max(buy_vote, sell_vote, hold_vote) / \
            max(total_directional, 1e-12)
        vote_margin = abs(buy_vote - sell_vote) / \
            max(buy_vote + sell_vote, 1e-12)

        return DecisionOutcome(
            votes=votes,
            best_by_side=best_by_side,
            winning_side=winning_side,
            selected_signal=selected_signal,
            selected_strategy=self._get_strategy_name(selected_signal),
            confidence=self._clamp(confidence, 0.0, 1.0),
            vote_margin=self._clamp(vote_margin, 0.0, 1.0),
            metadata={
                "method": "fallback_weighted_vote",
                "signal_count": len(signals),
            },
        )

    def _normalize_fusion_result(self, result: Any, signals: list[Any]) -> DecisionOutcome:
        if isinstance(result, DecisionOutcome):
            return result

        if isinstance(result, tuple):
            decision = result[0] if len(result) > 0 else "HOLD"
            confidence = result[1] if len(result) > 1 else 0.0
            vote_margin = result[2] if len(result) > 2 else 0.0

            selected_signal = self._best_signal(signals)

            return DecisionOutcome(
                winning_side=self._normalize_action(decision),
                selected_signal=selected_signal,
                selected_strategy=self._get_strategy_name(selected_signal),
                confidence=self._clamp(
                    self._safe_float(confidence, 0.0), 0.0, 1.0),
                vote_margin=self._clamp(
                    self._safe_float(vote_margin, 0.0), 0.0, 1.0),
                votes=self._votes_from_decision(decision, confidence),
                metadata={
                    "method": "tuple_fusion_result",
                    "raw": str(result),
                },
            )

        if isinstance(result, dict):
            decision = (
                result.get("decision")
                or result.get("action")
                or result.get("side")
                or result.get("winning_side")
                or "HOLD"
            )

            selected_signal = (
                result.get("selected_signal")
                or result.get("signal")
                or self._best_signal(signals)
            )

            votes = result.get("votes")
            if not isinstance(votes, dict):
                votes = self._votes_from_decision(
                    decision, result.get("confidence", 0.0))

            return DecisionOutcome(
                votes={
                    "buy": self._safe_float(votes.get("buy", votes.get("BUY", 0.0)), 0.0),
                    "sell": self._safe_float(votes.get("sell", votes.get("SELL", 0.0)), 0.0),
                    "hold": self._safe_float(votes.get("hold", votes.get("HOLD", 0.0)), 0.0),
                },
                best_by_side=dict(result.get("best_by_side") or {}),
                winning_side=self._normalize_action(decision),
                selected_signal=selected_signal,
                selected_strategy=str(
                    result.get("selected_strategy")
                    or self._get_strategy_name(selected_signal)
                    or self.strategy_name
                ),
                confidence=self._clamp(self._safe_float(
                    result.get("confidence"), 0.0), 0.0, 1.0),
                vote_margin=self._clamp(self._safe_float(
                    result.get("vote_margin"), 0.0), 0.0, 1.0),
                risk_score=self._clamp(self._safe_float(
                    result.get("risk_score"), 0.5), 0.0, 1.0),
                metadata={
                    "method": "dict_fusion_result",
                    **dict(result.get("metadata") or {}),
                },
            )

        return self._fallback_fusion(signals)

    def _votes_from_decision(self, decision: Any, confidence: Any) -> dict[str, float]:
        action = self._normalize_action(decision).lower()
        conf = self._clamp(self._safe_float(confidence, 0.0), 0.0, 1.0)
        votes = {"buy": 0.0, "sell": 0.0, "hold": 0.0}
        votes[action if action in votes else "hold"] = conf
        return votes

    # ------------------------------------------------------------------
    # AI
    # ------------------------------------------------------------------

    def _predict_ai(self, ctx: ReasoningContext) -> Any:
        if self.ai_model is None or not hasattr(self.ai_model, "predict"):
            return self._ai_decision("HOLD", 0.0, reason="No AI model supplied.")

        features = None

        try:
            if build_features is not None:
                features = build_features(ctx.candles)
        except Exception as exc:
            return self._ai_decision("HOLD", 0.0, reason=f"Feature build failed: {exc}")

        try:
            if features is None:
                return self._ai_decision("HOLD", 0.0, reason="No features were built.")

            arr = np.asarray(features, dtype=float)
            if arr.size == 0:
                return self._ai_decision("HOLD", 0.0, reason="Empty feature array.")

            arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

            return self.ai_model.predict(arr)
        except Exception as exc:
            return self._ai_decision("HOLD", 0.0, reason=f"AI prediction failed: {type(exc).__name__}: {exc}")

    def _ai_decision(self, action: str, confidence: float, reason: str = "") -> Any:
        @dataclass(slots=True)
        class _AIDecision:
            action: str
            confidence: float
            reason: str = ""
            probabilities: dict[str, float] = field(default_factory=dict)

        return _AIDecision(
            action=self._normalize_action(action),
            confidence=self._clamp(confidence, 0.0, 1.0),
            reason=reason,
        )

    def _should_ai_override(self, *, fusion_action: str, ai_action: str, ai_confidence: float) -> bool:
        fusion_action = self._normalize_action(fusion_action)
        ai_action = self._normalize_action(ai_action)

        if ai_confidence < self.ai_override_confidence:
            return False

        if ai_action == "HOLD":
            return self.allow_ai_hold_override

        if fusion_action == "HOLD":
            return True

        if ai_action == fusion_action:
            return True

        return self.allow_ai_opposite_override

    # ------------------------------------------------------------------
    # Reasoning
    # ------------------------------------------------------------------

    async def _run_reasoning(
        self,
        ctx: ReasoningContext,
        regime: Any,
        fusion_outcome: DecisionOutcome,
        ai_decision: Any,
    ) -> dict[str, Any]:
        if self.reasoning is None:
            return {
                "explanation": "Reasoning engine unavailable.",
                "decision": fusion_outcome.winning_side or "HOLD",
            }

        payload = {
            "symbol": ctx.symbol,
            "timeframe": ctx.timeframe,
            "signals": [self._signal_to_dict(signal) for signal in ctx.signals],
            "regime": self._regime_name(regime),
            "regime_confidence": self._safe_float(getattr(regime, "confidence", 0.0), 0.0),
            "ai": {
                "action": self._normalize_action(getattr(ai_decision, "action", "HOLD")),
                "confidence": self._safe_float(getattr(ai_decision, "confidence", 0.0), 0.0),
                "reason": str(getattr(ai_decision, "reason", "") or ""),
            },
            "fusion": {
                "decision": fusion_outcome.winning_side,
                "confidence": fusion_outcome.confidence,
                "vote_margin": fusion_outcome.vote_margin,
                "votes": dict(fusion_outcome.votes),
            },
            "portfolio_snapshot": dict(ctx.portfolio_snapshot or {}),
            "risk_limits": dict(ctx.risk_limits or {}),
        }

        try:
            if hasattr(self.reasoning, "reason") and callable(self.reasoning.reason):
                result = self.reasoning.reason(payload)
            elif hasattr(self.reasoning, "evaluate") and callable(self.reasoning.evaluate):
                result = self.reasoning.evaluate(payload)
            else:
                return {
                    "explanation": "Reasoning engine has no reason() or evaluate() method.",
                    "decision": fusion_outcome.winning_side or "HOLD",
                }

            result = await self._maybe_await(result)
            return self._normalize_reasoning_result(result)

        except Exception as exc:
            return {
                "explanation": f"Reasoning failed: {type(exc).__name__}: {exc}",
                "decision": fusion_outcome.winning_side or "HOLD",
                "error": str(exc),
            }

    def _normalize_reasoning_result(self, result: Any) -> dict[str, Any]:
        if result is None:
            return {
                "explanation": "",
                "decision": "HOLD",
            }

        if isinstance(result, dict):
            explanation = (
                result.get("explanation")
                or result.get("reasoning")
                or result.get("reason")
                or ""
            )
            return {
                **dict(result),
                "explanation": str(explanation or "").strip(),
            }

        if hasattr(result, "to_dict") and callable(result.to_dict):
            try:
                return self._normalize_reasoning_result(result.to_dict())
            except Exception:
                pass

        explanation = str(getattr(result, "explanation", "")
                          or getattr(result, "reasoning", "") or result)
        decision = str(getattr(result, "decision", "HOLD") or "HOLD")

        return {
            "explanation": explanation,
            "decision": decision,
            "confidence": self._safe_float(getattr(result, "confidence", 0.0), 0.0),
        }

    # ------------------------------------------------------------------
    # Risk estimate
    # ------------------------------------------------------------------

    def _estimate_risk_score(
        self,
        *,
        regime: Any,
        signal: Any,
        ai_confidence: float,
        vote_margin: float,
    ) -> float:
        risk = 0.5

        regime_name = self._regime_name(regime).upper()
        regime_conf = self._safe_float(getattr(regime, "confidence", 0.0), 0.0)

        if regime_name in {"VOLATILE", "HIGH_VOLATILITY"}:
            risk += 0.25 * max(regime_conf, 0.5)

        if regime_name in {"UNKNOWN"}:
            risk += 0.10

        if vote_margin < 0.10:
            risk += 0.15

        if ai_confidence < 0.50:
            risk += 0.10

        signal_risk = self._safe_float(self._get(
            signal, "risk_score", self._get(signal, "risk_estimate", None)), default=None)
        if signal_risk is not None:
            if signal_risk > 1.0:
                signal_risk = min(signal_risk / 100.0, 1.0)
            risk = (risk * 0.60) + (signal_risk * 0.40)

        return self._clamp(risk, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Reasons / metadata
    # ------------------------------------------------------------------

    def _build_reasons(
        self,
        *,
        regime: Any,
        ai_decision: Any,
        reasoning_payload: dict[str, Any],
        override_reason: str,
        fusion_outcome: DecisionOutcome,
    ) -> list[str]:
        reasons = [
            f"Regime: {self._regime_name(regime)}",
            f"Fusion: {fusion_outcome.winning_side or 'HOLD'} confidence={fusion_outcome.confidence:.3f}, vote_margin={fusion_outcome.vote_margin:.3f}",
            f"AI: {self._normalize_action(getattr(ai_decision, 'action', 'HOLD'))} confidence={self._safe_float(getattr(ai_decision, 'confidence', 0.0), 0.0):.3f}",
        ]

        ai_reason = str(getattr(ai_decision, "reason", "") or "").strip()
        if ai_reason:
            reasons.append(ai_reason)

        explanation = str(reasoning_payload.get("explanation") or "").strip()
        if explanation:
            reasons.append(explanation)

        if override_reason:
            reasons.append(override_reason)

        return reasons

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def _signal_to_dict(self, signal: Any) -> dict[str, Any]:
        if signal is None:
            return {}

        if isinstance(signal, dict):
            return dict(signal)

        if hasattr(signal, "to_dict") and callable(signal.to_dict):
            try:
                return dict(signal.to_dict())
            except Exception:
                pass

        output: dict[str, Any] = {}
        for key in (
            "symbol",
            "side",
            "decision",
            "action",
            "confidence",
            "strategy_name",
            "reason",
            "amount",
            "price",
            "risk_score",
            "risk_estimate",
            "expected_return",
            "alpha_score",
        ):
            if hasattr(signal, key):
                output[key] = getattr(signal, key)

        return output

    def _regime_to_dict(self, regime: Any) -> dict[str, Any]:
        if isinstance(regime, dict):
            return dict(regime)

        if hasattr(regime, "to_dict") and callable(regime.to_dict):
            try:
                return dict(regime.to_dict())
            except Exception:
                pass

        return {
            "name": self._regime_name(regime),
            "confidence": self._safe_float(getattr(regime, "confidence", 0.0), 0.0),
            "direction": str(getattr(regime, "direction", "") or ""),
            "volatility": self._safe_float(getattr(regime, "volatility", 0.0), 0.0),
            "trend_strength": self._safe_float(getattr(regime, "trend_strength", 0.0), 0.0),
        }

    def _ai_to_dict(self, ai_decision: Any) -> dict[str, Any]:
        if ai_decision is None:
            return {
                "action": "HOLD",
                "confidence": 0.0,
            }

        if hasattr(ai_decision, "to_dict") and callable(ai_decision.to_dict):
            try:
                return dict(ai_decision.to_dict())
            except Exception:
                pass

        return {
            "action": self._normalize_action(getattr(ai_decision, "action", "HOLD")),
            "confidence": self._safe_float(getattr(ai_decision, "confidence", 0.0), 0.0),
            "reason": str(getattr(ai_decision, "reason", "") or ""),
            "probabilities": dict(getattr(ai_decision, "probabilities", {}) or {}),
        }

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    def _attach_compat_fields(
        self,
        decision: Any,
        *,
        symbol: str,
        vote_margin: float,
        market_regime: str,
        ai_action: str,
        ai_confidence: float,
        selected_strategy: str,
    ) -> None:
        # Your TradeFilter and runtime often access these as attributes.
        fields_to_set = {
            "symbol": symbol,
            "vote_margin": self._clamp(vote_margin, 0.0, 1.0),
            "market_regime": market_regime,
            "ai_action": ai_action,
            "ai_confidence": self._clamp(ai_confidence, 0.0, 1.0),
            "selected_strategy": selected_strategy,
        }

        for key, value in fields_to_set.items():
            with contextlib_suppress_attribute_error():
                setattr(decision, key, value)

        # If slots prevent setting attributes, preserve them in metadata.
        metadata = getattr(decision, "metadata", None)
        if isinstance(metadata, dict):
            metadata.update(fields_to_set)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _coerce_context(self, ctx: ReasoningContext | dict[str, Any]) -> ReasoningContext:
        if isinstance(ctx, ReasoningContext):
            return ctx

        if isinstance(ctx, dict):
            return ReasoningContext(
                symbol=str(ctx.get("symbol") or "").strip().upper(),
                signals=list(ctx.get("signals") or []),
                candles=list(ctx.get("candles") or []),
                dataset=ctx.get("dataset"),
                timeframe=str(ctx.get("timeframe") or "1h").strip() or "1h",
                portfolio_snapshot=dict(ctx.get("portfolio_snapshot") or {}),
                risk_limits=dict(ctx.get("risk_limits") or {}),
                metadata=dict(ctx.get("metadata") or {}),
            )

        raise TypeError("ctx must be ReasoningContext or dict")

    def _best_signal(self, signals: list[Any]) -> Any:
        if not signals:
            return None

        return max(
            signals,
            key=lambda signal: self._safe_float(
                self._get(signal, "confidence", 0.0), 0.0),
        )

    def _get_strategy_name(self, signal: Any) -> str:
        value = self._get(signal, "strategy_name", None)
        if value is None:
            value = self._get(signal, "name", None)
        return str(value or self.strategy_name).strip() or self.strategy_name

    def _get(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    def _regime_name(self, regime: Any) -> str:
        if regime is None:
            return "UNKNOWN"

        if isinstance(regime, dict):
            return str(regime.get("name") or regime.get("regime") or regime.get("state") or "UNKNOWN").strip().upper()

        return str(getattr(regime, "name", "UNKNOWN") or "UNKNOWN").strip().upper()

    def _normalize_action(self, value: Any) -> str:
        text = str(value or "").strip().upper()

        if text in {"BUY", "LONG"}:
            return "BUY"

        if text in {"SELL", "SHORT"}:
            return "SELL"

        if text in {"HOLD", "WAIT", "NONE", "NEUTRAL", ""}:
            return "HOLD"

        return text if text in self.ACTIONS else "HOLD"

    def _safe_float(self, value: Any, default: Optional[float] = 0.0) -> Optional[float]:
        if value in (None, ""):
            return default

        try:
            number = float(value)
        except Exception:
            return default

        if not math.isfinite(number):
            return default

        return number

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value


class contextlib_suppress_attribute_error:
    """Tiny local suppressor to avoid importing contextlib for one AttributeError case."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return exc_type is AttributeError
