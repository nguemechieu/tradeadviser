import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.multi_symbol_orchestrator as orchestrator_module
from core.multi_symbol_orchestrator import MultiSymbolOrchestrator


class _DummyWorker:
    def __init__(
        self,
        symbol,
        broker,
        strategy,
        execution_manager,
        timeframe,
        limit,
        controller=None,
        startup_delay=0.0,
        poll_interval=2.0,
        signal_processor=None,
    ):
        self.symbol = symbol
        self.signal_processor = signal_processor
        self.running = True

    async def run(self):
        while self.running:
            await asyncio.sleep(0.01)


class _DummySystemState:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _DummyTradingEngine:
    def __init__(self, *args, **kwargs):
        self.stop_calls = 0

    async def stop(self):
        self.stop_calls += 1


class _DummyPortfolioManager:
    def __init__(self, event_bus):
        self.event_bus = event_bus


class _DummyMarketDataEngine:
    def __init__(self, broker, event_bus):
        self.broker = broker
        self.event_bus = event_bus


class _DummyEventBus:
    pass


class _DummyScheduler:
    pass


def _patch_dependencies(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "SymbolWorker", _DummyWorker)
    monkeypatch.setattr(orchestrator_module, "SystemState", _DummySystemState)
    monkeypatch.setattr(orchestrator_module, "TradingEngine", _DummyTradingEngine)
    monkeypatch.setattr(orchestrator_module, "PortfolioManager", _DummyPortfolioManager)
    monkeypatch.setattr(orchestrator_module, "MarketDataEngine", _DummyMarketDataEngine)
    monkeypatch.setattr(orchestrator_module, "EventBus", _DummyEventBus)
    monkeypatch.setattr(orchestrator_module, "Scheduler", _DummyScheduler)


def test_multi_symbol_orchestrator_requires_symbols(monkeypatch):
    _patch_dependencies(monkeypatch)
    orchestrator = MultiSymbolOrchestrator(
        controller=SimpleNamespace(),
        broker=object(),
        strategy=object(),
        execution_manager=object(),
        risk_engine=object(),
    )

    async def scenario():
        with pytest.raises(RuntimeError, match="No symbols provided"):
            await orchestrator.start()

    asyncio.run(scenario())


def test_multi_symbol_orchestrator_spawns_and_shuts_down_workers(monkeypatch):
    _patch_dependencies(monkeypatch)
    processor = lambda *args, **kwargs: None
    orchestrator = MultiSymbolOrchestrator(
        controller=SimpleNamespace(),
        broker=object(),
        strategy=object(),
        execution_manager=object(),
        risk_engine=object(),
        signal_processor=processor,
    )

    async def scenario():
        start_task = asyncio.create_task(orchestrator.start(["BTC/USDT", "ETH/USDT"]))
        await asyncio.sleep(0.05)

        assert len(orchestrator.workers) == 2
        assert all(worker.signal_processor is processor for worker in orchestrator.workers)

        await orchestrator.shutdown()

        with pytest.raises(asyncio.CancelledError):
            await start_task

        assert orchestrator.state.stopped is True
        assert orchestrator.engine.stop_calls == 1
        assert orchestrator.worker_tasks == []

    asyncio.run(scenario())
