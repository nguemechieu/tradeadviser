import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.memory import AgentMemory
from event_bus.event_bus import EventBus
from event_bus.event_types import EventType
from frontend.ui.app_controller import AppController
from market_data.orderbook_buffer import OrderBookBuffer
from market_data.ticker_buffer import TickerBuffer
from sessions.trading_session import SessionControllerProxy, TradingSession


class _FakeTradingRuntime:
    def __init__(self, controller):
        self.controller = controller
        self.event_bus = EventBus(enable_persistence=False)
        self.agent_memory = AgentMemory()
        self.portfolio = None

    async def start(self):
        return None

    async def stop(self, wait_for_background_workers=False):
        _ = wait_for_background_workers
        return None


class _FakeBroker:
    def __init__(self):
        self.account_id = None
        self.account_hash = None
        self.options = {}
        self.params = {}
        self.connect_calls = 0
        self.account_requests = 0

    async def connect(self):
        self.connect_calls += 1
        return True

    async def close(self):
        return True

    async def get_accounts(self):
        self.account_requests += 1
        return [{"account_id": "DU123456", "account_hash": "hash-abc"}]

    async def fetch_balance(self):
        return {"equity": 1000.0}

    async def fetch_positions(self):
        return []

    async def fetch_open_orders(self, limit=100):
        _ = limit
        return []


class _SignalRecorder:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


def test_initialize_syncs_discovered_account_to_session_and_config(monkeypatch):
    monkeypatch.setattr("sessions.trading_session.SopotekTrading", _FakeTradingRuntime)

    broker = _FakeBroker()
    broker_config = SimpleNamespace(
        exchange="schwab",
        mode="live",
        type="stocks",
        account_id=None,
        options={},
        params={},
    )
    config = SimpleNamespace(
        broker=broker_config,
        risk=None,
        strategy="Trend Following",
    )
    parent_controller = SimpleNamespace(
        _build_broker_for_login=lambda _config: broker,
        symbols=["AAPL"],
    )

    async def _exercise():
        session = TradingSession(
            session_id="schwab-live-001",
            config=config,
            parent_controller=parent_controller,
            logger=logging.getLogger("test.trading_session.account_sync"),
        )
        await session.initialize()

        assert broker.connect_calls == 1
        assert broker.account_requests >= 1
        assert broker.account_id == "DU123456"
        assert broker.account_hash == "hash-abc"
        assert config.broker.account_id == "DU123456"
        assert config.broker.options["account_id"] == "DU123456"
        assert config.broker.options["account_hash"] == "hash-abc"
        assert config.broker.params["account_id"] == "DU123456"
        assert config.broker.params["account_hash"] == "hash-abc"
        assert session.session_controller.current_account_label() == "DU123456"
        assert session.snapshot().account_label == "DU123456"

        await session.close()

    asyncio.run(_exercise())


