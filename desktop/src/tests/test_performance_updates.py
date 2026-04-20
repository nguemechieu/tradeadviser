import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QTableWidget, QTextBrowser

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.performance_engine import PerformanceEngine
from frontend.ui.panels.performance_updates import (
    performance_snapshot,
    populate_performance_view,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _Curve:
    def __init__(self):
        self.x = None
        self.y = None
        self.data = None

    def setData(self, *args):
        if len(args) == 1:
            self.x = None
            self.y = None
            self.data = list(args[0])
            return
        self.x = list(args[0])
        self.y = list(args[1])
        self.data = list(args[1])


def test_performance_engine_tracks_timestamps_for_datetime_axis():
    engine = PerformanceEngine()

    engine.update_equity(1000.0, timestamp=1710000000.0)
    engine.load_equity_history([1000.0, {"equity": 1100.0, "timestamp": 1710000060.0}])

    assert len(engine.equity_curve) == 2
    assert len(engine.equity_timestamps) == 2
    assert engine.equity_timestamps[1] == 1710000060.0


def test_performance_snapshot_builds_metrics_and_insights():
    fake = SimpleNamespace(
        controller=SimpleNamespace(
            performance_engine=SimpleNamespace(
                report=lambda: {
                    "max_drawdown": 0.05,
                    "sharpe_ratio": 1.4,
                    "sortino_ratio": 1.8,
                    "volatility": 0.2,
                    "value_at_risk": -0.03,
                    "conditional_var": -0.05,
                }
            )
        ),
        _performance_series=lambda: [1000.0, 1050.0, 1100.0],
        _performance_time_series=lambda: [1710000000.0, 1710003600.0, 1710007200.0],
        _performance_trade_records=lambda: [
            {"symbol": "EUR/USD", "status": "filled", "pnl": 10.0, "fee": 0.2, "spread_bps": 1.1, "slippage_bps": 0.3},
            {"symbol": "EUR/USD", "status": "filled", "pnl": -3.0, "fee": 0.1, "spread_bps": 1.0, "slippage_bps": 0.2},
            {"symbol": "BTC/USDT", "status": "open"},
        ],
        _safe_float=lambda value, default=None: default if value in (None, "") else float(value),
        _format_currency=lambda value: "-" if value is None else f"{float(value):,.2f}",
        _format_percent_text=lambda value: "-" if value is None else f"{float(value) * 100.0:.2f}%",
        _format_ratio_text=lambda value: "-" if value is None else f"{float(value):.2f}",
    )

    snapshot = performance_snapshot(fake)

    assert snapshot["headline"]
    assert snapshot["metrics"]["Net PnL"]["text"] == "100.00"
    assert snapshot["metrics"]["Trades"]["text"] == "3"
    assert snapshot["equity_timestamps"] == [1710000000.0, 1710003600.0, 1710007200.0]
    assert snapshot["symbol_rows"][0]["symbol"] == "EUR/USD"
    assert snapshot["insights"]


def test_performance_snapshot_prefers_current_runtime_equity_and_open_orders():
    fake = SimpleNamespace(
        controller=SimpleNamespace(
            performance_engine=SimpleNamespace(
                report=lambda: {
                    "max_drawdown": 0.05,
                    "sharpe_ratio": 1.2,
                }
            )
        ),
        _performance_series=lambda: [1000.0, 1100.0],
        _performance_time_series=lambda: [1710000000.0, 1710003600.0],
        _runtime_metrics_snapshot=lambda: {
            "equity_value": 1200.0,
            "equity_timestamp": 1710007200.0,
            "open_order_count": 2,
        },
        _performance_trade_records=lambda: [
            {"symbol": "BTC/USDT", "status": "filled", "pnl": 25.0},
            {"symbol": "BTC/USDT", "status": "open"},
        ],
        _safe_float=lambda value, default=None: default if value in (None, "") else float(value),
        _format_currency=lambda value: "-" if value is None else f"{float(value):,.2f}",
        _format_percent_text=lambda value: "-" if value is None else f"{float(value) * 100.0:.2f}%",
        _format_ratio_text=lambda value: "-" if value is None else f"{float(value):.2f}",
    )

    snapshot = performance_snapshot(fake)

    assert snapshot["metrics"]["Equity"]["text"] == "1,200.00"
    assert snapshot["metrics"]["Open Orders"]["text"] == "2"
    assert snapshot["metrics"]["Pending Orders"]["text"] == "2"
    assert snapshot["equity_series"][-1] == 1200.0
    assert snapshot["equity_timestamps"][-1] == 1710007200.0
    assert "2 open orders" in " ".join(snapshot["insights"])


def test_populate_performance_view_updates_widgets():
    _app()
    summary = QLabel()
    insights = QTextBrowser()
    symbol_table = QTableWidget()
    symbol_table.setColumnCount(6)
    equity_curve = _Curve()
    drawdown_curve = _Curve()
    metric_label = QLabel()

    fake = SimpleNamespace(
        _performance_metric_style=lambda tone: f"tone:{tone}",
        _format_percent_text=lambda value: "-" if value is None else f"{float(value) * 100.0:.2f}%",
        _format_currency=lambda value: "-" if value is None else f"{float(value):,.2f}",
    )

    populate_performance_view(
        fake,
        {
            "summary": summary,
            "metric_labels": {"Net PnL": metric_label},
            "equity_curve": equity_curve,
            "drawdown_curve": drawdown_curve,
            "insights": insights,
            "symbol_table": symbol_table,
        },
        {
            "headline": "Performance looks healthy.",
            "metrics": {"Net PnL": {"text": "100.00", "tone": "positive"}},
            "equity_series": [1000.0, 1100.0],
            "equity_timestamps": [1710000000.0, 1710003600.0],
            "drawdown_series": [0.0, 0.02],
            "drawdown_timestamps": [1710000000.0, 1710003600.0],
            "insights": ["Equity improved."],
            "symbol_rows": [{"symbol": "EUR/USD", "orders": 2, "realized": 2, "win_rate": 0.5, "net_pnl": 12.0, "avg_pnl": 6.0}],
        },
    )

    assert summary.text() == "Performance looks healthy."
    assert metric_label.text() == "100.00"
    assert metric_label.styleSheet() == "tone:positive"
    assert equity_curve.x == [1710000000.0, 1710003600.0]
    assert equity_curve.data == [1000.0, 1100.0]
    assert drawdown_curve.x == [1710000000.0, 1710003600.0]
    assert drawdown_curve.data == [0.0, 0.02]
    assert "Equity improved." in insights.toHtml()
    assert symbol_table.rowCount() == 1
