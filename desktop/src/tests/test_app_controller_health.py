import asyncio
import logging
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController
from frontend.ui.terminal import Terminal
from broker.paper_broker import PaperBroker


class _CleanupTask:
    def __init__(self, sink, name):
        self._sink = sink
        self._name = name
        self._done = False

    def done(self):
        return self._done

    def cancel(self):
        self._done = True
        self._sink.append(self._name)


class _ExecutorRecorder:
    def __init__(self, sink):
        self._sink = sink

    def shutdown(self, wait=False, cancel_futures=True):
        self._sink.append((bool(wait), bool(cancel_futures)))


class _FakeTerminal:
    def __init__(self, calls):
        self.detached_tool_windows = {}
        self._calls = calls
        self._ui_shutting_down = False
        self.logout_requested = SimpleNamespace(connect=lambda handler: self._calls["terminal"].append(("logout_connect", handler)))

    def _disconnect_controller_signals(self):
        self._calls["terminal"].append("disconnect")

    def show(self):
        self._calls["terminal"].append("show")

    def showNormal(self):
        self._calls["terminal"].append("show_normal")

    def raise_(self):
        self._calls["terminal"].append("raise")

    def activateWindow(self):
        self._calls["terminal"].append("activate")

    def close(self):
        self._calls["terminal"].append("close")

    def deleteLater(self):
        self._calls["terminal"].append("delete")


class _FakeTradingSystem:
    def __init__(self, calls):
        self._calls = calls
        self._signal_selection_executor = _ExecutorRecorder(self._calls["signal_shutdown"])

    async def stop(self, wait_for_background_workers=False):
        self._calls["trading_stop"].append(bool(wait_for_background_workers))
        self._shutdown_signal_selection_executor(wait=wait_for_background_workers)

    def _shutdown_signal_selection_executor(self, wait=False):
        executor = getattr(self, "_signal_selection_executor", None)
        if executor is None:
            return
        self._signal_selection_executor = None
        executor.shutdown(wait=wait, cancel_futures=True)


def _make_cleanup_controller(*, telegram_error=None):
    calls = {
        "telegram": [],
        "news": [],
        "cancelled": [],
        "ranking_shutdown": [],
        "signal_shutdown": [],
        "trading_stop": [],
        "progress": [],
        "terminal": [],
        "stack_removed": [],
        "broker": [],
        "emitted": [],
    }
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.shutdown")
    controller.connected = True
    controller.connection_signal = SimpleNamespace(
        emit=lambda state: calls["emitted"].append(state)
    )

    async def stop_telegram_service():
        calls["telegram"].append("stop")
        if telegram_error is not None:
            raise telegram_error

    async def close_news_service():
        calls["news"].append("close")

    async def close_broker():
        calls["broker"].append("close")

    controller._stop_telegram_service = stop_telegram_service
    controller.news_service = SimpleNamespace(close=close_news_service)
    controller._news_cache = {"cached": 1}
    controller._news_inflight = {"inflight": 1}
    controller._strategy_auto_assignment_task = _CleanupTask(calls["cancelled"], "auto")
    controller._strategy_auto_assignment_deferred_task = _CleanupTask(calls["cancelled"], "deferred")
    controller._strategy_ranking_executor = _ExecutorRecorder(calls["ranking_shutdown"])
    controller._terminal_runtime_restore_task = _CleanupTask(calls["cancelled"], "restore")
    controller.strategy_auto_assignment_enabled = True
    controller.time_frame = "1h"
    controller._update_strategy_auto_assignment_progress = lambda **changes: calls["progress"].append(changes)
    controller._ticker_task = _CleanupTask(calls["cancelled"], "ticker")
    controller._ws_task = _CleanupTask(calls["cancelled"], "ws")
    controller._ws_bus_task = _CleanupTask(calls["cancelled"], "ws_bus")
    controller.ws_bus = object()
    controller.ws_manager = object()
    controller.trading_system = _FakeTradingSystem(calls)
    controller.behavior_guard = object()
    controller._live_agent_decision_events = {"live": 1}
    controller._live_agent_runtime_feed = ["event"]
    controller.terminal = _FakeTerminal(calls)
    controller.stack = SimpleNamespace(removeWidget=lambda widget: calls["stack_removed"].append(widget))
    controller.broker = SimpleNamespace(close=close_broker)
    return controller, calls


