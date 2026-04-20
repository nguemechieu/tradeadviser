import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from PySide6.QtCore import QDate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator
from frontend.ui.terminal import (
    _hotfix_backtest_required_history_limit,
    _hotfix_backtest_frame_covers_range,
    _hotfix_prepare_backtest_context_with_selection,
)


class SequenceStrategy:
    def generate_signal(self, candles, strategy_name=None):
        length = len(candles)
        if length == 3:
            return {"side": "buy", "amount": 1, "reason": "entry"}
        if length == 5:
            return {"side": "sell", "amount": 1, "reason": "exit"}
        return None


def make_frame():
    return pd.DataFrame(
        [
            [1, 100, 101, 99, 100, 10],
            [2, 101, 102, 100, 101, 11],
            [3, 102, 103, 101, 102, 12],
            [4, 103, 104, 102, 103, 13],
            [5, 110, 111, 109, 110, 14],
            [6, 111, 112, 110, 111, 15],
        ],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )


def test_backtest_engine_executes_trades_and_builds_equity_curve():
    engine = BacktestEngine(strategy=SequenceStrategy(), simulator=Simulator(initial_balance=1000))

    results = engine.run(make_frame(), symbol="BTC/USDT")

    assert len(results) == 2
    assert list(results["side"]) == ["BUY", "SELL"]
    assert results.iloc[-1]["pnl"] == 8.0
    assert len(engine.equity_curve) == 6


def test_backtest_engine_closes_open_position_at_end():
    class HoldUntilEnd:
        def generate_signal(self, candles, strategy_name=None):
            if len(candles) == 2:
                return {"side": "buy", "amount": 1}
            return None

    engine = BacktestEngine(strategy=HoldUntilEnd(), simulator=Simulator(initial_balance=1000))
    results = engine.run(make_frame(), symbol="ETH/USDT")

    assert len(results) == 2
    assert results.iloc[-1]["reason"] == "end_of_test"
    assert results.iloc[-1]["side"] == "SELL"


def test_backtest_engine_respects_stop_event():
    class HoldStrategy:
        def generate_signal(self, candles, strategy_name=None):
            if len(candles) == 2:
                return {"side": "buy", "amount": 1}
            return None

    stop_event = threading.Event()
    stop_event.set()
    engine = BacktestEngine(strategy=HoldStrategy(), simulator=Simulator(initial_balance=1000))

    results = engine.run(make_frame(), symbol="ETH/USDT", stop_event=stop_event)

    assert results.empty
    assert engine.equity_curve == []


def test_backtest_engine_reuses_precomputed_feature_frame():
    class CachedFeatureStrategy:
        def __init__(self):
            self.compute_calls = 0
            self.signal_calls = 0

        def compute_features(self, candles):
            self.compute_calls += 1
            frame = candles.copy()
            frame["rsi"] = 50.0
            frame["ema_fast"] = frame["close"]
            frame["ema_slow"] = frame["close"] - 1.0
            frame["atr"] = 1.0
            frame["upper_band"] = frame["close"] + 1.0
            frame["lower_band"] = frame["close"] - 1.0
            frame["breakout_high"] = frame["high"].shift(1)
            frame["breakout_low"] = frame["low"].shift(1)
            frame["volume_ratio"] = 1.0
            frame["momentum"] = 0.0
            frame["macd_line"] = 0.0
            frame["macd_signal"] = 0.0
            frame["atr_pct"] = 0.0
            frame["trend_strength"] = 0.0
            frame["pullback_gap"] = 0.0
            frame["band_position"] = 0.5
            frame["regime"] = "range"
            return frame

        def generate_signal_from_features(self, df, strategy_name=None):
            self.signal_calls += 1
            if len(df) == 3:
                return {"side": "buy", "amount": 1, "reason": "entry"}
            if len(df) == 5:
                return {"side": "sell", "amount": 1, "reason": "exit"}
            return None

    strategy = CachedFeatureStrategy()
    engine = BacktestEngine(strategy=strategy, simulator=Simulator(initial_balance=1000))

    results = engine.run(make_frame(), symbol="BTC/USDT")

    assert len(results) == 2
    assert strategy.compute_calls == 1
    assert strategy.signal_calls == len(make_frame())


