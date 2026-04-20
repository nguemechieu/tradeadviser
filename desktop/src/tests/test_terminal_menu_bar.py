import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QEvent, QRect
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeTerminal(QMainWindow):
    def __init__(self, exchange_name=""):
        super().__init__()
        broker = SimpleNamespace(exchange_name=exchange_name) if exchange_name else None
        self.controller = SimpleNamespace(language_code="en", set_language=lambda _code: None, broker=broker, config=None)
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
        self.detached_tool_windows = {}

    def _tr(self, key, **kwargs):
        return key

    def apply_language(self):
        return Terminal.apply_language(self)

    def _active_exchange_name(self):
        return Terminal._active_exchange_name(self)

    def _is_qt_object_alive(self, obj):
        return Terminal._is_qt_object_alive(self, obj)

    def _sync_chart_timeframe_menu_actions(self):
        return Terminal._sync_chart_timeframe_menu_actions(self)

    def _update_autotrade_button(self):
        return None

    def _set_active_timeframe_button(self, _timeframe):
        return None

    def __getattr__(self, name):
        if name.startswith("_"):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class _ToolbarTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = SimpleNamespace(
            language_code="en",
            set_language=lambda _code: None,
            symbols=["BTC/USDT", "ETH/USDT"],
            broker=SimpleNamespace(exchange_name="binance"),
            config=None,
            is_live_mode=lambda: False,
            current_account_label=lambda: "Paper Desk",
            is_emergency_stop_active=lambda: False,
            telegram_enabled=False,
            trade_close_notifications_enabled=False,
            trade_close_notify_telegram=False,
            trade_close_notify_email=False,
            trade_close_notify_sms=False,
            openai_model="gpt-5-mini",
            news_enabled=False,
        )
        self.symbol = "BTC/USDT"
        self.current_timeframe = "1h"
        self.bound_session_id = ""
        self.bound_session_label = ""
        self.timeframe_buttons = {}
        self.toolbar = None
        self.toolbar_timeframe_label = None
        self.secondary_toolbar = None
        self.autotrading_enabled = False
        self.autotrade_scope_value = "all"
        self.connection_indicator = QLabel("CONNECTED")
        self.heartbeat = QLabel("●")
        self.symbol_label = None
        self.open_symbol_button = None
        self.screenshot_button = None
        self.session_mode_badge = None
        self.license_badge = None
        self.live_trading_bar_frame = None
        self.live_trading_bar_label = None
        self.live_trading_bar = None
        self.desk_status_frame = None
        self.desk_status_title_label = None
        self.desk_status_primary_label = None
        self.desk_status_secondary_label = None
        self.kill_switch_button = None
        self.trading_activity_label = None
        self.symbol_picker = None
        self.autotrade_scope_picker = None
        self.autotrade_scope_label_widget = None
        self.autotrade_controls_box = None
        self.autotrade_controls_layout = None
        self.autotrade_controls_row = None
        self.auto_button = None

    def _tr(self, key, **kwargs):
        return key

    def _action_button_style(self):
        return ""

    def _danger_button_style(self):
        return ""

    def _toggle_emergency_stop(self):
        return None

    def _open_symbol_from_picker(self):
        return None

    def _change_autotrade_scope(self, *_args, **_kwargs):
        return None

    def _toggle_autotrading(self):
        return None

    def _apply_autotrade_scope(self, *_args, **_kwargs):
        return None

    def _update_autotrade_button(self):
        return None

    def _update_session_badge(self):
        return None

    def _update_live_trading_bar(self):
        return None

    def _update_desk_status_panel(self):
        return Terminal._update_desk_status_panel(self)

    def _update_kill_switch_button(self):
        return None

    def _active_exchange_name(self):
        return Terminal._active_exchange_name(self)

    def _autotrade_scope_label(self):
        return Terminal._autotrade_scope_label(self)

    def _set_active_timeframe_button(self, _timeframe):
        return None

    def take_screen_shot(self):
        return None


