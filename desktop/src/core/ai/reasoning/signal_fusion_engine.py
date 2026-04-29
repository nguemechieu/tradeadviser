from __future__ import annotations

"""
InvestPro SignalFusionEngine

Combines multiple strategy/AI signals into one final directional vote.

Supports:
- BUY / SELL / HOLD signals
- dict signals and object/dataclass signals
- confidence weighting
- strategy weights
- optional recency decay
- minimum vote margin
- selected/best signal tracking
- metadata for debug panels, audit logs, and reasoning layer

Typical output:
    DecisionOutcome(
        votes={"buy": 1.42, "sell": 0.48, "hold": 0.10},
        winning_side="BUY",
        confidence=0.71,
        vote_margin=0.49,
        selected_signal=<best BUY signal>,
        selected_strategy="TrendFollowing",
    )

This output is compatible with the upgraded DecisionEngine.
"""

import math
import time
from dataclasses import dataclass, field, is_dataclass, asdict
from typing import Any, Optional


try:
    from models.signal import Signal
except Exception:  # pragma: no cover
    Signal = Any  # type: ignore


@dataclass(slots=True)
class FusionSignalScore:
    symbol: str = ""
    action: str = "HOLD"
    confidence: float = 0.0
    weight: float = 1.0
    score: float = 0.0
    strategy_name: str = "unknown"
    reason: str = ""
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "weight": self.weight,
            "score": self.score,
            "strategy_name": self.strategy_name,
            "reason": self.reason,
        }


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
    total_score: float = 0.0

    signal_scores: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> tuple[str, float, float]:
        return self.winning_side or "HOLD", self.confidence, self.vote_margin

    def to_dict(self) -> dict[str, Any]:
        return {
            "votes": dict(self.votes),
            "winning_side": self.winning_side,
            "selected_strategy": self.selected_strategy,
            "confidence": self.confidence,
            "vote_margin": self.vote_margin,
            "total_score": self.total_score,
            "signal_scores": list(self.signal_scores),
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


class SignalFusionEngine:
    """Weighted signal voting engine for InvestPro."""

    VALID_ACTIONS = {"BUY", "SELL", "HOLD"}

    def __init__(
        self,
        *,
        min_vote_margin: float = 0.05,
        min_confidence: float = 0.0,
        include_hold_votes: bool = True,
        confidence_floor: float = 0.0,
        confidence_ceiling: float = 1.0,
        default_weight: float = 1.0,
        strategy_weights: Optional[dict[str, float]] = None,
        use_signal_weight: bool = True,
        use_strategy_weight: bool = True,
        recency_half_life_seconds: Optional[float] = None,
        return_tuple: bool = False,
    ) -> None:
        self.min_vote_margin = self._clamp(min_vote_margin, 0.0, 1.0)
        self.min_confidence = self._clamp(min_confidence, 0.0, 1.0)
        self.include_hold_votes = bool(include_hold_votes)

        self.confidence_floor = self._clamp(confidence_floor, 0.0, 1.0)
        self.confidence_ceiling = self._clamp(
            confidence_ceiling, self.confidence_floor, 1.0)

        self.default_weight = max(0.0, float(default_weight or 1.0))
        self.strategy_weights = {
            str(key).strip(): max(0.0, float(value))
            for key, value in dict(strategy_weights or {}).items()
        }

        self.use_signal_weight = bool(use_signal_weight)
        self.use_strategy_weight = bool(use_strategy_weight)

        self.recency_half_life_seconds = (
            None
            if recency_half_life_seconds is None
            else max(1.0, float(recency_half_life_seconds))
        )

        # For backward compatibility with old code that expects:
        # decision, confidence, vote_margin = fuse(...)
        self.return_tuple = bool(return_tuple)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def configure_strategy_weights(self, strategy_weights: dict[str, float] | None) -> None:
        self.strategy_weights = {
            str(key).strip(): max(0.0, float(value))
            for key, value in dict(strategy_weights or {}).items()
        }

    def fuse(self, signals: list[Any] | tuple[Any, ...]) -> DecisionOutcome | tuple[str, float, float]:
        outcome = self._fuse(signals)

        if self.return_tuple:
            return outcome.as_tuple()

        return outcome

    def fuse_tuple(self, signals: list[Any] | tuple[Any, ...]) -> tuple[str, float, float]:
        return self._fuse(signals).as_tuple()

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    def _fuse(self, signals: list[Any] | tuple[Any, ...]) -> DecisionOutcome:
        rows = self._normalize_signals(signals)

        if not rows:
            return DecisionOutcome(
                votes={"buy": 0.0, "sell": 0.0, "hold": 1.0},
                winning_side="HOLD",
                confidence=0.0,
                vote_margin=0.0,
                total_score=0.0,
                reason="No valid signals supplied.",
                metadata={"signal_count": 0},
            )

        votes = {"buy": 0.0, "sell": 0.0, "hold": 0.0}
        best_by_side: dict[str, Any] = {}
        best_score_by_side = {"buy": -1.0, "sell": -1.0, "hold": -1.0}

        for row in rows:
            key = row.action.lower()

            if key not in votes:
                key = "hold"

            if key == "hold" and not self.include_hold_votes:
                continue

            votes[key] += row.score

            if row.score > best_score_by_side.get(key, -1.0):
                best_score_by_side[key] = row.score
                best_by_side[key] = row.raw

        buy = votes.get("buy", 0.0)
        sell = votes.get("sell", 0.0)
        hold = votes.get("hold", 0.0)

        directional_total = buy + sell
        total_score = buy + sell + hold

        if directional_total <= 0:
            return DecisionOutcome(
                votes=votes,
                best_by_side=best_by_side,
                winning_side="HOLD",
                selected_signal=best_by_side.get("hold"),
                selected_strategy=self._strategy_name(best_by_side.get(
                    "hold")) if best_by_side.get("hold") else "none",
                confidence=0.0,
                vote_margin=0.0,
                total_score=total_score,
                signal_scores=[row.to_dict() for row in rows],
                reason="No directional BUY or SELL vote.",
                metadata={
                    "signal_count": len(rows),
                    "directional_total": directional_total,
                    "hold_vote": hold,
                },
            )

        vote_margin = abs(buy - sell) / max(directional_total, 1e-12)

        if buy > sell:
            directional_winner = "BUY"
            selected_signal = best_by_side.get("buy")
            directional_winner_score = buy
        elif sell > buy:
            directional_winner = "SELL"
            selected_signal = best_by_side.get("sell")
            directional_winner_score = sell
        else:
            directional_winner = "HOLD"
            selected_signal = best_by_side.get(
                "hold") or self._best_raw_signal(rows)
            directional_winner_score = hold

        confidence_denominator = total_score if self.include_hold_votes else directional_total
        confidence = directional_winner_score / \
            max(confidence_denominator, 1e-12)
        confidence = self._clamp(confidence, 0.0, 1.0)

        if confidence < self.min_confidence:
            return DecisionOutcome(
                votes=votes,
                best_by_side=best_by_side,
                winning_side="HOLD",
                selected_signal=selected_signal,
                selected_strategy=self._strategy_name(selected_signal),
                confidence=confidence,
                vote_margin=vote_margin,
                total_score=total_score,
                signal_scores=[row.to_dict() for row in rows],
                reason=f"Fusion confidence {confidence:.3f} is below minimum {self.min_confidence:.3f}.",
                metadata={
                    "signal_count": len(rows),
                    "directional_winner": directional_winner,
                    "directional_total": directional_total,
                    "hold_vote": hold,
                },
            )

        if vote_margin < self.min_vote_margin:
            return DecisionOutcome(
                votes=votes,
                best_by_side=best_by_side,
                winning_side="HOLD",
                selected_signal=selected_signal,
                selected_strategy=self._strategy_name(selected_signal),
                confidence=confidence * 0.5,
                vote_margin=vote_margin,
                total_score=total_score,
                signal_scores=[row.to_dict() for row in rows],
                reason=f"Weak vote margin {vote_margin:.3f} below threshold {self.min_vote_margin:.3f}.",
                metadata={
                    "signal_count": len(rows),
                    "directional_winner": directional_winner,
                    "directional_total": directional_total,
                    "hold_vote": hold,
                },
            )

        return DecisionOutcome(
            votes=votes,
            best_by_side=best_by_side,
            winning_side=directional_winner,
            selected_signal=selected_signal,
            selected_strategy=self._strategy_name(selected_signal),
            confidence=confidence,
            vote_margin=vote_margin,
            total_score=total_score,
            signal_scores=[row.to_dict() for row in rows],
            reason=f"{directional_winner} won fusion vote with confidence {confidence:.3f} and margin {vote_margin:.3f}.",
            metadata={
                "signal_count": len(rows),
                "directional_total": directional_total,
                "hold_vote": hold,
                "min_vote_margin": self.min_vote_margin,
                "min_confidence": self.min_confidence,
                "include_hold_votes": self.include_hold_votes,
            },
        )

    # ------------------------------------------------------------------
    # Signal normalization
    # ------------------------------------------------------------------

    def _normalize_signals(self, signals: list[Any] | tuple[Any, ...]) -> list[FusionSignalScore]:
        output: list[FusionSignalScore] = []

        now = time.time()

        for signal in list(signals or []):
            action = self._normalize_action(
                self._get(signal, "action", None)
                or self._get(signal, "side", None)
                or self._get(signal, "decision", None)
            )

            confidence = self._safe_float(
                self._get(signal, "confidence", 0.0), 0.0)
            confidence = self._clamp(
                confidence, self.confidence_floor, self.confidence_ceiling)

            strategy_name = self._strategy_name(signal)

            weight = self.default_weight

            if self.use_signal_weight:
                weight *= max(
                    0.0,
                    self._safe_float(
                        self._get(
                            signal,
                            "weight",
                            self._get(signal, "strategy_weight", self._get(
                                signal, "adaptive_weight", 1.0)),
                        ),
                        1.0,
                    ),
                )

            if self.use_strategy_weight and strategy_name in self.strategy_weights:
                weight *= self.strategy_weights[strategy_name]

            recency_weight = self._recency_weight(signal, now)
            weight *= recency_weight

            score = confidence * weight

            if action not in self.VALID_ACTIONS:
                action = "HOLD"

            output.append(
                FusionSignalScore(
                    symbol=str(self._get(signal, "symbol", "")
                               or "").strip().upper(),
                    action=action,
                    confidence=confidence,
                    weight=weight,
                    score=score,
                    strategy_name=strategy_name,
                    reason=str(self._get(signal, "reason", "") or "").strip(),
                    raw=signal,
                )
            )

        return output

    def _recency_weight(self, signal: Any, now: float) -> float:
        if self.recency_half_life_seconds is None:
            return 1.0

        timestamp = (
            self._get(signal, "timestamp", None)
            or self._get(signal, "created_at", None)
            or self._get(signal, "time", None)
        )

        ts = self._timestamp_to_seconds(timestamp)

        if ts is None:
            return 1.0

        age = max(0.0, now - ts)

        # Exponential half-life decay.
        return 0.5 ** (age / self.recency_half_life_seconds)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_action(self, value: Any) -> str:
        text = str(value or "").strip().upper()

        if text in {"BUY", "LONG"}:
            return "BUY"

        if text in {"SELL", "SHORT"}:
            return "SELL"

        if text in {"HOLD", "WAIT", "NONE", "NEUTRAL", ""}:
            return "HOLD"

        return "HOLD"

    def _strategy_name(self, signal: Any) -> str:
        value = (
            self._get(signal, "strategy_name", None)
            or self._get(signal, "strategy", None)
            or self._get(signal, "name", None)
            or "unknown"
        )

        return str(value or "unknown").strip() or "unknown"

    def _best_raw_signal(self, rows: list[FusionSignalScore]) -> Any:
        if not rows:
            return None
        return max(rows, key=lambda row: row.score).raw

    def _get(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return float(default)

        try:
            number = float(value)
        except Exception:
            return float(default)

        if not math.isfinite(number):
            return float(default)

        return number

    def _timestamp_to_seconds(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None

        if isinstance(value, (int, float)):
            number = float(value)
            if abs(number) > 1e11:
                number = number / 1000.0
            return number

        if hasattr(value, "timestamp"):
            try:
                return float(value.timestamp())
            except Exception:
                return None

        text = str(value or "").strip()

        if not text:
            return None

        try:
            number = float(text)
            if abs(number) > 1e11:
                number = number / 1000.0
            return number
        except Exception:
            pass

        # Lightweight ISO timestamp support.
        try:
            from datetime import datetime, timezone

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            parsed = datetime.fromisoformat(text)

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return float(parsed.timestamp())
        except Exception:
            return None

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))