def test_run_startup_health_check_pushes_notification_once_for_same_result():
    notifications = []
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.health")
    controller.symbols = ["BTC/USDT"]
    controller.time_frame = "1h"
    controller.health_check_report = []
    controller.health_check_summary = "Not run"
    controller._startup_health_notification_signature = None
    controller.terminal = SimpleNamespace(
        _push_notification=lambda *args, **kwargs: notifications.append((args, kwargs))
    )

    async def fetch_status():
        return {"broker": "paper", "status": "ok"}

    async def fetch_orderbook(_symbol, limit=10):
        return {"bids": [[1.0, 1.0]], "asks": [[1.1, 1.0]]}

    async def fetch_positions():
        return []

    async def fetch_open_orders(symbol=None, limit=10):
        return []

    async def fetch_ohlcv(symbol, timeframe="1h", limit=50):
        return [[1, 1, 1, 1, 1, 1]]

    controller.broker = SimpleNamespace(
        fetch_status=fetch_status,
        fetch_ohlcv=fetch_ohlcv,
        fetch_orderbook=fetch_orderbook,
        fetch_positions=fetch_positions,
        fetch_open_orders=fetch_open_orders,
    )
    controller.get_broker_capabilities = lambda: {
        "connectivity": True,
        "ticker": True,
        "candles": True,
        "orderbook": True,
        "open_orders": True,
        "positions": True,
        "trading": True,
        "order_tracking": True,
    }
    controller._broker_is_connected = lambda broker=None: True

    async def fetch_balances(_broker=None):
        return {"free": {"USD": 1000.0}}

    async def fetch_ticker(symbol):
        return {"symbol": symbol, "last": 100.0}

    controller._fetch_balances = fetch_balances
    controller._safe_fetch_ticker = fetch_ticker

    asyncio.run(controller.run_startup_health_check())
    asyncio.run(controller.run_startup_health_check())

    assert "pass" in controller.health_check_summary
    assert len(notifications) == 1
    assert notifications[0][0][0] == "Startup health check"


def test_shutdown_for_exit_waits_for_background_workers():
    controller, calls = _make_cleanup_controller()

    asyncio.run(controller.shutdown_for_exit())

    assert calls["ranking_shutdown"] == [(True, True)]
    assert calls["trading_stop"] == [True]
    assert calls["signal_shutdown"] == [(True, True)]
    assert calls["broker"] == ["close"]
    assert calls["emitted"] == ["disconnected"]
    assert calls["terminal"] == ["disconnect", "delete"]
    assert len(calls["stack_removed"]) == 1


def test_cleanup_session_continues_after_step_failure():
    controller, calls = _make_cleanup_controller(telegram_error=RuntimeError("boom"))

    asyncio.run(controller._cleanup_session(stop_trading=True, close_broker=True))

    assert calls["telegram"] == ["stop"]
    assert calls["news"] == ["close"]
    assert calls["ranking_shutdown"] == [(False, True)]
    assert calls["trading_stop"] == [False]
    assert calls["signal_shutdown"] == [(False, True)]
    assert calls["broker"] == ["close"]
    assert calls["terminal"] == ["disconnect", "delete"]
    assert len(calls["stack_removed"]) == 1
    assert controller.trading_system is None
    assert controller.terminal is None
    assert controller.broker is None
    assert controller.ws_bus is None
    assert controller.ws_manager is None


