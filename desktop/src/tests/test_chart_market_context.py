import os
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_chart_background_context_flags_fast_printing_aggressive_buying_and_trend_strength():
    _app()
    widget = ChartWidget("BTC/USDT", "tick", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000, 1700000060, 1700000120, 1700000180, 1700000240, 1700000270, 1700000285, 1700000292],
            "open": [100.0, 101.0, 102.0, 103.0, 105.0, 107.0, 110.0, 113.0],
            "high": [101.3, 102.3, 103.4, 105.5, 107.6, 110.5, 113.6, 116.4],
            "low": [99.5, 100.4, 101.5, 102.4, 104.1, 106.3, 109.1, 112.1],
            "close": [101.0, 102.0, 103.1, 105.0, 107.0, 110.0, 113.0, 116.0],
            "volume": [100.0, 104.0, 109.0, 118.0, 130.0, 220.0, 270.0, 320.0],
        }
    )

    widget.update_candles(frame)

    background_text = widget.background_context_label.text()
    details_html = widget.market_info_details.toHtml()

    assert "Fast bar printing" in background_text
    assert "Aggressive buying" in background_text
    assert "Trend strength" in background_text
    assert "Long bullish candles" in details_html
    assert "Repeated higher highs / higher lows" in details_html


def test_chart_background_context_flags_slow_printing_rejection_and_resistance_pressure():
    _app()
    widget = ChartWidget("EUR/USD", "tick", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000, 1700000030, 1700000060, 1700000090, 1700000180, 1700000300, 1700000480, 1700000720],
            "open": [100.0, 102.0, 104.0, 106.0, 107.10, 107.30, 107.40, 107.50],
            "high": [102.0, 104.1, 106.0, 108.0, 110.00, 110.10, 109.95, 110.05],
            "low": [99.4, 101.3, 103.2, 105.1, 106.60, 106.90, 107.00, 106.95],
            "close": [101.4, 103.4, 105.4, 106.8, 107.20, 107.25, 107.35, 107.30],
            "volume": [150.0, 145.0, 140.0, 136.0, 95.0, 80.0, 72.0, 65.0],
        }
    )

    widget.update_candles(frame)

    background_text = widget.background_context_label.text()
    details_html = widget.market_info_details.toHtml()

    assert "Slow bar printing" in background_text
    assert "Rejection / indecision" in background_text
    assert "Resistance pressure" in background_text
    assert "Small candles with long wicks" in details_html
    assert "Repeated failures at one level" in details_html


def test_chart_layout_prioritizes_price_pane_and_zoom_controls_reduce_visible_span():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000 + (index * 3600) for index in range(18)],
            "open": [100.0 + index for index in range(18)],
            "high": [101.4 + index for index in range(18)],
            "low": [99.2 + index for index in range(18)],
            "close": [100.8 + index for index in range(18)],
            "volume": [1000.0 + (index * 40.0) for index in range(18)],
        }
    )

    widget.update_candles(frame)
    initial_x_range, _ = widget.price_plot.viewRange()
    initial_span = float(initial_x_range[1]) - float(initial_x_range[0])

    widget._zoom_chart(0.72)
    zoomed_x_range, _ = widget.price_plot.viewRange()
    zoomed_span = float(zoomed_x_range[1]) - float(zoomed_x_range[0])

    widget._set_chart_overlays_visible(False)

    assert widget.price_plot.minimumHeight() >= 460
    assert widget.volume_plot.maximumHeight() <= 150
    assert widget.splitter.count() == 2
    assert widget.overlay_context_item.isVisible() is False
    assert zoomed_span < initial_span