class _EventTerminal(Terminal):
    def __init__(self, controller):
        QMainWindow.__init__(self)
        self.controller = controller
        self.bound_session_id = "session-b"
        self.bound_session_label = "Session B"


class _SetupCoreTerminal(Terminal):
    def __init__(self):
        QMainWindow.__init__(self)
        self.controller = SimpleNamespace(order_type="market")
        self.bound_session_id = ""
        self.bound_session_label = ""


def test_create_menu_bar_groups_actions_into_single_clear_menus():
    _app()
    terminal = _FakeTerminal()

    Terminal._create_menu_bar(terminal)

    menu_titles = [action.text() for action in terminal.menuBar().actions()]

    file_actions = terminal.file_menu.actions()
    chart_actions = terminal.charts_menu.actions()
    chart_style_actions = terminal.chart_style_menu.actions()
    chart_study_actions = terminal.chart_studies_menu.actions()
    strategy_actions = terminal.strategy_menu.actions()
    backtest_actions = terminal.backtest_menu.actions()
    risk_actions = terminal.risk_menu.actions()
    analyze_positions_actions = terminal.analyze_positions_menu.actions()
    analyze_trade_actions = terminal.analyze_trade_review_menu.actions()
    analyze_desk_actions = terminal.analyze_desk_menu.actions()
    review_actions = terminal.review_menu.actions()
    research_actions = terminal.research_menu.actions()
    education_actions = terminal.education_menu.actions()
    tools_actions = terminal.tools_menu.actions()
    settings_actions = terminal.settings_menu.actions()

    assert terminal.settings_menu.menuAction() not in file_actions
    assert terminal.action_exit in file_actions
    assert terminal.action_generate_report not in file_actions
    assert terminal.action_export_trades not in file_actions
    assert terminal.settings_menu.title() in menu_titles

    assert terminal.action_app_settings in settings_actions
    assert terminal.language_menu.menuAction() in settings_actions

    assert terminal.backtest_menu.menuAction() in strategy_actions
    assert terminal.action_strategy_assigner in strategy_actions
    assert terminal.action_strategy_scorecard in strategy_actions
    assert terminal.action_strategy_debug in strategy_actions
    assert terminal.action_run_backtest in backtest_actions
    assert terminal.action_strategy_optimization in backtest_actions

    assert terminal.chart_timeframe_menu.menuAction() in chart_actions
    assert terminal.chart_style_menu.menuAction() in chart_actions
    assert terminal.chart_studies_menu.menuAction() in chart_actions
    assert terminal.action_chart_settings in chart_style_actions
    assert terminal.action_candle_colors in chart_style_actions
    assert terminal.action_edit_studies in chart_study_actions
    assert terminal.action_add_indicator in chart_study_actions
    assert terminal.action_remove_indicator in chart_study_actions
    assert terminal.action_remove_all_indicators in chart_study_actions
    assert terminal.chart_timeframe_actions["1h"].isChecked() is True

    assert terminal.analyze_positions_menu.menuAction() in risk_actions
    assert terminal.analyze_trade_review_menu.menuAction() in risk_actions
    assert terminal.analyze_desk_menu.menuAction() in risk_actions
    assert terminal.action_risk_settings in analyze_positions_actions
    assert terminal.action_portfolio_view in analyze_positions_actions
    assert terminal.action_position_analysis in analyze_positions_actions
    assert terminal.action_trade_checklist in analyze_trade_actions
    assert terminal.action_closed_journal in analyze_trade_actions
    assert terminal.action_journal_review in analyze_trade_actions
    assert terminal.action_system_health in analyze_desk_actions
    assert terminal.action_quant_pm in analyze_desk_actions
    assert terminal.action_kill_switch not in risk_actions

    assert terminal.action_performance in review_actions
    assert terminal.action_recommendations in review_actions
    assert terminal.action_closed_journal in review_actions
    assert terminal.action_journal_review in review_actions
    assert terminal.action_generate_report in review_actions
    assert terminal.action_export_trades in review_actions

    assert terminal.action_market_chat in research_actions
    assert terminal.action_quant_pm in research_actions
    assert terminal.action_ml_monitor in research_actions
    assert terminal.action_ml_research in research_actions
    assert terminal.action_stellar_asset_explorer in research_actions
    assert terminal.action_recommendations not in research_actions
    assert terminal.action_strategy_optimization not in research_actions
    assert terminal.action_strategy_assigner not in research_actions
    assert terminal.action_run_backtest not in research_actions

    assert terminal.education_menu.title() in menu_titles
    assert terminal.action_trader_tv in education_actions
    assert terminal.action_education_center in education_actions
    assert terminal.action_documentation in education_actions
    assert terminal.action_api_docs in education_actions
    assert terminal.action_market_chat not in education_actions

    assert terminal.action_logs in tools_actions
    assert terminal.action_export_diagnostics in tools_actions
    assert terminal.action_system_console in tools_actions
    assert terminal.action_system_status in tools_actions
    assert terminal.action_market_chat not in tools_actions
    assert terminal.action_performance not in tools_actions
    assert menu_titles[-1] == terminal.help_menu.title()


