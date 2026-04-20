import math

import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator


class StrategyRanker:
    """Rank trading strategies by backtest performance metrics."""

    def __init__(self, strategy_registry, initial_balance=10000, commission_bps=0.0, slippage_bps=0.0):
        """Create a ranker for backtesting strategies.

        Args:
            strategy_registry: A registry or factory object used by BacktestEngine to resolve strategies.
            initial_balance: Starting equity used by the simulator.
            commission_bps: Commission expressed in basis points.
            slippage_bps: Slippage expressed in basis points.
        """
        self.strategy_registry = strategy_registry
        self.initial_balance = float(initial_balance or 10000)
        self.commission_bps = float(commission_bps or 0.0)
        self.slippage_bps = float(slippage_bps or 0.0)

    def _score_report(self, report):
        """Compute a numeric score for a backtest report."""
        report = report or {}
        total_profit = float(report.get("total_profit", 0.0) or 0.0)
        sharpe = float(report.get("sharpe_ratio", 0.0) or 0.0)
        sortino = float(report.get("sortino_ratio", 0.0) or 0.0)
        win_rate = float(report.get("win_rate", 0.0) or 0.0)
        profit_factor = float(report.get("profit_factor", 0.0) or 0.0)
        max_drawdown = abs(float(report.get("max_drawdown", 0.0) or 0.0))
        closed_trades = float(report.get("closed_trades", 0.0) or 0.0)

        if not math.isfinite(profit_factor):
            profit_factor = 5.0

        score = 0.0
        score += sharpe * 40.0
        score += sortino * 25.0
        score += win_rate * 20.0
        score += min(profit_factor, 5.0) * 12.0
        score += total_profit / max(self.initial_balance, 1.0)
        score += min(closed_trades, 25.0) * 0.20
        score -= max_drawdown / max(self.initial_balance, 1.0)
        return float(score)

    def rank(self, data, symbol, timeframe=None, strategy_names=None, top_n=None):
        """Backtest strategies and return a ranked DataFrame of performance metrics."""
        names = list(strategy_names or getattr(self.strategy_registry, "list", lambda: [])())
        rows = []
        for strategy_name in names:
            simulator = Simulator(
                initial_balance=self.initial_balance,
                commission_bps=self.commission_bps,
                slippage_bps=self.slippage_bps,
            )
            engine = BacktestEngine(strategy=self.strategy_registry, simulator=simulator)
            trades = engine.run(
                data,
                symbol=symbol,
                strategy_name=strategy_name,
                metadata={"strategy_name": strategy_name, "timeframe": timeframe},
            )
            report = ReportGenerator(trades=trades, equity_history=getattr(engine, "equity_curve", [])).generate()
            row = {
                "strategy_name": str(strategy_name),
                "symbol": str(symbol or "").strip().upper(),
                "timeframe": str(timeframe or "").strip(),
                "score": self._score_report(report),
            }
            row.update(report)
            rows.append(row)

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame

        frame.sort_values(
            by=["score", "final_equity", "sharpe_ratio", "total_profit", "win_rate"],
            ascending=[False, False, False, False, False],
            inplace=True,
        )
        frame.reset_index(drop=True, inplace=True)
        if top_n is not None:
            frame = frame.head(max(1, int(top_n))).reset_index(drop=True)
        return frame
