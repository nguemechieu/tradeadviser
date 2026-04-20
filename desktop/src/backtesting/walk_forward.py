import copy

import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator


class WalkForwardAnalyzer:
    def __init__(self, strategy, initial_balance=10000, commission_bps=0.0, slippage_bps=0.0):
        self.strategy = strategy
        self.initial_balance = float(initial_balance)
        self.commission_bps = float(commission_bps or 0.0)
        self.slippage_bps = float(slippage_bps or 0.0)

    def _normalize_frame(self, data):
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return df.reset_index(drop=True)

    def _clone_strategy(self):
        try:
            return copy.deepcopy(self.strategy)
        except Exception:
            try:
                return self.strategy.__class__()
            except Exception:
                return self.strategy

    def run(self, data, symbol="BACKTEST", strategy_name=None, train_size=100, test_size=50, step_size=None):
        df = self._normalize_frame(data)
        if df.empty or len(df) < max(2, train_size + test_size):
            return pd.DataFrame(), pd.DataFrame()

        train_size = max(1, int(train_size))
        test_size = max(1, int(test_size))
        step = max(1, int(step_size or test_size))

        summary_rows = []
        trade_frames = []
        window_index = 0

        for train_start in range(0, len(df) - train_size - test_size + 1, step):
            train_end = train_start + train_size
            test_end = train_end + test_size
            train_df = df.iloc[train_start:train_end].reset_index(drop=True)
            test_df = df.iloc[train_end:test_end].reset_index(drop=True)
            if test_df.empty:
                continue

            strategy_instance = self._clone_strategy()
            engine = BacktestEngine(
                strategy=strategy_instance,
                simulator=Simulator(
                    initial_balance=self.initial_balance,
                    commission_bps=self.commission_bps,
                    slippage_bps=self.slippage_bps,
                ),
                metadata={
                    "walk_forward_window": window_index,
                    "train_start": train_df.iloc[0]["timestamp"],
                    "train_end": train_df.iloc[-1]["timestamp"],
                    "test_start": test_df.iloc[0]["timestamp"],
                    "test_end": test_df.iloc[-1]["timestamp"],
                },
            )
            trades = engine.run(test_df, symbol=symbol, strategy_name=strategy_name)
            report = ReportGenerator(trades=trades, equity_history=engine.equity_curve).generate()
            report.update(
                {
                    "window_index": window_index,
                    "symbol": symbol,
                    "strategy_name": strategy_name or getattr(strategy_instance, "strategy_name", None),
                    "train_start": train_df.iloc[0]["timestamp"],
                    "train_end": train_df.iloc[-1]["timestamp"],
                    "test_start": test_df.iloc[0]["timestamp"],
                    "test_end": test_df.iloc[-1]["timestamp"],
                    "train_rows": len(train_df),
                    "test_rows": len(test_df),
                }
            )
            summary_rows.append(report)
            if not trades.empty:
                trade_frames.append(trades)
            window_index += 1

        return pd.DataFrame(summary_rows), (pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame())
