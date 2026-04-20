class SignalFusionEngine:
    def fuse(self, signals: List[Signal]):
        buy = sum(s.confidence for s in signals if s.action == "BUY")
        sell = sum(s.confidence for s in signals if s.action == "SELL")

        total = buy + sell
        if total == 0:
            return "HOLD", 0.0, 0.0

        vote_margin = abs(buy - sell) / total
        decision = "BUY" if buy > sell else "SELL"
        confidence = max(buy, sell) / total

        if vote_margin < 0.05:
            return "HOLD", confidence * 0.5, vote_margin

        return decision, confidence, vote_margin