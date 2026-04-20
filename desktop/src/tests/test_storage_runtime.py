import asyncio
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB_PATH = Path(__file__).resolve().parent / "test_runtime_storage.sqlite3"
REMOTE_DB_PATH = Path(__file__).resolve().parent / "test_runtime_storage_remote.sqlite3"
os.environ["SOPOTEK_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from event_bus.event_bus import EventBus
from execution.execution_manager import ExecutionManager
from execution.order_router import OrderRouter
from storage import database as storage_db
from storage.market_data_repository import MarketDataRepository
from storage.trade_audit_repository import TradeAuditRepository
from storage.trade_repository import TradeRepository


class MockBroker:
    exchange_name = "paper"

    def __init__(self):
        self._balance = {"free": {"USDT": 1000.0}}
        exchange = type("Exchange", (), {})()
        exchange.markets = {"BTC/USDT": {"active": True}}
        exchange.amount_to_precision = lambda symbol, amount: amount
        self.exchange = exchange

    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
        stop_price=None,
    ):
        return {
            "id": "order-123",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": type,
            "price": 100.0 if price is None else price,
            "status": "filled",
            "timestamp": "2026-03-10T12:00:00+00:00",
            "params": params or {},
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    async def fetch_balance(self):
        return self._balance

    async def fetch_ticker(self, symbol):
        return {"symbol": symbol, "price": 100.0, "bid": 99.9, "ask": 100.1}


class TrackingBroker(MockBroker):
    def __init__(self):
        super().__init__()
        self.fetch_order_calls = 0

    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
        stop_price=None,
    ):
        return {
            "id": "order-track-1",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": type,
            "price": 100.0 if price is None else price,
            "status": "submitted",
            "filled": 0.0,
            "timestamp": "2026-03-10T12:00:00+00:00",
        }

    async def fetch_order(self, order_id, symbol=None):
        self.fetch_order_calls += 1
        return {
            "id": order_id,
            "symbol": symbol or "BTC/USDT",
            "side": "buy",
            "amount": 0.25,
            "type": "limit",
            "price": 101.0,
            "status": "filled" if self.fetch_order_calls >= 1 else "open",
            "filled": 0.25,
            "timestamp": "2026-03-10T12:00:05+00:00",
        }


def setup_function(_func):
    storage_db.engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    if REMOTE_DB_PATH.exists():
        REMOTE_DB_PATH.unlink()
    storage_db.configure_database(f"sqlite:///{DB_PATH.as_posix()}")
    storage_db.init_database()


def teardown_function(_func):
    storage_db.engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    if REMOTE_DB_PATH.exists():
        REMOTE_DB_PATH.unlink()


def test_market_data_repository_round_trips_candles():
    repo = MarketDataRepository()

    inserted = repo.save_candles(
        "BTC/USDT",
        "1h",
        [
            [1710000000000, 100.0, 101.0, 99.5, 100.5, 10.0],
            [1710003600000, 100.5, 102.0, 100.0, 101.5, 12.0],
        ],
        exchange="binanceus",
    )
    duplicate_inserted = repo.save_candles(
        "BTC/USDT",
        "1h",
        [
            [1710000000000, 100.0, 101.0, 99.5, 100.5, 10.0],
        ],
        exchange="binanceus",
    )
    candles = repo.get_candles("BTC/USDT", timeframe="1h", limit=10, exchange="binanceus")

    assert inserted == 2
    assert duplicate_inserted == 0
    assert len(candles) == 2
    assert candles[0][1:6] == [100.0, 101.0, 99.5, 100.5, 10.0]


def test_market_data_repository_filters_candles_by_date_range():
    repo = MarketDataRepository()

    repo.save_candles(
        "EUR/USD",
        "1d",
        [
            ["2026-03-10T00:00:00+00:00", 1.0, 1.1, 0.9, 1.05, 10.0],
            ["2026-03-11T00:00:00+00:00", 1.1, 1.2, 1.0, 1.15, 11.0],
            ["2026-03-12T00:00:00+00:00", 1.2, 1.3, 1.1, 1.25, 12.0],
        ],
        exchange="oanda:bid",
    )

    candles = repo.get_candles(
        "EUR/USD",
        timeframe="1d",
        limit=10,
        exchange="oanda:bid",
        start_time="2026-03-11",
        end_time="2026-03-12",
    )

    assert [row[0][:10] for row in candles] == ["2026-03-11", "2026-03-12"]


