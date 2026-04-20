import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.distributed_orchestrator as orchestrator_module
from core.distributed_orchestrator import DistributedOrchestrator


class _DummyProcess:
    def __init__(self, target=None, args=()):
        self.target = target
        self.args = args
        self.started = False
        self.terminated = False
        self.joined = False

    def start(self):
        self.started = True

    def terminate(self):
        self.terminated = True

    def join(self, timeout=None):
        self.joined = True


def test_distributed_orchestrator_skips_unpicklable_controller():
    controller = SimpleNamespace(handle_trade_execution=lambda trade: trade)
    orchestrator = DistributedOrchestrator(controller=controller, max_workers=2)

    started = orchestrator.start(["BTC/USDT", "ETH/USDT"])

    assert started is False
    assert orchestrator.processes == []
    assert orchestrator.last_error is not None


def test_distributed_orchestrator_starts_picklable_processes(monkeypatch):
    monkeypatch.setattr(orchestrator_module.mp, "Process", _DummyProcess)
    controller = SimpleNamespace(name="controller")
    orchestrator = DistributedOrchestrator(controller=controller, max_workers=2)

    started = orchestrator.start(["BTC/USDT", "ETH/USDT", "SOL/USDT"])

    assert started is True
    assert len(orchestrator.processes) == 2
    assert all(process.started for process in orchestrator.processes)

    processes = list(orchestrator.processes)
    orchestrator.stop()

    assert all(process.terminated for process in processes)
    assert all(process.joined for process in processes)
    assert orchestrator.processes == []
