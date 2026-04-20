"""Async event bus primitives shared by legacy and current runtimes."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from .event import Event

EventHandler = Callable[[Event], Any]


class _EventPriorityQueue:
    """Priority queue wrapper that exposes plain ``Event`` objects."""

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, Event]] = asyncio.PriorityQueue(
            maxsize=max(0, int(maxsize or 0))
        )

    @property
    def maxsize(self) -> int:
        return int(getattr(self._queue, "maxsize", 0) or 0)

    async def put(self, event: Event) -> None:
        await self._queue.put((int(event.priority), int(event.sequence), event))

    async def get(self) -> Event:
        _priority, _sequence, event = await self._queue.get()
        return event

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return int(self._queue.qsize())

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()


class EventStore:
    """Minimal async event store interface."""

    async def append(self, event: Event) -> None:  # pragma: no cover - interface hook
        raise NotImplementedError

    async def read(
        self,
        *,
        event_types: list[str] | None = None,
        limit: int | None = None,
    ) -> list[Event]:  # pragma: no cover - interface hook
        raise NotImplementedError


class InMemoryEventStore(EventStore):
    """Simple in-memory event sink for tests and lightweight runtimes."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def append(self, event: Event) -> None:
        self.events.append(event.copy())

    async def read(
        self,
        *,
        event_types: list[str] | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        events = list(self.events)
        if event_types is not None:
            allowed = {str(item) for item in event_types}
            events = [event for event in events if str(event.type) in allowed]
        if limit is not None and int(limit) >= 0:
            events = events[-int(limit) :]
        return [event.copy() for event in events]


class JsonlEventStore(EventStore):
    """Append-only JSONL event sink."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def append(self, event: Event) -> None:
        await asyncio.to_thread(self._append_sync, event)

    def _append_sync(self, event: Event) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.to_record()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, default=str))
            handle.write("\n")

    async def read(
        self,
        *,
        event_types: list[str] | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        records = await asyncio.to_thread(self._read_sync)
        if event_types is not None:
            allowed = {str(item) for item in event_types}
            records = [record for record in records if str(record.get("type")) in allowed]
        if limit is not None and int(limit) >= 0:
            records = records[-int(limit) :]
        return [Event.from_record(record) for record in records]

    def _read_sync(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                records.append(dict(json.loads(stripped)))
        return records


class AsyncEventBus:
    """Async event bus with legacy-compatible subscription semantics."""

    SHUTDOWN_EVENT = "__shutdown__"
    ALL_EVENTS = "*"

    def __init__(
        self,
        maxsize: int = 0,
        *,
        enable_persistence: bool = False,
        store: EventStore | None = None,
        logger: logging.Logger | None = None,
        **kwargs: Any,
    ) -> None:
        queue_maxsize = kwargs.get("queue_maxsize")
        resolved_maxsize = maxsize if int(maxsize or 0) > 0 else int(queue_maxsize or 0)
        self.queue = _EventPriorityQueue(maxsize=resolved_maxsize)
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._dispatcher_task: asyncio.Task[Any] | None = None
        self._failure_handler: Callable[..., Any] | None = None
        self._running = False
        self._sequence = 0
        self._enable_persistence = bool(enable_persistence)
        self._store = store
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @property
    def running(self) -> bool:
        return bool(self._running)

    @property
    def is_running(self) -> bool:
        return bool(
            self._running
            and self._dispatcher_task is not None
            and not self._dispatcher_task.done()
        )

    def subscribe(self, event_type: str, handler: EventHandler) -> EventHandler:
        self._subscribers[str(event_type)].append(handler)
        return handler

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(str(event_type), [])
        self._subscribers[str(event_type)] = [item for item in handlers if item is not handler]

    def set_failure_handler(self, handler: Callable[..., Any] | None) -> Callable[..., Any] | None:
        self._failure_handler = handler
        return handler

    def _coerce_event(self, event_or_type: Event | str, data: Any = None, **kwargs: Any) -> Event:
        if isinstance(event_or_type, Event):
            updates = dict(kwargs)
            if data is not None:
                updates["data"] = data
            if not updates:
                return event_or_type
            return event_or_type.copy(**updates)
        return Event(type=str(event_or_type), data=data, **kwargs)

    async def publish(self, event_or_type: Event | str, data: Any = None, **kwargs: Any) -> Event:
        event = self._coerce_event(event_or_type, data=data, **kwargs)
        event.sequence = int(self._sequence)
        self._sequence += 1

        if self._enable_persistence and self._store is not None:
            await self._store.append(event)

        await self.queue.put(event)
        return event

    async def _deliver(self, event: Event) -> Event:
        handlers = list(self._subscribers.get(str(event.type), []))
        handlers.extend(self._subscribers.get(self.ALL_EVENTS, []))
        if not handlers:
            self.logger.debug("No handlers subscribed for event type=%s", event.type)
            return event

        pending: list[Awaitable[Any]] = []
        pending_handlers: list[EventHandler] = []
        for handler in handlers:
            try:
                result = handler(event)
            except Exception as exc:
                self.logger.exception("Event handler crashed for type=%s", event.type)
                await self._report_failure(event, exc, handler, stage="event_handler")
                continue
            if inspect.isawaitable(result):
                pending.append(result)
                pending_handlers.append(handler)

        if pending:
            results = await asyncio.gather(*pending, return_exceptions=True)
            for handler, result in zip(pending_handlers, results):
                if isinstance(result, Exception):
                    # Handle Unicode characters in exception messages (e.g., emoji in market data)
                    # by converting to string with error handling and encoding replacement
                    try:
                        error_msg = str(result)
                        # Encode to bytes and back to ensure safe representation
                        error_msg = error_msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    except Exception:
                        try:
                            error_msg = repr(result)
                            error_msg = error_msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        except Exception:
                            error_msg = "[Unable to format error message]"
                    self.logger.error("Async event handler failed for type=%s: %s", event.type, error_msg)
                    await self._report_failure(event, result, handler, stage="event_handler")
        return event

    async def _report_failure(
        self,
        event: Event,
        error: Exception,
        handler: EventHandler,
        *,
        stage: str,
    ) -> None:
        failure_handler = self._failure_handler
        if failure_handler is None:
            return

        handler_name = getattr(handler, "__name__", handler.__class__.__name__)
        try:
            result = failure_handler(event, error, handler_name=handler_name, stage=stage)
        except TypeError:
            try:
                result = failure_handler(event, error, handler_name)
            except TypeError:
                result = failure_handler(event, error)
        except Exception:
            self.logger.exception("Failure handler crashed for event type=%s", event.type)
            return

        if inspect.isawaitable(result):
            try:
                await result
            except Exception:
                self.logger.exception("Async failure handler crashed for event type=%s", event.type)

    async def dispatch_once(self, event: Event | None = None) -> Event:
        owned_queue_item = event is None
        active_event = await self.queue.get() if owned_queue_item else event
        if active_event is None:
            raise RuntimeError("dispatch_once requires an event")

        try:
            if str(active_event.type) == self.SHUTDOWN_EVENT:
                self._running = False
                return active_event
            return await self._deliver(active_event)
        finally:
            if owned_queue_item:
                self.queue.task_done()

    async def start(self) -> None:
        await self.run()

    async def run(self) -> None:
        self._running = True
        try:
            while self._running:
                await self.dispatch_once()
        finally:
            self._running = False
            current_task = asyncio.current_task()
            if current_task is not None and self._dispatcher_task is current_task:
                self._dispatcher_task = None

    def run_in_background(self):

     try:
        loop = asyncio.get_running_loop()
     except RuntimeError:
        loop = asyncio.get_event_loop()

     if self._dispatcher_task and not self._dispatcher_task.done():
        return self._dispatcher_task

     self._dispatcher_task = loop.create_task(self.run())

     return self._dispatcher_task

    async def join(self) -> None:
        await self.queue.join()

    async def replay(
        self,
        *,
        event_types: list[str] | None = None,
        limit: int | None = None,
        handler: EventHandler | None = None,
    ) -> list[Event]:
        if self._store is None:
            return []
        replay_events = await self._store.read(event_types=event_types, limit=limit)
        delivered: list[Event] = []
        for stored_event in replay_events:
            replay_event = stored_event.copy(replayed=True)
            if handler is not None:
                result = handler(replay_event)
                if inspect.isawaitable(result):
                    await result
            else:
                await self._deliver(replay_event)
            delivered.append(replay_event)
        return delivered

    async def shutdown(self) -> None:
        task = self._dispatcher_task if self.is_running else None
        if task is None:
            self._running = False
            self._dispatcher_task = None
            return
        await self.publish(self.SHUTDOWN_EVENT)
        await asyncio.gather(task, return_exceptions=True)
        self._dispatcher_task = None


__all__ = [
    "AsyncEventBus",
    "EventStore",
    "InMemoryEventStore",
    "JsonlEventStore",
]
