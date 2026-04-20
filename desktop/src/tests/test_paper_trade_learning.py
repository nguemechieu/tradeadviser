import asyncio
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB_PATH = Path(__file__).resolve().parent / "test_paper_trade_learning.sqlite3"
os.environ["SOPOTEK_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from event_bus.event_bus import EventBus
from event_bus.event_types import EventType
from execution.execution_manager import ExecutionManager
from execution.order_router import OrderRouter
from paper_learning import PaperTradeDatasetBuilder, PaperTradingLearningService
from storage import database as storage_db
from storage.paper_trade_learning_repository import PaperTradeLearningRepository


def _sample_candles(count=80):
    base = 1710000000000
    candles = []
    close = 100.0
    for index in range(count):
        open_ = close
        close = close + (0.6 if index % 4 else 1.1)
        high = max(open_, close) + 0.45
        low = min(open_, close) - 0.45
        volume = 100.0 + (index * 2.0)
        candles.append([base + (index * 3600000), open_, high, low, close, volume])
    return candles


class MockPaperBroker:
    exchange_name = "paper"

    def __init__(self):
        self.orders = []
        self._balance = {"free": {"USDT": 100000.0, "BTC": 10.0}}
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
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        order_id = f"paper-order-{len(self.orders) + 1}"
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": type,
            "price": 100.0 if price is None else price,
            "status": "filled",
            "timestamp": "2026-03-31T13:00:00+00:00",
            "params": params or {},
            "stop_price": stop_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        self.orders.append(order)
        return order

    async def fetch_balance(self):
        return self._balance

    async def fetch_ticker(self, symbol):
        return {"symbol": symbol, "price": 100.0, "bid": 99.9, "ask": 100.1}


def setup_function(_func):
    storage_db.engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    storage_db.configure_database(f"sqlite:///{DB_PATH.as_posix()}")
    storage_db.init_database()


def teardown_function(_func):
    storage_db.engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_paper_trade_learning_repository_round_trips_append_only_rows():
    repo = PaperTradeLearningRepository()

    event_row = repo.append_trade_event(
        event_type="signal_received",
        symbol="BTC/USDT",
        decision_id="decision-1",
        exchange="paper",
        source="bot",
        strategy_name="EMA Cross",
        timeframe="1h",
        side="BUY",
        signal="BUY",
        confidence=0.72,
        payload={"reason": "trend alignment"},
        timestamp="2026-03-31T12:00:00+00:00",
    )
    record_row = repo.append_trade_record(
        trade_id="trade-1",
        decision_id="decision-1",
        symbol="BTC/USDT",
        exchange="paper",
        source="bot",
        strategy_name="EMA Cross",
        timeframe="1h",
        signal="BUY",
        side="BUY",
        market_regime="trending_up",
        volatility_regime="medium",
        feature_version="quant-v1",
        outcome="WIN",
        signal_timestamp="2026-03-31T12:00:00+00:00",
        entry_timestamp="2026-03-31T12:05:00+00:00",
        exit_timestamp="2026-03-31T13:05:00+00:00",
        duration_seconds=3600.0,
        quantity=1.0,
        entry_price=100.0,
        exit_price=104.5,
        pnl=4.5,
        pnl_pct=0.045,
        confidence=0.72,
        feature_values={"rsi": 63.0, "ema_fast": 103.0, "ema_slow": 101.0, "atr": 1.2},
        regime_snapshot={"regime": "trending_up", "volatility": "medium"},
        metadata={"reason": "trend alignment"},
    )

    events = repo.get_trade_events(limit=10, symbol="BTC/USDT")
    records = repo.get_trade_records(limit=10, symbol="BTC/USDT", exchange="paper")

    assert event_row.event_type == "signal_received"
    assert record_row.trade_id == "trade-1"
    assert len(events) == 1
    assert events[0].payload_json["reason"] == "trend alignment"
    assert len(records) == 1
    assert records[0].outcome == "WIN"
    assert abs(float(records[0].rsi) - 63.0) < 1e-9
    assert records[0].regime_json["regime"] == "trending_up"


def test_paper_trading_learning_service_records_closed_trade_and_builds_dataset():
    async def scenario():
        broker = MockPaperBroker()
        bus = EventBus()
        repo = PaperTradeLearningRepository()
        service = PaperTradingLearningService(
            event_bus=bus,
            repository=repo,
            exchange_resolver=lambda: "paper",
            tracked_sources={"bot"},
        )
        manager = ExecutionManager(
            broker=broker,
            event_bus=bus,
            router=OrderRouter(broker),
        )

        candles = _sample_candles()
        signal_context = {
            "decision_id": "buy-1",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "candles": candles,
            "signal": {
                "decision_id": "buy-1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "confidence": 0.74,
                "strategy_name": "EMA Cross",
                "reason": "Trend and momentum aligned",
                "timeframe": "1h",
                "source": "bot",
                "price": 100.0,
            },
        }
        exit_context = {
            "decision_id": "sell-1",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "candles": candles,
            "signal": {
                "decision_id": "sell-1",
                "symbol": "BTC/USDT",
                "side": "sell",
                "confidence": 0.61,
                "strategy_name": "EMA Cross",
                "reason": "Mean reversion target reached",
                "timeframe": "1h",
                "source": "bot",
                "price": 105.0,
            },
        }

        bus.run_in_background()
        await bus.publish(EventType.SIGNAL, signal_context)
        await asyncio.sleep(0.05)

        await manager.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            price=100.0,
            source="bot",
            decision_id="buy-1",
            strategy_name="EMA Cross",
            timeframe="1h",
            confidence=0.74,
            exchange="paper",
        )
        await asyncio.sleep(0.05)

        await bus.publish(EventType.SIGNAL, exit_context)
        await asyncio.sleep(0.05)

        await manager.execute(
            symbol="BTC/USDT",
            side="sell",
            amount=1.0,
            price=105.0,
            source="bot",
            decision_id="sell-1",
            strategy_name="EMA Cross",
            timeframe="1h",
            confidence=0.61,
            exchange="paper",
        )
        await asyncio.sleep(0.1)

        records = repo.get_trade_records(limit=10, symbol="BTC/USDT", exchange="paper")
        events = repo.get_trade_events(limit=30, symbol="BTC/USDT")

        assert service is not None
        assert len(records) == 1
        assert records[0].symbol == "BTC/USDT"
        assert records[0].outcome == "WIN"
        assert abs(float(records[0].pnl) - 5.0) < 1e-9
        assert records[0].feature_version == "quant-v1"
        assert records[0].features_json["rsi"] >= 0.0

        event_types = {row.event_type for row in events}
        assert {"signal_received", "execution_report", "trade_opened", "trade_closed"}.issubset(event_types)

        dataset = PaperTradeDatasetBuilder(repository=repo).build_dataset(
            symbol="BTC/USDT",
            strategy_name="EMA Cross",
            timeframe="1h",
            exchange="paper",
        )

        assert not dataset.empty
        assert "signal_is_buy" in dataset.feature_columns
        assert "confidence" in dataset.feature_columns
        assert int(dataset.frame.iloc[0]["target"]) == 1
        assert abs(float(dataset.frame.iloc[0]["pnl"]) - 5.0) < 1e-9

        await manager.stop()
        await bus.shutdown()

    asyncio.run(scenario())
