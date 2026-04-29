from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from models.signal import Signal


@dataclass(slots=True)
class DecisionOutcome:
    """Holds the outcome of a decision made by the DecisionEngine."""

    votes: dict[str, float] = field(default_factory=lambda: {"buy": 0.0, "sell": 0.0})
    best_by_side: dict[str, Signal] = field(default_factory=dict)
    winning_side: str | None = None
    selected_signal: Signal | None = None
    selected_strategy: str = "none"
    confidence: float = 0.0
    vote_margin: float = 0.0


class DecisionEngine:
    """Performs weighted voting only; no ML, LLM, or risk logic belongs here."""

    def decide(
        self,
        signals: list[Signal],
        *,
        weight_resolver: Callable[[str], float],
    ) -> DecisionOutcome:
        outcome = DecisionOutcome()
        best_scores = {"buy": -1.0, "sell": -1.0}
        for signal in list(signals or []):
            side = str(signal.side or "").strip().lower()
            if side not in outcome.votes:
                continue
            weight = max(0.0, float(weight_resolver(signal.strategy_name)))
            score = max(0.0, float(signal.confidence) * max(weight, 0.0))
            outcome.votes[side] += score
            if score > best_scores[side]:
                best_scores[side] = score
                outcome.best_by_side[side] = signal

        buy_score = max(0.0, float(outcome.votes.get("buy", 0.0)))
        sell_score = max(0.0, float(outcome.votes.get("sell", 0.0)))
        total_score = buy_score + sell_score
        if total_score <= 0.0:
            return outcome

        outcome.vote_margin = abs(buy_score - sell_score) / total_score
        if abs(buy_score - sell_score) <= 0.05:
            return outcome

        outcome.winning_side = "buy" if buy_score > sell_score else "sell"
        outcome.selected_signal = outcome.best_by_side.get(outcome.winning_side)
        if outcome.selected_signal is None:
            return outcome
        winning_score = buy_score if outcome.winning_side == "buy" else sell_score
        outcome.selected_strategy = outcome.selected_signal.strategy_name
        outcome.confidence = min(
            0.99,
            max(float(outcome.selected_signal.confidence), winning_score / max(total_score, 1e-9)),
        )
        return outcome
