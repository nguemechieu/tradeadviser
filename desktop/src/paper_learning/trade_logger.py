from __future__ import annotations

import asyncio

from event_bus.event import Event
from event_bus.event_types import EventType


class PaperTradeLogger:
    """Append-only logger for lifecycle events and finalized paper trade records."""

    def __init__(self, repository, event_bus=None):
        self.repository = repository
        self.event_bus = event_bus

    def _bus_has_subscribers(self, event_type):
        bus = self.event_bus
        subscribers = getattr(bus, "subscribers", {}) if bus is not None else {}
        return bool(subscribers.get(event_type) or subscribers.get("*"))

    async def log_event(self, event):
        if self.repository is not None:
            await asyncio.to_thread(self.repository.append_trade_event, event=event)
        if self.event_bus is not None and self._bus_has_subscribers(EventType.PAPER_TRADE_EVENT):
            await self.event_bus.publish(Event(EventType.PAPER_TRADE_EVENT, event.to_dict()))

    async def log_record(self, record):
        if self.repository is not None:
            await asyncio.to_thread(self.repository.append_trade_record, record=record)
        if self.event_bus is not None and self._bus_has_subscribers(EventType.PAPER_TRADE_RECORDED):
            await self.event_bus.publish(Event(EventType.PAPER_TRADE_RECORDED, record.to_dict()))
