import asyncio
import logging
import multiprocessing as mp
import pickle
from contextlib import suppress


def run_process(symbols, controller):
    from core.sopotek_trading import SopotekTrading

    async def runner():
        system = SopotekTrading(controller=controller)
        system.symbols = symbols
        await system.start()

    asyncio.run(runner())


class DistributedOrchestrator:
    """Launch symbol groups in separate processes when the controller is picklable."""

    def __init__(self, controller, max_workers=None, logger=None):
        self.controller = controller
        self.max_workers = max(1, int(max_workers or mp.cpu_count() or 1))
        self.logger = logger or logging.getLogger("DistributedOrchestrator")
        self.processes = []
        self.last_error = None

    def split_symbols(self, symbols):
        chunks = [[] for _ in range(self.max_workers)]

        for index, symbol in enumerate(symbols or []):
            chunks[index % self.max_workers].append(symbol)

        return [chunk for chunk in chunks if chunk]

    def _spawn_payload_is_picklable(self, symbols):
        try:
            pickle.dumps((list(symbols or []), self.controller))
        except Exception as exc:
            self.last_error = exc
            self.logger.warning(
                "distributed_orchestrator_disabled reason=unpicklable_controller error=%s",
                exc,
            )
            return False
        return True

    def start(self, symbols):
        chunks = self.split_symbols(symbols)
        if not chunks:
            return False
        if not self._spawn_payload_is_picklable(symbols):
            return False

        print(f"🔥 Starting {len(chunks)} processes")

        started = []
        try:
            for chunk in chunks:
                process = mp.Process(target=run_process, args=(chunk, self.controller))
                process.start()
                started.append(process)
        except Exception as exc:
            self.last_error = exc
            self.logger.warning("distributed_orchestrator_start_failed error=%s", exc)
            for process in started:
                with suppress(Exception):
                    process.terminate()
                with suppress(Exception):
                    process.join(timeout=2.0)
            return False

        self.processes.extend(started)
        return True

    def stop(self):
        for process in self.processes:
            with suppress(Exception):
                process.terminate()
            with suppress(Exception):
                process.join(timeout=2.0)
        self.processes = []
