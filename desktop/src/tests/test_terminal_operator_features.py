import os
import sys
import time
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QDockWidget, QMainWindow, QTableWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.chart.chart_widget import ChartWidget
from frontend.ui.terminal import Terminal, _hotfix_apply_storage_settings


class _SettingsRecorder:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class _MenuTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = SimpleNamespace(language_code="en", set_language=lambda _code: None, symbols=[])
        self.show_bid_ask_lines = True
        self.current_connection_status = "connecting"
        self.language_actions = {}
        self.timeframe_buttons = {}
        self.autotrading_enabled = False
        self.connection_indicator = None
        self.symbol_label = None
        self.open_symbol_button = None
        self.screenshot_button = None
        self.system_status_button = None
        self.kill_switch_button = None
        self.session_mode_badge = None
        self.license_badge = None
        self.trading_activity_label = None
        self.favorite_symbols = set()
        self.detached_tool_windows = {}

    def _tr(self, key, **kwargs):
        return key

    def apply_language(self):
        return Terminal.apply_language(self)

    def _sync_chart_timeframe_menu_actions(self):
        return Terminal._sync_chart_timeframe_menu_actions(self)

    def _update_autotrade_button(self):
        return None

    def _set_active_timeframe_button(self, _timeframe):
        return None

    def _current_chart_symbol(self):
        return "BTC/USDT"

    def __getattr__(self, name):
        if name.startswith("_"):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class _ChartRequestController:
    def __init__(self, frame):
        self.frame = frame
        self.candle_buffers = {}
        self.news_draw_on_chart = False

    async def request_candle_data(self, symbol, timeframe="1h", limit=None):
        return self.frame


class _DerivativeChartRequestController(_ChartRequestController):
    def __init__(self, frame):
        super().__init__(frame)
        self.requested_symbols = []

    @staticmethod
    def _resolve_preferred_market_symbol(symbol, preference=None):
        normalized = str(symbol or "").strip().upper()
        if normalized == "BTC/USD":
            return "BTC/USD:USD"
        return normalized

    async def request_candle_data(self, symbol, timeframe="1h", limit=None):
        self.requested_symbols.append(symbol)
        return self.frame


class _ChartRequestTerminal(QMainWindow):
    def __init__(self, frame):
        super().__init__()
        self.controller = _ChartRequestController(frame)
        self._ui_shutting_down = False
        self.logger = SimpleNamespace(error=lambda *args, **kwargs: None)
        self.system_console = SimpleNamespace(log=lambda *args, **kwargs: None)
        self.heartbeat = SimpleNamespace(setStyleSheet=lambda *args, **kwargs: None)
        self._chart_request_tokens = {}
        self.current_timeframe = "1h"
        self._last_chart_request_key = None
        self._active_chart_widget_ref = None
        self.symbol_picker = None
        self.chart = ChartWidget("AAVE/USD", "1h", self.controller)

    def _history_request_limit(self):
        return 240

    def _is_qt_object_alive(self, obj):
        return obj is not None

    def _iter_chart_widgets(self):
        return [self.chart]


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _bind(fake, *names):
    for name in names:
        method = getattr(Terminal, name)
        setattr(fake, name, lambda *args, _method=method, **kwargs: _method(fake, *args, **kwargs))


class _VisibleWindowStub:
    def __init__(self, visible=True):
        self._visible = visible

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def isVisible(self):
        return self._visible

    def isHidden(self):
        return not self._visible


def test_create_menu_bar_adds_workspace_notifications_palette_and_favorite_actions():
    _app()
    terminal = _MenuTerminal()

    Terminal._create_menu_bar(terminal)

    menu_titles = [action.text() for action in terminal.menuBar().actions()]

    workspace_actions = terminal.workspace_menu.actions()
    panels_actions = terminal.panels_menu.actions()
    strategy_actions = terminal.strategy_menu.actions()
    backtest_actions = terminal.backtest_menu.actions()
    assert terminal.action_workspace_trading in workspace_actions
    assert terminal.action_workspace_research in workspace_actions
    assert terminal.action_workspace_risk in workspace_actions
    assert terminal.action_workspace_review in workspace_actions
    assert terminal.action_symbol_universe in workspace_actions
    assert terminal.action_save_workspace_layout in workspace_actions
    assert terminal.action_restore_workspace_layout in workspace_actions
    assert terminal.action_reset_dock_layout in workspace_actions
    assert terminal.panels_menu.menuAction() in workspace_actions
    assert terminal.action_symbol_universe in terminal.tools_menu.actions()
    assert terminal.action_market_watch_panel in panels_actions
    assert terminal.action_tick_chart_panel in panels_actions
    assert terminal.action_session_tabs_panel in panels_actions
    assert terminal.action_system_console_panel in panels_actions
    assert terminal.backtest_menu.menuAction() in strategy_actions
    assert terminal.action_strategy_optimization in backtest_actions
    assert terminal.action_strategy_assigner in strategy_actions
    assert terminal.action_strategy_scorecard in strategy_actions
    assert terminal.action_strategy_debug in strategy_actions
    assert terminal.action_notifications in terminal.review_menu.actions()
    assert terminal.action_notifications in terminal.tools_menu.actions()
    assert terminal.action_agent_timeline in terminal.review_menu.actions()
    assert terminal.action_agent_timeline in terminal.research_menu.actions()
    assert terminal.action_agent_timeline in terminal.tools_menu.actions()
    assert terminal.action_trader_agent_monitor in terminal.review_menu.actions()
    assert terminal.action_trader_agent_monitor in terminal.research_menu.actions()
    assert terminal.action_trader_agent_monitor in terminal.tools_menu.actions()
    assert terminal.action_trader_tv in terminal.education_menu.actions()
    assert terminal.action_education_center in terminal.education_menu.actions()
    assert terminal.action_command_palette in terminal.tools_menu.actions()
    assert terminal.action_system_console in terminal.tools_menu.actions()
    assert terminal.action_system_status in terminal.tools_menu.actions()
    assert terminal.action_favorite_symbol in terminal.charts_menu.actions()
    assert terminal.chart_studies_menu.menuAction() in terminal.charts_menu.actions()
    assert terminal.action_remove_indicator in terminal.chart_studies_menu.actions()
    assert terminal.action_chart_settings in terminal.chart_style_menu.actions()
    assert terminal.chart_timeframe_menu.menuAction() in terminal.charts_menu.actions()
    assert menu_titles[-1] == terminal.help_menu.title()
    assert menu_titles[-2] == terminal.workspace_menu.title()