def test_terminal_disconnect_controller_signals_uses_tracked_wrappers():
    class _SignalRecorder:
        def __init__(self):
            self.disconnected = []

        def disconnect(self, slot):
            self.disconnected.append(slot)

    terminal = Terminal.__new__(Terminal)
    signal_a = _SignalRecorder()
    signal_b = _SignalRecorder()
    wrapped_a = object()
    wrapped_b = object()
    terminal._controller_signal_bindings = [(signal_a, wrapped_a), (signal_b, wrapped_b)]

    Terminal._disconnect_controller_signals(terminal)

    assert signal_a.disconnected == [wrapped_a]
    assert signal_b.disconnected == [wrapped_b]
    assert terminal._controller_signal_bindings == []


def test_terminal_safe_disconnect_suppresses_runtime_warnings():
    class _WarningSignal:
        def disconnect(self, _slot):
            warnings.warn(
                "Failed to disconnect (<bound method example>) from signal \"symbols_signal(QString,QVariantList)\".",
                RuntimeWarning,
                stacklevel=2,
            )

    terminal = Terminal.__new__(Terminal)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert Terminal._safe_disconnect(terminal, _WarningSignal(), object()) is True

    assert caught == []


def test_remove_app_event_filter_is_idempotent():
    removed = []
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.event_filter")
    controller._app_event_filter_target = SimpleNamespace(
        removeEventFilter=lambda target: removed.append(target)
    )
    controller._event_filter_disabled = False

    AppController._remove_app_event_filter(controller)
    AppController._remove_app_event_filter(controller)

    assert removed == [controller]
    assert controller._app_event_filter_target is None
    assert controller._event_filter_disabled is True


def test_current_account_label_prefers_wallet_for_solana_live_profiles():
    wallet_address = "So11111111111111111111111111111111111111112"
    controller = AppController.__new__(AppController)
    controller.broker = SimpleNamespace(
        exchange_name="solana",
        account_id="project-123",
        options={"wallet_address": wallet_address},
        params={},
    )
    controller.config = SimpleNamespace(
        broker=SimpleNamespace(
            exchange="solana",
            account_id="project-123",
            options={"wallet_address": wallet_address},
            params={},
        )
    )

    assert controller.current_account_label() == "So1111...1112"


def test_current_account_label_falls_back_to_masked_api_key_for_live_ccxt_profiles():
    api_key = "organizations/test/apiKeys/key-1"
    controller = AppController.__new__(AppController)
    controller.broker = SimpleNamespace(
        exchange_name="coinbase",
        api_key=api_key,
        options={},
        params={},
    )
    controller.config = SimpleNamespace(
        broker=SimpleNamespace(
            exchange="coinbase",
            api_key=api_key,
            options={},
            params={},
        )
    )

    assert controller.current_account_label() == "orga...ey-1"


def test_live_readiness_report_is_advisory_only():
    controller = AppController.__new__(AppController)
    controller.time_frame = "1h"
    controller.health_check_report = []
    controller.get_broker_capability_profile = lambda: {
        "live_mode": True,
        "exchange": "oanda",
        "connected": False,
        "account_label": "Not set",
        "capabilities": {"trading": True, "orderbook": False},
    }
    controller._primary_runtime_symbol = lambda symbol=None: "EUR/USD"
    controller.get_market_data_health_snapshot = lambda symbol=None, timeframe=None: {
        "symbol": symbol or "EUR/USD",
        "timeframe": timeframe or "1h",
        "quote": {"fresh": False, "age_label": "unknown", "threshold_label": "20s"},
        "candles": {"fresh": False, "age_label": "unknown", "threshold_label": "3h", "timeframe": timeframe or "1h"},
        "orderbook": {"supported": False, "fresh": None, "age_label": "unknown", "threshold_label": ""},
    }
    controller.is_emergency_stop_active = lambda: False
    controller.get_health_check_summary = lambda: "Startup health checks have not run yet."

    report = AppController.get_live_readiness_report(controller, symbol="EUR/USD", timeframe="15m")

    assert report["ready"] is True
    assert report["blocking_reasons"] == []
    assert "Readiness gate disabled" in report["summary"]
    assert report["warning_reasons"]