def test_market_data_repository_skips_invalid_rows_and_repairs_ohlc_bounds():
    repo = MarketDataRepository()

    inserted = repo.save_candles(
        "BTC/USDT",
        "1h",
        [
            [1710000000000, 100.0, 95.0, 105.0, 101.0, -5.0],
            [1710003600000, "bad", 106.0, 99.0, 103.0, 11.0],
            [1710007200000, 104.0, 108.0, 102.0, 107.0, None],
            [None, 105.0, 109.0, 103.0, 108.0, 9.0],
            [1710010800000, 0.0, 110.0, 104.0, 109.0, 7.0],
        ],
        exchange="coinbase",
    )

    candles = repo.get_candles("BTC/USDT", timeframe="1h", limit=10, exchange="coinbase")

    assert inserted == 2
    assert candles[0][1:6] == [100.0, 105.0, 95.0, 101.0, 0.0]
    assert candles[1][1:6] == [104.0, 108.0, 102.0, 107.0, 0.0]


def test_trade_audit_repository_records_recent_events():
    repo = TradeAuditRepository()

    repo.record_event(
        action="submit_attempt",
        status="pending",
        exchange="coinbase",
        account_label="Primary",
        symbol="BTC/USD:USD",
        requested_symbol="BTC/USD",
        side="buy",
        order_type="limit",
        venue="derivative",
        source="manual",
        message="Pre-trade review accepted.",
        payload={"reference_price": 105.0},
        timestamp="2026-03-17T09:30:00+00:00",
    )
    repo.record_event(
        action="submit_success",
        status="filled",
        exchange="coinbase",
        account_label="Primary",
        symbol="BTC/USD:USD",
        requested_symbol="BTC/USD",
        side="buy",
        order_type="limit",
        venue="derivative",
        source="manual",
        order_id="order-789",
        message="Order was accepted by the broker.",
        payload={"order_id": "order-789", "status": "filled"},
        timestamp="2026-03-17T09:31:00+00:00",
    )

    rows = repo.get_recent(limit=5)

    assert len(rows) == 2
    assert rows[0].action == "submit_success"
    assert rows[0].order_id == "order-789"
    assert rows[0].requested_symbol == "BTC/USD"
    assert '"status": "filled"' in str(rows[0].payload_json or "")


def test_execution_manager_persists_trade_history():
    broker = MockBroker()
    bus = EventBus()
    repo = TradeRepository()
    notifications = []
    manager = ExecutionManager(
        broker=broker,
        event_bus=bus,
        router=OrderRouter(broker),
        trade_repository=repo,
        trade_notifier=notifications.append,
    )

    execution = asyncio.run(
        manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.25,
            price=100.0,
            timeframe="15m",
            strategy_name="EMA Cross",
            signal_source_agent="SignalAgent2",
            consensus_status="unanimous",
            adaptive_weight=1.18,
            adaptive_score=0.46,
        )
    )
    trades = repo.get_trades(limit=10)

    assert execution["id"] == "order-123"
    assert len(trades) == 1
    assert trades[0].symbol == "BTC/USDT"
    assert trades[0].order_id == "order-123"
    assert trades[0].source == "bot"
    assert trades[0].timeframe == "15m"
    assert trades[0].strategy_name == "EMA Cross"
    assert trades[0].signal_source_agent == "SignalAgent2"
    assert trades[0].consensus_status == "unanimous"
    assert abs(float(trades[0].adaptive_weight) - 1.18) < 1e-9
    assert abs(float(trades[0].adaptive_score) - 0.46) < 1e-9
    assert notifications[0]["symbol"] == "BTC/USDT"
    assert notifications[0]["size"] == 0.25
    assert notifications[0]["source"] == "bot"
    assert notifications[0]["timeframe"] == "15m"
    assert notifications[0]["signal_source_agent"] == "SignalAgent2"


def test_execution_manager_updates_persisted_order_status_in_place():
    async def scenario():
        broker = TrackingBroker()
        bus = EventBus()
        repo = TradeRepository()
        manager = ExecutionManager(
            broker=broker,
            event_bus=bus,
            router=OrderRouter(broker),
            trade_repository=repo,
            trade_notifier=lambda *_args, **_kwargs: None,
        )
        manager._order_tracking_interval = 0.01
        manager._order_tracking_timeout = 0.25

        await manager.execute(symbol="BTC/USDT", side="buy", amount=0.25, type="limit", price=100.0)
        await asyncio.sleep(0.05)
        await manager.stop()

        trades = repo.get_trades(limit=10)
        assert len(trades) == 1
        assert trades[0].order_id == "order-track-1"
        assert trades[0].status == "filled"
        assert trades[0].price == 101.0
        assert trades[0].source == "bot"

    asyncio.run(scenario())


