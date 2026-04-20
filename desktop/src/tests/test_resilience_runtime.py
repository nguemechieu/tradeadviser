import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SOPOTEK_METRICS_ENABLED"] = "0"

from broker.broker_errors import BrokerOperationError
from event_bus.event_bus import EventBus
from execution.execution_engine import ExecutionEngine
from execution.execution_manager import ExecutionManager
from execution.order_router import OrderRouter
from sopotek.core.event_bus import AsyncEventBus
from sopotek.core.models import TradeReview
import sopotek.observability.prometheus as prometheus_module
from sopotek.observability.prometheus import PrometheusMonitoringService
from sopotek.resilience import CircuitBreaker, CircuitBreakerOpenError
from sopotek.resilience.dead_letter import DLQReprocessor, DeadLetterPublisher

prometheus_module._monitoring_service = None


class _RecordingProducer:
    def __init__(self) -> None:
        self.messages = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send_and_wait(self, topic, payload) -> None:
        self.messages.append((topic, payload))


class _FailingBroker:
    def __init__(self) -> None:
        self.calls = 0

    async def place_order(self, order):
        self.calls += 1
        raise RuntimeError("venue unavailable")


class _RateLimitedManagerBroker:
    def __init__(self) -> None:
        self.calls = 0
        exchange = type("Exchange", (), {})()
        exchange.markets = {}
        exchange.amount_to_precision = lambda symbol, amount: amount
        self.exchange = exchange
        self.exchange_name = "paper"

    async def create_order(self, *args, **kwargs):
        self.calls += 1
        raise BrokerOperationError(
            "broker transport failed",
            category="broker_error",
            retryable=True,
            cooldown_seconds=0,
        )

    async def fetch_balance(self):
        return {"free": {"USDT": 1000.0}}

    async def fetch_ticker(self, symbol):
        return {"symbol": symbol, "price": 100.0, "bid": 100.0, "ask": 100.0}


def test_circuit_breaker_opens_then_recovers():
    async def scenario():
        breaker = CircuitBreaker(
            "broker:alpha",
            failure_threshold=2,
            recovery_timeout_seconds=0.01,
        )

        await breaker.before_call()
        await breaker.record_failure(RuntimeError("first"))
        assert breaker.state.value == "closed"

        await breaker.before_call()
        await breaker.record_failure(RuntimeError("second"))
        assert breaker.state.value == "open"

        with pytest.raises(CircuitBreakerOpenError):
            await breaker.before_call()

        await asyncio.sleep(0.02)
        await breaker.before_call()
        assert breaker.state.value == "half_open"
        await breaker.record_success()
        assert breaker.state.value == "closed"

    asyncio.run(scenario())


def test_event_bus_failures_publish_to_dlq():
    async def scenario():
        producer = _RecordingProducer()
        publisher = DeadLetterPublisher(producer=producer)
        bus = AsyncEventBus()
        bus.set_failure_handler(publisher.handle_failed_event)

        async def broken_handler(event):
            raise RuntimeError(f"unable to process {event.type}")

        bus.subscribe("BROKEN_EVENT", broken_handler)
        bus.run_in_background()
        await bus.publish("BROKEN_EVENT", {"symbol": "BTC/USDT"}, source="unit_test")
        await asyncio.sleep(0.05)
        await bus.shutdown()
        return producer.messages

    messages = asyncio.run(scenario())

    assert len(messages) == 1
    topic, payload = messages[0]
    assert topic == "sopotek.dead_letter"
    assert payload["original_event"]["type"] == "BROKEN_EVENT"
    assert payload["retry_count"] == 0
    assert payload["failure"]["handler"] == "broken_handler"