def test_push_notification_dedupes_repeated_messages():
    fake = SimpleNamespace(
        _notification_records=[],
        _notification_dedupe_cache={},
        _runtime_notification_state={},
        detached_tool_windows={},
        action_notifications=None,
        _is_qt_object_alive=lambda _obj: False,
    )
    _bind(fake, "_ensure_notification_state", "_refresh_notification_action_text", "_push_notification")

    Terminal._push_notification(fake, "API disconnected", "Broker API is unavailable.", level="ERROR", source="broker", dedupe_seconds=60.0)
    Terminal._push_notification(fake, "API disconnected", "Broker API is unavailable.", level="ERROR", source="broker", dedupe_seconds=60.0)

    assert len(fake._notification_records) == 1
    assert fake._notification_records[0]["title"] == "API disconnected"


def test_get_or_create_tool_window_replaces_stale_detached_window_reference():
    _app()
    parent = QMainWindow()
    stale_window = QMainWindow(parent)
    stale_window.deleteLater()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()

    fake = SimpleNamespace(
        detached_tool_windows={"notification_center": stale_window},
        _is_qt_object_alive=lambda obj: False if obj is stale_window else True,
    )

    created = Terminal._get_or_create_tool_window(fake, "notification_center", "Notification Center")

    assert created is not stale_window
    assert fake.detached_tool_windows["notification_center"] is created
    assert created.windowTitle() == "Notification Center"
    assert created.objectName() == "tool_window_notification_center"
    assert "QTabWidget::pane" in created.styleSheet()
    assert "QHeaderView::section" in created.styleSheet()


def test_open_notification_center_builds_window_and_renders_records():
    _app()
    terminal = _MenuTerminal()
    terminal._notification_records = [
        {
            "id": 1,
            "timestamp": time.time(),
            "time_text": "2026-04-01 11:42:00",
            "created_at": "2026-04-01T11:42:00-04:00",
            "title": "API disconnected",
            "message": "The broker connection dropped.",
            "level": "ERROR",
            "source": "broker",
        }
    ]
    terminal._notification_dedupe_cache = {}
    terminal._runtime_notification_state = {}
    terminal.controller = SimpleNamespace(language_code="en", set_language=lambda _code: None, symbols=[])
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_ensure_notification_state",
        "_refresh_notification_action_text",
        "_refresh_notification_center_window",
        "_open_notification_center",
        "_workspace_context_key",
    )

    window = Terminal._open_notification_center(terminal)

    assert window is not None
    assert window.windowTitle() == "Notification Center"
    assert window._notification_table.rowCount() == 1
    assert "notifications shown" in window._notification_summary.text()
    assert window._notification_table.item(0, 2).text() == "API disconnected"
    assert window._notification_table.item(0, 3).text() == "The broker connection dropped."


def test_manual_trade_default_payload_uses_saved_template_values():
    fake = SimpleNamespace(
        controller=SimpleNamespace(symbols=["EUR/USD"]),
        symbol="EUR/USD",
        current_timeframe="1h",
        _current_chart_symbol=lambda: "EUR/USD",
        _load_manual_trade_template=lambda: {
            "order_type": "stop_limit",
            "quantity_mode": "lots",
            "amount": 0.5,
            "stop_price": 1.102,
        },
        _safe_float=lambda value, default=None: Terminal._safe_float(SimpleNamespace(), value, default),
        _manual_trade_quantity_context=lambda symbol: {
            "symbol": symbol,
            "supports_lots": True,
            "default_mode": "lots",
            "lot_units": 100000.0,
        },
        _normalize_manual_trade_quantity_mode=lambda value: value,
    )

    payload = Terminal._manual_trade_default_payload(fake, {"symbol": "EUR/USD"})

    assert payload["order_type"] == "stop_limit"
    assert payload["quantity_mode"] == "lots"
    assert payload["amount"] == 0.5
    assert payload["stop_price"] == 1.102


def test_apply_workspace_preset_toggles_docks_and_opens_matching_tools():
    fake = SimpleNamespace(
        settings=_SettingsRecorder(),
        favorite_symbols=set(),
        detached_tool_windows={
            "system_logs": _VisibleWindowStub(True),
            "market_chatgpt": _VisibleWindowStub(True),
            "manual_trade_ticket": _VisibleWindowStub(True),
        },
        system_console=SimpleNamespace(log=lambda *args, **kwargs: None),
        _is_qt_object_alive=lambda obj: obj is not None,
        _queue_terminal_layout_fit=lambda: None,
        _save_workspace_layout=lambda slot="last": True,
        _push_notification=lambda *args, **kwargs: None,
        _canonical_tool_window_key=lambda key: Terminal._canonical_tool_window_key(SimpleNamespace(), key),
    )
    opened = []
    fake._open_tool_window_by_key = lambda key: opened.append(key)
    for attr_name in (
        "market_watch_dock",
        "tick_chart_dock",
        "session_tabs_dock",
        "positions_dock",
        "trade_log_dock",
        "orderbook_dock",
        "risk_heatmap_dock",
        "system_status_dock",
        "system_console_dock",
    ):
        setattr(fake, attr_name, _VisibleWindowStub(True))

    Terminal._apply_workspace_preset(fake, "risk")

    assert fake.market_watch_dock.isHidden()
    assert fake.tick_chart_dock.isHidden()
    assert fake.session_tabs_dock.isHidden()
    assert not fake.positions_dock.isHidden()
    assert not fake.orderbook_dock.isHidden()
    assert not fake.risk_heatmap_dock.isHidden()
    assert fake.system_status_dock.isHidden()
    assert fake.system_console_dock.isHidden()
    assert fake.detached_tool_windows["system_logs"].isHidden()
    assert fake.detached_tool_windows["market_chatgpt"].isHidden()
    assert fake.detached_tool_windows["manual_trade_ticket"].isHidden()
    assert opened == ["portfolio_exposure", "position_analysis"]