def test_report_generator_exports_files(tmp_path):
    trades = pd.DataFrame(
        [
            {"timestamp": 1, "symbol": "BTC/USDT", "side": "BUY", "type": "ENTRY", "price": 100, "amount": 1, "pnl": 0.0, "equity": 1000},
            {"timestamp": 2, "symbol": "BTC/USDT", "side": "SELL", "type": "EXIT", "price": 110, "amount": 1, "pnl": 10.0, "equity": 1010},
        ]
    )
    generator = ReportGenerator(trades=trades, equity_history=[1000, 1010], output_dir=tmp_path)

    report = generator.generate()
    pdf_path = generator.export_pdf()
    sheet_path = generator.export_excel()

    assert report["total_profit"] == 10.0
    assert report["closed_trades"] == 1
    assert pdf_path.exists()
    assert sheet_path.exists()


def test_report_generator_honors_explicit_export_paths(tmp_path):
    trades = pd.DataFrame(
        [
            {"timestamp": 1, "symbol": "ETH/USDT", "side": "BUY", "type": "ENTRY", "price": 200, "amount": 1, "pnl": 0.0, "equity": 1000},
            {"timestamp": 2, "symbol": "ETH/USDT", "side": "SELL", "type": "EXIT", "price": 230, "amount": 1, "pnl": 30.0, "equity": 1030},
        ]
    )
    export_dir = tmp_path / "custom-output"
    export_dir.mkdir()
    generator = ReportGenerator(trades=trades, equity_history=[1000, 1030], output_dir=tmp_path / "unused-default")

    pdf_target = export_dir / "session.pdf"
    sheet_target = export_dir / "session.xlsx"
    pdf_path = generator.export_pdf(pdf_target)
    sheet_path = generator.export_excel(sheet_target)

    assert pdf_path == pdf_target
    assert pdf_target.exists()
    assert sheet_path.parent == export_dir
    assert sheet_path.stem == sheet_target.stem
    assert sheet_path.suffix in {".xlsx", ".csv"}
    assert sheet_path.exists()


def test_backtest_frame_range_check_detects_missing_selected_dates():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-03-10T00:00:00+00:00", "2026-03-11T00:00:00+00:00"],
                utc=True,
            ),
            "open": [1.0, 1.1],
            "high": [1.1, 1.2],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
            "volume": [10, 11],
        }
    )

    assert _hotfix_backtest_frame_covers_range(
        frame,
        QDate(2026, 3, 10),
        QDate(2026, 3, 11),
    )
    assert not _hotfix_backtest_frame_covers_range(
        frame,
        QDate(2026, 3, 10),
        QDate(2026, 3, 13),
    )


def test_backtest_required_history_limit_matches_selected_range_when_under_cap():
    terminal = SimpleNamespace(
        controller=SimpleNamespace(
            limit=50000,
            MAX_BACKTEST_HISTORY_LIMIT=1000000,
            _resolve_backtest_history_limit=lambda limit=None: max(100, min(int(limit or 1000000), 1000000)),
        )
    )

    required_limit = _hotfix_backtest_required_history_limit(
        terminal,
        "1m",
        QDate(2026, 1, 1),
        QDate(2026, 3, 13),
    )

    assert required_limit == 103744


def test_backtest_required_history_limit_caps_at_one_million_bars():
    terminal = SimpleNamespace(
        controller=SimpleNamespace(
            limit=50000,
            MAX_BACKTEST_HISTORY_LIMIT=1000000,
            _resolve_backtest_history_limit=lambda limit=None: max(100, min(int(limit or 1000000), 1000000)),
        )
    )

    required_limit = _hotfix_backtest_required_history_limit(
        terminal,
        "1m",
        QDate(2020, 1, 1),
        QDate(2026, 3, 13),
    )

    assert required_limit == 1000000


