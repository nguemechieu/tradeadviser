from __future__ import annotations

from numpy import dtype, integer, ndarray
from pandas import Series

"""
InvestPro WalkForwardAnalyzer

Runs walk-forward analysis for a strategy.

Walk-forward testing is stronger than a single backtest because it evaluates
the strategy across multiple chronological test windows.

Features:
- Rolling or anchored training windows.
- Optional strategy fitting/training before each test window.
- Robust DataFrame normalization.
- Failure isolation per window.
- Per-window reports.
- Combined trade output.
- Aggregate summary output.
- Optional CSV export.
- Compatible with strategies that implement:
    - fit(train_df)
    - train(train_df)
    - optimize(train_df)
    - prepare(train_df)
- Compatible with BacktestEngine + Simulator + ReportGenerator.
"""

import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator


EPSILON = 1e-12


@dataclass(slots=True)
class WalkForwardWindow:
    window_index: int
    train_start_index: int
    train_end_index: int
    test_start_index: int
    test_end_index: int
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    train_rows: int
    test_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_index": self.window_index,
            "train_start_index": self.train_start_index,
            "train_end_index": self.train_end_index,
            "test_start_index": self.test_start_index,
            "test_end_index": self.test_end_index,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
        }


@dataclass(slots=True)
class WalkForwardConfig:
    initial_balance: float = 10_000.0
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    train_size: int = 100
    test_size: int = 50
    step_size: Optional[int] = None
    anchored: bool = False
    allow_short: bool = True
    max_leverage: float = 1.0
    fit_strategy: bool = True
    include_failed_windows: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WalkForwardAggregate:
    windows: int = 0
    successful_windows: int = 0
    failed_windows: int = 0
    total_closed_trades: int = 0
    total_profit: float = 0.0
    average_profit: float = 0.0
    median_profit: float = 0.0
    average_final_equity: float = 0.0
    average_win_rate: float = 0.0
    average_sharpe: float = 0.0
    average_sortino: float = 0.0
    average_profit_factor: float = 0.0
    average_max_drawdown: float = 0.0
    average_max_drawdown_pct: float = 0.0
    consistency: float = 0.0
    robustness_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "windows": self.windows,
            "successful_windows": self.successful_windows,
            "failed_windows": self.failed_windows,
            "total_closed_trades": self.total_closed_trades,
            "total_profit": self.total_profit,
            "average_profit": self.average_profit,
            "median_profit": self.median_profit,
            "average_final_equity": self.average_final_equity,
            "average_win_rate": self.average_win_rate,
            "average_sharpe": self.average_sharpe,
            "average_sortino": self.average_sortino,
            "average_profit_factor": self.average_profit_factor,
            "average_max_drawdown": self.average_max_drawdown,
            "average_max_drawdown_pct": self.average_max_drawdown_pct,
            "consistency": self.consistency,
            "robustness_score": self.robustness_score,
        }


def _numeric_series(frame: pd.DataFrame, column: str) -> Series | ndarray[tuple[int], dtype[integer[Any]]]:
    if column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _finite_mean(series: pd.Series, cap: Optional[float] = None) -> float:
    if series is None or series.empty:
        return 0.0

    values = []
    for value in series.tolist():
        try:
            numeric = float(value)
        except Exception:
            continue

        if not math.isfinite(numeric):
            if cap is not None and numeric > 0:
                numeric = cap
            else:
                continue

        if cap is not None:
            numeric = max(-cap, min(cap, numeric))

        values.append(numeric)

    return float(sum(values) / len(values)) if values else 0.0