def test_default_dock_layout_prioritizes_chart_space_and_hides_secondary_docks():
    _app()
    terminal = _MenuTerminal()
    terminal._is_qt_object_alive = lambda obj: obj is not None
    _bind(terminal, "_safe_tabify_docks", "_normalize_workspace_sidebar_docks", "_apply_default_dock_layout")
    for name, area in (
        ("market_watch_dock", Qt.LeftDockWidgetArea),
        ("tick_chart_dock", Qt.LeftDockWidgetArea),
        ("session_tabs_dock", Qt.RightDockWidgetArea),
        ("positions_dock", Qt.RightDockWidgetArea),
        ("trade_log_dock", Qt.RightDockWidgetArea),
        ("orderbook_dock", Qt.RightDockWidgetArea),
        ("risk_heatmap_dock", Qt.RightDockWidgetArea),
        ("ai_signal_dock", Qt.RightDockWidgetArea),
        ("strategy_scorecard_dock", Qt.RightDockWidgetArea),
        ("strategy_debug_dock", Qt.RightDockWidgetArea),
        ("system_status_dock", Qt.RightDockWidgetArea),
        ("system_console_dock", Qt.BottomDockWidgetArea),
    ):
        dock = QDockWidget(name, terminal)
        dock.setObjectName(name)
        terminal.addDockWidget(area, dock)
        setattr(terminal, name, dock)
    terminal.open_orders_dock = terminal.positions_dock
    terminal.show()

    Terminal._apply_default_dock_layout(terminal)

    assert not terminal.market_watch_dock.isHidden()
    assert terminal.tick_chart_dock.isHidden()
    assert terminal.session_tabs_dock.isHidden()
    assert not terminal.positions_dock.isHidden()
    assert not terminal.trade_log_dock.isHidden()
    assert not terminal.orderbook_dock.isHidden()
    assert terminal.risk_heatmap_dock.isHidden()
    assert terminal.ai_signal_dock.isHidden()
    assert terminal.dockWidgetArea(terminal.positions_dock) == Qt.RightDockWidgetArea


def test_normalize_workspace_sidebar_docks_skips_removed_docks_when_resizing():
    _app()
    from ui.components import terminal as current_terminal_module

    class _ResizeCaptureTerminal(QMainWindow):
        def __init__(self):
            super().__init__()
            self.resize_calls = []
            self._ui_shutting_down = False

        def _is_qt_object_alive(self, obj):
            return obj is not None

        def resizeDocks(self, docks, sizes, orientation):
            self.resize_calls.append((list(docks), list(sizes), orientation))

    terminal = _ResizeCaptureTerminal()
    for name in ("_safe_tabify_docks", "_normalize_workspace_sidebar_docks"):
        method = getattr(current_terminal_module.Terminal, name)
        setattr(
            terminal,
            name,
            lambda *args, _method=method, **kwargs: _method(terminal, *args, **kwargs),
        )
    for name, area in (
        ("market_watch_dock", Qt.LeftDockWidgetArea),
        ("positions_dock", Qt.RightDockWidgetArea),
        ("trade_log_dock", Qt.RightDockWidgetArea),
    ):
        dock = QDockWidget(name, terminal)
        dock.setObjectName(name)
        terminal.addDockWidget(area, dock)
        setattr(terminal, name, dock)
    terminal.show()
    terminal.removeDockWidget(terminal.positions_dock)
    _app().processEvents()

    current_terminal_module.Terminal._normalize_workspace_sidebar_docks(terminal)

    assert len(terminal.resize_calls) == 1
    docks, sizes, orientation = terminal.resize_calls[0]
    assert [dock.objectName() for dock in docks] == ["market_watch_dock", "trade_log_dock"]
    assert sizes == [260, 360]
    assert orientation == Qt.Horizontal


def test_visible_tool_window_keys_normalizes_aliases_and_extended_subwindows():
    fake = SimpleNamespace(
        detached_tool_windows={
            "system_logs": _VisibleWindowStub(True),
            "market_chatgpt": _VisibleWindowStub(True),
            "trader_agent": _VisibleWindowStub(True),
            "ml_research_lab": _VisibleWindowStub(True),
            "unknown_window": _VisibleWindowStub(True),
            "api_reference": _VisibleWindowStub(False),
        },
        _is_qt_object_alive=lambda obj: obj is not None,
    )
    _bind(fake, "_canonical_tool_window_key", "_visible_tool_window_keys")

    visible = Terminal._visible_tool_window_keys(fake)

    assert visible == ["agent_timeline", "logs", "market_chat", "ml_research_lab"]


def test_open_tool_window_by_key_supports_aliases_and_extended_subwindows():
    calls = []
    fake = SimpleNamespace(
        _open_market_chat_window=lambda: calls.append("market_chat"),
        _open_logs=lambda: calls.append("logs"),
        _open_notification_center=lambda: calls.append("notification_center"),
        _open_ml_research_window=lambda: calls.append("ml_research_lab"),
        _open_agent_timeline=lambda: calls.append("agent_timeline"),
        _show_settings_window=lambda: calls.append("application_settings"),
        _open_risk_settings=lambda: calls.append("risk_settings"),
        _show_backtest_window=lambda: calls.append("backtesting_workspace"),
        _optimize_strategy=lambda: calls.append("strategy_optimization"),
        _open_trader_tv_window=lambda: calls.append("education_trader_tv"),
        _open_docs=lambda: calls.append("help_documentation"),
        _open_api_docs=lambda: calls.append("api_reference"),
        _open_manual_trade=lambda: calls.append("manual_trade_ticket"),
        _open_trade_review_window=lambda trade: calls.append(("trade_review", trade)),
        _open_stellar_asset_explorer_window=lambda: calls.append("stellar_asset_explorer"),
        _open_strategy_assignment_window=lambda: calls.append("strategy_assignments"),
    )
    _bind(fake, "_canonical_tool_window_key", "_open_tool_window_by_key")

    Terminal._open_tool_window_by_key(fake, "system_logs")
    Terminal._open_tool_window_by_key(fake, "market_chatgpt")
    Terminal._open_tool_window_by_key(fake, "notifications")
    Terminal._open_tool_window_by_key(fake, "trader_agent")
    Terminal._open_tool_window_by_key(fake, "risk_settings")
    Terminal._open_tool_window_by_key(fake, "application_settings")
    Terminal._open_tool_window_by_key(fake, "backtesting_workspace")
    Terminal._open_tool_window_by_key(fake, "strategy_optimization")
    Terminal._open_tool_window_by_key(fake, "education_trader_tv")
    Terminal._open_tool_window_by_key(fake, "documentation")
    Terminal._open_tool_window_by_key(fake, "api_reference")
    Terminal._open_tool_window_by_key(fake, "manual_trade")
    Terminal._open_tool_window_by_key(fake, "trade_review")
    Terminal._open_tool_window_by_key(fake, "stellar_asset_explorer")
    Terminal._open_tool_window_by_key(fake, "strategy_assigner")
    Terminal._open_tool_window_by_key(fake, "ml_research_lab")

    assert calls == [
        "logs",
        "market_chat",
        "notification_center",
        "agent_timeline",
        "risk_settings",
        "application_settings",
        "backtesting_workspace",
        "strategy_optimization",
        "education_trader_tv",
        "help_documentation",
        "api_reference",
        "manual_trade_ticket",
        ("trade_review", {}),
        "stellar_asset_explorer",
        "strategy_assignments",
        "ml_research_lab",
    ]


