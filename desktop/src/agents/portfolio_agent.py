from event_bus.event import Event
from event_bus.event_types import EventType

from agents.base_agent import BaseAgent


class PortfolioAgent(BaseAgent):
    def __init__(self, snapshot_builder, memory=None, event_bus=None):
        super().__init__("PortfolioAgent", memory=memory, event_bus=event_bus)
        self.snapshot_builder = snapshot_builder

    async def process(self, context):
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")
        snapshot = self.snapshot_builder(symbol=symbol)
        working["portfolio_snapshot"] = snapshot
        if self.event_bus is not None:
            await self.event_bus.publish(Event(EventType.PORTFOLIO_SNAPSHOT, dict(snapshot or {})))
        self.remember(
            "snapshot",
            {
                "equity": snapshot.get("equity"),
                "gross_exposure": snapshot.get("gross_exposure"),
                "net_exposure": snapshot.get("net_exposure"),
                "positions": snapshot.get("position_count"),
            },
            symbol=symbol,
            decision_id=decision_id,
        )
        return working
