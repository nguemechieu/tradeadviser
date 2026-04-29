from __future__ import annotations

"""
InvestPro Performance Engine

Tracks trading performance metrics from closed trades/fill events.

Features:
- Total trades
- Wins / losses / breakeven
- Win rate
- Realized PnL
- Return series
- Equity curve
- Peak equity
- Max drawdown
- Max drawdown percent
- Sharpe ratio
- Sortino ratio
- Profit factor
- Expectancy
- Average win
- Average loss
- Best trade
- Worst trade
- Per-strategy contribution
- Per-strategy statistics
- Snapshot compatibility with analytics.metrics.PerformanceSnapshot

This engine should be updated after a trade is closed or realized PnL changes.
"""

import math
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from analytics.metrics import PerformanceSnapshot


EPSILON = 1e-12


@dataclass(slots=True)
class StrategyPerformance:
    strategy_name: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    realized_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    total_notional: float = 0.0
    returns: list[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / max(1, self.total_trades)

    @property
    def profit_factor(self) -> float:
        loss_abs = abs(self.gross_loss)
        if loss_abs <= EPSILON:
            return float("inf") if self.gross_profit > 0 else 0.0
        return self.gross_profit / loss_abs

    @property
    def average_pnl(self) -> float:
        return self.realized_pnl / max(1, self.total_trades)

    @property
    def average_win(self) -> float:
        return self.gross_profit / max(1, self.wins)

    @property
    def average_loss(self) -> float:
        return self.gross_loss / max(1, self.losses)

    @property
    def expectancy(self) -> float:
        loss_rate = self.losses / max(1, self.total_trades)
        return (self.win_rate * self.average_win) + (loss_rate * self.average_loss)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "breakeven": self.breakeven,
            "win_rate": self.win_rate,
            "realized_pnl": self.realized_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "average_pnl": self.average_pnl,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "expectancy": self.expectancy,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "total_notional": self.total_notional,
            "return_count": len(self.returns),
        }


@dataclass(slots=True)
class TradePerformanceRecord:
    timestamp: str
    pnl: float
    notional: float
    trade_return: float
    strategy_name: str
    symbol: str = ""
    side: str = ""
    order_id: str = ""
    trade_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "pnl": self.pnl,
            "notional": self.notional,
            "trade_return": self.trade_return,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "side": self.side,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "metadata": self.metadata,
        }


