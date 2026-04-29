from __future__ import annotations

from events.event_bus import build_event_bus

"""
InvestPro MultiSymbolOrchestrator

Coordinates multi-symbol trading workers and shared system services.

Responsibilities:
- Build or accept shared event bus
- Build portfolio manager
- Build market data engine
- Build trading engine
- Create SymbolWorker per symbol
- Start workers with staggered startup delays
- Track system state
- Stop workers cleanly
- Expose runtime snapshot for UI / Telegram / health checks

This orchestrator is meant to sit above SymbolWorker and TradingEngine.
"""

import asyncio
import contextlib
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from core.system_state import SystemState

try:
    from core.scheduler.scheduler import Scheduler
except Exception:  # pragma: no cover
    Scheduler = None  # type: ignore

try:
    from events.event_bus.event_bus import EventBus
except Exception:  # pragma: no cover
    EventBus = None  # type: ignore

from worker.symbol_worker import SymbolWorker
from engines.trading_engine import TradingEngine
from manager.portfolio_manager import PortfolioManager
from engines.market_data_engine import MarketDataEngine


@dataclass(slots=True)
class WorkerRuntimeState:
    symbol: str
    task_name: str
    running: bool = False
    done: bool = False
    cancelled: bool = False
    error: str = ""
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "task_name": self.task_name,
            "running": self.running,
            "done": self.done,
            "cancelled": self.cancelled,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class MultiSymbolOrchestrator:
    """Start and stop a SymbolWorker per symbol."""

    def __init__(
        self,
        controller: Any,
        broker: Any,
        strategy: Any,
        execution_manager: Any,
        risk_engine: Any,
        signal_processor: Optional[Any] = None,
        *,
        event_bus: Optional[Any] = None,
        portfolio_manager: Optional[Any] = None,
        market_data_engine: Optional[Any] = None,
        trading_engine: Optional[Any] = None,
        logger: Optional[logging.Logger] = None,
        default_timeframe: str = "1h",
        default_limit: int = 240,
        poll_interval: float = 6.0,
        startup_stagger_seconds: float = 0.35,
        startup_stagger_modulo: int = 6,
        worker_shutdown_timeout_seconds: float = 15.0,
        mode: str = "paper",
    ) -> None:
        self.controller = controller
        self.broker = broker
        self.strategy = strategy
        self.execution_manager = execution_manager
        self.signal_processor = signal_processor
        self.risk_engine = risk_engine

        self.logger = logger or logging.getLogger(__name__)

        self.default_timeframe = str(default_timeframe or "1h")
        self.default_limit = max(1, int(default_limit or 240))
        self.poll_interval = max(0.1, float(poll_interval or 6.0))
        self.startup_stagger_seconds = max(
            0.0, float(startup_stagger_seconds or 0.0))
        self.startup_stagger_modulo = max(1, int(startup_stagger_modulo or 1))
        self.worker_shutdown_timeout_seconds = max(
            1.0, float(worker_shutdown_timeout_seconds))

        self.event_bus = event_bus or self._build_default_event_bus()
        self.portfolio_manager = portfolio_manager or PortfolioManager(
            self.event_bus)
        self.market_data_engine = market_data_engine or MarketDataEngine(
            self.broker, self.event_bus)

        self.engine = trading_engine or TradingEngine(
            self.market_data_engine,
            self.strategy,
            self.risk_engine,
            self.execution_manager,
            self.portfolio_manager,
        )

        self.state = SystemState(mode=mode)
        self.scheduler = Scheduler() if Scheduler is not None else None

        self.workers: list[Any] = []
        self.worker_tasks: list[asyncio.Task[Any]] = []
        self.worker_states: dict[str, WorkerRuntimeState] = {}

        self._running = False
        self._start_task: Optional[asyncio.Task[Any]] = None
        self._symbols: list[str] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    async def start(
        self,
        symbols: Optional[list[str] | tuple[str, ...]] = None,
        *,
        timeframe: Optional[str] = None,
        limit: Optional[int] = None,
        background: bool = False,
    ) -> Optional[asyncio.Task[Any]]:
        """Start all symbol workers.

        Args:
            symbols:
                Symbols to run.
            timeframe:
                Candle timeframe passed to each worker.
            limit:
                Historical candle limit passed to each worker.
            background:
                If True, run orchestrator in the background and return its task.
        """
        normalized_symbols = self._normalize_symbols(symbols or [])

        if not normalized_symbols:
            raise RuntimeError("No symbols provided")

        if self._running:
            self.logger.info("MultiSymbolOrchestrator already running")
            return self._start_task if background else None

        self._symbols = normalized_symbols
        self.state.set_symbols(normalized_symbols)
        self.state.set_timeframe(timeframe or self.default_timeframe)
        self.state.start("Multi-symbol orchestrator started.")
        self._running = True

        if background:
            self._start_task = asyncio.create_task(
                self._run_workers(
                    normalized_symbols,
                    timeframe=timeframe or self.default_timeframe,
                    limit=limit or self.default_limit,
                ),
                name="multi_symbol_orchestrator",
            )
            return self._start_task

        await self._run_workers(
            normalized_symbols,
            timeframe=timeframe or self.default_timeframe,
            limit=limit or self.default_limit,
        )
        return None

    async def _run_workers(
        self,
        symbols: list[str],
        *,
        timeframe: str,
        limit: int,
    ) -> None:
        await self._start_optional_service(self.event_bus, "event_bus")
        await self._start_optional_service(self.market_data_engine, "market_data_engine")
        await self._start_optional_service(self.portfolio_manager, "portfolio_manager")
        await self._start_optional_service(self.engine, "trading_engine")

        self.workers = []
        self.worker_tasks = []
        self.worker_states = {}

        for offset, symbol in enumerate(symbols):
            worker = self._create_worker(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                offset=offset,
            )

            task_name = f"symbol_worker:{symbol}"
            state = WorkerRuntimeState(
                symbol=symbol,
                task_name=task_name,
                running=True,
            )

            task = asyncio.create_task(
                self._run_worker_guarded(worker, state),
                name=task_name,
            )

            self.workers.append(worker)
            self.worker_tasks.append(task)
            self.worker_states[symbol] = state

        try:
            await asyncio.gather(*self.worker_tasks, return_exceptions=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.state.add_error(
                f"Orchestrator worker failure: {type(exc).__name__}: {exc}")
            self.logger.exception("MultiSymbolOrchestrator failed")
            raise
        finally:
            self.worker_tasks = [
                task for task in self.worker_tasks if not task.done()]
            if not self.worker_tasks:
                self._running = False

    async def _run_worker_guarded(self, worker: Any, runtime_state: WorkerRuntimeState) -> None:
        try:
            result = worker.run()
            await self._maybe_await(result)
        except asyncio.CancelledError:
            runtime_state.cancelled = True
            runtime_state.running = False
            runtime_state.done = True
            runtime_state.finished_at = self._utc_now()
            raise
        except Exception as exc:
            runtime_state.error = f"{type(exc).__name__}: {exc}"
            runtime_state.running = False
            runtime_state.done = True
            runtime_state.finished_at = self._utc_now()
            self.state.add_error(
                f"Worker failed [{runtime_state.symbol}]: {runtime_state.error}")
            self.logger.exception(
                "Symbol worker failed [%s]", runtime_state.symbol)
            raise
        finally:
            if not runtime_state.done:
                runtime_state.running = False
                runtime_state.done = True
                runtime_state.finished_at = self._utc_now()

    async def shutdown(self) -> None:
        """Stop workers and shared services cleanly."""
        self._running = False
        self.state.stop("Trading system stopped.")

        for worker in list(self.workers):
            self._stop_worker_flag(worker)

        tasks = list(self.worker_tasks or [])
        self.worker_tasks = []

        for task in tasks:
            if not task.done():
                task.cancel()

        if tasks:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=self.worker_shutdown_timeout_seconds,
                )

        for state in self.worker_states.values():
            if not state.done:
                state.running = False
                state.done = True
                state.finished_at = self._utc_now()

        await self._stop_optional_service(self.engine, "trading_engine")
        await self._stop_optional_service(self.market_data_engine, "market_data_engine")
        await self._stop_optional_service(self.portfolio_manager, "portfolio_manager")
        await self._stop_optional_service(self.event_bus, "event_bus")

        if self._start_task is not None and not self._start_task.done():
            self._start_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._start_task

        self._start_task = None

        self.logger.info("Trading system stopped")

    stop = shutdown

    # ------------------------------------------------------------------
    # Worker creation
    # ------------------------------------------------------------------

    def _create_worker(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
        offset: int,
    ) -> Any:
        startup_delay = (offset % self.startup_stagger_modulo) * \
            self.startup_stagger_seconds

        return SymbolWorker(
            symbol,
            self.broker,
            self.strategy,
            self.execution_manager,
            timeframe,
            limit,
            controller=self.controller,
            startup_delay=startup_delay,
            poll_interval=self.poll_interval,
            signal_processor=self.signal_processor,
        )

    def _stop_worker_flag(self, worker: Any) -> None:
        for attr in ("running", "_running", "active"):
            if hasattr(worker, attr):
                with contextlib.suppress(Exception):
                    setattr(worker, attr, False)

        stop_method = getattr(worker, "stop", None)
        if callable(stop_method):
            with contextlib.suppress(Exception):
                result = stop_method()
                # If stop() returns a coroutine, it will not be awaited here.
                # The task cancellation below still guarantees shutdown.

    # ------------------------------------------------------------------
    # Dynamic symbol management
    # ------------------------------------------------------------------

    async def add_symbol(
        self,
        symbol: str,
        *,
        timeframe: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> bool:
        normalized = self._normalize_symbol(symbol)
        if not normalized or normalized in self._symbols:
            return False

        self._symbols.append(normalized)
        self.state.add_symbol(normalized)

        if not self._running:
            return True

        worker = self._create_worker(
            symbol=normalized,
            timeframe=timeframe or self.state.timeframe or self.default_timeframe,
            limit=limit or self.default_limit,
            offset=len(self._symbols) - 1,
        )

        task_name = f"symbol_worker:{normalized}"
        runtime_state = WorkerRuntimeState(
            symbol=normalized,
            task_name=task_name,
            running=True,
        )

        task = asyncio.create_task(
            self._run_worker_guarded(worker, runtime_state),
            name=task_name,
        )

        self.workers.append(worker)
        self.worker_tasks.append(task)
        self.worker_states[normalized] = runtime_state

        return True

    async def remove_symbol(self, symbol: str) -> bool:
        normalized = self._normalize_symbol(symbol)
        if normalized not in self._symbols:
            return False

        self._symbols = [item for item in self._symbols if item != normalized]
        self.state.remove_symbol(normalized)

        remaining_workers = []
        for worker in self.workers:
            worker_symbol = self._normalize_symbol(
                getattr(worker, "symbol", ""))
            if worker_symbol == normalized:
                self._stop_worker_flag(worker)
            else:
                remaining_workers.append(worker)

        self.workers = remaining_workers

        remaining_tasks = []
        for task in self.worker_tasks:
            if task.get_name() == f"symbol_worker:{normalized}":
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            else:
                remaining_tasks.append(task)

        self.worker_tasks = remaining_tasks

        runtime_state = self.worker_states.get(normalized)
        if runtime_state:
            runtime_state.running = False
            runtime_state.done = True
            runtime_state.finished_at = self._utc_now()

        return True

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        worker_tasks = list(self.worker_tasks or [])

        return {
            "running": self._running,
            "symbols": list(self._symbols),
            "worker_count": len(self.workers),
            "active_worker_tasks": sum(1 for task in worker_tasks if not task.done()),
            "done_worker_tasks": sum(1 for task in worker_tasks if task.done()),
            "state": self.state.to_dict(),
            "workers": {
                symbol: state.to_dict()
                for symbol, state in self.worker_states.items()
            },
            "engine": self._snapshot_service(self.engine),
            "event_bus": self._snapshot_service(self.event_bus),
            "market_data_engine": self._snapshot_service(self.market_data_engine),
            "portfolio_manager": self._snapshot_service(self.portfolio_manager),
        }

    def healthy(self) -> bool:
        if self.state.kill_switch_active:
            return False

        failed_workers = [
            state for state in self.worker_states.values()
            if state.error
        ]

        if failed_workers:
            return False

        for service in (self.event_bus, self.market_data_engine, self.portfolio_manager, self.engine):
            healthy = getattr(service, "healthy", None)
            if callable(healthy):
                with contextlib.suppress(Exception):
                    if healthy() is False:
                        return False

        return True

    # ------------------------------------------------------------------
    # Service lifecycle helpers
    # ------------------------------------------------------------------

    async def _start_optional_service(self, service: Any, name: str) -> None:
        start = getattr(service, "start", None)
        if not callable(start):
            return

        try:
            try:
                result = start(background=True)
            except TypeError:
                result = start()

            await self._maybe_await(result)
            self.logger.debug("Started service: %s", name)
        except Exception as exc:
            self.logger.debug(
                "Optional service start failed [%s]: %s", name, exc)

    async def _stop_optional_service(self, service: Any, name: str) -> None:
        for method_name in ("stop", "shutdown", "close"):
            method = getattr(service, method_name, None)
            if not callable(method):
                continue

            try:
                result = method()
                await self._maybe_await(result)
                self.logger.debug(
                    "Stopped service: %s via %s", name, method_name)
                return
            except Exception as exc:
                self.logger.debug(
                    "Optional service stop failed [%s.%s]: %s", name, method_name, exc)

    def _snapshot_service(self, service: Any) -> dict[str, Any]:
        if service is None:
            return {}

        for method_name in ("snapshot", "to_dict", "status"):
            method = getattr(service, method_name, None)
            if callable(method):
                with contextlib.suppress(Exception):
                    result = method()
                    if isinstance(result, dict):
                        return result
                    return {"value": result}

        return {
            "class": service.__class__.__name__,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_default_event_bus(self) -> Any:
        if build_event_bus is not None:
            with contextlib.suppress(Exception):
                return build_event_bus(async_mode=True)

        if EventBus is not None:
            return EventBus()

        raise RuntimeError("No EventBus implementation available")

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

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