class WalkForwardAnalyzer:
    def __init__(
        self,
        strategy: Any,
        initial_balance: float = 10_000.0,
        commission_bps: float = 0.0,
        slippage_bps: float = 0.0,
        *,
        allow_short: bool = True,
        max_leverage: float = 1.0,
        config: Optional[WalkForwardConfig] = None,
    ) -> None:
        self.strategy = strategy
        self.config = config or WalkForwardConfig(
            initial_balance=float(initial_balance or 10_000.0),
            commission_bps=float(commission_bps or 0.0),
            slippage_bps=float(slippage_bps or 0.0),
            allow_short=bool(allow_short),
            max_leverage=max(1.0, float(max_leverage or 1.0)),
        )

        self.initial_balance = self.config.initial_balance
        self.commission_bps = self.config.commission_bps
        self.slippage_bps = self.config.slippage_bps

    # ------------------------------------------------------------------
    # Data normalization
    # ------------------------------------------------------------------

    def _normalize_frame(self, data: Any) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = df.reset_index(drop=True)

        if "timestamp" not in df.columns:
            df["timestamp"] = range(len(df))

        for column in ("open", "high", "low", "close", "volume"):
            if column not in df.columns:
                if column == "volume":
                    df[column] = 0.0
                elif "close" in df.columns:
                    df[column] = df["close"]
                else:
                    df[column] = 0.0

            df[column] = pd.to_numeric(df[column], errors="coerce")

        df.dropna(subset=["close"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    # ------------------------------------------------------------------
    # Strategy preparation
    # ------------------------------------------------------------------

    def _clone_strategy(self) -> Any:
        try:
            return copy.deepcopy(self.strategy)
        except Exception:
            pass

        try:
            return self.strategy.__class__()
        except Exception:
            return self.strategy

    def _fit_strategy(self, strategy_instance: Any, train_df: pd.DataFrame, metadata: dict[str, Any]) -> Any:
        """Fit/train/prepare strategy if it supports it."""
        if not self.config.fit_strategy:
            return strategy_instance

        for method_name in ("fit", "train", "optimize", "prepare"):
            method = getattr(strategy_instance, method_name, None)

            if not callable(method):
                continue

            try:
                try:
                    result = method(train_df, metadata=metadata)
                except TypeError:
                    result = method(train_df)

                # If the strategy returns a replacement object, use it.
                if result is not None:
                    return result

                return strategy_instance

            except Exception:
                # Let the caller catch the window-level failure.
                raise

        return strategy_instance

    # ------------------------------------------------------------------
    # Window generation
    # ------------------------------------------------------------------

    def _build_windows(
        self,
        df: pd.DataFrame,
        *,
        train_size: int,
        test_size: int,
        step_size: Optional[int],
        anchored: bool,
    ) -> list[WalkForwardWindow]:
        if df.empty:
            return []

        train_size = max(1, int(train_size))
        test_size = max(1, int(test_size))
        step = max(1, int(step_size or test_size))

        if len(df) < train_size + test_size:
            return []

        windows: list[WalkForwardWindow] = []
        window_index = 0

        for rolling_train_start in range(0, len(df) - train_size - test_size + 1, step):
            if anchored:
                train_start = 0
                train_end = rolling_train_start + train_size
            else:
                train_start = rolling_train_start
                train_end = train_start + train_size

            test_start = train_end
            test_end = test_start + test_size

            if test_end > len(df):
                break

            train_df = df.iloc[train_start:train_end]
            test_df = df.iloc[test_start:test_end]

            if train_df.empty or test_df.empty:
                continue

            windows.append(
                WalkForwardWindow(
                    window_index=window_index,
                    train_start_index=train_start,
                    train_end_index=train_end - 1,
                    test_start_index=test_start,
                    test_end_index=test_end - 1,
                    train_start=train_df.iloc[0]["timestamp"],
                    train_end=train_df.iloc[-1]["timestamp"],
                    test_start=test_df.iloc[0]["timestamp"],
                    test_end=test_df.iloc[-1]["timestamp"],
                    train_rows=len(train_df),
                    test_rows=len(test_df),
                )
            )

            window_index += 1

        return windows

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(
        self,
        data: Any,
        symbol: str = "BACKTEST",
        strategy_name: Optional[str] = None,
        train_size: Optional[int] = None,
        test_size: Optional[int] = None,
        step_size: Optional[int] = None,
        *,
        anchored: Optional[bool] = None,
        include_failed_windows: Optional[bool] = None,
        export_summary_csv_path: Optional[str] = None,
        export_trades_csv_path: Optional[str] = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Run walk-forward analysis.

        Returns:
            summary_df, trades_df
        """
        df = self._normalize_frame(data)

        effective_train_size = int(train_size or self.config.train_size)
        effective_test_size = int(test_size or self.config.test_size)
        effective_step_size = step_size if step_size is not None else self.config.step_size
        effective_anchored = self.config.anchored if anchored is None else bool(
            anchored)
        keep_failed = self.config.include_failed_windows if include_failed_windows is None else bool(
            include_failed_windows)

        if df.empty or len(df) < max(2, effective_train_size + effective_test_size):
            return pd.DataFrame(), pd.DataFrame()

        windows = self._build_windows(
            df,
            train_size=effective_train_size,
            test_size=effective_test_size,
            step_size=effective_step_size,
            anchored=effective_anchored,
        )

        summary_rows: list[dict[str, Any]] = []
        trade_frames: list[pd.DataFrame] = []

        symbol_text = str(symbol or "BACKTEST").strip().upper() or "BACKTEST"

        for window in windows:
            summary_row, trades_df = self._run_window(
                df=df,
                window=window,
                symbol=symbol_text,
                strategy_name=strategy_name,
            )

            if summary_row.get("status") == "failed" and not keep_failed:
                continue

            summary_rows.append(summary_row)

            if trades_df is not None and not trades_df.empty:
                trade_frames.append(trades_df)

        summary_df = pd.DataFrame(summary_rows)
        trades_output = pd.concat(
            trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()

        if not summary_df.empty:
            aggregate = self.aggregate_summary(summary_df)
            for key, value in aggregate.items():
                summary_df.attrs[key] = value

        if export_summary_csv_path:
            summary_df.to_csv(export_summary_csv_path, index=False)

        if export_trades_csv_path:
            trades_output.to_csv(export_trades_csv_path, index=False)

        return summary_df, trades_output

    def _run_window(
        self,
        *,
        df: pd.DataFrame,
        window: WalkForwardWindow,
        symbol: str,
        strategy_name: Optional[str],
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        train_df = df.iloc[window.train_start_index:
                           window.train_end_index + 1].reset_index(drop=True)
        test_df = df.iloc[window.test_start_index:window.test_end_index +
                          1].reset_index(drop=True)

        started_at = datetime.now(timezone.utc)

        base_metadata = {
            **window.to_dict(),
            "symbol": symbol,
            "strategy_name": strategy_name,
            "anchored": self.config.anchored,
            "initial_balance": self.config.initial_balance,
            "commission_bps": self.config.commission_bps,
            "slippage_bps": self.config.slippage_bps,
            **dict(self.config.metadata or {}),
        }

        try:
            strategy_instance = self._clone_strategy()
            strategy_instance = self._fit_strategy(
                strategy_instance, train_df, base_metadata)

            resolved_strategy_name = (
                strategy_name
                or getattr(strategy_instance, "strategy_name", None)
                or getattr(strategy_instance, "name", None)
                or strategy_instance.__class__.__name__
            )

            simulator = Simulator(
                initial_balance=self.config.initial_balance,
                commission_bps=self.config.commission_bps,
                slippage_bps=self.config.slippage_bps,
                allow_short=self.config.allow_short,
                max_leverage=self.config.max_leverage,
            )

            engine = BacktestEngine(
                strategy=strategy_instance,
                simulator=simulator,
                metadata=base_metadata,
            )

            trades = engine.run(
                test_df,
                symbol=symbol,
                strategy_name=resolved_strategy_name,
                metadata=base_metadata,
            )

            if not isinstance(trades, pd.DataFrame):
                trades = pd.DataFrame(trades)

            equity_history = (
                getattr(engine, "equity_curve", None)
                or getattr(simulator, "equity_curve", None)
                or []
            )

            report = ReportGenerator(
                trades=trades,
                equity_history=equity_history,
            ).generate()

            finished_at = datetime.now(timezone.utc)

            summary = {
                **dict(report or {}),
                **window.to_dict(),
                "symbol": symbol,
                "strategy_name": resolved_strategy_name,
                "status": "ok",
                "error": "",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": (finished_at - started_at).total_seconds(),
            }

            if not trades.empty:
                trades = trades.copy()
                trades["window_index"] = window.window_index
                trades["symbol"] = symbol
                trades["strategy_name"] = resolved_strategy_name
                trades["walk_forward_test_start"] = window.test_start
                trades["walk_forward_test_end"] = window.test_end

            return summary, trades

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)

            summary = {
                **window.to_dict(),
                "symbol": symbol,
                "strategy_name": strategy_name,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "total_profit": 0.0,
                "final_equity": self.config.initial_balance,
                "closed_trades": 0,
                "win_rate": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": (finished_at - started_at).total_seconds(),
            }

            return summary, pd.DataFrame()

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def aggregate_summary(self, summary_df: pd.DataFrame) -> dict[str, Any]:
        """Compute aggregate walk-forward metrics."""
        if summary_df is None or summary_df.empty:
            return WalkForwardAggregate().to_dict()

        frame = summary_df.copy()
        successful = frame[frame.get(
            "status", "ok") == "ok"] if "status" in frame.columns else frame

        windows = len(frame)
        successful_windows = len(successful)
        failed_windows = windows - successful_windows

        if successful.empty:
            return WalkForwardAggregate(
                windows=windows,
                successful_windows=0,
                failed_windows=failed_windows,
            ).to_dict()

        total_profit_series = _numeric_series(successful, "total_profit")
        final_equity_series = _numeric_series(successful, "final_equity")
        win_rate_series = _numeric_series(successful, "win_rate")
        sharpe_series = _numeric_series(successful, "sharpe_ratio")
        sortino_series = _numeric_series(successful, "sortino_ratio")
        profit_factor_series = _numeric_series(
            successful, "profit_factor")
        max_drawdown_series = _numeric_series(successful, "max_drawdown")
        max_drawdown_pct_series = _numeric_series(
            successful, "max_drawdown_pct")
        closed_trades_series = _numeric_series(
            successful, "closed_trades")

        total_profit = float(total_profit_series.sum()
                             ) if not total_profit_series.empty else 0.0
        positive_windows = int((total_profit_series > 0).sum(
        )) if not total_profit_series.empty else 0
        consistency = positive_windows / max(1, successful_windows)

        average_profit = float(total_profit_series.mean()
                               ) if not total_profit_series.empty else 0.0
        median_profit = float(total_profit_series.median()
                              ) if not total_profit_series.empty else 0.0

        average_profit_factor = _finite_mean(
            profit_factor_series, cap=10.0)

        average_sharpe = _finite_mean(sharpe_series, cap=10.0)
        average_sortino = _finite_mean(sortino_series, cap=15.0)
        average_win_rate = _finite_mean(win_rate_series, cap=1.0)

        average_max_drawdown = _finite_mean(
            max_drawdown_series.abs(), cap=None)
        average_max_drawdown_pct = _finite_mean(
            max_drawdown_pct_series.abs(), cap=1.0)

        total_closed_trades = int(
            closed_trades_series.sum()) if not closed_trades_series.empty else 0

        robustness_score = self._robustness_score(
            average_profit=average_profit,
            average_sharpe=average_sharpe,
            average_sortino=average_sortino,
            average_win_rate=average_win_rate,
            average_profit_factor=average_profit_factor,
            average_max_drawdown_pct=average_max_drawdown_pct,
            consistency=consistency,
            successful_windows=successful_windows,
            total_windows=windows,
        )

        return WalkForwardAggregate(
            windows=windows,
            successful_windows=successful_windows,
            failed_windows=failed_windows,
            total_closed_trades=total_closed_trades,
            total_profit=round(total_profit, 6),
            average_profit=round(average_profit, 6),
            median_profit=round(median_profit, 6),
            average_final_equity=round(
                float(final_equity_series.mean()), 6) if not final_equity_series.empty else 0.0,
            average_win_rate=round(average_win_rate, 6),
            average_sharpe=round(average_sharpe, 6),
            average_sortino=round(average_sortino, 6),
            average_profit_factor=round(average_profit_factor, 6),
            average_max_drawdown=round(average_max_drawdown, 6),
            average_max_drawdown_pct=round(average_max_drawdown_pct, 6),
            consistency=round(consistency, 6),
            robustness_score=round(robustness_score, 6),
        ).to_dict()

    def _robustness_score(
        self,
        *,
        average_profit: float,
        average_sharpe: float,
        average_sortino: float,
        average_win_rate: float,
        average_profit_factor: float,
        average_max_drawdown_pct: float,
        consistency: float,
        successful_windows: int,
        total_windows: int,
    ) -> float:
        """Score walk-forward robustness.

        This is a model-selection helper, not a financial guarantee.
        """
        success_ratio = successful_windows / max(1, total_windows)
        profit_return = average_profit / \
            max(abs(self.config.initial_balance), EPSILON)

        score = 0.0
        score += average_sharpe * 35.0
        score += average_sortino * 20.0
        score += average_win_rate * 20.0
        score += min(average_profit_factor, 5.0) * 10.0
        score += consistency * 30.0
        score += profit_return * 100.0
        score += success_ratio * 15.0
        score -= abs(average_max_drawdown_pct) * 35.0

        return float(score)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