def test_session_runtime_events_populate_live_agent_feed_and_notify_active_parent(monkeypatch):
    monkeypatch.setattr("sessions.trading_session.SopotekTrading", _FakeTradingRuntime)

    broker = _FakeBroker()
    broker_config = SimpleNamespace(
        exchange="oanda",
        mode="paper",
        type="forex",
        account_id=None,
        options={},
        params={},
    )
    config = SimpleNamespace(
        broker=broker_config,
        risk=None,
        strategy="Trend Following",
    )
    runtime_signal = _SignalRecorder()
    parent_controller = SimpleNamespace(
        _build_broker_for_login=lambda _config: broker,
        symbols=["EUR/USD"],
        active_session_id="oanda-paper-001",
        agent_runtime_signal=runtime_signal,
    )

    async def _exercise():
        session = TradingSession(
            session_id="oanda-paper-001",
            config=config,
            parent_controller=parent_controller,
            logger=logging.getLogger("test.trading_session.runtime_feed"),
        )
        await session.initialize()

        session.trading_system.agent_memory.store(
            "SignalAgent",
            "selected",
            {
                "strategy_name": "EMA Cross",
                "timeframe": "1h",
                "side": "buy",
                "reason": "Breakout confirmed.",
                "confidence": 0.82,
            },
            symbol="EUR/USD",
            decision_id="dec-1",
        )

        await session.event_bus.publish(
            EventType.DECISION_EVENT,
            {
                "profile_id": "growth",
                "symbol": "EUR/USD",
                "action": "BUY",
                "side": "buy",
                "quantity": 1.25,
                "price": 1.0842,
                "confidence": 0.78,
                "selected_strategy": "Trend Following",
                "reasoning": "BUY because weighted voting favored Trend Following.",
                "model_probability": 0.84,
                "applied_constraints": ["growth profile"],
                "votes": {"buy": 1.2, "sell": 0.4},
                "features": {"rsi": 31.2},
                "metadata": {"risk_level": "medium"},
            },
            source="TraderAgent",
        )
        await session.event_bus.dispatch_once()

        assert len(session.live_agent_runtime_feed) >= 2
        latest_bus_row = session.live_agent_runtime_feed[-1]
        assert latest_bus_row["event_type"] == EventType.DECISION_EVENT
        assert latest_bus_row["profile_id"] == "growth"
        assert latest_bus_row["agent_name"] == "TraderAgent"
        assert latest_bus_row["symbol"] == "EUR/USD"
        assert "TraderAgent chose BUY" in latest_bus_row["message"]
        assert session.live_agent_decision_events["EUR/USD"][-1]["profile_id"] == "growth"
        assert runtime_signal.calls[-1][0]["event_type"] == EventType.DECISION_EVENT

        await session.close()

    asyncio.run(_exercise())


def test_session_controller_uses_wallet_label_for_solana_project_profiles():
    wallet_address = "So11111111111111111111111111111111111111112"
    session = SimpleNamespace(
        config=SimpleNamespace(
            broker=SimpleNamespace(
                exchange="solana",
                account_id="project-123",
                options={"wallet_address": wallet_address},
                params={},
            )
        ),
        exchange="solana",
        broker_type="crypto",
        broker=SimpleNamespace(
            exchange_name="solana",
            account_id="project-123",
            options={"wallet_address": wallet_address},
            params={},
        ),
        symbols=[],
        balances={},
        session_id="solana-live-001",
        label="Solana Live",
        logger=logging.getLogger("test.trading_session.wallet_label"),
    )
    parent_controller = SimpleNamespace()
    controller = SessionControllerProxy(parent_controller, session)

    assert controller.current_account_label() == "So1111...1112"


def test_session_controller_keeps_symbol_state_isolated_from_parent_mutations():
    parent_controller = SimpleNamespace(
        strategy_name="Trend Following",
        time_frame="1h",
        multi_strategy_enabled=True,
        autotrade_scope="watchlist",
        autotrade_watchlist={"BTC/USDT"},
        symbol_strategy_assignments={
            "BTC/USDT": [
                {
                    "strategy_name": "Trend Following",
                    "score": 1.0,
                    "weight": 1.0,
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                    "rank": 1,
                }
            ]
        },
        symbol_strategy_rankings={
            "BTC/USDT": [
                {
                    "strategy_name": "Trend Following",
                    "score": 1.0,
                    "weight": 1.0,
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                    "rank": 1,
                }
            ]
        },
        symbol_strategy_locks={"BTC/USDT"},
        limit=500,
    )
    session = SimpleNamespace(
        config=SimpleNamespace(broker=SimpleNamespace(exchange="binance", mode="paper")),
        exchange="binance",
        broker_type="crypto",
        broker=SimpleNamespace(exchange_name="binance"),
        symbols=["ETH/USDT"],
        symbol_catalog=["ETH/USDT"],
        balances={},
        session_id="binance-paper-001",
        label="Binance Paper",
        logger=logging.getLogger("test.trading_session.isolation"),
        autotrade_scope="watchlist",
        autotrade_watchlist={"ETH/USDT"},
        symbol_strategy_assignments={
            "ETH/USDT": [
                {
                    "strategy_name": "EMA Cross",
                    "score": 2.0,
                    "weight": 1.0,
                    "symbol": "ETH/USDT",
                    "timeframe": "4h",
                    "rank": 1,
                }
            ]
        },
        symbol_strategy_rankings={
            "ETH/USDT": [
                {
                    "strategy_name": "EMA Cross",
                    "score": 2.0,
                    "weight": 1.0,
                    "symbol": "ETH/USDT",
                    "timeframe": "4h",
                    "rank": 1,
                }
            ]
        },
        symbol_strategy_locks={"ETH/USDT"},
        candle_buffers={},
        orderbook_buffer=OrderBookBuffer(),
        ticker_buffer=TickerBuffer(),
        recent_trades_cache={},
        recent_trades_last_request_at={},
        live_agent_runtime_feed=[],
        live_agent_decision_events={},
    )
    controller = SessionControllerProxy(parent_controller, session)

    parent_controller.autotrade_watchlist.add("SOL/USDT")
    parent_controller.symbol_strategy_assignments["BTC/USDT"][0]["strategy_name"] = "Changed"

    assert controller.get_active_autotrade_symbols() == ["ETH/USDT"]
    assert controller.assigned_strategies_for_symbol("ETH/USDT")[0]["strategy_name"] == "EMA Cross"
    assert controller.assigned_strategies_for_symbol("BTC/USDT")[0]["strategy_name"] == "Trend Following"