def test_bind_active_session_state_filters_implausible_pair_symbols():
    emitted_connections = []
    emitted_symbols = []

    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.session_bind.filter_symbols")
    controller.session_manager = SimpleNamespace(active_session_id=None)
    controller.connection_signal = SimpleNamespace(emit=lambda state: emitted_connections.append(state))
    controller.symbols_signal = SimpleNamespace(emit=lambda exchange, symbols: emitted_symbols.append((exchange, symbols)))
    controller._handle_session_registry_changed = lambda: None
    controller._restore_session_scoped_state = lambda session: None
    controller._refresh_symbol_universe_tiers = lambda **kwargs: None
    controller._stop_active_market_stream_tasks = lambda: asyncio.sleep(0)
    controller._restart_telegram_service = lambda: asyncio.sleep(0)
    controller._start_market_stream = lambda: asyncio.sleep(0)
    controller._warmup_visible_candles = lambda: asyncio.sleep(0)
    controller._create_task = lambda coro, name: None
    controller.run_startup_health_check = lambda: asyncio.sleep(0)

    fake_session = SimpleNamespace(
        session_id="coinbase-live-001",
        config=SimpleNamespace(broker=SimpleNamespace(type="crypto", exchange="coinbase", mode="live")),
        broker="broker",
        trading_system="runtime",
        symbols=["BTC/USD", "00/USD", "ETH/USD"],
        symbol_catalog=["BTC/USD", "00/USD", "ETH/USD", "SOL/USD"],
        balances={"total": {"USD": 5000.0}},
        portfolio="portfolio",
        session_controller=None,
        connected=True,
        exchange="coinbase",
    )

    asyncio.run(AppController._bind_active_session_state(controller, fake_session, restart_stream=False))

    assert controller.symbols == ["BTC/USD", "ETH/USD"]
    assert controller.symbol_catalog == ["BTC/USD", "ETH/USD", "SOL/USD"]
    assert "00/USD" not in controller.symbol_catalog
    assert fake_session.symbols == ["BTC/USD", "ETH/USD"]
    assert fake_session.symbol_catalog == ["BTC/USD", "ETH/USD", "SOL/USD"]
    assert emitted_connections == ["connected"]
    assert emitted_symbols == [("coinbase", ["BTC/USD", "ETH/USD"])]


def test_initialize_trading_keeps_dashboard_visible(monkeypatch):
    calls = {"terminal": [], "stack_set": [], "stack_add": [], "created_tasks": []}

    class _FakeTerminalWindow(_FakeTerminal):
        def __init__(self, controller):
            super().__init__(calls)
            self.controller = controller

        def load_persisted_runtime_data(self):
            return asyncio.sleep(0)

    monkeypatch.setattr("frontend.ui.app_controller.Terminal", _FakeTerminalWindow)

    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.dashboard_visible")
    controller.terminal = None
    controller.dashboard = SimpleNamespace()
    controller.stack = SimpleNamespace(
        addWidget=lambda widget: calls["stack_add"].append(widget),
        setCurrentWidget=lambda widget: calls["stack_set"].append(widget),
    )
    controller._fit_window_to_available_screen = lambda *args, **kwargs: calls["terminal"].append("fit")
    controller._handle_session_registry_changed = lambda: calls["terminal"].append("refresh_registry")
    def _record_task(coro, name):
        calls["created_tasks"].append(name)
        close_coro = getattr(coro, "close", None)
        if callable(close_coro):
            close_coro()
        return None

    controller._create_task = _record_task
    controller._extract_balance_equity_value = lambda balances: 1000.0
    controller.balances = {"total": {"USD": 1000.0}}
    controller.equity_signal = SimpleNamespace(emit=lambda value: calls["terminal"].append(("equity", value)))
    controller.run_startup_health_check = lambda: asyncio.sleep(0)
    controller._terminal_runtime_restore_task = None
    controller._on_logout_requested = lambda: None

    asyncio.run(controller.initialize_trading())

    assert controller.terminal is not None
    assert "show" in calls["terminal"]
    assert "raise" in calls["terminal"]
    assert "activate" in calls["terminal"]
    assert calls["stack_add"] == []
    assert calls["stack_set"] == []
    assert "terminal_runtime_restore" in calls["created_tasks"]
    assert "startup_health_check" in calls["created_tasks"]