def test_chart_top_left_overlays_stack_compactly_like_a_single_info_block():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000 + (index * 3600) for index in range(18)],
            "open": [100.0 + index for index in range(18)],
            "high": [101.4 + index for index in range(18)],
            "low": [99.2 + index for index in range(18)],
            "close": [100.8 + index for index in range(18)],
            "volume": [1000.0 + (index * 40.0) for index in range(18)],
        }
    )

    widget.update_candles(frame)

    header_pos = widget.overlay_header_item.pos()
    context_pos = widget.overlay_context_item.pos()
    ohlcv_pos = widget.overlay_ohlcv_item.pos()
    _, y_range = widget.price_plot.viewRange()
    y_span = float(y_range[1]) - float(y_range[0])

    assert widget.overlay_header_item.isVisible() is True
    assert widget.overlay_context_item.isVisible() is True
    assert widget.overlay_ohlcv_item.isVisible() is True
    assert abs(float(header_pos.x()) - float(context_pos.x())) < 1e-6
    assert abs(float(header_pos.x()) - float(ohlcv_pos.x())) < 1e-6
    assert float(header_pos.y()) > float(context_pos.y()) > float(ohlcv_pos.y())
    assert (float(header_pos.y()) - float(context_pos.y())) < (y_span * 0.10)
    assert (float(context_pos.y()) - float(ohlcv_pos.y())) < (y_span * 0.10)


def test_chart_volume_bar_is_optional_and_can_be_restored_from_the_chart_menu_state():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    assert widget.show_volume_panel is False
    assert widget.volume_plot.isHidden() is True
    assert widget.price_plot.getPlotItem().getAxis("bottom").isVisible() is True

    widget.set_volume_panel_visible(True)

    assert widget.show_volume_panel is True
    assert widget.volume_plot.isHidden() is False
    assert widget.volume_plot.getPlotItem().getAxis("bottom").isVisible() is True


def test_chart_visual_theme_updates_plot_background_and_axis_colors():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    widget.set_visual_theme(
        chart_background="#f4efe5",
        grid_color="#6b7a8f",
        axis_color="#223344",
    )

    axis = widget.price_plot.getPlotItem().getAxis("right")

    assert widget.chart_background == "#f4efe5"
    assert widget.grid_color == "#6b7a8f"
    assert widget.axis_color == "#223344"
    assert widget.price_plot.backgroundBrush().color().name() == "#f4efe5"
    assert axis.pen().color().name() == "#223344"
    assert axis.textPen().color().name() == "#223344"
    assert axis.tickPen().color().name() == "#6b7a8f"
    assert "#f4efe5" in widget.market_tabs.styleSheet()
    assert "#223344" in widget.instrument_label.styleSheet()
    assert "rgba(244,239,229" in widget.controls_container.styleSheet()
    assert "rgba(244,239,229" in widget.market_info_summary.styleSheet()
    assert "rgba(34,51,68" in widget.market_info_details.styleSheet()
    assert "rgba(34,51,68" in widget.market_info_card_titles["Last"].styleSheet()


def test_chart_coinbase_style_surfaces_market_summary_and_segmented_tabs():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    assert widget.market_meta_label.isHidden() is False
    assert widget.market_micro_label.isHidden() is False
    assert "#1652f0" in widget.market_tabs.styleSheet()
    assert "#1652f0" in widget.timeframe_picker.styleSheet()
    assert "border-radius: 20px" in widget.candlestick_shell.styleSheet()


def test_chart_moves_timeframe_controls_into_tab_strip_and_limits_them_to_candlestick_view():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    assert widget.market_tabs.cornerWidget() is widget.controls_container
    assert widget.controls_container.isHidden() is False

    widget.market_tabs.setCurrentWidget(widget.market_info_page)
    QApplication.processEvents()

    assert widget.controls_container.isHidden() is True

    widget.market_tabs.setCurrentWidget(widget.candlestick_page)
    QApplication.processEvents()

    assert widget.controls_container.isHidden() is False


