"""Decision service interface for server-side signal fusion and reasoning handoff."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Protocol

from server.app.backend.shared.enums.common import DecisionAction
from shared.contracts.trading import DecisionIntent, SignalBundle


class DecisionService(Protocol):
    """
    Server-side decision interface.

    The server is authoritative for creating trade intents from signal bundles.
    Desktop may request reviews but must not construct final autonomous intents.
    """

    async def decide(self, bundle: SignalBundle) -> DecisionIntent:
        ...


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else float(default)
    except Exception:
        return float(default)


def _side_value(value: Any) -> str:
    if hasattr(value, "value"):
        try:
            value = value.value
        except Exception:
            pass

    text = str(value or "").strip().lower()

    if text in {"buy", "long", "bull", "bullish"}:
        return "buy"

    if text in {"sell", "short", "bear", "bearish"}:
        return "sell"

    if text in {"hold", "neutral", "none", "wait"}:
        return "hold"

    return "hold"


def _signal_weight(signal: Any) -> float:
    """
    Compute signal weight.

    Supports optional fields if your Signal contract later adds them:
    - confidence
    - weight
    - strategy_weight
    - quality_score
    """

    confidence = max(0.0, min(1.0, _safe_float(getattr(signal, "confidence", 0.0), 0.0)))

    explicit_weight = _safe_float(
        getattr(signal, "weight", None)
        or getattr(signal, "strategy_weight", None)
        or 1.0,
        1.0,
        )

    quality_score = _safe_float(
        getattr(signal, "quality_score", None)
        or getattr(signal, "score", None)
        or 1.0,
        1.0,
        )

    return max(0.0, confidence * max(0.0, explicit_weight) * max(0.0, quality_score))


def _strategy_name(signal: Any) -> str:
    return str(getattr(signal, "strategy_name", None) or "unknown").strip() or "unknown"


def _signal_reasons(signal: Any) -> list[str]:
    reasons = getattr(signal, "reasons", None)

    if reasons is None:
        reason = getattr(signal, "reason", None)
        return [str(reason)] if reason else []

    if isinstance(reasons, str):
        return [reasons]

    try:
        return [str(item) for item in reasons if str(item).strip()]
    except Exception:
        return []


def _decision_action(value: Any) -> DecisionAction:
    if isinstance(value, DecisionAction):
        return value

    if hasattr(value, "value"):
        try:
            value = value.value
        except Exception:
            pass

    text = str(value or "").strip().lower()

    if text in {"buy", "long", "bull", "bullish"}:
        return DecisionAction.BUY

    if text in {"sell", "short", "bear", "bearish"}:
        return DecisionAction.SELL

    return DecisionAction.HOLD

class InMemoryDecisionService:
    """
    Deterministic in-memory decision service.

    This is still lightweight, but it performs real signal fusion:

    - validates empty bundles
    - groups signals by side
    - computes weighted buy/sell/hold votes
    - selects the strongest side
    - selects the best signal on that side
    - emits a DecisionIntent with supporting/rejected agents
    """

    def __init__(
            self,
            *,
            min_confidence: float = 0.50,
            min_vote_margin: float = 0.05,
            allow_hold: bool = True,
    ) -> None:
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self.min_vote_margin = max(0.0, float(min_vote_margin))
        self.allow_hold = bool(allow_hold)

    async def decide(self, bundle: SignalBundle) -> DecisionIntent:
        signals = list(getattr(bundle, "signals", None) or [])

        if not signals:
            return DecisionIntent(
                intent_id=f"intent_{bundle.bundle_id}",
                identifier=bundle.identifier,
                action=DecisionAction.HOLD,
                confidence=0.0,
                selected_strategy="none",
                supporting_agents=[],
                rejected_agents=[],
                reasons=["No signals were available for this bundle."],
            )

        grouped: dict[str, list[Any]] = defaultdict(list)
        side_scores: dict[str, float] = defaultdict(float)

        for signal in signals:
            side = _side_value(getattr(signal, "side", None))
            grouped[side].append(signal)
            side_scores[side] += _signal_weight(signal)

        buy_score = side_scores.get("buy", 0.0)
        sell_score = side_scores.get("sell", 0.0)
        hold_score = side_scores.get("hold", 0.0)

        if buy_score <= 0 and sell_score <= 0:
            selected_action = "hold"
        elif buy_score >= sell_score:
            selected_action = "buy"
        else:
            selected_action = "sell"

        winning_score = side_scores.get(selected_action, 0.0)
        opposite_score = sell_score if selected_action == "buy" else buy_score
        vote_margin = winning_score - opposite_score

        selected_signals = grouped.get(selected_action, [])

        if selected_action in {"buy", "sell"} and (
                winning_score < self.min_confidence or vote_margin < self.min_vote_margin
        ):
            if self.allow_hold:
                selected_action = "hold"
                selected_signals = grouped.get("hold", [])
                winning_score = max(hold_score, 0.0)

        best_signal = None
        if selected_signals:
            best_signal = max(selected_signals, key=_signal_weight)
        else:
            best_signal = max(signals, key=_signal_weight)

        confidence = max(
            0.0,
            min(
                1.0,
                _safe_float(getattr(best_signal, "confidence", winning_score), winning_score),
            ),
        )

        selected_strategy = (
            _strategy_name(best_signal)
            if selected_action != "hold"
            else "hold"
        )

        supporting_agents = [
            _strategy_name(signal)
            for signal in signals
            if _side_value(getattr(signal, "side", None)) == selected_action
        ]

        rejected_agents = [
            _strategy_name(signal)
            for signal in signals
            if _side_value(getattr(signal, "side", None)) != selected_action
        ]

        reasons: list[str] = []

        if selected_action == "hold":
            reasons.append(
                "Decision held because signal confidence or vote margin was insufficient."
            )

        reasons.extend(_signal_reasons(best_signal))

        reasons.append(
            f"Signal fusion scores: buy={buy_score:.4f}, sell={sell_score:.4f}, hold={hold_score:.4f}."
        )

        return DecisionIntent(
            intent_id=f"intent_{bundle.bundle_id}",
            identifier=bundle.identifier,
            action=_decision_action(selected_action),
            confidence=confidence,
            selected_strategy=selected_strategy,
            supporting_agents=supporting_agents,
            rejected_agents=rejected_agents,
            reasons=reasons,
        )


__all__ = [
    "DecisionService",
    "InMemoryDecisionService",
]