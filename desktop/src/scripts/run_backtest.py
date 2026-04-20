"""Run a simple momentum strategy backtest from CSV data."""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.backtesting.simulator import Simulator
from src.strategy.momentum_strategy import MomentumStrategy
from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator


def main():
    """Run the backtest and print a summary report."""
    data_path = REPO_ROOT / "data" / "processed" / "btc_1h.csv"
    df = pd.read_csv(data_path)

    strategy = MomentumStrategy(None)
    simulator = Simulator(initial_balance=500)
    engine = BacktestEngine(strategy, simulator)

    results = engine.run(df)
    report = ReportGenerator().generate(results)

    print("\nBacktest Results")
    print(report)


if __name__ == "__main__":
    main()