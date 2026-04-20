from __future__ import annotations

import math

from analytics.metrics import PerformanceSnapshot


class PerformanceEngine:
    def __init__(self) -> None:
        self.returns: list[float] = []
        self.snapshot = PerformanceSnapshot()

    def record_trade(self, *, pnl: float, notional: float, strategy_name: str) -> PerformanceSnapshot:
        pnl_value = float(pnl or 0.0)
        base = max(abs(float(notional or 0.0)), 1e-9)
        trade_return = pnl_value / base
        self.returns.append(trade_return)
        self.snapshot.total_trades += 1
        if pnl_value > 0:
            self.snapshot.wins += 1
        elif pnl_value < 0:
            self.snapshot.losses += 1
        self.snapshot.realized_pnl += pnl_value
        self.snapshot.win_rate = self.snapshot.wins / max(1, self.snapshot.total_trades)
        contribution = dict(self.snapshot.strategy_contribution)
        contribution[str(strategy_name or "unknown")] = contribution.get(str(strategy_name or "unknown"), 0.0) + pnl_value
        self.snapshot.strategy_contribution = contribution
        mean_return = sum(self.returns) / len(self.returns)
        variance = sum((value - mean_return) ** 2 for value in self.returns) / len(self.returns)
        std_return = math.sqrt(max(variance, 0.0))
        self.snapshot.sharpe_ratio = (mean_return / std_return) * math.sqrt(len(self.returns)) if std_return > 0 else 0.0
        return self.snapshot