def test_event_activates_bound_session_on_window_activate():
    _app()
    activations = []
    controller = SimpleNamespace(
        active_session_id="session-a",
        terminal=None,
        request_session_activation=lambda session_id: activations.append(session_id),
    )
    terminal = _EventTerminal(controller)

    handled = terminal.event(QEvent(QEvent.Type.WindowActivate))

    assert handled is True
    assert controller.terminal is terminal
    assert activations == ["session-b"]


def test_setup_core_initializes_terminal_state_before_ui_build():
    _app()
    terminal = _SetupCoreTerminal()

    terminal._setup_core()

    assert terminal.current_connection_status == "connecting"
    assert terminal.trade_log_dock is None
    assert terminal.session_selector is None
    assert terminal.detached_tool_windows == {}
    assert terminal.language_actions == {}


def test_create_menu_bar_hides_stellar_explorer_when_exchange_is_not_stellar():
    _app()
    terminal = _FakeTerminal(exchange_name="coinbase")

    Terminal._create_menu_bar(terminal)

    assert terminal.action_stellar_asset_explorer.isVisible() is False
    assert terminal._research_stellar_separator_action.isVisible() is False


def test_create_menu_bar_shows_stellar_explorer_when_exchange_is_stellar():
    _app()
    terminal = _FakeTerminal(exchange_name="stellar")

    Terminal._create_menu_bar(terminal)

    assert terminal.action_stellar_asset_explorer.isVisible() is True
    assert terminal._research_stellar_separator_action.isVisible() is True


def test_learning_windows_use_market_snapshot_in_text_payload():
    captured = []
    fake = SimpleNamespace(
        controller=SimpleNamespace(
            symbols=["ES", "NQ"],
            news_enabled=False,
            broker=SimpleNamespace(exchange_name="schwab"),
        ),
        current_timeframe="15m",
        current_connection_status="connected",
        autotrading_enabled=True,
        symbol="ES",
        _current_chart_symbol=lambda: "ES",
        _active_exchange_name=lambda: "schwab",
    )
    fake._learning_market_snapshot = lambda: Terminal._learning_market_snapshot(fake)
    fake._trader_tv_html = lambda: Terminal._trader_tv_html(fake)
    fake._trader_tv_symbol = lambda snapshot=None: Terminal._trader_tv_symbol(fake, snapshot)
    fake._trader_tv_chart_url = lambda snapshot=None: Terminal._trader_tv_chart_url(fake, snapshot)
    fake._trader_tv_video_url = lambda snapshot=None: Terminal._trader_tv_video_url(fake, snapshot)
    fake._trader_tv_browser_fallback_html = lambda title, description, primary_label, primary_url, secondary_label=None, secondary_url=None: (
        Terminal._trader_tv_browser_fallback_html(
            fake,
            title,
            description,
            primary_label,
            primary_url,
            secondary_label,
            secondary_url,
        )
    )
    fake._education_center_html = lambda: Terminal._education_center_html(fake)
    fake._open_text_window = lambda key, title, markup, width=0, height=0: captured.append(
        {"key": key, "title": title, "html": markup, "width": width, "height": height}
    )

    trader_tv_html = Terminal._trader_tv_html(fake)
    snapshot = Terminal._learning_market_snapshot(fake)
    Terminal._open_education_center_window(fake)

    assert snapshot["focus_symbol"] == "ES"
    assert snapshot["exchange"] == "SCHWAB"
    assert "Current Desk Snapshot" in trader_tv_html
    assert "Live feed off" in trader_tv_html
    assert Terminal._trader_tv_symbol(fake, snapshot) == "CME_MINI:ES1!"
    assert "tradingview.com/chart/?symbol=CME_MINI%3AES1%21" in Terminal._trader_tv_chart_url(fake, snapshot)
    assert "youtube.com/results?search_query=ES+SCHWAB+market+analysis+live+trading" in Terminal._trader_tv_video_url(fake, snapshot)
    assert "Launch TradingView chart" in Terminal._trader_tv_browser_fallback_html(
        fake,
        "TradingView Panel",
        "Fallback",
        "Launch TradingView chart",
        Terminal._trader_tv_chart_url(fake, snapshot),
        "Open YouTube market feed",
        Terminal._trader_tv_video_url(fake, snapshot),
    )

    assert captured[0]["key"] == "education_center"
    assert captured[0]["title"] == "Education Center"
    assert captured[0]["width"] == 940
    assert "Practice Loop Inside This App" in captured[0]["html"]
    assert "Ready-For-Live Checklist" in captured[0]["html"]


