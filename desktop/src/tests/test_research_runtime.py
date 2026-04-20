import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.experiment_tracker import ExperimentTracker
from backtesting.optimizer import StrategyOptimizer
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator
from backtesting.strategy_ranker import StrategyRanker
from backtesting.walk_forward import WalkForwardAnalyzer


def make_frame(length=12):
    rows = []
    base = 1_700_000_000
    price = 100.0
    for index in range(length):
        price += 1.5
        rows.append([base + index, price - 0.5, price + 0.5, price - 1.0, price, 10 + index])
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


class WindowStrategy:
    def generate_signal(self, candles, strategy_name=None):
        if len(candles) == 2:
            return {"side": "buy", "amount": 1}
        if len(candles) == 4:
            return {"side": "sell", "amount": 1}
        return None


class TunableStrategy:
    def __init__(self):
        self.rsi_period = 14
        self.ema_fast = 10
        self.ema_slow = 30
        self.atr_period = 14
        self.strategy_name = "Trend Following"

    def generate_signal(self, candles, strategy_name=None):
        if len(candles) == 2:
            return {"side": "buy", "amount": 1}
        if len(candles) == 5:
            return {"side": "sell", "amount": 1}
        return None


def test_simulator_applies_commission_and_slippage():
    simulator = Simulator(initial_balance=1000, commission_bps=10, slippage_bps=20)
    entry = simulator.execute({"side": "buy", "amount": 1}, {"timestamp": 1, "close": 100}, symbol="BTC/USDT")
    exit_trade = simulator.execute({"side": "sell", "amount": 1}, {"timestamp": 2, "close": 110}, symbol="BTC/USDT")

    assert entry["commission"] > 0
    assert entry["slippage_cost"] > 0
    assert exit_trade["commission"] > 0
    assert exit_trade["slippage_cost"] > 0
    assert exit_trade["pnl"] < 10.0


def test_report_generator_includes_research_metrics():
    trades = pd.DataFrame(
        [
            {"timestamp": 1, "symbol": "BTC/USDT", "side": "BUY", "type": "ENTRY", "price": 100, "amount": 1, "pnl": 0.0, "equity": 1000, "commission": 1.0, "slippage_cost": 0.5},
            {"timestamp": 2, "symbol": "BTC/USDT", "side": "SELL", "type": "EXIT", "price": 110, "amount": 1, "pnl": 8.5, "equity": 1008.5, "commission": 1.0, "slippage_cost": 0.5},
        ]
    )
    report = ReportGenerator(trades=trades, equity_history=[1000, 1008.5]).generate()

    assert report["commission_paid"] == 2.0
    assert report["slippage_cost"] == 1.0
    assert "profit_factor" in report
    assert "sortino_ratio" in report


def test_walk_forward_analyzer_builds_window_summaries():
    analyzer = WalkForwardAnalyzer(strategy=WindowStrategy(), initial_balance=1000, commission_bps=5, slippage_bps=5)
    summary, trades = analyzer.run(make_frame(14), symbol="BTC/USDT", train_size=5, test_size=4, step_size=4)

    assert not summary.empty
    assert "window_index" in summary.columns
    assert "commission_paid" in summary.columns
    assert isinstance(trades, pd.DataFrame)


def test_optimizer_tracks_experiments():
    optimizer = StrategyOptimizer(strategy=TunableStrategy(), initial_balance=1000)
    results = optimizer.optimize(
        make_frame(8),
        symbol="BTC/USDT",
        strategy_name="Trend Following",
        timeframe="1h",
        commission_bps=5,
        slippage_bps=5,
        param_grid={
            "rsi_period": [10],
            "ema_fast": [10],
            "ema_slow": [30],
            "atr_period": [14],
        },
        experiment_name="wf-baseline",
    )

    assert not results.empty
    tracker_frame = optimizer.experiment_tracker.to_frame()
    assert not tracker_frame.empty
    assert tracker_frame.iloc[0]["name"] == "wf-baseline"
    assert tracker_frame.iloc[0]["symbol"] == "BTC/USDT"


def test_experiment_tracker_flattens_records():
    tracker = ExperimentTracker()
    tracker.add_record(
        name="baseline",
        strategy_name="Trend Following",
        symbol="ETH/USDT",
        timeframe="4h",
        parameters={"ema_fast": 10},
        dataset_metadata={"rows": 500},
        metrics={"total_profit": 120.0},
    )
    frame = tracker.to_frame()

    assert not frame.empty
    assert frame.iloc[0]["param_ema_fast"] == 10
    assert frame.iloc[0]["data_rows"] == 500
    assert frame.iloc[0]["total_profit"] == 120.0


def test_strategy_ranker_ranks_multiple_strategies_for_symbol():
    class RankedRegistry:
        def list(self):
            return ["Fast Winner", "Slow Loser"]

        def _resolve_strategy(self, strategy_name=None):
            return self

        def generate_signal(self, candles, strategy_name=None):
            length = len(candles)
            if strategy_name == "Fast Winner":
                if length == 2:
                    return {"side": "buy", "amount": 1}
                if length == 5:
                    return {"side": "sell", "amount": 1}
            if strategy_name == "Slow Loser":
                if length == 3:
                    return {"side": "buy", "amount": 1}
                if length == 4:
                    return {"side": "sell", "amount": 1}
            return None

    ranker = StrategyRanker(strategy_registry=RankedRegistry(), initial_balance=1000)

    results = ranker.rank(make_frame(8), symbol="EUR/USD", timeframe="1h")

    assert not results.empty
    assert list(results["strategy_name"]) == ["Fast Winner", "Slow Loser"]
    assert float(results.iloc[0]["score"]) >= float(results.iloc[1]["score"])