def test_apply_storage_settings_falls_back_to_local_sqlite_when_pymysql_is_missing():
    calls = []

    def _configure_storage_database(**kwargs):
        calls.append(kwargs)
        if kwargs.get("database_mode") == "remote":
            raise ModuleNotFoundError("No module named 'pymysql'")
        return "sqlite:///fallback.sqlite3"

    fake = SimpleNamespace(
        controller=SimpleNamespace(configure_storage_database=_configure_storage_database),
    )

    notice = _hotfix_apply_storage_settings(
        fake,
        "remote",
        "mysql+pymysql://user:secret@localhost:3306/sopotek_trading?charset=utf8mb4",
        True,
    )

    assert "PyMySQL" in notice
    assert calls == [
        {
            "database_mode": "remote",
            "database_url": "mysql+pymysql://user:secret@localhost:3306/sopotek_trading?charset=utf8mb4",
            "persist": True,
            "raise_on_error": True,
        },
        {
            "database_mode": "local",
            "database_url": "",
            "persist": True,
            "raise_on_error": False,
        },
    ]


def test_command_palette_entries_include_operator_actions():
    fake = SimpleNamespace(
        controller=SimpleNamespace(symbols=[]),
        _open_manual_trade=lambda *args, **kwargs: None,
        _open_notification_center=lambda: None,
        _open_symbol_universe=lambda: None,
        _open_agent_timeline=lambda: None,
        _open_trader_agent_monitor=lambda: None,
        _open_performance=lambda: None,
        _show_portfolio_exposure=lambda: None,
        _open_position_analysis_window=lambda: None,
        _open_trade_checklist_window=lambda: None,
        _open_trade_journal_review_window=lambda: None,
        _open_recommendations_window=lambda: None,
        _open_market_chat_window=lambda: None,
        _open_quant_pm_window=lambda: None,
        _open_strategy_assignment_window=lambda: None,
        _optimize_strategy=lambda: None,
        _show_backtest_window=lambda: None,
        _export_diagnostics_bundle=lambda: None,
        _apply_workspace_preset=lambda _name: None,
        _save_current_workspace_layout=lambda: None,
        _restore_saved_workspace_layout=lambda: None,
        _apply_default_dock_layout=lambda: None,
        _show_workspace_dock=lambda _dock: None,
        market_watch_dock=object(),
        _toggle_current_symbol_favorite=lambda: None,
        _refresh_markets=lambda: None,
        _refresh_active_chart_data=lambda: None,
        _refresh_active_orderbook=lambda: None,
        _reload_balance=lambda: None,
    )

    entries = Terminal._command_palette_entries(fake, "")
    titles = {entry["title"] for entry in entries}

    assert "Trading Workspace" in titles
    assert "Research Workspace" in titles
    assert "Risk Workspace" in titles
    assert "Review Workspace" in titles
    assert "Symbol Universe" in titles
    assert "Trader Agent Monitor" in titles
    assert "Export Diagnostics Bundle" in titles
    assert "Reset Dock Layout" in titles
    assert "Show Market Watch" in titles


def test_open_symbol_universe_window_shows_controller_tiers():
    _app()
    terminal = _MenuTerminal()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=["BTC/USD", "ETH/USD", "SOL/USD"],
        get_symbol_universe_snapshot=lambda: {
            "active": ["BTC/USD", "ETH/USD"],
            "watchlist": ["BTC/USD", "SOL/USD", "ETH/USD"],
            "catalog": ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"],
            "background_catalog": ["SOL/USD", "XRP/USD"],
            "last_batch": ["BTC/USD", "SOL/USD"],
            "rotation_cursor": 2,
            "policy": {
                "live_symbol_limit": 4,
                "watchlist_limit": 8,
                "discovery_batch_size": 3,
            },
        },
    )
    terminal._is_qt_object_alive = lambda obj: obj is not None
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_symbol_universe_snapshot",
        "_refresh_symbol_universe_window",
        "_open_symbol_universe",
    )

    window = terminal._open_symbol_universe()

    assert window is not None
    assert "Active 2/4" in window._symbol_universe_summary.text()
    assert "Catalog 4" in window._symbol_universe_summary.text()
    tree = window._symbol_universe_tree
    top_labels = [tree.topLevelItem(index).text(0) for index in range(tree.topLevelItemCount())]
    assert "Active (2)" in top_labels
    assert "Watchlist (3)" in top_labels
    assert "Discovery Batch (2)" in top_labels
    active_item = tree.topLevelItem(0)
    assert active_item.childCount() >= 2
    child_symbols = {active_item.child(i).text(0) for i in range(active_item.childCount())}
    assert {"BTC/USD", "ETH/USD"}.issubset(child_symbols)


def test_market_watch_panel_action_shows_hidden_market_watch_dock():
    _app()
    terminal = _MenuTerminal()
    Terminal._create_menu_bar(terminal)
    _bind(terminal, "_show_workspace_dock")
    terminal._is_qt_object_alive = lambda obj: obj is not None
    terminal.show()
    terminal.market_watch_dock = QDockWidget("Market Watch", terminal)
    terminal.market_watch_dock.setObjectName("market_watch_dock")
    terminal.addDockWidget(Qt.LeftDockWidgetArea, terminal.market_watch_dock)
    terminal.trade_log_dock = QDockWidget("Trade Log", terminal)
    terminal.trade_log_dock.setObjectName("trade_log_dock")
    terminal.addDockWidget(Qt.RightDockWidgetArea, terminal.trade_log_dock)
    terminal.market_watch_dock.setFloating(True)
    terminal.market_watch_dock.hide()

    terminal.action_market_watch_panel.trigger()

    assert not terminal.market_watch_dock.isHidden()
    assert terminal.market_watch_dock.isFloating() is False
    assert terminal.dockWidgetArea(terminal.market_watch_dock) == Qt.LeftDockWidgetArea


