from __future__ import annotations

"""
InvestPro SignalAggregationAgent

Aggregates candidate signals produced by multiple SignalAgent instances.

Responsibilities:
- Validate signal candidates
- Respect consensus gate
- Rank candidates by adaptive score, confidence, assignment score, and risk
- Select the strongest trade-ready signal
- Build a display signal for UI/debug panels
- Publish optional UI/debug callback
- Emit event-bus events
- Store agent memory entries

Expected context keys:
    symbol
    decision_id
    signal_candidates
    signal_consensus
    assigned_strategies
    publish_debug
"""

import inspect
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from agents.base_agent import BaseAgent


@dataclass(slots=True)
class AggregationResult:
    status: str
    reason: str
    symbol: str = ""
    decision_id: Optional[str] = None
    selected_signal: Optional[dict[str, Any]] = None
    display_signal: Optional[dict[str, Any]] = None
    candidate_count: int = 0
    consensus_status: str = ""
    consensus_side: str = ""
    selected_agent: str = ""
    selected_strategy: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "symbol": self.symbol,
            "decision_id": self.decision_id,
            "selected_signal": dict(self.selected_signal or {}),
            "display_signal": dict(self.display_signal or {}),
            "candidate_count": self.candidate_count,
            "consensus_status": self.consensus_status,
            "consensus_side": self.consensus_side,
            "selected_agent": self.selected_agent,
            "selected_strategy": self.selected_strategy,
            "metadata": dict(self.metadata or {}),
        }


