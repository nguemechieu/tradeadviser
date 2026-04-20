from __future__ import annotations

from collections.abc import Mapping

from event_bus.event import Event
from event_bus.event_types import EventType
from execution.order_router import OrderRouter
from models.order import Order


class ExecutionEngine:
    def __init__(self, broker, bus, router=None):
        self.broker = broker
        self.bus = bus
        self.router = router or OrderRouter(broker)
        self.bus.subscribe(EventType.ORDER, self.execute)

    async def execute(self, event):
        order_payload = event.data if hasattr(event, "data") else event
        normalized_order = Order.from_mapping(order_payload).to_dict() if not isinstance(order_payload, Mapping) else dict(order_payload)
        execution = await self.router.route(normalized_order)
        if isinstance(execution, dict) and hasattr(self.bus, "publish"):
            await self.bus.publish(Event(EventType.ORDER_EVENT, execution))
        return execution
