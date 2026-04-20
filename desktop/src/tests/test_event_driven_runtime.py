import asyncio
import importlib.util
import sys
from pathlib import Path
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from event_bus.event_bus import EventBus


def _load_event_driven_runtime():
    module_path = Path(__file__).resolve().parents[1] / "agents" / "event_driven_runtime.py"
    agents_package = types.ModuleType("agents")
    agents_package.__path__ = [str(module_path.parent)]
    signal_fanout = types.ModuleType("agents.signal_fanout")

    async def run_signal_agents_parallel(signal_agents, context):
        return dict(context or {})

    signal_fanout.run_signal_agents_parallel = run_signal_agents_parallel
    sys.modules.setdefault("agents", agents_package)
    sys.modules["agents.signal_fanout"] = signal_fanout

    spec = importlib.util.spec_from_file_location("tests.event_driven_runtime_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.EventDrivenAgentRuntime


EventDrivenAgentRuntime = _load_event_driven_runtime()


class _SignalAgent:
    async def process(self, context):
        updated = dict(context or {})
        updated["signal"] = {
            "decision_id": updated.get("decision_id"),
            "symbol": updated.get("symbol"),
            "side": "buy",
            "amount": 0.1,
            "price": 100.0,
            "confidence": 0.82,
            "strategy_name": "runtime-test",
            "reason": "compatibility check",
        }
        return updated


class _RiskAgent:
    async def process(self, context):
        updated = dict(context or {})
        updated["trade_review"] = {"approved": True, "reason": "ok"}
        return updated


class _ExecutionAgent:
    async def process(self, context):
        updated = dict(context or {})
        updated["execution_result"] = {"status": "filled", "reason": "submitted"}
        return updated


def test_event_driven_runtime_uses_background_event_bus_when_started():
    async def scenario():
        runtime = EventDrivenAgentRuntime(
            bus=EventBus(),
            signal_agent=_SignalAgent(),
            risk_agent=_RiskAgent(),
            execution_agent=_ExecutionAgent(),
        )

        await runtime.start()
        assert runtime.bus.is_running is True

        result = await asyncio.wait_for(
            runtime.process_market_data(
                {
                    "decision_id": "decision-1",
                    "symbol": "BTC/USDT",
                    "timeframe": "1m",
                },
                timeout=0.25,
            ),
            timeout=0.5,
        )

        await runtime.stop()
        return result, runtime.bus.is_running

    result, bus_running = asyncio.run(scenario())

    assert result["signal"]["strategy_name"] == "runtime-test"
    assert result["trade_review"]["approved"] is True
    assert result["execution_result"]["status"] == "filled"
    assert bus_running is False