def test_open_agent_timeline_builds_runtime_table_from_controller_feed():
    _app()
    terminal = _MenuTerminal()
    now = time.time()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "timestamp": now - 10,
                "kind": "memory",
                "symbol": "EUR/USD",
                "agent_name": "SignalAgent",
                "stage": "selected",
                "strategy_name": "EMA Cross",
                "timeframe": "4h",
                "message": "Signal selected for EUR/USD.",
                "payload": {"confidence": 0.82},
            },
            {
                "timestamp_label": "2026-03-17 10:06:00 UTC",
                "timestamp": now - 5,
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_approved",
                "stage": "",
                "strategy_name": "EMA Cross",
                "timeframe": "4h",
                "message": "Risk approved BUY for EUR/USD.",
                "payload": {"approved": True},
            },
        ],
        strategy_assignment_state_for_symbol=lambda symbol: {
            "mode": "single",
            "active_rows": [{"strategy_name": "Trend Following", "timeframe": "1h"}],
            "locked": True,
        },
        latest_agent_decision_overview_for_symbol=lambda symbol: {
            "strategy_name": "EMA Cross",
            "timeframe": "4h",
            "side": "buy",
            "approved": True,
            "final_agent": "RiskAgent",
            "final_stage": "approved",
            "reason": "within limits",
        },
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    tree = window._agent_timeline_tree

    assert tree.topLevelItemCount() == 1
    group = tree.topLevelItem(0)
    assert group.text(2) == "EUR/USD"
    assert group.text(3) == "2 events"
    assert group.childCount() == 2
    assert group.child(0).text(3) == "SignalAgent"
    assert group.child(1).text(3) == "risk_approved"
    assert "Current Assignment" in window._agent_timeline_assignment_label.text()
    assert "Strategy: Trend Following" in window._agent_timeline_assignment_label.text()
    assert "Latest Agent Recommendation" in window._agent_timeline_recommendation_label.text()
    assert "Strategy: EMA Cross" in window._agent_timeline_recommendation_label.text()
    assert "Approved: 1" in window._agent_timeline_health_counts.text()
    assert "Execution: 0" in window._agent_timeline_health_counts.text()
    assert "Count: 1" in window._agent_timeline_health_symbols.text()
    assert "Changes: 2" in window._agent_timeline_health_recent.text()
    group.setExpanded(True)
    tree.setCurrentItem(group.child(0))
    Terminal._refresh_agent_timeline_details(terminal, window)
    assert "Agent/Event: SignalAgent" in window._agent_timeline_detail_browser.toPlainText()
    assert '"confidence": 0.82' in window._agent_timeline_detail_browser.toPlainText()


def test_open_agent_timeline_accepts_iso_runtime_timestamps():
    _app()
    terminal = _MenuTerminal()
    now_dt = datetime.now(timezone.utc)
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "timestamp": (now_dt - timedelta(seconds=12)).isoformat(),
                "kind": "memory",
                "symbol": "EUR/USD",
                "agent_name": "SignalAgent",
                "stage": "selected",
                "strategy_name": "EMA Cross",
                "timeframe": "4h",
                "message": "Signal selected for EUR/USD.",
                "payload": {"confidence": 0.82},
            },
            {
                "timestamp_label": "2026-03-17 10:06:00 UTC",
                "timestamp": (now_dt - timedelta(seconds=4)).isoformat(),
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_approved",
                "stage": "",
                "strategy_name": "EMA Cross",
                "timeframe": "4h",
                "message": "Risk approved BUY for EUR/USD.",
                "payload": {"approved": True},
            },
        ],
        strategy_assignment_state_for_symbol=lambda symbol: {
            "mode": "single",
            "active_rows": [{"strategy_name": "Trend Following", "timeframe": "1h"}],
            "locked": True,
        },
        latest_agent_decision_overview_for_symbol=lambda symbol: {
            "strategy_name": "EMA Cross",
            "timeframe": "4h",
            "side": "buy",
            "approved": True,
            "final_agent": "RiskAgent",
            "final_stage": "approved",
            "reason": "within limits",
        },
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    tree = window._agent_timeline_tree

    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).childCount() == 2
    assert "Approved: 1" in window._agent_timeline_health_counts.text()
    assert "Changes: 2" in window._agent_timeline_health_recent.text()


def test_open_trader_agent_monitor_reuses_agent_runtime_monitor_and_shows_trader_details():
    _app()
    terminal = _MenuTerminal()
    now = time.time()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:06:00 UTC",
                "timestamp": now - 5,
                "kind": "bus",
                "agent_name": "TraderAgent",
                "event_type": "DECISION_EVENT",
                "profile_id": "growth",
                "symbol": "EUR/USD",
                "action": "BUY",
                "strategy_name": "Trend Following",
                "confidence": 0.78,
                "model_probability": 0.84,
                "reason": "BUY because weighted voting favored Trend Following and the growth profile allows the trade.",
                "applied_constraints": ["growth profile", "full size"],
                "votes": {"buy": 1.24, "sell": 0.31},
                "features": {"rsi": 31.4, "volatility": 0.012},
                "payload": {"profile_id": "growth", "action": "BUY"},
            },
            {
                "timestamp_label": "2026-03-17 10:02:00 UTC",
                "timestamp": now - 40,
                "kind": "bus",
                "agent_name": "TraderAgent",
                "event_type": "DECISION_EVENT",
                "profile_id": "income",
                "symbol": "BTC/USDT",
                "action": "SKIP",
                "strategy_name": "ML Ensemble",
                "confidence": 0.33,
                "model_probability": 0.29,
                "reason": "SKIP because the income profile requires higher confidence.",
                "applied_constraints": ["income profile", "low confidence"],
                "votes": {"buy": 0.41, "sell": 0.39},
                "features": {"order_book_imbalance": -0.12},
                "payload": {"profile_id": "income", "action": "SKIP"},
            },
        ],
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_populate_agent_timeline_filters",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_open_trader_agent_monitor",
        "_open_agent_timeline",
    )

    window = Terminal._open_trader_agent_monitor(terminal)
    tree = window._agent_timeline_tree

    assert window.windowTitle() == "Agent Runtime Monitor"
    assert terminal.detached_tool_windows["agent_timeline"] is window
    assert "trader_agent_monitor" not in terminal.detached_tool_windows
    assert tree.topLevelItemCount() == 2
    window._agent_timeline_filter.setText("income")
    Terminal._refresh_agent_timeline_window(terminal, window)
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(2) == "BTC/USDT"

    window._agent_timeline_filter.clear()
    Terminal._refresh_agent_timeline_window(terminal, window)
    btc_group = next(tree.topLevelItem(index) for index in range(tree.topLevelItemCount()) if tree.topLevelItem(index).text(2) == "BTC/USDT")
    tree.setCurrentItem(btc_group.child(0) or btc_group)
    Terminal._refresh_agent_timeline_details(terminal, window)
    detail_text = window._agent_timeline_detail_browser.toPlainText()
    assert "Agent/Event: TraderAgent" in detail_text
    assert "Profile: income" in detail_text
    assert "Action: SKIP" in detail_text
    assert "Model Probability:" in detail_text
    assert "income profile requires higher confidence" in detail_text
    assert "Votes:" in detail_text
    assert "Features:" in detail_text


