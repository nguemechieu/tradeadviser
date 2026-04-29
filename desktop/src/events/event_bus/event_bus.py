from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from events.event_bus.async_event_bus import AsyncEventBus

if TYPE_CHECKING:
    from derivatives.core.models import DerivativesEvent

# At runtime, we'll use a lazy-loaded class
_DerivativesEvent: Any = None


def _get_derivatives_event() -> type[Any]:
    """Lazily load DerivativesEvent to break circular imports."""
    global _DerivativesEvent
    if _DerivativesEvent is None:
        from derivatives.core.models import DerivativesEvent as DE
        _DerivativesEvent = DE
    return _DerivativesEvent


EventHandler = Callable[[Any], Any]


class EventBus(AsyncEventBus):
    """
    Async event bus for the derivatives engine.

    Features:
    - topic-based subscriptions
    - wildcard "*" subscriptions
    - async and sync handlers
    - in-memory event history
    - background dispatcher mode
    - immediate delivery mode when dispatcher is not running
    - graceful shutdown
    """

    ALL_TOPICS = "*"
    SHUTDOWN_TOPIC = "__shutdown__"

    def __init__(
            self,
            *,
            history_size: int = 50_000,
            queue_maxsize: int = 0,
            logger: logging.Logger | None = None,
            **kwargs: Any,
    ) -> None:
        super().__init__(logger=logger, **kwargs)

        self.logger = logger or logging.getLogger("DerivativesEventBus")

        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Any] = asyncio.Queue(
            maxsize=max(0, int(queue_maxsize or 0))
        )

        self._dispatcher_task: asyncio.Task[Any] | None = None
        self._running = False
        self._closed = False
        self._sequence = 0

        self._state_lock = asyncio.Lock()
        self._publish_lock = asyncio.Lock()

        self.history: deque[Any] = deque(
            maxlen=max(100, int(history_size or 50_000))
        )

    # ------------------------------------------------------------------
    # Subscription API
    # ------------------------------------------------------------------

    def subscribe(self, topic: str, handler: EventHandler) -> EventHandler:
        topic_key = self._normalize_topic(topic)

        if not callable(handler):
            raise TypeError("Event handler must be callable.")

        handlers = self._subscribers[topic_key]

        if handler not in handlers:
            handlers.append(handler)

        return handler

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        topic_key = self._normalize_topic(topic)

        handlers = self._subscribers.get(topic_key)
        if not handlers:
            return

        self._subscribers[topic_key] = [
            item for item in handlers if item is not handler
        ]

        if not self._subscribers[topic_key]:
            self._subscribers.pop(topic_key, None)

    def clear_subscribers(self, topic: str | None = None) -> None:
        if topic is None:
            self._subscribers.clear()
            return

        self._subscribers.pop(self._normalize_topic(topic), None)

    # ------------------------------------------------------------------
    # Publishing API
    # ------------------------------------------------------------------

    async def publish(
            self,
            topic: str,
            data: Any = None,
            *,
            source: str = "system",
            metadata: dict[str, Any] | None = None,
    ) -> Any:
        if self._closed and topic != self.SHUTDOWN_TOPIC:
            raise RuntimeError("EventBus is closed and cannot publish new events.")

        async with self._publish_lock:
            DerivativesEvent = _get_derivatives_event()
            event = DerivativesEvent(
                topic=self._normalize_topic(topic),
                data=data,
                source=str(source or "system"),
                metadata=dict(metadata or {}),
                sequence=self._sequence,
            )
            self._sequence += 1
            self.history.append(event)

        if self._running:
            await self._queue.put(event)
        else:
            await self._deliver(event)

        return event

    async def publish_nowait(
            self,
            topic: str,
            data: Any = None,
            *,
            source: str = "system",
            metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Compatibility helper.

        This method is async because event construction needs sequence safety.
        It uses Queue.put_nowait only when the dispatcher is running.
        """

        if self._closed and topic != self.SHUTDOWN_TOPIC:
            raise RuntimeError("EventBus is closed and cannot publish new events.")

        async with self._publish_lock:
            DerivativesEvent = _get_derivatives_event()
            event = DerivativesEvent(
                topic=self._normalize_topic(topic),
                data=data,
                source=str(source or "system"),
                metadata=dict(metadata or {}),
                sequence=self._sequence,
            )
            self._sequence += 1
            self.history.append(event)

        if self._running:
            self._queue.put_nowait(event)
        else:
            await self._deliver(event)

        return event

    # ------------------------------------------------------------------
    # Delivery internals
    # ------------------------------------------------------------------

    async def _deliver(self, event: Any) -> None:
        handlers = self._handlers_for(event.topic)

        if not handlers:
            return

        awaitables: list[Awaitable[Any]] = []

        for handler in handlers:
            try:
                result = handler(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception(
                    "event_handler_crashed topic=%s handler=%r",
                    event.topic,
                    handler,
                )
                continue

            if inspect.isawaitable(result):
                awaitables.append(result)

        if not awaitables:
            return

        results = await asyncio.gather(*awaitables, return_exceptions=True)

        for handler, result in zip(
                [handler for handler in handlers if inspect.iscoroutinefunction(handler)],
                results,
        ):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, Exception):
                self.logger.exception(
                    "async_event_handler_crashed topic=%s handler=%r",
                    event.topic,
                    handler,
                    exc_info=result,
                )

    def _handlers_for(self, topic: str) -> list[EventHandler]:
        topic_key = self._normalize_topic(topic)

        handlers: list[EventHandler] = []
        handlers.extend(self._subscribers.get(topic_key, []))

        if topic_key != self.ALL_TOPICS:
            handlers.extend(self._subscribers.get(self.ALL_TOPICS, []))

        deduped: list[EventHandler] = []
        seen: set[int] = set()

        for handler in handlers:
            identity = id(handler)
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(handler)

        return deduped

    # ------------------------------------------------------------------
    # Runtime lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        async with self._state_lock:
            if self._running:
                return
            self._running = True
            self._closed = False

        try:
            while True:
                event = await self._queue.get()

                try:
                    if event.topic == self.SHUTDOWN_TOPIC:
                        break

                    await self._deliver(event)

                except asyncio.CancelledError:
                    raise

                except Exception:
                    self.logger.exception(
                        "event_delivery_failed topic=%s sequence=%s",
                        getattr(event, "topic", ""),
                        getattr(event, "sequence", None),
                    )

                finally:
                    self._queue.task_done()

        finally:
            async with self._state_lock:
                self._running = False
                self._dispatcher_task = None

    def run_in_background(self) -> asyncio.Task[Any]:
        if self._closed:
            self._closed = False

        task = self._dispatcher_task

        if task is not None and not task.done():
            return task

        self._dispatcher_task = asyncio.create_task(
            self.start(),
            name="derivatives_event_bus",
        )

        return self._dispatcher_task

    async def join(self) -> None:
        await self._queue.join()

    async def shutdown(self, *, drain: bool = True, timeout: float = 10.0) -> None:
        self._closed = True

        task = self._dispatcher_task

        if task is None or task.done():
            async with self._state_lock:
                self._running = False
                self._dispatcher_task = None
            return

        current_task = asyncio.current_task()
        if task is current_task:
            self._running = False
            return

        if drain:
            with suppress(Exception):
                await asyncio.wait_for(self._queue.join(), timeout=timeout)

        async with self._publish_lock:
            event = DerivativesEvent(
                topic=self.SHUTDOWN_TOPIC,
                data={},
                source="system",
                metadata={},
                sequence=self._sequence,
            )
            self._sequence += 1
            self.history.append(event)

        await self._queue.put(event)

        try:
            await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        self._dispatcher_task = None

    # ------------------------------------------------------------------
    # Utility API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return bool(self._running)

    @property
    def is_closed(self) -> bool:
        return bool(self._closed)

    @property
    def sequence(self) -> int:
        return int(self._sequence)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def recent_events(
            self,
            *,
            topic: str | None = None,
            limit: int = 1000,
    ) -> list[Any]:
        items = list(self.history)

        if topic is not None:
            topic_key = self._normalize_topic(topic)
            items = [event for event in items if event.topic == topic_key]

        return items[-max(1, int(limit or 1000)):]

    @staticmethod
    def _normalize_topic(topic: Any) -> str:
        text = str(topic or "").strip()
        return text or "unknown"


__all__ = ["EventBus", "EventHandler"]