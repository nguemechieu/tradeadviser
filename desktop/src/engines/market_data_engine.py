import asyncio
import contextlib

from events.event import Event
from events.event_bus.event_types import EventType


class MarketDataEngine:

    def __init__(self, broker, event_bus):
        self.broker = broker
        self.bus = event_bus
        self._task = None
        self._running = False

    async def start(self):
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self.stream(), name="market_data_stream")

    async def stop(self):
        self._running = False
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def stream(self):
        try:
            while self._running:
                tick = await self.broker.fetch_ticker("BTC/USDT")

                event = Event(
                    EventType.MARKET_TICK,
                    tick
                )

                await self.bus.publish(event)
        except asyncio.CancelledError:
            raise
