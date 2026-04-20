import asyncio
import time
from core.scheduler.utils.utils import dynamic_based_on_latency


class EventScheduler:

    def __init__(
            self,
            event_bus,
            symbols,
            *,
            interval=2.0,
            batch_size=5,
            logger=None,
    ):
        self.bus = event_bus
        self.symbols = list(symbols)
        self.interval = interval
        self.batch_size = batch_size
        self.logger = logger

        self._running = False
        self._index = 0

    # =========================
    # START
    # =========================
    async def start(self):

        self._running = True

        while self._running:


            await self._tick()
            await asyncio.sleep(self.interval)


    def stop(self):
        self._running = False

    # =========================
    # ONE TICK
    # =========================
    async def _tick(self):

        batch = self._next_batch()

        for symbol in batch:
            await self.bus.publish(
                "scheduler.tick",
                {"symbol": symbol},
                source="scheduler"
            )

    # =========================
    # ROTATION
    # =========================
    def _next_batch(self):

        if not self.symbols:
            return []

        start = self._index
        end = start + self.batch_size

        batch = self.symbols[start:end]
        self._index = end % len(self.symbols)

        return batch