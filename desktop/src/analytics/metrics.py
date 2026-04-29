from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class PerformanceSnapshot:
    """
    Portfolio/trading performance snapshot.

    This object is intentionally simple and serializable so it can be used by:
    - desktop UI
    - API responses
    - Telegram summaries
    - reports
    - learning engine
    - strategy ranking
    """

    # Core trade counts
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0

    # PnL
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # Ratios / quality
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0

    # Average trade statistics
    average_trade_pnl: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0

    # Capital / equity
    starting_equity: float = 0.0
    current_equity: float = 0.0
    peak_equity: float = 0.0
    total_notional: float = 0.0

    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0

    # Strategy analytics
    strategy_contribution: dict[str, float] = field(default_factory=dict)
    strategy_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Optional chart/report fields
    equity_curve: list[float] = field(default_factory=list)
    recent_returns: list[float] = field(default_factory=list)

    # Metadata
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "breakeven": self.breakeven,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "win_rate": self.win_rate,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "average_trade_pnl": self.average_trade_pnl,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "starting_equity": self.starting_equity,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "total_notional": self.total_notional,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "strategy_contribution": dict(self.strategy_contribution),
            "strategy_stats": dict(self.strategy_stats),
            "equity_curve": list(self.equity_curve),
            "recent_returns": list(self.recent_returns),
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @property
    def net_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_closed_trades(self) -> int:
        return self.wins + self.losses + self.breakeven

    @property
    def loss_rate(self) -> float:
        return self.losses / max(1, self.total_trades)

    @property
    def breakeven_rate(self) -> float:
        return self.breakeven / max(1, self.total_trades)
