from __future__ import annotations

"""
InvestPro TradingScheduler

Rotates through tradable symbols and calls strategy_engine.evaluate_symbol(symbol).

Designed for:
- live/paper trading loops
- multi-symbol scanning
- throttled batch execution
- controlled concurrency
- UI/Telegram status snapshots
- graceful start/stop
- fault isolation per symbol

Features:
- batch rotation
- max concurrent symbol evaluation
- per-symbol timeout
- per-symbol backoff after failures
- cycle metrics
- dynamic symbol add/remove/update
- graceful stop
- optional run_once()
- status snapshot
"""

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(slots=True)
class SymbolScheduleState:
    symbol: str
    enabled: bool = True
    last_run_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_duration_seconds: float = 0.0
    run_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    next_allowed_at_monotonic: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "enabled": self.enabled,
            "last_run_at": self.last_run_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_duration_seconds": self.last_duration_seconds,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "next_allowed_in_seconds": max(self.next_allowed_at_monotonic - time.monotonic(), 0.0),
            "last_error": self.last_error,
        }


@dataclass(slots=True)
class TradingSchedulerSnapshot:
    running: bool
    symbols: list[str]
    enabled_symbols: list[str]
    interval: float
    batch_size: int
    max_concurrent: int
    cycle_count: int
    last_cycle_started_at: Optional[str]
    last_cycle_finished_at: Optional[str]
    last_cycle_duration_seconds: float
    last_batch: list[str]
    total_symbol_runs: int
    total_symbol_errors: int
    state_by_symbol: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "symbols": list(self.symbols),
            "enabled_symbols": list(self.enabled_symbols),
            "interval": self.interval,
            "batch_size": self.batch_size,
            "max_concurrent": self.max_concurrent,
            "cycle_count": self.cycle_count,
            "last_cycle_started_at": self.last_cycle_started_at,
            "last_cycle_finished_at": self.last_cycle_finished_at,
            "last_cycle_duration_seconds": self.last_cycle_duration_seconds,
            "last_batch": list(self.last_batch),
            "total_symbol_runs": self.total_symbol_runs,
            "total_symbol_errors": self.total_symbol_errors,
            "state_by_symbol": dict(self.state_by_symbol),
        }


