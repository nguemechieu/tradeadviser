"""In-memory event bus for the server skeleton.

Replace this with Kafka, Redis streams, or another durable bus as migration
progresses. The interface is intentionally simple so services can depend on it
without binding to transport details yet.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any


EventHandler = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class InMemoryEventBus:
    """Simple async event bus used by the initial server shell."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        for handler in self._subscribers.get(topic, []):
            result = handler(topic, payload)
            if asyncio.iscoroutine(result):
                await result

