import html
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6 import QtCore
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph import DateAxisItem, InfiniteLine, PlotWidget, ScatterPlotItem, SignalProxy, TextItem, mkPen

from ui.components.chart.chart_items import CandlestickItem
from ui.components.chart.indicator_utils import (
    accumulation_distribution,
    accelerator,
    adx,
    alligator,
    atr,
    awesome,
    bears_power,
    bollinger,
    bulls_power,
    cci,
    demarker,
    ema,
    envelopes,
    force_index,
    gator,
    ichimoku,
    lwma,
    macd,
    market_facilitation_index,
    momentum,
    money_flow_index,
    obv,
    parabolic_sar,
    rsi,
    rvi,
    sma,
    smma,
    standard_deviation,
    stochastic,
    true_range,
    williams_r,
)


TIMEFRAME_OPTIONS = ["1m", "5m", "15m", "30m", "1h","4h", "1d", "1w", "1mn"]


class TradingDateAxisItem(DateAxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = []
        if spacing < 60:
            time_format = "%m-%d %H:%M:%S"
        elif spacing < 86400:
            time_format = "%m-%d %H:%M"
        elif spacing < 31 * 86400:
            time_format = "%Y-%m-%d"
        else:
            time_format = "%Y-%m"

        for value in values:
            try:
                numeric = float(value)
            except Exception:
                labels.append("")
                continue

            if not np.isfinite(numeric):
                labels.append("")
                continue

            try:
                dt = datetime.fromtimestamp(numeric, tz=timezone.utc)
                labels.append(dt.strftime(time_format))
            except Exception:
                labels.append("")

        return labels


class ChartWidget(QWidget):
    sigMouseMoved = QtCore.Signal(object)
    sigTradeLevelRequested = QtCore.Signal(dict)
    sigTradeLevelChanged = QtCore.Signal(dict)
    sigTradeContextAction = QtCore.Signal(dict)
    sigTimeframeSelected = QtCore.Signal(str)
    sigActivated = QtCore.Signal(object)

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        controller,
        candle_up_color: str = "#26a69a",
        candle_down_color: str = "#ef5350",
        show_volume_panel: bool = False,
        chart_background: str = "#11161f",
        grid_color: str = "#8290a0",
        axis_color: str = "#9aa4b2",
    ):
        super().__init__()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.controller = controller
        self.symbol = symbol
        self.timeframe = timeframe
        self.candle_up_color = candle_up_color
        self.candle_down_color = candle_down_color
        self._last_candles = None
        self.show_bid_ask_lines = True
        self.show_volume_panel = bool(show_volume_panel)
        self._last_bid = None
        self._last_ask = None

        self.indicators = []
        self.indicator_items = {}
        self.indicator_panes = {}
        self.heatmap_buffer = []
        self.max_heatmap_rows = 220
        self.max_heatmap_levels = 120
        self._last_heatmap_price_range = None
        self._last_df = None
        self._last_x = None
        self._last_candle_stats = None
        self._watermark_initialized = False
        self._auto_fit_pending = True
        self._last_view_context = None
        self.default_visible_bars = 96
        self.chart_background = str(chart_background or "#11161f")
        self.panel_background = "#171d29"
        self.grid_color = str(grid_color or "#8290a0")
        self.axis_color = str(axis_color or "#9aa4b2")
        self.coinbase_accent = "#1652f0"
        self.muted_text = "#728198"
        self._last_price_change = None
        self._news_events = []
        self._news_items = []
        self._visible_news_events = []
        self._trade_overlay_updating = False
        self._trade_overlay_state = {"side": "buy", "entry": None, "stop_loss": None, "take_profit": None}
        self._last_orderbook_bids = []
        self._last_orderbook_asks = []
        self._timeframe_picker_updating = False
        self.chart_overlays_visible = True
        self.compact_view_mode = False
        self._chart_status_mode = "idle"
        self._chart_status_message = ""
        self._chart_status_detail = ""
        self._chart_status_requested_bars = None
        self._chart_loading_frames = ["|", "/", "-", "\\"]
        self._chart_loading_index = 0
        self._chart_tool_buttons = {}
        self._active_chart_tool = None
        self._chart_drawings = []
        self._drawing_anchor = None
        self._drawing_preview = None
        self._selected_annotation = None
        self._annotation_drag_state = None
        self._suppress_next_mouse_clicked = False
        self._trade_target_view_summary = ""
        self._chart_status_clear_timer = QtCore.QTimer(self)
        self._chart_status_clear_timer.setSingleShot(True)
        self._chart_status_clear_timer.timeout.connect(self._clear_status_notice)
        self._chart_loading_timer = QtCore.QTimer(self)
        self._chart_loading_timer.setInterval(150)
        self._chart_loading_timer.timeout.connect(self._tick_loading_status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.info_bar = QFrame()
        self.info_bar.setStyleSheet(
            """
            QFrame {
                background-color: #131a24;
                border: 1px solid #243142;
                border-radius: 14px;
            }
            """
        )
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(10, 5, 10, 5)
        info_layout.setSpacing(8)

        left_info = QVBoxLayout()
        left_info.setContentsMargins(0, 0, 0, 0)
        left_info.setSpacing(0)

        self.instrument_label = QLabel()
        self.instrument_label.setStyleSheet("color: #f6f8fb; font-weight: 800; font-size: 15px;")
        left_info.addWidget(self.instrument_label)

        self.market_stats_label = QLabel()
        self.market_stats_label.setStyleSheet("color: #32d296; font-weight: 800; font-size: 14px;")
        left_info.addWidget(self.market_stats_label)
        info_layout.addLayout(left_info, 1)

        self.market_meta_label = QLabel()
        self.market_meta_label.setStyleSheet("color: #728198; font-size: 11px;")
        self.market_meta_label.setWordWrap(False)
        self.market_micro_label = QLabel()
        self.market_micro_label.setStyleSheet("color: #9aa4b2; font-size: 11px;")
        self.market_micro_label.setWordWrap(False)
        self.background_context_label = QLabel()
        self.background_context_label.setStyleSheet("color: #e7c56f; font-size: 11px; font-weight: 700;")
        self.background_context_label.setWordWrap(True)
        self.ohlcv_label = QLabel()
        self.ohlcv_label.setStyleSheet("color: #dde5ef; font-weight: 700; font-size: 11px;")
        self.ohlcv_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_details = QVBoxLayout()
        header_details.setContentsMargins(0, 0, 0, 0)
        header_details.setSpacing(1)
        header_details.addWidget(self.market_meta_label)
        header_details.addWidget(self.market_micro_label)
        info_layout.addLayout(header_details, 2)

        for hidden_label in (self.background_context_label, self.ohlcv_label):
            hidden_label.hide()

        self.controls_container = QFrame()
        self.controls_container.setStyleSheet(
            """
            QFrame {
                background-color: #0f1621;
                border: 1px solid #243142;
                border-radius: 12px;
            }
            """
        )
        controls_layout = QHBoxLayout(self.controls_container)
        controls_layout.setContentsMargins(6, 3, 6, 3)
        controls_layout.setSpacing(4)

        self.timeframe_title = QLabel("TF")
        self.timeframe_title.setStyleSheet("color: #8fa4bf; font-size: 11px; font-weight: 700; padding-right: 4px;")
        controls_layout.addWidget(self.timeframe_title)

        self.timeframe_picker = QComboBox()
        self.timeframe_picker.setMinimumWidth(74)
        self.timeframe_picker.setMaximumWidth(94)
        self.timeframe_picker.setStyleSheet(
            """
            QComboBox {
                background-color: #162130;
                color: #f6f8fb;
                border: 1px solid #2b3b54;
                border-radius: 12px;
                padding: 4px 10px;
                font-weight: 700;
            }
            QComboBox::drop-down {
                border: 0;
                width: 20px;
            }
            """
        )
        self.timeframe_picker.addItems(TIMEFRAME_OPTIONS)
        if self.timeframe_picker.findText(str(self.timeframe)) < 0:
            self.timeframe_picker.addItem(str(self.timeframe))
        self.timeframe_picker.setCurrentText(str(self.timeframe))
        self.timeframe_picker.setToolTip("Select the timeframe for this chart. Hotkeys: , previous timeframe | . next timeframe.")
        self.timeframe_picker.currentTextChanged.connect(self._handle_timeframe_picker_changed)
        controls_layout.addWidget(self.timeframe_picker)

        self.overlay_toggle_button = QPushButton("Info")
        self.overlay_toggle_button.setCheckable(True)
        self.overlay_toggle_button.setChecked(True)
        self.overlay_toggle_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.overlay_toggle_button.setMinimumHeight(26)
        self.overlay_toggle_button.setStyleSheet(self._chart_nav_button_style(accent=True))
        self.overlay_toggle_button.clicked.connect(lambda checked=False: self._set_chart_overlays_visible(checked))
        controls_layout.addWidget(self.overlay_toggle_button)

        self.chart_tools_title = QLabel("Draw")
        self.chart_tools_title.setStyleSheet("color: #8fa4bf; font-size: 11px; font-weight: 700; padding-left: 6px;")
        controls_layout.addWidget(self.chart_tools_title)

        self.chart_tool_buttons = []
        for label, tool_name in self._chart_tool_definitions():
            button = QPushButton(label)
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(26)
            button.setCheckable(tool_name != "clear")
            button.setStyleSheet(self._chart_nav_button_style())
            button.setToolTip(self._chart_tool_tooltip(tool_name))
            button.clicked.connect(
                lambda checked=False, name=tool_name: self._handle_chart_tool_button(name, checked=checked)
            )
            controls_layout.addWidget(button)
            self.chart_tool_buttons.append(button)
            self._chart_tool_buttons[tool_name] = button

        self.chart_nav_buttons = []
        self.fit_chart_button = None
        for label, callback in (
            ("<-", lambda: self._pan_chart(-0.28)),
            ("+", lambda: self._zoom_chart(0.72)),
            ("Fit", self._fit_recent_chart),
            ("-", lambda: self._zoom_chart(1.35)),
            ("->", lambda: self._pan_chart(0.28)),
        ):
            button = QPushButton(label)
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(26)
            button.setStyleSheet(self._chart_nav_button_style(accent=(label == "Fit")))
            button.setToolTip(self._chart_nav_tooltip(label))
            button.clicked.connect(lambda _checked=False, action=callback: action())
            controls_layout.addWidget(button)
            self.chart_nav_buttons.append(button)
            if label == "Fit":
                self.fit_chart_button = button

        layout.addWidget(self.info_bar)

        self.market_tabs = QTabWidget()
        self.market_tabs.setDocumentMode(True)
        self.market_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #273142;
                background-color: #11161f;
                border-radius: 14px;
            }
            QTabBar::tab {
                background-color: #171d29;
                color: #8e9bab;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QTabBar::tab:selected {
                background-color: #1f2735;
                color: #f6f8fb;
            }
            """
        )
        self.market_tabs.setCornerWidget(self.controls_container, QtCore.Qt.Corner.TopRightCorner)
        self.market_tabs.currentChanged.connect(lambda _index: self._sync_chart_controls_visibility())
        layout.addWidget(self.market_tabs, 1)

        self.candlestick_page = QWidget()
        candlestick_layout = QVBoxLayout(self.candlestick_page)
        candlestick_layout.setContentsMargins(8, 4, 8, 8)
        candlestick_layout.setSpacing(4)

        self.candlestick_shell = QFrame()
        candlestick_shell_layout = QVBoxLayout(self.candlestick_shell)
        candlestick_shell_layout.setContentsMargins(2, 2, 2, 2)
        candlestick_shell_layout.setSpacing(0)

        self.splitter = QSplitter(QtCore.Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: #0f1419;
                border-top: 1px solid #1a2231;
                border-bottom: 1px solid #1a2231;
            }
            QSplitter::handle:hover {
                background-color: #192636;
            }
            """
        )
        candlestick_shell_layout.addWidget(self.splitter)
        candlestick_layout.addWidget(self.candlestick_shell)
        self.market_tabs.addTab(self.candlestick_page, "Candlestick")

        date_axis_top = TradingDateAxisItem(orientation="bottom")
        self.price_plot = PlotWidget(axisItems={"bottom": date_axis_top})
        self.price_plot.setLabel("right", "Price")
        self.price_plot.hideAxis("left")
        self.price_plot.showAxis("right")
        self.price_plot.hideAxis("bottom")
        self.price_plot.setMinimumHeight(400)
        self.splitter.addWidget(self.price_plot)

        self.candle_item = CandlestickItem(
            body_width=60.0,
            up_color=self.candle_up_color,
            down_color=self.candle_down_color,
        )
        self.price_plot.addItem(self.candle_item)

        self.ema_curve = self.price_plot.plot(pen=mkPen("#42a5f5", width=1.8))
        self.ema_curve.setVisible(False)

        self.signal_markers = ScatterPlotItem()
        self.news_markers = ScatterPlotItem()
        self.trade_scatter = ScatterPlotItem()
        self.price_plot.addItem(self.signal_markers)
        self.price_plot.addItem(self.news_markers)
        self.price_plot.addItem(self.trade_scatter)

        date_axis_mid = TradingDateAxisItem(orientation="bottom")
        self.volume_plot = PlotWidget(axisItems={"bottom": date_axis_mid})
        self.volume_plot.setXLink(self.price_plot)
        self.volume_plot.setLabel("left", "Volume")
        self.volume_plot.hideAxis("right")
        self.volume_plot.hideAxis("bottom")
        self.volume_plot.setMinimumHeight(70)
        self.volume_plot.setMaximumHeight(120)
        self.splitter.addWidget(self.volume_plot)

        self.volume_bars = pg.BarGraphItem(x=[], height=[], width=60.0, brush="#5c6bc0")
        self.volume_plot.addItem(self.volume_bars)

        date_axis_bottom = TradingDateAxisItem(orientation="bottom")
        self.heatmap_plot = PlotWidget(axisItems={"bottom": date_axis_bottom})
        self.heatmap_plot.setXLink(self.price_plot)
        self.heatmap_plot.setLabel("left", "Orderbook")
        self.heatmap_plot.setLabel("bottom", "Date / Time (UTC)")
        self.heatmap_plot.setMinimumHeight(50)
        self.heatmap_plot.setMaximumHeight(100)
        self.heatmap_plot.hide()

        self.heatmap_image = pg.ImageItem()
        colormap = pg.colormap.get("inferno")
        self.heatmap_image.setLookupTable(colormap.getLookupTable())
        self.heatmap_plot.addItem(self.heatmap_image)

        self.depth_page = QWidget()
        depth_layout = QVBoxLayout(self.depth_page)
        depth_layout.setContentsMargins(10, 10, 10, 10)
        depth_layout.setSpacing(8)

        self.depth_summary_label = QLabel("Depth chart will populate when live order book data arrives.")
        self.depth_summary_label.setStyleSheet("color: #8e9bab; font-size: 12px;")
        depth_layout.addWidget(self.depth_summary_label)

        self.depth_plot = PlotWidget()
        self.depth_plot.setMinimumHeight(360)
        self._style_plot(self.depth_plot, left_label="Cumulative Size", bottom_label="Price", show_bottom=True)
        self.depth_bid_curve = self.depth_plot.plot(
            [],
            [],
            pen=mkPen("#26a69a", width=2.2),
            stepMode="right",
            fillLevel=0,
            brush=(38, 166, 154, 70),
        )
        self.depth_ask_curve = self.depth_plot.plot(
            [],
            [],
            pen=mkPen("#ef5350", width=2.2),
            stepMode="right",
            fillLevel=0,
            brush=(239, 83, 80, 70),
        )
        depth_layout.addWidget(self.depth_plot, 1)
        self.market_tabs.addTab(self.depth_page, "Depth Chart")

        self.market_info_page = QWidget()
        info_tab_layout = QVBoxLayout(self.market_info_page)
        info_tab_layout.setContentsMargins(10, 10, 10, 10)
        info_tab_layout.setSpacing(10)

        self.market_info_summary = QLabel("Market details will update with ticker, candle, and order book context.")
        self.market_info_summary.setWordWrap(True)
        self.market_info_summary.setStyleSheet(
            "color: #ecf2f8; background-color: #171d29; border: 1px solid #273142; "
            "border-radius: 12px; padding: 12px; font-size: 12px; font-weight: 600;"
        )
        info_tab_layout.addWidget(self.market_info_summary)

        metrics_widget = QWidget()
        metrics_layout = QGridLayout(metrics_widget)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(10)
        self.market_info_cards = {}
        self.market_info_card_frames = {}
        self.market_info_card_titles = {}
        for index, key in enumerate(
            ["Last", "Mid", "Spread", "Best Bid", "Best Ask", "Range", "Visible Vol", "Depth Bias"]
        ):
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: #171d29; border: 1px solid #273142; border-radius: 12px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            title = QLabel(key)
            title.setStyleSheet("color: #8e9bab; font-size: 12px;")
            value = QLabel("-")
            value.setStyleSheet("color: #f6f8fb; font-size: 16px; font-weight: 700;")
            card_layout.addWidget(title)
            card_layout.addWidget(value)
            metrics_layout.addWidget(card, index // 4, index % 4)
            self.market_info_cards[key] = value
            self.market_info_card_frames[key] = card
            self.market_info_card_titles[key] = title
        info_tab_layout.addWidget(metrics_widget)

        self.market_info_details = QTextBrowser()
        self.market_info_details.setStyleSheet(
            "QTextBrowser { background-color: #171d29; color: #dde5ef; border: 1px solid #273142; border-radius: 12px; padding: 12px; }"
        )
        info_tab_layout.addWidget(self.market_info_details, 1)
        self.market_tabs.addTab(self.market_info_page, "Market Info")
        
        # Tick Chart tab - displays individual trades/ticks
        self.tick_page = QWidget()
        tick_layout = QVBoxLayout(self.tick_page)
        tick_layout.setContentsMargins(10, 10, 10, 10)
        tick_layout.setSpacing(8)
        
        self.tick_summary_label = QLabel("Tick chart displays individual trade executions and market ticks.")
        self.tick_summary_label.setStyleSheet("color: #8e9bab; font-size: 12px;")
        tick_layout.addWidget(self.tick_summary_label)
        
        date_axis_tick = TradingDateAxisItem(orientation="bottom")
        self.tick_plot = PlotWidget(axisItems={"bottom": date_axis_tick})
        self.tick_plot.setLabel("left", "Price")
        self.tick_plot.setLabel("bottom", "Time (UTC)")
        self.tick_plot.setMinimumHeight(300)
        self._style_plot(self.tick_plot, left_label="Price", bottom_label="Time (UTC)", show_bottom=True)
        
        self.tick_scatter = ScatterPlotItem()
        self.tick_plot.addItem(self.tick_scatter)
        
        tick_layout.addWidget(self.tick_plot, 1)
        self.market_tabs.addTab(self.tick_page, "Ticks")
        
        self._sync_chart_controls_visibility()

        self._style_plot(self.price_plot, right_label="Price", show_bottom=False)
        self._style_plot(self.volume_plot, left_label="Volume", bottom_label="Date / Time (UTC)", show_bottom=True)
        self._style_plot(self.heatmap_plot, left_label="Orderbook", bottom_label="Date / Time (UTC)", show_bottom=False)

        self.v_line = InfiniteLine(angle=90, movable=False, pen=mkPen((142, 164, 196, 90), width=1, style=QtCore.Qt.PenStyle.DashLine))
        self.h_line = InfiniteLine(angle=0, movable=False, pen=mkPen((142, 164, 196, 90), width=1, style=QtCore.Qt.PenStyle.DashLine))
        self.price_plot.addItem(self.v_line, ignoreBounds=True)
        self.price_plot.addItem(self.h_line, ignoreBounds=True)

        # Live price lines
        self.bid_line = InfiniteLine(
            angle=0,
            movable=False,
            pen=mkPen("#26a69a", width=1, style=QtCore.Qt.PenStyle.DashLine),
            label="Bid {value:.6f}",
            labelOpts={"position": 0.98, "color": "#26a69a", "fill": (11, 18, 32, 160)},
        )
        self.ask_line = InfiniteLine(
            angle=0,
            movable=False,
            pen=mkPen("#ef5350", width=1, style=QtCore.Qt.PenStyle.DashLine),
            label="Ask {value:.6f}",
            labelOpts={"position": 0.98, "color": "#ef5350", "fill": (11, 18, 32, 160)},
        )
        self.last_line = InfiniteLine(
            angle=0,
            movable=False,
            pen=mkPen("#32d296", width=1.15),
            label="{value:.6f}",
            labelOpts={"position": 0.98, "color": "#ffffff", "fill": (50, 210, 150, 205)},
        )

        for line in (self.bid_line, self.ask_line, self.last_line):
            line.setVisible(False)
            self.price_plot.addItem(line, ignoreBounds=True)

        self.trade_entry_line = self._create_trade_overlay_line("#2a7fff", "Entry {value:.6f}", "entry")
        self.trade_stop_line = self._create_trade_overlay_line("#ef5350", "SL {value:.6f}", "stop_loss")
        self.trade_take_line = self._create_trade_overlay_line("#32d296", "TP {value:.6f}", "take_profit")
        self.trade_risk_top_curve, self.trade_risk_bottom_curve, self.trade_risk_fill = self._create_trade_band(
            "#ef5350", 68
        )
        self.trade_reward_top_curve, self.trade_reward_bottom_curve, self.trade_reward_fill = self._create_trade_band(
            "#32d296", 58
        )
        self.trade_target_view_label = TextItem(
            html="",
            anchor=(1.0, 0.0),
            border=mkPen((76, 92, 115, 220)),
            fill=pg.mkBrush(11, 18, 32, 234),
        )
        self.trade_target_view_label.setZValue(12)
        self.trade_target_view_label.setVisible(False)
        self.price_plot.addItem(self.trade_target_view_label)

        self.text_item = TextItem(
            html="",
            anchor=(0.0, 1.0),
            border=mkPen((76, 92, 115, 210)),
            fill=pg.mkBrush(23, 29, 41, 238),
        )
        self.price_plot.addItem(self.text_item)

        self.news_hover_item = TextItem(
            html="",
            anchor=(0.0, 1.0),
            border=mkPen((244, 162, 97, 180), width=1),
            fill=pg.mkBrush(23, 29, 41, 240),
        )
        self.news_hover_item.setZValue(20)
        self.news_hover_item.setVisible(False)
        self.price_plot.addItem(self.news_hover_item)

        self.watermark_item = TextItem(
            html="",
            anchor=(0.5, 0.5),
            border=None,
            fill=None,
        )
        self.watermark_item.setZValue(-10)
        self.price_plot.addItem(self.watermark_item)

        self.status_overlay_item = TextItem(
            html="",
            anchor=(0.5, 0.5),
            border=mkPen((76, 92, 115, 220)),
            fill=pg.mkBrush(10, 15, 23, 236),
        )
        self.status_overlay_item.setZValue(16)
        self.status_overlay_item.setVisible(False)
        self.price_plot.addItem(self.status_overlay_item)

        self.overlay_header_item = TextItem(
            html="",
            anchor=(0.0, 0.0),
            border=mkPen((55, 70, 92, 185)),
            fill=pg.mkBrush(10, 15, 23, 222),
        )
        self.overlay_header_item.setZValue(14)
        self.price_plot.addItem(self.overlay_header_item)

        self.overlay_context_item = TextItem(
            html="",
            anchor=(0.0, 0.0),
            border=mkPen((77, 93, 116, 170)),
            fill=pg.mkBrush(14, 20, 29, 214),
        )
        self.overlay_context_item.setZValue(14)
        self.price_plot.addItem(self.overlay_context_item)

        self.overlay_ohlcv_item = TextItem(
            html="",
            anchor=(0.0, 0.0),
            border=mkPen((55, 70, 92, 185)),
            fill=pg.mkBrush(10, 15, 23, 226),
        )
        self.overlay_ohlcv_item.setZValue(14)
        self.price_plot.addItem(self.overlay_ohlcv_item)

        self.price_plot.getPlotItem().vb.sigRangeChanged.connect(self._update_watermark_position)
        self.price_plot.getPlotItem().vb.sigRangeChanged.connect(self._update_status_overlay_position)
        self.price_plot.getPlotItem().vb.sigRangeChanged.connect(self._update_overlay_positions)

        self.proxy = SignalProxy(self.price_plot.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved)
        self.price_plot.scene().sigMouseClicked.connect(self._mouse_clicked)
        self.price_plot.scene().installEventFilter(self)
        self.price_plot.viewport().installEventFilter(self)
        self._update_chart_interaction_cursor()

        self.splitter.setStretchFactor(0, 12)
        self.splitter.setStretchFactor(1, 2)
        self.set_volume_panel_visible(self.show_volume_panel)

        self._update_chart_header()
        self._refresh_market_panels()
        self._update_watermark_html()
        self._update_chart_overlays()
        self._apply_visual_theme()

    def _style_plot(self, plot, left_label=None, right_label=None, bottom_label=None, show_bottom=False):
        plot.setBackground(self._normalized_color(self.chart_background, "#11161f"))
        plot.showGrid(x=True, y=True, alpha=0.09)
        plot.setMenuEnabled(False)
        plot.hideButtons()

        item = plot.getPlotItem()
        item.layout.setContentsMargins(2, 2, 4, 2)

        if left_label:
            plot.setLabel("left", left_label)
        if right_label:
            plot.setLabel("right", right_label)
        if bottom_label:
            plot.setLabel("bottom", bottom_label)

        axis_names = ("left", "right", "bottom", "top")
        for axis_name in axis_names:
            axis = item.getAxis(axis_name)
            axis.setTextPen(pg.mkColor(self._normalized_color(self.axis_color, "#9aa4b2")))
            axis.setPen(pg.mkPen(self._normalized_color(self.axis_color, "#9aa4b2"), width=1))
            axis.setTickPen(pg.mkPen(self._normalized_color(self.grid_color, "#8290a0"), width=0.8))
            axis.setStyle(tickLength=-5, autoExpandTextSpace=False)
            try:
                axis.setGrid(48)
            except Exception:
                pass

        plot.showAxis("bottom") if show_bottom else plot.hideAxis("bottom")
        if right_label:
            plot.showAxis("right")

        item.vb.setBackgroundColor(pg.mkColor(self._normalized_color(self.chart_background, "#11161f")))

    def _normalized_color(self, value, fallback: str) -> str:
        try:
            return pg.mkColor(value).name()
        except Exception:
            return pg.mkColor(fallback).name()

    def _rgba_css(self, value, alpha: int, fallback: str) -> str:
        color = pg.mkColor(self._normalized_color(value, fallback))
        return f"rgba({color.red()},{color.green()},{color.blue()},{max(0, min(255, int(alpha)))})"

    def _update_chart_header_theme(self):
        surface_background = self._rgba_css(self.chart_background, 246, "#11161f")
        shell_background = self._rgba_css(self.chart_background, 252, "#11161f")
        border = self._rgba_css(self.grid_color, 88, "#8290a0")
        soft_border = self._rgba_css(self.grid_color, 56, "#8290a0")
        accent_glow = self._rgba_css(self.axis_color, 18, "#9aa4b2")
        title_color = self._normalized_color(self.axis_color, "#f6f8fb")
        meta_color = self._rgba_css(self.axis_color, 184, "#9aa4b2")
        micro_color = self._rgba_css(self.axis_color, 154, "#9aa4b2")

        self.info_bar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {surface_background};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            """
        )
        self.instrument_label.setStyleSheet(
            f"color: {title_color}; font-weight: 800; font-size: 17px; letter-spacing: 0.3px;"
        )
        self.market_meta_label.setStyleSheet(f"color: {meta_color}; font-size: 11px; font-weight: 600;")
        self.market_micro_label.setStyleSheet(f"color: {micro_color}; font-size: 11px;")
        self.controls_container.setStyleSheet(
            f"""
            QFrame {{
                background-color: {shell_background};
                border: 1px solid {soft_border};
                border-radius: 16px;
                padding: 0px;
            }}
            """
        )
        self.timeframe_title.setStyleSheet(
            f"color: {meta_color}; font-size: 11px; font-weight: 700; padding-right: 4px;"
        )
        self.background_context_label.setStyleSheet(
            f"color: {self.coinbase_accent}; background-color: {accent_glow}; "
            "border-radius: 9px; padding: 4px 8px; font-size: 11px; font-weight: 800;"
        )
        self.ohlcv_label.setStyleSheet(
            f"color: {title_color}; font-weight: 700; font-size: 11px; background-color: {accent_glow}; "
            "border-radius: 9px; padding: 4px 8px;"
        )

    def _market_panel_card_style(self, alpha: int = 248) -> str:
        background = self._rgba_css(self.chart_background, alpha, "#171d29")
        border = self._rgba_css(self.grid_color, 82, "#273142")
        return (
            "QFrame { "
            f"background-color: {background}; border: 1px solid {border}; border-radius: 14px; "
            "}"
        )

    def _update_market_context_theme(self):
        panel_background = self._rgba_css(self.chart_background, 246, "#171d29")
        detail_background = self._rgba_css(self.chart_background, 250, "#171d29")
        border = self._rgba_css(self.grid_color, 84, "#273142")
        title_color = self._rgba_css(self.axis_color, 168, "#8e9bab")
        value_color = self._normalized_color(self.axis_color, "#f6f8fb")
        detail_color = self._rgba_css(self.axis_color, 228, "#dde5ef")

        self.depth_summary_label.setStyleSheet(
            f"color: {title_color}; font-size: 12px; font-weight: 600;"
        )
        self.market_info_summary.setStyleSheet(
            "QLabel { "
            f"color: {value_color}; background-color: {panel_background}; border: 1px solid {border}; "
            "border-radius: 14px; padding: 14px; font-size: 12px; font-weight: 700; "
            "}"
        )
        self.market_info_details.setStyleSheet(
            "QTextBrowser { "
            f"background-color: {detail_background}; color: {detail_color}; border: 1px solid {border}; "
            "border-radius: 14px; padding: 14px; "
            "}"
        )
        for key, value_label in self.market_info_cards.items():
            frame = self.market_info_card_frames.get(key)
            if frame is not None:
                frame.setStyleSheet(self._market_panel_card_style(alpha=250))
            title = self.market_info_card_titles.get(key)
            if title is not None:
                title.setStyleSheet(f"color: {title_color}; font-size: 12px; font-weight: 700;")
            value_label.setStyleSheet(f"color: {value_color}; font-size: 16px; font-weight: 800;")

    def _timeframe_picker_style(self) -> str:
        field_background = self._rgba_css(self.chart_background, 255, "#11161f")
        text_color = self._normalized_color(self.axis_color, "#f6f8fb")
        border = self._rgba_css(self.grid_color, 98, "#8290a0")
        accent = self.coinbase_accent
        return (
            "QComboBox {"
            f"background-color: {field_background}; color: {text_color}; border: 1px solid {border}; "
            "border-radius: 12px; padding: 5px 10px; font-weight: 700; min-width: 60px;"
            "}"
            "QComboBox:hover {"
            f"border-color: {accent};"
            "}"
            "QComboBox::drop-down {"
            "border: 0; width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            f"background-color: {field_background}; color: {text_color}; selection-background-color: {accent};"
            "}"
        )

    def _update_chart_controls_theme(self):
        self.timeframe_picker.setStyleSheet(self._timeframe_picker_style())
        self.overlay_toggle_button.setStyleSheet(self._chart_nav_button_style(accent=True))
        self.chart_tools_title.setStyleSheet(
            f"color: {self._rgba_css(self.axis_color, 184, '#9aa4b2')}; font-size: 11px; font-weight: 700; padding-left: 6px;"
        )
        for button in list(getattr(self, "chart_tool_buttons", [])):
            button.setStyleSheet(self._chart_nav_button_style())
        for button in list(getattr(self, "chart_nav_buttons", [])):
            button.setStyleSheet(self._chart_nav_button_style(accent=(button is self.fit_chart_button)))

    def _chart_tool_definitions(self):
        return [
            ("Long", "long_rr"),
            ("Short", "short_rr"),
            ("Trend", "trend"),
            ("Info", "info"),
            ("Ghost", "ghost"),
            ("Arrow", "arrow"),
            ("Clear", "clear"),
        ]

    def _handle_chart_tool_button(self, tool_name: str, checked: bool = False):
        normalized = str(tool_name or "").strip().lower()
        if normalized == "clear":
            self._clear_chart_drawings()
            self.clear_trade_overlay()
            try:
                self.sigTradeContextAction.emit(
                    {
                        "action": "clear_levels",
                        "symbol": self.symbol,
                        "timeframe": self.timeframe,
                        "price": self._current_chart_reference_price() or 0.0,
                    }
                )
            except Exception:
                pass
            button = self._chart_tool_buttons.get("clear")
            if button is not None:
                button.blockSignals(True)
                button.setChecked(False)
                button.blockSignals(False)
            self._show_chart_interaction_notice("Chart annotations cleared.", auto_clear_ms=900)
            return

        if not checked and self._active_chart_tool == normalized:
            self._set_active_chart_tool(None)
            label = next((label for label, name in self._chart_tool_definitions() if name == normalized), "Tool")
            self._show_chart_interaction_notice(f"{label} tool disarmed.", auto_clear_ms=900)
            return
        if checked:
            self._set_active_chart_tool(normalized)
            label = next((label for label, name in self._chart_tool_definitions() if name == normalized), "Tool")
            detail = (
                "Click a price level to drop a target view."
                if normalized in {"long_rr", "short_rr"}
                else "Click once to anchor and again to place the drawing."
            )
            self._show_chart_interaction_notice(f"{label} tool armed.", detail, auto_clear_ms=1400)

    def _set_active_chart_tool(self, tool_name: str | None):
        normalized = str(tool_name or "").strip().lower() or None
        self._active_chart_tool = normalized
        self._drawing_anchor = None
        self._clear_drawing_preview()
        for name, button in dict(getattr(self, "_chart_tool_buttons", {}) or {}).items():
            button.blockSignals(True)
            button.setChecked(name == normalized and button.isCheckable())
            button.blockSignals(False)
        self._update_chart_interaction_cursor()

    def _chart_tool_tooltip(self, tool_name: str) -> str:
        tool = str(tool_name or "").strip().lower()
        hints = {
            "long_rr": "Long target view. Hotkey: L",
            "short_rr": "Short target view. Hotkey: S",
            "trend": "Trend line. Hotkey: T",
            "info": "Measurement/info line. Hotkey: I",
            "ghost": "Projected ghost path. Hotkey: G",
            "arrow": "Arrow annotation. Hotkey: A",
            "clear": "Clear all chart drawings and trade levels. Hotkey: Esc to cancel tools, Delete to remove selected items.",
        }
        return hints.get(tool, "Chart tool")

    def _chart_nav_tooltip(self, label: str) -> str:
        text = str(label or "").strip()
        hints = {
            "<-": "Pan chart left. Hotkey: Left Arrow",
            "->": "Pan chart right. Hotkey: Right Arrow",
            "+": "Zoom in. Hotkeys: + or Mouse Wheel Up",
            "-": "Zoom out. Hotkeys: - or Mouse Wheel Down",
            "Fit": "Fit the recent visible move. Hotkey: F",
        }
        return hints.get(text, "Chart navigation")

    def _chart_hotkey_summary(self) -> str:
        return "L/S/T/I/G/A tools | F fit | V volume | ,/. timeframe | Wheel zoom | Shift+Wheel pan"

    def _show_chart_interaction_notice(self, message: str, detail: str = "", auto_clear_ms: int = 1400):
        self._set_chart_status(
            "notice",
            message,
            detail or self._chart_hotkey_summary(),
            auto_clear_ms=auto_clear_ms,
        )

    def _chart_tool_shortcuts(self):
        return {
            "l": ("long_rr", "Long"),
            "s": ("short_rr", "Short"),
            "t": ("trend", "Trend"),
            "i": ("info", "Info"),
            "g": ("ghost", "Ghost"),
            "a": ("arrow", "Arrow"),
        }

    def _update_chart_interaction_cursor(self):
        viewport = getattr(self.price_plot, "viewport", lambda: None)()
        if viewport is None:
            return
        if self._annotation_drag_state is not None:
            viewport.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return
        if self._active_chart_tool is not None or self._drawing_anchor is not None:
            viewport.setCursor(QtCore.Qt.CursorShape.CrossCursor)
            return
        if self._selected_annotation is not None:
            viewport.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            return
        viewport.unsetCursor()

    def _cycle_timeframe(self, offset: int):
        options = [str(option).strip().lower() for option in TIMEFRAME_OPTIONS if str(option).strip()]
        if not options:
            return
        current = str(self.timeframe or options[0]).strip().lower() or options[0]
        if current not in options:
            options.append(current)
        current_index = options.index(current)
        target = options[(current_index + int(offset)) % len(options)]
        if target == current:
            return
        self.set_timeframe(target, emit_signal=True)
        self._show_chart_interaction_notice(f"Timeframe {target.upper()} selected.", auto_clear_ms=900)

    def _annotation_matches(self, left, right) -> bool:
        if left is right:
            return True
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        if str(left.get("kind") or "").strip().lower() != str(right.get("kind") or "").strip().lower():
            return False
        if left.get("kind") == "drawing":
            return left.get("drawing") is right.get("drawing")
        return True

    def _is_selected_drawing(self, drawing) -> bool:
        selected = getattr(self, "_selected_annotation", None)
        return isinstance(selected, dict) and selected.get("kind") == "drawing" and selected.get("drawing") is drawing

    def _trade_overlay_selected(self) -> bool:
        selected = getattr(self, "_selected_annotation", None)
        return isinstance(selected, dict) and selected.get("kind") == "trade_overlay"

    def _select_annotation(self, annotation):
        if annotation is not None and not isinstance(annotation, dict):
            return
        current = getattr(self, "_selected_annotation", None)
        if self._annotation_matches(current, annotation):
            return
        self._selected_annotation = annotation
        for drawing in list(getattr(self, "_chart_drawings", []) or []):
            start = drawing.get("start")
            end = drawing.get("end")
            if start is not None and end is not None:
                self._update_segment_drawing(drawing, start, end)
        self._apply_trade_overlay_line_styles()
        self._update_trade_target_view()
        self._update_chart_interaction_cursor()

    def _select_chart_drawing(self, drawing):
        if drawing is None:
            self._select_annotation(None)
            return
        self._select_annotation({"kind": "drawing", "drawing": drawing})

    def _select_trade_overlay(self):
        if self._format_numeric_value(self._trade_overlay_state.get("entry")) is None:
            self._select_annotation(None)
            return
        self._select_annotation({"kind": "trade_overlay"})

    def _annotation_display_name(self, annotation=None) -> str:
        target = annotation if isinstance(annotation, dict) else getattr(self, "_selected_annotation", None)
        if not isinstance(target, dict):
            return "Annotation"
        if target.get("kind") == "trade_overlay":
            side = str(self._trade_overlay_state.get("side") or "buy").strip().lower() or "buy"
            return "Short Target View" if side == "sell" else "Long Target View"
        drawing = target.get("drawing")
        tool = str(getattr(drawing, "get", lambda *_args, **_kwargs: "")("tool") or "").strip().lower()
        label_map = {
            "trend": "Trend Line",
            "info": "Info Line",
            "ghost": "Ghost Overlay",
            "arrow": "Arrow",
        }
        return label_map.get(tool, "Drawing")

    def _remove_chart_drawing(self, drawing):
        if drawing is None:
            return False
        remaining = []
        removed = False
        for candidate in list(getattr(self, "_chart_drawings", []) or []):
            if candidate is drawing:
                self._remove_chart_items(candidate.get("items"))
                removed = True
                continue
            remaining.append(candidate)
        self._chart_drawings = remaining
        if removed and self._is_selected_drawing(drawing):
            self._select_annotation(None)
        self._update_chart_interaction_cursor()
        return removed

    def _remove_selected_annotation(self):
        selected = getattr(self, "_selected_annotation", None)
        if not isinstance(selected, dict):
            return False
        if selected.get("kind") == "drawing":
            return self._remove_chart_drawing(selected.get("drawing"))
        if selected.get("kind") == "trade_overlay":
            self.clear_trade_overlay()
            self._select_annotation(None)
            self._update_chart_interaction_cursor()
            return True
        return False

    def _emit_trade_level_changed(self, level: str, price):
        numeric = self._format_numeric_value(price)
        if not level or numeric is None or numeric <= 0:
            return
        self.sigTradeLevelChanged.emit(
            {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "level": str(level),
                "price": float(numeric),
            }
        )

    def _sync_chart_controls_visibility(self):
        controls = getattr(self, "controls_container", None)
        tabs = getattr(self, "market_tabs", None)
        candlestick_page = getattr(self, "candlestick_page", None)
        if controls is None or tabs is None or candlestick_page is None:
            return
        show_controls = (not bool(getattr(self, "compact_view_mode", False))) and tabs.currentWidget() is candlestick_page
        controls.setVisible(show_controls)

    def _update_chart_surface_theme(self):
        shell_background = self._rgba_css(self.chart_background, 252, "#11161f")
        border = self._rgba_css(self.grid_color, 74, "#8290a0")
        handle_color = self._rgba_css(self.chart_background, 255, "#101827")
        handle_hover = self._rgba_css(self.axis_color, 26, "#9aa4b2")
        handle_border = self._rgba_css(self.grid_color, 72, "#8290a0")
        self.candlestick_shell.setStyleSheet(
            f"""
            QFrame {{
                background-color: {shell_background};
                border: 1px solid {border};
                border-radius: 20px;
            }}
            """
        )
        self.splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                background-color: {handle_color};
                border-top: 1px solid {handle_border};
                border-bottom: 1px solid {handle_border};
            }}
            QSplitter::handle:hover {{
                background-color: {handle_hover};
            }}
            """
        )

    def _update_market_tab_theme(self):
        chart_background = self._normalized_color(self.chart_background, "#11161f")
        panel_background = self._rgba_css(self.chart_background, 250, "#171d29")
        tab_text = self._rgba_css(self.axis_color, 176, "#9aa4b2")
        active_text = "#f8fbff"
        border = self._rgba_css(self.grid_color, 86, "#8290a0")
        hover_tab = self._rgba_css(self.axis_color, 22, "#9aa4b2")
        selected_tab = self.coinbase_accent
        self.market_tabs.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: 1px solid {border};
                background-color: {chart_background};
                border-radius: 18px;
                top: 10px;
            }}
            QTabBar::tab {{
                background-color: {panel_background};
                color: {tab_text};
                padding: 9px 16px;
                margin-right: 8px;
                border: 1px solid transparent;
                border-radius: 16px;
                font-weight: 700;
            }}
            QTabBar::tab:hover {{
                background-color: {hover_tab};
                color: {active_text};
            }}
            QTabBar::tab:selected {{
                background-color: {selected_tab};
                color: {active_text};
                border-color: {selected_tab};
            }}
            QTabBar::tab:!selected {{
                margin-top: 4px;
            }}
            """
        )

    def _update_chart_guide_theme(self):
        guide_color = pg.mkColor(self._normalized_color(self.axis_color, "#9aa4b2"))
        guide_color.setAlpha(90)
        guide_pen = mkPen(guide_color, width=1, style=QtCore.Qt.PenStyle.DashLine)
        self.v_line.setPen(guide_pen)
        self.h_line.setPen(guide_pen)

    def _apply_visual_theme(self):
        self._update_chart_header_theme()
        self._update_chart_controls_theme()
        self._update_chart_surface_theme()
        self._update_market_tab_theme()
        self._update_market_context_theme()
        self._style_plot(self.price_plot, right_label="Price", show_bottom=not self.show_volume_panel)
        self._style_plot(self.volume_plot, left_label="Volume", bottom_label="Date / Time (UTC)", show_bottom=self.show_volume_panel)
        self._style_plot(self.depth_plot, right_label="Price", bottom_label="Depth")
        self._style_plot(self.heatmap_plot, right_label="Price")
        self._update_chart_guide_theme()
        self._update_chart_bottom_axis_visibility()
        self._update_watermark_html()
        self._update_chart_overlays()
        self._refresh_status_overlay()

    def set_visual_theme(
        self,
        chart_background: str | None = None,
        grid_color: str | None = None,
        axis_color: str | None = None,
    ):
        if chart_background is not None:
            self.chart_background = str(chart_background or "#11161f")
        if grid_color is not None:
            self.grid_color = str(grid_color or "#8290a0")
        if axis_color is not None:
            self.axis_color = str(axis_color or "#9aa4b2")
        self._apply_visual_theme()
        self.refresh_context_display()

    def _chart_pane_widgets(self):
        panes = []
        for index in range(self.splitter.count()):
            widget = self.splitter.widget(index)
            if isinstance(widget, PlotWidget):
                panes.append(widget)
        return panes

    def _update_chart_bottom_axis_visibility(self):
        panes = self._chart_pane_widgets()
        visible_panes = [pane for pane in panes if not pane.isHidden()]
        active_bottom_pane = visible_panes[-1] if visible_panes else self.price_plot
        for pane in panes:
            if pane is active_bottom_pane:
                pane.showAxis("bottom")
                pane.setLabel("bottom", "Date / Time (UTC)")
            else:
                pane.hideAxis("bottom")

    def _apply_chart_pane_layout(self):
        pane_count = self.splitter.count()
        indicator_count = max(pane_count - 2, 0)
        if self.compact_view_mode:
            if self.show_volume_panel:
                self.volume_plot.show()
                sizes = [max(340, 520 - (indicator_count * 42))]
                if indicator_count:
                    sizes.extend([96] * indicator_count)
                sizes.append(82)
            else:
                self.volume_plot.hide()
                sizes = [max(400, 620 - (indicator_count * 36))]
                if indicator_count:
                    sizes.extend([96] * indicator_count)
                sizes.append(0)
            self._update_chart_bottom_axis_visibility()
            self.splitter.setSizes(sizes[:pane_count])
            return
        if self.show_volume_panel:
            self.volume_plot.show()
            sizes = [max(720, 960 - (indicator_count * 60))]
            if indicator_count:
                sizes.extend([130] * indicator_count)
            sizes.append(132)
        else:
            self.volume_plot.hide()
            sizes = [max(820, 1040 - (indicator_count * 45))]
            if indicator_count:
                sizes.extend([130] * indicator_count)
            sizes.append(0)
        self._update_chart_bottom_axis_visibility()
        self.splitter.setSizes(sizes[:pane_count])

    def _chart_nav_button_style(self, accent=False):
        text_color = "#f8fbff" if accent else self._normalized_color(self.axis_color, "#f2f6fb")
        background = self.coinbase_accent if accent else self._rgba_css(self.chart_background, 255, "#141d2b")
        hover = "#0f52ff" if accent else self._rgba_css(self.axis_color, 22, "#1d2a3d")
        border = self.coinbase_accent if accent else self._rgba_css(self.grid_color, 96, "#314156")
        checked_border = "#4a86ff" if accent else self.coinbase_accent
        return (
            "QPushButton {"
            f"background-color: {background}; color: {text_color}; border: 1px solid {border}; "
            "border-radius: 14px; padding: 6px 11px; font-size: 12px; font-weight: 700; min-width: 34px;"
            "}"
            "QPushButton:hover {"
            f"background-color: {hover}; border-color: {checked_border};"
            "}"
            "QPushButton:checked {"
            f"background-color: {hover}; border-color: {checked_border};"
            "}"
        )

    def _style_color_value(self, style: str, fallback: str) -> str:
        text = str(style or "")
        marker = "color:"
        if marker not in text:
            return fallback
        try:
            tail = text.split(marker, 1)[1]
            color = tail.split(";", 1)[0].strip()
            return color or fallback
        except Exception:
            return fallback

    def _overlay_card_html(self, title: str, lines, title_color: str, body_color: str = "#d7dfeb") -> str:
        line_html = "".join(
            f"<div style='color: {body_color}; font-size: 10px; margin-top: 2px; line-height: 1.2;'>{html.escape(str(line or ''))}</div>"
            for line in lines
            if str(line or "").strip()
        )
        return (
            "<div style='padding: 5px 7px;'>"
            f"<div style='color: {title_color}; font-size: 9px; font-weight: 800; letter-spacing: 0.4px; text-transform: uppercase;'>{html.escape(title)}</div>"
            f"{line_html}"
            "</div>"
        )

    def _chart_status_html(self) -> str:
        if not self._chart_status_message:
            return ""

        mode = str(self._chart_status_mode or "idle").strip().lower()
        title = "Chart Status"
        title_color = "#8fb2db"
        body_color = "#ecf2f8"
        lines = [self._chart_status_message]

        if mode == "loading":
            frame = self._chart_loading_frames[self._chart_loading_index % len(self._chart_loading_frames)]
            title = f"Loading {frame}"
            title_color = "#8fb2db"
            body_color = "#ecf2f8"
        elif mode == "error":
            title = "No Data"
            title_color = "#ef9a9a"
            body_color = "#fce8e6"
        elif mode == "notice":
            title = "History"
            title_color = "#f2d08b"
            body_color = "#f6f1dd"

        if self._chart_status_detail:
            lines.append(self._chart_status_detail)

        return self._overlay_card_html(title, lines, title_color, body_color)

    def _refresh_status_overlay(self):
        html_value = self._chart_status_html()
        if not html_value:
            self.status_overlay_item.setHtml("")
            self.status_overlay_item.setVisible(False)
            return
        self.status_overlay_item.setHtml(html_value)
        self.status_overlay_item.setVisible(True)
        self._update_status_overlay_position()

    def _set_chart_status(self, mode: str, message: str = "", detail: str = "", auto_clear_ms: int = 0):
        self._chart_status_mode = str(mode or "idle").strip().lower()
        self._chart_status_message = str(message or "").strip()
        self._chart_status_detail = str(detail or "").strip()

        if self._chart_status_clear_timer.isActive():
            self._chart_status_clear_timer.stop()

        if self._chart_status_mode == "loading" and self._chart_status_message:
            if not self._chart_loading_timer.isActive():
                # Safely start timer - use singleShot if not on main thread
                try:
                    import threading
                    from PySide6.QtCore import QTimer as QT
                    if threading.current_thread() is threading.main_thread():
                        self._chart_loading_timer.start()
                    else:
                        # From background thread, use singleShot which is thread-safe
                        QT.singleShot(100, lambda: self._chart_loading_timer.start() if not self._chart_loading_timer.isActive() else None)
                except Exception:
                    pass
        else:
            self._chart_loading_timer.stop()

        self._refresh_status_overlay()

        if auto_clear_ms > 0 and self._chart_status_mode not in {"idle", "loading", "error"} and self._chart_status_message:
            # Safely start timer - use singleShot if not on main thread
            try:
                import threading
                from PySide6.QtCore import QTimer as QT
                if threading.current_thread() is threading.main_thread():
                    self._chart_status_clear_timer.start(int(auto_clear_ms))
                else:
                    # From background thread, use singleShot which is thread-safe
                    QT.singleShot(auto_clear_ms, lambda: self._chart_status_clear_timer.start(int(auto_clear_ms)) if not self._chart_status_clear_timer.isActive() else None)
            except Exception:
                pass

    def _tick_loading_status(self):
        if self._chart_status_mode != "loading":
            self._chart_loading_timer.stop()
            return
        self._chart_loading_index = (self._chart_loading_index + 1) % max(len(self._chart_loading_frames), 1)
        self._refresh_status_overlay()

    def _clear_status_notice(self):
        if self._chart_status_mode == "notice":
            self.clear_data_status()

    def clear_data_status(self):
        self._chart_status_requested_bars = None
        self._set_chart_status("idle")

    def set_loading_state(self, loading: bool, requested_bars: int | None = None):
        if not loading:
            if self._chart_status_mode == "loading":
                self.clear_data_status()
            return

        self._chart_status_requested_bars = int(requested_bars) if requested_bars not in (None, "") else None
        if self._chart_status_requested_bars is not None and self._chart_status_requested_bars > 0:
            detail = (
                f"Requesting up to {self._chart_status_requested_bars} candles for "
                f"{self.symbol.upper()} ({self.timeframe})."
            )
        else:
            detail = f"Requesting candles for {self.symbol.upper()} ({self.timeframe})."
        self._chart_loading_index = 0
        self._set_chart_status("loading", "Loading market data...", detail)

    def set_no_data_state(self, detail: str = ""):
        status_detail = str(detail or "").strip()
        if not status_detail:
            status_detail = f"No candle history was returned for {self.symbol.upper()} ({self.timeframe})."
        self._set_chart_status("error", "No data received.", status_detail)

    def _clear_primary_chart_data(self):
        self._last_candles = None
        self._last_df = None
        self._last_x = None
        self._last_candle_stats = None
        self._visible_news_events = []
        self.candle_item.setData([])
        self.ema_curve.setData([], [])
        self.signal_markers.setData([], [])
        self.news_markers.setData([], [])
        self.trade_scatter.setData([], [])
        self.volume_bars.setOpts(
            x=[],
            height=[],
            width=max(float(getattr(self.candle_item, "body_width", 60.0) or 60.0), 1e-6),
            brushes=[],
        )
        self.last_line.setVisible(False)
        if hasattr(self, "clear_news_events"):
            self.clear_news_events()

    def set_history_notice(self, received_bars: int, requested_bars: int):
        try:
            received = max(0, int(received_bars))
        except Exception:
            received = 0
        try:
            requested = max(0, int(requested_bars))
        except Exception:
            requested = 0

        if received <= 0 or requested <= 0 or received >= requested:
            if self._chart_status_mode == "notice":
                self.clear_data_status()
            return

        self._set_chart_status(
            "notice",
            f"Loaded {received:,} / {requested:,} candles.",
            "Chart is using the broker history that is currently available.",
            auto_clear_ms=4800,
        )

    def _update_chart_overlays(self):
        header_lines = [
            str(self.market_meta_label.text() or "").strip(),
            str(self.market_micro_label.text() or "").strip(),
        ]
        context_text = str(self.background_context_label.text() or "").strip()
        ohlcv_text = str(self.ohlcv_label.text() or "").strip()
        header_summary = " | ".join(line for line in header_lines if line)

        header_visible = self.chart_overlays_visible and bool(header_summary)
        self.overlay_header_item.setHtml(
            self._overlay_card_html(
                "Market Context",
                [header_summary],
                "#8fb2db",
            )
        )
        self.overlay_header_item.setVisible(header_visible)

        context_color = self._style_color_value(getattr(self.background_context_label, "styleSheet", lambda: "")(), "#e7c56f")
        self.overlay_context_item.setHtml(
            self._overlay_card_html(
                "Background",
                [context_text],
                context_color,
                "#e8eef8",
            )
        )
        self.overlay_context_item.setVisible(self.chart_overlays_visible and bool(context_text))

        if ohlcv_text:
            ohlcv_segments = [segment.strip() for segment in ohlcv_text.split("  ") if segment.strip()]
            ohlcv_summary = " | ".join(ohlcv_segments)
            self.overlay_ohlcv_item.setHtml(
                self._overlay_card_html(
                    "Visible Candle",
                    [ohlcv_summary],
                    "#f2f6fb",
                )
            )
            self.overlay_ohlcv_item.setVisible(self.chart_overlays_visible)
        else:
            self.overlay_ohlcv_item.setVisible(False)

        self._update_overlay_positions()

    def _set_chart_overlays_visible(self, visible):
        self.chart_overlays_visible = bool(visible)
        toggle = getattr(self, "overlay_toggle_button", None)
        if toggle is not None and bool(toggle.isChecked()) != self.chart_overlays_visible:
            toggle.setChecked(self.chart_overlays_visible)
        self._update_chart_overlays()

    def _overlay_height_in_data(self, item, y_units_per_pixel: float) -> float:
        try:
            rect = item.boundingRect()
            return max(float(rect.height()) * max(y_units_per_pixel, 1e-9), 1e-6)
        except Exception:
            return max(y_units_per_pixel * 28.0, 1e-6)

    def _update_overlay_positions(self, *_args):
        if not self.chart_overlays_visible:
            return
        try:
            x_range, y_range = self.price_plot.viewRange()
        except Exception:
            return
        if len(x_range) < 2 or len(y_range) < 2:
            return

        x_min = float(x_range[0])
        x_max = float(x_range[1])
        y_min = float(y_range[0])
        y_max = float(y_range[1])
        x_span = max(abs(x_max - x_min), 1e-9)
        y_span = max(abs(y_max - y_min), 1e-9)
        step = self._time_axis_step()

        try:
            pixel_size = self.price_plot.getPlotItem().vb.viewPixelSize()
            y_units_per_pixel = abs(float(pixel_size[1])) if len(pixel_size) > 1 else y_span * 0.002
        except Exception:
            y_units_per_pixel = y_span * 0.002

        x_pad = max(x_span * 0.014, step * 1.35)
        y_pad = max(y_span * 0.018, y_units_per_pixel * 16.0, 1e-6)
        stack_gap = max(y_units_per_pixel * 7.0, y_span * 0.006)

        current_y = y_max - y_pad
        overlay_items = (
            self.overlay_header_item,
            self.overlay_context_item,
            self.overlay_ohlcv_item,
        )
        for item in overlay_items:
            if not item.isVisible():
                continue
            item.setPos(x_min + x_pad, current_y)
            current_y -= self._overlay_height_in_data(item, y_units_per_pixel) + stack_gap

    def _update_status_overlay_position(self, *_args):
        if not self.status_overlay_item.isVisible():
            return
        try:
            x_range, y_range = self.price_plot.viewRange()
        except Exception:
            return
        if len(x_range) < 2 or len(y_range) < 2:
            return
        center_x = (float(x_range[0]) + float(x_range[1])) / 2.0
        center_y = (float(y_range[0]) + float(y_range[1])) / 2.0
        self.status_overlay_item.setPos(center_x, center_y)

    def _time_axis_step(self):
        if self._last_x is None or len(self._last_x) < 2:
            return 60.0
        diffs = np.diff(self._last_x)
        diffs = diffs[np.isfinite(diffs)]
        diffs = diffs[np.abs(diffs) > 0]
        if len(diffs) == 0:
            return 60.0
        return max(float(np.median(np.abs(diffs))), 1e-6)

    def _fit_visible_y_range(self, x_min=None, x_max=None):
        if self._last_df is None or self._last_x is None or len(self._last_x) == 0:
            return

        mask = np.ones(len(self._last_x), dtype=bool)
        if x_min is not None and x_max is not None:
            mask = (self._last_x >= float(x_min)) & (self._last_x <= float(x_max))
            if not np.any(mask):
                mask = np.ones(len(self._last_x), dtype=bool)

        indices = np.where(mask)[0]
        visible = self._last_df.iloc[indices]
        if visible.empty:
            return

        try:
            high_values = visible["high"].astype(float).to_numpy()
            low_values = visible["low"].astype(float).to_numpy()
            volume_values = visible["volume"].astype(float).to_numpy()
        except Exception:
            return

        finite_high = high_values[np.isfinite(high_values)]
        finite_low = low_values[np.isfinite(low_values)]
        if len(finite_high) == 0 or len(finite_low) == 0:
            return

        high_price = float(np.max(finite_high))
        low_price = float(np.min(finite_low))
        span = max(high_price - low_price, max(abs(high_price) * 0.02, 1e-9))
        y_pad = span * 0.12

        price_vb = self.price_plot.getPlotItem().vb
        price_vb.enableAutoRange(x=False, y=False)
        price_vb.setYRange(low_price - y_pad, high_price + y_pad, padding=0.0)

        finite_volume = volume_values[np.isfinite(volume_values)]
        max_volume = float(np.max(finite_volume)) if len(finite_volume) else 0.0
        volume_vb = self.volume_plot.getPlotItem().vb
        volume_vb.enableAutoRange(x=False, y=False)
        volume_vb.setYRange(0.0, max(max_volume * 1.15, 1.0), padding=0.0)

        self._update_overlay_positions()

    def _set_chart_x_window(self, x_min, x_max, fit_y=True):
        if self._last_x is None or len(self._last_x) == 0:
            return

        step = self._time_axis_step()
        data_min = float(self._last_x[0] - (step * 2.0))
        data_max = float(self._last_x[-1] + (step * 2.0))
        min_span = max(step * 10.0, 1e-6)
        max_span = max(data_max - data_min, min_span)

        left = float(x_min)
        right = float(x_max)
        span = max(right - left, min_span)
        span = min(span, max_span)
        center = (left + right) / 2.0

        left = center - (span / 2.0)
        right = center + (span / 2.0)
        if left < data_min:
            left = data_min
            right = left + span
        if right > data_max:
            right = data_max
            left = right - span
        if left < data_min:
            left = data_min

        price_vb = self.price_plot.getPlotItem().vb
        price_vb.enableAutoRange(x=False, y=False)
        price_vb.setXRange(left, right, padding=0.0)
        if fit_y:
            self._fit_visible_y_range(left, right)
        else:
            self._update_overlay_positions()

    def _zoom_chart(self, scale):
        if self._last_x is None or len(self._last_x) == 0:
            return
        try:
            x_range, _ = self.price_plot.viewRange()
        except Exception:
            return
        if len(x_range) < 2:
            return
        center = (float(x_range[0]) + float(x_range[1])) / 2.0
        self._zoom_chart_at(center, scale)

    def _zoom_chart_at(self, anchor_x, scale):
        if self._last_x is None or len(self._last_x) == 0:
            return
        try:
            x_range, _ = self.price_plot.viewRange()
        except Exception:
            return
        if len(x_range) < 2:
            return
        left = float(x_range[0])
        right = float(x_range[1])
        span = max(right - left, self._time_axis_step() * 10.0)
        target_span = span * float(scale)
        numeric_anchor = self._format_numeric_value(anchor_x)
        if numeric_anchor is None:
            numeric_anchor = (left + right) / 2.0
        ratio = 0.5 if span <= 0 else min(1.0, max(0.0, (float(numeric_anchor) - left) / span))
        new_left = float(numeric_anchor) - (target_span * ratio)
        new_right = float(numeric_anchor) + (target_span * (1.0 - ratio))
        self._set_chart_x_window(new_left, new_right, fit_y=True)

    def _pan_chart(self, fraction):
        if self._last_x is None or len(self._last_x) == 0:
            return
        try:
            x_range, _ = self.price_plot.viewRange()
        except Exception:
            return
        if len(x_range) < 2:
            return
        span = float(x_range[1]) - float(x_range[0])
        shift = span * float(fraction)
        self._set_chart_x_window(float(x_range[0]) + shift, float(x_range[1]) + shift, fit_y=True)

    def _fit_recent_chart(self):
        if self._last_x is None or len(self._last_x) == 0 or self._last_candle_stats is None:
            return
        self._fit_chart_view(self._last_candle_stats, self._infer_candle_width(self._last_x))
        self._update_overlay_positions()

    def _create_indicator_pane(self, key: str, label: str):
        existing = self.indicator_panes.get(key)
        if existing is not None:
            return existing

        axis = TradingDateAxisItem(orientation="bottom")
        pane = PlotWidget(axisItems={"bottom": axis})
        pane.setXLink(self.price_plot)
        pane.hideAxis("right")
        pane.setMinimumHeight(90)
        self._style_plot(pane, left_label=label, show_bottom=False)
        self.splitter.insertWidget(max(self.splitter.count() - 1, 1), pane)
        self.indicator_panes[key] = pane

        current_sizes = self.splitter.sizes()
        if len(current_sizes) >= self.splitter.count():
            current_sizes.insert(max(len(current_sizes) - 1, 1), 130)
            self.splitter.setSizes(current_sizes[: self.splitter.count()])
        self._apply_chart_pane_layout()
        return pane

    def _create_curve(self, plot, color: str, width: float = 1.4, style=None):
        pen = mkPen(color, width=width)
        if style is not None:
            pen.setStyle(style)
        return plot.plot(pen=pen)

    def _create_histogram(self, plot, brush="#5c6bc0"):
        item = pg.BarGraphItem(x=[], height=[], width=1.0, y0=0, brush=brush)
        plot.addItem(item)
        return item

    def _set_histogram_data(self, item, x, values, width, brushes=None):
        if brushes is None:
            item.setOpts(x=x, height=values, width=width, y0=0)
        else:
            item.setOpts(x=x, height=values, width=width, y0=0, brushes=brushes)

    def _add_reference_line(self, plot, y_value: float, color: str = "#5d6d8a"):
        line = InfiniteLine(
            angle=0,
            movable=False,
            pen=mkPen(color, width=1, style=QtCore.Qt.PenStyle.DashLine),
        )
        line.setPos(y_value)
        plot.addItem(line, ignoreBounds=True)
        return line

    def _create_trade_band(self, color: str, alpha: int):
        top_curve = pg.PlotCurveItem([], [], pen=mkPen(color, width=1.1))
        bottom_curve = pg.PlotCurveItem([], [], pen=mkPen(color, width=1.1))
        fill = pg.FillBetweenItem(
            top_curve,
            bottom_curve,
            brush=pg.mkBrush(pg.mkColor(color).red(), pg.mkColor(color).green(), pg.mkColor(color).blue(), alpha),
        )
        for item, z_value in ((fill, 2), (top_curve, 3), (bottom_curve, 3)):
            item.setZValue(z_value)
            self.price_plot.addItem(item)
        fill.setVisible(False)
        return top_curve, bottom_curve, fill

    def _create_trade_overlay_line(self, color: str, label: str, level: str):
        line = InfiniteLine(
            angle=0,
            movable=True,
            pen=mkPen(color, width=1.35, style=QtCore.Qt.PenStyle.DashLine),
            label=label,
            labelOpts={"position": 0.98, "color": color, "fill": (11, 18, 32, 185)},
        )
        line.setVisible(False)
        line._trade_level = level
        line.sigPositionChangeFinished.connect(lambda item=line: self._handle_trade_line_moved(item))
        self.price_plot.addItem(line, ignoreBounds=True)
        return line

    def _apply_trade_overlay_line_styles(self):
        side = str(self._trade_overlay_state.get("side") or "buy").strip().lower() or "buy"
        selected = self._trade_overlay_selected()
        entry_color = "#32d296" if side == "buy" else "#ef5350"
        entry_width = 1.85 if selected else 1.4
        level_width = 1.8 if selected else 1.35
        band_width = 1.45 if selected else 1.1

        self.trade_entry_line.setPen(mkPen(entry_color, width=entry_width, style=QtCore.Qt.PenStyle.DashLine))
        self.trade_entry_line.label.fill = pg.mkBrush(pg.mkColor(entry_color))
        self.trade_entry_line.label.setColor(pg.mkColor("#ffffff"))
        self.trade_stop_line.setPen(mkPen("#ef5350", width=level_width, style=QtCore.Qt.PenStyle.DashLine))
        self.trade_take_line.setPen(mkPen("#32d296", width=level_width, style=QtCore.Qt.PenStyle.DashLine))
        for curve in (self.trade_risk_top_curve, self.trade_risk_bottom_curve):
            curve.setPen(mkPen("#ef5350", width=band_width))
        for curve in (self.trade_reward_top_curve, self.trade_reward_bottom_curve):
            curve.setPen(mkPen("#32d296", width=band_width))

    def _segment_drawing_pen(self, drawing):
        color = pg.mkColor(str(drawing.get("color") or "#9ec1ff"))
        preview_alpha = 140 if drawing.get("preview") else 255
        color.setAlpha(preview_alpha)
        width = 2.4 if self._is_selected_drawing(drawing) and not drawing.get("preview") else 1.6
        return mkPen(color, width=width, style=drawing.get("line_style"))

    def _estimate_x_step(self) -> float:
        if self._last_x is not None and len(self._last_x) >= 2:
            diffs = np.diff(self._last_x)
            diffs = diffs[np.isfinite(diffs)]
            diffs = diffs[np.abs(diffs) > 0]
            if len(diffs):
                return float(np.median(np.abs(diffs)))
        return float(self._timeframe_seconds() or 60.0)

    def _default_trade_overlay_window(self, anchor_x=None):
        step = max(self._estimate_x_step(), 1e-6)
        try:
            x_range, _ = self.price_plot.viewRange()
            visible_span = abs(float(x_range[1]) - float(x_range[0])) if len(x_range) >= 2 else 0.0
        except Exception:
            visible_span = step * 24.0

        numeric_anchor = self._format_numeric_value(anchor_x)
        if numeric_anchor is None:
            if self._last_x is not None and len(self._last_x) > 0:
                numeric_anchor = float(self._last_x[-1])
            else:
                numeric_anchor = 0.0
        x_span = max(step * 16.0, visible_span * 0.18, step * 4.0)
        return float(numeric_anchor), float(numeric_anchor + x_span)

    def _trade_overlay_window(self):
        state = dict(getattr(self, "_trade_overlay_state", {}) or {})
        x_start = self._format_numeric_value(state.get("x_start"))
        x_end = self._format_numeric_value(state.get("x_end"))
        if x_start is None or x_end is None or x_end <= x_start:
            return self._default_trade_overlay_window(anchor_x=state.get("anchor_x"))
        return float(x_start), float(x_end)

    def _current_chart_reference_price(self):
        state = dict(getattr(self, "_trade_overlay_state", {}) or {})
        for key in ("entry", "take_profit", "stop_loss"):
            price = self._format_numeric_value(state.get(key))
            if price is not None:
                return price
        stats = getattr(self, "_last_candle_stats", {}) or {}
        return self._format_numeric_value(stats.get("last_price"))

    def _default_trade_levels_for_entry(self, entry_price: float, side: str = "buy"):
        try:
            _x_range, y_range = self.price_plot.viewRange()
            visible_span = abs(float(y_range[1]) - float(y_range[0])) if len(y_range) >= 2 else 0.0
        except Exception:
            visible_span = 0.0
        risk_distance = max(abs(float(entry_price)) * 0.0025, visible_span * 0.055, 1e-6)
        normalized_side = str(side or "buy").strip().lower() or "buy"
        if normalized_side == "sell":
            return (
                float(entry_price),
                float(entry_price + risk_distance),
                float(entry_price - (risk_distance * 2.0)),
            )
        return (
            float(entry_price),
            float(entry_price - risk_distance),
            float(entry_price + (risk_distance * 2.0)),
        )

    def _update_trade_target_view(self):
        state = dict(getattr(self, "_trade_overlay_state", {}) or {})
        side = str(state.get("side") or "buy").strip().lower() or "buy"
        entry = self._format_numeric_value(state.get("entry"))
        stop_loss = self._format_numeric_value(state.get("stop_loss"))
        take_profit = self._format_numeric_value(state.get("take_profit"))
        selected = self._trade_overlay_selected()
        self._trade_target_view_summary = ""

        if entry is None or stop_loss is None or take_profit is None:
            for curve in (
                self.trade_risk_top_curve,
                self.trade_risk_bottom_curve,
                self.trade_reward_top_curve,
                self.trade_reward_bottom_curve,
            ):
                curve.setData([], [])
            self.trade_risk_fill.setVisible(False)
            self.trade_reward_fill.setVisible(False)
            self.trade_target_view_label.setVisible(False)
            return

        x_start, x_end = self._trade_overlay_window()
        x_values = [x_start, x_end]
        self.trade_risk_top_curve.setData(x_values, [entry, entry])
        self.trade_risk_bottom_curve.setData(x_values, [stop_loss, stop_loss])
        self.trade_reward_top_curve.setData(x_values, [take_profit, take_profit])
        self.trade_reward_bottom_curve.setData(x_values, [entry, entry])
        self.trade_risk_fill.setVisible(True)
        self.trade_reward_fill.setVisible(True)

        if side == "sell":
            risk = stop_loss - entry
            reward = entry - take_profit
        else:
            risk = entry - stop_loss
            reward = take_profit - entry

        if risk <= 0 or reward <= 0:
            self.trade_target_view_label.setVisible(False)
            return

        ratio = reward / risk if risk else 0.0
        self._trade_target_view_summary = f"RR {ratio:.2f} | Risk {risk:.5f} | Reward {reward:.5f}"
        body_lines = [
            f"Entry {entry:.6f} | SL {stop_loss:.6f} | TP {take_profit:.6f}",
            f"Risk {risk:.5f} | Reward {reward:.5f}",
        ]
        self.trade_target_view_label.setHtml(
            self._overlay_card_html(
                "Long Target View" if side == "buy" else "Short Target View",
                body_lines + [f"RR {ratio:.2f}"],
                "#ffd166" if selected else "#9ec1ff",
                body_color="#f4f8ff",
            )
        )
        self.trade_target_view_label.setPos(float(x_end), float(max(entry, stop_loss, take_profit)))
        self.trade_target_view_label.setVisible(True)

    def _handle_trade_line_moved(self, line):
        if self._trade_overlay_updating:
            return
        try:
            price = float(line.value())
        except Exception:
            return
        if not np.isfinite(price) or price <= 0:
            return
        level = getattr(line, "_trade_level", "")
        if not level:
            return
        self._trade_overlay_state[level] = price
        self.sigTradeLevelChanged.emit(
            {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "level": level,
                "price": price,
            }
        )
        self._update_trade_target_view()

    def set_trade_overlay(self, entry=None, stop_loss=None, take_profit=None, side="buy"):
        self._trade_overlay_updating = True
        try:
            normalized_side = str(side or "buy").strip().lower() or "buy"
            previous_state = dict(getattr(self, "_trade_overlay_state", {}) or {})
            self._trade_overlay_state = {
                "side": normalized_side,
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "anchor_x": previous_state.get("anchor_x"),
                "x_start": previous_state.get("x_start"),
                "x_end": previous_state.get("x_end"),
            }

            for line, value in (
                (self.trade_entry_line, entry),
                (self.trade_stop_line, stop_loss),
                (self.trade_take_line, take_profit),
            ):
                numeric = None
                try:
                    if value not in (None, ""):
                        numeric = float(value)
                except Exception:
                    numeric = None
                if numeric is not None and np.isfinite(numeric) and numeric > 0:
                    line.setPos(numeric)
                    line.setVisible(True)
                else:
                    line.setVisible(False)
        finally:
            self._trade_overlay_updating = False
        self._apply_trade_overlay_line_styles()
        self._update_trade_target_view()

    def clear_trade_overlay(self):
        self.set_trade_overlay(
            entry=None,
            stop_loss=None,
            take_profit=None,
            side=self._trade_overlay_state.get("side", "buy"),
        )
        if self._trade_overlay_selected():
            self._select_annotation(None)

    def _sync_view_context(self):
        context = (self.symbol, self.timeframe)
        if context != self._last_view_context:
            self._last_view_context = context
            self._auto_fit_pending = True
            self.heatmap_buffer.clear()
            self._last_heatmap_price_range = None
            self.heatmap_image.clear()
            self._last_orderbook_bids = []
            self._last_orderbook_asks = []
            self.depth_bid_curve.setData([], [])
            self.depth_ask_curve.setData([], [])
            self.depth_summary_label.setText("Depth chart will populate when live order book data arrives.")

    def _should_fit_chart_view(self, x):
        if self._auto_fit_pending:
            return True

        if x is None or len(x) == 0:
            return False

        try:
            x_range, _y_range = self.price_plot.viewRange()
        except Exception:
            return True

        if len(x_range) < 2 or not np.isfinite(x_range[0]) or not np.isfinite(x_range[1]):
            return True

        min_x = float(x[0])
        max_x = float(x[-1])
        visible_span = float(x_range[1]) - float(x_range[0])
        full_span = max(max_x - min_x, 1e-9)

        if visible_span <= 0:
            return True

        if float(x_range[1]) < min_x or float(x_range[0]) > max_x:
            return True

        # If the viewport is effectively the entire history, fit to a more useful recent window.
        if visible_span >= full_span * 0.98:
            return True

        return False

    def _visible_slice_start(self, x):
        if x is None or len(x) == 0:
            return 0
        visible_bars = min(len(x), self.default_visible_bars)
        return max(0, len(x) - visible_bars)

    def _build_candle_stats(self, df, x):
        if df is None or len(df) == 0 or x is None or len(x) == 0:
            return None

        start_index = self._visible_slice_start(x)
        visible = df.iloc[start_index:].copy()
        if visible.empty:
            return None

        open_values = visible["open"].astype(float).to_numpy()
        high_values = visible["high"].astype(float).to_numpy()
        low_values = visible["low"].astype(float).to_numpy()
        close_values = visible["close"].astype(float).to_numpy()
        volume_values = visible["volume"].astype(float).to_numpy()
        visible_x = np.asarray(x[start_index:], dtype=float)

        finite_high = high_values[np.isfinite(high_values)]
        finite_low = low_values[np.isfinite(low_values)]
        finite_close = close_values[np.isfinite(close_values)]
        finite_volume = volume_values[np.isfinite(volume_values)]

        if len(finite_high) == 0 or len(finite_low) == 0 or len(finite_close) == 0:
            return None

        first_open = float(open_values[0])
        last_close = float(close_values[-1])
        variation = ((last_close - first_open) / first_open * 100.0) if abs(first_open) > 1e-12 else 0.0

        return {
            "start_index": start_index,
            "x": visible_x,
            "min_price": float(np.min(finite_low)),
            "max_price": float(np.max(finite_high)),
            "max_volume": float(np.max(finite_volume)) if len(finite_volume) else 0.0,
            "average_close": float(np.mean(finite_close)),
            "cumulative_volume": float(np.sum(finite_volume)) if len(finite_volume) else 0.0,
            "last_price": last_close,
            "variation_pct": variation,
        }

    def _fit_chart_view(self, stats, width):
        if not stats:
            return

        visible_x = np.asarray(stats["x"], dtype=float)
        if len(visible_x) == 0:
            return

        min_x = float(visible_x[0] - (width * 2.0))
        max_x = float(visible_x[-1] + (width * 2.0))
        min_y = float(stats["min_price"])
        max_y = float(stats["max_price"])
        y_span = max(max_y - min_y, max(abs(max_y) * 0.02, 1e-9))
        y_pad = y_span * 0.10

        price_vb = self.price_plot.getPlotItem().vb
        price_vb.enableAutoRange(x=False, y=False)
        price_vb.setXRange(min_x, max_x, padding=0.0)
        price_vb.setYRange(min_y - y_pad, max_y + y_pad, padding=0.0)

        volume_vb = self.volume_plot.getPlotItem().vb
        volume_vb.enableAutoRange(x=False, y=False)
        volume_vb.setYRange(0.0, max(float(stats["max_volume"]) * 1.15, 1.0), padding=0.0)

        self._auto_fit_pending = False

    def _mouse_moved(self, evt):
        pos = evt[0]
        if not self.price_plot.sceneBoundingRect().contains(pos):
            self.news_hover_item.setVisible(False)
            return

        mouse_point = self.price_plot.getPlotItem().vb.mapSceneToView(pos)
        x = mouse_point.x()
        y = mouse_point.y()

        self.v_line.setPos(x)
        self.h_line.setPos(y)
        row = self._row_for_x(x)
        self.text_item.setHtml(self._hover_html(row, y))
        self.text_item.setPos(x, y)
        self._update_ohlcv_for_x(x)
        self._update_news_hover(x, y)
        if self._drawing_anchor is not None and self._drawing_preview is not None:
            self._update_segment_drawing(self._drawing_preview, self._drawing_anchor, {"x": x, "y": y})

    def _update_news_hover(self, x_value, y_value):
        event = self._nearest_news_event(x_value, y_value)
        if event is None:
            self.news_hover_item.setVisible(False)
            return

        self.news_hover_item.setHtml(self._news_hover_html(event))
        self.news_hover_item.setPos(float(event["x"]), float(event["y"]))
        self.news_hover_item.setVisible(True)

    def _chart_point_from_scene_pos(self, pos):
        if pos is None or not self.price_plot.sceneBoundingRect().contains(pos):
            return None
        try:
            mouse_point = self.price_plot.getPlotItem().vb.mapSceneToView(pos)
            x_value = float(mouse_point.x())
            y_value = float(mouse_point.y())
        except Exception:
            return None
        if not np.isfinite(x_value) or not np.isfinite(y_value) or y_value <= 0:
            return None
        return {"x": x_value, "y": y_value}

    def _remove_chart_items(self, items):
        for item in list(items or []):
            try:
                self.price_plot.removeItem(item)
            except Exception:
                continue

    def _create_segment_drawing(self, tool: str, preview: bool = False):
        normalized_tool = str(tool or "").strip().lower()
        color_map = {
            "trend": "#7cb7ff",
            "info": "#ffd166",
            "ghost": "#90a6c1",
            "arrow": "#ff8c42",
        }
        style_map = {
            "trend": QtCore.Qt.PenStyle.SolidLine,
            "info": QtCore.Qt.PenStyle.DashLine,
            "ghost": QtCore.Qt.PenStyle.DashDotLine,
            "arrow": QtCore.Qt.PenStyle.SolidLine,
        }
        curve = pg.PlotCurveItem([], [], pen=mkPen(color_map.get(normalized_tool, "#9ec1ff"), width=1.6))
        curve.setZValue(8 if not preview else 7)
        self.price_plot.addItem(curve)
        drawing = {
            "tool": normalized_tool,
            "curve": curve,
            "items": [curve],
            "preview": bool(preview),
            "summary": "",
            "color": color_map.get(normalized_tool, "#9ec1ff"),
            "line_style": style_map.get(normalized_tool),
        }

        if normalized_tool in {"info", "ghost"}:
            label = TextItem(
                html="",
                anchor=(0.5, 1.0),
                border=mkPen((76, 92, 115, 205)),
                fill=pg.mkBrush(11, 18, 32, 230 if not preview else 188),
            )
            label.setVisible(False)
            label.setZValue(10 if not preview else 9)
            self.price_plot.addItem(label)
            drawing["label"] = label
            drawing["items"].append(label)

        if normalized_tool == "arrow":
            color = pg.mkColor(str(drawing.get("color") or "#ff8c42"))
            color.setAlpha(140 if preview else 255)
            arrow = pg.ArrowItem(
                angle=0,
                headLen=14,
                tipAngle=28,
                baseAngle=22,
                tailLen=0,
                brush=pg.mkBrush(color),
                pen=mkPen(color, width=1.3),
            )
            arrow.setVisible(False)
            arrow.setZValue(10 if not preview else 9)
            self.price_plot.addItem(arrow)
            drawing["arrow"] = arrow
            drawing["items"].append(arrow)

        return drawing

    def _format_duration_label(self, seconds):
        numeric = self._format_numeric_value(seconds)
        if numeric is None:
            return "-"
        duration = abs(float(numeric))
        if duration < 60:
            return f"{duration:.0f}s"
        if duration < 3600:
            return f"{duration / 60.0:.1f}m"
        if duration < 86400:
            return f"{duration / 3600.0:.1f}h"
        if duration < 604800:
            return f"{duration / 86400.0:.1f}d"
        return f"{duration / 604800.0:.1f}w"

    def _line_measurement_details(self, start, end):
        delta = float(end["y"]) - float(start["y"])
        percent = (delta / float(start["y"])) * 100.0 if abs(float(start["y"])) > 1e-9 else 0.0
        bar_count = abs(float(end["x"]) - float(start["x"])) / max(self._estimate_x_step(), 1e-6)
        duration = self._format_duration_label(abs(float(end["x"]) - float(start["x"])))
        prefix = "+" if delta >= 0 else ""
        summary = f"{prefix}{self._format_metric(delta, 6)} ({percent:+.2f}%)"
        lines = [
            summary,
            f"{bar_count:.1f} bars | {duration}",
            f"{self._format_time_label(start['x'])} -> {self._format_time_label(end['x'])}",
        ]
        return lines, summary

    def _ghost_curve_points(self, start, end):
        x_start = float(start["x"])
        x_end = float(end["x"])
        y_start = float(start["y"])
        y_end = float(end["y"])
        delta_x = x_end - x_start
        delta_y = y_end - y_start
        lift = max(abs(delta_y) * 0.2, abs(y_start) * 0.0025, 1e-6)
        control_x = x_start + (delta_x * 0.58)
        control_y = y_start + (delta_y * 0.45) + (lift if delta_y >= 0 else -lift)
        return [x_start, control_x, x_end], [y_start, control_y, y_end]

    def _update_segment_drawing(self, drawing, start, end):
        if not drawing or start is None or end is None:
            return
        normalized_tool = str(drawing.get("tool") or "").strip().lower()
        if normalized_tool == "ghost":
            x_values, y_values = self._ghost_curve_points(start, end)
        else:
            x_values = [float(start["x"]), float(end["x"])]
            y_values = [float(start["y"]), float(end["y"])]
        drawing["points"] = list(zip(x_values, y_values))
        drawing["curve"].setPen(self._segment_drawing_pen(drawing))
        drawing["curve"].setData(x_values, y_values)

        label = drawing.get("label")
        if label is not None:
            lines, summary = self._line_measurement_details(start, end)
            title = "Info Line" if normalized_tool == "info" else "Ghost Feed"
            if normalized_tool == "ghost":
                lines = [lines[0], lines[1], "Projected path overlay"]
            title_color = "#ffd166" if normalized_tool == "info" or self._is_selected_drawing(drawing) else "#9ec1ff"
            label.setHtml(self._overlay_card_html(title, lines, title_color))
            label.setPos(float(end["x"]), float(end["y"]))
            label.setVisible(True)
            drawing["summary"] = summary

        arrow = drawing.get("arrow")
        if arrow is not None:
            angle = float(np.degrees(np.arctan2(float(end["y"]) - float(start["y"]), (float(end["x"]) - float(start["x"])) or 1e-9)))
            color = pg.mkColor(str(drawing.get("color") or "#ff8c42"))
            color.setAlpha(140 if drawing.get("preview") else 255)
            try:
                arrow.setStyle(
                    angle=angle,
                    pen=mkPen(color, width=1.9 if self._is_selected_drawing(drawing) else 1.3),
                    brush=pg.mkBrush(color),
                )
            except Exception:
                pass
            arrow.setPos(float(end["x"]), float(end["y"]))
            arrow.setVisible(True)

    def _clear_drawing_preview(self):
        preview = getattr(self, "_drawing_preview", None)
        if preview:
            self._remove_chart_items(preview.get("items"))
        self._drawing_preview = None

    def _commit_chart_drawing(self, tool: str, start, end):
        if start is None or end is None:
            return
        if abs(float(end["x"]) - float(start["x"])) < 1e-9 and abs(float(end["y"]) - float(start["y"])) < 1e-9:
            return
        drawing = self._create_segment_drawing(tool, preview=False)
        drawing["start"] = dict(start)
        drawing["end"] = dict(end)
        self._update_segment_drawing(drawing, start, end)
        self._chart_drawings.append(drawing)
        self._select_chart_drawing(drawing)

    def _clear_chart_drawings(self):
        self._drawing_anchor = None
        self._clear_drawing_preview()
        if isinstance(getattr(self, "_selected_annotation", None), dict) and self._selected_annotation.get("kind") == "drawing":
            self._select_annotation(None)
        for drawing in list(getattr(self, "_chart_drawings", []) or []):
            self._remove_chart_items(drawing.get("items"))
        self._chart_drawings = []
        self._update_chart_interaction_cursor()

    def _scene_distance_to_segment(self, point, start, end) -> float:
        px = float(point.x())
        py = float(point.y())
        ax = float(start.x())
        ay = float(start.y())
        bx = float(end.x())
        by = float(end.y())
        dx = bx - ax
        dy = by - ay
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return float(np.hypot(px - ax, py - ay))
        scale = ((px - ax) * dx + (py - ay) * dy) / ((dx * dx) + (dy * dy))
        scale = min(1.0, max(0.0, scale))
        closest_x = ax + (scale * dx)
        closest_y = ay + (scale * dy)
        return float(np.hypot(px - closest_x, py - closest_y))

    def _drawing_hit_distance(self, drawing, scene_pos):
        if drawing is None or scene_pos is None:
            return None
        label = drawing.get("label")
        try:
            if label is not None and label.isVisible() and label.sceneBoundingRect().contains(scene_pos):
                return 0.0
        except Exception:
            pass

        points = list(drawing.get("points") or [])
        if len(points) < 2:
            start = drawing.get("start")
            end = drawing.get("end")
            if start is None or end is None:
                return None
            points = [
                (float(start["x"]), float(start["y"])),
                (float(end["x"]), float(end["y"])),
            ]
        if len(points) < 2:
            return None

        try:
            view_box = self.price_plot.getPlotItem().vb
            scene_points = [
                view_box.mapViewToScene(QtCore.QPointF(float(x_value), float(y_value)))
                for x_value, y_value in points
            ]
        except Exception:
            return None

        best = None
        for index in range(len(scene_points) - 1):
            distance = self._scene_distance_to_segment(scene_pos, scene_points[index], scene_points[index + 1])
            if best is None or distance < best:
                best = distance
        return best

    def _annotation_hit_test(self, scene_pos, _point=None):
        if scene_pos is None:
            return None
        try:
            label = self.trade_target_view_label
            if label is not None and label.isVisible() and label.sceneBoundingRect().contains(scene_pos):
                return {"kind": "trade_overlay"}
        except Exception:
            pass

        best = None
        best_distance = None
        for drawing in reversed(list(getattr(self, "_chart_drawings", []) or [])):
            distance = self._drawing_hit_distance(drawing, scene_pos)
            if distance is None or distance > 18.0:
                continue
            if best is None or distance < best_distance:
                best = {"kind": "drawing", "drawing": drawing}
                best_distance = distance
        return best

    def _begin_annotation_drag(self, annotation, point):
        if not isinstance(annotation, dict) or point is None:
            return False
        if annotation.get("kind") == "drawing":
            drawing = annotation.get("drawing")
            if drawing is None:
                return False
            self._annotation_drag_state = {
                "kind": "drawing",
                "drawing": drawing,
                "origin": dict(point),
                "start": dict(drawing.get("start") or point),
                "end": dict(drawing.get("end") or point),
                "moved": False,
            }
            self._update_chart_interaction_cursor()
            return True
        if annotation.get("kind") == "trade_overlay":
            state = dict(getattr(self, "_trade_overlay_state", {}) or {})
            if self._format_numeric_value(state.get("entry")) is None:
                return False
            self._annotation_drag_state = {
                "kind": "trade_overlay",
                "origin": dict(point),
                "state": state,
                "moved": False,
            }
            self._update_chart_interaction_cursor()
            return True
        return False

    def _update_annotation_drag(self, point):
        drag = getattr(self, "_annotation_drag_state", None)
        if not isinstance(drag, dict) or point is None:
            return False
        origin = drag.get("origin") or {}
        delta_x = float(point["x"]) - float(origin.get("x", point["x"]))
        delta_y = float(point["y"]) - float(origin.get("y", point["y"]))
        if abs(delta_x) < 1e-9 and abs(delta_y) < 1e-9:
            return False
        drag["moved"] = True

        if drag.get("kind") == "drawing":
            start = dict(drag.get("start") or {})
            end = dict(drag.get("end") or {})
            min_y = min(float(start.get("y", 0.0)), float(end.get("y", 0.0)))
            if min_y + delta_y <= 0:
                delta_y = max(delta_y, 1e-6 - min_y)
            drawing = drag.get("drawing")
            new_start = {"x": float(start.get("x", 0.0)) + delta_x, "y": float(start.get("y", 0.0)) + delta_y}
            new_end = {"x": float(end.get("x", 0.0)) + delta_x, "y": float(end.get("y", 0.0)) + delta_y}
            drawing["start"] = new_start
            drawing["end"] = new_end
            self._update_segment_drawing(drawing, new_start, new_end)
            return True

        if drag.get("kind") == "trade_overlay":
            state = dict(drag.get("state") or {})
            numeric_prices = [
                self._format_numeric_value(state.get("entry")),
                self._format_numeric_value(state.get("stop_loss")),
                self._format_numeric_value(state.get("take_profit")),
            ]
            numeric_prices = [value for value in numeric_prices if value is not None]
            if numeric_prices:
                min_price = min(float(value) for value in numeric_prices)
                if min_price + delta_y <= 0:
                    delta_y = max(delta_y, 1e-6 - min_price)

            updated = {
                "entry": float(state.get("entry", 0.0)) + delta_y,
                "stop_loss": float(state.get("stop_loss", 0.0)) + delta_y,
                "take_profit": float(state.get("take_profit", 0.0)) + delta_y,
                "anchor_x": float(state.get("anchor_x", 0.0)) + delta_x if state.get("anchor_x") is not None else None,
                "x_start": float(state.get("x_start", 0.0)) + delta_x if state.get("x_start") is not None else None,
                "x_end": float(state.get("x_end", 0.0)) + delta_x if state.get("x_end") is not None else None,
                "side": str(state.get("side") or "buy"),
            }
            self._trade_overlay_state.update(
                {
                    "anchor_x": updated["anchor_x"],
                    "x_start": updated["x_start"],
                    "x_end": updated["x_end"],
                }
            )
            self.set_trade_overlay(
                entry=updated["entry"],
                stop_loss=updated["stop_loss"],
                take_profit=updated["take_profit"],
                side=updated["side"],
            )
            return True
        return False

    def _finish_annotation_drag(self):
        drag = getattr(self, "_annotation_drag_state", None)
        self._annotation_drag_state = None
        self._update_chart_interaction_cursor()
        if not isinstance(drag, dict) or not drag.get("moved"):
            return False
        if drag.get("kind") == "trade_overlay":
            state = dict(getattr(self, "_trade_overlay_state", {}) or {})
            self._emit_trade_level_changed("entry", state.get("entry"))
            self._emit_trade_level_changed("stop_loss", state.get("stop_loss"))
            self._emit_trade_level_changed("take_profit", state.get("take_profit"))
        return True

    def _place_trade_projection(self, side: str, point):
        if point is None:
            return
        entry, stop_loss, take_profit = self._default_trade_levels_for_entry(float(point["y"]), side=side)
        x_start, x_end = self._default_trade_overlay_window(anchor_x=point["x"])
        self._trade_overlay_state.update(
            {
                "anchor_x": float(point["x"]),
                "x_start": x_start,
                "x_end": x_end,
            }
        )
        self.set_trade_overlay(entry=entry, stop_loss=stop_loss, take_profit=take_profit, side=side)
        self._select_trade_overlay()
        label = "Short" if str(side or "").strip().lower() == "sell" else "Long"
        self._show_chart_interaction_notice(
            f"{label} target view placed.",
            "Drag the target card to reposition the setup, or drag SL/TP/Entry lines for fine control.",
            auto_clear_ms=1600,
        )

    def _handle_chart_tool_click(self, point):
        tool = str(getattr(self, "_active_chart_tool", "") or "").strip().lower()
        if not tool or point is None:
            return False
        if tool == "long_rr":
            self._place_trade_projection("buy", point)
            return True
        if tool == "short_rr":
            self._place_trade_projection("sell", point)
            return True
        if self._drawing_anchor is None:
            self._drawing_anchor = {"x": float(point["x"]), "y": float(point["y"])}
            self._clear_drawing_preview()
            self._drawing_preview = self._create_segment_drawing(tool, preview=True)
            self._update_segment_drawing(self._drawing_preview, self._drawing_anchor, point)
            return True

        self._commit_chart_drawing(tool, self._drawing_anchor, point)
        self._drawing_anchor = None
        self._clear_drawing_preview()
        return True

    def _nearest_news_event(self, x_value, y_value):
        events = list(self._visible_news_events or [])
        if not events:
            return None

        try:
            x_range, y_range = self.price_plot.viewRange()
        except Exception:
            return None

        x_span = abs(float(x_range[1]) - float(x_range[0])) if len(x_range) >= 2 else 0.0
        y_span = abs(float(y_range[1]) - float(y_range[0])) if len(y_range) >= 2 else 0.0
        x_threshold = max(x_span * 0.02, 60.0)
        y_threshold = max(y_span * 0.06, 1e-6)

        closest = None
        closest_score = None
        for event in events:
            dx = abs(float(event.get("x", 0.0)) - float(x_value))
            dy = abs(float(event.get("y", 0.0)) - float(y_value))
            if dx > x_threshold or dy > y_threshold:
                continue
            score = dx + (dy * 0.5)
            if closest is None or score < closest_score:
                closest = event
                closest_score = score
        return closest

    def eventFilter(self, watched, event):
        scene = getattr(self.price_plot, "scene", lambda: None)()
        viewport = getattr(self.price_plot, "viewport", lambda: None)()
        if watched is scene:
            event_type = event.type()
            if event_type == QtCore.QEvent.Type.GraphicsSceneMousePress:
                if event.button() == QtCore.Qt.MouseButton.LeftButton and self._drawing_anchor is None:
                    point = self._chart_point_from_scene_pos(event.scenePos())
                    hit = self._annotation_hit_test(event.scenePos(), point)
                    if hit is not None:
                        self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
                        self._select_annotation(hit)
                        if self._begin_annotation_drag(hit, point):
                            self._suppress_next_mouse_clicked = True
                            event.accept()
                            return True
            elif event_type == QtCore.QEvent.Type.GraphicsSceneMouseMove:
                if self._annotation_drag_state is not None:
                    point = self._chart_point_from_scene_pos(event.scenePos())
                    if point is not None:
                        self._update_annotation_drag(point)
                    event.accept()
                    return True
            elif event_type == QtCore.QEvent.Type.GraphicsSceneMouseRelease:
                if self._annotation_drag_state is not None:
                    point = self._chart_point_from_scene_pos(event.scenePos())
                    if point is not None:
                        self._update_annotation_drag(point)
                    self._finish_annotation_drag()
                    self._suppress_next_mouse_clicked = True
                    event.accept()
                    return True
        if watched is viewport:
            event_type = event.type()
            if event_type == QtCore.QEvent.Type.Wheel:
                delta = 0
                try:
                    delta = int(event.angleDelta().y() or event.angleDelta().x())
                except Exception:
                    delta = 0
                if delta == 0:
                    return super().eventFilter(watched, event)
                try:
                    scene_pos = self.price_plot.mapToScene(event.position().toPoint())
                except Exception:
                    scene_pos = None
                point = self._chart_point_from_scene_pos(scene_pos)
                steps = max(abs(float(delta)) / 120.0, 1.0)
                if bool(event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier):
                    pan_step = 0.16 * steps
                    self._pan_chart(-pan_step if delta > 0 else pan_step)
                else:
                    zoom_scale = (0.84 ** steps) if delta > 0 else (1.19 ** steps)
                    self._zoom_chart_at(point["x"] if point is not None else None, zoom_scale)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        allowed_modifiers = {
            QtCore.Qt.KeyboardModifier.NoModifier,
            QtCore.Qt.KeyboardModifier.ShiftModifier,
        }
        if modifiers not in allowed_modifiers:
            super().keyPressEvent(event)
            return

        if event.key() in (QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace):
            if self._remove_selected_annotation():
                event.accept()
                return
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self._drawing_anchor is not None:
                self._drawing_anchor = None
                self._clear_drawing_preview()
                self._show_chart_interaction_notice("Drawing preview cancelled.", auto_clear_ms=900)
                self._update_chart_interaction_cursor()
                event.accept()
                return
            if self._active_chart_tool is not None:
                self._set_active_chart_tool(None)
                self._show_chart_interaction_notice("Chart tool disarmed.", auto_clear_ms=900)
                event.accept()
                return
            if self._selected_annotation is not None:
                self._select_annotation(None)
                self._show_chart_interaction_notice("Selection cleared.", auto_clear_ms=900)
                event.accept()
                return
        if event.key() == QtCore.Qt.Key.Key_F:
            self._fit_recent_chart()
            self._show_chart_interaction_notice("Chart fit to recent move.", auto_clear_ms=900)
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_V:
            self.set_volume_panel_visible(not self.show_volume_panel)
            self._show_chart_interaction_notice(
                "Volume pane shown." if self.show_volume_panel else "Volume pane hidden.",
                auto_clear_ms=900,
            )
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Left:
            self._pan_chart(-0.18)
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Right:
            self._pan_chart(0.18)
            event.accept()
            return
        if event.key() in (QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Equal):
            self._zoom_chart(0.72)
            event.accept()
            return
        if event.key() in (QtCore.Qt.Key.Key_Minus, QtCore.Qt.Key.Key_Underscore):
            self._zoom_chart(1.35)
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Comma:
            self._cycle_timeframe(-1)
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Period:
            self._cycle_timeframe(1)
            event.accept()
            return

        tool_name = None
        tool_label = ""
        tool_map = self._chart_tool_shortcuts()
        text = str(event.text() or "").strip().lower()
        if text in tool_map:
            tool_name, tool_label = tool_map[text]
        if tool_name:
            if self._active_chart_tool == tool_name:
                self._set_active_chart_tool(None)
                self._show_chart_interaction_notice(f"{tool_label} tool disarmed.", auto_clear_ms=900)
            else:
                self._set_active_chart_tool(tool_name)
                detail = (
                    "Click a price level to drop a target view."
                    if tool_name in {"long_rr", "short_rr"}
                    else "Click once to anchor and again to place the drawing."
                )
                self._show_chart_interaction_notice(f"{tool_label} tool armed.", detail, auto_clear_ms=1400)
            event.accept()
            return
        super().keyPressEvent(event)

    def _news_hover_html(self, event):
        headline = str(event.get("headline") or "News event")
        source = str(event.get("source") or "News Feed")
        summary = str(event.get("summary") or "").strip()
        impact = str(event.get("impact") or "-")
        sentiment = str(event.get("sentiment") or "-")
        time_text = str(event.get("time") or "")
        summary_html = ""
        if summary:
            trimmed = summary[:180] + ("..." if len(summary) > 180 else "")
            summary_html = (
                f"<div style='color: #d7e8ff; font-size: 10px; margin-top: 3px;'>"
                f"{html.escape(trimmed)}</div>"
            )
        return (
            "<div style='padding: 6px 8px;'>"
            f"<div style='color: #ffd166; font-size: 10px; font-weight: 700;'>{html.escape(source)} | {html.escape(time_text)}</div>"
            f"<div style='color: #f8fbff; font-size: 11px; font-weight: 700; margin-top: 2px;'>{html.escape(headline)}</div>"
            f"{summary_html}"
            f"<div style='color: #9ec1ff; font-size: 10px; margin-top: 3px;'>Impact {html.escape(impact)} | Sentiment {html.escape(sentiment)}</div>"
            "</div>"
        )

    def _mouse_clicked(self, event):
        self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        try:
            self.sigActivated.emit(self)
        except Exception:
            pass
        if self._suppress_next_mouse_clicked:
            self._suppress_next_mouse_clicked = False
            try:
                event.accept()
            except Exception:
                pass
            return
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            if self._drawing_anchor is not None:
                self._drawing_anchor = None
                self._clear_drawing_preview()
                try:
                    event.accept()
                except Exception:
                    pass
                return
            hit = self._annotation_hit_test(event.scenePos(), self._chart_point_from_scene_pos(event.scenePos()))
            if hit is not None:
                self._select_annotation(hit)
                self._show_annotation_context_menu(event, hit)
                return
            self._show_trade_context_menu(event)
            return
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            point = self._chart_point_from_scene_pos(event.scenePos())
            if self._handle_chart_tool_click(point):
                try:
                    event.accept()
                except Exception:
                    pass
                return
            if self._selected_annotation is not None and self._annotation_hit_test(event.scenePos(), point) is None:
                self._select_annotation(None)
        try:
            is_double = bool(event.double())
        except Exception:
            is_double = False
        if not is_double:
            return
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        pos = event.scenePos()
        if not self.price_plot.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.price_plot.getPlotItem().vb.mapSceneToView(pos)
        price = float(mouse_point.y())
        if not np.isfinite(price) or price <= 0:
            return

        self.sigTradeLevelRequested.emit(
            {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "price": price,
                "x": float(mouse_point.x()),
            }
        )
        try:
            event.accept()
        except Exception:
            pass

    def _show_annotation_context_menu(self, event, annotation):
        if not isinstance(annotation, dict):
            return
        menu = QMenu(self)
        remove_action = menu.addAction(f"Remove {self._annotation_display_name(annotation)}")
        chosen = menu.exec(event.screenPos().toPoint())
        if chosen is not remove_action:
            return
        if self._remove_selected_annotation():
            try:
                event.accept()
            except Exception:
                pass

    def _show_trade_context_menu(self, event):
        pos = event.scenePos()
        if not self.price_plot.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.price_plot.getPlotItem().vb.mapSceneToView(pos)
        price = float(mouse_point.y())
        if not np.isfinite(price) or price <= 0:
            return

        menu = QMenu(self)
        buy_limit = menu.addAction("Buy Limit Here")
        sell_limit = menu.addAction("Sell Limit Here")
        menu.addSeparator()
        set_entry = menu.addAction("Set Entry Here")
        set_stop = menu.addAction("Set Stop Loss Here")
        set_take = menu.addAction("Set Take Profit Here")
        menu.addSeparator()
        clear_levels = menu.addAction("Clear Trade Levels")
        chosen = menu.exec(event.screenPos().toPoint())
        if chosen is None:
            return

        mapping = {
            buy_limit: "buy_limit",
            sell_limit: "sell_limit",
            set_entry: "set_entry",
            set_stop: "set_stop_loss",
            set_take: "set_take_profit",
            clear_levels: "clear_levels",
        }
        action_name = mapping.get(chosen)
        if not action_name:
            return

        self.sigTradeContextAction.emit(
            {
                "action": action_name,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "price": price,
            }
        )
        try:
            event.accept()
        except Exception:
            pass

    def _active_broker_name(self):
        broker = getattr(self.controller, "broker", None)
        if broker is not None:
            name = getattr(broker, "exchange_name", None)
            if name:
                return str(name)

        config = getattr(self.controller, "config", None)
        broker_config = getattr(config, "broker", None)
        if broker_config is not None:
            exchange = getattr(broker_config, "exchange", None)
            if exchange:
                return str(exchange)

        return "Broker"

    def _symbol_parts(self):
        if "/" not in str(self.symbol):
            return str(self.symbol).upper(), ""
        base, quote = str(self.symbol).upper().split("/", 1)
        return base, quote

    def _timeframe_description(self):
        mapping = {
            "1m": "1 minute chart",
            "5m": "5 minute chart",
            "15m": "15 minute chart",
            "30m": "30 minute chart",
            "1h": "1 hour chart",
            "4h": "4 hour chart",
            "1d": "1 day chart",
            "1w": "1 week chart",
            "1mn": "1 month chart",
        }
        return mapping.get(str(self.timeframe).lower(), f"{self.timeframe} chart")

    def _handle_timeframe_picker_changed(self, value):
        if self._timeframe_picker_updating:
            return
        self.set_timeframe(value, emit_signal=True)

    def set_timeframe(self, timeframe, emit_signal=False):
        normalized = str(timeframe or self.timeframe or "1h").strip().lower() or "1h"
        previous = str(getattr(self, "timeframe", "") or "").strip().lower()
        self.timeframe = normalized

        picker = getattr(self, "timeframe_picker", None)
        if picker is not None:
            if picker.findText(normalized) < 0:
                picker.addItem(normalized)
            self._timeframe_picker_updating = True
            try:
                picker.setCurrentText(normalized)
            finally:
                self._timeframe_picker_updating = False

        if previous != normalized:
            self.refresh_context_display()
            if emit_signal:
                self.sigTimeframeSelected.emit(normalized)

    def _update_chart_header(self):
        base, quote = self._symbol_parts()
        broker_name = self._active_broker_name().upper()
        self.instrument_label.setText(f"{self.symbol.upper()}  {self.timeframe.upper()}")

        stats = self._last_candle_stats or {}
        if quote:
            description = f"{broker_name} DESK  |  {base} quoted in {quote}"
        else:
            description = f"{broker_name} DESK  |  {self._timeframe_description()}"

        bid = self._format_numeric_value(self._last_bid)
        ask = self._format_numeric_value(self._last_ask)
        mid = ((bid + ask) / 2.0) if bid is not None and ask is not None else None
        spread = None
        if bid is not None and ask is not None and ask >= bid:
            spread = ask - bid

        if stats:
            last_price = self._format_metric(stats.get("last_price", 0.0))
            variation = float(stats.get("variation_pct", 0.0))
            cumulative_volume = self._format_volume(stats.get("cumulative_volume", 0.0))
            positive = variation >= 0
            change_color = "#2db784" if positive else "#d75462"
            prefix = "+" if positive else ""
            self.market_stats_label.setText(f"{last_price}  {prefix}{variation:.2f}%")
            self.market_stats_label.setStyleSheet(
                f"color: {change_color}; font-weight: 800; font-size: 15px;"
            )
            self.market_meta_label.setText(
                f"{description}  |  Avg close {self._format_metric(stats.get('average_close', 0.0))}  |  "
                f"Visible range {self._format_metric(stats.get('min_price', 0.0), 4)} - {self._format_metric(stats.get('max_price', 0.0), 4)}"
            )
            self.market_micro_label.setText(
                f"Bid {self._format_metric(bid, 8)}  |  Ask {self._format_metric(ask, 8)}  |  "
                f"Mid {self._format_metric(mid, 8)}  |  Spread {self._format_metric(spread, 8)}  |  Visible Vol {cumulative_volume}"
            )
        else:
            self.market_stats_label.setText(self._timeframe_description())
            self.market_stats_label.setStyleSheet("color: #8e9bab; font-weight: 700; font-size: 14px;")
            self.market_meta_label.setText(description)
            self.market_micro_label.setText(
                f"Bid {self._format_metric(bid, 8)}  |  Ask {self._format_metric(ask, 8)}  |  Mid {self._format_metric(mid, 8)}  |  Spread {self._format_metric(spread, 8)}"
            )

    def _update_watermark_html(self):
        base, quote = self._symbol_parts()
        description = f"{base} / {quote}" if quote else base
        symbol_color = self._rgba_css(self.axis_color, 22, "#f6f8fb")
        timeframe_color = self._rgba_css(self.axis_color, 32, "#9aa4b2")
        detail_color = self._rgba_css(self.grid_color, 40, "#728198")
        self.watermark_item.setHtml(
            (
                "<div style='text-align:center;'>"
                f"<div style='color: {symbol_color}; font-size: 40px; font-weight: 800; letter-spacing: 1px;'>{self.symbol.upper()}</div>"
                f"<div style='color: {timeframe_color}; font-size: 22px; font-weight: 700;'>{self.timeframe.upper()}</div>"
                f"<div style='color: {detail_color}; font-size: 11px; text-transform: uppercase;'>{description}</div>"
                "</div>"
            )
        )

    def refresh_context_display(self):
        self._update_chart_header()
        self._refresh_market_panels()
        self._update_watermark_html()
        self._update_watermark_position()
        self._update_status_overlay_position()
        self._update_chart_overlays()

    def _refresh_market_panels(self):
        self._update_depth_chart()
        self._update_market_info()

    def _update_depth_chart(self):
        bids = []
        asks = []
        for level in self._last_orderbook_bids or []:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                price = self._format_numeric_value(level[0])
                size = self._format_numeric_value(level[1])
                if price is not None and size is not None and price > 0 and size > 0:
                    bids.append((price, size))
        for level in self._last_orderbook_asks or []:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                price = self._format_numeric_value(level[0])
                size = self._format_numeric_value(level[1])
                if price is not None and size is not None and price > 0 and size > 0:
                    asks.append((price, size))

        if not bids and not asks:
            self.depth_bid_curve.setData([], [])
            self.depth_ask_curve.setData([], [])
            return

        if bids:
            bids = sorted(bids, key=lambda item: item[0], reverse=True)
            bid_prices = np.array([price for price, _size in bids], dtype=float)
            bid_sizes = np.cumsum(np.array([size for _price, size in bids], dtype=float))
            self.depth_bid_curve.setData(bid_prices, bid_sizes)
        else:
            self.depth_bid_curve.setData([], [])

        if asks:
            asks = sorted(asks, key=lambda item: item[0])
            ask_prices = np.array([price for price, _size in asks], dtype=float)
            ask_sizes = np.cumsum(np.array([size for _price, size in asks], dtype=float))
            self.depth_ask_curve.setData(ask_prices, ask_sizes)
        else:
            self.depth_ask_curve.setData([], [])

        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None
        spread_text = "-"
        if best_bid is not None and best_ask is not None and best_ask >= best_bid:
            spread_text = self._format_metric(best_ask - best_bid, 8)
        self.depth_summary_label.setText(
            f"Best bid {self._format_metric(best_bid, 8)} | Best ask {self._format_metric(best_ask, 8)} | Spread {spread_text}"
        )

    def _update_market_info(self):
        stats = self._last_candle_stats or {}
        bid = self._format_numeric_value(self._last_bid)
        ask = self._format_numeric_value(self._last_ask)
        last_price = self._format_numeric_value(stats.get("last_price")) if stats else None
        if last_price is None:
            if bid is not None and ask is not None:
                last_price = (bid + ask) / 2.0
            else:
                last_price = bid or ask

        mid = None
        if bid is not None and ask is not None:
            mid = (bid + ask) / 2.0
        spread = None
        if bid is not None and ask is not None and ask >= bid:
            spread = ask - bid

        bid_depth = sum(max(0.0, self._format_numeric_value(level[1]) or 0.0) for level in self._last_orderbook_bids or [] if isinstance(level, (list, tuple)) and len(level) >= 2)
        ask_depth = sum(max(0.0, self._format_numeric_value(level[1]) or 0.0) for level in self._last_orderbook_asks or [] if isinstance(level, (list, tuple)) and len(level) >= 2)
        depth_bias = None
        total_depth = bid_depth + ask_depth
        if total_depth > 0:
            depth_bias = ((bid_depth - ask_depth) / total_depth) * 100.0

        range_text = "-"
        if stats:
            range_text = (
                f"{self._format_metric(stats.get('min_price'), 6)} - "
                f"{self._format_metric(stats.get('max_price'), 6)}"
            )

        card_values = {
            "Last": self._format_metric(last_price, 8),
            "Mid": self._format_metric(mid, 8),
            "Spread": self._format_metric(spread, 8),
            "Best Bid": self._format_metric(bid, 8),
            "Best Ask": self._format_metric(ask, 8),
            "Range": range_text,
            "Visible Vol": self._format_volume(stats.get("cumulative_volume", 0.0)) if stats else "-",
            "Depth Bias": "-" if depth_bias is None else f"{depth_bias:+.2f}%",
        }
        for key, value_label in self.market_info_cards.items():
            value_label.setText(card_values.get(key, "-"))

        base, quote = self._symbol_parts()
        headline = f"Desk view: {self.symbol.upper()} | {self._active_broker_name().upper()} | {self.timeframe.upper()}"
        if stats and stats.get("variation_pct") is not None:
            headline += f" | Visible move {float(stats.get('variation_pct') or 0.0):+.2f}%"
        if spread is not None:
            headline += f" | Spread {self._format_metric(spread, 8)}"
        if depth_bias is not None:
            headline += f" | Depth bias {depth_bias:+.2f}%"
        self.market_info_summary.setText(headline)

        detail_lines = [
            f"<h3>{self.symbol.upper()}</h3>",
            (
                f"<p><b>Desk context:</b> {base} / {quote if quote else 'quote unavailable'} | "
                f"<b>Broker:</b> {self._active_broker_name().upper()} | "
                f"<b>Timeframe:</b> {self.timeframe.upper()}</p>"
            ),
            (
                f"<p><b>Visible range:</b> {range_text} | "
                f"<b>Average close:</b> {self._format_metric(stats.get('average_close'), 8) if stats else '-'} | "
                f"<b>Visible volume:</b> {self._format_volume(stats.get('cumulative_volume', 0.0)) if stats else '-'}</p>"
            ),
            (
                f"<p><b>Order book:</b> bid depth {self._format_volume(bid_depth)} | "
                f"ask depth {self._format_volume(ask_depth)} | "
                f"spread {self._format_metric(spread, 8)} | "
                f"mid {self._format_metric(mid, 8)}</p>"
            ),
        ]
        if depth_bias is not None:
            tilt = "buyers" if depth_bias > 0 else "sellers" if depth_bias < 0 else "balanced flow"
            detail_lines.append(
                f"<p><b>Depth tilt:</b> {tilt} with a {depth_bias:+.2f}% balance versus the opposing side.</p>"
            )
        self.market_info_details.setHtml("".join(detail_lines))

    def _format_numeric_value(self, value):
        try:
            numeric = float(value)
        except Exception:
            return None
        if not np.isfinite(numeric):
            return None
        return numeric

    def _update_watermark_position(self, *_args):
        try:
            x_range, y_range = self.price_plot.viewRange()
            center_x = (float(x_range[0]) + float(x_range[1])) / 2.0
            center_y = (float(y_range[0]) + float(y_range[1])) / 2.0
            self.watermark_item.setPos(center_x, center_y)
            self._update_status_overlay_position()
            self._watermark_initialized = True
        except Exception:
            return

    def _format_metric(self, value, digits=6):
        try:
            numeric = float(value)
        except Exception:
            return "-"
        if abs(numeric) >= 1000:
            return f"{numeric:,.2f}"
        if abs(numeric) >= 1:
            return f"{numeric:,.{min(digits, 4)}f}"
        return f"{numeric:,.{digits}f}"

    def _format_volume(self, value):
        try:
            numeric = float(value)
        except Exception:
            return "-"
        if numeric >= 1_000_000_000:
            return f"{numeric / 1_000_000_000:.2f}B"
        if numeric >= 1_000_000:
            return f"{numeric / 1_000_000:.2f}M"
        if numeric >= 1_000:
            return f"{numeric / 1_000:.2f}K"
        return f"{numeric:.2f}"

    def _format_time_label(self, value):
        if value in (None, ""):
            return "-"

        try:
            if hasattr(value, "to_pydatetime"):
                dt = value.to_pydatetime()
            elif isinstance(value, datetime):
                dt = value
            elif isinstance(value, (int, float, np.integer, np.floating)):
                numeric = float(value)
                if abs(numeric) > 1e11:
                    numeric = numeric / 1000.0
                dt = datetime.fromtimestamp(numeric, tz=timezone.utc)
            else:
                text = str(value).strip()
                if not text:
                    return "-"
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return str(value)

    def _set_ohlcv_from_row(self, row):
        if row is None:
            self.ohlcv_label.setText("Time -  O -  H -  L -  C -  Chg -  V -")
            self._update_chart_overlays()
            return

        open_price = self._format_numeric_value(row.get("open", 0.0))
        close_price = self._format_numeric_value(row.get("close", 0.0))
        delta = None
        if open_price is not None and close_price is not None:
            delta = close_price - open_price
        prefix = "+" if delta is not None and delta >= 0 else ""
        self.ohlcv_label.setText(
            "  ".join(
                [
                    f"T {self._format_time_label(row.get('timestamp'))}",
                    f"O {self._format_metric(row.get('open', 0.0))}",
                    f"H {self._format_metric(row.get('high', 0.0))}",
                    f"L {self._format_metric(row.get('low', 0.0))}",
                    f"C {self._format_metric(row.get('close', 0.0))}",
                    f"Chg {prefix}{self._format_metric(delta, 6)}",
                    f"V {self._format_volume(row.get('volume', 0.0))}",
                ]
            )
        )
        self._update_chart_overlays()

    def _row_for_x(self, x_value):
        if self._last_df is None or self._last_x is None or len(self._last_x) == 0:
            return None

        try:
            index = int(np.nanargmin(np.abs(self._last_x - float(x_value))))
        except Exception:
            index = len(self._last_df) - 1

        if index < 0 or index >= len(self._last_df):
            return None
        return self._last_df.iloc[index]

    def _hover_html(self, row, y_value):
        if row is None:
            return f"<span style='color:#f6f8fb'>Price {y_value:.6f}</span>"

        open_price = self._format_numeric_value(row.get("open", 0.0))
        close_price = self._format_numeric_value(row.get("close", 0.0))
        delta = None
        if open_price is not None and close_price is not None:
            delta = close_price - open_price
        delta_color = "#2db784" if (delta or 0.0) >= 0 else "#d75462"
        delta_prefix = "+" if delta is not None and delta >= 0 else ""
        return (
            "<div style='padding: 6px 8px;'>"
            f"<div style='color: #9aa4b2; font-size: 10px; font-weight: 700;'>{html.escape(self._format_time_label(row.get('timestamp')))}</div>"
            f"<div style='color: #f6f8fb; font-size: 11px; margin-top: 2px;'>Cursor {y_value:.6f}</div>"
            f"<div style='color: #dde5ef; font-size: 10px; margin-top: 3px;'>"
            f"O {self._format_metric(row.get('open', 0.0))}  "
            f"H {self._format_metric(row.get('high', 0.0))}  "
            f"L {self._format_metric(row.get('low', 0.0))}  "
            f"C {self._format_metric(row.get('close', 0.0))}</div>"
            f"<div style='color: {delta_color}; font-size: 10px; font-weight: 700; margin-top: 3px;'>"
            f"Bar change {delta_prefix}{self._format_metric(delta, 6)}  |  Volume {self._format_volume(row.get('volume', 0.0))}</div>"
            "</div>"
        )

    def _update_ohlcv_for_x(self, x_value):
        self._set_ohlcv_from_row(self._row_for_x(x_value))

    def _extract_time_axis(self, df):
        if "timestamp" not in df.columns:
            return np.arange(len(df), dtype=float)

        ts = df["timestamp"]

        try:
            import pandas as pd

            # Numeric epoch input
            if pd.api.types.is_numeric_dtype(ts):
                x = pd.to_numeric(ts, errors="coerce").to_numpy(dtype=float)
                if len(x) > 0:
                    median = np.nanmedian(np.abs(x))
                    if median > 1e11:  # likely milliseconds
                        x = x / 1000.0
                return x

            dt = pd.to_datetime(ts, errors="coerce", utc=True)
            valid_mask = (~dt.isna()).to_numpy(dtype=bool)
            if not valid_mask.any():
                return np.arange(len(df), dtype=float)

            # Normalize to nanosecond precision before converting to epoch seconds.
            # Pandas may otherwise keep second-based datetime units, which would turn
            # valid epoch timestamps such as 1700000000 into 1.7 after / 1e9.
            x = np.full(len(df), np.nan, dtype=float)
            valid_datetimes = dt.loc[valid_mask].astype("datetime64[ns, UTC]")
            x[valid_mask] = valid_datetimes.astype("int64").to_numpy(dtype=float) / 1e9
            if np.isnan(x).all():
                return np.arange(len(df), dtype=float)
            return x
        except Exception:
            return np.arange(len(df), dtype=float)

    def _timeframe_seconds(self, timeframe=None):
        normalized = str(timeframe or self.timeframe or "").strip().lower()
        mapping = {
            "tick": 1.0,
            "1m": 60.0,
            "5m": 300.0,
            "15m": 900.0,
            "30m": 1800.0,
            "1h": 3600.0,
            "4h": 14400.0,
            "1d": 86400.0,
            "1w": 604800.0,
        }
        if normalized in mapping:
            return mapping[normalized]
        match = re.fullmatch(r"(\d+)([mhdw])", normalized)
        if not match:
            return None
        size = float(match.group(1))
        unit = match.group(2)
        multiplier = {"m": 60.0, "h": 3600.0, "d": 86400.0, "w": 604800.0}.get(unit)
        if multiplier is None:
            return None
        return size * multiplier

    def _normalize_chart_time_axis(self, x_values):
        x = np.asarray(x_values, dtype=float)
        if len(x) < 2:
            return x

        finite_mask = np.isfinite(x)
        if not finite_mask.all():
            x = x[finite_mask]
        if len(x) < 2:
            return x

        if str(self.timeframe or "").strip().lower() == "tick":
            return x

        expected_step = self._timeframe_seconds()
        if expected_step is None or expected_step <= 0:
            return x

        diffs = np.diff(x)
        diffs = diffs[np.isfinite(diffs)]
        diffs = diffs[diffs > 0]
        if len(diffs) == 0:
            return x

        median_step = float(np.median(diffs))
        max_gap = float(np.max(diffs))
        min_gap = float(np.min(diffs))
        irregular_spacing = (
            median_step > (expected_step * 1.5)
            or median_step < (expected_step * 0.5)
            or max_gap > (expected_step * 4.0)
            or (max_gap / max(min_gap, 1e-9)) > 6.0
        )
        if not irregular_spacing:
            return x

        anchor = float(x[-1])
        start = anchor - (expected_step * (len(x) - 1))
        return np.linspace(start, anchor, num=len(x), dtype=float)

    def _infer_candle_width(self, x):
        expected_step = self._timeframe_seconds()
        if len(x) < 2:
            if expected_step is not None and expected_step > 0:
                return max(expected_step * 0.64, 1e-6)
            return 60.0

        diffs = np.diff(x)
        diffs = diffs[np.isfinite(diffs)]
        diffs = diffs[np.abs(diffs) > 0]
        if len(diffs) == 0:
            if expected_step is not None and expected_step > 0:
                return max(expected_step * 0.64, 1e-6)
            return 60.0

        step = float(np.median(np.abs(diffs)))
        if expected_step is not None and expected_step > 0:
            step = min(step, float(expected_step))
        return max(min(step * 0.64, step * 0.8), 1e-6)

    def _resolve_signal_x(self, index):
        try:
            numeric = float(index)
        except Exception:
            numeric = None

        if numeric is not None and np.isfinite(numeric):
            if self._last_x is not None and len(self._last_x) > 0:
                rounded = int(round(numeric))
                if abs(numeric - rounded) <= 1e-6 and 0 <= rounded < len(self._last_x):
                    return float(self._last_x[rounded])
            return numeric

        timestamp_text = str(index or "").strip()
        if not timestamp_text:
            return None

        try:
            import pandas as pd

            parsed = pd.to_datetime(timestamp_text, errors="coerce", utc=True)
            if pd.isna(parsed):
                return None
            return float(parsed.timestamp())
        except Exception:
            return None

    def update_orderbook_heatmap(self, bids, asks):
        self._last_orderbook_bids = list(bids or [])
        self._last_orderbook_asks = list(asks or [])
        self._refresh_market_panels()
        if not bids and not asks:
            return

        parsed_levels = []
        for level in (bids or [])[: self.max_heatmap_levels]:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                try:
                    price = float(level[0])
                    volume = float(level[1])
                    if np.isfinite(price) and np.isfinite(volume) and volume > 0:
                        parsed_levels.append((price, volume))
                except Exception:
                    continue

        for level in (asks or [])[: self.max_heatmap_levels]:
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                try:
                    price = float(level[0])
                    volume = float(level[1])
                    if np.isfinite(price) and np.isfinite(volume) and volume > 0:
                        parsed_levels.append((price, volume))
                except Exception:
                    continue

        if not parsed_levels:
            return

        prices = np.array([price for price, _volume in parsed_levels], dtype=float)
        volumes = np.array([volume for _price, volume in parsed_levels], dtype=float)

        price_min = float(np.min(prices))
        price_max = float(np.max(prices))

        last_close = None
        if self._last_df is not None and not self._last_df.empty and "close" in self._last_df.columns:
            try:
                last_close = float(self._last_df["close"].iloc[-1])
            except Exception:
                last_close = None

        raw_span = max(price_max - price_min, 1e-9)
        anchor_price = last_close if last_close is not None and np.isfinite(last_close) else float(np.mean(prices))
        padding = max(raw_span * 0.2, abs(anchor_price) * 0.0015, 1e-6)
        grid_min = min(price_min, anchor_price - padding)
        grid_max = max(price_max, anchor_price + padding)

        previous_range = self._last_heatmap_price_range
        if previous_range is not None:
            prev_min, prev_max = previous_range
            grid_min = min(grid_min, float(prev_min))
            grid_max = max(grid_max, float(prev_max))
        self._last_heatmap_price_range = (grid_min, grid_max)

        if not np.isfinite(grid_min) or not np.isfinite(grid_max) or grid_max <= grid_min:
            return

        price_axis = np.linspace(grid_min, grid_max, self.max_heatmap_levels)
        column = np.zeros(self.max_heatmap_levels, dtype=float)
        for price, volume in parsed_levels:
            index = int(np.searchsorted(price_axis, price, side="left"))
            index = max(0, min(self.max_heatmap_levels - 1, index))
            column[index] += volume

        column_max = float(np.max(column))
        if column_max > 0:
            column /= column_max

        self.heatmap_buffer.append(column)
        if len(self.heatmap_buffer) > self.max_heatmap_rows:
            self.heatmap_buffer.pop(0)

        matrix = np.array(self.heatmap_buffer, dtype=float).T
        if matrix.size == 0:
            return

        matrix_max = float(np.nanmax(matrix))
        if matrix_max > 0:
            matrix = matrix / matrix_max

        if self._last_x is not None and len(self._last_x) >= 2:
            diffs = np.diff(self._last_x)
            diffs = diffs[np.isfinite(diffs)]
            diffs = diffs[np.abs(diffs) > 0]
            step = float(np.median(np.abs(diffs))) if len(diffs) else 60.0
            x_end = float(self._last_x[-1]) + (step * 0.5)
        elif self._last_x is not None and len(self._last_x) == 1:
            step = 60.0
            x_end = float(self._last_x[-1]) + (step * 0.5)
        else:
            step = 1.0
            x_end = float(matrix.shape[1])

        x_start = x_end - (step * matrix.shape[1])
        rect = QtCore.QRectF(
            x_start,
            grid_min,
            max(step * matrix.shape[1], 1e-6),
            max(grid_max - grid_min, 1e-9),
        )

        self.heatmap_image.setImage(np.flipud(matrix), autoLevels=False, levels=(0.0, 1.0))
        self.heatmap_image.setRect(rect)
        self.heatmap_plot.setYRange(grid_min, grid_max, padding=0.02)

    def add_strategy_signal(self, index, price, signal):
        x_value = self._resolve_signal_x(index)
        try:
            y_value = float(price)
        except Exception:
            return

        if x_value is None or not np.isfinite(y_value):
            return

        normalized_signal = str(signal or "").strip().upper()
        if normalized_signal == "BUY":
            self.signal_markers.addPoints(x=[x_value], y=[y_value], symbol="t1", brush="#26a69a", size=12)
        elif normalized_signal == "SELL":
            self.signal_markers.addPoints(x=[x_value], y=[y_value], symbol="t", brush="#ef5350", size=12)

    def clear_news_events(self):
        self._news_events = []
        self._visible_news_events = []
        self.news_markers.setData([], [])
        self.news_hover_item.setVisible(False)
        for item in list(self._news_items):
            try:
                self.price_plot.removeItem(item)
            except Exception:
                pass
        self._news_items = []

    def set_news_events(self, events):
        self._news_events = list(events or [])
        self._render_news_events()

    def _render_news_events(self):
        self.news_markers.setData([], [])
        self.news_hover_item.setVisible(False)
        self._visible_news_events = []
        for item in list(self._news_items):
            try:
                self.price_plot.removeItem(item)
            except Exception:
                pass
        self._news_items = []

        if self._last_x is None or self._last_df is None or len(self._last_x) == 0 or not self._news_events:
            return

        try:
            high_values = self._last_df["high"].astype(float).to_numpy()
            price_anchor = float(np.nanmax(high_values))
            low_anchor = float(np.nanmin(self._last_df["low"].astype(float).to_numpy()))
        except Exception:
            return

        visible_min = float(np.nanmin(self._last_x))
        visible_max = float(np.nanmax(self._last_x))
        price_span = max(price_anchor - low_anchor, 1e-6)
        marker_y = price_anchor + (price_span * 0.03)

        xs = []
        ys = []
        tooltips = []
        visible_events = []

        for event in self._news_events[:12]:
            timestamp_text = str(event.get("timestamp", "") or "")
            try:
                event_dt = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            except Exception:
                continue
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            x_value = float(event_dt.timestamp())
            if x_value < visible_min or x_value > visible_max:
                continue
            xs.append(x_value)
            ys.append(marker_y)
            headline = str(event.get("title", "") or "News event")
            source = str(event.get("source", "") or "News Feed")
            summary = str(event.get("summary", "") or "").strip()
            impact = event.get("impact", "")
            sentiment = event.get("sentiment_score", "")
            timestamp_label = event_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            tooltip_parts = [f"{source} | {timestamp_label}", headline]
            if summary:
                tooltip_parts.append(summary)
            if impact not in ("", None) or sentiment not in ("", None):
                tooltip_parts.append(f"Impact {impact} | Sentiment {sentiment}")
            tooltips.append("\n".join(str(part) for part in tooltip_parts if str(part).strip()))
            visible_events.append(
                {
                    "x": x_value,
                    "y": marker_y,
                    "headline": headline,
                    "source": source,
                    "time": timestamp_label,
                    "summary": summary,
                    "impact": impact,
                    "sentiment": sentiment,
                }
            )

        if not xs:
            return

        self.news_markers.setData(
            x=xs,
            y=ys,
            symbol="d",
            size=9,
            brush=pg.mkBrush("#ffd166"),
            pen=mkPen("#f4a261", width=1.1),
            data=tooltips,
        )
        self._visible_news_events = visible_events

        for event in visible_events[:5]:
            x_value = float(event["x"])
            line = InfiniteLine(
                pos=x_value,
                angle=90,
                movable=False,
                pen=mkPen((244, 162, 97, 70), width=1, style=QtCore.Qt.PenStyle.DotLine),
            )
            self.price_plot.addItem(line, ignoreBounds=True)
            self._news_items.append(line)

            label = TextItem(
                html=(
                    "<div style='background-color: rgba(11,18,32,0.92); color: #f8fbff; "
                    "padding: 4px 7px; border: 1px solid rgba(244,162,97,0.55); border-radius: 6px;'>"
                    f"<div style='color: #ffd166; font-size: 10px; font-weight: 700;'>{event['source']} | {event['time']}</div>"
                    f"<div style='color: #f8fbff; font-size: 11px; font-weight: 600;'>{event['headline'][:68]}{'...' if len(event['headline']) > 68 else ''}</div>"
                    f"<div style='color: #9ec1ff; font-size: 10px;'>Impact {event['impact']} | Sentiment {event['sentiment']}</div>"
                    "</div>"
                ),
                anchor=(0.0, 1.0),
                border=None,
                fill=None,
            )
            label.setPos(x_value, marker_y)
            self.price_plot.addItem(label)
            self._news_items.append(label)

    def _pivot_window(self, period: int) -> int:
        return max(2, int(period) // 2)

    def _build_fractal_points(self, high, low, x, period: int):
        window = self._pivot_window(period)
        upper_x = []
        upper_y = []
        lower_x = []
        lower_y = []

        for index in range(window, len(x) - window):
            high_slice = high.iloc[index - window: index + window + 1]
            low_slice = low.iloc[index - window: index + window + 1]

            current_high = float(high.iloc[index])
            current_low = float(low.iloc[index])

            if np.isfinite(current_high) and current_high >= float(high_slice.max()):
                upper_x.append(float(x[index]))
                upper_y.append(current_high)

            if np.isfinite(current_low) and current_low <= float(low_slice.min()):
                lower_x.append(float(x[index]))
                lower_y.append(current_low)

        return (np.array(upper_x, dtype=float), np.array(upper_y, dtype=float)), (
            np.array(lower_x, dtype=float),
            np.array(lower_y, dtype=float),
        )

    def _build_zigzag_points(self, high, low, x, period: int):
        window = self._pivot_window(period)
        candidates = []

        for index in range(window, len(x) - window):
            high_slice = high.iloc[index - window: index + window + 1]
            low_slice = low.iloc[index - window: index + window + 1]
            current_high = float(high.iloc[index])
            current_low = float(low.iloc[index])

            if np.isfinite(current_high) and current_high >= float(high_slice.max()):
                candidates.append((index, "H", current_high))

            if np.isfinite(current_low) and current_low <= float(low_slice.min()):
                candidates.append((index, "L", current_low))

        if not candidates:
            return np.array([], dtype=float), np.array([], dtype=float)

        candidates.sort(key=lambda item: item[0])
        pivots = []

        for candidate in candidates:
            if not pivots:
                pivots.append(candidate)
                continue

            last_index, last_kind, last_price = pivots[-1]
            current_index, current_kind, current_price = candidate

            if current_kind == last_kind:
                if current_kind == "H" and current_price >= last_price:
                    pivots[-1] = candidate
                elif current_kind == "L" and current_price <= last_price:
                    pivots[-1] = candidate
                continue

            if current_index == last_index:
                more_extreme = (
                    current_kind == "H" and current_price >= last_price
                ) or (
                    current_kind == "L" and current_price <= last_price
                )
                if more_extreme:
                    pivots[-1] = candidate
                continue

            pivots.append(candidate)

        zz_x = np.array([float(x[index]) for index, _kind, _price in pivots], dtype=float)
        zz_y = np.array([float(price) for _index, _kind, price in pivots], dtype=float)
        return zz_x, zz_y

    def _build_fibonacci_overlay(self):
        levels = [
            (0.0, "#90caf9"),
            (0.236, "#4fc3f7"),
            (0.382, "#26a69a"),
            (0.5, "#ffd54f"),
            (0.618, "#ffb74d"),
            (0.786, "#ef5350"),
            (1.0, "#ce93d8"),
        ]
        curves = []
        labels = []
        for ratio, color in levels:
            curve = self._create_curve(
                self.price_plot,
                color,
                1.0 if ratio not in {0.0, 1.0} else 1.2,
                QtCore.Qt.PenStyle.DashLine,
            )
            label = TextItem(
                html="",
                anchor=(1.0, 0.5),
                border=None,
                fill=pg.mkBrush(11, 18, 32, 160),
            )
            self.price_plot.addItem(label)
            curves.append(curve)
            labels.append(label)
        return {"curves": curves, "labels": labels, "levels": levels}

    def set_compact_view_mode(self, enabled: bool):
        self.compact_view_mode = bool(enabled)
        self.default_visible_bars = 60 if self.compact_view_mode else 96

        try:
            self.info_bar.setVisible(not self.compact_view_mode)
        except Exception:
            pass

        try:
            self.market_tabs.setCurrentWidget(self.candlestick_page)
            self.market_tabs.tabBar().setVisible(not self.compact_view_mode)
        except Exception:
            pass

        self._sync_chart_controls_visibility()

        self.splitter.setHandleWidth(6 if self.compact_view_mode else 10)
        self.price_plot.setMinimumHeight(280 if self.compact_view_mode else 460)
        self.volume_plot.setMinimumHeight(64 if self.compact_view_mode else 88)
        self.volume_plot.setMaximumHeight(96 if self.compact_view_mode else 150)
        self.heatmap_plot.setMinimumHeight(60 if self.compact_view_mode else 80)
        self.heatmap_plot.setMaximumHeight(96 if self.compact_view_mode else 135)
        self.depth_plot.setMinimumHeight(220 if self.compact_view_mode else 360)

        self._apply_chart_pane_layout()
        if self._last_candle_stats is not None and self._last_x is not None and len(self._last_x) > 0:
            self._fit_chart_view(self._last_candle_stats, self._infer_candle_width(self._last_x))
            self._update_overlay_positions()
        self.updateGeometry()
        self.repaint()

    def _remove_plot_artifact(self, plot, item):
        if item is None:
            return
        try:
            plot.removeItem(item)
        except Exception:
            pass

    def remove_indicator(self, key: str):
        indicator_key = str(key or "").strip()
        if not indicator_key:
            return False

        indicator_present = any(
            str(spec.get("key") or "").strip() == indicator_key
            for spec in list(self.indicators or [])
            if isinstance(spec, dict)
        )
        pane = self.indicator_panes.pop(indicator_key, None)
        items = self.indicator_items.pop(indicator_key, None)
        if not indicator_present and pane is None and items is None:
            return False

        self.indicators = [
            spec
            for spec in list(self.indicators or [])
            if not isinstance(spec, dict) or str(spec.get("key") or "").strip() != indicator_key
        ]

        if pane is not None:
            try:
                pane.hide()
            except Exception:
                pass
            try:
                pane.setParent(None)
            except Exception:
                pass
            try:
                pane.deleteLater()
            except Exception:
                pass
        elif isinstance(items, dict):
            for artifact in list(items.get("curves", []) or []):
                self._remove_plot_artifact(self.price_plot, artifact)
            for artifact in list(items.get("labels", []) or []):
                self._remove_plot_artifact(self.price_plot, artifact)
        else:
            for artifact in list(items or []):
                self._remove_plot_artifact(self.price_plot, artifact)

        self._apply_chart_pane_layout()
        self.updateGeometry()
        self.repaint()
        return True

    def add_indicator(self, name: str, period: int = 20):
        indicator = (name or "").strip().upper()
        period = max(2, int(period))
        aliases = {
            "MOVING AVERAGE": "SMA",
            "MA": "SMA",
            "EXPONENTIAL MOVING AVERAGE": "EMA",
            "WEIGHTED MOVING AVERAGE": "LWMA",
            "LINEAR WEIGHTED MOVING AVERAGE": "LWMA",
            "WMA": "LWMA",
            "SMOOTHED MOVING AVERAGE": "SMMA",
            "BOLLINGER": "BB",
            "BOLLINGER BANDS": "BB",
            "AVERAGE DIRECTIONAL MOVEMENT INDEX": "ADX",
            "AVERAGE TRUE RANGE": "ATR",
            "PARABOLIC SAR": "SAR",
            "STANDARD DEVIATION": "STDDEV",
            "ACCELERATOR OSCILLATOR": "AC",
            "AWESOME OSCILLATOR": "AO",
            "STOCHASTIC OSCILLATOR": "STOCHASTIC",
            "WILLIAMS' PERCENT RANGE": "WPR",
            "WILLIAMS PERCENT RANGE": "WPR",
            "ACCUMULATION/DISTRIBUTION": "AD",
            "ACCUMULATION DISTRIBUTION": "AD",
            "MONEY FLOW INDEX": "MFI",
            "ON BALANCE VOLUME": "OBV",
            "MARKET FACILITATION INDEX": "BW_MFI",
            "GATOR OSCILLATOR": "GATOR",
            "DONCHIAN CHANNEL": "DONCHIAN",
            "DONCHIAN CHANNELS": "DONCHIAN",
            "KELTNER CHANNEL": "KELTNER",
            "KELTNER CHANNELS": "KELTNER",
            "FIBONACCI": "FIBO",
            "FIBONACCI RETRACEMENT": "FIBO",
            "FIBO": "FIBO",
            "FRACTALS": "FRACTAL",
            "ZIG ZAG": "ZIGZAG",
        }
        indicator = aliases.get(indicator, indicator)

        if indicator in {"SMA", "EMA", "SMMA", "LWMA", "VWAP"}:
            key = f"{indicator}_{period}"
            if key in self.indicator_items:
                return key
            color_map = {
                "SMA": "#ffd54f",
                "EMA": "#80deea",
                "SMMA": "#b39ddb",
                "LWMA": "#ff8a65",
                "VWAP": "#81c784",
            }
            self.indicator_items[key] = [self._create_curve(self.price_plot, color_map.get(indicator, "#ffd54f"), 1.6)]
            self.indicators.append({"type": indicator, "period": period, "key": key})
            return key

        if indicator in {"BB", "ENVELOPES", "DONCHIAN", "KELTNER"}:
            key = f"{indicator}_{period}"
            if key in self.indicator_items:
                return key
            if indicator == "BB":
                items = [
                    self._create_curve(self.price_plot, "#ffb74d", 1.4),
                    self._create_curve(self.price_plot, "#ab47bc", 1.1),
                    self._create_curve(self.price_plot, "#ab47bc", 1.1),
                ]
            elif indicator == "ENVELOPES":
                items = [
                    self._create_curve(self.price_plot, "#90caf9", 1.3),
                    self._create_curve(self.price_plot, "#4fc3f7", 1.0),
                    self._create_curve(self.price_plot, "#4fc3f7", 1.0),
                ]
            elif indicator == "DONCHIAN":
                items = [
                    self._create_curve(self.price_plot, "#64b5f6", 1.1),
                    self._create_curve(self.price_plot, "#90caf9", 1.0, QtCore.Qt.PenStyle.DashLine),
                    self._create_curve(self.price_plot, "#64b5f6", 1.1),
                ]
            else:
                items = [
                    self._create_curve(self.price_plot, "#ffcc80", 1.2),
                    self._create_curve(self.price_plot, "#ce93d8", 1.0),
                    self._create_curve(self.price_plot, "#ce93d8", 1.0),
                ]
            self.indicator_items[key] = items
            self.indicators.append({"type": indicator, "period": period, "key": key})
            return key

        if indicator in {"ICHIMOKU", "ALLIGATOR"}:
            key = indicator
            if key in self.indicator_items:
                return key
            if indicator == "ICHIMOKU":
                items = [
                    self._create_curve(self.price_plot, "#ffca28", 1.2),
                    self._create_curve(self.price_plot, "#42a5f5", 1.2),
                    self._create_curve(self.price_plot, "#66bb6a", 1.0),
                    self._create_curve(self.price_plot, "#ef5350", 1.0),
                    self._create_curve(self.price_plot, "#b39ddb", 1.0),
                ]
            else:
                items = [
                    self._create_curve(self.price_plot, "#42a5f5", 1.3),
                    self._create_curve(self.price_plot, "#ef5350", 1.3),
                    self._create_curve(self.price_plot, "#66bb6a", 1.3),
                ]
            self.indicator_items[key] = items
            self.indicators.append({"type": indicator, "period": period, "key": key})
            return key

        if indicator == "SAR":
            key = "SAR"
            if key in self.indicator_items:
                return key
            scatter = ScatterPlotItem()
            self.price_plot.addItem(scatter)
            self.indicator_items[key] = [scatter]
            self.indicators.append({"type": "SAR", "period": period, "key": key})
            return key

        if indicator == "FRACTAL":
            key = f"FRACTAL_{period}"
            if key in self.indicator_items:
                return key
            upper = ScatterPlotItem()
            lower = ScatterPlotItem()
            self.price_plot.addItem(upper)
            self.price_plot.addItem(lower)
            self.indicator_items[key] = [upper, lower]
            self.indicators.append({"type": "FRACTAL", "period": period, "key": key})
            return key

        if indicator == "ZIGZAG":
            key = f"ZIGZAG_{period}"
            if key in self.indicator_items:
                return key
            curve = self._create_curve(self.price_plot, "#f06292", 1.8)
            self.indicator_items[key] = [curve]
            self.indicators.append({"type": "ZIGZAG", "period": period, "key": key})
            return key

        if indicator == "FIBO":
            key = f"FIBO_{period}"
            if key in self.indicator_items:
                return key
            self.indicator_items[key] = self._build_fibonacci_overlay()
            self.indicators.append({"type": "FIBO", "period": period, "key": key})
            return key

        if indicator == "VOLUMES":
            key = "VOLUMES"
            if key not in self.indicator_items:
                self.indicator_items[key] = []
                self.indicators.append({"type": "VOLUMES", "period": period, "key": key})
            return key

        pane_label_map = {
            "ADX": "ADX",
            "ATR": "ATR",
            "STDDEV": "StdDev",
            "AC": "Accelerator",
            "AO": "Awesome",
            "CCI": "CCI",
            "DEMARKER": "DeMarker",
            "MACD": "MACD",
            "MOMENTUM": "Momentum",
            "OSMA": "OsMA",
            "RSI": "RSI",
            "RVI": "RVI",
            "STOCHASTIC": "Stochastic",
            "WPR": "Williams %R",
            "AD": "A/D",
            "MFI": "Money Flow",
            "OBV": "OBV",
            "BULLS POWER": "Bulls Power",
            "BEARS POWER": "Bears Power",
            "FORCE INDEX": "Force Index",
            "GATOR": "Gator",
            "BW_MFI": "Market Facilitation",
        }
        lower_indicator = indicator
        if lower_indicator in pane_label_map:
            key = f"{lower_indicator}_{period}" if lower_indicator in {
                "ADX",
                "ATR",
                "STDDEV",
                "CCI",
                "DEMARKER",
                "MOMENTUM",
                "RSI",
                "STOCHASTIC",
                "WPR",
                "MFI",
                "FORCE INDEX",
            } else lower_indicator.replace(" ", "_")
            if key in self.indicator_items:
                return key

            pane = self._create_indicator_pane(key, pane_label_map[lower_indicator])
            items = []

            if lower_indicator == "ADX":
                items = [
                    self._create_curve(pane, "#ffd54f", 1.4),
                    self._create_curve(pane, "#26a69a", 1.2),
                    self._create_curve(pane, "#ef5350", 1.2),
                ]
                self._add_reference_line(pane, 20.0)
            elif lower_indicator in {"ATR", "STDDEV", "AD", "MFI", "OBV", "MOMENTUM", "BULLS POWER", "BEARS POWER", "FORCE INDEX"}:
                items = [self._create_curve(pane, "#80deea", 1.5)]
                if lower_indicator in {"BULLS POWER", "BEARS POWER", "FORCE INDEX"}:
                    self._add_reference_line(pane, 0.0)
            elif lower_indicator in {"AC", "AO", "OSMA", "GATOR", "BW_MFI"}:
                items = [self._create_histogram(pane)]
                if lower_indicator == "GATOR":
                    items.append(self._create_histogram(pane))
                self._add_reference_line(pane, 0.0)
            elif lower_indicator == "CCI":
                items = [self._create_curve(pane, "#ffb74d", 1.5)]
                self._add_reference_line(pane, 100.0)
                self._add_reference_line(pane, -100.0)
            elif lower_indicator == "DEMARKER":
                items = [self._create_curve(pane, "#64b5f6", 1.5)]
                self._add_reference_line(pane, 0.3)
                self._add_reference_line(pane, 0.7)
            elif lower_indicator == "MACD":
                items = [
                    self._create_histogram(pane),
                    self._create_curve(pane, "#42a5f5", 1.3),
                    self._create_curve(pane, "#ffca28", 1.1),
                ]
                self._add_reference_line(pane, 0.0)
            elif lower_indicator == "RSI":
                items = [self._create_curve(pane, "#ab47bc", 1.5)]
                self._add_reference_line(pane, 30.0)
                self._add_reference_line(pane, 70.0)
            elif lower_indicator == "RVI":
                items = [
                    self._create_curve(pane, "#4fc3f7", 1.4),
                    self._create_curve(pane, "#ffb74d", 1.1),
                ]
                self._add_reference_line(pane, 0.0)
            elif lower_indicator == "STOCHASTIC":
                items = [
                    self._create_curve(pane, "#66bb6a", 1.4),
                    self._create_curve(pane, "#ef5350", 1.1),
                ]
                self._add_reference_line(pane, 20.0)
                self._add_reference_line(pane, 80.0)
            elif lower_indicator == "WPR":
                items = [self._create_curve(pane, "#90caf9", 1.4)]
                self._add_reference_line(pane, -20.0)
                self._add_reference_line(pane, -80.0)

            self.indicator_items[key] = items
            self.indicators.append({"type": lower_indicator, "period": period, "key": key})
            return key

        return None

    def _update_indicators(self, df, x, width):
        if not self.indicators:
            return

        open_ = df["open"].astype(float)
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)

        for spec in self.indicators:
            ind_type = spec["type"]
            period = spec["period"]
            key = spec["key"]
            items = self.indicator_items.get(key, [])

            if ind_type == "SMA" and items:
                series = sma(close, period).to_numpy()
                items[0].setData(x, series)

            elif ind_type == "EMA" and items:
                series = ema(close, period).to_numpy()
                items[0].setData(x, series)

            elif ind_type == "SMMA" and items:
                series = smma(close, period).to_numpy()
                items[0].setData(x, series)

            elif ind_type == "LWMA" and items:
                series = lwma(close, period).to_numpy()
                items[0].setData(x, series)

            elif ind_type == "VWAP" and items:
                typical_price = (high + low + close) / 3.0
                pv = typical_price * volume
                vwap = pv.rolling(window=period, min_periods=1).sum() / volume.rolling(window=period, min_periods=1).sum().replace(0, np.nan)
                items[0].setData(x, vwap.bfill().fillna(close).to_numpy())

            elif ind_type == "BB" and len(items) == 3:
                mid = close.rolling(window=period, min_periods=1).mean()
                std = close.rolling(window=period, min_periods=1).std().fillna(0.0)
                upper = (mid + 2.0 * std).to_numpy()
                lower = (mid - 2.0 * std).to_numpy()
                items[0].setData(x, mid.to_numpy())
                items[1].setData(x, upper)
                items[2].setData(x, lower)

            elif ind_type == "ENVELOPES" and len(items) == 3:
                mid, upper, lower = envelopes(close, period)
                items[0].setData(x, mid.to_numpy())
                items[1].setData(x, upper.to_numpy())
                items[2].setData(x, lower.to_numpy())

            elif ind_type == "DONCHIAN" and len(items) == 3:
                upper = high.rolling(window=period, min_periods=1).max()
                lower = low.rolling(window=period, min_periods=1).min()
                mid = (upper + lower) / 2.0
                items[0].setData(x, upper.to_numpy())
                items[1].setData(x, mid.to_numpy())
                items[2].setData(x, lower.to_numpy())

            elif ind_type == "KELTNER" and len(items) == 3:
                atr_series = atr(high, low, close, period)
                mid = close.ewm(span=period, adjust=False).mean()
                upper = mid + (2.0 * atr_series)
                lower = mid - (2.0 * atr_series)
                items[0].setData(x, mid.to_numpy())
                items[1].setData(x, upper.to_numpy())
                items[2].setData(x, lower.to_numpy())

            elif ind_type == "ICHIMOKU" and len(items) == 5:
                tenkan, kijun, span_a, span_b, chikou = ichimoku(high, low, close)
                items[0].setData(x, tenkan.to_numpy())
                items[1].setData(x, kijun.to_numpy())
                items[2].setData(x, span_a.to_numpy())
                items[3].setData(x, span_b.to_numpy())
                items[4].setData(x, chikou.to_numpy())

            elif ind_type == "ALLIGATOR" and len(items) == 3:
                jaw, teeth, lips = alligator(high, low)
                items[0].setData(x, jaw.to_numpy())
                items[1].setData(x, teeth.to_numpy())
                items[2].setData(x, lips.to_numpy())

            elif ind_type == "SAR" and items:
                sar = parabolic_sar(high, low)
                items[0].setData(
                    x=np.asarray(x, dtype=float),
                    y=sar.to_numpy(),
                    symbol="o",
                    size=5,
                    brush=pg.mkBrush("#90caf9"),
                    pen=mkPen("#90caf9"),
                )

            elif ind_type == "FRACTAL" and len(items) == 2:
                (upper_x, upper_y), (lower_x, lower_y) = self._build_fractal_points(high, low, x, period)
                items[0].setData(
                    x=upper_x,
                    y=upper_y,
                    symbol="t",
                    size=10,
                    brush="#ef5350",
                    pen=mkPen("#ef5350"),
                )
                items[1].setData(
                    x=lower_x,
                    y=lower_y,
                    symbol="t1",
                    size=10,
                    brush="#26a69a",
                    pen=mkPen("#26a69a"),
                )

            elif ind_type == "ZIGZAG" and items:
                zz_x, zz_y = self._build_zigzag_points(high, low, x, period)
                items[0].setData(zz_x, zz_y)

            elif ind_type == "FIBO" and isinstance(items, dict):
                curves = items.get("curves", [])
                labels = items.get("labels", [])
                levels = items.get("levels", [])
                lookback = min(len(df), max(2, int(period)))
                window_high = high.iloc[-lookback:]
                window_low = low.iloc[-lookback:]
                if len(window_high) == 0 or len(window_low) == 0 or len(x) == 0:
                    continue

                high_value = float(window_high.max())
                low_value = float(window_low.min())
                span = high_value - low_value
                if not np.isfinite(span) or span <= 0:
                    span = max(abs(high_value) * 0.001, 1e-9)

                x_start = float(x[max(0, len(x) - lookback)])
                x_end = float(x[-1])
                label_x = x_end + max(width * 2.0, 1.0)

                for index, (ratio, _color) in enumerate(levels):
                    level_price = high_value - (span * float(ratio))
                    curves[index].setData(
                        np.array([x_start, x_end], dtype=float),
                        np.array([level_price, level_price], dtype=float),
                    )
                    labels[index].setHtml(
                        f"<span style='color:#d7dfeb;font-size:11px;'>"
                        f"{ratio * 100:.1f}%  {level_price:.6f}</span>"
                    )
                    labels[index].setPos(label_x, level_price)

            elif ind_type == "ADX" and len(items) == 3:
                adx_line, plus_di, minus_di = adx(high, low, close, period)
                items[0].setData(x, adx_line.to_numpy())
                items[1].setData(x, plus_di.to_numpy())
                items[2].setData(x, minus_di.to_numpy())

            elif ind_type == "ATR" and items:
                items[0].setData(x, atr(high, low, close, period).to_numpy())

            elif ind_type == "STDDEV" and items:
                items[0].setData(x, standard_deviation(close, period).to_numpy())

            elif ind_type == "AC" and items:
                values = accelerator(high, low).to_numpy()
                brushes = [pg.mkBrush("#26a69a" if index == 0 or values[index] >= values[index - 1] else "#ef5350") for index in range(len(values))]
                self._set_histogram_data(items[0], x, values, width, brushes)

            elif ind_type == "AO" and items:
                values = awesome(high, low).to_numpy()
                brushes = [pg.mkBrush("#26a69a" if index == 0 or values[index] >= values[index - 1] else "#ef5350") for index in range(len(values))]
                self._set_histogram_data(items[0], x, values, width, brushes)

            elif ind_type == "CCI" and items:
                items[0].setData(x, cci(high, low, close, period).to_numpy())

            elif ind_type == "DEMARKER" and items:
                items[0].setData(x, demarker(high, low, period).to_numpy())

            elif ind_type == "MACD" and len(items) == 3:
                macd_line, signal_line, histogram = macd(close)
                brushes = [pg.mkBrush("#26a69a" if value >= 0 else "#ef5350") for value in histogram.to_numpy()]
                self._set_histogram_data(items[0], x, histogram.to_numpy(), width, brushes)
                items[1].setData(x, macd_line.to_numpy())
                items[2].setData(x, signal_line.to_numpy())

            elif ind_type == "MOMENTUM" and items:
                items[0].setData(x, momentum(close, period).to_numpy())

            elif ind_type == "OSMA" and items:
                _macd_line, _signal_line, histogram = macd(close)
                brushes = [pg.mkBrush("#26a69a" if value >= 0 else "#ef5350") for value in histogram.to_numpy()]
                self._set_histogram_data(items[0], x, histogram.to_numpy(), width, brushes)

            elif ind_type == "RSI" and items:
                items[0].setData(x, rsi(close, period).to_numpy())

            elif ind_type == "RVI" and len(items) == 2:
                rvi_line, signal_line = rvi(open_, high, low, close, period)
                items[0].setData(x, rvi_line.to_numpy())
                items[1].setData(x, signal_line.to_numpy())

            elif ind_type == "STOCHASTIC" and len(items) == 2:
                percent_k, percent_d = stochastic(high, low, close, period)
                items[0].setData(x, percent_k.to_numpy())
                items[1].setData(x, percent_d.to_numpy())

            elif ind_type == "WPR" and items:
                items[0].setData(x, williams_r(high, low, close, period).to_numpy())

            elif ind_type == "AD" and items:
                items[0].setData(x, accumulation_distribution(high, low, close, volume).to_numpy())

            elif ind_type == "MFI" and items:
                items[0].setData(x, money_flow_index(high, low, close, volume, period).to_numpy())

            elif ind_type == "OBV" and items:
                items[0].setData(x, obv(close, volume).to_numpy())

            elif ind_type == "BULLS POWER" and items:
                items[0].setData(x, bulls_power(high, close).to_numpy())

            elif ind_type == "BEARS POWER" and items:
                items[0].setData(x, bears_power(low, close).to_numpy())

            elif ind_type == "FORCE INDEX" and items:
                items[0].setData(x, force_index(close, volume, period).to_numpy())

            elif ind_type == "GATOR" and len(items) == 2:
                upper, lower = gator(high, low)
                upper_brushes = [pg.mkBrush("#26a69a" if value >= 0 else "#ef5350") for value in upper.to_numpy()]
                lower_brushes = [pg.mkBrush("#ef5350" if value < 0 else "#26a69a") for value in lower.to_numpy()]
                self._set_histogram_data(items[0], x, upper.to_numpy(), width, upper_brushes)
                self._set_histogram_data(items[1], x, lower.to_numpy(), width, lower_brushes)

            elif ind_type == "BW_MFI" and items:
                values, colors = market_facilitation_index(high, low, volume)
                self._set_histogram_data(items[0], x, values.to_numpy(), width, [pg.mkBrush(color) for color in colors])

            elif ind_type == "VOLUMES":
                continue

    def update_candles(self, df):
        if df is None or len(df) == 0:
            return

        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            return

        frame = df.copy()
        if "timestamp" in frame.columns:
            timestamp_series = frame["timestamp"]
            timestamp_inference = ""
            try:
                non_null_timestamps = timestamp_series.dropna()
                if len(non_null_timestamps) > 0:
                    timestamp_inference = pd.api.types.infer_dtype(non_null_timestamps, skipna=True)
            except Exception:
                timestamp_inference = ""

            if pd.api.types.is_datetime64_any_dtype(timestamp_series) or timestamp_inference in {"datetime", "datetime64", "date"}:
                frame["timestamp"] = pd.to_datetime(timestamp_series, errors="coerce", utc=True)
            else:
                numeric_timestamps = pd.to_numeric(timestamp_series, errors="coerce")
                if int(numeric_timestamps.notna().sum()) >= max(1, len(frame.index) // 2):
                    normalized_seconds = numeric_timestamps.where(
                        numeric_timestamps.abs() <= 1e11,
                        numeric_timestamps / 1000.0,
                    )
                    frame["timestamp"] = pd.to_datetime(normalized_seconds, unit="s", errors="coerce", utc=True)
                else:
                    frame["timestamp"] = pd.to_datetime(timestamp_series, errors="coerce", utc=True)

            min_timestamp = pd.Timestamp("1990-01-01T00:00:00+00:00")
            max_timestamp = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=365 * 5)
            frame = frame[
                frame["timestamp"].isna()
                | ((frame["timestamp"] >= min_timestamp) & (frame["timestamp"] <= max_timestamp))
            ]
        for column in ["open", "high", "low", "close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame.replace([np.inf, -np.inf], np.nan, inplace=True)
        drop_columns = ["open", "high", "low", "close"]
        if "timestamp" in frame.columns:
            drop_columns.append("timestamp")
        frame.dropna(subset=drop_columns, inplace=True)
        if frame.empty:
            self._clear_primary_chart_data()
            self.set_no_data_state("No valid candle timestamps were returned for this chart.")
            return

        frame = frame[(frame["open"] > 0) & (frame["high"] > 0) & (frame["low"] > 0) & (frame["close"] > 0)]
        if frame.empty:
            return

        price_bounds = frame[["open", "high", "low", "close"]]
        frame["high"] = price_bounds.max(axis=1)
        frame["low"] = price_bounds.min(axis=1)
        frame["volume"] = frame["volume"].fillna(0.0).clip(lower=0.0)
        if "timestamp" in frame.columns:
            frame.sort_values("timestamp", inplace=True)
            frame.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
            frame.reset_index(drop=True, inplace=True)

        x = self._normalize_chart_time_axis(self._extract_time_axis(frame))
        width = self._infer_candle_width(x)
        self._sync_view_context()
        self._last_df = frame.copy()
        self._last_x = np.array(x, dtype=float)
        self._last_candle_stats = self._build_candle_stats(self._last_df, self._last_x)
        if self._chart_status_mode == "loading":
            self.clear_data_status()

        candles = np.column_stack(
            [
                x,
                frame["open"].astype(float).to_numpy(),
                frame["close"].astype(float).to_numpy(),
                frame["low"].astype(float).to_numpy(),
                frame["high"].astype(float).to_numpy(),
            ]
        )

        self._last_candles = candles
        self.candle_item.set_body_width(width)
        self.candle_item.setData(candles)
        self.ema_curve.setData([], [])

        volume = frame["volume"].astype(float).to_numpy()
        colors = [self.candle_up_color if c >= o else self.candle_down_color for o, c in zip(frame["open"], frame["close"])]
        brushes = [pg.mkBrush(c) for c in colors]
        self.volume_bars.setOpts(x=x, height=volume, width=width, brushes=brushes)

        self._update_indicators(frame, x, width)

        if self._should_fit_chart_view(self._last_x):
            self._fit_chart_view(self._last_candle_stats, width)
        self.refresh_context_display()
        self._update_ohlcv_for_x(self._last_x[-1] if len(self._last_x) else 0.0)
        self._render_news_events()

        try:
            last_close = float(frame["close"].iloc[-1])
            prev_close = float(frame["close"].iloc[-2]) if len(frame) > 1 else last_close
            line_color = self.candle_up_color if last_close >= prev_close else self.candle_down_color
            self.last_line.setPen(mkPen(line_color, width=1.15))
            self.last_line.label.fill = pg.mkBrush(pg.mkColor(line_color))
            self.last_line.label.setColor(pg.mkColor("#ffffff"))
            self.last_line.setPos(last_close)
            self.last_line.setVisible(True)
        except Exception:
            pass

    def update_price_lines(self, bid: float, ask: float, last: float | None = None):
        try:
            bid_f = float(bid)
            ask_f = float(ask)
        except Exception:
            return

        self._last_bid = bid_f
        self._last_ask = ask_f

        if bid_f > 0:
            self.bid_line.setPos(bid_f)
            self.bid_line.setVisible(self.show_bid_ask_lines)

        if ask_f > 0:
            self.ask_line.setPos(ask_f)
            self.ask_line.setVisible(self.show_bid_ask_lines)

        if last is None:
            last_f = (bid_f + ask_f) / 2.0 if (bid_f > 0 and ask_f > 0) else 0.0
        else:
            try:
                last_f = float(last)
            except Exception:
                last_f = 0.0

        if last_f > 0:
            self.last_line.setPos(last_f)
            self.last_line.setVisible(True)
        self._update_chart_header()
        self._refresh_market_panels()

    def update_ticks(self, trades):
        """Update tick/trade chart with individual trade data.
        
        Args:
            trades: List of trade data dictionaries with keys: timestamp, price, size, side
        """
        if not trades or not hasattr(self, 'tick_scatter'):
            return
        
        try:
            times = []
            prices = []
            colors = []
            sizes = []
            
            for trade in (trades or []):
                try:
                    timestamp = float(trade.get('timestamp') or trade.get('time') or 0)
                    price = float(trade.get('price') or 0)
                    size = float(trade.get('size') or trade.get('amount') or 0)
                    side = str(trade.get('side') or 'unknown').lower()
                    
                    if timestamp > 0 and price > 0 and size > 0:
                        times.append(timestamp)
                        prices.append(price)
                        sizes.append(max(0.1, min(size * 5, 100)))  # Scale sizes for visibility
                        
                        # Color based on side
                        if side == 'buy':
                            colors.append('#26a69a')  # Green for buy
                        elif side == 'sell':
                            colors.append('#ef5350')  # Red for sell
                        else:
                            colors.append('#8ea4d1')  # Blue for unknown
                except Exception:
                    continue
            
            if times and prices:
                # Update scatter plot
                self.tick_scatter.setData(x=times, y=prices, size=sizes, brush=colors, pen=None)
                
                # Update label
                self.tick_summary_label.setText(
                    f"Showing {len(times)} recent ticks - size scaled by trade volume"
                )
            else:
                self.tick_scatter.clear()
                self.tick_summary_label.setText("No tick data available for this symbol.")
        except Exception as e:
            self.tick_summary_label.setText(f"Error loading tick data: {str(e)}")

    def set_bid_ask_lines_visible(self, visible: bool):
        self.show_bid_ask_lines = bool(visible)
        self.bid_line.setVisible(self.show_bid_ask_lines and self._last_bid is not None and self._last_bid > 0)
        self.ask_line.setVisible(self.show_bid_ask_lines and self._last_ask is not None and self._last_ask > 0)

    def set_volume_panel_visible(self, visible: bool):
        self.show_volume_panel = bool(visible)
        self._apply_chart_pane_layout()

    def set_candle_colors(self, up_color: str, down_color: str):
        self.candle_up_color = up_color
        self.candle_down_color = down_color
        self.candle_item.set_colors(up_color, down_color)
        if self._last_candles is not None:
            self.candle_item.setData(self._last_candles)

    def link_all_charts(self, _count):
        return

from ui.components.chart.chart_market_context import install_chart_market_context
from ui.components.chart.chart_trade_features import install_chart_trade_features

install_chart_market_context(ChartWidget)
install_chart_trade_features(ChartWidget)
