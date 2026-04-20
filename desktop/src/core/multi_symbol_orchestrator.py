import asyncio
import contextlib

from core.scheduler.scheduler import Scheduler
from core.system_state import SystemState
from worker.symbol_worker import SymbolWorker
from  engines.trading_engine import TradingEngine
from  manager.portfolio_manager import PortfolioManager
from  event_bus.event_bus import  EventBus
from engines.market_data_engine import MarketDataEngine
class MultiSymbolOrchestrator:

    def __init__(self,controller, broker, strategy, execution_manager, risk_engine, signal_processor=None):
        self.controller = controller

        self.broker = broker
        self.event_bus=EventBus()
        self.strategy = strategy
        self.execution_manager = execution_manager
        self.signal_processor = signal_processor
        self.portfolio_manager=PortfolioManager(self.event_bus)
        self.market_data_engine=MarketDataEngine(self.broker,self.event_bus)
        self.risk_engine=risk_engine

        self.engine = TradingEngine( self.market_data_engine,
                                     self.strategy,
                                     self.risk_engine,
                                     self.execution_manager,
                                     self.portfolio_manager)

        self.state = SystemState()

        self.scheduler = Scheduler()

        self.workers = []
        self.worker_tasks = []

    async def start(self, symbols=None):

        if symbols is None:

            raise RuntimeError("No symbols provided")

        tasks = []
        timeframe = "1h"
        limit = 240
        for offset, symbol in enumerate(symbols):

            worker = SymbolWorker(
                symbol,
                self.broker,
                self.strategy,
                self.execution_manager,
                timeframe,
                limit,
                controller=self.controller,
                startup_delay=(offset % 6) * 0.35,
                poll_interval=6.0,
                signal_processor=self.signal_processor,
            )

            self.workers.append(worker)

            tasks.append(asyncio.create_task(worker.run(), name=f"symbol_worker:{symbol}"))

        self.worker_tasks = tasks
        try:
            await asyncio.gather(*tasks)
        finally:
            self.worker_tasks = [task for task in tasks if not task.done()]




    # ===================================
    # STOP SYSTEM
    # ===================================

    async def shutdown(self):
        self.state.stop()

        for worker in list(self.workers):
            try:
                worker.running = False
            except Exception:
                pass

        tasks = list(getattr(self, "worker_tasks", []) or [])
        self.worker_tasks = []
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        await self.engine.stop()

        print("Trading system stopped")