def test_chart_indicators_can_be_removed_from_price_and_lower_panes():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    ema_key = widget.add_indicator("EMA", 14)
    rsi_key = widget.add_indicator("RSI", 14)

    assert ema_key in widget.indicator_items
    assert rsi_key in widget.indicator_items
    assert rsi_key in widget.indicator_panes
    assert widget.splitter.count() == 3

    assert widget.remove_indicator(ema_key) is True
    assert ema_key not in widget.indicator_items
    assert all(spec["key"] != ema_key for spec in widget.indicators)

    assert widget.remove_indicator(rsi_key) is True
    assert rsi_key not in widget.indicator_items
    assert rsi_key not in widget.indicator_panes
    assert all(spec["key"] != rsi_key for spec in widget.indicators)
    assert widget.splitter.count() == 2


def test_chart_compact_view_mode_prioritizes_candles_and_keeps_datetime_axis_visible():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())

    widget.set_compact_view_mode(True)

    assert widget.compact_view_mode is True
    assert widget.default_visible_bars == 60
    assert widget.info_bar.isHidden() is True
    assert widget.market_tabs.tabBar().isHidden() is True
    assert widget.price_plot.minimumHeight() == 280
    assert widget.volume_plot.maximumHeight() == 96
    assert widget.price_plot.getPlotItem().getAxis("bottom").isVisible() is True


def test_chart_status_overlay_handles_loading_no_data_and_limited_history_states():
    _app()
    widget = ChartWidget("AAVE/USD", "1h", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000 + (index * 3600) for index in range(12)],
            "open": [100.0 + index for index in range(12)],
            "high": [101.1 + index for index in range(12)],
            "low": [99.4 + index for index in range(12)],
            "close": [100.5 + index for index in range(12)],
            "volume": [900.0 + (index * 25.0) for index in range(12)],
        }
    )

    widget.set_loading_state(True, requested_bars=240)

    assert widget.status_overlay_item.isVisible() is True
    assert widget._chart_status_mode == "loading"
    assert widget._chart_status_message == "Loading market data..."
    assert widget._chart_status_requested_bars == 240

    widget.update_candles(frame)

    assert widget.status_overlay_item.isVisible() is False
    assert widget._chart_status_mode == "idle"

    widget.set_no_data_state()

    assert widget.status_overlay_item.isVisible() is True
    assert widget._chart_status_mode == "error"
    assert widget._chart_status_message == "No data received."

    widget.set_history_notice(60, 240)

    assert widget.status_overlay_item.isVisible() is True
    assert widget._chart_status_mode == "notice"
    assert widget._chart_status_message == "Loaded 60 / 240 candles."


def test_chart_update_candles_filters_malformed_rows_before_rendering():
    _app()
    widget = ChartWidget("QNT/USDC", "1h", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000, 1700000000, 1700003600, None, 1700007200],
            "open": [74.0, 74.5, "bad", 75.0, 76.0],
            "high": [73.0, 76.0, 78.0, 76.0, 77.0],
            "low": [75.0, 73.5, 72.0, 74.0, 75.5],
            "close": [74.2, 75.2, 76.0, 75.5, 76.8],
            "volume": [-3.0, 15.0, 20.0, 4.0, None],
        }
    )

    widget.update_candles(frame)

    assert widget._last_df is not None
    assert len(widget._last_df.index) == 2
    assert float(widget._last_df.iloc[0]["open"]) == 74.5
    assert float(widget._last_df.iloc[0]["high"]) == 76.0
    assert float(widget._last_df.iloc[0]["low"]) == 73.5
    assert float(widget._last_df.iloc[0]["close"]) == 75.2
    assert float(widget._last_df.iloc[0]["volume"]) == 15.0
    assert float(widget._last_df.iloc[1]["volume"]) == 0.0


