"""Terminal UI definitions and behavior for Sopotek trading app.

This module defines Terminal window, chart panes, market watch, session
control, and many supporting UI actions for live trading and analysis.

Type-checking directives are configured for dynamic UI attributes and hotpatch
methods that are assigned outside of class definitions.
"""

# mypy: disable-error-code="attr-defined, method-assign"
# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportGeneralTypeIssues=false
import asyncio
import contextlib
import html
import inspect
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import threading
import time
from urllib.parse import quote_plus
import warnings
import shiboken6 # type: ignore[import-untyped]
import traceback
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyqtgraph as pg  # type: ignore[import-untyped]

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast
from PySide6.QtCore import Qt, QDate, QSettings, QDateTime, Signal, QTimer, QUrl, QRect, QEvent
from PySide6.QtGui import QAction, QActionGroup, QColor, QTextCursor, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QDockWidget, QSpinBox,
    QTableWidget, QTableWidgetItem,
    QAbstractItemView,
    QPushButton, QLabel, QComboBox, QProgressBar,
    QTabWidget, QToolBar, QDialog, QGridLayout, QDoubleSpinBox, QMessageBox, QFormLayout, QInputDialog, QColorDialog,
    QFrame, QHeaderView, QMenu,
    QHBoxLayout, QSizePolicy, QTextEdit, QTextBrowser, QApplication, QLineEdit, QSlider, QCheckBox, QScrollArea, QFileDialog
)

from ui.components.actions.operator_features import install_terminal_operator_features


def _dock_is_layout_managed(window, dock):
    """Return True when a dock is alive and currently attached to the main layout."""
    if not isinstance(dock, QDockWidget):
        return False
    is_alive = getattr(window, "_is_qt_object_alive", None)
    if callable(is_alive):
        try:
            if not is_alive(dock):
                return False
        except Exception:
            return False
    elif dock is None:
        return False
    try:
        if dock.isFloating():
            return False
    except Exception:
        return False
    try:
        return window.dockWidgetArea(dock) != Qt.DockWidgetArea.NoDockWidgetArea
    except Exception:
        return False


class _MultiChartPage(QWidget):
    """Subclass for dynamic multi-chart page state keys used in Terminal."""
    _detach_window_key: str
    _terminal_multi_chart_symbols: list[str]
    _terminal_multi_chart_timeframe: str


if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    repo_root = Path(__file__).resolve().parents[3]
    repo_value = str(repo_root)
    if repo_value not in sys.path:
        sys.path.insert(0, repo_value)
    from src.main import main as app_main

    raise SystemExit(app_main())

from backtesting.backtest_engine import BacktestEngine
from backtesting.report_generator import ReportGenerator
from backtesting.simulator import Simulator
from broker.market_venues import MARKET_VENUE_CHOICES
from event_bus.event_types import EventType
from ui.components.chart.chart_widget import ChartWidget
from ui.components.actions.trading_actions import (
    cancel_all_orders,
    cancel_all_orders_async,
    close_all_positions,
    close_all_positions_async,
    export_trades,
    show_async_message,
)
from ui.components.actions.live_trade_actions import submit_manual_trade as submit_live_manual_trade
from ui.components.actions.optimization_actions import (
    apply_best_optimization_params,
    optimize_strategy,
    optimization_selection_changed,
    refresh_optimization_selectors,
    refresh_optimization_window,
    show_optimization_window,
)
from ui.components.actions.backtest_actions import (
    generate_report,
    load_backtest_history_clicked,
    refresh_backtest_window,
    show_backtest_window,
    start_backtest,
    stop_backtest,
)
from ui.components.actions.window_actions import (
    open_docs,
    open_logs,
    open_ml_monitor,
    open_text_window,
    sync_logs_window,
)
from ui.components.i18n import apply_runtime_translations, iter_supported_languages
from ui.components.loading_overlay import LoadingOverlay
from ui.components.panels.system_panels import (
    AI_MONITOR_HEADERS,
    create_ai_signal_panel,
    create_live_agent_timeline_panel,
    create_system_console_panel,
    create_system_status_panel,
)
from ui.components.panels.manual_trade_panels import ensure_manual_trade_ticket_window
from ui.components.panels.manual_trade_updates import (
    default_entry_price_for_symbol,
    manual_trade_default_payload,
    manual_trade_format_context,
    manual_trade_quantity_context,
    populate_manual_trade_ticket,
    refresh_manual_trade_ticket,
    normalize_manual_trade_amount,
    normalize_manual_trade_price,
    normalize_manual_trade_quantity_mode,
    submit_manual_trade_from_ticket,
    submit_manual_trade_side,
    suggest_manual_trade_levels,
    validate_manual_trade_amount,
)
from ui.components.panels.performance_updates import (
    performance_snapshot,
    populate_performance_symbol_table,
    populate_performance_view,
    refresh_performance_views,
)
from ui.components.panels.runtime_updates import (
    load_initial_terminal_data,
    load_persisted_runtime_data,
    refresh_assets_async,
    refresh_open_orders_async,
    refresh_order_history_async,
    refresh_positions_async,
    refresh_trade_history_async,
    schedule_assets_refresh,
    schedule_open_orders_refresh,
    schedule_order_history_refresh,
    schedule_positions_refresh,
    schedule_trade_history_refresh,
)
from ui.components.panels.trading_panels import (
    create_open_orders_panel,
    create_positions_panel,
    create_trade_log_panel,
)
from ui.components.panels.trading_updates import (
    apply_assets_filter,
    apply_open_orders_filter,
    apply_order_history_filter,
    apply_positions_filter,
    apply_trade_history_filter,
    apply_trade_log_filter,
    format_trade_log_value,
    format_trade_source_label,
    normalize_open_order_entry,
    normalize_position_entry,
    normalize_trade_log_entry,
    populate_assets_table,
    populate_open_orders_table,
    populate_order_history_table,
    populate_positions_table,
    populate_trade_history_table,
    trade_log_row_for_entry,
    update_trade_log,
)
from ui.components.panels.workspace_panels import (
    create_orderbook_panel,
    create_risk_heatmap_panel,
    create_strategy_debug_panel,
    create_strategy_scorecard_panel,
)
from ui.components.panels.workspace_updates import (
    handle_strategy_debug,
    refresh_strategy_comparison_panel,
    risk_heatmap_positions_snapshot,
    set_risk_heatmap_status,
    strategy_scorecard_rows,
    update_orderbook,
    update_recent_trades,
    update_risk_heatmap,
)
from ui.components.services.diagnostics_service import export_diagnostics_bundle
from ui.components.services.error_reporting import report_uncaught_exception, set_active_terminal
from ui.components.services.screenshot_service import prompt_and_save_widget_screenshot
from ui.components.services.runtime_metrics import build_runtime_metrics_snapshot
from integrations.news_service import NewsService
from quant.ml_research import MLResearchPipeline
from strategy.strategy import Strategy

RISK_PROFILE_PRESETS = {
    "Capital Preservation": {
        "max_portfolio_risk": 0.03,
        "max_risk_per_trade": 0.005,
        "max_position_size_pct": 0.03,
        "max_gross_exposure_pct": 0.50,
        "description": "Very defensive. Small risk budget, small positions, and low total exposure.",
    },
    "Conservative": {
        "max_portfolio_risk": 0.05,
        "max_risk_per_trade": 0.01,
        "max_position_size_pct": 0.05,
        "max_gross_exposure_pct": 1.00,
        "description": "Controlled risk for steady participation with tighter exposure limits.",
    },
    "Balanced": {
        "max_portfolio_risk": 0.10,
        "max_risk_per_trade": 0.02,
        "max_position_size_pct": 0.10,
        "max_gross_exposure_pct": 2.00,
        "description": "General-purpose default. Balanced between protection and opportunity.",
    },
    "Growth": {
        "max_portfolio_risk": 0.15,
        "max_risk_per_trade": 0.03,
        "max_position_size_pct": 0.16,
        "max_gross_exposure_pct": 2.50,
        "description": "Moderately aggressive growth profile with room for larger positions.",
    },
    "Active Trader": {
        "max_portfolio_risk": 0.18,
        "max_risk_per_trade": 0.025,
        "max_position_size_pct": 0.12,
        "max_gross_exposure_pct": 3.50,
        "description": "Designed for more active rotation across symbols with controlled per-trade risk.",
    },
    "Aggressive": {
        "max_portfolio_risk": 0.25,
        "max_risk_per_trade": 0.05,
        "max_position_size_pct": 0.25,
        "max_gross_exposure_pct": 4.00,
        "description": "High-risk profile for experienced users who accept deeper swings.",
    },
}

CHART_TIMEFRAME_MENU_OPTIONS = [
    ("1 Min", "1m"),
    ("5 Min", "5m"),
    ("15 Min", "15m"),
    ("30 Min", "30m"),
    ("1 Hour", "1h"),
    ("4 Hours", "4h"),
    ("1 Day", "1d"),
    ("1 Week", "1w"),
]

CHART_INDICATOR_OPTIONS = [
    "Moving Average",
    "EMA",
    "SMMA",
    "LWMA",
    "VWAP",
    "Fibonacci Retracement",
    "ADX",
    "ATR",
    "Bollinger Bands",
    "Envelopes",
    "Ichimoku",
    "Parabolic SAR",
    "Standard Deviation",
    "Accelerator Oscillator",
    "Awesome Oscillator",
    "CCI",
    "DeMarker",
    "MACD",
    "Momentum",
    "OsMA",
    "RSI",
    "RVI",
    "Stochastic Oscillator",
    "Williams' Percent Range",
    "Accumulation/Distribution",
    "Money Flow Index",
    "On Balance Volume",
    "Volumes",
    "Alligator",
    "Fractal",
    "Gator Oscillator",
    "Market Facilitation Index",
    "Bulls Power",
    "Bears Power",
    "Force Index",
    "Donchian Channel",
    "Keltner Channel",
    "ZigZag",
]

CHART_INDICATOR_DEFAULT_PERIODS = {
    "Moving Average": 14,
    "EMA": 14,
    "SMMA": 14,
    "LWMA": 14,
    "VWAP": 20,
    "Fibonacci Retracement": 120,
    "ADX": 14,
    "ATR": 14,
    "Bollinger Bands": 20,
    "Envelopes": 14,
    "Standard Deviation": 20,
    "CCI": 14,
    "DeMarker": 14,
    "Momentum": 14,
    "RSI": 14,
    "RVI": 10,
    "Stochastic Oscillator": 14,
    "Williams' Percent Range": 14,
    "Money Flow Index": 14,
    "Force Index": 13,
    "Donchian Channel": 20,
    "Keltner Channel": 20,
    "Fractal": 5,
    "ZigZag": 12,
}

CHART_FIXED_DEFAULT_INDICATORS = {
    "Ichimoku",
    "Parabolic SAR",
    "Accelerator Oscillator",
    "Awesome Oscillator",
    "MACD",
    "OsMA",
    "Accumulation/Distribution",
    "On Balance Volume",
    "Volumes",
    "Alligator",
    "Gator Oscillator",
    "Market Facilitation Index",
    "Bulls Power",
    "Bears Power",
}

CHART_STUDY_MENU_GROUPS = [
    (
        "Trend",
        [
            ("Moving Average", 14),
            ("EMA", 14),
            ("VWAP", 20),
            ("Bollinger Bands", 20),
            ("Ichimoku", None),
        ],
    ),
    (
        "Momentum",
        [
            ("RSI", 14),
            ("MACD", None),
            ("Stochastic Oscillator", 14),
            ("Momentum", 14),
        ],
    ),
    (
        "Volatility & Volume",
        [
            ("ATR", 14),
            ("Standard Deviation", 20),
            ("Volumes", None),
            ("On Balance Volume", None),
        ],
    ),
]


def global_exception_hook(exctype, value, tb):
    """Global exception hook to capture unexpected errors in the GUI process."""
    # Ignore expected shutdown interrupts so the terminal closes quietly.
    if exctype in (KeyboardInterrupt, SystemExit):
        return

    print("UNCAUGHT EXCEPTION:")
    traceback.print_exception(exctype, value, tb)
    report_uncaught_exception(exctype, value, tb)


def global_thread_exception_hook(args):
    """Capture uncaught worker-thread exceptions with the same reporting path."""
    exctype = getattr(args, "exc_type", Exception)
    value = getattr(args, "exc_value", None)
    tb = getattr(args, "exc_traceback", None)
    if exctype in (KeyboardInterrupt, SystemExit):
        return

    print("UNCAUGHT THREAD EXCEPTION:")
    traceback.print_exception(exctype, value, tb)
    report_uncaught_exception(exctype, value, tb)


def _json_text(value: object, fallback: str) -> str:
    """Convert a JSON value to a safe string representation with fallback."""
    if isinstance(value, str):
        return value or fallback
    if isinstance(value, (bytes, bytearray)):
        try:
            decoded = bytes(value).decode("utf-8")
        except (UnicodeDecodeError, TypeError, ValueError):
            return fallback
        return decoded or fallback
    return fallback


def _setting_bool(value: object, default: bool = False) -> bool:
    """Normalize various setting value formats to a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_float(value: Any) -> float | None:
    """Try converting a value to float; return None on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _coerce_timestamp_seconds(value: Any) -> float | None:
    """Normalize epoch or ISO-8601 timestamps into UTC seconds."""
    if value in (None, ""):
        return None
    if isinstance(value, QDateTime):
        return value.toMSecsSinceEpoch() / 1000.0
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1_000_000_000_000:
            return numeric / 1000.0
        return numeric

    text = str(value).strip()
    if not text:
        return None

    try:
        numeric = float(text)
    except (TypeError, ValueError):
        numeric = None
    if numeric is not None:
        if numeric > 1_000_000_000_000:
            return numeric / 1000.0
        return numeric

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.timestamp()


def _read_pyproject_version(pyproject_path: Path) -> str | None:
    """Read the project version from pyproject.toml (PEP 621 [project] version)."""
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return None

    in_project_section = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[project]":
            in_project_section = True
            continue
        if in_project_section and line.startswith("["):
            break
        if in_project_section:
            match = re.match(r'version\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                return match.group(1).strip() or None
    return None


def _bounded_terminal_window_extent(requested, available, *, margin=24, minimum=640):
    try:
        requested_value = int(requested)
    except Exception:
        requested_value = int(minimum)

    try:
        available_value = int(available)
    except Exception:
        available_value = requested_value

    usable = max(320, available_value - max(0, int(margin)))
    bounded_minimum = min(max(320, int(minimum)), usable)
    bounded_size = max(bounded_minimum, min(requested_value, usable))
    return bounded_size, bounded_minimum


class Terminal(QMainWindow):
    """Main trading terminal UI window.

    Contains broker controls, charts, orders, positions, and autoscaling status.
    """
    logout_requested = Signal()
    ai_signal = Signal(dict)
    autotrade_toggle = Signal(bool)

    def __init__(self, controller):
        """Initialize terminal state and start refresh timers."""

        # The controller is not a QWidget parent; it is an application controller
        # object that manages the terminal state and signals.
        super().__init__()

        set_active_terminal(self)
        sys.excepthook = global_exception_hook
        threading.excepthook = global_thread_exception_hook

        self.controller = controller
        self.logger = controller.logger
        self.bound_session_id = str(getattr(controller, "active_session_id", "") or "").strip()
        self.bound_session_label = ""
        self._controller_signal_bindings = []
        self._status_value_cache = {}
        self._session_selector_signature = None
        self._session_tabs_signature = None
        self._market_watch_row_cache = {}
        self._market_watch_symbols_signature = None
        self._assets_table_signature = None
        self._positions_table_signature = None
        self._open_orders_table_signature = None
        self._order_history_table_signature = None
        self._trade_history_table_signature = None
        self._risk_heatmap_signature = None
        self._strategy_comparison_signature = None
        self._terminal_refresh_timestamps = {}
        self._terminal_refresh_dirty_sections = {
            "execution_tables",
            "risk_heatmap",
            "session_controls",
            "strategy_comparison",
            "live_agent_timeline",
        }
        self._terminal_refresh_queued = False
        self._market_watch_flush_queued = False
        self._market_watch_pending_quotes = {}
        self._last_market_watch_reorder_at = 0.0
        self._runtime_health_cache_key = None
        self._cached_capability_profile = {}
        self._cached_readiness_report = {}
        self._cached_market_data_health = {}
        self._last_runtime_health_refresh_at = 0.0
        self._runtime_timers_started = False
        self._workspace_interaction_notice_at = 0.0

        self.settings = QSettings("TradeAdviser", "TradingPlatform")

        self.symbols_table = QTableWidget()
        self.system_console: Any = None

        self.risk_map = None
        self.auto_button = QPushButton()

        self.historical_data = controller.historical_data

        self.confidence_data = []

        if controller.symbols:
            index = random.randint(0, len(controller.symbols) - 1)
            self.symbol = controller.symbols[index]
        else:
            self.symbol = "BTC/USDT"

        self.MAX_LOG_ROWS = 200
        self.AI_TABLE_REFRESH_MIN_SECONDS = 0.5
        self.AI_SIGNAL_LOG_MIN_SECONDS = 30.0
        self.PASSIVE_SIGNAL_SCAN_INTERVAL_MS = 5000
        self.PASSIVE_SIGNAL_SCAN_MAX_SYMBOLS = 6
        self.MARKET_WATCH_FLUSH_INTERVAL_MS = 60
        self.MARKET_WATCH_REORDER_MIN_SECONDS = 0.75
        self.RUNTIME_HEALTH_CACHE_SECONDS = 3.0
        self.WORKSPACE_READY_TIMEOUT_SECONDS = 60.0
        self.INITIAL_ACCOUNT_SYNC_TIMEOUT_SECONDS = 40.0
        self.INITIAL_STAGE_TIMEOUT_SECONDS = 18.0
        self.current_timeframe = getattr(controller,"time_frame")
        self.autotrading_enabled = False
        scope_normalizer = getattr(controller, "_normalize_autotrade_scope", None)
        if callable(scope_normalizer):
            try:
                self.autotrade_scope_value = str(scope_normalizer(getattr(controller, "autotrade_scope", "all")) or "all").lower()
            except Exception:
                self.autotrade_scope_value = str(getattr(controller, "autotrade_scope", "all") or "all").lower()
        else:
            self.autotrade_scope_value = str(getattr(controller, "autotrade_scope", "all") or "all").lower()
        self.autotrade_watchlist = set(getattr(controller, "autotrade_watchlist", set()) or set())

        self.training_status = {}
        self.show_bid_ask_lines = True
        self.show_chart_volume = _setting_bool(self.settings.value("terminal/show_chart_volume", False), False)
        self._ui_shutting_down = False
        self._initial_terminal_data_task = None
        self._workspace_ready = False
        self._assets_refresh_task = None
        self._positions_refresh_task = None
        self._open_orders_refresh_task = None
        self._order_history_refresh_task = None
        self._trade_history_refresh_task = None
        self._broker_status_refresh_task = None
        self._latest_assets_snapshot = {}
        self._latest_positions_snapshot = []
        self._latest_open_orders_snapshot = []
        self._latest_order_history_snapshot = []
        self._latest_trade_history_snapshot = []
        self._latest_broker_status_snapshot = {"status": "disconnected", "summary": "Disconnected"}
        self._last_broker_status_refresh_at = 0.0
        self._last_assets_refresh_at = 0.0
        self._last_positions_refresh_at = 0.0
        self._last_open_orders_refresh_at = 0.0
        self._last_order_history_refresh_at = 0.0
        self._last_trade_history_refresh_at = 0.0
        self._last_ai_table_refresh_at = 0.0
        self._last_passive_signal_scan_at = 0.0
        self._passive_signal_scan_task = None
        self._autotrade_enable_task = None
        self._ai_signal_records = {}
        self._ai_signal_log_state = {}
        self._recommendation_records = {}
        self._closed_journal_refresh_task = None

        self.candle_up_color = str(self.settings.value("chart/candle_up_color", "#26a69a") or "#26a69a")
        self.candle_down_color = str(self.settings.value("chart/candle_down_color", "#ef5350") or "#ef5350")
        self.chart_background_color = str(self.settings.value("chart/background_color", "#11161f") or "#11161f")
        self.chart_grid_color = str(self.settings.value("chart/grid_color", "#8290a0") or "#8290a0")
        self.chart_axis_color = str(self.settings.value("chart/axis_color", "#9aa4b2") or "#9aa4b2")

        self.heartbeat = QLabel("●")
        self.heartbeat.setStyleSheet("color: green")

        self._setup_core()
        self._setup_ui()
        self._setup_panels()
        self._setup_workspace_loading_overlay()
        self._restore_settings()
        self._connect_signals()
        self._setup_spinner()

        if hasattr(self.controller, "language_changed"):
            self.controller.language_changed.connect(lambda _code: self.apply_language())

        self._app_event_filter_installed = False
        app = QApplication.instance()
        if app is not None:
            try:
                app.installEventFilter(self)
                self._app_event_filter_installed = True
            except Exception:
                self._app_event_filter_installed = False

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._schedule_terminal_refresh)
        self.refresh_timer.setInterval(1000)

        self.orderbook_timer = QTimer()
        self.orderbook_timer.timeout.connect(self._request_active_orderbook)
        self.orderbook_timer.setInterval(1500)

        self.signal_scan_timer = QTimer()
        self.signal_scan_timer.timeout.connect(self._schedule_passive_signal_scan)
        self.signal_scan_timer.setInterval(int(self.PASSIVE_SIGNAL_SCAN_INTERVAL_MS))
        QTimer.singleShot(0, self._schedule_initial_terminal_data_load)

        self.ai_signal.connect(self._update_ai_signal)

    def _setup_workspace_loading_overlay(self):
        self.workspace_loading_overlay = LoadingOverlay(self, title="Preparing trading workspace...")
        self.workspace_loading_overlay.set_loading(
            "Preparing trading workspace...",
            "Connecting the terminal, restoring account state, and loading market data. Please wait up to 1 minute.",
        )

    def _set_workspace_loading_state(self, title, detail=None, *, visible=True):
        overlay = getattr(self, "workspace_loading_overlay", None)
        if overlay is None:
            return
        if visible:
            self._workspace_ready = False
            self._stop_runtime_timers()
            overlay.set_loading(
                str(title or "Preparing trading workspace...").strip() or "Preparing trading workspace...",
                str(detail or "Please wait up to 1 minute while the terminal finishes loading.").strip() or None,
            )
        else:
            self._workspace_ready = True
            overlay.clear_loading()
            self._start_runtime_timers()

    def _start_runtime_timers(self):
        if getattr(self, "_ui_shutting_down", False):
            return
        if bool(getattr(self, "_runtime_timers_started", False)):
            return
        refresh_timer = getattr(self, "refresh_timer", None)
        if refresh_timer is not None:
            refresh_timer.start(max(250, int(refresh_timer.interval() or 1000)))
        orderbook_timer = getattr(self, "orderbook_timer", None)
        if orderbook_timer is not None:
            orderbook_timer.start(max(250, int(orderbook_timer.interval() or 1500)))
        signal_timer = getattr(self, "signal_scan_timer", None)
        if signal_timer is not None:
            signal_timer.start(max(500, int(signal_timer.interval() or int(self.PASSIVE_SIGNAL_SCAN_INTERVAL_MS))))
        self._runtime_timers_started = True
        QTimer.singleShot(1800, self._schedule_passive_signal_scan)
        self._schedule_terminal_refresh()

    def _stop_runtime_timers(self):
        refresh_timer = getattr(self, "refresh_timer", None)
        if refresh_timer is not None:
            refresh_timer.stop()
        orderbook_timer = getattr(self, "orderbook_timer", None)
        if orderbook_timer is not None:
            orderbook_timer.stop()
        signal_timer = getattr(self, "signal_scan_timer", None)
        if signal_timer is not None:
            signal_timer.stop()
        self._runtime_timers_started = False

    def _workspace_loading_active(self):
        if getattr(self, "_ui_shutting_down", False):
            return False
        if bool(getattr(self, "_workspace_ready", False)):
            return False
        overlay = getattr(self, "workspace_loading_overlay", None)
        try:
            if overlay is not None and overlay.isVisible():
                return True
        except Exception:
            pass
        task = getattr(self, "_initial_terminal_data_task", None)
        return task is not None and not task.done()

    def _terminal_owns_object(self, obj):
        current = obj
        for _ in range(16):
            if current is None:
                return False
            if current is self:
                return True
            if isinstance(current, QWidget):
                try:
                    if self.isAncestorOf(current):
                        return True
                except Exception:
                    pass
            parent_getter = getattr(current, "parent", None)
            if not callable(parent_getter):
                break
            try:
                current = parent_getter()
            except Exception:
                break
        return False

    def _notify_workspace_loading_interaction(self):
        now = time.monotonic()
        if (now - float(getattr(self, "_workspace_interaction_notice_at", 0.0) or 0.0)) < 1.5:
            return
        self._workspace_interaction_notice_at = now
        updater = getattr(self, "_set_workspace_loading_state", None)
        if callable(updater):
            updater(
                "Preparing trading workspace...",
                "The terminal is still loading balances, positions, orders, and chart data. Please wait up to 1 minute and be patient.",
                visible=True,
            )

    async def wait_until_ready(self, timeout: float | None = None) -> bool:
        task = getattr(self, "_initial_terminal_data_task", None)
        if task is None:
            await asyncio.sleep(0)
            task = getattr(self, "_initial_terminal_data_task", None)
        if task is None:
            self._workspace_ready = True
            self._set_workspace_loading_state(None, None, visible=False)
            return True

        try:
            resolved_timeout = max(
                1.0,
                float(timeout if timeout is not None else getattr(self, "WORKSPACE_READY_TIMEOUT_SECONDS", 60.0)),
            )
            await asyncio.wait_for(asyncio.shield(task), timeout=resolved_timeout)
            return True
        except asyncio.TimeoutError:
            self.logger.warning("Initial terminal data load timed out; opening workspace in degraded mode.")
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._set_workspace_loading_state(
                None,
                "Some account or market data took too long to load. The workspace is opening in safe mode and will keep refreshing.",
                visible=False,
            )
            return False
        except Exception:
            self.logger.exception("Initial terminal readiness failed")
            self._set_workspace_loading_state(
                None,
                "Initial workspace data could not be restored. The terminal will continue retrying in the background.",
                visible=False,
            )
            return False

    def _mark_terminal_refresh_dirty(self, *section_names):
        dirty_sections = getattr(self, "_terminal_refresh_dirty_sections", None)
        if dirty_sections is None:
            dirty_sections = set()
            self._terminal_refresh_dirty_sections = dirty_sections
        for section_name in section_names:
            name = str(section_name or "").strip()
            if name:
                dirty_sections.add(name)

    def _should_refresh_terminal_section(self, section_name, *, interval_seconds=0.0, force=False):
        name = str(section_name or "").strip()
        if not name:
            return True

        dirty_sections = getattr(self, "_terminal_refresh_dirty_sections", None)
        if dirty_sections is None:
            dirty_sections = set()
            self._terminal_refresh_dirty_sections = dirty_sections
        timestamps = getattr(self, "_terminal_refresh_timestamps", None)
        if timestamps is None:
            timestamps = {}
            self._terminal_refresh_timestamps = timestamps

        now = time.monotonic()
        last_refresh_at = float(timestamps.get(name, 0.0) or 0.0)
        should_refresh = bool(force or name in dirty_sections)
        if not should_refresh:
            should_refresh = last_refresh_at <= 0.0
        if not should_refresh and interval_seconds <= 0.0:
            should_refresh = True
        if not should_refresh and (now - last_refresh_at) >= float(interval_seconds):
            should_refresh = True
        if should_refresh:
            timestamps[name] = now
            dirty_sections.discard(name)
            return True
        return False

    def _run_scheduled_terminal_refresh(self):
        self._terminal_refresh_queued = False
        self._refresh_terminal()

    def _schedule_terminal_refresh(self):
        if getattr(self, "_ui_shutting_down", False):
            return
        if getattr(self, "_terminal_refresh_queued", False):
            return
        self._terminal_refresh_queued = True
        QTimer.singleShot(0, self._run_scheduled_terminal_refresh)


    def _setup_core(self):
        """Configure core terminal window settings and initialize state holders."""

        self.order_type = self.controller.order_type
        self.setWindowTitle(self._terminal_window_title())
        self.resize(1600, 900)
        self.setMinimumSize(960, 640)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setDockOptions(
            # GroupedDragging has been unstable on Windows when hidden/tabbed docks
            # are dragged together, so keep tabs but drag only the active dock.
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )
        self._pending_initial_window_fit = True

        self.connection_indicator = QLabel("● CONNECTING")
        self.connection_indicator.setStyleSheet(
            "color: orange; font-weight: bold;"
        )

        self.timeframe_buttons = {}
        self.toolbar = None
        self.toolbar_timeframe_label = None
        self.autotrade_scope_picker = None
        self.autotrade_scope_label_widget = None
        self.autotrade_controls_box = None
        self.autotrade_controls_layout = None
        self.autotrade_controls_row = None
        self._autotrade_toolbar_layout_mode = "full"
        self.system_status_button = None
        self.system_status_dock = None
        self.ai_signal_dock = None
        self.live_agent_timeline_dock = None
        self.live_agent_timeline_summary = None
        self.live_agent_timeline_browser = None
        self.secondary_toolbar = None
        self.market_watch_dock = None
        self.tick_chart_dock = None
        self.system_console_dock = None
        self.positions_dock = None
        self.open_orders_dock = None
        self.trade_log_dock = None
        self.orderbook_dock = None
        self.strategy_scorecard_dock = None
        self.strategy_debug_dock = None
        self.risk_heatmap_dock = None
        self.trading_activity_label = None
        self.live_trading_bar_frame = None
        self.live_trading_bar_label = None
        self.live_trading_bar = None
        self.session_mode_badge = None
        self.session_selector = None
        self.session_tabs_dock = None
        self.session_tabs_widget = None
        self.desk_status_frame = None
        self.desk_status_title_label = None
        self.desk_status_primary_label = None
        self.desk_status_secondary_label = None
        self.kill_switch_button = None
        self.symbol_picker = None
        self.detached_tool_windows: dict[str, Any] = {}
        self._active_chart_widget_ref = None
        self._last_chart_request_key = None
        self.current_connection_status = "connecting"
        self.language_actions = {}

    def _terminal_window_title(self):
        label = str(getattr(self, "bound_session_label", "") or "").strip()
        session_id = str(getattr(self, "bound_session_id", "") or "").strip()
        suffix = label or session_id
        if suffix:
            return f"TradeAdviser Terminal - {suffix}"
        return "TradeAdviser Terminal"

    def _fit_window_to_available_screen(self, requested_width=None, requested_height=None):
        screen = self.screen()
        if screen is None:
            app = QApplication.instance()
            screen = app.primaryScreen() if app is not None else None
        if screen is None:
            return

        available = screen.availableGeometry()
        width, minimum_width = _bounded_terminal_window_extent(
            requested_width if requested_width is not None else self.width() or 1600,
            available.width(),
            minimum=960,
        )
        height, minimum_height = _bounded_terminal_window_extent(
            requested_height if requested_height is not None else self.height() or 900,
            available.height(),
            minimum=640,
        )
        self.setMinimumSize(minimum_width, minimum_height)
        self.resize(width, height)

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_pending_initial_window_fit", False):
            self._pending_initial_window_fit = False
            QTimer.singleShot(0, self._fit_window_to_available_screen)

    def eventFilter(self, watched, event):
        if self._workspace_loading_active() and self._terminal_owns_object(watched) and isinstance(event, QEvent):
            blocked_types = {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.Wheel,
                QEvent.Type.KeyPress,
                QEvent.Type.KeyRelease,
                QEvent.Type.ShortcutOverride,
                QEvent.Type.ContextMenu,
                QEvent.Type.GraphicsSceneMousePress,
                QEvent.Type.GraphicsSceneMouseRelease,
                QEvent.Type.GraphicsSceneMouseDoubleClick,
                QEvent.Type.GraphicsSceneWheel,
            }
            if event.type() in blocked_types:
                self._notify_workspace_loading_interaction()
                try:
                    event.accept()
                except Exception:
                    pass
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        refresh_autotrade_controls_layout = getattr(self, "_refresh_autotrade_controls_layout", None)
        if callable(refresh_autotrade_controls_layout):
            refresh_autotrade_controls_layout()

    def bind_session(self, session_id, label=None):
        self.bound_session_id = str(session_id or "").strip()
        self.bound_session_label = str(label or "").strip()
        self.setWindowTitle(self._terminal_window_title())
        refresh_picker = getattr(self, "_refresh_session_selector", None)
        if callable(refresh_picker):
            refresh_picker()
        refresh_tabs = getattr(self, "_refresh_session_tabs", None)
        if callable(refresh_tabs):
            refresh_tabs()
        update_badge = getattr(self, "_update_session_badge", None)
        if callable(update_badge):
            update_badge()

    def _session_is_current(self):
        bound_session_id = str(getattr(self, "bound_session_id", "") or "").strip()
        if not bound_session_id:
            return True
        controller = getattr(self, "controller", None)
        active_session_id = str(getattr(controller, "active_session_id", "") or "").strip()
        return bound_session_id == active_session_id

    def _extract_session_id_from_payload(self, value):
        if isinstance(value, dict):
            session_id = str(value.get("session_id") or "").strip()
            if session_id:
                return session_id
            for nested_key in ("metadata", "event", "trade", "signal"):
                nested_value = value.get(nested_key)
                nested_session_id = self._extract_session_id_from_payload(nested_value)
                if nested_session_id:
                    return nested_session_id
        elif isinstance(value, (list, tuple)):
            for item in value:
                nested_session_id = self._extract_session_id_from_payload(item)
                if nested_session_id:
                    return nested_session_id
        return ""

    def _payload_session_matches_terminal(self, *args, **kwargs):
        bound_session_id = str(getattr(self, "bound_session_id", "") or "").strip()
        if not bound_session_id:
            return True

        payload_session_id = ""
        for value in list(args) + list(kwargs.values()):
            payload_session_id = self._extract_session_id_from_payload(value)
            if payload_session_id:
                break

        if not payload_session_id:
            return self._session_is_current()
        return payload_session_id == bound_session_id

    def _session_scoped_slot(self, slot):
        def _wrapped(*args, **kwargs):
            if getattr(self, "_ui_shutting_down", False):
                return None
            if not self._payload_session_matches_terminal(*args, **kwargs):
                return None
            return slot(*args, **kwargs)

        return _wrapped

    def _maybe_activate_bound_session(self):
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        bound_session_id = str(getattr(self, "bound_session_id", "") or "").strip()
        if not bound_session_id:
            controller.terminal = self
            return
        if str(getattr(controller, "active_session_id", "") or "").strip() == bound_session_id:
            controller.terminal = self
            return
        request_activation = getattr(controller, "request_session_activation", None)
        if callable(request_activation):
            controller.terminal = self
            request_activation(bound_session_id)

    def event(self, event):
        if event is not None and event.type() == QEvent.Type.WindowActivate:
            self._maybe_activate_bound_session()
        return super().event(event)

    def _history_request_limit(self, fallback=None):
        """Compute effective OHLCV history limit using app, runtime, and broker caps."""
        value = fallback if fallback is not None else getattr(self.controller, "limit", 50000)
        try:
            resolved = max(100, int(value))
        except (TypeError, ValueError):
            resolved = 50000

        runtime_cap = getattr(self.controller, "runtime_history_limit", None)
        if runtime_cap is None:
            runtime_cap = 1000
        try:
            resolved = min(resolved, max(100, int(runtime_cap)))
        except (TypeError, ValueError):
            pass

        broker = getattr(self.controller, "broker", None)
        broker_cap = getattr(broker, "MAX_OHLCV_COUNT", None)
        try:
            if broker_cap is not None:
                resolved = min(resolved, max(100, int(broker_cap)))
        except (TypeError, ValueError):
            pass

        return resolved

    def _tr(self, key, **kwargs):
        """Translate UI key using controller translation system."""
        if hasattr(self.controller, "tr"):
            return self.controller.tr(key, **kwargs)
        return key

    def _active_exchange_name(self):
        """Determine current active exchange name from broker or settings."""
        broker = getattr(self.controller, "broker", None)
        if broker is not None:
            name = getattr(broker, "exchange_name", None)
            if name:
                return str(name).lower()

        config = getattr(self.controller, "config", None)
        broker_config = getattr(config, "broker", None)
        if broker_config is not None:
            exchange = getattr(broker_config, "exchange", None)
            if exchange:
                return str(exchange).lower()

        if hasattr(self, "symbols_table") and self.symbols_table is not None:
            name = self.symbols_table.accessibleName()
            if name:
                return str(name).lower()

        return ""

    def _is_stellar_market_watch(self):
        """Return whether the current market watch should include Stellar column behavior."""
        return self._active_exchange_name() == "stellar"

    def _sync_exchange_scoped_actions(self):
        """Show venue-specific actions only when the active broker supports them."""
        is_stellar = Terminal._active_exchange_name(self) == "stellar"

        stellar_action = getattr(self, "action_stellar_asset_explorer", None)
        if stellar_action is not None:
            stellar_action.setVisible(is_stellar)

        stellar_separator = getattr(self, "_research_stellar_separator_action", None)
        if stellar_separator is not None:
            stellar_separator.setVisible(is_stellar)
        tools_stellar_separator = getattr(self, "_tools_stellar_separator_action", None)
        if tools_stellar_separator is not None:
            tools_stellar_separator.setVisible(is_stellar)

        explorer_window = (getattr(self, "detached_tool_windows", {}) or {}).get("stellar_asset_explorer")
        if not is_stellar and Terminal._is_qt_object_alive(self, explorer_window):
            explorer_window.hide()

    def _market_watch_headers(self):
        """Return headers for the market watch table based on exchange type."""
        if self._is_stellar_market_watch():
            return ["Watch", "Symbol", "Bid", "Ask", "USD Value", "AI Training"]
        return ["Watch", "Symbol", "Bid", "Ask", "AI Training"]

    def _market_watch_watch_column(self):
        return 0

    def _market_watch_symbol_column(self):
        return 1

    def _market_watch_bid_column(self):
        return 2

    def _market_watch_ask_column(self):
        return 3

    def _market_watch_status_column(self):
        return 5 if self._is_stellar_market_watch() else 4

    def _market_watch_usd_column(self):
        return 4 if self._is_stellar_market_watch() else None

    def _configure_market_watch_table(self):
        """Initialize the watchlist table structure and header labels."""
        if not hasattr(self, "symbols_table") or self.symbols_table is None:
            return
        headers = self._market_watch_headers()
        self.symbols_table.setColumnCount(len(headers))
        self.symbols_table.setHorizontalHeaderLabels(headers)
        
        # Set table title/tooltip to show current venue type
        venue_type = self._get_current_venue_type()
        exchange = str(
            getattr(getattr(self.controller, "broker", None), "exchange_name", None)
            or getattr(getattr(getattr(self.controller, "config", None), "broker", None), "exchange", "")
            or ""
        ).upper() or "BROKER"
        
        # Set window title or accessible name to show venue info
        if hasattr(self, "symbols_table"):
            self.symbols_table.setAccessibleName(f"Market Watch - {exchange} {venue_type}")
            self.symbols_table.setToolTip(f"Symbols list for {exchange} {venue_type} market\nVenue: {venue_type}")

    def _normalized_symbol(self, symbol):
        """Normalize symbol text to uppercase trimmed value."""
        return str(symbol or "").upper().strip()

    def _rebuild_market_watch_row_cache(self):
        """Rebuild the symbol-to-row cache used by live market-watch updates."""
        if not hasattr(self, "symbols_table") or self.symbols_table is None:
            self._market_watch_row_cache = {}
            return self._market_watch_row_cache

        symbol_column = self._market_watch_symbol_column()
        cache = {}
        for row in range(self.symbols_table.rowCount()):
            item = self.symbols_table.item(row, symbol_column)
            normalized = self._normalized_symbol(item.text()) if item is not None else ""
            if normalized:
                cache[normalized] = row
        self._market_watch_row_cache = cache
        return cache

    def _find_market_watch_row(self, symbol):
        """Find the row index for a symbol in the watchlist table."""
        target = self._normalized_symbol(symbol)
        if not target or not hasattr(self, "symbols_table") or self.symbols_table is None:
            return None

        symbol_column = self._market_watch_symbol_column()
        cache = getattr(self, "_market_watch_row_cache", None)
        if isinstance(cache, dict):
            cached_row = cache.get(target)
            if isinstance(cached_row, int) and 0 <= cached_row < self.symbols_table.rowCount():
                cached_item = self.symbols_table.item(cached_row, symbol_column)
                if cached_item is not None and self._normalized_symbol(cached_item.text()) == target:
                    return cached_row

        cache = self._rebuild_market_watch_row_cache()
        cached_row = cache.get(target)
        if isinstance(cached_row, int) and 0 <= cached_row < self.symbols_table.rowCount():
            return cached_row
        return None

    def _market_watch_check_item(self, symbol, checked=False):
        """Create a checkable table cell for market watch symbol inclusion."""
        item = QTableWidgetItem("")
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
        )
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setToolTip(f"Trade {self._normalized_symbol(symbol)} when AI scope is Watchlist")
        return item

    def _set_market_watch_text_item(self, row, column, value, *, tooltip=None):
        text = str(value)
        item = self.symbols_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(text)
            self.symbols_table.setItem(row, column, item)
        elif item.text() != text:
            item.setText(text)
        if tooltip is not None and item.toolTip() != tooltip:
            item.setToolTip(tooltip)
        return item

    def _set_market_watch_row(self, row, symbol, bid="-", ask="-", status="⏳", usd_value="-"):
        """Update or insert a market watch row with latest quote and state values."""
        normalized_symbol = self._normalized_symbol(symbol)
        checked = normalized_symbol in self.autotrade_watchlist
        watch_column = self._market_watch_watch_column()
        symbol_column = self._market_watch_symbol_column()
        bid_column = self._market_watch_bid_column()
        ask_column = self._market_watch_ask_column()
        previous_symbol_item = self.symbols_table.item(row, symbol_column)
        previous_symbol = self._normalized_symbol(previous_symbol_item.text()) if previous_symbol_item is not None else ""

        existing_check = self.symbols_table.item(row, watch_column)
        if existing_check is None:
            self.symbols_table.setItem(row, watch_column, self._market_watch_check_item(normalized_symbol, checked))
        else:
            blocked = self.symbols_table.blockSignals(True)
            existing_check.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            existing_check.setToolTip(f"Trade {normalized_symbol} when AI scope is Watchlist")
            self.symbols_table.blockSignals(blocked)

        self._set_market_watch_text_item(row, symbol_column, normalized_symbol)
        self._set_market_watch_text_item(row, bid_column, bid)
        self._set_market_watch_text_item(row, ask_column, ask)

        usd_column = self._market_watch_usd_column()
        if usd_column is not None:
            self._set_market_watch_text_item(row, usd_column, usd_value)

        self._set_market_watch_text_item(row, self._market_watch_status_column(), status)
        row_cache = getattr(self, "_market_watch_row_cache", None)
        if not isinstance(row_cache, dict):
            row_cache = {}
            self._market_watch_row_cache = row_cache
        if previous_symbol and previous_symbol != normalized_symbol:
            row_cache.pop(previous_symbol, None)
        if normalized_symbol:
            row_cache[normalized_symbol] = row

    def _queue_market_watch_quote_update(self, symbol, *, bid="-", ask="-", status="Live", usd_value="-"):
        normalized_symbol = self._normalized_symbol(symbol)
        if not normalized_symbol:
            return
        pending_quotes = getattr(self, "_market_watch_pending_quotes", None)
        if not isinstance(pending_quotes, dict):
            pending_quotes = {}
            self._market_watch_pending_quotes = pending_quotes
        pending_quotes[normalized_symbol] = {
            "symbol": normalized_symbol,
            "bid": bid,
            "ask": ask,
            "status": status,
            "usd_value": usd_value,
        }

    def _run_scheduled_market_watch_flush(self):
        self._market_watch_flush_queued = False
        self._flush_market_watch_updates()

    def _schedule_market_watch_flush(self):
        if getattr(self, "_ui_shutting_down", False):
            return
        if getattr(self, "_market_watch_flush_queued", False):
            return
        self._market_watch_flush_queued = True
        interval_ms = max(0, int(getattr(self, "MARKET_WATCH_FLUSH_INTERVAL_MS", 60) or 60))
        QTimer.singleShot(interval_ms, self._run_scheduled_market_watch_flush)

    def _maybe_reorder_market_watch_rows(self, *, force=False):
        if getattr(self, "_ui_shutting_down", False):
            return
        now = time.monotonic()
        min_interval = max(0.0, float(getattr(self, "MARKET_WATCH_REORDER_MIN_SECONDS", 0.75) or 0.75))
        if not force and (now - float(getattr(self, "_last_market_watch_reorder_at", 0.0) or 0.0)) < min_interval:
            return
        self._reorder_market_watch_rows()
        self._last_market_watch_reorder_at = time.monotonic()

    def _flush_market_watch_updates(self, *, force_reorder=False):
        if not hasattr(self, "symbols_table") or self.symbols_table is None:
            return

        pending_quotes = getattr(self, "_market_watch_pending_quotes", None)
        if not isinstance(pending_quotes, dict) or not pending_quotes:
            return

        quote_updates = list(pending_quotes.values())
        pending_quotes.clear()
        inserted_rows = False
        blocked = self.symbols_table.blockSignals(True)
        previous_updates_enabled = None
        try:
            previous_updates_enabled = bool(self.symbols_table.updatesEnabled())
        except Exception:
            previous_updates_enabled = None

        try:
            self.symbols_table.setUpdatesEnabled(False)
            for entry in quote_updates:
                symbol = str(entry.get("symbol") or "").strip()
                if not symbol:
                    continue
                target_row = self._find_market_watch_row(symbol)
                if target_row is None:
                    target_row = self.symbols_table.rowCount()
                    self.symbols_table.insertRow(target_row)
                    self._market_watch_symbols_signature = None
                    inserted_rows = True
                self._set_market_watch_row(
                    target_row,
                    symbol,
                    bid=entry.get("bid", "-"),
                    ask=entry.get("ask", "-"),
                    status=entry.get("status", "Live"),
                    usd_value=entry.get("usd_value", "-"),
                )
        finally:
            self.symbols_table.blockSignals(blocked)
            try:
                if previous_updates_enabled is not None:
                    self.symbols_table.setUpdatesEnabled(previous_updates_enabled)
                else:
                    self.symbols_table.setUpdatesEnabled(True)
            except Exception:
                pass

        if inserted_rows:
            self._rebuild_market_watch_row_cache()
        if inserted_rows or force_reorder:
            self._maybe_reorder_market_watch_rows(force=True)

    def _sync_watchlist_from_table(self):
        """Extract selected watchlist symbols from the table and persist to controller."""
        watchlist = set()
        watch_column = self._market_watch_watch_column()
        symbol_column = self._market_watch_symbol_column()
        for row in range(self.symbols_table.rowCount()):
            watch_item = self.symbols_table.item(row, watch_column)
            symbol_item = self.symbols_table.item(row, symbol_column)
            if watch_item is None or symbol_item is None:
                continue
            if watch_item.checkState() == Qt.CheckState.Checked:
                normalized = self._normalized_symbol(symbol_item.text())
                if normalized:
                    watchlist.add(normalized)
        self.autotrade_watchlist = watchlist
        if hasattr(self.controller, "set_autotrade_watchlist"):
            self.controller.set_autotrade_watchlist(sorted(watchlist))

    def _handle_market_watch_item_changed(self, item):
        """Handle a check state change for the market watch table."""
        if item is None or item.column() != self._market_watch_watch_column():
            return
        self._sync_watchlist_from_table()
        self._reorder_market_watch_rows()
        self._queue_terminal_layout_fit()
        self._mark_terminal_refresh_dirty("session_controls")
        self._schedule_terminal_refresh()

    def _market_watch_row_snapshot(self, row):
        watch_item = self.symbols_table.item(row, self._market_watch_watch_column())
        symbol_item = self.symbols_table.item(row, self._market_watch_symbol_column())
        bid_item = self.symbols_table.item(row, self._market_watch_bid_column())
        ask_item = self.symbols_table.item(row, self._market_watch_ask_column())
        status_item = self.symbols_table.item(row, self._market_watch_status_column())
        usd_column = self._market_watch_usd_column()
        usd_item = self.symbols_table.item(row, usd_column) if usd_column is not None else None
        return {
            "checked": watch_item is not None and watch_item.checkState() == Qt.CheckState.Checked,
            "symbol": symbol_item.text() if symbol_item is not None else "",
            "bid": bid_item.text() if bid_item is not None else "-",
            "ask": ask_item.text() if ask_item is not None else "-",
            "status": status_item.text() if status_item is not None else "-",
            "usd_value": usd_item.text() if usd_item is not None else "-",
        }

    def _market_watch_priority_rank(self, symbol, checked=False):
        normalized = self._normalized_symbol(symbol)
        available_symbols = [
            self._normalized_symbol(item)
            for item in (getattr(self.controller, "symbols", []) or [])
            if self._normalized_symbol(item)
        ]
        available_set = set(available_symbols)
        scope = str(self.autotrade_scope_value or "all").lower()

        if scope == "all":
            if normalized in available_set:
                return (0, available_symbols.index(normalized))
            return (1, normalized)
        if scope == "selected":
            selected = self._normalized_symbol(self._current_chart_symbol() or getattr(self, "symbol", ""))
            if normalized == selected and selected:
                return (0, 0)
            if normalized in available_set:
                return (1, available_symbols.index(normalized))
            return (2, normalized)
        if scope == "watchlist":
            if checked or normalized in self.autotrade_watchlist:
                return (0, normalized)
            if normalized in available_set:
                return (1, available_symbols.index(normalized))
            return (2, normalized)
        if scope == "ranked":
            ranked_symbols = []
            resolver = getattr(getattr(self, "controller", None), "get_best_ranked_autotrade_symbols", None)
            if callable(resolver):
                try:
                    ranked_symbols = [
                        self._normalized_symbol(item)
                        for item in resolver(available_symbols=available_symbols)
                        if self._normalized_symbol(item)
                    ]
                except Exception:
                    ranked_symbols = []
            if normalized in ranked_symbols:
                return (0, ranked_symbols.index(normalized))
            if normalized in available_set:
                return (1, available_symbols.index(normalized))
            return (2, normalized)
        return (9, normalized)

    def _reorder_market_watch_rows(self):
        if not hasattr(self, "symbols_table") or self.symbols_table is None:
            return
        row_count = self.symbols_table.rowCount()
        if row_count <= 1:
            return

        snapshots = [self._market_watch_row_snapshot(row) for row in range(row_count)]
        checked_symbols = {
            self._normalized_symbol(item.get("symbol", ""))
            for item in snapshots
            if item.get("checked")
        }
        snapshots.sort(
            key=lambda item: (
                self._market_watch_priority_rank(item.get("symbol", ""), item.get("checked", False)),
                self._normalized_symbol(item.get("symbol", "")),
            )
        )

        self.autotrade_watchlist = {symbol for symbol in checked_symbols if symbol}
        blocked = self.symbols_table.blockSignals(True)
        previous_updates_enabled = None
        try:
            previous_updates_enabled = bool(self.symbols_table.updatesEnabled())
        except Exception:
            previous_updates_enabled = None

        try:
            self.symbols_table.setUpdatesEnabled(False)
            self.symbols_table.setRowCount(len(snapshots))
            self._market_watch_row_cache = {}
            for row, snapshot in enumerate(snapshots):
                self._set_market_watch_row(
                    row,
                    snapshot.get("symbol", ""),
                    bid=snapshot.get("bid", "-"),
                    ask=snapshot.get("ask", "-"),
                    status=snapshot.get("status", "-"),
                    usd_value=snapshot.get("usd_value", "-"),
                )
        finally:
            self.symbols_table.blockSignals(blocked)
            try:
                if previous_updates_enabled is not None:
                    self.symbols_table.setUpdatesEnabled(previous_updates_enabled)
                else:
                    self.symbols_table.setUpdatesEnabled(True)
            except Exception:
                pass
        self._rebuild_market_watch_row_cache()

    def _autotrade_scope_label(self):
        resolver = getattr(getattr(self, "controller", None), "_autotrade_scope_display_name", None)
        if callable(resolver):
            try:
                return str(resolver(self.autotrade_scope_value or "all") or "All Symbols")
            except Exception:
                pass
        labels = {
            "all": "All Symbols",
            "selected": "Selected Symbol",
            "watchlist": "Watchlist",
            "ranked": "Best Ranked",
        }
        return labels.get(str(self.autotrade_scope_value or "all").lower(), "All Symbols")

    def _apply_autotrade_scope(self, scope):
        normalizer = getattr(getattr(self, "controller", None), "_normalize_autotrade_scope", None)
        if callable(normalizer):
            try:
                normalized = str(normalizer(scope) or "all").strip().lower()
            except Exception:
                normalized = str(scope or "all").strip().lower()
        else:
            normalized = str(scope or "all").strip().lower()
        if normalized not in {"all", "selected", "watchlist", "ranked"}:
            normalized = "all"
        self.autotrade_scope_value = normalized
        if hasattr(self.controller, "set_autotrade_scope"):
            self.controller.set_autotrade_scope(normalized)
        self.settings.setValue("autotrade/scope", normalized)
        if self.autotrade_scope_picker is not None:
            index = self.autotrade_scope_picker.findData(normalized)
            if index >= 0 and self.autotrade_scope_picker.currentIndex() != index:
                blocked = self.autotrade_scope_picker.blockSignals(True)
                self.autotrade_scope_picker.setCurrentIndex(index)
                self.autotrade_scope_picker.blockSignals(blocked)
            self.autotrade_scope_picker.setToolTip(
                "Choose whether AI trading scans all loaded symbols, only the active symbol, checked watchlist symbols, or the broker's best-ranked candidates."
            )
        self._update_autotrade_button()
        if hasattr(self, "status_labels"):
            self._refresh_terminal()
        self._reorder_market_watch_rows()

    def _change_autotrade_scope(self):
        if self.autotrade_scope_picker is None:
            return
        self._apply_autotrade_scope(self.autotrade_scope_picker.currentData())
        if hasattr(self, "system_console"):
            self.system_console.log(f"AI auto trade scope set to {self._autotrade_scope_label()}.", "INFO")

    def _stable_usd_assets(self):
        return {"USD", "USDC", "USDT", "USDP", "FDUSD", "TUSD", "BUSD"}

    def _ticker_mid_price(self, ticker):
        if not isinstance(ticker, dict):
            return None

        try:
            bid = float(ticker.get("bid") or ticker.get("bidPrice") or ticker.get("bp") or 0)
            ask = float(ticker.get("ask") or ticker.get("askPrice") or ticker.get("ap") or 0)
            last = float(ticker.get("last") or ticker.get("price") or 0)
        except (TypeError, ValueError):
            return None

        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        if last > 0:
            return last
        if bid > 0:
            return bid
        if ask > 0:
            return ask
        return None

    def _lookup_symbol_mid_price_from_stream(self, symbol):
        ticker_stream = getattr(self.controller, "ticker_stream", None)
        if ticker_stream is None:
            return None
        ticker = ticker_stream.get(symbol)
        return self._ticker_mid_price(ticker)

    def _asset_to_usd_rate(self, asset_code):
        code = str(asset_code or "").upper().strip()
        if not code:
            return None
        if code in self._stable_usd_assets():
            return 1.0

        for stable in sorted(self._stable_usd_assets()):
            direct = self._lookup_symbol_mid_price(f"{code}/{stable}")
            if direct and direct > 0:
                return direct

            inverse = self._lookup_symbol_mid_price(f"{stable}/{code}")
            if inverse and inverse > 0:
                return 1.0 / inverse

        return None

    def _stellar_usd_value(self, symbol, bid, ask):
        if not self._is_stellar_market_watch():
            return None
        if not isinstance(symbol, str) or "/" not in symbol:
            return None

        try:
            mid = (float(bid) + float(ask)) / 2.0
        except (TypeError, ValueError):
            return None
        if mid <= 0:
            return None

        _base, quote = symbol.upper().split("/", 1)
        quote_to_usd = self._asset_to_usd_rate(quote)
        if quote_to_usd is None:
            return None
        return mid * quote_to_usd

    def _format_market_watch_number(self, value):
        if value is None:
            return "-"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "-"
        if numeric >= 1000:
            return f"{numeric:,.2f}"
        if numeric >= 1:
            return f"{numeric:,.4f}"
        return f"{numeric:,.6f}"

    def _format_market_watch_usd(self, value):
        if value is None:
            return "-"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "-"
        if numeric >= 1000:
            return f"${numeric:,.2f}"
        if numeric >= 1:
            return f"${numeric:,.4f}"
        return f"${numeric:,.6f}"

    def _is_qt_object_alive(self, obj):
        try:
            validator = getattr(shiboken6, "isValid", lambda *_: False)
            if obj is None:
                return False
            return bool(validator(obj))
        except (AttributeError, TypeError, RuntimeError):
            return False

    def _chart_tabs_ready(self):
        return (not self._ui_shutting_down) and self._is_qt_object_alive(
            getattr(self, "chart_tabs", None)
        )

    def _iter_detached_chart_pages(self):
        windows = getattr(self, "detached_tool_windows", {}) or {}
        pages = []
        stale_keys = []

        for key, window in windows.items():
            if not self._is_qt_object_alive(window):
                stale_keys.append(key)
                continue
            if not getattr(window, "_contains_chart_page", False):
                continue
            try:
                page = window.centralWidget()
            except (AttributeError, RuntimeError):
                page = None
            if page is not None:
                pages.append(page)

        for key in stale_keys:
            windows.pop(key, None)

        return pages

    def _chart_widgets_in_page(self, page):
        """Return all ChartWidget instances inside a page or window UI element."""
        if page is None:
            return []
        if isinstance(page, ChartWidget):
            return [page]
        try:
            return list(page.findChildren(ChartWidget))
        except Exception as e:
            self.logger.error(f"Error finding chart widgets in page: {e}")
            return []

    def _is_multi_chart_page(self, page):
        """Return True when the page is a grouped multi-chart layout."""
        if page is None:
            return False
        try:
            return str(page.objectName() or "") == "multi_chart_page"
        except Exception as e:
            self.logger.error(f"Error checking multi-chart page: {e}")
            return False

    def _normalized_chart_symbols(self, symbols, max_count=4):
        """Normalize a list of chart symbols uppercase, trimming duplicates and capping the count."""
        normalized = []
        for symbol in symbols or []:
            value = str(symbol or "").strip().upper()
            if not value or value in normalized:
                continue
            normalized.append(value)
            if len(normalized) >= max_count:
                break
        return normalized

    def _multi_chart_symbols(self, max_count=4):
        """Generate a prioritized set of chart symbols used for multi-chart layout creation."""
        candidates = []

        current_symbol = self._current_chart_symbol() or getattr(self, "symbol", "")
        if current_symbol:
            candidates.append(current_symbol)

        for chart in self._all_chart_widgets():
            candidates.append(getattr(chart, "symbol", ""))

        for symbol in sorted(getattr(self, "autotrade_watchlist", set()) or set()):
            candidates.append(symbol)

        for symbol in getattr(self.controller, "symbols", []) or []:
            candidates.append(symbol)

        return self._normalized_chart_symbols(candidates, max_count=max_count)

    def _multi_chart_window_key(self, symbols, timeframe):
        """Create a working key for multi-chart windows to remember layout/restoration state."""
        safe_symbols = "_".join(
            symbol.replace("/", "_").replace(":", "_")
            for symbol in self._normalized_chart_symbols(symbols, max_count=4)
        )
        safe_timeframe = str(timeframe or self.current_timeframe or "1h").strip().lower().replace("/", "_")
        return f"multi_chart_{safe_timeframe}_{safe_symbols or 'group'}"

    def _find_multi_chart_tab(self, symbols, timeframe):
        """Find the index of an existing multi-chart tab matching target symbols and timeframe."""
        if not self._chart_tabs_ready():
            return -1

        target_symbols = self._normalized_chart_symbols(symbols, max_count=4)
        target_timeframe = str(timeframe or self.current_timeframe or "1h").strip().lower() or "1h"
        if not target_symbols:
            return -1

        try:
            count = self.chart_tabs.count()
        except RuntimeError:
            return -1

        for index in range(count):
            try:
                page = self.chart_tabs.widget(index)
            except RuntimeError:
                break
            if not self._is_multi_chart_page(page):
                continue
            page_symbols = self._normalized_chart_symbols(
                getattr(page, "_terminal_multi_chart_symbols", None)
                or [getattr(chart, "symbol", "") for chart in self._chart_widgets_in_page(page)],
                max_count=4,
            )
            page_timeframe = str(
                getattr(page, "_terminal_multi_chart_timeframe", None)
                or target_timeframe
            ).strip().lower() or target_timeframe
            if page_symbols == target_symbols and page_timeframe == target_timeframe:
                return index
        return -1

    def _build_multi_chart_page(self, symbols, timeframe):
        """Create and return a QWidget containing up to four linked ChartWidgets."""
        normalized_symbols = self._normalized_chart_symbols(symbols, max_count=4)
        if not normalized_symbols:
            return None

        normalized_tf = str(timeframe or self.current_timeframe or "1h").strip().lower() or "1h"
        page = _MultiChartPage()
        page.setObjectName("multi_chart_page")
        setattr(page, "_detach_window_key", self._multi_chart_window_key(normalized_symbols, normalized_tf))
        setattr(page, "_terminal_multi_chart_symbols", list(normalized_symbols))
        setattr(page, "_terminal_multi_chart_timeframe", normalized_tf)

        layout = QGridLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        column_count = 1 if len(normalized_symbols) == 1 else 2
        row_count = int(np.ceil(len(normalized_symbols) / column_count))
        for row in range(row_count):
            layout.setRowStretch(row, 1)
        for column in range(column_count):
            layout.setColumnStretch(column, 1)

        for index, symbol in enumerate(normalized_symbols):
            chart = ChartWidget(
                symbol,
                normalized_tf,
                self.controller,
                candle_up_color=self.candle_up_color,
                candle_down_color=self.candle_down_color,
                show_volume_panel=getattr(self, "show_chart_volume", False),
                chart_background=getattr(self, "chart_background_color", "#11161f"),
                grid_color=getattr(self, "chart_grid_color", "#8290a0"),
                axis_color=getattr(self, "chart_axis_color", "#9aa4b2"),
            )
            self._configure_chart_widget(chart)
            chart.setMinimumHeight(300)
            row = index // column_count
            column = index % column_count
            layout.addWidget(chart, row, column)

        return page

    def _close_multi_chart_pages(self):
        """Close and clean up all multi-chart tabs and detached windows."""
        if self._chart_tabs_ready():
            for index in reversed(range(self.chart_tabs.count())):
                page = self.chart_tabs.widget(index)
                if self._is_multi_chart_page(page):
                    self._close_chart_tab(index)

        for key, window in list((getattr(self, "detached_tool_windows", {}) or {}).items()):
            if not self._is_qt_object_alive(window):
                self.detached_tool_windows.pop(key, None)
                continue
            if not getattr(window, "_contains_chart_page", False):
                continue
            page = getattr(window, "centralWidget", lambda: None)()
            if not self._is_multi_chart_page(page):
                continue
            self.detached_tool_windows.pop(key, None)
            window._contains_chart_page = False
            try:
                window.close()
            except (RuntimeError, AttributeError):
                pass
            try:
                window.deleteLater()
            except (RuntimeError, AttributeError):
                pass

    def _set_active_chart_widget(self, chart, refresh_orderbook=False):
        """Mark a specific ChartWidget as active and update UI state accordingly."""
        if not isinstance(chart, ChartWidget) or not self._is_qt_object_alive(chart):
            return

        self._active_chart_widget_ref = chart
        self.current_timeframe = str(getattr(chart, "timeframe", self.current_timeframe) or self.current_timeframe)
        self.controller.time_frame = self.current_timeframe
        self.settings.setValue("terminal/current_timeframe", self.current_timeframe)
        self._set_active_timeframe_button(self.current_timeframe)

        symbol = str(getattr(chart, "symbol", "") or "").strip().upper()
        if symbol and self.symbol_picker is not None:
            self.symbol_picker.setCurrentText(symbol)

        page = self._chart_page_for_widget(chart)
        if page is not None and self._chart_tabs_ready():
            try:
                index = self.chart_tabs.indexOf(page)
            except RuntimeError:
                index = -1
            if index >= 0 and self.chart_tabs.currentIndex() != index:
                self.chart_tabs.setCurrentIndex(index)

        self._last_chart_request_key = (symbol, self.current_timeframe)
        if refresh_orderbook:
            self._request_active_orderbook()

    def _preferred_chart_in_page(self, page):
        """Return the currently active chart in a page or the first chart as fallback."""
        charts = self._chart_widgets_in_page(page)
        if not charts:
            return None

        active_chart = getattr(self, "_active_chart_widget_ref", None)
        if isinstance(active_chart, ChartWidget) and self._is_qt_object_alive(active_chart):
            for chart in charts:
                if chart is active_chart:
                    return chart
        return charts[0]

    def _chart_page_for_widget(self, target_chart):
        """Find the parent page or tab that contains the given ChartWidget."""
        if target_chart is None:
            return None
        if isinstance(target_chart, ChartWidget):
            for page in self._iter_detached_chart_pages():
                if target_chart in self._chart_widgets_in_page(page):
                    return page
            if self._chart_tabs_ready():
                try:
                    count = self.chart_tabs.count()
                except RuntimeError:
                    count = 0
                for index in range(count):
                    try:
                        page = self.chart_tabs.widget(index)
                    except RuntimeError:
                        break
                    if target_chart in self._chart_widgets_in_page(page):
                        return page
            return target_chart
        return None

    def _all_chart_widgets(self):
        """Collect all active ChartWidget objects from tabs and detached windows."""
        charts = []
        if self._chart_tabs_ready():
            try:
                count = self.chart_tabs.count()
            except RuntimeError:
                count = 0

            for index in range(count):
                try:
                    page = self.chart_tabs.widget(index)
                except RuntimeError:
                    break
                charts.extend(self._chart_widgets_in_page(page))

        for page in self._iter_detached_chart_pages():
            charts.extend(self._chart_widgets_in_page(page))
        return charts

    def _single_chart_window_key(self, symbol, timeframe):
        """Generate a stable key for a single chart window state based on symbol/timeframe."""
        safe_symbol = str(symbol or "").upper().replace("/", "_").replace(":", "_")
        safe_timeframe = str(timeframe or "").lower().replace("/", "_")
        return f"chart_{safe_symbol}_{safe_timeframe}"

    def _detached_chart_windows(self):
        """List all currently detached chart windows that are still valid."""
        windows = []
        for window in self.detached_tool_windows.values():
            if not self._is_qt_object_alive(window):
                continue
            if getattr(window, "_contains_chart_page", False):
                windows.append(window)
        return windows

    def _find_detached_chart_window(self, symbol=None, timeframe=None) -> Any | None:
        """Find a detached chart window matching symbol/timeframe if present."""
        target_symbol = str(symbol or "").upper().strip() if symbol else None
        target_timeframe = str(timeframe or "").strip() if timeframe else None
        for window in self._detached_chart_windows():
            charts = self._chart_widgets_in_page(getattr(window, "centralWidget", lambda: None)())
            if not charts:
                continue
            chart = charts[0]
            if target_symbol and str(chart.symbol).upper() != target_symbol:
                continue
            if target_timeframe and str(chart.timeframe) != target_timeframe:
                continue
            return window
        return None

    def _active_detached_chart_window(self):
        """Return the active detached chart window, if there is exactly one or the active window."""
        active_window = QApplication.activeWindow()
        if active_window is not None and getattr(active_window, "_contains_chart_page", False):
            return active_window
        detached_windows = self._detached_chart_windows()
        if len(detached_windows) == 1:
            return detached_windows[0]
        return None

    def _install_chart_window_actions(self, window):
        """Install the terminal action shortcuts to a detached window context."""
        if window is None or not self._is_qt_object_alive(window):
            return
        if getattr(window, "_chart_actions_installed", False):
            return

        for action_name in (
            "action_reattach_chart",
            "action_tile_charts",
            "action_cascade_charts",
            "action_refresh_chart",
            "action_refresh_orderbook",
        ):
            action = getattr(self, action_name, None)
            if action is not None:
                window.addAction(action)

        window._chart_actions_installed = True

    def _detached_chart_layouts(self):
        """Serialize geometry and symbol data for detached chart windows."""
        layouts = []
        for window in self._detached_chart_windows():
            page = getattr(window, "centralWidget", lambda: None)()
            charts = self._chart_widgets_in_page(page)
            if not charts:
                continue
            geometry = window.geometry()
            layout = {
                "timeframe": str(getattr(charts[0], "timeframe", self.current_timeframe)),
                "x": int(geometry.x()),
                "y": int(geometry.y()),
                "width": int(geometry.width()),
                "height": int(geometry.height()),
            }
            if len(charts) > 1 or self._is_multi_chart_page(page):
                layout["kind"] = "group"
                layout["symbols"] = [str(chart.symbol) for chart in charts]
            else:
                layout["symbol"] = str(charts[0].symbol)
            layouts.append(layout)
        return layouts

    def _save_detached_chart_layouts(self):
        """Persist the current detached chart window geometries to settings."""
        try:
            self.settings.setValue("charts/detached_layouts", json.dumps(self._detached_chart_layouts()))
        except (TypeError, ValueError, OSError) as exc:
            self.logger.debug("Unable to save detached chart layouts: %s", exc)

    def _restore_detached_chart_layouts(self):
        """Restore detached chart windows from saved geometry and layout data."""
        raw_value = self.settings.value("charts/detached_layouts", "[]")
        try:
            layouts = json.loads(_json_text(raw_value, "[]"))
        except (json.JSONDecodeError, TypeError, ValueError):
            layouts = []

        if not isinstance(layouts, list):
            return

        for entry in layouts:
            if not isinstance(entry, dict):
                continue
            timeframe = str(entry.get("timeframe") or "").strip() or self.current_timeframe
            symbols = self._normalized_chart_symbols(entry.get("symbols") or [], max_count=4)
            symbol = str(entry.get("symbol") or "").strip().upper()
            if not symbol:
                symbol = symbols[0] if symbols else ""
            try:
                x = int(entry.get("x", 0))
                y = int(entry.get("y", 0))
                width = max(360, int(entry.get("width", 1200)))
                height = max(260, int(entry.get("height", 780)))
            except Exception as exc:
                self.logger.debug("Invalid geometry in detached chart layout entry: %s", exc)
                x, y, width, height = 0, 0, 1200, 780
            geometry = QRect(x, y, width, height)
            if str(entry.get("kind") or "").strip().lower() == "group" and symbols:
                self._open_or_focus_detached_chart_group(symbols, timeframe, geometry=geometry)
            elif symbol:
                self._open_or_focus_detached_chart(symbol, timeframe, geometry=geometry)

    def _reattach_chart_window(self, window):
        """Move a detached chart window back into the main chart tab view."""
        if window is None or not self._is_qt_object_alive(window):
            return
        if not getattr(window, "_contains_chart_page", False):
            return

        page = window.takeCentralWidget()
        if page is None:
            return

        title = self._chart_page_title(page)
        page.setParent(None)
        self.chart_tabs.addTab(page, title)
        self.chart_tabs.setCurrentWidget(page)
        charts = self._chart_widgets_in_page(page)
        if charts:
            self._set_active_chart_widget(charts[0])
        for chart in charts:
            self._schedule_chart_data_refresh(chart)
        self._request_active_orderbook()
        window._contains_chart_page = False
        window.close()
        window.deleteLater()
        self._save_detached_chart_layouts()

    def _iter_chart_widgets(self):
        charts = []
        if self._chart_tabs_ready():
            try:
                count = self.chart_tabs.count()
            except RuntimeError:
                count = 0

            for index in range(count):
                try:
                    page = self.chart_tabs.widget(index)
                except RuntimeError:
                    break
                charts.extend(self._chart_widgets_in_page(page))

        for page in self._iter_detached_chart_pages():
            charts.extend(self._chart_widgets_in_page(page))
        return charts

    def _current_chart_widget(self):
        active_chart = getattr(self, "_active_chart_widget_ref", None)
        if isinstance(active_chart, ChartWidget) and self._is_qt_object_alive(active_chart):
            page = self._chart_page_for_widget(active_chart)
            if page is not None:
                active_window = QApplication.activeWindow()
                if active_window is not None and active_window is not self:
                    active_page = getattr(active_window, "centralWidget", lambda: None)()
                    if active_page is page or active_chart in self._chart_widgets_in_page(active_page):
                        return active_chart
                if self._chart_tabs_ready():
                    try:
                        current_page = self.chart_tabs.currentWidget()
                    except RuntimeError:
                        current_page = None
                    if current_page is page or active_chart in self._chart_widgets_in_page(current_page):
                        return active_chart

        active_window = QApplication.activeWindow()
        if active_window is not None and active_window is not self:
            charts = self._chart_widgets_in_page(getattr(active_window, "centralWidget", lambda: None)())
            if charts:
                return charts[0]

        if self._chart_tabs_ready():
            try:
                page = self.chart_tabs.currentWidget()
            except RuntimeError:
                page = None
            charts = self._chart_widgets_in_page(page)
            if charts:
                return charts[0]

        detached_pages = self._iter_detached_chart_pages()
        if detached_pages:
            charts = self._chart_widgets_in_page(detached_pages[0])
            if charts:
                return charts[0]

        return None

    def _safe_disconnect(self, signal, slot):
        if signal is None or slot is None:
            return False
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"Failed to disconnect .*",
                    category=RuntimeWarning,
                )
                signal.disconnect(slot)
            return True
        except (RuntimeError, TypeError):
            return False

    def _disconnect_controller_signals(self):
        bindings = list(getattr(self, "_controller_signal_bindings", []) or [])
        self._controller_signal_bindings = []
        for signal, slot in bindings:
            self._safe_disconnect(signal, slot)

    def _timeframe_button_style(self):
        return """
            QPushButton {
                background-color: #162033;
                color: #c7d2e0;
                border: 1px solid #25314a;
                border-radius: 9px;
                padding: 6px 12px;
                font-weight: 600;
                min-width: 44px;
            }
            QPushButton:hover {
                background-color: #1d2940;
                border-color: #3c537f;
            }
            QPushButton:checked {
                background-color: #2a7fff;
                color: white;
                border-color: #65a3ff;
            }
        """

    def _action_button_style(self):
        return """
            QPushButton {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1c2940;
                border-color: #4f638d;
            }
        """

    def _danger_button_style(self):
        return """
            QPushButton {
                background-color: #3a1014;
                color: #ffd7db;
                border: 1px solid #8d3f49;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #4d151c;
                border-color: #c25f6d;
            }
        """

    def _session_badge_style(self, live=False):
        background = "#4a151b" if live else "#123126"
        border = "#d36b77" if live else "#2b8d68"
        text = "#ffe4e7" if live else "#d9ffee"
        return (
            "QLabel { "
            f"background-color: {background}; color: {text}; border: 1px solid {border}; "
            "border-radius: 12px; padding: 8px 14px; font-weight: 800; letter-spacing: 0.5px; }"
        )

    def _live_trading_bar_style(self, armed=False):
        frame_background = "#301117" if armed else "#24161a"
        frame_border = "#de6b7f" if armed else "#805760"
        label_color = "#ffe3e8" if armed else "#d8b9c0"
        chunk_color = "#ff6b81" if armed else "#b85b69"
        return (
            "QFrame { "
            f"background-color: {frame_background}; border: 1px solid {frame_border}; border-radius: 14px; "
            "}"
            "QLabel { "
            f"color: {label_color}; font-size: 11px; font-weight: 800; letter-spacing: 0.8px; "
            "padding: 0 2px; border: 0; background: transparent; }"
            "QProgressBar { "
            "background-color: #12070a; border: 1px solid #5d3139; border-radius: 6px; "
            "padding: 0; min-height: 10px; max-height: 10px; }"
            "QProgressBar::chunk { "
            f"background-color: {chunk_color}; border-radius: 5px; margin: 1px; "
            "}"
        )

    def _desk_status_frame_style(self, tone="idle"):
        palette = {
            "idle": {
                "background": "#101827",
                "border": "#2b3954",
                "title": "#8fa3c2",
                "primary": "#eef4ff",
                "secondary": "#b7c6db",
            },
            "live": {
                "background": "#10211f",
                "border": "#2f8b73",
                "title": "#8ed6c4",
                "primary": "#ebfff8",
                "secondary": "#bfe7dc",
            },
            "alert": {
                "background": "#2a1117",
                "border": "#be5d71",
                "title": "#ffb7c5",
                "primary": "#fff0f3",
                "secondary": "#f1c8d1",
            },
        }.get(str(tone or "idle").lower(), None) or {
            "background": "#101827",
            "border": "#2b3954",
            "title": "#8fa3c2",
            "primary": "#eef4ff",
            "secondary": "#b7c6db",
        }
        return (
            "QFrame { "
            f"background-color: {palette['background']}; border: 1px solid {palette['border']}; border-radius: 16px; "
            "}"
            "QLabel { background: transparent; border: 0; }"
            "QLabel#desk_status_title { "
            f"color: {palette['title']}; font-size: 10px; font-weight: 800; letter-spacing: 1.1px; "
            "}"
            "QLabel#desk_status_primary { "
            f"color: {palette['primary']}; font-size: 13px; font-weight: 800; "
            "}"
            "QLabel#desk_status_secondary { "
            f"color: {palette['secondary']}; font-size: 11px; font-weight: 600; "
            "}"
        )

    def _desk_notification_summary(self):
        controller = getattr(self, "controller", None)
        if not bool(getattr(controller, "trade_close_notifications_enabled", False)):
            return "Alerts off"
        channels = []
        if bool(getattr(controller, "trade_close_notify_telegram", False)):
            channels.append("Telegram")
        if bool(getattr(controller, "trade_close_notify_email", False)):
            channels.append("Email")
        if bool(getattr(controller, "trade_close_notify_sms", False)):
            channels.append("SMS")
        if not channels:
            return "Alerts on"
        return f"Alerts: {', '.join(channels)}"

    def _update_desk_status_panel(self):
        frame = getattr(self, "desk_status_frame", None)
        title_label = getattr(self, "desk_status_title_label", None)
        primary_label = getattr(self, "desk_status_primary_label", None)
        secondary_label = getattr(self, "desk_status_secondary_label", None)
        if frame is None or title_label is None or primary_label is None or secondary_label is None:
            return

        controller = getattr(self, "controller", None)
        live_mode = bool(getattr(controller, "is_live_mode", lambda: False)())
        emergency_stop = bool(getattr(controller, "is_emergency_stop_active", lambda: False)())
        autotrading_live = bool(getattr(self, "autotrading_enabled", False))
        scope_label = Terminal._autotrade_scope_label(self)
        session_label = str(getattr(self, "bound_session_label", "") or getattr(self, "bound_session_id", "") or "").strip()
        account_label = str(getattr(controller, "current_account_label", lambda: "Account not set")() or "").strip() or "Account not set"
        exchange_label = (Terminal._active_exchange_name(self) or "broker").upper()
        mode_label = "LIVE" if live_mode else "PAPER"
        news_label = "on" if bool(getattr(controller, "news_enabled", False)) else "off"
        model_label = str(getattr(controller, "openai_model", "") or "").strip() or "not set"
        model_display = Terminal._elide_text(self, model_label, max_length=18)
        alerts_summary = Terminal._desk_notification_summary(self)

        if emergency_stop:
            desk_title = "DESK LOCKDOWN"
            tone = "alert"
        elif live_mode and autotrading_live:
            desk_title = "LIVE EXECUTION"
            tone = "live"
        else:
            desk_title = "DESK STATUS"
            tone = "idle"

        primary_segments = []
        if session_label:
            primary_segments.append(Terminal._elide_text(self, session_label, max_length=18))
        primary_segments.append(f"{mode_label} {exchange_label}")
        primary_segments.append(Terminal._elide_text(self, account_label, max_length=22))
        primary_text = " | ".join(primary_segments)

        ai_summary = f"AI live on {scope_label}" if autotrading_live else f"AI idle on {scope_label}"
        guard_summary = "Kill switch on" if emergency_stop else "Kill switch clear"
        secondary_text = " | ".join(
            [
                ai_summary,
                guard_summary,
                alerts_summary,
                f"News {news_label}",
                f"Model {model_display}",
            ]
        )

        title_label.setText(desk_title)
        primary_label.setText(primary_text)
        secondary_label.setText(secondary_text)
        frame.setStyleSheet(Terminal._desk_status_frame_style(self, tone=tone))
        frame.setToolTip(
            "\n".join(
                [
                    f"Session: {session_label or 'Main desk'}",
                    f"Mode: {mode_label}",
                    f"Broker: {exchange_label}",
                    f"Account: {account_label}",
                    f"AI scope: {scope_label}",
                    f"AI trading: {'enabled' if autotrading_live else 'disabled'}",
                    f"Emergency stop: {'active' if emergency_stop else 'clear'}",
                    alerts_summary,
                    f"News feed: {news_label}",
                    f"OpenAI model: {model_label}",
                ]
            )
        )

    def _detached_tool_window_style(self):
        return (
            "QMainWindow { background-color: #08111d; }"
            "QLabel { color: #dce7f8; }"
            "QFrame#tool_window_hero { "
            "background-color: #101a2d; border: 1px solid #22344f; border-radius: 16px; "
            "}"
            "QLabel#tool_window_hero_title { color: #f4f8ff; font-size: 20px; font-weight: 800; }"
            "QLabel#tool_window_hero_body { color: #c9d5e8; font-size: 13px; font-weight: 600; }"
            "QLabel#tool_window_summary_card { "
            "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
            "border-radius: 14px; padding: 12px; font-size: 13px; font-weight: 600; "
            "}"
            "QLabel#tool_window_section_hint { color: #8fa7c6; padding-top: 2px; }"
            "QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit { "
            "background-color: #0f1726; color: #e6edf7; border: 1px solid #22344f; border-radius: 10px; "
            "padding: 7px 10px; selection-background-color: #21456f; selection-color: #ffffff; "
            "}"
            "QComboBox::drop-down { border: 0; width: 22px; }"
            "QTextBrowser { "
            "background-color: #0f1726; color: #e6edf7; border: 1px solid #22344f; border-radius: 14px; padding: 14px; "
            "}"
            "QTableWidget, QTableView { "
            "background-color: #0f1726; color: #d9e6f7; border: 1px solid #20324d; border-radius: 12px; "
            "gridline-color: #20324d; alternate-background-color: #0c1421; "
            "}"
            "QHeaderView::section { "
            "background-color: #101c2e; color: #9fb5d3; padding: 8px 10px; border: 0; "
            "border-bottom: 1px solid #22344f; font-weight: 700; "
            "}"
            "QPushButton { "
            "background-color: #162033; color: #d7dfeb; border: 1px solid #2d3a56; border-radius: 12px; "
            "padding: 8px 14px; font-weight: 600; "
            "}"
            "QPushButton:hover { background-color: #1c2940; border-color: #4f638d; }"
            "QTabWidget::pane { border: 1px solid #20324d; background-color: #0b1220; border-radius: 14px; }"
            "QTabBar::tab { "
            "background-color: #101a2d; color: #9fb5d3; padding: 9px 14px; margin-right: 4px; "
            "border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 700; "
            "}"
            "QTabBar::tab:selected { background-color: #163150; color: #ffffff; }"
            "QTabBar::tab:hover:!selected { background-color: #14263e; color: #dce7f8; }"
            "QCheckBox, QRadioButton { color: #dce7f8; spacing: 8px; }"
            "QGroupBox { color: #f1f6ff; font-weight: 700; border: 1px solid #20324d; border-radius: 14px; margin-top: 12px; padding: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #8fa7c6; }"
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #0b1220; width: 12px; margin: 4px; border-radius: 6px; }"
            "QScrollBar::handle:vertical { background: #22344f; min-height: 24px; border-radius: 6px; }"
            "QScrollBar::handle:vertical:hover { background: #32527d; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, "
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; height: 0px; }"
        )

    def _tool_window_text_browser_style(self):
        return (
            "QTextBrowser { "
            "background-color: #0f1726; color: #e6edf7; border: 1px solid #22344f; "
            "border-radius: 14px; padding: 18px; line-height: 1.45; "
            "}"
        )

    def _tool_window_chip_button_style(self):
        return (
            "QPushButton { "
            "background-color:#0f1727; color:#d7dfeb; border:1px solid #24344f; "
            "border-radius:11px; padding:8px 12px; font-weight:700; "
            "}"
            "QPushButton:hover { background-color:#17304d; border-color:#4f638d; }"
        )

    def _tool_window_input_style(self):
        return (
            "QTextEdit { "
            "background-color: #0f1727; color: #f4f8ff; border: 1px solid #24344f; "
            "border-radius: 12px; padding: 12px; selection-background-color: #21456f; selection-color: #ffffff; "
            "}"
        )

    def _build_tool_window_hero(self, title, body, meta=None):
        hero = QFrame()
        hero.setObjectName("tool_window_hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(6)

        title_label = QLabel(str(title or "").strip())
        title_label.setObjectName("tool_window_hero_title")
        hero_layout.addWidget(title_label)

        body_label = QLabel(str(body or "").strip())
        body_label.setWordWrap(True)
        body_label.setObjectName("tool_window_hero_body")
        hero_layout.addWidget(body_label)

        meta_text = str(meta or "").strip()
        meta_label = None
        if meta_text:
            meta_label = QLabel(meta_text)
            meta_label.setObjectName("tool_window_section_hint")
            hero_layout.addWidget(meta_label)

        return hero, title_label, body_label, meta_label

    def _build_tool_window_section_label(self, text):
        label = QLabel(str(text or "").strip())
        label.setObjectName("tool_window_section_hint")
        return label

    def _workspace_tab_style(self):
        return (
            "QTabWidget::pane { border: 1px solid #20324d; background-color: #0b1220; border-radius: 14px; }"
            "QTabBar::tab { "
            "background-color: #101a2d; color: #9fb5d3; padding: 10px 14px; margin-right: 4px; "
            "border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 700; min-width: 120px; "
            "}"
            "QTabBar::tab:selected { background-color: #163150; color: #ffffff; }"
            "QTabBar::tab:hover:!selected { background-color: #14263e; color: #dce7f8; }"
        )

    def _dock_widget_title_style(self):
        return (
            "QDockWidget { color: #dce7f8; font-weight: 700; }"
            "QDockWidget::title { "
            "background-color: #101827; color: #f4f8ff; text-align: left; padding: 8px 12px; "
            "border: 1px solid #22344f; border-bottom: 0; border-top-left-radius: 10px; border-top-right-radius: 10px; "
            "}"
            "QDockWidget::close-button, QDockWidget::float-button { "
            "background-color: #162033; border: 1px solid #2d3a56; border-radius: 7px; padding: 1px; "
            "}"
            "QDockWidget::close-button:hover, QDockWidget::float-button:hover { background-color: #1d2d46; border-color: #4f638d; }"
        )

    def _apply_workspace_tab_chrome(self, tabs):
        is_alive = getattr(self, "_is_qt_object_alive", None)
        if tabs is None or (callable(is_alive) and not is_alive(tabs)):
            return
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        tabs.tabBar().setExpanding(False)
        tabs.setStyleSheet(Terminal._workspace_tab_style(self))

    def _apply_dock_widget_chrome(self, dock):
        is_alive = getattr(self, "_is_qt_object_alive", None)
        if dock is None or (callable(is_alive) and not is_alive(dock)):
            return
        dock.setStyleSheet(Terminal._dock_widget_title_style(self))

    def _configure_tool_form_layout(self, form):
        if form is None:
            return
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def _empty_state_html(self, title, message, hint=None):
        escaped_title = html.escape(str(title or "").strip() or "Nothing here yet")
        escaped_message = html.escape(str(message or "").strip() or "There is no data to show yet.")
        escaped_hint = html.escape(str(hint or "").strip())
        hint_block = f"<p style='margin:10px 0 0 0;color:#8fa7c6;'>{escaped_hint}</p>" if escaped_hint else ""
        return (
            "<div style='background:#101a2d;border:1px solid #20324d;border-radius:16px;padding:18px 20px;'>"
            f"<div style='color:#f4f8ff;font-size:18px;font-weight:800;margin-bottom:8px;'>{escaped_title}</div>"
            f"<div style='color:#d9e6f7;line-height:1.5;'>{escaped_message}</div>"
            f"{hint_block}"
            "</div>"
        )

    def _get_current_venue_type(self):
        """Get the current market venue type (e.g., 'DERIVATIVE', 'SPOT', 'OPTION')."""
        broker = getattr(self.controller, "broker", None)
        if broker is None:
            return "AUTO"
        
        # Get market preference from broker
        market_pref = getattr(broker, "market_preference", "auto")
        market_pref = str(market_pref or "auto").strip().lower()
        
        # Map to display-friendly format
        venue_map = {
            "derivative": "DERIVATIVE",
            "spot": "SPOT",
            "option": "OPTION",
            "otc": "OTC",
            "auto": "AUTO",
        }
        return venue_map.get(market_pref, "AUTO")

    def _update_session_badge(self):
        badge = getattr(self, "session_mode_badge", None)
        if badge is None:
            return
        live = bool(getattr(self.controller, "is_live_mode", lambda: False)())
        mode_text = "LIVE" if live else "PAPER"
        exchange = str(
            getattr(getattr(self.controller, "broker", None), "exchange_name", None)
            or getattr(getattr(getattr(self.controller, "config", None), "broker", None), "exchange", "")
            or ""
        ).upper() or "BROKER"
        
        # Add venue type to badge display
        venue_type = self._get_current_venue_type()
        badge_text = f"{mode_text} | {exchange} | {venue_type}"
        badge.setText(badge_text)
        
        badge.setStyleSheet(self._session_badge_style(live=live))
        account = getattr(self.controller, "current_account_label", lambda: "Not set")()
        badge.setToolTip(f"Mode: {mode_text}\nBroker: {exchange}\nVenue Type: {venue_type}\nAccount: {account}")
        self._update_live_trading_bar()
        self._update_desk_status_panel()

    def _update_live_trading_bar(self):
        frame = getattr(self, "live_trading_bar_frame", None)
        label = getattr(self, "live_trading_bar_label", None)
        bar = getattr(self, "live_trading_bar", None)
        if frame is None or label is None or bar is None:
            return

        live_mode = bool(getattr(self.controller, "is_live_mode", lambda: False)())
        if not live_mode:
            frame.setVisible(False)
            self._update_desk_status_panel()
            return

        frame.setVisible(True)
        armed = bool(self.autotrading_enabled)
        if armed:
            label.setText("LIVE TRADING ACTIVE")
            label.setToolTip("Live session is active and AI trading is currently enabled.")
        else:
            label.setText("LIVE MODE ARMED")
            label.setToolTip("Live broker session is open. AI trading is currently off.")
        frame.setStyleSheet(self._live_trading_bar_style(armed=armed))
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setFormat("")
        self._update_desk_status_panel()


    def _open_stellar_asset_explorer_window(self) -> None:
        """Placeholder for dynamically patched Stellar explorer method."""
        # This method is set via module-level hotfix patching later in the file.
        pass

    def _update_kill_switch_button(self):
        button = getattr(self, "kill_switch_button", None)
        if button is None:
            return
        active = bool(getattr(self.controller, "is_emergency_stop_active", lambda: False)())
        if active:
            button.setText("Resume")
            button.setToolTip("Clear the emergency lock so new orders can be submitted again.")
        else:
            button.setText("Kill Switch")
            button.setToolTip("Stop auto trading, cancel open orders, close tracked positions, and block new entries.")
        self._update_desk_status_panel()

    def _set_active_timeframe_button(self, active_tf):
        for tf, button in self.timeframe_buttons.items():
            button.setChecked(tf == active_tf)

        if self.toolbar_timeframe_label is not None:
            self.toolbar_timeframe_label.setText(
                self._tr("terminal.toolbar.timeframe_active", timeframe=active_tf)
            )
        self._sync_chart_timeframe_menu_actions()

    def _sync_chart_timeframe_menu_actions(self):
        current = str(
            getattr(self, "current_timeframe", getattr(getattr(self, "controller", None), "time_frame", "1h"))
            or "1h"
        ).strip().lower() or "1h"
        for timeframe, action in getattr(self, "chart_timeframe_actions", {}).items():
            try:
                action.blockSignals(True)
                action.setChecked(str(timeframe).strip().lower() == current)
            finally:
                action.blockSignals(False)

    def _autotrade_toolbar_mode(self, available_width=None):
        width = int(available_width or 0)
        if width <= 0:
            toolbar = getattr(self, "secondary_toolbar", None)
            try:
                width = int(toolbar.width() or 0)
            except Exception:
                width = 0
        if width <= 0:
            try:
                width = int(self.width() or 0)
            except Exception:
                width = 0
        if width and width < 460:
            return "tight"
        if width and width < 640:
            return "compact"
        return "full"

    def _refresh_autotrade_controls_layout(self, available_width=None):
        layout = getattr(self, "autotrade_controls_layout", None)
        label = getattr(self, "autotrade_scope_label_widget", None)
        picker = getattr(self, "autotrade_scope_picker", None)
        button = getattr(self, "auto_button", None)
        box = getattr(self, "autotrade_controls_box", None)
        row = getattr(self, "autotrade_controls_row", None)

        mode = Terminal._autotrade_toolbar_mode(self, available_width)
        self._autotrade_toolbar_layout_mode = mode

        if layout is not None:
            if mode == "tight":
                layout.setContentsMargins(6, 4, 6, 4)
                layout.setSpacing(6)
            elif mode == "compact":
                layout.setContentsMargins(8, 5, 8, 5)
                layout.setSpacing(7)
            else:
                layout.setContentsMargins(8, 6, 8, 6)
                layout.setSpacing(8)

        if row is not None:
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if box is not None:
            box.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        if label is not None:
            label.setVisible(mode != "tight")

        if picker is not None:
            picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            if mode == "tight":
                picker.setMinimumContentsLength(6)
                picker.setMinimumWidth(82)
                picker.setMaximumWidth(108)
            elif mode == "compact":
                picker.setMinimumContentsLength(8)
                picker.setMinimumWidth(96)
                picker.setMaximumWidth(128)
            else:
                picker.setMinimumContentsLength(10)
                picker.setMinimumWidth(108)
                picker.setMaximumWidth(148)

        if button is not None:
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            if mode == "tight":
                button.setMinimumWidth(92)
            elif mode == "compact":
                button.setMinimumWidth(126)
            else:
                button.setMinimumWidth(148)

    def _autotrade_button_text(self, enabled, phase=0, mode=None):
        current_mode = str(mode or getattr(self, "_autotrade_toolbar_layout_mode", "full") or "full").lower()
        if enabled:
            if current_mode == "tight":
                return "Stop"
            return "Stop Trading"
        if current_mode == "tight":
            return "Start"
        return "Start Trading"

    def _update_autotrade_button(self):
        refresh_autotrade_controls_layout = getattr(self, "_refresh_autotrade_controls_layout", None)
        if callable(refresh_autotrade_controls_layout):
            refresh_autotrade_controls_layout()
        layout_mode = str(getattr(self, "_autotrade_toolbar_layout_mode", "full") or "full").lower()
        phase = getattr(self, "_spinner_index", 0) % 3
        self.auto_button.setChecked(bool(self.autotrading_enabled))
        if self.autotrading_enabled:
            padding = "8px 12px" if layout_mode == "tight" else "9px 15px" if layout_mode == "compact" else "10px 18px"
            self.auto_button.setText(Terminal._autotrade_button_text(self, True, phase=phase, mode=layout_mode))
            self.auto_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #123524;
                    color: #d7ffe9;
                    border: 2px solid #32d296;
                    border-radius: 14px;
                    padding: %s;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #184630;
                }
                """
                % padding
            )
            self._update_trading_activity_indicator(active=True)
        else:
            padding = "8px 12px" if layout_mode == "tight" else "9px 15px" if layout_mode == "compact" else "10px 18px"
            self.auto_button.setText(Terminal._autotrade_button_text(self, False, mode=layout_mode))
            self.auto_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #34161a;
                    color: #ffd9de;
                    border: 2px solid #b45b68;
                    border-radius: 14px;
                    padding: %s;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #442026;
                }
                """
                % padding
            )
            self._update_trading_activity_indicator(active=False)
        scope_label = self._autotrade_scope_label()
        action_label = "Stop Trading" if self.autotrading_enabled else "Start Trading"
        self.auto_button.setAccessibleName(action_label)
        self.auto_button.setToolTip(
            f"{action_label} for {scope_label}. "
            "When enabled, the bot scans the chosen symbols and sends live signals/orders."
        )
        self._update_live_trading_bar()

    def _update_trading_activity_indicator(self, active=None):
        label = getattr(self, "trading_activity_label", None)
        if label is None:
            return

        is_active = self.autotrading_enabled if active is None else bool(active)
        if not is_active:
            label.setText("AI Idle")
            label.setStyleSheet(
                "color: #8fa7c6; background-color: #132033; border: 1px solid #24324a; "
                "border-radius: 10px; padding: 5px 10px; font-weight: 700;"
            )
            self._update_desk_status_panel()
            return

        phase = getattr(self, "_spinner_index", 0) % 3
        texts = ["AI Live", "AI Live.", "AI Live.."]
        backgrounds = ["#123524", "#184630", "#0f2e22"]
        borders = ["#28a86b", "#32d296", "#1f8f5c"]
        label.setText(texts[phase])
        label.setStyleSheet(
            f"color: #d7ffe9; background-color: {backgrounds[phase]}; border: 1px solid {borders[phase]}; "
            "border-radius: 10px; padding: 5px 10px; font-weight: 700;"
        )
        self._update_desk_status_panel()

    def _setup_ui(self):

        self.chart_tabs = QTabWidget()
        self.chart_tabs.setTabsClosable(True)
        self.chart_tabs.setObjectName("terminal_chart_tabs")

        self.chart_tabs.tabCloseRequested.connect(self._close_chart_tab)
        self.chart_tabs.currentChanged.connect(self._on_chart_tab_changed)
        self.chart_tabs.tabBarDoubleClicked.connect(self._detach_chart_tab)
        self._apply_workspace_tab_chrome(self.chart_tabs)

        self.setCentralWidget(self.chart_tabs)

        self._create_menu_bar()
        self._create_toolbar()

        self._create_chart_tab(
            self.symbol,
            self.controller.time_frame
        )

        self.chart_tabs.setUsesScrollButtons(True)
        self.chart_tabs.tabBar().setExpanding(False)
        self.apply_language()

    # ==========================================================
    # MENU
    # ==========================================================

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.clear()
        menu_bar.setStyleSheet(
            """
            QMenuBar {
                background-color: #0b1220;
                border-bottom: 1px solid #1e2a3f;
                padding: 4px 10px;
                color: #dce7f8;
                spacing: 6px;
                font-weight: 600;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 10px;
                margin: 0 2px;
                border-radius: 8px;
            }
            QMenuBar::item:selected {
                background-color: #132033;
            }
            QMenuBar::item:pressed {
                background-color: #17304f;
            }
            QMenu {
                background-color: #101827;
                border: 1px solid #24324a;
                padding: 6px;
                color: #dce7f8;
            }
            QMenu::item {
                padding: 7px 28px 7px 12px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #17304f;
            }
            QMenu::separator {
                height: 1px;
                background: #24324a;
                margin: 6px 8px;
            }
            """
        )

        self.file_menu = menu_bar.addMenu("")
        self.trading_menu = menu_bar.addMenu("")
        self.strategy_menu = menu_bar.addMenu("")
        self.charts_menu = menu_bar.addMenu("")
        self.data_menu = menu_bar.addMenu("")
        self.settings_menu = menu_bar.addMenu("")
        self.risk_menu = menu_bar.addMenu("")
        self.review_menu = menu_bar.addMenu("")
        self.research_menu = menu_bar.addMenu("")
        self.education_menu = menu_bar.addMenu("")
        self.tools_menu = menu_bar.addMenu("")
        self.help_menu = menu_bar.addMenu("")

        self.language_menu = QMenu(self.settings_menu)
        self.backtest_menu = QMenu(self.strategy_menu)
        self.chart_style_menu = QMenu(self.charts_menu)
        self.chart_studies_menu = QMenu(self.charts_menu)
        self.chart_quick_studies_menu = QMenu(self.chart_studies_menu)
        self.chart_timeframe_menu = QMenu(self.charts_menu)
        self.tools_desk_menu = QMenu(self.tools_menu)
        self.tools_strategy_lab_menu = QMenu(self.tools_menu)
        self.tools_review_lab_menu = QMenu(self.tools_menu)
        self.tools_ops_menu = QMenu(self.tools_menu)
        self.tools_learning_menu = QMenu(self.tools_menu)
        self.chart_timeframe_actions = {}
        self._chart_timeframe_action_group = QActionGroup(self)
        self._chart_timeframe_action_group.setExclusive(True)
        self.analyze_positions_menu = QMenu(self.risk_menu)
        self.analyze_trade_review_menu = QMenu(self.risk_menu)
        self.analyze_desk_menu = QMenu(self.risk_menu)

        self.action_generate_report = QAction(self)
        self.action_generate_report.triggered.connect(self._generate_report)
        self.action_export_trades = QAction(self)
        self.action_export_trades.triggered.connect(self._export_trades)
        self.action_exit = QAction(self)
        self.action_exit.triggered.connect(self.close)

        self.action_start_trading = QAction(self)
        self.action_start_trading.triggered.connect(lambda: self._set_autotrading_enabled(True))
        self.action_start_trading.setShortcut("Ctrl+T")
        self.action_stop_trading = QAction(self)
        self.action_stop_trading.triggered.connect(lambda: self._set_autotrading_enabled(False))
        self.action_manual_trade = QAction(self)
        self.action_manual_trade.triggered.connect(self._open_manual_trade)
        self.action_close_all = QAction(self)
        self.action_close_all.triggered.connect(self._close_all_positions)
        self.action_cancel_orders = QAction(self)
        self.action_cancel_orders.triggered.connect(self._cancel_all_orders)
        self.action_kill_switch = QAction("Emergency Kill Switch", self)
        self.action_kill_switch.triggered.connect(self._toggle_emergency_stop)

        self.action_run_backtest = QAction(self)
        self.action_run_backtest.triggered.connect(
            lambda: asyncio.get_event_loop().create_task(self.run_backtest_clicked())
        )
        self.action_run_backtest.setShortcut("Ctrl+B")
        self.action_new_chart = QAction(self)
        self.action_new_chart.setShortcut("Ctrl+N")
        self.action_new_chart.triggered.connect(self._add_new_chart)
        self.action_multi_chart = QAction(self)
        self.action_multi_chart.triggered.connect(self._multi_chart_layout)
        self.action_detach_chart = QAction("Detach Current Tab", self)
        self.action_detach_chart.setShortcut("Ctrl+Shift+D")
        self.action_detach_chart.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.action_detach_chart.triggered.connect(self._detach_current_chart_tab)
        self.action_reattach_chart = QAction("Reattach Active Chart", self)
        self.action_reattach_chart.setShortcut("Ctrl+Shift+R")
        self.action_reattach_chart.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.action_reattach_chart.triggered.connect(self._reattach_active_chart_window)
        self.action_tile_chart_windows = QAction("Tile Chart Windows", self)
        self.action_tile_chart_windows.setShortcut("Ctrl+Shift+T")
        self.action_tile_chart_windows.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.action_tile_chart_windows.triggered.connect(self._tile_chart_windows)
        self.action_cascade_chart_windows = QAction("Cascade Chart Windows", self)
        self.action_cascade_chart_windows.setShortcut("Ctrl+Shift+C")
        self.action_cascade_chart_windows.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.action_cascade_chart_windows.triggered.connect(self._cascade_chart_windows)
        self.action_candle_colors = QAction(self)
        self.action_candle_colors.triggered.connect(self._choose_candle_colors)
        self.action_chart_settings = QAction("Chart Settings...", self)
        self.action_chart_settings.triggered.connect(self._open_chart_settings)
        self.action_edit_studies = QAction("Edit Studies...", self)
        self.action_edit_studies.triggered.connect(self._open_studies_manager)
        self.action_add_indicator = QAction(self)
        self.action_add_indicator.triggered.connect(self._add_indicator_to_current_chart)
        self.action_remove_indicator = QAction(self)
        self.action_remove_indicator.triggered.connect(self._remove_indicator_from_current_chart)
        self.action_remove_all_indicators = QAction("Remove All Studies", self)
        self.action_remove_all_indicators.triggered.connect(self._remove_all_indicators_from_current_chart)
        self.toggle_bid_ask_lines_action = QAction(self)
        self.toggle_bid_ask_lines_action.setCheckable(True)
        self.toggle_bid_ask_lines_action.setChecked(self.show_bid_ask_lines)
        self.toggle_bid_ask_lines_action.triggered.connect(self._toggle_bid_ask_lines)
        self.toggle_volume_bar_action = QAction(self)
        self.toggle_volume_bar_action.setCheckable(True)
        self.toggle_volume_bar_action.setChecked(getattr(self, "show_chart_volume", False))
        self.toggle_volume_bar_action.triggered.connect(self._toggle_chart_volume)
        self.action_refresh_markets = QAction(self)
        self.action_refresh_markets.triggered.connect(self._refresh_markets)
        self.action_refresh_chart = QAction(self)
        self.action_refresh_chart.triggered.connect(self._refresh_active_chart_data)
        self.action_refresh_orderbook = QAction(self)
        self.action_refresh_orderbook.triggered.connect(self._refresh_active_orderbook)
        self.action_reload_balance = QAction(self)
        self.action_reload_balance.triggered.connect(self._reload_balance)
        self.action_app_settings = QAction(self)
        self.action_app_settings.triggered.connect(self._open_settings)
        self.action_risk_settings = QAction("Risk Settings", self)
        self.action_risk_settings.triggered.connect(self._open_risk_settings)
        self.action_portfolio_view = QAction(self)
        self.action_portfolio_view.triggered.connect(self._show_portfolio_exposure)
        self.language_actions = {}
        for code, label in iter_supported_languages():
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, lang=code: self.controller.set_language(lang))
            self.language_menu.addAction(action)
            self.language_actions[code] = action

        self.action_market_chat = QAction("Sopotek Pilot", self)
        self.action_market_chat.triggered.connect(self._open_market_chat_window)
        self.action_recommendations = QAction("Recommendations", self)
        self.action_recommendations.triggered.connect(self._open_recommendations_window)
        self.action_ml_monitor = QAction(self)
        self.action_ml_monitor.triggered.connect(self._open_ml_monitor)
        self.action_logs = QAction(self)
        self.action_logs.triggered.connect(self._open_logs)
        self.action_export_diagnostics = QAction("Export Diagnostics Bundle", self)
        self.action_export_diagnostics.triggered.connect(self._export_diagnostics_bundle)
        self.action_performance = QAction(self)
        self.action_performance.triggered.connect(self._open_performance)
        self.action_performance.setShortcut("Ctrl+Shift+P")
        self.action_closed_journal = QAction("Closed Journal", self)
        self.action_closed_journal.triggered.connect(self._open_closed_journal_window)
        self.action_trade_checklist = QAction("Trade Checklist", self)
        self.action_trade_checklist.triggered.connect(self._open_trade_checklist_window)
        self.action_trade_checklist.setShortcut("Ctrl+Shift+K")
        self.action_journal_review = QAction("Journal Review", self)
        self.action_journal_review.triggered.connect(self._open_trade_journal_review_window)
        self.action_system_health = QAction("System Health", self)
        self.action_system_health.triggered.connect(self._open_system_health_window)
        self.action_quant_pm = QAction("Quant PM", self)
        self.action_quant_pm.triggered.connect(self._open_quant_pm_window)
        self.action_ml_research = QAction("ML Research Lab", self)
        self.action_ml_research.triggered.connect(self._open_ml_research_window)
        self.action_trader_tv = QAction("Trader TV", self)
        self.action_trader_tv.triggered.connect(self._open_trader_tv_window)
        self.action_education_center = QAction("Education Center", self)
        self.action_education_center.triggered.connect(self._open_education_center_window)
        self.action_position_analysis = QAction("Position Analysis", self)
        self.action_position_analysis.triggered.connect(self._open_position_analysis_window)
        self.action_position_analysis.setShortcut("Ctrl+Shift+I")
        self.action_execution_workspace = QAction("Execution Workspace", self)
        self.action_execution_workspace.triggered.connect(self._open_execution_workspace_dock)
        self.action_execution_orderbook = QAction("Order Book", self)
        self.action_execution_orderbook.triggered.connect(lambda: self._open_execution_workspace_dock("Order Book"))
        self.action_execution_market_trades = QAction("Market Trades", self)
        self.action_execution_market_trades.triggered.connect(lambda: self._open_execution_workspace_dock("Trade"))
        self.action_execution_positions = QAction("Positions", self)
        self.action_execution_positions.triggered.connect(lambda: self._open_execution_workspace_dock("Positions"))
        self.action_execution_open_orders = QAction("Open Orders", self)
        self.action_execution_open_orders.triggered.connect(lambda: self._open_execution_workspace_dock("Open Orders"))
        self.action_execution_order_history = QAction("Order History", self)
        self.action_execution_order_history.triggered.connect(lambda: self._open_execution_workspace_dock("Order History"))
        self.action_execution_trade_history = QAction("Trade History", self)
        self.action_execution_trade_history.triggered.connect(lambda: self._open_execution_workspace_dock("Trade History"))
        self.action_strategy_optimization = QAction("Strategy Optimization", self)
        self.action_strategy_optimization.triggered.connect(self._optimize_strategy)
        self.action_strategy_optimization.setShortcut("Ctrl+Shift+O")
        self.action_strategy_assigner = QAction("Strategy Assigner", self)
        self.action_strategy_assigner.triggered.connect(self._open_strategy_assignment_window)
        self.action_strategy_scorecard = QAction("Strategy Scorecard", self)
        self.action_strategy_scorecard.triggered.connect(self._open_strategy_scorecard_dock)
        self.action_strategy_debug = QAction("Strategy Debug", self)
        self.action_strategy_debug.triggered.connect(self._open_strategy_debug_dock)
        self.action_system_console = QAction("System Console", self)
        self.action_system_console.triggered.connect(self._open_system_console_dock)
        self.action_system_status = QAction("System Status", self)
        self.action_system_status.triggered.connect(self._open_system_status_dock)
        self.action_stellar_asset_explorer = QAction("Stellar Asset Explorer", self)
        self.action_stellar_asset_explorer.triggered.connect(self._open_stellar_asset_explorer_window)

        self.settings_menu.addAction(self.action_app_settings)
        self.settings_menu.addMenu(self.language_menu)
        self.file_menu.addAction(self.action_exit)

        self.trading_menu.addAction(self.action_start_trading)
        self.trading_menu.addAction(self.action_stop_trading)
        self.trading_menu.addAction(self.action_manual_trade)
        self.trading_menu.addSeparator()
        self.trading_menu.addAction(self.action_execution_workspace)
        self.trading_menu.addAction(self.action_execution_orderbook)
        self.trading_menu.addAction(self.action_execution_positions)
        self.trading_menu.addAction(self.action_execution_open_orders)
        self.trading_menu.addAction(self.action_execution_order_history)
        self.trading_menu.addAction(self.action_execution_trade_history)
        self.trading_menu.addSeparator()
        self.trading_menu.addAction(self.action_close_all)
        self.trading_menu.addAction(self.action_cancel_orders)
        self.trading_menu.addSeparator()
        self.trading_menu.addAction(self.action_kill_switch)

        self.backtest_menu.addAction(self.action_run_backtest)
        self.backtest_menu.addAction(self.action_strategy_optimization)
        self.strategy_menu.addMenu(self.backtest_menu)
        self.strategy_menu.addSeparator()
        self.strategy_menu.addAction(self.action_strategy_assigner)
        self.strategy_menu.addAction(self.action_strategy_scorecard)
        self.strategy_menu.addAction(self.action_strategy_debug)

        self.charts_menu.addAction(self.action_new_chart)
        self.charts_menu.addAction(self.action_multi_chart)
        self.charts_menu.addSeparator()
        self.charts_menu.addMenu(self.chart_timeframe_menu)
        self.charts_menu.addMenu(self.chart_style_menu)
        self.charts_menu.addMenu(self.chart_studies_menu)
        self.charts_menu.addSeparator()
        self.charts_menu.addAction(self.action_detach_chart)
        self.charts_menu.addAction(self.action_reattach_chart)
        self.charts_menu.addAction(self.action_tile_chart_windows)
        self.charts_menu.addAction(self.action_cascade_chart_windows)

        self.chart_style_menu.addAction(self.action_chart_settings)
        self.chart_style_menu.addSeparator()
        self.chart_style_menu.addAction(self.action_candle_colors)
        self.chart_style_menu.addAction(self.toggle_bid_ask_lines_action)
        self.chart_style_menu.addAction(self.toggle_volume_bar_action)

        self.chart_studies_menu.addAction(self.action_edit_studies)
        self.chart_studies_menu.addAction(self.action_add_indicator)
        self.chart_studies_menu.addAction(self.action_remove_indicator)
        self.chart_studies_menu.addAction(self.action_remove_all_indicators)
        self.chart_studies_menu.addSeparator()
        self.chart_studies_menu.addMenu(self.chart_quick_studies_menu)

        for label, timeframe in CHART_TIMEFRAME_MENU_OPTIONS:
            timeframe_action = QAction(label, self)
            timeframe_action.setCheckable(True)
            timeframe_action.triggered.connect(
                lambda checked=False, tf=timeframe: self._set_timeframe(tf)
            )
            self._chart_timeframe_action_group.addAction(timeframe_action)
            self.chart_timeframe_menu.addAction(timeframe_action)
            self.chart_timeframe_actions[timeframe] = timeframe_action

        for section_name, studies in CHART_STUDY_MENU_GROUPS:
            section_menu = self.chart_quick_studies_menu.addMenu(section_name)
            for study_name, default_period in studies:
                study_action = QAction(study_name, self)
                study_action.triggered.connect(
                    lambda checked=False, name=study_name, period=default_period: self._add_indicator_to_current_chart(
                        indicator_name=name,
                        preset_period=period,
                        prompt_for_period=False,
                    )
                )
                section_menu.addAction(study_action)

        self.data_menu.addAction(self.action_refresh_markets)
        self.data_menu.addAction(self.action_refresh_chart)
        self.data_menu.addAction(self.action_refresh_orderbook)
        self.data_menu.addSeparator()
        self.data_menu.addAction(self.action_reload_balance)

        self.risk_menu.addMenu(self.analyze_positions_menu)
        self.risk_menu.addMenu(self.analyze_trade_review_menu)
        self.risk_menu.addMenu(self.analyze_desk_menu)

        self.analyze_positions_menu.addAction(self.action_risk_settings)
        self.analyze_positions_menu.addAction(self.action_portfolio_view)
        self.analyze_positions_menu.addAction(self.action_position_analysis)

        self.analyze_trade_review_menu.addAction(self.action_trade_checklist)
        self.analyze_trade_review_menu.addAction(self.action_closed_journal)
        self.analyze_trade_review_menu.addAction(self.action_journal_review)
        self.analyze_trade_review_menu.addAction(self.action_performance)

        self.analyze_desk_menu.addAction(self.action_system_health)
        self.analyze_desk_menu.addAction(self.action_recommendations)
        self.analyze_desk_menu.addAction(self.action_quant_pm)
        self.review_menu.addAction(self.action_performance)
        self.review_menu.addAction(self.action_recommendations)
        self.review_menu.addAction(self.action_closed_journal)
        self.review_menu.addAction(self.action_journal_review)
        self.review_menu.addSeparator()
        self.review_menu.addAction(self.action_generate_report)
        self.review_menu.addAction(self.action_export_trades)

        self.research_menu.addAction(self.action_market_chat)
        self.research_menu.addAction(self.action_quant_pm)
        self.research_menu.addAction(self.action_ml_monitor)
        self.research_menu.addAction(self.action_ml_research)
        self._research_stellar_separator_action = self.research_menu.addSeparator()
        self.research_menu.addAction(self.action_stellar_asset_explorer)

        self.education_menu.addAction(self.action_trader_tv)
        self.education_menu.addAction(self.action_education_center)

        self.tools_menu.addAction(self.action_manual_trade)
        self.tools_menu.addAction(self.action_market_chat)
        self.tools_menu.addAction(self.action_recommendations)
        self.tools_menu.addAction(self.action_performance)
        self.tools_menu.addAction(self.action_position_analysis)
        self.tools_menu.addSeparator()
        self.tools_menu.addMenu(self.tools_desk_menu)
        self.tools_menu.addMenu(self.tools_strategy_lab_menu)
        self.tools_menu.addMenu(self.tools_review_lab_menu)
        self.tools_menu.addMenu(self.tools_ops_menu)
        self.tools_menu.addMenu(self.tools_learning_menu)
        self.tools_menu.addSeparator()
        self.tools_desk_menu.addAction(self.action_manual_trade)
        self.tools_desk_menu.addAction(self.action_execution_workspace)
        self.tools_desk_menu.addAction(self.action_execution_orderbook)
        self.tools_desk_menu.addAction(self.action_execution_positions)
        self.tools_desk_menu.addAction(self.action_execution_open_orders)
        self.tools_desk_menu.addAction(self.action_execution_order_history)
        self.tools_desk_menu.addAction(self.action_execution_trade_history)
        self.tools_desk_menu.addAction(self.action_execution_market_trades)
        self.tools_desk_menu.addSeparator()
        self.tools_desk_menu.addAction(self.action_position_analysis)
        self.tools_desk_menu.addAction(self.action_portfolio_view)
        self.tools_desk_menu.addAction(self.action_risk_settings)
        self.tools_desk_menu.addSeparator()
        self.tools_desk_menu.addAction(self.action_system_status)
        self.tools_desk_menu.addAction(self.action_system_console)

        self.tools_strategy_lab_menu.addAction(self.action_market_chat)
        self.tools_strategy_lab_menu.addAction(self.action_recommendations)
        self.tools_strategy_lab_menu.addAction(self.action_quant_pm)
        self.tools_strategy_lab_menu.addAction(self.action_ml_monitor)
        self.tools_strategy_lab_menu.addAction(self.action_ml_research)
        self.tools_strategy_lab_menu.addSeparator()
        self.tools_strategy_lab_menu.addAction(self.action_strategy_assigner)
        self.tools_strategy_lab_menu.addAction(self.action_strategy_optimization)
        self.tools_strategy_lab_menu.addAction(self.action_strategy_scorecard)
        self.tools_strategy_lab_menu.addAction(self.action_strategy_debug)
        self._tools_stellar_separator_action = self.tools_strategy_lab_menu.addSeparator()
        self.tools_strategy_lab_menu.addAction(self.action_stellar_asset_explorer)

        self.tools_review_lab_menu.addAction(self.action_performance)
        self.tools_review_lab_menu.addAction(self.action_closed_journal)
        self.tools_review_lab_menu.addAction(self.action_journal_review)
        self.tools_review_lab_menu.addAction(self.action_trade_checklist)
        self.tools_review_lab_menu.addSeparator()
        self.tools_review_lab_menu.addAction(self.action_generate_report)
        self.tools_review_lab_menu.addAction(self.action_export_trades)

        self.tools_ops_menu.addAction(self.action_system_health)
        self.tools_menu.addAction(self.action_logs)
        self.tools_ops_menu.addAction(self.action_logs)
        self.tools_ops_menu.addAction(self.action_export_diagnostics)
        self.tools_ops_menu.addSeparator()
        self.tools_ops_menu.addAction(self.action_system_console)
        self.tools_ops_menu.addAction(self.action_system_status)
        self.tools_ops_menu.addSeparator()
        self.tools_ops_menu.addAction(self.action_app_settings)
        self.tools_ops_menu.addAction(self.action_risk_settings)

        self.tools_learning_menu.addAction(self.action_trader_tv)
        self.tools_learning_menu.addAction(self.action_education_center)
        self.tools_learning_menu.addSeparator()
        self.tools_menu.addAction(self.action_export_diagnostics)
        self.tools_menu.addAction(self.action_system_console)
        self.tools_menu.addAction(self.action_system_status)
        self.action_documentation = QAction(self)
        self.action_documentation.triggered.connect(self._open_docs)
        self.help_menu.addAction(self.action_documentation)
        self.action_api_docs = QAction(self)
        self.action_api_docs.triggered.connect(self._open_api_docs)
        self.help_menu.addAction(self.action_api_docs)
        self.education_menu.addSeparator()
        self.education_menu.addAction(self.action_documentation)
        self.education_menu.addAction(self.action_api_docs)
        self.tools_learning_menu.addAction(self.action_documentation)
        self.tools_learning_menu.addAction(self.action_api_docs)
        self.help_menu.addSeparator()
        self.action_about = QAction(self)
        self.action_about.triggered.connect(self._show_about)
        self.help_menu.addAction(self.action_about)

        self._sync_chart_timeframe_menu_actions()
        Terminal._sync_exchange_scoped_actions(self)
        self.apply_language()

    def update_connection_status(self, status: str):
        self.current_connection_status = status

        if status == "connected":
            self.connection_indicator.setText("● CONNECTED")
            self.connection_indicator.setStyleSheet(
                "color: green; font-weight: bold;"
            )
        elif status == "disconnected":
            self.connection_indicator.setText("● DISCONNECTED")
            self.connection_indicator.setStyleSheet(
                "color: red; font-weight: bold;"
            )
        else:
            self.connection_indicator.setText("● CONNECTING")
            self.connection_indicator.setStyleSheet(
                "color: orange; font-weight: bold;"
            )

    def apply_language(self):
        previous_language = getattr(self, "_applied_language_code", None)
        self.setWindowTitle(self._tr("terminal.window_title"))

        if hasattr(self, "file_menu"):
            self.file_menu.setTitle(self._tr("terminal.menu.file"))
            self.trading_menu.setTitle(self._tr("terminal.menu.trading"))
            self.strategy_menu.setTitle(self._tr("terminal.menu.strategy"))
            self.backtest_menu.setTitle(self._tr("terminal.menu.backtesting"))
            self.charts_menu.setTitle(self._tr("terminal.menu.charts"))
            self.data_menu.setTitle(self._tr("terminal.menu.data"))
            self.settings_menu.setTitle(self._tr("terminal.menu.settings"))
            self.risk_menu.setTitle("Analyze")
            self.review_menu.setTitle(self._tr("terminal.menu.review"))
            self.research_menu.setTitle(self._tr("terminal.menu.research"))
            self.education_menu.setTitle("Education")
            self.language_menu.setTitle(self._tr("terminal.menu.language"))
            self.tools_menu.setTitle(self._tr("terminal.menu.tools"))
            self.help_menu.setTitle(self._tr("terminal.menu.help"))
            self.chart_timeframe_menu.setTitle("Time Frame")
            self.chart_style_menu.setTitle("Style")
            self.chart_studies_menu.setTitle("Studies")
            self.chart_quick_studies_menu.setTitle("Quick Studies")
            self.tools_desk_menu.setTitle("Trading Desk")
            self.tools_strategy_lab_menu.setTitle("Strategy Lab")
            self.tools_review_lab_menu.setTitle("Analytics & Review")
            self.tools_ops_menu.setTitle("Desk Ops")
            self.tools_learning_menu.setTitle("Learning & Docs")
            self.analyze_positions_menu.setTitle("Positions & Risk")
            self.analyze_trade_review_menu.setTitle("Trade Review")
            self.analyze_desk_menu.setTitle("Desk & System")

            self.action_generate_report.setText(self._tr("terminal.action.generate_report"))
            self.action_export_trades.setText(self._tr("terminal.action.export_trades"))
            self.action_exit.setText(self._tr("terminal.action.exit"))
            self.action_start_trading.setText(self._tr("terminal.action.start_auto"))
            self.action_stop_trading.setText(self._tr("terminal.action.stop_auto"))
            self.action_manual_trade.setText(self._tr("terminal.action.manual_trade"))
            self.action_close_all.setText(self._tr("terminal.action.close_all"))
            self.action_cancel_orders.setText(self._tr("terminal.action.cancel_all"))
            self.action_kill_switch.setText("Emergency Kill Switch")
            self.action_run_backtest.setText(self._tr("terminal.action.run_backtest"))
            self.action_strategy_optimization.setText("Strategy Optimization")
            self.action_new_chart.setText(self._tr("terminal.action.new_chart"))
            self.action_multi_chart.setText(self._tr("terminal.action.multi_chart"))
            self.action_detach_chart.setText("Detach Chart")
            self.action_reattach_chart.setText("Reattach Chart")
            self.action_tile_chart_windows.setText("Tile Chart Windows")
            self.action_cascade_chart_windows.setText("Cascade Chart Windows")
            self.action_chart_settings.setText("Chart Settings...")
            self.action_candle_colors.setText("Candle Colors...")
            self.action_edit_studies.setText("Edit Studies...")
            self.action_add_indicator.setText("Add Study...")
            self.action_remove_indicator.setText("Remove Study...")
            self.action_remove_all_indicators.setText("Remove All Studies")
            self.toggle_bid_ask_lines_action.setText(self._tr("terminal.action.toggle_bid_ask"))
            self.toggle_volume_bar_action.setText("Show Volume Subgraph")
            self.action_refresh_markets.setText(self._tr("terminal.action.refresh_markets"))
            self.action_refresh_chart.setText(self._tr("terminal.action.refresh_chart"))
            self.action_refresh_orderbook.setText(self._tr("terminal.action.refresh_orderbook"))
            self.action_reload_balance.setText(self._tr("terminal.action.reload_balance"))
            self.action_app_settings.setText(self._tr("terminal.action.app_settings"))
            self.action_risk_settings.setText("Risk Profile Settings")
            self.action_portfolio_view.setText("Portfolio Exposure")
            self.action_market_chat.setText("Sopotek Pilot")
            self.action_recommendations.setText("Recommendations")
            self.action_ml_monitor.setText(self._tr("terminal.action.ml_monitor"))
            self.action_logs.setText(self._tr("terminal.action.logs"))
            self.action_export_diagnostics.setText("Export Diagnostics Bundle")
            self.action_performance.setText(self._tr("terminal.action.performance"))
            self.action_closed_journal.setText("Closed Journal")
            self.action_trade_checklist.setText("Trade Checklist")
            self.action_journal_review.setText("Journal Review")
            self.action_system_health.setText("System Health")
            self.action_quant_pm.setText("Quant PM")
            self.action_ml_research.setText("ML Research Lab")
            self.action_trader_tv.setText("Trader TV")
            self.action_education_center.setText("Education Center")
            self.action_position_analysis.setText("Position Analysis")
            self.action_strategy_optimization.setText("Strategy Optimization")
            self.action_strategy_assigner.setText("Strategy Assigner")
            self.action_strategy_scorecard.setText("Strategy Scorecard")
            self.action_strategy_debug.setText("Strategy Debug")
            self.action_system_console.setText("System Console")
            self.action_system_status.setText("System Status")
            self.action_stellar_asset_explorer.setText("Stellar Asset Explorer")
            self.action_documentation.setText(self._tr("terminal.action.documentation"))
            self.action_api_docs.setText(self._tr("terminal.action.api_reference"))
            self.action_about.setText(self._tr("terminal.action.about"))

            active_language = getattr(self.controller, "language_code", "en")
            for code, action in self.language_actions.items():
                action.blockSignals(True)
                action.setChecked(code == active_language)
                action.blockSignals(False)

        if getattr(self, "symbol_label", None) is not None:
            self.symbol_label.setText(self._tr("terminal.toolbar.symbol"))
        if getattr(self, "open_symbol_button", None) is not None:
            self.open_symbol_button.setText(self._tr("terminal.toolbar.open_symbol"))
        if getattr(self, "screenshot_button", None) is not None:
            self.screenshot_button.setText(self._tr("terminal.toolbar.screenshot"))
        if getattr(self, "system_status_button", None) is not None:
            self.system_status_button.setText("Status")
            self.system_status_button.setToolTip("Show or hide the System Status panel")
        if getattr(self, "kill_switch_button", None) is not None:
            self._update_kill_switch_button()
        if getattr(self, "session_mode_badge", None) is not None:
            self._update_session_badge()
        if getattr(self, "trading_activity_label", None) is not None:
            self.trading_activity_label.setToolTip("Shows whether AI trading is currently active")
        if getattr(self, "desk_status_frame", None) is not None:
            self._update_desk_status_panel()

        self._set_active_timeframe_button(getattr(self, "current_timeframe", "1h"))
        self._update_autotrade_button()

        status_key = {
            "connected": "terminal.status.connected",
            "disconnected": "terminal.status.disconnected",
        }.get(self.current_connection_status, "terminal.status.connecting")
        if getattr(self, "connection_indicator", None) is not None:
            self.connection_indicator.setText(f"* {self._tr(status_key)}")

        apply_runtime_translations(
            self,
            getattr(self.controller, "language_code", "en"),
            previous_language=previous_language,
        )
        self._applied_language_code = getattr(self.controller, "language_code", "en")
        Terminal._sync_exchange_scoped_actions(self)

    # ==========================================================
    # TOOLBAR
    # ==========================================================

    def _create_toolbar(self):
        frame_style = "QFrame { background-color: #0f1726; border: 1px solid #24324a; border-radius: 16px; }"
        self.timeframe_buttons.clear()
        self.toolbar_timeframe_label = None

        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("terminal_main_toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet("QToolBar { spacing: 8px; padding: 6px; }")
        self.toolbar = toolbar
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        controls_toolbar = QToolBar("Trading Controls")
        controls_toolbar.setObjectName("terminal_controls_toolbar")
        controls_toolbar.setMovable(False)
        controls_toolbar.setFloatable(False)
        controls_toolbar.setStyleSheet("QToolBar { spacing: 8px; padding: 4px 6px 8px 6px; }")
        self.secondary_toolbar = controls_toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, controls_toolbar)

        session_box = QFrame()
        session_box.setStyleSheet(
            "QFrame { background-color: #101827; border: 1px solid #24324a; border-radius: 14px; }"
        )
        session_layout = QHBoxLayout(session_box)
        session_layout.setContentsMargins(10, 6, 10, 6)
        session_layout.setSpacing(8)

        self.session_label = QLabel("Session")
        self.session_label.setStyleSheet("color: #9fb0c7; font-weight: 700;")
        session_layout.addWidget(self.session_label)

        self.session_selector = QComboBox()
        self.session_selector.setMinimumWidth(180)
        self.session_selector.setMaximumWidth(260)
        self.session_selector.setStyleSheet(
            """
            QComboBox {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                border-radius: 10px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QComboBox::drop-down {
                border: 0;
                width: 24px;
            }
            """
        )
        activate_selected_session = getattr(self, "_activate_selected_session_from_toolbar", None)
        if callable(activate_selected_session):
            self.session_selector.currentIndexChanged.connect(activate_selected_session)
        session_layout.addWidget(self.session_selector)
        toolbar.addWidget(session_box)

        symbol_box = QFrame()
        symbol_box.setStyleSheet(
            "QFrame { background-color: #101827; border: 1px solid #24324a; border-radius: 14px; }"
        )
        symbol_layout = QHBoxLayout(symbol_box)
        symbol_layout.setContentsMargins(10, 6, 10, 6)
        symbol_layout.setSpacing(8)

        self.symbol_label = QLabel(self._tr("terminal.toolbar.symbol"))
        self.symbol_label.setStyleSheet("color: #9fb0c7; font-weight: 700;")
        symbol_layout.addWidget(self.symbol_label)

        self.symbol_picker = QComboBox()
        self.symbol_picker.setMinimumWidth(150)
        self.symbol_picker.setMaximumWidth(240)
        self.symbol_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.symbol_picker.setMinimumContentsLength(10)
        self.symbol_picker.setStyleSheet(
            """
            QComboBox {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                border-radius: 10px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QComboBox::drop-down {
                border: 0;
                width: 24px;
            }
            """
        )
        for sym in self.controller.symbols:
            self.symbol_picker.addItem(sym)
        self.symbol_picker.setCurrentText(self.symbol)
        self.symbol_picker.activated.connect(lambda _=None: self._open_symbol_from_picker())
        symbol_layout.addWidget(self.symbol_picker)

        self.open_symbol_button = QPushButton(self._tr("terminal.toolbar.open_symbol"))
        self.open_symbol_button.setStyleSheet(self._action_button_style())
        self.open_symbol_button.clicked.connect(self._open_symbol_from_picker)
        symbol_layout.addWidget(self.open_symbol_button)

        toolbar.addWidget(symbol_box)

        desk_status_box = QFrame()
        desk_status_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        desk_status_box.setMinimumWidth(360)
        desk_status_layout = QVBoxLayout(desk_status_box)
        desk_status_layout.setContentsMargins(12, 8, 12, 8)
        desk_status_layout.setSpacing(3)
        self.desk_status_frame = desk_status_box

        self.desk_status_title_label = QLabel("DESK STATUS")
        self.desk_status_title_label.setObjectName("desk_status_title")
        desk_status_layout.addWidget(self.desk_status_title_label)

        self.desk_status_primary_label = QLabel("PAPER BROKER | Account not set")
        self.desk_status_primary_label.setObjectName("desk_status_primary")
        desk_status_layout.addWidget(self.desk_status_primary_label)

        self.desk_status_secondary_label = QLabel("AI idle on All Symbols | Alerts off | News off | Model not set")
        self.desk_status_secondary_label.setObjectName("desk_status_secondary")
        desk_status_layout.addWidget(self.desk_status_secondary_label)

        toolbar.addWidget(desk_status_box)

        utility_box = QFrame()
        utility_box.setStyleSheet(frame_style)
        utility_layout = QHBoxLayout(utility_box)
        utility_layout.setContentsMargins(8, 6, 8, 6)
        utility_layout.setSpacing(8)

        self.connection_indicator.hide()
        utility_layout.addWidget(self.heartbeat)

        self.screenshot_button = QPushButton(self._tr("terminal.toolbar.screenshot"))
        self.screenshot_button.setStyleSheet(self._action_button_style())
        self.screenshot_button.setMinimumWidth(96)
        self.screenshot_button.clicked.connect(self.take_screen_shot)
        utility_layout.addWidget(self.screenshot_button)

        self.session_mode_badge = QLabel("PAPER")
        self.session_mode_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        utility_layout.addWidget(self.session_mode_badge)

        self.live_trading_bar_frame = QFrame()
        self.live_trading_bar_frame.setMinimumWidth(148)
        live_bar_layout = QVBoxLayout(self.live_trading_bar_frame)
        live_bar_layout.setContentsMargins(10, 6, 10, 6)
        live_bar_layout.setSpacing(4)
        self.live_trading_bar_label = QLabel("LIVE MODE")
        self.live_trading_bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        live_bar_layout.addWidget(self.live_trading_bar_label)
        self.live_trading_bar = QProgressBar()
        self.live_trading_bar.setFixedWidth(128)
        self.live_trading_bar.setFixedHeight(12)
        self.live_trading_bar.setRange(0, 0)
        self.live_trading_bar.setTextVisible(False)
        live_bar_layout.addWidget(self.live_trading_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        utility_layout.addWidget(self.live_trading_bar_frame)

        self.kill_switch_button = QPushButton("Kill Switch")
        self.kill_switch_button.setStyleSheet(self._danger_button_style())
        self.kill_switch_button.setMinimumWidth(102)
        self.kill_switch_button.clicked.connect(self._toggle_emergency_stop)
        utility_layout.addWidget(self.kill_switch_button)

        self.trading_activity_label = QLabel("AI Idle")
        self.trading_activity_label.setMinimumWidth(70)
        self.trading_activity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        utility_layout.addWidget(self.trading_activity_label)

        toolbar.addWidget(utility_box)

        controls_row = QWidget()
        controls_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_row_layout = QHBoxLayout(controls_row)
        controls_row_layout.setContentsMargins(0, 0, 0, 0)
        controls_row_layout.setSpacing(0)
        controls_row_layout.addStretch(1)
        self.autotrade_controls_row = controls_row

        actions_box = QFrame()
        actions_box.setStyleSheet(frame_style)
        actions_box.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.autotrade_controls_box = actions_box
        actions_layout = QHBoxLayout(actions_box)
        actions_layout.setContentsMargins(8, 6, 8, 6)
        actions_layout.setSpacing(8)
        self.autotrade_controls_layout = actions_layout

        scope_label = QLabel("Scope")
        scope_label.setStyleSheet("color: #9fb0c7; font-weight: 700;")
        self.autotrade_scope_label_widget = scope_label
        actions_layout.addWidget(scope_label)

        self.autotrade_scope_picker = QComboBox()
        self.autotrade_scope_picker.setMinimumWidth(108)
        self.autotrade_scope_picker.setMaximumWidth(148)
        self.autotrade_scope_picker.setMinimumContentsLength(10)
        self.autotrade_scope_picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.autotrade_scope_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.autotrade_scope_picker.setStyleSheet(
            """
            QComboBox {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                border-radius: 10px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QComboBox::drop-down {
                border: 0;
                width: 24px;
            }
            """
        )
        self.autotrade_scope_picker.addItem("All Symbols", "all")
        self.autotrade_scope_picker.addItem("Selected Symbol", "selected")
        self.autotrade_scope_picker.addItem("Watchlist", "watchlist")
        self.autotrade_scope_picker.addItem("Best Ranked", "ranked")
        self.autotrade_scope_picker.currentIndexChanged.connect(self._change_autotrade_scope)
        actions_layout.addWidget(self.autotrade_scope_picker)

        self.auto_button = QPushButton()
        self.auto_button.setCheckable(True)
        self.auto_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.auto_button.clicked.connect(self._toggle_autotrading)
        actions_layout.addWidget(self.auto_button)

        controls_row_layout.addWidget(actions_box, 0, Qt.AlignmentFlag.AlignRight)
        controls_toolbar.addWidget(controls_row)

        self._set_active_timeframe_button(self.current_timeframe)
        self._apply_autotrade_scope(self.autotrade_scope_value)
        refresh_autotrade_controls_layout = getattr(self, "_refresh_autotrade_controls_layout", None)
        if callable(refresh_autotrade_controls_layout):
            refresh_autotrade_controls_layout()
        self._update_autotrade_button()
        refresh_session_selector = getattr(self, "_refresh_session_selector", None)
        if callable(refresh_session_selector):
            refresh_session_selector()
        self._update_session_badge()
        self._update_live_trading_bar()
        self._update_kill_switch_button()
        self._update_desk_status_panel()

    # ==========================================================
    # AUTOTRADING
    # ==========================================================

    def _set_autotrading_enabled(self, enabled):
        target = bool(enabled)
        if self.autotrading_enabled == target:
            return
        self._toggle_autotrading()

    def _toggle_autotrading(self):
        target_enabled = not self.autotrading_enabled

        if target_enabled:
            pending_enable = getattr(self, "_autotrade_enable_task", None)
            if pending_enable is not None and not pending_enable.done():
                return

            if not self.controller.trading_system:
                self.logger.error("Trading system is not initialized yet")
                QMessageBox.warning(
                    self,
                    self._tr("terminal.warning.trading_not_ready_title"),
                    self._tr("terminal.warning.trading_not_ready_body"),
                )
                self.autotrading_enabled = False
                self._update_autotrade_button()
                self.autotrade_toggle.emit(False)
                return

            active_symbols = []
            if hasattr(self.controller, "get_active_autotrade_symbols"):
                try:
                    active_symbols = self.controller.get_active_autotrade_symbols()
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    active_symbols = []
            if not active_symbols:
                message = "No symbols are available for the chosen AI scope."
                if self.autotrade_scope_value == "watchlist":
                    message = "Watchlist scope is selected, but no symbols are checked in Market Watch."
                elif self.autotrade_scope_value == "selected":
                    message = "Selected-symbol scope is selected, but there is no active symbol yet."
                elif self.autotrade_scope_value == "ranked":
                    message = "Best-ranked scope is selected, but there are no ranked or tradable symbols ready yet."
                QMessageBox.warning(self, "AI Trading Scope", message)
                self.autotrading_enabled = False
                self._update_autotrade_button()
                self.autotrade_toggle.emit(False)
                return

            if bool(getattr(self.controller, "is_live_mode", lambda: False)()):
                loop = asyncio.get_event_loop()
                self._autotrade_enable_task = loop.create_task(
                    self._enable_live_autotrading_async(active_symbols)
                )
                return

            self.autotrading_enabled = True
            self._update_autotrade_button()

            loop = asyncio.get_event_loop()
            loop.create_task(self.controller.trading_system.start())
            self.autotrade_toggle.emit(True)
            if hasattr(self, "system_console"):
                self.system_console.log(
                    f"AI auto trading enabled for {len(active_symbols)} symbol(s) using scope: {self._autotrade_scope_label()}.",
                    "INFO",
                )

        else:
            self.autotrading_enabled = False

            self._update_autotrade_button()

            if self.controller.trading_system:
                asyncio.create_task(self.controller.trading_system.stop())

            self.autotrade_toggle.emit(False)
            if hasattr(self, "system_console"):
                self.system_console.log("AI auto trading disabled.", "INFO")

    async def _enable_live_autotrading_async(self, active_symbols):
        try:
            controller = getattr(self, "controller", None)
            readiness_resolver = getattr(controller, "evaluate_live_readiness_report_async", None)
            if callable(readiness_resolver):
                try:
                    await readiness_resolver(
                        symbol=self._current_chart_symbol() or getattr(self, "symbol", None),
                        timeframe=getattr(self, "current_timeframe", "1h"),
                    )
                except Exception:
                    self.logger.debug("Async live readiness warmup failed during AI enable", exc_info=True)

            if getattr(self, "_ui_shutting_down", False):
                return

            self.autotrading_enabled = True
            self._update_autotrade_button()

            loop = asyncio.get_event_loop()
            loop.create_task(self.controller.trading_system.start())
            self.autotrade_toggle.emit(True)
            if hasattr(self, "system_console"):
                self.system_console.log(
                    f"AI auto trading enabled for {len(active_symbols)} symbol(s) using scope: {self._autotrade_scope_label()}.",
                    "INFO",
                )
        except asyncio.CancelledError:
            return
        finally:
            current = asyncio.current_task()
            if getattr(self, "_autotrade_enable_task", None) is current:
                self._autotrade_enable_task = None

    def _stop_autotrading_for_emergency(self):
        self.autotrading_enabled = False
        self._update_autotrade_button()
        self.autotrade_toggle.emit(False)
        trading_system = getattr(self.controller, "trading_system", None)
        if trading_system is not None:
            trading_system.running = False

    def _toggle_emergency_stop(self):
        if bool(getattr(self.controller, "is_emergency_stop_active", lambda: False)()):
            self.controller.clear_emergency_stop()
            self._update_kill_switch_button()
            self._refresh_terminal()
            self.system_console.log("Emergency lock cleared. New orders may be submitted again.", "WARN")
            self._show_async_message(
                "Trading Resumed",
                "Emergency lock cleared. Auto trading remains OFF until you enable it again.",
                QMessageBox.Icon.Information,
            )
            return

        confirm = QMessageBox.question(
            self,
            "Emergency Kill Switch",
            (
                "Activate the emergency kill switch?\n\n"
                "This will stop auto trading, cancel open orders, close tracked positions, "
                "and block new entries until you resume manually."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        asyncio.get_event_loop().create_task(self._activate_emergency_stop_async())

    async def _activate_emergency_stop_async(self):
        self.controller.activate_emergency_stop("Emergency kill switch engaged by operator")
        self._update_kill_switch_button()
        self._refresh_terminal()
        self._stop_autotrading_for_emergency()
        self.system_console.log("Emergency kill switch engaged. Canceling open orders and closing tracked positions.", "WARN")
        try:
            await self._cancel_all_orders_async(show_dialog=False)
        except (asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        try:
            await self._close_all_positions_async(show_dialog=False)
        except (asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        self._refresh_terminal()
        self._show_async_message(
            "Emergency Kill Switch",
            "Emergency lock is active. Auto trading is OFF and new orders are blocked until you press Resume.",
            QMessageBox.Icon.Warning,
        )

    def _refresh_session_selector(self):
        selector = getattr(self, "session_selector", None)
        controller = getattr(self, "controller", None)
        if selector is None or controller is None or not hasattr(controller, "list_trading_sessions"):
            return

        try:
            sessions = list(controller.list_trading_sessions() or [])
        except Exception:
            sessions = []

        active_session_id = str(getattr(controller, "active_session_id", "") or "").strip()
        items = []
        selected_index = 0
        for index, session in enumerate(sessions):
            session_id = str(session.get("session_id") or "").strip()
            label = str(session.get("label") or session_id or "Session").strip()
            status = str(session.get("status") or "unknown").upper()
            items.append((f"{label} [{status}]", session_id))
            if session_id and session_id == active_session_id:
                selected_index = index
        if not items:
            items = [("No active sessions", "")]

        signature = (id(selector), active_session_id, tuple(items))
        if (
            signature == getattr(self, "_session_selector_signature", None)
            and selector.count() == len(items)
        ):
            if selector.currentIndex() != selected_index:
                blocked = selector.blockSignals(True)
                selector.setCurrentIndex(selected_index)
                selector.blockSignals(blocked)
            return

        blocked = selector.blockSignals(True)
        selector.clear()
        if not sessions:
            selector.addItem("No active sessions", "")
            selector.setCurrentIndex(0)
            selector.blockSignals(blocked)
            self._session_selector_signature = signature
            return

        for text, session_id in items:
            selector.addItem(text, session_id)

        selector.setCurrentIndex(selected_index)
        selector.blockSignals(blocked)
        self._session_selector_signature = signature

    def _activate_selected_session_from_toolbar(self, *_args):
        selector = getattr(self, "session_selector", None)
        controller = getattr(self, "controller", None)
        if selector is None or controller is None or not hasattr(controller, "request_session_activation"):
            return
        session_id = str(selector.currentData() or "").strip()
        if not session_id or session_id == str(getattr(controller, "active_session_id", "") or "").strip():
            return
        controller.request_session_activation(session_id)

    # ==========================================================
    # CHARTS
    # ==========================================================

    def _create_chart_tab(self, symbol, timeframe):
        chart = ChartWidget(
            symbol,
            timeframe,
            self.controller,
            candle_up_color=self.candle_up_color,
            candle_down_color=self.candle_down_color,
            show_volume_panel=getattr(self, "show_chart_volume", False),
            chart_background=getattr(self, "chart_background_color", "#11161f"),
            grid_color=getattr(self, "chart_grid_color", "#8290a0"),
            axis_color=getattr(self, "chart_axis_color", "#9aa4b2"),
        )
        self._configure_chart_widget(chart)

        row = self._find_market_watch_row(symbol)
        if row is None:
            row = self.symbols_table.rowCount()
            self.symbols_table.insertRow(row)
            self._market_watch_symbols_signature = None
        self._set_market_watch_row(row, symbol, bid="-", ask="-", status="? Training...", usd_value="-")
        self.chart_tabs.addTab(chart, f"{symbol} ({timeframe})")
        chart.link_all_charts(self.chart_tabs.count())
        self.chart_tabs.setCurrentWidget(chart)
        self._set_active_chart_widget(chart)
        if self.symbol_picker is not None:
            self.symbol_picker.setCurrentText(symbol)
        self._request_active_orderbook()

    def _show_chart_page_in_window(self, page, title, detach_key, width=1320, height=860, geometry=None):
        window = self._get_or_create_tool_window(detach_key, title, width=width, height=height)
        window._contains_chart_page = True
        window._chart_window_key = detach_key
        window.setWindowTitle(title)
        window.setCentralWidget(page)
        page.setVisible(True)
        self._install_chart_window_actions(window)
        if geometry is not None:
            window.setGeometry(geometry)
        window.show()
        window.raise_()
        window.activateWindow()

        for chart in self._chart_widgets_in_page(page):
            try:
                chart.refresh_context_display()
            except (RuntimeError, AttributeError, TypeError):
                pass
            last_df = getattr(chart, "_last_df", None)
            if last_df is not None and hasattr(last_df, "empty") and not last_df.empty:
                try:
                    chart.update_candles(last_df.copy())
                except (RuntimeError, AttributeError, TypeError, ValueError):
                    self._schedule_chart_data_refresh(chart)
            else:
                self._schedule_chart_data_refresh(chart)
            try:
                chart.updateGeometry()
                chart.repaint()
            except (RuntimeError, AttributeError, TypeError):
                pass

        try:
            window.centralWidget().updateGeometry()
            window.centralWidget().repaint()
        except (AttributeError, RuntimeError, TypeError):
            pass
        if not getattr(window, "_chart_layout_save_hook_installed", False):
            window.destroyed.connect(lambda *_: self._save_detached_chart_layouts())
            window._chart_layout_save_hook_installed = True
        return window

    def _schedule_chart_data_refresh(self, chart):
        if not isinstance(chart, ChartWidget):
            return

        if hasattr(self.controller, "request_candle_data"):
            asyncio.get_event_loop().create_task(
                self._request_chart_data_for_widget(
                    chart,
                    limit=self._history_request_limit(),
                )
            )
        else:
            asyncio.get_event_loop().create_task(
                self._reload_chart_data(chart.symbol, chart.timeframe)
            )

    def _register_chart_request_token(self, chart):
        tokens = getattr(self, "_chart_request_tokens", None)
        if not isinstance(tokens, dict):
            tokens = {}
            self._chart_request_tokens = tokens
        token = object()
        tokens[id(chart)] = token
        return token

    def _is_chart_request_current(self, chart, token):
        if not isinstance(chart, ChartWidget):
            return False
        if not self._is_qt_object_alive(chart):
            return False
        tokens = getattr(self, "_chart_request_tokens", None)
        if not isinstance(tokens, dict):
            return False
        return tokens.get(id(chart)) is token

    async def _request_chart_data_for_widget(self, chart, limit=None):
        if not isinstance(chart, ChartWidget):
            return None
        if not self._is_qt_object_alive(chart):
            return None
        if not hasattr(self.controller, "request_candle_data"):
            return None

        symbol = str(getattr(chart, "symbol", "") or "").strip()
        timeframe = str(getattr(chart, "timeframe", getattr(self, "current_timeframe", "1h")) or "1h").strip() or "1h"
        if not symbol:
            return None

        resolver = getattr(self.controller, "_resolve_preferred_market_symbol", None)
        resolved_symbol = symbol
        if callable(resolver):
            try:
                resolved_symbol = str(resolver(symbol) or symbol).strip().upper() or symbol
            except Exception:
                resolved_symbol = symbol
        if resolved_symbol and resolved_symbol != symbol:
            self._retarget_chart_widget_symbol(chart, resolved_symbol)
            symbol = resolved_symbol

        try:
            requested_limit = int(limit if limit is not None else self._history_request_limit())
        except Exception:
            requested_limit = int(self._history_request_limit())
        requested_limit = max(requested_limit, 1)

        token = self._register_chart_request_token(chart)
        if hasattr(chart, "set_loading_state"):
            chart.set_loading_state(True, requested_bars=requested_limit)

        try:
            frame = await self.controller.request_candle_data(
                symbol=symbol,
                timeframe=timeframe,
                limit=requested_limit,
            )
        except Exception as exc:
            if self._is_chart_request_current(chart, token) and hasattr(chart, "set_no_data_state"):
                chart.set_no_data_state(str(exc))
            raise

        if not self._is_chart_request_current(chart, token):
            return frame

        frame = candles_to_df(frame)
        if frame is None or getattr(frame, "empty", False):
            if hasattr(chart, "set_no_data_state"):
                chart.set_no_data_state()
            return None

        self._update_chart(symbol, frame)

        try:
            received_count = int(len(frame.index))
        except Exception:
            received_count = int(len(frame))

        if requested_limit > 0 and received_count < requested_limit:
            if hasattr(chart, "set_history_notice"):
                chart.set_history_notice(received_count, requested_limit)
        elif hasattr(chart, "clear_data_status"):
            chart.clear_data_status()
        return frame

    def _retarget_chart_widget_symbol(self, chart, symbol):
        if not isinstance(chart, ChartWidget) or not self._is_qt_object_alive(chart):
            return None

        target_symbol = str(symbol or "").strip().upper()
        current_symbol = str(getattr(chart, "symbol", "") or "").strip().upper()
        if not target_symbol:
            return current_symbol or None
        if target_symbol == current_symbol:
            return target_symbol

        chart.symbol = target_symbol
        if getattr(self, "symbol", None) == current_symbol:
            self.symbol = target_symbol

        if hasattr(chart, "refresh_context_display"):
            try:
                chart.refresh_context_display()
            except (RuntimeError, AttributeError, TypeError):
                pass

        page = None
        chart_page_for_widget = getattr(self, "_chart_page_for_widget", None)
        if callable(chart_page_for_widget):
            try:
                page = chart_page_for_widget(chart)
            except Exception:
                page = None

        chart_tabs_ready = getattr(self, "_chart_tabs_ready", None)
        if callable(chart_tabs_ready):
            try:
                if chart_tabs_ready() and page is not None:
                    index = self.chart_tabs.indexOf(page)
                    if index >= 0:
                        self.chart_tabs.setTabText(index, self._chart_page_title(page, fallback_index=index))
            except Exception:
                pass

        try:
            window = page.window() if page is not None and hasattr(page, "window") else None
        except Exception:
            window = None
        if window is not None and window is not self and getattr(window, "_contains_chart_page", False):
            try:
                window.setWindowTitle(self._chart_page_title(page))
            except Exception:
                pass

        active_chart = getattr(self, "_active_chart_widget_ref", None)
        if active_chart is chart and self.symbol_picker is not None:
            try:
                if self.symbol_picker.findText(target_symbol) < 0:
                    self.symbol_picker.addItem(target_symbol)
                self.symbol_picker.setCurrentText(target_symbol)
            except Exception:
                pass
            current_timeframe = str(getattr(self, "current_timeframe", "1h") or "1h")
            self._last_chart_request_key = (target_symbol, str(getattr(chart, "timeframe", current_timeframe) or current_timeframe))

        return target_symbol

    def _chart_page_title(self, page, fallback_index=None):
        charts = self._chart_widgets_in_page(page)
        timeframe = self.current_timeframe
        if charts:
            timeframe = getattr(charts[0], "timeframe", timeframe)
        if len(charts) == 1:
            chart = charts[0]
            return f"{chart.symbol} ({chart.timeframe})"
        if len(charts) > 1:
            return f"Chart Group ({timeframe})"
        if fallback_index is not None and self._chart_tabs_ready():
            try:
                return self.chart_tabs.tabText(fallback_index)
            except (IndexError, RuntimeError):
                pass
        return "Detached Chart"

    def _close_chart_tab(self, index):
        if not self._chart_tabs_ready():
            return

        try:
            page = self.chart_tabs.widget(index)
        except RuntimeError:
            return

        self.chart_tabs.removeTab(index)
        if page is not None:
            page.deleteLater()

    def _detach_current_chart_tab(self):
        if not self._chart_tabs_ready():
            return
        self._detach_chart_tab(self.chart_tabs.currentIndex())

    def _reattach_active_chart_window(self):
        window = self._active_detached_chart_window()
        if window is None:
            self.system_console.log("Focus a detached chart window first.", "ERROR")
            return
        self._reattach_chart_window(window)

    def _tile_chart_windows(self):
        windows = self._detached_chart_windows()
        if not windows:
            self.system_console.log("No detached chart windows to tile.", "INFO")
            return

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else self.geometry()
        count = len(windows)
        columns = max(1, int(np.ceil(np.sqrt(count))))
        rows = max(1, int(np.ceil(count / columns)))
        width = max(360, available.width() // columns)
        height = max(260, available.height() // rows)

        for index, window in enumerate(windows):
            row = index // columns
            col = index % columns
            window.showNormal()
            window.setGeometry(
                available.x() + (col * width),
                available.y() + (row * height),
                width,
                height,
            )
        self._save_detached_chart_layouts()

    def _cascade_chart_windows(self):
        windows = self._detached_chart_windows()
        if not windows:
            self.system_console.log("No detached chart windows to cascade.", "INFO")
            return

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else self.geometry()
        width = max(520, int(available.width() * 0.62))
        height = max(360, int(available.height() * 0.62))
        step = 32

        for index, window in enumerate(windows):
            offset = step * index
            max_x_offset = max(0, available.width() - width)
            max_y_offset = max(0, available.height() - height)
            window.showNormal()
            window.setGeometry(
                available.x() + min(offset, max_x_offset),
                available.y() + min(offset, max_y_offset),
                width,
                height,
            )
            window.raise_()

        windows[-1].activateWindow()
        self._save_detached_chart_layouts()

    def _detach_chart_tab(self, index):
        if not self._chart_tabs_ready():
            return
        if index is None or index < 0:
            return

        try:
            page = self.chart_tabs.widget(index)
        except RuntimeError:
            return
        if page is None:
            return

        title = self._chart_page_title(page, fallback_index=index)
        charts = self._chart_widgets_in_page(page)
        if len(charts) == 1:
            detach_key = self._single_chart_window_key(charts[0].symbol, charts[0].timeframe)
        else:
            object_name = getattr(page, "objectName", lambda: "")() or "chart_page"
            detach_key = getattr(page, "_detach_window_key", None)
            if not detach_key:
                detach_key = f"{object_name}_{abs(hash((title, id(page))))}"
                page._detach_window_key = detach_key

        existing_window = self._find_detached_chart_window(
            symbol=charts[0].symbol if len(charts) == 1 else None,
            timeframe=charts[0].timeframe if len(charts) == 1 else None,
        ) or self.detached_tool_windows.get(detach_key)
        if existing_window is not None:
            existing_window.showNormal()
            existing_window.raise_()
            existing_window.activateWindow()
            return

        self.chart_tabs.removeTab(index)
        page.setParent(None)
        self._show_chart_page_in_window(page, title, detach_key, width=1320, height=860)
        self._save_detached_chart_layouts()

    def _open_or_focus_detached_chart(self, symbol, timeframe=None, geometry=None, compact_view=False):
        target_symbol = (symbol or "").strip().upper()
        target_timeframe = timeframe or self.current_timeframe
        if not target_symbol:
            return None

        detach_key = self._single_chart_window_key(target_symbol, target_timeframe)
        existing_window = self._find_detached_chart_window(target_symbol, target_timeframe) or self.detached_tool_windows.get(detach_key)
        if self._is_qt_object_alive(existing_window):
            if geometry is not None:
                existing_window.setGeometry(geometry)
            existing_window.showNormal()
            existing_window.raise_()
            existing_window.activateWindow()
            page = existing_window.centralWidget()
            if page is None:
                return existing_window
            for chart in self._chart_widgets_in_page(page):
                if hasattr(chart, "set_compact_view_mode"):
                    chart.set_compact_view_mode(compact_view)
                self._schedule_chart_data_refresh(chart)
            self._save_detached_chart_layouts()
            return existing_window

        existing_index = self._find_chart_tab(target_symbol, target_timeframe)
        if existing_index >= 0:
            try:
                page = self.chart_tabs.widget(existing_index)
            except RuntimeError:
                page = None
            if page is not None:
                for chart in self._chart_widgets_in_page(page):
                    if hasattr(chart, "set_compact_view_mode"):
                        chart.set_compact_view_mode(compact_view)
                self.chart_tabs.removeTab(existing_index)
                page.setParent(None)
                return self._show_chart_page_in_window(
                    page,
                    self._chart_page_title(page),
                    detach_key,
                    width=1320,
                    height=860,
                    geometry=geometry,
                )

        chart = ChartWidget(
            target_symbol,
            target_timeframe,
            self.controller,
            candle_up_color=self.candle_up_color,
            candle_down_color=self.candle_down_color,
            show_volume_panel=getattr(self, "show_chart_volume", False),
            chart_background=getattr(self, "chart_background_color", "#11161f"),
            grid_color=getattr(self, "chart_grid_color", "#8290a0"),
            axis_color=getattr(self, "chart_axis_color", "#9aa4b2"),
        )
        self._configure_chart_widget(chart)
        if hasattr(chart, "set_compact_view_mode"):
            chart.set_compact_view_mode(compact_view)
        window = self._show_chart_page_in_window(
            chart,
            f"{target_symbol} ({target_timeframe})",
            detach_key,
            width=1320,
            height=860,
            geometry=geometry,
        )
        self._schedule_chart_data_refresh(chart)
        self._save_detached_chart_layouts()
        return window

    def _open_or_focus_detached_chart_group(self, symbols, timeframe=None, geometry=None):
        target_symbols = self._normalized_chart_symbols(symbols, max_count=4)
        target_timeframe = str(timeframe or self.current_timeframe or "1h").strip().lower() or "1h"
        if not target_symbols:
            return None

        detach_key = self._multi_chart_window_key(target_symbols, target_timeframe)
        existing_window = self.detached_tool_windows.get(detach_key)
        if self._is_qt_object_alive(existing_window):
            if geometry is not None:
                existing_window.setGeometry(geometry)
            existing_window.showNormal()
            existing_window.raise_()
            existing_window.activateWindow()
            page = existing_window.centralWidget()
            for chart in self._chart_widgets_in_page(page):
                self._schedule_chart_data_refresh(chart)
            preferred_chart = self._preferred_chart_in_page(page)
            if preferred_chart is not None:
                self._set_active_chart_widget(preferred_chart)
            self._save_detached_chart_layouts()
            return existing_window

        existing_index = self._find_multi_chart_tab(target_symbols, target_timeframe)
        if existing_index >= 0:
            try:
                page = self.chart_tabs.widget(existing_index)
            except RuntimeError:
                page = None
            if page is not None:
                self.chart_tabs.removeTab(existing_index)
                page.setParent(None)
                window = self._show_chart_page_in_window(
                    page,
                    self._chart_page_title(page),
                    detach_key,
                    width=1320,
                    height=860,
                    geometry=geometry,
                )
                preferred_chart = self._preferred_chart_in_page(page)
                if preferred_chart is not None:
                    self._set_active_chart_widget(preferred_chart)
                self._save_detached_chart_layouts()
                return window

        page = self._build_multi_chart_page(target_symbols, target_timeframe)
        if page is None:
            return None

        window = self._show_chart_page_in_window(
            page,
            self._chart_page_title(page),
            detach_key,
            width=1320,
            height=860,
            geometry=geometry,
        )
        preferred_chart = self._preferred_chart_in_page(page)
        if preferred_chart is not None:
            self._set_active_chart_widget(preferred_chart)
        self._save_detached_chart_layouts()
        return window

    def _on_chart_tab_changed(self, index):
        if not self._chart_tabs_ready():
            return

        try:
            page = self.chart_tabs.widget(index)
        except RuntimeError:
            return
        charts = self._chart_widgets_in_page(page)
        if not charts:
            return

        chart = self._preferred_chart_in_page(page)
        if chart is None:
            return

        self._set_active_chart_widget(chart)
        if hasattr(chart, "set_timeframe"):
            chart.set_timeframe(chart.timeframe, emit_signal=False)
        for chart_widget in charts:
            self._schedule_chart_data_refresh(chart_widget)
        self._request_active_orderbook()

    def _add_new_chart(self):
        symbol, ok = QInputDialog.getText(
            self,
            self._tr("terminal.dialog.new_chart_title"),
            self._tr("terminal.dialog.new_chart_prompt"),
        )
        if ok and symbol:
            self._open_symbol_chart(symbol.upper(), self.current_timeframe)

    def _configure_chart_widget(self, chart):
        if not isinstance(chart, ChartWidget):
            return chart
        chart.set_bid_ask_lines_visible(self.show_bid_ask_lines)
        chart.set_volume_panel_visible(getattr(self, "show_chart_volume", False))
        if not bool(getattr(chart, "_sopotek_trade_signal_hooks_installed", False)):
            chart.sigTradeLevelRequested.connect(self._handle_chart_trade_level_request)
            chart.sigTradeLevelChanged.connect(self._handle_chart_trade_level_changed)
            chart.sigTradeContextAction.connect(self._handle_chart_trade_context_action)
            chart.sigTimeframeSelected.connect(lambda timeframe, chart_ref=chart: self._set_chart_timeframe(chart_ref, timeframe))
            chart.sigActivated.connect(lambda chart_ref, _chart=chart: self._set_active_chart_widget(_chart, refresh_orderbook=True))
            chart._sopotek_trade_signal_hooks_installed = True
        return chart

    def _handle_chart_trade_level_request(self, payload):
        if not isinstance(payload, dict):
            return
        price = self._safe_float(payload.get("price"))
        if price is None or price <= 0:
            return
        symbol = str(payload.get("symbol") or self._current_chart_symbol() or getattr(self, "symbol", "")).strip()
        if not symbol:
            return
        self._open_manual_trade(
            {
                "symbol": symbol,
                "order_type": "limit",
                "price": price,
                "source": "chart_double_click",
                "timeframe": payload.get("timeframe"),
            }
        )

    def _handle_chart_trade_level_changed(self, payload):
        if not isinstance(payload, dict):
            return
        window = self.detached_tool_windows.get("manual_trade_ticket")
        if not self._is_qt_object_alive(window):
            return
        symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
        current_symbol = str(symbol_picker.currentText() or "").strip() if symbol_picker is not None else ""
        if str(payload.get("symbol") or "").strip() != current_symbol:
            return

        level = str(payload.get("level") or "").strip().lower()
        price = self._safe_float(payload.get("price"))
        if price is None or price <= 0:
            return

        if level == "entry":
            self._set_manual_trade_order_type(window, "limit")
            self._set_manual_trade_text_field(window, "_manual_trade_price_input", price)
        elif level == "stop_loss":
            self._set_manual_trade_text_field(window, "_manual_trade_stop_loss_input", price)
        elif level == "take_profit":
            self._set_manual_trade_text_field(window, "_manual_trade_take_profit_input", price)

    def _handle_chart_trade_context_action(self, payload):
        if not isinstance(payload, dict):
            return
        action = str(payload.get("action") or "").strip().lower()
        symbol = str(payload.get("symbol") or self._current_chart_symbol() or "").strip()
        price = self._safe_float(payload.get("price"))
        if action == "clear_levels":
            self._clear_trade_overlays(symbol=symbol)
            window = self.detached_tool_windows.get("manual_trade_ticket")
            if self._is_qt_object_alive(window):
                ticket_symbol = str(getattr(getattr(window, "_manual_trade_symbol_picker", None), "currentText", lambda: "")()).strip()
                if ticket_symbol == symbol:
                    self._set_manual_trade_text_field(window, "_manual_trade_price_input", None)
                    self._set_manual_trade_text_field(window, "_manual_trade_stop_loss_input", None)
                    self._set_manual_trade_text_field(window, "_manual_trade_take_profit_input", None)
            return
        if price is None or price <= 0 or not symbol:
            return

        if action == "buy_limit":
            self._open_manual_trade(
                {
                    "symbol": symbol,
                    "side": "buy",
                    "order_type": "limit",
                    "price": price,
                    "source": "chart_context_menu",
                    "timeframe": payload.get("timeframe"),
                }
            )
            return
        if action == "sell_limit":
            self._open_manual_trade(
                {
                    "symbol": symbol,
                    "side": "sell",
                    "order_type": "limit",
                    "price": price,
                    "source": "chart_context_menu",
                    "timeframe": payload.get("timeframe"),
                }
            )
            return

        window = self.detached_tool_windows.get("manual_trade_ticket")
        if not self._is_qt_object_alive(window):
            self._open_manual_trade(
                {
                    "symbol": symbol,
                    "order_type": "limit",
                    "price": price if action == "set_entry" else None,
                    "stop_loss": price if action == "set_stop_loss" else None,
                    "take_profit": price if action == "set_take_profit" else None,
                    "source": "chart_context_menu",
                    "timeframe": payload.get("timeframe"),
                }
            )
            return

        symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
        if symbol_picker is not None:
            symbol_picker.setCurrentText(symbol)
        if action == "set_entry":
            self._set_manual_trade_order_type(window, "limit")
            self._set_manual_trade_text_field(window, "_manual_trade_price_input", price)
        elif action == "set_stop_loss":
            self._set_manual_trade_text_field(window, "_manual_trade_stop_loss_input", price)
        elif action == "set_take_profit":
            self._set_manual_trade_text_field(window, "_manual_trade_take_profit_input", price)
        self._refresh_manual_trade_ticket(window)

    def _find_chart_tab(self, symbol, timeframe):
        if not self._chart_tabs_ready():
            return -1

        for i in range(self.chart_tabs.count()):
            page = self.chart_tabs.widget(i)
            for chart in self._chart_widgets_in_page(page):
                if chart.symbol == symbol and chart.timeframe == timeframe:
                    return i
        return -1

    def _open_symbol_chart(self, symbol, timeframe=None):
        target_symbol = (symbol or "").strip().upper()
        if not target_symbol:
            return

        target_timeframe = timeframe or self.current_timeframe
        detached_window = self._find_detached_chart_window(target_symbol, target_timeframe) or self.detached_tool_windows.get(
            self._single_chart_window_key(target_symbol, target_timeframe)
        )
        if self._is_qt_object_alive(detached_window):
            detached_window.showNormal()
            detached_window.raise_()
            detached_window.activateWindow()
            page = detached_window.centralWidget()
            if page is None:
                return
            for chart in self._chart_widgets_in_page(page):
                self._schedule_chart_data_refresh(chart)
            return

        existing_index = self._find_chart_tab(target_symbol, target_timeframe)
        if existing_index >= 0:
            self.chart_tabs.setCurrentIndex(existing_index)
            return

        self.training_status[target_symbol] = "TRAINING"
        self._create_chart_tab(target_symbol, target_timeframe)

    def _open_symbol_from_picker(self):
        if self.symbol_picker is None:
            return

        self._open_symbol_chart(self.symbol_picker.currentText(), self.current_timeframe)

    def _set_chart_timeframe(self, chart, tf="1h"):
        normalized_tf = str(tf or self.current_timeframe or "1h").strip().lower() or "1h"
        page = self._chart_page_for_widget(chart)
        if page is None:
            return
        charts = self._chart_widgets_in_page(page)

        self.current_timeframe = normalized_tf
        self.controller.time_frame = normalized_tf
        self.settings.setValue("terminal/current_timeframe", normalized_tf)
        self._set_active_timeframe_button(normalized_tf)

        if not charts:
            return

        anchor_chart = chart if chart in charts else charts[0]
        for chart_widget in charts:
            if hasattr(chart_widget, "set_timeframe"):
                chart_widget.set_timeframe(normalized_tf, emit_signal=False)
            else:
                chart_widget.timeframe = normalized_tf
                if hasattr(chart_widget, "refresh_context_display"):
                    chart_widget.refresh_context_display()
            self._schedule_chart_data_refresh(chart_widget)

        if self.symbol_picker is not None:
            self.symbol_picker.setCurrentText(anchor_chart.symbol)

        if self._chart_tabs_ready():
            try:
                index = self.chart_tabs.indexOf(page)
            except RuntimeError:
                index = -1
            if index >= 0:
                self.chart_tabs.setCurrentIndex(index)
                self.chart_tabs.setTabText(index, self._chart_page_title(page, fallback_index=index))

        if page is not None:
            window = page.window()
            if window is not None and window is not self and getattr(window, "_contains_chart_page", False):
                window.setWindowTitle(self._chart_page_title(page))
                self._save_detached_chart_layouts()

        self._last_chart_request_key = (anchor_chart.symbol, normalized_tf)
        self._request_active_orderbook()

    def _set_timeframe(self, tf="1h"):
        chart = self._current_chart_widget()
        if chart is None and self._chart_tabs_ready():
            try:
                chart = self.chart_tabs.currentWidget()
            except RuntimeError:
                chart = None
        self._set_chart_timeframe(chart, tf)

    def _toggle_bid_ask_lines(self, checked):
        self.show_bid_ask_lines = bool(checked)

        for chart in self._iter_chart_widgets():
            chart.set_bid_ask_lines_visible(self.show_bid_ask_lines)

    def _toggle_chart_volume(self, checked):
        self.show_chart_volume = bool(checked)
        for chart in self._iter_chart_widgets():
            chart.set_volume_panel_visible(self.show_chart_volume)
        settings = getattr(self, "settings", None)
        if settings is not None:
            settings.setValue("terminal/show_chart_volume", self.show_chart_volume)

    # ==========================================================
    # UPDATE METHODS
    # ==========================================================
    def _update_chart(self, symbol, df):
        if self._ui_shutting_down:
            return

        fallback_frame = candles_to_df(df)
        symbol_buffers = getattr(self.controller, "candle_buffers", {}).get(symbol, {})

        for chart in self._iter_chart_widgets():
            if chart.symbol != symbol:
                continue
            chart_frame = symbol_buffers.get(chart.timeframe) if isinstance(symbol_buffers, dict) else None
            if chart_frame is None:
                chart_frame = fallback_frame
            else:
                chart_frame = candles_to_df(chart_frame)
            chart.update_candles(chart_frame)

        self.heartbeat.setStyleSheet("color: green;")
        if getattr(self.controller, "news_draw_on_chart", False) and hasattr(self.controller, "request_news"):
            asyncio.get_event_loop().create_task(self.controller.request_news(symbol))

    def _update_equity(self, equity):
        if getattr(self, "equity_summary_label", None) is not None:
            self.equity_summary_label.setText(f"Equity: {float(equity):,.2f}")
        if getattr(self, "equity_curve", None) is not None:
            equity_series = list(self._performance_series())
            equity_timestamps = list(self._performance_time_series())
            if equity_timestamps and len(equity_timestamps) == len(equity_series):
                self.equity_curve.setData(equity_timestamps, equity_series)
            else:
                self.equity_curve.setData(equity_series)
        self._refresh_performance_views()

    def _strategy_family_name(self, strategy_name):
        normalized = Strategy.normalize_strategy_name(strategy_name)
        if " | " in normalized:
            return normalized.split(" | ", 1)[0].strip()
        return Strategy.resolve_signal_strategy_name(normalized)

    def _grouped_strategy_names(self, selected_strategy=None):
        names = list(Strategy.AVAILABLE_STRATEGIES)
        selected = str(selected_strategy or "").strip()
        if selected and selected not in names:
            names.append(selected)

        grouped = []
        seen = set()
        core_families = list(getattr(Strategy, "CORE_STRATEGIES", []) or [])
        for family in core_families:
            family_items = [name for name in names if self._strategy_family_name(name) == family]
            if not family_items:
                continue
            family_items.sort(key=lambda item: (0 if Strategy.normalize_strategy_name(item) == family else 1, item))
            grouped.append(family_items)
            seen.update(family_items)

        remaining = [name for name in names if name not in seen]
        if remaining:
            remaining.sort()
            grouped.append(remaining)
        return grouped

    def _populate_strategy_picker(self, picker, selected_strategy=None):
        if picker is None:
            return
        target = Strategy.normalize_strategy_name(selected_strategy or "")
        blocked = picker.blockSignals(True)
        picker.clear()
        first_group = True
        for group in self._grouped_strategy_names(selected_strategy=target):
            if not group:
                continue
            if not first_group:
                picker.insertSeparator(picker.count())
            for name in group:
                picker.addItem(name)
            first_group = False
        if target:
            if picker.findText(target) < 0:
                if picker.count() > 0:
                    picker.insertSeparator(picker.count())
                picker.addItem(target)
            picker.setCurrentText(target)
        picker.blockSignals(blocked)

    def _lookup_symbol_mid_price(self, symbol):
        ticker = None
        ticker_buffer = getattr(self.controller, "ticker_buffer", None)
        if ticker_buffer is not None and hasattr(ticker_buffer, "get"):
            try:
                ticker = ticker_buffer.get(symbol)
            except (AttributeError, KeyError, TypeError, RuntimeError):
                ticker = None
        if not isinstance(ticker, dict):
            ticker_stream = getattr(self.controller, "ticker_stream", None)
            if ticker_stream is not None and hasattr(ticker_stream, "get"):
                try:
                    ticker = ticker_stream.get(symbol)
                except (AttributeError, KeyError, TypeError, RuntimeError):
                    ticker = None
        if not isinstance(ticker, dict):
            return None

        candidates = []
        for key in ("price", "last", "close", "bid", "ask"):
            numeric = _coerce_float(ticker.get(key))
            if numeric is None:
                continue
            if numeric > 0:
                candidates.append(numeric)
        if not candidates:
            return None
        if len(candidates) >= 2 and ticker.get("bid") is not None and ticker.get("ask") is not None:
            bid = _coerce_float(ticker.get("bid"))
            ask = _coerce_float(ticker.get("ask"))
            if bid is not None and ask is not None and bid > 0 and ask > 0:
                return (bid + ask) / 2.0
        return candidates[0]

    def _normalize_position_entry(self, raw):
        return normalize_position_entry(self, raw)

    def _portfolio_positions_snapshot(self):
        portfolio = getattr(self.controller, "portfolio", None)
        positions = []
        if portfolio is None:
            return positions

        raw_positions: list[object] = []
        get_positions = getattr(portfolio, "get_positions", None)
        if callable(get_positions):
            try:
                raw_positions = get_positions() or []
            except (AttributeError, RuntimeError, TypeError, ValueError):
                raw_positions = []
        if isinstance(raw_positions, dict):
            raw_positions = list(raw_positions.values())
        if not raw_positions:
            stored_positions = getattr(portfolio, "positions", {})
            if isinstance(stored_positions, dict):
                raw_positions = list(stored_positions.values())
            elif isinstance(stored_positions, (list, tuple)):
                raw_positions = list(stored_positions)

        for pos in raw_positions:
            normalized = self._normalize_position_entry(pos)
            if normalized is not None and normalized["amount"] > 0:
                positions.append(normalized)
        return positions

    def _active_positions_snapshot(self):
        normalized_positions = []
        for raw in list(getattr(self, "_latest_positions_snapshot", []) or []):
            normalized = self._normalize_position_entry(raw)
            if normalized is not None and float(normalized.get("amount", 0.0) or 0.0) > 0:
                normalized_positions.append(normalized)
        if normalized_positions:
            return normalized_positions
        return list(self._portfolio_positions_snapshot() or [])

    def _active_open_orders_snapshot(self):
        normalized_orders = []
        for raw in list(getattr(self, "_latest_open_orders_snapshot", []) or []):
            normalized = self._normalize_open_order_entry(raw)
            if normalized is not None:
                normalized_orders.append(normalized)
        return normalized_orders

    def _runtime_metrics_snapshot(self):
        return build_runtime_metrics_snapshot(self)

    def _populate_positions_table(self, positions):
        populate_positions_table(self, positions)

    def _apply_positions_filter(self):
        apply_positions_filter(self)

    def _build_position_close_button(self, position, compact=False):
        button = QPushButton("->" if compact else "-> Close")
        button.setStyleSheet(self._action_button_style())
        button.setToolTip("Close this position with a market order.")
        normalized = self._normalize_position_entry(position) or {}
        button.setEnabled(
            bool(getattr(self.controller, "broker", None))
            and bool(str(normalized.get("symbol") or "").strip())
            and float(normalized.get("amount", 0.0) or 0.0) > 0
        )
        button.clicked.connect(
            lambda _checked=False, payload=dict(normalized): self._confirm_close_position(payload)
        )
        return button

    def _confirm_close_position(self, position):
        normalized = self._normalize_position_entry(position)
        if normalized is None:
            QMessageBox.warning(self, "Close Position", "The selected position is no longer available.")
            return

        symbol = str(normalized.get("symbol") or "").strip().upper()
        amount = float(normalized.get("amount", 0.0) or 0.0)
        if not symbol or amount <= 0:
            QMessageBox.warning(self, "Close Position", "Unable to determine a valid position to close.")
            return
        side_label = str(normalized.get("position_side") or normalized.get("side") or "").strip().upper()
        descriptor = f"{side_label} {symbol}".strip()

        confirm = QMessageBox.question(
            self,
            "Close Position",
            f"Close {amount:.6f}".rstrip("0").rstrip(".") + f" {descriptor} with a market order?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._run_close_position_task(symbol, amount=amount, position=normalized)

    def _run_close_position_task(self, symbol, amount=None, position=None):
        runner = self._close_position_async(symbol, amount=amount, position=position, show_dialog=True)
        create_task = getattr(self.controller, "_create_task", None)
        if callable(create_task):
            create_task(runner, "close_single_position")
        else:
            asyncio.create_task(runner)

    async def _close_position_async(self, symbol, amount=None, position=None, show_dialog=True):
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "close_market_chat_position"):
            if show_dialog:
                QMessageBox.warning(self, "Close Position", "Close-position controls are not available right now.")
            return

        try:
            result = await controller.close_market_chat_position(symbol, amount=amount, position=position)
            result_payload = result if isinstance(result, dict) else {}
            result_status = str(result_payload.get("status") or "submitted").strip() or "submitted"
            status_text = result_status.replace("_", " ").upper()
            order_id = result_payload.get("order_id") or result_payload.get("id")
            if order_id is None and isinstance(result, str):
                order_id = result
            position_payload = dict(position) if isinstance(position, dict) else None
            amount_text = ""
            if amount is not None:
                amount_text = f" {float(amount):.6f}".rstrip("0").rstrip(".")
            side_text = ""
            if position_payload is not None:
                resolved_side = str(position_payload.get("position_side") or position_payload.get("side") or "").strip().upper()
                if resolved_side:
                    side_text = f" [{resolved_side}]"
            self.system_console.log(f"Close position {status_text}: {symbol}{side_text}{amount_text}", "INFO")
            if hasattr(controller, "queue_trade_audit"):
                controller.queue_trade_audit(
                    "close_position_success",
                    status=result_status,
                    symbol=symbol,
                    side="sell" if str((position_payload or {}).get("position_side") or (position_payload or {}).get("side") or "").strip().lower() != "short" else "buy",
                    order_type="market",
                    source="terminal",
                    order_id=order_id,
                    payload={"amount": amount, "position": position_payload if position_payload is not None else position},
                    message=f"Submitted close-position order for {symbol}.",
                )
            self._schedule_positions_refresh()
            self._refresh_position_analysis_window()
            if show_dialog:
                self._show_async_message(
                    "Close Position",
                    f"{status_text.title()} close order for {symbol}.",
                    QMessageBox.Icon.Information,
                )
        except Exception as exc:
            self.logger.exception("Close-position request failed")
            self.system_console.log(f"Close position failed for {symbol}: {exc}", "ERROR")
            if hasattr(controller, "queue_trade_audit"):
                controller.queue_trade_audit(
                    "close_position_error",
                    status="error",
                    symbol=symbol,
                    order_type="market",
                    source="terminal",
                    message=str(exc),
                    payload={"amount": amount, "position": dict(position or {}) if isinstance(position, dict) else position},
                )
            if show_dialog:
                self._show_async_message("Close Position Failed", str(exc), QMessageBox.Icon.Critical)

    def _show_position_details(self, position):
        """Show detailed position information dialog."""
        from ui.components.dialogs.position_details_dialog import PositionDetailsDialog
        
        # Enrich position with additional data if available
        normalized = self._normalize_position_entry(position)
        if normalized is None:
            QMessageBox.warning(self, "Position Details", "Unable to load position details.")
            return
        
        # Get venue information
        venue = getattr(self.controller.broker if hasattr(self.controller, "broker") else None, "venue_key", "UNKNOWN")
        
        # Add extra fields to position data for display
        enriched_position = dict(normalized)
        enriched_position["venue"] = str(venue or "").upper()
        
        # Try to add liquidation prices if available
        broker = getattr(self.controller, "broker", None)
        if broker and hasattr(broker, "get_liquidation_prices"):
            try:
                liq_prices = broker.get_liquidation_prices(
                    symbol=normalized.get("symbol"),
                    side=normalized.get("side")
                )
                if isinstance(liq_prices, dict):
                    enriched_position["intraday_liquidation_price"] = liq_prices.get("intraday")
                    enriched_position["overnight_liquidation_price"] = liq_prices.get("overnight")
            except Exception:
                pass  # If not available, just skip
        
        dialog = PositionDetailsDialog(
            self,
            enriched_position,
            terminal=self,
            on_close_position=self._confirm_close_position,
            on_close_all=self._close_all_positions,
        )
        dialog.exec()

    def _normalize_open_order_entry(self, order):
        return normalize_open_order_entry(self, order)

    def _populate_assets_table(self, balances):
        populate_assets_table(self, balances)

    def _apply_assets_filter(self):
        apply_assets_filter(self)

    def _populate_open_orders_table(self, orders):
        populate_open_orders_table(self, orders)

    def _apply_open_orders_filter(self):
        apply_open_orders_filter(self)

    def _populate_order_history_table(self, orders):
        populate_order_history_table(self, orders)

    def _apply_order_history_filter(self):
        apply_order_history_filter(self)

    def _populate_trade_history_table(self, trades):
        populate_trade_history_table(self, trades)

    def _apply_trade_history_filter(self):
        apply_trade_history_filter(self)

    async def _refresh_assets_async(self):
        await refresh_assets_async(self)

    async def _refresh_positions_async(self):
        await refresh_positions_async(self)

    def _schedule_assets_refresh(self):
        schedule_assets_refresh(self)

    def _schedule_positions_refresh(self):
        schedule_positions_refresh(self)

    async def _refresh_order_history_async(self):
        await refresh_order_history_async(self)

    def _schedule_order_history_refresh(self):
        schedule_order_history_refresh(self)

    async def _refresh_trade_history_async(self):
        await refresh_trade_history_async(self)

    def _schedule_trade_history_refresh(self):
        schedule_trade_history_refresh(self)

    def _resolve_position_analysis_metric(self, account, balances, *keys):
        candidates = []
        for key in keys:
            if key is None:
                continue
            key_text = str(key)
            variants = {
                key_text,
                key_text.lower(),
                key_text.upper(),
                key_text.replace("_", ""),
                key_text.replace("_", "").lower(),
                key_text.replace("_", "").upper(),
            }
            variants.update(
                {
                    key_text.replace("_", " "),
                    key_text.replace("_", "-"),
                    key_text.replace("_", " ").title(),
                    "".join(part.capitalize() for part in key_text.split("_")),
                }
            )
            for variant in variants:
                if variant not in candidates:
                    candidates.append(variant)

        for source in (account, balances):
            if not isinstance(source, dict):
                continue
            for candidate in candidates:
                if candidate in source:
                    numeric = self._safe_float(source.get(candidate))
                    if numeric is not None:
                        return numeric
        return None

    def _position_analysis_has_key(self, account, balances, *keys):
        candidates = []
        for key in keys:
            if key is None:
                continue
            key_text = str(key)
            variants = {
                key_text,
                key_text.lower(),
                key_text.upper(),
                key_text.replace("_", ""),
                key_text.replace("_", "").lower(),
                key_text.replace("_", "").upper(),
                key_text.replace("_", " "),
                key_text.replace("_", "-"),
                "".join(part.capitalize() for part in key_text.split("_")),
            }
            for variant in variants:
                if variant not in candidates:
                    candidates.append(variant)

        for source in (account, balances):
            if not isinstance(source, dict):
                continue
            for candidate in candidates:
                if candidate in source:
                    return True
        return False

    def _position_analysis_metric_labels(self, payload):
        account = dict(payload.get("account") or {})
        balances = dict(payload.get("balances") or {})

        equity_label = "Equity"
        if self._position_analysis_has_key(account, balances, "nav"):
            equity_label = "NAV"
        elif self._position_analysis_has_key(account, balances, "net_liquidation"):
            equity_label = "Net Liquidation"
        elif self._position_analysis_has_key(account, balances, "account_value", "total_account_value"):
            equity_label = "Account Value"

        balance_label = "Balance"
        if self._position_analysis_has_key(account, balances, "cash", "cash_balance"):
            balance_label = "Cash"

        available_label = "Available Margin"
        if self._position_analysis_has_key(account, balances, "buying_power", "buyingPower"):
            available_label = "Buying Power"
        elif self._position_analysis_has_key(account, balances, "free"):
            available_label = "Free Balance"

        used_label = "Margin Used"
        if self._position_analysis_has_key(account, balances, "used") and not self._position_analysis_has_key(account, balances, "margin_used", "marginUsed"):
            used_label = "Used Balance"

        ratio_label = "Margin Ratio"
        if self._position_analysis_has_key(account, balances, "margin_closeout_percent", "marginCloseoutPercent"):
            ratio_label = "Margin Closeout %"

        return {
            "equity": equity_label,
            "balance": balance_label,
            "available": available_label,
            "used": used_label,
            "ratio": ratio_label,
        }

    def _position_analysis_window_payload(self):
        broker = getattr(self.controller, "broker", None)
        exchange = str(getattr(broker, "exchange_name", "") or "").lower()
        balances = dict(getattr(self.controller, "balances", {}) or {})
        account = dict((balances or {}).get("raw", {}) or {})
        positions = list(self._active_positions_snapshot() or [])
        financing_total = sum(
            self._safe_float(item.get("financing"), 0.0) or 0.0
            for item in positions
            if isinstance(item, dict)
        )
        trade_records_getter = getattr(self, "_performance_trade_records", None)
        trade_records = trade_records_getter() if callable(trade_records_getter) else []
        fee_values = []
        for trade in trade_records:
            if not isinstance(trade, dict):
                continue
            fee = self._safe_float(trade.get("fee"))
            if fee is not None:
                fee_values.append(fee)
        payload = {
            "available": broker is not None,
            "exchange": exchange or "-",
            "account": account,
            "balances": balances,
            "positions": positions,
            "financing_total": financing_total,
            "fee_total": sum(fee_values) if fee_values else 0.0,
            "fee_count": len(fee_values),
        }

        nav = self._resolve_position_analysis_metric(account, balances, "nav", "equity", "net_liquidation", "account_value", "total_account_value")
        balance = self._resolve_position_analysis_metric(account, balances, "balance", "cash", "cash_balance")
        margin_used = self._resolve_position_analysis_metric(account, balances, "margin_used", "used_margin", "used")
        margin_available = self._resolve_position_analysis_metric(account, balances, "margin_available", "free_margin", "free")
        unrealized = self._resolve_position_analysis_metric(account, balances, "unrealized_pl", "unrealized_pnl", "upl", "pl_unrealized")
        realized = self._resolve_position_analysis_metric(account, balances, "realized_pl", "realized_pnl", "pl")
        position_value = self._resolve_position_analysis_metric(account, balances, "position_value", "positions_value", "exposure", "gross_exposure")
        margin_closeout = self._resolve_position_analysis_metric(account, balances, "margin_closeout_percent", "margin_ratio")
        guard_snapshot = {}
        controller_guard = getattr(self.controller, "margin_closeout_snapshot", None)
        if callable(controller_guard):
            try:
                guard_snapshot = dict(controller_guard(balances) or {})
            except Exception:
                guard_snapshot = {}

        if nav is None:
            nav = balance
        if balance is None:
            balance = nav
        if unrealized is None:
            unrealized = sum(float(item.get("pnl", 0.0) or 0.0) for item in positions)
        if realized is None:
            realized = sum(float(item.get("realized_pnl", 0.0) or 0.0) for item in positions)
        if position_value is None:
            position_value = sum(float(item.get("value", 0.0) or 0.0) for item in positions)
        if margin_used is None:
            margin_used = sum(float(item.get("margin_used", 0.0) or 0.0) for item in positions)

        payload["nav"] = nav
        payload["balance"] = balance
        payload["margin_used"] = margin_used
        payload["margin_available"] = margin_available
        payload["unrealized_pl"] = unrealized
        payload["realized_pl"] = realized
        payload["position_value"] = position_value
        payload["margin_closeout_percent"] = margin_closeout
        payload["margin_closeout_guard"] = guard_snapshot
        payload["labels"] = self._position_analysis_metric_labels(payload)
        return payload

    def _build_position_analysis_html(self, payload):
        broker_name = html.escape(str(payload.get("exchange", "-") or "-").upper())
        labels = dict(payload.get("labels") or {})
        equity_label = html.escape(str(labels.get("equity") or "Equity"))
        balance_label = html.escape(str(labels.get("balance") or "Balance"))
        available_label = html.escape(str(labels.get("available") or "Available Margin"))
        used_label = html.escape(str(labels.get("used") or "Margin Used"))
        ratio_label = html.escape(str(labels.get("ratio") or "Margin Ratio"))
        financing_total = self._safe_float(payload.get("financing_total"), 0.0) or 0.0
        fee_total = self._safe_float(payload.get("fee_total"), 0.0) or 0.0
        fee_count = int(payload.get("fee_count") or 0)
        fee_suffix = f" across <b>{fee_count}</b> recorded fills" if fee_count else ""
        if not payload.get("available"):
            return (
                "<h3 style='margin-top:0;'>Position Analysis</h3>"
                "<p>Connect a broker to see account metrics, open positions, exposure, and P/L analysis here.</p>"
            )

        positions = list(payload.get("positions", []) or [])
        if not positions:
            equity_text = self._format_currency(payload.get("nav"))
            balance_text = self._format_currency(payload.get("balance"))
            return (
                "<h3 style='margin-top:0;'>Position Analysis</h3>"
                f"<p>Broker <b>{broker_name}</b> is connected. No open positions were found.</p>"
                f"<p>{equity_label}: <b>{equity_text}</b> | {balance_label}: <b>{balance_text}</b></p>"
                f"<p>Open-position financing: <b>{self._format_currency(financing_total)}</b> | "
                f"Tracked broker fees: <b>{self._format_currency(fee_total)}</b>{fee_suffix}</p>"
            )

        total_unrealized = sum(float(item.get("pnl", 0.0) or 0.0) for item in positions)
        total_realized = sum(float(item.get("realized_pnl", 0.0) or 0.0) for item in positions)
        total_margin = sum(float(item.get("margin_used", 0.0) or 0.0) for item in positions)
        long_count = sum(1 for item in positions if item.get("side") != "short")
        short_count = len(positions) - long_count
        biggest_winner = max(positions, key=lambda item: float(item.get("pnl", 0.0) or 0.0))
        biggest_loser = min(positions, key=lambda item: float(item.get("pnl", 0.0) or 0.0))
        concentrated = max(positions, key=lambda item: float(item.get("value", 0.0) or 0.0))
        nav = float(payload.get("nav", 0.0) or 0.0)
        margin_available = self._safe_float(payload.get("margin_available"))
        margin_closeout = payload.get("margin_closeout_percent")
        margin_guard = dict(payload.get("margin_closeout_guard") or {})

        bullets = [
            f"Broker <b>{broker_name}</b> {equity_label.lower()} is <b>{self._format_currency(nav)}</b> with {balance_label.lower()} <b>{self._format_currency(payload.get('balance'))}</b>.",
            f"Open positions: <b>{len(positions)}</b> total, with <b>{long_count}</b> long and <b>{short_count}</b> short exposures.",
            f"Combined unrealized P/L is <b>{self._format_currency(total_unrealized)}</b>; realized P/L contribution in open positions is <b>{self._format_currency(total_realized)}</b>.",
            f"Aggregate position {used_label.lower()} is <b>{self._format_currency(total_margin)}</b>.",
            f"Open-position financing totals <b>{self._format_currency(financing_total)}</b>; tracked broker transaction fees total <b>{self._format_currency(fee_total)}</b>{fee_suffix}.",
            f"Biggest winner: <b>{html.escape(biggest_winner.get('symbol', '-'))}</b> at <b>{self._format_currency(biggest_winner.get('pnl'))}</b>.",
            f"Biggest loser: <b>{html.escape(biggest_loser.get('symbol', '-'))}</b> at <b>{self._format_currency(biggest_loser.get('pnl'))}</b>.",
            f"Largest exposure by value is <b>{html.escape(concentrated.get('symbol', '-'))}</b> at <b>{self._format_currency(concentrated.get('value'))}</b>.",
        ]
        if margin_available is not None:
            bullets.insert(1, f"{available_label} is <b>{self._format_currency(margin_available)}</b>.")
        if margin_closeout is not None:
            bullets.append(f"{ratio_label} is <b>{float(margin_closeout):.4f}</b>.")
        else:
            bullets.append("Broker did not expose a margin-ratio style metric in the current balance payload.")
        if margin_guard.get("enabled"):
            state = "blocking new trades" if margin_guard.get("blocked") else "monitoring"
            bullets.append(
                f"Margin closeout guard is <b>{state}</b> at <b>{float(margin_guard.get('threshold', 0.0) or 0.0):.2%}</b>."
            )

        return (
            "<h3 style='margin-top:0;'>Position Analysis</h3>"
            "<ul style='margin-top:6px;'>"
            + "".join(f"<li>{item}</li>" for item in bullets)
            + "</ul>"
        )

    def _refresh_position_analysis_window(self, window=None):
        window = window or self.detached_tool_windows.get("position_analysis")
        if not self._is_qt_object_alive(window):
            return

        summary = getattr(window, "_position_analysis_summary", None)
        close_all_btn = getattr(window, "_position_analysis_close_all", None)
        table = getattr(window, "_position_analysis_table", None)
        details = getattr(window, "_position_analysis_details", None)
        if summary is None or table is None or details is None:
            return

        payload = self._position_analysis_window_payload()
        window._position_analysis_payload = payload

        if not payload.get("available"):
            summary.setText("Position analysis is available after a broker is connected.")
            table.setRowCount(0)
            if close_all_btn is not None:
                close_all_btn.setEnabled(False)
            details.setHtml(self._build_position_analysis_html(payload))
            return

        positions = list(payload.get("positions", []) or [])
        if close_all_btn is not None:
            close_all_btn.setEnabled(bool(positions))
        exchange_label = str(payload.get("exchange") or "-").upper()
        labels = dict(payload.get("labels") or {})
        equity_label = str(labels.get("equity") or "Equity")
        balance_label = str(labels.get("balance") or "Balance")
        available_label = str(labels.get("available") or "Available Margin")
        used_label = str(labels.get("used") or "Margin Used")
        summary.setText(
            f"Broker {exchange_label} | {equity_label} {self._format_currency(payload.get('nav'))} | {balance_label} {self._format_currency(payload.get('balance'))} | "
            f"Unrealized P/L {self._format_currency(payload.get('unrealized_pl'))} | {used_label} {self._format_currency(payload.get('margin_used'))} | "
            f"{available_label} {self._format_currency(payload.get('margin_available'))} | Financing {self._format_currency(payload.get('financing_total'))} | "
            f"Fees {self._format_currency(payload.get('fee_total'))}"
        )

        columns = [
            ("Symbol", "symbol"),
            ("Side", "side"),
            ("Units", "units"),
            ("Amount", "amount"),
            ("Entry", "entry_price"),
            ("Mark", "mark_price"),
            ("Value", "value"),
            ("Unrealized P/L", "pnl"),
            ("Realized P/L", "realized_pnl"),
            ("Financing", "financing"),
            ("Margin Used", "margin_used"),
            ("Resettable P/L", "resettable_pl"),
        ]
        table.setRowCount(len(positions))
        for row_index, position in enumerate(positions):
            for col_index, (title, key) in enumerate(columns):
                raw_value = position.get(key, "")
                if isinstance(raw_value, float):
                    if title in {"Symbol", "Side"}:
                        text = str(raw_value)
                    elif title in {"Units", "Amount"}:
                        text = f"{raw_value:.6f}".rstrip("0").rstrip(".")
                    elif title in {"Entry", "Mark"}:
                        text = f"{raw_value:.6f}".rstrip("0").rstrip(".")
                    else:
                        text = f"{raw_value:.2f}"
                else:
                    text = str(raw_value).upper() if title == "Side" else str(raw_value)
                item = QTableWidgetItem(text)
                if title in {"Unrealized P/L", "Realized P/L"}:
                    numeric = self._safe_float(raw_value, 0.0) or 0.0
                    item.setForeground(QColor("#32d296" if numeric >= 0 else "#ef5350"))
                table.setItem(row_index, col_index, item)
            table.setCellWidget(row_index, len(columns), self._build_position_close_button(position, compact=False))

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        details.setHtml(self._build_position_analysis_html(payload))

    def _open_position_analysis_window(self):
        window = self._get_or_create_tool_window(
            "position_analysis",
            "Position Analysis",
            width=1200,
            height=680,
        )

        if getattr(window, "_position_analysis_table", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            summary = QLabel("Loading broker position analysis.")
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
            )
            layout.addWidget(summary)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.addStretch()
            close_all_btn = QPushButton("Close All Positions")
            close_all_btn.setStyleSheet(self._action_button_style())
            close_all_btn.clicked.connect(self._close_all_positions)
            actions.addWidget(close_all_btn)
            layout.addLayout(actions)

            table = QTableWidget()
            table.setColumnCount(13)
            table.setHorizontalHeaderLabels(
                ["Symbol", "Side", "Units", "Amount", "Entry", "Mark", "Value", "Unrealized P/L", "Realized P/L", "Financing", "Margin Used", "Resettable P/L", "Action"]
            )
            layout.addWidget(table)

            details = QTextBrowser()
            details.setStyleSheet(
                "QTextBrowser { background-color: #0b1220; color: #e6edf7; border: 1px solid #20324d; "
                "border-radius: 10px; padding: 12px; }"
            )
            layout.addWidget(details)

            window.setCentralWidget(container)
            window._position_analysis_summary = summary
            window._position_analysis_close_all = close_all_btn
            window._position_analysis_table = table
            window._position_analysis_details = details
            window._position_analysis_payload = {}

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._schedule_positions_refresh())
            sync_timer.timeout.connect(lambda: self._refresh_position_analysis_window(window))
            sync_timer.start(2500)
            window._position_analysis_timer = sync_timer

        self._schedule_positions_refresh()
        self._refresh_position_analysis_window(window)
        window.show()
        window.raise_()
        window.activateWindow()

    # Backward-compatible aliases
    def _oanda_position_window_payload(self):
        return self._position_analysis_window_payload()

    def _build_oanda_positions_analysis_html(self, payload):
        return self._build_position_analysis_html(payload)

    def _refresh_oanda_positions_window(self, window=None):
        return self._refresh_position_analysis_window(window)

    def _open_oanda_positions_window(self):
        return self._open_position_analysis_window()

    def _quant_pm_strategy_exposure_rows(self):
        controller = self.controller
        allocator = getattr(controller, "portfolio_allocator", None)
        portfolio_manager = getattr(getattr(controller, "trading_system", None), "portfolio", None)
        portfolio = getattr(portfolio_manager, "portfolio", None)
        market_prices = getattr(portfolio_manager, "market_prices", {}) or {}
        positions = getattr(portfolio, "positions", {}) or {}
        symbol_map = dict(getattr(allocator, "_symbol_strategy_map", {}) or {})
        current_strategy = str(getattr(controller, "strategy_name", "") or "Unassigned").strip() or "Unassigned"
        rows = {}
        total_exposure = 0.0

        for symbol, position in positions.items():
            quantity = self._safe_float(getattr(position, "quantity", 0.0), 0.0) or 0.0
            if quantity == 0:
                continue
            symbol_text = str(symbol or "").upper().strip()
            price = self._safe_float(market_prices.get(symbol_text), getattr(position, "avg_price", 0.0)) or 0.0
            exposure = abs(quantity * price)
            total_exposure += exposure
            strategy_name = str(symbol_map.get(symbol_text) or current_strategy).strip() or "Unassigned"
            bucket = rows.setdefault(
                strategy_name,
                {"strategy": strategy_name, "symbols": 0, "exposure": 0.0, "weight": 0.0},
            )
            bucket["symbols"] += 1
            bucket["exposure"] += exposure

        if total_exposure > 0:
            for item in rows.values():
                item["weight"] = item["exposure"] / total_exposure

        ordered = sorted(
            rows.values(),
            key=lambda item: (
                self._safe_float(item.get("exposure"), 0.0) or 0.0,
                self._safe_float(item.get("weight"), 0.0) or 0.0,
            ),
            reverse=True,
        )
        return ordered, total_exposure

    def _quant_pm_position_rows(self):
        controller = self.controller
        allocator = getattr(controller, "portfolio_allocator", None)
        portfolio_manager = getattr(getattr(controller, "trading_system", None), "portfolio", None)
        portfolio = getattr(portfolio_manager, "portfolio", None)
        market_prices = getattr(portfolio_manager, "market_prices", {}) or {}
        positions = getattr(portfolio, "positions", {}) or {}
        symbol_map = dict(getattr(allocator, "_symbol_strategy_map", {}) or {})
        current_strategy = str(getattr(controller, "strategy_name", "") or "Unassigned").strip() or "Unassigned"
        rows = []

        for symbol, position in positions.items():
            quantity = self._safe_float(getattr(position, "quantity", 0.0), 0.0) or 0.0
            if quantity == 0:
                continue
            symbol_text = str(symbol or "").upper().strip()
            avg_price = self._safe_float(getattr(position, "avg_price", 0.0), 0.0) or 0.0
            mark_price = self._safe_float(market_prices.get(symbol_text), avg_price) or avg_price
            exposure = quantity * mark_price
            rows.append(
                {
                    "symbol": symbol_text,
                    "strategy": str(symbol_map.get(symbol_text) or current_strategy).strip() or "Unassigned",
                    "quantity": quantity,
                    "entry": avg_price,
                    "mark": mark_price,
                    "exposure": exposure,
                    "abs_exposure": abs(exposure),
                    "direction": "LONG" if quantity > 0 else "SHORT",
                }
            )

        rows.sort(key=lambda item: item.get("abs_exposure", 0.0), reverse=True)
        return rows

    async def _quant_pm_correlation_rows(self, symbols, timeframe="1h", limit=160):
        trading_system = getattr(self.controller, "trading_system", None)
        data_hub = getattr(trading_system, "data_hub", None)
        if data_hub is None:
            return [], "Quant data hub is not active yet."

        unique_symbols = []
        for symbol in symbols:
            normalized = str(symbol or "").upper().strip()
            if normalized and normalized not in unique_symbols:
                unique_symbols.append(normalized)
        unique_symbols = unique_symbols[:6]
        if len(unique_symbols) < 2:
            return [], "At least two active symbols with market data are needed for correlation analysis."

        series_map = {}
        for symbol in unique_symbols:
            try:
                dataset = await data_hub.get_symbol_dataset(symbol=symbol, timeframe=timeframe, limit=limit, prefer_live=False)
            except Exception as exc:
                self.logger.debug("Quant PM dataset load failed for %s: %s", symbol, exc)
                continue
            frame = getattr(dataset, "frame", None)
            if frame is None or frame.empty or "close" not in frame.columns:
                continue
            closes = pd.to_numeric(frame["close"], errors="coerce").dropna()
            returns = closes.pct_change().dropna()
            if len(returns) < 8:
                continue
            series_map[symbol] = returns.reset_index(drop=True)

        ordered_symbols = [symbol for symbol in unique_symbols if symbol in series_map]
        if len(ordered_symbols) < 2:
            return [], "Not enough historical data is available yet for a stable correlation matrix."

        matrix = []
        for left in ordered_symbols:
            row = {"symbol": left}
            left_series = series_map[left]
            for right in ordered_symbols:
                aligned = pd.concat([left_series, series_map[right]], axis=1).dropna()
                if len(aligned) < 6:
                    corr = 0.0
                else:
                    corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
                    if pd.isna(corr):
                        corr = 0.0
                row[right] = float(corr)
            matrix.append(row)

        return matrix, ""

    async def _quant_pm_payload(self):
        controller = self.controller
        trading_system = getattr(controller, "trading_system", None)
        allocator = getattr(controller, "portfolio_allocator", None)
        risk_engine = getattr(controller, "institutional_risk_engine", None)
        behavior_guard = getattr(controller, "behavior_guard", None)
        available = trading_system is not None and allocator is not None and risk_engine is not None

        strategy_rows, strategy_total_exposure = self._quant_pm_strategy_exposure_rows()
        position_rows = self._quant_pm_position_rows()
        live_mode = bool(getattr(controller, "is_live_mode", lambda: False)())
        account_label = str(getattr(controller, "current_account_label", lambda: "Not set")() or "").strip()
        if not account_label or account_label.lower() == "not set":
            account_label = "Profile unavailable"

        equity = None
        equity_source = "unavailable"
        extract_equity = getattr(controller, "_extract_balance_equity_value", None)
        if callable(extract_equity):
            try:
                equity = self._safe_float(extract_equity(getattr(controller, "balances", {}) or {}))
            except Exception:
                equity = None
            if equity is not None:
                equity_source = "broker"

        portfolio_manager = getattr(trading_system, "portfolio", None) if trading_system is not None else None
        if equity is None and portfolio_manager is not None and not live_mode:
            try:
                equity = self._safe_float(portfolio_manager.equity())
            except Exception:
                equity = None
            if equity is not None:
                equity_source = "portfolio"
        if equity is None and not live_mode:
            equity = self._safe_float(getattr(controller, "initial_capital", None))
            if equity is not None:
                equity_source = "initial_capital"

        allocation_snapshot = dict(getattr(controller, "quant_allocation_snapshot", {}) or {})
        risk_snapshot = dict(getattr(controller, "quant_risk_snapshot", {}) or {})
        allocator_status = allocator.status_snapshot() if allocator is not None else {}
        institutional_status = risk_engine.status_snapshot() if risk_engine is not None else {}
        behavior_status = behavior_guard.status_snapshot() if behavior_guard is not None else {}
        health_report = []
        health_report_getter = getattr(controller, "get_health_check_report", None)
        if callable(health_report_getter):
            try:
                health_report = list(health_report_getter() or [])
            except Exception:
                health_report = []
        health_attention = []
        for item in health_report:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip().lower()
            if status not in {"fail", "warn"}:
                continue
            name = str(item.get("name") or "Check").strip() or "Check"
            detail = str(item.get("detail") or "").strip()
            health_attention.append(f"{name}: {detail}" if detail else name)

        active_symbols = [row.get("symbol") for row in position_rows[:6]]
        if len(active_symbols) < 2:
            active_symbols.extend(list(getattr(controller, "symbols", []) or [])[: max(0, 6 - len(active_symbols))])
        correlation_rows, correlation_note = await self._quant_pm_correlation_rows(
            active_symbols,
            timeframe=str(getattr(controller, "time_frame", "1h") or "1h"),
            limit=160,
        )

        return {
            "available": available,
            "exchange": self._active_exchange_name() or "-",
            "account": account_label,
            "mode": "LIVE" if live_mode else "PAPER",
            "health": getattr(controller, "get_health_check_summary", lambda: "Not run")(),
            "equity": equity,
            "equity_source": equity_source,
            "health_attention": health_attention,
            "strategy_rows": strategy_rows,
            "strategy_total_exposure": strategy_total_exposure,
            "position_rows": position_rows,
            "allocation_snapshot": allocation_snapshot,
            "allocator_status": allocator_status,
            "risk_snapshot": risk_snapshot,
            "institutional_status": institutional_status,
            "behavior_status": behavior_status,
            "correlation_rows": correlation_rows,
            "correlation_note": correlation_note,
        }

    def _build_quant_pm_html(self, payload):
        if not payload.get("available"):
            return (
                "<h3 style='margin-top:0;'>Quant PM</h3>"
                "<p>Start the trading system to view allocator budgets, institutional risk, exposure, and correlation analysis.</p>"
            )

        allocation = dict(payload.get("allocation_snapshot") or {})
        risk = dict(payload.get("risk_snapshot") or {})
        behavior = dict(payload.get("behavior_status") or {})
        top_strategy = next(iter(payload.get("strategy_rows") or []), None)
        correlation_note = str(payload.get("correlation_note") or "").strip()
        health_attention = [str(item).strip() for item in (payload.get("health_attention") or []) if str(item).strip()]
        equity_source = str(payload.get("equity_source") or "unavailable").strip().lower()
        equity_text = f"Equity snapshot is <b>{html.escape(self._format_currency(payload.get('equity')))}</b>"
        if equity_source == "broker":
            equity_text = f"Live broker equity snapshot is <b>{html.escape(self._format_currency(payload.get('equity')))}</b>"
        elif equity_source == "unavailable" and str(payload.get("mode") or "").upper() == "LIVE":
            equity_text = "Live broker equity snapshot is <b>unavailable</b>"
        bullets = [
            f"Mode <b>{html.escape(str(payload.get('mode') or '-'))}</b> on broker <b>{html.escape(str(payload.get('exchange') or '-').upper())}</b> for account <b>{html.escape(str(payload.get('account') or '-'))}</b>.",
            f"{equity_text} with health check <b>{html.escape(str(payload.get('health') or 'Not run'))}</b>.",
            f"Allocator model is <b>{html.escape(str((payload.get('allocator_status') or {}).get('allocation_model') or '-'))}</b>; latest target weight is <b>{html.escape(self._format_percent_text(allocation.get('target_weight')))}</b> for strategy <b>{html.escape(str(allocation.get('strategy_name') or '-'))}</b>.",
            f"Institutional risk headline: <b>{html.escape(str(risk.get('reason') or 'No recent risk decision'))}</b>.",
            f"Behavior guard state is <b>{html.escape(str(behavior.get('state') or 'UNKNOWN'))}</b> with summary <b>{html.escape(str(behavior.get('summary') or '-'))}</b>.",
        ]
        if health_attention:
            bullets.append(f"Health attention: <b>{html.escape(' | '.join(health_attention[:3]))}</b>.")
        if top_strategy is not None:
            bullets.append(
                f"Top deployed strategy is <b>{html.escape(str(top_strategy.get('strategy') or '-'))}</b> at <b>{html.escape(self._format_currency(top_strategy.get('exposure')))}</b> exposure."
            )
        if correlation_note:
            bullets.append(html.escape(correlation_note))

        return "<h3 style='margin-top:0;'>Quant PM</h3><ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>"

    def _populate_quant_pm_strategy_table(self, table, rows):
        if table is None or not self._is_qt_object_alive(table):
            return
        rows = list(rows or [])
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("strategy", ""),
                str(int(row.get("symbols", 0) or 0)),
                self._format_currency(row.get("exposure")),
                self._format_percent_text(row.get("weight")),
            ]
            for col_index, value in enumerate(values):
                table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _populate_quant_pm_position_table(self, table, rows, equity):
        if table is None or not self._is_qt_object_alive(table):
            return
        rows = list(rows or [])
        table.setRowCount(len(rows))
        equity_value = self._safe_float(equity, 0.0) or 0.0
        for row_index, row in enumerate(rows):
            exposure = self._safe_float(row.get("exposure"), 0.0) or 0.0
            exposure_pct = (abs(exposure) / equity_value) if equity_value > 0 else None
            values = [
                row.get("symbol", ""),
                row.get("strategy", ""),
                row.get("direction", ""),
                f"{self._safe_float(row.get('quantity'), 0.0) or 0.0:.6f}".rstrip("0").rstrip("."),
                f"{self._safe_float(row.get('entry'), 0.0) or 0.0:.6f}".rstrip("0").rstrip("."),
                f"{self._safe_float(row.get('mark'), 0.0) or 0.0:.6f}".rstrip("0").rstrip("."),
                self._format_currency(exposure),
                self._format_percent_text(exposure_pct),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index == 6:
                    item.setForeground(QColor("#32d296" if exposure >= 0 else "#ef5350"))
                table.setItem(row_index, col_index, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _populate_quant_pm_correlation_table(self, table, rows):
        if table is None or not self._is_qt_object_alive(table):
            return
        rows = list(rows or [])
        if not rows:
            table.clear()
            table.setRowCount(0)
            table.setColumnCount(0)
            return

        symbols = [str(item.get("symbol") or "").upper().strip() for item in rows]
        table.clear()
        table.setColumnCount(len(symbols))
        table.setRowCount(len(symbols))
        table.setHorizontalHeaderLabels(symbols)
        table.setVerticalHeaderLabels(symbols)
        for row_index, row in enumerate(rows):
            for col_index, symbol in enumerate(symbols):
                corr = self._safe_float(row.get(symbol), 0.0) or 0.0
                item = QTableWidgetItem(f"{corr:.2f}")
                intensity = min(255, int(abs(corr) * 160) + 40)
                if corr >= 0:
                    item.setBackground(QColor(40, 70, 40 + intensity // 3, min(220, intensity)))
                    item.setForeground(QColor("#d7ffe9"))
                else:
                    item.setBackground(QColor(80 + intensity // 3, 35, 35, min(220, intensity)))
                    item.setForeground(QColor("#ffe4e8"))
                table.setItem(row_index, col_index, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _schedule_quant_pm_refresh(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        task = getattr(window, "_quant_pm_refresh_task", None)
        if task is not None and not task.done():
            return
        try:
            window._quant_pm_refresh_task = asyncio.get_event_loop().create_task(
                self._refresh_quant_pm_async(window)
            )
        except Exception as exc:
            self.logger.error("Unable to schedule Quant PM refresh: %s", exc)

    async def _refresh_quant_pm_async(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return

        summary = getattr(window, "_quant_pm_summary", None)
        strategy_table = getattr(window, "_quant_pm_strategy_table", None)
        position_table = getattr(window, "_quant_pm_position_table", None)
        correlation_table = getattr(window, "_quant_pm_correlation_table", None)
        details = getattr(window, "_quant_pm_details", None)
        if (
            summary is None
            or strategy_table is None
            or position_table is None
            or correlation_table is None
            or details is None
        ):
            return

        try:
            payload = await self._quant_pm_payload()
        except Exception as exc:
            self.logger.debug("Quant PM refresh failed: %s", exc)
            return

        if window is None or not self._is_qt_object_alive(window):
            return

        window._quant_pm_payload = payload
        allocation = dict(payload.get("allocation_snapshot") or {})
        risk = dict(payload.get("risk_snapshot") or {})
        behavior = dict(payload.get("behavior_status") or {})
        summary.setText(
            f"{payload.get('mode', 'PAPER')} | {str(payload.get('exchange') or '-').upper()} | "
            f"Equity {self._format_currency(payload.get('equity'))} | "
            f"Allocator {self._format_percent_text(allocation.get('target_weight'))} | "
            f"Risk VaR {self._format_percent_text(risk.get('trade_var_pct'))} | "
            f"Behavior {behavior.get('state', 'UNKNOWN')}"
        )
        self._populate_quant_pm_strategy_table(strategy_table, payload.get("strategy_rows"))
        self._populate_quant_pm_position_table(position_table, payload.get("position_rows"), payload.get("equity"))
        self._populate_quant_pm_correlation_table(correlation_table, payload.get("correlation_rows"))
        details.setHtml(self._build_quant_pm_html(payload))

    def _open_quant_pm_window(self):
        window = self._get_or_create_tool_window(
            "quant_pm",
            "Quant PM",
            width=1240,
            height=760,
        )

        if getattr(window, "_quant_pm_summary", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            summary = QLabel("Loading quant PM dashboard.")
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
            )
            layout.addWidget(summary)

            top_row = QHBoxLayout()
            top_row.setSpacing(10)

            strategy_table = QTableWidget()
            strategy_table.setColumnCount(4)
            strategy_table.setHorizontalHeaderLabels(["Strategy", "Symbols", "Exposure", "Weight"])
            top_row.addWidget(strategy_table, 1)

            correlation_table = QTableWidget()
            top_row.addWidget(correlation_table, 1)
            layout.addLayout(top_row)

            position_table = QTableWidget()
            position_table.setColumnCount(8)
            position_table.setHorizontalHeaderLabels(
                ["Symbol", "Strategy", "Direction", "Qty", "Entry", "Mark", "Exposure", "% Equity"]
            )
            layout.addWidget(position_table)

            details = QTextBrowser()
            details.setStyleSheet(
                "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; border-radius: 12px; padding: 12px; }"
            )
            layout.addWidget(details)

            window.setCentralWidget(container)
            window._quant_pm_summary = summary
            window._quant_pm_strategy_table = strategy_table
            window._quant_pm_position_table = position_table
            window._quant_pm_correlation_table = correlation_table
            window._quant_pm_details = details
            window._quant_pm_payload = {}

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._schedule_quant_pm_refresh(window))
            sync_timer.start(3000)
            window._quant_pm_timer = sync_timer

        self._schedule_quant_pm_refresh(window)
        window.show()
        window.raise_()
        window.activateWindow()

    async def _refresh_open_orders_async(self):
        await refresh_open_orders_async(self)

    async def _refresh_broker_status_async(self):
        if self._ui_shutting_down:
            return
        if self._server_authority_active():
            self._last_broker_status_refresh_at = time.monotonic()
            return

        broker = getattr(self.controller, "broker", None)
        if broker is None:
            self._latest_broker_status_snapshot = {"status": "disconnected", "summary": "Disconnected"}
            return

        try:
            status = await broker.fetch_status()
            if isinstance(status, dict):
                status_text = str(status.get("status") or "ok").strip() or "ok"
                broker_label = str(status.get("broker") or getattr(broker, "exchange_name", "") or "").strip().upper()
                summary = f"{broker_label + ' ' if broker_label else ''}{status_text.upper()}".strip()
                self._latest_broker_status_snapshot = {
                    "status": status_text.lower(),
                    "summary": summary or "Connected",
                    "detail": status,
                }
            else:
                summary = str(status or "Connected").strip() or "Connected"
                self._latest_broker_status_snapshot = {
                    "status": summary.lower(),
                    "summary": summary,
                    "detail": status,
                }
        except NotImplementedError:
            summary = "Connected" if getattr(self.controller, "connected", False) else "Unknown"
            self._latest_broker_status_snapshot = {
                "status": summary.lower(),
                "summary": summary,
            }
        except Exception as exc:
            self._latest_broker_status_snapshot = {
                "status": "error",
                "summary": "Error",
                "detail": str(exc),
            }

    def _schedule_broker_status_refresh(self, force=False):
        if self._server_authority_active():
            return
        task = getattr(self, "_broker_status_refresh_task", None)
        if task is not None and not task.done():
            return

        now = time.monotonic()
        if not force and (now - float(getattr(self, "_last_broker_status_refresh_at", 0.0) or 0.0)) < 15.0:
            return

        self._last_broker_status_refresh_at = now
        try:
            self._broker_status_refresh_task = asyncio.get_event_loop().create_task(self._refresh_broker_status_async())
        except Exception as exc:
            self.logger.debug("Unable to schedule broker-status refresh: %s", exc)

    def _schedule_open_orders_refresh(self):
        schedule_open_orders_refresh(self)

    async def _load_initial_terminal_data(self):
        await load_initial_terminal_data(self)

    def _schedule_initial_terminal_data_load(self):
        task = getattr(self, "_initial_terminal_data_task", None)
        if task is not None and not task.done():
            return
        try:
            self._set_workspace_loading_state(
                "Preparing trading workspace...",
                "Connecting the terminal, restoring account state, and loading initial market context. Please wait up to 1 minute.",
            )
            self._initial_terminal_data_task = asyncio.get_event_loop().create_task(self._load_initial_terminal_data())
            current_task = self._initial_terminal_data_task

            def _clear_task(completed):
                if getattr(self, "_initial_terminal_data_task", None) is completed:
                    self._initial_terminal_data_task = None
                try:
                    completed.exception()
                except asyncio.CancelledError:
                    return
                except Exception:
                    self.logger.debug("Initial terminal data task failed", exc_info=True)

            current_task.add_done_callback(_clear_task)
        except Exception as exc:
            self.logger.debug("Unable to schedule initial terminal data load: %s", exc)

    def _refresh_strategy_comparison_panel(self):
        refresh_strategy_comparison_panel(self)

    def _normalize_trade_log_entry(self, trade):
        return normalize_trade_log_entry(self, trade)

    def _format_trade_log_value(self, value):
        return format_trade_log_value(self, value)

    def _format_trade_source_label(self, value):
        return format_trade_source_label(self, value)

    def _trade_log_row_for_entry(self, entry):
        return trade_log_row_for_entry(self, entry)

    def _update_trade_log(self, trade):
        update_trade_log(self, trade)
        self._mark_terminal_refresh_dirty("strategy_comparison", "session_controls")
        if getattr(self, "_ui_shutting_down", False):
            return

        # A fill or cancellation should quickly reconcile every execution tab.
        for attr_name in (
            "_last_assets_refresh_at",
            "_last_positions_refresh_at",
            "_last_open_orders_refresh_at",
            "_last_order_history_refresh_at",
            "_last_trade_history_refresh_at",
        ):
            setattr(self, attr_name, 0.0)

        self._schedule_assets_refresh()
        self._schedule_positions_refresh()
        self._schedule_open_orders_refresh()
        self._schedule_order_history_refresh()
        self._schedule_trade_history_refresh()

    def _apply_trade_log_filter(self):
        apply_trade_log_filter(self)

    def _handle_agent_runtime_event(self, payload):
        if getattr(self, "_ui_shutting_down", False) or not isinstance(payload, dict):
            return
        self._mark_terminal_refresh_dirty("live_agent_timeline")

        symbol = str(payload.get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/")
        timeline_dock = getattr(self, "live_agent_timeline_dock", None)
        if timeline_dock is not None and self._is_qt_object_alive(timeline_dock) and hasattr(self, "_refresh_live_agent_timeline_panel"):
            self._schedule_terminal_refresh()
        timeline_window = getattr(self, "detached_tool_windows", {}).get("agent_timeline")
        if timeline_window is not None and self._is_qt_object_alive(timeline_window) and hasattr(self, "_refresh_agent_timeline_window"):
            self._refresh_agent_timeline_window(window=timeline_window)
        trader_monitor_window = getattr(self, "detached_tool_windows", {}).get("trader_agent_monitor")
        if (
            trader_monitor_window is not None
            and self._is_qt_object_alive(trader_monitor_window)
            and hasattr(self, "_refresh_trader_agent_monitor_window")
        ):
            self._refresh_trader_agent_monitor_window(window=trader_monitor_window)
        window = getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
        selected_symbol = ""
        if window is not None:
            selected_symbol = str(getattr(window, "_strategy_assignment_selected_symbol", "") or "").strip().upper().replace("-", "/").replace("_", "/")
            if not selected_symbol:
                picker = getattr(window, "_strategy_assignment_symbol_picker", None)
                if picker is not None:
                    selected_symbol = str(picker.currentText() or "").strip().upper().replace("-", "/").replace("_", "/")

        kind = str(payload.get("kind") or "").strip().lower()
        event_type = str(payload.get("event_type") or "").strip()
        reason = str(payload.get("reason") or payload.get("message") or "").strip()

        if window is not None and symbol and symbol == selected_symbol:
            message = str(payload.get("message") or "").strip()
            if not message and kind == "memory":
                agent_name = str(payload.get("agent_name") or "Agent").strip() or "Agent"
                stage = str(payload.get("stage") or "updated").strip() or "updated"
                message = f"Live agent update: {agent_name} {stage} for {symbol}."
                if reason:
                    message = f"{message} {reason}"
            self._refresh_strategy_assignment_window(window=window, message=message or None)

        if kind == "bus" and event_type == EventType.RISK_ALERT:
            detail = reason or f"Risk blocked the trade for {symbol or 'the selected symbol'}."
            if hasattr(self, "_push_notification"):
                self._push_notification(
                    "Agent risk blocked",
                    detail,
                    level="WARN",
                    source="risk",
                    dedupe_seconds=10.0,
                )
            if hasattr(self, "system_console"):
                self.system_console.log(
                    f"Agent risk blocked for {symbol or 'symbol'}: {detail}",
                    "WARN",
                )

    async def load_persisted_runtime_data(self):
        await load_persisted_runtime_data(self)

    def _update_ticker(self, symbol, bid, ask):
        if self._ui_shutting_down:
            return

        usd_column = self._market_watch_usd_column()
        usd_text = "-"
        if usd_column is not None:
            usd_value = self._stellar_usd_value(symbol, bid, ask)
            usd_text = self._format_market_watch_usd(usd_value)

        self._queue_market_watch_quote_update(
            symbol,
            bid=self._format_market_watch_number(bid),
            ask=self._format_market_watch_number(ask),
            status="Live",
            usd_value=usd_text,
        )
        self._schedule_market_watch_flush()

        try:
            mid = (float(bid) + float(ask)) / 2
        except Exception:
            mid = 0.0

        self.tick_prices.append(mid)

        if len(self.tick_prices) > 200:
            self.tick_prices.pop(0)

    def _server_authority_active(self):
        controller = getattr(self, "controller", None)
        resolver = getattr(controller, "is_hybrid_server_authoritative", None)
        if callable(resolver):
            try:
                return bool(resolver())
            except Exception:
                return False
        return False

    def apply_server_market_watch_snapshot(self, payload):
        if self._ui_shutting_down or not isinstance(payload, dict):
            return

        snapshots = list(payload.get("market_watch") or payload.get("symbols") or [])
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            identifier = snapshot.get("identifier") if isinstance(snapshot.get("identifier"), dict) else {}
            symbol = self._normalized_symbol(snapshot.get("symbol") or identifier.get("symbol"))
            if not symbol:
                continue
            bid = self._format_market_watch_number(
                self._safe_float(snapshot.get("bid"), self._safe_float(snapshot.get("last_price"), 0.0) or 0.0)
            )
            ask = self._format_market_watch_number(
                self._safe_float(snapshot.get("ask"), self._safe_float(snapshot.get("last_price"), 0.0) or 0.0)
            )
            status = str(snapshot.get("status") or snapshot.get("trend") or "Live").strip() or "Live"
            usd_text = "-"
            usd_column = self._market_watch_usd_column()
            if usd_column is not None:
                usd_value = self._stellar_usd_value(
                    symbol,
                    self._safe_float(snapshot.get("bid"), self._safe_float(snapshot.get("last_price"), 0.0) or 0.0),
                    self._safe_float(snapshot.get("ask"), self._safe_float(snapshot.get("last_price"), 0.0) or 0.0),
                )
                usd_text = self._format_market_watch_usd(usd_value)
            self._queue_market_watch_quote_update(
                symbol,
                bid=bid,
                ask=ask,
                status=status,
                usd_value=usd_text,
            )
        if snapshots:
            self._flush_market_watch_updates()

    def apply_server_runtime_snapshot(self, payload):
        if self._ui_shutting_down or not isinstance(payload, dict):
            return

        if "assets" in payload:
            self._latest_assets_snapshot = dict(payload.get("assets") or {})
        if "positions" in payload:
            self._latest_positions_snapshot = list(payload.get("positions") or [])
        if "open_orders" in payload:
            self._latest_open_orders_snapshot = list(payload.get("open_orders") or [])
        if "order_history" in payload:
            self._latest_order_history_snapshot = list(payload.get("order_history") or [])
        if "trade_history" in payload:
            self._latest_trade_history_snapshot = list(payload.get("trade_history") or [])
        if "broker_status" in payload:
            self._latest_broker_status_snapshot = dict(payload.get("broker_status") or {})
        if payload.get("market_watch") or payload.get("symbols"):
            self.apply_server_market_watch_snapshot(payload)

        now = time.monotonic()
        self._last_assets_refresh_at = now
        self._last_positions_refresh_at = now
        self._last_open_orders_refresh_at = now
        self._last_order_history_refresh_at = now
        self._last_trade_history_refresh_at = now
        self._last_broker_status_refresh_at = now
        dirty_sections = ["session_controls"]
        if any(key in payload for key in ("assets", "positions", "open_orders", "order_history", "trade_history")):
            dirty_sections.append("execution_tables")
        if "positions" in payload:
            dirty_sections.append("risk_heatmap")
        if any(key in payload for key in ("trade_history", "order_history")):
            dirty_sections.append("strategy_comparison")
        self._mark_terminal_refresh_dirty(*dirty_sections)
        self._schedule_terminal_refresh()

        if getattr(self, "tick_chart_curve", None) is not None:
            self.tick_chart_curve.setData(self.tick_prices)

        market_watch_rows = list(payload.get("market_watch") or payload.get("symbols") or [])
        if market_watch_rows:
            normalized_quotes = []
            for snapshot in market_watch_rows:
                if not isinstance(snapshot, dict):
                    continue
                identifier = snapshot.get("identifier") if isinstance(snapshot.get("identifier"), dict) else {}
                symbol = self._normalized_symbol(snapshot.get("symbol") or identifier.get("symbol"))
                if not symbol:
                    continue
                bid = self._safe_float(snapshot.get("bid"), self._safe_float(snapshot.get("last_price"), 0.0) or 0.0)
                ask = self._safe_float(snapshot.get("ask"), self._safe_float(snapshot.get("last_price"), 0.0) or 0.0)
                if bid <= 0 and ask <= 0:
                    continue
                last = self._safe_float(snapshot.get("last_price"), 0.0) or 0.0
                if last <= 0 and bid > 0 and ask > 0:
                    last = (bid + ask) / 2.0
                normalized_quotes.append((symbol, bid, ask, last))

            if normalized_quotes:
                quote_lookup = {symbol: (bid, ask, last) for symbol, bid, ask, last in normalized_quotes}
                for chart in self._iter_chart_widgets():
                    quote = quote_lookup.get(getattr(chart, "symbol", ""))
                    if quote is None:
                        continue
                    bid, ask, last = quote
                    chart.update_price_lines(bid=bid, ask=ask, last=last)

    # ==========================================================
    # PANELS
    # ==========================================================

    def _create_market_watch_panel(self):
        dock = QDockWidget("Market Watch", self)
        dock.setObjectName("market_watch_dock")
        self.market_watch_dock = dock
        self.symbols_table = QTableWidget()
        self._configure_market_watch_table()
        self.symbols_table.itemChanged.connect(self._handle_market_watch_item_changed)
        dock.setWidget(self.symbols_table)
        self._apply_dock_widget_chrome(dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        self.tick_chart = pg.PlotWidget()
        self.tick_chart_curve = self.tick_chart.plot(pen="y")
        self.tick_prices = []

        tick_dock = QDockWidget("Tick Chart", self)
        tick_dock.setObjectName("tick_chart_dock")
        self.tick_chart_dock = tick_dock
        tick_dock.setWidget(self.tick_chart)
        self._apply_dock_widget_chrome(tick_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tick_dock)

    def _create_positions_panel(self):
        create_positions_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "positions_dock", None))

    def _create_open_orders_panel(self):
        create_open_orders_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "open_orders_dock", None))

    def _create_orderbook_panel(self):
        create_orderbook_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "orderbook_dock", None))

    def _create_trade_log_panel(self):
        create_trade_log_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "trade_log_dock", None))

    def _create_equity_panel(self):

        dock = QDockWidget("Equity Curve", self)

        container = QWidget()
        layout = QVBoxLayout()

        self.equity_summary_label = QLabel("Equity: 0.00")
        self.equity_summary_label.setStyleSheet("color: #dce7f8; font-size: 15px; font-weight: 700;")
        layout.addWidget(self.equity_summary_label)

        self.equity_chart = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(orientation="bottom")})
        self._style_performance_plot(self.equity_chart, left_label="Equity", bottom_label="Time")
        self.equity_curve = self.equity_chart.plot(pen="g")

        layout.addWidget(self.equity_chart)

        container.setLayout(layout)

        dock.setWidget(container)
        self._apply_dock_widget_chrome(dock)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _show_system_status_panel(self):
        dock = getattr(self, "system_status_dock", None)
        if dock is None:
            return
        if dock.isVisible():
            dock.hide()
            return
        dock.show()
        dock.raise_()

    def _create_performance_panel(self):
        dock = QDockWidget("Performance", self)
        dock.setMinimumWidth(420)
        container = QWidget()
        container.setStyleSheet("background-color: #0b1220;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        summary = QLabel("Performance snapshot will appear here as equity and realized trades accumulate.")
        summary.setWordWrap(True)
        summary.setStyleSheet(
            "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
            "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
        )
        layout.addWidget(summary)

        metric_names = [
            "Net PnL",
            "Return",
            "Max Drawdown",
            "Sharpe Ratio",
            "Win Rate",
            "Profit Factor",
            "Fees",
            "Avg Slippage",
        ]
        metrics_grid, metric_labels = self._build_performance_metric_grid(metric_names, columns=2)
        layout.addLayout(metrics_grid)

        plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(orientation="bottom")})
        self._style_performance_plot(plot, left_label="Equity", bottom_label="Time")
        plot.setMinimumHeight(180)
        curve = plot.plot(pen=pg.mkPen("#2a7fff", width=2.2))
        layout.addWidget(plot)

        insights = QTextBrowser()
        insights.setOpenExternalLinks(False)
        insights.setMaximumHeight(180)
        insights.setStyleSheet(
            "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; "
            "border-radius: 12px; padding: 8px; }"
        )
        layout.addWidget(insights)

        self._performance_panel_widgets = {
            "summary": summary,
            "metric_labels": metric_labels,
            "equity_curve": curve,
            "drawdown_curve": None,
            "insights": insights,
            "symbol_table": None,
        }

        container.setLayout(layout)
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._apply_dock_widget_chrome(dock)

    def _build_performance_metric_grid(self, metric_names, columns=2):
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        labels = {}

        for index, name in enumerate(metric_names):
            frame = QFrame()
            frame.setStyleSheet(
                "QFrame { background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; }"
            )
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(12, 10, 12, 10)
            frame_layout.setSpacing(4)

            title = QLabel(name)
            title.setStyleSheet("color: #8fa7c6; font-size: 11px; font-weight: 700; text-transform: uppercase;")
            value = QLabel("-")
            value.setStyleSheet("color: #e6edf7; font-size: 18px; font-weight: 700;")
            value.setWordWrap(True)

            frame_layout.addWidget(title)
            frame_layout.addWidget(value)

            row = index // columns
            column = index % columns
            grid.addWidget(frame, row, column)
            labels[name] = value

        return grid, labels

    def _style_performance_plot(self, plot, left_label=None, bottom_label="Samples"):
        if plot is None:
            return
        plot.setBackground("#0b1220")
        plot.showGrid(x=True, y=True, alpha=0.18)
        plot.setMenuEnabled(False)
        plot.setMouseEnabled(x=False, y=False)
        axis_pen = pg.mkPen("#6f89ac")
        text_pen = pg.mkPen("#8fa7c6")
        for axis_name in ("left", "bottom"):
            axis = plot.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(text_pen)
        if left_label:
            plot.setLabel("left", left_label, color="#8fa7c6")
        plot.setLabel("bottom", bottom_label, color="#8fa7c6")

    def _safe_float(self, value, default=None):
        try:
            numeric = float(value)
        except Exception:
            return default
        if not np.isfinite(numeric):
            return default
        return numeric

    def _format_currency(self, value):
        numeric = self._safe_float(value)
        if numeric is None:
            return "-"
        return f"{numeric:,.2f}"

    def _format_percent_text(self, value):
        numeric = self._safe_float(value)
        if numeric is None:
            return "-"
        return f"{numeric * 100.0:.2f}%"

    def _format_ratio_text(self, value):
        numeric = self._safe_float(value)
        if numeric is None:
            return "-"
        return f"{numeric:.2f}"

    def _performance_metric_style(self, tone):
        color_map = {
            "positive": "#32d296",
            "negative": "#ff6b6b",
            "warning": "#ffb84d",
            "muted": "#8fa7c6",
            "neutral": "#e6edf7",
        }
        color = color_map.get(tone, "#e6edf7")
        return f"color: {color}; font-size: 18px; font-weight: 700;"

    def _performance_trade_records(self):
        perf = getattr(self.controller, "performance_engine", None)
        source = []
        if perf is not None:
            trades = getattr(perf, "trades", None)
            if isinstance(trades, list):
                source = [trade for trade in trades if isinstance(trade, dict)]

        deduped = []
        keyed = {}
        anonymous_index = 0
        for trade in source:
            order_id = str(trade.get("order_id") or trade.get("id") or "").strip()
            if order_id:
                keyed[order_id] = dict(trade)
            else:
                anonymous_index += 1
                keyed[f"anon_{anonymous_index}"] = dict(trade)
        deduped = list(keyed.values())

        if deduped:
            return deduped

        fallback = []
        table = getattr(self, "trade_log", None)
        if table is None:
            return fallback
        for row in range(table.rowCount()):
            fallback.append(
                {
                    "timestamp": table.item(row, 0).text() if table.item(row, 0) else "",
                    "symbol": table.item(row, 1).text() if table.item(row, 1) else "",
                    "source": table.item(row, 2).text() if table.item(row, 2) else "",
                    "side": table.item(row, 3).text() if table.item(row, 3) else "",
                    "price": table.item(row, 4).text() if table.item(row, 4) else "",
                    "size": table.item(row, 5).text() if table.item(row, 5) else "",
                    "order_type": table.item(row, 6).text() if table.item(row, 6) else "",
                    "status": table.item(row, 7).text() if table.item(row, 7) else "",
                    "order_id": table.item(row, 8).text() if table.item(row, 8) else "",
                    "pnl": table.item(row, 9).text() if table.item(row, 9) else "",
                }
            )
        return fallback

    def _strategy_scorecard_rows(self):
        return strategy_scorecard_rows(self)

    def _performance_snapshot(self):
        return performance_snapshot(self)

    def _populate_performance_symbol_table(self, table, symbol_rows):
        populate_performance_symbol_table(self, table, symbol_rows)

    def _populate_performance_view(self, widgets, snapshot):
        populate_performance_view(self, widgets, snapshot)

    def _refresh_performance_views(self):
        refresh_performance_views(self)

    def _create_strategy_comparison(self):
        create_strategy_scorecard_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "strategy_scorecard_dock", None))

    # ==========================================================
    # BACKTEST
    # ==========================================================

    async def run_backtest_clicked(self):
        await _hotfix_run_backtest_clicked(self)






    # ==========================================================
    # REPORT
    # ==========================================================

    def _generate_report(self):
        generator = ReportGenerator(
            trades=self.controller.performance_engine.trades,
            equity_history=self.controller.performance_engine.equity_history
        )
        generator.export_pdf()
        generator.export_excel()
        self.system_console.log("Report Generated", "INFO")

    # ==========================================================
    # SCREENSHOT
    # ==========================================================

    def take_screen_shot(self):
        path = prompt_and_save_widget_screenshot(self, self)
        if path:
            self.system_console.log("Screenshot saved", "INFO")




    #######################################################
    # Start BackTesting
    #######################################################
    def start_backtest(self):
        start_backtest(self)

    def stop_backtest(self):
        stop_backtest(self)

    def _refresh_active_chart_data(self):
        _hotfix_refresh_active_chart_data(self)

    def _refresh_active_orderbook(self):
        _hotfix_refresh_active_orderbook(self)

    def _reload_balance(self):
        _hotfix_reload_balance(self)

    def _open_settings(self):
        _hotfix_open_settings(self)

    def _open_ml_research_window(self):
        _hotfix_show_ml_research_window(self)

    def _open_strategy_assignment_window(self):
        _hotfix_show_strategy_assignment_window(self)

    def _refresh_strategy_assignment_window(self, window=None, message=None):
        return _hotfix_refresh_strategy_assignment_window(self, window=window, message=message)

    def _refresh_agent_timeline_window(self, window=None):
        _ = window
        return None

    def _push_notification(self, *_args, **_kwargs):
        return None









    # ==========================================================
    # SETTINGS
    # ==========================================================

    def closeEvent(self, event):
        self._ui_shutting_down = True

        # Stop periodic timers to prevent callbacks while widgets are tearing down.
        try:
            self._stop_runtime_timers()
            if hasattr(self, "spinner_timer") and self.spinner_timer is not None:
                self.spinner_timer.stop()
            passive_task = getattr(self, "_passive_signal_scan_task", None)
            if passive_task is not None and not passive_task.done():
                passive_task.cancel()
            autotrade_task = getattr(self, "_autotrade_enable_task", None)
            if autotrade_task is not None and not autotrade_task.done():
                autotrade_task.cancel()
            for task_name in (
                "_initial_terminal_data_task",
                "_assets_refresh_task",
                "_positions_refresh_task",
                "_open_orders_refresh_task",
                "_order_history_refresh_task",
                "_trade_history_refresh_task",
                "_broker_status_refresh_task",
            ):
                task = getattr(self, task_name, None)
                if task is not None and not task.done():
                    task.cancel()
        except Exception:
            pass

        try:
            self._disconnect_controller_signals()
            self._safe_disconnect(self.ai_signal, self._update_ai_signal)
        except Exception:
            pass

        try:
            if bool(getattr(self, "_app_event_filter_installed", False)):
                app = QApplication.instance()
                if app is not None:
                    app.removeEventFilter(self)
                self._app_event_filter_installed = False
        except Exception:
            pass

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("chart/candle_up_color", self.candle_up_color)
        self.settings.setValue("chart/candle_down_color", self.candle_down_color)
        super().closeEvent(event)

    def _restore_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        restored_state = False
        state = self.settings.value("windowState")
        if state:
            try:
                restored_state = bool(self.restoreState(state))
            except Exception:
                restored_state = False

        if restored_state:
            self._normalize_workspace_sidebar_docks()
            QTimer.singleShot(0, lambda: self._ensure_execution_workspace_visible(force=True))
            self._queue_terminal_layout_fit()
        else:
            QTimer.singleShot(0, self._apply_default_dock_layout)

        self._apply_candle_colors_to_all_charts()

    def _queue_terminal_layout_fit(self):
        QTimer.singleShot(0, self._apply_terminal_table_sizing)

    def _apply_terminal_table_sizing(self):
        market_watch = getattr(self, "symbols_table", None)
        if self._is_qt_object_alive(market_watch):
            market_watch.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            market_watch.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            market_watch.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            header = market_watch.horizontalHeader()
            if self._is_qt_object_alive(header):
                header.setMinimumSectionSize(40)
                header.setSectionResizeMode(self._market_watch_watch_column(), QHeaderView.ResizeMode.ResizeToContents)
                header.setSectionResizeMode(self._market_watch_symbol_column(), QHeaderView.ResizeMode.Stretch)
                header.setSectionResizeMode(self._market_watch_bid_column(), QHeaderView.ResizeMode.ResizeToContents)
                header.setSectionResizeMode(self._market_watch_ask_column(), QHeaderView.ResizeMode.ResizeToContents)
                usd_column = self._market_watch_usd_column()
                if usd_column is not None:
                    header.setSectionResizeMode(usd_column, QHeaderView.ResizeMode.ResizeToContents)
                header.setSectionResizeMode(self._market_watch_status_column(), QHeaderView.ResizeMode.ResizeToContents)

        for table_name in (
            "positions_table",
            "open_orders_table",
            "trade_log",
            "strategy_table",
            "debug_table",
            "ai_table",
        ):
            table = getattr(self, table_name, None)
            if not self._is_qt_object_alive(table):
                continue
            table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            table.setWordWrap(False)
            header = table.horizontalHeader()
            if self._is_qt_object_alive(header):
                header.setStretchLastSection(True)

    def _safe_tabify_docks(self, primary, secondary):
        if primary is None or secondary is None or primary is secondary:
            return False
        if not _dock_is_layout_managed(self, primary) or not _dock_is_layout_managed(self, secondary):
            return False
        try:
            self.tabifyDockWidget(primary, secondary)
        except RuntimeError:
            return False
        return True

    def _normalize_workspace_sidebar_docks(self):
        left_anchor = getattr(self, "market_watch_dock", None)
        tick_dock = getattr(self, "tick_chart_dock", None)
        if _dock_is_layout_managed(self, left_anchor) and _dock_is_layout_managed(self, tick_dock):
            self._safe_tabify_docks(left_anchor, tick_dock)

        right_candidates = []
        for attr_name in (
            "orderbook_dock",
            "positions_dock",
            "trade_log_dock",
            "risk_heatmap_dock",
            "ai_signal_dock",
            "live_agent_timeline_dock",
            "strategy_scorecard_dock",
            "strategy_debug_dock",
            "session_tabs_dock",
            "system_status_dock",
        ):
            dock = getattr(self, attr_name, None)
            if not _dock_is_layout_managed(self, dock) or dock in right_candidates:
                continue
            right_candidates.append(dock)

        if len(right_candidates) > 1:
            anchor = right_candidates[0]
            for dock in right_candidates[1:]:
                self._safe_tabify_docks(anchor, dock)

        resize_targets = []
        for dock in (left_anchor, right_candidates[0] if right_candidates else None):
            if _dock_is_layout_managed(self, dock) and dock not in resize_targets:
                resize_targets.append(dock)
        try:
            if len(resize_targets) >= 2:
                self.resizeDocks(
                    resize_targets,
                    [260, 360][: len(resize_targets)],
                    Qt.Orientation.Horizontal,
                )
        except Exception:
            pass

    def _apply_default_dock_layout(self):
        default_areas = {
            "market_watch_dock": Qt.DockWidgetArea.LeftDockWidgetArea,
            "tick_chart_dock": Qt.DockWidgetArea.LeftDockWidgetArea,
            "positions_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "trade_log_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "orderbook_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "risk_heatmap_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "ai_signal_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "live_agent_timeline_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "strategy_scorecard_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "strategy_debug_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "session_tabs_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "system_status_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "system_console_dock": Qt.DockWidgetArea.BottomDockWidgetArea,
        }
        visible_docks = {
            "market_watch_dock",
            "positions_dock",
            "trade_log_dock",
            "orderbook_dock",
        }

        for attr_name, area in default_areas.items():
            dock = getattr(self, attr_name, None)
            if not self._is_qt_object_alive(dock):
                continue
            try:
                if dock.isFloating():
                    dock.setFloating(False)
            except Exception:
                pass
            try:
                self.addDockWidget(area, dock)
            except Exception:
                pass
            dock.show() if attr_name in visible_docks else dock.hide()

        self._normalize_workspace_sidebar_docks()

        if self.orderbook_dock is not None:
            self.orderbook_dock.raise_()
        elif self.positions_dock is not None:
            self.positions_dock.raise_()
        if self.market_watch_dock is not None:
            self.market_watch_dock.raise_()

        self._queue_terminal_layout_fit()

    def _show_workspace_dock(self, dock):
        if not self._is_qt_object_alive(dock):
            return
        dock_name = ""
        try:
            dock_name = str(dock.objectName() or "").strip()
        except Exception:
            dock_name = ""

        default_areas = {
            "market_watch_dock": Qt.DockWidgetArea.LeftDockWidgetArea,
            "tick_chart_dock": Qt.DockWidgetArea.LeftDockWidgetArea,
            "positions_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "open_orders_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "trade_log_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "orderbook_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "risk_heatmap_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "ai_signal_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "live_agent_timeline_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "strategy_scorecard_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "strategy_debug_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "session_tabs_dock": Qt.DockWidgetArea.RightDockWidgetArea,
            "system_console_dock": Qt.DockWidgetArea.BottomDockWidgetArea,
            "system_status_dock": Qt.DockWidgetArea.RightDockWidgetArea,
        }

        try:
            if dock.isFloating():
                dock.setFloating(False)
        except Exception:
            pass

        target_area = default_areas.get(dock_name)
        if target_area is not None:
            try:
                self.addDockWidget(target_area, dock)
            except Exception:
                pass

        self._normalize_workspace_sidebar_docks()

        dock.show()
        try:
            dock.raise_()
        except Exception:
            pass

        if hasattr(self, "_queue_terminal_layout_fit"):
            self._queue_terminal_layout_fit()

    def _open_strategy_scorecard_dock(self):
        self._show_workspace_dock(getattr(self, "strategy_scorecard_dock", None))

    def _open_strategy_debug_dock(self):
        self._show_workspace_dock(getattr(self, "strategy_debug_dock", None))

    def _open_system_console_dock(self):
        self._show_workspace_dock(getattr(self, "system_console_dock", None))

    def _open_system_status_dock(self):
        self._show_workspace_dock(getattr(self, "system_status_dock", None))

    def _open_live_agent_timeline_dock(self):
        self._show_workspace_dock(getattr(self, "live_agent_timeline_dock", None))

    def _execution_workspace_dock(self):
        for attr_name in ("orderbook_dock", "positions_dock", "open_orders_dock"):
            dock = getattr(self, attr_name, None)
            if self._is_qt_object_alive(dock):
                return dock
        creator = getattr(self, "_create_positions_panel", None)
        if callable(creator):
            creator()
        for attr_name in ("orderbook_dock", "positions_dock", "open_orders_dock"):
            dock = getattr(self, attr_name, None)
            if self._is_qt_object_alive(dock):
                return dock
        return None

    def _select_execution_workspace_tab(self, tab_label=None):
        tabs = getattr(self, "positions_orders_tabs", None)
        if not self._is_qt_object_alive(tabs):
            return False
        desired = str(tab_label or "").strip().lower()
        if not desired:
            return tabs.count() > 0
        for index in range(tabs.count()):
            title = str(tabs.tabText(index) or "").strip().lower()
            if title == desired:
                tabs.setCurrentIndex(index)
                return True
        return False

    def _ensure_execution_workspace_visible(self, *, preferred_tab=None, force=False):
        dock = self._execution_workspace_dock()
        if not self._is_qt_object_alive(dock):
            return False
        should_show = force
        if not should_show:
            try:
                should_show = not bool(dock.isVisible())
            except Exception:
                should_show = True
        if should_show:
            self._show_workspace_dock(dock)
        if preferred_tab:
            self._select_execution_workspace_tab(preferred_tab)
        return True

    def _open_execution_workspace_dock(self, tab_label=None):
        if self._ensure_execution_workspace_visible(preferred_tab=tab_label, force=True):
            return
        console = getattr(self, "system_console", None)
        if console is not None and hasattr(console, "log"):
            console.log("Execution workspace is not available.", "ERROR")

    def _apply_candle_colors_to_all_charts(self):
        for chart in self._iter_chart_widgets():
            chart.set_candle_colors(self.candle_up_color, self.candle_down_color)

    def _chart_theme_kwargs(self):
        return {
            "chart_background": getattr(self, "chart_background_color", "#11161f"),
            "grid_color": getattr(self, "chart_grid_color", "#8290a0"),
            "axis_color": getattr(self, "chart_axis_color", "#9aa4b2"),
        }

    def _apply_chart_theme_to_all_charts(self):
        theme_kwargs = self._chart_theme_kwargs()
        for chart in self._iter_chart_widgets():
            if hasattr(chart, "set_visual_theme"):
                chart.set_visual_theme(**theme_kwargs)

    def _open_chart_settings(self):
        self._show_settings_window("Display")

    def _choose_candle_colors(self):
        up = QColorDialog.getColor(QColor(self.candle_up_color), self, "Select Bullish Candle Color")
        if not up.isValid():
            return

        down = QColorDialog.getColor(QColor(self.candle_down_color), self, "Select Bearish Candle Color")
        if not down.isValid():
            return

        self.candle_up_color = up.name()
        self.candle_down_color = down.name()

        self.settings.setValue("chart/candle_up_color", self.candle_up_color)
        self.settings.setValue("chart/candle_down_color", self.candle_down_color)

        self._apply_candle_colors_to_all_charts()

    def _current_chart_indicator_specs(self, chart=None):
        active_chart = chart if isinstance(chart, ChartWidget) else self._current_chart_widget()
        if not isinstance(active_chart, ChartWidget):
            return None, []
        indicator_specs = [
            spec
            for spec in list(getattr(active_chart, "indicators", []) or [])
            if isinstance(spec, dict) and str(spec.get("key") or "").strip()
        ]
        return active_chart, indicator_specs

    def _show_loaded_studies(self):
        chart, indicator_specs = self._current_chart_indicator_specs()
        if not isinstance(chart, ChartWidget):
            QMessageBox.warning(self, "Studies", "Select a chart first.")
            return
        if not indicator_specs:
            QMessageBox.information(self, "Studies", "This chart does not have any studies loaded.")
            return

        study_lines = "\n".join(
            f"- {self._chart_indicator_display_name(spec)}"
            for spec in indicator_specs
        )
        QMessageBox.information(
            self,
            "Studies",
            f"Active studies on {chart.symbol} ({chart.timeframe}):\n\n{study_lines}",
        )

    def _open_studies_manager(self):
        chart, _indicator_specs = self._current_chart_indicator_specs()
        if not isinstance(chart, ChartWidget):
            QMessageBox.warning(self, "Studies", "Select a chart first.")
            return

        choices = [
            "Show Loaded Studies",
            "Add Study...",
            "Remove Study...",
            "Remove All Studies",
        ]
        choice, ok = QInputDialog.getItem(
            self,
            "Edit Studies",
            "Study action:",
            choices,
            0,
            False,
        )
        if not ok or not choice:
            return

        if choice == "Show Loaded Studies":
            self._show_loaded_studies()
        elif choice == "Add Study...":
            self._add_indicator_to_current_chart()
        elif choice == "Remove Study...":
            self._remove_indicator_from_current_chart()
        elif choice == "Remove All Studies":
            self._remove_all_indicators_from_current_chart()

    def _remove_all_indicators_from_current_chart(self):
        chart, indicator_specs = self._current_chart_indicator_specs()
        if not isinstance(chart, ChartWidget):
            QMessageBox.warning(self, "Studies", "Select a chart first.")
            return
        if not indicator_specs:
            QMessageBox.information(self, "Studies", "This chart has no studies to remove.")
            return

        response = QMessageBox.question(
            self,
            "Remove All Studies",
            f"Remove all studies from {chart.symbol} ({chart.timeframe})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        removed = False
        for spec in indicator_specs:
            removed = chart.remove_indicator(str(spec.get("key") or "").strip()) or removed

        if not removed:
            QMessageBox.warning(self, "Studies", "Unable to remove the loaded studies.")
            return

        chart.updateGeometry()
        chart.repaint()

    def _add_indicator_to_current_chart(self, checked=False, indicator_name=None, preset_period=None, prompt_for_period=True):
        _ = checked
        chart = self._current_chart_widget()
        if not isinstance(chart, ChartWidget):
            QMessageBox.warning(self, "Chart", "Select a chart first.")
            return

        indicator = str(indicator_name or "").strip()
        if not indicator:
            indicator, ok = QInputDialog.getItem(
                self,
                "Add Study",
                "Study:",
                CHART_INDICATOR_OPTIONS,
                0,
                False,
            )
            if not ok or not indicator:
                return

        period = preset_period if preset_period is not None else CHART_INDICATOR_DEFAULT_PERIODS.get(indicator, 20)
        if indicator not in CHART_FIXED_DEFAULT_INDICATORS and prompt_for_period:
            period, ok = QInputDialog.getInt(
                self,
                "Study Length",
                "Period:",
                period,
                2,
                500,
                1,
            )
            if not ok:
                return
        elif indicator not in CHART_FIXED_DEFAULT_INDICATORS:
            try:
                period = max(2, int(period))
            except (TypeError, ValueError):
                period = CHART_INDICATOR_DEFAULT_PERIODS.get(indicator, 20)

        key = chart.add_indicator(indicator, period)
        if key is None:
            QMessageBox.warning(self, "Study", "Unsupported study.")
            return

        # Force redraw using existing candle cache for this symbol/timeframe.
        asyncio.get_event_loop().create_task(self._reload_chart_data(chart.symbol, chart.timeframe))

    def _chart_indicator_display_name(self, spec):
        indicator_type = str((spec or {}).get("type") or "").strip().upper()
        raw_period = (spec or {}).get("period")
        try:
            period = int(raw_period) if raw_period is not None else None
        except (TypeError, ValueError):
            period = None
        label_map = {
            "SMA": "Moving Average",
            "EMA": "EMA",
            "SMMA": "SMMA",
            "LWMA": "LWMA",
            "VWAP": "VWAP",
            "BB": "Bollinger Bands",
            "ENVELOPES": "Envelopes",
            "ICHIMOKU": "Ichimoku",
            "SAR": "Parabolic SAR",
            "STDDEV": "Standard Deviation",
            "AC": "Accelerator Oscillator",
            "AO": "Awesome Oscillator",
            "CCI": "CCI",
            "DEMARKER": "DeMarker",
            "MACD": "MACD",
            "MOMENTUM": "Momentum",
            "OSMA": "OsMA",
            "RSI": "RSI",
            "RVI": "RVI",
            "STOCHASTIC": "Stochastic Oscillator",
            "WPR": "Williams' Percent Range",
            "AD": "Accumulation/Distribution",
            "MFI": "Money Flow Index",
            "OBV": "On Balance Volume",
            "VOLUMES": "Volumes",
            "ALLIGATOR": "Alligator",
            "FRACTAL": "Fractal",
            "GATOR": "Gator Oscillator",
            "BW_MFI": "Market Facilitation Index",
            "BULLS POWER": "Bulls Power",
            "BEARS POWER": "Bears Power",
            "FORCE INDEX": "Force Index",
            "DONCHIAN": "Donchian Channel",
            "KELTNER": "Keltner Channel",
            "ZIGZAG": "ZigZag",
            "FIBO": "Fibonacci Retracement",
            "ADX": "ADX",
            "ATR": "ATR",
        }
        label = label_map.get(indicator_type, indicator_type.title() if indicator_type else "Indicator")
        singleton_indicators = {
            "ICHIMOKU",
            "SAR",
            "AC",
            "AO",
            "MACD",
            "OSMA",
            "AD",
            "OBV",
            "VOLUMES",
            "ALLIGATOR",
            "GATOR",
            "BW_MFI",
            "BULLS POWER",
            "BEARS POWER",
        }
        if indicator_type in singleton_indicators or period is None:
            return label
        return f"{label} ({period})"

    def _remove_indicator_from_current_chart(self):
        chart = self._current_chart_widget()
        if not isinstance(chart, ChartWidget):
            QMessageBox.warning(self, "Studies", "Select a chart first.")
            return

        indicator_specs = [
            spec
            for spec in list(getattr(chart, "indicators", []) or [])
            if isinstance(spec, dict) and str(spec.get("key") or "").strip()
        ]
        if not indicator_specs:
            QMessageBox.information(self, "Studies", "This chart has no studies to remove.")
            return

        options = []
        option_map = {}
        for spec in indicator_specs:
            key = str(spec.get("key") or "").strip()
            option = f"{self._chart_indicator_display_name(spec)} [{key}]"
            options.append(option)
            option_map[option] = key

        selection, ok = QInputDialog.getItem(
            self,
            "Remove Study",
            "Study:",
            options,
            0,
            False,
        )
        if not ok or not selection:
            return

        if not chart.remove_indicator(option_map.get(selection, "")):
            QMessageBox.warning(self, "Studies", "Unable to remove the selected study.")
            return

        chart.updateGeometry()
        chart.repaint()

    def _update_orderbook(self, symbol, bids, asks):
        update_orderbook(self, symbol, bids, asks)

    def _update_recent_trades(self, symbol, trades):
        update_recent_trades(self, symbol, trades)

    def _update_news(self, symbol, events):
        normalized = str(symbol or "").upper().strip()
        for chart in self._iter_chart_widgets():
            if str(getattr(chart, "symbol", "")).upper() != normalized:
                continue
            if getattr(self.controller, "news_draw_on_chart", False):
                chart.set_news_events(events or [])
            else:
                chart.clear_news_events()

    def _create_strategy_debug_panel(self):
        create_strategy_debug_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "strategy_debug_dock", None))

    def _handle_strategy_debug(self, debug):
        handle_strategy_debug(self, debug)

    def _update_training_status(self, symbol, status):
        status_column = self._market_watch_status_column()

        row = self._find_market_watch_row(symbol)
        if row is None:
            return

        if status == "training":
            item = QTableWidgetItem("⏳ Training...")
            item.setForeground(QColor("yellow"))
            icon = self._spinner_frames[self._spinner_index % 2]
            self._spinner_index += 1

            item = QTableWidgetItem(f"{icon} Training...")
            item.setForeground(QColor("yellow"))

        elif status == "ready":
            item = QTableWidgetItem("🟢 Ready")
            item.setForeground(QColor("yellow"))

        elif status == "error":
            item = QTableWidgetItem("🔴 Error")
            item.setForeground(QColor("red"))
        else:
            item = QTableWidgetItem(status)

        self.symbols_table.setItem(row, status_column, item)

    def _rotate_spinner(self):
        try:
            self._spinner_index += 1
            self._update_trading_activity_indicator()
            self._update_autotrade_button()

            # Lightweight spinner update: only touch existing rows that are in training state.
            if not hasattr(self, "symbols_table") or self.symbols_table is None:
                return

            icon = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]

            rows = self.symbols_table.rowCount()
            status_column = self._market_watch_status_column()

            for row in range(rows):
                status_item = self.symbols_table.item(row, status_column)

                if not status_item:
                    continue

                text = status_item.text() or ""

                if "Training" in text or "?" in text or "?" in text:
                    status_item.setText(f"{icon} Training...")
                    status_item.setForeground(QColor("yellow"))

        except Exception as e:
            self.logger.error(e)

    def _connect_signals(self):
        self._controller_signal_bindings = []

        def _bind(signal_name, slot):
            signal = getattr(self.controller, signal_name, None)
            if signal is None:
                return
            wrapped = self._session_scoped_slot(slot)
            signal.connect(wrapped)
            self._controller_signal_bindings.append((signal, wrapped))

        _bind("candle_signal", self._update_chart)
        _bind("equity_signal", self._update_equity)
        _bind("trade_signal", self._update_trade_log)
        _bind("ticker_signal", self._update_ticker)
        _bind("news_signal", self._update_news)
        _bind("orderbook_signal", self._update_orderbook)
        _bind("recent_trades_signal", self._update_recent_trades)
        _bind("ai_signal_monitor", self._update_ai_signal)
        _bind("strategy_debug_signal", self._handle_strategy_debug)
        _bind("agent_runtime_signal", self._handle_agent_runtime_event)
        _bind("training_status_signal", self._update_training_status)
        _bind("symbols_signal", self._update_symbols)

    def _setup_panels(self):
        self._create_session_tabs_panel()
        self._create_system_console_panel()

        self._create_market_watch_panel()
        self._create_positions_panel()
        self._create_trade_log_panel()
        self._create_strategy_comparison()
        self._create_strategy_debug_panel()
        self._create_system_status_panel()
        self._create_risk_heatmap()
        self._create_ai_signal_panel()
        self._create_live_agent_timeline_panel()

    def _create_system_console_panel(self):
        create_system_console_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "system_console_dock", None))

    def _create_session_tabs_panel(self):
        dock = QDockWidget("Sessions", self)
        dock.setObjectName("session_tabs_dock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        tabs = QTabWidget()
        tabs.setObjectName("session_tabs_widget")
        self._apply_workspace_tab_chrome(tabs)
        dock.setWidget(tabs)

        self.session_tabs_dock = dock
        self.session_tabs_widget = tabs
        self._apply_dock_widget_chrome(dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._refresh_session_tabs()

    def _refresh_session_tabs(self):
        tabs = getattr(self, "session_tabs_widget", None)
        controller = getattr(self, "controller", None)
        if tabs is None or controller is None or not hasattr(controller, "list_trading_sessions"):
            return

        try:
            sessions = list(controller.list_trading_sessions() or [])
        except Exception:
            sessions = []

        aggregate = {}
        if hasattr(controller, "aggregate_session_portfolio"):
            try:
                aggregate = dict(controller.aggregate_session_portfolio() or {})
            except Exception:
                aggregate = {}

        active_session_id = str(getattr(controller, "active_session_id", "") or "").strip()
        selected_index = 1 if sessions else 0
        session_signature = []
        for index, session in enumerate(sessions):
            session_id = str(session.get("session_id") or "").strip()
            label = str(session.get("label") or session_id or "Session").strip()
            status = str(session.get("status") or "unknown").upper()
            mode = str(session.get("mode") or "paper").upper()
            if session_id and session_id == active_session_id:
                selected_index = index + 1
            session_signature.append(
                (
                    session_id,
                    label,
                    status,
                    mode,
                    str(session.get("account_label") or "Not set"),
                    float(session.get("equity") or 0.0),
                    float(session.get("drawdown_pct") or 0.0),
                    float(session.get("gross_exposure") or 0.0),
                    int(session.get("symbols_count") or 0),
                    int(session.get("positions_count") or 0),
                    int(session.get("open_orders_count") or 0),
                    int(session.get("trade_count") or 0),
                    str(session.get("strategy") or "Trend Following"),
                )
            )
        signature = (
            id(tabs),
            active_session_id,
            (
                int(aggregate.get("session_count") or len(sessions)),
                int(aggregate.get("running_sessions") or 0),
                int(aggregate.get("risk_blocked_sessions") or 0),
                float(aggregate.get("total_equity") or 0.0),
                float(aggregate.get("total_gross_exposure") or 0.0),
                float(aggregate.get("total_unrealized_pnl") or 0.0),
            ),
            tuple(session_signature),
        )
        expected_tabs = 1 if not sessions else len(sessions) + 1
        if (
            signature == getattr(self, "_session_tabs_signature", None)
            and tabs.count() == expected_tabs
        ):
            if tabs.currentIndex() != selected_index:
                tabs.setCurrentIndex(selected_index)
            return

        while tabs.count():
            widget = tabs.widget(0)
            tabs.removeTab(0)
            if widget is not None:
                widget.deleteLater()

        if not sessions:
            placeholder = QTextBrowser()
            placeholder.setStyleSheet(Terminal._tool_window_text_browser_style(self))
            placeholder.setHtml(
                Terminal._empty_state_html(
                    self,
                    "No Active Sessions",
                    "Create or activate a trading session to manage accounts, orders, and runtime state from one desk.",
                    hint="The portfolio aggregator and individual session tabs will appear here automatically.",
                )
            )
            tabs.addTab(placeholder, "Sessions")
            tabs.setCurrentIndex(0)
            self._session_tabs_signature = signature
            return

        portfolio_viewer = QTextBrowser()
        portfolio_viewer.setHtml(
            "<h3>Portfolio Aggregator</h3>"
            "<p><b>Sessions:</b> {sessions}<br>"
            "<b>Running:</b> {running}<br>"
            "<b>Risk Blocked:</b> {risk_blocked}<br>"
            "<b>Total Equity:</b> {equity:,.2f}<br>"
            "<b>Gross Exposure:</b> {exposure:,.2f}<br>"
            "<b>Unrealized PnL:</b> {pnl:,.2f}</p>"
            "<p>Use the toolbar selector or the dashboard to switch, start, stop, or remove individual broker sessions.</p>".format(
                sessions=int(aggregate.get("session_count") or len(sessions)),
                running=int(aggregate.get("running_sessions") or 0),
                risk_blocked=int(aggregate.get("risk_blocked_sessions") or 0),
                equity=float(aggregate.get("total_equity") or 0.0),
                exposure=float(aggregate.get("total_gross_exposure") or 0.0),
                pnl=float(aggregate.get("total_unrealized_pnl") or 0.0),
            )
        )
        tabs.addTab(portfolio_viewer, "Portfolio")

        for index, session in enumerate(sessions):
            viewer = QTextBrowser()
            label = str(session.get("label") or session.get("session_id") or "Session").strip()
            status = str(session.get("status") or "unknown").upper()
            mode = str(session.get("mode") or "paper").upper()
            equity = float(session.get("equity") or 0.0)
            drawdown = float(session.get("drawdown_pct") or 0.0)
            gross_exposure = float(session.get("gross_exposure") or 0.0)
            viewer.setHtml(
                "<h3>{label}</h3>"
                "<p><b>Status:</b> {status}<br>"
                "<b>Mode:</b> {mode}<br>"
                "<b>Account:</b> {account}<br>"
                "<b>Equity:</b> {equity:,.2f}<br>"
                "<b>Drawdown:</b> {drawdown:.2%}<br>"
                "<b>Gross Exposure:</b> {gross_exposure:,.2f}<br>"
                "<b>Symbols:</b> {symbols}<br>"
                "<b>Positions:</b> {positions}<br>"
                "<b>Open Orders:</b> {orders}<br>"
                "<b>Trades:</b> {trades}<br>"
                "<b>Strategy:</b> {strategy}</p>"
                "<p>The main terminal workspace follows the currently active session selected in the toolbar.</p>".format(
                    label=label,
                    status=status,
                    mode=mode,
                    account=str(session.get("account_label") or "Not set"),
                    equity=equity,
                    drawdown=drawdown,
                    gross_exposure=gross_exposure,
                    symbols=int(session.get("symbols_count") or 0),
                    positions=int(session.get("positions_count") or 0),
                    orders=int(session.get("open_orders_count") or 0),
                    trades=int(session.get("trade_count") or 0),
                    strategy=str(session.get("strategy") or "Trend Following"),
                )
            )
            tabs.addTab(viewer, label)
        tabs.setCurrentIndex(selected_index)
        self._session_tabs_signature = signature

    def _current_chart_symbol(self):
        chart = self._current_chart_widget()
        if chart is not None:
            return chart.symbol
        return getattr(self, "symbol", None)

    def _defer_controller_coroutine(self, coro_factory, task_name):
        if self._ui_shutting_down:
            return

        def _start():
            if self._ui_shutting_down:
                return
            try:
                coro = coro_factory()
            except Exception:
                logger = getattr(self, "logger", None)
                if logger is not None:
                    logger.debug("Deferred controller coroutine factory failed for %s", task_name, exc_info=True)
                return

            create_task = getattr(getattr(self, "controller", None), "_create_task", None)
            try:
                if callable(create_task):
                    create_task(coro, task_name)
                else:
                    asyncio.get_event_loop().create_task(coro)
            except Exception:
                close = getattr(coro, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
                logger = getattr(self, "logger", None)
                if logger is not None:
                    logger.debug("Deferred controller coroutine scheduling failed for %s", task_name, exc_info=True)

        defer_start = False
        if QApplication.instance() is not None:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            defer_start = running_loop is not None and str(type(running_loop).__module__ or "").startswith("qasync")

        if not defer_start:
            _start()
            return
        QTimer.singleShot(0, _start)

    def _request_active_orderbook(self):
        if self._ui_shutting_down or self._workspace_loading_active():
            return

        symbol = self._current_chart_symbol()
        if not symbol:
            return

        if hasattr(self.controller, "request_orderbook"):
            self._defer_controller_coroutine(
                lambda symbol=symbol: self.controller.request_orderbook(symbol=symbol, limit=20),
                f"request_orderbook:{symbol}",
            )
        if hasattr(self.controller, "request_recent_trades"):
            self._defer_controller_coroutine(
                lambda symbol=symbol: self.controller.request_recent_trades(symbol=symbol, limit=40),
                f"request_recent_trades:{symbol}",
            )

    def _passive_signal_scan_symbols(self):
        if getattr(self, "_ui_shutting_down", False) or bool(getattr(self, "autotrading_enabled", False)):
            return []
        if not self._session_is_current():
            return []

        controller = getattr(self, "controller", None)
        trading_system = getattr(controller, "trading_system", None) if controller is not None else None
        if controller is None or trading_system is None or not hasattr(trading_system, "process_symbol"):
            return []

        max_symbols = max(1, int(getattr(self, "PASSIVE_SIGNAL_SCAN_MAX_SYMBOLS", 6) or 6))
        scope = str(getattr(self, "autotrade_scope_value", "all") or "all").strip().lower() or "all"
        current_symbol = self._normalized_symbol(self._current_chart_symbol() or getattr(self, "symbol", ""))
        active_symbol_resolver = getattr(controller, "get_active_autotrade_symbols", None)
        symbol_enabled_resolver = getattr(controller, "is_symbol_enabled_for_autotrade", None)
        fallback_supported = {
            self._normalized_symbol(symbol)
            for symbol in list(getattr(controller, "symbols", []) or [])
            if self._normalized_symbol(symbol)
        }

        resolved = []

        def _append(symbol):
            normalized = self._normalized_symbol(symbol)
            if not normalized or normalized in resolved:
                return
            if callable(symbol_enabled_resolver):
                try:
                    if not bool(symbol_enabled_resolver(normalized)):
                        return
                except Exception:
                    pass
            elif fallback_supported and normalized not in fallback_supported:
                return
            resolved.append(normalized)

        resolved_from_scope = []
        if callable(active_symbol_resolver):
            try:
                resolved_from_scope = list(active_symbol_resolver() or [])
            except Exception:
                resolved_from_scope = []

        if scope == "selected":
            _append(current_symbol)
            if not resolved:
                for symbol in resolved_from_scope:
                    _append(symbol)
                    if resolved:
                        break
            return resolved[:1]

        for symbol in resolved_from_scope:
            _append(symbol)

        if current_symbol and current_symbol in resolved:
            resolved.remove(current_symbol)
            resolved.insert(0, current_symbol)
        elif not resolved:
            _append(current_symbol)

        if not resolved:
            for symbol in list(getattr(controller, "symbols", []) or [])[:max_symbols]:
                _append(symbol)

        return resolved[:max_symbols]

    async def _run_passive_signal_scan(self):
        if getattr(self, "_ui_shutting_down", False) or bool(getattr(self, "autotrading_enabled", False)):
            return
        if not self._session_is_current():
            return

        controller = getattr(self, "controller", None)
        trading_system = getattr(controller, "trading_system", None) if controller is not None else None
        if controller is None or trading_system is None or not hasattr(trading_system, "process_symbol"):
            return

        symbols = list(self._passive_signal_scan_symbols() or [])
        if not symbols:
            return

        default_timeframe = str(getattr(self, "current_timeframe", "") or getattr(controller, "time_frame", "1h") or "1h").strip() or "1h"
        target_limit = getattr(controller, "limit", None)
        timeframe_resolver = getattr(trading_system, "_assigned_timeframe_for_symbol", None)

        for symbol in symbols:
            if getattr(self, "_ui_shutting_down", False) or bool(getattr(self, "autotrading_enabled", False)):
                return
            try:
                timeframe_value = default_timeframe
                if callable(timeframe_resolver):
                    try:
                        timeframe_value = str(
                            timeframe_resolver(symbol, fallback=default_timeframe) or default_timeframe
                        ).strip() or default_timeframe
                    except TypeError:
                        timeframe_value = str(timeframe_resolver(symbol) or default_timeframe).strip() or default_timeframe
                result = trading_system.process_symbol(
                    symbol,
                    timeframe=timeframe_value,
                    limit=target_limit,
                    publish_debug=True,
                    allow_execution=False,
                )
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logger = getattr(self, "logger", None)
                if logger is not None:
                    logger.debug("Passive signal scan failed for %s: %s", symbol, exc, exc_info=True)

    def _schedule_passive_signal_scan(self):
        if (
            getattr(self, "_ui_shutting_down", False)
            or self._workspace_loading_active()
            or bool(getattr(self, "autotrading_enabled", False))
        ):
            return
        if not self._session_is_current():
            return
        if not self._passive_signal_scan_symbols():
            return

        task = getattr(self, "_passive_signal_scan_task", None)
        if task is not None and not task.done():
            return

        self._last_passive_signal_scan_at = time.monotonic()
        try:
            task = asyncio.get_event_loop().create_task(self._run_passive_signal_scan())
        except Exception as exc:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.debug("Unable to schedule passive signal scan: %s", exc)
            return

        self._passive_signal_scan_task = task

        def _done(completed):
            if getattr(self, "_passive_signal_scan_task", None) is completed:
                self._passive_signal_scan_task = None
            try:
                exception = completed.exception()
            except asyncio.CancelledError:
                return
            if exception is not None:
                logger = getattr(self, "logger", None)
                if logger is not None:
                    logger.debug("Passive signal scan task failed", exc_info=(type(exception), exception, exception.__traceback__))

        task.add_done_callback(_done)

    def _setup_spinner(self):

        self._spinner_frames = ["⏳", "⌛"]
        self._spinner_index = 0

        self.spinner_timer = QTimer()
        self.spinner_timer.timeout.connect(self._rotate_spinner)

        self.spinner_timer.start(500)

    def _update_symbols(self, exchange, symbols):
        normalized_symbols = [str(symbol or "").strip().upper() for symbol in symbols or [] if str(symbol or "").strip()]
        supported_symbols = set(normalized_symbols)
        resolver = getattr(getattr(self, "controller", None), "_resolve_preferred_market_symbol", None)
        watchlist = set(getattr(self, "autotrade_watchlist", set()) or set())
        market_watch_signature = (str(exchange or "").strip().lower(), tuple(normalized_symbols))
        self.symbols_table.setAccessibleName(exchange)
        Terminal._sync_exchange_scoped_actions(self)
        self._configure_market_watch_table()
        symbols_changed = market_watch_signature != getattr(self, "_market_watch_symbols_signature", None)
        if self.symbol_picker is not None and symbols_changed:
            current_symbol = str(self.symbol_picker.currentText() or "").strip().upper()
            resolved_current_symbol = current_symbol
            if callable(resolver) and current_symbol:
                try:
                    resolved_current_symbol = str(resolver(current_symbol) or current_symbol).strip().upper() or current_symbol
                except Exception:
                    resolved_current_symbol = current_symbol
            self.symbol_picker.blockSignals(True)
            self.symbol_picker.clear()
            self.symbol_picker.addItems(normalized_symbols)
            if resolved_current_symbol in supported_symbols:
                self.symbol_picker.setCurrentText(resolved_current_symbol)
            elif current_symbol in supported_symbols:
                self.symbol_picker.setCurrentText(current_symbol)
            elif normalized_symbols:
                self.symbol_picker.setCurrentIndex(0)
            self.symbol_picker.blockSignals(False)

        if symbols_changed:
            ordered_symbols = sorted(
                normalized_symbols,
                key=lambda symbol: (
                    self._market_watch_priority_rank(symbol, symbol in watchlist),
                    self._normalized_symbol(symbol),
                ),
            )
            blocked = self.symbols_table.blockSignals(True)
            previous_updates_enabled = None
            try:
                previous_updates_enabled = bool(self.symbols_table.updatesEnabled())
            except Exception:
                previous_updates_enabled = None

            try:
                self.symbols_table.setUpdatesEnabled(False)
                self.symbols_table.setRowCount(len(ordered_symbols))
                self._market_watch_row_cache = {}
                for row, symbol in enumerate(ordered_symbols):
                    self._set_market_watch_row(row, symbol, bid="-", ask="-", status="⏳", usd_value="-")
            finally:
                self.symbols_table.blockSignals(blocked)
                try:
                    if previous_updates_enabled is not None:
                        self.symbols_table.setUpdatesEnabled(previous_updates_enabled)
                    else:
                        self.symbols_table.setUpdatesEnabled(True)
                except Exception:
                    pass
            self._rebuild_market_watch_row_cache()
            self._market_watch_symbols_signature = market_watch_signature

        if callable(resolver):
            for chart in self._all_chart_widgets():
                chart_symbol = str(getattr(chart, "symbol", "") or "").strip().upper()
                if not chart_symbol:
                    continue
                try:
                    resolved_chart_symbol = str(resolver(chart_symbol) or chart_symbol).strip().upper() or chart_symbol
                except Exception:
                    resolved_chart_symbol = chart_symbol
                if resolved_chart_symbol == chart_symbol:
                    continue
                if supported_symbols and resolved_chart_symbol not in supported_symbols and chart_symbol in supported_symbols:
                    continue
                self._retarget_chart_widget_symbol(chart, resolved_chart_symbol)
                self._schedule_chart_data_refresh(chart)

        subscription_requester = getattr(getattr(self, "controller", None), "request_hybrid_market_watch_subscription", None)
        if callable(subscription_requester) and normalized_symbols:
            try:
                subscription_requester(
                    normalized_symbols,
                    timeframe=str(getattr(self, "current_timeframe", "") or "1h").strip() or "1h",
                )
            except Exception:
                self.logger.debug("Hybrid market-watch subscription request failed", exc_info=True)

    def _manual_trade_default_payload(self, prefill=None):
        return manual_trade_default_payload(self, prefill=prefill)

    def _chart_for_symbol(self, symbol):
        target = str(symbol or "").strip()
        if not target:
            return None
        current_chart = self._current_chart_widget()
        if isinstance(current_chart, ChartWidget) and getattr(current_chart, "symbol", "") == target:
            return current_chart
        for chart in self._all_chart_widgets():
            if getattr(chart, "symbol", "") == target:
                return chart
        return None

    def _default_entry_price_for_symbol(self, symbol, side="buy"):
        return default_entry_price_for_symbol(self, symbol, side=side)

    def _suggest_manual_trade_levels(self, symbol, side="buy", entry_price=None):
        return suggest_manual_trade_levels(self, symbol, side=side, entry_price=entry_price)

    def _manual_trade_format_context(self, symbol):
        return manual_trade_format_context(self, symbol)

    def _normalize_manual_trade_quantity_mode(self, value):
        return normalize_manual_trade_quantity_mode(self, value)

    def _manual_trade_quantity_context(self, symbol):
        return manual_trade_quantity_context(self, symbol)

    def _normalize_manual_trade_amount(self, symbol, amount, quantity_mode="units"):
        return normalize_manual_trade_amount(self, symbol, amount, quantity_mode=quantity_mode)

    def _validate_manual_trade_amount(self, symbol, amount, quantity_mode="units"):
        return validate_manual_trade_amount(self, symbol, amount, quantity_mode=quantity_mode)

    def _normalize_manual_trade_price(self, symbol, value):
        return normalize_manual_trade_price(self, symbol, value)

    def _apply_manual_trade_price_field_format(self, window, attr_name):
        field = getattr(window, attr_name, None)
        symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
        if field is None or symbol_picker is None:
            return
        text = str(field.text() or "").strip()
        if not text:
            return
        normalized = self._normalize_manual_trade_price(str(symbol_picker.currentText() or "").strip(), text)
        field.blockSignals(True)
        field.setText("" if normalized is None else str(normalized))
        field.blockSignals(False)

    def _manual_trade_target_charts(self, symbol):
        target = str(symbol or "").strip()
        if not target:
            return []
        return [chart for chart in self._all_chart_widgets() if getattr(chart, "symbol", "") == target]

    def _clear_trade_overlays(self, symbol=None):
        charts = self._manual_trade_target_charts(symbol) if symbol else self._all_chart_widgets()
        for chart in charts:
            try:
                chart.clear_trade_overlay()
            except Exception:
                pass

    def _sync_manual_trade_ticket_to_chart(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
        side_picker = getattr(window, "_manual_trade_side_picker", None)
        type_picker = getattr(window, "_manual_trade_type_picker", None)
        price_input = getattr(window, "_manual_trade_price_input", None)
        stop_loss_input = getattr(window, "_manual_trade_stop_loss_input", None)
        take_profit_input = getattr(window, "_manual_trade_take_profit_input", None)

        symbol = str(symbol_picker.currentText() or "").strip() if symbol_picker is not None else ""
        if not symbol:
            self._clear_trade_overlays()
            return

        side = str(side_picker.currentText() or "buy").strip().lower() if side_picker is not None else "buy"
        order_type = str(type_picker.currentText() or "market").strip().lower() if type_picker is not None else "market"
        entry = self._safe_float(price_input.text()) if (price_input is not None and order_type in {"limit", "stop_limit"}) else None
        stop_loss = self._safe_float(stop_loss_input.text()) if stop_loss_input is not None else None
        take_profit = self._safe_float(take_profit_input.text()) if take_profit_input is not None else None

        for chart in self._all_chart_widgets():
            try:
                if getattr(chart, "symbol", "") == symbol:
                    chart.set_trade_overlay(entry=entry, stop_loss=stop_loss, take_profit=take_profit, side=side)
                else:
                    chart.clear_trade_overlay()
            except Exception:
                continue

    def _set_manual_trade_text_field(self, window, attr_name, value):
        field = getattr(window, attr_name, None)
        if field is None:
            return
        field.blockSignals(True)
        field.setText("" if value in (None, "") else str(value))
        field.blockSignals(False)
        self._refresh_manual_trade_ticket(window)

    def _set_manual_trade_order_type(self, window, value):
        picker = getattr(window, "_manual_trade_type_picker", None)
        if picker is None:
            return
        picker.blockSignals(True)
        picker.setCurrentText(str(value or "market"))
        picker.blockSignals(False)
        self._refresh_manual_trade_ticket(window)

    def _submit_manual_trade_side(self, window, side):
        submit_manual_trade_side(self, window, side)

    def _refresh_manual_trade_ticket(self, window):
        refresh_manual_trade_ticket(self, window)

    def _populate_manual_trade_ticket(self, window, prefill=None):
        populate_manual_trade_ticket(self, window, prefill=prefill)

    def _open_manual_trade(self, prefill=None):
        if not getattr(self.controller, "broker", None):
            QMessageBox.warning(self, "Manual Order", "Connect a broker before placing an order.")
            return
        window = self._get_or_create_tool_window(
            "manual_trade_ticket",
            "Manual Trade Ticket",
            width=560,
            height=460,
        )
        ensure_manual_trade_ticket_window(self, window)

        self._populate_manual_trade_ticket(window, prefill=prefill)
        window.show()
        window.raise_()
        window.activateWindow()

    def _submit_manual_trade_from_ticket(self, window):
        submit_manual_trade_from_ticket(self, window)

    def _optimize_strategy(self):
        self._open_text_window(
            "strategy_optimization",
            "Strategy Optimization",
            """
            <h2>Strategy Optimization</h2>
            <p>This workspace is reserved for parameter sweeps and strategy comparison.</p>
            <p>Current chart timeframe: <b>{}</b></p>
            <p>Loaded symbols: <b>{}</b></p>
            <p>Optimization controls can be added here next without changing the main terminal layout.</p>
            """.format(self.current_timeframe, len(getattr(self.controller, "symbols", []))),
            width=680,
            height=420,
        )

    def _get_or_create_tool_window(self, key, title, width=900, height=560) -> Any:
        window: Any = self.detached_tool_windows.get(key)

        if window is not None:
            if self._is_qt_object_alive(window):
                window.showNormal()
                window.raise_()
                window.activateWindow()
                return window
            self.detached_tool_windows.pop(key, None)

        parent = self if isinstance(self, QWidget) else None
        window = QMainWindow(parent)
        window.setObjectName(f"tool_window_{key}")
        window.setWindowFlag(Qt.WindowType.Window, True)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.setWindowTitle(title)
        window.resize(width, height)
        window.setStyleSheet(Terminal._detached_tool_window_style(self))
        window.destroyed.connect(
            lambda *_: self.detached_tool_windows.pop(key, None)
        )

        self.detached_tool_windows[key] = window
        return window

    def _clone_table_widget(self, source, target):
        if not self._is_qt_object_alive(source) or not self._is_qt_object_alive(target):
            return
        if self._monitor_table_is_busy(target):
            return

        blocked = target.blockSignals(True)
        target.setUpdatesEnabled(False)
        try:
            target.clearContents()
            target.setColumnCount(source.columnCount())
            target.setRowCount(source.rowCount())

            headers = []
            for col in range(source.columnCount()):
                header_item = source.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"Column {col + 1}")
            target.setHorizontalHeaderLabels(headers)

            for row in range(source.rowCount()):
                for col in range(source.columnCount()):
                    source_item = source.item(row, col)
                    if source_item is None:
                        continue
                    target.setItem(row, col, source_item.clone())

            target.resizeColumnsToContents()
            target.horizontalHeader().setStretchLastSection(True)
        finally:
            target.setUpdatesEnabled(True)
            target.blockSignals(blocked)

    def _configure_monitor_table(self, table):
        if table is None or not self._is_qt_object_alive(table):
            return

        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        table.setDragEnabled(False)
        table.setSortingEnabled(False)
        table.setWordWrap(False)
        table.setCornerButtonEnabled(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        table.setShowGrid(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if table.viewport() is not None:
            table.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        table.setStyleSheet(
            "QTableWidget { "
            "background-color: #0f1726; color: #d9e6f7; gridline-color: #20324d; "
            "border: 1px solid #20324d; border-radius: 12px; alternate-background-color: #0c1421; "
            "}"
            "QTableWidget::item:selected { background-color: #1c3150; color: #ffffff; }"
            "QHeaderView::section { "
            "background-color: #101c2e; color: #9fb5d3; padding: 8px 10px; border: 0; "
            "border-bottom: 1px solid #22344f; font-weight: 700; "
            "}"
        )

    def _monitor_table_is_busy(self, table):
        if table is None or not self._is_qt_object_alive(table):
            return True

        try:
            viewport = table.viewport()
        except Exception:
            viewport = None

        mouse_pressed = QApplication.mouseButtons() != Qt.MouseButton.NoButton
        if mouse_pressed and (table.underMouse() or (viewport is not None and viewport.underMouse())):
            return True

        return bool(table.hasFocus() or (viewport is not None and viewport.hasFocus()))

    def _sync_logs_window(self, editor):
        sync_logs_window(self, editor)

    def _open_logs(self):
        open_logs(self)

    def _open_ml_monitor(self):
        open_ml_monitor(self)

    def _open_text_window(self, key, title, html, width=760, height=520):
        return open_text_window(self, key, title, html, width=width, height=height)

    def _format_backtest_timestamp(self, value):
        if value in (None, ""):
            return "-"

        try:
            numeric = float(value)
            if numeric > 1e12:
                numeric /= 1000.0
            return QDateTime.fromSecsSinceEpoch(int(numeric)).toString("yyyy-MM-dd HH:mm")
        except Exception:
            return str(value)

    def _format_backtest_range(self, dataset):
        if dataset is None or not hasattr(dataset, "__len__") or len(dataset) == 0:
            return "-"

        try:
            start_value = dataset.iloc[0]["timestamp"]
            end_value = dataset.iloc[-1]["timestamp"]
        except Exception:
            try:
                start_value = dataset[0][0]
                end_value = dataset[-1][0]
            except Exception:
                return "-"

        return f"{self._format_backtest_timestamp(start_value)} -> {self._format_backtest_timestamp(end_value)}"

    def _append_backtest_journal(self, message, level="INFO"):
        lines = list(getattr(self, "_backtest_journal_lines", []) or [])
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        lines.append(f"[{timestamp}] {level.upper()}: {message}")
        self._backtest_journal_lines = lines[-300:]
        self._refresh_backtest_window()

    def _populate_backtest_results_table(self, table, trades_df):
        headers = ["Time", "Symbol", "Side", "Type", "Price", "Amount", "PnL", "Equity", "Reason"]
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        if trades_df is None or getattr(trades_df, "empty", True):
            table.setRowCount(0)
            return

        table.setRowCount(len(trades_df))

        for row_index, (_idx, row) in enumerate(trades_df.iterrows()):
            values = [
                self._format_backtest_timestamp(row.get("timestamp")),
                row.get("symbol", "-"),
                row.get("side", "-"),
                row.get("type", "-"),
                f"{float(row.get('price', 0) or 0):.6f}",
                f"{float(row.get('amount', 0) or 0):.6f}",
                f"{float(row.get('pnl', 0) or 0):.2f}",
                f"{float(row.get('equity', 0) or 0):.2f}",
                row.get("reason", ""),
            ]
            for column, value in enumerate(values):
                table.setItem(row_index, column, QTableWidgetItem(str(value)))

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _build_backtest_report_text(self, context, report, trades_df):
        symbol = context.get("symbol", "-")
        timeframe = context.get("timeframe", "-")
        strategy_name = context.get("strategy_name") or getattr(self.controller, "strategy_name", None) or getattr(getattr(self.controller, "config", None), "strategy", "Trend Following")
        candle_count = len(context.get("data")) if hasattr(context.get("data"), "__len__") else 0
        initial_deposit = float(getattr(self.controller, "initial_capital", 10000) or 10000)
        spread_pct = float(getattr(self.controller, "spread_pct", 0.0) or 0.0)
        equity_curve = getattr(getattr(self, "backtest_engine", None), "equity_curve", []) or []
        requested_range_text = _hotfix_backtest_requested_range_text(context=context)
        requested_bars = _hotfix_backtest_requested_limit(context=context, fallback=getattr(self.controller, "limit", 50000))

        report = report or {}
        total_profit = float(report.get("total_profit", 0.0) or 0.0)
        total_trades = int(report.get("total_trades", 0) or 0)
        closed_trades = int(report.get("closed_trades", 0) or 0)
        win_rate = float(report.get("win_rate", 0.0) or 0.0) * 100.0
        avg_profit = float(report.get("avg_profit", 0.0) or 0.0)
        max_drawdown = float(report.get("max_drawdown", 0.0) or 0.0)
        final_equity = float(report.get("final_equity", initial_deposit) or initial_deposit)

        gross_profit = 0.0
        gross_loss = 0.0
        if trades_df is not None and not getattr(trades_df, "empty", True) and "pnl" in trades_df:
            pnl_series = trades_df["pnl"].fillna(0).astype(float)
            gross_profit = float(pnl_series[pnl_series > 0].sum())
            gross_loss = float(pnl_series[pnl_series < 0].sum())

        profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0 else (gross_profit if gross_profit > 0 else 0.0)
        bars = len(equity_curve) if equity_curve else candle_count

        lines = [
            "Strategy Tester Report",
            "",
            f"Expert: {strategy_name}",
            f"Symbol: {symbol}",
            f"Period: {timeframe}",
            "Model: Bar-close simulation",
            f"Spread: {spread_pct:.4f}%",
            f"Initial Deposit: {initial_deposit:.2f}",
            f"Bars in Test: {bars}",
            f"Target Bars: {requested_bars}",
            f"Selected Dates: {requested_range_text}",
            f"Range: {self._format_backtest_range(context.get('data'))}",
            "",
            f"Total Net Profit: {total_profit:.2f}",
            f"Gross Profit: {gross_profit:.2f}",
            f"Gross Loss: {gross_loss:.2f}",
            f"Profit Factor: {profit_factor:.2f}",
            f"Expected Payoff: {avg_profit:.2f}",
            f"Max Drawdown: {max_drawdown:.2f}",
            f"Total Trades: {total_trades}",
            f"Closed Trades: {closed_trades}",
            f"Win Rate: {win_rate:.2f}%",
            f"Final Equity: {final_equity:.2f}",
        ]
        return "\n".join(lines)

    def _show_backtest_window(self):
        return show_backtest_window(self)

    def _refresh_backtest_window(self, window=None, message=None):
        refresh_backtest_window(self, window=window, message=message)

    def _show_risk_settings_window(self):
        risk_engine = getattr(self.controller, "risk_engine", None)
        if risk_engine is None:
            QMessageBox.warning(self, "Risk Engine Missing", "Trading/risk engine is not initialized yet.")
            return None

        window = self._get_or_create_tool_window(
            "risk_settings",
            "Risk Settings",
            width=460,
            height=340,
        )

        if getattr(window, "_risk_container", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            form = QFormLayout()

            max_portfolio = QDoubleSpinBox()
            max_portfolio.setRange(0, 1)
            max_portfolio.setSingleStep(0.01)

            max_trade = QDoubleSpinBox()
            max_trade.setRange(0, 1)
            max_trade.setSingleStep(0.01)

            max_position = QDoubleSpinBox()
            max_position.setRange(0, 1)
            max_position.setSingleStep(0.01)

            max_gross = QDoubleSpinBox()
            max_gross.setRange(0, 5)
            max_gross.setSingleStep(0.1)

            form.addRow("Max Portfolio Risk:", max_portfolio)
            form.addRow("Max Risk Per Trade:", max_trade)
            form.addRow("Max Position Size:", max_position)
            form.addRow("Max Gross Exposure:", max_gross)
            layout.addLayout(form)

            status = QLabel("-")
            status.setStyleSheet("color: #9fb0c7;")
            layout.addWidget(status)

            save_btn = QPushButton("Save Risk Settings")
            save_btn.clicked.connect(lambda: self._apply_risk_settings(window))
            layout.addWidget(save_btn)

            window.setCentralWidget(container)
            window._risk_container = container
            window._risk_max_portfolio = max_portfolio
            window._risk_max_trade = max_trade
            window._risk_max_position = max_position
            window._risk_max_gross = max_gross
            window._risk_status = status

        window._risk_max_portfolio.setValue(getattr(risk_engine, "max_portfolio_risk", 0.2))
        window._risk_max_trade.setValue(getattr(risk_engine, "max_risk_per_trade", 0.02))
        window._risk_max_position.setValue(getattr(risk_engine, "max_position_size_pct", 0.05))
        window._risk_max_gross.setValue(getattr(risk_engine, "max_gross_exposure_pct", 1.0))
        window._risk_status.setText("Adjust limits and click Save Risk Settings.")

        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _apply_risk_settings(self, window):
        try:
            risk_engine = getattr(self.controller, "risk_engine", None)
            if risk_engine is None:
                return

            risk_engine.max_portfolio_risk = window._risk_max_portfolio.value()
            risk_engine.max_risk_per_trade = window._risk_max_trade.value()
            risk_engine.max_position_size_pct = window._risk_max_position.value()
            risk_engine.max_gross_exposure_pct = window._risk_max_gross.value()

            window._risk_status.setText("Risk settings saved.")
            self.system_console.log("Risk settings updated successfully.")
        except Exception as exc:
            self.logger.error(f"Risk settings error: {exc}")

    def _populate_portfolio_exposure_table(self, table):
        positions = self._active_positions_snapshot()
        if table.columnCount() < 4:
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(
                ["Symbol", "Size", "Value (USD)", "Portfolio %"]
            )
        table.setRowCount(len(positions))
        total_value = sum(float(pos.get("value", 0) or 0) for pos in positions)

        for row, pos in enumerate((positions)):
            symbol = pos.get("symbol", "-")
            size = pos.get("amount", pos.get("size", "-"))
            value = float(pos.get("value", 0) or 0)
            pct = (value / total_value * 100) if total_value else 0

            table.setItem(row, 0, QTableWidgetItem(str(symbol)))
            table.setItem(row, 1, QTableWidgetItem(f"{float(size or 0):.6f}".rstrip("0").rstrip(".")))
            table.setItem(row, 2, QTableWidgetItem(f"{value:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{pct:.2f}%"))

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _show_portfolio_exposure_window(self):
        window = self._get_or_create_tool_window(
            "portfolio_exposure",
            "Portfolio Exposure",
            width=760,
            height=460,
        )

        table = getattr(window, "_exposure_table", None)
        if table is None:
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(
                ["Symbol", "Size", "Value (USD)", "Portfolio %"]
            )
            window.setCentralWidget(table)
            window._exposure_table = table

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(
                lambda: self._populate_portfolio_exposure_table(table)
            )
            sync_timer.start(1200)
            window._sync_timer = sync_timer

        self._populate_portfolio_exposure_table(table)
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _show_about(self):
        version_text = html.escape(self._app_version_text())
        self._open_text_window(
            "about_window",
            "About TradeAdviser",
            f"""
            <h2>TradeAdviser</h2>
            <p><b>Built by:</b> TradeAdviser Team</p>
            <p><b>Version:</b> {version_text}</p>
            <p><b>Workspace:</b> Open access desktop runtime</p>
            <p><b>Purpose:</b> AI-assisted multi-broker trading workstation for live trading, paper trading, analytics, and historical testing.</p>
            <p><b>Main capabilities:</b> live charts, AI signal monitoring, orderbook analysis, risk controls, backtesting, strategy optimization, and broker abstraction across crypto, stocks, forex, paper, and Stellar.</p>
            <p><b>Best use:</b> start in paper mode, validate charts and signals, confirm balances and risk limits, then move into live trading only after the setup looks stable.</p>
            <p><b>Core stack:</b> PySide6, pyqtgraph, pandas, technical-analysis indicators, broker adapters, and async market-data pipelines.</p>
            <p><b>Designed for:</b> fast iteration without losing visibility into risk, execution status, or model behavior.</p>
            """,
            width=700,
            height=520,
        )

    def _app_version_text(self):
        repo_root = Path(__file__).resolve().parents[3]
        package_version = self._read_package_version(repo_root)
        git_version = self._read_git_version(repo_root)

        if package_version and git_version:
            return f"{package_version} ({git_version})"
        if git_version:
            return git_version
        if package_version:
            return package_version
        return "Version not available"

    def _read_package_version(self, repo_root: Path):
        pyproject_path = repo_root / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        try:
            version = _read_pyproject_version(pyproject_path)
            if version:
                return version
        except Exception:
            return None
        return None

    def _read_git_version(self, repo_root: Path):
        try:
            describe = subprocess.run(
                ["git", "describe", "--tags", "--always", "--dirty"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if not describe:
                return None

            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if branch and branch != "HEAD":
                return f"{describe} on {branch}"
            return describe
        except Exception:
            return None

    def _close_all_positions(self):
        close_all_positions(self)

    def _export_trades(self):
        export_trades(self)

    def _cancel_all_orders(self):
        cancel_all_orders(self)

    def _show_async_message(self, title, text, icon=QMessageBox.Icon.Information):
        show_async_message(self, title, text, icon=icon)

    async def _submit_manual_trade(
        self,
        symbol,
        side,
        amount,
        requested_amount=None,
        quantity_mode="units",
        order_type="market",
        price=None,
        stop_price=None,
        stop_loss=None,
        take_profit=None,
    ):
        try:
            await submit_live_manual_trade(
                self,
                symbol=symbol,
                side=side,
                amount=amount,
                requested_amount=requested_amount,
                quantity_mode=quantity_mode,
                order_type=order_type,
                price=price,
                stop_price=stop_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        except Exception as exc:
            self.logger.exception("Manual order failed")
            self.system_console.log(f"Manual order failed for {symbol}: {exc}", "ERROR")
            self._show_async_message("Manual Order Failed", str(exc), QMessageBox.Icon.Critical)

    def _tracked_app_positions(self):
        trading_system = getattr(self.controller, "trading_system", None)
        portfolio_manager = getattr(trading_system, "portfolio", None)
        portfolio = getattr(portfolio_manager, "portfolio", None)
        positions = getattr(portfolio, "positions", {}) if portfolio is not None else {}
        tracked = []
        if not isinstance(positions, dict):
            return tracked

        for symbol, position in positions.items():
            quantity = float(getattr(position, "quantity", 0) or 0)
            if quantity == 0:
                continue
            tracked.append(
                {
                    "symbol": symbol,
                    "amount": abs(quantity),
                    "side": "long" if quantity > 0 else "short",
                }
            )
        return tracked

    async def _close_all_positions_async(self, show_dialog=True):
        await close_all_positions_async(self, show_dialog=show_dialog)

    async def _cancel_all_orders_async(self, show_dialog=True):
        await cancel_all_orders_async(self, show_dialog=show_dialog)

    def _open_docs(self):
        open_docs(self)

    def _open_api_docs(self):
        self._open_text_window(
            "api_reference",
            "API Reference",
            """
            <h2>API Reference</h2>
            <h3>Broker Layer</h3>
            <p>The app uses a normalized broker interface so the terminal can work across multiple providers with the same core methods.</p>
            <p><b>Common market-data methods:</b> fetch_ticker, fetch_orderbook, fetch_ohlcv, fetch_trades, fetch_symbols, fetch_markets, fetch_status.</p>
            <p><b>Common trading methods:</b> create_order, cancel_order, cancel_all_orders.</p>
            <p><b>Common account methods:</b> fetch_balance, fetch_positions, fetch_orders, fetch_open_orders, fetch_closed_orders, fetch_order.</p>
            <p><b>Controller refresh surfaces:</b> candles, order book, recent public trades, ticker updates, and chart market-context views are all normalized through the controller before the terminal renders them.</p>

            <h3>Broker Types in This App</h3>
            <p><b>CCXTBroker:</b> crypto exchanges using the CCXT unified API.</p>
            <p><b>OandaBroker:</b> forex account and market access.</p>
            <p><b>AlpacaBroker:</b> stock and equity trading access.</p>
            <p><b>PaperBroker:</b> local simulation for testing flows safely.</p>
            <p><b>StellarBroker:</b> Horizon-backed Stellar market data, balances, offers, and signed offer submission.</p>

            <h3>Configuration Fields</h3>
            <p><b>type:</b> crypto, forex, stocks, or paper.</p>
            <p><b>exchange:</b> provider name such as binanceus, coinbase, oanda, alpaca, paper, or stellar.</p>
            <p><b>mode:</b> live or paper.</p>
            <p><b>api_key / secret:</b> broker credentials. For Stellar this maps to public key and secret seed.</p>
            <p><b>account_id:</b> required for Oanda.</p>
            <p><b>password / passphrase:</b> required on some exchanges. Coinbase Advanced Trade in this app uses API key name plus private key instead.</p>
            <p><b>sandbox:</b> enables testnet or practice behavior where supported.</p>
            <p><b>options / params:</b> broker-specific advanced settings.</p>

            <h3>Execution Notes</h3>
            <p>Execution passes through a router and execution manager. Before orders are sent, the app checks balances, market state, minimums, and cooldown status.</p>
            <p>Exchange-specific rejections are logged and may place the symbol on cooldown to reduce error spam.</p>

            <h3>Backtesting and Optimization Internals</h3>
            <p><b>BacktestEngine:</b> replays candle windows through the active strategy and simulator.</p>
            <p><b>Simulator:</b> executes simplified buy/sell flows for historical testing.</p>
            <p><b>ReportGenerator:</b> creates summary metrics plus PDF/spreadsheet exports.</p>
            <p><b>StrategyOptimizer:</b> runs parameter sweeps and ranks results by performance.</p>

            <h3>Live Data Notes</h3>
            <p>Some brokers use websocket market data; others fall back to polling. Stellar currently uses polling via Horizon.</p>

            <h3>External References</h3>
            <p><a href="https://docs.ccxt.com">CCXT Documentation</a></p>
            <p><a href="https://github.com/ccxt/ccxt/wiki/manual">CCXT Manual</a></p>
            <p><a href="https://developers.stellar.org/docs/data/apis/horizon/api-reference">Stellar Horizon API Reference</a></p>
            <p><a href="https://stellar-sdk.readthedocs.io/en/latest/index.html">stellar-sdk Python Documentation</a></p>
            <p><a href="https://alpaca.markets/docs/">Alpaca API Docs</a></p>
            <p><a href="https://developer.oanda.com/rest-live-v20/introduction/">Oanda v20 API Docs</a></p>
            """,
            width=900,
            height=720,
        )

    def _learning_market_snapshot(self):
        symbol = ""
        try:
            symbol = str(self._current_chart_symbol() or "").strip().upper()
        except Exception:
            symbol = ""
        if not symbol:
            symbol = str(getattr(self, "symbol", "") or "").strip().upper()

        loaded_symbols = list(getattr(self.controller, "symbols", []) or [])
        if not symbol and loaded_symbols:
            symbol = str(loaded_symbols[0]).strip().upper()

        timeframe = str(getattr(self, "current_timeframe", "") or "1h").strip() or "1h"
        try:
            exchange_name = str(self._active_exchange_name() or "").strip()
        except Exception:
            exchange_name = ""

        return {
            "focus_symbol": symbol or "No active symbol",
            "timeframe": timeframe,
            "exchange": exchange_name.upper() or "DESK",
            "loaded_symbols": len(loaded_symbols),
            "connection": str(getattr(self, "current_connection_status", "connecting") or "connecting").strip().title(),
            "news_mode": "Live feed on" if bool(getattr(self.controller, "news_enabled", True)) else "Live feed off",
            "autotrade_mode": "Enabled" if bool(getattr(self, "autotrading_enabled", False)) else "Disabled",
        }

    def _trader_tv_html(self):
        snapshot = self._learning_market_snapshot()
        focus_symbol = html.escape(snapshot["focus_symbol"])
        timeframe = html.escape(snapshot["timeframe"])
        exchange = html.escape(snapshot["exchange"])
        connection = html.escape(snapshot["connection"])
        news_mode = html.escape(snapshot["news_mode"])
        autotrade_mode = html.escape(snapshot["autotrade_mode"])

        return f"""
            <h2>Trader TV</h2>
            <p><b>Trader TV</b> is the desk-side market briefing for the current Sopotek session. Use it to learn what matters before you place a trade.</p>

            <h3>Current Desk Snapshot</h3>
            <p>
                <b>Desk:</b> {exchange}<br>
                <b>Focus symbol:</b> {focus_symbol}<br>
                <b>Time frame:</b> {timeframe}<br>
                <b>Loaded symbols:</b> {snapshot["loaded_symbols"]}<br>
                <b>Connection:</b> {connection}<br>
                <b>News mode:</b> {news_mode}<br>
                <b>Auto trading:</b> {autotrade_mode}
            </p>

            <h3>What To Learn From The Market</h3>
            <ul>
                <li><b>Trend:</b> Start with the higher-timeframe direction before drilling into entries.</li>
                <li><b>Volatility:</b> Watch candle expansion, ATR, and spread changes before sizing up.</li>
                <li><b>Liquidity:</b> Check order-book depth and recent prints so you do not trade into thin conditions.</li>
                <li><b>Event risk:</b> Treat macro releases, earnings, and breaking news as volatility events.</li>
            </ul>

            <h3>Trader TV Segments</h3>
            <ul>
                <li><b>Pre-Market Map:</b> Mark the dominant trend, nearby support and resistance, and the high-impact calendar events for the session.</li>
                <li><b>Intraday Rotation:</b> Compare leaders, laggards, and correlated symbols to understand where capital is rotating.</li>
                <li><b>Risk Window:</b> Confirm whether volatility is expanding fast enough to justify a trade and whether your stop still fits the plan.</li>
                <li><b>Closing Review:</b> Revisit your best and worst decisions while the market context is still fresh.</li>
            </ul>

            <h3>Where To Continue In Sopotek</h3>
            <ul>
                <li><b>Charts -&gt; Studies:</b> Layer RSI, moving averages, ATR, and volume studies onto the active chart.</li>
                <li><b>Research -&gt; Sopotek Pilot:</b> Ask the AI for symbol context, scenario planning, and trade ideas.</li>
                <li><b>Analyze -&gt; Positions &amp; Risk:</b> Check exposure, position structure, and portfolio limits before execution.</li>
                <li><b>Review -&gt; Journal Review:</b> Turn live observations into repeatable lessons after the session.</li>
            </ul>
        """

    def _trader_tv_interval(self, timeframe=None):
        mapping = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "45m": "45",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "1d": "D",
            "1w": "W",
            "1mn": "M",
            "1mo": "M",
        }
        key = str(timeframe or getattr(self, "current_timeframe", "1h") or "1h").strip().lower()
        return mapping.get(key, "60")

    def _trader_tv_symbol(self, snapshot=None):
        snapshot = snapshot or self._learning_market_snapshot()
        raw_symbol = str(snapshot.get("focus_symbol") or "").strip().upper()
        exchange = str(snapshot.get("exchange") or "").strip().upper()
        if not raw_symbol or raw_symbol == "NO ACTIVE SYMBOL":
            return "COINBASE:BTCUSD"

        if ":" in raw_symbol and "/" not in raw_symbol:
            return raw_symbol

        futures_symbols = {
            "ES": "CME_MINI:ES1!",
            "MES": "CME_MINI:MES1!",
            "NQ": "CME_MINI:NQ1!",
            "MNQ": "CME_MINI:MNQ1!",
            "YM": "CBOT_MINI:YM1!",
            "MYM": "CBOT_MINI:MYM1!",
            "RTY": "CME_MINI:RTY1!",
            "M2K": "CME_MINI:M2K1!",
            "CL": "NYMEX:CL1!",
            "MCL": "NYMEX:MCL1!",
            "GC": "COMEX:GC1!",
            "MGC": "COMEX:MGC1!",
            "SI": "COMEX:SI1!",
            "HG": "COMEX:HG1!",
            "ZB": "CBOT:ZB1!",
            "ZN": "CBOT:ZN1!",
            "6E": "CME:6E1!",
            "6J": "CME:6J1!",
        }
        if raw_symbol in futures_symbols:
            return futures_symbols[raw_symbol]

        exchange_map = {
            "ALPACA": "NASDAQ",
            "AMP": "CME_MINI",
            "BINANCE": "BINANCE",
            "BINANCEUS": "BINANCE",
            "COINBASE": "COINBASE",
            "IBKR": "NASDAQ",
            "KRAKEN": "KRAKEN",
            "OANDA": "OANDA",
            "PAPER": "COINBASE",
            "SCHWAB": "NASDAQ",
            "STELLAR": "CRYPTO",
            "TDAMERITRADE": "NASDAQ",
            "TRADOVATE": "CME_MINI",
        }

        if "/" in raw_symbol:
            base, quote = raw_symbol.split("/", 1)
            base = re.sub(r"[^A-Z0-9]", "", base)
            quote = re.sub(r"[^A-Z0-9]", "", quote.split(":", 1)[0])
            if exchange == "OANDA" and len(base) == 3 and len(quote) == 3:
                return f"OANDA:{base}{quote}"
            provider = exchange_map.get(exchange)
            if provider is None:
                if len(base) == 3 and len(quote) == 3:
                    provider = "OANDA"
                elif quote in {"USD", "USDT", "USDC"}:
                    provider = "COINBASE"
                else:
                    provider = "NASDAQ"
            return f"{provider}:{base}{quote}"

        if re.fullmatch(r"[A-Z]{1,5}", raw_symbol or ""):
            return f"{exchange_map.get(exchange, 'NASDAQ')}:{raw_symbol}"

        return "COINBASE:BTCUSD"

    def _trader_tv_chart_url(self, snapshot=None):
        snapshot = snapshot or self._learning_market_snapshot()
        return f"https://www.tradingview.com/chart/?symbol={quote_plus(self._trader_tv_symbol(snapshot))}"

    def _trader_tv_video_url(self, snapshot=None):
        snapshot = snapshot or self._learning_market_snapshot()
        focus_symbol = str(snapshot.get("focus_symbol") or "").strip().upper()
        exchange = str(snapshot.get("exchange") or "").strip().upper()
        if focus_symbol and focus_symbol != "NO ACTIVE SYMBOL":
            query = f"{focus_symbol} {exchange} market analysis live trading"
        else:
            query = "market analysis live trading"
        return f"https://www.youtube.com/results?search_query={quote_plus(query.strip())}"

    def _trader_tv_chart_embed_html(self, snapshot=None):
        snapshot = snapshot or self._learning_market_snapshot()
        widget_config = {
            "autosize": True,
            "symbol": self._trader_tv_symbol(snapshot),
            "interval": self._trader_tv_interval(snapshot.get("timeframe")),
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "withdateranges": True,
            "hide_side_toolbar": False,
            "allow_symbol_change": True,
            "watchlist": [],
            "details": True,
            "hotlist": True,
            "calendar": False,
            "support_host": "https://www.tradingview.com",
            "container_id": "trader_tv_chart_widget",
        }
        return f"""
            <!doctype html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    html, body {{
                        margin: 0;
                        background: #0b1220;
                        height: 100%;
                        overflow: hidden;
                    }}
                    .tradingview-widget-container,
                    #trader_tv_chart_widget {{
                        height: 100%;
                        width: 100%;
                    }}
                </style>
            </head>
            <body>
                <div class="tradingview-widget-container">
                    <div id="trader_tv_chart_widget"></div>
                    <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
                    {json.dumps(widget_config)}
                    </script>
                </div>
            </body>
            </html>
        """

    def _trader_tv_browser_fallback_html(self, title, description, primary_label, primary_url, secondary_label=None, secondary_url=None):
        primary_label = html.escape(str(primary_label or "Open"))
        primary_url = html.escape(str(primary_url or ""))
        secondary_html = ""
        if secondary_label and secondary_url:
            secondary_html = (
                f'<p><a href="{html.escape(str(secondary_url))}">{html.escape(str(secondary_label))}</a></p>'
            )
        return f"""
            <h2>{html.escape(str(title or "Trader TV"))}</h2>
            <p>{html.escape(str(description or ""))}</p>
            <p><a href="{primary_url}">{primary_label}</a></p>
            {secondary_html}
            <p>Install the Qt WebEngine components to view live embedded media directly inside Trader TV.</p>
        """

    def _trader_tv_web_view_class(self):
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore
        except Exception:
            return None
        return QWebEngineView

    def _education_center_html(self):
        snapshot = self._learning_market_snapshot()
        focus_symbol = html.escape(snapshot["focus_symbol"])
        timeframe = html.escape(snapshot["timeframe"])

        return f"""
            <h2>Education Center</h2>
            <p><b>Education Center</b> is the trader learning hub inside Sopotek. Use it to build skill, rehearse process, and connect lessons to the live workspace.</p>

            <h3>Learning Track</h3>
            <ol>
                <li><b>Market structure:</b> Learn trend, range, breakout, pullback, and failed breakout behavior.</li>
                <li><b>Trade location:</b> Practice entering only where reward-to-risk is clear and invalidation is obvious.</li>
                <li><b>Risk control:</b> Keep size aligned with volatility, stop distance, and your account rules.</li>
                <li><b>Execution discipline:</b> Trade the plan you wrote, not the emotion you feel in the moment.</li>
                <li><b>Review loop:</b> Journal every good and bad trade so the next session starts smarter.</li>
            </ol>

            <h3>Practice Loop Inside This App</h3>
            <ul>
                <li><b>Step 1:</b> Open <b>{focus_symbol}</b> on <b>{timeframe}</b> and map the structure with chart studies.</li>
                <li><b>Step 2:</b> Use <b>Trader TV</b> and <b>Sopotek Pilot</b> to form a market thesis.</li>
                <li><b>Step 3:</b> Run the idea through <b>Analyze</b> for exposure, stop placement, and portfolio fit.</li>
                <li><b>Step 4:</b> Execute in paper mode first, then review it in <b>Closed Journal</b> and <b>Journal Review</b>.</li>
            </ul>

            <h3>Study Topics To Repeat Weekly</h3>
            <ul>
                <li><b>Context:</b> How trend, volatility, and liquidity change the same setup.</li>
                <li><b>Risk:</b> Why the best traders protect downside before they chase upside.</li>
                <li><b>Process:</b> How checklists and journals improve consistency more than raw prediction.</li>
                <li><b>Adaptation:</b> How to review losses without overfitting or revenge trading.</li>
            </ul>

            <h3>Ready-For-Live Checklist</h3>
            <ul>
                <li>You can explain the setup in one sentence before you enter.</li>
                <li>You know where the trade is wrong before you know where it can win.</li>
                <li>Your size respects the risk profile, not your latest emotion.</li>
                <li>You are willing to review the trade honestly after it closes.</li>
            </ul>
        """

    def _open_trader_tv_window(self):
        window = self._get_or_create_tool_window(
            "education_trader_tv",
            "Trader TV",
            width=1160,
            height=820,
        )

        if getattr(window, "_trader_tv_tabs", None) is None:
            container = QWidget()
            container.setStyleSheet("background-color: #0b1220;")
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(12)

            intro = QLabel(
                "Trader TV now gives you a live chart surface, a market-video feed, and the desk brief in one place."
            )
            intro.setWordWrap(True)
            intro.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 12px; font-size: 14px; font-weight: 600;"
            )
            layout.addWidget(intro)

            action_row = QHBoxLayout()
            action_row.setSpacing(8)

            refresh_button = QPushButton("Refresh Trader TV")
            refresh_button.setStyleSheet(self._action_button_style())
            refresh_button.clicked.connect(lambda: self._open_trader_tv_window())
            action_row.addWidget(refresh_button)

            open_chart_button = QPushButton("Open TradingView")
            open_chart_button.setStyleSheet(self._action_button_style())
            open_chart_button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(str(getattr(window, "_trader_tv_chart_url", ""))))
            )
            action_row.addWidget(open_chart_button)

            open_video_button = QPushButton("Open YouTube Feed")
            open_video_button.setStyleSheet(self._action_button_style())
            open_video_button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(str(getattr(window, "_trader_tv_video_url", ""))))
            )
            action_row.addWidget(open_video_button)

            action_row.addStretch(1)
            layout.addLayout(action_row)

            status = QLabel()
            status.setWordWrap(True)
            status.setStyleSheet("color: #8fa7c6; padding: 0 2px 2px 2px;")
            layout.addWidget(status)

            tabs = QTabWidget()
            tabs.setDocumentMode(True)
            tabs.setStyleSheet(
                "QTabWidget::pane { border: 1px solid #20324d; background-color: #0b1220; }"
                "QTabBar::tab { background-color: #101a2d; color: #cfe0f7; padding: 8px 12px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px; }"
                "QTabBar::tab:selected { background-color: #163150; color: #ffffff; }"
            )
            layout.addWidget(tabs, stretch=1)

            brief_browser = QTextBrowser()
            brief_browser.setOpenExternalLinks(True)
            brief_browser.setStyleSheet(
                "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; border-radius: 10px; padding: 14px; }"
            )
            tabs.addTab(brief_browser, "Desk Brief")

            web_view_class = self._trader_tv_web_view_class()
            chart_surface = None
            chart_mode = "fallback"
            if web_view_class is not None:
                try:
                    chart_surface = web_view_class()
                    chart_mode = "web"
                except Exception:
                    chart_surface = None
                    chart_mode = "fallback"
            if chart_surface is None:
                chart_surface = QTextBrowser()
                chart_surface.setOpenExternalLinks(True)
                chart_surface.setStyleSheet(
                    "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; border-radius: 10px; padding: 14px; }"
                )
            tabs.addTab(chart_surface, "TradingView")

            video_surface = None
            video_mode = "fallback"
            if web_view_class is not None:
                try:
                    video_surface = web_view_class()
                    video_mode = "web"
                except Exception:
                    video_surface = None
                    video_mode = "fallback"
            if video_surface is None:
                video_surface = QTextBrowser()
                video_surface.setOpenExternalLinks(True)
                video_surface.setStyleSheet(
                    "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; border-radius: 10px; padding: 14px; }"
                )
            tabs.addTab(video_surface, "Market Video")

            window.setCentralWidget(container)
            window._trader_tv_tabs = tabs
            window._trader_tv_intro = intro
            window._trader_tv_status = status
            window._trader_tv_brief_browser = brief_browser
            window._trader_tv_chart_surface = chart_surface
            window._trader_tv_chart_mode = chart_mode
            window._trader_tv_video_surface = video_surface
            window._trader_tv_video_mode = video_mode
            window._trader_tv_open_chart_button = open_chart_button
            window._trader_tv_open_video_button = open_video_button

        snapshot = self._learning_market_snapshot()
        chart_url = self._trader_tv_chart_url(snapshot)
        video_url = self._trader_tv_video_url(snapshot)
        window._trader_tv_chart_url = chart_url
        window._trader_tv_video_url = video_url

        focus_symbol = html.escape(str(snapshot.get("focus_symbol") or "No active symbol"))
        timeframe = html.escape(str(snapshot.get("timeframe") or "1h"))
        exchange = html.escape(str(snapshot.get("exchange") or "DESK"))
        status = getattr(window, "_trader_tv_status", None)
        if status is not None:
            mode_label = "embedded live panels" if (
                getattr(window, "_trader_tv_chart_mode", "fallback") == "web"
                and getattr(window, "_trader_tv_video_mode", "fallback") == "web"
            ) else "browser-linked media panels"
            status.setText(
                f"Watching {focus_symbol} on {timeframe} from {exchange}. Trader TV is running in {mode_label} mode."
            )

        brief_browser = getattr(window, "_trader_tv_brief_browser", None)
        if brief_browser is not None:
            brief_browser.setHtml(self._trader_tv_html())

        chart_surface = getattr(window, "_trader_tv_chart_surface", None)
        if chart_surface is not None:
            if getattr(window, "_trader_tv_chart_mode", "fallback") == "web":
                chart_surface.setHtml(self._trader_tv_chart_embed_html(snapshot), QUrl("https://www.tradingview.com/"))
            else:
                chart_surface.setHtml(
                    self._trader_tv_browser_fallback_html(
                        "TradingView Panel",
                        "Open the live chart in your browser when Qt WebEngine is unavailable in this environment.",
                        "Launch TradingView chart",
                        chart_url,
                        "Open the market video feed",
                        video_url,
                    )
                )

        video_surface = getattr(window, "_trader_tv_video_surface", None)
        if video_surface is not None:
            if getattr(window, "_trader_tv_video_mode", "fallback") == "web":
                video_surface.load(QUrl(video_url))
            else:
                video_surface.setHtml(
                    self._trader_tv_browser_fallback_html(
                        "Market Video Feed",
                        "Open a YouTube market-analysis feed focused on the current desk symbol.",
                        "Launch YouTube market feed",
                        video_url,
                        "Open TradingView chart",
                        chart_url,
                    )
                )

        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _open_education_center_window(self):
        return self._open_text_window(
            "education_center",
            "Education Center",
            self._education_center_html(),
            width=940,
            height=760,
        )

    def _multi_chart_layout(self):

        try:
            symbols = self._multi_chart_symbols(max_count=4)
            if not symbols:
                if hasattr(self, "system_console") and self.system_console is not None:
                    self.system_console.log("No symbols are available to build a multi-chart workspace.", "INFO")
                return

            timeframe = str(self.current_timeframe or "1h").strip().lower() or "1h"
            self._close_multi_chart_pages()

            screen = QApplication.primaryScreen()
            available = screen.availableGeometry() if screen is not None else self.geometry()
            count = len(symbols)
            columns = 1 if count == 1 else 2
            rows = max(1, int(np.ceil(count / columns)))
            width = max(420, available.width() // columns)
            height = max(320, available.height() // rows)

            opened_windows = []
            preferred_window = None
            preferred_symbol = str(self._current_chart_symbol() or getattr(self, "symbol", "")).strip().upper()

            for index, symbol in enumerate(symbols):
                row = index // columns
                column = index % columns
                rect = QRect(
                    available.x() + (column * width),
                    available.y() + (row * height),
                    width,
                    height,
                )
                window = self._open_or_focus_detached_chart(
                    symbol,
                    timeframe,
                    geometry=rect,
                    compact_view=True,
                )
                if self._is_qt_object_alive(window):
                    opened_windows.append(window)
                    if preferred_window is None or str(symbol).upper() == preferred_symbol:
                        preferred_window = window

            if self._is_qt_object_alive(preferred_window):
                preferred_window.raise_()
                preferred_window.activateWindow()
            elif opened_windows:
                opened_windows[-1].raise_()
                opened_windows[-1].activateWindow()

        except Exception as e:

            self.logger.error(f"Multi chart layout error: {e}")

    def _open_performance(self):
        window = self._get_or_create_tool_window(
            "performance_analytics",
            "Performance Analytics",
            width=1120,
            height=780,
        )

        if getattr(window, "_performance_container", None) is None:
            container = QWidget()
            container.setStyleSheet("background-color: #0b1220;")
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(12)

            summary = QLabel("Performance analytics will summarize profitability, risk, execution quality, and symbol contribution.")
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 14px; padding: 14px; font-size: 14px; font-weight: 600;"
            )
            layout.addWidget(summary)

            metric_names = [
                "Equity",
                "Starting Equity",
                "Net PnL",
                "Return",
                "Trades",
                "Realized Trades",
                "Win Rate",
                "Profit Factor",
                "Fees",
                "Execution Drag",
                "Avg Spread",
                "Avg Slippage",
                "Sharpe Ratio",
                "Sortino Ratio",
                "Max Drawdown",
                "VaR (95%)",
            ]
            stats_grid, metric_labels = self._build_performance_metric_grid(metric_names, columns=4)
            layout.addLayout(stats_grid)

            equity_plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(orientation="bottom")})
            self._style_performance_plot(equity_plot, left_label="Equity", bottom_label="Time")
            equity_plot.setMinimumHeight(230)
            curve = equity_plot.plot(pen=pg.mkPen("#2a7fff", width=2.4))
            layout.addWidget(equity_plot)

            drawdown_plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(orientation="bottom")})
            self._style_performance_plot(drawdown_plot, left_label="Drawdown", bottom_label="Time")
            drawdown_plot.setMinimumHeight(170)
            drawdown_curve = drawdown_plot.plot(
                pen=pg.mkPen("#ef5350", width=1.8),
                fillLevel=0,
                brush=pg.mkBrush(239, 83, 80, 70),
            )
            layout.addWidget(drawdown_plot)

            insights = QTextBrowser()
            insights.setOpenExternalLinks(False)
            insights.setMinimumHeight(150)
            insights.setStyleSheet(
                "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 10px; }"
            )
            layout.addWidget(insights)

            symbol_table = QTableWidget()
            symbol_table.setColumnCount(6)
            symbol_table.setHorizontalHeaderLabels(
                ["Symbol", "Orders", "Realized", "Win Rate", "Net PnL", "Avg PnL"]
            )
            symbol_table.setStyleSheet(
                "QTableWidget { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; "
                "border-radius: 12px; gridline-color: #20324d; }"
            )
            layout.addWidget(symbol_table)

            window.setCentralWidget(container)
            window._performance_container = container
            window._performance_widgets = {
                "summary": summary,
                "metric_labels": metric_labels,
                "equity_curve": curve,
                "drawdown_curve": drawdown_curve,
                "insights": insights,
                "symbol_table": symbol_table,
            }

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._refresh_performance_window(window))
            sync_timer.start(1000)
            window._sync_timer = sync_timer

        self._refresh_performance_window(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _populate_closed_journal_table(self, table, rows):
        if table is None or not self._is_qt_object_alive(table):
            return
        if table.columnCount() < 11:
            table.setColumnCount(11)
        table.setRowCount(len(rows or []))
        for row_index, row in enumerate(rows or []):
            outcome = str(row.get("outcome") or self._derived_trade_outcome(row) or "").strip()
            values = [
                row.get("timestamp", ""),
                row.get("symbol", ""),
                self._format_trade_source_label(row.get("source", "")),
                row.get("side", ""),
                row.get("price", ""),
                row.get("size", ""),
                row.get("order_type", ""),
                row.get("status", ""),
                outcome,
                row.get("order_id", ""),
                row.get("pnl", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(self._format_trade_log_value(value))
                table.setItem(row_index, column, item)
            tooltip_lines = []
            if row.get("strategy_name"):
                tooltip_lines.append(f"Strategy: {row.get('strategy_name')}")
            if row.get("reason"):
                tooltip_lines.append(f"Reason: {row.get('reason')}")
            if row.get("setup"):
                tooltip_lines.append(f"Setup: {row.get('setup')}")
            if outcome:
                tooltip_lines.append(f"Outcome: {outcome}")
            if row.get("lessons"):
                tooltip_lines.append(f"Lessons: {row.get('lessons')}")
            if self._safe_float(row.get("stop_loss")) is not None:
                tooltip_lines.append(f"Stop Loss: {self._format_trade_log_value(row.get('stop_loss'))}")
            if self._safe_float(row.get("take_profit")) is not None:
                tooltip_lines.append(f"Take Profit: {self._format_trade_log_value(row.get('take_profit'))}")
            if self._safe_float(row.get("confidence")) is not None:
                tooltip_lines.append(f"Confidence: {float(row.get('confidence')) * 100.0:.1f}%")
            if self._safe_float(row.get("spread_bps")) is not None:
                tooltip_lines.append(f"Spread: {float(row.get('spread_bps')):.2f} bps")
            if self._safe_float(row.get("slippage_bps")) is not None:
                tooltip_lines.append(f"Slippage: {float(row.get('slippage_bps')):.2f} bps")
            if self._safe_float(row.get("fee")) is not None:
                tooltip_lines.append(f"Fee: {self._format_currency(row.get('fee'))}")
            tooltip = "\n".join(tooltip_lines)
            if tooltip:
                for column in range(table.columnCount()):
                    item = table.item(row_index, column)
                    if item is not None:
                        item.setToolTip(tooltip)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _schedule_closed_journal_refresh(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        task = getattr(window, "_closed_refresh_task", None)
        if task is not None and not task.done():
            return
        try:
            window._closed_refresh_task = asyncio.get_event_loop().create_task(
                self._refresh_closed_journal_async(window)
            )
        except Exception as exc:
            self.logger.debug("Unable to schedule closed journal refresh: %s", exc)

    async def _refresh_closed_journal_async(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        controller = self.controller
        table = getattr(window, "_closed_journal_table", None)
        summary = getattr(window, "_closed_journal_summary", None)
        if (
            table is None
            or summary is None
            or not self._is_qt_object_alive(table)
            or not self._is_qt_object_alive(summary)
        ):
            return
        try:
            rows = await controller.fetch_trade_history(limit=220)
        except Exception as exc:
            rows = []
            self.logger.debug("Closed journal refresh failed: %s", exc)
        if (
            window is None
            or not self._is_qt_object_alive(window)
            or not self._is_qt_object_alive(table)
            or not self._is_qt_object_alive(summary)
        ):
            return
        window._closed_journal_rows = list(rows or [])
        self._populate_closed_journal_table(table, rows)
        summary.setText(
            f"Closed journal shows {len(rows)} merged broker and local trade-history rows. Double-click a row for post-trade review."
        )

    def _open_closed_journal_window(self):
        window = self._get_or_create_tool_window(
            "closed_trade_journal",
            "Closed Trade Journal",
            width=1120,
            height=620,
        )

        if getattr(window, "_closed_journal_table", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            summary = QLabel("Loading closed-trade history from broker and local trade records.")
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
            )
            layout.addWidget(summary)

            controls = QHBoxLayout()
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(lambda: self._schedule_closed_journal_refresh(window))
            review_btn = QPushButton("Review Trade")
            review_btn.clicked.connect(lambda: self._open_trade_review_from_journal(window))
            summary_btn = QPushButton("Weekly/Monthly Review")
            summary_btn.clicked.connect(self._open_trade_journal_review_window)
            controls.addWidget(refresh_btn)
            controls.addWidget(review_btn)
            controls.addWidget(summary_btn)
            controls.addStretch()
            layout.addLayout(controls)

            table = QTableWidget()
            table.setColumnCount(11)
            table.setHorizontalHeaderLabels(
                ["Timestamp", "Symbol", "Source", "Side", "Price", "Size", "Order Type", "Status", "Outcome", "Order ID", "PnL"]
            )
            table.cellDoubleClicked.connect(lambda *_: self._open_trade_review_from_journal(window))
            layout.addWidget(table)

            window.setCentralWidget(container)
            window._closed_journal_summary = summary
            window._closed_journal_table = table
            window._closed_journal_rows = []
            window._closed_journal_review_btn = review_btn
            window._closed_journal_summary_btn = summary_btn

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._schedule_closed_journal_refresh(window))
            sync_timer.start(4000)
            window._closed_journal_timer = sync_timer

        self._schedule_closed_journal_refresh(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _default_trade_checklist_snapshot(self):
        mode = "live" if str(getattr(getattr(self.controller, "config", None), "mode", "demo") or "demo").strip().lower() == "live" else "demo"
        timeframe = str(getattr(self, "current_timeframe", getattr(self.controller, "time_frame", "1h")) or "1h").strip() or "1h"
        symbol = str(self._current_chart_symbol() or getattr(self, "symbol", "") or "").strip()
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")
        watch_symbols = [symbol] if symbol else []
        while len(watch_symbols) < 4:
            watch_symbols.append("")
        return {
            "account": str(getattr(self.controller, "current_account_label", lambda: "")() or "").strip(),
            "date": current_date,
            "time": current_time,
            "timeframe": timeframe,
            "mode": mode,
            "watch_symbols": watch_symbols[:4],
            "news_bias": "",
            "strategy_setup": "",
            "setup_timeframe": timeframe,
            "higher_tf_confirmed": "",
            "entry_trigger": "",
            "stop_loss_reason": "",
            "take_profit_reason": "",
            "risk_reward_target": "",
            "account_equity": "",
            "risk_per_trade": "",
            "risk_dollar": "",
            "stop_distance": "",
            "position_formula": "Position lots = Risk $ / (Stop distance * pip/point value per lot)",
            "exit_reason": "",
            "actual_pnl": "",
            "actual_pnl_pct": "",
            "trade_duration": "",
            "action_items": "",
            "daily_max_loss": "",
            "ai_enabled": "Y" if getattr(self, "autotrading_enabled", False) else "N",
            "telegram_alerts": "Y" if getattr(self.controller, "telegram_enabled", False) else "N",
            "journal_coverage": "Y",
            "trader_name": "",
            "signature": "",
            "review_date": current_date,
            "checkboxes": {
                "economic_calendar": False,
                "market_session": False,
                "recent_news": False,
                "spread_slippage": False,
                "orders_placed_on_chart": False,
                "size_matches_risk": False,
                "planned_screenshot": False,
                "stop_adjustment_rule": False,
                "close_on_invalidation": False,
                "no_averaging": False,
                "journal_logged": False,
                "weekly_review": False,
                "daily_max_loss_rule": False,
                "avoid_major_news": False,
                "fixed_position_sizing": False,
            },
        }

    def _trade_checklist_snapshot(self, window):
        snapshot = self._default_trade_checklist_snapshot()
        snapshot.update(
            {
                "account": window._trade_checklist_account.text().strip(),
                "date": window._trade_checklist_date.text().strip(),
                "time": window._trade_checklist_time.text().strip(),
                "timeframe": window._trade_checklist_timeframe.text().strip(),
                "mode": str(window._trade_checklist_mode.currentData() or "demo"),
                "watch_symbols": [
                    window._trade_checklist_watch_1.text().strip(),
                    window._trade_checklist_watch_2.text().strip(),
                    window._trade_checklist_watch_3.text().strip(),
                    window._trade_checklist_watch_4.text().strip(),
                ],
                "news_bias": window._trade_checklist_news_bias.text().strip(),
                "strategy_setup": window._trade_checklist_strategy_setup.toPlainText().strip(),
                "setup_timeframe": window._trade_checklist_setup_timeframe.text().strip(),
                "higher_tf_confirmed": window._trade_checklist_higher_tf.text().strip(),
                "entry_trigger": window._trade_checklist_entry_trigger.toPlainText().strip(),
                "stop_loss_reason": window._trade_checklist_stop_loss.toPlainText().strip(),
                "take_profit_reason": window._trade_checklist_take_profit.toPlainText().strip(),
                "risk_reward_target": window._trade_checklist_rr_target.text().strip(),
                "account_equity": window._trade_checklist_equity.text().strip(),
                "risk_per_trade": window._trade_checklist_risk_per_trade.text().strip(),
                "risk_dollar": window._trade_checklist_risk_dollar.text().strip(),
                "stop_distance": window._trade_checklist_stop_distance.text().strip(),
                "position_formula": window._trade_checklist_position_formula.text().strip(),
                "exit_reason": window._trade_checklist_exit_reason.text().strip(),
                "actual_pnl": window._trade_checklist_actual_pnl.text().strip(),
                "actual_pnl_pct": window._trade_checklist_actual_pnl_pct.text().strip(),
                "trade_duration": window._trade_checklist_trade_duration.text().strip(),
                "action_items": window._trade_checklist_action_items.toPlainText().strip(),
                "daily_max_loss": window._trade_checklist_daily_max_loss.text().strip(),
                "ai_enabled": window._trade_checklist_ai_enabled.text().strip(),
                "telegram_alerts": window._trade_checklist_telegram_alerts.text().strip(),
                "journal_coverage": window._trade_checklist_journal_coverage.text().strip(),
                "trader_name": window._trade_checklist_trader_name.text().strip(),
                "signature": window._trade_checklist_signature.text().strip(),
                "review_date": window._trade_checklist_review_date.text().strip(),
                "checkboxes": {
                    key: checkbox.isChecked()
                    for key, checkbox in getattr(window, "_trade_checklist_checkboxes", {}).items()
                },
            }
        )
        return snapshot

    def _apply_trade_checklist_snapshot(self, window, snapshot):
        data = self._default_trade_checklist_snapshot()
        if isinstance(snapshot, dict):
            data.update(snapshot)
        watch_symbols = list(data.get("watch_symbols") or ["", "", "", ""])
        while len(watch_symbols) < 4:
            watch_symbols.append("")

        window._trade_checklist_account.setText(str(data.get("account") or ""))
        window._trade_checklist_date.setText(str(data.get("date") or ""))
        window._trade_checklist_time.setText(str(data.get("time") or ""))
        window._trade_checklist_timeframe.setText(str(data.get("timeframe") or ""))
        mode_index = window._trade_checklist_mode.findData(str(data.get("mode") or "demo"))
        window._trade_checklist_mode.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        window._trade_checklist_watch_1.setText(str(watch_symbols[0] or ""))
        window._trade_checklist_watch_2.setText(str(watch_symbols[1] or ""))
        window._trade_checklist_watch_3.setText(str(watch_symbols[2] or ""))
        window._trade_checklist_watch_4.setText(str(watch_symbols[3] or ""))
        window._trade_checklist_news_bias.setText(str(data.get("news_bias") or ""))
        window._trade_checklist_strategy_setup.setPlainText(str(data.get("strategy_setup") or ""))
        window._trade_checklist_setup_timeframe.setText(str(data.get("setup_timeframe") or ""))
        window._trade_checklist_higher_tf.setText(str(data.get("higher_tf_confirmed") or ""))
        window._trade_checklist_entry_trigger.setPlainText(str(data.get("entry_trigger") or ""))
        window._trade_checklist_stop_loss.setPlainText(str(data.get("stop_loss_reason") or ""))
        window._trade_checklist_take_profit.setPlainText(str(data.get("take_profit_reason") or ""))
        window._trade_checklist_rr_target.setText(str(data.get("risk_reward_target") or ""))
        window._trade_checklist_equity.setText(str(data.get("account_equity") or ""))
        window._trade_checklist_risk_per_trade.setText(str(data.get("risk_per_trade") or ""))
        window._trade_checklist_risk_dollar.setText(str(data.get("risk_dollar") or ""))
        window._trade_checklist_stop_distance.setText(str(data.get("stop_distance") or ""))
        window._trade_checklist_position_formula.setText(str(data.get("position_formula") or ""))
        window._trade_checklist_exit_reason.setText(str(data.get("exit_reason") or ""))
        window._trade_checklist_actual_pnl.setText(str(data.get("actual_pnl") or ""))
        window._trade_checklist_actual_pnl_pct.setText(str(data.get("actual_pnl_pct") or ""))
        window._trade_checklist_trade_duration.setText(str(data.get("trade_duration") or ""))
        window._trade_checklist_action_items.setPlainText(str(data.get("action_items") or ""))
        window._trade_checklist_daily_max_loss.setText(str(data.get("daily_max_loss") or ""))
        window._trade_checklist_ai_enabled.setText(str(data.get("ai_enabled") or ""))
        window._trade_checklist_telegram_alerts.setText(str(data.get("telegram_alerts") or ""))
        window._trade_checklist_journal_coverage.setText(str(data.get("journal_coverage") or ""))
        window._trade_checklist_trader_name.setText(str(data.get("trader_name") or ""))
        window._trade_checklist_signature.setText(str(data.get("signature") or ""))
        window._trade_checklist_review_date.setText(str(data.get("review_date") or ""))

        checkbox_values = data.get("checkboxes") if isinstance(data.get("checkboxes"), dict) else {}
        for key, checkbox in getattr(window, "_trade_checklist_checkboxes", {}).items():
            checkbox.setChecked(bool(checkbox_values.get(key, False)))
        self._update_trade_checklist_status(window)

    def _update_trade_checklist_status(self, window, message=None):
        if not self._is_qt_object_alive(window):
            return
        warning = getattr(window, "_trade_checklist_warning", None)
        status = getattr(window, "_trade_checklist_status", None)
        if warning is not None:
            mode = str(window._trade_checklist_mode.currentData() or "demo")
            equity_text = str(window._trade_checklist_equity.text() or "").replace("$", "").replace(",", "").strip()
            equity = self._safe_float(equity_text)
            if mode == "live" and equity is not None and equity < 100:
                warning.setText("Live mode with equity under $100: strongly consider demo or micro-lots only.")
                warning.setStyleSheet("color:#ffd7a8; background-color:#2a1d12; border:1px solid #8b5a2b; border-radius:10px; padding:8px 10px;")
            else:
                warning.setText("Checklist ready. Use it before entry, during management, and in post-trade review.")
                warning.setStyleSheet("color:#9fd6c2; background-color:#11241d; border:1px solid #285746; border-radius:10px; padding:8px 10px;")
        if status is not None and message is not None:
            status.setText(message)

    def _save_trade_checklist(self, window):
        self.settings.setValue("trade_checklist/latest", json.dumps(self._trade_checklist_snapshot(window)))
        self._update_trade_checklist_status(window, "Trade checklist saved.")

    def _prefill_trade_checklist(self, window):
        snapshot = self._default_trade_checklist_snapshot()
        current = self._trade_checklist_snapshot(window)
        for key in ("trader_name", "signature", "daily_max_loss", "risk_per_trade", "risk_dollar", "position_formula"):
            snapshot[key] = current.get(key, snapshot.get(key, ""))
        self._apply_trade_checklist_snapshot(window, snapshot)
        self._update_trade_checklist_status(window, "Checklist prefilled from current app context.")

    def _reset_trade_checklist(self, window):
        self._apply_trade_checklist_snapshot(window, self._default_trade_checklist_snapshot())
        self._update_trade_checklist_status(window, "Checklist reset to defaults.")

    def _open_trade_checklist_window(self):
        window = self._get_or_create_tool_window(
            "trade_checklist",
            "Trade Checklist",
            width=980,
            height=840,
        )

        if getattr(window, "_trade_checklist_container", None) is None:
            container = QWidget()
            root_layout = QVBoxLayout(container)
            root_layout.setContentsMargins(12, 12, 12, 12)
            root_layout.setSpacing(10)

            intro = QLabel("Use this checklist to validate the trade before entry, manage it consistently, and review it afterward.")
            intro.setWordWrap(True)
            intro.setStyleSheet("color:#d9e6f7; font-weight:600; padding:4px 0;")
            root_layout.addWidget(intro)

            warning = QLabel("")
            warning.setWordWrap(True)
            root_layout.addWidget(warning)

            button_row = QHBoxLayout()
            prefill_btn = QPushButton("Prefill Current")
            save_btn = QPushButton("Save Checklist")
            reset_btn = QPushButton("Reset")
            button_row.addWidget(prefill_btn)
            button_row.addWidget(save_btn)
            button_row.addWidget(reset_btn)
            button_row.addStretch(1)
            root_layout.addLayout(button_row)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            form_holder = QWidget()
            form_layout = QVBoxLayout(form_holder)
            form_layout.setSpacing(12)

            def section(title):
                frame = QFrame()
                frame.setStyleSheet(
                    "QFrame { background-color:#101a2d; border:1px solid #20324d; border-radius:12px; }"
                    "QLabel { color:#d8e6ff; }"
                    "QLineEdit, QTextEdit, QComboBox { background-color:#09111f; color:#e7f0ff; border:1px solid #24344f; border-radius:8px; padding:6px; }"
                    "QCheckBox { color:#d8e6ff; spacing:8px; }"
                )
                layout = QVBoxLayout(frame)
                layout.setContentsMargins(12, 12, 12, 12)
                layout.setSpacing(8)
                title_label = QLabel(title)
                title_label.setStyleSheet("font-size:14px; font-weight:700; color:#f4f8ff;")
                layout.addWidget(title_label)
                form_layout.addWidget(frame)
                return layout

            account_layout = section("Account & Setup")
            account_grid = QGridLayout()
            account = QLineEdit()
            date_input = QLineEdit()
            time_input = QLineEdit()
            timeframe_input = QLineEdit()
            mode = QComboBox()
            mode.addItem("Demo", "demo")
            mode.addItem("Live", "live")
            watch_1 = QLineEdit()
            watch_2 = QLineEdit()
            watch_3 = QLineEdit()
            watch_4 = QLineEdit()
            account_grid.addWidget(QLabel("Account"), 0, 0)
            account_grid.addWidget(account, 0, 1)
            account_grid.addWidget(QLabel("Date"), 0, 2)
            account_grid.addWidget(date_input, 0, 3)
            account_grid.addWidget(QLabel("Time"), 1, 0)
            account_grid.addWidget(time_input, 1, 1)
            account_grid.addWidget(QLabel("Timeframe"), 1, 2)
            account_grid.addWidget(timeframe_input, 1, 3)
            account_grid.addWidget(QLabel("Mode"), 2, 0)
            account_grid.addWidget(mode, 2, 1)
            account_grid.addWidget(QLabel("Watch 1"), 3, 0)
            account_grid.addWidget(watch_1, 3, 1)
            account_grid.addWidget(QLabel("Watch 2"), 3, 2)
            account_grid.addWidget(watch_2, 3, 3)
            account_grid.addWidget(QLabel("Watch 3"), 4, 0)
            account_grid.addWidget(watch_3, 4, 1)
            account_grid.addWidget(QLabel("Watch 4"), 4, 2)
            account_grid.addWidget(watch_4, 4, 3)
            account_layout.addLayout(account_grid)

            pretrade_layout = section("Pre-market / Pre-trade")
            pretrade_checks = {
                "economic_calendar": QCheckBox("Check economic calendar — avoid high-impact events for this trade"),
                "market_session": QCheckBox("Confirm market session & liquidity for symbol"),
                "recent_news": QCheckBox("Check recent news for symbol"),
            }
            for checkbox in pretrade_checks.values():
                pretrade_layout.addWidget(checkbox)
            news_bias = QLineEdit()
            pretrade_layout.addWidget(QLabel("Recent news bias"))
            pretrade_layout.addWidget(news_bias)

            trade_layout = section("Trade Idea & Rule")
            strategy_setup = QTextEdit()
            strategy_setup.setMaximumHeight(70)
            setup_timeframe = QLineEdit()
            higher_tf = QLineEdit()
            entry_trigger = QTextEdit()
            entry_trigger.setMaximumHeight(60)
            stop_loss = QTextEdit()
            stop_loss.setMaximumHeight(60)
            take_profit = QTextEdit()
            take_profit.setMaximumHeight(60)
            rr_target = QLineEdit()
            trade_layout.addWidget(QLabel("Strategy / Setup"))
            trade_layout.addWidget(strategy_setup)
            trade_grid = QGridLayout()
            trade_grid.addWidget(QLabel("Timeframe"), 0, 0)
            trade_grid.addWidget(setup_timeframe, 0, 1)
            trade_grid.addWidget(QLabel("Higher TF confirmed (Y/N)"), 0, 2)
            trade_grid.addWidget(higher_tf, 0, 3)
            trade_layout.addLayout(trade_grid)
            trade_layout.addWidget(QLabel("Entry trigger (exact)"))
            trade_layout.addWidget(entry_trigger)
            trade_layout.addWidget(QLabel("Stop Loss (level & reason)"))
            trade_layout.addWidget(stop_loss)
            trade_layout.addWidget(QLabel("Take Profit (level & reason)"))
            trade_layout.addWidget(take_profit)
            trade_layout.addWidget(QLabel("Risk / Reward target (min)"))
            trade_layout.addWidget(rr_target)

            sizing_layout = section("Position Sizing")
            sizing_grid = QGridLayout()
            equity = QLineEdit()
            risk_per_trade = QLineEdit()
            risk_dollar = QLineEdit()
            stop_distance = QLineEdit()
            position_formula = QLineEdit()
            sizing_grid.addWidget(QLabel("Account equity"), 0, 0)
            sizing_grid.addWidget(equity, 0, 1)
            sizing_grid.addWidget(QLabel("Risk per trade % or $"), 0, 2)
            sizing_grid.addWidget(risk_per_trade, 0, 3)
            sizing_grid.addWidget(QLabel("Calculated risk $"), 1, 0)
            sizing_grid.addWidget(risk_dollar, 1, 1)
            sizing_grid.addWidget(QLabel("Stop distance"), 1, 2)
            sizing_grid.addWidget(stop_distance, 1, 3)
            sizing_grid.addWidget(QLabel("Position size formula"), 2, 0)
            sizing_grid.addWidget(position_formula, 2, 1, 1, 3)
            sizing_layout.addLayout(sizing_grid)
            sizing_layout.addWidget(QLabel("For small accounts: trade demo / micro-lots only"))

            execution_layout = section("Execution / During Trade / Post-trade")
            execution_checks = {
                "spread_slippage": QCheckBox("Re-check spread & slippage risk"),
                "orders_placed_on_chart": QCheckBox("Limit entry / take-profit / stop placed on chart"),
                "size_matches_risk": QCheckBox("Confirm order size matches risk calc"),
                "planned_screenshot": QCheckBox("Save / chart a screenshot of planned trade"),
                "stop_adjustment_rule": QCheckBox("Do not adjust stop unless plan allows"),
                "close_on_invalidation": QCheckBox("If invalidation is hit, close immediately"),
                "no_averaging": QCheckBox("No averaging into a losing trade unless pre-planned"),
            }
            for checkbox in execution_checks.values():
                execution_layout.addWidget(checkbox)
            exit_grid = QGridLayout()
            exit_reason = QLineEdit()
            actual_pnl = QLineEdit()
            actual_pnl_pct = QLineEdit()
            trade_duration = QLineEdit()
            exit_grid.addWidget(QLabel("Exit reason"), 0, 0)
            exit_grid.addWidget(exit_reason, 0, 1, 1, 3)
            exit_grid.addWidget(QLabel("Actual P&L $"), 1, 0)
            exit_grid.addWidget(actual_pnl, 1, 1)
            exit_grid.addWidget(QLabel("P&L %"), 1, 2)
            exit_grid.addWidget(actual_pnl_pct, 1, 3)
            exit_grid.addWidget(QLabel("Trade duration"), 2, 0)
            exit_grid.addWidget(trade_duration, 2, 1)
            execution_layout.addLayout(exit_grid)

            review_layout = section("Journal & Review / Risk & Behavior Controls / Sopotek")
            review_checks = {
                "journal_logged": QCheckBox("Log trade in journal (entry, exit, size, screenshots)"),
                "weekly_review": QCheckBox("Weekly review: Win rate, Avg RR, Expectancy, Max DD"),
                "daily_max_loss_rule": QCheckBox("Daily max loss rule enforced"),
                "avoid_major_news": QCheckBox("Avoid major news unless strategy is news-based"),
                "fixed_position_sizing": QCheckBox("Keep position sizing fixed to plan"),
            }
            for checkbox in review_checks.values():
                review_layout.addWidget(checkbox)
            action_items = QTextEdit()
            action_items.setMaximumHeight(80)
            daily_max_loss = QLineEdit()
            ai_enabled = QLineEdit()
            telegram_alerts = QLineEdit()
            journal_coverage = QLineEdit()
            review_layout.addWidget(QLabel("Action items for improvement"))
            review_layout.addWidget(action_items)
            review_grid = QGridLayout()
            review_grid.addWidget(QLabel("Daily max loss rule"), 0, 0)
            review_grid.addWidget(daily_max_loss, 0, 1)
            review_grid.addWidget(QLabel("AI Trading enabled?"), 1, 0)
            review_grid.addWidget(ai_enabled, 1, 1)
            review_grid.addWidget(QLabel("Telegram alerts set?"), 1, 2)
            review_grid.addWidget(telegram_alerts, 1, 3)
            review_grid.addWidget(QLabel("Journal coverage enabled?"), 2, 0)
            review_grid.addWidget(journal_coverage, 2, 1)
            review_layout.addLayout(review_grid)

            signoff_layout = section("Sign-off")
            signoff_grid = QGridLayout()
            trader_name = QLineEdit()
            signature = QLineEdit()
            review_date = QLineEdit()
            signoff_grid.addWidget(QLabel("Trader name"), 0, 0)
            signoff_grid.addWidget(trader_name, 0, 1)
            signoff_grid.addWidget(QLabel("Signature"), 0, 2)
            signoff_grid.addWidget(signature, 0, 3)
            signoff_grid.addWidget(QLabel("Review date"), 1, 0)
            signoff_grid.addWidget(review_date, 1, 1)
            signoff_layout.addLayout(signoff_grid)

            form_layout.addStretch(1)
            scroll.setWidget(form_holder)
            root_layout.addWidget(scroll, 1)

            status = QLabel("Checklist ready.")
            status.setWordWrap(True)
            status.setStyleSheet("color:#9fb0c7; padding-top:4px;")
            root_layout.addWidget(status)

            window.setCentralWidget(container)
            window._trade_checklist_container = container
            window._trade_checklist_warning = warning
            window._trade_checklist_status = status
            window._trade_checklist_account = account
            window._trade_checklist_date = date_input
            window._trade_checklist_time = time_input
            window._trade_checklist_timeframe = timeframe_input
            window._trade_checklist_mode = mode
            window._trade_checklist_watch_1 = watch_1
            window._trade_checklist_watch_2 = watch_2
            window._trade_checklist_watch_3 = watch_3
            window._trade_checklist_watch_4 = watch_4
            window._trade_checklist_news_bias = news_bias
            window._trade_checklist_strategy_setup = strategy_setup
            window._trade_checklist_setup_timeframe = setup_timeframe
            window._trade_checklist_higher_tf = higher_tf
            window._trade_checklist_entry_trigger = entry_trigger
            window._trade_checklist_stop_loss = stop_loss
            window._trade_checklist_take_profit = take_profit
            window._trade_checklist_rr_target = rr_target
            window._trade_checklist_equity = equity
            window._trade_checklist_risk_per_trade = risk_per_trade
            window._trade_checklist_risk_dollar = risk_dollar
            window._trade_checklist_stop_distance = stop_distance
            window._trade_checklist_position_formula = position_formula
            window._trade_checklist_exit_reason = exit_reason
            window._trade_checklist_actual_pnl = actual_pnl
            window._trade_checklist_actual_pnl_pct = actual_pnl_pct
            window._trade_checklist_trade_duration = trade_duration
            window._trade_checklist_action_items = action_items
            window._trade_checklist_daily_max_loss = daily_max_loss
            window._trade_checklist_ai_enabled = ai_enabled
            window._trade_checklist_telegram_alerts = telegram_alerts
            window._trade_checklist_journal_coverage = journal_coverage
            window._trade_checklist_trader_name = trader_name
            window._trade_checklist_signature = signature
            window._trade_checklist_review_date = review_date
            window._trade_checklist_checkboxes = {}
            window._trade_checklist_checkboxes.update(pretrade_checks)
            window._trade_checklist_checkboxes.update(execution_checks)
            window._trade_checklist_checkboxes.update(review_checks)

            prefill_btn.clicked.connect(lambda: self._prefill_trade_checklist(window))
            save_btn.clicked.connect(lambda: self._save_trade_checklist(window))
            reset_btn.clicked.connect(lambda: self._reset_trade_checklist(window))
            mode.currentIndexChanged.connect(lambda *_: self._update_trade_checklist_status(window))
            equity.textChanged.connect(lambda *_: self._update_trade_checklist_status(window))

        raw_snapshot = self.settings.value("trade_checklist/latest", "")
        try:
            snapshot = json.loads(_json_text(raw_snapshot, "{}")) if raw_snapshot else {}
        except Exception:
            snapshot = {}
        if not snapshot:
            snapshot = self._default_trade_checklist_snapshot()
        self._apply_trade_checklist_snapshot(window, snapshot)
        window.show()
        window.raise_()
        window.activateWindow()

    def _trade_review_selected_row(self, window):
        table = getattr(window, "_closed_journal_table", None)
        rows = list(getattr(window, "_closed_journal_rows", []) or [])
        if table is None:
            return None
        row = table.currentRow()
        if row < 0 or row >= len(rows):
            return None
        return rows[row]

    def _trade_timestamp_ms(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, QDateTime):
            return int(value.toMSecsSinceEpoch())
        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric > 1_000_000_000_000:
                return int(numeric)
            if numeric > 1_000_000_000:
                return int(numeric * 1000)
        text = str(value).strip()
        if not text:
            return None
        try:
            if text.isdigit():
                numeric = float(text)
                if numeric > 1_000_000_000_000:
                    return int(numeric)
                if numeric > 1_000_000_000:
                    return int(numeric * 1000)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp() * 1000)
        except Exception:
            return None

    def _trade_review_snapshot(self, trade, candles, trade_index):
        if not candles:
            return {"trade_index": 0, "post5": None, "post20": None}

        entry_price = self._safe_float(trade.get("price"))
        if entry_price is None:
            try:
                entry_price = float(candles[min(max(trade_index, 0), len(candles) - 1)].get("close"))
            except Exception:
                entry_price = None

        def _move_after(offset):
            target_index = trade_index + offset
            if entry_price in (None, 0) or target_index >= len(candles):
                return None
            try:
                target_close = float(candles[target_index].get("close"))
            except Exception:
                return None
            side = str(trade.get("side") or "").strip().lower()
            raw_move = (target_close - entry_price) / entry_price
            return raw_move if side == "buy" else -raw_move if side == "sell" else raw_move

        return {
            "trade_index": trade_index,
            "post5": _move_after(5),
            "post20": _move_after(20),
        }

    def _trade_review_html(self, trade, candles, trade_index):
        strategy = html.escape(str(trade.get("strategy_name") or "Not tagged"))
        reason = html.escape(str(trade.get("reason") or "No reason recorded"))
        source = html.escape(self._format_trade_source_label(trade.get("source") or "-") or "-")
        side = html.escape(str(trade.get("side") or "-").upper())
        status = html.escape(str(trade.get("status") or "-").upper())
        symbol = html.escape(str(trade.get("symbol") or "-"))
        review = self._trade_review_snapshot(trade, candles, trade_index)

        lines = [
            f"<h3 style='margin-bottom:6px;'>{symbol} | {side} | {status}</h3>",
            f"<p><b>Source:</b> {source} | <b>Strategy:</b> {strategy}</p>",
            f"<p><b>Why it was taken:</b> {reason}</p>",
            f"<p><b>Entry:</b> {html.escape(self._format_trade_log_value(trade.get('price')))} | "
            f"<b>Expected:</b> {html.escape(self._format_trade_log_value(trade.get('expected_price')))} | "
            f"<b>Size:</b> {html.escape(self._format_trade_log_value(trade.get('size')))}</p>",
        ]

        details = []
        confidence = self._safe_float(trade.get("confidence"))
        if confidence is not None:
            details.append(f"<b>Confidence:</b> {confidence * 100.0:.1f}%")
        spread_bps = self._safe_float(trade.get("spread_bps"))
        if spread_bps is not None:
            details.append(f"<b>Spread:</b> {spread_bps:.2f} bps")
        slippage_bps = self._safe_float(trade.get("slippage_bps"))
        if slippage_bps is not None:
            details.append(f"<b>Slippage:</b> {slippage_bps:.2f} bps")
        fee = self._safe_float(trade.get("fee"))
        if fee is not None:
            details.append(f"<b>Fee:</b> {self._format_currency(fee)}")
        pnl = self._safe_float(trade.get("pnl"))
        if pnl is not None:
            details.append(f"<b>Realized PnL:</b> {self._format_currency(pnl)}")
        if details:
            lines.append("<p>" + " | ".join(details) + "</p>")

        review_bits = []
        if review.get("post5") is not None:
            review_bits.append(f"<b>5-candle move:</b> {self._format_percent_text(review.get('post5'))}")
        if review.get("post20") is not None:
            review_bits.append(f"<b>20-candle move:</b> {self._format_percent_text(review.get('post20'))}")
        if review_bits:
            lines.append("<p>" + " | ".join(review_bits) + "</p>")

        journal_bits = []
        stop_loss = self._safe_float(trade.get("stop_loss"))
        take_profit = self._safe_float(trade.get("take_profit"))
        if stop_loss is not None:
            journal_bits.append(f"<b>Stop Loss:</b> {html.escape(self._format_trade_log_value(stop_loss))}")
        if take_profit is not None:
            journal_bits.append(f"<b>Take Profit:</b> {html.escape(self._format_trade_log_value(take_profit))}")
        if trade.get("outcome"):
            journal_bits.append(f"<b>Outcome:</b> {html.escape(str(trade.get('outcome')))}")
        if journal_bits:
            lines.append("<p>" + " | ".join(journal_bits) + "</p>")

        if trade.get("setup"):
            lines.append(f"<p><b>Setup:</b> {html.escape(str(trade.get('setup')))}</p>")
        if trade.get("lessons"):
            lines.append(f"<p><b>Lessons:</b> {html.escape(str(trade.get('lessons')))}</p>")

        if not candles:
            lines.append("<p>No candle context was available for replay.</p>")

        return "".join(lines)

    def _derived_trade_outcome(self, trade):
        def _local_safe_float(value):
            parser = getattr(self, "_safe_float", None)
            if callable(parser):
                return parser(value)
            if value in (None, "", "-"):
                return None
            try:
                return float(value)
            except Exception:
                return None

        if not isinstance(trade, dict):
            return ""
        explicit = str(trade.get("outcome") or "").strip()
        if explicit:
            return explicit
        pnl = _local_safe_float(trade.get("pnl"))
        status = str(trade.get("status") or "").strip().lower()
        if pnl is not None:
            if pnl > 0:
                return "Win"
            if pnl < 0:
                return "Loss"
            if status in {"filled", "closed"}:
                return "Flat"
        if status in {"rejected", "failed"}:
            return "Rejected"
        if status in {"canceled", "cancelled", "expired"}:
            return "Canceled"
        return status.title() if status else ""

    def _set_text_edit_value(self, widget, value):
        if widget is None:
            return
        widget.blockSignals(True)
        widget.setPlainText(str(value or ""))
        widget.blockSignals(False)

    def _trade_review_journal_text(self, widget):
        if widget is None:
            return ""
        try:
            return str(widget.toPlainText() or "").strip()
        except Exception:
            return ""

    def _populate_trade_review_journal_fields(self, window):
        state = getattr(window, "_trade_review_state", {}) or {}
        trade = state.get("trade") or {}
        reason_edit = getattr(window, "_trade_review_reason_edit", None)
        setup_edit = getattr(window, "_trade_review_setup_edit", None)
        outcome_edit = getattr(window, "_trade_review_outcome_edit", None)
        lessons_edit = getattr(window, "_trade_review_lessons_edit", None)
        stop_loss_input = getattr(window, "_trade_review_stop_loss_input", None)
        take_profit_input = getattr(window, "_trade_review_take_profit_input", None)

        self._set_text_edit_value(reason_edit, trade.get("reason"))
        self._set_text_edit_value(setup_edit, trade.get("setup"))
        self._set_text_edit_value(outcome_edit, trade.get("outcome") or self._derived_trade_outcome(trade))
        self._set_text_edit_value(lessons_edit, trade.get("lessons"))
        if stop_loss_input is not None:
            stop_loss_input.blockSignals(True)
            stop_loss_input.setText("" if trade.get("stop_loss") in (None, "") else str(trade.get("stop_loss")))
            stop_loss_input.blockSignals(False)
        if take_profit_input is not None:
            take_profit_input.blockSignals(True)
            take_profit_input.setText("" if trade.get("take_profit") in (None, "") else str(trade.get("take_profit")))
            take_profit_input.blockSignals(False)

    def _merge_trade_journal_update(self, target, updated):
        if not isinstance(target, dict):
            return
        for key in (
            "trade_db_id",
            "reason",
            "stop_loss",
            "take_profit",
            "setup",
            "outcome",
            "lessons",
        ):
            if key in updated:
                target[key] = updated.get(key)

    def _sync_trade_journal_windows(self, updated_trade):
        if not isinstance(updated_trade, dict):
            return

        trade_id = str(updated_trade.get("trade_db_id") or "").strip()
        order_id = str(updated_trade.get("order_id") or "").strip()

        closed_window = self.detached_tool_windows.get("closed_trade_journal")
        if closed_window is not None:
            rows = list(getattr(closed_window, "_closed_journal_rows", []) or [])
            for row in rows:
                row_trade_id = str(row.get("trade_db_id") or "").strip()
                row_order_id = str(row.get("order_id") or "").strip()
                if (trade_id and row_trade_id == trade_id) or (order_id and row_order_id == order_id):
                    self._merge_trade_journal_update(row, updated_trade)
            self._populate_closed_journal_table(getattr(closed_window, "_closed_journal_table", None), rows)

        review_window = self.detached_tool_windows.get("trade_review")
        if review_window is not None:
            state = getattr(review_window, "_trade_review_state", {}) or {}
            trade = state.get("trade") or {}
            row_trade_id = str(trade.get("trade_db_id") or "").strip()
            row_order_id = str(trade.get("order_id") or "").strip()
            if (trade_id and row_trade_id == trade_id) or (order_id and row_order_id == order_id):
                self._merge_trade_journal_update(trade, updated_trade)
                state["trade"] = trade
                review_window._trade_review_state = state
                self._populate_trade_review_journal_fields(review_window)
                self._render_trade_review_window(review_window)

        journal_review_window = self.detached_tool_windows.get("trade_journal_review")
        if journal_review_window is not None:
            self._schedule_trade_journal_review_refresh(journal_review_window)

    async def _save_trade_review_journal_async(self, window):
        state = getattr(window, "_trade_review_state", {}) or {}
        trade = dict(state.get("trade") or {})
        status_label = getattr(window, "_trade_review_journal_status", None)
        repository = getattr(self.controller, "trade_repository", None)
        if repository is None:
            if status_label is not None:
                status_label.setText("Trade repository not available.")
            return

        update_payload = {
            "trade_db_id": trade.get("trade_db_id"),
            "order_id": trade.get("order_id"),
            "exchange": getattr(getattr(self.controller, "broker", None), "exchange_name", None),
            "reason": self._trade_review_journal_text(getattr(window, "_trade_review_reason_edit", None)),
            "setup": self._trade_review_journal_text(getattr(window, "_trade_review_setup_edit", None)),
            "outcome": self._trade_review_journal_text(getattr(window, "_trade_review_outcome_edit", None)),
            "lessons": self._trade_review_journal_text(getattr(window, "_trade_review_lessons_edit", None)),
            "stop_loss": str(getattr(window, "_trade_review_stop_loss_input", None).text() or "").strip()
            if getattr(window, "_trade_review_stop_loss_input", None) is not None else "",
            "take_profit": str(getattr(window, "_trade_review_take_profit_input", None).text() or "").strip()
            if getattr(window, "_trade_review_take_profit_input", None) is not None else "",
        }

        if not update_payload["trade_db_id"] and not update_payload["order_id"]:
            if status_label is not None:
                status_label.setText("This trade cannot be journaled yet because no persistent trade id was found.")
            return

        if status_label is not None:
            status_label.setText("Saving journal notes...")

        try:
            saved = await asyncio.to_thread(
                repository.update_trade_journal,
                trade_id=update_payload["trade_db_id"],
                order_id=update_payload["order_id"],
                exchange=update_payload["exchange"],
                reason=update_payload["reason"],
                stop_loss=update_payload["stop_loss"],
                take_profit=update_payload["take_profit"],
                setup=update_payload["setup"],
                outcome=update_payload["outcome"],
                lessons=update_payload["lessons"],
            )
        except Exception as exc:
            self.logger.debug("Trade journal save failed: %s", exc)
            if status_label is not None:
                status_label.setText(f"Unable to save journal: {exc}")
            return

        if saved is None:
            if status_label is not None:
                status_label.setText("No matching stored trade was found to update.")
            return

        updated_trade = dict(trade)
        updated_trade.update(
            {
                "trade_db_id": getattr(saved, "id", trade.get("trade_db_id")),
                "reason": getattr(saved, "reason", None) or "",
                "stop_loss": getattr(saved, "stop_loss", None),
                "take_profit": getattr(saved, "take_profit", None),
                "setup": getattr(saved, "setup", None) or "",
                "outcome": getattr(saved, "outcome", None) or "",
                "lessons": getattr(saved, "lessons", None) or "",
            }
        )
        state["trade"] = updated_trade
        window._trade_review_state = state
        self._sync_trade_journal_windows(updated_trade)
        if status_label is not None:
            status_label.setText("Journal saved.")

    def _save_trade_review_journal(self, window):
        try:
            asyncio.get_event_loop().create_task(self._save_trade_review_journal_async(window))
        except Exception as exc:
            self.logger.debug("Unable to schedule trade journal save: %s", exc)
            status_label = getattr(window, "_trade_review_journal_status", None)
            if status_label is not None:
                status_label.setText("Unable to schedule journal save.")

    def _render_trade_review_window(self, window):
        state = getattr(window, "_trade_review_state", {}) or {}
        trade = state.get("trade") or {}
        candles = list(state.get("candles") or [])
        summary = getattr(window, "_trade_review_summary", None)
        details = getattr(window, "_trade_review_details", None)
        slider = getattr(window, "_trade_review_slider", None)
        curve = getattr(window, "_trade_review_curve", None)
        marker = getattr(window, "_trade_review_marker", None)
        vline = getattr(window, "_trade_review_vline", None)
        hline = getattr(window, "_trade_review_hline", None)

        if summary is not None:
            summary.setText(
                f"{trade.get('symbol', '-')} | {str(trade.get('side', '-')).upper()} | "
                f"{str(trade.get('status', '-')).upper()} | Strategy: {trade.get('strategy_name') or 'Not tagged'}"
            )

        if details is not None:
            details.setHtml(self._trade_review_html(trade, candles, int(state.get("trade_index", 0) or 0)))

        if not candles or curve is None or slider is None:
            if curve is not None:
                curve.setData([], [])
            if marker is not None:
                marker.setData([], [])
            return

        trade_index = min(max(int(state.get("trade_index", 0) or 0), 0), len(candles) - 1)
        slider.blockSignals(True)
        slider.setMinimum(0)
        slider.setMaximum(max(len(candles) - 1, 0))
        slider.setValue(min(max(int(slider.value()), trade_index), len(candles) - 1))
        slider.blockSignals(False)

        visible_end = max(int(slider.value()), trade_index)
        visible = candles[:visible_end + 1]
        x_values = list(range(len(visible)))
        close_values = [float(item.get("close", 0) or 0) for item in visible]
        curve.setData(x_values, close_values)

        marker_price = self._safe_float(trade.get("price"))
        if marker_price is None and 0 <= trade_index < len(candles):
            marker_price = self._safe_float(candles[trade_index].get("close"))
        if marker is not None:
            if trade_index <= visible_end and marker_price is not None:
                marker.setData([trade_index], [marker_price])
            else:
                marker.setData([], [])
        if vline is not None:
            vline.setValue(trade_index)
        if hline is not None and marker_price is not None:
            hline.setValue(marker_price)

    async def _load_trade_review_async(self, window, trade):
        candles = []
        trade_index = 0
        try:
            raw = await self.controller._safe_fetch_ohlcv(
                trade.get("symbol"),
                timeframe=self.current_timeframe,
                limit=220,
            )
        except Exception as exc:
            raw = []
            self.logger.debug("Trade review candle load failed: %s", exc)

        for row in raw or []:
            if not isinstance(row, (list, tuple)) or len(row) < 5:
                continue
            candles.append(
                {
                    "timestamp": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5] if len(row) > 5 else 0,
                }
            )

        if candles:
            target_ts = self._trade_timestamp_ms(trade.get("timestamp"))
            if target_ts is not None:
                indexed = []
                for idx, candle in enumerate(candles):
                    candle_ts = self._trade_timestamp_ms(candle.get("timestamp"))
                    if candle_ts is None:
                        continue
                    indexed.append((abs(candle_ts - target_ts), idx))
                if indexed:
                    trade_index = min(indexed)[1]
            trade_index = min(max(int(trade_index), 0), len(candles) - 1)

        window._trade_review_state = {
            "trade": dict(trade or {}),
            "candles": candles,
            "trade_index": trade_index,
        }
        self._populate_trade_review_journal_fields(window)
        slider = getattr(window, "_trade_review_slider", None)
        if slider is not None and candles:
            slider.blockSignals(True)
            slider.setMaximum(max(len(candles) - 1, 0))
            slider.setValue(min(len(candles) - 1, max(trade_index + 20, trade_index)))
            slider.blockSignals(False)
        self._render_trade_review_window(window)

    def _toggle_trade_review_playback(self, window):
        timer = getattr(window, "_trade_review_timer", None)
        button = getattr(window, "_trade_review_play_btn", None)
        slider = getattr(window, "_trade_review_slider", None)
        if timer is None or button is None or slider is None:
            return
        if timer.isActive():
            timer.stop()
            button.setText("Play Replay")
            return
        timer.start(220)
        button.setText("Pause Replay")

    def _advance_trade_review_playback(self, window):
        slider = getattr(window, "_trade_review_slider", None)
        timer = getattr(window, "_trade_review_timer", None)
        button = getattr(window, "_trade_review_play_btn", None)
        if slider is None or timer is None:
            return
        if slider.value() >= slider.maximum():
            timer.stop()
            if button is not None:
                button.setText("Play Replay")
            return
        slider.setValue(slider.value() + 1)

    def _open_trade_review_window(self, trade):
        window = self._get_or_create_tool_window(
            "trade_review",
            "Trade Review",
            width=1120,
            height=760,
        )

        if getattr(window, "_trade_review_curve", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            summary = QLabel("Loading trade review context.")
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
            )
            layout.addWidget(summary)

            controls = QHBoxLayout()
            play_btn = QPushButton("Play Replay")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(0)
            controls.addWidget(play_btn)
            controls.addWidget(slider, 1)
            layout.addLayout(controls)

            plot = pg.PlotWidget()
            self._style_performance_plot(plot, left_label="Price")
            plot.setMinimumHeight(340)
            curve = plot.plot(pen=pg.mkPen("#4ea1ff", width=2.2))
            marker = pg.ScatterPlotItem(size=11, brush=pg.mkBrush("#ffb84d"), pen=pg.mkPen("#ffd37a", width=1.5))
            plot.addItem(marker)
            vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ffb84d", width=1.2, style=Qt.PenStyle.DashLine))
            hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#49d17d", width=1.0, style=Qt.PenStyle.DotLine))
            plot.addItem(vline)
            plot.addItem(hline)
            layout.addWidget(plot)

            details = QTextBrowser()
            details.setStyleSheet(
                "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; border-radius: 12px; padding: 12px; }"
            )
            layout.addWidget(details, 1)

            journal_card = QFrame()
            journal_card.setStyleSheet(
                "QFrame { background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; }"
                "QLabel { color: #d8e6ff; }"
                "QLineEdit, QTextEdit { background-color: #09111f; color: #d8e6ff; border: 1px solid #20324d; border-radius: 8px; padding: 6px; }"
            )
            journal_layout = QVBoxLayout(journal_card)
            journal_layout.setContentsMargins(12, 12, 12, 12)
            journal_layout.setSpacing(8)

            journal_title = QLabel("Trade Journal")
            journal_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f4f8ff;")
            journal_layout.addWidget(journal_title)

            journal_form = QFormLayout()
            reason_edit = QTextEdit()
            reason_edit.setFixedHeight(60)
            setup_edit = QTextEdit()
            setup_edit.setFixedHeight(60)
            outcome_edit = QTextEdit()
            outcome_edit.setFixedHeight(50)
            lessons_edit = QTextEdit()
            lessons_edit.setFixedHeight(72)
            stop_loss_input = QLineEdit()
            take_profit_input = QLineEdit()
            journal_form.addRow("Entry Reason", reason_edit)
            journal_form.addRow("Setup", setup_edit)
            journal_form.addRow("Stop Loss", stop_loss_input)
            journal_form.addRow("Take Profit", take_profit_input)
            journal_form.addRow("Outcome", outcome_edit)
            journal_form.addRow("Lessons", lessons_edit)
            journal_layout.addLayout(journal_form)

            journal_controls = QHBoxLayout()
            journal_status = QLabel("Add the setup, TP/SL, outcome, and lessons for this trade.")
            journal_status.setWordWrap(True)
            journal_status.setStyleSheet("color: #9eb4d2;")
            save_journal_btn = QPushButton("Save Journal")
            save_journal_btn.clicked.connect(lambda: self._save_trade_review_journal(window))
            open_review_btn = QPushButton("Open Weekly/Monthly Review")
            open_review_btn.clicked.connect(self._open_trade_journal_review_window)
            journal_controls.addWidget(journal_status, 1)
            journal_controls.addWidget(save_journal_btn)
            journal_controls.addWidget(open_review_btn)
            journal_layout.addLayout(journal_controls)

            layout.addWidget(journal_card)

            window.setCentralWidget(container)
            window._trade_review_summary = summary
            window._trade_review_slider = slider
            window._trade_review_play_btn = play_btn
            window._trade_review_curve = curve
            window._trade_review_marker = marker
            window._trade_review_vline = vline
            window._trade_review_hline = hline
            window._trade_review_details = details
            window._trade_review_reason_edit = reason_edit
            window._trade_review_setup_edit = setup_edit
            window._trade_review_outcome_edit = outcome_edit
            window._trade_review_lessons_edit = lessons_edit
            window._trade_review_stop_loss_input = stop_loss_input
            window._trade_review_take_profit_input = take_profit_input
            window._trade_review_journal_status = journal_status
            window._trade_review_save_btn = save_journal_btn
            window._trade_review_state = {}

            timer = QTimer(window)
            timer.timeout.connect(lambda: self._advance_trade_review_playback(window))
            window._trade_review_timer = timer
            play_btn.clicked.connect(lambda: self._toggle_trade_review_playback(window))
            slider.valueChanged.connect(lambda *_: self._render_trade_review_window(window))

        timer = getattr(window, "_trade_review_timer", None)
        button = getattr(window, "_trade_review_play_btn", None)
        if timer is not None and timer.isActive():
            timer.stop()
        if button is not None:
            button.setText("Play Replay")

        try:
            window._trade_review_task = asyncio.get_event_loop().create_task(
                self._load_trade_review_async(window, trade)
            )
        except Exception as exc:
            self.logger.debug("Unable to schedule trade review load: %s", exc)
            window._trade_review_state = {"trade": dict(trade or {}), "candles": [], "trade_index": 0}
            self._populate_trade_review_journal_fields(window)
            self._render_trade_review_window(window)

        window.show()
        window.raise_()
        window.activateWindow()

    def _open_trade_review_from_journal(self, window):
        trade = self._trade_review_selected_row(window)
        if not isinstance(trade, dict):
            QMessageBox.information(self, "Trade Review", "Select a closed trade first.")
            return
        self._open_trade_review_window(trade)

    def _trade_datetime_utc(self, value):
        timestamp_ms = self._trade_timestamp_ms(value)
        if timestamp_ms is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        except Exception :
            return None

    def _journal_review_bounds(self, mode):
        now = datetime.now(timezone.utc)
        label = str(mode or "Weekly").strip().title()
        if label == "Monthly":
            current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_anchor = current_start - timedelta(days=1)
            previous_start = previous_anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            label = "Weekly"
            current_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            previous_start = current_start - timedelta(days=7)
        return label, previous_start, current_start, now

    def _rows_for_journal_period(self, rows, start_dt, end_dt):
        selected = []
        for row in rows or []:
            trade_dt = self._trade_datetime_utc(row.get("timestamp"))
            if trade_dt is None:
                continue
            if start_dt <= trade_dt < end_dt:
                selected.append(row)
        return selected

    def _journal_review_analysis_rows(self, rows):
        analysis_rows = []
        for row in rows or []:
            status = str(row.get("status") or "").strip().lower()
            pnl = self._safe_float(row.get("pnl"))
            if status in {"filled", "closed"} or pnl is not None:
                analysis_rows.append(row)
        return analysis_rows

    def _summarize_journal_rows(self, rows):
        trades = list(rows or [])
        pnl_values = [self._safe_float(row.get("pnl")) for row in trades]
        pnl_values = [value for value in pnl_values if value is not None]
        fee_values = [self._safe_float(row.get("fee")) for row in trades]
        fee_values = [value for value in fee_values if value is not None]
        slippage_values = [self._safe_float(row.get("slippage_bps")) for row in trades]
        slippage_values = [value for value in slippage_values if value is not None]
        confidence_values = [self._safe_float(row.get("confidence")) for row in trades]
        confidence_values = [value for value in confidence_values if value is not None]

        wins = [value for value in pnl_values if value > 0]
        losses = [value for value in pnl_values if value < 0]
        complete_entries = 0
        strategy_map = {}
        symbol_loss_counts = {}

        for row in trades:
            if all(str(row.get(field) or "").strip() for field in ("reason", "setup", "outcome", "lessons")):
                complete_entries += 1
            strategy_name = str(row.get("strategy_name") or "Unlabeled").strip() or "Unlabeled"
            bucket = strategy_map.setdefault(strategy_name, {"rows": [], "pnl": [], "wins": 0, "fees": 0.0})
            bucket["rows"].append(row)
            pnl = self._safe_float(row.get("pnl"))
            if pnl is not None:
                bucket["pnl"].append(pnl)
                if pnl > 0:
                    bucket["wins"] += 1
                if pnl < 0:
                    symbol = str(row.get("symbol") or "").strip() or "Unknown"
                    symbol_loss_counts[symbol] = symbol_loss_counts.get(symbol, 0) + 1
            fee = self._safe_float(row.get("fee"), 0.0)
            bucket["fees"] += fee or 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        strategy_rows = []
        for strategy_name, bucket in strategy_map.items():
            pnl_list = bucket["pnl"]
            strategy_rows.append(
                {
                    "strategy": strategy_name,
                    "trades": len(bucket["rows"]),
                    "win_rate": (bucket["wins"] / len(pnl_list)) if pnl_list else None,
                    "net_pnl": sum(pnl_list) if pnl_list else 0.0,
                    "avg_pnl": (sum(pnl_list) / len(pnl_list)) if pnl_list else None,
                    "journal_coverage": (
                        sum(
                            1 for item in bucket["rows"]
                            if all(str(item.get(field) or "").strip() for field in ("reason", "setup", "outcome", "lessons"))
                        ) / len(bucket["rows"])
                    ) if bucket["rows"] else None,
                    "fees": bucket["fees"],
                }
            )
        strategy_rows.sort(key=lambda item: (item.get("net_pnl") is None, -(item.get("net_pnl") or 0.0), item["strategy"]))

        return {
            "trade_count": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "net_pnl": sum(pnl_values) if pnl_values else 0.0,
            "avg_pnl": (sum(pnl_values) / len(pnl_values)) if pnl_values else None,
            "win_rate": (len(wins) / len(pnl_values)) if pnl_values else None,
            "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
            "fees": sum(fee_values) if fee_values else 0.0,
            "avg_slippage": (sum(slippage_values) / len(slippage_values)) if slippage_values else None,
            "avg_confidence": (sum(confidence_values) / len(confidence_values)) if confidence_values else None,
            "journal_coverage": (complete_entries / len(trades)) if trades else None,
            "strategy_rows": strategy_rows,
            "symbol_loss_counts": symbol_loss_counts,
        }

    def _journal_review_mistakes(self, rows, stats):
        issues = []
        missing_setup = sum(1 for row in rows if not str(row.get("setup") or "").strip())
        missing_lessons = sum(
            1 for row in rows
            if self._safe_float(row.get("pnl")) is not None and self._safe_float(row.get("pnl")) < 0
            and not str(row.get("lessons") or "").strip()
        )
        missing_risk = sum(
            1 for row in rows
            if str(row.get("status") or "").strip().lower() in {"filled", "closed"}
            and (self._safe_float(row.get("stop_loss")) is None or self._safe_float(row.get("take_profit")) is None)
        )
        if missing_setup:
            issues.append(f"{missing_setup} trade(s) are missing setup notes, which weakens pattern review.")
        if missing_lessons:
            issues.append(f"{missing_lessons} losing trade(s) have no lessons recorded yet.")
        if missing_risk:
            issues.append(f"{missing_risk} filled trade(s) are missing either stop loss or take profit documentation.")
        avg_slippage = stats.get("avg_slippage")
        if avg_slippage is not None and avg_slippage > 8:
            issues.append(f"Average slippage is elevated at {avg_slippage:.2f} bps. Execution quality may be hurting edge.")
        recurring_symbols = [symbol for symbol, count in (stats.get("symbol_loss_counts") or {}).items() if count >= 3]
        if recurring_symbols:
            issues.append(f"Repeated losses clustered on {', '.join(sorted(recurring_symbols)[:4])}. Review symbol selection and session quality.")
        if not issues:
            issues.append("No obvious discipline issue stands out in this period. Keep journaling every trade to preserve that visibility.")
        return issues

    def _journal_review_edge_decay(self, current_stats, previous_stats):
        notes = []
        current_trades = int(current_stats.get("trade_count") or 0)
        previous_trades = int(previous_stats.get("trade_count") or 0)
        if previous_trades <= 0:
            return ["No prior period data was available, so edge decay cannot be measured yet."]

        current_win = current_stats.get("win_rate")
        previous_win = previous_stats.get("win_rate")
        if current_win is not None and previous_win is not None and current_win < previous_win - 0.10:
            notes.append(
                f"Win rate cooled from {previous_win * 100.0:.1f}% to {current_win * 100.0:.1f}%."
            )
        current_avg = current_stats.get("avg_pnl")
        previous_avg = previous_stats.get("avg_pnl")
        if current_avg is not None and previous_avg not in (None, 0):
            if current_avg < previous_avg * 0.7:
                notes.append(
                    f"Average trade expectancy slipped from {self._format_currency(previous_avg)} to {self._format_currency(current_avg)}."
                )
        current_pf = current_stats.get("profit_factor")
        previous_pf = previous_stats.get("profit_factor")
        if current_pf is not None and previous_pf not in (None, 0):
            if current_pf < previous_pf * 0.75:
                notes.append(f"Profit factor softened from {previous_pf:.2f} to {current_pf:.2f}.")
        if current_trades > previous_trades * 1.5 and (current_stats.get("net_pnl") or 0.0) < (previous_stats.get("net_pnl") or 0.0):
            notes.append("Trade count increased materially while returns weakened. That is a classic overtrading signal.")

        previous_by_strategy = {
            row["strategy"]: row for row in previous_stats.get("strategy_rows", [])
        }
        for row in current_stats.get("strategy_rows", []):
            previous_row = previous_by_strategy.get(row["strategy"])
            if not previous_row:
                continue
            if int(row.get("trades") or 0) < 3 or int(previous_row.get("trades") or 0) < 3:
                continue
            current_win_rate = row.get("win_rate")
            previous_win_rate = previous_row.get("win_rate")
            if current_win_rate is not None and previous_win_rate is not None and current_win_rate < previous_win_rate - 0.15:
                notes.append(
                    f"{row['strategy']} cooled from {previous_win_rate * 100.0:.1f}% to {current_win_rate * 100.0:.1f}% win rate."
                )
        if not notes:
            notes.append("No strong edge decay signal stands out versus the prior period.")
        return notes

    def _journal_review_overview_html(self, mode, start_dt, end_dt, current_stats, previous_stats, mistakes, edge_decay):
        period_label = f"{mode} review from {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"
        overview_lines = [
            f"<h3>{html.escape(period_label)}</h3>",
            "<p><b>Focus:</b> combine performance metrics with journaling quality so the review shows what happened and why.</p>",
            "<p>"
            f"<b>Current net PnL:</b> {html.escape(self._format_currency(current_stats.get('net_pnl')))} | "
            f"<b>Win rate:</b> {html.escape(self._format_percent_text(current_stats.get('win_rate')))} | "
            f"<b>Journal coverage:</b> {html.escape(self._format_percent_text(current_stats.get('journal_coverage')))}"
            "</p>",
            "<h4>Mistakes To Review</h4><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in mistakes) + "</ul>",
            "<h4>Edge Decay Check</h4><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in edge_decay) + "</ul>",
        ]
        if int(previous_stats.get("trade_count") or 0) > 0:
            overview_lines.append(
                "<p>"
                f"<b>Previous period net PnL:</b> {html.escape(self._format_currency(previous_stats.get('net_pnl')))} | "
                f"<b>Previous win rate:</b> {html.escape(self._format_percent_text(previous_stats.get('win_rate')))}"
                "</p>"
            )
        return "".join(overview_lines)

    def _populate_journal_review_strategy_table(self, table, rows):
        if table is None:
            return
        table.setRowCount(len(rows or []))
        for row_index, row in enumerate(rows or []):
            values = [
                row.get("strategy", ""),
                row.get("trades", ""),
                self._format_percent_text(row.get("win_rate")),
                self._format_currency(row.get("net_pnl")),
                self._format_currency(row.get("avg_pnl")),
                self._format_percent_text(row.get("journal_coverage")),
                self._format_currency(row.get("fees")),
            ]
            for column, value in enumerate(values):
                table.setItem(row_index, column, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _schedule_trade_journal_review_refresh(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        task = getattr(window, "_journal_review_task", None)
        if task is not None and not task.done():
            return
        try:
            window._journal_review_task = asyncio.get_event_loop().create_task(
                self._refresh_trade_journal_review_async(window)
            )
        except Exception as exc:
            self.logger.debug("Unable to schedule journal review refresh: %s", exc)

    async def _refresh_trade_journal_review_async(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        controller = self.controller
        period_picker = getattr(window, "_journal_review_period_picker", None)
        summary = getattr(window, "_journal_review_summary", None)
        metrics = getattr(window, "_journal_review_metrics", {}) or {}
        overview = getattr(window, "_journal_review_overview", None)
        strategy_table = getattr(window, "_journal_review_strategy_table", None)
        if (
            period_picker is None
            or summary is None
            or overview is None
            or strategy_table is None
            or not self._is_qt_object_alive(period_picker)
            or not self._is_qt_object_alive(summary)
            or not self._is_qt_object_alive(overview)
            or not self._is_qt_object_alive(strategy_table)
        ):
            return

        try:
            rows = await controller.fetch_trade_history(limit=700)
        except Exception as exc:
            rows = []
            self.logger.debug("Journal review refresh failed: %s", exc)
        if (
            window is None
            or not self._is_qt_object_alive(window)
            or not self._is_qt_object_alive(period_picker)
            or not self._is_qt_object_alive(summary)
            or not self._is_qt_object_alive(overview)
            or not self._is_qt_object_alive(strategy_table)
        ):
            return

        mode, previous_start, current_start, now = self._journal_review_bounds(period_picker.currentText())
        current_rows = self._journal_review_analysis_rows(self._rows_for_journal_period(rows, current_start, now))
        previous_rows = self._journal_review_analysis_rows(self._rows_for_journal_period(rows, previous_start, current_start))
        current_stats = self._summarize_journal_rows(current_rows)
        previous_stats = self._summarize_journal_rows(previous_rows)
        mistakes = self._journal_review_mistakes(current_rows, current_stats)
        edge_decay = self._journal_review_edge_decay(current_stats, previous_stats)

        summary.setText(
            f"{mode} review loaded with {current_stats.get('trade_count', 0)} closed trade(s). "
            "Use this to spot discipline issues, execution drag, and strategy fatigue."
        )

        metric_values = {
            "Trades": str(current_stats.get("trade_count", 0)),
            "Net PnL": self._format_currency(current_stats.get("net_pnl")),
            "Win Rate": self._format_percent_text(current_stats.get("win_rate")),
            "Avg Trade": self._format_currency(current_stats.get("avg_pnl")),
            "Profit Factor": "-" if current_stats.get("profit_factor") is None else f"{float(current_stats.get('profit_factor')):.2f}",
            "Fees": self._format_currency(current_stats.get("fees")),
            "Avg Slippage": "-" if current_stats.get("avg_slippage") is None else f"{float(current_stats.get('avg_slippage')):.2f} bps",
            "Journal Coverage": self._format_percent_text(current_stats.get("journal_coverage")),
        }
        for key, label in metrics.items():
            if label is not None:
                label.setText(metric_values.get(key, "-"))

        overview.setHtml(
            self._journal_review_overview_html(
                mode,
                current_start,
                now,
                current_stats,
                previous_stats,
                mistakes,
                edge_decay,
            )
        )
        self._populate_journal_review_strategy_table(strategy_table, current_stats.get("strategy_rows"))

    def _open_trade_journal_review_window(self):
        window = self._get_or_create_tool_window(
            "trade_journal_review",
            "Journal Review",
            width=1180,
            height=760,
        )

        if getattr(window, "_journal_review_summary", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            summary = QLabel("Loading weekly/monthly journal review.")
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
                "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
            )
            layout.addWidget(summary)

            controls = QHBoxLayout()
            period_picker = QComboBox()
            period_picker.addItems(["Weekly", "Monthly"])
            refresh_btn = QPushButton("Refresh Review")
            refresh_btn.clicked.connect(lambda: self._schedule_trade_journal_review_refresh(window))
            controls.addWidget(QLabel("Review Period"))
            controls.addWidget(period_picker)
            controls.addWidget(refresh_btn)
            controls.addStretch()
            layout.addLayout(controls)

            metrics_widget = QWidget()
            metrics_layout = QGridLayout(metrics_widget)
            metrics_layout.setContentsMargins(0, 0, 0, 0)
            metrics_layout.setHorizontalSpacing(10)
            metrics_layout.setVerticalSpacing(10)
            metric_labels = {}
            metric_keys = ["Trades", "Net PnL", "Win Rate", "Avg Trade", "Profit Factor", "Fees", "Avg Slippage", "Journal Coverage"]
            for index, key in enumerate(metric_keys):
                card = QFrame()
                card.setStyleSheet(
                    "QFrame { background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; }"
                )
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(12, 12, 12, 12)
                title = QLabel(key)
                title.setStyleSheet("color: #8ca8cc; font-size: 12px;")
                value = QLabel("-")
                value.setStyleSheet("color: #f4f8ff; font-size: 17px; font-weight: 700;")
                card_layout.addWidget(title)
                card_layout.addWidget(value)
                metrics_layout.addWidget(card, index // 4, index % 4)
                metric_labels[key] = value
            layout.addWidget(metrics_widget)

            overview = QTextBrowser()
            overview.setStyleSheet(
                "QTextBrowser { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; border-radius: 12px; padding: 12px; }"
            )
            layout.addWidget(overview)

            strategy_table = QTableWidget()
            strategy_table.setColumnCount(7)
            strategy_table.setHorizontalHeaderLabels(
                ["Strategy", "Trades", "Win Rate", "Net PnL", "Avg Trade", "Journal Coverage", "Fees"]
            )
            strategy_table.setStyleSheet(
                "QTableWidget { background-color: #101a2d; color: #d8e6ff; border: 1px solid #20324d; "
                "border-radius: 12px; gridline-color: #20324d; }"
            )
            layout.addWidget(strategy_table)

            window.setCentralWidget(container)
            window._journal_review_summary = summary
            window._journal_review_period_picker = period_picker
            window._journal_review_metrics = metric_labels
            window._journal_review_overview = overview
            window._journal_review_strategy_table = strategy_table

            period_picker.currentTextChanged.connect(lambda *_: self._schedule_trade_journal_review_refresh(window))

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._schedule_trade_journal_review_refresh(window))
            sync_timer.start(7000)
            window._journal_review_timer = sync_timer

        self._schedule_trade_journal_review_refresh(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _refresh_health_window(self, window):
        controller = self.controller
        summary = getattr(window, "_health_summary", None)
        checks_table = getattr(window, "_health_checks_table", None)
        capabilities_browser = getattr(window, "_capabilities_browser", None)
        readiness_browser = getattr(window, "_health_readiness_browser", None)
        data_health_browser = getattr(window, "_health_data_health_browser", None)
        decision_browser = getattr(window, "_health_decision_browser", None)
        strategy_browser = getattr(window, "_health_strategy_browser", None)
        if summary is None or checks_table is None or capabilities_browser is None:
            return

        report = controller.get_health_check_report() if hasattr(controller, "get_health_check_report") else []
        monitor_symbol = self._current_chart_symbol() or getattr(self, "symbol", None)
        timeframe_value = str(getattr(self, "current_timeframe", "") or getattr(controller, "time_frame", "1h") or "1h").strip() or "1h"
        readiness_report = {}
        if hasattr(controller, "get_live_readiness_report"):
            try:
                readiness_report = dict(
                    controller.get_live_readiness_report(
                        symbol=monitor_symbol,
                        timeframe=timeframe_value,
                    )
                    or {}
                )
            except Exception:
                readiness_report = {}
        data_health = dict(readiness_report.get("market_data") or {})
        if not data_health and hasattr(controller, "get_market_data_health_snapshot"):
            try:
                data_health = dict(
                    controller.get_market_data_health_snapshot(
                        symbol=monitor_symbol,
                        timeframe=timeframe_value,
                    )
                    or {}
                )
            except Exception:
                data_health = {}
        capability_profile = {}
        if hasattr(controller, "get_broker_capability_profile"):
            try:
                capability_profile = dict(controller.get_broker_capability_profile() or {})
            except Exception:
                capability_profile = {}
        decision_timeline = {}
        if hasattr(controller, "decision_timeline_snapshot"):
            try:
                decision_timeline = dict(controller.decision_timeline_snapshot(symbol=monitor_symbol, limit=8) or {})
            except Exception:
                decision_timeline = {}
        feedback_summary = {}
        if hasattr(controller, "strategy_feedback_summary"):
            try:
                feedback_summary = dict(controller.strategy_feedback_summary(limit=200) or {})
            except Exception:
                feedback_summary = {}
        portfolio_symbol = str(readiness_report.get("symbol") or monitor_symbol or "").strip()
        portfolio_rows = []
        if portfolio_symbol and hasattr(controller, "strategy_portfolio_profile_for_symbol"):
            try:
                portfolio_rows = list(controller.strategy_portfolio_profile_for_symbol(portfolio_symbol) or [])
            except Exception:
                portfolio_rows = []

        summary.setText(
            f"Startup health: {getattr(controller, 'get_health_check_summary', lambda: 'Not run')()} | "
            f"Mode: {'LIVE' if getattr(controller, 'is_live_mode', lambda: False)() else 'PAPER'} | "
            f"Account: {getattr(controller, 'current_account_label', lambda: 'Not set')()} | "
            f"Readiness: {str(readiness_report.get('summary') or 'Not checked').strip() or 'Not checked'}"
        )

        checks_table.setRowCount(len(report))
        for row_index, item in enumerate(report):
            checks_table.setItem(row_index, 0, QTableWidgetItem(str(item.get("name", ""))))
            checks_table.setItem(row_index, 1, QTableWidgetItem(str(item.get("status", "")).upper()))
            checks_table.setItem(row_index, 2, QTableWidgetItem(str(item.get("detail", ""))))
        checks_table.resizeColumnsToContents()
        checks_table.horizontalHeader().setStretchLastSection(True)

        capabilities = controller.get_broker_capabilities() if hasattr(controller, "get_broker_capabilities") else {}
        capability_lines = [
            "Broker profile",
            f"Summary: {str(capability_profile.get('summary') or '-').strip() or '-'}",
            f"Market data provider: {str(capability_profile.get('market_data_provider') or '-').strip() or '-'}",
            f"Swap provider: {str(capability_profile.get('swap_provider') or '-').strip() or '-'}",
            f"Live order ready: {'Yes' if capability_profile.get('live_order_ready') else 'No'}",
            "",
            "Capabilities",
        ]
        for key, value in capabilities.items():
            label = str(key).replace("_", " ").title()
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value) if value else "-"
            else:
                rendered = "Yes" if value else "No"
            capability_lines.append(f"{label}: {rendered}")
        capabilities_browser.setPlainText("\n".join(capability_lines))

        if readiness_browser is not None:
            readiness_lines = [str(readiness_report.get("summary") or "Readiness data is not available yet.").strip()]
            for item in list(readiness_report.get("checks") or []):
                readiness_lines.append(
                    f"[{str(item.get('status') or '').upper() or 'INFO'}] "
                    f"{str(item.get('name') or '').strip()}: {str(item.get('detail') or '').strip()}"
                )
            readiness_browser.setPlainText("\n".join(readiness_lines))

        if data_health_browser is not None:
            quote = dict(data_health.get("quote") or {})
            candles = dict(data_health.get("candles") or {})
            orderbook = dict(data_health.get("orderbook") or {})
            data_lines = [
                str(data_health.get("summary") or "Market data health is not available yet.").strip(),
                f"Stream status: {str(data_health.get('stream_status') or '-').strip() or '-'}",
                f"Quote feed: {str(quote.get('age_label') or 'unknown').strip() or 'unknown'} old",
                f"Candle feed: {str(candles.get('age_label') or 'unknown').strip() or 'unknown'} old for {str(candles.get('timeframe') or timeframe_value).strip() or timeframe_value}",
                "Orderbook feed: not supported" if orderbook.get("supported") is False else (
                    f"Orderbook feed: {str(orderbook.get('age_label') or 'unknown').strip() or 'unknown'} old"
                ),
            ]
            data_health_browser.setPlainText("\n".join(data_lines))

        if decision_browser is not None:
            decision_lines = [str(decision_timeline.get("summary") or "No decision timeline is available yet.").strip()]
            for item in list(decision_timeline.get("steps") or [])[-8:]:
                timestamp_label = str(item.get("timestamp_label") or "").strip()
                agent_name = str(item.get("agent_name") or item.get("stage") or "runtime").strip()
                status = str(item.get("status") or "pending").strip().upper()
                reason = str(item.get("reason") or "").strip()
                line = f"{timestamp_label or '-'} | {agent_name} | {status}"
                if reason:
                    line = f"{line} | {reason}"
                decision_lines.append(line)
            decision_browser.setPlainText("\n".join(decision_lines))

        if strategy_browser is not None:
            strategy_lines = [
                str(feedback_summary.get("summary") or "No live strategy feedback is available yet.").strip()
            ]
            if portfolio_rows:
                strategy_lines.append("")
                strategy_lines.append(f"Managed portfolio for {portfolio_symbol}:")
                for row in list(portfolio_rows or [])[:6]:
                    strategy_lines.append(
                        (
                            f"{float(row.get('portfolio_weight', 0.0) or 0.0) * 100:.1f}% "
                            f"{str(row.get('strategy_name') or '-').strip()} "
                            f"{str(row.get('timeframe') or timeframe_value).strip()} | "
                            f"adaptive {float(row.get('adaptive_weight', 1.0) or 1.0):.2f} | "
                            f"live {float(row.get('feedback_multiplier', 1.0) or 1.0):.2f}x"
                        )
                    )
                    strategy_lines.append(str(row.get("management_reason") or "").strip())
            improving = list(feedback_summary.get("improving") or [])
            degrading = list(feedback_summary.get("degrading") or [])
            if improving:
                strategy_lines.append("")
                strategy_lines.append("Improving profiles:")
                for row in improving[:3]:
                    strategy_lines.append(
                        f"{str(row.get('strategy_name') or '-').strip()} {str(row.get('symbol') or '-').strip()} "
                        f"{str(row.get('timeframe') or '-').strip()} | {float(row.get('feedback_multiplier', 1.0) or 1.0):.2f}x"
                    )
            if degrading:
                strategy_lines.append("")
                strategy_lines.append("Needs attention:")
                for row in degrading[:3]:
                    strategy_lines.append(
                        f"{str(row.get('strategy_name') or '-').strip()} {str(row.get('symbol') or '-').strip()} "
                        f"{str(row.get('timeframe') or '-').strip()} | {float(row.get('feedback_multiplier', 1.0) or 1.0):.2f}x"
                    )
            strategy_browser.setPlainText("\n".join(strategy_lines))

    def _export_diagnostics_bundle(self):
        default_dir = str(self.settings.value("diagnostics/export_dir", "logs") or "logs")
        destination = QFileDialog.getExistingDirectory(self, "Export Diagnostics Bundle", default_dir)
        if not destination:
            return None
        try:
            bundle_path = export_diagnostics_bundle(self, destination)
        except Exception as exc:
            self.logger.exception("Diagnostics bundle export failed")
            if hasattr(self, "_push_notification"):
                self._push_notification(
                    "Diagnostics export failed",
                    str(exc),
                    level="ERROR",
                    source="diagnostics",
                    dedupe_seconds=5.0,
                )
            QMessageBox.warning(self, "Export Diagnostics", f"Diagnostics bundle export failed:\n{exc}")
            return None

        self.settings.setValue("diagnostics/export_dir", str(Path(destination)))
        if getattr(self, "system_console", None) is not None:
            self.system_console.log(f"Diagnostics bundle exported to {bundle_path}", "INFO")
        if hasattr(self, "_push_notification"):
            self._push_notification(
                "Diagnostics bundle exported",
                f"Saved diagnostics bundle to {bundle_path}.",
                level="INFO",
                source="diagnostics",
                dedupe_seconds=2.0,
            )
        QMessageBox.information(self, "Export Diagnostics", f"Diagnostics bundle exported to:\n{bundle_path}")
        return bundle_path

    def _open_system_health_window(self):
        window = self._get_or_create_tool_window(
            "system_health",
            "System Health",
            width=980,
            height=620,
        )

        if getattr(window, "_health_checks_table", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            hero, _, _, _ = self._build_tool_window_hero(
                "System Health",
                "Monitor startup checks, live readiness, broker capabilities, and the latest decision path from one control surface.",
                meta="Diagnostics | Readiness | Broker profile | Strategy feedback",
            )
            layout.addWidget(hero)

            summary = QLabel("Running startup health checks.")
            summary.setWordWrap(True)
            summary.setObjectName("tool_window_summary_card")
            layout.addWidget(summary)

            controls = QHBoxLayout()
            rerun_btn = QPushButton("Run Checks")
            rerun_btn.setStyleSheet(self._action_button_style())
            rerun_btn.clicked.connect(
                lambda: (
                    self.controller._create_task(self.controller.run_startup_health_check(), "manual_health_check")
                    if hasattr(self.controller, "run_startup_health_check") and hasattr(self.controller, "_create_task")
                    else None
                )
            )
            export_btn = QPushButton("Export Diagnostics")
            export_btn.setStyleSheet(self._action_button_style())
            export_btn.clicked.connect(self._export_diagnostics_bundle)
            logs_btn = QPushButton("Open Logs")
            logs_btn.setStyleSheet(self._action_button_style())
            logs_btn.clicked.connect(self._open_logs)
            controls.addWidget(rerun_btn)
            controls.addWidget(export_btn)
            controls.addWidget(logs_btn)
            controls.addStretch()
            layout.addLayout(controls)

            tabs = QTabWidget()
            self._apply_workspace_tab_chrome(tabs)
            layout.addWidget(tabs)

            checks = QTableWidget()
            checks.setColumnCount(3)
            checks.setHorizontalHeaderLabels(["Check", "Status", "Detail"])
            self._configure_monitor_table(checks)
            checks_page = QWidget()
            checks_layout = QVBoxLayout(checks_page)
            checks_layout.setContentsMargins(0, 0, 0, 0)
            checks_layout.addWidget(checks)
            tabs.addTab(checks_page, "Startup Checks")

            def _section_title(text):
                return self._build_tool_window_section_label(text)

            def _section_browser():
                browser = QTextBrowser()
                browser.setMinimumHeight(120)
                browser.setStyleSheet(self._tool_window_text_browser_style())
                return browser

            mission_page = QWidget()
            mission_layout = QVBoxLayout(mission_page)
            mission_layout.setContentsMargins(0, 0, 0, 0)
            mission_layout.setSpacing(10)

            readiness_browser = _section_browser()
            mission_layout.addWidget(_section_title("Live Readiness"))
            mission_layout.addWidget(readiness_browser)

            data_health_browser = _section_browser()
            mission_layout.addWidget(_section_title("Market Data Health"))
            mission_layout.addWidget(data_health_browser)

            decision_browser = _section_browser()
            mission_layout.addWidget(_section_title("Decision Timeline"))
            mission_layout.addWidget(decision_browser)

            strategy_browser = _section_browser()
            mission_layout.addWidget(_section_title("Managed Strategy Portfolio"))
            mission_layout.addWidget(strategy_browser)
            tabs.addTab(mission_page, "Mission Control")

            capabilities_browser = QTextBrowser()
            capabilities_browser.setStyleSheet(self._tool_window_text_browser_style())
            capabilities_page = QWidget()
            capabilities_layout = QVBoxLayout(capabilities_page)
            capabilities_layout.setContentsMargins(0, 0, 0, 0)
            capabilities_layout.addWidget(capabilities_browser)
            tabs.addTab(capabilities_page, "Broker Profile")

            window.setCentralWidget(container)
            window._health_summary = summary
            window._health_rerun_btn = rerun_btn
            window._health_export_btn = export_btn
            window._health_checks_table = checks
            window._capabilities_browser = capabilities_browser
            window._health_tabs = tabs
            window._health_readiness_browser = readiness_browser
            window._health_data_health_browser = data_health_browser
            window._health_decision_browser = decision_browser
            window._health_strategy_browser = strategy_browser

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._refresh_health_window(window))
            sync_timer.start(3000)
            window._health_timer = sync_timer

        if hasattr(self.controller, "run_startup_health_check") and hasattr(self.controller, "_create_task"):
            self.controller._create_task(self.controller.run_startup_health_check(), "manual_health_check")
        self._refresh_health_window(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _performance_series(self):
        perf = getattr(self.controller, "performance_engine", None)
        if perf is None:
            return []

        for attr in ("equity_history", "equity_curve"):
            series = getattr(perf, attr, None)
            if isinstance(series, list):
                return series

        return []

    def _performance_time_series(self):
        perf = getattr(self.controller, "performance_engine", None)
        if perf is None:
            return []

        for attr in ("equity_time_history", "equity_timestamps"):
            series = getattr(perf, attr, None)
            if isinstance(series, list):
                return series

        return []

    def _format_performance_value(self, value, percent=False):
        if value is None:
            return "-"

        try:
            numeric = float(value)
        except Exception as ex:
            self.logger.debug(f"Performance value formatting error for {value}: {ex}")
            return str(value)

        if percent:
            return f"{numeric * 100:.2f}%"
        return f"{numeric:.4f}"

    def _refresh_performance_window(self, window):
        widgets = getattr(window, "_performance_widgets", None)
        if widgets is None:
            return
        self._populate_performance_view(widgets, self._performance_snapshot())

    def _open_risk_settings(self):
        self._show_risk_settings_window()

    def save_settings(self):
        dialog = QDialog(self)
        save_btn = QPushButton("Save")
        layout = QVBoxLayout()
        max_portfolio_risk = QDoubleSpinBox()
        max_portfolio_risk.setRange(0, 1)
        max_portfolio_risk.setSingleStep(0.01)
        max_risk_per_trade = QDoubleSpinBox()
        max_risk_per_trade.setRange(0, 5)
        max_risk_per_trade.setSingleStep(0.01)
        max_position_size = QDoubleSpinBox()
        max_position_size.setRange(0, 5)
        max_position_size.setSingleStep(0.01)
        max_gross_exposure = QDoubleSpinBox()
        max_gross_exposure.setRange(0, 5)
        max_gross_exposure.setSingleStep(0.01)

        try:

            self.controller.risk_engine.max_portfolio_risk = max_portfolio_risk.value()
            self.controller.risk_engine.max_risk_per_trade = max_risk_per_trade.value()
            self.controller.risk_engine.max_position_size_pct = max_position_size.value()
            self.controller.risk_engine.max_gross_exposure_pct = max_gross_exposure.value()

            QMessageBox.information(
                dialog,
                "Risk Settings",
                "Risk settings updated successfully."
            )

            dialog.close()

        except Exception as e:

            self.logger.error(f"Risk settings error: {e}")

        save_btn.clicked.connect(self.save_settings)

        layout.addWidget(save_btn)

        dialog.setLayout(layout)

        dialog.exec()

    def _show_portfolio_exposure(self):
        try:
            self._show_portfolio_exposure_window()
        except Exception as e:
            self.logger.error(f"Portfolio exposure error: {e}")

    async def _reload_chart_data(self, symbol, timeframe):

        try:

            buffers = self.controller.candle_buffers.get(symbol)

            if not buffers:
                return

            df = buffers.get(timeframe)

            if df is None:
                return

            self._update_chart(symbol, df)

        except Exception as e:

            self.logger.error(f"Timeframe reload failed: {e}")



    def _format_balance_text(self, balance):
        """Render balances like: XLM:100, USDT:100."""
        if not isinstance(balance, dict) or not balance:
            return "-"

        # Common CCXT shape: {"free": {...}, "used": {...}, "total": {...}}
        if isinstance(balance.get("total"), dict):
            source = balance.get("total") or {}
        elif isinstance(balance.get("free"), dict):
            source = balance.get("free") or {}
        else:
            # Flat dict fallback; skip known non-asset keys
            skip = {"free", "used", "total", "info", "raw", "equity", "cash", "currency"}
            source = {k: v for k, v in balance.items() if k not in skip}

        parts = []
        for sym, val in source.items():
            try:
                num = float(val)
            except Exception:
                continue
            if num == 0:
                continue
            parts.append(f"{sym}:{num:g}")

        if not parts:
            return "-"

        parts.sort()
        return ", ".join(parts)

    def _compact_balance_text(self, balance, max_items=4):
        full_text = self._format_balance_text(balance)
        if full_text == "-":
            return "-", "-"

        parts = [part.strip() for part in full_text.split(",") if part.strip()]
        compact = ", ".join(parts[:max_items])
        if len(parts) > max_items:
            compact = f"{compact} +{len(parts) - max_items} more"

        return compact, full_text

    def _elide_text(self, value, max_length=42):
        text = str(value)
        if len(text) <= max_length:
            return text
        return f"{text[: max_length - 1]}..."

    def _set_status_value(self, field, value, tooltip=None):
        label = self.status_labels.get(field)
        if label is None or not self._is_qt_object_alive(label):
            if label is not None:
                try:
                    self.status_labels.pop(field, None)
                except Exception:
                    pass
            cache = getattr(self, "_status_value_cache", None)
            if isinstance(cache, dict):
                cache.pop(field, None)
            return

        display = self._elide_text(value)
        resolved_tooltip = tooltip or str(value)
        cache = getattr(self, "_status_value_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._status_value_cache = cache
        cached = cache.get(field)
        if (
            isinstance(cached, tuple)
            and len(cached) == 3
            and cached[0] is label
            and cached[1] == display
            and cached[2] == resolved_tooltip
        ):
            return
        label.setText(display)
        label.setToolTip(resolved_tooltip)
        cache[field] = (label, display, resolved_tooltip)

    def _system_status_exchange_display(self):
        broker = getattr(self.controller, "broker", None)
        config = getattr(self.controller, "config", None)
        broker_config = getattr(config, "broker", None)

        exchange = getattr(broker, "exchange_name", None)
        if not exchange and broker_config is not None:
            exchange = getattr(broker_config, "exchange", None)

        normalized = str(exchange or "Unknown").strip()
        normalized_lower = normalized.lower()

        if normalized_lower == "stellar":
            horizon_url = getattr(broker, "horizon_url", "")
            if horizon_url:
                return "Stellar Horizon", horizon_url
            return "Stellar Horizon", "stellar"

        if not normalized:
            return "Unknown", "Unknown"

        return normalized, normalized

    def _runtime_health_snapshot(self, monitor_symbol, timeframe_value):
        controller = getattr(self, "controller", None)
        cache_key = (
            str(monitor_symbol or "").strip().upper(),
            str(timeframe_value or "").strip().lower() or "1h",
        )
        cache_seconds = max(0.5, float(getattr(self, "RUNTIME_HEALTH_CACHE_SECONDS", 3.0) or 3.0))
        now = time.monotonic()
        should_refresh = cache_key != getattr(self, "_runtime_health_cache_key", None)
        should_refresh = should_refresh or (
            (now - float(getattr(self, "_last_runtime_health_refresh_at", 0.0) or 0.0)) >= cache_seconds
        )

        if should_refresh:
            capability_profile = {}
            if hasattr(controller, "get_broker_capability_profile"):
                try:
                    capability_profile = dict(controller.get_broker_capability_profile() or {})
                except Exception:
                    capability_profile = {}

            readiness_report = {}
            if hasattr(controller, "get_live_readiness_report"):
                try:
                    readiness_report = dict(
                        controller.get_live_readiness_report(
                            symbol=monitor_symbol,
                            timeframe=timeframe_value,
                        )
                        or {}
                    )
                except Exception:
                    readiness_report = {}

            market_data_health = dict(readiness_report.get("market_data") or {})
            if not market_data_health and hasattr(controller, "get_market_data_health_snapshot"):
                try:
                    market_data_health = dict(
                        controller.get_market_data_health_snapshot(
                            symbol=monitor_symbol,
                            timeframe=timeframe_value,
                        )
                        or {}
                    )
                except Exception:
                    market_data_health = {}

            self._cached_capability_profile = capability_profile
            self._cached_readiness_report = readiness_report
            self._cached_market_data_health = market_data_health
            self._runtime_health_cache_key = cache_key
            self._last_runtime_health_refresh_at = now

        return (
            dict(getattr(self, "_cached_capability_profile", {}) or {}),
            dict(getattr(self, "_cached_readiness_report", {}) or {}),
            dict(getattr(self, "_cached_market_data_health", {}) or {}),
        )

    def _refresh_terminal(self):

        try:
            if getattr(self, "_ui_shutting_down", False):
                return

            controller = self.controller
            runtime_metrics = self._runtime_metrics_snapshot()
            balance = dict(runtime_metrics.get("balances") or {})
            equity = float(runtime_metrics.get("equity_value") or 0.0)
            spread = runtime_metrics.get("spread_pct", 0)
            positions = list(runtime_metrics.get("positions") or [])
            open_orders = list(runtime_metrics.get("open_orders") or [])
            symbols_loaded = int(runtime_metrics.get("symbols_loaded") or 0)
            exchange_display, exchange_tooltip = self._system_status_exchange_display()

            free = runtime_metrics.get("free_balances", 0)
            used = runtime_metrics.get("used_balances", 0)

            balance_summary, balance_tooltip = self._compact_balance_text(balance)
            free_summary, free_tooltip = self._compact_balance_text(
                free if isinstance(free, dict) else {"USDT": free}
            )
            used_summary, used_tooltip = self._compact_balance_text(
                used if isinstance(used, dict) else {"USDT": used}
            )
            monitor_symbol = self._current_chart_symbol() or getattr(self, "symbol", None)
            timeframe_value = str(getattr(self, "current_timeframe", "") or getattr(controller, "time_frame", "1h") or "1h").strip() or "1h"
            capability_profile, readiness_report, market_data_health = self._runtime_health_snapshot(
                monitor_symbol,
                timeframe_value,
            )

            def _format_feed_status(snapshot):
                payload = dict(snapshot or {})
                if payload.get("supported") is False:
                    return "N/A", "This feed is not supported by the active broker profile."
                freshness = payload.get("fresh")
                if freshness is True:
                    status_text = "Fresh"
                elif freshness is False:
                    status_text = "Stale"
                else:
                    status_text = "Unknown"
                age_label = str(payload.get("age_label") or "unknown").strip() or "unknown"
                threshold_label = str(payload.get("threshold_label") or "n/a").strip() or "n/a"
                display = f"{status_text} ({age_label})"
                tooltip = f"Status: {status_text}\nAge: {age_label}\nThreshold: {threshold_label}"
                return display, tooltip

            self._set_status_value("Exchange", exchange_display, exchange_tooltip)
            self._set_status_value("Mode", "LIVE" if getattr(controller, "is_live_mode", lambda: False)() else "PAPER")
            self._set_status_value("Account", getattr(controller, "current_account_label", lambda: "Not set")())
            self._set_status_value("Workspace", "Open access")
            self._set_status_value("Risk Profile", getattr(controller, "risk_profile_name", "Balanced"))
            trade_venue = str(
                getattr(getattr(controller, "broker", None), "resolved_market_preference", "")
                or getattr(controller, "market_trade_preference", "auto")
                or "auto"
            ).upper()
            news_mode_parts = []
            if getattr(controller, "news_enabled", False):
                news_mode_parts.append("feed")
            if getattr(controller, "news_draw_on_chart", False):
                news_mode_parts.append("chart")
            if getattr(controller, "news_autotrade_enabled", False):
                news_mode_parts.append("auto")
            news_mode = " / ".join(news_mode_parts) if news_mode_parts else "OFF"
            self._set_status_value("Trade Venue", trade_venue)
            self._set_status_value("Data Provider", capability_profile.get("market_data_provider", "-"))
            self._set_status_value("Swap Provider", capability_profile.get("swap_provider", "-") or "-")
            self._set_status_value("News Mode", news_mode)

            self._set_status_value("Symbols Loaded", symbols_loaded)

            self._set_status_value("Equity", self._format_currency(equity))

            self._set_status_value("Balance", balance_summary, balance_tooltip)

            self._set_status_value("Free Margin", free_summary, free_tooltip)

            self._set_status_value("Used Margin", used_summary, used_tooltip)

            self._set_status_value("Spread %", f"{spread:.4f}")

            self._set_status_value("Open Positions", len(positions))
            self._set_status_value("Open Orders", len(open_orders))

            market_stream_status = "Stopped"
            if hasattr(controller, "get_market_stream_status"):
                market_stream_status = controller.get_market_stream_status()

            broker_status = dict(getattr(self, "_latest_broker_status_snapshot", {}) or {})
            self._set_status_value("Broker API", broker_status.get("summary", "Unknown"), str(broker_status.get("detail", "")) or None)
            self._set_status_value("Websocket", market_stream_status)

            self._set_status_value("AITrading", "ON" if self.autotrading_enabled else "OFF")
            self._set_status_value("AI Scope", self._autotrade_scope_label())
            self._set_status_value("Watchlist", len(self.autotrade_watchlist))
            behavior_status = {}
            if hasattr(controller, "get_behavior_guard_status"):
                behavior_status = controller.get_behavior_guard_status() or {}
            self._set_status_value("Behavior Guard", behavior_status.get("summary", "Not active"))
            self._set_status_value("Guard Reason", behavior_status.get("reason", "No active behavior restrictions"))
            self._set_status_value("Health Check", getattr(controller, "get_health_check_summary", lambda: "Not run")())
            readiness_tooltip_lines = []
            readiness_display = str(readiness_report.get("summary") or "Not checked").strip() or "Not checked"
            for reason in list(readiness_report.get("blocking_reasons") or [])[:4]:
                readiness_tooltip_lines.append(f"BLOCK: {reason}")
            for reason in list(readiness_report.get("warning_reasons") or [])[:4]:
                readiness_tooltip_lines.append(f"WARN: {reason}")
            readiness_tooltip = "\n".join(readiness_tooltip_lines) or readiness_display
            self._set_status_value("Readiness", readiness_display, readiness_tooltip)
            quote_display, quote_tooltip = _format_feed_status((market_data_health or {}).get("quote"))
            candle_display, candle_tooltip = _format_feed_status((market_data_health or {}).get("candles"))
            orderbook_display, orderbook_tooltip = _format_feed_status((market_data_health or {}).get("orderbook"))
            self._set_status_value("Quote Health", quote_display, quote_tooltip)
            self._set_status_value("Candle Health", candle_display, candle_tooltip)
            self._set_status_value("Orderbook Health", orderbook_display, orderbook_tooltip)
            self._set_status_value("Pipeline", getattr(controller, "get_pipeline_status_summary", lambda: "Idle")())

            self._set_status_value("Timeframe", self.current_timeframe)
            if self._should_refresh_terminal_section("session_controls", interval_seconds=2.0):
                self._refresh_session_selector()
                self._refresh_session_tabs()
            self._update_session_badge()
            self._update_kill_switch_button()

            if self._should_refresh_terminal_section("risk_heatmap", interval_seconds=2.0):
                self._update_risk_heatmap()
            if self._server_authority_active() and self._should_refresh_terminal_section(
                "execution_tables",
                interval_seconds=0.5,
            ):
                self._populate_assets_table(getattr(self, "_latest_assets_snapshot", {}) or {})
                self._populate_positions_table(positions)
                self._populate_open_orders_table(open_orders)
                self._populate_order_history_table(getattr(self, "_latest_order_history_snapshot", []) or [])
                self._populate_trade_history_table(getattr(self, "_latest_trade_history_snapshot", []) or [])
            if not self._server_authority_active():
                self._schedule_broker_status_refresh()
                self._schedule_assets_refresh()
                self._schedule_positions_refresh()
                self._schedule_open_orders_refresh()
                self._schedule_order_history_refresh()
                self._schedule_trade_history_refresh()
            if self._should_refresh_terminal_section("strategy_comparison", interval_seconds=3.0):
                self._refresh_strategy_comparison_panel()
            if self._should_refresh_terminal_section("live_agent_timeline", interval_seconds=3.0):
                self._refresh_live_agent_timeline_panel()

        except Exception as e:

            self.logger.error(e)


    def _refresh_markets(self):

        blocked = self.symbols_table.blockSignals(True)
        self.symbols_table.setRowCount(0)
        self._configure_market_watch_table()

        for symbol in self.controller.symbols:

            row = self.symbols_table.rowCount()
            self.symbols_table.insertRow(row)

            self._set_market_watch_row(row, symbol, bid="-", ask="-", status="⏳", usd_value="-")
        self.symbols_table.blockSignals(blocked)
        self._reorder_market_watch_rows()

    def _create_system_status_panel(self):
        create_system_status_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "system_status_dock", None))

    def _create_ai_signal_panel(self):
        create_ai_signal_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "ai_signal_dock", None))

    def _create_live_agent_timeline_panel(self):
        create_live_agent_timeline_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "live_agent_timeline_dock", None))

    def _ai_monitor_rows(self):
        def _sort_key(item):
            timestamp_text = item.get("timestamp", "")
            try:
                normalized = timestamp_text.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)

        return sorted(self._ai_signal_records.values(), key=_sort_key, reverse=True)[: self.MAX_LOG_ROWS]

    def _refresh_ai_monitor_table(self, table, force=False):
        if table is None or not self._is_qt_object_alive(table):
            return
        if (not force) and self._monitor_table_is_busy(table):
            return

        rows = self._ai_monitor_rows()
        blocked = table.blockSignals(True)
        table.setUpdatesEnabled(False)
        try:
            if table.columnCount() != len(AI_MONITOR_HEADERS):
                table.setColumnCount(len(AI_MONITOR_HEADERS))
            if table.horizontalHeaderItem(0) is None:
                table.setHorizontalHeaderLabels(AI_MONITOR_HEADERS)

            table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                values = [
                    item["symbol"],
                    item["signal"],
                    f"{item['confidence']:.2f}",
                    item["regime"],
                    str(item["volatility"]),
                    item["timestamp"],
                ]
                for col, value in enumerate(values):
                    cell = table.item(row, col)
                    if cell is None:
                        cell = QTableWidgetItem("")
                        table.setItem(row, col, cell)
                    cell.setText(str(value))

            table.resizeColumnsToContents()
            header = table.horizontalHeader()
            if header is not None:
                header.setStretchLastSection(True)
        finally:
            table.setUpdatesEnabled(True)
            table.blockSignals(blocked)

    def _live_agent_timeline_target_symbol(self):
        controller = getattr(self, "controller", None)
        available_symbols = [
            self._normalized_symbol(symbol)
            for symbol in list(getattr(controller, "symbols", []) or [])
            if self._normalized_symbol(symbol)
        ]
        available_set = set(available_symbols)

        current_symbol = self._normalized_symbol(self._current_chart_symbol() or getattr(self, "symbol", ""))
        if current_symbol and (not available_set or current_symbol in available_set):
            return current_symbol

        feed_resolver = getattr(controller, "live_agent_runtime_feed", None) if controller is not None else None
        if callable(feed_resolver):
            try:
                feed_rows = list(feed_resolver(limit=60) or [])
            except Exception:
                feed_rows = []
            for row in feed_rows:
                candidate = self._normalized_symbol((row or {}).get("symbol"))
                if candidate and (not available_set or candidate in available_set):
                    return candidate

        if available_symbols:
            return available_symbols[0]
        return current_symbol

    def _agent_runtime_status_label(self, row):
        payload = dict((row or {}).get("payload") or {}) if isinstance((row or {}).get("payload"), dict) else {}
        event_type = str((row or {}).get("event_type") or "").strip().lower()
        approved = (row or {}).get("approved")
        if approved is None:
            approved = payload.get("approved")
        stage = str((row or {}).get("stage") or "").strip().lower()

        if event_type == "risk_alert" or approved is False:
            return "Rejected"
        if event_type == "order_filled":
            return "Filled"
        if event_type == "execution_plan":
            return "Execution"
        if event_type == "risk_approved" or approved is True:
            return "Approved"
        if event_type == "signal" or stage in {"signal", "selected"}:
            return "Signal"
        if stage:
            return stage.replace("_", " ").title()
        if event_type:
            return event_type.replace("_", " ").title()
        return "Runtime"

    def _agent_runtime_health_snapshot(self, rows, now_ts=None):
        runtime_rows = [dict(row) for row in list(rows or [])]
        now_value = float(now_ts or time.time())
        latest_timestamp = None
        latest_symbols = []
        grouped = {}
        counts = {
            "signals": 0,
            "approved": 0,
            "rejected": 0,
            "execution": 0,
            "filled": 0,
        }
        recent_event_count = 0

        for row in runtime_rows:
            symbol = str((row or {}).get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/")
            if symbol:
                grouped.setdefault(symbol, []).append(dict(row))
                if symbol not in latest_symbols:
                    latest_symbols.append(symbol)

            timestamp_value = (row or {}).get("timestamp")
            timestamp_float = _coerce_timestamp_seconds(timestamp_value)
            if timestamp_float is not None:
                latest_timestamp = timestamp_float if latest_timestamp is None else max(latest_timestamp, timestamp_float)
                if (now_value - timestamp_float) <= 60.0:
                    recent_event_count += 1

            status_label = self._agent_runtime_status_label(row)
            if status_label == "Signal":
                counts["signals"] += 1
            elif status_label == "Approved":
                counts["approved"] += 1
            elif status_label == "Rejected":
                counts["rejected"] += 1
            elif status_label == "Execution":
                counts["execution"] += 1
            elif status_label == "Filled":
                counts["filled"] += 1

        anomalies = []
        for symbol, symbol_rows in grouped.items():
            rejected_count = sum(1 for row in symbol_rows if self._agent_runtime_status_label(row) == "Rejected")
            if rejected_count >= 2:
                anomalies.append(f"{symbol}: repeated rejections ({rejected_count})")

            symbol_latest = None
            filled_ids = set()
            execution_ids = []
            for row in symbol_rows:
                timestamp_float = _coerce_timestamp_seconds((row or {}).get("timestamp"))
                if timestamp_float is not None:
                    symbol_latest = timestamp_float if symbol_latest is None else max(symbol_latest, timestamp_float)
                event_type = str((row or {}).get("event_type") or "").strip().lower()
                decision_id = str((row or {}).get("decision_id") or "").strip()
                if event_type == "order_filled" and decision_id:
                    filled_ids.add(decision_id)
                if event_type == "execution_plan":
                    execution_ids.append(decision_id)

            if symbol_latest is not None and (now_value - symbol_latest) > 300.0:
                anomalies.append(f"{symbol}: stale decision flow")
            if execution_ids and any((not decision_id) or (decision_id not in filled_ids) for decision_id in execution_ids):
                anomalies.append(f"{symbol}: execution plan without fill")

        if latest_timestamp is None:
            health = "IDLE"
            last_event_age = None
        else:
            last_event_age = max(0.0, now_value - latest_timestamp)
            if last_event_age > 300.0:
                health = "STALE"
            elif anomalies:
                health = "DEGRADED"
            elif counts["approved"] > 0 or counts["execution"] > 0 or counts["filled"] > 0:
                health = "HEALTHY"
            else:
                health = "WATCHING"

        def _age_text(seconds_value):
            if seconds_value is None:
                return "none yet"
            if seconds_value < 60.0:
                return f"{int(seconds_value)}s ago"
            if seconds_value < 3600.0:
                return f"{int(seconds_value // 60)}m ago"
            return f"{int(seconds_value // 3600)}h ago"

        latest_symbol_states = []
        for symbol, symbol_rows in list(grouped.items())[:5]:
            latest_row = symbol_rows[0]
            message = str(
                latest_row.get("message")
                or latest_row.get("reason")
                or latest_row.get("stage")
                or "No detail recorded."
            ).strip()
            latest_symbol_states.append(
                {
                    "symbol": symbol,
                    "status": self._agent_runtime_status_label(latest_row),
                    "message": message,
                }
            )

        return {
            "health": health,
            "last_event_age": last_event_age,
            "last_event_age_text": _age_text(last_event_age),
            "counts": counts,
            "recent_event_count": recent_event_count,
            "active_symbol_count": len(grouped),
            "latest_symbols": latest_symbols[:4],
            "anomalies": anomalies[:5],
            "latest_symbol_states": latest_symbol_states,
            "event_count": len(runtime_rows),
        }

    def _refresh_live_agent_timeline_panel(self, force=False):
        dock = getattr(self, "live_agent_timeline_dock", None)
        summary = getattr(self, "live_agent_timeline_summary", None)
        browser = getattr(self, "live_agent_timeline_browser", None)
        if not self._is_qt_object_alive(summary) or not self._is_qt_object_alive(browser):
            return
        if (not force) and self._is_qt_object_alive(dock) and (not dock.isVisible()):
            return

        controller = getattr(self, "controller", None)
        symbol = self._live_agent_timeline_target_symbol()
        snapshot = {}
        snapshot_resolver = getattr(controller, "decision_timeline_snapshot", None) if controller is not None else None
        if callable(snapshot_resolver):
            try:
                snapshot = dict(snapshot_resolver(symbol=symbol or None, limit=12) or {})
            except TypeError:
                snapshot = dict(snapshot_resolver(symbol) or {})
            except Exception:
                snapshot = {}

        resolved_symbol = self._normalized_symbol((snapshot or {}).get("symbol") or symbol or "")
        runtime_rows = []
        global_runtime_rows = []
        feed_resolver = getattr(controller, "live_agent_runtime_feed", None) if controller is not None else None
        if callable(feed_resolver):
            try:
                runtime_rows = list(feed_resolver(limit=60, symbol=resolved_symbol or None) or [])
            except TypeError:
                runtime_rows = list(feed_resolver(60, resolved_symbol or None) or [])
            except Exception:
                runtime_rows = []
            try:
                global_runtime_rows = list(feed_resolver(limit=200) or [])
            except TypeError:
                global_runtime_rows = list(feed_resolver(200) or [])
            except Exception:
                global_runtime_rows = list(runtime_rows)

        steps = list((snapshot or {}).get("steps") or [])
        health_snapshot = self._agent_runtime_health_snapshot(global_runtime_rows)
        summary_text = str((snapshot or {}).get("summary") or "").strip()
        if not summary_text:
            if resolved_symbol:
                summary_text = f"{resolved_symbol}: no agent decision chain has been recorded yet."
            else:
                summary_text = "No agent runtime decisions have been recorded in this session yet."

        anomaly_text = ", ".join(list(health_snapshot.get("anomalies") or [])[:2]) or "none"
        counts = dict(health_snapshot.get("counts") or {})
        summary_lines = [
            f"Health: {health_snapshot.get('health') or 'IDLE'} | Last event: {health_snapshot.get('last_event_age_text') or 'none yet'}",
            f"Signals: {int(counts.get('signals', 0) or 0)} | Approved: {int(counts.get('approved', 0) or 0)} | Rejected: {int(counts.get('rejected', 0) or 0)} | Execution: {int(counts.get('execution', 0) or 0)} | Filled: {int(counts.get('filled', 0) or 0)}",
            f"Active symbols: {int(health_snapshot.get('active_symbol_count', 0) or 0)} | Events last minute: {int(health_snapshot.get('recent_event_count', 0) or 0)}",
            f"Anomalies: {anomaly_text}",
        ]
        if resolved_symbol:
            summary_lines.append(f"Focus symbol: {resolved_symbol}")
        summary_lines.append(f"Decision steps: {len(steps)}")
        summary_lines.append(f"Runtime events: {len(runtime_rows)}")
        summary_lines.append(summary_text)
        rendered_summary = "\n".join(summary_lines)

        detail_lines = ["Agent Health Check"]
        detail_lines.append(
            f"Status: {health_snapshot.get('health') or 'IDLE'} | Last event: {health_snapshot.get('last_event_age_text') or 'none yet'}"
        )
        detail_lines.append(
            "Counts: "
            f"signals={int(counts.get('signals', 0) or 0)}, "
            f"approved={int(counts.get('approved', 0) or 0)}, "
            f"rejected={int(counts.get('rejected', 0) or 0)}, "
            f"execution={int(counts.get('execution', 0) or 0)}, "
            f"filled={int(counts.get('filled', 0) or 0)}"
        )
        latest_symbols = ", ".join(list(health_snapshot.get("latest_symbols") or [])) or "none"
        detail_lines.append(f"Symbols active: {latest_symbols}")
        anomalies = list(health_snapshot.get("anomalies") or [])
        detail_lines.append(f"Anomalies: {', '.join(anomalies) if anomalies else 'none'}")
        latest_symbol_states = list(health_snapshot.get("latest_symbol_states") or [])
        if latest_symbol_states:
            detail_lines.append("")
            detail_lines.append("Latest Symbol States")
            for item in latest_symbol_states:
                detail_lines.append(
                    f"- {item.get('symbol')}: {item.get('status')} | {item.get('message')}"
                )
        detail_lines.append("")
        if steps:
            detail_lines.append("Focus Symbol Decision Chain")
            for index, step in enumerate(steps, start=1):
                timestamp_label = str(step.get("timestamp_label") or "-").strip() or "-"
                agent_name = str(step.get("agent_name") or "Agent").strip() or "Agent"
                stage = str(step.get("stage") or "").strip()
                status = str(step.get("status") or "pending").strip().upper() or "PENDING"
                strategy_name = str(step.get("strategy_name") or "").strip()
                timeframe = str(step.get("timeframe") or "").strip()
                side = str(step.get("side") or "").strip().upper()
                reason = str(step.get("reason") or "").strip()

                headline = f"{index}. {timestamp_label} | {agent_name} | {status}"
                if stage:
                    headline = f"{headline} | {stage}"
                detail_lines.append(headline)

                context_parts = []
                if side:
                    context_parts.append(f"Side: {side}")
                if strategy_name:
                    context_parts.append(f"Strategy: {strategy_name}")
                if timeframe:
                    context_parts.append(f"Timeframe: {timeframe}")
                if context_parts:
                    detail_lines.append("   " + " | ".join(context_parts))
                if reason:
                    detail_lines.append("   " + reason)
                detail_lines.append("")
        elif runtime_rows:
            detail_lines.append("Focus Symbol Runtime Events")
            detail_lines.append("No decision chain is available yet. Latest runtime events:")
            detail_lines.append("")
            for row in runtime_rows[:10]:
                timestamp_label = str(row.get("timestamp_label") or "-").strip() or "-"
                actor = str(row.get("agent_name") or row.get("event_type") or row.get("kind") or "runtime").strip()
                message = str(row.get("message") or row.get("reason") or "").strip() or "No detail recorded."
                detail_lines.append(f"{timestamp_label} | {actor} | {message}")
        else:
            detail_lines.append("Focus Symbol Runtime")
            detail_lines.append("Select or scan a symbol to start building an agent decision chain.")

        rendered_detail = "\n".join(detail_lines).strip()
        cache_key = (rendered_summary, rendered_detail)
        if getattr(self, "_live_agent_timeline_cache", None) == cache_key:
            return

        summary.setText(rendered_summary)
        browser.setPlainText(rendered_detail)
        self._live_agent_timeline_cache = cache_key

    def _update_ai_signal(self, data):
        if self._ui_shutting_down:
            return
        if not isinstance(data, dict):
            return

        symbol = str(data.get("symbol", "") or "").strip()
        if not symbol:
            return

        record = {
            "symbol": symbol,
            "signal": str(data.get("signal", "") or ""),
            "confidence": float(data.get("confidence", 0.0) or 0.0),
            "regime": str(data.get("regime", "") or ""),
            "volatility": data.get("volatility", ""),
            "reason": str(data.get("reason", "") or ""),
            "decision": str(data.get("decision", "") or ""),
            "risk": str(data.get("risk", "") or ""),
            "warnings": list(data.get("warnings") or []),
            "provider": str(data.get("provider", "") or ""),
            "mode": str(data.get("mode", "") or ""),
            "timestamp": str(data.get("timestamp", "") or ""),
            "market_hours": dict(data.get("market_hours") or {}) if isinstance(data.get("market_hours"), dict) else {},
            "market_session": str(data.get("market_session", "") or ""),
            "high_liquidity_session": data.get("high_liquidity_session"),
        }
        self._ai_signal_records[symbol] = record
        self._record_recommendation(
            symbol=symbol,
            signal=record["signal"],
            confidence=record["confidence"],
            regime=record["regime"],
            volatility=record["volatility"],
            reason=record["reason"],
            strategy="AI Monitor",
            timestamp=record["timestamp"],
        )
        self._log_ai_signal_update(record)

        now = time.monotonic()
        if (now - float(getattr(self, "_last_ai_table_refresh_at", 0.0) or 0.0)) < float(self.AI_TABLE_REFRESH_MIN_SECONDS or 0.5):
            return
        self._last_ai_table_refresh_at = now

        dock = getattr(self, "ai_signal_dock", None)
        if self._is_qt_object_alive(getattr(self, "ai_table", None)) and (
            dock is None or (self._is_qt_object_alive(dock) and dock.isVisible())
        ):
            self._refresh_ai_monitor_table(self.ai_table)

        monitor_window = (getattr(self, "detached_tool_windows", {}) or {}).get("ml_monitor")
        if self._is_qt_object_alive(monitor_window) and bool(monitor_window.isVisible()):
            self._refresh_ai_monitor_table(getattr(monitor_window, "_monitor_table", None))

    def _log_ai_signal_update(self, record):
        if not isinstance(record, dict):
            return

        system_console = getattr(self, "system_console", None)
        if system_console is None or not hasattr(system_console, "log"):
            return

        symbol = str(record.get("symbol", "") or "").strip().upper()
        if not symbol:
            return

        try:
            confidence = float(record.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0

        signal_text = str(record.get("signal", "") or "HOLD").strip().upper() or "HOLD"
        regime = str(record.get("regime", "") or "").strip().upper()
        decision = str(record.get("decision", "") or "").strip().upper()
        provider = str(record.get("provider", "") or "").strip()
        mode = str(record.get("mode", "") or "").strip()
        reason = " ".join(str(record.get("reason", "") or "").split()).strip()
        market_hours = dict(record.get("market_hours") or {}) if isinstance(record.get("market_hours"), dict) else {}
        asset_type = str(market_hours.get("asset_type") or "").strip().lower()
        market_session = str(
            market_hours.get("session")
            or record.get("market_session")
            or ""
        ).strip().lower()
        market_open = market_hours.get("market_open")
        trade_allowed = market_hours.get("trade_allowed")
        high_liquidity = market_hours.get("high_liquidity")

        market_parts = []
        if asset_type:
            market_parts.append(asset_type)
        if market_session:
            market_parts.append(f"session {market_session}")
        if market_open is True:
            market_parts.append("open")
        elif market_open is False:
            market_parts.append("closed")
        if trade_allowed is True:
            market_parts.append("trade allowed")
        elif trade_allowed is False:
            market_parts.append("trade blocked")
        if high_liquidity is True:
            market_parts.append("liq high")
        elif high_liquidity is False:
            market_parts.append("liq normal")
        market_summary = " | ".join(market_parts)

        signature = (
            signal_text,
            decision,
            round(confidence, 2),
            regime,
            provider.lower(),
            mode.lower(),
            market_summary,
            reason[:160],
        )
        log_state = getattr(self, "_ai_signal_log_state", None)
        if not isinstance(log_state, dict):
            log_state = {}
            self._ai_signal_log_state = log_state

        previous = dict(log_state.get(symbol, {}) or {})
        now = time.monotonic()
        if previous.get("signature") == signature:
            last_logged = float(previous.get("logged_at", 0.0) or 0.0)
            if (now - last_logged) < float(getattr(self, "AI_SIGNAL_LOG_MIN_SECONDS", 30.0) or 30.0):
                return

        message_parts = [f"Signal monitor {symbol}: {signal_text}", f"conf {confidence:.2f}"]
        if regime:
            message_parts.append(f"regime {regime}")
        if provider:
            message_parts.append(provider)
        if mode:
            message_parts.append(mode)
        if market_summary:
            message_parts.append(f"market {market_summary}")
        message = " | ".join(message_parts)
        if reason:
            message = f"{message} | {reason[:180]}"

        level = "WARN" if decision in {"REJECT", "BLOCK", "CANCEL"} else "INFO"
        try:
            system_console.log(message, level)
        except Exception:
            self.logger.debug("Unable to log AI signal monitor update", exc_info=True)
            return

        log_state[symbol] = {"signature": signature, "logged_at": now}

    def _recommendation_sort_key(self, item):
        timestamp_text = str(item.get("timestamp", "") or "")
        try:
            normalized = timestamp_text.replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(normalized)
        except Exception:
            timestamp = datetime.min.replace(tzinfo=timezone.utc)
        confidence = float(item.get("confidence", 0.0) or 0.0)
        return (confidence, timestamp)

    def _record_recommendation(
        self,
        symbol,
        signal="",
        confidence=0.0,
        regime="",
        volatility="",
        reason="",
        strategy="",
        timestamp="",
    ):
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return

        existing = dict(self._recommendation_records.get(normalized_symbol, {}))
        record = {
            "symbol": normalized_symbol,
            "signal": str(signal or existing.get("signal", "")).upper(),
            "confidence": float(confidence if confidence not in (None, "") else existing.get("confidence", 0.0) or 0.0),
            "regime": str(regime or existing.get("regime", "") or ""),
            "volatility": volatility if volatility not in (None, "") else existing.get("volatility", ""),
            "reason": str(reason or existing.get("reason", "") or ""),
            "strategy": str(strategy or existing.get("strategy", "") or ""),
            "timestamp": str(timestamp or existing.get("timestamp", "") or datetime.now(timezone.utc).isoformat()),
        }
        self._recommendation_records[normalized_symbol] = record
        self._refresh_recommendations_window()

    def _recommendation_rows(self):
        return sorted(
            self._recommendation_records.values(),
            key=self._recommendation_sort_key,
            reverse=True,
        )[: self.MAX_LOG_ROWS]

    def _recommendation_summary_text(self, rows):
        if not rows:
            return "No recommendations on deck yet. Start market monitoring or AI trading to build an explainable idea queue."

        buy_count = sum(1 for item in rows if str(item.get("signal", "")).upper() == "BUY")
        sell_count = sum(1 for item in rows if str(item.get("signal", "")).upper() == "SELL")
        avg_conf = sum(float(item.get("confidence", 0.0) or 0.0) for item in rows) / max(len(rows), 1)
        top_symbol = rows[0].get("symbol", "-")
        top_reason = rows[0].get("reason", "") or "Reason not supplied by strategy."
        return (
            f"{len(rows)} symbols tracked | BUY {buy_count} | SELL {sell_count} | "
            f"avg confidence {avg_conf:.2f} | strongest idea: {top_symbol} - {top_reason}"
        )

    def _recommendation_details_html(self, record):
        if not isinstance(record, dict):
            return Terminal._empty_state_html(
                self,
                "Recommendation Detail",
                "Select a symbol from the recommendation list to review the signal, confidence, regime, and strategy rationale.",
                hint="This panel updates as live strategy and agent runtime output arrives.",
            )

        symbol = html.escape(str(record.get("symbol", "-") or "-"))
        signal = html.escape(str(record.get("signal", "WATCH") or "WATCH"))
        strategy = html.escape(str(record.get("strategy", "Recommendation Engine") or "Recommendation Engine"))
        reason = html.escape(str(record.get("reason", "") or "Reason not found in runtime data."))
        regime = html.escape(str(record.get("regime", "") or "Not available"))
        timestamp = html.escape(str(record.get("timestamp", "") or "Not available"))
        try:
            confidence = float(record.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        volatility = html.escape(str(record.get("volatility", "") or "Not available"))
        return (
            f"<h3>{symbol}: {signal}</h3>"
            f"<p><b>Why it is recommended:</b> {reason}</p>"
            f"<p><b>Confidence:</b> {confidence:.2f}<br>"
            f"<b>Source:</b> {strategy}<br>"
            f"<b>Market regime:</b> {regime}<br>"
            f"<b>Volatility:</b> {volatility}<br>"
            f"<b>Last update:</b> {timestamp}</p>"
            "<p>This window reflects live strategy and AI runtime output. If a field is empty, that detail was not provided by the active engine yet.</p>"
        )

    def _market_chat_quick_prompts(self):
        return [
            "Show commands.",
            "Give me a short account and balance summary.",
            "Show trade history analysis.",
            "Summarize the latest news affecting my active symbols.",
            "Show app status.",
            "How is my equity and profitability looking right now?",
            "Take a screenshot of the app.",
            "Show my broker position analysis with equity, NAV, and P/L.",
            "Start AI trading.",
            "Preview this trade command without executing it: trade buy EUR/USD amount 1000",
            "Preview this cancel command without executing it: cancel order id 123456",
            "Preview this close command without executing it: close position EUR/USD",
            "Summarize current recommendations and why they are recommended.",
            "Explain my behavior guard status and any risk concerns.",
            "Show Telegram status and send a Telegram test message.",
            "What stands out in this market and app state right now?",
        ]

    def _market_chat_confirmation_preview(self, content):
        text = str(content or "").strip()
        lowered = text.lower()
        if "detected but not executed" not in lowered or "confirm" not in lowered:
            return None

        if lowered.startswith("trade command detected"):
            title = "Trade Confirmation Required"
            accent = "#f0a35e"
        elif lowered.startswith("cancel-order command detected"):
            title = "Cancel Confirmation Required"
            accent = "#ffb86c"
        elif lowered.startswith("close-position command detected"):
            title = "Close Confirmation Required"
            accent = "#ff9a76"
        else:
            title = "Confirmation Required"
            accent = "#f0a35e"

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        summary = lines[0] if lines else "Action requires confirmation."
        confirm_hint = ""
        details = []
        for line in lines[1:]:
            if "add the word confirm" in line.lower():
                confirm_hint = line
            else:
                details.append(line)

        return {
            "title": title,
            "summary": summary,
            "confirm_hint": confirm_hint or "Add the word CONFIRM to execute it.",
            "details": details,
            "accent": accent,
        }

    def _market_chat_pending_confirmation(self, window):
        history = list(getattr(window, "_market_chat_history", []) or [])
        if not history:
            return None
        latest = history[-1]
        if str(latest.get("role") or "").strip().lower() != "assistant":
            return None
        preview = latest.get("confirmation_preview")
        if not isinstance(preview, dict):
            return None
        command = str(latest.get("pending_command") or "").strip()
        if not command:
            return None
        return {"preview": preview, "command": command}

    def _confirm_market_chat_action(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window) or getattr(window, "_market_chat_busy", False):
            return
        pending = self._market_chat_pending_confirmation(window)
        if not pending:
            self._refresh_market_chat_window(window, status_message="No pending action to confirm.")
            return
        command = str(pending.get("command") or "").strip()
        if not command:
            self._refresh_market_chat_window(window, status_message="Pending action is missing its command text.")
            return
        if "confirm" not in command.lower().split():
            command = f"{command} confirm"
        self._submit_market_chat_prompt(prompt=command, window=window)

    def _cancel_market_chat_action(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window) or getattr(window, "_market_chat_busy", False):
            return
        pending = self._market_chat_pending_confirmation(window)
        if not pending:
            self._refresh_market_chat_window(window, status_message="No pending action to cancel.")
            return
        history = list(getattr(window, "_market_chat_history", []) or [])
        if history and history[-1].get("confirmation_preview"):
            history.append(
                {
                    "role": "assistant",
                    "content": "Pending action canceled. Nothing was executed.",
                }
            )
            window._market_chat_history = history
        window._market_chat_status_message = "Pending action canceled."
        self._refresh_market_chat_window(window)

    def _render_market_chat_html(self, history):
        rows = []
        for entry in list(history or []):
            role = str(entry.get("role") or "assistant").strip().lower()
            content = html.escape(str(entry.get("content") or "").strip()).replace("\n", "<br>")
            if not content:
                continue
            if role == "user":
                rows.append(
                    "<div style='margin: 8px 0; text-align: right;'>"
                    "<div style='display: inline-block; max-width: 82%; background:#17304d; color:#f4f8ff; "
                    "border:1px solid #2a4d73; border-radius:14px; padding:10px 12px;'><b>You</b><br>"
                    f"{content}</div></div>"
                )
            else:
                preview = entry.get("confirmation_preview") or self._market_chat_confirmation_preview(entry.get("content"))
                if isinstance(preview, dict):
                    title = html.escape(str(preview.get("title") or "Confirmation Required"))
                    summary = html.escape(str(preview.get("summary") or "Action requires confirmation."))
                    confirm_hint = html.escape(str(preview.get("confirm_hint") or "Add the word CONFIRM to execute it."))
                    accent = html.escape(str(preview.get("accent") or "#f0a35e"))
                    details_html = ""
                    for detail in list(preview.get("details") or []):
                        details_html += (
                            "<div style='margin-top:6px; color:#d8e6ff;'>"
                            f"{html.escape(str(detail))}"
                            "</div>"
                        )
                    rows.append(
                        "<div style='margin: 10px 0; text-align: left;'>"
                        "<div style='display: inline-block; max-width: 88%; background:#16141b; color:#f8efe7; "
                        f"border:1px solid {accent}; border-left:5px solid {accent}; border-radius:14px; padding:12px 14px;'>"
                        "<div style='font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:#ffcf9a; margin-bottom:6px;'>"
                        "Sopotek Pilot"
                        "</div>"
                        f"<div style='font-weight:700; color:#fff3e2; margin-bottom:4px;'>{title}</div>"
                        f"<div>{summary}</div>"
                        f"{details_html}"
                        "<div style='margin-top:10px; padding:8px 10px; background:#241d16; border-radius:10px; color:#ffd7a8;'>"
                        f"{confirm_hint}"
                        "</div>"
                        "</div></div>"
                    )
                else:
                    rows.append(
                        "<div style='margin: 8px 0; text-align: left;'>"
                        "<div style='display: inline-block; max-width: 82%; background:#0f1727; color:#d9e6f7; "
                        "border:1px solid #24344f; border-radius:14px; padding:10px 12px;'><b>Sopotek Pilot</b><br>"
                        f"{content}</div></div>"
                    )
        if not rows:
            return (
                "<div style='color:#9fb0c7; padding:14px;'>"
                "Ask about the app, the market, your balances, positions, equity, profitability, performance, recommendations, or behavior guard. Type 'show commands' for the control list."
                "</div>"
            )
        return "".join(rows)

    def _refresh_market_chat_window(self, window=None, status_message=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return

        transcript = getattr(window, "_market_chat_transcript", None)
        status = getattr(window, "_market_chat_status", None)
        send_btn = getattr(window, "_market_chat_send_btn", None)
        input_box = getattr(window, "_market_chat_input", None)
        clear_btn = getattr(window, "_market_chat_clear_btn", None)
        listen_btn = getattr(window, "_market_chat_listen_btn", None)
        speak_btn = getattr(window, "_market_chat_speak_btn", None)
        auto_speak_btn = getattr(window, "_market_chat_auto_speak_btn", None)
        provider_picker = getattr(window, "_market_chat_provider_picker", None)
        output_picker = getattr(window, "_market_chat_output_picker", None)
        voice_picker = getattr(window, "_market_chat_voice_picker", None)
        refresh_voices_btn = getattr(window, "_market_chat_refresh_voices_btn", None)
        voice_meta = getattr(window, "_market_chat_voice_meta", None)
        confirm_panel = getattr(window, "_market_chat_confirm_panel", None)
        confirm_label = getattr(window, "_market_chat_confirm_label", None)
        confirm_btn = getattr(window, "_market_chat_confirm_btn", None)
        cancel_btn = getattr(window, "_market_chat_cancel_btn", None)
        if transcript is None or status is None:
            return

        history = list(getattr(window, "_market_chat_history", []) or [])
        transcript.setHtml(self._render_market_chat_html(history))
        transcript.moveCursor(QTextCursor.MoveOperation.End)

        busy = bool(getattr(window, "_market_chat_busy", False))
        voice_busy = bool(getattr(window, "_market_chat_voice_busy", False))
        if status_message is not None:
            window._market_chat_status_message = status_message
        status.setText(
            getattr(window, "_market_chat_status_message", None)
            or (
                "Listening to your voice prompt..." if voice_busy else
                ("Sopotek Pilot is thinking..." if busy else "Ready. Ask about the app, market, balances, equity, or strategy behavior.")
            )
        )
        if send_btn is not None:
            has_text = bool(input_box.toPlainText().strip()) if input_box is not None else True
            send_btn.setEnabled((not busy) and (not voice_busy) and has_text)
            send_btn.setText("Thinking..." if busy else "Send")
        if input_box is not None:
            input_box.setReadOnly(busy or voice_busy)
        if clear_btn is not None:
            clear_btn.setEnabled((not busy) and (not voice_busy) and bool(history))
        voice_snapshot = getattr(self.controller, "market_chat_voice_state", lambda: {})() or {}
        voice_available = bool(voice_snapshot.get("voice_available"))
        listen_available = bool(voice_snapshot.get("listen_available"))
        speak_available = bool(voice_snapshot.get("speak_available"))
        if listen_btn is not None:
            listen_btn.setVisible(listen_available)
            listen_btn.setEnabled(listen_available and (not busy) and (not voice_busy))
            listen_btn.setText("Listening..." if voice_busy and getattr(window, "_market_chat_voice_mode", "") == "listen" else "Listen")
        if speak_btn is not None:
            speak_btn.setVisible(speak_available)
            speak_btn.setEnabled(speak_available and (not busy) and (not voice_busy) and bool(self._latest_market_chat_reply(window)))
            speak_btn.setText("Speaking..." if voice_busy and getattr(window, "_market_chat_voice_mode", "") == "speak" else "Speak Reply")
        if auto_speak_btn is not None:
            auto_speak_btn.setVisible(speak_available)
            auto_speak_btn.setEnabled(speak_available and (not voice_busy))
        voice_controls_enabled = voice_available and (not busy) and (not voice_busy)
        if provider_picker is not None:
            provider_picker.setVisible(True)
            provider_picker.setEnabled((not busy) and (not voice_busy))
        if output_picker is not None:
            output_picker.setVisible(True)
            output_picker.setEnabled((not busy) and (not voice_busy))
        if voice_picker is not None:
            voice_picker.setVisible(True)
            voice_picker.setEnabled(voice_controls_enabled and not getattr(window, "_market_chat_loading_voices", False))
        if refresh_voices_btn is not None:
            refresh_voices_btn.setVisible(True)
            refresh_voices_btn.setEnabled(voice_controls_enabled and not getattr(window, "_market_chat_loading_voices", False))
            refresh_voices_btn.setText("Refreshing..." if getattr(window, "_market_chat_loading_voices", False) else "Refresh Voices")
        if voice_meta is not None:
            voice_meta.setVisible(True)
            voice_meta.setText(self._market_chat_voice_state_text(window))
        pending = self._market_chat_pending_confirmation(window)
        if confirm_panel is not None and confirm_label is not None and confirm_btn is not None and cancel_btn is not None:
            if pending is not None:
                preview = pending.get("preview") or {}
                confirm_panel.setVisible(True)
                confirm_label.setText(
                    f"{preview.get('title', 'Confirmation Required')}: {preview.get('confirm_hint', 'Add CONFIRM to execute.')}"
                )
                confirm_btn.setEnabled((not busy) and (not voice_busy))
                cancel_btn.setEnabled((not busy) and (not voice_busy))
            else:
                confirm_panel.setVisible(False)
                confirm_label.setText("")
                confirm_btn.setEnabled(False)
                cancel_btn.setEnabled(False)

    async def _run_market_chat_request(self, window, question, conversation):
        try:
            answer = await self.controller.ask_openai_about_app(question, conversation=conversation)
        except Exception as exc:
            answer = f"Sopotek Pilot request failed: {exc}"

        preview = self._market_chat_confirmation_preview(answer)
        history = list(getattr(window, "_market_chat_history", []) or [])
        entry = {"role": "assistant", "content": str(answer or "No response returned.")}
        if preview is not None:
            entry["confirmation_preview"] = preview
            entry["pending_command"] = str(question or "").strip()
        history.append(entry)
        window._market_chat_history = history
        window._market_chat_busy = False
        window._market_chat_status_message = "Confirmation required." if preview is not None else "Response ready."
        self._refresh_market_chat_window(window)
        auto_speak_btn = getattr(window, "_market_chat_auto_speak_btn", None)
        if auto_speak_btn is not None and auto_speak_btn.isChecked():
            self._speak_market_chat_reply(window, latest_text=entry["content"], automatic=True)

    def _submit_market_chat_prompt(self, prompt=None, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_busy", False):
            return

        input_box = getattr(window, "_market_chat_input", None)
        if input_box is None:
            return

        question = str(prompt or input_box.toPlainText()).strip()
        if not question:
            self._refresh_market_chat_window(window, status_message="Type a question first.")
            return

        history = list(getattr(window, "_market_chat_history", []) or [])
        conversation = history[-8:]
        history.append({"role": "user", "content": question})
        window._market_chat_history = history
        window._market_chat_busy = True
        window._market_chat_status_message = "Sending question to Sopotek Pilot..."
        input_box.clear()
        self._refresh_market_chat_window(window)

        task_factory = getattr(self.controller, "_create_task", None)
        runner = self._run_market_chat_request(window, question, conversation)
        if callable(task_factory):
            window._market_chat_task = task_factory(runner, "market_chat_request")
        else:
            window._market_chat_task = asyncio.create_task(runner)

    def _clear_market_chat(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_busy", False) or getattr(window, "_market_chat_voice_busy", False):
            return
        window._market_chat_history = []
        window._market_chat_status_message = "Conversation cleared."
        self._refresh_market_chat_window(window)

    def _latest_market_chat_reply(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return ""
        history = list(getattr(window, "_market_chat_history", []) or [])
        for entry in reversed(history):
            if str(entry.get("role") or "").strip().lower() == "assistant":
                return str(entry.get("content") or "").strip()
        return ""

    def _market_chat_voice_state_text(self, window=None):
        _ = window
        snapshot = getattr(self.controller, "market_chat_voice_state", lambda: {})() or {}
        provider = str(snapshot.get("recognition_provider") or snapshot.get("provider") or "windows").strip().lower()
        provider_label = "Google" if provider == "google" else "Windows"
        output_provider = str(snapshot.get("output_provider") or "windows").strip().lower()
        effective_output_provider = str(
            snapshot.get("effective_output_provider") or output_provider or "windows"
        ).strip().lower() or "windows"
        output_label = "OpenAI" if output_provider == "openai" else "Windows"
        effective_output_label = "OpenAI" if effective_output_provider == "openai" else "Windows"
        voice_name = str(snapshot.get("voice_name") or "").strip() or "System Default"
        if provider == "google" and not snapshot.get("google_available"):
            return (
                f"Recognition: {provider_label} needs SpeechRecognition + sounddevice installed. "
                f"Speech: {effective_output_label} ({voice_name})."
            )
        if snapshot.get("output_fallback") and output_provider == "openai" and effective_output_provider == "windows":
            return (
                f"Recognition: {provider_label}. "
                f"Speech: OpenAI is unavailable, so Sopotek Pilot will use Windows speech ({voice_name})."
            )
        if output_provider == "openai" and not snapshot.get("openai_available"):
            return (
                f"Recognition: {provider_label}. "
                f"Speech: {output_label} needs an OpenAI API key in Settings -> Integrations."
            )
        return f"Recognition: {provider_label}. Speech: {effective_output_label}. Voice: {voice_name}."

    def _set_market_chat_auto_speak(self, checked, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        enabled = bool(checked)
        self.settings.setValue("market_chat/auto_speak", enabled)
        self._refresh_market_chat_window(
            window,
            status_message=(
                "Auto Speak enabled. Sopotek Pilot replies will be spoken automatically."
                if enabled
                else "Auto Speak disabled."
            ),
        )

    def _populate_market_chat_voice_controls(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return

        provider_picker = getattr(window, "_market_chat_provider_picker", None)
        output_picker = getattr(window, "_market_chat_output_picker", None)
        voice_picker = getattr(window, "_market_chat_voice_picker", None)
        voice_meta = getattr(window, "_market_chat_voice_meta", None)
        if provider_picker is None or output_picker is None or voice_picker is None:
            return

        controller = self.controller
        snapshot = getattr(controller, "market_chat_voice_state", lambda: {})() or {}
        provider = str(snapshot.get("recognition_provider") or snapshot.get("provider") or "windows").strip().lower() or "windows"
        output_provider = str(snapshot.get("output_provider") or "windows").strip().lower() or "windows"
        voice_name = str(snapshot.get("voice_name") or "").strip()
        voices = list(getattr(window, "_market_chat_voice_choices", []) or [])

        window._market_chat_voice_controls_updating = True
        try:
            provider_picker.blockSignals(True)
            provider_picker.clear()
            for key, label in getattr(controller, "market_chat_voice_provider_choices", lambda: [])():
                provider_picker.addItem(str(label), str(key))
            provider_index = provider_picker.findData(provider)
            provider_picker.setCurrentIndex(provider_index if provider_index >= 0 else 0)
            provider_picker.blockSignals(False)

            output_picker.blockSignals(True)
            output_picker.clear()
            for key, label in getattr(controller, "market_chat_voice_output_provider_choices", lambda: [])():
                output_picker.addItem(str(label), str(key))
            output_index = output_picker.findData(output_provider)
            output_picker.setCurrentIndex(output_index if output_index >= 0 else 0)
            output_picker.blockSignals(False)

            voice_picker.blockSignals(True)
            voice_picker.clear()
            if output_provider == "windows":
                voice_picker.addItem("System Default", "")
            for voice in voices:
                voice_picker.addItem(str(voice), str(voice))
            if voice_name and voice_picker.findData(voice_name) < 0:
                voice_picker.addItem(f"{voice_name} (saved)", voice_name)
            voice_index = voice_picker.findData(voice_name)
            voice_picker.setCurrentIndex(voice_index if voice_index >= 0 else 0)
            voice_picker.blockSignals(False)
        finally:
            window._market_chat_voice_controls_updating = False

        if voice_meta is not None:
            voice_meta.setText(self._market_chat_voice_state_text(window))

    async def _refresh_market_chat_voice_choices_async(self, window, announce=False):
        if not self._is_qt_object_alive(window):
            return

        snapshot = getattr(self.controller, "market_chat_voice_state", lambda: {})() or {}
        output_provider = str(snapshot.get("output_provider") or "windows").strip().lower() or "windows"
        try:
            voices = await getattr(self.controller, "market_chat_list_voices", lambda *_args, **_kwargs: [])(output_provider)
            provider_label = "OpenAI" if output_provider == "openai" else "Windows"
            message = (
                f"Loaded {len(voices)} {provider_label} voice{'s' if len(voices) != 1 else ''}."
                if announce
                else None
            )
        except Exception as exc:
            voices = []
            message = f"Voice list refresh failed: {exc}"

        if not self._is_qt_object_alive(window):
            return

        window._market_chat_loading_voices = False
        window._market_chat_voice_choices = list(voices or [])
        self._populate_market_chat_voice_controls(window)
        self._refresh_market_chat_window(window, status_message=message)

    def _refresh_market_chat_voice_choices(self, window=None, announce=False):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_loading_voices", False):
            return

        window._market_chat_loading_voices = True
        snapshot = getattr(self.controller, "market_chat_voice_state", lambda: {})() or {}
        output_provider = str(snapshot.get("output_provider") or "windows").strip().lower() or "windows"
        provider_label = "OpenAI" if output_provider == "openai" else "installed"
        self._refresh_market_chat_window(window, status_message=f"Loading {provider_label} voices...")
        runner = self._refresh_market_chat_voice_choices_async(window, announce=announce)
        task_factory = getattr(self.controller, "_create_task", None)
        if callable(task_factory):
            window._market_chat_voice_choices_task = task_factory(runner, "market_chat_voice_choices")
        else:
            window._market_chat_voice_choices_task = asyncio.create_task(runner)

    def _set_market_chat_voice_provider(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_voice_controls_updating", False):
            return

        provider_picker = getattr(window, "_market_chat_provider_picker", None)
        if provider_picker is None:
            return
        provider = str(provider_picker.currentData() or provider_picker.currentText() or "windows").strip().lower() or "windows"
        resolved = getattr(self.controller, "set_market_chat_voice_provider", lambda value: value)(provider)
        self._populate_market_chat_voice_controls(window)
        self._refresh_market_chat_window(
            window,
            status_message=(
                "Google voice recognition selected."
                if resolved == "google"
                else "Windows voice recognition selected."
            ),
        )

    def _set_market_chat_voice_output_provider(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_voice_controls_updating", False):
            return

        output_picker = getattr(window, "_market_chat_output_picker", None)
        if output_picker is None:
            return
        provider = str(output_picker.currentData() or output_picker.currentText() or "windows").strip().lower() or "windows"
        resolved = getattr(self.controller, "set_market_chat_voice_output_provider", lambda value: value)(provider)
        window._market_chat_voice_choices = []
        self._populate_market_chat_voice_controls(window)
        self._refresh_market_chat_voice_choices(window, announce=False)
        snapshot = getattr(self.controller, "market_chat_voice_state", lambda: {})() or {}
        effective_output = str(snapshot.get("effective_output_provider") or resolved or "windows").strip().lower() or "windows"
        if provider == "openai" and effective_output == "windows":
            status_message = "OpenAI speech selected. Windows speech will be used until an OpenAI API key is configured."
        else:
            status_message = (
                "OpenAI speech selected."
                if resolved == "openai"
                else "Windows speech selected."
            )
        self._refresh_market_chat_window(
            window,
            status_message=status_message,
        )

    def _set_market_chat_voice(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_voice_controls_updating", False):
            return

        voice_picker = getattr(window, "_market_chat_voice_picker", None)
        if voice_picker is None:
            return
        voice_name = str(voice_picker.currentData() or "").strip()
        snapshot = getattr(self.controller, "market_chat_voice_state", lambda: {})() or {}
        output_provider = str(snapshot.get("output_provider") or "windows").strip().lower() or "windows"
        getattr(self.controller, "set_market_chat_voice", lambda value, _provider=None: value)(voice_name, output_provider)
        self._populate_market_chat_voice_controls(window)
        self._refresh_market_chat_window(
            window,
            status_message=f"Voice changed to {voice_name or 'System Default'}.",
        )

    async def _listen_market_chat_async(self, window):
        controller = self.controller
        if not getattr(controller, "market_chat_voice_input_available", lambda: False)():
            self._refresh_market_chat_window(window, status_message="Voice input is not available on this system.")
            return

        window._market_chat_voice_busy = True
        window._market_chat_voice_mode = "listen"
        window._market_chat_status_message = "Listening for your question..."
        self._refresh_market_chat_window(window)
        try:
            result = await controller.market_chat_listen(timeout_seconds=8)
        except Exception as exc:
            result = {"ok": False, "message": f"Voice listening failed: {exc}", "text": ""}

        window._market_chat_voice_busy = False
        window._market_chat_voice_mode = ""
        text = str(result.get("text", "") or "").strip()
        if not result.get("ok") or not text:
            self._refresh_market_chat_window(window, status_message=result.get("message") or "No speech was detected.")
            return

        input_box = getattr(window, "_market_chat_input", None)
        if input_box is not None:
            input_box.setPlainText(text)
        self._refresh_market_chat_window(window, status_message=f"Voice captured: {text}")
        self._submit_market_chat_prompt(text, window)

    def _listen_market_chat(self, window=None):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_busy", False) or getattr(window, "_market_chat_voice_busy", False):
            return
        runner = self._listen_market_chat_async(window)
        task_factory = getattr(self.controller, "_create_task", None)
        if callable(task_factory):
            window._market_chat_voice_task = task_factory(runner, "market_chat_listen")
        else:
            window._market_chat_voice_task = asyncio.create_task(runner)

    async def _speak_market_chat_reply_async(self, window, text):
        controller = self.controller
        if not getattr(controller, "market_chat_voice_output_available", lambda: False)():
            self._refresh_market_chat_window(window, status_message="Voice playback is not available on this system.")
            return

        message = str(text or "").strip()
        if not message:
            self._refresh_market_chat_window(window, status_message="No assistant reply is available to speak yet.")
            return

        window._market_chat_voice_busy = True
        window._market_chat_voice_mode = "speak"
        window._market_chat_status_message = "Speaking Sopotek Pilot reply..."
        self._refresh_market_chat_window(window)
        try:
            result = await controller.market_chat_speak(message)
        except Exception as exc:
            result = {"ok": False, "message": f"Voice playback failed: {exc}"}

        window._market_chat_voice_busy = False
        window._market_chat_voice_mode = ""
        self._refresh_market_chat_window(window, status_message=result.get("message") or "Voice playback finished.")

    def _speak_market_chat_reply(self, window=None, latest_text=None, automatic=False):
        window = window or self.detached_tool_windows.get("market_chatgpt")
        if not self._is_qt_object_alive(window):
            return
        if getattr(window, "_market_chat_busy", False) or getattr(window, "_market_chat_voice_busy", False):
            return
        message = str(latest_text or self._latest_market_chat_reply(window) or "").strip()
        if not message:
            if not automatic:
                self._refresh_market_chat_window(window, status_message="No assistant reply is available to speak yet.")
            return
        runner = self._speak_market_chat_reply_async(window, message)
        task_factory = getattr(self.controller, "_create_task", None)
        if callable(task_factory):
            window._market_chat_voice_task = task_factory(runner, "market_chat_speak")
        else:
            window._market_chat_voice_task = asyncio.create_task(runner)

    def _open_market_chat_window(self):
        window = self._get_or_create_tool_window(
            "market_chatgpt",
            "Sopotek Pilot",
            width=980,
            height=720,
        )
        window.setMinimumSize(760, 620)

        if getattr(window, "_market_chat_transcript", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            hero, _, _, _ = self._build_tool_window_hero(
                "Sopotek Pilot",
                "Ask about the app, market context, balances, profitability, recommendations, behavior guard, screenshots, broker positions, and explicit trade commands.",
                meta="Portfolio copilot | Voice control | Trade confirmation workflow",
            )
            layout.addWidget(hero)

            intro = QLabel(
                "Use Sopotek Pilot to ask about the app, market context, balances, equity, profitability, performance, recommendations, behavior guard, news, Telegram management, screenshots, broker position analysis, and explicit trade commands. Type 'show commands' at any time for the control list."
            )
            intro.setWordWrap(True)
            intro.setObjectName("tool_window_section_hint")
            layout.addWidget(intro)

            status = QLabel("Ready. Ask about the app, market, balances, broker positions, screenshots, or type 'show commands' for app controls.")
            status.setWordWrap(True)
            status.setObjectName("tool_window_summary_card")
            layout.addWidget(status)

            layout.addWidget(self._build_tool_window_section_label("Quick Prompts"))
            prompt_scroll = QScrollArea()
            prompt_scroll.setWidgetResizable(True)
            prompt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            prompt_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            prompt_scroll.setFrameShape(QFrame.Shape.NoFrame)
            prompt_scroll.setMaximumHeight(72)
            prompt_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            prompt_container = QWidget()
            prompt_row = QHBoxLayout(prompt_container)
            prompt_row.setContentsMargins(0, 0, 0, 0)
            prompt_row.setSpacing(8)
            for prompt in self._market_chat_quick_prompts():
                btn = QPushButton(prompt)
                btn.setStyleSheet(self._tool_window_chip_button_style())
                btn.clicked.connect(lambda checked=False, text=prompt: self._submit_market_chat_prompt(text, window))
                prompt_row.addWidget(btn)
            prompt_row.addStretch(1)
            prompt_scroll.setWidget(prompt_container)
            layout.addWidget(prompt_scroll)

            transcript = QTextBrowser()
            transcript.setOpenExternalLinks(False)
            transcript.setMinimumHeight(280)
            transcript.setStyleSheet(self._tool_window_text_browser_style())
            layout.addWidget(transcript, 1)

            input_box = QTextEdit()
            input_box.setPlaceholderText(
                "Ask anything about the app, the market, balances, broker positions, equity, profitability, recommendations, Telegram, screenshots, or type 'show commands'. Trade example: trade buy EUR/USD amount 1000 confirm"
            )
            input_box.setMinimumHeight(96)
            input_box.setMaximumHeight(110)
            input_box.setStyleSheet(self._tool_window_input_style())
            layout.addWidget(input_box)

            controls_frame = QFrame()
            controls_frame.setObjectName("tool_window_hero")
            controls_frame_layout = QVBoxLayout(controls_frame)
            controls_frame_layout.setContentsMargins(14, 12, 14, 12)
            controls_frame_layout.setSpacing(10)
            controls_frame_layout.addWidget(self._build_tool_window_section_label("Voice And Command Controls"))

            controls = QGridLayout()
            controls.setHorizontalSpacing(8)
            controls.setVerticalSpacing(8)
            listen_btn = QPushButton("Listen")
            listen_btn.setStyleSheet(self._action_button_style())
            speak_btn = QPushButton("Speak Reply")
            speak_btn.setStyleSheet(self._action_button_style())
            auto_speak_btn = QPushButton("Auto Speak")
            auto_speak_btn.setStyleSheet(self._action_button_style())
            auto_speak_btn.setCheckable(True)
            auto_speak_enabled = str(
                self.settings.value("market_chat/auto_speak", "false") or "false"
            ).strip().lower() in {"1", "true", "yes", "on"}
            auto_speak_btn.setChecked(auto_speak_enabled)
            provider_picker = QComboBox()
            provider_picker.setMinimumWidth(130)
            output_picker = QComboBox()
            output_picker.setMinimumWidth(130)
            voice_picker = QComboBox()
            voice_picker.setMinimumWidth(230)
            refresh_voices_btn = QPushButton("Refresh Voices")
            refresh_voices_btn.setStyleSheet(self._action_button_style())
            send_btn = QPushButton("Send")
            send_btn.setStyleSheet(self._action_button_style())
            clear_btn = QPushButton("Clear Chat")
            clear_btn.setStyleSheet(self._action_button_style())
            listen_btn.clicked.connect(lambda: self._listen_market_chat(window))
            speak_btn.clicked.connect(lambda: self._speak_market_chat_reply(window))
            auto_speak_btn.toggled.connect(lambda checked: self._set_market_chat_auto_speak(checked, window))
            provider_picker.currentIndexChanged.connect(lambda _index: self._set_market_chat_voice_provider(window))
            output_picker.currentIndexChanged.connect(lambda _index: self._set_market_chat_voice_output_provider(window))
            voice_picker.currentIndexChanged.connect(lambda _index: self._set_market_chat_voice(window))
            refresh_voices_btn.clicked.connect(lambda: self._refresh_market_chat_voice_choices(window, announce=True))
            send_btn.clicked.connect(lambda: self._submit_market_chat_prompt(window=window))
            clear_btn.clicked.connect(lambda: self._clear_market_chat(window))
            controls.addWidget(listen_btn, 0, 0)
            controls.addWidget(speak_btn, 0, 1)
            controls.addWidget(auto_speak_btn, 0, 2)
            controls.addWidget(clear_btn, 0, 3)
            controls.addWidget(send_btn, 0, 4)
            controls.addWidget(QLabel("Recognition"), 1, 0)
            controls.addWidget(provider_picker, 1, 1)
            controls.addWidget(QLabel("Speech"), 1, 2)
            controls.addWidget(output_picker, 1, 3)
            controls.addWidget(refresh_voices_btn, 1, 4)
            controls.addWidget(QLabel("Voice"), 2, 0)
            controls.addWidget(voice_picker, 2, 1, 1, 4)
            controls.setColumnStretch(1, 1)
            controls.setColumnStretch(3, 1)
            controls.setColumnStretch(4, 1)
            controls_frame_layout.addLayout(controls)

            voice_meta = QLabel("")
            voice_meta.setWordWrap(True)
            voice_meta.setObjectName("tool_window_section_hint")
            controls_frame_layout.addWidget(voice_meta)
            layout.addWidget(controls_frame)

            confirm_panel = QFrame()
            confirm_panel.setVisible(False)
            confirm_panel.setStyleSheet(
                "QFrame { background-color: #1f1712; border: 1px solid #8b5a2b; border-radius: 12px; }"
                "QLabel { color: #ffe2bb; font-weight: 600; }"
            )
            confirm_layout = QHBoxLayout(confirm_panel)
            confirm_layout.setContentsMargins(12, 10, 12, 10)
            confirm_layout.setSpacing(10)
            confirm_label = QLabel("")
            confirm_label.setWordWrap(True)
            confirm_btn = QPushButton("Confirm Action")
            cancel_btn = QPushButton("Cancel Action")
            confirm_btn.setStyleSheet(
                "QPushButton { background-color:#2f6f44; color:#eafff0; border:1px solid #4ba66e; border-radius:10px; padding:8px 12px; font-weight:700; }"
                "QPushButton:hover { background-color:#3d8957; }"
            )
            cancel_btn.setStyleSheet(
                "QPushButton { background-color:#4a1c22; color:#ffe2e5; border:1px solid #b05f6b; border-radius:10px; padding:8px 12px; font-weight:700; }"
                "QPushButton:hover { background-color:#61252d; }"
            )
            confirm_btn.clicked.connect(lambda: self._confirm_market_chat_action(window))
            cancel_btn.clicked.connect(lambda: self._cancel_market_chat_action(window))
            confirm_layout.addWidget(confirm_label, 1)
            confirm_layout.addWidget(confirm_btn)
            confirm_layout.addWidget(cancel_btn)
            layout.addWidget(confirm_panel)

            input_box.textChanged.connect(lambda: self._refresh_market_chat_window(window))

            window.setCentralWidget(container)
            window._market_chat_transcript = transcript
            window._market_chat_status = status
            window._market_chat_input = input_box
            window._market_chat_send_btn = send_btn
            window._market_chat_clear_btn = clear_btn
            window._market_chat_listen_btn = listen_btn
            window._market_chat_speak_btn = speak_btn
            window._market_chat_auto_speak_btn = auto_speak_btn
            window._market_chat_provider_picker = provider_picker
            window._market_chat_output_picker = output_picker
            window._market_chat_voice_picker = voice_picker
            window._market_chat_refresh_voices_btn = refresh_voices_btn
            window._market_chat_voice_meta = voice_meta
            window._market_chat_confirm_panel = confirm_panel
            window._market_chat_confirm_label = confirm_label
            window._market_chat_confirm_btn = confirm_btn
            window._market_chat_cancel_btn = cancel_btn
            window._market_chat_history = []
            window._market_chat_busy = False
            window._market_chat_voice_busy = False
            window._market_chat_voice_mode = ""
            window._market_chat_voice_controls_updating = False
            window._market_chat_loading_voices = False
            window._market_chat_voice_choices = []
            window._market_chat_status_message = (
                "Ready. Speak or type a question about the app, market, balances, broker positions, screenshots, or type 'show commands' for app controls."
                if getattr(self.controller, "market_chat_voice_available", lambda: False)()
                else status.text()
            )
            self._populate_market_chat_voice_controls(window)
            self._refresh_market_chat_voice_choices(window)

        self._refresh_market_chat_window(window)
        window.show()
        window.adjustSize()
        if window.width() < 900 or window.height() < 680:
            window.resize(max(window.width(), 900), max(window.height(), 680))
        window.raise_()
        window.activateWindow()

    def _refresh_recommendations_window(self):
        window = self.detached_tool_windows.get("trade_recommendations")
        if window is None:
            return
        if not self._is_qt_object_alive(window):
            self.detached_tool_windows.pop("trade_recommendations", None)
            return
        self._populate_recommendations_window(window)

    def _populate_recommendations_window(self, window):
        table = getattr(window, "_recommendations_table", None)
        summary = getattr(window, "_recommendations_summary", None)
        details = getattr(window, "_recommendations_details", None)
        if table is None or summary is None or details is None:
            return

        rows = self._recommendation_rows()
        selected_symbol = str(getattr(window, "_selected_symbol", "") or "").upper()

        table.setRowCount(len(rows))
        selected_row = -1
        for row, item in enumerate(rows):
            reason_text = str(item.get("reason", "") or "Reason not found in runtime data.")
            compact_reason = reason_text if len(reason_text) <= 72 else f"{reason_text[:69]}..."
            values = [
                item.get("symbol", ""),
                str(item.get("signal", "") or ""),
                f"{float(item.get('confidence', 0.0) or 0.0):.2f}",
                str(item.get("strategy", "") or ""),
                str(item.get("regime", "") or ""),
                compact_reason,
                str(item.get("timestamp", "") or ""),
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
            if str(item.get("symbol", "")).upper() == selected_symbol:
                selected_row = row

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        summary.setText(self._recommendation_summary_text(rows))

        if rows:
            if selected_row < 0:
                selected_row = 0
                window._selected_symbol = str(rows[0].get("symbol", "") or "")
            table.selectRow(selected_row)
            details.setHtml(self._recommendation_details_html(rows[selected_row]))
        else:
            window._selected_symbol = ""
            details.setHtml(self._recommendation_details_html(None))

    def _update_recommendation_details(self, window):
        if window is None or not self._is_qt_object_alive(window):
            return
        table = getattr(window, "_recommendations_table", None)
        details = getattr(window, "_recommendations_details", None)
        if table is None or details is None:
            return
        row = table.currentRow()
        if row < 0:
            details.setHtml(self._recommendation_details_html(None))
            return
        symbol_item = table.item(row, 0)
        symbol = str(symbol_item.text() if symbol_item is not None else "").upper()
        window._selected_symbol = symbol
        details.setHtml(self._recommendation_details_html(self._recommendation_records.get(symbol)))

    def _open_recommendations_window(self):
        window = self._get_or_create_tool_window(
            "trade_recommendations",
            "Trade Recommendations",
            width=1080,
            height=640,
        )

        if getattr(window, "_recommendations_table", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            hero, _, _, _ = self._build_tool_window_hero(
                "Trade Recommendations",
                "Review the symbols currently favored by the strategy engine and AI monitor, then open any idea to inspect the rationale before acting.",
                meta="Signal queue | Confidence ranking | Regime context | Explainability",
            )
            layout.addWidget(hero)

            intro = QLabel(
                "Review the symbols currently recommended by the strategy engine and AI monitor, with the reason behind each trade idea."
            )
            intro.setWordWrap(True)
            intro.setObjectName("tool_window_section_hint")
            layout.addWidget(intro)

            summary = QLabel()
            summary.setWordWrap(True)
            summary.setObjectName("tool_window_summary_card")
            layout.addWidget(summary)

            actions = QHBoxLayout()
            refresh_btn = QPushButton("Refresh Queue")
            refresh_btn.setStyleSheet(self._action_button_style())
            refresh_btn.clicked.connect(lambda: self._populate_recommendations_window(window))
            pilot_btn = QPushButton("Open Sopotek Pilot")
            pilot_btn.setStyleSheet(self._action_button_style())
            pilot_btn.clicked.connect(self._open_market_chat_window)
            actions.addWidget(refresh_btn)
            actions.addWidget(pilot_btn)
            actions.addStretch()
            layout.addLayout(actions)

            table = QTableWidget()
            table.setAlternatingRowColors(True)
            table.setColumnCount(7)
            table.setHorizontalHeaderLabels(
                ["Symbol", "Action", "Confidence", "Source", "Regime", "Why", "Time"]
            )
            layout.addWidget(table)

            details = QTextBrowser()
            details.setStyleSheet(self._tool_window_text_browser_style())
            layout.addWidget(details)

            window.setCentralWidget(container)
            window._recommendations_summary = summary
            window._recommendations_refresh_btn = refresh_btn
            window._recommendations_pilot_btn = pilot_btn
            window._recommendations_table = table
            window._recommendations_details = details
            window._selected_symbol = ""

            table.itemSelectionChanged.connect(lambda: self._update_recommendation_details(window))

            sync_timer = QTimer(window)
            sync_timer.timeout.connect(lambda: self._populate_recommendations_window(window))
            sync_timer.start(1200)
            window._sync_timer = sync_timer

        self._populate_recommendations_window(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _create_regime_panel(self):

        dock = QDockWidget("Market Regime", self)

        container = QWidget()
        layout = QVBoxLayout()

        self.regime_label = QLabel("Regime: UNKNOWN")
        self.regime_label.setStyleSheet("font-size: 18px;")

        layout.addWidget(self.regime_label)

        container.setLayout(layout)

        dock.setWidget(container)
        self._apply_dock_widget_chrome(dock)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _update_regime(self, regime):

        colors = {
            "TREND_UP": "green",
            "TREND_DOWN": "red",
            "RANGE": "yellow",
            "HIGH_VOL": "orange"
        }

        color = colors.get(regime, "white")

        self.regime_label.setText(f"Regime: {regime}")
        self.regime_label.setStyleSheet(
            f"font-size:18px;color:{color}"
        )

    def _create_portfolio_exposure_graph(self):

        dock = QDockWidget("Portfolio Exposure", self)

        self.exposure_chart = pg.PlotWidget()

        self.exposure_bars = pg.BarGraphItem(
            x=[],
            height=[],
            width=0.6
        )

        self.exposure_chart.addItem(self.exposure_bars)

        dock.setWidget(self.exposure_chart)
        self._apply_dock_widget_chrome(dock)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _create_model_confidence(self):

        dock = QDockWidget("Model Confidence", self)

        self.confidence_plot = pg.PlotWidget()

        self.confidence_curve = self.confidence_plot.plot(
            pen="cyan"
        )



        dock.setWidget(self.confidence_plot)
        self._apply_dock_widget_chrome(dock)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _update_confidence(self, confidence):

        self.confidence_data.append(confidence)

        if len(self.confidence_data) > 200:
            self.confidence_data.pop(0)

        self.confidence_curve.setData(self.confidence_data)

    def _update_portfolio_exposure(self):
        positions = self._active_positions_snapshot()
        if not positions:
            return

        symbols = []
        values = []

        for pos in positions:
            symbols.append(pos.get("symbol", "-"))
            values.append(float(pos.get("value", 0) or 0))

        x = list(range(len(symbols)))

        self.exposure_bars.setOpts(
            x=x,
            height=values
        )

    def _set_risk_heatmap_status(self, message, tone="muted"):
        set_risk_heatmap_status(self, message, tone=tone)

    def _create_risk_heatmap(self):
        create_risk_heatmap_panel(self)
        self._apply_dock_widget_chrome(getattr(self, "risk_heatmap_dock", None))

    def _risk_heatmap_positions_snapshot(self):
        return risk_heatmap_positions_snapshot(self)

    def _update_risk_heatmap(self):
        update_risk_heatmap(self)




# ==========================================================
# TERMINAL HOTFIX OVERRIDES
# ==========================================================
# These overrides stabilize runtime paths without requiring a full terminal rewrite.


def _empty_candles_frame(pd_module):
    return pd_module.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])


def _normalize_candle_timestamps(pd_module, series):
    if pd_module.api.types.is_numeric_dtype(series):
        numeric = pd_module.to_numeric(series, errors="coerce")
        median = numeric.abs().median()
        unit = "ms" if pd_module.notna(median) and median > 1e11 else "s"
        return pd_module.to_datetime(numeric, unit=unit, errors="coerce", utc=True)

    return pd_module.to_datetime(series, errors="coerce", utc=True)


def candles_to_df(df):
    """Normalize and sanitize OHLCV rows before chart/backtest usage."""
    try:
        import pandas as pd
    except Exception:
        pd = None

    if df is None:
        return _empty_candles_frame(pd) if pd else []

    if pd is not None:
        try:
            frame = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
            if frame.empty:
                return _empty_candles_frame(pd)

            required = ["timestamp", "open", "high", "low", "close", "volume"]

            if not set(required).issubset(frame.columns):
                if frame.shape[1] < 6:
                    return _empty_candles_frame(pd)
                frame = frame.iloc[:, :6].copy()
                frame.columns = required
            else:
                frame = frame.loc[:, required].copy()

            frame["timestamp"] = _normalize_candle_timestamps(pd, frame["timestamp"])

            for column in ["open", "high", "low", "close", "volume"]:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

            frame.replace([float("inf"), float("-inf")], pd.NA, inplace=True)
            frame.dropna(subset=["timestamp", "open", "high", "low", "close"], inplace=True)
            if frame.empty:
                return _empty_candles_frame(pd)

            # Repair inconsistent broker rows so chart bounds stay sane.
            price_bounds = frame[["open", "high", "low", "close"]]
            frame["high"] = price_bounds.max(axis=1)
            frame["low"] = price_bounds.min(axis=1)
            frame["volume"] = frame["volume"].fillna(0.0).clip(lower=0.0)

            frame.sort_values("timestamp", inplace=True)
            frame.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
            frame.reset_index(drop=True, inplace=True)
            return frame
        except Exception:
            return _empty_candles_frame(pd)

    return df


async def _hotfix_prepare_backtest_context(self):
    return await _hotfix_prepare_backtest_context_with_selection(self)


def _hotfix_backtest_symbol_candidates(self):
    candidates = []

    chart = None
    try:
        chart = self._current_chart_widget()
    except Exception:
        chart = None

    for value in [
        getattr(chart, "symbol", None),
        getattr(self, "symbol", None),
        getattr(getattr(self, "symbol_picker", None), "currentText", lambda: "")(),
    ]:
        text = str(value or "").strip()
        if text and text not in candidates:
            candidates.append(text)

    for symbol in list(getattr(self.controller, "symbols", []) or []):
        text = str(symbol or "").strip()
        if text and text not in candidates:
            candidates.append(text)

    return candidates


def _hotfix_backtest_timeframe_candidates(self):
    candidates = []
    for timeframe in list(getattr(self, "timeframe_buttons", {}).keys()):
        text = str(timeframe or "").strip()
        if text and text not in candidates:
            candidates.append(text)
    for timeframe in ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1mn"]:
        if timeframe not in candidates:
            candidates.append(timeframe)
    return candidates


def _hotfix_qdate_from_value(value):
    if isinstance(value, QDate) and value.isValid():
        return value
    if isinstance(value, datetime):
        return QDate(value.year, value.month, value.day)
    if isinstance(value, str):
        parsed = QDate.fromString(value, "yyyy-MM-dd")
        if parsed.isValid():
            return parsed
    return None


def _hotfix_qdate_to_text(value):
    qdate = _hotfix_qdate_from_value(value)
    return qdate.toString("yyyy-MM-dd") if qdate is not None else ""


def _hotfix_qdate_to_utc_boundary_text(value, *, end_of_day=False):
    qdate = _hotfix_qdate_from_value(value)
    if qdate is None or not qdate.isValid():
        return None
    suffix = "23:59:59.999999+00:00" if end_of_day else "00:00:00+00:00"
    return f"{qdate.toString('yyyy-MM-dd')}T{suffix}"


def _hotfix_clamp_qdate(value, minimum, maximum):
    if value is None or not value.isValid():
        return minimum
    if minimum is not None and value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def _hotfix_backtest_requested_range_text(window=None, context=None):
    context = context or {}
    start_widget = getattr(window, "_backtest_start_date", None) if window is not None else None
    end_widget = getattr(window, "_backtest_end_date", None) if window is not None else None
    start_value = start_widget.date() if start_widget is not None else _hotfix_qdate_from_value(context.get("start_date"))
    end_value = end_widget.date() if end_widget is not None else _hotfix_qdate_from_value(context.get("end_date"))
    if start_value is None or end_value is None or not start_value.isValid() or not end_value.isValid():
        return "-"
    return f"{start_value.toString('yyyy-MM-dd')} -> {end_value.toString('yyyy-MM-dd')}"


def _hotfix_backtest_requested_limit(window=None, context=None, fallback=None):
    context = context or {}
    backtest_cap = 1000000
    if window is not None:
        terminal = getattr(window, "_terminal_owner", None)
        controller = getattr(terminal, "controller", None) if terminal is not None else None
        backtest_cap = int(getattr(controller, "MAX_BACKTEST_HISTORY_LIMIT", backtest_cap) or backtest_cap)
    widget = getattr(window, "_backtest_history_limit", None) if window is not None else None
    if widget is not None:
        try:
            return max(1, min(int(widget.value()), backtest_cap))
        except Exception:
            pass
    value = context.get("history_limit", fallback if fallback is not None else 50000)
    try:
        return max(1, min(int(value), backtest_cap))
    except Exception:
        fallback_value = fallback if fallback is not None else 50000
        return max(1, min(int(fallback_value), backtest_cap))


def _hotfix_backtest_apply_history_limit(frame, requested_limit):
    frame = candles_to_df(frame)
    if frame is None or getattr(frame, "empty", True):
        return frame
    try:
        limit = max(1, int(requested_limit or len(frame)))
    except Exception:
        limit = len(frame)
    if len(frame) <= limit:
        return frame
    limited = frame.tail(limit).copy()
    limited.reset_index(drop=True, inplace=True)
    return limited


def _hotfix_timeframe_seconds(timeframe):
    normalized = str(timeframe or "").strip().lower()
    mapping = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "45m": 2700,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
        "3d": 259200,
        "1w": 604800,
        "1mn": 2592000,
    }
    return mapping.get(normalized)


def _hotfix_backtest_required_history_limit(self, timeframe, start_date=None, end_date=None, requested_limit=None):
    default_limit = int(requested_limit or getattr(self.controller, "limit", 1000) or 1000)
    step_seconds = _hotfix_timeframe_seconds(timeframe)
    start_qdate = _hotfix_qdate_from_value(start_date)
    end_qdate = _hotfix_qdate_from_value(end_date)

    required_limit = default_limit
    if step_seconds and start_qdate is not None and end_qdate is not None and start_qdate.isValid() and end_qdate.isValid():
        if end_qdate < start_qdate:
            end_qdate = start_qdate
        start_ts = pd.Timestamp(f"{start_qdate.toString('yyyy-MM-dd')} 00:00:00", tz="UTC")
        end_ts = pd.Timestamp(f"{end_qdate.toString('yyyy-MM-dd')} 23:59:59", tz="UTC")
        total_seconds = max((end_ts - start_ts).total_seconds(), float(step_seconds))
        required_bars = int(np.ceil(total_seconds / float(step_seconds))) + 64
        required_limit = max(default_limit, required_bars)

    resolver = getattr(self.controller, "_resolve_backtest_history_limit", None)
    if not callable(resolver):
        resolver = getattr(self.controller, "_resolve_history_limit", None)
    if callable(resolver):
        try:
            return int(resolver(required_limit))
        except Exception:
            pass
    return max(100, min(int(required_limit), int(getattr(self.controller, "MAX_BACKTEST_HISTORY_LIMIT", 1000000) or 1000000)))


def _hotfix_backtest_frame_for_symbol(self, symbol, timeframe):
    buffers = getattr(self.controller, "candle_buffers", {})
    frame = None
    if hasattr(buffers, "get"):
        frame = (buffers.get(symbol) or {}).get(timeframe)
    return candles_to_df(frame)


def _hotfix_backtest_frame_covers_range(frame, start_date, end_date):
    frame = candles_to_df(frame)
    if frame is None or getattr(frame, "empty", True):
        return False

    start_qdate = _hotfix_qdate_from_value(start_date)
    end_qdate = _hotfix_qdate_from_value(end_date)
    if start_qdate is None or end_qdate is None or not start_qdate.isValid() or not end_qdate.isValid():
        return True

    try:
        min_ts = pd.Timestamp(frame.iloc[0]["timestamp"])
        max_ts = pd.Timestamp(frame.iloc[-1]["timestamp"])
    except Exception:
        return False

    if pd.isna(min_ts) or pd.isna(max_ts):
        return False

    try:
        min_day = min_ts.tz_convert("UTC").date() if min_ts.tzinfo is not None else min_ts.date()
        max_day = max_ts.tz_convert("UTC").date() if max_ts.tzinfo is not None else max_ts.date()
    except Exception:
        min_day = min_ts.date()
        max_day = max_ts.date()

    start_day = pd.Timestamp(f"{start_qdate.toString('yyyy-MM-dd')}").date()
    end_day = pd.Timestamp(f"{end_qdate.toString('yyyy-MM-dd')}").date()
    return bool(min_day <= start_day and max_day >= end_day)


def _hotfix_backtest_date_bounds(frame):
    frame = candles_to_df(frame)
    if frame is None or getattr(frame, "empty", True):
        return None, None
    try:
        start_ts = pd.Timestamp(frame.iloc[0]["timestamp"])
        end_ts = pd.Timestamp(frame.iloc[-1]["timestamp"])
    except Exception:
        return None, None
    if pd.isna(start_ts) or pd.isna(end_ts):
        return None, None
    return QDate(start_ts.year, start_ts.month, start_ts.day), QDate(end_ts.year, end_ts.month, end_ts.day)


def _hotfix_filter_backtest_frame_by_date(frame, start_date, end_date):
    frame = candles_to_df(frame)
    if frame is None or getattr(frame, "empty", True):
        return frame

    start_qdate = _hotfix_qdate_from_value(start_date)
    end_qdate = _hotfix_qdate_from_value(end_date)
    if start_qdate is None or end_qdate is None:
        return frame
    if end_qdate < start_qdate:
        end_qdate = start_qdate

    start_ts = pd.Timestamp(f"{start_qdate.toString('yyyy-MM-dd')} 00:00:00", tz="UTC")
    end_ts = pd.Timestamp(f"{end_qdate.toString('yyyy-MM-dd')} 00:00:00", tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    filtered = frame[(frame["timestamp"] >= start_ts) & (frame["timestamp"] <= end_ts)].copy()
    filtered.reset_index(drop=True, inplace=True)
    return filtered


def _hotfix_start_backtest_graph_animation(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    if window is None:
        return
    timer = getattr(window, "_backtest_graph_timer", None)
    if timer is not None and not timer.isActive():
        window._backtest_graph_phase = 0.0
        timer.start()


def _hotfix_stop_backtest_graph_animation(window, clear=False):
    if window is None:
        return
    timer = getattr(window, "_backtest_graph_timer", None)
    if timer is not None and timer.isActive():
        timer.stop()
    if clear:
        graph_curve = getattr(window, "_backtest_graph_curve", None)
        animation_curve = getattr(window, "_backtest_graph_animation_curve", None)
        if graph_curve is not None:
            graph_curve.setData([])
        if animation_curve is not None:
            animation_curve.setData([])


def _hotfix_tick_backtest_graph_animation(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    if window is None:
        return

    graph_curve = getattr(window, "_backtest_graph_curve", None)
    animation_curve = getattr(window, "_backtest_graph_animation_curve", None)
    if graph_curve is None or animation_curve is None:
        return

    equity_curve = list(getattr(getattr(self, "backtest_engine", None), "equity_curve", []) or [])
    if len(equity_curve) >= 2:
        graph_curve.setData(list(range(len(equity_curve))), equity_curve)
        animation_curve.setData([])
        return

    baseline = float(getattr(self.controller, "initial_capital", 10000) or 10000)
    amplitude = max(baseline * 0.003, 5.0)
    phase = float(getattr(window, "_backtest_graph_phase", 0.0) or 0.0)
    x_values = np.arange(60, dtype=float)
    y_values = baseline + np.linspace(0.0, amplitude * 2.5, num=60) + np.sin((x_values / 4.0) + phase) * amplitude
    window._backtest_graph_phase = phase + 0.35
    graph_curve.setData([])
    animation_curve.setData(x_values, y_values)


def _hotfix_refresh_backtest_selectors(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    if window is None:
        return

    symbol_picker = getattr(window, "_backtest_symbol_picker", None)
    strategy_picker = getattr(window, "_backtest_strategy_picker", None)
    timeframe_picker = getattr(window, "_backtest_timeframe_picker", None)
    start_date_edit = getattr(window, "_backtest_start_date", None)
    end_date_edit = getattr(window, "_backtest_end_date", None)
    if symbol_picker is None or strategy_picker is None or timeframe_picker is None:
        return

    current_symbol = str(symbol_picker.currentText()).strip()
    current_strategy = str(strategy_picker.currentText()).strip()
    current_timeframe = str(timeframe_picker.currentText()).strip()
    context = getattr(self, "_backtest_context", {}) or {}

    symbol_candidates = _hotfix_backtest_symbol_candidates(self)
    target_symbol = context.get("symbol") or current_symbol or (symbol_candidates[0] if symbol_candidates else "")
    target_strategy = Strategy.normalize_strategy_name(
        context.get("strategy_name")
        or current_strategy
        or getattr(self.controller, "strategy_name", None)
        or getattr(getattr(self.controller, "config", None), "strategy", "Trend Following")
    )
    timeframe_candidates = _hotfix_backtest_timeframe_candidates(self)
    target_timeframe = str(
        context.get("timeframe")
        or current_timeframe
        or getattr(self, "current_timeframe", getattr(self.controller, "time_frame", "1h"))
    ).strip()

    symbol_picker.blockSignals(True)
    symbol_picker.clear()
    for symbol in symbol_candidates:
        symbol_picker.addItem(symbol)
    if target_symbol and symbol_picker.findText(target_symbol) < 0:
        symbol_picker.addItem(target_symbol)
    if target_symbol:
        symbol_picker.setCurrentText(target_symbol)
    symbol_picker.blockSignals(False)

    self._populate_strategy_picker(strategy_picker, selected_strategy=target_strategy)

    timeframe_picker.blockSignals(True)
    timeframe_picker.clear()
    for name in timeframe_candidates:
        timeframe_picker.addItem(name)
    if target_timeframe and timeframe_picker.findText(target_timeframe) < 0:
        timeframe_picker.addItem(target_timeframe)
    timeframe_picker.setCurrentText(target_timeframe)
    timeframe_picker.blockSignals(False)


async def _hotfix_load_backtest_history(self, window=None, force=False):
    window = window or getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    if window is None:
        raise RuntimeError("Backtest workspace is not open.")
    if not getattr(self.controller, "broker", None):
        raise RuntimeError("Connect a broker before loading exchange history for backtesting.")
    if not hasattr(self.controller, "request_candle_data"):
        raise RuntimeError("This controller cannot fetch historical candles.")

    symbol_picker = getattr(window, "_backtest_symbol_picker", None)
    timeframe_picker = getattr(window, "_backtest_timeframe_picker", None)
    strategy_picker = getattr(window, "_backtest_strategy_picker", None)
    start_date_edit = getattr(window, "_backtest_start_date", 0)
    end_date_edit = getattr(window, "_backtest_end_date", datetime.now())
    history_limit_widget = getattr(window, "_backtest_history_limit", None)

    symbol = str(symbol_picker.currentText()).strip() if symbol_picker is not None else ""
    timeframe = str(timeframe_picker.currentText()).strip() if timeframe_picker is not None else getattr(self, "current_timeframe", "1h")
    strategy_name = str(strategy_picker.currentText()).strip() if strategy_picker is not None else ""
    start_date = start_date_edit.date() if start_date_edit is not None else None
    end_date = end_date_edit.date() if end_date_edit is not None else None
    requested_limit = _hotfix_backtest_requested_limit(
        window=window,
        context=getattr(self, "_backtest_context", {}) or {},
        fallback=getattr(self.controller, "limit", 50000),
    )

    limit = _hotfix_backtest_required_history_limit(
        self,
        timeframe,
        start_date=start_date,
        end_date=end_date,
        requested_limit=requested_limit,
    )
    requested_range = _hotfix_backtest_requested_range_text(window=window) or "-"
    self._append_backtest_journal(
        f"Loading exchange candles for {symbol} {timeframe} covering {requested_range} (fetch limit {limit}, target bars {requested_limit}).",
        "INFO",
    )
    await self.controller.request_candle_data(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        start_time=_hotfix_qdate_to_utc_boundary_text(start_date, end_of_day=False),
        end_time=_hotfix_qdate_to_utc_boundary_text(end_date, end_of_day=True),
    )

    context = await _hotfix_prepare_backtest_context_with_selection(
        self,
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
        force_history_refresh=force,
    )
    self._backtest_context = context
    self.results = None
    self.backtest_report = None
    loaded_bars = len(context.get("data") or [])
    self._append_backtest_journal(
        f"Loaded {loaded_bars} exchange candle bars for {symbol} {timeframe}.",
        "INFO",
    )
    _hotfix_refresh_backtest_selectors(self, window)
    self._refresh_backtest_window(window, message=f"Loaded {loaded_bars} exchange bars for {symbol} {timeframe}.")
    return context


async def _hotfix_load_backtest_history_runner(self, window=None, force=True):
    try:
        await _hotfix_load_backtest_history(self, window=window, force=force)
    except Exception as exc:
        self.system_console.log(f"Backtest history load failed: {exc}", "ERROR")
        self._append_backtest_journal(f"Exchange history load failed: {exc}", "ERROR")
        self._refresh_backtest_window(window, message=f"Backtest history load failed: {exc}")


def _hotfix_load_backtest_history_clicked(self):
    load_backtest_history_clicked(self)


def _hotfix_backtest_selection_changed(self):
    if getattr(self, "_backtest_running", False):
        return

    window = getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    if window is None:
        return

    symbol_picker = getattr(window, "_backtest_symbol_picker", None)
    strategy_picker = getattr(window, "_backtest_strategy_picker", None)
    timeframe_picker = getattr(window, "_backtest_timeframe_picker", None)
    start_date_edit = getattr(window, "_backtest_start_date", None)
    end_date_edit = getattr(window, "_backtest_end_date", None)
    history_limit_widget = getattr(window, "_backtest_history_limit", None)
    if symbol_picker is None or strategy_picker is None or timeframe_picker is None:
        return

    selected_symbol = str(symbol_picker.currentText()).strip()
    selected_strategy = Strategy.normalize_strategy_name(strategy_picker.currentText())
    selected_timeframe = str(timeframe_picker.currentText()).strip() or getattr(self, "current_timeframe", getattr(self.controller, "time_frame", "1h"))
    previous = getattr(self, "_backtest_context", {}) or {}
    timeframe = selected_timeframe
    selected_start_date = start_date_edit.date() if start_date_edit is not None else _hotfix_qdate_from_value(previous.get("start_date"))
    selected_end_date = end_date_edit.date() if end_date_edit is not None else _hotfix_qdate_from_value(previous.get("end_date"))
    selected_history_limit = _hotfix_backtest_requested_limit(
        window=window,
        context=previous,
        fallback=getattr(self.controller, "limit", 50000),
    )
    if selected_start_date is not None and selected_end_date is not None and selected_end_date < selected_start_date:
        selected_end_date = selected_start_date
        if end_date_edit is not None:
            end_date_edit.blockSignals(True)
            end_date_edit.setDate(selected_end_date)
            end_date_edit.blockSignals(False)

    dataset = _hotfix_backtest_frame_for_symbol(self, selected_symbol, timeframe)
    filtered_dataset = _hotfix_filter_backtest_frame_by_date(dataset, selected_start_date, selected_end_date)
    filtered_dataset = _hotfix_backtest_apply_history_limit(filtered_dataset, selected_history_limit)
    covers_range = _hotfix_backtest_frame_covers_range(dataset, selected_start_date, selected_end_date)

    selection_changed = (
        selected_symbol != str(previous.get("symbol") or "").strip()
        or selected_strategy != Strategy.normalize_strategy_name(previous.get("strategy_name"))
        or selected_timeframe != str(previous.get("timeframe") or "").strip()
        or _hotfix_qdate_to_text(selected_start_date) != str(previous.get("start_date") or "").strip()
        or _hotfix_qdate_to_text(selected_end_date) != str(previous.get("end_date") or "").strip()
        or int(selected_history_limit) != int(previous.get("history_limit") or getattr(self.controller, "limit", 50000))
    )

    self._backtest_context = {
        "symbol": selected_symbol,
        "timeframe": timeframe,
        "data": filtered_dataset.copy() if hasattr(filtered_dataset, "copy") else filtered_dataset,
        "strategy": previous.get("strategy"),
        "strategy_name": selected_strategy,
        "start_date": _hotfix_qdate_to_text(selected_start_date),
        "end_date": _hotfix_qdate_to_text(selected_end_date),
        "history_limit": int(selected_history_limit),
    }

    if selection_changed:
        self.results = None
        self.backtest_report = None

    info = "Selection updated. Start backtest when ready."
    if dataset is None or getattr(dataset, "empty", False):
        info = "Selection updated. Use Load Exchange Data or Start Backtest to fetch candles from the connected exchange."
    elif not covers_range:
        info = "Selection updated. Cached candles do not fully cover the selected date range. Load Exchange Data to refresh from the exchange."
    elif filtered_dataset is None or getattr(filtered_dataset, "empty", False):
        info = "Selection updated. No candles fall inside the selected date range."
    self._refresh_backtest_window(message=info)


async def _hotfix_prepare_backtest_context_with_selection(self, symbol=None, timeframe=None, strategy_name=None, force_history_refresh=False):
    chart = self._current_chart_widget()
    if chart is None and hasattr(self, "_iter_chart_widgets"):
        charts = self._iter_chart_widgets()
        chart = charts[0] if charts else None

    window = getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    symbol_picker = getattr(window, "_backtest_symbol_picker", None) if window is not None else None
    strategy_picker = getattr(window, "_backtest_strategy_picker", None) if window is not None else None
    start_date_edit = getattr(window, "_backtest_start_date", None) if window is not None else None
    end_date_edit = getattr(window, "_backtest_end_date", None) if window is not None else None

    selected_symbol = str(symbol or "").strip() or (str(symbol_picker.currentText()).strip() if symbol_picker is not None else "")
    selected_strategy = str(strategy_name or "").strip() or (str(strategy_picker.currentText()).strip() if strategy_picker is not None else "")
    context = getattr(self, "_backtest_context", {}) or {}
    selected_start_date = start_date_edit.date() if start_date_edit is not None else _hotfix_qdate_from_value(context.get("start_date"))
    selected_end_date = end_date_edit.date() if end_date_edit is not None else _hotfix_qdate_from_value(context.get("end_date"))
    selected_history_limit = _hotfix_backtest_requested_limit(
        window=window,
        context=context,
        fallback=getattr(self.controller, "limit", 50000),
    )

    symbol = selected_symbol or getattr(chart, "symbol", None) or getattr(self, "symbol", None)
    if not symbol:
        candidates = _hotfix_backtest_symbol_candidates(self)
        symbol = candidates[0] if candidates else None

    timeframe = str(timeframe or "").strip() or getattr(chart, "timeframe", None) or getattr(self, "current_timeframe", "1h")
    if not symbol:
        raise RuntimeError("No symbol is available for backtesting")

    strategy_source = None
    trading_system = getattr(self.controller, "trading_system", None)
    if trading_system is not None:
        strategy_source = getattr(trading_system, "strategy", None)
    if strategy_source is None:
        from strategy.strategy_registry import StrategyRegistry
        strategy_source = StrategyRegistry()

    buffers = getattr(self.controller, "candle_buffers", {})
    frame = None
    if hasattr(buffers, "get"):
        frame = (buffers.get(symbol) or {}).get(timeframe)
    needs_history_refresh = (
        force_history_refresh
        or frame is None
        or not _hotfix_backtest_frame_covers_range(frame, selected_start_date, selected_end_date)
    )
    if needs_history_refresh and hasattr(self.controller, "request_candle_data"):
        fetch_limit = _hotfix_backtest_required_history_limit(
            self,
            timeframe,
            start_date=selected_start_date,
            end_date=selected_end_date,
            requested_limit=selected_history_limit,
        )
        await self.controller.request_candle_data(
            symbol=symbol,
            timeframe=timeframe,
            limit=fetch_limit,
            start_time=_hotfix_qdate_to_utc_boundary_text(selected_start_date, end_of_day=False),
            end_time=_hotfix_qdate_to_utc_boundary_text(selected_end_date, end_of_day=True),
            history_scope="backtest",
        )
        frame = (getattr(self.controller, "candle_buffers", {}).get(symbol) or {}).get(timeframe)
    frame = candles_to_df(frame)
    if frame is None or getattr(frame, "empty", False):
        raise RuntimeError(f"No candle history available for {symbol} {timeframe}")
    minimum_date, maximum_date = _hotfix_backtest_date_bounds(frame)
    if selected_start_date is None:
        selected_start_date = minimum_date
    if selected_end_date is None:
        selected_end_date = maximum_date
    selected_start_date = _hotfix_clamp_qdate(selected_start_date, minimum_date, maximum_date)
    selected_end_date = _hotfix_clamp_qdate(selected_end_date, minimum_date, maximum_date)
    if selected_end_date is not None and selected_start_date is not None and selected_end_date < selected_start_date:
        selected_end_date = selected_start_date
    filtered_frame = _hotfix_filter_backtest_frame_by_date(frame, selected_start_date, selected_end_date)
    if filtered_frame is None or getattr(filtered_frame, "empty", False):
        requested_range = _hotfix_backtest_requested_range_text(
            context={"start_date": _hotfix_qdate_to_text(selected_start_date), "end_date": _hotfix_qdate_to_text(selected_end_date)}
        )
        raise RuntimeError(f"No candle history available for {symbol} {timeframe} inside {requested_range}")
    if start_date_edit is not None and end_date_edit is not None and minimum_date is not None and maximum_date is not None:
        start_date_edit.blockSignals(True)
        end_date_edit.blockSignals(True)
        start_date_edit.setMinimumDate(minimum_date)
        start_date_edit.setMaximumDate(maximum_date)
        end_date_edit.setMinimumDate(minimum_date)
        end_date_edit.setMaximumDate(maximum_date)
        start_date_edit.setDate(selected_start_date)
        end_date_edit.setDate(selected_end_date)
        start_date_edit.blockSignals(False)
        end_date_edit.blockSignals(False)

    strategy_name = Strategy.normalize_strategy_name(
        selected_strategy
        or getattr(self.controller, "strategy_name", None)
        or getattr(getattr(self.controller, "config", None), "strategy", None)
    )
    filtered_frame = _hotfix_backtest_apply_history_limit(filtered_frame, selected_history_limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data": filtered_frame.copy() if hasattr(filtered_frame, "copy") else filtered_frame,
        "strategy": strategy_source,
        "strategy_name": strategy_name,
        "start_date": _hotfix_qdate_to_text(selected_start_date),
        "end_date": _hotfix_qdate_to_text(selected_end_date),
        "history_limit": int(selected_history_limit),
    }


async def _hotfix_run_backtest_clicked(self):
    self._show_backtest_window()
    try:
        context = await _hotfix_prepare_backtest_context(self)

        self.backtest_engine = BacktestEngine(
            strategy=context["strategy"],
            simulator=Simulator(
                initial_balance=getattr(self.controller, "initial_capital", 10000)
            ),
        )
        self._backtest_context = context
        self.results = None
        self.backtest_report = None
        self._backtest_journal_lines = []
        self._backtest_running = False
        self._backtest_stop_requested = False
        self._backtest_stop_event = None
        self._backtest_task = None
        self._append_backtest_journal(
            f"Initialized strategy tester for {context['symbol']} {context['timeframe']} using {context.get('strategy_name') or 'Default'}."
        )
        _hotfix_refresh_backtest_selectors(self)
        self._refresh_backtest_window(message="Backtest engine initialized.")

    except Exception as e:
        self.system_console.log(f"Backtest initialization error: {e}")
        self._append_backtest_journal(f"Initialization failed: {e}", "ERROR")
        _hotfix_refresh_backtest_selectors(self)
        self._refresh_backtest_window(message=f"Backtest initialization error: {e}")


async def _hotfix_run_backtest_async(self, data, symbol, strategy_name, timeframe):
    try:
        self._append_backtest_journal(
            f"Starting backtest for {symbol} on {timeframe}.",
            "INFO",
        )
        self.results = await asyncio.to_thread(
            self.backtest_engine.run,
            data,
            symbol,
            strategy_name,
            self._backtest_stop_event,
        )
        self.backtest_report = ReportGenerator(
            trades=self.results,
            equity_history=getattr(self.backtest_engine, "equity_curve", []),
        ).generate()
        total_trades = len(self.results) if hasattr(self.results, "__len__") else 0
        if getattr(self, "_backtest_stop_requested", False):
            self.system_console.log("Backtest stopped.", "INFO")
            self._append_backtest_journal(
                f"Backtest stopped after {total_trades} trade rows and final equity {float(self.backtest_report.get('final_equity', 0.0) or 0.0):.2f}.",
                "WARN",
            )
            self._refresh_backtest_window(message="Backtest stopped.")
        else:
            self.system_console.log("Backtest completed.", "INFO")
            self._append_backtest_journal(
                f"Backtest completed with {total_trades} trade rows and final equity {float(self.backtest_report.get('final_equity', 0.0) or 0.0):.2f}.",
                "INFO",
            )
            self._refresh_backtest_window(message="Backtest completed.")

    except Exception as e:
        self.system_console.log(f"Backtest failed: {e}", "ERROR")
        self._append_backtest_journal(f"Backtest failed: {e}", "ERROR")
        self._refresh_backtest_window(message=f"Backtest failed: {e}")
    finally:
        _hotfix_stop_backtest_graph_animation(
            getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
        )
        self._backtest_running = False
        self._backtest_stop_event = None
        self._backtest_task = None
        self._refresh_backtest_window()


async def _hotfix_prepare_and_run_backtest(self):
    try:
        context = await _hotfix_prepare_backtest_context(self)
        self.backtest_engine = BacktestEngine(
            strategy=context["strategy"],
            simulator=Simulator(
                initial_balance=getattr(self.controller, "initial_capital", 10000)
            ),
        )
        self._backtest_context = context
        self.results = None
        self.backtest_report = None
        self._backtest_running = True
        self._backtest_stop_requested = False
        self._backtest_stop_event = threading.Event()
        _hotfix_refresh_backtest_selectors(self)
        self._append_backtest_journal(
            f"Prepared {context['symbol']} {context['timeframe']} using {context.get('strategy_name') or 'Default'}."
        )
        _hotfix_start_backtest_graph_animation(self)
        self._refresh_backtest_window(message="Backtest running...")
        data = candles_to_df(context.get("data"))
        if data is None or not hasattr(data, "__len__") or len(data) == 0:
            raise RuntimeError("No historical data available for backtesting.")
        await _hotfix_run_backtest_async(
            self,
            data,
            context.get("symbol", "BACKTEST"),
            context.get("strategy_name"),
            context.get("timeframe", "-"),
        )
    except Exception as e:
        self._backtest_running = False
        self._backtest_stop_event = None
        self._backtest_task = None
        self.system_console.log(f"Backtest failed to start: {e}", "ERROR")
        self._append_backtest_journal(f"Backtest failed to start: {e}", "ERROR")
        self._refresh_backtest_window(message=f"Backtest failed to start: {e}")


def _hotfix_start_backtest(self):
    start_backtest(self)


def _hotfix_stop_backtest(self):
    stop_backtest(self)


def _hotfix_generate_report(self):
    generate_report(self)


def _hotfix_show_optimization_window(self):
    return show_optimization_window(self)


def _hotfix_stellar_expert_asset_url(_self, code, issuer=None):
    base_url = "https://stellar.expert/explorer/public/asset"
    normalized_code = str(code or "").upper().strip()
    normalized_issuer = str(issuer or "").strip()
    if not normalized_code:
        return base_url
    if normalized_code == "XLM":
        return f"{base_url}/XLM"
    if not normalized_issuer:
        return base_url
    return f"{base_url}/{normalized_code}-{normalized_issuer}"


def _hotfix_stellar_asset_identifier(_self, code, issuer=None):
    normalized_code = str(code or "").upper().strip()
    normalized_issuer = str(issuer or "").strip()
    if not normalized_code:
        return ""
    if normalized_code == "XLM" or not normalized_issuer:
        return normalized_code
    return f"{normalized_code}:{normalized_issuer}"


def _hotfix_parse_stellar_asset_entry(self, raw):
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = text.upper().strip()
    if normalized == "XLM":
        return {
            "id": "XLM",
            "code": "XLM",
            "issuer": "",
            "source": "Native",
            "url": self._stellar_expert_asset_url("XLM"),
            "trusted": True,
            "needs_trustline": False,
            "screened": True,
            "risk_label": "Native",
        }
    if ":" not in text:
        return None
    code, issuer = text.split(":", 1)
    identifier = self._stellar_asset_identifier(code, issuer)
    return {
        "id": identifier,
        "code": str(code or "").upper().strip(),
        "issuer": str(issuer or "").strip(),
        "source": "Manual",
        "url": self._stellar_expert_asset_url(code, issuer),
        "trusted": False,
        "needs_trustline": True,
        "screened": False,
        "risk_label": "Manual",
    }


def _hotfix_selected_stellar_asset_row(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("stellar_asset_explorer")
    if window is None:
        return None
    asset_picker = getattr(window, "_stellar_asset_picker", None)
    asset_table = getattr(window, "_stellar_asset_table", None)
    rows = list(getattr(window, "_stellar_asset_rows", []) or [])
    if asset_picker is None and asset_table is None:
        return None
    selected_identifier = ""
    if asset_table is not None and asset_table.currentRow() >= 0:
        item = asset_table.item(asset_table.currentRow(), 0)
        if item is not None:
            selected_identifier = str(item.data(Qt.UserRole) or item.text() or "").strip()
    if not selected_identifier and asset_picker is not None:
        selected_identifier = str(asset_picker.currentData() or "").strip()
        if not selected_identifier and asset_picker.currentText():
            selected_identifier = str(asset_picker.currentText() or "").strip()
    for row in rows:
        if str(row.get("id") or "") == selected_identifier:
            return row
    return rows[0] if rows else None


def _hotfix_is_stellar_asset_blocked(self, row):
    if not isinstance(row, dict):
        return False
    if bool(row.get("blocked")):
        return True

    risk_fragments = [
        str(row.get("risk_label") or ""),
        str(row.get("warning") or ""),
        str(row.get("status") or ""),
        str(row.get("tag") or ""),
        str(row.get("tags") or ""),
        str(row.get("labels") or ""),
    ]
    combined_risk_text = " ".join(fragment.strip().lower() for fragment in risk_fragments if str(fragment or "").strip())
    if any(marker in combined_risk_text for marker in ("scam", "spam", "fraud", "phishing", "banned", "blacklist", "blacklisted", "blocked")):
        return True

    broker = getattr(self.controller, "broker", None)
    blocked_checker = getattr(broker, "is_asset_blocked", None)
    if not callable(blocked_checker):
        return False

    code = str(row.get("code") or "").upper().strip()
    issuer = str(row.get("issuer") or "").strip() or None
    try:
        return bool(blocked_checker(code, issuer))
    except TypeError:
        identifier = self._stellar_asset_identifier(code, issuer)
        return bool(blocked_checker(identifier))


def _hotfix_stellar_asset_explorer_rows(self):
    broker = getattr(self.controller, "broker", None)
    asset_registry = getattr(broker, "asset_registry", {}) or {}
    account_codes = {
        str(code or "").upper().strip()
        for code in (getattr(broker, "_account_asset_codes", []) or [])
        if str(code or "").strip()
    }
    network_codes = {
        str(code or "").upper().strip()
        for code in (getattr(broker, "_network_asset_codes", []) or [])
        if str(code or "").strip()
    }

    rows = {}

    def upsert(code, issuer=None, source=None):
        normalized_code = str(code or "").upper().strip()
        normalized_issuer = str(issuer or "").strip()
        if not normalized_code:
            return
        key = normalized_code if normalized_code == "XLM" or not normalized_issuer else f"{normalized_code}:{normalized_issuer}"
        row = rows.setdefault(
            key,
            {
                "code": normalized_code,
                "issuer": normalized_issuer,
                "sources": set(),
            },
        )
        if normalized_issuer and not row.get("issuer"):
            row["issuer"] = normalized_issuer
        if source:
            row["sources"].add(str(source))

    for code, descriptor in asset_registry.items():
        upsert(
            getattr(descriptor, "code", code),
            getattr(descriptor, "issuer", None),
        )

    for code in account_codes:
        descriptor = asset_registry.get(code)
        upsert(code, getattr(descriptor, "issuer", None), "Account")

    for code in network_codes:
        descriptor = asset_registry.get(code)
        upsert(code, getattr(descriptor, "issuer", None), "Network")

    exchange_name = str(getattr(self.controller, "exchange", "") or "").strip().lower()
    if not rows and exchange_name == "stellar":
        upsert("XLM", None, "Network")

    is_blocked = getattr(self, "_is_stellar_asset_blocked", None)
    if not callable(is_blocked):
        is_blocked = lambda row: _hotfix_is_stellar_asset_blocked(self, row)

    ordered_rows = []
    for row in rows.values():
        sources = sorted(set(row.get("sources") or []))
        code = str(row.get("code") or "")
        issuer = str(row.get("issuer") or "")
        screened = code == "XLM" or code in network_codes
        trusted = code == "XLM" or code in account_codes
        row_payload = {
            "id": self._stellar_asset_identifier(code, issuer),
            "code": code,
            "issuer": issuer,
            "source": ", ".join(sources) if sources else "Known",
            "url": self._stellar_expert_asset_url(code, issuer),
            "screened": screened,
            "trusted": trusted,
            "needs_trustline": bool(code and code != "XLM" and not trusted),
            "risk_label": "Screened" if screened else "Unscreened",
        }
        if is_blocked(row_payload):
            continue
        ordered_rows.append(row_payload)

    ordered_rows.sort(
        key=lambda item: (
            0 if bool(item.get("screened")) else 1,
            0 if "Account" in str(item.get("source") or "") else 1,
            0 if str(item.get("code") or "") == "XLM" else 1,
            str(item.get("code") or ""),
            str(item.get("issuer") or ""),
        )
    )
    return ordered_rows


def _hotfix_merge_stellar_asset_rows(self, base_rows, extra_rows=None):
    is_blocked = getattr(self, "_is_stellar_asset_blocked", None)
    if not callable(is_blocked):
        is_blocked = lambda row: _hotfix_is_stellar_asset_blocked(self, row)
    merged_rows = {}
    for raw_row in list(base_rows or []) + list(extra_rows or []):
        if not isinstance(raw_row, dict):
            continue
        if is_blocked(raw_row):
            continue
        identifier = str(raw_row.get("id") or "").strip()
        if not identifier:
            continue
        existing = dict(merged_rows.get(identifier) or {})
        row = dict(raw_row)
        source_parts = [
            str(existing.get("source") or "").strip(),
            str(row.get("source") or "").strip(),
        ]
        merged = dict(existing)
        merged.update(row)
        merged["source"] = ", ".join(part for part in dict.fromkeys(part for part in source_parts if part) if part)
        merged["screened"] = bool(existing.get("screened")) or bool(row.get("screened"))
        merged["trusted"] = bool(existing.get("trusted")) or bool(row.get("trusted"))
        merged["needs_trustline"] = bool(
            str(merged.get("code") or "").upper() != "XLM" and not bool(merged.get("trusted"))
        )
        score_value = row.get("score", existing.get("score"))
        merged["score"] = float(score_value) if score_value not in (None, "") else None
        roi_value = row.get("roi_pct", existing.get("roi_pct"))
        merged["roi_pct"] = float(roi_value) if roi_value not in (None, "") else None
        merged["roi_symbol"] = str(row.get("roi_symbol") or existing.get("roi_symbol") or "").strip()
        merged_rows[identifier] = merged

    ordered_rows = list(merged_rows.values())
    ordered_rows.sort(
        key=lambda item: (
            0 if bool(item.get("screened")) else 1,
            0 if bool(item.get("trusted")) else 1,
            0 if "Directory" in str(item.get("source") or "") else 1,
            -(float(item.get("roi_pct")) if item.get("roi_pct") not in (None, "") else -999999.0),
            -(float(item.get("score")) if item.get("score") not in (None, "") else 0.0),
            str(item.get("code") or ""),
            str(item.get("issuer") or ""),
        )
    )
    return ordered_rows


async def _hotfix_load_stellar_asset_directory_page_async(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("stellar_asset_explorer")
    if window is None:
        return

    status = getattr(window, "_stellar_asset_status", None)
    cursor_input = getattr(window, "_stellar_asset_directory_cursor", None)
    broker = getattr(self.controller, "broker", None)
    exchange_name = str(getattr(self.controller, "exchange", "") or "").strip().lower()
    if broker is None or exchange_name != "stellar":
        raise RuntimeError("Connect a Stellar broker before loading the asset directory.")
    if not hasattr(broker, "fetch_asset_directory_page"):
        raise RuntimeError("The connected broker does not support Stellar asset directory pages.")

    cursor = str(cursor_input.text() or "").strip() if cursor_input is not None else ""
    if status is not None:
        status.setText(
            "Loading Stellar asset directory page..."
            + (f" cursor {cursor}." if cursor else "")
        )

    payload = await broker.fetch_asset_directory_page(cursor=cursor or None, limit=60)
    page_rows = [dict(item) for item in list(payload.get("rows") or []) if isinstance(item, dict)]
    existing_rows = {
        str(row.get("id") or "").strip(): dict(row)
        for row in list(getattr(window, "_stellar_asset_directory_rows", []) or [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    for row in page_rows:
        existing_rows[str(row.get("id") or "").strip()] = dict(row)
    window._stellar_asset_directory_rows = list(existing_rows.values())
    window._stellar_asset_next_cursor = str(payload.get("next_cursor") or "").strip()

    next_cursor = str(payload.get("next_cursor") or "").strip()
    status_message = (
        f"Loaded {len(page_rows)} Stellar directory assets."
        + (f" Next cursor: {next_cursor}" if next_cursor else " Reached the end of the directory page chain.")
    )
    self._refresh_stellar_asset_explorer_window(window, message=status_message)


def _hotfix_load_stellar_asset_directory_page(self, window=None):
    async def runner():
        try:
            await self._load_stellar_asset_directory_page_async(window)
        except Exception as exc:
            if hasattr(self, "logger"):
                self.logger.exception("Stellar asset directory load failed")
            if hasattr(self, "system_console"):
                self.system_console.log(f"Stellar asset directory load failed: {exc}", "ERROR")
            self._refresh_stellar_asset_explorer_window(window, message=str(exc))
            self._show_async_message("Stellar Asset Directory Failed", str(exc), QMessageBox.Icon.Critical)

    asyncio.get_event_loop().create_task(runner())


async def _hotfix_auto_trust_stellar_asset_by_roi_async(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("stellar_asset_explorer")
    if window is None:
        return

    status = getattr(window, "_stellar_asset_status", None)
    broker = getattr(self.controller, "broker", None)
    exchange_name = str(getattr(self.controller, "exchange", "") or "").strip().lower()
    if broker is None or exchange_name != "stellar":
        raise RuntimeError("Connect a Stellar broker before auto-trusting a Stellar asset.")
    if not hasattr(broker, "create_trustline") or not hasattr(broker, "estimate_asset_roi"):
        raise RuntimeError("The connected broker does not support ROI-based trustline selection.")

    visible_rows = [dict(row) for row in list(getattr(window, "_stellar_asset_rows", []) or []) if isinstance(row, dict)]
    is_blocked = getattr(self, "_is_stellar_asset_blocked", None)
    if not callable(is_blocked):
        is_blocked = lambda row: _hotfix_is_stellar_asset_blocked(self, row)
    candidates = [
        row
        for row in visible_rows
        if str(row.get("code") or "").upper() != "XLM"
        and bool(row.get("needs_trustline"))
        and bool(row.get("screened"))
        and not is_blocked(row)
    ]
    if not candidates:
        raise ValueError("No visible screened Stellar assets need trustlines right now.")

    ranked_candidates = sorted(
        candidates,
        key=lambda row: (
            -(float(row.get("score")) if row.get("score") not in (None, "") else 0.0),
            str(row.get("code") or ""),
        ),
    )[:12]

    if status is not None:
        status.setText(f"Scoring {len(ranked_candidates)} Stellar assets by recent ROI...")

    best_row = None
    best_snapshot = None
    for row in ranked_candidates:
        identifier = self._stellar_asset_identifier(row.get("code"), row.get("issuer"))
        snapshot = await broker.estimate_asset_roi(identifier, timeframe="1h", limit=48)
        if not isinstance(snapshot, dict) or snapshot.get("roi_pct") is None:
            continue
        roi_value = float(snapshot.get("roi_pct") or 0.0)
        row["roi_pct"] = roi_value
        row["roi_symbol"] = str(snapshot.get("symbol") or "").strip()
        if best_snapshot is None or roi_value > float(best_snapshot.get("roi_pct") or 0.0):
            best_row = row
            best_snapshot = snapshot

    if best_row is None or best_snapshot is None:
        raise RuntimeError("Unable to compute ROI for the visible Stellar assets. Load a different page or adjust the filters.")

    best_roi = float(best_snapshot.get("roi_pct") or 0.0)
    if best_roi <= 0.0:
        raise RuntimeError("No positive-ROI Stellar asset was found among the visible screened candidates.")

    identifier = self._stellar_asset_identifier(best_row.get("code"), best_row.get("issuer"))
    if status is not None:
        status.setText(f"Submitting trustline for best ROI asset {identifier} ({best_roi:.2f}% )...")

    result = await broker.create_trustline(identifier)
    for row in list(getattr(window, "_stellar_asset_directory_rows", []) or []):
        if str(row.get("id") or "").strip() == identifier:
            row["trusted"] = True
            row["needs_trustline"] = False
            row["roi_pct"] = best_roi
            row["roi_symbol"] = str(best_snapshot.get("symbol") or "").strip()
    if hasattr(self, "_refresh_markets"):
        self._refresh_markets()
    message = (
        str(result.get("message") or f"Trustline submitted for {identifier}.")
        + f" Auto-selected from ROI {best_roi:.2f}% via {str(best_snapshot.get('symbol') or identifier)}."
    )
    self._refresh_stellar_asset_explorer_window(window, message=message)
    if hasattr(self, "system_console"):
        self.system_console.log(message, "INFO")


def _hotfix_auto_trust_stellar_asset_by_roi(self, window=None):
    async def runner():
        try:
            await self._auto_trust_stellar_asset_by_roi_async(window)
        except Exception as exc:
            if hasattr(self, "logger"):
                self.logger.exception("Stellar ROI trustline selection failed")
            if hasattr(self, "system_console"):
                self.system_console.log(f"Stellar ROI trustline selection failed: {exc}", "ERROR")
            self._refresh_stellar_asset_explorer_window(window, message=str(exc))
            self._show_async_message("Stellar ROI Trustline Failed", str(exc), QMessageBox.Icon.Critical)

    asyncio.get_event_loop().create_task(runner())


def _hotfix_refresh_stellar_asset_explorer_window(self, window=None, message=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("stellar_asset_explorer")
    if window is None:
        return

    status = getattr(window, "_stellar_asset_status", None)
    asset_picker = getattr(window, "_stellar_asset_picker", None)
    asset_table = getattr(window, "_stellar_asset_table", None)
    manual_input = getattr(window, "_stellar_asset_input", None)
    directory_cursor_input = getattr(window, "_stellar_asset_directory_cursor", None)
    details = getattr(window, "_stellar_asset_details", None)
    safe_filter = getattr(window, "_stellar_asset_filter_safe", None)
    trustline_filter = getattr(window, "_stellar_asset_filter_untrusted", None)
    trustline_btn = getattr(window, "_stellar_asset_trustline_btn", None)
    load_directory_btn = getattr(window, "_stellar_asset_load_directory_btn", None)
    auto_trust_btn = getattr(window, "_stellar_asset_auto_trust_btn", None)
    if status is None or asset_picker is None or manual_input is None or details is None:
        return

    merge_rows = getattr(self, "_merge_stellar_asset_rows", None)
    if not callable(merge_rows):
        merge_rows = lambda base_rows, extra_rows=None: _hotfix_merge_stellar_asset_rows(self, base_rows, extra_rows)
    rows = merge_rows(
        self._stellar_asset_explorer_rows(),
        getattr(window, "_stellar_asset_directory_rows", []),
    )
    broker = getattr(self.controller, "broker", None)
    broker_name = str(getattr(self.controller, "exchange", "") or "Broker").strip() or "Broker"
    selected_value = str(asset_picker.currentData() or "").strip()
    if asset_table is not None and asset_table.currentRow() >= 0:
        selected_item = asset_table.item(asset_table.currentRow(), 0)
        if selected_item is not None:
            selected_value = str(selected_item.data(Qt.UserRole) or selected_item.text() or "").strip() or selected_value
    show_screened_only = bool(safe_filter.isChecked()) if safe_filter is not None else False
    show_needs_trustline_only = bool(trustline_filter.isChecked()) if trustline_filter is not None else False
    filtered_rows = []
    for row in rows:
        if show_screened_only and not bool(row.get("screened")):
            continue
        if show_needs_trustline_only and not bool(row.get("needs_trustline")):
            continue
        filtered_rows.append(row)

    blocked = asset_picker.blockSignals(True)
    asset_picker.clear()
    selected_index = 0
    for row in filtered_rows:
        label = str(row.get("code") or "")
        issuer = str(row.get("issuer") or "").strip()
        source = str(row.get("source") or "").strip()
        risk_label = str(row.get("risk_label") or "").strip()
        roi_value = row.get("roi_pct")
        roi_label = f"{float(roi_value):+.2f}%" if roi_value not in (None, "") else ""
        if issuer:
            label = f"{label} | {issuer[:12]}..."
        if risk_label:
            label = f"{label} [{risk_label}]"
        if roi_label:
            label = f"{label} ROI {roi_label}"
        if source:
            label = f"{label} {{{source}}}"
        asset_picker.addItem(label, row.get("id"))
    if selected_value:
        for index in range(asset_picker.count()):
            if str(asset_picker.itemData(index) or "").strip() == selected_value:
                asset_picker.setCurrentIndex(index)
                selected_index = index
                break
    elif asset_picker.count():
        asset_picker.setCurrentIndex(0)
    asset_picker.blockSignals(blocked)
    window._stellar_asset_all_rows = list(rows)
    window._stellar_asset_rows = list(filtered_rows)
    if asset_table is not None:
        table_blocked = asset_table.blockSignals(True)
        asset_table.setColumnCount(7)
        asset_table.setHorizontalHeaderLabels(
            ["Asset", "Issuer", "Trust", "Safety", "ROI 24h", "Score", "Source"]
        )
        asset_table.setRowCount(len(filtered_rows))
        selected_table_row = -1
        for row_index, row in enumerate(filtered_rows):
            trust_state = "Trusted" if row.get("trusted") else ("Needs trustline" if row.get("needs_trustline") else "Native")
            roi_value = row.get("roi_pct")
            roi_text = f"{float(roi_value):+.2f}%" if roi_value not in (None, "") else "-"
            score_value = row.get("score")
            score_text = f"{float(score_value):.0f}" if score_value not in (None, "") else "-"
            values = [
                str(row.get("code") or ""),
                str(row.get("issuer") or ""),
                trust_state,
                str(row.get("risk_label") or ""),
                roi_text,
                score_text,
                str(row.get("source") or ""),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == 0:
                    item.setData(Qt.UserRole, str(row.get("id") or ""))
                asset_table.setItem(row_index, column_index, item)
            if str(row.get("id") or "") == str(asset_picker.currentData() or ""):
                selected_table_row = row_index
        asset_table.resizeColumnsToContents()
        asset_table.horizontalHeader().setStretchLastSection(True)
        if selected_table_row >= 0:
            asset_table.selectRow(selected_table_row)
        elif filtered_rows:
            asset_table.selectRow(0)
        asset_table.blockSignals(table_blocked)

    current_row = self._selected_stellar_asset_row(window)
    if not str(manual_input.text() or "").strip() and current_row is not None:
        manual_input.setText(str(current_row.get("id") or ""))

    typed_row = self._parse_stellar_asset_entry(manual_input.text() if manual_input is not None else "")

    if message:
        status.setText(message)
    elif filtered_rows:
        imported_count = len(
            [
                row
                for row in filtered_rows
                if "Directory" in str(row.get("source") or "")
            ]
        )
        status.setText(
            f"Loaded {len(filtered_rows)} Stellar assets"
            + (f" ({len(rows)} total)" if len(filtered_rows) != len(rows) else "")
            + (f" | Directory imports: {imported_count}" if imported_count else "")
            + ". Screened assets passed the app's Horizon liquidity/account heuristics; review issuers before trusting them."
        )
    else:
        status.setText(
            "No Stellar assets match the current filters. Connect a Stellar broker, adjust the filters, or type XLM / CODE:ISSUER manually."
        )

    quick_links = []
    for row in filtered_rows[:24]:
        code = html.escape(str(row.get("code") or ""))
        issuer = str(row.get("issuer") or "").strip()
        source = html.escape(str(row.get("source") or "Known"))
        trust_state = "Trusted" if row.get("trusted") else ("Needs trustline" if row.get("needs_trustline") else "Native")
        risk_label = html.escape(str(row.get("risk_label") or "Known"))
        score_value = row.get("score")
        roi_value = row.get("roi_pct")
        roi_symbol = html.escape(str(row.get("roi_symbol") or "").strip())
        metric_parts = []
        if score_value not in (None, ""):
            metric_parts.append(f"Score {float(score_value):.0f}")
        if roi_value not in (None, ""):
            roi_text = f"ROI {float(roi_value):+.2f}%"
            if roi_symbol:
                roi_text = f"{roi_text} via {roi_symbol}"
            metric_parts.append(roi_text)
        asset_label = code if not issuer else f"{code}:{html.escape(issuer)}"
        quick_links.append(
            f"<li><a href=\"{html.escape(str(row.get('url') or ''))}\">{asset_label}</a> "
            f"<span style='color:#8ea3bf;'>({source} | {risk_label} | {html.escape(trust_state)}"
            + (f" | {' | '.join(metric_parts)}" if metric_parts else "")
            + ")</span></li>"
        )

    broker_hint = (
        "Stellar broker connected."
        if getattr(broker, "asset_registry", None)
        else "Explorer shortcuts available even without a live Stellar broker."
    )
    directory_cursor = html.escape(str(directory_cursor_input.text() or "").strip()) if directory_cursor_input is not None else ""
    next_cursor = html.escape(str(getattr(window, "_stellar_asset_next_cursor", "") or "").strip())
    selected_asset_html = "<p>No asset is selected.</p>"
    if current_row is not None:
        selected_identifier = html.escape(str(current_row.get("id") or ""))
        selected_source = html.escape(str(current_row.get("source") or "Known"))
        selected_risk = html.escape(str(current_row.get("risk_label") or "Known"))
        selected_trust = "Trusted" if current_row.get("trusted") else ("Needs trustline" if current_row.get("needs_trustline") else "Native")
        selected_score = current_row.get("score")
        selected_roi = current_row.get("roi_pct")
        selected_roi_symbol = html.escape(str(current_row.get("roi_symbol") or "").strip())
        selected_metrics = []
        if selected_score not in (None, ""):
            selected_metrics.append(f"Score: {float(selected_score):.0f}")
        if selected_roi not in (None, ""):
            selected_roi_text = f"ROI 24h: {float(selected_roi):+.2f}%"
            if selected_roi_symbol:
                selected_roi_text = f"{selected_roi_text} via {selected_roi_symbol}"
            selected_metrics.append(selected_roi_text)
        selected_asset_html = "".join(
            [
                "<div style='padding:10px; border:1px solid #24344f; border-radius:8px; background:#101a2d;'>",
                f"<b>{selected_identifier}</b><br/>",
                f"<span style='color:#8ea3bf;'>Source: {selected_source} | Safety: {selected_risk} | Trust: {html.escape(selected_trust)}</span>",
                f"<br/><span style='color:#8ea3bf;'>{' | '.join(selected_metrics)}</span>" if selected_metrics else "",
                "</div>",
            ]
        )
    typed_asset_html = ""
    if typed_row is not None and not bool(typed_row.get("screened")):
        typed_asset_html = (
            "<p style='color:#f6c177;'><b>Manual asset:</b> typed assets are unverified by the app. "
            "Confirm the issuer before opening a trustline.</p>"
        )
    details_sections = [
        "<h2>Stellar Asset Explorer</h2>",
        "<p>Filter for screened assets, review trust status, open public asset pages from <b>stellar.expert</b>, and add trustlines before trading.</p>",
        "<p><a href=\"https://stellar.expert/explorer/public/asset\">Open Asset Directory</a></p>",
        f"<p>{html.escape(broker_hint)} Broker: <b>{html.escape(broker_name.upper())}</b></p>",
    ]
    if directory_cursor or next_cursor:
        details_sections.append(
            f"<p style='color:#8ea3bf;'>Directory cursor: <code>{directory_cursor or 'first page'}</code>"
            + (f" | Next cursor: <code>{next_cursor}</code>" if next_cursor else "")
            + "</p>"
        )
    details_sections.extend(
        [
            "<p style='color:#8ea3bf;'>Screened means the asset passed the app's Horizon-based activity and liquidity checks. It is safer than unverified listings, but not a guarantee.</p>",
            "<h3>Selected Asset</h3>",
            selected_asset_html,
            typed_asset_html,
            "<h3>Quick Links</h3>",
            (
                f"<ul>{''.join(quick_links)}</ul>"
                if quick_links
                else "<p>No broker asset registry is available yet. Use the text field above with values like <code>XLM</code> or <code>USDC:G...</code>.</p>"
            ),
        ]
    )
    details.setHtml("".join(details_sections))
    if trustline_btn is not None:
        broker_ready = str(getattr(self.controller, "exchange", "") or "").strip().lower() == "stellar" and hasattr(broker, "create_trustline")
        trust_target = typed_row if typed_row is not None else current_row
        can_trust = bool(
            broker_ready
            and trust_target is not None
            and str(trust_target.get("code") or "").upper() != "XLM"
            and (bool(trust_target.get("needs_trustline")) or typed_row is not None)
        )
        trustline_btn.setEnabled(can_trust)
        if not broker_ready:
            trustline_btn.setToolTip("Connect a Stellar broker with a secret seed to add trustlines.")
        elif trust_target is None:
            trustline_btn.setToolTip("Select a Stellar asset or type CODE:ISSUER to open a trustline.")
        elif str(trust_target.get("code") or "").upper() == "XLM":
            trustline_btn.setToolTip("XLM is native and does not need a trustline.")
        elif not bool(trust_target.get("needs_trustline")) and typed_row is None:
            trustline_btn.setToolTip("This asset already has a trustline.")
        else:
            trustline_btn.setToolTip("Submit a Stellar trustline transaction for the selected asset.")
    if load_directory_btn is not None:
        can_load_directory = str(getattr(self.controller, "exchange", "") or "").strip().lower() == "stellar" and hasattr(broker, "fetch_asset_directory_page")
        load_directory_btn.setEnabled(can_load_directory)
        if not can_load_directory:
            load_directory_btn.setToolTip("Connect a Stellar broker to load an asset directory page.")
        else:
            load_directory_btn.setToolTip("Load a page of additional Stellar assets from the directory feed.")
    if auto_trust_btn is not None:
        can_auto_trust = bool(
            str(getattr(self.controller, "exchange", "") or "").strip().lower() == "stellar"
            and hasattr(broker, "create_trustline")
            and hasattr(broker, "estimate_asset_roi")
            and any(
                str(row.get("code") or "").upper() != "XLM"
                and bool(row.get("needs_trustline"))
                and bool(row.get("screened"))
                for row in filtered_rows
            )
        )
        auto_trust_btn.setEnabled(can_auto_trust)
        if not can_auto_trust:
            auto_trust_btn.setToolTip("Show at least one screened Stellar asset that still needs a trustline to auto-select by ROI.")
        else:
            auto_trust_btn.setToolTip("Compute recent ROI for the visible screened assets and trust the best positive candidate automatically.")


def _hotfix_open_selected_stellar_asset(self, window=None, typed=False):
    """Open selected or typed Stellar asset in external explorer.

    window: Stellar asset explorer dock window instance.
    typed: If True, use typed code/issuer in input box instead of row selection.
    """
    window = window or getattr(self, "detached_tool_windows", {}).get("stellar_asset_explorer")
    if window is None:
        return

    status = cast(Optional[QLabel], getattr(window, "_stellar_asset_status", None))
    asset_picker = cast(Optional[QComboBox], getattr(window, "_stellar_asset_picker", None))
    manual_input = cast(Optional[QLineEdit], getattr(window, "_stellar_asset_input", None))

    url = "https://stellar.expert/explorer/public/asset"
    if typed:
        parsed = self._parse_stellar_asset_entry(manual_input.text() if manual_input is not None else "")
        if parsed is None:
            if status is not None:
                status.setText("Type XLM or CODE:ISSUER before opening a Stellar asset page.")
            return
        url = str(parsed.get("url") or url)
    else:
        row = self._selected_stellar_asset_row(window)
        if row is not None:
            url = str(row.get("url") or "").strip() or url

    QDesktopServices.openUrl(QUrl(url))
    if status is not None:
        status.setText(f"Opened {url}")


async def _hotfix_open_stellar_asset_trustline_async(self, window=None):
    """Request a Stellar trustline for selected or typed asset from explorer."""
    window = window or getattr(self, "detached_tool_windows", {}).get("stellar_asset_explorer")
    if window is None:
        return

    status = cast(Optional[QLabel], getattr(window, "_stellar_asset_status", None))
    manual_input = cast(Optional[QLineEdit], getattr(window, "_stellar_asset_input", None))
    broker = getattr(self.controller, "broker", None)
    if broker is None or str(getattr(self.controller, "exchange", "") or "").strip().lower() != "stellar":
        raise RuntimeError("Connect a Stellar broker before opening a trustline.")
    if not hasattr(broker, "create_trustline"):
        raise RuntimeError("The connected broker does not support Stellar trustlines.")

    typed_row = self._parse_stellar_asset_entry(manual_input.text() if manual_input is not None else "")
    row = typed_row if typed_row is not None else self._selected_stellar_asset_row(window)
    if row is None:
        raise ValueError("Select a Stellar asset or type CODE:ISSUER before opening a trustline.")
    if str(row.get("code") or "").upper() == "XLM":
        message = "XLM is native and does not require a trustline."
        if status is not None:
            status.setText(message)
        return

    identifier = self._stellar_asset_identifier(row.get("code"), row.get("issuer"))
    if status is not None:
        status.setText(f"Submitting trustline for {identifier}...")
    result = await broker.create_trustline(identifier)
    if hasattr(self, "_refresh_markets"):
        self._refresh_markets()
    self._refresh_stellar_asset_explorer_window(
        window,
        message=str(result.get("message") or f"Trustline submitted for {identifier}."),
    )
    if hasattr(self, "system_console"):
        self.system_console.log(
            str(result.get("message") or f"Trustline submitted for {identifier}."),
            "INFO",
        )


def _hotfix_open_stellar_asset_trustline(self, window=None):
    """Fire-and-forget wrapper for async Stellar trustline request with error handling."""
    async def runner():
        try:
            await self._open_stellar_asset_trustline_async(window)
        except Exception as exc:
            if hasattr(self, "logger"):
                self.logger.exception("Stellar trustline request failed")
            if hasattr(self, "system_console"):
                self.system_console.log(f"Trustline request failed: {exc}", "ERROR")
            self._refresh_stellar_asset_explorer_window(window, message=str(exc))
            self._show_async_message("Stellar Trustline Failed", str(exc), QMessageBox.Icon.Critical)

    asyncio.get_event_loop().create_task(runner())


def _hotfix_open_stellar_asset_explorer_window(self):
    if Terminal._active_exchange_name(self) != "stellar":
        return

    window = self._get_or_create_tool_window(
        "stellar_asset_explorer",
        "Stellar Asset Explorer",
        width=980,
        height=700,
    )

    if getattr(window, "_stellar_asset_container", None) is None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        status = QLabel("Loading Stellar asset shortcuts.")
        status.setWordWrap(True)
        status.setStyleSheet(
            "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; padding: 10px; border-radius: 8px;"
        )
        layout.addWidget(status)

        controls = QFrame()
        controls.setStyleSheet(
            "QFrame { background-color: #0f1727; border: 1px solid #24344f; border-radius: 10px; }"
            "QLabel { color: #d7dfeb; font-weight: 700; }"
            "QComboBox, QLineEdit { background-color: #0b1220; color: #f4f8ff; border: 1px solid #2a3d5c; border-radius: 6px; padding: 6px 10px; min-width: 180px; }"
        )
        controls_layout = QGridLayout(controls)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setHorizontalSpacing(16)
        controls_layout.setVerticalSpacing(8)

        asset_picker = QComboBox()
        manual_input = QLineEdit()
        manual_input.setPlaceholderText("XLM or CODE:ISSUER")
        directory_cursor_input = QLineEdit()
        directory_cursor_input.setPlaceholderText("Directory cursor (optional)")
        safe_filter = QCheckBox("Show only screened assets")
        safe_filter.setChecked(True)
        trustline_filter = QCheckBox("Only assets that need trustlines")
        open_selected_btn = QPushButton("Open Selected Asset")
        open_typed_btn = QPushButton("Open Typed Asset")
        open_trustline_btn = QPushButton("Open Trustline")
        open_directory_btn = QPushButton("Open Asset Directory")
        load_directory_btn = QPushButton("Load Directory Page")
        auto_trust_btn = QPushButton("Trust Best ROI")
        refresh_btn = QPushButton("Refresh Asset List")

        open_selected_btn.clicked.connect(lambda: self._open_selected_stellar_asset(window))
        open_typed_btn.clicked.connect(lambda: self._open_selected_stellar_asset(window, typed=True))
        open_trustline_btn.clicked.connect(lambda: self._open_stellar_asset_trustline(window))
        open_directory_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://stellar.expert/explorer/public/asset"))
        )
        load_directory_btn.clicked.connect(lambda: self._load_stellar_asset_directory_page(window))
        auto_trust_btn.clicked.connect(lambda: self._auto_trust_stellar_asset_by_roi(window))
        refresh_btn.clicked.connect(lambda: self._refresh_stellar_asset_explorer_window(window))

        controls_layout.addWidget(QLabel("Known Asset"), 0, 0)
        controls_layout.addWidget(asset_picker, 0, 1, 1, 3)
        controls_layout.addWidget(QLabel("Manual Asset"), 1, 0)
        controls_layout.addWidget(manual_input, 1, 1, 1, 3)
        controls_layout.addWidget(QLabel("Directory Cursor"), 2, 0)
        controls_layout.addWidget(directory_cursor_input, 2, 1, 1, 2)
        controls_layout.addWidget(load_directory_btn, 2, 3)
        controls_layout.addWidget(safe_filter, 3, 0, 1, 2)
        controls_layout.addWidget(trustline_filter, 3, 2, 1, 2)
        controls_layout.addWidget(open_selected_btn, 4, 0)
        controls_layout.addWidget(open_typed_btn, 4, 1)
        controls_layout.addWidget(open_trustline_btn, 4, 2)
        controls_layout.addWidget(auto_trust_btn, 4, 3)
        controls_layout.addWidget(open_directory_btn, 5, 0, 1, 2)
        controls_layout.addWidget(refresh_btn, 5, 2, 1, 2)
        layout.addWidget(controls)

        asset_table = QTableWidget()
        asset_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        asset_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        asset_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        asset_table.verticalHeader().setVisible(False)
        asset_table.setAlternatingRowColors(True)
        layout.addWidget(asset_table)

        details = QTextBrowser()
        details.setOpenExternalLinks(True)
        details.setStyleSheet(
            "QTextBrowser { background-color: #0b1220; color: #d7dfeb; border: 1px solid #24344f; border-radius: 10px; padding: 10px; }"
        )
        layout.addWidget(details, 1)

        window.setCentralWidget(container)
        window._stellar_asset_container = container
        window._stellar_asset_status = status
        window._stellar_asset_picker = asset_picker
        window._stellar_asset_input = manual_input
        window._stellar_asset_directory_cursor = directory_cursor_input
        window._stellar_asset_table = asset_table
        window._stellar_asset_details = details
        window._stellar_asset_filter_safe = safe_filter
        window._stellar_asset_filter_untrusted = trustline_filter
        window._stellar_asset_trustline_btn = open_trustline_btn
        window._stellar_asset_load_directory_btn = load_directory_btn
        window._stellar_asset_auto_trust_btn = auto_trust_btn
        window._stellar_asset_directory_rows = []
        window._stellar_asset_next_cursor = ""
        window._stellar_asset_rows = []

        asset_picker.currentIndexChanged.connect(
            lambda _idx: self._refresh_stellar_asset_explorer_window(window)
        )
        asset_table.itemSelectionChanged.connect(lambda: self._refresh_stellar_asset_explorer_window(window))
        manual_input.textChanged.connect(lambda _text: self._refresh_stellar_asset_explorer_window(window))
        safe_filter.toggled.connect(lambda _checked: self._refresh_stellar_asset_explorer_window(window))
        trustline_filter.toggled.connect(lambda _checked: self._refresh_stellar_asset_explorer_window(window))

    self._refresh_stellar_asset_explorer_window(window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def _hotfix_refresh_optimization_window(self, window=None, message=None):
    refresh_optimization_window(self, window=window, message=message)


def _hotfix_refresh_optimization_selectors(self, window=None):
    refresh_optimization_selectors(self, window=window)


def _hotfix_optimization_selection_changed(self):
    optimization_selection_changed(self)


async def _hotfix_run_strategy_optimization(self):
    if getattr(self, "_optimization_running", False):
        self._show_optimization_window()
        self._refresh_optimization_window(message="Optimization is already running.")
        return

    try:
        from backtesting.optimizer import StrategyOptimizer

        self._show_optimization_window()
        context = await _hotfix_prepare_backtest_context_with_selection(
            self,
            symbol=str(getattr(getattr(self.detached_tool_windows.get("strategy_optimization"), "_optimization_symbol_picker", None), "currentText", lambda: "")()).strip() or None,
            timeframe=str(getattr(getattr(self.detached_tool_windows.get("strategy_optimization"), "_optimization_timeframe_picker", None), "currentText", lambda: "")()).strip() or None,
            strategy_name=str(getattr(getattr(self.detached_tool_windows.get("strategy_optimization"), "_optimization_strategy_picker", None), "currentText", lambda: "")()).strip() or None,
        )
        data = candles_to_df(context.get("data"))
        if data is None or not hasattr(data, "__len__") or len(data) == 0:
            raise RuntimeError("No historical data available for optimization")

        optimizer = StrategyOptimizer(
            strategy=context["strategy"],
            initial_balance=getattr(self.controller, "initial_capital", 10000),
        )
        self._optimization_running = True
        self._optimization_mode = "param"
        self._optimization_status_message = "Optimization running..."
        self._optimization_context = context
        _hotfix_refresh_optimization_selectors(self)
        self._show_optimization_window()
        self._refresh_optimization_window(message="Optimization running...")
        await asyncio.sleep(0)

        self.optimization_results = await asyncio.to_thread(
            optimizer.optimize,
            data,
            context["symbol"],
            context.get("strategy_name"),
        )
        self.strategy_ranking_results = None
        self.strategy_ranking_best = None
        self.optimization_best = None
        if self.optimization_results is not None and not self.optimization_results.empty:
            self.optimization_best = self.optimization_results.iloc[0].to_dict()

        self.system_console.log("Strategy optimization completed.", "INFO")
        self._optimization_status_message = "Strategy optimization completed."
        self._show_optimization_window()
        self._refresh_optimization_window(message="Strategy optimization completed.")

    except Exception as e:
        self.system_console.log(f"Strategy optimization failed: {e}", "ERROR")
        self._optimization_status_message = f"Strategy optimization failed: {e}"
        self._show_optimization_window()
        self._refresh_optimization_window(message=f"Strategy optimization failed: {e}")
    finally:
        self._optimization_running = False
        self._refresh_optimization_window()


async def _hotfix_run_strategy_ranking(self):
    if getattr(self, "_optimization_running", False):
        self._show_optimization_window()
        self._refresh_optimization_window(message="Optimization is already running.")
        return

    try:
        from backtesting.strategy_ranker import StrategyRanker

        self._show_optimization_window()
        context = await _hotfix_prepare_backtest_context_with_selection(
            self,
            symbol=str(getattr(getattr(self.detached_tool_windows.get("strategy_optimization"), "_optimization_symbol_picker", None), "currentText", lambda: "")()).strip() or None,
            timeframe=str(getattr(getattr(self.detached_tool_windows.get("strategy_optimization"), "_optimization_timeframe_picker", None), "currentText", lambda: "")()).strip() or None,
            strategy_name=str(getattr(getattr(self.detached_tool_windows.get("strategy_optimization"), "_optimization_strategy_picker", None), "currentText", lambda: "")()).strip() or None,
        )
        data = candles_to_df(context.get("data"))
        if data is None or not hasattr(data, "__len__") or len(data) == 0:
            raise RuntimeError("No historical data available for strategy ranking")

        ranker = StrategyRanker(
            strategy_registry=context["strategy"],
            initial_balance=getattr(self.controller, "initial_capital", 10000),
        )
        self._optimization_running = True
        self._optimization_mode = "ranking"
        self._optimization_status_message = "Ranking all strategies..."
        self._optimization_context = context
        _hotfix_refresh_optimization_selectors(self)
        self._show_optimization_window()
        self._refresh_optimization_window(message="Ranking all strategies...")
        await asyncio.sleep(0)

        self.strategy_ranking_results = await asyncio.to_thread(
            ranker.rank,
            data,
            context["symbol"],
            context.get("timeframe"),
            list(getattr(context["strategy"], "list", lambda: [])()),
        )
        self.strategy_ranking_best = None
        if self.strategy_ranking_results is not None and not self.strategy_ranking_results.empty:
            self.strategy_ranking_best = self.strategy_ranking_results.iloc[0].to_dict()

        self.system_console.log("Strategy ranking completed.", "INFO")
        self._optimization_status_message = "Strategy ranking completed."
        self._show_optimization_window()
        self._refresh_optimization_window(message="Strategy ranking completed.")

    except Exception as e:
        self.system_console.log(f"Strategy ranking failed: {e}", "ERROR")
        self._optimization_status_message = f"Strategy ranking failed: {e}"
        self._show_optimization_window()
        self._refresh_optimization_window(message=f"Strategy ranking failed: {e}")
    finally:
        self._optimization_running = False
        self._refresh_optimization_window()


def _hotfix_assign_ranked_strategies_to_symbol(self):
    try:
        lock_message = _hotfix_strategy_assignment_lock_message(self)
        if lock_message:
            raise RuntimeError(lock_message)

        results = getattr(self, "strategy_ranking_results", None)
        if results is None or getattr(results, "empty", True):
            raise RuntimeError("Run strategy ranking before assigning strategies to a symbol")

        window = getattr(self, "detached_tool_windows", {}).get("strategy_optimization")
        assign_count = getattr(window, "_optimization_assign_count", None) if window is not None else None
        top_n = int(assign_count.value()) if assign_count is not None else int(getattr(self.controller, "max_symbol_strategies", 3) or 3)
        context = getattr(self, "_optimization_context", {}) or {}
        symbol = str(context.get("symbol") or "").strip()
        if not symbol:
            raise RuntimeError("No symbol selected for strategy assignment")

        timeframe = str(context.get("timeframe") or "").strip()
        self.controller.multi_strategy_enabled = True
        assigned = self.controller.assign_ranked_strategies_to_symbol(
            symbol,
            results.to_dict("records"),
            top_n=top_n,
            timeframe=timeframe,
        )
        assigned_names = ", ".join(str(item.get("strategy_name") or "").strip() for item in assigned)
        self.system_console.log(f"Assigned top {len(assigned)} strategies to {symbol}: {assigned_names}", "INFO")
        self._refresh_optimization_window(message=f"Assigned top {len(assigned)} strategies to {symbol}.")
    except Exception as e:
        self.system_console.log(f"Strategy assignment failed: {e}", "ERROR")
        self._refresh_optimization_window(message=f"Strategy assignment failed: {e}")


def _hotfix_apply_best_optimization_params(self):
    apply_best_optimization_params(self)


def _hotfix_optimize_strategy(self):
    optimize_strategy(self)


def _hotfix_strategy_assignment_auto_status(self):
    controller = getattr(self, "controller", None)
    resolver = getattr(controller, "strategy_auto_assignment_status", None) if controller is not None else None
    if callable(resolver):
        try:
            status = dict(resolver() or {})
        except Exception:
            status = {}
    else:
        enabled = bool(getattr(controller, "strategy_auto_assignment_enabled", False)) if controller is not None else False
        status = {
            "enabled": enabled,
            "ready": not enabled or bool(getattr(controller, "strategy_auto_assignment_ready", False)),
            "running": bool(getattr(controller, "strategy_auto_assignment_in_progress", False)) if controller is not None else False,
            "completed": 0,
            "total": 0,
            "current_symbol": "",
            "message": "",
        }
    return status


def _hotfix_strategy_assignment_lock_message(self):
    status = _hotfix_strategy_assignment_auto_status(self)
    enabled = bool(status.get("enabled", False))
    ready = bool(status.get("ready", not enabled))
    if (not enabled) or ready:
        return ""

    custom_message = str(status.get("message") or "").strip()
    if custom_message:
        return custom_message

    completed = int(status.get("completed", 0) or 0)
    total = int(status.get("total", 0) or 0)
    current_symbol = str(status.get("current_symbol") or "").strip()
    if total > 0:
        suffix = f" Current symbol: {current_symbol}." if current_symbol else ""
        return f"Automatic strategy assignment is still scanning symbols ({completed}/{total}).{suffix}"
    return "Automatic strategy assignment is still scanning symbols."


def _hotfix_strategy_assignment_mode_label(mode):
    normalized = str(mode or "").strip().lower()
    if normalized == "single":
        return "Assigned Strategy"
    if normalized == "ranked":
        return "Ranked Mix"
    return "Default Strategy"


def _hotfix_strategy_assignment_rows(self):
    controller = getattr(self, "controller", None)
    if controller is None:
        return []

    symbols = []
    for source in (
        getattr(controller, "symbols", []) or [],
        list(getattr(controller, "symbol_strategy_assignments", {}).keys()),
        list(getattr(controller, "symbol_strategy_rankings", {}).keys()),
        [self._current_chart_symbol()] if hasattr(self, "_current_chart_symbol") else [],
    ):
        for symbol in list(source or []):
            normalized = str(symbol or "").strip().upper().replace("-", "/").replace("_", "/")
            if normalized and normalized not in symbols:
                symbols.append(normalized)

    rows = []
    state_resolver = getattr(controller, "strategy_assignment_state_for_symbol", None)
    default_strategy = str(getattr(controller, "strategy_name", "Trend Following") or "Trend Following").strip()
    default_timeframe = str(getattr(self, "current_timeframe", getattr(controller, "time_frame", "1h")) or "1h").strip()
    for symbol in symbols:
        state = state_resolver(symbol) if callable(state_resolver) else {}
        explicit_rows = list(state.get("explicit_rows", []) or [])
        active_rows = list(state.get("active_rows", []) or [])
        ranked_rows = list(state.get("ranked_rows", []) or [])
        mode = str(state.get("mode") or "default").strip().lower()
        timeframe = str(
            (explicit_rows[0].get("timeframe") if explicit_rows else "")
            or (active_rows[0].get("timeframe") if active_rows else "")
            or default_timeframe
        ).strip() or default_timeframe
        if active_rows:
            strategy_text = ", ".join(
                str(item.get("strategy_name") or "").strip()
                for item in active_rows[:3]
                if str(item.get("strategy_name") or "").strip()
            )
            if len(active_rows) > 3:
                strategy_text = f"{strategy_text}, +{len(active_rows) - 3} more"
        else:
            strategy_text = default_strategy
        rows.append(
            {
                "symbol": symbol,
                "mode": _hotfix_strategy_assignment_mode_label(mode),
                "strategies": strategy_text or default_strategy,
                "timeframe": timeframe,
                "ranked_count": len(ranked_rows),
                "active_count": len(active_rows),
            }
        )
    return rows


def _hotfix_refresh_strategy_assignment_window(self, window=None, message=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    if window is None:
        return

    status = getattr(window, "_strategy_assignment_status", None)
    summary = getattr(window, "_strategy_assignment_summary", None)
    symbol_picker = getattr(window, "_strategy_assignment_symbol_picker", None)
    strategy_picker = getattr(window, "_strategy_assignment_strategy_picker", None)
    timeframe_picker = getattr(window, "_strategy_assignment_timeframe_picker", None)
    top_n = getattr(window, "_strategy_assignment_top_n", None)
    table = getattr(window, "_strategy_assignment_table", None)
    agent_status = getattr(window, "_strategy_assignment_agent_status", None)
    agent_table = getattr(window, "_strategy_assignment_agent_table", None)
    if any(part is None for part in (status, summary, symbol_picker, strategy_picker, timeframe_picker, top_n, table)):
        return

    controller = getattr(self, "controller", None)
    if controller is None:
        return

    auto_status = _hotfix_strategy_assignment_auto_status(self)
    lock_message = _hotfix_strategy_assignment_lock_message(self)
    edits_locked = bool(lock_message)

    rows = _hotfix_strategy_assignment_rows(self)
    selected_symbol = str(
        getattr(window, "_strategy_assignment_selected_symbol", "")
        or symbol_picker.currentText()
        or (rows[0]["symbol"] if rows else "")
    ).strip()
    state_resolver = getattr(controller, "strategy_assignment_state_for_symbol", None)
    state = state_resolver(selected_symbol) if callable(state_resolver) and selected_symbol else {}
    explicit_rows = list(state.get("explicit_rows", []) or [])
    active_rows = list(state.get("active_rows", []) or [])
    ranked_rows = list(state.get("ranked_rows", []) or [])
    default_strategy = str(getattr(controller, "strategy_name", "Trend Following") or "Trend Following").strip()
    selected_strategy = str(
        (explicit_rows[0].get("strategy_name") if explicit_rows else "")
        or (active_rows[0].get("strategy_name") if active_rows else "")
        or default_strategy
    ).strip()
    selected_timeframe = str(
        (explicit_rows[0].get("timeframe") if explicit_rows else "")
        or (active_rows[0].get("timeframe") if active_rows else "")
        or getattr(self, "current_timeframe", getattr(controller, "time_frame", "1h"))
    ).strip()

    setattr(self, "_strategy_assignment_bootstrapping", True)
    try:
        current_symbols = [row["symbol"] for row in rows]
        blocked = symbol_picker.blockSignals(True)
        symbol_picker.clear()
        for symbol in current_symbols:
            symbol_picker.addItem(symbol)
        if selected_symbol and symbol_picker.findText(selected_symbol) < 0:
            symbol_picker.addItem(selected_symbol)
        if selected_symbol:
            symbol_picker.setCurrentText(selected_symbol)
        symbol_picker.blockSignals(blocked)

        self._populate_strategy_picker(strategy_picker, selected_strategy=selected_strategy)

        timeframe_candidates = _hotfix_backtest_timeframe_candidates(self)
        blocked = timeframe_picker.blockSignals(True)
        timeframe_picker.clear()
        for timeframe in timeframe_candidates:
            timeframe_picker.addItem(timeframe)
        if selected_timeframe and timeframe_picker.findText(selected_timeframe) < 0:
            timeframe_picker.addItem(selected_timeframe)
        if selected_timeframe:
            timeframe_picker.setCurrentText(selected_timeframe)
        timeframe_picker.blockSignals(blocked)

        top_n.setValue(max(1, min(10, len(explicit_rows) if len(explicit_rows) > 1 else int(getattr(controller, "max_symbol_strategies", 3) or 3))))
    finally:
        setattr(self, "_strategy_assignment_bootstrapping", False)

    window._strategy_assignment_selected_symbol = selected_symbol
    status.setText(message or lock_message or "Assign a symbol to the default strategy, one strategy, or a ranked mix.")

    mode_label = _hotfix_strategy_assignment_mode_label(state.get("mode"))
    active_text = ", ".join(
        str(item.get("strategy_name") or "").strip()
        for item in active_rows[:3]
        if str(item.get("strategy_name") or "").strip()
    ) or default_strategy
    if len(active_rows) > 3:
        active_text = f"{active_text}, +{len(active_rows) - 3} more"
    decision_chain_resolver = getattr(controller, "latest_agent_decision_chain_for_symbol", None)
    decision_overview_resolver = getattr(controller, "latest_agent_decision_overview_for_symbol", None)
    decision_chain = []
    if callable(decision_chain_resolver) and selected_symbol:
        try:
            decision_chain = list(decision_chain_resolver(selected_symbol, limit=12) or [])
        except Exception:
            decision_chain = []
    decision_overview = {}
    if callable(decision_overview_resolver) and selected_symbol:
        try:
            decision_overview = dict(decision_overview_resolver(selected_symbol) or {})
        except Exception:
            decision_overview = {}

    auto_suffix = ""
    if bool(auto_status.get("enabled", False)):
        if edits_locked:
            completed = int(auto_status.get("completed", 0) or 0)
            total = int(auto_status.get("total", 0) or 0)
            auto_suffix = f" | Auto Scan: {completed}/{total}"
        else:
            auto_suffix = " | Auto Scan: Ready"
    agent_suffix = f" | Agent Steps: {len(decision_chain)}"
    agent_best_strategy = str(decision_overview.get("strategy_name") or "").strip()
    agent_best_timeframe = str(decision_overview.get("timeframe") or "").strip()
    if agent_best_strategy:
        label = f"{agent_best_strategy} ({agent_best_timeframe or '-'})"
        agent_suffix = f"{agent_suffix} | Agent Best: {label}"
    adaptive_profiles = []
    adaptive_profiles_resolver = getattr(controller, "adaptive_strategy_profiles_for_symbol", None)
    if callable(adaptive_profiles_resolver) and selected_symbol:
        try:
            adaptive_profiles = [
                dict(item)
                for item in (adaptive_profiles_resolver(selected_symbol) or [])
                if isinstance(item, dict)
            ]
        except Exception:
            adaptive_profiles = []
    adaptive_profiles.sort(
        key=lambda item: _coerce_float(item.get("adaptive_weight")) or 0.0,
        reverse=True,
    )
    adaptive_suffix = ""
    adaptive_leader = adaptive_profiles[0] if adaptive_profiles else {}
    adaptive_leader_name = str(adaptive_leader.get("strategy_name") or "").strip()
    adaptive_leader_weight = _coerce_float(adaptive_leader.get("adaptive_weight"))
    if adaptive_leader_name and adaptive_leader_weight is not None:
        adaptive_suffix = f" | Adaptive Leader: {adaptive_leader_name} x{adaptive_leader_weight:.2f}"
    summary.setText(
        f"Selected Symbol: {selected_symbol or '-'} | Mode: {mode_label} | "
        f"Trading With: {active_text} | Ranked Candidates: {len(ranked_rows)}{auto_suffix}{agent_suffix}{adaptive_suffix}"
    )

    use_default_btn = getattr(window, "_strategy_assignment_use_default_btn", None)
    assign_single_btn = getattr(window, "_strategy_assignment_assign_single_btn", None)
    assign_ranked_btn = getattr(window, "_strategy_assignment_assign_ranked_btn", None)
    strategy_picker.setEnabled(not edits_locked)
    timeframe_picker.setEnabled(not edits_locked)
    top_n.setEnabled(not edits_locked)
    if use_default_btn is not None:
        use_default_btn.setEnabled(not edits_locked)
    if assign_single_btn is not None:
        assign_single_btn.setEnabled(not edits_locked)
    if assign_ranked_btn is not None:
        assign_ranked_btn.setEnabled(not edits_locked)

    table.setColumnCount(6)
    table.setHorizontalHeaderLabels(["Symbol", "Mode", "Strategies", "Timeframe", "Ranked", "Live"])
    table.setRowCount(len(rows))
    selected_row = -1
    for row_index, row in enumerate(rows):
        values = [
            row.get("symbol", ""),
            row.get("mode", ""),
            row.get("strategies", ""),
            row.get("timeframe", ""),
            str(row.get("ranked_count", 0)),
            f"{int(row.get('active_count', 0))} {'strategy' if int(row.get('active_count', 0)) == 1 else 'strategies'}",
        ]
        for col_index, value in enumerate(values):
            table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        if str(row.get("symbol") or "").strip() == selected_symbol:
            selected_row = row_index
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(True)
    if selected_row >= 0:
        table.selectRow(selected_row)

    if agent_status is not None:
        if decision_chain:
            final_agent = str(decision_overview.get("final_agent") or decision_chain[-1].get("agent_name") or "").strip()
            final_stage = str(decision_overview.get("final_stage") or decision_chain[-1].get("stage") or "").strip()
            timestamp_label = str(decision_overview.get("timestamp_label") or decision_chain[-1].get("timestamp_label") or "").strip()
            detail = f"Latest Agent Chain: {len(decision_chain)} steps"
            if final_agent or final_stage:
                detail = f"{detail} | Final: {final_agent or '-'} / {final_stage or '-'}"
            if timestamp_label:
                detail = f"{detail} | {timestamp_label}"
            agent_status.setText(detail)
        else:
            agent_status.setText("Latest Agent Chain: no stored decision yet for the selected symbol.")

    if agent_table is not None:
        agent_table.setColumnCount(6)
        agent_table.setHorizontalHeaderLabels(["Agent", "Stage", "Strategy", "Timeframe", "Detail", "Time"])
        agent_table.setRowCount(len(decision_chain))
        for row_index, row in enumerate(decision_chain):
            payload = dict(row.get("payload") or {})
            detail = str(row.get("reason") or payload.get("regime") or payload.get("volatility") or payload.get("execution_strategy") or "").strip()
            values = [
                row.get("agent_name", ""),
                row.get("stage", ""),
                row.get("strategy_name", ""),
                row.get("timeframe", ""),
                detail,
                row.get("timestamp_label", ""),
            ]
            for col_index, value in enumerate(values):
                agent_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        agent_table.resizeColumnsToContents()
        agent_table.horizontalHeader().setStretchLastSection(True)

    adaptive_status = getattr(window, "_strategy_assignment_adaptive_status", None)
    adaptive_table = getattr(window, "_strategy_assignment_adaptive_table", None)
    if adaptive_status is not None:
        if adaptive_profiles:
            leader_timeframe = str(adaptive_leader.get("timeframe") or "-").strip() or "-"
            leader_weight_text = (
                f"{adaptive_leader_weight:.2f}" if adaptive_leader_weight is not None else "-"
            )
            adaptive_status.setText(
                f"Adaptive Memory: {len(adaptive_profiles)} strategy profiles | "
                f"Leader: {adaptive_leader_name} ({leader_timeframe}) x{leader_weight_text}"
            )
        else:
            adaptive_status.setText("Adaptive Memory: no stored strategy profiles for the selected symbol.")
    if adaptive_table is not None:
        adaptive_table.setColumnCount(8)
        adaptive_table.setHorizontalHeaderLabels(
            ["Strategy", "Timeframe", "Mode", "Weight", "Samples", "Win Rate", "Avg P/L", "Scope"]
        )
        adaptive_table.setRowCount(len(adaptive_profiles))
        for row_index, profile in enumerate(adaptive_profiles):
            values = [
                str(profile.get("strategy_name") or ""),
                str(profile.get("timeframe") or ""),
                str(profile.get("mode") or ""),
                f"{(_coerce_float(profile.get('adaptive_weight')) or 0.0):.2f}",
                str(int(_coerce_float(profile.get("sample_size")) or 0)),
                f"{(_coerce_float(profile.get('win_rate')) or 0.0):.0%}",
                f"{(_coerce_float(profile.get('average_pnl')) or 0.0):.2f}",
                str(profile.get("scope") or ""),
            ]
            for col_index, value in enumerate(values):
                adaptive_table.setItem(row_index, col_index, QTableWidgetItem(value))
        adaptive_table.resizeColumnsToContents()
        adaptive_table.horizontalHeader().setStretchLastSection(True)
    if adaptive_profiles:
        _hotfix_refresh_strategy_assignment_adaptive_details(
            self,
            window=window,
            selected_symbol=selected_symbol,
            strategy_name=adaptive_leader_name,
            timeframe=str(adaptive_leader.get("timeframe") or "").strip() or None,
        )
    else:
        adaptive_plot_status = getattr(window, "_strategy_assignment_adaptive_plot_status", None)
        adaptive_plot = getattr(window, "_strategy_assignment_adaptive_plot", None)
        adaptive_details = getattr(window, "_strategy_assignment_adaptive_details", None)
        if adaptive_plot_status is not None:
            adaptive_plot_status.setText("Adaptive history: no scored trades for the selected symbol.")
        if adaptive_plot is not None and hasattr(adaptive_plot, "clear"):
            adaptive_plot.clear()
        if adaptive_details is not None:
            adaptive_details.setHtml("<h3>Adaptive detail</h3><p>No adaptive-memory samples are available yet.</p>")


def _hotfix_refresh_strategy_assignment_adaptive_details(
    self,
    window=None,
    selected_symbol=None,
    strategy_name=None,
    timeframe=None,
):
    window = window or getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    if window is None:
        return

    details = getattr(window, "_strategy_assignment_adaptive_details", None)
    plot_status = getattr(window, "_strategy_assignment_adaptive_plot_status", None)
    plot = getattr(window, "_strategy_assignment_adaptive_plot", None)
    if details is None and plot_status is None and plot is None:
        return

    controller = getattr(self, "controller", None)
    if controller is None:
        return

    normalized_symbol = str(
        selected_symbol
        or getattr(window, "_strategy_assignment_selected_symbol", "")
        or getattr(getattr(window, "_strategy_assignment_symbol_picker", None), "currentText", lambda: "")()
    ).strip()
    normalized_strategy = str(strategy_name or "").strip()
    normalized_timeframe = str(timeframe or "").strip() or None
    if not normalized_symbol or not normalized_strategy:
        if plot_status is not None:
            plot_status.setText("Adaptive history: select a strategy profile to inspect scored trades.")
        if plot is not None and hasattr(plot, "clear"):
            plot.clear()
        if details is not None:
            details.setHtml("<h3>Adaptive detail</h3><p>Select a strategy profile to inspect its scored trades.</p>")
        return

    detail_payload = {}
    detail_resolver = getattr(controller, "adaptive_strategy_detail_for_symbol", None)
    if callable(detail_resolver):
        try:
            detail_payload = dict(
                detail_resolver(
                    normalized_symbol,
                    normalized_strategy,
                    timeframe=normalized_timeframe,
                    limit=8,
                )
                or {}
            )
        except Exception:
            detail_payload = {}

    timeline_payload = {}
    timeline_resolver = getattr(controller, "adaptive_strategy_timeline_for_symbol", None)
    if callable(timeline_resolver):
        try:
            timeline_payload = dict(
                timeline_resolver(
                    normalized_symbol,
                    normalized_strategy,
                    timeframe=normalized_timeframe,
                    limit=16,
                )
                or {}
            )
        except Exception:
            timeline_payload = {}

    profile = dict(detail_payload.get("profile") or timeline_payload.get("profile") or {})
    samples = [
        dict(item)
        for item in (detail_payload.get("samples") or [])
        if isinstance(item, dict)
    ]
    timeline = [
        dict(item)
        for item in (timeline_payload.get("timeline") or [])
        if isinstance(item, dict)
    ]

    if plot is not None and hasattr(plot, "clear"):
        plot.clear()
        if timeline:
            x_values = []
            y_values = []
            for index, entry in enumerate(timeline):
                x_values.append(_coerce_float(entry.get("timestamp_value")) or float(index))
                y_values.append(_coerce_float(entry.get("adaptive_weight")) or 0.0)
            plot.plot(
                x_values,
                y_values,
                pen=pg.mkPen("#2a7fff", width=2),
                symbol="o",
                symbolSize=7,
                symbolBrush=pg.mkBrush("#4fd1c5"),
            )

    current_weight = _coerce_float(profile.get("adaptive_weight"))
    if current_weight is None and timeline:
        current_weight = _coerce_float(timeline[-1].get("adaptive_weight"))
    sample_count = len(samples) if samples else len(timeline)
    if plot_status is not None:
        status_text = f"Adaptive history: {sample_count} scored trades"
        if current_weight is not None:
            status_text = f"{status_text} | Current {current_weight:.2f}"
        plot_status.setText(status_text)

    if details is not None:
        scope = html.escape(str(detail_payload.get("scope") or timeline_payload.get("scope") or "strategy"))
        header = (
            f"<h3>Adaptive detail</h3>"
            f"<p><b>{html.escape(normalized_strategy)}</b> | Symbol {html.escape(normalized_symbol)}"
            f" | Timeframe {html.escape(normalized_timeframe or '-')} | Scope {scope}</p>"
        )
        summary_bits = []
        if current_weight is not None:
            summary_bits.append(f"Current weight <b>{current_weight:.2f}</b>")
        sample_size = int(_coerce_float(profile.get("sample_size")) or 0)
        if sample_size:
            summary_bits.append(f"Sample size <b>{sample_size}</b>")
        win_rate = _coerce_float(profile.get("win_rate"))
        if win_rate is not None:
            summary_bits.append(f"Win rate <b>{win_rate:.0%}</b>")
        average_pnl = _coerce_float(profile.get("average_pnl"))
        if average_pnl is not None:
            summary_bits.append(f"Average P/L <b>{average_pnl:.2f}</b>")
        summary_html = f"<p>{' | '.join(summary_bits)}</p>" if summary_bits else ""
        history_items = []
        for sample in samples:
            timestamp = html.escape(str(sample.get("timestamp") or "-"))
            side = html.escape(str(sample.get("side") or "-"))
            pnl = _coerce_float(sample.get("pnl"))
            score = _coerce_float(sample.get("score"))
            reason = html.escape(str(sample.get("reason") or "").strip() or "-")
            pnl_text = f"{pnl:.2f}" if pnl is not None else "-"
            score_text = f"{score:.2f}" if score is not None else "-"
            history_items.append(
                "<li>"
                f"<b>{timestamp}</b> | {side} | "
                f"P/L {pnl_text} | Score {score_text} | {reason}"
                "</li>"
            )
        if history_items:
            details.setHtml(header + summary_html + "<ul>" + "".join(history_items) + "</ul>")
        else:
            details.setHtml(header + summary_html + "<p>No scored trades are stored for this profile yet.</p>")


def _hotfix_strategy_assignment_selection_changed(self):
    if bool(getattr(self, "_strategy_assignment_bootstrapping", False)):
        return
    window = getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    if window is None:
        return
    symbol_picker = getattr(window, "_strategy_assignment_symbol_picker", None)
    if symbol_picker is None:
        return
    window._strategy_assignment_selected_symbol = str(symbol_picker.currentText() or "").strip()
    _hotfix_refresh_strategy_assignment_window(self, window=window)


def _hotfix_strategy_assignment_table_selected(self):
    window = getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    if window is None or bool(getattr(self, "_strategy_assignment_bootstrapping", False)):
        return
    table = getattr(window, "_strategy_assignment_table", None)
    symbol_picker = getattr(window, "_strategy_assignment_symbol_picker", None)
    if table is None or symbol_picker is None or table.currentRow() < 0:
        return
    item = table.item(table.currentRow(), 0)
    symbol = str(item.text() if item is not None else "").strip()
    if not symbol:
        return
    blocked = symbol_picker.blockSignals(True)
    symbol_picker.setCurrentText(symbol)
    symbol_picker.blockSignals(blocked)
    window._strategy_assignment_selected_symbol = symbol
    _hotfix_refresh_strategy_assignment_window(self, window=window)


def _hotfix_apply_default_strategy_assignment(self):
    window = getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    controller = getattr(self, "controller", None)
    if window is None or controller is None:
        return
    lock_message = _hotfix_strategy_assignment_lock_message(self)
    if lock_message:
        self.system_console.log(lock_message, "WARN")
        _hotfix_refresh_strategy_assignment_window(self, window=window, message=lock_message)
        return
    symbol_picker = getattr(window, "_strategy_assignment_symbol_picker", None)
    symbol = str(symbol_picker.currentText() if symbol_picker is not None else "").strip()
    if not symbol:
        self.system_console.log("Select a symbol before clearing its strategy assignment.", "ERROR")
        return
    controller.clear_symbol_strategy_assignment(symbol)
    _hotfix_refresh_strategy_assignment_window(
        self,
        window=window,
        message=f"{symbol} now uses the default strategy with the rest of the system.",
    )


def _hotfix_apply_single_strategy_assignment(self):
    window = getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    controller = getattr(self, "controller", None)
    if window is None or controller is None:
        return
    lock_message = _hotfix_strategy_assignment_lock_message(self)
    if lock_message:
        self.system_console.log(lock_message, "WARN")
        _hotfix_refresh_strategy_assignment_window(self, window=window, message=lock_message)
        return
    symbol_picker = getattr(window, "_strategy_assignment_symbol_picker", None)
    strategy_picker = getattr(window, "_strategy_assignment_strategy_picker", None)
    timeframe_picker = getattr(window, "_strategy_assignment_timeframe_picker", None)
    symbol = str(symbol_picker.currentText() if symbol_picker is not None else "").strip()
    strategy_name = str(strategy_picker.currentText() if strategy_picker is not None else "").strip()
    timeframe = str(timeframe_picker.currentText() if timeframe_picker is not None else "").strip()
    if not symbol:
        self.system_console.log("Select a symbol before assigning a strategy.", "ERROR")
        return
    try:
        assigned = controller.assign_strategy_to_symbol(symbol, strategy_name, timeframe=timeframe)
        strategy_label = str(assigned[0].get("strategy_name") or strategy_name).strip()
        _hotfix_refresh_strategy_assignment_window(
            self,
            window=window,
            message=f"{symbol} is now assigned to {strategy_label}.",
        )
    except Exception as exc:
        self.system_console.log(f"Strategy assignment failed: {exc}", "ERROR")
        _hotfix_refresh_strategy_assignment_window(self, window=window, message=f"Strategy assignment failed: {exc}")


def _hotfix_apply_ranked_strategy_assignment_from_window(self):
    window = getattr(self, "detached_tool_windows", {}).get("strategy_assignments")
    controller = getattr(self, "controller", None)
    if window is None or controller is None:
        return
    lock_message = _hotfix_strategy_assignment_lock_message(self)
    if lock_message:
        self.system_console.log(lock_message, "WARN")
        _hotfix_refresh_strategy_assignment_window(self, window=window, message=lock_message)
        return
    symbol_picker = getattr(window, "_strategy_assignment_symbol_picker", None)
    timeframe_picker = getattr(window, "_strategy_assignment_timeframe_picker", None)
    top_n = getattr(window, "_strategy_assignment_top_n", None)
    symbol = str(symbol_picker.currentText() if symbol_picker is not None else "").strip()
    timeframe = str(timeframe_picker.currentText() if timeframe_picker is not None else "").strip()
    if not symbol:
        self.system_console.log("Select a symbol before assigning a ranked mix.", "ERROR")
        return
    rankings = controller.ranked_strategies_for_symbol(symbol) if hasattr(controller, "ranked_strategies_for_symbol") else []
    if not rankings:
        self.system_console.log(f"No ranked strategies are saved for {symbol}. Run Rank All Strategies first.", "ERROR")
        _hotfix_refresh_strategy_assignment_window(
            self,
            window=window,
            message=f"No ranked strategies are saved for {symbol} yet. Run Rank All Strategies first.",
        )
        return
    assigned = controller.assign_ranked_strategies_to_symbol(
        symbol,
        rankings,
        top_n=int(top_n.value()) if top_n is not None else None,
        timeframe=timeframe,
    )
    _hotfix_refresh_strategy_assignment_window(
        self,
        window=window,
        message=f"{symbol} now uses a ranked mix of {len(assigned)} strategies.",
    )


def _hotfix_show_strategy_assignment_window(self):
    window = self._get_or_create_tool_window(
        "strategy_assignments",
        "Strategy Assigner",
        width=1080,
        height=680,
    )

    if getattr(window, "_strategy_assignment_container", None) is None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        status = QLabel("Assign a symbol to the default strategy, one strategy, or a ranked mix.")
        status.setWordWrap(True)
        status.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; padding: 10px; border-radius: 8px;")
        layout.addWidget(status)

        controls_frame = QFrame()
        controls_frame.setStyleSheet(
            "QFrame { background-color: #0f1727; border: 1px solid #24344f; border-radius: 10px; }"
            "QLabel { color: #d7dfeb; font-weight: 700; }"
            "QComboBox, QSpinBox { background-color: #0b1220; color: #f4f8ff; border: 1px solid #2a3d5c; border-radius: 6px; padding: 6px 10px; min-width: 160px; }"
        )
        controls_layout = QGridLayout(controls_frame)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setHorizontalSpacing(16)
        controls_layout.setVerticalSpacing(8)

        symbol_picker = QComboBox()
        strategy_picker = QComboBox()
        timeframe_picker = QComboBox()
        top_n = QSpinBox()
        top_n.setRange(1, 10)
        top_n.setValue(int(getattr(self.controller, "max_symbol_strategies", 3) or 3))

        controls_layout.addWidget(QLabel("Symbol"), 0, 0)
        controls_layout.addWidget(symbol_picker, 0, 1)
        controls_layout.addWidget(QLabel("Assigned Strategy"), 0, 2)
        controls_layout.addWidget(strategy_picker, 0, 3)
        controls_layout.addWidget(QLabel("Timeframe"), 1, 0)
        controls_layout.addWidget(timeframe_picker, 1, 1)
        controls_layout.addWidget(QLabel("Ranked Mix Size"), 1, 2)
        controls_layout.addWidget(top_n, 1, 3)
        layout.addWidget(controls_frame)

        button_row = QHBoxLayout()
        use_default_btn = QPushButton("Use Default")
        assign_single_btn = QPushButton("Assign Strategy")
        assign_ranked_btn = QPushButton("Use Ranked Mix")
        open_optimization_btn = QPushButton("Open Strategy Optimization")
        use_default_btn.clicked.connect(self._apply_default_strategy_assignment)
        assign_single_btn.clicked.connect(self._apply_single_strategy_assignment)
        assign_ranked_btn.clicked.connect(self._apply_ranked_strategy_assignment)
        open_optimization_btn.clicked.connect(self._optimize_strategy)
        button_row.addWidget(use_default_btn)
        button_row.addWidget(assign_single_btn)
        button_row.addWidget(assign_ranked_btn)
        button_row.addWidget(open_optimization_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        summary = QLabel("Loading symbol assignments.")
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #9fb0c7;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.itemSelectionChanged.connect(lambda: _hotfix_strategy_assignment_table_selected(self))
        layout.addWidget(table)

        agent_status = QLabel("Latest agent chain will appear once the selected symbol has been processed.")
        agent_status.setWordWrap(True)
        agent_status.setStyleSheet("color: #9fb0c7; font-style: italic;")
        layout.addWidget(agent_status)

        agent_table = QTableWidget()
        agent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        agent_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        agent_table.setMinimumHeight(180)
        layout.addWidget(agent_table)

        symbol_picker.currentTextChanged.connect(lambda _text: _hotfix_strategy_assignment_selection_changed(self))
        strategy_picker.currentTextChanged.connect(lambda _text: _hotfix_strategy_assignment_selection_changed(self))
        timeframe_picker.currentTextChanged.connect(lambda _text: _hotfix_strategy_assignment_selection_changed(self))

        window.setCentralWidget(container)
        window._strategy_assignment_container = container
        window._strategy_assignment_status = status
        window._strategy_assignment_summary = summary
        window._strategy_assignment_symbol_picker = symbol_picker
        window._strategy_assignment_strategy_picker = strategy_picker
        window._strategy_assignment_timeframe_picker = timeframe_picker
        window._strategy_assignment_top_n = top_n
        window._strategy_assignment_table = table
        window._strategy_assignment_agent_status = agent_status
        window._strategy_assignment_agent_table = agent_table
        window._strategy_assignment_use_default_btn = use_default_btn
        window._strategy_assignment_assign_single_btn = assign_single_btn
        window._strategy_assignment_assign_ranked_btn = assign_ranked_btn
        window._strategy_assignment_open_optimization_btn = open_optimization_btn

    _hotfix_refresh_strategy_assignment_window(self, window=window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def _hotfix_ml_model_family_options():
    return [
        ("Linear", "linear"),
        ("Tree Ensemble", "tree"),
        ("Sequence Linear", "sequence"),
    ]


def _hotfix_get_ml_pipeline(self):
    pipeline = getattr(self, "_ml_research_pipeline", None)
    if pipeline is None:
        pipeline = MLResearchPipeline()
        self._ml_research_pipeline = pipeline
    return pipeline


def _hotfix_show_ml_research_window(self):
    window = self._get_or_create_tool_window(
        "ml_research_lab",
        "ML Research Lab",
        width=1180,
        height=760,
    )

    if getattr(window, "_ml_research_container", None) is None:
        container = QWidget()
        layout = QVBoxLayout(container)

        status = QLabel("ML research workspace ready.")
        status.setStyleSheet("color: #e6edf7; font-weight: 700;")
        layout.addWidget(status)

        selection_frame = QFrame()
        selection_frame.setStyleSheet(
            "QFrame { background-color: #0f1727; border: 1px solid #24344f; border-radius: 10px; }"
            "QLabel { color: #d7dfeb; font-weight: 700; }"
            "QComboBox, QDoubleSpinBox { background-color: #0b1220; color: #f4f8ff; border: 1px solid #2a3d5c; border-radius: 6px; padding: 6px 10px; min-width: 140px; }"
        )
        selection_layout = QGridLayout(selection_frame)
        selection_layout.setContentsMargins(14, 12, 14, 12)
        selection_layout.setHorizontalSpacing(16)
        selection_layout.setVerticalSpacing(8)

        symbol_picker = QComboBox()
        timeframe_picker = QComboBox()
        family_picker = QComboBox()
        for label, value in _hotfix_ml_model_family_options():
            family_picker.addItem(label, value)

        horizon_spin = QDoubleSpinBox()
        horizon_spin.setDecimals(0)
        horizon_spin.setRange(1, 50)
        horizon_spin.setValue(3)

        threshold_spin = QDoubleSpinBox()
        threshold_spin.setDecimals(4)
        threshold_spin.setRange(0.0, 0.25)
        threshold_spin.setSingleStep(0.0005)
        threshold_spin.setValue(0.0015)

        test_size_spin = QDoubleSpinBox()
        test_size_spin.setDecimals(2)
        test_size_spin.setRange(0.10, 0.50)
        test_size_spin.setSingleStep(0.05)
        test_size_spin.setValue(0.25)

        sequence_spin = QDoubleSpinBox()
        sequence_spin.setDecimals(0)
        sequence_spin.setRange(2, 12)
        sequence_spin.setValue(4)

        train_window_spin = QDoubleSpinBox()
        train_window_spin.setDecimals(0)
        train_window_spin.setRange(20, 5000)
        train_window_spin.setValue(80)

        test_window_spin = QDoubleSpinBox()
        test_window_spin.setDecimals(0)
        test_window_spin.setRange(10, 1000)
        test_window_spin.setValue(30)

        selection_layout.addWidget(QLabel("Symbol"), 0, 0)
        selection_layout.addWidget(symbol_picker, 0, 1)
        selection_layout.addWidget(QLabel("Timeframe"), 0, 2)
        selection_layout.addWidget(timeframe_picker, 0, 3)
        selection_layout.addWidget(QLabel("Model Family"), 0, 4)
        selection_layout.addWidget(family_picker, 0, 5)
        selection_layout.addWidget(QLabel("Horizon"), 1, 0)
        selection_layout.addWidget(horizon_spin, 1, 1)
        selection_layout.addWidget(QLabel("Return Threshold"), 1, 2)
        selection_layout.addWidget(threshold_spin, 1, 3)
        selection_layout.addWidget(QLabel("Test Size"), 1, 4)
        selection_layout.addWidget(test_size_spin, 1, 5)
        selection_layout.addWidget(QLabel("Sequence Length"), 2, 0)
        selection_layout.addWidget(sequence_spin, 2, 1)
        selection_layout.addWidget(QLabel("WF Train"), 2, 2)
        selection_layout.addWidget(train_window_spin, 2, 3)
        selection_layout.addWidget(QLabel("WF Test"), 2, 4)
        selection_layout.addWidget(test_window_spin, 2, 5)
        layout.addWidget(selection_frame)

        controls = QHBoxLayout()
        train_btn = QPushButton("Train Model")
        walk_forward_btn = QPushButton("Run Walk-Forward")
        auto_research_btn = QPushButton("Auto Research Best")
        auto_deploy_btn = QPushButton("Auto Deploy Best")
        deploy_btn = QPushButton("Deploy Selected")
        train_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(self._run_ml_model_training()))
        walk_forward_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(self._run_ml_walk_forward()))
        auto_research_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(self._run_ml_auto_research()))
        auto_deploy_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(self._run_ml_auto_research(auto_deploy=True)))
        deploy_btn.clicked.connect(self._deploy_selected_ml_model)
        controls.addWidget(train_btn)
        controls.addWidget(walk_forward_btn)
        controls.addWidget(auto_research_btn)
        controls.addWidget(auto_deploy_btn)
        controls.addWidget(deploy_btn)
        controls.addStretch()
        layout.addLayout(controls)

        summary = QLabel("-")
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #9fb0c7;")
        layout.addWidget(summary)

        tabs = QTabWidget()

        experiments_table = QTableWidget()
        experiments_table.setAlternatingRowColors(True)
        experiments_table.setSelectionBehavior(QTableWidget.SelectRows)
        experiments_table.setSelectionMode(QTableWidget.SingleSelection)
        experiments_table.setColumnCount(8)
        experiments_table.setHorizontalHeaderLabels(
            ["Experiment", "Model", "Family", "Symbol", "TF", "Test Acc", "Precision", "Created"]
        )
        tabs.addTab(experiments_table, "Experiments")

        walk_table = QTableWidget()
        walk_table.setAlternatingRowColors(True)
        walk_table.setColumnCount(7)
        walk_table.setHorizontalHeaderLabels(
            ["Window", "Train Rows", "Test Rows", "Accuracy", "Precision", "Recall", "Avg Conf."]
        )
        tabs.addTab(walk_table, "Walk-Forward")

        leaderboard_table = QTableWidget()
        leaderboard_table.setAlternatingRowColors(True)
        leaderboard_table.setSelectionBehavior(QTableWidget.SelectRows)
        leaderboard_table.setSelectionMode(QTableWidget.SingleSelection)
        leaderboard_table.setColumnCount(8)
        leaderboard_table.setHorizontalHeaderLabels(
            ["Model", "Family", "Seq", "Score", "WF Acc", "WF Prec", "Test Acc", "Test Prec"]
        )
        tabs.addTab(leaderboard_table, "Leaderboard")

        details = QTextBrowser()
        details.setStyleSheet(
            "QTextBrowser { background-color: #0b1220; color: #d7dfeb; border: 1px solid #24344f; border-radius: 10px; padding: 10px; }"
        )
        tabs.addTab(details, "Details")
        layout.addWidget(tabs)

        window.setCentralWidget(container)
        window._ml_research_container = container
        window._ml_research_status = status
        window._ml_research_summary = summary
        window._ml_research_symbol_picker = symbol_picker
        window._ml_research_timeframe_picker = timeframe_picker
        window._ml_research_family_picker = family_picker
        window._ml_research_horizon_spin = horizon_spin
        window._ml_research_threshold_spin = threshold_spin
        window._ml_research_test_size_spin = test_size_spin
        window._ml_research_sequence_spin = sequence_spin
        window._ml_research_train_window_spin = train_window_spin
        window._ml_research_test_window_spin = test_window_spin
        window._ml_research_train_btn = train_btn
        window._ml_research_walk_btn = walk_forward_btn
        window._ml_research_auto_btn = auto_research_btn
        window._ml_research_auto_deploy_btn = auto_deploy_btn
        window._ml_research_deploy_btn = deploy_btn
        window._ml_research_experiments_table = experiments_table
        window._ml_research_walk_table = walk_table
        window._ml_research_leaderboard_table = leaderboard_table
        window._ml_research_details = details

        symbol_picker.currentTextChanged.connect(lambda _text: _hotfix_ml_research_selection_changed(self))
        timeframe_picker.currentTextChanged.connect(lambda _text: _hotfix_ml_research_selection_changed(self))
        family_picker.currentIndexChanged.connect(lambda _idx: _hotfix_ml_research_selection_changed(self))
        horizon_spin.valueChanged.connect(lambda _v: _hotfix_ml_research_selection_changed(self))
        threshold_spin.valueChanged.connect(lambda _v: _hotfix_ml_research_selection_changed(self))
        test_size_spin.valueChanged.connect(lambda _v: _hotfix_ml_research_selection_changed(self))
        sequence_spin.valueChanged.connect(lambda _v: _hotfix_ml_research_selection_changed(self))
        train_window_spin.valueChanged.connect(lambda _v: _hotfix_ml_research_selection_changed(self))
        test_window_spin.valueChanged.connect(lambda _v: _hotfix_ml_research_selection_changed(self))
        experiments_table.itemSelectionChanged.connect(lambda: self._refresh_ml_research_window())
        leaderboard_table.itemSelectionChanged.connect(lambda: self._refresh_ml_research_window())

    _hotfix_refresh_ml_research_selectors(self, window)
    self._refresh_ml_research_window(window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def _hotfix_refresh_ml_research_selectors(self, window=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("ml_research_lab")
    if window is None:
        return
    symbol_picker = getattr(window, "_ml_research_symbol_picker", None)
    timeframe_picker = getattr(window, "_ml_research_timeframe_picker", None)
    family_picker = getattr(window, "_ml_research_family_picker", None)
    if symbol_picker is None or timeframe_picker is None or family_picker is None:
        return

    context = getattr(self, "_ml_research_context", {}) or {}
    symbol_candidates = _hotfix_backtest_symbol_candidates(self)
    timeframe_candidates = _hotfix_backtest_timeframe_candidates(self)
    target_symbol = str(context.get("symbol") or symbol_picker.currentText() or (symbol_candidates[0] if symbol_candidates else "")).strip()
    target_timeframe = str(context.get("timeframe") or timeframe_picker.currentText() or getattr(self, "current_timeframe", getattr(self.controller, "time_frame", "1h"))).strip()
    target_family = str(context.get("model_family") or family_picker.currentData() or "linear").strip()

    symbol_picker.blockSignals(True)
    symbol_picker.clear()
    for symbol in symbol_candidates:
        symbol_picker.addItem(symbol)
    if target_symbol and symbol_picker.findText(target_symbol) < 0:
        symbol_picker.addItem(target_symbol)
    if target_symbol:
        symbol_picker.setCurrentText(target_symbol)
    symbol_picker.blockSignals(False)

    timeframe_picker.blockSignals(True)
    timeframe_picker.clear()
    for timeframe in timeframe_candidates:
        timeframe_picker.addItem(timeframe)
    if target_timeframe and timeframe_picker.findText(target_timeframe) < 0:
        timeframe_picker.addItem(target_timeframe)
    timeframe_picker.setCurrentText(target_timeframe)
    timeframe_picker.blockSignals(False)

    for idx in range(family_picker.count()):
        if str(family_picker.itemData(idx)) == target_family:
            family_picker.blockSignals(True)
            family_picker.setCurrentIndex(idx)
            family_picker.blockSignals(False)
            break


def _hotfix_ml_research_selection_changed(self):
    if bool(getattr(self, "_ml_research_running", False)):
        return

    window = getattr(self, "detached_tool_windows", {}).get("ml_research_lab")
    if window is None:
        return

    symbol_picker = getattr(window, "_ml_research_symbol_picker", None)
    timeframe_picker = getattr(window, "_ml_research_timeframe_picker", None)
    family_picker = getattr(window, "_ml_research_family_picker", None)
    if symbol_picker is None or timeframe_picker is None or family_picker is None:
        return

    self._ml_research_context = {
        "symbol": str(symbol_picker.currentText() or "").strip(),
        "timeframe": str(timeframe_picker.currentText() or "").strip(),
        "model_family": str(family_picker.currentData() or "linear").strip(),
        "horizon": int(getattr(window, "_ml_research_horizon_spin").value()),
        "return_threshold": float(getattr(window, "_ml_research_threshold_spin").value()),
        "test_size": float(getattr(window, "_ml_research_test_size_spin").value()),
        "sequence_length": int(getattr(window, "_ml_research_sequence_spin").value()),
        "train_window": int(getattr(window, "_ml_research_train_window_spin").value()),
        "test_window": int(getattr(window, "_ml_research_test_window_spin").value()),
    }
    self._refresh_ml_research_window(message="ML research selection updated.")


async def _hotfix_prepare_ml_research_context(self):
    window = getattr(self, "detached_tool_windows", {}).get("ml_research_lab")
    context = getattr(self, "_ml_research_context", {}) or {}
    symbol = str(context.get("symbol") or "").strip() or (
        str(getattr(getattr(window, "_ml_research_symbol_picker", None), "currentText", lambda: "")()).strip()
    )
    timeframe = str(context.get("timeframe") or "").strip() or (
        str(getattr(getattr(window, "_ml_research_timeframe_picker", None), "currentText", lambda: "")()).strip()
    )
    backtest_context = await _hotfix_prepare_backtest_context_with_selection(self, symbol=symbol or None, timeframe=timeframe or None, strategy_name="ML Model")
    data = backtest_context.get("data")
    pipeline = _hotfix_get_ml_pipeline(self)
    dataset = pipeline.build_dataset(
        data,
        horizon=int(context.get("horizon", 3) or 3),
        return_threshold=float(context.get("return_threshold", 0.0015) or 0.0015),
        symbol=backtest_context.get("symbol"),
        timeframe=backtest_context.get("timeframe"),
    )
    return {
        **backtest_context,
        "dataset": dataset,
        "model_family": str(context.get("model_family") or "linear"),
        "test_size": float(context.get("test_size", 0.25) or 0.25),
        "sequence_length": int(context.get("sequence_length", 4) or 4),
        "train_window": int(context.get("train_window", 80) or 80),
        "test_window": int(context.get("test_window", 30) or 30),
    }


def _hotfix_populate_ml_experiments_table(_self, table, results_frame):
    if table is None:
        return
    frame = results_frame if isinstance(results_frame, pd.DataFrame) else pd.DataFrame()
    if frame.empty:
        table.setRowCount(0)
        return
    display = frame.copy().sort_values("created_at", ascending=False).reset_index(drop=True)
    table.setRowCount(len(display))
    columns = [
        ("name", "{}"),
        ("param_model_name", "{}"),
        ("param_model_family", "{}"),
        ("symbol", "{}"),
        ("timeframe", "{}"),
        ("test_accuracy", "{:.3f}"),
        ("test_precision", "{:.3f}"),
        ("created_at", "{}"),
    ]
    for row_idx, (_, row) in enumerate(display.iterrows()):
        for col_idx, (column, fmt) in enumerate(columns):
            value = row.get(column, "")
            try:
                text = fmt.format(float(value)) if fmt != "{}" and value != "" else fmt.format(value)
            except Exception:
                text = str(value)
            item = QTableWidgetItem(text)
            if col_idx == 1:
                item.setData(Qt.UserRole, str(row.get("param_model_name") or ""))
            table.setItem(row_idx, col_idx, item)
    table.resizeColumnsToContents()


def _hotfix_populate_ml_walk_table(_self, table, frame):
    if table is None:
        return
    frame = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    if frame.empty:
        table.setRowCount(0)
        return
    display = frame.copy().reset_index(drop=True)
    table.setRowCount(len(display))
    columns = [
        ("window_index", "{:g}"),
        ("train_rows", "{:g}"),
        ("test_rows", "{:g}"),
        ("accuracy", "{:.3f}"),
        ("precision", "{:.3f}"),
        ("recall", "{:.3f}"),
        ("avg_confidence", "{:.3f}"),
    ]
    for row_idx, (_, row) in enumerate(display.iterrows()):
        for col_idx, (column, fmt) in enumerate(columns):
            value = row.get(column, "")
            try:
                text = fmt.format(float(value))
            except Exception:
                text = str(value)
            table.setItem(row_idx, col_idx, QTableWidgetItem(text))
    table.resizeColumnsToContents()


def _hotfix_populate_ml_leaderboard_table(_self, table, frame):
    if table is None:
        return
    leaderboard = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    if leaderboard.empty:
        table.setRowCount(0)
        return
    display = leaderboard.copy().reset_index(drop=True)
    table.setRowCount(len(display))
    columns = [
        ("model_name", "{}"),
        ("model_family", "{}"),
        ("sequence_length", "{:g}"),
        ("selection_score", "{:.3f}"),
        ("walk_forward_accuracy", "{:.3f}"),
        ("walk_forward_precision", "{:.3f}"),
        ("test_accuracy", "{:.3f}"),
        ("test_precision", "{:.3f}"),
    ]
    for row_idx, (_, row) in enumerate(display.iterrows()):
        for col_idx, (column, fmt) in enumerate(columns):
            value = row.get(column, "")
            try:
                text = fmt.format(float(value)) if fmt != "{}" else fmt.format(value)
            except Exception:
                text = str(value)
            item = QTableWidgetItem(text)
            if col_idx == 0:
                item.setData(Qt.UserRole, str(row.get("model_name") or ""))
            table.setItem(row_idx, col_idx, item)
    table.resizeColumnsToContents()


def _hotfix_select_ml_table_row_by_model_name(table, model_name):
    if table is None:
        return
    target = str(model_name or "").strip()
    if not target:
        return
    blocked = table.blockSignals(True)
    try:
        for row_idx in range(table.rowCount()):
            items = [table.item(row_idx, column) for column in range(min(2, table.columnCount()))]
            candidate = ""
            for item in items:
                if item is None:
                    continue
                candidate = str(item.data(Qt.UserRole) or item.text() or "").strip()
                if candidate:
                    break
            if candidate == target:
                table.selectRow(row_idx)
                return
    finally:
        table.blockSignals(blocked)


def _hotfix_effective_ml_model_name(self, window=None, prefer_best=True):
    model_name = ""
    if window is not None:
        leaderboard_table = getattr(window, "_ml_research_leaderboard_table", None)
        if leaderboard_table is not None and leaderboard_table.currentRow() >= 0:
            item = leaderboard_table.item(leaderboard_table.currentRow(), 0)
            if item is not None:
                model_name = str(item.data(Qt.UserRole) or item.text() or "").strip()
        if not model_name:
            table = getattr(window, "_ml_research_experiments_table", None)
            if table is not None and table.currentRow() >= 0:
                item = table.item(table.currentRow(), 1)
                if item is not None:
                    model_name = str(item.data(Qt.UserRole) or item.text() or "").strip()
    if not model_name and prefer_best:
        best_candidate = getattr(getattr(self, "_ml_auto_research_result", None), "best_candidate", None)
        model_name = str(getattr(best_candidate, "model_name", "") or "").strip()
    if not model_name:
        model_name = str(getattr(getattr(self, "_ml_latest_result", None), "model_name", "") or "").strip()
    return model_name


def _hotfix_build_ml_research_details(_self, context, result=None, walk_summary=None, auto_summary=None):
    lines = ["<h3 style='margin-top:0;'>ML Research Lab</h3>"]
    if context:
        lines.append(
            "<p>"
            f"<b>Symbol:</b> {html.escape(str(context.get('symbol') or '-'))} | "
            f"<b>Timeframe:</b> {html.escape(str(context.get('timeframe') or '-'))} | "
            f"<b>Family:</b> {html.escape(str(context.get('model_family') or '-'))} | "
            f"<b>Horizon:</b> {html.escape(str(context.get('horizon') or '-'))}"
            "</p>"
        )
    best_candidate = getattr(auto_summary, "best_candidate", None) if auto_summary is not None else None
    if best_candidate is not None:
        best_metrics = dict(getattr(best_candidate, "selection_metrics", {}) or {})
        lines.append("<h4>Auto Research Winner</h4>")
        lines.append(
            "<ul>"
            f"<li>Model: <b>{html.escape(str(best_candidate.model_name or '-'))}</b></li>"
            f"<li>Family: <b>{html.escape(str(best_candidate.model_family or '-'))}</b> | Sequence length: <b>{int(best_candidate.sequence_length or 1)}</b></li>"
            f"<li>Selection score: <b>{float(best_metrics.get('selection_score', 0.0) or 0.0):.3f}</b></li>"
            f"<li>Walk-forward accuracy: <b>{float(best_metrics.get('walk_forward_accuracy', 0.0) or 0.0):.3f}</b></li>"
            f"<li>Walk-forward precision: <b>{float(best_metrics.get('walk_forward_precision', 0.0) or 0.0):.3f}</b></li>"
            f"<li>Test accuracy: <b>{float(best_metrics.get('test_accuracy', 0.0) or 0.0):.3f}</b></li>"
            "</ul>"
        )
    if result is not None:
        metrics = dict(getattr(result, "metrics", {}) or {})
        lines.append("<h4>Training Result</h4>")
        lines.append(
            "<ul>"
            f"<li>Model: <b>{html.escape(str(getattr(result, 'model_name', '-') or '-'))}</b></li>"
            f"<li>Train accuracy: <b>{metrics.get('train_accuracy', 0.0):.3f}</b></li>"
            f"<li>Test accuracy: <b>{metrics.get('test_accuracy', 0.0):.3f}</b></li>"
            f"<li>Test precision: <b>{metrics.get('test_precision', 0.0):.3f}</b></li>"
            f"<li>Test recall: <b>{metrics.get('test_recall', 0.0):.3f}</b></li>"
            f"<li>Avg test confidence: <b>{metrics.get('avg_test_confidence', 0.0):.3f}</b></li>"
            "</ul>"
        )
    if isinstance(walk_summary, pd.DataFrame) and not walk_summary.empty:
        lines.append("<h4>Walk-Forward</h4>")
        lines.append(
            "<ul>"
            f"<li>Windows: <b>{len(walk_summary)}</b></li>"
            f"<li>Avg accuracy: <b>{walk_summary['accuracy'].mean():.3f}</b></li>"
            f"<li>Avg precision: <b>{walk_summary['precision'].mean():.3f}</b></li>"
            f"<li>Avg recall: <b>{walk_summary['recall'].mean():.3f}</b></li>"
            "</ul>"
        )
    if result is None and (not isinstance(walk_summary, pd.DataFrame) or walk_summary.empty):
        lines.append("<p>Train a model or run walk-forward analysis to populate this workspace.</p>")
    return "".join(lines)


def _hotfix_refresh_ml_research_window(self, window=None, message=None):
    window = window or getattr(self, "detached_tool_windows", {}).get("ml_research_lab")
    if window is None:
        return
    status = getattr(window, "_ml_research_status", None)
    summary = getattr(window, "_ml_research_summary", None)
    train_btn = getattr(window, "_ml_research_train_btn", None)
    walk_btn = getattr(window, "_ml_research_walk_btn", None)
    auto_btn = getattr(window, "_ml_research_auto_btn", None)
    auto_deploy_btn = getattr(window, "_ml_research_auto_deploy_btn", None)
    deploy_btn = getattr(window, "_ml_research_deploy_btn", None)
    experiments_table = getattr(window, "_ml_research_experiments_table", None)
    walk_table = getattr(window, "_ml_research_walk_table", None)
    leaderboard_table = getattr(window, "_ml_research_leaderboard_table", None)
    details = getattr(window, "_ml_research_details", None)
    if status is None or summary is None or experiments_table is None or walk_table is None or leaderboard_table is None or details is None:
        return

    if message is not None:
        self._ml_research_status_message = message

    context = getattr(self, "_ml_research_context", {}) or {}
    running = bool(getattr(self, "_ml_research_running", False))
    running_mode = str(getattr(self, "_ml_research_mode", "") or "").strip().lower()
    best_candidate = getattr(getattr(self, "_ml_auto_research_result", None), "best_candidate", None)
    status.setText(getattr(self, "_ml_research_status_message", None) or ("ML research running..." if running else "ML research workspace ready."))
    summary_parts = [
        f"Symbol: {context.get('symbol', '-')} | Timeframe: {context.get('timeframe', '-')} | "
        f"Family: {context.get('model_family', '-')} | Horizon: {context.get('horizon', '-')} | "
        f"Test Size: {float(context.get('test_size', 0.25) or 0.25):.0%}"
    ]
    if best_candidate is not None:
        summary_parts.append(
            f" | Best: {best_candidate.model_family} -> {best_candidate.model_name}"
        )
    summary.setText("".join(summary_parts))
    if train_btn is not None:
        train_btn.setEnabled(not running)
        train_btn.setText("Training..." if running and running_mode == "training" else "Train Model")
    if walk_btn is not None:
        walk_btn.setEnabled(not running)
        walk_btn.setText("Running..." if running and running_mode == "walk_forward" else "Run Walk-Forward")
    if auto_btn is not None:
        auto_btn.setEnabled(not running)
        auto_btn.setText("Researching..." if running and running_mode == "auto_research" else "Auto Research Best")
    if auto_deploy_btn is not None:
        auto_deploy_btn.setEnabled(not running)
        auto_deploy_btn.setText("Deploying..." if running and running_mode == "auto_deploy" else "Auto Deploy Best")

    pipeline = _hotfix_get_ml_pipeline(self)
    experiment_frame = pipeline.experiment_tracker.to_frame()
    _hotfix_populate_ml_experiments_table(self, experiments_table, experiment_frame)
    _hotfix_populate_ml_walk_table(self, walk_table, getattr(self, "_ml_walk_forward_summary", None))
    _hotfix_populate_ml_leaderboard_table(self, leaderboard_table, getattr(getattr(self, "_ml_auto_research_result", None), "leaderboard", None))

    preferred_model_name = str(getattr(self, "_ml_selected_model_name", "") or "").strip()
    if not preferred_model_name and best_candidate is not None:
        preferred_model_name = str(best_candidate.model_name or "").strip()
    if preferred_model_name:
        _hotfix_select_ml_table_row_by_model_name(experiments_table, preferred_model_name)
        _hotfix_select_ml_table_row_by_model_name(leaderboard_table, preferred_model_name)

    selected_model_name = _hotfix_effective_ml_model_name(self, window=window)
    if deploy_btn is not None:
        deploy_btn.setEnabled((not running) and bool(selected_model_name or getattr(getattr(self, "_ml_latest_result", None), "model_name", "")))

    details.setHtml(
        _hotfix_build_ml_research_details(
            self,
            context,
            result=getattr(self, "_ml_latest_result", None),
            walk_summary=getattr(self, "_ml_walk_forward_summary", None),
            auto_summary=getattr(self, "_ml_auto_research_result", None),
        )
    )


async def _hotfix_run_ml_model_training(self):
    if bool(getattr(self, "_ml_research_running", False)):
        self._show_ml_research_window()
        self._refresh_ml_research_window(message="ML research is already running.")
        return

    try:
        self._show_ml_research_window()
        context = await _hotfix_prepare_ml_research_context(self)
        dataset = context.get("dataset")
        if dataset is None or dataset.empty:
            raise RuntimeError("No ML dataset could be built from the selected history")

        self._ml_research_running = True
        self._ml_research_mode = "training"
        self._ml_research_status_message = "Training ML model..."
        self._ml_research_context = {**(getattr(self, "_ml_research_context", {}) or {}), **context}
        self._refresh_ml_research_window(message="Training ML model...")

        pipeline = _hotfix_get_ml_pipeline(self)
        model_name = (
            f"{context['symbol'].replace('/', '_')}_{context['timeframe']}_{context['model_family']}_{int(datetime.now().timestamp())}"
        )
        result = await asyncio.to_thread(
            pipeline.train_classifier,
            dataset,
            model_name,
            context["model_family"],
            context["sequence_length"],
            context["test_size"],
            "ml_research_lab",
            "terminal_training",
        )
        self._ml_latest_result = result
        self._ml_selected_model_name = str(result.model_name or "").strip()
        self.system_console.log(f"ML model trained: {result.model_name}", "INFO")
        self._ml_research_status_message = "ML training completed."
        self._refresh_ml_research_window(message="ML training completed.")
    except Exception as e:
        self.system_console.log(f"ML training failed: {e}", "ERROR")
        self._ml_research_status_message = f"ML training failed: {e}"
        self._refresh_ml_research_window(message=f"ML training failed: {e}")
    finally:
        self._ml_research_running = False
        self._ml_research_mode = ""
        self._refresh_ml_research_window()


async def _hotfix_run_ml_walk_forward(self):
    if bool(getattr(self, "_ml_research_running", False)):
        self._show_ml_research_window()
        self._refresh_ml_research_window(message="ML research is already running.")
        return

    try:
        self._show_ml_research_window()
        context = await _hotfix_prepare_ml_research_context(self)
        dataset = context.get("dataset")
        if dataset is None or dataset.empty:
            raise RuntimeError("No ML dataset could be built from the selected history")

        self._ml_research_running = True
        self._ml_research_mode = "walk_forward"
        self._ml_research_status_message = "Running ML walk-forward..."
        self._ml_research_context = {**(getattr(self, "_ml_research_context", {}) or {}), **context}
        self._refresh_ml_research_window(message="Running ML walk-forward...")

        pipeline = _hotfix_get_ml_pipeline(self)
        summary_df, predictions_df = await asyncio.to_thread(
            pipeline.run_walk_forward,
            dataset,
            context["model_family"],
            context["sequence_length"],
            context["train_window"],
            context["test_window"],
            None,
        )
        self._ml_walk_forward_summary = summary_df
        self._ml_walk_forward_predictions = predictions_df
        self.system_console.log("ML walk-forward analysis completed.", "INFO")
        self._ml_research_status_message = "ML walk-forward completed."
        self._refresh_ml_research_window(message="ML walk-forward completed.")
    except Exception as e:
        self.system_console.log(f"ML walk-forward failed: {e}", "ERROR")
        self._ml_research_status_message = f"ML walk-forward failed: {e}"
        self._refresh_ml_research_window(message=f"ML walk-forward failed: {e}")
    finally:
        self._ml_research_running = False
        self._ml_research_mode = ""
        self._refresh_ml_research_window()


async def _hotfix_run_ml_auto_research(self, auto_deploy=False):
    if bool(getattr(self, "_ml_research_running", False)):
        self._show_ml_research_window()
        self._refresh_ml_research_window(message="ML research is already running.")
        return

    try:
        self._show_ml_research_window()
        context = await _hotfix_prepare_ml_research_context(self)
        dataset = context.get("dataset")
        if dataset is None or dataset.empty:
            raise RuntimeError("No ML dataset could be built from the selected history")

        self._ml_research_running = True
        self._ml_research_mode = "auto_deploy" if auto_deploy else "auto_research"
        self._ml_research_status_message = (
            "Auto researching and deploying the best ML model..."
            if auto_deploy
            else "Auto researching ML candidates..."
        )
        self._ml_research_context = {**(getattr(self, "_ml_research_context", {}) or {}), **context}
        self._refresh_ml_research_window(message=self._ml_research_status_message)

        pipeline = _hotfix_get_ml_pipeline(self)
        symbol_label = str(context.get("symbol") or "symbol").replace("/", "_")
        timeframe_label = str(context.get("timeframe") or "1h").replace("/", "_")
        auto_summary = await asyncio.to_thread(
            pipeline.auto_research,
            dataset,
            ["linear", "tree", "sequence"],
            context["sequence_length"],
            context["test_size"],
            context["train_window"],
            context["test_window"],
            None,
            f"{symbol_label}_{timeframe_label}_auto",
            "ml_auto_research_lab",
            "terminal_auto_research",
            None,
        )
        best_candidate = getattr(auto_summary, "best_candidate", None)
        if best_candidate is None:
            raise RuntimeError("Auto research did not return a winning model")

        self._ml_auto_research_result = auto_summary
        self._ml_best_result = best_candidate.result
        self._ml_latest_result = best_candidate.result
        self._ml_walk_forward_summary = best_candidate.walk_summary
        self._ml_walk_forward_predictions = best_candidate.walk_predictions
        self._ml_selected_model_name = str(best_candidate.model_name or "").strip()
        self._ml_research_context = {
            **(getattr(self, "_ml_research_context", {}) or {}),
            "model_family": str(best_candidate.model_family or context.get("model_family") or "linear"),
            "sequence_length": int(best_candidate.sequence_length or context.get("sequence_length", 4) or 4),
        }

        best_score = float(best_candidate.selection_score or 0.0)
        self.system_console.log(
            f"Auto research selected {best_candidate.model_name} ({best_candidate.model_family}) "
            f"with score {best_score:.3f}.",
            "INFO",
        )
        self._ml_research_status_message = (
            f"Auto research selected {best_candidate.model_name}."
        )
        self._refresh_ml_research_window(message=self._ml_research_status_message)

        if auto_deploy:
            self._ml_research_running = False
            self._ml_research_mode = ""
            self._deploy_selected_ml_model(model_name=best_candidate.model_name)
            self._ml_research_status_message = f"Auto research deployed {best_candidate.model_name}."
            self._refresh_ml_research_window(message=self._ml_research_status_message)
    except Exception as e:
        self.system_console.log(f"ML auto research failed: {e}", "ERROR")
        self._ml_research_status_message = f"ML auto research failed: {e}"
        self._refresh_ml_research_window(message=f"ML auto research failed: {e}")
    finally:
        self._ml_research_running = False
        self._ml_research_mode = ""
        self._refresh_ml_research_window()


def _hotfix_deploy_selected_ml_model(self, model_name=None):
    try:
        window = getattr(self, "detached_tool_windows", {}).get("ml_research_lab")
        pipeline = _hotfix_get_ml_pipeline(self)
        model_name = str(model_name or "").strip() or _hotfix_effective_ml_model_name(self, window=window)
        if not model_name:
            raise RuntimeError("Train or select an ML model before deployment")

        trading_system = getattr(self.controller, "trading_system", None)
        strategy_registry = getattr(trading_system, "strategy", None)
        if strategy_registry is None:
            from strategy.strategy_registry import StrategyRegistry

            strategy_registry = StrategyRegistry()
            if trading_system is not None:
                trading_system.strategy = strategy_registry

        pipeline.deploy_to_strategy_registry(strategy_registry, model_name, strategy_name="ML Model")
        self.controller.strategy_name = "ML Model"
        self._ml_selected_model_name = model_name
        if hasattr(strategy_registry, "set_active"):
            strategy_registry.set_active("ML Model")
        self.system_console.log(f"Deployed ML model: {model_name}", "INFO")
        self._refresh_ml_research_window(message=f"Deployed ML model: {model_name}")
    except Exception as e:
        self.system_console.log(f"ML model deployment failed: {e}", "ERROR")
        self._refresh_ml_research_window(message=f"ML model deployment failed: {e}")


async def _hotfix_reload_chart_data(self, symbol, timeframe):
    try:
        df = None

        # Preferred cache shape: candle_buffers[symbol][timeframe]
        buffers = getattr(self.controller, "candle_buffers", None)
        if hasattr(buffers, "get"):
            symbol_bucket = buffers.get(symbol)
            if hasattr(symbol_bucket, "get"):
                df = symbol_bucket.get(timeframe)

        # Fallback to legacy candle_buffer store.
        if df is None:
            legacy = getattr(self.controller, "candle_buffer", None)
            if hasattr(legacy, "get"):
                symbol_bucket = legacy.get(symbol)
                if hasattr(symbol_bucket, "get"):
                    df = symbol_bucket.get(timeframe)
                elif symbol_bucket is not None:
                    df = symbol_bucket

                if df is None:
                    df = legacy.get(timeframe)

        if df is None:
            return

        self._update_chart(symbol, df)

    except Exception as e:
        self.logger.error(f"Timeframe reload failed: {e}")


def _hotfix_open_risk_settings(self):
    self._show_settings_window("Risk")


def _hotfix_save_settings(self):
    try:
        self._show_settings_window("General")
    except Exception as e:
        self.logger.error(f"Risk settings error: {e}")


def _hotfix_settings_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _hotfix_settings_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


def _hotfix_settings_int(value, default):
    try:
        return int(float(value))
    except Exception:
        return default


def _hotfix_update_database_mode_state(window):
    if window is None:
        return

    mode_picker = getattr(window, "_settings_database_mode", None)
    url_input = getattr(window, "_settings_database_url", None)
    hint_label = getattr(window, "_settings_database_hint", None)
    if mode_picker is None or url_input is None:
        return

    remote_selected = str(mode_picker.currentData() or "local").strip().lower() == "remote"
    url_input.setEnabled(remote_selected)
    if not remote_selected:
        url_input.setPlaceholderText("Local SQLite is active. Switch to Remote to use a custom database URL.")
    else:
        url_input.setPlaceholderText("postgresql+psycopg://user:password@host:5432/dbname")

    if hint_label is not None:
        if remote_selected:
            hint_label.setText(
                "Use any SQLAlchemy connection URL your Python environment supports. "
                "Example: postgresql+psycopg://user:password@host:5432/dbname"
            )
        else:
            hint_label.setText("Local mode uses Sopotek's built-in SQLite database in the data folder.")


def _hotfix_focus_settings_tab(window, tab_name):
    tabs = getattr(window, "_settings_tabs", None)
    if tabs is None or not tab_name:
        return

    target = str(tab_name).strip().lower()
    for index in range(tabs.count()):
        if str(tabs.tabText(index) or "").strip().lower() == target:
            tabs.setCurrentIndex(index)
            return


def _hotfix_refresh_market_type_picker(window, controller):
    picker = getattr(window, "_settings_market_type", None)
    if picker is None:
        return

    current = str(picker.currentData() or getattr(controller, "market_trade_preference", "auto") or "auto").strip().lower()
    if hasattr(controller, "supported_market_venues"):
        supported = list(controller.supported_market_venues() or [])
    else:
        supported = ["auto", "spot"]
    supported = [str(item).strip().lower() for item in supported if str(item).strip()]
    if not supported:
        supported = ["auto", "spot"]

    picker.blockSignals(True)
    picker.clear()
    for label, value in MARKET_VENUE_CHOICES:
        if value in supported:
            picker.addItem(label, value)

    target = current if current in supported else ("auto" if "auto" in supported else supported[0])
    index = picker.findData(target)
    picker.setCurrentIndex(index if index >= 0 else 0)
    picker.blockSignals(False)


def _hotfix_get_live_risk_engine(self):
    trading_system = getattr(self.controller, "trading_system", None)
    risk_engine = getattr(trading_system, "risk_engine", None)
    if risk_engine is not None:
        return risk_engine
    return getattr(self.controller, "risk_engine", None)


def _hotfix_risk_profile_names():
    return list(RISK_PROFILE_PRESETS.keys()) + ["Custom"]


def _hotfix_normalize_risk_profile_name(name):
    normalized = str(name or "").strip()
    if normalized in RISK_PROFILE_PRESETS:
        return normalized
    if normalized.lower() == "custom":
        return "Custom"
    return "Balanced"


def _hotfix_risk_profile_payload(name):
    normalized = _hotfix_normalize_risk_profile_name(name)
    payload = dict(RISK_PROFILE_PRESETS.get(normalized) or RISK_PROFILE_PRESETS["Balanced"])
    payload["name"] = normalized
    return payload


def _hotfix_detect_risk_profile_name(values):
    max_portfolio = float(values.get("max_portfolio_risk", 0.0) or 0.0)
    max_trade = float(values.get("max_risk_per_trade", 0.0) or 0.0)
    max_position = float(values.get("max_position_size_pct", 0.0) or 0.0)
    max_gross = float(values.get("max_gross_exposure_pct", 0.0) or 0.0)
    for name, profile in RISK_PROFILE_PRESETS.items():
        if (
            abs(max_portfolio - float(profile["max_portfolio_risk"])) <= 1e-9
            and abs(max_trade - float(profile["max_risk_per_trade"])) <= 1e-9
            and abs(max_position - float(profile["max_position_size_pct"])) <= 1e-9
            and abs(max_gross - float(profile["max_gross_exposure_pct"])) <= 1e-9
        ):
            return name
    return "Custom"


def _hotfix_set_risk_profile_status(window, profile_name, source=""):
    label = getattr(window, "_settings_risk_profile_description", None)
    if label is None:
        return
    normalized = _hotfix_normalize_risk_profile_name(profile_name)
    if normalized == "Custom":
        label.setText(
            "Custom profile: these limits no longer match one preset exactly. "
            "You can keep them as-is or reapply a preset."
        )
        return
    payload = _hotfix_risk_profile_payload(normalized)
    prefix = f"{normalized}: {payload.get('description', '')}"
    if source:
        prefix = f"{source} {prefix}".strip()
    label.setText(prefix)


def _hotfix_apply_risk_profile_to_window(window, profile_name):
    if window is None:
        return
    normalized = _hotfix_normalize_risk_profile_name(profile_name)
    picker = getattr(window, "_settings_risk_profile", None)
    if picker is None:
        return
    window._risk_profile_updating = True
    try:
        if normalized != "Custom":
            payload = _hotfix_risk_profile_payload(normalized)
            for attr_name, key in (
                ("_settings_max_portfolio", "max_portfolio_risk"),
                ("_settings_max_trade", "max_risk_per_trade"),
                ("_settings_max_position", "max_position_size_pct"),
                ("_settings_max_gross", "max_gross_exposure_pct"),
            ):
                widget = getattr(window, attr_name, None)
                if widget is not None:
                    widget.setValue(float(payload[key]))
        profile_index = picker.findText(normalized)
        if profile_index < 0:
            profile_index = picker.findText("Custom")
        picker.setCurrentIndex(profile_index if profile_index >= 0 else 0)
    finally:
        window._risk_profile_updating = False
    _hotfix_set_risk_profile_status(window, normalized)


def _hotfix_sync_risk_profile_from_window(window):
    if window is None or bool(getattr(window, "_risk_profile_updating", False)):
        return
    profile_name = _hotfix_detect_risk_profile_name(
        {
            "max_portfolio_risk": getattr(getattr(window, "_settings_max_portfolio", None), "value", lambda: 0.0)(),
            "max_risk_per_trade": getattr(getattr(window, "_settings_max_trade", None), "value", lambda: 0.0)(),
            "max_position_size_pct": getattr(getattr(window, "_settings_max_position", None), "value", lambda: 0.0)(),
            "max_gross_exposure_pct": getattr(getattr(window, "_settings_max_gross", None), "value", lambda: 0.0)(),
        }
    )
    picker = getattr(window, "_settings_risk_profile", None)
    if picker is not None:
        window._risk_profile_updating = True
        try:
            profile_index = picker.findText(profile_name)
            picker.setCurrentIndex(profile_index if profile_index >= 0 else picker.findText("Custom"))
        finally:
            window._risk_profile_updating = False
    _hotfix_set_risk_profile_status(window, profile_name)


def _hotfix_build_strategy_params(values, controller):
    current = dict(getattr(controller, "strategy_params", {}) or {})
    defaults = {
        "rsi_period": int(current.get("rsi_period", 14)),
        "ema_fast": int(current.get("ema_fast", 20)),
        "ema_slow": int(current.get("ema_slow", 50)),
        "atr_period": int(current.get("atr_period", 14)),
        "oversold_threshold": float(current.get("oversold_threshold", 35.0)),
        "overbought_threshold": float(current.get("overbought_threshold", 65.0)),
        "breakout_lookback": int(current.get("breakout_lookback", 20)),
        "min_confidence": float(current.get("min_confidence", 0.55)),
        "signal_amount": float(current.get("signal_amount", 1.0)),
    }
    params = {
        "rsi_period": max(2, int(values.get("strategy_rsi_period", defaults["rsi_period"]))),
        "ema_fast": max(2, int(values.get("strategy_ema_fast", defaults["ema_fast"]))),
        "ema_slow": max(3, int(values.get("strategy_ema_slow", defaults["ema_slow"]))),
        "atr_period": max(2, int(values.get("strategy_atr_period", defaults["atr_period"]))),
        "oversold_threshold": float(values.get("strategy_oversold_threshold", defaults["oversold_threshold"])),
        "overbought_threshold": float(values.get("strategy_overbought_threshold", defaults["overbought_threshold"])),
        "breakout_lookback": max(2, int(values.get("strategy_breakout_lookback", defaults["breakout_lookback"]))),
        "min_confidence": max(0.0, min(1.0, float(values.get("strategy_min_confidence", defaults["min_confidence"])))),
        "signal_amount": max(0.0001, float(values.get("strategy_signal_amount", defaults["signal_amount"]))),
    }
    if params["ema_fast"] >= params["ema_slow"]:
        params["ema_fast"] = max(2, min(params["ema_fast"], params["ema_slow"] - 1))
    if params["oversold_threshold"] >= params["overbought_threshold"]:
        params["oversold_threshold"] = min(params["oversold_threshold"], params["overbought_threshold"] - 1.0)
    return params


def _hotfix_update_color_button(button, color):
    if button is None:
        return
    qcolor = QColor(str(color or "#1f2937"))
    text_color = "#11161f" if qcolor.lightnessF() >= 0.62 else "#ffffff"
    button.setText(color)
    button.setStyleSheet(
        """
        QPushButton {
            background-color: %s;
            color: %s;
            border: 1px solid #31415f;
            border-radius: 8px;
            padding: 6px 10px;
            font-weight: 700;
        }
        """
        % (color, text_color)
    )


def _hotfix_pick_settings_color(window, attr_name, button, title):
    current = getattr(window, attr_name, "#26a69a")
    picked = QColorDialog.getColor(QColor(current), window, title)
    if not picked.isValid():
        return
    color = picked.name()
    setattr(window, attr_name, color)
    _hotfix_update_color_button(button, color)


def _hotfix_collect_settings_values(self, window=None):
    if window is None:
        window = self.detached_tool_windows.get("application_settings")
    if window is None:
        return None

    return {
        "timeframe": window._settings_timeframe.currentText(),
        "order_type": window._settings_order_type.currentText(),
        "market_trade_preference": window._settings_market_type.currentData(),
        "database_mode": window._settings_database_mode.currentData(),
        "database_url": window._settings_database_url.text().strip(),
        "history_limit": int(window._settings_history_limit.value()),
        "initial_capital": float(window._settings_initial_capital.value()),
        "hedging_enabled": bool(window._settings_hedging_enabled.currentData()),
        "refresh_interval_ms": int(window._settings_refresh_ms.value()),
        "orderbook_interval_ms": int(window._settings_orderbook_ms.value()),
        "forex_candle_price_component": window._settings_forex_candle_source.currentData(),
        "show_bid_ask_lines": window._settings_bid_ask_mode.currentData(),
        "chart_background_color": getattr(window, "_settings_chart_background_color", self.chart_background_color),
        "chart_grid_color": getattr(window, "_settings_chart_grid_color", self.chart_grid_color),
        "chart_axis_color": getattr(window, "_settings_chart_axis_color", self.chart_axis_color),
        "candle_up_color": getattr(window, "_settings_up_color", self.candle_up_color),
        "candle_down_color": getattr(window, "_settings_down_color", self.candle_down_color),
        "risk_profile_name": _hotfix_detect_risk_profile_name(
            {
                "max_portfolio_risk": float(window._settings_max_portfolio.value()),
                "max_risk_per_trade": float(window._settings_max_trade.value()),
                "max_position_size_pct": float(window._settings_max_position.value()),
                "max_gross_exposure_pct": float(window._settings_max_gross.value()),
            }
        ),
        "max_portfolio_risk": float(window._settings_max_portfolio.value()),
        "max_risk_per_trade": float(window._settings_max_trade.value()),
        "max_position_size_pct": float(window._settings_max_position.value()),
        "max_gross_exposure_pct": float(window._settings_max_gross.value()),
        "margin_closeout_guard_enabled": bool(window._settings_margin_closeout_guard.currentData()),
        "max_margin_closeout_pct": float(window._settings_margin_closeout_pct.value()),
        "strategy_name": window._settings_strategy_name.currentText(),
        "strategy_rsi_period": int(window._settings_strategy_rsi_period.value()),
        "strategy_ema_fast": int(window._settings_strategy_ema_fast.value()),
        "strategy_ema_slow": int(window._settings_strategy_ema_slow.value()),
        "strategy_atr_period": int(window._settings_strategy_atr_period.value()),
        "strategy_oversold_threshold": float(window._settings_strategy_oversold.value()),
        "strategy_overbought_threshold": float(window._settings_strategy_overbought.value()),
        "strategy_breakout_lookback": int(window._settings_strategy_breakout.value()),
        "strategy_min_confidence": float(window._settings_strategy_confidence.value()),
        "strategy_signal_amount": float(window._settings_strategy_amount.value()),
        "telegram_enabled": window._settings_telegram_enabled.currentData(),
        "telegram_bot_token": window._settings_telegram_bot_token.text().strip(),
        "telegram_chat_id": window._settings_telegram_chat_id.text().strip(),
        "trade_close_notifications_enabled": window._settings_trade_close_notifications_enabled.currentData(),
        "trade_close_notify_telegram": bool(window._settings_trade_close_notify_telegram.isChecked()),
        "trade_close_notify_email": bool(window._settings_trade_close_notify_email.isChecked()),
        "trade_close_notify_sms": bool(window._settings_trade_close_notify_sms.isChecked()),
        "trade_close_email_host": window._settings_trade_close_email_host.text().strip(),
        "trade_close_email_port": int(window._settings_trade_close_email_port.value()),
        "trade_close_email_username": window._settings_trade_close_email_username.text().strip(),
        "trade_close_email_password": window._settings_trade_close_email_password.text(),
        "trade_close_email_from": window._settings_trade_close_email_from.text().strip(),
        "trade_close_email_to": window._settings_trade_close_email_to.text().strip(),
        "trade_close_email_starttls": bool(window._settings_trade_close_email_starttls.isChecked()),
        "trade_close_sms_account_sid": window._settings_trade_close_sms_account_sid.text().strip(),
        "trade_close_sms_auth_token": window._settings_trade_close_sms_auth_token.text(),
        "trade_close_sms_from_number": window._settings_trade_close_sms_from_number.text().strip(),
        "trade_close_sms_to_number": window._settings_trade_close_sms_to_number.text().strip(),
        "openai_api_key": window._settings_openai_api_key.text().strip(),
        "openai_model": window._settings_openai_model.text().strip(),
        "news_enabled": window._settings_news_enabled.currentData(),
        "news_autotrade_enabled": window._settings_news_autotrade.currentData(),
        "news_draw_on_chart": window._settings_news_chart.currentData(),
        "news_feed_url": window._settings_news_feed_url.text().strip(),
    }


async def _hotfix_test_openai_from_settings_async(self, window):
    try:
        api_key = window._settings_openai_api_key.text().strip()
        model = window._settings_openai_model.text().strip() or "gpt-5-mini"
        result = await self.controller.test_openai_connection(api_key=api_key, model=model)
    except Exception as exc:
        result = {"ok": False, "message": f"OpenAI test failed: {exc}"}

    ok = bool(result.get("ok"))
    message = str(result.get("message") or ("OpenAI connection OK." if ok else "OpenAI test failed."))
    label = getattr(window, "_settings_openai_test_status", None)
    button = getattr(window, "_settings_openai_test_button", None)
    if label is not None:
        tone = "#32d296" if ok else "#ff6b6b"
        label.setStyleSheet(f"color: {tone}; padding-top: 4px;")
        label.setText(message)
    if button is not None:
        button.setEnabled(True)
        button.setText("Test OpenAI")


def _hotfix_test_openai_from_settings(self, window=None):
    window = window or self.detached_tool_windows.get("application_settings")
    if window is None:
        return

    label = getattr(window, "_settings_openai_test_status", None)
    button = getattr(window, "_settings_openai_test_button", None)
    if label is not None:
        label.setStyleSheet("color: #9fb0c7; padding-top: 4px;")
        label.setText("Testing OpenAI connection...")
    if button is not None:
        button.setEnabled(False)
        button.setText("Testing...")

    runner = _hotfix_test_openai_from_settings_async(self, window)
    task_factory = getattr(self.controller, "_create_task", None)
    if callable(task_factory):
        window._settings_openai_test_task = task_factory(runner, "settings_openai_test")
    else:
        window._settings_openai_test_task = asyncio.create_task(runner)


def _hotfix_wrap_tab_in_scroll_area(content, minimum_width=0):
    if isinstance(content, QScrollArea):
        return content

    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    holder = QWidget()
    holder_layout = QVBoxLayout(holder)
    holder_layout.setContentsMargins(0, 0, 0, 0)
    holder_layout.setSpacing(0)
    holder_layout.addWidget(content)
    holder_layout.addStretch(1)
    if minimum_width:
        holder.setMinimumWidth(int(minimum_width))

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    scroll.setWidget(holder)
    return scroll


def _hotfix_missing_database_driver_name(error):
    name = str(getattr(error, "name", "") or "").strip().lower()
    if name:
        return name

    for value in getattr(error, "args", ()) or ():
        text = str(value or "").strip().lower()
        if "pymysql" in text:
            return "pymysql"
        if "pymsql" in text:
            return "pymsql"
    return ""


def _hotfix_apply_storage_settings(self, database_mode, database_url, persist):
    if not hasattr(self.controller, "configure_storage_database"):
        return ""

    try:
        self.controller.configure_storage_database(
            database_mode=database_mode,
            database_url=database_url,
            persist=persist,
            raise_on_error=bool(persist),
        )
        return ""
    except ModuleNotFoundError as exc:
        missing_driver = _hotfix_missing_database_driver_name(exc)
        if database_mode == "remote" and missing_driver in {"pymysql", "pymsql"}:
            self.controller.configure_storage_database(
                database_mode="local",
                database_url="",
                persist=persist,
                raise_on_error=False,
            )
            return (
                "Remote MySQL storage requires PyMySQL, so Sopotek kept storage on Local SQLite. "
                "Install PyMySQL or switch the storage backend back to Local SQLite."
            )
        raise


def _hotfix_apply_settings_values(self, values, persist=True, reload_chart=False):
    if not isinstance(values, dict):
        return ""

    timeframe = values.get("timeframe", getattr(self, "current_timeframe", "1h"))
    order_type = values.get("order_type", getattr(self, "order_type", "limit"))
    market_trade_preference = str(
        values.get("market_trade_preference", getattr(self.controller, "market_trade_preference", "auto"))
        or "auto"
    ).strip().lower()
    history_limit = max(100, int(values.get("history_limit", getattr(self.controller, "limit", 50000))))
    initial_capital = max(0.0, float(values.get("initial_capital", getattr(self.controller, "initial_capital", 10000))))
    refresh_interval_ms = max(250, int(values.get("refresh_interval_ms", 1000)))
    orderbook_interval_ms = max(250, int(values.get("orderbook_interval_ms", 1500)))
    database_mode = str(values.get("database_mode", getattr(self.controller, "database_mode", "local")) or "local").strip().lower()
    database_url = str(values.get("database_url", getattr(self.controller, "database_url", "")) or "").strip()
    forex_candle_price_component = str(
        values.get(
            "forex_candle_price_component",
            getattr(self.controller, "forex_candle_price_component", "bid"),
        )
        or "bid"
    ).strip().lower()
    show_bid_ask_lines = bool(values.get("show_bid_ask_lines", getattr(self, "show_bid_ask_lines", True)))
    chart_background_color = str(
        values.get("chart_background_color", getattr(self, "chart_background_color", "#11161f")) or "#11161f"
    )
    chart_grid_color = str(values.get("chart_grid_color", getattr(self, "chart_grid_color", "#8290a0")) or "#8290a0")
    chart_axis_color = str(values.get("chart_axis_color", getattr(self, "chart_axis_color", "#9aa4b2")) or "#9aa4b2")
    candle_up_color = values.get("candle_up_color", getattr(self, "candle_up_color", "#26a69a"))
    candle_down_color = values.get("candle_down_color", getattr(self, "candle_down_color", "#ef5350"))
    strategy_name = Strategy.normalize_strategy_name(
        values.get("strategy_name", getattr(self.controller, "strategy_name", "Trend Following"))
    )
    strategy_params = _hotfix_build_strategy_params(values, self.controller)

    self.current_timeframe = timeframe
    self.order_type = order_type
    self.controller.time_frame = timeframe
    self.controller.order_type = order_type
    if hasattr(self.controller, "set_market_trade_preference"):
        self.controller.set_market_trade_preference(market_trade_preference)
    market_trade_preference = str(
        getattr(self.controller, "market_trade_preference", market_trade_preference) or market_trade_preference
    ).strip().lower()
    if hasattr(self.controller, "set_forex_candle_price_component"):
        self.controller.set_forex_candle_price_component(forex_candle_price_component)
    forex_candle_price_component = str(
        getattr(
            self.controller,
            "forex_candle_price_component",
            forex_candle_price_component,
        )
        or forex_candle_price_component
    ).strip().lower()
    storage_notice = _hotfix_apply_storage_settings(self, database_mode, database_url, persist)
    self.controller.limit = history_limit
    self.controller.initial_capital = initial_capital
    backtest_window = getattr(self, "detached_tool_windows", {}).get("backtesting_workspace")
    backtest_history_limit = getattr(backtest_window, "_backtest_history_limit", None) if backtest_window is not None else None
    if backtest_history_limit is not None:
        backtest_history_limit.blockSignals(True)
        backtest_history_limit.setValue(float(history_limit))
        backtest_history_limit.blockSignals(False)
    backtest_context = getattr(self, "_backtest_context", None)
    if isinstance(backtest_context, dict):
        backtest_context["history_limit"] = int(history_limit)
    self.controller.risk_profile_name = str(
        values.get(
            "risk_profile_name",
            _hotfix_detect_risk_profile_name(
                {
                    "max_portfolio_risk": values.get("max_portfolio_risk", getattr(self.controller, "max_portfolio_risk", 0.2)),
                    "max_risk_per_trade": values.get("max_risk_per_trade", getattr(self.controller, "max_risk_per_trade", 0.02)),
                    "max_position_size_pct": values.get("max_position_size_pct", getattr(self.controller, "max_position_size_pct", 0.05)),
                    "max_gross_exposure_pct": values.get("max_gross_exposure_pct", getattr(self.controller, "max_gross_exposure_pct", 1.0)),
                }
            ),
        )
        or "Balanced"
    )
    self.controller.max_portfolio_risk = float(values.get("max_portfolio_risk", getattr(self.controller, "max_portfolio_risk", 0.2)))
    self.controller.max_risk_per_trade = float(values.get("max_risk_per_trade", getattr(self.controller, "max_risk_per_trade", 0.02)))
    self.controller.max_position_size_pct = float(values.get("max_position_size_pct", getattr(self.controller, "max_position_size_pct", 0.05)))
    self.controller.max_gross_exposure_pct = float(values.get("max_gross_exposure_pct", getattr(self.controller, "max_gross_exposure_pct", 1.0)))
    self.controller.hedging_enabled = bool(
        values.get(
            "hedging_enabled",
            getattr(self.controller, "hedging_enabled", True),
        )
    )
    self.controller.margin_closeout_guard_enabled = bool(
        values.get(
            "margin_closeout_guard_enabled",
            getattr(self.controller, "margin_closeout_guard_enabled", True),
        )
    )
    self.controller.max_margin_closeout_pct = max(
        0.01,
        min(
            1.0,
            float(
                values.get(
                    "max_margin_closeout_pct",
                    getattr(self.controller, "max_margin_closeout_pct", 0.50),
                )
                or 0.50
            ),
        ),
    )
    self.controller.strategy_name = strategy_name
    self.controller.strategy_params = strategy_params
    if hasattr(self.controller, "update_integration_settings"):
        self.controller.update_integration_settings(
            telegram_enabled=bool(values.get("telegram_enabled", getattr(self.controller, "telegram_enabled", False))),
            telegram_bot_token=values.get("telegram_bot_token", getattr(self.controller, "telegram_bot_token", "")),
            telegram_chat_id=values.get("telegram_chat_id", getattr(self.controller, "telegram_chat_id", "")),
            trade_close_notifications_enabled=bool(values.get("trade_close_notifications_enabled", getattr(self.controller, "trade_close_notifications_enabled", False))),
            trade_close_notify_telegram=bool(values.get("trade_close_notify_telegram", getattr(self.controller, "trade_close_notify_telegram", False))),
            trade_close_notify_email=bool(values.get("trade_close_notify_email", getattr(self.controller, "trade_close_notify_email", False))),
            trade_close_notify_sms=bool(values.get("trade_close_notify_sms", getattr(self.controller, "trade_close_notify_sms", False))),
            trade_close_email_host=values.get("trade_close_email_host", getattr(self.controller, "trade_close_email_host", "")),
            trade_close_email_port=int(values.get("trade_close_email_port", getattr(self.controller, "trade_close_email_port", 587)) or 587),
            trade_close_email_username=values.get("trade_close_email_username", getattr(self.controller, "trade_close_email_username", "")),
            trade_close_email_password=values.get("trade_close_email_password", getattr(self.controller, "trade_close_email_password", "")),
            trade_close_email_from=values.get("trade_close_email_from", getattr(self.controller, "trade_close_email_from", "")),
            trade_close_email_to=values.get("trade_close_email_to", getattr(self.controller, "trade_close_email_to", "")),
            trade_close_email_starttls=bool(values.get("trade_close_email_starttls", getattr(self.controller, "trade_close_email_starttls", True))),
            trade_close_sms_account_sid=values.get("trade_close_sms_account_sid", getattr(self.controller, "trade_close_sms_account_sid", "")),
            trade_close_sms_auth_token=values.get("trade_close_sms_auth_token", getattr(self.controller, "trade_close_sms_auth_token", "")),
            trade_close_sms_from_number=values.get("trade_close_sms_from_number", getattr(self.controller, "trade_close_sms_from_number", "")),
            trade_close_sms_to_number=values.get("trade_close_sms_to_number", getattr(self.controller, "trade_close_sms_to_number", "")),
            openai_api_key=values.get("openai_api_key", getattr(self.controller, "openai_api_key", "")),
            openai_model=values.get("openai_model", getattr(self.controller, "openai_model", "gpt-5-mini")),
            news_enabled=bool(values.get("news_enabled", getattr(self.controller, "news_enabled", True))),
            news_autotrade_enabled=bool(values.get("news_autotrade_enabled", getattr(self.controller, "news_autotrade_enabled", False))),
            news_draw_on_chart=bool(values.get("news_draw_on_chart", getattr(self.controller, "news_draw_on_chart", True))),
            news_feed_url=values.get("news_feed_url", getattr(self.controller, "news_feed_url", "")),
        )
    update_desk_status_panel = getattr(self, "_update_desk_status_panel", None)
    if callable(update_desk_status_panel):
        update_desk_status_panel()

    self.chart_background_color = chart_background_color
    self.chart_grid_color = chart_grid_color
    self.chart_axis_color = chart_axis_color
    self.candle_up_color = candle_up_color
    self.candle_down_color = candle_down_color
    self.show_bid_ask_lines = show_bid_ask_lines
    if getattr(self.controller, "news_draw_on_chart", False):
        for chart in self._iter_chart_widgets():
            if hasattr(self.controller, "request_news"):
                asyncio.get_event_loop().create_task(self.controller.request_news(chart.symbol, force=True))
    else:
        for chart in self._iter_chart_widgets():
            chart.clear_news_events()

    config = getattr(self.controller, "config", None)
    if config is not None and hasattr(config, "strategy"):
        try:
            config.strategy = strategy_name
        except Exception:
            pass

    if hasattr(self.controller, "candle_buffer") and hasattr(self.controller.candle_buffer, "max_length"):
        self.controller.candle_buffer.max_length = history_limit
    if hasattr(self.controller, "ticker_buffer") and hasattr(self.controller.ticker_buffer, "max_length"):
        self.controller.ticker_buffer.max_length = history_limit

    trading_system = getattr(self.controller, "trading_system", None)
    if trading_system is not None:
        setattr(trading_system, "time_frame", timeframe)
        setattr(trading_system, "limit", history_limit)
        strategy_registry = getattr(trading_system, "strategy", None)
        if strategy_registry is not None and hasattr(strategy_registry, "configure"):
            strategy_registry.configure(strategy_name=strategy_name, params=strategy_params)

    risk_engine = _hotfix_get_live_risk_engine(self)
    if risk_engine is not None:
        risk_engine.account_equity = initial_capital
        risk_engine.max_portfolio_risk = self.controller.max_portfolio_risk
        risk_engine.max_risk_per_trade = self.controller.max_risk_per_trade
        risk_engine.max_position_size_pct = self.controller.max_position_size_pct
        risk_engine.max_gross_exposure_pct = self.controller.max_gross_exposure_pct

    self._set_active_timeframe_button(timeframe)
    self._apply_candle_colors_to_all_charts()

    toggle_action = getattr(self, "toggle_bid_ask_lines_action", None)
    if toggle_action is not None:
        blocked = toggle_action.blockSignals(True)
        toggle_action.setChecked(show_bid_ask_lines)
        toggle_action.blockSignals(blocked)

    for chart in self._iter_chart_widgets():
        if hasattr(chart, "set_visual_theme"):
            chart.set_visual_theme(**self._chart_theme_kwargs())
        chart.set_candle_colors(candle_up_color, candle_down_color)
        chart.set_bid_ask_lines_visible(show_bid_ask_lines)

    if hasattr(self, "refresh_timer") and self.refresh_timer is not None:
        self.refresh_timer.setInterval(refresh_interval_ms)
        if bool(getattr(self, "_workspace_ready", False)):
            self.refresh_timer.start(refresh_interval_ms)
    if hasattr(self, "orderbook_timer") and self.orderbook_timer is not None:
        self.orderbook_timer.setInterval(orderbook_interval_ms)
        if bool(getattr(self, "_workspace_ready", False)):
            self.orderbook_timer.start(orderbook_interval_ms)

    current_chart = self._current_chart_widget()
    if isinstance(current_chart, ChartWidget):
        current_chart.timeframe = timeframe
        if hasattr(current_chart, "refresh_context_display"):
            current_chart.refresh_context_display()
        current_index = self.chart_tabs.currentIndex() if self._chart_tabs_ready() else -1
        if current_index >= 0:
            current_page = self.chart_tabs.widget(current_index)
            current_charts = self._chart_widgets_in_page(current_page)
            if len(current_charts) == 1 and current_charts[0] is current_chart:
                self.chart_tabs.setTabText(current_index, f"{current_chart.symbol} ({timeframe})")
        if reload_chart and hasattr(self.controller, "request_candle_data"):
            asyncio.get_event_loop().create_task(
                self._request_chart_data_for_widget(
                    current_chart,
                    limit=history_limit,
                )
            )
        else:
            asyncio.get_event_loop().create_task(
                self._reload_chart_data(current_chart.symbol, timeframe)
            )
        self._request_active_orderbook()

    if persist:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("chart/background_color", chart_background_color)
        self.settings.setValue("chart/grid_color", chart_grid_color)
        self.settings.setValue("chart/axis_color", chart_axis_color)
        self.settings.setValue("chart/candle_up_color", candle_up_color)
        self.settings.setValue("chart/candle_down_color", candle_down_color)
        self.settings.setValue("storage/database_mode", getattr(self.controller, "database_mode", database_mode))
        self.settings.setValue("storage/database_url", getattr(self.controller, "database_url", database_url))
        self.settings.setValue("terminal/current_timeframe", timeframe)
        self.settings.setValue("terminal/order_type", order_type)
        self.settings.setValue("trading/market_type", market_trade_preference)
        self.settings.setValue("market_data/forex_candle_price_component", forex_candle_price_component)
        self.settings.setValue("terminal/history_limit", history_limit)
        self.settings.setValue("terminal/initial_capital", initial_capital)
        self.settings.setValue("terminal/refresh_interval_ms", refresh_interval_ms)
        self.settings.setValue("terminal/orderbook_interval_ms", orderbook_interval_ms)
        self.settings.setValue("terminal/show_bid_ask_lines", show_bid_ask_lines)
        self.settings.setValue("risk/profile_name", getattr(self.controller, "risk_profile_name", "Balanced"))
        self.settings.setValue("risk/max_portfolio_risk", self.controller.max_portfolio_risk)
        self.settings.setValue("risk/max_risk_per_trade", self.controller.max_risk_per_trade)
        self.settings.setValue("risk/max_position_size_pct", self.controller.max_position_size_pct)
        self.settings.setValue("risk/max_gross_exposure_pct", self.controller.max_gross_exposure_pct)
        self.settings.setValue("trading/hedging_enabled", bool(getattr(self.controller, "hedging_enabled", True)))
        self.settings.setValue("risk/margin_closeout_guard_enabled", bool(self.controller.margin_closeout_guard_enabled))
        self.settings.setValue("risk/max_margin_closeout_pct", float(self.controller.max_margin_closeout_pct))
        self.settings.setValue("strategy/name", strategy_name)
        self.settings.setValue("strategy/rsi_period", strategy_params["rsi_period"])
        self.settings.setValue("strategy/ema_fast", strategy_params["ema_fast"])
        self.settings.setValue("strategy/ema_slow", strategy_params["ema_slow"])
        self.settings.setValue("strategy/atr_period", strategy_params["atr_period"])
        self.settings.setValue("strategy/oversold_threshold", strategy_params["oversold_threshold"])
        self.settings.setValue("strategy/overbought_threshold", strategy_params["overbought_threshold"])
        self.settings.setValue("strategy/breakout_lookback", strategy_params["breakout_lookback"])
        self.settings.setValue("strategy/min_confidence", strategy_params["min_confidence"])
        self.settings.setValue("strategy/signal_amount", strategy_params["signal_amount"])
        self.settings.setValue("integrations/telegram_enabled", bool(values.get("telegram_enabled", getattr(self.controller, "telegram_enabled", False))))
        self.settings.setValue("integrations/telegram_bot_token", values.get("telegram_bot_token", getattr(self.controller, "telegram_bot_token", "")))
        self.settings.setValue("integrations/telegram_chat_id", values.get("telegram_chat_id", getattr(self.controller, "telegram_chat_id", "")))
        self.settings.setValue("integrations/trade_close_notifications_enabled", bool(values.get("trade_close_notifications_enabled", getattr(self.controller, "trade_close_notifications_enabled", False))))
        self.settings.setValue("integrations/trade_close_notify_telegram", bool(values.get("trade_close_notify_telegram", getattr(self.controller, "trade_close_notify_telegram", False))))
        self.settings.setValue("integrations/trade_close_notify_email", bool(values.get("trade_close_notify_email", getattr(self.controller, "trade_close_notify_email", False))))
        self.settings.setValue("integrations/trade_close_notify_sms", bool(values.get("trade_close_notify_sms", getattr(self.controller, "trade_close_notify_sms", False))))
        self.settings.setValue("integrations/trade_close_email_host", values.get("trade_close_email_host", getattr(self.controller, "trade_close_email_host", "")))
        self.settings.setValue("integrations/trade_close_email_port", int(values.get("trade_close_email_port", getattr(self.controller, "trade_close_email_port", 587)) or 587))
        self.settings.setValue("integrations/trade_close_email_username", values.get("trade_close_email_username", getattr(self.controller, "trade_close_email_username", "")))
        self.settings.setValue("integrations/trade_close_email_password", values.get("trade_close_email_password", getattr(self.controller, "trade_close_email_password", "")))
        self.settings.setValue("integrations/trade_close_email_from", values.get("trade_close_email_from", getattr(self.controller, "trade_close_email_from", "")))
        self.settings.setValue("integrations/trade_close_email_to", values.get("trade_close_email_to", getattr(self.controller, "trade_close_email_to", "")))
        self.settings.setValue("integrations/trade_close_email_starttls", bool(values.get("trade_close_email_starttls", getattr(self.controller, "trade_close_email_starttls", True))))
        self.settings.setValue("integrations/trade_close_sms_account_sid", values.get("trade_close_sms_account_sid", getattr(self.controller, "trade_close_sms_account_sid", "")))
        self.settings.setValue("integrations/trade_close_sms_auth_token", values.get("trade_close_sms_auth_token", getattr(self.controller, "trade_close_sms_auth_token", "")))
        self.settings.setValue("integrations/trade_close_sms_from_number", values.get("trade_close_sms_from_number", getattr(self.controller, "trade_close_sms_from_number", "")))
        self.settings.setValue("integrations/trade_close_sms_to_number", values.get("trade_close_sms_to_number", getattr(self.controller, "trade_close_sms_to_number", "")))
        self.settings.setValue("integrations/openai_api_key", values.get("openai_api_key", getattr(self.controller, "openai_api_key", "")))
        self.settings.setValue("integrations/openai_model", values.get("openai_model", getattr(self.controller, "openai_model", "gpt-5-mini")))
        self.settings.setValue("integrations/news_enabled", bool(values.get("news_enabled", getattr(self.controller, "news_enabled", True))))
        self.settings.setValue("integrations/news_autotrade_enabled", bool(values.get("news_autotrade_enabled", getattr(self.controller, "news_autotrade_enabled", False))))
        self.settings.setValue("integrations/news_draw_on_chart", bool(values.get("news_draw_on_chart", getattr(self.controller, "news_draw_on_chart", True))))
        self.settings.setValue("integrations/news_feed_url", values.get("news_feed_url", getattr(self.controller, "news_feed_url", "")))
        self._save_detached_chart_layouts()

    return storage_notice


def _hotfix_show_settings_window(self, initial_tab=None):
    window = self._get_or_create_tool_window(
        "application_settings",
        "Settings",
        width=680,
        height=700,
    )

    if getattr(window, "_settings_container", None) is None:
        container = QWidget()
        container.setObjectName("tool_window_root")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("tool_window_hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(6)

        title = QLabel("Terminal Settings")
        title.setObjectName("tool_window_hero_title")
        hero_layout.addWidget(title)

        intro = QLabel(
            "Configure trading defaults, chart behavior, refresh timing, and integrations here. "
            "Use the Analyze menu when you want to jump straight to portfolio controls and risk limits."
        )
        intro.setWordWrap(True)
        intro.setObjectName("tool_window_hero_body")
        hero_layout.addWidget(intro)

        hero_meta = QLabel("Execution defaults | Risk controls | Charts | Integrations")
        hero_meta.setObjectName("tool_window_section_hint")
        hero_layout.addWidget(hero_meta)
        layout.addWidget(hero)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        layout.addWidget(tabs)

        general_tab = QWidget()
        general_form = QFormLayout(general_tab)
        self._configure_tool_form_layout(general_form)

        timeframe = QComboBox()
        timeframe.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        order_type = QComboBox()
        order_type.addItems(["market", "limit", "stop_limit"])
        market_type = QComboBox()
        for label, value in MARKET_VENUE_CHOICES:
            market_type.addItem(label, value)

        history_limit = QDoubleSpinBox()
        history_limit.setDecimals(0)
        history_limit.setRange(100, 50000)
        history_limit.setSingleStep(500)
        history_limit.setSuffix(" candles")
        history_limit.setToolTip("Maximum number of candles to request and keep for charts and backtesting.")

        initial_capital = QDoubleSpinBox()
        initial_capital.setDecimals(2)
        initial_capital.setRange(0, 1000000000)
        initial_capital.setSingleStep(1000)

        refresh_ms = QDoubleSpinBox()
        refresh_ms.setDecimals(0)
        refresh_ms.setRange(250, 60000)
        refresh_ms.setSingleStep(250)

        orderbook_ms = QDoubleSpinBox()
        orderbook_ms.setDecimals(0)
        orderbook_ms.setRange(250, 60000)
        orderbook_ms.setSingleStep(250)

        hedging_mode = QComboBox()
        hedging_mode.addItem("Enabled (when broker supports hedging)", True)
        hedging_mode.addItem("Disabled", False)

        general_form.addRow("Default timeframe", timeframe)
        general_form.addRow("Default order type", order_type)
        general_form.addRow("Trading venue", market_type)
        general_form.addRow("Hedging mode", hedging_mode)
        general_form.addRow("History limit (candles)", history_limit)
        general_form.addRow("Initial capital", initial_capital)
        general_form.addRow("Terminal refresh (ms)", refresh_ms)
        general_form.addRow("Orderbook refresh (ms)", orderbook_ms)
        tabs.addTab(_hotfix_wrap_tab_in_scroll_area(general_tab, minimum_width=600), "General")

        storage_tab = QWidget()
        storage_form = QFormLayout(storage_tab)
        self._configure_tool_form_layout(storage_form)

        database_mode = QComboBox()
        database_mode.addItem("Local SQLite", "local")
        database_mode.addItem("Remote URL", "remote")

        database_url = QLineEdit()
        database_hint = QLabel()
        database_hint.setWordWrap(True)
        database_hint.setObjectName("tool_window_section_hint")

        storage_form.addRow("Database backend", database_mode)
        storage_form.addRow("Remote database URL", database_url)
        storage_form.addRow("", database_hint)
        tabs.addTab(_hotfix_wrap_tab_in_scroll_area(storage_tab, minimum_width=600), "Storage")

        display_tab = QWidget()
        display_form = QFormLayout(display_tab)
        self._configure_tool_form_layout(display_form)

        bid_ask_mode = QComboBox()
        bid_ask_mode.addItem("Show", True)
        bid_ask_mode.addItem("Hide", False)

        forex_candle_source = QComboBox()
        forex_candle_source.addItem("Bid (MT4-style)", "bid")
        forex_candle_source.addItem("Mid", "mid")
        forex_candle_source.addItem("Ask", "ask")
        forex_candle_source.setToolTip("MT4-style forex charts typically use bid candles.")

        display_hint = QLabel("MT4-style chart colors let you tune the plot background, foreground, grid, and candles.")
        display_hint.setWordWrap(True)
        display_hint.setObjectName("tool_window_section_hint")

        chart_background_btn = QPushButton()
        chart_grid_btn = QPushButton()
        chart_axis_btn = QPushButton()
        up_color_btn = QPushButton()
        down_color_btn = QPushButton()
        chart_background_btn.clicked.connect(
            lambda: _hotfix_pick_settings_color(
                window,
                "_settings_chart_background_color",
                chart_background_btn,
                "Select Chart Background Color",
            )
        )
        chart_grid_btn.clicked.connect(
            lambda: _hotfix_pick_settings_color(
                window,
                "_settings_chart_grid_color",
                chart_grid_btn,
                "Select Chart Grid Color",
            )
        )
        chart_axis_btn.clicked.connect(
            lambda: _hotfix_pick_settings_color(
                window,
                "_settings_chart_axis_color",
                chart_axis_btn,
                "Select Chart Foreground Color",
            )
        )
        up_color_btn.clicked.connect(
            lambda: _hotfix_pick_settings_color(
                window,
                "_settings_up_color",
                up_color_btn,
                "Select Bullish Candle Color",
            )
        )
        down_color_btn.clicked.connect(
            lambda: _hotfix_pick_settings_color(
                window,
                "_settings_down_color",
                down_color_btn,
                "Select Bearish Candle Color",
            )
        )

        display_form.addRow("Forex candle source", forex_candle_source)
        display_form.addRow("Bid/ask guide lines", bid_ask_mode)
        display_form.addRow("", display_hint)
        display_form.addRow("Chart background", chart_background_btn)
        display_form.addRow("Chart foreground", chart_axis_btn)
        display_form.addRow("Grid color", chart_grid_btn)
        display_form.addRow("Bullish candle color", up_color_btn)
        display_form.addRow("Bearish candle color", down_color_btn)
        tabs.addTab(_hotfix_wrap_tab_in_scroll_area(display_tab, minimum_width=600), "Display")

        risk_tab = QWidget()
        risk_form = QFormLayout(risk_tab)
        self._configure_tool_form_layout(risk_form)

        risk_profile = QComboBox()
        for name in _hotfix_risk_profile_names():
            risk_profile.addItem(name)

        risk_profile_description = QLabel()
        risk_profile_description.setWordWrap(True)
        risk_profile_description.setObjectName("tool_window_section_hint")

        max_portfolio = QDoubleSpinBox()
        max_portfolio.setDecimals(4)
        max_portfolio.setRange(0, 100000)
        max_portfolio.setSingleStep(0.01)

        max_trade = QDoubleSpinBox()
        max_trade.setDecimals(4)
        max_trade.setRange(0, 100000)
        max_trade.setSingleStep(0.01)

        max_position = QDoubleSpinBox()
        max_position.setDecimals(4)
        max_position.setRange(0, 100000)
        max_position.setSingleStep(0.01)

        max_gross = QDoubleSpinBox()
        max_gross.setDecimals(4)
        max_gross.setRange(0, 100000)
        max_gross.setSingleStep(0.01)

        margin_closeout_guard = QComboBox()
        margin_closeout_guard.addItem("Enabled", True)
        margin_closeout_guard.addItem("Disabled", False)

        margin_closeout_pct = QDoubleSpinBox()
        margin_closeout_pct.setDecimals(4)
        margin_closeout_pct.setRange(0.01, 1.0)
        margin_closeout_pct.setSingleStep(0.01)
        margin_closeout_pct.setToolTip("Blocks new trades when margin closeout risk reaches this ratio. Example: 0.50 = 50%.")

        risk_form.addRow("Risk profile", risk_profile)
        risk_form.addRow("", risk_profile_description)
        risk_form.addRow("Max portfolio risk", max_portfolio)
        risk_form.addRow("Max risk per trade", max_trade)
        risk_form.addRow("Max position size", max_position)
        risk_form.addRow("Max gross exposure", max_gross)
        risk_form.addRow("Closeout guard", margin_closeout_guard)
        risk_form.addRow("Closeout block threshold", margin_closeout_pct)
        tabs.addTab(_hotfix_wrap_tab_in_scroll_area(risk_tab, minimum_width=600), "Risk")

        strategy_tab = QWidget()
        strategy_form = QFormLayout(strategy_tab)
        self._configure_tool_form_layout(strategy_form)

        strategy_name = QComboBox()
        self._populate_strategy_picker(strategy_name, selected_strategy=getattr(self.controller, "strategy_name", "Trend Following"))

        strategy_rsi_period = QDoubleSpinBox()
        strategy_rsi_period.setDecimals(0)
        strategy_rsi_period.setRange(2, 500)
        strategy_rsi_period.setSingleStep(1)

        strategy_ema_fast = QDoubleSpinBox()
        strategy_ema_fast.setDecimals(0)
        strategy_ema_fast.setRange(2, 500)
        strategy_ema_fast.setSingleStep(1)

        strategy_ema_slow = QDoubleSpinBox()
        strategy_ema_slow.setDecimals(0)
        strategy_ema_slow.setRange(3, 1000)
        strategy_ema_slow.setSingleStep(1)

        strategy_atr_period = QDoubleSpinBox()
        strategy_atr_period.setDecimals(0)
        strategy_atr_period.setRange(2, 500)
        strategy_atr_period.setSingleStep(1)

        strategy_oversold = QDoubleSpinBox()
        strategy_oversold.setDecimals(1)
        strategy_oversold.setRange(0, 100)
        strategy_oversold.setSingleStep(1)

        strategy_overbought = QDoubleSpinBox()
        strategy_overbought.setDecimals(1)
        strategy_overbought.setRange(0, 100)
        strategy_overbought.setSingleStep(1)

        strategy_breakout = QDoubleSpinBox()
        strategy_breakout.setDecimals(0)
        strategy_breakout.setRange(2, 500)
        strategy_breakout.setSingleStep(1)

        strategy_confidence = QDoubleSpinBox()
        strategy_confidence.setDecimals(2)
        strategy_confidence.setRange(0, 1)
        strategy_confidence.setSingleStep(0.01)

        strategy_amount = QDoubleSpinBox()
        strategy_amount.setDecimals(4)
        strategy_amount.setRange(0.0001, 1000000)
        strategy_amount.setSingleStep(0.01)

        strategy_form.addRow("Active strategy", strategy_name)
        strategy_form.addRow("RSI period", strategy_rsi_period)
        strategy_form.addRow("EMA fast", strategy_ema_fast)
        strategy_form.addRow("EMA slow", strategy_ema_slow)
        strategy_form.addRow("ATR period", strategy_atr_period)
        strategy_form.addRow("Oversold threshold", strategy_oversold)
        strategy_form.addRow("Overbought threshold", strategy_overbought)
        strategy_form.addRow("Breakout lookback", strategy_breakout)
        strategy_form.addRow("AI min confidence", strategy_confidence)
        strategy_form.addRow("Signal amount", strategy_amount)
        tabs.addTab(_hotfix_wrap_tab_in_scroll_area(strategy_tab, minimum_width=600), "Strategy")

        integrations_tab = QWidget()
        integrations_form = QFormLayout(integrations_tab)
        self._configure_tool_form_layout(integrations_form)

        telegram_enabled = QComboBox()
        telegram_enabled.addItem("Disabled", False)
        telegram_enabled.addItem("Enabled", True)

        telegram_bot_token = QLineEdit()
        telegram_bot_token.setPlaceholderText("Telegram bot token")

        telegram_chat_id = QLineEdit()
        telegram_chat_id.setPlaceholderText("Telegram chat ID")

        trade_close_notifications_enabled = QComboBox()
        trade_close_notifications_enabled.addItem("Disabled", False)
        trade_close_notifications_enabled.addItem("Enabled", True)

        trade_close_notify_telegram = QCheckBox("Send to Telegram")
        trade_close_notify_email = QCheckBox("Send to email")
        trade_close_notify_sms = QCheckBox("Send to SMS")

        trade_close_email_host = QLineEdit()
        trade_close_email_host.setPlaceholderText("smtp.gmail.com")
        trade_close_email_port = QSpinBox()
        trade_close_email_port.setRange(1, 65535)
        trade_close_email_port.setValue(587)
        trade_close_email_username = QLineEdit()
        trade_close_email_username.setPlaceholderText("SMTP username")
        trade_close_email_password = QLineEdit()
        trade_close_email_password.setEchoMode(QLineEdit.EchoMode.Password)
        trade_close_email_password.setPlaceholderText("SMTP password")
        trade_close_email_from = QLineEdit()
        trade_close_email_from.setPlaceholderText("sender@example.com")
        trade_close_email_to = QLineEdit()
        trade_close_email_to.setPlaceholderText("recipient@example.com, another@example.com")
        trade_close_email_starttls = QCheckBox("Use STARTTLS")
        trade_close_email_starttls.setChecked(True)

        trade_close_sms_account_sid = QLineEdit()
        trade_close_sms_account_sid.setPlaceholderText("Twilio account SID")
        trade_close_sms_auth_token = QLineEdit()
        trade_close_sms_auth_token.setEchoMode(QLineEdit.EchoMode.Password)
        trade_close_sms_auth_token.setPlaceholderText("Twilio auth token")
        trade_close_sms_from_number = QLineEdit()
        trade_close_sms_from_number.setPlaceholderText("+15551234567")
        trade_close_sms_to_number = QLineEdit()
        trade_close_sms_to_number.setPlaceholderText("+15557654321")

        openai_api_key = QLineEdit()
        openai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        openai_api_key.setPlaceholderText("OpenAI API key")

        openai_model = QLineEdit()
        openai_model.setPlaceholderText("gpt-5-mini")

        openai_test_button = QPushButton("Test OpenAI")
        openai_test_button.setStyleSheet(self._action_button_style())
        openai_test_status = QLabel("Use this to verify the typed OpenAI key and model before saving.")
        openai_test_status.setWordWrap(True)
        openai_test_status.setStyleSheet("color: #9fb0c7; padding-top: 4px;")
        openai_test_row = QWidget()
        openai_test_layout = QVBoxLayout(openai_test_row)
        openai_test_layout.setContentsMargins(0, 0, 0, 0)
        openai_test_layout.setSpacing(6)
        openai_test_layout.addWidget(openai_test_button)
        openai_test_layout.addWidget(openai_test_status)

        news_enabled = QComboBox()
        news_enabled.addItem("Disabled", False)
        news_enabled.addItem("Enabled", True)

        news_autotrade = QComboBox()
        news_autotrade.addItem("Off", False)
        news_autotrade.addItem("On", True)

        news_chart = QComboBox()
        news_chart.addItem("Hide", False)
        news_chart.addItem("Draw on charts", True)

        news_feed_url = QLineEdit()
        news_feed_url.setPlaceholderText(NewsService.DEFAULT_FEED_URL)

        integrations_form.addRow("Telegram notifications", telegram_enabled)
        integrations_form.addRow("Telegram bot token", telegram_bot_token)
        integrations_form.addRow("Telegram chat ID", telegram_chat_id)
        integrations_form.addRow(QLabel("<b>Trade close notifications</b>"))
        integrations_form.addRow("Trade close alerts", trade_close_notifications_enabled)
        integrations_form.addRow("", trade_close_notify_telegram)
        integrations_form.addRow("", trade_close_notify_email)
        integrations_form.addRow("", trade_close_notify_sms)
        integrations_form.addRow("SMTP host", trade_close_email_host)
        integrations_form.addRow("SMTP port", trade_close_email_port)
        integrations_form.addRow("SMTP username", trade_close_email_username)
        integrations_form.addRow("SMTP password", trade_close_email_password)
        integrations_form.addRow("Email from", trade_close_email_from)
        integrations_form.addRow("Email to", trade_close_email_to)
        integrations_form.addRow("", trade_close_email_starttls)
        integrations_form.addRow(QLabel("<b>SMS (Twilio)</b>"))
        integrations_form.addRow("Twilio account SID", trade_close_sms_account_sid)
        integrations_form.addRow("Twilio auth token", trade_close_sms_auth_token)
        integrations_form.addRow("Twilio from number", trade_close_sms_from_number)
        integrations_form.addRow("Twilio to number", trade_close_sms_to_number)
        integrations_form.addRow("OpenAI API key", openai_api_key)
        integrations_form.addRow("OpenAI model", openai_model)
        integrations_form.addRow("OpenAI test", openai_test_row)
        integrations_form.addRow("News feed", news_enabled)
        integrations_form.addRow("Trade from news bias", news_autotrade)
        integrations_form.addRow("Draw news on chart", news_chart)
        integrations_form.addRow("News feed URL", news_feed_url)
        tabs.addTab(_hotfix_wrap_tab_in_scroll_area(integrations_tab, minimum_width=600), "Integrations")

        summary = QLabel("-")
        summary.setWordWrap(True)
        summary.setObjectName("tool_window_summary_card")
        layout.addWidget(summary)

        actions = QHBoxLayout()
        exposure_btn = QPushButton("Open Portfolio Exposure")
        exposure_btn.setStyleSheet(self._action_button_style())
        exposure_btn.clicked.connect(self._show_portfolio_exposure)
        apply_btn = QPushButton("Save Settings")
        apply_btn.setStyleSheet(self._action_button_style())
        apply_btn.clicked.connect(lambda: self._apply_settings_window(window))
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(self._action_button_style())
        close_btn.clicked.connect(window.close)
        actions.addWidget(exposure_btn)
        actions.addStretch()
        actions.addWidget(apply_btn)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        window.setCentralWidget(container)
        window._settings_container = container
        window._settings_tabs = tabs
        window._settings_timeframe = timeframe
        window._settings_order_type = order_type
        window._settings_market_type = market_type
        window._settings_hedging_enabled = hedging_mode
        window._settings_database_mode = database_mode
        window._settings_database_url = database_url
        window._settings_database_hint = database_hint
        window._settings_history_limit = history_limit
        window._settings_initial_capital = initial_capital
        window._settings_refresh_ms = refresh_ms
        window._settings_orderbook_ms = orderbook_ms
        window._settings_forex_candle_source = forex_candle_source
        window._settings_bid_ask_mode = bid_ask_mode
        window._settings_chart_background_button = chart_background_btn
        window._settings_chart_axis_button = chart_axis_btn
        window._settings_chart_grid_button = chart_grid_btn
        window._settings_up_button = up_color_btn
        window._settings_down_button = down_color_btn
        window._settings_risk_profile = risk_profile
        window._settings_risk_profile_description = risk_profile_description
        window._settings_max_portfolio = max_portfolio
        window._settings_max_trade = max_trade
        window._settings_max_position = max_position
        window._settings_max_gross = max_gross
        window._settings_margin_closeout_guard = margin_closeout_guard
        window._settings_margin_closeout_pct = margin_closeout_pct
        window._risk_profile_updating = False
        window._settings_strategy_name = strategy_name
        window._settings_strategy_rsi_period = strategy_rsi_period
        window._settings_strategy_ema_fast = strategy_ema_fast
        window._settings_strategy_ema_slow = strategy_ema_slow
        window._settings_strategy_atr_period = strategy_atr_period
        window._settings_strategy_oversold = strategy_oversold
        window._settings_strategy_overbought = strategy_overbought
        window._settings_strategy_breakout = strategy_breakout
        window._settings_strategy_confidence = strategy_confidence
        window._settings_strategy_amount = strategy_amount
        window._settings_telegram_enabled = telegram_enabled
        window._settings_telegram_bot_token = telegram_bot_token
        window._settings_telegram_chat_id = telegram_chat_id
        window._settings_trade_close_notifications_enabled = trade_close_notifications_enabled
        window._settings_trade_close_notify_telegram = trade_close_notify_telegram
        window._settings_trade_close_notify_email = trade_close_notify_email
        window._settings_trade_close_notify_sms = trade_close_notify_sms
        window._settings_trade_close_email_host = trade_close_email_host
        window._settings_trade_close_email_port = trade_close_email_port
        window._settings_trade_close_email_username = trade_close_email_username
        window._settings_trade_close_email_password = trade_close_email_password
        window._settings_trade_close_email_from = trade_close_email_from
        window._settings_trade_close_email_to = trade_close_email_to
        window._settings_trade_close_email_starttls = trade_close_email_starttls
        window._settings_trade_close_sms_account_sid = trade_close_sms_account_sid
        window._settings_trade_close_sms_auth_token = trade_close_sms_auth_token
        window._settings_trade_close_sms_from_number = trade_close_sms_from_number
        window._settings_trade_close_sms_to_number = trade_close_sms_to_number
        window._settings_openai_api_key = openai_api_key
        window._settings_openai_model = openai_model
        window._settings_openai_test_button = openai_test_button
        window._settings_openai_test_status = openai_test_status
        window._settings_news_enabled = news_enabled
        window._settings_news_autotrade = news_autotrade
        window._settings_news_chart = news_chart
        window._settings_news_feed_url = news_feed_url
        window._settings_summary = summary
        openai_test_button.clicked.connect(lambda: _hotfix_test_openai_from_settings(self, window))
        database_mode.currentIndexChanged.connect(lambda *_: _hotfix_update_database_mode_state(window))
        risk_profile.currentTextChanged.connect(lambda value: _hotfix_apply_risk_profile_to_window(window, value))
        max_portfolio.valueChanged.connect(lambda *_: _hotfix_sync_risk_profile_from_window(window))
        max_trade.valueChanged.connect(lambda *_: _hotfix_sync_risk_profile_from_window(window))
        max_position.valueChanged.connect(lambda *_: _hotfix_sync_risk_profile_from_window(window))
        max_gross.valueChanged.connect(lambda *_: _hotfix_sync_risk_profile_from_window(window))

    risk_engine = _hotfix_get_live_risk_engine(self)
    refresh_interval = 1000
    if hasattr(self, "refresh_timer") and self.refresh_timer is not None:
        refresh_interval = max(250, self.refresh_timer.interval())
    orderbook_interval = 1500
    if hasattr(self, "orderbook_timer") and self.orderbook_timer is not None:
        orderbook_interval = max(250, self.orderbook_timer.interval())

    _hotfix_refresh_market_type_picker(window, self.controller)
    window._settings_timeframe.setCurrentText(getattr(self, "current_timeframe", getattr(self.controller, "time_frame", "1h")))
    window._settings_order_type.setCurrentText(getattr(self, "order_type", getattr(self.controller, "order_type", "limit")))
    market_index = window._settings_market_type.findData(getattr(self.controller, "market_trade_preference", "auto"))
    window._settings_market_type.setCurrentIndex(market_index if market_index >= 0 else 0)
    database_mode_index = window._settings_database_mode.findData(getattr(self.controller, "database_mode", "local"))
    window._settings_database_mode.setCurrentIndex(database_mode_index if database_mode_index >= 0 else 0)
    window._settings_database_url.setText(str(getattr(self.controller, "database_url", "") or ""))
    _hotfix_update_database_mode_state(window)
    window._settings_hedging_enabled.setCurrentIndex(0 if getattr(self.controller, "hedging_enabled", True) else 1)
    window._settings_history_limit.setValue(float(getattr(self.controller, "limit", 50000)))
    window._settings_initial_capital.setValue(float(getattr(self.controller, "initial_capital", 10000)))
    window._settings_refresh_ms.setValue(float(refresh_interval))
    window._settings_orderbook_ms.setValue(float(orderbook_interval))
    forex_candle_source_index = window._settings_forex_candle_source.findData(
        getattr(self.controller, "forex_candle_price_component", "bid")
    )
    window._settings_forex_candle_source.setCurrentIndex(
        forex_candle_source_index if forex_candle_source_index >= 0 else 0
    )
    window._settings_bid_ask_mode.setCurrentIndex(0 if getattr(self, "show_bid_ask_lines", True) else 1)

    window._settings_chart_background_color = getattr(self, "chart_background_color", "#11161f")
    window._settings_chart_grid_color = getattr(self, "chart_grid_color", "#8290a0")
    window._settings_chart_axis_color = getattr(self, "chart_axis_color", "#9aa4b2")
    window._settings_up_color = getattr(self, "candle_up_color", "#26a69a")
    window._settings_down_color = getattr(self, "candle_down_color", "#ef5350")
    _hotfix_update_color_button(
        window._settings_chart_background_button,
        window._settings_chart_background_color,
    )
    _hotfix_update_color_button(
        window._settings_chart_grid_button,
        window._settings_chart_grid_color,
    )
    _hotfix_update_color_button(
        window._settings_chart_axis_button,
        window._settings_chart_axis_color,
    )
    _hotfix_update_color_button(window._settings_up_button, window._settings_up_color)
    _hotfix_update_color_button(window._settings_down_button, window._settings_down_color)

    window._settings_max_portfolio.setValue(float(getattr(risk_engine, "max_portfolio_risk", getattr(self.controller, "max_portfolio_risk", 0.2))))
    window._settings_max_trade.setValue(float(getattr(risk_engine, "max_risk_per_trade", getattr(self.controller, "max_risk_per_trade", 0.02))))
    window._settings_max_position.setValue(float(getattr(risk_engine, "max_position_size_pct", getattr(self.controller, "max_position_size_pct", 0.05))))
    window._settings_max_gross.setValue(float(getattr(risk_engine, "max_gross_exposure_pct", getattr(self.controller, "max_gross_exposure_pct", 1.0))))
    window._settings_margin_closeout_guard.setCurrentIndex(
        0 if getattr(self.controller, "margin_closeout_guard_enabled", True) else 1
    )
    window._settings_margin_closeout_pct.setValue(
        float(getattr(self.controller, "max_margin_closeout_pct", 0.50))
    )
    configured_profile = str(
        getattr(self.controller, "risk_profile_name", "")
        or self.settings.value("risk/profile_name", "")
        or ""
    ).strip()
    detected_profile = _hotfix_detect_risk_profile_name(
        {
            "max_portfolio_risk": window._settings_max_portfolio.value(),
            "max_risk_per_trade": window._settings_max_trade.value(),
            "max_position_size_pct": window._settings_max_position.value(),
            "max_gross_exposure_pct": window._settings_max_gross.value(),
        }
    )
    _hotfix_apply_risk_profile_to_window(window, configured_profile or detected_profile)
    strategy_params = dict(getattr(self.controller, "strategy_params", {}) or {})
    current_strategy_name = Strategy.normalize_strategy_name(
        getattr(self.controller, "strategy_name", None) or getattr(getattr(self.controller, "config", None), "strategy", "Trend Following")
    )
    window._settings_strategy_name.setCurrentText(str(current_strategy_name))
    window._settings_strategy_rsi_period.setValue(float(strategy_params.get("rsi_period", 14)))
    window._settings_strategy_ema_fast.setValue(float(strategy_params.get("ema_fast", 20)))
    window._settings_strategy_ema_slow.setValue(float(strategy_params.get("ema_slow", 50)))
    window._settings_strategy_atr_period.setValue(float(strategy_params.get("atr_period", 14)))
    window._settings_strategy_oversold.setValue(float(strategy_params.get("oversold_threshold", 35.0)))
    window._settings_strategy_overbought.setValue(float(strategy_params.get("overbought_threshold", 65.0)))
    window._settings_strategy_breakout.setValue(float(strategy_params.get("breakout_lookback", 20)))
    window._settings_strategy_confidence.setValue(float(strategy_params.get("min_confidence", 0.55)))
    window._settings_strategy_amount.setValue(float(strategy_params.get("signal_amount", 1.0)))
    window._settings_telegram_enabled.setCurrentIndex(1 if getattr(self.controller, "telegram_enabled", False) else 0)
    window._settings_telegram_bot_token.setText(str(getattr(self.controller, "telegram_bot_token", "") or ""))
    window._settings_telegram_chat_id.setText(str(getattr(self.controller, "telegram_chat_id", "") or ""))
    window._settings_trade_close_notifications_enabled.setCurrentIndex(1 if getattr(self.controller, "trade_close_notifications_enabled", False) else 0)
    window._settings_trade_close_notify_telegram.setChecked(bool(getattr(self.controller, "trade_close_notify_telegram", False)))
    window._settings_trade_close_notify_email.setChecked(bool(getattr(self.controller, "trade_close_notify_email", False)))
    window._settings_trade_close_notify_sms.setChecked(bool(getattr(self.controller, "trade_close_notify_sms", False)))
    window._settings_trade_close_email_host.setText(str(getattr(self.controller, "trade_close_email_host", "") or ""))
    window._settings_trade_close_email_port.setValue(int(getattr(self.controller, "trade_close_email_port", 587) or 587))
    window._settings_trade_close_email_username.setText(str(getattr(self.controller, "trade_close_email_username", "") or ""))
    window._settings_trade_close_email_password.setText(str(getattr(self.controller, "trade_close_email_password", "") or ""))
    window._settings_trade_close_email_from.setText(str(getattr(self.controller, "trade_close_email_from", "") or ""))
    window._settings_trade_close_email_to.setText(str(getattr(self.controller, "trade_close_email_to", "") or ""))
    window._settings_trade_close_email_starttls.setChecked(bool(getattr(self.controller, "trade_close_email_starttls", True)))
    window._settings_trade_close_sms_account_sid.setText(str(getattr(self.controller, "trade_close_sms_account_sid", "") or ""))
    window._settings_trade_close_sms_auth_token.setText(str(getattr(self.controller, "trade_close_sms_auth_token", "") or ""))
    window._settings_trade_close_sms_from_number.setText(str(getattr(self.controller, "trade_close_sms_from_number", "") or ""))
    window._settings_trade_close_sms_to_number.setText(str(getattr(self.controller, "trade_close_sms_to_number", "") or ""))
    window._settings_openai_api_key.setText(str(getattr(self.controller, "openai_api_key", "") or ""))
    window._settings_openai_model.setText(str(getattr(self.controller, "openai_model", "gpt-5-mini") or "gpt-5-mini"))
    window._settings_openai_test_status.setStyleSheet("color: #9fb0c7; padding-top: 4px;")
    window._settings_openai_test_status.setText("Use this to verify the typed OpenAI key and model before saving.")
    window._settings_openai_test_button.setEnabled(True)
    window._settings_openai_test_button.setText("Test OpenAI")
    window._settings_news_enabled.setCurrentIndex(1 if getattr(self.controller, "news_enabled", True) else 0)
    window._settings_news_autotrade.setCurrentIndex(1 if getattr(self.controller, "news_autotrade_enabled", False) else 0)
    window._settings_news_chart.setCurrentIndex(1 if getattr(self.controller, "news_draw_on_chart", True) else 0)
    window._settings_news_feed_url.setText(str(getattr(self.controller, "news_feed_url", NewsService.DEFAULT_FEED_URL) or NewsService.DEFAULT_FEED_URL))

    window._settings_summary.setText(
        "Current defaults: "
        f"{window._settings_timeframe.currentText()} | "
        f"{window._settings_order_type.currentText()} orders | "
        f"{window._settings_market_type.currentText()} venue | "
        f"{window._settings_database_mode.currentText()} storage | "
        f"{window._settings_risk_profile.currentText()} risk | "
        f"closeout {'on' if window._settings_margin_closeout_guard.currentData() else 'off'} @ {window._settings_margin_closeout_pct.value():.2%} | "
        f"{window._settings_strategy_name.currentText()} | "
        f"hedging {'on' if window._settings_hedging_enabled.currentData() else 'off'} | "
        f"history {int(window._settings_history_limit.value())} candles | "
        f"capital {window._settings_initial_capital.value():.2f} | "
        f"Telegram {'on' if window._settings_telegram_enabled.currentData() else 'off'} | "
        f"Trade close alerts {'on' if window._settings_trade_close_notifications_enabled.currentData() else 'off'} | "
        f"News {'on' if window._settings_news_enabled.currentData() else 'off'} | "
        f"OpenAI {'set' if window._settings_openai_api_key.text().strip() else 'not set'}"
    )

    _hotfix_focus_settings_tab(window, initial_tab or "General")

    window.show()
    window.raise_()
    window.activateWindow()
    return window


def _hotfix_apply_settings_window(self, window=None):
    try:
        values = _hotfix_collect_settings_values(self, window)
        if not values:
            return

        storage_notice = _hotfix_apply_settings_values(self, values, persist=True, reload_chart=True)

        active_window = window or self.detached_tool_windows.get("application_settings")
        summary = getattr(active_window, "_settings_summary", None)
        if summary is not None:
            summary.setText(
                ("Saved settings. " + storage_notice + " ") if storage_notice else "Saved settings. "
                f"Storage: {getattr(self.controller, 'current_database_label', lambda: values.get('database_mode', 'local'))()} | "
                f"Risk profile: {values.get('risk_profile_name', 'Custom')} | "
                f"Closeout guard: {'enabled' if values.get('margin_closeout_guard_enabled') else 'disabled'} @ {float(values.get('max_margin_closeout_pct', 0.50) or 0.50):.2%} | "
                f"Hedging: {'enabled' if values.get('hedging_enabled', True) else 'disabled'} | "
                f"Strategy: {values['strategy_name']} | "
                f"Timeframe: {values['timeframe']} | "
                f"Order type: {values['order_type']} | "
                f"Venue: {values['market_trade_preference']} | "
                f"FX candles: {str(values.get('forex_candle_price_component') or 'bid').capitalize()} | "
                f"History: {values['history_limit']} | "
                f"Bid/ask lines: {'shown' if values['show_bid_ask_lines'] else 'hidden'} | "
                f"News auto: {'enabled' if values['news_autotrade_enabled'] else 'disabled'} | "
                f"Telegram: {'enabled' if values['telegram_enabled'] else 'disabled'} | "
                f"Trade close alerts: {'enabled' if values['trade_close_notifications_enabled'] else 'disabled'} | "
                f"OpenAI model: {values.get('openai_model') or 'gpt-5-mini'}"
            )

        if storage_notice:
            self.system_console.log(storage_notice, "WARN")
        self.system_console.log("Application settings updated successfully.", "INFO")

    except Exception as e:
        active_window = window or self.detached_tool_windows.get("application_settings")
        summary = getattr(active_window, "_settings_summary", None)
        if summary is not None:
            summary.setText(f"Unable to save settings: {e}")
        self.logger.error(f"Settings error: {e}")


def _hotfix_open_settings(self):
    self._show_settings_window("General")


def _hotfix_restore_settings(self):
    geometry = self.settings.value("geometry")
    if geometry:
        self.restoreGeometry(geometry)

    state = self.settings.value("windowState")
    if state:
        self.restoreState(state)
        normalize = getattr(self, "_normalize_workspace_sidebar_docks", None)
        if callable(normalize):
            normalize()
        ensure_execution = getattr(self, "_ensure_execution_workspace_visible", None)
        if callable(ensure_execution):
            QTimer.singleShot(0, lambda: ensure_execution(force=True))

    strategy_params = dict(getattr(self.controller, "strategy_params", {}) or {})

    values = {
        "timeframe": self.settings.value("terminal/current_timeframe", getattr(self.controller, "time_frame", getattr(self, "current_timeframe", "1h"))),
        "order_type": self.settings.value("terminal/order_type", getattr(self.controller, "order_type", getattr(self, "order_type", "limit"))),
        "market_trade_preference": self.settings.value("trading/market_type", getattr(self.controller, "market_trade_preference", "auto")),
        "database_mode": self.settings.value("storage/database_mode", getattr(self.controller, "database_mode", "local")),
        "database_url": self.settings.value("storage/database_url", getattr(self.controller, "database_url", "")),
        "history_limit": _hotfix_settings_int(self.settings.value("terminal/history_limit", getattr(self.controller, "limit", 50000)), getattr(self.controller, "limit", 50000)),
        "initial_capital": _hotfix_settings_float(self.settings.value("terminal/initial_capital", getattr(self.controller, "initial_capital", 10000)), getattr(self.controller, "initial_capital", 10000)),
        "hedging_enabled": _hotfix_settings_bool(self.settings.value("trading/hedging_enabled", getattr(self.controller, "hedging_enabled", True)), getattr(self.controller, "hedging_enabled", True)),
        "refresh_interval_ms": _hotfix_settings_int(self.settings.value("terminal/refresh_interval_ms", 1000), 1000),
        "orderbook_interval_ms": _hotfix_settings_int(self.settings.value("terminal/orderbook_interval_ms", 1500), 1500),
        "forex_candle_price_component": self.settings.value(
            "market_data/forex_candle_price_component",
            getattr(self.controller, "forex_candle_price_component", "bid"),
        ),
        "show_bid_ask_lines": _hotfix_settings_bool(self.settings.value("terminal/show_bid_ask_lines", getattr(self, "show_bid_ask_lines", True)), getattr(self, "show_bid_ask_lines", True)),
        "chart_background_color": self.settings.value("chart/background_color", getattr(self, "chart_background_color", "#11161f")),
        "chart_grid_color": self.settings.value("chart/grid_color", getattr(self, "chart_grid_color", "#8290a0")),
        "chart_axis_color": self.settings.value("chart/axis_color", getattr(self, "chart_axis_color", "#9aa4b2")),
        "candle_up_color": self.settings.value("chart/candle_up_color", getattr(self, "candle_up_color", "#26a69a")),
        "candle_down_color": self.settings.value("chart/candle_down_color", getattr(self, "candle_down_color", "#ef5350")),
        "risk_profile_name": self.settings.value("risk/profile_name", getattr(self.controller, "risk_profile_name", "Balanced")),
        "max_portfolio_risk": _hotfix_settings_float(self.settings.value("risk/max_portfolio_risk", getattr(self.controller, "max_portfolio_risk", 0.2)), getattr(self.controller, "max_portfolio_risk", 0.2)),
        "max_risk_per_trade": _hotfix_settings_float(self.settings.value("risk/max_risk_per_trade", getattr(self.controller, "max_risk_per_trade", 0.02)), getattr(self.controller, "max_risk_per_trade", 0.02)),
        "max_position_size_pct": _hotfix_settings_float(self.settings.value("risk/max_position_size_pct", getattr(self.controller, "max_position_size_pct", 0.05)), getattr(self.controller, "max_position_size_pct", 0.05)),
        "max_gross_exposure_pct": _hotfix_settings_float(self.settings.value("risk/max_gross_exposure_pct", getattr(self.controller, "max_gross_exposure_pct", 1.0)), getattr(self.controller, "max_gross_exposure_pct", 1.0)),
        "margin_closeout_guard_enabled": _hotfix_settings_bool(self.settings.value("risk/margin_closeout_guard_enabled", getattr(self.controller, "margin_closeout_guard_enabled", True)), getattr(self.controller, "margin_closeout_guard_enabled", True)),
        "max_margin_closeout_pct": _hotfix_settings_float(self.settings.value("risk/max_margin_closeout_pct", getattr(self.controller, "max_margin_closeout_pct", 0.50)), getattr(self.controller, "max_margin_closeout_pct", 0.50)),
        "strategy_name": self.settings.value("strategy/name", getattr(self.controller, "strategy_name", "Trend Following")),
        "strategy_rsi_period": _hotfix_settings_int(self.settings.value("strategy/rsi_period", strategy_params.get("rsi_period", 14)), 14),
        "strategy_ema_fast": _hotfix_settings_int(self.settings.value("strategy/ema_fast", strategy_params.get("ema_fast", 20)), 20),
        "strategy_ema_slow": _hotfix_settings_int(self.settings.value("strategy/ema_slow", strategy_params.get("ema_slow", 50)), 50),
        "strategy_atr_period": _hotfix_settings_int(self.settings.value("strategy/atr_period", strategy_params.get("atr_period", 14)), 14),
        "strategy_oversold_threshold": _hotfix_settings_float(self.settings.value("strategy/oversold_threshold", strategy_params.get("oversold_threshold", 35.0)), 35.0),
        "strategy_overbought_threshold": _hotfix_settings_float(self.settings.value("strategy/overbought_threshold", strategy_params.get("overbought_threshold", 65.0)), 65.0),
        "strategy_breakout_lookback": _hotfix_settings_int(self.settings.value("strategy/breakout_lookback", strategy_params.get("breakout_lookback", 20)), 20),
        "strategy_min_confidence": _hotfix_settings_float(self.settings.value("strategy/min_confidence", strategy_params.get("min_confidence", 0.55)), 0.55),
        "strategy_signal_amount": _hotfix_settings_float(self.settings.value("strategy/signal_amount", strategy_params.get("signal_amount", 1.0)), 1.0),
        "telegram_enabled": _hotfix_settings_bool(self.settings.value("integrations/telegram_enabled", getattr(self.controller, "telegram_enabled", False)), getattr(self.controller, "telegram_enabled", False)),
        "telegram_bot_token": self.settings.value("integrations/telegram_bot_token", getattr(self.controller, "telegram_bot_token", "")),
        "telegram_chat_id": self.settings.value("integrations/telegram_chat_id", getattr(self.controller, "telegram_chat_id", "")),
        "trade_close_notifications_enabled": _hotfix_settings_bool(self.settings.value("integrations/trade_close_notifications_enabled", getattr(self.controller, "trade_close_notifications_enabled", False)), getattr(self.controller, "trade_close_notifications_enabled", False)),
        "trade_close_notify_telegram": _hotfix_settings_bool(self.settings.value("integrations/trade_close_notify_telegram", getattr(self.controller, "trade_close_notify_telegram", False)), getattr(self.controller, "trade_close_notify_telegram", False)),
        "trade_close_notify_email": _hotfix_settings_bool(self.settings.value("integrations/trade_close_notify_email", getattr(self.controller, "trade_close_notify_email", False)), getattr(self.controller, "trade_close_notify_email", False)),
        "trade_close_notify_sms": _hotfix_settings_bool(self.settings.value("integrations/trade_close_notify_sms", getattr(self.controller, "trade_close_notify_sms", False)), getattr(self.controller, "trade_close_notify_sms", False)),
        "trade_close_email_host": self.settings.value("integrations/trade_close_email_host", getattr(self.controller, "trade_close_email_host", "")),
        "trade_close_email_port": _hotfix_settings_int(self.settings.value("integrations/trade_close_email_port", getattr(self.controller, "trade_close_email_port", 587)), 587),
        "trade_close_email_username": self.settings.value("integrations/trade_close_email_username", getattr(self.controller, "trade_close_email_username", "")),
        "trade_close_email_password": self.settings.value("integrations/trade_close_email_password", getattr(self.controller, "trade_close_email_password", "")),
        "trade_close_email_from": self.settings.value("integrations/trade_close_email_from", getattr(self.controller, "trade_close_email_from", "")),
        "trade_close_email_to": self.settings.value("integrations/trade_close_email_to", getattr(self.controller, "trade_close_email_to", "")),
        "trade_close_email_starttls": _hotfix_settings_bool(self.settings.value("integrations/trade_close_email_starttls", getattr(self.controller, "trade_close_email_starttls", True)), getattr(self.controller, "trade_close_email_starttls", True)),
        "trade_close_sms_account_sid": self.settings.value("integrations/trade_close_sms_account_sid", getattr(self.controller, "trade_close_sms_account_sid", "")),
        "trade_close_sms_auth_token": self.settings.value("integrations/trade_close_sms_auth_token", getattr(self.controller, "trade_close_sms_auth_token", "")),
        "trade_close_sms_from_number": self.settings.value("integrations/trade_close_sms_from_number", getattr(self.controller, "trade_close_sms_from_number", "")),
        "trade_close_sms_to_number": self.settings.value("integrations/trade_close_sms_to_number", getattr(self.controller, "trade_close_sms_to_number", "")),
        "openai_api_key": self.settings.value("integrations/openai_api_key", getattr(self.controller, "openai_api_key", "")),
        "openai_model": self.settings.value("integrations/openai_model", getattr(self.controller, "openai_model", "gpt-5-mini")),
        "news_enabled": _hotfix_settings_bool(self.settings.value("integrations/news_enabled", getattr(self.controller, "news_enabled", True)), getattr(self.controller, "news_enabled", True)),
        "news_autotrade_enabled": _hotfix_settings_bool(self.settings.value("integrations/news_autotrade_enabled", getattr(self.controller, "news_autotrade_enabled", False)), getattr(self.controller, "news_autotrade_enabled", False)),
        "news_draw_on_chart": _hotfix_settings_bool(self.settings.value("integrations/news_draw_on_chart", getattr(self.controller, "news_draw_on_chart", True)), getattr(self.controller, "news_draw_on_chart", True)),
        "news_feed_url": self.settings.value("integrations/news_feed_url", getattr(self.controller, "news_feed_url", NewsService.DEFAULT_FEED_URL)),
    }

    _hotfix_apply_settings_values(self, values, persist=False, reload_chart=False)
    self._restore_detached_chart_layouts()


def _hotfix_close_event(self, event):
    self._save_detached_chart_layouts()
    self._ui_shutting_down = True
    try:
        stop_runtime_timers = getattr(self, "_stop_runtime_timers", None)
        if callable(stop_runtime_timers):
            stop_runtime_timers()
        if hasattr(self, "spinner_timer") and self.spinner_timer is not None:
            self.spinner_timer.stop()
        for task_name in (
            "_initial_terminal_data_task",
            "_assets_refresh_task",
            "_positions_refresh_task",
            "_open_orders_refresh_task",
            "_order_history_refresh_task",
            "_trade_history_refresh_task",
            "_broker_status_refresh_task",
            "_passive_signal_scan_task",
            "_autotrade_enable_task",
        ):
            task = getattr(self, task_name, None)
            if task is not None and not task.done():
                task.cancel()
        if hasattr(self, "_disconnect_controller_signals"):
            self._disconnect_controller_signals()
        if hasattr(self, "_safe_disconnect") and hasattr(self, "ai_signal"):
            self._safe_disconnect(self.ai_signal, self._update_ai_signal)
        if bool(getattr(self, "_app_event_filter_installed", False)):
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._app_event_filter_installed = False
    except Exception:
        pass

    values = {
        "timeframe": getattr(self, "current_timeframe", getattr(self.controller, "time_frame", "1h")),
        "order_type": getattr(self, "order_type", getattr(self.controller, "order_type", "limit")),
        "market_trade_preference": getattr(self.controller, "market_trade_preference", "auto"),
        "forex_candle_price_component": getattr(self.controller, "forex_candle_price_component", "bid"),
        "history_limit": getattr(self.controller, "limit", 50000),
        "initial_capital": getattr(self.controller, "initial_capital", 10000),
        "hedging_enabled": getattr(self.controller, "hedging_enabled", True),
        "refresh_interval_ms": self.refresh_timer.interval() if hasattr(self, "refresh_timer") and self.refresh_timer is not None else 1000,
        "orderbook_interval_ms": self.orderbook_timer.interval() if hasattr(self, "orderbook_timer") and self.orderbook_timer is not None else 1500,
        "show_bid_ask_lines": getattr(self, "show_bid_ask_lines", True),
        "chart_background_color": getattr(self, "chart_background_color", "#11161f"),
        "chart_grid_color": getattr(self, "chart_grid_color", "#8290a0"),
        "chart_axis_color": getattr(self, "chart_axis_color", "#9aa4b2"),
        "candle_up_color": getattr(self, "candle_up_color", "#26a69a"),
        "candle_down_color": getattr(self, "candle_down_color", "#ef5350"),
        "risk_profile_name": getattr(self.controller, "risk_profile_name", "Balanced"),
        "max_portfolio_risk": getattr(self.controller, "max_portfolio_risk", 0.2),
        "max_risk_per_trade": getattr(self.controller, "max_risk_per_trade", 0.02),
        "max_position_size_pct": getattr(self.controller, "max_position_size_pct", 0.05),
        "max_gross_exposure_pct": getattr(self.controller, "max_gross_exposure_pct", 1.0),
        "margin_closeout_guard_enabled": getattr(self.controller, "margin_closeout_guard_enabled", True),
        "max_margin_closeout_pct": getattr(self.controller, "max_margin_closeout_pct", 0.50),
        "strategy_name": getattr(self.controller, "strategy_name", "Trend Following"),
        "strategy_rsi_period": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 14)("rsi_period", 14),
        "strategy_ema_fast": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 20)("ema_fast", 20),
        "strategy_ema_slow": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 50)("ema_slow", 50),
        "strategy_atr_period": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 14)("atr_period", 14),
        "strategy_oversold_threshold": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 35.0)("oversold_threshold", 35.0),
        "strategy_overbought_threshold": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 65.0)("overbought_threshold", 65.0),
        "strategy_breakout_lookback": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 20)("breakout_lookback", 20),
        "strategy_min_confidence": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 0.55)("min_confidence", 0.55),
        "strategy_signal_amount": getattr(getattr(self.controller, "strategy_params", {}), "get", lambda *_: 1.0)("signal_amount", 1.0),
        "telegram_enabled": getattr(self.controller, "telegram_enabled", False),
        "telegram_bot_token": getattr(self.controller, "telegram_bot_token", ""),
        "telegram_chat_id": getattr(self.controller, "telegram_chat_id", ""),
        "trade_close_notifications_enabled": getattr(self.controller, "trade_close_notifications_enabled", False),
        "trade_close_notify_telegram": getattr(self.controller, "trade_close_notify_telegram", False),
        "trade_close_notify_email": getattr(self.controller, "trade_close_notify_email", False),
        "trade_close_notify_sms": getattr(self.controller, "trade_close_notify_sms", False),
        "trade_close_email_host": getattr(self.controller, "trade_close_email_host", ""),
        "trade_close_email_port": getattr(self.controller, "trade_close_email_port", 587),
        "trade_close_email_username": getattr(self.controller, "trade_close_email_username", ""),
        "trade_close_email_password": getattr(self.controller, "trade_close_email_password", ""),
        "trade_close_email_from": getattr(self.controller, "trade_close_email_from", ""),
        "trade_close_email_to": getattr(self.controller, "trade_close_email_to", ""),
        "trade_close_email_starttls": getattr(self.controller, "trade_close_email_starttls", True),
        "trade_close_sms_account_sid": getattr(self.controller, "trade_close_sms_account_sid", ""),
        "trade_close_sms_auth_token": getattr(self.controller, "trade_close_sms_auth_token", ""),
        "trade_close_sms_from_number": getattr(self.controller, "trade_close_sms_from_number", ""),
        "trade_close_sms_to_number": getattr(self.controller, "trade_close_sms_to_number", ""),
        "openai_api_key": getattr(self.controller, "openai_api_key", ""),
        "openai_model": getattr(self.controller, "openai_model", "gpt-5-mini"),
        "news_enabled": getattr(self.controller, "news_enabled", True),
        "news_autotrade_enabled": getattr(self.controller, "news_autotrade_enabled", False),
        "news_draw_on_chart": getattr(self.controller, "news_draw_on_chart", True),
        "news_feed_url": getattr(self.controller, "news_feed_url", NewsService.DEFAULT_FEED_URL),
    }
    _hotfix_apply_settings_values(self, values, persist=True, reload_chart=False)
    super(Terminal, self).closeEvent(event)


async def _hotfix_refresh_markets_async(self):
    broker = getattr(self.controller, "broker", None)
    if broker is None:
        raise RuntimeError("Broker is not connected")

    if hasattr(broker, "connect"):
        try:
            maybe = broker.connect()
            if asyncio.iscoroutine(maybe):
                await maybe
        except Exception:
            pass

    symbols = None
    if hasattr(self.controller, "_fetch_symbols"):
        symbols = await self.controller._fetch_symbols(broker)
    else:
        if hasattr(broker, "fetch_symbol"):
            symbols = await broker.fetch_symbol()
        elif hasattr(broker, "fetch_symbols"):
            symbols = await broker.fetch_symbols()

    if not symbols:
        raise RuntimeError("No symbols were returned by the broker")

    broker_cfg = getattr(getattr(self.controller, "config", None), "broker", None)
    broker_type = getattr(broker_cfg, "type", None)
    exchange = getattr(broker_cfg, "exchange", None) or getattr(broker, "exchange_name", "Broker")

    if hasattr(self.controller, "_filter_symbols_for_trading"):
        symbols = self.controller._filter_symbols_for_trading(symbols, broker_type, exchange=exchange)

    if hasattr(self.controller, "_select_trade_symbols"):
        selected = await self.controller._select_trade_symbols(symbols, broker_type)
        if selected:
            symbols = selected

    self.controller.symbols = list(symbols)
    emit_symbols = getattr(self.controller, "_emit_symbols_signal_deferred", None)
    if callable(emit_symbols):
        emit_symbols(str(exchange), list(self.controller.symbols))
    else:
        self.controller.symbols_signal.emit(str(exchange), list(self.controller.symbols))

    active_symbol = self._current_chart_symbol()
    if active_symbol and hasattr(self.controller, "request_candle_data"):
        active_chart = self._current_chart_widget()
        if isinstance(active_chart, ChartWidget) and str(getattr(active_chart, "symbol", "") or "").strip() == str(active_symbol).strip():
            await self._request_chart_data_for_widget(
                active_chart,
                limit=self._history_request_limit(),
            )
        else:
            await self.controller.request_candle_data(
                symbol=active_symbol,
                timeframe=getattr(self, "current_timeframe", "1h"),
                limit=self._history_request_limit(),
            )
            await self._reload_chart_data(active_symbol, getattr(self, "current_timeframe", "1h"))

    if active_symbol and hasattr(self.controller, "request_orderbook"):
        await self.controller.request_orderbook(symbol=active_symbol, limit=20)

    self._refresh_terminal()
    self.system_console.log(f"Markets refreshed: {len(self.controller.symbols)} symbols loaded.", "INFO")
    
    # Log venue type information
    venue_type = self._get_current_venue_type()
    broker = getattr(self.controller, "broker", None)
    exchange = str(getattr(broker, "exchange_name", None) or "").upper() or "BROKER"
    self.system_console.log(f"Venue Type: {venue_type} - Market symbols displayed for {exchange} {venue_type} market.", "INFO")


def _hotfix_refresh_markets(self):
    async def runner():
        try:
            await _hotfix_refresh_markets_async(self)
        except Exception as e:
            self.system_console.log(f"Market refresh failed: {e}", "ERROR")

    asyncio.get_event_loop().create_task(runner())


async def _hotfix_reload_balance_async(self):
    if not hasattr(self.controller, "update_balance"):
        raise RuntimeError("Balance reload is not supported by this controller")

    await self.controller.update_balance()
    self._refresh_terminal()

    balance = getattr(self.controller, "balances", {})
    summary, _tooltip = self._compact_balance_text(balance)
    self.system_console.log(f"Balances reloaded: {summary}", "INFO")


def _hotfix_reload_balance(self):
    async def runner():
        try:
            await _hotfix_reload_balance_async(self)
        except Exception as e:
            self.system_console.log(f"Balance reload failed: {e}", "ERROR")

    asyncio.get_event_loop().create_task(runner())


def _hotfix_refresh_active_orderbook(self):
    symbol = self._current_chart_symbol()
    if not symbol:
        self.system_console.log("Open a chart before refreshing orderbook.", "ERROR")
        return

    async def runner():
        try:
            if not hasattr(self.controller, "request_orderbook"):
                raise RuntimeError("Orderbook refresh is not supported by this controller")
            await self.controller.request_orderbook(symbol=symbol, limit=20)
            if hasattr(self.controller, "request_recent_trades"):
                await self.controller.request_recent_trades(symbol=symbol, limit=40)
            self.system_console.log(f"Orderbook refreshed for {symbol}.", "INFO")
        except Exception as e:
            self.system_console.log(f"Orderbook refresh failed: {e}", "ERROR")

    asyncio.get_event_loop().create_task(runner())


def _hotfix_refresh_active_chart_data(self):
    chart = self._current_chart_widget()
    if not isinstance(chart, ChartWidget):
        self.system_console.log("Open a chart before refreshing candles.", "ERROR")
        return

    symbol = chart.symbol
    timeframe = getattr(chart, "timeframe", getattr(self, "current_timeframe", "1h"))

    async def runner():
        try:
            if not hasattr(self.controller, "request_candle_data"):
                raise RuntimeError("Chart refresh is not supported by this controller")

            await self._request_chart_data_for_widget(
                chart,
                limit=self._history_request_limit(),
            )
            self.system_console.log(f"Chart data refreshed for {symbol} ({timeframe}).", "INFO")
        except Exception as e:
            self.system_console.log(f"Chart refresh failed: {e}", "ERROR")

    asyncio.get_event_loop().create_task(runner())


# Bind overrides
Terminal.run_backtest_clicked = _hotfix_run_backtest_clicked
Terminal._prepare_and_run_backtest = _hotfix_prepare_and_run_backtest
Terminal._load_backtest_history_runner = _hotfix_load_backtest_history_runner
Terminal._backtest_requested_range_text = staticmethod(_hotfix_backtest_requested_range_text)
Terminal._backtest_requested_limit = staticmethod(_hotfix_backtest_requested_limit)
Terminal._backtest_symbol_candidates = _hotfix_backtest_symbol_candidates
Terminal._backtest_timeframe_candidates = _hotfix_backtest_timeframe_candidates
Terminal._refresh_backtest_selectors = _hotfix_refresh_backtest_selectors
Terminal._load_backtest_history_clicked = _hotfix_load_backtest_history_clicked
Terminal._backtest_selection_changed = _hotfix_backtest_selection_changed
Terminal._start_backtest_graph_animation = _hotfix_start_backtest_graph_animation
Terminal._stop_backtest_graph_animation = staticmethod(_hotfix_stop_backtest_graph_animation)
Terminal._tick_backtest_graph_animation = _hotfix_tick_backtest_graph_animation
Terminal.start_backtest = _hotfix_start_backtest
Terminal.stop_backtest = _hotfix_stop_backtest
Terminal._generate_report = _hotfix_generate_report
Terminal._show_optimization_window = _hotfix_show_optimization_window
Terminal._refresh_optimization_selectors = _hotfix_refresh_optimization_selectors
Terminal._optimization_selection_changed = _hotfix_optimization_selection_changed
Terminal._refresh_optimization_window = _hotfix_refresh_optimization_window
Terminal._run_strategy_optimization = _hotfix_run_strategy_optimization
Terminal._run_strategy_ranking = _hotfix_run_strategy_ranking
Terminal._apply_best_optimization_params = _hotfix_apply_best_optimization_params
Terminal._assign_ranked_strategies_to_symbol = _hotfix_assign_ranked_strategies_to_symbol
Terminal._optimize_strategy = _hotfix_optimize_strategy
Terminal._open_strategy_assignment_window = _hotfix_show_strategy_assignment_window
Terminal._show_strategy_assignment_window = _hotfix_show_strategy_assignment_window
Terminal._refresh_strategy_assignment_window = _hotfix_refresh_strategy_assignment_window
Terminal._refresh_strategy_assignment_adaptive_details = _hotfix_refresh_strategy_assignment_adaptive_details
Terminal._apply_default_strategy_assignment = _hotfix_apply_default_strategy_assignment
Terminal._apply_single_strategy_assignment = _hotfix_apply_single_strategy_assignment
Terminal._apply_ranked_strategy_assignment = _hotfix_apply_ranked_strategy_assignment_from_window
Terminal._stellar_expert_asset_url = _hotfix_stellar_expert_asset_url
Terminal._stellar_asset_identifier = _hotfix_stellar_asset_identifier
Terminal._parse_stellar_asset_entry = _hotfix_parse_stellar_asset_entry
Terminal._selected_stellar_asset_row = _hotfix_selected_stellar_asset_row
Terminal._is_stellar_asset_blocked = _hotfix_is_stellar_asset_blocked
Terminal._stellar_asset_explorer_rows = _hotfix_stellar_asset_explorer_rows
Terminal._merge_stellar_asset_rows = _hotfix_merge_stellar_asset_rows
Terminal._refresh_stellar_asset_explorer_window = _hotfix_refresh_stellar_asset_explorer_window
Terminal._open_selected_stellar_asset = _hotfix_open_selected_stellar_asset
Terminal._load_stellar_asset_directory_page_async = _hotfix_load_stellar_asset_directory_page_async
Terminal._load_stellar_asset_directory_page = _hotfix_load_stellar_asset_directory_page
Terminal._open_stellar_asset_trustline_async = _hotfix_open_stellar_asset_trustline_async
Terminal._open_stellar_asset_trustline = _hotfix_open_stellar_asset_trustline
Terminal._auto_trust_stellar_asset_by_roi_async = _hotfix_auto_trust_stellar_asset_by_roi_async
Terminal._auto_trust_stellar_asset_by_roi = _hotfix_auto_trust_stellar_asset_by_roi
Terminal._open_stellar_asset_explorer_window = _hotfix_open_stellar_asset_explorer_window
Terminal._open_ml_research_window = _hotfix_show_ml_research_window
Terminal._show_ml_research_window = _hotfix_show_ml_research_window
Terminal._refresh_ml_research_window = _hotfix_refresh_ml_research_window
Terminal._run_ml_model_training = _hotfix_run_ml_model_training
Terminal._run_ml_walk_forward = _hotfix_run_ml_walk_forward
Terminal._run_ml_auto_research = _hotfix_run_ml_auto_research
Terminal._deploy_selected_ml_model = _hotfix_deploy_selected_ml_model
Terminal._reload_chart_data = _hotfix_reload_chart_data
Terminal._refresh_markets = _hotfix_refresh_markets
Terminal._reload_balance = _hotfix_reload_balance
Terminal._refresh_active_chart_data = _hotfix_refresh_active_chart_data
Terminal._refresh_active_orderbook = _hotfix_refresh_active_orderbook
Terminal._show_settings_window = _hotfix_show_settings_window
Terminal._apply_settings_window = _hotfix_apply_settings_window
Terminal._show_risk_settings_window = _hotfix_show_settings_window
Terminal._apply_risk_settings = _hotfix_apply_settings_window
Terminal._open_settings = _hotfix_open_settings
Terminal._open_risk_settings = _hotfix_open_risk_settings
Terminal._restore_settings = _hotfix_restore_settings
Terminal.closeEvent = _hotfix_close_event
Terminal.save_settings = _hotfix_save_settings
















#
#
# install_terminal_operator_features(Terminal)
