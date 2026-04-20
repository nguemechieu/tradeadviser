from agents.base_agent import BaseAgent


class SignalAggregationAgent(BaseAgent):
    def __init__(self, display_builder=None, publisher=None, memory=None, event_bus=None):
        super().__init__("SignalAggregationAgent", memory=memory, event_bus=event_bus)
        self.display_builder = display_builder
        self.publisher = publisher

    def _candidate_rank(self, candidate):
        signal = dict((candidate or {}).get("signal") or {})
        return (
            float(signal.get("adaptive_score", signal.get("confidence", 0.0)) or 0.0),
            float(signal.get("confidence", 0.0) or 0.0),
            float(signal.get("strategy_assignment_score", 0.0) or 0.0),
        )

    def _build_display_signal(self, working, signal, assigned_strategies):
        if callable(self.display_builder):
            return self.display_builder(working, signal, assigned_strategies)
        if isinstance(signal, dict):
            return dict(signal)
        return {
            "symbol": str((working or {}).get("symbol") or "").strip().upper(),
            "side": "hold",
            "amount": 0.0,
            "confidence": 0.0,
            "reason": str((working or {}).get("signal_hold_reason") or "No entry signal on the latest scan.").strip(),
        }

    def _publish(self, working, display_signal):
        if callable(self.publisher):
            self.publisher(working, display_signal)

    async def process(self, context):
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")
        consensus = dict(working.get("signal_consensus") or {})
        consensus_status = str(consensus.get("status") or "").strip().lower()
        consensus_side = str(consensus.get("side") or "").strip().lower()

        candidates = [
            dict(candidate)
            for candidate in (working.get("signal_candidates") or [])
            if isinstance(candidate, dict) and isinstance(candidate.get("signal"), dict)
        ]
        candidate_count = len(candidates)
        assigned_strategies = list(working.get("assigned_strategies") or [])

        if not candidates:
            reason = "No signal candidates were produced for this symbol."
            working["signal"] = None
            working["signal_hold_reason"] = reason
            working["halt_pipeline"] = True
            display_signal = self._build_display_signal(working, None, assigned_strategies)
            working["display_signal"] = display_signal
            self._publish(working, display_signal)
            self.remember(
                "hold",
                {
                    "reason": reason,
                    "candidate_count": 0,
                    "consensus_side": consensus_side,
                    "consensus_status": consensus_status,
                },
                symbol=symbol,
                decision_id=decision_id,
            )
            return working

        if consensus and not bool(consensus.get("trade_ready")):
            if consensus_status == "split":
                reason = "Signal agents disagreed on direction."
            elif consensus_status == "weak":
                reason = "Signal agents did not reach enough votes to act."
            else:
                reason = "Signal consensus was not trade-ready."
            working["signal"] = None
            working["signal_hold_reason"] = reason
            working["halt_pipeline"] = True
            display_signal = self._build_display_signal(working, None, assigned_strategies)
            working["display_signal"] = display_signal
            self._publish(working, display_signal)
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

        ranked = sorted(candidates, key=self._candidate_rank, reverse=True)
        best = ranked[0]
        signal = dict(best.get("signal") or {})
        assigned_strategies = list(best.get("assigned_strategies") or assigned_strategies)

        signal["signal_source_agent"] = best.get("agent_name")
        signal["consensus_status"] = consensus.get("status")
        signal["consensus_side"] = consensus_side
        signal["consensus_used"] = bool(consensus)
        signal["final_confidence"] = float(consensus.get("confidence", signal.get("confidence", 0.0)) or 0.0)

        working["signal"] = signal
        working["assigned_strategies"] = assigned_strategies
        display_signal = self._build_display_signal(working, signal, assigned_strategies)
        working["display_signal"] = display_signal
        self._publish(working, display_signal)

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
            },
            symbol=symbol,
            decision_id=decision_id,
        )
        return working
