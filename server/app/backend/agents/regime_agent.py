class RegimeAgent:
    def classify(self, data: dict[str, float]) -> str:
        volatility = float(data.get("volatility", 0))
        trend_strength = float(data.get("trend_strength", 0))

        if volatility >= 0.7:
            return "high-volatility"
        if trend_strength >= 0.6:
            return "trending"
        return "range-bound"