def test_trade_repository_round_trips_trade_journal_fields():
    repo = TradeRepository()

    trade = repo.save_trade(
        symbol="EUR/USD",
        side="BUY",
        quantity=1000,
        price=1.075,
        exchange="oanda",
        order_id="journal-1",
        status="filled",
        stop_loss=1.06,
        take_profit=1.09,
        reason="Breakout through London range",
        setup="Trend continuation after news compression",
        outcome="Win",
        lessons="Entry worked best once spread normalized.",
    )

    updated = repo.update_trade_journal(
        trade_id=trade.id,
        reason="Breakout retest with confirmation",
        stop_loss=1.061,
        take_profit=1.091,
        setup="Retest after breakout candle close",
        outcome="Strong win",
        lessons="Wait for retest instead of chasing first impulse.",
    )
    stored = repo.get_trades(limit=5)[0]

    assert updated is not None
    assert stored.order_id == "journal-1"
    assert stored.stop_loss == 1.061
    assert stored.take_profit == 1.091
    assert stored.reason == "Breakout retest with confirmation"
    assert stored.setup == "Retest after breakout candle close"
    assert stored.outcome == "Strong win"
    assert stored.lessons == "Wait for retest instead of chasing first impulse."


def test_trade_repository_derives_and_preserves_closed_trade_outcome():
    repo = TradeRepository()

    created = repo.save_or_update_trade(
        symbol="BTC/USDT",
        side="SELL",
        quantity=0.25,
        price=101.5,
        exchange="paper",
        order_id="close-1",
        status="closed",
        pnl=12.75,
    )
    refreshed = repo.save_or_update_trade(
        symbol="BTC/USDT",
        side="SELL",
        quantity=0.25,
        price=101.5,
        exchange="paper",
        order_id="close-1",
        status="closed",
    )

    assert created.outcome == "Win"
    assert refreshed.outcome == "Win"
    assert refreshed.pnl == 12.75


def test_trade_repository_filters_trade_history_by_exchange():
    repo = TradeRepository()

    repo.save_trade(
        symbol="BTC/USDT",
        side="BUY",
        quantity=0.1,
        price=100.0,
        exchange="paper",
        order_id="paper-1",
        status="filled",
    )
    repo.save_trade(
        symbol="BTC/USDT",
        side="BUY",
        quantity=0.2,
        price=101.0,
        exchange="coinbase",
        order_id="coinbase-1",
        status="filled",
    )

    paper_rows = repo.get_trades(limit=10, exchange="paper")
    coinbase_rows = repo.get_trades(limit=10, exchange="coinbase")

    assert len(paper_rows) == 1
    assert paper_rows[0].order_id == "paper-1"
    assert len(coinbase_rows) == 1
    assert coinbase_rows[0].order_id == "coinbase-1"


def test_database_runtime_reconfiguration_switches_repository_backend():
    local_repo = MarketDataRepository()
    remote_repo = MarketDataRepository()

    inserted_local = local_repo.save_candles(
        "BTC/USDT",
        "1h",
        [[1711000000000, 100.0, 101.0, 99.0, 100.5, 11.0]],
        exchange="binanceus",
    )

    storage_db.configure_database(f"sqlite:///{REMOTE_DB_PATH.as_posix()}")
    storage_db.init_database()

    inserted_remote = remote_repo.save_candles(
        "ETH/USDT",
        "1h",
        [[1711003600000, 200.0, 202.0, 198.5, 201.0, 15.0]],
        exchange="binanceus",
    )

    remote_rows = remote_repo.get_candles("ETH/USDT", timeframe="1h", limit=5, exchange="binanceus")
    local_rows_after_switch = remote_repo.get_candles("BTC/USDT", timeframe="1h", limit=5, exchange="binanceus")

    assert inserted_local == 1
    assert inserted_remote == 1
    assert storage_db.get_database_url().endswith("test_runtime_storage_remote.sqlite3")
    assert len(remote_rows) == 1
    assert local_rows_after_switch == []
