from app.models.trade import Trade


class FeedbackAgent:
    def process(self, trade: Trade) -> dict[str, str | float]:
        pnl_value = float(trade.pnl)
        return {
            "strategy": trade.strategy,
            "symbol": trade.symbol,
            "pnl": pnl_value,
            "feedback": "reinforce" if pnl_value >= 0 else "de-risk",
        }

