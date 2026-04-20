from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict, deque
from typing import Any, Callable

from derivatives.core.models import DerivativesEvent

EventHandler = Callable[[DerivativesEvent], Any]


class EventBus:
    ALL_TOPICS = "*"
    SHUTDOWN_TOPIC = "__shutdown__"


    def __init__(self, *, history_size: int = 5000, logger: logging.Logger | None = None) -> None:

        self.logger = logger or logging.getLogger("DerivativesEventBus")
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[DerivativesEvent] = asyncio.Queue()
        self._dispatcher_task: asyncio.Task[Any] | None = None
        self._running = False
        self._sequence = 0

        self.history = deque(maxlen=max(100000, int(history_size or 5000)))


    def subscribe(self, topic: str, handler: EventHandler) -> EventHandler:
        self._subscribers[str(topic)].append(handler)
        return handler

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(str(topic), [])
        self._subscribers[str(topic)] = [item for item in handlers if item is not handler]

    async def publish(
        self,
        topic: str,
        data: Any,
        *,
        source: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> DerivativesEvent:
        event = DerivativesEvent(
            topic=str(topic),
            data=data,
            source=str(source),
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

    async def _deliver(self, event: DerivativesEvent) -> None:
        handlers = list(self._subscribers.get(event.topic, []))
        handlers.extend(self._subscribers.get(self.ALL_TOPICS, []))
        if not handlers:
            return
        tasks = []
        for handler in handlers:
            try:
                result = handler(event)
            except Exception:
                self.logger.exception("event_handler_crashed topic=%s handler=%s", event.topic, handler)
                continue
            if inspect.isawaitable(result):
                tasks.append(result)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self) -> None:
        self._running = True
        try:
            while self._running:
                event = await self._queue.get()
                try:
                    if event.topic == self.SHUTDOWN_TOPIC:
                        self._running = False
                        return
                    await self._deliver(event)
                finally:
                    self._queue.task_done()
        finally:
            self._running = False
            self._dispatcher_task = None

    def run_in_background(self) -> asyncio.Task[Any]:
        if self._dispatcher_task is not None and not self._dispatcher_task.done():
            return self._dispatcher_task
        self._dispatcher_task = asyncio.create_task(self.start(), name="derivatives_event_bus")
        return self._dispatcher_task

    async def join(self) -> None:
        await self._queue.join()

    async def shutdown(self) -> None:
        task = self._dispatcher_task if self._dispatcher_task is not None and not self._dispatcher_task.done() else None
        if task is None:
            self._running = False
            self._dispatcher_task = None
            return
        await self._queue.put(DerivativesEvent(topic=self.SHUTDOWN_TOPIC, data={}, source="system", sequence=self._sequence))
        self._sequence += 1
        await asyncio.gather(task, return_exceptions=True)
        self._dispatcher_task = None