class SignalAggregationAgent(BaseAgent):
    """Select the final signal from multiple candidate signals."""

    HOLD_REASONS = {
        "no_candidates": "No signal candidates were produced for this symbol.",
        "split": "Signal agents disagreed on direction.",
        "weak": "Signal agents did not reach enough votes to act.",
        "not_ready": "Signal consensus was not trade-ready.",
        "invalid_side": "Selected signal has no valid BUY or SELL side.",
        "low_confidence": "Selected signal confidence is below the minimum threshold.",
    }

    def __init__(
        self,
        display_builder: Any = None,
        publisher: Any = None,
        memory: Any = None,
        event_bus: Any = None,
        *,
        logger: Any = None,
        min_confidence: float = 0.0,
        require_consensus: bool = True,
        allow_hold_signal: bool = False,
        selected_topic: str = "signal.aggregated",
        hold_topic: str = "signal.hold",
        failed_topic: str = "signal.aggregation.failed",
    ) -> None:
        super().__init__(
            "SignalAggregationAgent",
            memory=memory,
            event_bus=event_bus,
            logger=logger,
        )
        self.display_builder = display_builder
        self.publisher = publisher

        self.min_confidence = self._clamp(min_confidence, 0.0, 1.0)
        self.require_consensus = bool(require_consensus)
        self.allow_hold_signal = bool(allow_hold_signal)

        self.selected_topic = str(selected_topic or "signal.aggregated")
        self.hold_topic = str(hold_topic or "signal.hold")
        self.failed_topic = str(failed_topic or "signal.aggregation.failed")

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def _candidate_rank(self, candidate: Any) -> tuple[float, float, float, float, float]:
        """Rank candidates from strongest to weakest.

        Ranking priority:
        1. adaptive_score
        2. final/confidence
        3. strategy assignment score
        4. inverse risk score
        5. recency timestamp
        """
        signal = dict((candidate or {}).get("signal") or {})

        adaptive_score = self._safe_float(
            signal.get("adaptive_score", signal.get("confidence", 0.0)),
            0.0,
        )
        confidence = self._safe_float(
            signal.get("final_confidence", signal.get("confidence", 0.0)),
            0.0,
        )
        assignment_score = self._safe_float(
            signal.get("strategy_assignment_score", 0.0),
            0.0,
        )
        risk_score = self._safe_float(
            signal.get("risk_score", signal.get("risk_estimate", 0.5)),
            0.5,
        )
        recency = self._timestamp_score(signal.get(
            "timestamp") or candidate.get("timestamp"))

        return (
            adaptive_score,
            confidence,
            assignment_score,
            1.0 - self._clamp(risk_score, 0.0, 1.0),
            recency,
        )

    def _normalize_candidates(self, candidates: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []

        for candidate in list(candidates or []):
            if not isinstance(candidate, dict):
                continue

            signal = candidate.get("signal")
            if not isinstance(signal, dict):
                continue

            normalized = dict(candidate)
            normalized["signal"] = dict(signal)
            output.append(normalized)

        return output

    # ------------------------------------------------------------------
    # Display / publish
    # ------------------------------------------------------------------

    def _build_display_signal(
        self,
        working: dict[str, Any],
        signal: Optional[dict[str, Any]],
        assigned_strategies: list[Any],
    ) -> dict[str, Any]:
        if callable(self.display_builder):
            try:
                result = self.display_builder(
                    working, signal, assigned_strategies)
                if isinstance(result, dict):
                    return result
            except Exception as exc:
                self._log_error("Signal display builder failed: %s", exc)

        if isinstance(signal, dict):
            display = dict(signal)
            display.setdefault("symbol", str(
                (working or {}).get("symbol") or "").strip().upper())
            return self._json_safe(display)

        return {
            "symbol": str((working or {}).get("symbol") or "").strip().upper(),
            "side": "hold",
            "amount": 0.0,
            "confidence": 0.0,
            "reason": str(
                (working or {}).get("signal_hold_reason")
                or "No entry signal on the latest scan."
            ).strip(),
        }

    async def _publish_callback(self, working: dict[str, Any], display_signal: dict[str, Any]) -> None:
        if not callable(self.publisher):
            return

        try:
            result = self.publisher(working, display_signal)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self._log_error("Signal publisher callback failed: %s", exc)

    async def _emit_result(self, result: AggregationResult) -> None:
        topic = self.selected_topic if result.status == "selected" else self.hold_topic
        await self.emit(
            topic,
            result.to_dict(),
            symbol=result.symbol,
            decision_id=result.decision_id,
            remember=False,
        )

    # ------------------------------------------------------------------
    # Process
    # ------------------------------------------------------------------

    async def process(self, context: Any) -> dict[str, Any]:
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")

        consensus = dict(working.get("signal_consensus") or {})
        consensus_status = str(consensus.get("status") or "").strip().lower()
        consensus_side = str(consensus.get("side") or "").strip().lower()

        candidates = self._normalize_candidates(
            working.get("signal_candidates") or [])
        candidate_count = len(candidates)
        assigned_strategies = list(working.get("assigned_strategies") or [])

        if not candidates:
            return await self._hold(
                working=working,
                reason=self.HOLD_REASONS["no_candidates"],
                candidate_count=0,
                consensus=consensus,
                consensus_status=consensus_status,
                consensus_side=consensus_side,
                assigned_strategies=assigned_strategies,
                symbol=symbol,
                decision_id=decision_id,
            )

        if self.require_consensus and consensus and not bool(consensus.get("trade_ready")):
            if consensus_status == "split":
                reason = self.HOLD_REASONS["split"]
            elif consensus_status == "weak":
                reason = self.HOLD_REASONS["weak"]
            else:
                reason = self.HOLD_REASONS["not_ready"]

            return await self._hold(
                working=working,
                reason=reason,
                candidate_count=candidate_count,
                consensus=consensus,
                consensus_status=consensus_status,
                consensus_side=consensus_side,
                assigned_strategies=assigned_strategies,
                symbol=symbol,
                decision_id=decision_id,
            )

        ranked = sorted(candidates, key=self._candidate_rank, reverse=True)
        best = ranked[0]
        signal = dict(best.get("signal") or {})
        assigned_strategies = list(
            best.get("assigned_strategies") or assigned_strategies)

        signal_side = self._normalize_side(signal.get(
            "side") or signal.get("action") or signal.get("decision"))
        signal_confidence = self._safe_float(
            consensus.get("confidence", signal.get(
                "final_confidence", signal.get("confidence", 0.0))),
            0.0,
        )

        if signal_side == "HOLD" and not self.allow_hold_signal:
            return await self._hold(
                working=working,
                reason=self.HOLD_REASONS["invalid_side"],
                candidate_count=candidate_count,
                consensus=consensus,
                consensus_status=consensus_status,
                consensus_side=consensus_side,
                assigned_strategies=assigned_strategies,
                symbol=symbol,
                decision_id=decision_id,
                ranked_candidates=ranked,
            )

        if signal_confidence < self.min_confidence:
            return await self._hold(
                working=working,
                reason=f"{self.HOLD_REASONS['low_confidence']} ({signal_confidence:.3f} < {self.min_confidence:.3f}).",
                candidate_count=candidate_count,
                consensus=consensus,
                consensus_status=consensus_status,
                consensus_side=consensus_side,
                assigned_strategies=assigned_strategies,
                symbol=symbol,
                decision_id=decision_id,
                ranked_candidates=ranked,
            )

        signal["side"] = signal_side.lower()
        signal["signal_source_agent"] = best.get(
            "agent_name") or signal.get("signal_source_agent")
        signal["consensus_status"] = consensus.get("status")
        signal["consensus_side"] = consensus_side
        signal["consensus_used"] = bool(consensus)
        signal["final_confidence"] = signal_confidence
        signal["candidate_count"] = candidate_count
        signal["aggregation_rank"] = 1
        signal["aggregation_score"] = self._candidate_rank(best)[0]
        signal["decision_id"] = signal.get("decision_id") or decision_id
        signal["symbol"] = signal.get("symbol") or symbol

        working["signal"] = signal
        working["assigned_strategies"] = assigned_strategies
        working["halt_pipeline"] = False
        working["signal_aggregation"] = {
            "status": "selected",
            "candidate_count": candidate_count,
            "selected_agent": signal.get("signal_source_agent"),
            "selected_strategy": signal.get("strategy_name"),
            "ranked_candidates": self._ranked_preview(ranked),
        }

        display_signal = self._build_display_signal(
            working, signal, assigned_strategies)
        working["display_signal"] = display_signal

        await self._publish_callback(working, display_signal)

        result = AggregationResult(
            status="selected",
            reason=str(signal.get("reason")
                       or "Selected strongest aggregated signal.").strip(),
            symbol=symbol,
            decision_id=str(decision_id) if decision_id else None,
            selected_signal=signal,
            display_signal=display_signal,
            candidate_count=candidate_count,
            consensus_status=str(signal.get("consensus_status") or ""),
            consensus_side=consensus_side,
            selected_agent=str(signal.get("signal_source_agent") or ""),
            selected_strategy=str(signal.get("strategy_name") or ""),
            metadata={
                "ranked_candidates": self._ranked_preview(ranked),
                "assigned_strategies": self._json_safe(assigned_strategies),
            },
        )

        await self._emit_result(result)

        self.remember(
            "selected",
            {
                "reason": signal.get("reason"),
                "side": signal.get("side"),
                "confidence": signal.get("final_confidence"),
                "strategy_name": signal.get("strategy_name"),
                "candidate_count": candidate_count,
                "signal_source_agent": signal.get("signal_source_agent"),
                "consensus_side": consensus_side,
                "consensus_status": signal.get("consensus_status"),
                "consensus_used": signal.get("consensus_used"),
                "adaptive_weight": signal.get("adaptive_weight"),
                "adaptive_sample_size": signal.get("adaptive_sample_size"),
                "aggregation_score": signal.get("aggregation_score"),
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        return working

    async def _hold(
        self,
        *,
        working: dict[str, Any],
        reason: str,
        candidate_count: int,
        consensus: dict[str, Any],
        consensus_status: str,
        consensus_side: str,
        assigned_strategies: list[Any],
        symbol: str,
        decision_id: Any,
        ranked_candidates: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        working["signal"] = None
        working["signal_hold_reason"] = reason
        working["halt_pipeline"] = True

        display_signal = self._build_display_signal(
            working, None, assigned_strategies)
        working["display_signal"] = display_signal
        working["signal_aggregation"] = {
            "status": "hold",
            "reason": reason,
            "candidate_count": candidate_count,
            "consensus_side": consensus_side,
            "consensus_status": consensus_status,
            "ranked_candidates": self._ranked_preview(ranked_candidates or []),
        }

        await self._publish_callback(working, display_signal)

        result = AggregationResult(
            status="hold",
            reason=reason,
            symbol=symbol,
            decision_id=str(decision_id) if decision_id else None,
            selected_signal=None,
            display_signal=display_signal,
            candidate_count=candidate_count,
            consensus_status=consensus_status,
            consensus_side=consensus_side,
            metadata={
                "consensus": self._json_safe(consensus),
                "ranked_candidates": self._ranked_preview(ranked_candidates or []),
            },
        )

        await self._emit_result(result)

        self.remember(
            "hold",
            {
                "reason": reason,
                "candidate_count": candidate_count,
                "consensus_side": consensus_side,
                "consensus_status": consensus_status,
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        return working

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ranked_preview(self, ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []

        for index, candidate in enumerate(list(ranked or [])[:10], start=1):
            signal = dict(candidate.get("signal") or {})
            output.append(
                {
                    "rank": index,
                    "agent_name": candidate.get("agent_name"),
                    "side": self._normalize_side(signal.get("side") or signal.get("action") or signal.get("decision")),
                    "confidence": self._safe_float(signal.get("confidence"), 0.0),
                    "final_confidence": self._safe_float(signal.get("final_confidence", signal.get("confidence")), 0.0),
                    "adaptive_score": self._safe_float(signal.get("adaptive_score", signal.get("confidence")), 0.0),
                    "strategy_name": signal.get("strategy_name"),
                    "reason": signal.get("reason"),
                    "rank_score": self._candidate_rank(candidate),
                }
            )

        return self._json_safe(output)

    def _normalize_side(self, value: Any) -> str:
        text = str(value or "").strip().upper()

        if text in {"BUY", "LONG"}:
            return "BUY"

        if text in {"SELL", "SHORT"}:
            return "SELL"

        return "HOLD"

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

    def _timestamp_score(self, value: Any) -> float:
        if value in (None, ""):
            return 0.0

        if isinstance(value, (int, float)):
            timestamp = float(value)
            if abs(timestamp) > 1e11:
                timestamp = timestamp / 1000.0
            return timestamp

        if hasattr(value, "timestamp"):
            try:
                return float(value.timestamp())
            except Exception:
                return 0.0

        text = str(value or "").strip()
        if not text:
            return 0.0

        try:
            timestamp = float(text)
            if abs(timestamp) > 1e11:
                timestamp = timestamp / 1000.0
            return timestamp
        except Exception:
            pass

        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return float(parsed.timestamp())
        except Exception:
            return 0.0

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))
