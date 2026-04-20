from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PerformanceSnapshot:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    strategy_contribution: dict[str, float] = field(default_factory=dict)