def test_chart_update_candles_normalizes_mixed_second_and_millisecond_timestamps():
    _app()
    widget = ChartWidget("AAVE/USD", "1m", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000, 1700000060000, 1700000120],
            "open": [100.0, 100.2, 100.4],
            "high": [100.5, 100.7, 100.9],
            "low": [99.8, 100.0, 100.2],
            "close": [100.2, 100.4, 100.6],
            "volume": [12.0, 15.0, 18.0],
        }
    )

    widget.update_candles(frame)

    assert widget._last_x is not None
    assert len(widget._last_x) == 3
    diffs = [round(float(widget._last_x[i + 1] - widget._last_x[i]), 3) for i in range(2)]
    assert diffs == [60.0, 60.0]
    assert [round(float(value), 3) for value in widget._last_x] == [1700000000.0, 1700000060.0, 1700000120.0]

    axis = widget.price_plot.getAxis("bottom")
    assert axis.tickStrings([float(widget._last_x[-1])], 1.0, 60.0) == ["11-14 22:15"]


def test_chart_update_candles_accepts_preparsed_datetime_timestamps():
    _app()
    widget = ChartWidget("BTC/USDT", "1m", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([1700000000, 1700000060, 1700000120], unit="s", utc=True),
            "open": [100.0, 100.2, 100.4],
            "high": [100.5, 100.7, 100.9],
            "low": [99.8, 100.0, 100.2],
            "close": [100.2, 100.4, 100.6],
            "volume": [12.0, 15.0, 18.0],
        }
    )

    widget.update_candles(frame)

    assert widget._last_df is not None
    assert widget._last_x is not None
    assert [round(float(value), 3) for value in widget._last_x] == [1700000000.0, 1700000060.0, 1700000120.0]


def test_chart_update_candles_regularizes_sparse_intraday_spacing_to_timeframe():
    _app()
    widget = ChartWidget("AAVE/USD", "1m", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000, 1700003600, 1700007200],
            "open": [100.0, 100.2, 100.4],
            "high": [100.5, 100.7, 100.9],
            "low": [99.8, 100.0, 100.2],
            "close": [100.2, 100.4, 100.6],
            "volume": [12.0, 15.0, 18.0],
        }
    )

    widget.update_candles(frame)

    assert widget._last_x is not None
    assert len(widget._last_x) == 3
    diffs = [round(float(widget._last_x[i + 1] - widget._last_x[i]), 3) for i in range(2)]
    assert diffs == [60.0, 60.0]
    assert round(float(widget._last_x[-1]), 3) == 1700007200.0


def test_chart_update_candles_preserves_real_tick_timestamps():
    _app()
    widget = ChartWidget("BTC/USDT", "tick", _controller())
    timestamps = [1700000000, 1700000060, 1700000120, 1700000180, 1700000240, 1700000270, 1700000285, 1700000292]
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 101.0, 102.0, 103.0, 105.0, 107.0, 110.0, 113.0],
            "high": [101.3, 102.3, 103.4, 105.5, 107.6, 110.5, 113.6, 116.4],
            "low": [99.5, 100.4, 101.5, 102.4, 104.1, 106.3, 109.1, 112.1],
            "close": [101.0, 102.0, 103.1, 105.0, 107.0, 110.0, 113.0, 116.0],
            "volume": [100.0, 104.0, 109.0, 118.0, 130.0, 220.0, 270.0, 320.0],
        }
    )

    widget.update_candles(frame)

    assert widget._last_x is not None
    assert [round(float(value), 3) for value in widget._last_x] == [float(value) for value in timestamps]


def test_chart_update_candles_rejects_epoch_placeholder_timestamps():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", _controller())
    frame = pd.DataFrame(
        {
            "timestamp": [1, 2, 3],
            "open": [100.0, 100.2, 100.4],
            "high": [100.5, 100.7, 100.9],
            "low": [99.8, 100.0, 100.2],
            "close": [100.2, 100.4, 100.6],
            "volume": [12.0, 15.0, 18.0],
        }
    )

    widget.update_candles(frame)

    assert widget._last_df is None
    assert widget._last_x is None
    assert widget._chart_status_mode == "error"
    assert widget._chart_status_message == "No data received."
