from __future__ import annotations

"""
InvestPro SignalConsensusAgent

Builds consensus across multiple signal candidates.

Expected context:
    {
        "symbol": "BTC/USDT",
        "decision_id": "...",
        "signal_candidates": [
            {
                "agent_name": "SignalAgent",
                "signal": {
                    "side": "buy",
                    "confidence": 0.72,
                    "strategy_assignment_weight": 1.10,
                    "adaptive_weight": 1.05,
                    ...
                }
            }
        ]
    }

Output added to context:
    context["signal_consensus"] = {
        "status": "unanimous|majority|weighted|split|weak|empty",
        "side": "buy|sell|",
        "confidence": 0.0-1.0,
        "trade_ready": bool,
        ...
    }

If trade_ready is True, signal_candidates are filtered to the winning side.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import BaseAgent


@dataclass(slots=True)
class ConsensusVote:
    side: str
    count: int = 0
    weighted_score: float = 0.0
    confidence_sum: float = 0.0
    max_confidence: float = 0.0
    agents: list[str] = field(default_factory=list)
    strategies: list[str] = field(default_factory=list)

    @property
    def average_confidence(self) -> float:
        if self.count <= 0:
            return 0.0
        return self.confidence_sum / float(self.count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "count": self.count,
            "weighted_score": self.weighted_score,
            "confidence_sum": self.confidence_sum,
            "average_confidence": self.average_confidence,
            "max_confidence": self.max_confidence,
            "agents": list(self.agents),
            "strategies": list(self.strategies),
        }


class SignalConsensusAgent(BaseAgent):
    """Vote across signal candidates and decide whether the signal set is trade-ready."""

    def __init__(
        self,
        minimum_votes: int = 2,
        memory: Any = None,
        event_bus: Any = None,
        *,
        logger: Any = None,
        minimum_confidence: float = 0.50,
        minimum_weight_margin: float = 0.0,
        minimum_vote_margin: int = 1,
        use_adaptive_weight: bool = True,
        use_strategy_assignment_weight: bool = True,
        consensus_topic: str = "signal.consensus",
        split_is_trade_ready: bool = False,
        weighted_is_trade_ready: bool = True,
    ) -> None:
        super().__init__(
            "SignalConsensusAgent",
            memory=memory,
            event_bus=event_bus,
            logger=logger,
        )

        self.minimum_votes = max(1, int(minimum_votes or 2))
        self.minimum_confidence = self._clamp(minimum_confidence, 0.0, 1.0)
        self.minimum_weight_margin = max(
            0.0, float(minimum_weight_margin or 0.0))
        self.minimum_vote_margin = max(0, int(minimum_vote_margin or 0))

        self.use_adaptive_weight = bool(use_adaptive_weight)
        self.use_strategy_assignment_weight = bool(
            use_strategy_assignment_weight)

        self.consensus_topic = str(consensus_topic or "signal.consensus")
        self.split_is_trade_ready = bool(split_is_trade_ready)
        self.weighted_is_trade_ready = bool(weighted_is_trade_ready)

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------

    def _weighted_score(self, candidate: Any) -> float:
        signal = dict((candidate or {}).get("signal") or {})

        confidence = self._safe_float(signal.get("confidence"), 0.0)
        confidence = self._clamp(confidence, 0.0, 1.0)

        weight = 1.0

        if self.use_strategy_assignment_weight:
            weight *= max(
                0.0001,
                self._safe_float(signal.get(
                    "strategy_assignment_weight"), 1.0),
            )

        if self.use_adaptive_weight:
            weight *= max(
                0.0001,
                self._safe_float(signal.get("adaptive_weight"), 1.0),
            )

        extra_weight = self._safe_float(signal.get("weight"), 1.0)
        weight *= max(0.0001, extra_weight)

        return confidence * weight

    def _normalize_side(self, value: Any) -> str:
        text = str(value or "").strip().lower()

        if text in {"buy", "long"}:
            return "buy"

        if text in {"sell", "short"}:
            return "sell"

        return ""

    def _normalize_candidates(self, candidates: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []

        for candidate in list(candidates or []):
            if not isinstance(candidate, dict):
                continue

            signal = candidate.get("signal")
            if not isinstance(signal, dict):
                continue

            side = self._normalize_side(
                signal.get("side")
                or signal.get("action")
                or signal.get("decision")
            )

            if side not in {"buy", "sell"}:
                continue

            normalized = dict(candidate)
            normalized["signal"] = dict(signal)
            normalized["normalized_side"] = side
            output.append(normalized)

        return output

    def _build_vote_table(self, candidates: list[dict[str, Any]]) -> dict[str, ConsensusVote]:
        vote_table: dict[str, ConsensusVote] = {}

        for candidate in candidates:
            signal = dict(candidate.get("signal") or {})
            side = str(candidate.get("normalized_side") or "").strip().lower()

            if side not in {"buy", "sell"}:
                continue

            bucket = vote_table.setdefault(side, ConsensusVote(side=side))

            confidence = self._clamp(
                self._safe_float(signal.get("confidence"), 0.0),
                0.0,
                1.0,
            )
            score = self._weighted_score(candidate)

            bucket.count += 1
            bucket.weighted_score += score
            bucket.confidence_sum += confidence
            bucket.max_confidence = max(bucket.max_confidence, confidence)

            agent_name = str(candidate.get("agent_name") or signal.get(
                "signal_source_agent") or "").strip()
            strategy_name = str(signal.get("strategy_name") or "").strip()

            if agent_name and agent_name not in bucket.agents:
                bucket.agents.append(agent_name)

            if strategy_name and strategy_name not in bucket.strategies:
                bucket.strategies.append(strategy_name)

        return vote_table

    # ------------------------------------------------------------------
    # Main process
    # ------------------------------------------------------------------

    async def process(self, context: Any) -> dict[str, Any]:
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")

        candidates = self._normalize_candidates(
            working.get("signal_candidates") or [])

        if not candidates:
            consensus = self._empty_consensus()
            working["signal_consensus"] = consensus

            self.remember(
                "empty",
                consensus,
                symbol=symbol,
                decision_id=decision_id,
            )

            await self.emit(
                self.consensus_topic,
                {
                    "symbol": symbol,
                    "decision_id": decision_id,
                    **consensus,
                },
                symbol=symbol,
                decision_id=decision_id,
            )

            return working

        vote_table = self._build_vote_table(candidates)

        if not vote_table:
            consensus = self._empty_consensus(
                status="empty", reason="No directional BUY/SELL votes were found.")
            working["signal_consensus"] = consensus

            self.remember(
                "empty",
                consensus,
                symbol=symbol,
                decision_id=decision_id,
            )

            await self.emit(
                self.consensus_topic,
                {
                    "symbol": symbol,
                    "decision_id": decision_id,
                    **consensus,
                },
                symbol=symbol,
                decision_id=decision_id,
            )

            return working

        ranked = sorted(
            vote_table.items(),
            key=lambda item: (
                item[1].count,
                item[1].weighted_score,
                item[1].average_confidence,
                item[1].max_confidence,
            ),
            reverse=True,
        )

        winner_side, winner = ranked[0]
        runner = ranked[1][1] if len(ranked) > 1 else None

        total_votes = sum(bucket.count for bucket in vote_table.values())
        total_weight = sum(
            bucket.weighted_score for bucket in vote_table.values())

        configured_minimum_votes = self.minimum_votes
        minimum_votes = min(configured_minimum_votes, max(1, total_votes))

        winner_count = int(winner.count)
        winner_weight = float(winner.weighted_score)
        winner_avg_confidence = float(winner.average_confidence)
        winner_max_confidence = float(winner.max_confidence)

        runner_count = int(runner.count) if runner else 0
        runner_weight = float(runner.weighted_score) if runner else 0.0

        count_margin = winner_count - runner_count
        weight_margin = winner_weight - runner_weight

        normalized_vote_margin = count_margin / max(total_votes, 1)
        normalized_weight_margin = weight_margin / max(total_weight, 1e-12)

        if len(ranked) == 1 and winner_count >= minimum_votes:
            status = "unanimous"
        elif len(ranked) > 1 and winner_count == runner_count:
            status = "split"
        elif winner_count >= minimum_votes and count_margin >= self.minimum_vote_margin:
            status = "majority"
        elif (
            self.weighted_is_trade_ready
            and weight_margin > self.minimum_weight_margin
            and winner_avg_confidence >= self.minimum_confidence
        ):
            status = "weighted"
        else:
            status = "weak"

        confidence = self._calculate_consensus_confidence(
            winner=winner,
            total_votes=total_votes,
            total_weight=total_weight,
            normalized_vote_margin=normalized_vote_margin,
            normalized_weight_margin=normalized_weight_margin,
        )

        confidence = round(self._clamp(confidence, 0.0, 1.0), 3)

        trade_ready = self._is_trade_ready(
            status=status,
            confidence=confidence,
            winner_count=winner_count,
            minimum_votes=minimum_votes,
            count_margin=count_margin,
            weight_margin=weight_margin,
        )

        consensus = {
            "status": status,
            "reason": self._reason_for_status(
                status=status,
                winner_side=winner_side,
                winner_count=winner_count,
                total_votes=total_votes,
                confidence=confidence,
            ),
            "side": winner_side if trade_ready else "",
            "confidence": confidence,
            "trade_ready": trade_ready,
            "vote_count": winner_count,
            "total_votes": total_votes,
            "minimum_votes": minimum_votes,
            "configured_minimum_votes": configured_minimum_votes,
            "votes": {
                side: bucket.to_dict()
                for side, bucket in vote_table.items()
            },
            "vote_margin": count_margin,
            "normalized_vote_margin": round(normalized_vote_margin, 3),
            "weight_margin": round(weight_margin, 6),
            "normalized_weight_margin": round(normalized_weight_margin, 3),
            "winner_weight": round(winner_weight, 6),
            "runner_weight": round(runner_weight, 6),
            "winner_average_confidence": round(winner_avg_confidence, 3),
            "winner_max_confidence": round(winner_max_confidence, 3),
            "minimum_confidence": self.minimum_confidence,
            "minimum_weight_margin": self.minimum_weight_margin,
            "minimum_vote_margin": self.minimum_vote_margin,
        }

        working["signal_consensus"] = consensus

        if trade_ready:
            working["signal_candidates"] = [
                candidate
                for candidate in candidates
                if str(candidate.get("normalized_side") or "").strip().lower() == winner_side
            ]

        self.remember(
            status,
            {
                "side": consensus["side"],
                "confidence": consensus["confidence"],
                "trade_ready": trade_ready,
                "vote_count": consensus["vote_count"],
                "total_votes": consensus["total_votes"],
                "minimum_votes": consensus["minimum_votes"],
                "configured_minimum_votes": consensus["configured_minimum_votes"],
                "vote_margin": consensus["vote_margin"],
                "normalized_vote_margin": consensus["normalized_vote_margin"],
                "weight_margin": consensus["weight_margin"],
                "normalized_weight_margin": consensus["normalized_weight_margin"],
                "winner_weight": consensus["winner_weight"],
                "runner_weight": consensus["runner_weight"],
                "winner_average_confidence": consensus["winner_average_confidence"],
                "votes": consensus["votes"],
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        await self.emit(
            self.consensus_topic,
            {
                "symbol": symbol,
                "decision_id": decision_id,
                **consensus,
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        return working

    # ------------------------------------------------------------------
    # Decision helpers
    # ------------------------------------------------------------------

    def _calculate_consensus_confidence(
        self,
        *,
        winner: ConsensusVote,
        total_votes: int,
        total_weight: float,
        normalized_vote_margin: float,
        normalized_weight_margin: float,
    ) -> float:
        vote_share = winner.count / max(total_votes, 1)
        weight_share = winner.weighted_score / max(total_weight, 1e-12)
        avg_confidence = winner.average_confidence

        confidence = (
            0.40 * vote_share
            + 0.35 * weight_share
            + 0.15 * avg_confidence
            + 0.05 * max(0.0, normalized_vote_margin)
            + 0.05 * max(0.0, normalized_weight_margin)
        )

        return confidence

    def _is_trade_ready(
        self,
        *,
        status: str,
        confidence: float,
        winner_count: int,
        minimum_votes: int,
        count_margin: int,
        weight_margin: float,
    ) -> bool:
        if status == "split":
            return self.split_is_trade_ready and confidence >= self.minimum_confidence

        if status == "unanimous":
            return winner_count >= minimum_votes and confidence >= self.minimum_confidence

        if status == "majority":
            return (
                winner_count >= minimum_votes
                and count_margin >= self.minimum_vote_margin
                and confidence >= self.minimum_confidence
            )

        if status == "weighted":
            return (
                self.weighted_is_trade_ready
                and weight_margin > self.minimum_weight_margin
                and confidence >= self.minimum_confidence
            )

        return False

    def _reason_for_status(
        self,
        *,
        status: str,
        winner_side: str,
        winner_count: int,
        total_votes: int,
        confidence: float,
    ) -> str:
        if status == "unanimous":
            return f"All directional signal agents agree on {winner_side.upper()}."

        if status == "majority":
            return f"Signal agents reached a majority {winner_side.upper()} vote: {winner_count}/{total_votes}."

        if status == "weighted":
            return f"Weighted signal confidence favors {winner_side.upper()}."

        if status == "split":
            return "Signal agents are split across directions."

        if status == "weak":
            return f"Signal consensus is weak with confidence {confidence:.3f}."

        return "No usable signal consensus was found."

    def _empty_consensus(self, *, status: str = "empty", reason: str = "No signal candidates were available.") -> dict[str, Any]:
        return {
            "status": status,
            "reason": reason,
            "side": "",
            "confidence": 0.0,
            "trade_ready": False,
            "vote_count": 0,
            "total_votes": 0,
            "minimum_votes": self.minimum_votes,
            "configured_minimum_votes": self.minimum_votes,
            "votes": {},
            "vote_margin": 0,
            "normalized_vote_margin": 0.0,
            "weight_margin": 0.0,
            "normalized_weight_margin": 0.0,
            "winner_weight": 0.0,
            "runner_weight": 0.0,
            "winner_average_confidence": 0.0,
            "winner_max_confidence": 0.0,
            "minimum_confidence": self.minimum_confidence,
            "minimum_weight_margin": self.minimum_weight_margin,
            "minimum_vote_margin": self.minimum_vote_margin,
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

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

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))