def test_restore_terminal_runtime_data_prefers_initial_runtime_loader():
    calls = []

    async def _load_initial_runtime_data():
        calls.append("initial")

    async def _load_persisted_runtime_data():
        calls.append("persisted")

    controller = AppController.__new__(AppController)
    controller._terminal_runtime_restore_task = None

    terminal = SimpleNamespace(
        _ui_shutting_down=False,
        load_initial_runtime_data=_load_initial_runtime_data,
        load_persisted_runtime_data=_load_persisted_runtime_data,
    )

    asyncio.run(AppController._restore_terminal_runtime_data(controller, terminal))

    assert calls == ["initial"]


def test_resolve_initial_storage_preferences_prefers_remote_env_when_unset(monkeypatch):
    class _FakeSettings:
        def contains(self, _key):
            return False

        def value(self, _key, default=None):
            return default

    monkeypatch.setenv(
        "SOPOTEK_DATABASE_URL",
        "mysql://sopotek:sopotek_local@mysql:3306/sopotek_trading?chartset=utf8mb4",
    )

    mode, url = AppController._resolve_initial_storage_preferences(_FakeSettings())

    assert mode == "remote"
    assert url == (
        "mysql+pymysql://sopotek:sopotek_local@mysql:3306/"
        "sopotek_trading?charset=utf8mb4"
    )


def test_resolve_initial_storage_preferences_respects_saved_local_mode(monkeypatch):
    class _FakeSettings:
        def contains(self, key):
            return key in {"storage/database_mode", "storage/database_url"}

        def value(self, key, default=None):
            if key == "storage/database_mode":
                return "local"
            if key == "storage/database_url":
                return ""
            return default

    monkeypatch.setenv(
        "SOPOTEK_DATABASE_URL",
        "mysql+pymysql://sopotek:sopotek_local@mysql:3306/sopotek_trading?charset=utf8mb4",
    )

    mode, url = AppController._resolve_initial_storage_preferences(_FakeSettings())

    assert mode == "local"
    assert url == ""


def test_resolve_initial_storage_preferences_env_mode_overrides_saved_local(monkeypatch):
    class _FakeSettings:
        def contains(self, key):
            return key in {"storage/database_mode", "storage/database_url"}

        def value(self, key, default=None):
            if key == "storage/database_mode":
                return "local"
            if key == "storage/database_url":
                return ""
            return default

    monkeypatch.setenv("SOPOTEK_DATABASE_MODE", "remote")
    monkeypatch.setenv(
        "SOPOTEK_DATABASE_URL",
        "mysql://sopotek:sopotek_local@mysql:3306/sopotek_trading?chartset=utf8mb4",
    )

    mode, url = AppController._resolve_initial_storage_preferences(_FakeSettings())

    assert mode == "remote"
    assert url == (
        "mysql+pymysql://sopotek:sopotek_local@mysql:3306/"
        "sopotek_trading?charset=utf8mb4"
    )


def test_setup_data_requires_remote_storage_when_env_forces_remote(monkeypatch):
    controller = AppController.__new__(AppController)
    captured = {}

    controller.database_mode = "remote"
    controller.database_url = "mysql+pymysql://sopotek:sopotek_local@mysql:3306/sopotek_trading?charset=utf8mb4"
    controller.configure_storage_database = lambda **kwargs: captured.update(kwargs)
    controller._restore_performance_state = lambda: None

    monkeypatch.setenv("SOPOTEK_DATABASE_MODE", "remote")
    monkeypatch.setenv("SOPOTEK_DATABASE_URL", controller.database_url)

    AppController._setup_data(controller)

    assert captured["database_mode"] == "remote"
    assert captured["database_url"] == controller.database_url
    assert captured["persist"] is False
    assert captured["raise_on_error"] is True


