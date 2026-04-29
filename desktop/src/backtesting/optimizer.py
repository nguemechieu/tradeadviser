from concurrent.futures import ThreadPoolExecutor
import copy
import itertools

import pandas as pd
from backtesting.backtest_engine import BacktestEngine
from backtesting.experiment_tracker import ExperimentTracker
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator


class StrategyOptimizer:
    """Hyperparameter optimizer for trading strategy backtests."""

    def __init__(self, strategy, initial_balance=10000):
        """Create an optimizer for a base strategy.

        Args:
            strategy: A strategy object or strategy registry used by BacktestEngine.
            initial_balance: Starting equity for each backtest run.
        """
        self.strategy = strategy
        self.initial_balance: float = float(initial_balance) if initial_balance is not None else 10000.0
        self.experiment_tracker = ExperimentTracker()

    def _resolve_strategy(self, strategy_name=None):
        """Resolve a concrete strategy instance for a given strategy name."""
        if hasattr(self.strategy, "_resolve_strategy"):
            return self.strategy._resolve_strategy(strategy_name)
        return self.strategy

    def _clone_strategy(self, base_strategy):
        """Return a deep copy of a strategy, falling back to a constructor copy if needed."""
        try:
            return copy.deepcopy(base_strategy)
        except Exception:
            model = getattr(base_strategy, "model", None)
            try:
                clone = base_strategy.__class__(model=model)
            except TypeError:
                clone = base_strategy.__class__()
                if model is not None and hasattr(clone, "model"):
                    clone.model = model
            return clone

    def default_param_grid(self, strategy_name=None):
        """Generate a default hyperparameter grid for optimizer search."""
        base = self._resolve_strategy(strategy_name)

        def around(value, offsets, minimum):
            candidates = []
            for offset in offsets:
                candidate = int(value + offset)
                if candidate >= minimum and candidate not in candidates:
                    candidates.append(candidate)
            return candidates or [int(max(value, minimum))]

        rsi_period = int(getattr(base, "rsi_period", 14) or 14)
        ema_fast = int(getattr(base, "ema_fast", 20) or 20)
        ema_slow = int(getattr(base, "ema_slow", 50) or 50)
        atr_period = int(getattr(base, "atr_period", 14) or 14)

        return {
            "rsi_period": around(rsi_period, (-4, 0, 4), 2),
            "ema_fast": around(ema_fast, (-5, 0, 5), 2),
            "ema_slow": around(ema_slow, (-10, 0, 10), 3),
            "atr_period": around(atr_period, (-4, 0, 4), 2),
        }

    def _param_rows(self, param_grid):
        """Yield valid hyperparameter combinations from a parameter grid."""
        keys = list(param_grid.keys())
        values = [list(param_grid[key]) for key in keys]
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            if params.get("ema_fast", 0) >= params.get("ema_slow", 0):
                continue
            yield params

    def _resolve_max_workers(self, job_count, max_workers=None):
        """Resolve the number of worker threads to use for parallel evaluation."""
        total_jobs = max(0, int(job_count or 0))
        if total_jobs <= 1:
            return 1
        if max_workers is not None:
            return max(1, min(int(max_workers), total_jobs))
        cpu_total = max(1, int(os.cpu_count() or 1))
        return max(1, min(total_jobs, cpu_total))

    def _evaluate_param_row(
        self,
        params,
        data,
        symbol,
        strategy_name,
        timeframe,
        commission_bps,
        slippage_bps,
    ):
        """Evaluate a single hyperparameter combination and return the result row."""
        strategy_instance = self._clone_strategy(self._resolve_strategy(strategy_name))
        for key, value in params.items():
            setattr(strategy_instance, key, value)

        engine = BacktestEngine(
            strategy=strategy_instance,
            simulator=Simulator(
                initial_balance=self.initial_balance,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            ),
            metadata={
                "strategy_name": strategy_name or getattr(strategy_instance, "strategy_name", None),
                "symbol": symbol,
                "timeframe": timeframe,
            },
        )
        trades = engine.run(data, symbol=symbol, strategy_name=strategy_name)
        report = ReportGenerator(
            trades=trades,
            equity_history=engine.equity_curve,
        ).generate()

        row = dict(params)
        row.update(report)
        row["symbol"] = symbol
        row["strategy_name"] = strategy_name or getattr(strategy_instance, "strategy_name", None)
        row["timeframe"] = timeframe
        row["commission_bps"] = float(commission_bps or 0.0)
        row["slippage_bps"] = float(slippage_bps or 0.0)
        return row, report, strategy_instance

    def optimize(
        self,
        data,
        symbol="BACKTEST",
        strategy_name=None,
        param_grid=None,
        timeframe="1h",
        commission_bps=0.0,
        slippage_bps=0.0,
        experiment_name=None,
        max_workers=None,
    ):
        """Run a parameter search and return a ranked results DataFrame."""
        grid = param_grid or self.default_param_grid(strategy_name)
        param_rows = list(self._param_rows(grid))
        worker_count = self._resolve_max_workers(len(param_rows), max_workers=max_workers)
        rows = []

        evaluations = []
        if worker_count <= 1:
            for job_index, params in enumerate(param_rows):
                row, report, strategy_instance = self._evaluate_param_row(
                    params,
                    data,
                    symbol,
                    strategy_name,
                    timeframe,
                    commission_bps,
                    slippage_bps,
                )
                evaluations.append((job_index, params, row, report, strategy_instance))
        else:
            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="optimizer") as executor:
                future_map = {
                    executor.submit(
                        self._evaluate_param_row,
                        params,
                        data,
                        symbol,
                        strategy_name,
                        timeframe,
                        commission_bps,
                        slippage_bps,
                    ): (job_index, params)
                    for job_index, params in enumerate(param_rows)
                }
                for future in as_completed(future_map):
                    job_index, params = future_map[future]
                    row, report, strategy_instance = future.result()
                    evaluations.append((job_index, params, row, report, strategy_instance))

        for _, params, row, report, strategy_instance in sorted(evaluations, key=lambda item: item[0]):
            rows.append(row)
            self.experiment_tracker.add_record(
                name=experiment_name or f"optimizer-{strategy_name or getattr(strategy_instance, 'strategy_name', 'strategy')}",
                strategy_name=strategy_name or getattr(strategy_instance, "strategy_name", None),
                symbol=symbol,
                timeframe=timeframe,
                parameters=params,
                dataset_metadata={"rows": len(data) if hasattr(data, "__len__") else 0},
                metrics=report,
                notes="optimizer_run",
            )

        if not rows:
            return pd.DataFrame()

        results = pd.DataFrame(rows)
        if sort_columns := [
            column
            for column in [
                "total_profit",
                "sharpe_ratio",
                "final_equity",
                "win_rate",
            ]
            if column in results.columns
        ]:
            results = results.sort_values(sort_columns, ascending=False).reset_index(drop=True)
        return results
