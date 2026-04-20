import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import AlertEvent, ExecutionReport, PortfolioSnapshot, Position, TraderDecision
from sopotek.services import AlertingEngine, BaseAlertChannel, MobileDashboardService


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class MemoryAlertChannel(BaseAlertChannel):
    name = "memory"

    def __init__(self) -> None:
        self.sent: list[AlertEvent] = []

    async def send(self, alert: AlertEvent) -> bool:
        self.sent.append(alert)
        return True


def test_alerting_engine_dispatches_execution_alert_and_updates_mobile_dashboard():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        sent_alerts = []
        memory_channel = MemoryAlertChannel()
        with tempfile.TemporaryDirectory() as temp_dir:
            dashboard = MobileDashboardService(bus, base_dir=temp_dir)
            engine = AlertingEngine(
                bus,
                external_channels=[memory_channel],
                alert_cooldown_seconds=0.0,
            )
            bus.subscribe(EventType.ALERT_EVENT, lambda event: sent_alerts.append(event.data))

            await bus.publish(
                EventType.EXECUTION_REPORT,
                ExecutionReport(
                    order_id="ord-1",
                    symbol="AAPL",
                    side="buy",
                    quantity=5.0,
                    requested_price=198.0,
                    fill_price=None,
                    status="rejected_market_hours",
                    latency_ms=0.0,
                    strategy_name="breakout",
                    metadata={"error": "stock market is closed due to regular hours, weekend, or holiday."},
                ),
                priority=80,
            )
            await _drain(bus)

            snapshot_path = Path(temp_dir) / "snapshot.json"
            summary_path = Path(temp_dir) / "summary.json"
            return {
                "alerts": sent_alerts,
                "memory": memory_channel.sent,
                "snapshot": dashboard.read_snapshot(),
                "snapshot_exists": snapshot_path.exists(),
                "summary_exists": summary_path.exists(),
                "summary": json.loads(summary_path.read_text(encoding="utf-8")),
            }

    result = asyncio.run(scenario())

    assert len(result["alerts"]) == 1
    assert len(result["memory"]) == 1
    assert result["alerts"][0].severity == "critical"
    assert result["alerts"][0].category == "execution"
    assert result["snapshot_exists"]
    assert result["summary_exists"]
    assert result["snapshot"]["latest_alert"]["category"] == "execution"
    assert result["summary"]["latest_alert"]["severity"] == "critical"


def test_mobile_dashboard_tracks_portfolio_and_decisions():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        update_events = []
        with tempfile.TemporaryDirectory() as temp_dir:
            dashboard = MobileDashboardService(bus, base_dir=temp_dir)
            bus.subscribe(EventType.MOBILE_DASHBOARD_UPDATE, lambda event: update_events.append(event.data))

            await bus.publish(
                EventType.PORTFOLIO_SNAPSHOT,
                PortfolioSnapshot(
                    cash=95000.0,
                    equity=101500.0,
                    positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=1.25, average_price=80000.0, last_price=81200.0)},
                    realized_pnl=1200.0,
                    unrealized_pnl=1500.0,
                    drawdown_pct=0.03,
                ),
                priority=50,
            )
            await bus.publish(
                EventType.DECISION_EVENT,
                TraderDecision(
                    profile_id="growth",
                    symbol="BTC/USDT",
                    action="BUY",
                    side="buy",
                    quantity=1.25,
                    price=81200.0,
                    confidence=0.81,
                    selected_strategy="trend_following",
                    reasoning="BUY because trend is strong.",
                ),
                priority=62,
            )
            await _drain(bus)
            return dashboard.read_snapshot(), update_events

    snapshot, update_events = asyncio.run(scenario())

    assert snapshot["equity"] == 101500.0
    assert snapshot["open_positions"] == 1
    assert snapshot["positions"][0]["symbol"] == "BTC/USDT"
    assert snapshot["latest_decision"]["action"] == "BUY"
    assert len(update_events) >= 2
