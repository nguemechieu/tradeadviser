import asyncio
import time


class TradingScheduler:

    def __init__(
            self,
            strategy_engine,
            symbols,
            *,
            interval=2.0,
            batch_size=5,
            max_concurrent=5,
            logger=None,
    ):
        self.engine = strategy_engine
        self.symbols = list(symbols)
        self.interval = interval
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.logger = logger

        self._running = False
        self._index = 0

    # =========================
    # START
    # =========================
    async def start(self):
        self._running = True

        while self._running:
            start_time = time.time()

            await self._run_cycle()

            elapsed = time.time() - start_time
            sleep_time = max(0, self.interval - elapsed)

            await asyncio.sleep(sleep_time)

    # =========================
    # STOP
    # =========================
    def stop(self):
        self._running = False

    # =========================
    # ONE CYCLE
    # =========================
    async def _run_cycle(self):

        batch = self._next_batch()

        tasks = [
            self._run_symbol(symbol)
            for symbol in batch
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    # =========================
    # SYMBOL EXECUTION
    # =========================
    async def _run_symbol(self, symbol):

        async with self.semaphore:
            try:
                await self.engine.evaluate_symbol(symbol)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Scheduler error [{symbol}]: {e}")

    # =========================
    # BATCH ROTATION
    # =========================
    def _next_batch(self):

        if not self.symbols:
            return []

        start = self._index
        end = start + self.batch_size

        batch = self.symbols[start:end]

        self._index = end % len(self.symbols)

        return batch