def test_create_toolbar_keeps_symbol_and_screenshot_on_same_row_and_drops_toolbar_timeframes():
    _app()
    terminal = _ToolbarTerminal()

    Terminal._create_toolbar(terminal)

    main_toolbar_widgets = [terminal.toolbar.widgetForAction(action) for action in terminal.toolbar.actions()]
    controls_toolbar_widgets = [
        terminal.secondary_toolbar.widgetForAction(action) for action in terminal.secondary_toolbar.actions()
    ]

    assert terminal.toolbar_timeframe_label is None
    assert terminal.timeframe_buttons == {}
    assert any(widget is not None and widget.isAncestorOf(terminal.symbol_picker) for widget in main_toolbar_widgets)
    assert any(widget is not None and widget.isAncestorOf(terminal.screenshot_button) for widget in main_toolbar_widgets)
    assert not any(
        widget is not None and widget.isAncestorOf(terminal.screenshot_button)
        for widget in controls_toolbar_widgets
    )
    assert terminal.desk_status_frame is not None
    assert terminal.desk_status_title_label.text() == "DESK STATUS"
    assert "PAPER BINANCE" in terminal.desk_status_primary_label.text()
    assert "Paper Desk" in terminal.desk_status_primary_label.text()
    assert "AI idle on All Symbols" in terminal.desk_status_secondary_label.text()


def test_create_toolbar_adds_professional_desk_status_summary():
    _app()
    terminal = _ToolbarTerminal()
    terminal.bound_session_label = "Desk Alpha"
    terminal.controller.is_live_mode = lambda: True
    terminal.controller.current_account_label = lambda: "Primary Futures"
    terminal.controller.trade_close_notifications_enabled = True
    terminal.controller.trade_close_notify_telegram = True
    terminal.controller.trade_close_notify_email = True
    terminal.controller.news_enabled = True
    terminal.controller.openai_model = "gpt-5.4-mini"

    Terminal._create_toolbar(terminal)

    assert terminal.desk_status_title_label.text() == "DESK STATUS"
    assert "Desk Alpha" in terminal.desk_status_primary_label.text()
    assert "LIVE BINANCE" in terminal.desk_status_primary_label.text()
    assert "Alerts: Telegram, Email" in terminal.desk_status_secondary_label.text()
    assert "News on" in terminal.desk_status_secondary_label.text()
    assert "Model gpt-5.4-mini" in terminal.desk_status_secondary_label.text()


