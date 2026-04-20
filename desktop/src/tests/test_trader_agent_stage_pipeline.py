import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.agents.trader_agent import InvestorProfile
from sopotek.core.event_types import EventType
from sopotek.core.models import FeatureVector, Signal
from sopotek.core.orchestrator import SopotekRuntime


async def _drain(bus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class DummyBroker:
    def __init__(self) -> None:
        self.orders = []

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        return []

    async def place_order(self, order):
        self.orders.append(order)
        return {
            "id": f"order-{len(self.orders)}",
            "status": "filled",
            "price": order.price,
            "fill_price": order.price,
            "filled_quantity": order.quantity,
            "remaining_quantity": 0.0,
            "partial": False,
        }

    async def stream_ticks(self, symbol: str):
        if False:
            yield {"symbol": symbol, "price": 0.0}


def _build_runtime() -> SopotekRuntime:
    return SopotekRuntime(
        broker=DummyBroker(),
        starting_equity=100000.0,
        enable_default_agents=False,
        enable_trader_agent=True,
        trader_profiles={
            "growth": InvestorProfile(
                risk_level="medium",
                goal="growth",
                max_drawdown=0.10,
                trade_frequency="medium",
                preferred_assets=["BTC/USDT"],
                time_horizon="medium",
            )
        },
        active_trader_profile="growth",
    )


def test_stage_pipeline_emits_signal_validation_decision_risk_and_execution_events():
    async def scenario():
        runtime = _build_runtime()
        created = []
        validated = []
        decisions = []
        approved = []
        executed = []

        runtime.bus.subscribe(EventType.SIGNAL_CREATED, lambda event: created.append(event.data))
        runtime.bus.subscribe(EventType.SIGNAL_VALIDATED, lambda event: validated.append(event.data))
        runtime.bus.subscribe(EventType.DECISION_MADE, lambda event: decisions.append(event.data))
        runtime.bus.subscribe(EventType.RISK_APPROVED, lambda event: approved.append(event.data))
        runtime.bus.subscribe(EventType.ORDER_EXECUTED, lambda event: executed.append(event.data))

        await runtime.bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await runtime.bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={
                    "rsi": 34.0,
                    "ema_gap": 0.025,
                    "volatility": 0.01,
                    "order_book_imbalance": 0.18,
                    "volume_ratio": 1.1,
                },
            ),
            priority=45,
        )
        await runtime.bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.78,
                strategy_name="trend_following",
                reason="trend continuation",
                metadata={"timeframe": "1m"},
            ),
            priority=61,
        )
        await _drain(runtime.bus)
        return runtime, created, validated, decisions, approved, executed

    runtime, created, validated, decisions, approved, executed = asyncio.run(scenario())

    assert created
    assert validated
    assert decisions
    assert approved
    assert executed
    assert decisions[-1].id == created[-1].id
    assert approved[-1].metadata["signal_id"] == decisions[-1].id
    assert approved[-1].metadata["signal_status"] == "APPROVED"
    assert executed[-1].metadata["signal_id"] == decisions[-1].id
    assert runtime.broker.orders


def test_risk_engine_is_the_final_gate_after_decision_stage():
    async def scenario():
        runtime = _build_runtime()
        runtime.trader_agent.loss_streak_by_profile["growth"] = 3
        decision_signals = []
        rejected = []

        runtime.bus.subscribe(EventType.DECISION_MADE, lambda event: decision_signals.append(event.data))
        runtime.bus.subscribe(EventType.RISK_REJECTED, lambda event: rejected.append(event.data))

        await runtime.bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await runtime.bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={"rsi": 34.0, "ema_gap": 0.02, "volatility": 0.01, "order_book_imbalance": 0.15},
            ),
            priority=45,
        )
        await runtime.bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.80,
                strategy_name="trend_following",
                reason="trend continuation",
                metadata={"timeframe": "1m"},
            ),
            priority=61,
        )
        await _drain(runtime.bus)
        return runtime, decision_signals, rejected

    runtime, decision_signals, rejected = asyncio.run(scenario())

    assert decision_signals
    assert rejected
    assert rejected[-1].reason == "Loss-streak pause triggered by centralized risk engine"
    assert runtime.broker.orders == []
