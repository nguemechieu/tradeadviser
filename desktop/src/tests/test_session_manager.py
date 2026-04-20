import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController
from sessions.session_manager import SessionManager
from sessions.trading_session import SessionControllerProxy, SessionRiskLimits, TradingSession


class _FakeSession:
    def __init__(self, *, session_id, config, parent_controller, logger=None, on_state_change=None):
        self.session_id = session_id
        self.config = config
        self.parent_controller = parent_controller
        self.logger = logger or logging.getLogger("test.session")
        self.on_state_change = on_state_change
        broker_cfg = config.broker
        self.exchange = str(broker_cfg.exchange or "broker")
        self.broker_type = str(broker_cfg.type or "paper")
        self.mode = str(broker_cfg.mode or "paper")
        self.strategy_name = str(getattr(config, "strategy", "Trend Following") or "Trend Following")
        self.label = f"{self.exchange.upper()} {self.mode.upper()}"
        self.status = "created"
        self.connected = False
        self.autotrading = False
        self.symbols = ["BTC/USDT"]
        self.balances = {"total": {"USD": 1000.0}}
        self.positions = []
        self.open_orders = []
        self.trade_history = []
        self.portfolio = None
        self.broker = object()
        self.trading_system = object()
        self.session_controller = SimpleNamespace(
            behavior_guard="guard",
            event_bus="bus",
            agent_event_runtime="runtime",
            signal_agents=["agent"],
            signal_consensus_agent="consensus",
            signal_aggregation_agent="aggregation",
            reasoning_engine="reasoning",
            agent_memory="memory",
        )
        self._closed = False

    async def initialize(self):
        self.connected = True
        self.status = "ready"
        if callable(self.on_state_change):
            self.on_state_change(self)
        return self

    async def start_trading(self):
        self.autotrading = True
        self.status = "running"
        if callable(self.on_state_change):
            self.on_state_change(self)
        return self

    async def stop_trading(self):
        self.autotrading = False
        self.status = "ready"
        if callable(self.on_state_change):
            self.on_state_change(self)
        return self

    async def close(self):
        self.connected = False
        self.status = "closed"
        self._closed = True
        if callable(self.on_state_change):
            self.on_state_change(self)

    async def route_price(self, symbol, side):
        price = 100.0 if self.exchange == "binance" else 99.0
        if str(side or "").lower() == "sell":
            price = 101.0 if self.exchange == "binance" else 100.5
        return {
            "session_id": self.session_id,
            "exchange": self.exchange,
            "symbol": symbol,
            "side": side,
            "price": price,
        }

    def snapshot(self):
        equity = float(self.balances.get("total", {}).get("USD", 0.0))
        return SimpleNamespace(
            to_dict=lambda: {
                "session_id": self.session_id,
                "label": self.label,
                "exchange": self.exchange,
                "broker_type": self.broker_type,
                "mode": self.mode,
                "strategy": self.strategy_name,
                "status": self.status,
                "connected": self.connected,
                "autotrading": self.autotrading,
                "account_label": "acct",
                "equity": equity,
                "balance_summary": f"USD {equity:,.2f}",
                "positions_count": len(self.positions),
                "open_orders_count": len(self.open_orders),
                "trade_count": len(self.trade_history),
                "symbols_count": len(self.symbols),
                "last_error": "",
                "last_update_at": "",
                "started_at": "",
                "metadata": {},
            },
            equity=equity,
            positions_count=len(self.positions),
            open_orders_count=len(self.open_orders),
            trade_count=len(self.trade_history),
            exchange=self.exchange,
        )


def _config(exchange, broker_type="crypto", mode="paper", strategy="Trend Following"):
    return SimpleNamespace(
        broker=SimpleNamespace(type=broker_type, exchange=exchange, mode=mode),
        strategy=strategy,
    )


