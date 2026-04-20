from agents.base_agent import BaseAgent


class SignalConsensusAgent(BaseAgent):
    def __init__(self, minimum_votes=2, memory=None, event_bus=None):
        super().__init__("SignalConsensusAgent", memory=memory, event_bus=event_bus)
        self.minimum_votes = max(1, int(minimum_votes or 2))

    def _weighted_score(self, candidate):
        signal = dict((candidate or {}).get("signal") or {})
        confidence = float(signal.get("confidence", 0.0) or 0.0)
        weight = float(signal.get("strategy_assignment_weight", 1.0) or 1.0)
        return confidence * max(0.0001, weight)

    async def process(self, context):
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")

        candidates = [
            dict(candidate)
            for candidate in (working.get("signal_candidates") or [])
            if isinstance(candidate, dict) and isinstance(candidate.get("signal"), dict)
        ]
        if not candidates:
            return working

        vote_table = {}
        for candidate in candidates:
            signal = dict(candidate.get("signal") or {})
            side = str(signal.get("side") or "").strip().lower()
            if side not in {"buy", "sell"}:
                continue
            bucket = vote_table.setdefault(side, {"count": 0, "weighted_score": 0.0})
            bucket["count"] += 1
            bucket["weighted_score"] += self._weighted_score(candidate)

        if not vote_table:
            return working

        ranked = sorted(
            vote_table.items(),
            key=lambda item: (item[1]["count"], item[1]["weighted_score"]),
            reverse=True,
        )
        winner_side, winner = ranked[0]
        runner = ranked[1][1] if len(ranked) > 1 else None

        total_votes = sum(bucket["count"] for bucket in vote_table.values())
        configured_minimum_votes = self.minimum_votes
        minimum_votes = min(configured_minimum_votes, max(1, total_votes))

        winner_count = int(winner["count"])
        winner_weight = float(winner["weighted_score"])
        runner_count = int(runner["count"]) if runner else 0
        runner_weight = float(runner["weighted_score"]) if runner else 0.0

        if len(ranked) == 1:
            status = "unanimous"
        elif winner_count == runner_count:
            status = "split"
        elif winner_count >= minimum_votes:
            status = "majority"
        elif winner_weight > runner_weight:
            status = "weighted"
        else:
            status = "weak"

        confidence = (winner_count / total_votes) if total_votes > 0 else 0.0
        trade_ready = status in {"unanimous", "majority", "weighted"} and confidence >= 0.5

        consensus = {
            "status": status,
            "side": winner_side if trade_ready else "",
            "confidence": round(confidence, 3),
            "trade_ready": trade_ready,
            "vote_count": winner_count,
            "total_votes": total_votes,
            "minimum_votes": minimum_votes,
            "configured_minimum_votes": configured_minimum_votes,
            "votes": vote_table,
            "vote_margin": winner_count - runner_count,
            "weight_margin": winner_weight - runner_weight,
        }
        working["signal_consensus"] = consensus

        if trade_ready:
            working["signal_candidates"] = [
                candidate
                for candidate in candidates
                if str((candidate.get("signal") or {}).get("side") or "").strip().lower() == winner_side
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
                "weight_margin": consensus["weight_margin"],
            },
            symbol=symbol,
            decision_id=decision_id,
        )
        return working