def test_dlq_reprocessor_reinjects_with_incremented_retry_count():
    async def scenario():
        bus = AsyncEventBus()
        received = []
        bus.subscribe("BROKEN_EVENT", lambda event: received.append(event))
        bus.run_in_background()
        reprocessor = DLQReprocessor(bus, max_retry_count=3, consumer=object())

        success = await reprocessor.reprocess_payload(
            {
                "retry_count": 1,
                "failure": {"stage": "event_delivery"},
                "original_event": {
                    "type": "BROKEN_EVENT",
                    "data": {"symbol": "ETH/USDT"},
                    "priority": 42,
                    "metadata": {},
                    "correlation_id": "corr-123",
                },
            }
        )
        await asyncio.sleep(0.05)
        await bus.shutdown()
        return success, received

    success, received = asyncio.run(scenario())

    assert success is True
    assert len(received) == 1
    assert received[0].data["symbol"] == "ETH/USDT"
    assert received[0].metadata["dlq"]["retry_count"] == 2


def test_dlq_reprocessor_drops_messages_at_retry_limit():
    async def scenario():
        bus = AsyncEventBus()
        received = []
        bus.subscribe("BROKEN_EVENT", lambda event: received.append(event))
        reprocessor = DLQReprocessor(bus, max_retry_count=2, consumer=object())
        success = await reprocessor.reprocess_payload(
            {
                "retry_count": 2,
                "failure": {"stage": "event_delivery"},
                "original_event": {
                    "type": "BROKEN_EVENT",
                    "data": {"symbol": "SOL/USDT"},
                    "priority": 50,
                    "metadata": {},
                },
            }
        )
        return success, received

    success, received = asyncio.run(scenario())

    assert success is False
    assert received == []


def test_prometheus_monitoring_service_renders_required_metrics():
    service = PrometheusMonitoringService(enabled=False, port=8001)
    service.observe_event_latency(event_type="MARKET_TICK", source="feed", latency_ms=12.5)
    service.observe_execution_time(component="execution_engine", venue="paper", status="filled", duration_seconds=0.15)
    service.increment_error_count(component="event_bus", error_type="RuntimeError")
    service.set_circuit_state(breaker="execution_engine:paper", state="open")
    body = service.render_latest()

    assert "sopotek_event_latency_ms" in body
    assert "sopotek_execution_time_seconds" in body
    assert "sopotek_error_total" in body
    assert "sopotek_circuit_breaker_state" in body


def test_execution_engine_circuit_breaker_blocks_after_threshold():
    async def scenario():
        broker = _FailingBroker()
        engine = ExecutionEngine(
            broker,
            max_retries=1,
            circuit_failure_threshold=2,
            circuit_recovery_timeout_seconds=60.0,
        )
        review = TradeReview(
            approved=True,
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            price=100.0,
            reason="stress",
            metadata={},
        )

        first = await engine.execute_review(review)
        second = await engine.execute_review(review)
        third = await engine.execute_review(review)
        return broker.calls, first, second, third

    calls, first, second, third = asyncio.run(scenario())

    assert calls == 2
    assert first.status == "failed"
    assert second.status == "failed"
    assert third.status == "failed"
    assert third.metadata["raw"]["error_category"] == "circuit_open"


def test_execution_manager_circuit_breaker_blocks_after_threshold():
    async def scenario():
        broker = _RateLimitedManagerBroker()
        bus = EventBus()
        manager = ExecutionManager(
            broker,
            bus,
            OrderRouter(broker),
            circuit_failure_threshold=2,
            circuit_recovery_timeout_seconds=60.0,
        )

        first = await manager.execute(symbol="BTC/USDT", side="buy", amount=0.1, price=100.0)
        second = await manager.execute(symbol="BTC/USDT", side="buy", amount=0.1, price=100.0)
        third = await manager.execute(symbol="BTC/USDT", side="buy", amount=0.1, price=100.0)
        return broker.calls, first, second, third

    calls, first, second, third = asyncio.run(scenario())

    assert calls == 2
    assert first is None
    assert second is None
    assert third["status"] == "rejected"
    assert third["error_category"] == "circuit_open"
