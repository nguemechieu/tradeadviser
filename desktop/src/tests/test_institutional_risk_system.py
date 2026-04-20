import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.order_executor import OrderExecutor
from execution.virtual_trade_manager import VirtualTradeManager
from journal.trade_journal import TradeJournal
from monitoring.portfolio_monitor import PortfolioMonitor
from monitoring.trade_watcher import TradeWatcher
from risk.exposure_manager import ExposureManager
from risk.institutional_risk_engine import InstitutionalRiskEngine, InstitutionalRiskLimits
from sopotek.brokers.paper import PaperBroker
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import ExecutionReport, Signal
from sopotek.engines.market_data import MarketDataEngine
from sopotek.engines.portfolio import PortfolioEngine
from sopotek.engines.strategy import BaseStrategy, StrategyEngine, StrategyRegistry


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class CapturingPaperBroker(PaperBroker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received_orders = []

    async def place_order(self, order):
        self.received_orders.append(order)
        return await super().place_order(order)


class SingleSignalStrategy(BaseStrategy):
    name = "single_signal"

    def __init__(self) -> None:
        self.emitted = False

    async def generate_signal(self, *, symbol: str, trigger: str, payload):
        if self.emitted or trigger != EventType.MARKET_TICK:
            return None
        price = float(getattr(payload, "price", None) or payload.get("price") or 0.0)
        if price <= 0.0:
            return None
        self.emitted = True
        return Signal(
            symbol=symbol,
            side="buy",
            quantity=500.0,
            price=price,
            strategy_name=self.name,
            reason="Initial breakout",
            stop_price=price - 5.0,
            metadata={
                "risk_reward_ratio": 2.0,
                "entry_reason": "Breakout through resistance",
                "signal_data": {"setup": "breakout"},
            },
        )


def _build_runtime(tmp_path, *, starting_cash=100000.0, max_daily_loss_pct=0.03):
    bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
    broker = CapturingPaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
    market_data = MarketDataEngine(broker, bus)
    PortfolioEngine(bus, starting_cash=starting_cash)
    exposure_manager = ExposureManager()
    portfolio_monitor = PortfolioMonitor(
        bus,
        exposure_manager=exposure_manager,
        max_daily_loss_pct=max_daily_loss_pct,
        starting_equity=starting_cash,
    )
    risk_engine = InstitutionalRiskEngine(
        bus,
        exposure_manager=exposure_manager,
        portfolio_monitor=portfolio_monitor,
        limits=InstitutionalRiskLimits(
            max_risk_per_trade_pct=0.01,
            max_position_exposure_pct=0.30,
            max_trade_drawdown_pct=0.05,
            max_daily_loss_pct=max_daily_loss_pct,
            allow_quantity_resize=True,
        ),
        starting_equity=starting_cash,
    )
    journal = TradeJournal(database_url=f"sqlite:///{(tmp_path / 'institutional_journal.db').as_posix()}")
    virtual_trade_manager = VirtualTradeManager(bus, journal=journal, close_retry_seconds=0.25)
    order_executor = OrderExecutor(broker, bus, virtual_trade_manager)
    watcher = TradeWatcher(bus, virtual_trade_manager, poll_interval=0.01)
    _ = (risk_engine, order_executor)
    return bus, broker, market_data, journal, virtual_trade_manager, watcher


def test_institutional_pipeline_uses_virtual_exits_and_updates_journal(tmp_path):
    async def scenario():
        bus, broker, market_data, journal, virtual_trade_manager, watcher = _build_runtime(tmp_path)
        registry = StrategyRegistry()
        registry.register(SingleSignalStrategy())
        StrategyEngine(bus, registry)

        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 100.0})
        await _drain(bus)

        open_trades = virtual_trade_manager.list_open_trades("BTC/USDT")
        assert len(open_trades) == 1
        trade = open_trades[0]

        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 94.0})
        await _drain(bus)
        await watcher.check_once()
        await _drain(bus)

        return {
            "broker": broker,
            "trade": trade,
            "journal_row": journal.fetch_trade(trade.trade_id),
            "open_trades": virtual_trade_manager.list_open_trades("BTC/USDT"),
        }

    result = asyncio.run(scenario())

    assert len(result["broker"].received_orders) == 2
    assert result["broker"].received_orders[0].stop_price is None
    assert result["broker"].received_orders[0].take_profit is None
    assert result["broker"].received_orders[1].stop_price is None
    assert result["broker"].received_orders[1].take_profit is None
    assert result["broker"].received_orders[0].quantity == pytest.approx(200.0)
    assert result["journal_row"] is not None
    assert result["journal_row"].status == "closed"
    assert result["journal_row"].exit_reason == "Virtual stop loss hit"
    assert result["journal_row"].pnl == pytest.approx(-1200.0)
    assert result["open_trades"] == []


