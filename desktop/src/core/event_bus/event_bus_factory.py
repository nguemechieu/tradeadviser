"""Core event bus construction helpers."""

from __future__ import annotations

from pathlib import Path

from event_bus.async_event_bus import AsyncEventBus, EventStore, InMemoryEventStore, JsonlEventStore
from event_bus.event import Event
from event_bus.event_bus import EventBus


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
    logger=None,
    **_kwargs,
):
    """Create the canonical event bus for current and legacy runtime paths."""

    store = build_event_store(persistent=persistent, path=store_path)
    if async_mode:
        return AsyncEventBus(
            maxsize=queue_maxsize,
            store=store,
            enable_persistence=bool(store is not None),
            logger=logger,
        )
    return EventBus(
        maxsize=queue_maxsize,
        store=store,
        enable_persistence=bool(store is not None),
        logger=logger,
    )


__all__ = [
    "AsyncEventBus",
    "Event",
    "EventBus",
    "EventStore",
    "InMemoryEventStore",
    "JsonlEventStore",
    "build_event_bus",
    "build_event_store",
]
