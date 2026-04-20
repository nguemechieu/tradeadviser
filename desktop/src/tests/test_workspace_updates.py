import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QTableWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.panels.workspace_updates import (
    handle_strategy_debug,
    refresh_strategy_comparison_panel,
    strategy_scorecard_rows,
    update_orderbook,
    update_recent_trades,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_update_orderbook_and_recent_trades_route_to_active_views():
    orderbook_updates = []
    trade_updates = []
    chart_updates = []

    class _Chart:
        def __init__(self, symbol):
            self.symbol = symbol

        def update_orderbook_heatmap(self, bids, asks):
            chart_updates.append((self.symbol, bids, asks))

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        _current_chart_symbol=lambda: "EUR/USD",
        orderbook_panel=SimpleNamespace(
            update_orderbook=lambda bids, asks: orderbook_updates.append((bids, asks)),
            update_recent_trades=lambda trades: trade_updates.append(trades),
        ),
        _iter_chart_widgets=lambda: [_Chart("EUR/USD"), _Chart("BTC/USDT")],
    )

    update_orderbook(fake, "EUR/USD", [(1.1, 10)], [(1.2, 12)])
    update_recent_trades(fake, "EUR/USD", [{"price": 1.15}])

    assert orderbook_updates == [([(1.1, 10)], [(1.2, 12)])]
    assert trade_updates == [[{"price": 1.15}]]
    assert chart_updates == [("EUR/USD", [(1.1, 10)], [(1.2, 12)])]


def test_handle_strategy_debug_populates_table_and_matching_chart():
    _app()
    recommendations = []
    chart_events = []
    table = QTableWidget()
    table.setColumnCount(7)

    class _Chart:
        def __init__(self, symbol):
            self.symbol = symbol

        def add_strategy_signal(self, index, price, signal):
            chart_events.append((self.symbol, index, price, signal))

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        MAX_LOG_ROWS=200,
        debug_table=table,
        _record_recommendation=lambda **kwargs: recommendations.append(kwargs),
        _iter_chart_widgets=lambda: [_Chart("EUR/USD"), _Chart("BTC/USDT")],
    )

    handle_strategy_debug(
        fake,
        {
            "symbol": "EUR/USD",
            "index": 42,
            "signal": "BUY",
            "rsi": 61.5,
            "ema_fast": 1.101,
            "ema_slow": 1.095,
            "ml_probability": 0.83,
            "reason": "Momentum aligned",
            "timestamp": "2026-03-15T12:00:00+00:00",
        },
    )

    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "BUY"
    assert recommendations[0]["strategy"] == "Strategy Engine"
    assert chart_events == [("EUR/USD", 42, 1.101, "BUY")]


def test_strategy_scorecard_rows_group_and_sort_trade_performance():
    fake = SimpleNamespace(
        controller=SimpleNamespace(strategy_name="Trend Following", config=None),
        _performance_trade_records=lambda: [
            {
                "source": "manual",
                "strategy_name": "",
                "pnl": 10.0,
                "confidence": 0.7,
                "spread_bps": 1.2,
                "slippage_bps": 0.5,
                "fee": 0.2,
            },
            {
                "source": "bot",
                "strategy_name": "Trend Following",
                "pnl": -3.0,
                "confidence": 0.6,
                "spread_bps": 1.0,
                "slippage_bps": 0.4,
                "fee": 0.1,
            },
            {
                "source": "bot",
                "strategy_name": "Trend Following",
                "pnl": 8.0,
                "confidence": 0.9,
                "spread_bps": 0.8,
                "slippage_bps": 0.3,
                "fee": 0.1,
            },
        ],
        _safe_float=lambda value, default=None: default if value is None else float(value),
    )

    rows = strategy_scorecard_rows(fake)

    by_strategy = {row["strategy"]: row for row in rows}

    assert rows[0]["strategy"] == "Manual"
    assert by_strategy["Trend Following"]["orders"] == 2
    assert by_strategy["Trend Following"]["realized"] == 2
    assert by_strategy["Trend Following"]["net_pnl"] == 5.0
    assert by_strategy["Manual"]["source"] == "Manual"


def test_refresh_strategy_comparison_panel_populates_table():
    _app()
    table = QTableWidget()
    table.setColumnCount(11)
    fake = SimpleNamespace(
        strategy_table=table,
        controller=SimpleNamespace(strategy_name="Trend Following", config=None),
        _performance_trade_records=lambda: [
            {
                "source": "bot",
                "strategy_name": "Trend Following",
                "pnl": 12.5,
                "confidence": 0.75,
                "spread_bps": 0.9,
                "slippage_bps": 0.2,
                "fee": 0.3,
            }
        ],
        _safe_float=lambda value, default=None: default if value is None else float(value),
        _format_percent_text=lambda value: "-" if value is None else f"{float(value) * 100.0:.2f}%",
        _format_currency=lambda value: "-" if value is None else f"{float(value):,.2f}",
    )

    refresh_strategy_comparison_panel(fake)

    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "Trend Following"
    assert table.item(0, 5).text() == "12.50"