def test_configure_storage_database_demotes_remote_mode_when_sqlite_fallback_is_used(monkeypatch):
    import frontend.ui.app_controller as app_controller_mod

    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.storage")
    controller.settings = SimpleNamespace(setValue=lambda *_args, **_kwargs: None)
    controller._rebind_storage_dependencies = lambda: None

    monkeypatch.setattr(app_controller_mod, "configure_database", lambda _url=None: "sqlite:////tmp/sopotek_fallback.sqlite3")
    monkeypatch.setattr(app_controller_mod, "init_database", lambda: None)
    monkeypatch.setattr(app_controller_mod, "get_database_url", lambda: "sqlite:////tmp/sopotek_fallback.sqlite3")
    monkeypatch.setattr(app_controller_mod, "MarketDataRepository", lambda: object())
    monkeypatch.setattr(app_controller_mod, "TradeRepository", lambda: object())
    monkeypatch.setattr(app_controller_mod, "TradeAuditRepository", lambda: object())
    monkeypatch.setattr(app_controller_mod, "EquitySnapshotRepository", lambda: object())
    monkeypatch.setattr(app_controller_mod, "AgentDecisionRepository", lambda: object())

    configured = AppController.configure_storage_database(
        controller,
        database_mode="remote",
        database_url="postgresql+psycopg://sopotek:sopotek_local@postgres:5432/sopotek_trading",
        persist=False,
        raise_on_error=True,
    )

    assert configured == "sqlite:////tmp/sopotek_fallback.sqlite3"
    assert controller.database_mode == "local"
    assert controller.database_url == ""
    assert controller.database_connection_url == "sqlite:////tmp/sopotek_fallback.sqlite3"


def test_build_broker_for_login_routes_crypto_paper_sessions_to_paper_broker():
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.paper_routing")
    controller.initial_capital = 25000.0
    controller.paper_data_exchange = None
    controller.paper_data_exchanges = []
    config = SimpleNamespace(
        broker=SimpleNamespace(
            type="crypto",
            exchange="binanceus",
            mode="paper",
            params={},
            options={},
        )
    )
    controller.config = config

    broker = controller._build_broker_for_login(config)

    assert isinstance(broker, PaperBroker)
    assert config.broker.params["paper_data_exchange"] == "binanceus"
    assert config.broker.params["paper_data_exchanges"][0] == "binanceus"
    assert controller.paper_data_exchange == "binanceus"
    assert broker.exchange_name == "binanceus"


def test_active_exchange_code_prefers_selected_exchange_for_paper_broker():
    controller = AppController.__new__(AppController)
    controller.broker = SimpleNamespace(exchange_name="binanceus", mode="paper")
    controller.config = SimpleNamespace(
        broker=SimpleNamespace(exchange="binanceus", type="crypto", mode="paper")
    )

    assert controller._active_exchange_code() == "binanceus"


def test_friendly_initialization_error_explains_binanceus_testnet_restriction():
    controller = AppController.__new__(AppController)
    message = controller._friendly_initialization_error(
        "binanceus GET https://testnet.binance.vision/api/v3/time 451 restricted location"
    )

    assert "PaperBroker" not in message
    assert "PAPER mode" in message
    assert "LIVE mode" in message
    assert "Binance US sandbox routing" in message


def test_friendly_startup_error_explains_local_mysql_volume_credential_drift():
    controller = AppController.__new__(AppController)
    controller.database_url = "mysql+pymysql://sopotek:sopotek_local@mysql:3306/sopotek_trading?charset=utf8mb4"

    message = controller._friendly_startup_error(
        "sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) "
        "(1045, \"Access denied for user 'sopotek'@'172.18.0.3' (using password: YES)\")"
    )

    assert "server rejected the username or password" in message
    assert "mysql_data" in message
    assert "docker compose down -v" in message
    assert "mysql+pymysql://sopotek:***@mysql:3306/sopotek_trading?charset=utf8mb4" in message