def test_bind_active_session_state_restores_session_scoped_symbols_and_buffers():
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.app_controller.session_restore")
    controller.active_session_id = None
    controller.limit = 500
    controller.autotrade_scope = "watchlist"
    controller.autotrade_watchlist = {"BTC/USDT"}
    controller.symbol_strategy_assignments = {
        "BTC/USDT": [
            {
                "strategy_name": "Trend Following",
                "score": 1.0,
                "weight": 1.0,
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "rank": 1,
            }
        ]
    }
    controller.symbol_strategy_rankings = {}
    controller.symbol_strategy_locks = {"BTC/USDT"}
    controller.candle_buffers = {"BTC/USDT": {"1h": "btc"}}
    controller.orderbook_buffer = OrderBookBuffer()
    controller.ticker_buffer = TickerBuffer()
    controller._recent_trades_cache = {"BTC/USDT": [{"price": 1.0}]}
    controller._recent_trades_last_request_at = {"BTC/USDT": 1.0}
    controller._live_agent_runtime_feed = [{"symbol": "BTC/USDT"}]
    controller._live_agent_decision_events = {"BTC/USDT": [{"decision_id": "a"}]}
    controller.connection_signal = SimpleNamespace(emit=lambda *_args, **_kwargs: None)
    controller.symbols_signal = SimpleNamespace(emit=lambda *_args, **_kwargs: None)
    controller._refresh_symbol_universe_tiers = lambda **_kwargs: None
    controller._handle_session_registry_changed = lambda: None
    controller._stop_active_market_stream_tasks = lambda: asyncio.sleep(0)
    controller._restart_telegram_service = lambda: asyncio.sleep(0)
    controller._start_market_stream = lambda: asyncio.sleep(0)
    controller._warmup_visible_candles = lambda: asyncio.sleep(0)
    controller._create_task = lambda coro, _name: coro.close() if hasattr(coro, "close") else None

    session_a = SimpleNamespace(
        session_id="session-a",
        config=SimpleNamespace(broker=SimpleNamespace(type="crypto")),
        broker=SimpleNamespace(exchange_name="binance"),
        trading_system=None,
        symbols=["BTC/USDT"],
        symbol_catalog=["BTC/USDT"],
        balances={},
        portfolio=None,
        session_controller=SimpleNamespace(
            behavior_guard=None,
            event_bus=None,
            agent_event_runtime=None,
            signal_agents=[],
            signal_consensus_agent=None,
            signal_aggregation_agent=None,
            reasoning_engine=None,
            agent_memory=None,
        ),
        connected=True,
        exchange="binance",
        autotrade_scope="watchlist",
        autotrade_watchlist={"BTC/USDT"},
        symbol_strategy_assignments={
            "BTC/USDT": [
                {
                    "strategy_name": "Trend Following",
                    "score": 1.0,
                    "weight": 1.0,
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                    "rank": 1,
                }
            ]
        },
        symbol_strategy_rankings={},
        symbol_strategy_locks={"BTC/USDT"},
        candle_buffers={"BTC/USDT": {"1h": "btc"}},
        orderbook_buffer=OrderBookBuffer(),
        ticker_buffer=TickerBuffer(),
        recent_trades_cache={"BTC/USDT": [{"price": 1.0}]},
        recent_trades_last_request_at={"BTC/USDT": 1.0},
        live_agent_runtime_feed=[{"symbol": "BTC/USDT"}],
        live_agent_decision_events={"BTC/USDT": [{"decision_id": "a"}]},
    )
    session_b = SimpleNamespace(
        session_id="session-b",
        config=SimpleNamespace(broker=SimpleNamespace(type="crypto")),
        broker=SimpleNamespace(exchange_name="coinbase"),
        trading_system=None,
        symbols=["ETH/USDT"],
        symbol_catalog=["ETH/USDT"],
        balances={},
        portfolio=None,
        session_controller=SimpleNamespace(
            behavior_guard=None,
            event_bus=None,
            agent_event_runtime=None,
            signal_agents=[],
            signal_consensus_agent=None,
            signal_aggregation_agent=None,
            reasoning_engine=None,
            agent_memory=None,
        ),
        connected=True,
        exchange="coinbase",
        autotrade_scope="watchlist",
        autotrade_watchlist={"ETH/USDT"},
        symbol_strategy_assignments={
            "ETH/USDT": [
                {
                    "strategy_name": "EMA Cross",
                    "score": 2.0,
                    "weight": 1.0,
                    "symbol": "ETH/USDT",
                    "timeframe": "4h",
                    "rank": 1,
                }
            ]
        },
        symbol_strategy_rankings={},
        symbol_strategy_locks={"ETH/USDT"},
        candle_buffers={"ETH/USDT": {"4h": "eth"}},
        orderbook_buffer=OrderBookBuffer(),
        ticker_buffer=TickerBuffer(),
        recent_trades_cache={"ETH/USDT": [{"price": 2.0}]},
        recent_trades_last_request_at={"ETH/USDT": 2.0},
        live_agent_runtime_feed=[{"symbol": "ETH/USDT"}],
        live_agent_decision_events={"ETH/USDT": [{"decision_id": "b"}]},
    )
    sessions = {
        "session-a": session_a,
        "session-b": session_b,
    }
    controller.session_manager = SimpleNamespace(
        active_session_id=None,
        get_session=lambda session_id: sessions.get(session_id),
    )

    async def _exercise():
        await controller._bind_active_session_state(session_a, restart_stream=False)
        controller.autotrade_watchlist = {"BTC/USDT", "SOL/USDT"}
        controller.symbol_strategy_assignments["BTC/USDT"][0]["strategy_name"] = "Updated"
        controller.candle_buffers["BTC/USDT"]["1h"] = "btc-updated"

        await controller._bind_active_session_state(session_b, restart_stream=False)

        assert session_a.autotrade_watchlist == {"BTC/USDT", "SOL/USDT"}
        assert session_a.symbol_strategy_assignments["BTC/USDT"][0]["strategy_name"] == "Updated"
        assert session_a.candle_buffers["BTC/USDT"]["1h"] == "btc-updated"
        assert controller.autotrade_watchlist == {"ETH/USDT"}
        assert controller.symbol_strategy_assignments["ETH/USDT"][0]["strategy_name"] == "EMA Cross"
        assert controller.candle_buffers is session_b.candle_buffers
        assert controller._live_agent_runtime_feed is session_b.live_agent_runtime_feed

    asyncio.run(_exercise())
