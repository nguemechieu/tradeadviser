from __future__ import annotations

"""
InvestPro StrategyRanker

Ranks trading strategies by running backtests and scoring the reports.

Features:
- Backtests multiple strategies.
- Handles strategy failures without stopping the full ranking run.
- Scores with Sharpe, Sortino, win rate, profit factor, total profit, drawdown, and trade count.
- Applies penalties for too few trades and excessive drawdown.
- Supports top-N selection.
- Supports optional CSV export.
- Works with strategy registries exposing:
    - list()
    - list_strategies()
    - keys()
    - strategies dict
- Returns a pandas DataFrame ready for UI, reports, or ML model selection.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator


EPSILON = 1e-12


@dataclass(slots=True)
class RankerConfig:
    initial_balance: float = 10_000.0
    commission_bps: float = 0.0
    slippage_bps: float = 0.0

    min_trades: int = 5
    ideal_trades: int = 25

    max_profit_factor_cap: float = 5.0
    max_sharpe_cap: float = 5.0
    max_sortino_cap: float = 7.0

    drawdown_penalty_weight: float = 35.0
    low_trade_penalty_weight: float = 20.0
    failure_score: float = -1_000_000.0

    allow_short: bool = True
    max_leverage: float = 1.0

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyRankResult:
    strategy_name: str
    symbol: str
    timeframe: str
    score: float
    status: str
    error: str = ""
    report: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        row = {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "score": self.score,
            "status": self.status,
            "error": self.error,
        }
        row.update(self.report)
        if self.metadata:
            row["rank_metadata"] = self.metadata.values().mapping.values().__str__()
        return row



class StrategyRanker:
    """Rank trading strategies by backtest performance metrics."""

    def __init__(
        self,
        strategy_registry: Any,
        initial_balance: float = 10_000.0,
        commission_bps: float = 0.0,
        slippage_bps: float = 0.0,
        *,
        min_trades: int = 5,
        ideal_trades: int = 25,
        allow_short: bool = True,
        max_leverage: float = 1.0,
        config: Optional[RankerConfig] = None,
    ) -> None:
        self.strategy_registry = strategy_registry

        self.config = config or RankerConfig(
            initial_balance=float(initial_balance or 10_000.0),
            commission_bps=float(commission_bps or 0.0),
            slippage_bps=float(slippage_bps or 0.0),
            min_trades=max(0, int(min_trades or 5)),
            ideal_trades=max(1, int(ideal_trades or 25)),
            allow_short=bool(allow_short),
            max_leverage=max(1.0, float(max_leverage or 1.0)),
        )

        self.initial_balance = self.config.initial_balance
        self.commission_bps = self.config.commission_bps
        self.slippage_bps = self.config.slippage_bps

    # ------------------------------------------------------------------
    # Strategy discovery
    # ------------------------------------------------------------------

    def list_strategy_names(self, strategy_names: Optional[Iterable[str]] = None) -> list[str]:
        """Return strategy names from explicit input or registry."""
        if strategy_names is not None:
            return self._clean_names(strategy_names)

        registry = self.strategy_registry

        for method_name in ("list", "list_strategies", "names", "keys"):
            method = getattr(registry, method_name, None)
            if callable(method):
                try:
                    return self._clean_names(method())
                except Exception:
                     raise

        strategies = getattr(registry, "strategies", None)
        if isinstance(strategies, dict):
            return self._clean_names(strategies.keys())

        if isinstance(registry, dict):
            return self._clean_names(registry.keys())

        return []

    def _clean_names(self, names: Iterable[Any]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()

        for item in names or []:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)

        return cleaned

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_report(self, report: dict[str, Any]) -> float:
        """Compute a numeric score for a backtest report.

        Higher is better.

        The score rewards:
        - risk-adjusted returns
        - consistency
        - profit factor
        - total profit
        - enough trades

        The score penalizes:
        - drawdown
        - too few trades
        - negative returns
        """
        report = report or {}

        total_profit = self._safe_float(report.get("total_profit"), 0.0)
        final_equity = self._safe_float(
            report.get("final_equity"), self.initial_balance)

        sharpe = self._cap(
            self._safe_float(report.get("sharpe_ratio"), 0.0),
            -self.config.max_sharpe_cap,
            self.config.max_sharpe_cap,
        )

        sortino = self._cap(
            self._safe_float(report.get("sortino_ratio"), 0.0),
            -self.config.max_sortino_cap,
            self.config.max_sortino_cap,
        )

        win_rate = self._cap(self._safe_float(
            report.get("win_rate"), 0.0), 0.0, 1.0)

        profit_factor = self._safe_float(report.get("profit_factor"), 0.0)
        if not math.isfinite(profit_factor):
            profit_factor = self.config.max_profit_factor_cap
        profit_factor = self._cap(
            profit_factor, 0.0, self.config.max_profit_factor_cap)

        max_drawdown = abs(
            self._safe_float(
                report.get("max_drawdown", report.get("max_drawdown_value")),
                0.0,
            )
        )

        max_drawdown_pct = abs(
            self._safe_float(
                report.get("max_drawdown_pct", report.get("drawdown_pct")),
                0.0,
            )
        )

        closed_trades = self._safe_float(
            report.get("closed_trades", report.get("total_trades")),
            0.0,
        )

        total_return = (final_equity - self.initial_balance) / \
            max(abs(self.initial_balance), EPSILON)
        profit_return = total_profit / max(abs(self.initial_balance), EPSILON)

        if max_drawdown_pct <= 0 < max_drawdown:
            max_drawdown_pct = max_drawdown / \
                max(abs(self.initial_balance), EPSILON)

        trade_quality_multiplier = self._trade_count_multiplier(closed_trades)

        score = 0.0

        # Risk-adjusted performance
        score += sharpe * 40.0
        score += sortino * 25.0

        # Trade correctness / payoff quality
        score += win_rate * 20.0
        score += profit_factor * 12.0

        # Absolute return contribution
        score += profit_return * 100.0
        score += total_return * 100.0

        # Enough samples matter
        score += min(closed_trades, float(self.config.ideal_trades)) * 0.20

        # Risk penalty
        score -= max_drawdown_pct * self.config.drawdown_penalty_weight

        # Low-sample penalty
        if closed_trades < self.config.min_trades:
            missing = self.config.min_trades - closed_trades
            score -= missing * self.config.low_trade_penalty_weight

        # Negative performance penalty
        if total_profit < 0:
            score += profit_return * 100.0

        score *= trade_quality_multiplier

        return float(score)

    def _trade_count_multiplier(self, closed_trades: float) -> float:
        if self.config.ideal_trades <= 0:
            return 1.0

        if closed_trades <= 0:
            return 0.25

        ratio = closed_trades / max(float(self.config.ideal_trades), 1.0)
        return self._cap(ratio, 0.25, 1.0)

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank(
        self,
        data: Any,
        symbol: str,
        timeframe: Optional[str] = None,
        strategy_names: Optional[Iterable[str]] = None,
        top_n: Optional[int] = None,
        *,
        include_failed: bool = True,
        export_csv_path: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Backtest strategies and return a ranked DataFrame."""

        names = self.list_strategy_names(strategy_names)
        rows: list[dict[str, Any]] = []

        symbol_text = str(symbol or "").strip().upper()
        timeframe_text = str(timeframe or "").strip()

        for strategy_name in names:
            result = self._rank_single_strategy(
                data=data,
                symbol=symbol_text,
                timeframe=timeframe_text,
                strategy_name=strategy_name,
                metadata=metadata,
            )

            if result.status == "failed" and not include_failed:
                continue

            rows.append(result.to_row())

        frame = pd.DataFrame(rows)

        if frame.empty:
            return frame

        for column in (
            "score",
            "final_equity",
            "sharpe_ratio",
            "sortino_ratio",
            "total_profit",
            "profit_factor",
            "win_rate",
            "closed_trades",
            "max_drawdown",
        ):
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

        sort_columns = [
            column
            for column in ["score", "final_equity", "sharpe_ratio", "total_profit", "win_rate"]
            if column in frame.columns
        ]

        if sort_columns:
            frame.sort_values(
                by=sort_columns,
                ascending=[False] * len(sort_columns),
                inplace=True,
            )

        frame.reset_index(drop=True, inplace=True)
        frame.insert(0, "rank", range(1, len(frame) + 1))

        if top_n is not None:
         try:
          top_n_value = int(top_n)
         except (TypeError, ValueError):
          top_n_value = None

         if top_n_value is not None and top_n_value > 0:
           frame = frame.head(top_n_value).reset_index(drop=True)
           frame["rank"] = range(1, len(frame) + 1)

         if export_csv_path:
            frame.to_csv(export_csv_path, index=False)

         return frame
        return None

    def _rank_single_strategy(
        self,
        *,
        data: Any,
        symbol: str,
        timeframe: str,
        strategy_name: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> StrategyRankResult:
        started_at = datetime.now(timezone.utc)

        try:
            simulator = Simulator(
                initial_balance=self.config.initial_balance,
                commission_bps=self.config.commission_bps,
                slippage_bps=self.config.slippage_bps,
                allow_short=self.config.allow_short,
                max_leverage=self.config.max_leverage,
            )

            engine = BacktestEngine(
                strategy=self.strategy_registry, simulator=simulator)

            trades = engine.run(
                data,
                symbol=symbol,
                strategy_name=strategy_name,
                metadata={
                    "strategy_name": strategy_name,
                    "timeframe": timeframe,
                    **dict(metadata or {}),
                },
            )

            equity_history = (
                getattr(engine, "equity_curve", None)
                or getattr(simulator, "equity_curve", None)
                or []
            )

            report = ReportGenerator(
                trades=trades,
                equity_history=equity_history,
            ).generate()

            report = dict(report or {})
            score = self._score_report(report)

            finished_at = datetime.now(timezone.utc)

            return StrategyRankResult(
                strategy_name=str(strategy_name),
                symbol=symbol,
                timeframe=timeframe,
                score=score,
                status="ok",
                report=report,
                metadata={
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                    "commission_bps": self.config.commission_bps,
                    "slippage_bps": self.config.slippage_bps,
                    "initial_balance": self.config.initial_balance,
                },
            )

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)

            return StrategyRankResult(
                strategy_name=str(strategy_name),
                symbol=symbol,
                timeframe=timeframe,
                score=self.config.failure_score,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                report={
                    "total_profit": 0.0,
                    "final_equity": self.config.initial_balance,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown": 0.0,
                    "closed_trades": 0,
                },
                metadata={
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                },
            )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def best_strategy(
        self,
        data: Any,
        symbol: str,
        timeframe: Optional[str] = None,
        strategy_names: Optional[Iterable[str]] = None,
    ) -> Optional[dict[str, Any]]:
        frame = self.rank(
            data=data,
            symbol=symbol,
            timeframe=timeframe,
            strategy_names=strategy_names,
            top_n=1,
            include_failed=False,
        )

        if frame.empty:
            return None

        return dict(frame.iloc[0].to_dict())

    def rank_many(
        self,
        datasets: dict[str, Any],
        *,
        timeframe: Optional[str] = None,
        strategy_names: Optional[Iterable[str]] = None,
        top_n_per_symbol: Optional[int] = None,
    ) -> pd.DataFrame:
        """Rank strategies across many symbols.

        Args:
            datasets:
                Mapping of symbol -> OHLCV dataframe/list.
                :param datasets:
                :param top_n_per_symbol:
                :param strategy_names:
                :param timeframe:
        """
        frames: list[pd.DataFrame] = []

        for symbol, data in dict(datasets or {}).items():
            frame = self.rank(
                data=data,
                symbol=str(symbol),
                timeframe=timeframe,
                strategy_names=strategy_names,
                top_n=top_n_per_symbol,
            )
            if not frame.empty:
                frames.append(frame)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)

        if "score" in combined.columns:
            combined.sort_values("score", ascending=False, inplace=True)

        combined.reset_index(drop=True, inplace=True)
        combined["global_rank"] = range(1, len(combined) + 1)

        return combined

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except Exception:
            return float(default)

        if not math.isfinite(number):
            return float(default)

        return number

    @staticmethod
    def _cap(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