def test_open_agent_timeline_restores_snapshot_rows_when_live_runtime_feed_is_empty():
    _app()
    terminal = _MenuTerminal()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=["EUR/USD"],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [],
        decision_timeline_snapshot=lambda symbol=None, limit=12: {
            "symbol": symbol or "EUR/USD",
            "summary": "EUR/USD: BUY approved via TraderAgent.",
            "steps": [
                {
                    "timestamp": 100.0,
                    "timestamp_label": "2026-04-10 10:00:00 UTC",
                    "agent_name": "SignalAgent",
                    "stage": "signal",
                    "status": "signal",
                    "strategy_name": "EMA Cross",
                    "timeframe": "1h",
                    "side": "buy",
                    "reason": "Momentum breakout aligned with trend.",
                    "payload": {"confidence": 0.82},
                },
                {
                    "timestamp": 105.0,
                    "timestamp_label": "2026-04-10 10:00:05 UTC",
                    "agent_name": "TraderAgent",
                    "stage": "buy",
                    "status": "approved",
                    "strategy_name": "EMA Cross",
                    "timeframe": "1h",
                    "side": "buy",
                    "reason": "BUY because weighted voting favored Trend Following.",
                    "payload": {
                        "profile_id": "growth",
                        "action": "BUY",
                        "confidence": 0.78,
                        "model_probability": 0.84,
                        "votes": {"buy": 1.24, "sell": 0.31},
                        "features": {"rsi": 31.4},
                    },
                },
            ],
        },
        strategy_assignment_state_for_symbol=lambda symbol: {
            "mode": "single",
            "active_rows": [{"strategy_name": "EMA Cross", "timeframe": "1h"}],
            "locked": False,
        },
        latest_agent_decision_overview_for_symbol=lambda symbol: {
            "strategy_name": "EMA Cross",
            "timeframe": "1h",
            "side": "buy",
            "approved": True,
            "final_agent": "TraderAgent",
            "final_stage": "buy",
            "reason": "BUY because weighted voting favored Trend Following.",
        },
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_agent_timeline_snapshot_rows",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_populate_agent_timeline_filters",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    tree = window._agent_timeline_tree

    assert tree.topLevelItemCount() == 1
    group = tree.topLevelItem(0)
    assert group.text(2) == "EUR/USD"
    assert group.childCount() == 2
    assert "restored decision steps" in window._agent_timeline_summary.text()
    tree.setCurrentItem(group.child(0))
    Terminal._refresh_agent_timeline_details(terminal, window)
    detail_text = window._agent_timeline_detail_browser.toPlainText()
    assert "Agent/Event: TraderAgent" in detail_text
    assert "Profile: growth" in detail_text
    assert "Action: BUY" in detail_text
    assert "Votes:" in detail_text


def test_replay_selected_agent_timeline_symbol_opens_strategy_assigner_for_selected_symbol():
    _app()
    terminal = _MenuTerminal()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "kind": "memory",
                "symbol": "GBP/USD",
                "agent_name": "SignalAgent",
                "stage": "selected",
                "strategy_name": "Trend Following",
                "timeframe": "1h",
                "message": "Signal selected for GBP/USD.",
            }
        ],
    )
    replay_messages = []
    strategy_window = SimpleNamespace(_strategy_assignment_symbol_picker=QComboBox())
    terminal._open_strategy_assignment_window = lambda: strategy_window
    terminal._refresh_strategy_assignment_window = lambda window=None, message=None: replay_messages.append((window, message))
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    window._agent_timeline_tree.setCurrentItem(window._agent_timeline_tree.topLevelItem(0).child(0))
    opened = Terminal._replay_selected_agent_timeline_symbol(terminal, window)

    assert opened is strategy_window
    assert strategy_window._strategy_assignment_selected_symbol == "GBP/USD"
    assert strategy_window._strategy_assignment_symbol_picker.currentText() == "GBP/USD"
    assert replay_messages[0][0] is strategy_window
    assert "Replaying the latest agent chain for GBP/USD." == replay_messages[0][1]


def test_agent_timeline_filters_and_pin_symbol_scope_rows():
    _app()
    terminal = _MenuTerminal()
    now = time.time()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:06:00 UTC",
                "timestamp": now - 10,
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_approved",
                "approved": True,
                "strategy_name": "EMA Cross",
                "timeframe": "4h",
                "message": "Risk approved BUY for EUR/USD.",
                "payload": {"approved": True},
            },
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "timestamp": now - 15,
                "kind": "memory",
                "symbol": "EUR/USD",
                "agent_name": "SignalAgent",
                "stage": "selected",
                "strategy_name": "EMA Cross",
                "timeframe": "4h",
                "message": "Signal selected for EUR/USD.",
                "payload": {"confidence": 0.82},
            },
            {
                "timestamp_label": "2026-03-17 10:04:00 UTC",
                "timestamp": now - 120,
                "kind": "bus",
                "symbol": "GBP/USD",
                "event_type": "risk_alert",
                "approved": False,
                "strategy_name": "Trend Following",
                "timeframe": "1h",
                "message": "Risk blocked GBP/USD.",
                "payload": {"approved": False},
            },
        ],
        strategy_assignment_state_for_symbol=lambda symbol: {
            "mode": "single",
            "active_rows": [{"strategy_name": "Trend Following", "timeframe": "1h"}],
            "locked": False,
        },
        latest_agent_decision_overview_for_symbol=lambda symbol: {
            "strategy_name": "EMA Cross" if symbol == "EUR/USD" else "Trend Following",
            "timeframe": "4h" if symbol == "EUR/USD" else "1h",
            "side": "buy",
            "approved": symbol == "EUR/USD",
            "final_agent": "RiskAgent",
            "final_stage": "approved" if symbol == "EUR/USD" else "rejected",
            "reason": "within limits" if symbol == "EUR/USD" else "risk blocked",
        },
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_populate_agent_timeline_filters",
        "_toggle_agent_timeline_pin_symbol",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    tree = window._agent_timeline_tree

    assert tree.topLevelItemCount() == 2
    assert window._agent_timeline_status_filter.findText("Approved") >= 0
    assert window._agent_timeline_status_filter.findText("Rejected") >= 0
    assert window._agent_timeline_timeframe_filter.findText("4h") >= 0
    assert window._agent_timeline_strategy_filter.findText("EMA Cross") >= 0
    assert "Approved: 1" in window._agent_timeline_health_counts.text()
    assert "Rejected: 1" in window._agent_timeline_health_counts.text()
    assert "Changes: 2" in window._agent_timeline_health_recent.text()

    window._agent_timeline_status_filter.setCurrentText("Approved")
    Terminal._refresh_agent_timeline_window(terminal, window)
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(2) == "EUR/USD"

    window._agent_timeline_status_filter.setCurrentIndex(0)
    window._agent_timeline_timeframe_filter.setCurrentText("1h")
    Terminal._refresh_agent_timeline_window(terminal, window)
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(2) == "GBP/USD"

    window._agent_timeline_timeframe_filter.setCurrentIndex(0)
    window._agent_timeline_strategy_filter.setCurrentText("EMA Cross")
    Terminal._refresh_agent_timeline_window(terminal, window)
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(2) == "EUR/USD"

    window._agent_timeline_strategy_filter.setCurrentIndex(0)
    eur_group = tree.topLevelItem(0)
    tree.setCurrentItem(eur_group)
    pinned = Terminal._toggle_agent_timeline_pin_symbol(terminal, window)
    assert pinned == "EUR/USD"
    assert window._agent_timeline_pin_btn.text() == "Unpin EUR/USD"
    assert "Pinned EUR/USD" in window._agent_timeline_summary.text()
    assert "Count: 1" in window._agent_timeline_health_symbols.text()

    unpinned = Terminal._toggle_agent_timeline_pin_symbol(terminal, window)
    assert unpinned == ""
    assert window._agent_timeline_pin_btn.text() == "Pin Selected Symbol"