def test_session_manager_lifecycle_and_best_route():
    controller = SimpleNamespace(_handle_session_registry_changed=lambda: None)
    manager = SessionManager(
        parent_controller=controller,
        logger=logging.getLogger("test.session_manager"),
        session_factory=_FakeSession,
    )

    async def scenario():
        first = await manager.create_session(_config("binance"))
        second = await manager.create_session(_config("coinbase"))
        await manager.activate_session(second.session_id)
        await manager.start_session(first.session_id)
        aggregate = manager.aggregate_portfolio()
        best_buy = await manager.route_order_to_best_session("BTC/USDT", "buy")
        best_sell = await manager.route_order_to_best_session("BTC/USDT", "sell")
        await manager.stop_session(first.session_id)
        destroyed = await manager.destroy_session(second.session_id)
        return first, second, aggregate, best_buy, best_sell, destroyed

    first, second, aggregate, best_buy, best_sell, destroyed = asyncio.run(scenario())

    assert first.session_id == "binance-paper-001"
    assert second.session_id == "coinbase-paper-002"
    assert aggregate["session_count"] == 2
    assert aggregate["total_equity"] == 2000.0
    assert best_buy["exchange"] == "coinbase"
    assert best_sell["exchange"] == "binance"
    assert destroyed is True
    assert second._closed is True


def test_bind_active_session_state_updates_controller_fields():
    emitted_connections = []
    emitted_symbols = []
    created_tasks = []
    registry_events = []

    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.session_bind")
    controller.session_manager = SimpleNamespace(active_session_id=None)
    controller.connection_signal = SimpleNamespace(emit=lambda state: emitted_connections.append(state))
    controller.symbols_signal = SimpleNamespace(emit=lambda exchange, symbols: emitted_symbols.append((exchange, symbols)))
    controller._handle_session_registry_changed = lambda: registry_events.append("refresh")
    controller._create_task = lambda coro, name: created_tasks.append(name)
    controller._restart_telegram_service = lambda: asyncio.sleep(0)
    controller._start_market_stream = lambda: asyncio.sleep(0)
    controller._warmup_visible_candles = lambda: asyncio.sleep(0)
    controller.run_startup_health_check = lambda: asyncio.sleep(0)
    controller.dashboard = None
    controller.terminal = None

    fake_session = SimpleNamespace(
        session_id="binance-paper-001",
        config=_config("binance"),
        broker="broker",
        trading_system="runtime",
        symbols=["BTC/USDT", "ETH/USDT"],
        symbol_catalog=["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"],
        balances={"total": {"USD": 5000.0}},
        portfolio="portfolio",
        session_controller=SimpleNamespace(
            behavior_guard="guard",
            event_bus="bus",
            agent_event_runtime="runtime_bus",
            signal_agents=["agent"],
            signal_consensus_agent="consensus",
            signal_aggregation_agent="aggregation",
            reasoning_engine="reasoning",
            agent_memory="memory",
        ),
        connected=True,
        exchange="binance",
    )

    asyncio.run(AppController._bind_active_session_state(controller, fake_session, restart_stream=False))

    assert controller.active_session_id == "binance-paper-001"
    assert controller.session_manager.active_session_id == "binance-paper-001"
    assert controller.broker == "broker"
    assert controller.trading_system == "runtime"
    assert controller.symbols == ["BTC/USDT", "ETH/USDT"]
    assert controller.symbol_catalog == ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]
    assert controller.balance == {"total": {"USD": 5000.0}}
    assert emitted_connections == ["connected"]
    assert emitted_symbols == [("binance", ["BTC/USDT", "ETH/USDT"])]
    assert registry_events == ["refresh"]
    assert created_tasks == []
    assert controller.get_symbol_universe_snapshot()["catalog"] == ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]