def test_update_desk_status_panel_reflects_live_execution_and_kill_switch():
    _app()
    terminal = _ToolbarTerminal()
    terminal.controller.is_live_mode = lambda: True
    terminal.controller.is_emergency_stop_active = lambda: True
    terminal.controller.trade_close_notifications_enabled = True
    terminal.controller.trade_close_notify_sms = True
    terminal.autotrading_enabled = True

    Terminal._create_toolbar(terminal)
    Terminal._update_desk_status_panel(terminal)

    assert terminal.desk_status_title_label.text() == "DESK LOCKDOWN"
    assert "LIVE BINANCE" in terminal.desk_status_primary_label.text()
    assert "AI live on All Symbols" in terminal.desk_status_secondary_label.text()
    assert "Kill switch on" in terminal.desk_status_secondary_label.text()
    assert "Alerts: SMS" in terminal.desk_status_secondary_label.text()


def test_apply_workspace_tab_chrome_sets_professional_tab_shell():
    _app()
    terminal = _ToolbarTerminal()
    tabs = QTabWidget()

    Terminal._apply_workspace_tab_chrome(terminal, tabs)

    assert tabs.documentMode() is True
    assert "QTabWidget::pane" in tabs.styleSheet()
    assert "QTabBar::tab:selected" in tabs.styleSheet()


def test_empty_state_html_promotes_title_message_and_hint():
    terminal = _ToolbarTerminal()

    markup = Terminal._empty_state_html(
        terminal,
        "Recommendation Detail",
        "Select a symbol to review the rationale.",
        hint="Live confidence and regime context will appear here.",
    )

    assert "Recommendation Detail" in markup
    assert "Select a symbol to review the rationale." in markup
    assert "Live confidence and regime context will appear here." in markup


def test_autotrade_toolbar_compacts_scope_controls_before_hiding_the_picker():
    _app()
    terminal = _ToolbarTerminal()

    Terminal._create_toolbar(terminal)

    Terminal._refresh_autotrade_controls_layout(terminal, available_width=380)

    assert terminal.autotrade_scope_label_widget.isHidden() is True
    assert terminal.autotrade_scope_picker.minimumWidth() == 82
    assert terminal.autotrade_scope_picker.maximumWidth() == 108
    assert terminal.auto_button.minimumWidth() == 92

    Terminal._refresh_autotrade_controls_layout(terminal, available_width=760)

    assert terminal.autotrade_scope_label_widget.isHidden() is False
    assert terminal.autotrade_scope_picker.minimumWidth() == 108
    assert terminal.autotrade_scope_picker.maximumWidth() == 148
    assert terminal.auto_button.minimumWidth() == 148


def test_autotrade_button_text_uses_clear_start_stop_copy():
    terminal = _ToolbarTerminal()

    assert Terminal._autotrade_button_text(terminal, False, mode="full") == "Start Trading"
    assert Terminal._autotrade_button_text(terminal, True, mode="full") == "Stop Trading"
    assert Terminal._autotrade_button_text(terminal, False, mode="tight") == "Start"
    assert Terminal._autotrade_button_text(terminal, True, mode="tight") == "Stop"


def test_fit_window_to_available_screen_bounds_terminal_to_viewport():
    _app()
    terminal = _FakeTerminal()
    terminal.screen = lambda: SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 1280, 720))

    Terminal._fit_window_to_available_screen(terminal, requested_width=1700, requested_height=950)

    assert terminal.minimumWidth() == 960
    assert terminal.minimumHeight() == 640
    assert terminal.width() == 1256
    assert terminal.height() == 696


def test_set_status_value_ignores_deleted_qt_labels():
    terminal = _FakeTerminal()

    class _DeadLabel:
        def setText(self, _value):
            raise AssertionError("deleted label should not be touched")

        def setToolTip(self, _value):
            raise AssertionError("deleted label should not be touched")

    dead_label = _DeadLabel()
    terminal.status_labels = {"Websocket": dead_label}
    terminal._is_qt_object_alive = lambda obj: obj is not dead_label
    terminal._elide_text = lambda value, max_length=42: str(value)

    Terminal._set_status_value(terminal, "Websocket", "Restarting", "Restarting market data")

    assert terminal.status_labels == {}