def test_agent_timeline_anomaly_summary_flags_rejections_stale_and_unfilled_execution():
    _app()
    terminal = _MenuTerminal()
    now = time.time()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:06:00 UTC",
                "timestamp": now - 15,
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_alert",
                "approved": False,
                "message": "Risk blocked EUR/USD.",
            },
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "timestamp": now - 25,
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_alert",
                "approved": False,
                "message": "Risk blocked EUR/USD again.",
            },
            {
                "timestamp_label": "2026-03-17 09:55:00 UTC",
                "timestamp": now - 600,
                "kind": "memory",
                "symbol": "GBP/USD",
                "agent_name": "SignalAgent",
                "stage": "selected",
                "strategy_name": "Trend Following",
                "timeframe": "1h",
                "message": "Signal selected for GBP/USD.",
            },
            {
                "timestamp_label": "2026-03-17 10:04:30 UTC",
                "timestamp": now - 30,
                "kind": "bus",
                "symbol": "USD/JPY",
                "event_type": "execution_plan",
                "decision_id": "dec-42",
                "strategy_name": "EMA Cross",
                "timeframe": "15m",
                "message": "Execution plan ready for USD/JPY.",
            },
        ],
        strategy_assignment_state_for_symbol=lambda symbol: {"mode": "default", "active_rows": [], "locked": False},
        latest_agent_decision_overview_for_symbol=lambda symbol: {},
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_populate_agent_timeline_filters",
        "_toggle_agent_timeline_pin_symbol",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)

    anomaly_text = window._agent_timeline_anomaly_label.text()
    assert "3 symbols flagged" in anomaly_text
    assert "EUR/USD: Repeated risk rejections (2)" in anomaly_text
    assert "GBP/USD: Stale decision flow" in anomaly_text
    assert "USD/JPY: Execution plan without fill" in anomaly_text

    tree = window._agent_timeline_tree
    group = tree.topLevelItem(0)
    tree.setCurrentItem(group)
    Terminal._refresh_agent_timeline_details(terminal, window)
    if group.text(2) == "EUR/USD":
        assert "Anomalies: Repeated risk rejections (2)" in window._agent_timeline_detail_browser.toPlainText()


def test_acknowledge_selected_agent_timeline_anomaly_hides_current_flagged_symbol():
    _app()
    terminal = _MenuTerminal()
    now = time.time()
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:06:00 UTC",
                "timestamp": now - 15,
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_alert",
                "approved": False,
                "message": "Risk blocked EUR/USD.",
            },
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "timestamp": now - 25,
                "kind": "bus",
                "symbol": "EUR/USD",
                "event_type": "risk_alert",
                "approved": False,
                "message": "Risk blocked EUR/USD again.",
            },
        ],
        strategy_assignment_state_for_symbol=lambda symbol: {"mode": "default", "active_rows": [], "locked": False},
        latest_agent_decision_overview_for_symbol=lambda symbol: {},
    )
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_populate_agent_timeline_filters",
        "_toggle_agent_timeline_pin_symbol",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    tree = window._agent_timeline_tree
    tree.setCurrentItem(tree.topLevelItem(0))

    acknowledged = Terminal._acknowledge_selected_agent_timeline_anomaly(terminal, window)

    assert acknowledged == "EUR/USD"
    assert window._agent_timeline_anomaly_snapshot["count"] == 0
    assert window._agent_timeline_anomaly_label.text() == "Agent Anomalies\nAll current anomalies are acknowledged."


def test_refresh_selected_agent_timeline_symbol_opens_chart_and_requests_refresh():
    _app()
    terminal = _MenuTerminal()
    now = time.time()
    calls = []
    terminal.controller = SimpleNamespace(
        language_code="en",
        set_language=lambda _code: None,
        symbols=[],
        live_agent_runtime_feed=lambda limit=200, symbol=None, kinds=None: [
            {
                "timestamp_label": "2026-03-17 10:05:00 UTC",
                "timestamp": now - 10,
                "kind": "memory",
                "symbol": "USD/JPY",
                "agent_name": "SignalAgent",
                "stage": "selected",
                "strategy_name": "EMA Cross",
                "timeframe": "15m",
                "message": "Signal selected for USD/JPY.",
            }
        ],
        strategy_assignment_state_for_symbol=lambda symbol: {"mode": "default", "active_rows": [], "locked": False},
        latest_agent_decision_overview_for_symbol=lambda symbol: {},
    )
    terminal._open_symbol_chart = lambda symbol, timeframe=None: calls.append(("open", symbol, timeframe))
    terminal._refresh_active_chart_data = lambda: calls.append(("chart",))
    terminal._refresh_active_orderbook = lambda: calls.append(("orderbook",))
    _bind(
        terminal,
        "_get_or_create_tool_window",
        "_is_qt_object_alive",
        "_selected_agent_timeline_symbol",
        "_selected_agent_timeline_row",
        "_agent_timeline_row_status_label",
        "_populate_agent_timeline_filters",
        "_toggle_agent_timeline_pin_symbol",
        "_agent_timeline_health_snapshot",
        "_refresh_agent_timeline_health",
        "_agent_timeline_anomaly_snapshot",
        "_agent_timeline_anomaly_fingerprint",
        "_visible_agent_timeline_anomaly_snapshot",
        "_refresh_agent_timeline_anomalies",
        "_agent_timeline_assignment_text",
        "_agent_timeline_recommendation_text",
        "_refresh_agent_timeline_window",
        "_refresh_agent_timeline_details",
        "_replay_selected_agent_timeline_symbol",
        "_open_selected_agent_timeline_symbol_in_strategy_assigner",
        "_refresh_selected_agent_timeline_symbol",
        "_acknowledge_selected_agent_timeline_anomaly",
        "_open_agent_timeline",
    )

    window = Terminal._open_agent_timeline(terminal)
    tree = window._agent_timeline_tree
    tree.setCurrentItem(tree.topLevelItem(0).child(0))

    refreshed = Terminal._refresh_selected_agent_timeline_symbol(terminal, window)

    assert refreshed == "USD/JPY"
    assert calls == [("open", "USD/JPY", "15m"), ("chart",), ("orderbook",)]