def test_trading_session_start_runs_runtime_in_background():
    runtime_started = asyncio.Event()
    runtime_stopped = asyncio.Event()

    class _BlockingRuntime:
        def __init__(self):
            self.stop_calls = 0

        async def start(self):
            runtime_started.set()
            await runtime_stopped.wait()

        async def stop(self, wait_for_background_workers=False):
            _ = wait_for_background_workers
            self.stop_calls += 1
            runtime_stopped.set()

    controller = SimpleNamespace(logger=logging.getLogger("test.session_runtime"))
    session = TradingSession(
        session_id="binance-paper-001",
        config=_config("binance"),
        parent_controller=controller,
        logger=logging.getLogger("test.session_runtime"),
    )
    runtime = _BlockingRuntime()

    async def fake_initialize():
        session.connected = True
        session.status = "ready"
        session.trading_system = runtime
        return session

    session.initialize = fake_initialize  # type: ignore[method-assign]

    async def scenario():
        await session.start_trading()
        await runtime_started.wait()
        assert session.autotrading is True
        assert session.status == "running"
        assert session._runtime_task is not None
        assert session._runtime_task.done() is False
        await session.stop_trading()
        return runtime.stop_calls, session.status, session.autotrading, session._runtime_task

    stop_calls, status, autotrading, runtime_task = asyncio.run(scenario())

    assert stop_calls == 1
    assert status == "ready"
    assert autotrading is False
    assert runtime_task is None


def test_trading_session_risk_state_blocks_drawdown_exposure_and_leverage():
    controller = SimpleNamespace(logger=logging.getLogger("test.session_risk"))
    session = TradingSession(
        session_id="coinbase-paper-001",
        config=_config("coinbase"),
        parent_controller=controller,
        logger=logging.getLogger("test.session_risk"),
    )
    session.risk_limits = SessionRiskLimits(
        max_drawdown_pct=0.10,
        max_position_size_pct=0.50,
        max_gross_exposure_pct=2.0,
        max_leverage=5.0,
    )
    session.balances = {"total": {"USD": 1000.0}}
    session.positions = [{"symbol": "BTC/USDT", "notional": 2500.0, "leverage": 8.0}]
    session._peak_equity = 1500.0

    session._update_risk_state()

    assert session.risk_state.blocked is True
    assert "Drawdown" in session.risk_state.reason
    assert "Gross exposure" in session.risk_state.reason
    assert "leverage" in session.risk_state.reason
    assert session.last_error == session.risk_state.reason


def test_trading_session_fetch_symbols_safe_preserves_full_runtime_universe():
    class _Broker:
        async def fetch_symbols(self):
            return ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD"]

    controller = SimpleNamespace(
        logger=logging.getLogger("test.session_symbols"),
        _limit_runtime_symbols=lambda *_args, **_kwargs: ["BTC/USD"],
    )
    session = TradingSession(
        session_id="coinbase-paper-001",
        config=_config("coinbase"),
        parent_controller=controller,
        logger=logging.getLogger("test.session_symbols"),
    )
    session.broker = _Broker()

    symbols = asyncio.run(session._fetch_symbols_safe())

    assert symbols == ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD"]
    assert session.symbol_catalog == ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD"]


def test_trading_session_fetch_symbols_safe_uses_session_config_instead_of_parent_symbols():
    class _Broker:
        async def fetch_symbols(self):
            return []

    controller = SimpleNamespace(
        logger=logging.getLogger("test.session_symbols_isolated"),
        symbols=["GBP/USD", "EUR/USD", "AUD/JPY"],
    )
    config = SimpleNamespace(
        broker=SimpleNamespace(
            type="crypto",
            exchange="coinbase",
            mode="paper",
            params={"symbols": ["BTC/USD", "ETH/USD"]},
        ),
        strategy="Trend Following",
    )
    session = TradingSession(
        session_id="coinbase-paper-001",
        config=config,
        parent_controller=controller,
        logger=logging.getLogger("test.session_symbols_isolated"),
    )
    session.broker = _Broker()

    symbols = asyncio.run(session._fetch_symbols_safe())

    assert symbols == ["BTC/USD", "ETH/USD"]
    assert "GBP/USD" not in symbols
    assert session.symbol_catalog == ["BTC/USD", "ETH/USD"]


def test_app_controller_fetch_symbols_does_not_reuse_stale_controller_symbols():
    class _Broker:
        async def fetch_symbols(self):
            return []

    controller = AppController.__new__(AppController)
    controller.symbols = ["GBP/USD", "EUR/USD", "AUD/JPY"]
    controller.config = SimpleNamespace(
        broker=SimpleNamespace(params={"symbols": ["BTC/USD"]})
    )

    symbols = asyncio.run(AppController._fetch_symbols(controller, _Broker()))

    assert symbols == ["BTC/USD"]
    assert "GBP/USD" not in symbols


