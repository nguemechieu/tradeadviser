import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.chart.chart_widget import ChartWidget


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _controller():
    return SimpleNamespace(broker=None, config=None)


def _sample_frame(rows=40):
    return pd.DataFrame(
        {
            "timestamp": [1700000000 + (index * 3600) for index in range(rows)],
            "open": [100.0 + (index * 0.8) for index in range(rows)],
            "high": [101.2 + (index * 0.8) for index in range(rows)],
            "low": [99.1 + (index * 0.8) for index in range(rows)],
            "close": [100.6 + (index * 0.85) for index in range(rows)],
            "volume": [900.0 + (index * 22.0) for index in range(rows)],
        }
    )


def test_ema_indicator_reuses_existing_key_and_populates_curve():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    key = widget.add_indicator("EMA", 5)
    duplicate_key = widget.add_indicator("EMA", 5)
    widget.update_candles(_sample_frame())

    curve = widget.indicator_items[key][0]
    x_data, y_data = curve.getData()

    assert key == "EMA_5"
    assert duplicate_key == key
    assert len(widget.indicator_items[key]) == 1
    assert len(x_data) == 40
    assert len(y_data) == 40
    assert np.isfinite(y_data[-1])


def test_macd_indicator_creates_lower_pane_and_updates_all_series():
    _app()
    widget = ChartWidget("ETH/USDT", "1h", _controller())

    key = widget.add_indicator("MACD", 12)
    widget.update_candles(_sample_frame())

    histogram, macd_line, signal_line = widget.indicator_items[key]
    macd_x, macd_y = macd_line.getData()
    signal_x, signal_y = signal_line.getData()

    assert key == "MACD"
    assert key in widget.indicator_panes
    assert widget.splitter.count() == 3
    assert len(histogram.opts.get("x", [])) == 40
    assert len(histogram.opts.get("height", [])) == 40
    assert len(macd_x) == 40
    assert len(macd_y) == 40
    assert len(signal_x) == 40
    assert len(signal_y) == 40
    assert np.isfinite(macd_y[-1])
    assert np.isfinite(signal_y[-1])


def test_rsi_indicator_updates_linked_lower_pane_curve():
    _app()
    widget = ChartWidget("SOL/USDT", "1h", _controller())

    key = widget.add_indicator("RSI", 14)
    widget.update_candles(_sample_frame())

    curve = widget.indicator_items[key][0]
    x_data, y_data = curve.getData()

    assert key == "RSI_14"
    assert key in widget.indicator_panes
    assert len(x_data) == 40
    assert len(y_data) == 40
    assert np.isfinite(y_data[-1])