def test_chart_context_action_supports_market_ticket_prefill():
    captured = {}
    fake = SimpleNamespace(
        _current_chart_symbol=lambda: "BTC/USDT",
        _open_manual_trade=lambda prefill=None: captured.setdefault("prefill", dict(prefill or {})),
    )

    Terminal._handle_chart_trade_context_action(
        fake,
        {"action": "buy_market_ticket", "symbol": "BTC/USDT", "timeframe": "1h", "price": 100.0},
    )

    assert captured["prefill"]["symbol"] == "BTC/USDT"
    assert captured["prefill"]["side"] == "buy"
    assert captured["prefill"]["order_type"] == "market"


def test_request_chart_data_for_widget_marks_empty_broker_history_on_chart():
    _app()
    terminal = _ChartRequestTerminal(None)
    _bind(
        terminal,
        "_register_chart_request_token",
        "_is_chart_request_current",
        "_request_chart_data_for_widget",
        "_update_chart",
    )

    result = asyncio.run(Terminal._request_chart_data_for_widget(terminal, terminal.chart, limit=240))

    assert result is None
    assert terminal.chart._chart_status_mode == "error"
    assert terminal.chart._chart_status_message == "No data received."


def test_request_chart_data_for_widget_retargets_coinbase_derivative_symbol():
    _app()
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000 + (index * 3600) for index in range(5)],
            "open": [100.0 + index for index in range(5)],
            "high": [101.0 + index for index in range(5)],
            "low": [99.0 + index for index in range(5)],
            "close": [100.4 + index for index in range(5)],
            "volume": [1000.0 + (index * 20.0) for index in range(5)],
        }
    )
    terminal = _ChartRequestTerminal(frame)
    terminal.controller = _DerivativeChartRequestController(frame)
    terminal.chart.controller = terminal.controller
    terminal.chart.symbol = "BTC/USD"
    terminal._active_chart_widget_ref = terminal.chart
    terminal.symbol_picker = QComboBox()
    terminal.symbol_picker.addItem("BTC/USD")
    terminal.symbol_picker.setCurrentText("BTC/USD")
    _bind(
        terminal,
        "_register_chart_request_token",
        "_is_chart_request_current",
        "_request_chart_data_for_widget",
        "_update_chart",
        "_retarget_chart_widget_symbol",
    )

    result = asyncio.run(Terminal._request_chart_data_for_widget(terminal, terminal.chart, limit=240))

    assert result is not None
    assert terminal.controller.requested_symbols == ["BTC/USD:USD"]
    assert terminal.chart.symbol == "BTC/USD:USD"
    assert terminal.symbol_picker.currentText() == "BTC/USD:USD"


def test_request_chart_data_for_widget_marks_limited_history_after_loading():
    _app()
    frame = pd.DataFrame(
        {
            "timestamp": [1700000000 + (index * 3600) for index in range(60)],
            "open": [100.0 + index for index in range(60)],
            "high": [101.0 + index for index in range(60)],
            "low": [99.0 + index for index in range(60)],
            "close": [100.4 + index for index in range(60)],
            "volume": [1000.0 + (index * 20.0) for index in range(60)],
        }
    )
    terminal = _ChartRequestTerminal(frame)
    _bind(
        terminal,
        "_register_chart_request_token",
        "_is_chart_request_current",
        "_request_chart_data_for_widget",
        "_update_chart",
    )

    result = asyncio.run(Terminal._request_chart_data_for_widget(terminal, terminal.chart, limit=240))

    assert result is not None
    assert terminal.chart._chart_status_mode == "notice"
    assert terminal.chart._chart_status_message == "Loaded 60 / 240 candles."
    assert terminal.chart._last_df is not None
    assert len(terminal.chart._last_df.index) == 60


def test_update_symbols_retargets_coinbase_derivative_charts():
    _app()
    chart = ChartWidget("BTC/USD", "1h", SimpleNamespace(broker=None))
    refreshed = []
    symbol_picker = QComboBox()
    symbol_picker.addItem("BTC/USD")
    symbol_picker.setCurrentText("BTC/USD")
    fake = SimpleNamespace(
        controller=SimpleNamespace(
            _resolve_preferred_market_symbol=lambda symbol, preference=None: "BTC/USD:USD" if str(symbol).upper() == "BTC/USD" else str(symbol).upper()
        ),
        symbols_table=QTableWidget(),
        symbol_picker=symbol_picker,
        chart=chart,
        symbol="BTC/USD",
        current_timeframe="1h",
        _active_chart_widget_ref=chart,
        _configure_market_watch_table=lambda: None,
        _set_market_watch_row=lambda row, symbol, bid="-", ask="-", status="", usd_value="-": None,
        _reorder_market_watch_rows=lambda: None,
        _all_chart_widgets=lambda: [chart],
        _schedule_chart_data_refresh=lambda chart_ref: refreshed.append(chart_ref.symbol),
        _is_qt_object_alive=lambda obj: obj is not None,
        _chart_tabs_ready=lambda: False,
        _refresh_symbol_picker_favorites=lambda: None,
        _update_favorite_action_text=lambda: None,
    )
    _bind(fake, "_retarget_chart_widget_symbol")

    Terminal._update_symbols(fake, "coinbase", ["BTC/USD:USD"])

    assert chart.symbol == "BTC/USD:USD"
    assert symbol_picker.currentText() == "BTC/USD:USD"
    assert refreshed == ["BTC/USD:USD"]


def test_request_active_orderbook_uses_controller_task_scheduler():
    _app()
    scheduled = []

    async def _request_orderbook(*, symbol, limit=20):
        return {"symbol": symbol, "limit": limit}

    async def _request_recent_trades(*, symbol, limit=40):
        return [{"symbol": symbol, "limit": limit}]

    def _create_task(coro, name):
        scheduled.append(name)
        coro.close()
        return None

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(
            request_orderbook=_request_orderbook,
            request_recent_trades=_request_recent_trades,
            _create_task=_create_task,
        ),
        logger=SimpleNamespace(debug=lambda *args, **kwargs: None),
        _current_chart_symbol=lambda: "BTC/USDT",
    )
    _bind(fake, "_defer_controller_coroutine", "_request_active_orderbook")

    Terminal._request_active_orderbook(fake)

    assert scheduled == ["request_orderbook:BTC/USDT", "request_recent_trades:BTC/USDT"]