def test_publish_runtime_payloads_preserve_session_identity():
    ai_payloads = []
    debug_payloads = []

    controller = AppController.__new__(AppController)
    controller._session_closing = False
    controller.terminal = None
    controller.ai_signal_monitor = SimpleNamespace(emit=lambda payload: ai_payloads.append(payload))
    controller.strategy_debug_signal = SimpleNamespace(emit=lambda payload: debug_payloads.append(payload))

    AppController.publish_ai_signal(
        controller,
        "BTC/USDT",
        {
            "side": "buy",
            "confidence": 0.82,
            "reason": "Momentum aligned",
            "session_id": "binance-paper-001",
            "session_label": "BINANCE PAPER 001",
        },
    )
    AppController.publish_strategy_debug(
        controller,
        "BTC/USDT",
        {
            "side": "buy",
            "confidence": 0.82,
            "reason": "Momentum aligned",
            "session_id": "binance-paper-001",
            "session_label": "BINANCE PAPER 001",
        },
    )

    assert ai_payloads[0]["session_id"] == "binance-paper-001"
    assert ai_payloads[0]["session_label"] == "BINANCE PAPER 001"
    assert debug_payloads[0]["session_id"] == "binance-paper-001"
    assert debug_payloads[0]["session_label"] == "BINANCE PAPER 001"


def test_publish_ai_signal_preserves_market_hours_metadata():
    ai_payloads = []

    controller = AppController.__new__(AppController)
    controller._session_closing = False
    controller.terminal = None
    controller.ai_signal_monitor = SimpleNamespace(emit=lambda payload: ai_payloads.append(payload))

    AppController.publish_ai_signal(
        controller,
        "AAPL",
        {
            "side": "hold",
            "confidence": 0.35,
            "reason": "SKIP because stock market is closed.",
            "market_hours": {
                "asset_type": "stocks",
                "market_open": False,
                "trade_allowed": False,
                "session": "closed",
                "high_liquidity": None,
                "reason": "stock market is closed due to regular hours, weekend, or holiday.",
            },
        },
    )

    assert ai_payloads[0]["market_hours"]["asset_type"] == "stocks"
    assert ai_payloads[0]["market_hours"]["trade_allowed"] is False
    assert ai_payloads[0]["market_session"] == "closed"


def test_session_controller_proxy_uses_session_scoped_autotrade_symbol_inputs():
    captured = {}

    def resolve_symbols(**kwargs):
        captured["active"] = kwargs
        return ["SOL/USD", "ADA/USD"]

    def resolve_enabled(symbol, **kwargs):
        captured["enabled"] = {"symbol": symbol, **kwargs}
        return symbol == "SOL/USD"

    parent = SimpleNamespace(
        get_active_autotrade_symbols=resolve_symbols,
        is_symbol_enabled_for_autotrade=resolve_enabled,
    )
    session = SimpleNamespace(
        session_id="coinbase-paper-001",
        label="COINBASE PAPER 001",
        logger=logging.getLogger("test.session_proxy"),
        config=_config("coinbase"),
        exchange="coinbase",
        broker=SimpleNamespace(exchange_name="coinbase"),
        broker_type="crypto",
        symbols=["BTC/USD", "ETH/USD"],
        symbol_catalog=["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD"],
        balances={"total": {"USD": 1000.0}},
        last_ai_signal={},
        last_strategy_debug={},
    )

    proxy = SessionControllerProxy(parent, session)

    assert proxy.get_active_autotrade_symbols() == ["SOL/USD", "ADA/USD"]
    assert proxy.is_symbol_enabled_for_autotrade("SOL/USD") is True
    assert captured["active"]["available_symbols"] == ["BTC/USD", "ETH/USD"]
    assert captured["active"]["catalog_symbols"] == ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD"]
    assert captured["enabled"]["symbol"] == "SOL/USD"
    assert captured["enabled"]["exchange"] == "coinbase"
