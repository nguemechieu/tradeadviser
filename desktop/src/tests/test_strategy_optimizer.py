import sys
import threading
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.optimizer import StrategyOptimizer


def make_frame():
    return pd.DataFrame(
        [
            [1, 100, 101, 99, 100, 10],
            [2, 102, 103, 101, 102, 11],
            [3, 104, 105, 103, 104, 12],
            [4, 106, 107, 105, 106, 13],
            [5, 108, 109, 107, 108, 14],
            [6, 110, 111, 109, 110, 15],
        ],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )


class TunableStrategy:
    def __init__(self):
        self.rsi_period = 14
        self.ema_fast = 20
        self.ema_slow = 50
        self.atr_period = 14

    def generate_signal(self, candles, strategy_name=None):
        length = len(candles)
        if self.ema_fast == 10 and self.ema_slow == 30:
            if length == 2:
                return {"side": "buy", "amount": 1}
            if length == 5:
                return {"side": "sell", "amount": 1}
        elif self.ema_fast == 15 and self.ema_slow == 35:
            if length == 3:
                return {"side": "buy", "amount": 1}
            if length == 4:
                return {"side": "sell", "amount": 1}
        return None


def test_strategy_optimizer_ranks_best_parameter_set():
    optimizer = StrategyOptimizer(strategy=TunableStrategy(), initial_balance=1000)
    results = optimizer.optimize(
        make_frame(),
        symbol="BTC/USDT",
        param_grid={
            "rsi_period": [10],
            "ema_fast": [10, 15],
            "ema_slow": [30, 35],
            "atr_period": [14],
        },
    )

    assert not results.empty
    best = results.iloc[0]
    assert int(best["ema_fast"]) == 10
    assert int(best["ema_slow"]) == 30
    assert float(best["total_profit"]) >= float(results.iloc[-1]["total_profit"])


def test_strategy_optimizer_skips_invalid_fast_slow_pairs():
    optimizer = StrategyOptimizer(strategy=TunableStrategy(), initial_balance=1000)
    results = optimizer.optimize(
        make_frame(),
        symbol="BTC/USDT",
        param_grid={
            "rsi_period": [10],
            "ema_fast": [20],
            "ema_slow": [10, 20, 30],
            "atr_period": [14],
        },
    )

    assert set(results["ema_slow"].astype(int).tolist()) == {30}


def test_strategy_optimizer_resolves_parallel_worker_count():
    optimizer = StrategyOptimizer(strategy=TunableStrategy(), initial_balance=1000)

    assert optimizer._resolve_max_workers(0) == 1
    assert optimizer._resolve_max_workers(1) == 1
    assert optimizer._resolve_max_workers(4, max_workers=2) == 2
    assert optimizer._resolve_max_workers(4, max_workers=10) == 4


def test_strategy_optimizer_parallel_run_keeps_results_and_tracking():
    class ParallelProbeStrategy(TunableStrategy):
        thread_ids = set()
        lock = threading.Lock()

        def generate_signal(self, candles, strategy_name=None):
            with self.lock:
                self.thread_ids.add(threading.get_ident())
            time.sleep(0.01)
            return super().generate_signal(candles, strategy_name=strategy_name)

    ParallelProbeStrategy.thread_ids.clear()
    optimizer = StrategyOptimizer(strategy=ParallelProbeStrategy(), initial_balance=1000)
    results = optimizer.optimize(
        make_frame(),
        symbol="BTC/USDT",
        param_grid={
            "rsi_period": [10],
            "ema_fast": [10, 15],
            "ema_slow": [30, 35],
            "atr_period": [14],
        },
        max_workers=2,
        experiment_name="parallel-check",
    )

    assert not results.empty
    assert len(optimizer.experiment_tracker.records) == 4
    assert len(ParallelProbeStrategy.thread_ids) >= 2