class PerformanceEngine:
    """Track realized trading performance.

    This class updates a PerformanceSnapshot while also maintaining richer local
    state for analytics and UI dashboards.
    """

    def __init__(
        self,
        *,
        starting_equity: float = 0.0,
        risk_free_rate: float = 0.0,
        annualization_factor: Optional[float] = None,
        snapshot: Optional[PerformanceSnapshot] = None,
        max_history: int = 10_000,
    ) -> None:
        self.starting_equity = self._safe_float(starting_equity, 0.0)
        self.current_equity = self.starting_equity
        self.peak_equity = self.starting_equity
        self.risk_free_rate = self._safe_float(risk_free_rate, 0.0)
        self.annualization_factor = annualization_factor
        self.max_history = max(100, int(max_history or 10_000))

        self.returns: list[float] = []
        self.equity_curve: list[float] = [self.current_equity]
        self.trade_history: list[TradePerformanceRecord] = []
        self.strategy_stats: dict[str, StrategyPerformance] = {}

        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.best_trade = 0.0
        self.worst_trade = 0.0
        self.total_notional = 0.0
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        self.breakeven = 0

        self.snapshot = snapshot or PerformanceSnapshot()
        self._sync_snapshot()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_trade(
        self,
        *,
        pnl: float,
        notional: float,
        strategy_name: str,
        symbol: str = "",
        side: str = "",
        order_id: str = "",
        trade_id: str = "",
        timestamp: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PerformanceSnapshot:
        """Record a realized trade result and return updated snapshot."""
        pnl_value = self._safe_float(pnl, 0.0)
        notional_value = abs(self._safe_float(notional, 0.0))
        base = max(notional_value, EPSILON)
        trade_return = pnl_value / base

        strategy_key = str(strategy_name or "unknown").strip() or "unknown"

        record = TradePerformanceRecord(
            timestamp=timestamp or self._utc_now(),
            pnl=pnl_value,
            notional=notional_value,
            trade_return=trade_return,
            strategy_name=strategy_key,
            symbol=str(symbol or "").strip().upper(),
            side=str(side or "").strip().lower(),
            order_id=str(order_id or "").strip(),
            trade_id=str(trade_id or "").strip(),
            metadata=dict(metadata or {}),
        )

        self._append_trade(record)
        self._update_global_metrics(record)
        self._update_strategy_metrics(record)
        self._sync_snapshot()

        return self.snapshot

    def record_trade_event(self, trade: dict[str, Any]) -> PerformanceSnapshot:
        """Record performance from a trade dictionary.

        Useful when called from broker fill/close events.
        """
        if not isinstance(trade, dict):
            raise TypeError("trade must be a dictionary")

        pnl = self._first_float(
            trade,
            "pnl",
            "realized_pnl",
            "realized_pl",
            "profit",
            "profit_loss",
            default=0.0,
        )

        notional = self._infer_notional(trade)

        return self.record_trade(
            pnl=pnl,
            notional=notional,
            strategy_name=str(trade.get("strategy_name")
                              or trade.get("strategy") or "unknown"),
            symbol=str(trade.get("symbol") or ""),
            side=str(trade.get("side") or trade.get("position_side") or ""),
            order_id=str(trade.get("order_id") or trade.get("id") or ""),
            trade_id=str(trade.get("trade_id")
                         or trade.get("position_id") or ""),
            timestamp=str(trade.get("timestamp") or self._utc_now()),
            metadata={
                "raw_status": trade.get("status"),
                "source": trade.get("source"),
                "broker": trade.get("broker") or trade.get("exchange"),
            },
        )

    def get_snapshot(self) -> PerformanceSnapshot:
        self._sync_snapshot()
        return self.snapshot

    def get_metrics(self) -> dict[str, Any]:
        """Return full metrics as a dictionary for APIs/UI."""
        self._sync_snapshot()

        return {
            "starting_equity": self.starting_equity,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "total_trades": self._snapshot_get("total_trades", 0),
            "wins": self._snapshot_get("wins", 0),
            "losses": self._snapshot_get("losses", 0),
            "breakeven": self.breakeven,
            "win_rate": self._snapshot_get("win_rate", 0.0),
            "realized_pnl": self._snapshot_get("realized_pnl", 0.0),
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "average_trade_pnl": self.average_trade_pnl,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "total_notional": self.total_notional,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self._snapshot_get("sharpe_ratio", 0.0),
            "sortino_ratio": self.sortino_ratio,
            "strategy_contribution": dict(self._snapshot_get("strategy_contribution", {}) or {}),
            "strategy_stats": {
                name: stats.to_dict()
                for name, stats in self.strategy_stats.items()
            },
            "return_count": len(self.returns),
            "equity_curve": list(self.equity_curve),
        }

    def get_strategy_metrics(self, strategy_name: str) -> dict[str, Any]:
        key = str(strategy_name or "unknown").strip() or "unknown"
        stats = self.strategy_stats.get(key)

        if stats is None:
            return StrategyPerformance(strategy_name=key).to_dict()

        return stats.to_dict()

    def get_trade_history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        records = self.trade_history[-int(limit):] if limit else self.trade_history
        return [record.to_dict() for record in records]

    def reset(self, *, starting_equity: Optional[float] = None) -> PerformanceSnapshot:
        """Reset all performance state."""
        if starting_equity is not None:
            self.starting_equity = self._safe_float(starting_equity, 0.0)

        self.current_equity = self.starting_equity
        self.peak_equity = self.starting_equity
        self.returns.clear()
        self.equity_curve = [self.current_equity]
        self.trade_history.clear()
        self.strategy_stats.clear()

        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.best_trade = 0.0
        self.worst_trade = 0.0
        self.total_notional = 0.0
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        self.breakeven = 0

        self.snapshot = PerformanceSnapshot()
        self._sync_snapshot()

        return self.snapshot

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def profit_factor(self) -> float:
        loss_abs = abs(self.gross_loss)
        if loss_abs <= EPSILON:
            return float("inf") if self.gross_profit > 0 else 0.0
        return self.gross_profit / loss_abs

    @property
    def average_trade_pnl(self) -> float:
        total_trades = int(self._snapshot_get("total_trades", 0) or 0)
        realized_pnl = float(self._snapshot_get("realized_pnl", 0.0) or 0.0)
        return realized_pnl / max(1, total_trades)

    @property
    def average_win(self) -> float:
        wins = int(self._snapshot_get("wins", 0) or 0)
        return self.gross_profit / max(1, wins)

    @property
    def average_loss(self) -> float:
        losses = int(self._snapshot_get("losses", 0) or 0)
        return self.gross_loss / max(1, losses)

    @property
    def expectancy(self) -> float:
        total = int(self._snapshot_get("total_trades", 0) or 0)
        if total <= 0:
            return 0.0

        win_rate = float(self._snapshot_get("win_rate", 0.0) or 0.0)
        loss_rate = int(self._snapshot_get("losses", 0) or 0) / max(1, total)

        return (win_rate * self.average_win) + (loss_rate * self.average_loss)

    @property
    def sortino_ratio(self) -> float:
        if not self.returns:
            return 0.0

        mean_return = self._mean(self.returns)
        downside = [min(0.0, value - self.risk_free_rate)
                    for value in self.returns]
        downside_variance = self._mean([value * value for value in downside])

        if downside_variance <= EPSILON:
            return 0.0

        raw = (mean_return - self.risk_free_rate) / \
            math.sqrt(downside_variance)
        return raw * self._annualization_multiplier()

    # ------------------------------------------------------------------
    # Internal update logic
    # ------------------------------------------------------------------

    def _append_trade(self, record: TradePerformanceRecord) -> None:
        self.trade_history.append(record)
        self.returns.append(record.trade_return)

        if len(self.trade_history) > self.max_history:
            self.trade_history = self.trade_history[-self.max_history:]

        if len(self.returns) > self.max_history:
            self.returns = self.returns[-self.max_history:]

    def _update_global_metrics(self, record: TradePerformanceRecord) -> None:
        self.current_equity += record.pnl
        self.peak_equity = max(self.peak_equity, self.current_equity)
        self.equity_curve.append(self.current_equity)

        if len(self.equity_curve) > self.max_history:
            self.equity_curve = self.equity_curve[-self.max_history:]

        drawdown = self.peak_equity - self.current_equity
        self.max_drawdown = max(self.max_drawdown, drawdown)

        if abs(self.peak_equity) > EPSILON:
            drawdown_pct = drawdown / abs(self.peak_equity)
            self.max_drawdown_pct = max(self.max_drawdown_pct, drawdown_pct)

        self.total_notional += record.notional

        total_trades = int(self._snapshot_get("total_trades", 0) or 0) + 1
        wins = int(self._snapshot_get("wins", 0) or 0)
        losses = int(self._snapshot_get("losses", 0) or 0)

        if record.pnl > 0:
            wins += 1
            self.gross_profit += record.pnl
        elif record.pnl < 0:
            losses += 1
            self.gross_loss += record.pnl
        else:
            self.breakeven += 1

        realized_pnl = float(self._snapshot_get(
            "realized_pnl", 0.0) or 0.0) + record.pnl

        self._snapshot_set("total_trades", total_trades)
        self._snapshot_set("wins", wins)
        self._snapshot_set("losses", losses)
        self._snapshot_set("realized_pnl", realized_pnl)
        self._snapshot_set("win_rate", wins / max(1, total_trades))

        if total_trades == 1:
            self.best_trade = record.pnl
            self.worst_trade = record.pnl
        else:
            self.best_trade = max(self.best_trade, record.pnl)
            self.worst_trade = min(self.worst_trade, record.pnl)

        contribution = dict(self._snapshot_get(
            "strategy_contribution", {}) or {})
        contribution[record.strategy_name] = contribution.get(
            record.strategy_name, 0.0) + record.pnl
        self._snapshot_set("strategy_contribution", contribution)

        self._snapshot_set("sharpe_ratio", self._compute_sharpe_ratio())

    def _update_strategy_metrics(self, record: TradePerformanceRecord) -> None:
        stats = self.strategy_stats.get(record.strategy_name)

        if stats is None:
            stats = StrategyPerformance(strategy_name=record.strategy_name)
            self.strategy_stats[record.strategy_name] = stats

        stats.total_trades += 1
        stats.realized_pnl += record.pnl
        stats.total_notional += record.notional
        stats.returns.append(record.trade_return)

        if record.pnl > 0:
            stats.wins += 1
            stats.gross_profit += record.pnl
        elif record.pnl < 0:
            stats.losses += 1
            stats.gross_loss += record.pnl
        else:
            stats.breakeven += 1

        if stats.total_trades == 1:
            stats.best_trade = record.pnl
            stats.worst_trade = record.pnl
        else:
            stats.best_trade = max(stats.best_trade, record.pnl)
            stats.worst_trade = min(stats.worst_trade, record.pnl)

        if len(stats.returns) > self.max_history:
            stats.returns = stats.returns[-self.max_history:]

    def _sync_snapshot(self) -> None:
        """Write optional extended fields to snapshot when they exist.

        This keeps compatibility with your existing analytics.metrics.PerformanceSnapshot
        even if it only defines a few fields.
        """
        self._snapshot_set_if_exists("gross_profit", self.gross_profit)
        self._snapshot_set_if_exists("gross_loss", self.gross_loss)
        self._snapshot_set_if_exists("profit_factor", self.profit_factor)
        self._snapshot_set_if_exists("expectancy", self.expectancy)
        self._snapshot_set_if_exists(
            "average_trade_pnl", self.average_trade_pnl)
        self._snapshot_set_if_exists("average_win", self.average_win)
        self._snapshot_set_if_exists("average_loss", self.average_loss)
        self._snapshot_set_if_exists("best_trade", self.best_trade)
        self._snapshot_set_if_exists("worst_trade", self.worst_trade)
        self._snapshot_set_if_exists("total_notional", self.total_notional)
        self._snapshot_set_if_exists("current_equity", self.current_equity)
        self._snapshot_set_if_exists("peak_equity", self.peak_equity)
        self._snapshot_set_if_exists("max_drawdown", self.max_drawdown)
        self._snapshot_set_if_exists("max_drawdown_pct", self.max_drawdown_pct)
        self._snapshot_set_if_exists("sortino_ratio", self.sortino_ratio)
        self._snapshot_set_if_exists("breakeven", self.breakeven)
        self._snapshot_set_if_exists(
            "strategy_stats",
            {name: stats.to_dict()
             for name, stats in self.strategy_stats.items()},
        )
        self._snapshot_set_if_exists("updated_at", self._utc_now())

    # ------------------------------------------------------------------
    # Math helpers
    # ------------------------------------------------------------------

    def _compute_sharpe_ratio(self) -> float:
        if not self.returns:
            return 0.0

        adjusted_returns = [
            value - self.risk_free_rate for value in self.returns]
        mean_return = self._mean(adjusted_returns)
        variance = self._mean(
            [(value - mean_return) ** 2 for value in adjusted_returns])
        std_return = math.sqrt(max(variance, 0.0))

        if std_return <= EPSILON:
            return 0.0

        return (mean_return / std_return) * self._annualization_multiplier()

    def _annualization_multiplier(self) -> float:
        if self.annualization_factor is not None:
            return math.sqrt(max(float(self.annualization_factor), 1.0))

        # Backward-compatible behavior with your original engine:
        # Sharpe scales by sqrt(number of recorded returns).
        return math.sqrt(max(len(self.returns), 1))

    @staticmethod
    def _mean(values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    # ------------------------------------------------------------------
    # Snapshot compatibility helpers
    # ------------------------------------------------------------------

    def _snapshot_get(self, name: str, default: Any = None) -> Any:
        return getattr(self.snapshot, name, default)

    def _snapshot_set(self, name: str, value: Any) -> None:
        try:
            setattr(self.snapshot, name, value)
        except Exception:
            pass

    def _snapshot_set_if_exists(self, name: str, value: Any) -> None:
        if hasattr(self.snapshot, name):
            self._snapshot_set(name, value)

    def snapshot_to_dict(self) -> dict[str, Any]:
        snapshot = self.get_snapshot()

        if is_dataclass(snapshot):
            return asdict(snapshot)

        if hasattr(snapshot, "model_dump"):
            return snapshot.model_dump()

        if hasattr(snapshot, "dict"):
            return snapshot.dict()

        return dict(getattr(snapshot, "__dict__", {}) or {})

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _infer_notional(self, trade: dict[str, Any]) -> float:
        notional = self._first_float(
            trade,
            "notional",
            "quote_amount",
            "cost",
            "value",
            "trade_value",
            default=None,
        )

        if notional is not None and notional > 0:
            return abs(notional)

        amount = self._first_float(
            trade,
            "amount",
            "quantity",
            "qty",
            "size",
            "filled",
            "filled_size",
            default=0.0,
        )

        price = self._first_float(
            trade,
            "price",
            "average",
            "avg_price",
            "close_price",
            "exit_price",
            "entry_price",
            default=0.0,
        )

        return abs(float(amount or 0.0) * float(price or 0.0))

    def _first_float(self, payload: dict[str, Any], *keys: str, default: Optional[float] = None) -> Optional[float]:
        if not isinstance(payload, dict):
            return default

        for key in keys:
            value = self._safe_float_or_none(payload.get(key))
            if value is not None:
                return value

        raw = payload.get("raw")
        if isinstance(raw, dict):
            for key in keys:
                value = self._safe_float_or_none(raw.get(key))
                if value is not None:
                    return value

        return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            numeric = float(value)
        except Exception:
            return default

        return numeric if math.isfinite(numeric) else default

    @staticmethod
    def _safe_float_or_none(value: Any) -> Optional[float]:
        if value in (None, "", "-"):
            return None

        try:
            numeric = float(value)
        except Exception:
            return None

        return numeric if math.isfinite(numeric) else None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