def test_daily_loss_limit_blocks_new_trades(tmp_path):
    async def scenario():
        bus, broker, market_data, _, _, watcher = _build_runtime(
            tmp_path,
            starting_cash=10000.0,
            max_daily_loss_pct=0.005,
        )
        rejections = []
        bus.subscribe(EventType.RISK_REJECTED, lambda event: rejections.append(event.data))

        first_signal = Signal(
            symbol="ETH/USDT",
            side="buy",
            quantity=100.0,
            price=100.0,
            strategy_name="manual",
            reason="Opening trade",
            stop_price=95.0,
            metadata={"risk_reward_ratio": 2.0, "entry_reason": "First trade"},
        )
        await bus.publish(EventType.SIGNAL, first_signal, priority=60, source="test")
        await _drain(bus)

        await market_data.publish_tick("ETH/USDT", {"symbol": "ETH/USDT", "price": 94.0})
        await _drain(bus)
        await watcher.check_once()
        await _drain(bus)

        second_signal = Signal(
            symbol="ETH/USDT",
            side="buy",
            quantity=100.0,
            price=100.0,
            strategy_name="manual",
            reason="Second attempt",
            stop_price=95.0,
            metadata={"risk_reward_ratio": 2.0, "entry_reason": "Second trade"},
        )
        await bus.publish(EventType.SIGNAL, second_signal, priority=60, source="test")
        await _drain(bus)

        return broker, rejections

    broker, rejections = asyncio.run(scenario())

    assert len(broker.received_orders) == 2
    assert rejections
    assert "daily loss" in rejections[-1].reason.lower()


def test_virtual_trade_manager_promotes_break_even_and_trailing_stop():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        close_requests = []
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))
        manager = VirtualTradeManager(bus, close_retry_seconds=0.25)
        report = ExecutionReport(
            order_id="trade-1",
            symbol="SOL/USDT",
            side="buy",
            quantity=1.0,
            requested_price=100.0,
            fill_price=100.0,
            status="filled",
            latency_ms=0.0,
            strategy_name="trail_test",
            stop_price=95.0,
            take_profit=110.0,
            filled_quantity=1.0,
            metadata={
                "trade_id": "trade-1",
                "risk_amount": 100.0,
                "stop_distance": 5.0,
                "risk_reward_ratio": 2.0,
                "trailing_stop_distance": 5.0,
                "break_even_trigger_distance": 5.0,
                "entry_reason": "Momentum ignition",
            },
        )
        await manager.register_entry(report)
        await manager.check_exit_conditions({"SOL/USDT": 106.0})
        trade = manager.get_trade("trade-1")
        await manager.check_exit_conditions({"SOL/USDT": 101.0})
        await _drain(bus)
        return trade, close_requests

    trade, close_requests = asyncio.run(scenario())

    assert trade is not None
    assert trade.break_even_armed is True
    assert trade.virtual_stop_loss == pytest.approx(101.0)
    assert trade.state == "closing"
    assert len(close_requests) == 1
    assert close_requests[0].reason == "Virtual stop loss hit"