def test_prepare_backtest_context_fetches_exchange_history_when_cache_range_is_too_small():
    symbol = "EUR/USD"
    timeframe = "1h"
    cached_frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-03-10T00:00:00+00:00", "2026-03-11T00:00:00+00:00"],
                utc=True,
            ),
            "open": [1.0, 1.1],
            "high": [1.1, 1.2],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
            "volume": [10, 11],
        }
    )
    full_frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-03-10T00:00:00+00:00",
                    "2026-03-11T00:00:00+00:00",
                    "2026-03-12T00:00:00+00:00",
                    "2026-03-13T00:00:00+00:00",
                ],
                utc=True,
            ),
            "open": [1.0, 1.1, 1.2, 1.3],
            "high": [1.1, 1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1, 1.2],
            "close": [1.05, 1.15, 1.25, 1.35],
            "volume": [10, 11, 12, 13],
        }
    )

    fetch_calls = []
    controller = SimpleNamespace(
        trading_system=None,
        candle_buffers={symbol: {timeframe: cached_frame}},
        strategy_name="Trend Following",
        limit=1000,
        _resolve_history_limit=lambda limit=None: int(limit or 1000),
    )

    async def request_candle_data(symbol, timeframe="1h", limit=None, start_time=None, end_time=None, history_scope="runtime"):
        fetch_calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "start_time": start_time,
                "end_time": end_time,
                "history_scope": history_scope,
            }
        )
        controller.candle_buffers[symbol][timeframe] = full_frame

    controller.request_candle_data = request_candle_data

    terminal = SimpleNamespace(
        _current_chart_widget=lambda: None,
        controller=controller,
        current_timeframe=timeframe,
        symbol=symbol,
        _backtest_context={
            "start_date": "2026-03-10",
            "end_date": "2026-03-13",
        },
    )

    context = asyncio.run(
        _hotfix_prepare_backtest_context_with_selection(
            terminal,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name="Trend Following",
        )
    )

    assert fetch_calls
    assert fetch_calls[0]["symbol"] == symbol
    assert fetch_calls[0]["timeframe"] == timeframe
    assert fetch_calls[0]["start_time"] == "2026-03-10T00:00:00+00:00"
    assert fetch_calls[0]["end_time"] == "2026-03-13T23:59:59.999999+00:00"
    assert fetch_calls[0]["history_scope"] == "backtest"
    assert len(context["data"]) == 4
    assert str(context["start_date"]) == "2026-03-10"
    assert str(context["end_date"]) == "2026-03-13"


def test_prepare_backtest_context_respects_requested_history_limit():
    symbol = "EUR/USD"
    timeframe = "1h"
    full_frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-03-10T00:00:00+00:00",
                    "2026-03-11T00:00:00+00:00",
                    "2026-03-12T00:00:00+00:00",
                    "2026-03-13T00:00:00+00:00",
                ],
                utc=True,
            ),
            "open": [1.0, 1.1, 1.2, 1.3],
            "high": [1.1, 1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1, 1.2],
            "close": [1.05, 1.15, 1.25, 1.35],
            "volume": [10, 11, 12, 13],
        }
    )

    controller = SimpleNamespace(
        trading_system=None,
        candle_buffers={symbol: {timeframe: full_frame}},
        strategy_name="Trend Following",
        limit=50000,
        _resolve_history_limit=lambda limit=None: int(limit or 50000),
    )

    terminal = SimpleNamespace(
        _current_chart_widget=lambda: None,
        controller=controller,
        current_timeframe=timeframe,
        symbol=symbol,
        _backtest_context={
            "start_date": "2026-03-10",
            "end_date": "2026-03-13",
            "history_limit": 2,
        },
    )

    context = asyncio.run(
        _hotfix_prepare_backtest_context_with_selection(
            terminal,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name="Trend Following",
        )
    )

    assert len(context["data"]) == 2
    assert str(context["history_limit"]) == "2"
    assert str(context["data"].iloc[0]["timestamp"].date()) == "2026-03-12"
    assert str(context["data"].iloc[-1]["timestamp"].date()) == "2026-03-13"
