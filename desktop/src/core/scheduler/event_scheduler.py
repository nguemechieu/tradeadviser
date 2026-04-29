from __future__ import annotations

"""
InvestPro EventScheduler

Publishes scheduler tick events for rotating symbols.

This scheduler does not evaluate symbols directly. Instead, it emits events:

    topic: scheduler.tick
    payload:
        {
            "symbol": "BTC/USDT",
            "cycle_id": 1,
            "batch_index": 0,
            "batch_size": 5,
            "timestamp": "...",
        }

Downstream components can subscribe to scheduler.tick and decide what to do.

Designed for:
- event-driven trading loops
- symbol workers
- market-data refresh
- strategy scan triggers
- UI/Telegram health snapshots
- adaptive interval scheduling
"""

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from core.scheduler.utils.utils import dynamic_based_on_latency
except Exception:  # pragma: no cover
    dynamic_based_on_latency = None  # type: ignore


@dataclass(slots=True)
class SymbolTickState:
    symbol: str
    enabled: bool = True
    last_tick_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_latency_seconds: float = 0.0
    tick_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    next_allowed_at_monotonic: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "enabled": self.enabled,
            "last_tick_at": self.last_tick_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_latency_seconds": self.last_latency_seconds,
            "tick_count": self.tick_count,
            "error_count": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "next_allowed_in_seconds": max(self.next_allowed_at_monotonic - time.monotonic(), 0.0),
            "last_error": self.last_error,
        }


@dataclass(slots=True)
class EventSchedulerSnapshot:
    running: bool
    topic: str
    source: str
    symbols: list[str]
    enabled_symbols: list[str]
    interval: float
    current_interval: float
    batch_size: int
    cycle_count: int
    last_cycle_started_at: Optional[str]
    last_cycle_finished_at: Optional[str]
    last_cycle_duration_seconds: float
    last_batch: list[str]
    total_ticks: int
    total_errors: int
    state_by_symbol: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "topic": self.topic,
            "source": self.source,
            "symbols": list(self.symbols),
            "enabled_symbols": list(self.enabled_symbols),
            "interval": self.interval,
            "current_interval": self.current_interval,
            "batch_size": self.batch_size,
            "cycle_count": self.cycle_count,
            "last_cycle_started_at": self.last_cycle_started_at,
            "last_cycle_finished_at": self.last_cycle_finished_at,
            "last_cycle_duration_seconds": self.last_cycle_duration_seconds,
            "last_batch": list(self.last_batch),
            "total_ticks": self.total_ticks,
            "total_errors": self.total_errors,
            "state_by_symbol": dict(self.state_by_symbol),
        }


