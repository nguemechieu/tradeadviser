from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from event_bus.event_bus import EventBus as LegacyEventBus
from core.event_bus import Event, InMemoryEventStore, JsonlEventStore
from core.event_bus import AsyncEventBus as _BaseAsyncEventBus
from core.event_bus import EventStore


@dataclass(slots=True)
class EventBusMetrics:
    published_events: int = 0
    delivered_events: int = 0
    failed_events: int = 0
    max_queue_depth: int = 0
    last_publish_latency_ms: float = 0.0
    publish_latency_ms_total: float = 0.0
    delivery_latency_ms_total: float = 0.0
    events_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def average_publish_latency_ms(self) -> float:
        if self.published_events <= 0:
            return 0.0
        return self.publish_latency_ms_total / self.published_events

    @property
    def average_delivery_latency_ms(self) -> float:
        if self.delivered_events <= 0:
            return 0.0
        return self.delivery_latency_ms_total / self.delivered_events


class AsyncEventBus(_BaseAsyncEventBus):
    """Institutional async event bus with priority delivery and backpressure hooks."""

    def __init__(
        self,
        *,
        store: EventStore | None = None,
        enable_persistence: bool = True,
        queue_maxsize: int = 0,
        publish_timeout: float | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(store=store, enable_persistence=enable_persistence, logger=logger)
        self.queue = asyncio.PriorityQueue(maxsize=max(0, int(queue_maxsize)))
        self.publish_timeout = None if publish_timeout is None else max(0.0, float(publish_timeout))
        self.metrics = EventBusMetrics()

    @property
    def queue_depth(self) -> int:
        return int(self.queue.qsize())

    @property
    def backpressure_active(self) -> bool:
        maxsize = int(getattr(self.queue, "maxsize", 0) or 0)
        return bool(maxsize > 0 and self.queue_depth >= maxsize)

    async def publish(self, event_or_type: Event | str, data: Any = None, **kwargs: Any) -> Event:
        start = time.perf_counter()
        event = self._coerce_event(event_or_type, data=data, **kwargs)
        event.sequence = self._sequence
        self._sequence += 1
        if self._enable_persistence and self._store is not None:
            await self._store.append(event)

        item = (int(event.priority), int(event.sequence), event)
        if self.publish_timeout is None:
            await self.queue.put(item)
        else:
            await asyncio.wait_for(self.queue.put(item), timeout=self.publish_timeout)

        latency_ms = (time.perf_counter() - start) * 1000.0
        self.metrics.published_events += 1
        self.metrics.last_publish_latency_ms = latency_ms
        self.metrics.publish_latency_ms_total += latency_ms
        self.metrics.max_queue_depth = max(self.metrics.max_queue_depth, self.queue_depth)
        self.metrics.events_by_type[event.type] = self.metrics.events_by_type.get(event.type, 0) + 1
        self.logger.debug(
            "event_published type=%s priority=%s sequence=%s queue_depth=%s",
            event.type,
            event.priority,
            event.sequence,
            self.queue_depth,
        )
        return event

    async def dispatch_once(self, event: Event | None = None) -> Event:
        start = time.perf_counter()
        try:
            dispatched = await super().dispatch_once(event)
        except Exception:
            self.metrics.failed_events += 1
            raise
        if getattr(dispatched, "type", None) != self.SHUTDOWN_EVENT:
            latency_ms = (time.perf_counter() - start) * 1000.0
            self.metrics.delivered_events += 1
            self.metrics.delivery_latency_ms_total += latency_ms
        return dispatched

    async def publish_many(self, events: list[Event | tuple[str, Any] | dict[str, Any]]) -> list[Event]:
        published: list[Event] = []
        for item in list(events or []):
            if isinstance(item, Event):
                published.append(await self.publish(item))
                continue
            if isinstance(item, tuple) and len(item) == 2:
                published.append(await self.publish(str(item[0]), item[1]))
                continue
            payload = dict(item or {})
            event_type = payload.pop("type", payload.pop("event_type", None))
            if event_type is None:
                raise ValueError("Event payload must include 'type' or 'event_type'")
            data = payload.pop("data", None)
            published.append(await self.publish(str(event_type), data, **payload))
        return published

    def snapshot_metrics(self) -> dict[str, Any]:
        return {
            "published_events": self.metrics.published_events,
            "delivered_events": self.metrics.delivered_events,
            "failed_events": self.metrics.failed_events,
            "queue_depth": self.queue_depth,
            "max_queue_depth": self.metrics.max_queue_depth,
            "average_publish_latency_ms": self.metrics.average_publish_latency_ms,
            "average_delivery_latency_ms": self.metrics.average_delivery_latency_ms,
            "events_by_type": dict(self.metrics.events_by_type),
        }


EventBus = LegacyEventBus


def build_event_store(*, persistent: bool = False, path: str | Path | None = None) -> EventStore | None:
    if not persistent:
        return None
    if path is None:
        return InMemoryEventStore()
    return JsonlEventStore(path)


def build_event_bus(
    *,
    async_mode: bool = False,
    persistent: bool = False,
    store_path: str | Path | None = None,
    queue_maxsize: int = 0,
    publish_timeout: float | None = None,
    logger: logging.Logger | None = None,
):
    """Create the canonical event bus for institutional components."""

    if async_mode:
        store = build_event_store(persistent=persistent, path=store_path)
        return AsyncEventBus(
            store=store,
            enable_persistence=bool(store is not None),
            queue_maxsize=queue_maxsize,
            publish_timeout=publish_timeout,
            logger=logger,
        )
    return EventBus()


__all__ = [
    "AsyncEventBus",
    "Event",
    "EventBus",
    "EventBusMetrics",
    "EventStore",
    "InMemoryEventStore",
    "JsonlEventStore",
    "build_event_bus",
    "build_event_store",
]