def test_set_status_value_skips_redundant_label_updates():
    terminal = _FakeTerminal()

    class _Label:
        def __init__(self):
            self.text_calls = 0
            self.tooltip_calls = 0

        def setText(self, _value):
            self.text_calls += 1

        def setToolTip(self, _value):
            self.tooltip_calls += 1

    label = _Label()
    terminal.status_labels = {"Websocket": label}
    terminal._is_qt_object_alive = lambda obj: obj is label
    terminal._elide_text = lambda value, max_length=42: str(value)
    terminal._status_value_cache = {}

    Terminal._set_status_value(terminal, "Websocket", "Running", "Connected")
    Terminal._set_status_value(terminal, "Websocket", "Running", "Connected")

    assert label.text_calls == 1
    assert label.tooltip_calls == 1


def test_refresh_session_selector_skips_rebuilding_identical_sessions():
    class _Selector:
        def __init__(self):
            self.items = []
            self.clear_calls = 0
            self.add_calls = 0
            self._current_index = 0
            self._signals_blocked = False

        def blockSignals(self, value):
            previous = self._signals_blocked
            self._signals_blocked = bool(value)
            return previous

        def clear(self):
            self.clear_calls += 1
            self.items = []

        def addItem(self, text, data):
            self.add_calls += 1
            self.items.append((text, data))

        def setCurrentIndex(self, index):
            self._current_index = int(index)

        def currentIndex(self):
            return self._current_index

        def count(self):
            return len(self.items)

    selector = _Selector()
    sessions = [
        {"session_id": "sess-1", "label": "Primary", "status": "running"},
        {"session_id": "sess-2", "label": "Backup", "status": "paused"},
    ]
    fake = SimpleNamespace(
        session_selector=selector,
        controller=SimpleNamespace(
            list_trading_sessions=lambda: list(sessions),
            active_session_id="sess-1",
        ),
        _session_selector_signature=None,
    )

    Terminal._refresh_session_selector(fake)
    Terminal._refresh_session_selector(fake)

    assert selector.clear_calls == 1
    assert selector.add_calls == 2
    assert selector.items[0] == ("Primary [RUNNING]", "sess-1")


def test_refresh_session_tabs_skips_rebuilding_identical_sessions():
    _app()

    class _Tabs:
        def __init__(self):
            self._tabs = []
            self.add_calls = 0
            self.remove_calls = 0
            self._current_index = 0

        def count(self):
            return len(self._tabs)

        def widget(self, index):
            return self._tabs[index][0]

        def removeTab(self, index):
            self.remove_calls += 1
            self._tabs.pop(index)

        def addTab(self, widget, label):
            self.add_calls += 1
            self._tabs.append((widget, label))

        def setCurrentIndex(self, index):
            self._current_index = int(index)

        def currentIndex(self):
            return self._current_index

    tabs = _Tabs()
    sessions = [
        {
            "session_id": "sess-1",
            "label": "Primary",
            "status": "running",
            "mode": "paper",
            "equity": 10100.0,
            "drawdown_pct": 0.02,
            "gross_exposure": 3500.0,
            "symbols_count": 12,
            "positions_count": 2,
            "open_orders_count": 1,
            "trade_count": 8,
            "strategy": "Trend Following",
        }
    ]
    fake = SimpleNamespace(
        session_tabs_widget=tabs,
        controller=SimpleNamespace(
            list_trading_sessions=lambda: list(sessions),
            aggregate_session_portfolio=lambda: {
                "session_count": 1,
                "running_sessions": 1,
                "risk_blocked_sessions": 0,
                "total_equity": 10100.0,
                "total_gross_exposure": 3500.0,
                "total_unrealized_pnl": 125.0,
            },
            active_session_id="sess-1",
        ),
        _session_tabs_signature=None,
    )

    Terminal._refresh_session_tabs(fake)
    Terminal._refresh_session_tabs(fake)

    assert tabs.add_calls == 2
    assert tabs.remove_calls == 0
    assert tabs.currentIndex() == 1