class EventScheduler:
    """Publish rotating scheduler tick events to an event bus."""

    def __init__(
        self,
        event_bus: Any,
        symbols: list[str] | tuple[str, ...],
        *,
        interval: float = 2.0,
        batch_size: int = 5,
        logger: Any = None,
        topic: str = "scheduler.tick",
        source: str = "scheduler",
        publish_timeout_seconds: Optional[float] = 10.0,
        error_backoff_seconds: float = 5.0,
        max_error_backoff_seconds: float = 120.0,
        adaptive_interval: bool = False,
        min_interval: float = 0.25,
        max_interval: float = 30.0,
        publish_concurrently: bool = False,
    ) -> None:
        if event_bus is None:
            raise ValueError("event_bus is required")

        self.bus = event_bus
        self.symbols = self._normalize_symbols(symbols)

        self.interval = max(0.0, float(interval or 0.0))
        self.current_interval = self.interval
        self.batch_size = max(1, int(batch_size or 1))

        self.logger = logger
        self.topic = str(topic or "scheduler.tick")
        self.source = str(source or "scheduler")

        self.publish_timeout_seconds = (
            None
            if publish_timeout_seconds is None
            else max(0.1, float(publish_timeout_seconds))
        )

        self.error_backoff_seconds = max(0.0, float(error_backoff_seconds))
        self.max_error_backoff_seconds = max(
            self.error_backoff_seconds, float(max_error_backoff_seconds))

        self.adaptive_interval = bool(adaptive_interval)
        self.min_interval = max(0.0, float(min_interval))
        self.max_interval = max(self.min_interval, float(max_interval))
        self.publish_concurrently = bool(publish_concurrently)

        self._running = False
        self._stop_event: Optional[asyncio.Event] = None
        self._run_task: Optional[asyncio.Task[Any]] = None
        self._index = 0

        self._symbol_state: dict[str, SymbolTickState] = {
            symbol: SymbolTickState(symbol=symbol)
            for symbol in self.symbols
        }

        self._cycle_count = 0
        self._total_ticks = 0
        self._total_errors = 0
        self._last_cycle_started_at: Optional[str] = None
        self._last_cycle_finished_at: Optional[str] = None
        self._last_cycle_duration_seconds = 0.0
        self._last_batch: list[str] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    async def start(self, *, background: bool = False) -> Optional[asyncio.Task[Any]]:
        """Start the event scheduler.

        Args:
            background:
                If True, starts the scheduler as an asyncio task and returns it.
                If False, runs until stopped.
        """
        if self._running:
            return self._run_task if background else None

        self._running = True
        self._stop_event = asyncio.Event()

        if background:
            self._run_task = asyncio.create_task(
                self._run_loop(), name="event_scheduler")
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

                await self._tick()

                self._cycle_count += 1
                self._last_cycle_finished_at = self._utc_now()
                self._last_cycle_duration_seconds = time.monotonic() - cycle_start

                self._update_adaptive_interval(
                    self._last_cycle_duration_seconds)

                sleep_time = max(0.0, self.current_interval -
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
    # Tick execution
    # ------------------------------------------------------------------

    async def run_once(self) -> list[Any]:
        """Publish one tick batch."""
        return await self._tick()

    async def tick_symbol_now(self, symbol: str) -> Any:
        """Publish one tick for a specific symbol immediately."""
        normalized = self._normalize_symbol(symbol)
        if not normalized:
            raise ValueError("symbol is required")

        if normalized not in self._symbol_state:
            self.add_symbol(normalized)

        return await self._publish_symbol_tick(
            normalized,
            cycle_id=self._cycle_count,
            batch_index=0,
            batch_size=1,
            ignore_backoff=True,
        )

    async def _tick(self) -> list[Any]:
        batch = self._next_batch()
        self._last_batch = list(batch)

        if not batch:
            return []

        if self.publish_concurrently:
            tasks = [
                asyncio.create_task(
                    self._publish_symbol_tick(
                        symbol,
                        cycle_id=self._cycle_count,
                        batch_index=index,
                        batch_size=len(batch),
                    ),
                    name=f"event_tick:{symbol}",
                )
                for index, symbol in enumerate(batch)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for index, symbol in enumerate(batch):
                result = await self._publish_symbol_tick(
                    symbol,
                    cycle_id=self._cycle_count,
                    batch_index=index,
                    batch_size=len(batch),
                )
                results.append(result)

        return results

    async def _publish_symbol_tick(
        self,
        symbol: str,
        *,
        cycle_id: int,
        batch_index: int,
        batch_size: int,
        ignore_backoff: bool = False,
    ) -> Any:
        state = self._symbol_state.get(symbol)

        if state is None:
            state = SymbolTickState(symbol=symbol)
            self._symbol_state[symbol] = state

        if not state.enabled:
            return None

        if not ignore_backoff and time.monotonic() < state.next_allowed_at_monotonic:
            return None

        started = time.monotonic()
        timestamp = self._utc_now()

        payload = {
            "symbol": symbol,
            "cycle_id": cycle_id,
            "batch_index": batch_index,
            "batch_size": batch_size,
            "timestamp": timestamp,
        }

        state.last_tick_at = timestamp
        state.tick_count += 1
        self._total_ticks += 1

        try:
            publish_result = self.bus.publish(
                self.topic,
                payload,
                source=self.source,
            )

            if inspect.isawaitable(publish_result):
                if self.publish_timeout_seconds is None:
                    result = await publish_result
                else:
                    result = await asyncio.wait_for(
                        publish_result,
                        timeout=self.publish_timeout_seconds,
                    )
            else:
                result = publish_result

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
            state.next_allowed_at_monotonic = time.monotonic(
            ) + self._error_backoff_for(state.consecutive_errors)
            self._total_errors += 1

            self._log_error(
                "EventScheduler publish error [%s]: %s", symbol, exc)
            return exc

        finally:
            state.last_latency_seconds = time.monotonic() - started

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def _next_batch(self) -> list[str]:
        enabled_symbols = [
            symbol
            for symbol in self.symbols
            if self._symbol_state.get(symbol, SymbolTickState(symbol=symbol)).enabled
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
        existing = dict(self._symbol_state)

        self.symbols = normalized
        self._symbol_state = {
            symbol: existing.get(symbol, SymbolTickState(symbol=symbol))
            for symbol in normalized
        }
        self._index = 0

    def add_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        if not normalized:
            return

        if normalized not in self.symbols:
            self.symbols.append(normalized)

        self._symbol_state.setdefault(
            normalized, SymbolTickState(symbol=normalized))

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
            if self._symbol_state.get(symbol, SymbolTickState(symbol=symbol)).enabled
        ]

        return EventSchedulerSnapshot(
            running=self._running,
            topic=self.topic,
            source=self.source,
            symbols=list(self.symbols),
            enabled_symbols=enabled,
            interval=self.interval,
            current_interval=self.current_interval,
            batch_size=self.batch_size,
            cycle_count=self._cycle_count,
            last_cycle_started_at=self._last_cycle_started_at,
            last_cycle_finished_at=self._last_cycle_finished_at,
            last_cycle_duration_seconds=self._last_cycle_duration_seconds,
            last_batch=list(self._last_batch),
            total_ticks=self._total_ticks,
            total_errors=self._total_errors,
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
    # Adaptive interval
    # ------------------------------------------------------------------

    def _update_adaptive_interval(self, latency_seconds: float) -> None:
        if not self.adaptive_interval:
            self.current_interval = self.interval
            return

        if callable(dynamic_based_on_latency):
            try:
                value = dynamic_based_on_latency(
                    base_interval=self.interval,
                    latency=latency_seconds,
                    min_interval=self.min_interval,
                    max_interval=self.max_interval,
                )
                self.current_interval = self._clamp(
                    float(value), self.min_interval, self.max_interval)
                return
            except TypeError:
                try:
                    value = dynamic_based_on_latency(
                        self.interval, latency_seconds)
                    self.current_interval = self._clamp(
                        float(value), self.min_interval, self.max_interval)
                    return
                except Exception:
                    pass
            except Exception:
                pass

        # Built-in fallback:
        # If the cycle is slow, slightly increase interval.
        # If the cycle is very fast, slowly return toward base interval.
        if latency_seconds > self.interval:
            self.current_interval = self._clamp(
                latency_seconds * 1.25, self.min_interval, self.max_interval)
        else:
            self.current_interval = self._clamp(
                self.interval, self.min_interval, self.max_interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_backoff_for(self, consecutive_errors: int) -> float:
        if self.error_backoff_seconds <= 0:
            return 0.0

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

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