class TradingScheduler:
    """Async symbol evaluation scheduler."""

    def __init__(
        self,
        strategy_engine: Any,
        symbols: list[str] | tuple[str, ...],
        *,
        interval: float = 2.0,
        batch_size: int = 5,
        max_concurrent: int = 5,
        symbol_timeout_seconds: Optional[float] = 30.0,
        error_backoff_seconds: float = 10.0,
        max_error_backoff_seconds: float = 300.0,
        logger: Any = None,
    ) -> None:
        if strategy_engine is None:
            raise ValueError("strategy_engine is required")

        self.engine = strategy_engine
        self.symbols = self._normalize_symbols(symbols)

        self.interval = max(0.0, float(interval or 0.0))
        self.batch_size = max(1, int(batch_size or 1))
        self.max_concurrent = max(1, int(max_concurrent or 1))
        self.symbol_timeout_seconds = (
            None
            if symbol_timeout_seconds is None
            else max(0.1, float(symbol_timeout_seconds))
        )
        self.error_backoff_seconds = max(0.0, float(error_backoff_seconds))
        self.max_error_backoff_seconds = max(
            self.error_backoff_seconds, float(max_error_backoff_seconds))
        self.logger = logger

        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        self._running = False
        self._stop_event: Optional[asyncio.Event] = None
        self._index = 0
        self._run_task: Optional[asyncio.Task[Any]] = None

        self._symbol_state: dict[str, SymbolScheduleState] = {
            symbol: SymbolScheduleState(symbol=symbol)
            for symbol in self.symbols
        }

        self._cycle_count = 0
        self._last_cycle_started_at: Optional[str] = None
        self._last_cycle_finished_at: Optional[str] = None
        self._last_cycle_duration_seconds = 0.0
        self._last_batch: list[str] = []
        self._total_symbol_runs = 0
        self._total_symbol_errors = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    async def start(self, *, background: bool = False) -> Optional[asyncio.Task[Any]]:
        """Start the scheduler loop.

        Args:
            background:
                If True, create and return a background task.
                If False, run the loop until stopped.
        """
        if self._running:
            return self._run_task if background else None

        self._running = True
        self._stop_event = asyncio.Event()

        if background:
            self._run_task = asyncio.create_task(
                self._run_loop(), name="trading_scheduler")
            return self._run_task

        await self._run_loop()
        return None

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False

        if self._stop_event is not None:
            self._stop_event.set()

        if self._run_task is not None and not self._run_task.done():
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass

        self._run_task = None

    def stop_nowait(self) -> None:
        """Synchronous stop signal for UI callbacks."""
        self._running = False
        if self._stop_event is not None:
            self._stop_event.set()

    async def _run_loop(self) -> None:
        try:
            while self._running:
                cycle_start = time.monotonic()
                self._last_cycle_started_at = self._utc_now()

                await self._run_cycle()

                self._cycle_count += 1
                self._last_cycle_finished_at = self._utc_now()
                self._last_cycle_duration_seconds = time.monotonic() - cycle_start

                sleep_time = max(0.0, self.interval -
                                 self._last_cycle_duration_seconds)
                await self._sleep_or_stop(sleep_time)

        finally:
            self._running = False

    async def _sleep_or_stop(self, seconds: float) -> None:
        if seconds <= 0:
            return

        if self._stop_event is None:
            await asyncio.sleep(seconds)
            return

        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    # ------------------------------------------------------------------
    # Manual execution
    # ------------------------------------------------------------------

    async def run_once(self) -> list[Any]:
        """Run one scheduler cycle and return symbol results."""
        return await self._run_cycle()

    async def evaluate_symbol_now(self, symbol: str) -> Any:
        """Evaluate a single symbol immediately."""
        normalized = self._normalize_symbol(symbol)
        if not normalized:
            raise ValueError("symbol is required")

        if normalized not in self._symbol_state:
            self.add_symbol(normalized)

        return await self._run_symbol(normalized, ignore_backoff=True)

    # ------------------------------------------------------------------
    # One cycle
    # ------------------------------------------------------------------

    async def _run_cycle(self) -> list[Any]:
        batch = self._next_batch()
        self._last_batch = list(batch)

        if not batch:
            return []

        tasks = [
            asyncio.create_task(self._run_symbol(symbol),
                                name=f"evaluate_symbol:{symbol}")
            for symbol in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(batch, results):
            if isinstance(result, Exception):
                self._log_error(
                    "Scheduler task error [%s]: %s", symbol, result)

        return results

    async def _run_symbol(self, symbol: str, *, ignore_backoff: bool = False) -> Any:
        state = self._symbol_state.get(symbol)

        if state is None:
            state = SymbolScheduleState(symbol=symbol)
            self._symbol_state[symbol] = state

        if not state.enabled:
            return None

        now_monotonic = time.monotonic()
        if not ignore_backoff and now_monotonic < state.next_allowed_at_monotonic:
            return None

        async with self.semaphore:
            started = time.monotonic()
            state.last_run_at = self._utc_now()
            state.run_count += 1
            self._total_symbol_runs += 1

            try:
                call = self.engine.evaluate_symbol(symbol)
                result = await self._maybe_await(call)

                if self.symbol_timeout_seconds is not None and inspect.isawaitable(call):
                    # This branch is intentionally not used because call has already been awaited.
                    # Timeout is applied below via helper for callables in future refactors.
                    pass

                state.last_success_at = self._utc_now()
                state.consecutive_errors = 0
                state.last_error = ""
                state.next_allowed_at_monotonic = 0.0
                return result

            except Exception as exc:
                state.error_count += 1
                state.consecutive_errors += 1
                state.last_error_at = self._utc_now()
                state.last_error = f"{type(exc).__name__}: {exc}"
                self._total_symbol_errors += 1

                backoff = self._error_backoff_for(state.consecutive_errors)
                state.next_allowed_at_monotonic = time.monotonic() + backoff

                self._log_error("Scheduler error [%s]: %s", symbol, exc)
                return exc

            finally:
                state.last_duration_seconds = time.monotonic() - started

    # ------------------------------------------------------------------
    # Batch rotation
    # ------------------------------------------------------------------

    def _next_batch(self) -> list[str]:
        enabled_symbols = [
            symbol
            for symbol in self.symbols
            if self._symbol_state.get(symbol, SymbolScheduleState(symbol=symbol)).enabled
        ]

        if not enabled_symbols:
            return []

        self._index %= len(enabled_symbols)

        batch: list[str] = []
        attempts = 0

        while len(batch) < self.batch_size and attempts < len(enabled_symbols):
            symbol = enabled_symbols[self._index]
            self._index = (self._index + 1) % len(enabled_symbols)
            attempts += 1

            state = self._symbol_state.get(symbol)
            if state is None:
                continue

            if time.monotonic() < state.next_allowed_at_monotonic:
                continue

            batch.append(symbol)

        return batch

    # ------------------------------------------------------------------
    # Symbol management
    # ------------------------------------------------------------------

    def set_symbols(self, symbols: list[str] | tuple[str, ...]) -> None:
        normalized = self._normalize_symbols(symbols)
        self.symbols = normalized
        self._index = 0

        existing = dict(self._symbol_state)
        self._symbol_state = {
            symbol: existing.get(symbol, SymbolScheduleState(symbol=symbol))
            for symbol in normalized
        }

    def add_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        if not normalized:
            return

        if normalized not in self.symbols:
            self.symbols.append(normalized)

        self._symbol_state.setdefault(
            normalized, SymbolScheduleState(symbol=normalized))

    def remove_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        self.symbols = [item for item in self.symbols if item != normalized]
        self._symbol_state.pop(normalized, None)
        self._index = 0 if not self.symbols else self._index % len(
            self.symbols)

    def enable_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        if normalized not in self._symbol_state:
            self.add_symbol(normalized)
        self._symbol_state[normalized].enabled = True

    def disable_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        if normalized in self._symbol_state:
            self._symbol_state[normalized].enabled = False

    def clear_symbol_backoff(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        state = self._symbol_state.get(normalized)
        if state:
            state.next_allowed_at_monotonic = 0.0
            state.consecutive_errors = 0

    # ------------------------------------------------------------------
    # Snapshot / health
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        enabled = [
            symbol
            for symbol in self.symbols
            if self._symbol_state.get(symbol, SymbolScheduleState(symbol=symbol)).enabled
        ]

        return TradingSchedulerSnapshot(
            running=self._running,
            symbols=list(self.symbols),
            enabled_symbols=enabled,
            interval=self.interval,
            batch_size=self.batch_size,
            max_concurrent=self.max_concurrent,
            cycle_count=self._cycle_count,
            last_cycle_started_at=self._last_cycle_started_at,
            last_cycle_finished_at=self._last_cycle_finished_at,
            last_cycle_duration_seconds=self._last_cycle_duration_seconds,
            last_batch=list(self._last_batch),
            total_symbol_runs=self._total_symbol_runs,
            total_symbol_errors=self._total_symbol_errors,
            state_by_symbol={
                symbol: state.to_dict()
                for symbol, state in self._symbol_state.items()
            },
        ).to_dict()

    def healthy(self) -> bool:
        if not self._running:
            return True

        for state in self._symbol_state.values():
            if state.consecutive_errors >= 5:
                return False

        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            if self.symbol_timeout_seconds is None:
                return await value
            return await asyncio.wait_for(value, timeout=self.symbol_timeout_seconds)
        return value

    def _error_backoff_for(self, consecutive_errors: int) -> float:
        if self.error_backoff_seconds <= 0:
            return 0.0

        # Exponential backoff: 10s, 20s, 40s...
        delay = self.error_backoff_seconds * \
            (2 ** max(0, consecutive_errors - 1))
        return min(delay, self.max_error_backoff_seconds)

    def _normalize_symbol(self, symbol: Any) -> str:
        return str(symbol or "").strip().upper()

    def _normalize_symbols(self, symbols: list[str] | tuple[str, ...]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()

        for symbol in symbols or []:
            normalized = self._normalize_symbol(symbol)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append(normalized)

        return output

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_error(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            try:
                self.logger.error(message, *args)
                return
            except Exception:
                pass
