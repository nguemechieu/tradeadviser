"""Async event bus primitives shared by legacy and current runtimes."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..event import Event

try:
    from .event_types import EventType
except Exception:  # pragma: no cover
    EventType = None  # type: ignore


EventHandler = Callable[[Event], Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_key(value: Any) -> str:
    """Normalize event names from strings, enums, or Event objects."""
    if isinstance(value, Event):
        value = value.type

    if hasattr(value, "value"):
        try:
            return str(value.value)
        except Exception:
            pass

    text = str(value or "").strip()

    # Protect against accidental str(EnumMember), for example "EventType.MARKET_TICK".
    if EventType is not None and text.startswith("EventType."):
        member_name = text.split(".", 1)[1]
        member = getattr(EventType, member_name, None)
        if member is not None and hasattr(member, "value"):
            return str(member.value)

    return text or "unknown"


def _safe_error_text(error: BaseException) -> str:
    try:
        message = str(error)
    except Exception:
        message = repr(error)

    try:
        return message.encode("utf-8", errors="replace").decode(
            "utf-8",
            errors="replace",
        )
    except Exception:
        return "[Unable to format error message]"


@dataclass(slots=True)
class EventBusStats:
    published: int = 0
    delivered: int = 0
    failed: int = 0
    dropped: int = 0
    replayed: int = 0
    started_at: datetime = field(default_factory=_utc_now)
    last_event_at: datetime | None = None
    last_error_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "delivered": self.delivered,
            "failed": self.failed,
            "dropped": self.dropped,
            "replayed": self.replayed,
            "started_at": self.started_at.isoformat(),
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
        }


class _EventPriorityQueue:
    """Priority queue wrapper that exposes plain Event objects."""

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, Event]] = asyncio.PriorityQueue(
            maxsize=max(0, int(maxsize or 0))
        )

    @property
    def maxsize(self) -> int:
        return int(getattr(self._queue, "maxsize", 0) or 0)

    async def put(self, event: Event) -> None:
        await self._queue.put((int(event.priority), int(event.sequence), event))

    def put_nowait(self, event: Event) -> None:
        self._queue.put_nowait((int(event.priority), int(event.sequence), event))

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

    async def append(self, event: Event) -> None:
        raise NotImplementedError

    async def read(
            self,
            *,
            event_types: list[str] | None = None,
            limit: int | None = None,
    ) -> list[Event]:
        raise NotImplementedError


class InMemoryEventStore(EventStore):
    """Simple in-memory event sink for tests and lightweight runtimes."""

    def __init__(self, max_events: int = 50_000) -> None:
        self.events: list[Event] = []
        self.max_events = max(1, int(max_events or 50_000))
        self._lock = asyncio.Lock()

    async def append(self, event: Event) -> None:
        async with self._lock:
            self.events.append(event.copy())
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events :]

    async def read(
            self,
            *,
            event_types: list[str] | None = None,
            limit: int | None = None,
    ) -> list[Event]:
        async with self._lock:
            events = list(self.events)

        if event_types is not None:
            allowed = {_event_key(item) for item in event_types}
            events = [event for event in events if _event_key(event.type) in allowed]

        if limit is not None and int(limit) >= 0:
            events = events[-int(limit) :]

        return [event.copy() for event in events]


class JsonlEventStore(EventStore):
    """Append-only JSONL event sink."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def append(self, event: Event) -> None:
        async with self._lock:
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
            allowed = {_event_key(item) for item in event_types}
            records = [
                record
                for record in records
                if _event_key(record.get("type")) in allowed
            ]

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

                try:
                    records.append(dict(json.loads(stripped)))
                except Exception:
                    continue

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
            fail_fast: bool = False,
            publish_timeout: float | None = None,
            dispatch_timeout: float | None = None,
            dead_letter_maxsize: int = 1000,
            **kwargs: Any,
    ) -> None:
        queue_maxsize = kwargs.get("queue_maxsize")
        resolved_maxsize = (
            maxsize if int(maxsize or 0) > 0 else int(queue_maxsize or 0)
        )

        self.queue = _EventPriorityQueue(maxsize=resolved_maxsize)
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._dispatcher_task: asyncio.Task[Any] | None = None
        self._failure_handler: Callable[..., Any] | None = None
        self._running = False
        self._sequence = 0
        self._sequence_lock = asyncio.Lock()

        self._enable_persistence = bool(enable_persistence)
        self._store = store
        self._fail_fast = bool(fail_fast)
        self._publish_timeout = publish_timeout
        self._dispatch_timeout = dispatch_timeout
        self._dead_letter_maxsize = max(1, int(dead_letter_maxsize or 1000))
        self._dead_letters: list[dict[str, Any]] = []
        self._stats = EventBusStats()
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

    @property
    def subscribers(self) -> dict[str, list[EventHandler]]:
        return self._subscribers

    @property
    def dead_letters(self) -> list[dict[str, Any]]:
        return list(self._dead_letters)

    def subscribe(self, event_type: str | Any, handler: EventHandler) -> EventHandler:
        if not callable(handler):
            raise TypeError("Event handler must be callable")

        key = _event_key(event_type)
        handlers = self._subscribers[key]

        if handler not in handlers:
            handlers.append(handler)

        return handler

    def unsubscribe(self, event_type: str | Any, handler: EventHandler) -> None:
        key = _event_key(event_type)
        handlers = self._subscribers.get(key, [])
        self._subscribers[key] = [item for item in handlers if item is not handler]

        if not self._subscribers[key]:
            self._subscribers.pop(key, None)

    def clear_subscribers(self, event_type: str | Any | None = None) -> None:
        if event_type is None:
            self._subscribers.clear()
            return

        self._subscribers.pop(_event_key(event_type), None)

    def set_failure_handler(
            self,
            handler: Callable[..., Any] | None = None,
    ) -> Callable[..., Any] | None:
        """Register or clear the failure handler."""

        if handler is None:
            self._failure_handler = None
            return None

        if not callable(handler):
            self.logger.warning(
                "Ignoring invalid failure handler %r because it is not callable.",
                handler,
            )
            self._failure_handler = None
            return None

        self._failure_handler = handler
        return handler

    def _coerce_event(
            self,
            event_or_type: Event | str | Any,
            data: Any = None,
            **kwargs: Any,
    ) -> Event:
        if isinstance(event_or_type, Event):
            updates = dict(kwargs)

            if data is not None:
                updates["data"] = data

            if not updates:
                return event_or_type.copy()

            return event_or_type.copy(**updates)

        return Event(type=_event_key(event_or_type), data=data, **kwargs)

    async def _next_sequence(self) -> int:
        async with self._sequence_lock:
            sequence = int(self._sequence)
            self._sequence += 1
            return sequence

    async def publish(
            self,
            event_or_type: Event | str | Any,
            data: Any = None,
            **kwargs: Any,
    ) -> Event:
        event = self._coerce_event(event_or_type, data=data, **kwargs)
        event.type = _event_key(event.type)
        event.sequence = await self._next_sequence()

        if self._enable_persistence and self._store is not None:
            await self._store.append(event)

        put_operation = self.queue.put(event)

        if self._publish_timeout is not None:
            await asyncio.wait_for(put_operation, timeout=float(self._publish_timeout))
        else:
            await put_operation

        self._stats.published += 1
        self._stats.last_event_at = _utc_now()

        return event

    def publish_nowait(
            self,
            event_or_type: Event | str | Any,
            data: Any = None,
            **kwargs: Any,
    ) -> Event:
        event = self._coerce_event(event_or_type, data=data, **kwargs)
        event.type = _event_key(event.type)

        # publish_nowait is sync, so sequence assignment cannot await the lock.
        # This is still safe on the running event loop thread.
        event.sequence = int(self._sequence)
        self._sequence += 1

        if self._enable_persistence and self._store is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._store.append(event))
            except RuntimeError:
                pass

        self.queue.put_nowait(event)

        self._stats.published += 1
        self._stats.last_event_at = _utc_now()

        return event

    def publish_sync(
            self,
            event_or_type: Event | str | Any,
            data: Any = None,
            **kwargs: Any,
    ) -> Event:
        event = self._coerce_event(event_or_type, data=data, **kwargs)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.publish(event))

        loop.create_task(self.publish(event))
        return event

    async def _deliver(self, event: Event) -> Event:
        key = _event_key(event.type)

        handlers = list(self._subscribers.get(key, []))
        if key != self.ALL_EVENTS:
            handlers.extend(self._subscribers.get(self.ALL_EVENTS, []))

        handlers = self._dedupe_handlers(handlers)

        if not handlers:
            self.logger.debug("No handlers subscribed for event type=%s", key)
            return event

        pending: list[Awaitable[Any]] = []
        pending_handlers: list[EventHandler] = []

        for handler in handlers:
            try:
                result = handler(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.exception("Event handler crashed for type=%s", key)
                await self._report_failure(event, exc, handler, stage="event_handler")

                if self._fail_fast:
                    raise

                continue

            if inspect.isawaitable(result):
                pending.append(result)
                pending_handlers.append(handler)

        if pending:
            if self._dispatch_timeout is not None:
                pending_results = await asyncio.gather(
                    *[
                        asyncio.wait_for(item, timeout=float(self._dispatch_timeout))
                        for item in pending
                    ],
                    return_exceptions=True,
                )
            else:
                pending_results = await asyncio.gather(
                    *pending,
                    return_exceptions=True,
                )

            for handler, result in zip(pending_handlers, pending_results):
                if isinstance(result, asyncio.CancelledError):
                    raise result

                if isinstance(result, Exception):
                    error_msg = _safe_error_text(result)
                    self.logger.error(
                        "Async event handler failed for type=%s: %s",
                        key,
                        error_msg,
                    )
                    await self._report_failure(
                        event,
                        result,
                        handler,
                        stage="event_handler",
                    )

                    if self._fail_fast:
                        raise result

        self._stats.delivered += 1
        return event

    @staticmethod
    def _dedupe_handlers(handlers: list[EventHandler]) -> list[EventHandler]:
        deduped: list[EventHandler] = []
        seen: set[int] = set()

        for handler in handlers:
            identity = id(handler)
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(handler)

        return deduped

    async def _report_failure(
            self,
            event: Event,
            error: Exception,
            handler: EventHandler,
            *,
            stage: str,
    ) -> None:
        self._stats.failed += 1
        self._stats.last_error_at = _utc_now()

        failure_record = {
            "event_type": _event_key(event.type),
            "event_sequence": getattr(event, "sequence", None),
            "stage": stage,
            "handler": getattr(handler, "__name__", handler.__class__.__name__),
            "error": _safe_error_text(error),
            "timestamp": _utc_now().isoformat(),
        }

        self._dead_letters.append(failure_record)

        if len(self._dead_letters) > self._dead_letter_maxsize:
            self._dead_letters = self._dead_letters[-self._dead_letter_maxsize :]

        failure_handler = self._failure_handler

        if failure_handler is None:
            return

        if not callable(failure_handler):
            self.logger.warning(
                "Clearing invalid failure handler %r because it is not callable.",
                failure_handler,
            )
            self._failure_handler = None
            return

        try:
            try:
                result = failure_handler(event, error, handler, stage=stage)
            except TypeError:
                try:
                    result = failure_handler(event, error, handler)
                except TypeError:
                    try:
                        result = failure_handler(event, error)
                    except TypeError:
                        result = failure_handler(failure_record)

            if inspect.isawaitable(result):
                await result

        except Exception:
            self.logger.exception(
                "Failure handler crashed for event type=%s",
                event.type,
            )

    async def dispatch_once(self, event: Event | None = None) -> Event:
        owned_queue_item = event is None
        active_event = await self.queue.get() if owned_queue_item else event

        if active_event is None:
            raise RuntimeError("dispatch_once requires an event")

        try:
            if _event_key(active_event.type) == self.SHUTDOWN_EVENT:
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

    def run_in_background(self) -> asyncio.Task[Any]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError(
                "AsyncEventBus.run_in_background() requires a running event loop. "
                "Call it from inside async code, or use await bus.start()."
            ) from exc

        if self._dispatcher_task and not self._dispatcher_task.done():
            return self._dispatcher_task

        self._dispatcher_task = loop.create_task(
            self.run(),
            name="AsyncEventBus.run",
        )
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
            replay_event.type = _event_key(replay_event.type)

            if handler is not None:
                result = handler(replay_event)

                if inspect.isawaitable(result):
                    await result
            else:
                await self._deliver(replay_event)

            delivered.append(replay_event)
            self._stats.replayed += 1

        return delivered

    async def shutdown(
            self,
            *,
            timeout: float = 5.0,
            cancel: bool = True,
    ) -> None:
        task = self._dispatcher_task if self.is_running else None

        if task is None:
            self._running = False
            self._dispatcher_task = None
            return

        current_task = asyncio.current_task()
        if task is current_task:
            self._running = False
            self._dispatcher_task = None
            return

        self._running = False

        with contextlib.suppress(Exception):
            await self.publish(self.SHUTDOWN_EVENT)

        try:
            await asyncio.wait_for(
                asyncio.gather(task, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            if cancel and not task.done():
                task.cancel()

                with contextlib.suppress(asyncio.CancelledError):
                    await task

        self._dispatcher_task = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "is_running": self.is_running,
            "queue_size": self.queue.qsize(),
            "queue_maxsize": self.queue.maxsize,
            "subscriber_count": sum(len(items) for items in self._subscribers.values()),
            "subscribed_event_types": sorted(self._subscribers.keys()),
            "persistence_enabled": self._enable_persistence,
            "store": self._store.__class__.__name__ if self._store is not None else None,
            "dead_letter_count": len(self._dead_letters),
            "stats": self._stats.to_dict(),
        }

    def stats(self) -> dict[str, Any]:
        return self.snapshot()


def build_event_store(
        *,
        persistent: bool = False,
        path: str | Path | None = None,
) -> EventStore | None:
    if not persistent:
        return None

    if path is None:
        return InMemoryEventStore()

    return JsonlEventStore(path)


def build_event_bus(
        *,
        persistent: bool = False,
        store_path: str | Path | None = None,
        queue_maxsize: int = 0,
        logger: logging.Logger | None = None,
        **kwargs: Any,
) -> AsyncEventBus:
    store = build_event_store(persistent=persistent, path=store_path)

    return AsyncEventBus(
        queue_maxsize=queue_maxsize,
        store=store,
        enable_persistence=bool(store is not None),
        logger=logger,
        **kwargs,
    )


__all__ = [
    "AsyncEventBus",
    "EventBusStats",
    "EventStore",
    "EventHandler",
    "InMemoryEventStore",
    "JsonlEventStore",
    "build_event_bus",
    "build_event_store",
]