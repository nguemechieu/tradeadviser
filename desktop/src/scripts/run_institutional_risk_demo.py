from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from execution.order_executor import OrderExecutor
from execution.virtual_trade_manager import VirtualTradeManager
from journal.trade_journal import TradeJournal
from monitoring.portfolio_monitor import PortfolioMonitor
from monitoring.trade_watcher import TradeWatcher
from risk.exposure_manager import ExposureManager
from risk.institutional_risk_engine import InstitutionalRiskEngine
from sopotek.brokers.paper import PaperBroker
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.models import Signal
from sopotek.engines.market_data import MarketDataEngine
from sopotek.engines.portfolio import PortfolioEngine
from sopotek.engines.strategy import BaseStrategy, StrategyEngine, StrategyRegistry


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class DemoBreakoutStrategy(BaseStrategy):
    name = "institutional_demo_breakout"

    def __init__(self) -> None:
        self._emitted = False

    async def generate_signal(self, *, symbol: str, trigger: str, payload):
        if self._emitted or trigger != "MARKET_TICK":
            return None
        price = float(getattr(payload, "price", None) or payload.get("price") or 0.0)
        if price <= 0.0:
            return None
        self._emitted = True
        return Signal(
            symbol=symbol,
            side="buy",
            quantity=500.0,
            price=price,
            strategy_name=self.name,
            reason="Desktop breakout confirmation",
            stop_price=price - 5.0,
            metadata={
                "risk_reward_ratio": 2.0,
                "entry_reason": "Breakout through local resistance",
                "signal_data": {"timeframe": "1m", "regime": "trend"},
            },
        )


async def main() -> None:
    bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
    broker = PaperBroker(partial_fill_probability=0.0, slippage_bps=0.0)
    market_data = MarketDataEngine(broker, bus)
    PortfolioEngine(bus, starting_cash=100000.0)

    exposure_manager = ExposureManager()
    portfolio_monitor = PortfolioMonitor(bus, exposure_manager=exposure_manager, max_daily_loss_pct=0.03)
    risk_engine = InstitutionalRiskEngine(
        bus,
        exposure_manager=exposure_manager,
        portfolio_monitor=portfolio_monitor,
    )
    journal = TradeJournal(database_url="sqlite:///data/institutional_demo_journal.db")
    virtual_trade_manager = VirtualTradeManager(bus, journal=journal)
    order_executor = OrderExecutor(broker, bus, virtual_trade_manager)
    watcher = TradeWatcher(bus, virtual_trade_manager, poll_interval=0.05)

    registry = StrategyRegistry()
    registry.register(DemoBreakoutStrategy())
    StrategyEngine(bus, registry)

    _ = (risk_engine, order_executor)

    await watcher.start()
    await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 100.0})
    await _drain(bus)

    await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 111.0})
    await _drain(bus)
    await watcher.check_once()
    await _drain(bus)
    await watcher.stop()

    print("Broker orders:", broker.order_log)
    print("Journal rows:", journal.list_trades(limit=10))


if __name__ == "__main__":
    asyncio.run(main())
