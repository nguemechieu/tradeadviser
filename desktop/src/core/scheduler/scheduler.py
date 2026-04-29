from __future__ import annotations

"""
InvestPro Scheduler

A lightweight asyncio scheduler for managing background tasks.

Supports:
- one-shot coroutine tasks
- recurring interval jobs
- named tasks
- graceful start/stop
- task cancellation
- exception capture
- status snapshots
- health checks
- sync or async callable support

Typical usage:
    scheduler = Scheduler()

    scheduler.add_task(my_async_worker(), name="worker")
    scheduler.add_interval_task(fetch_prices, interval_seconds=5, name="price_feed")

    await scheduler.start()
    ...
    await scheduler.stop()
"""

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Coroutine, Optional


@dataclass(slots=True)
class ScheduledTaskInfo:
    name: str
    kind: str = "task"  # task, interval
    status: str = "pending"  # pending, running, completed, failed, cancelled
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    run_count: int = 0
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


class Scheduler:
    """Manage asyncio background tasks for InvestPro."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        cancel_timeout_seconds: float = 10.0,
        stop_on_error: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.cancel_timeout_seconds = max(0.1, float(cancel_timeout_seconds))
        self.stop_on_error = bool(stop_on_error)

        self._pending: list[tuple[str, Callable[..., Any] | Awaitable[Any],
                                  tuple[Any, ...], dict[str, Any], dict[str, Any]]] = []
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._task_info: dict[str, ScheduledTaskInfo] = {}

        self._running = False
        self._stopping = False
        self._started_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    @property
    def tasks(self) -> list[asyncio.Task[Any]]:
        """Backward-compatible list of active asyncio tasks."""
        return list(self._tasks.values())

    # ------------------------------------------------------------------
    # Add tasks
    # ------------------------------------------------------------------

    def add_task(
        self,
        coro_or_callable: Callable[..., Any] | Awaitable[Any],
        *args: Any,
        name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Add a one-shot coroutine or callable.

        Accepts:
            scheduler.add_task(my_coro())
            scheduler.add_task(my_async_func, arg1, arg2)
            scheduler.add_task(my_sync_func, arg1, arg2)
        """
        task_name = self._unique_name(
            name or self._infer_name(coro_or_callable))

        info = ScheduledTaskInfo(
            name=task_name,
            kind="task",
            metadata=dict(metadata or {}),
        )

        self._task_info[task_name] = info

        if self._running:
            self._tasks[task_name] = asyncio.create_task(
                self._run_once(task_name, coro_or_callable, args, kwargs),
                name=task_name,
            )
        else:
            self._pending.append(
                (task_name, coro_or_callable, args, kwargs, dict(metadata or {})))

        return task_name

    def add_interval_task(
        self,
        func: Callable[..., Any],
        *args: Any,
        interval_seconds: float,
        name: Optional[str] = None,
        run_immediately: bool = True,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Add a recurring task that runs every interval_seconds."""
        if not callable(func):
            raise TypeError("func must be callable for interval tasks")

        interval = max(0.1, float(interval_seconds))
        task_name = self._unique_name(name or self._infer_name(func))

        info = ScheduledTaskInfo(
            name=task_name,
            kind="interval",
            metadata={
                **dict(metadata or {}),
                "interval_seconds": interval,
                "run_immediately": bool(run_immediately),
            },
        )

        self._task_info[task_name] = info

        runner_kwargs = {
            "interval_seconds": interval,
            "run_immediately": bool(run_immediately),
            "func": func,
            "args": args,
            "kwargs": kwargs,
        }

        if self._running:
            self._tasks[task_name] = asyncio.create_task(
                self._run_interval(task_name, **runner_kwargs),
                name=task_name,
            )
        else:
            self._pending.append(
                (
                    task_name,
                    self._interval_marker,
                    (),
                    runner_kwargs,
                    dict(metadata or {}),
                )
            )

        return task_name

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, *, wait: bool = False) -> None:
        """Start scheduled tasks.

        Args:
            wait:
                If True, wait until all current tasks finish.
                For interval tasks, wait=True will run until cancelled/stopped.
        """
        if self._running:
            if wait:
                await self.wait()
            return

        self._running = True
        self._stopping = False
        self._started_at = time.time()

        pending = list(self._pending)
        self._pending.clear()

        for task_name, target, args, kwargs, metadata in pending:
            if target is self._interval_marker:
                task = asyncio.create_task(
                    self._run_interval(task_name, **kwargs),
                    name=task_name,
                )
            else:
                task = asyncio.create_task(
                    self._run_once(task_name, target, args, kwargs),
                    name=task_name,
                )

            self._tasks[task_name] = task

        if wait:
            await self.wait()

    async def wait(self) -> None:
        """Wait for active tasks to complete."""
        if not self._tasks:
            return

        results = await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self.logger.debug(
                    "Scheduled task finished with error: %s", result)

    async def stop(self) -> None:
        """Cancel all running tasks gracefully."""
        self._stopping = True
        self._running = False

        if not self._tasks:
            return

        for task in self._tasks.values():
            if not task.done():
                task.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks.values(), return_exceptions=True),
                timeout=self.cancel_timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                "Scheduler stop timed out after %.2fs", self.cancel_timeout_seconds)

        for task_name, task in list(self._tasks.items()):
            info = self._task_info.get(task_name)
            if info is None:
                continue

            if task.cancelled():
                info.status = "cancelled"
                info.finished_at = self._utc_now()
            elif task.done() and task.exception() is not None:
                info.status = "failed"
                info.error = repr(task.exception())
                info.finished_at = self._utc_now()

        self._tasks.clear()
        self._stopping = False

    async def restart(self, *, wait: bool = False) -> None:
        await self.stop()
        await self.start(wait=wait)

    # ------------------------------------------------------------------
    # Task control
    # ------------------------------------------------------------------

    async def cancel_task(self, name: str) -> bool:
        task_name = str(name or "").strip()
        task = self._tasks.get(task_name)

        if task is None:
            return False

        if not task.done():
            task.cancel()

        try:
            await asyncio.wait_for(task, timeout=self.cancel_timeout_seconds)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            self.logger.warning("Task cancellation timed out: %s", task_name)
        except Exception as exc:
            self.logger.debug(
                "Task cancellation completed with error for %s: %s", task_name, exc)

        info = self._task_info.get(task_name)
        if info:
            info.status = "cancelled"
            info.finished_at = self._utc_now()

        self._tasks.pop(task_name, None)
        return True

    def remove_pending_task(self, name: str) -> bool:
        task_name = str(name or "").strip()
        before = len(self._pending)
        self._pending = [
            item for item in self._pending if item[0] != task_name]

        removed = len(self._pending) != before

        if removed:
            self._task_info.pop(task_name, None)

        return removed

    # ------------------------------------------------------------------
    # Runners
    # ------------------------------------------------------------------

    async def _run_once(
        self,
        task_name: str,
        target: Callable[..., Any] | Awaitable[Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        info = self._task_info.setdefault(
            task_name, ScheduledTaskInfo(name=task_name))
        info.status = "running"
        info.started_at = self._utc_now()

        try:
            result = self._call_target(target, *args, **kwargs)
            result = await self._maybe_await(result)

            info.status = "completed"
            info.finished_at = self._utc_now()
            info.run_count += 1
            return result

        except asyncio.CancelledError:
            info.status = "cancelled"
            info.finished_at = self._utc_now()
            raise

        except Exception as exc:
            info.status = "failed"
            info.error = f"{type(exc).__name__}: {exc}"
            info.finished_at = self._utc_now()
            self.logger.exception("Scheduled task failed: %s", task_name)

            if self.stop_on_error:
                self._running = False

            return None

    async def _run_interval(
        self,
        task_name: str,
        *,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        interval_seconds: float,
        run_immediately: bool,
    ) -> None:
        info = self._task_info.setdefault(
            task_name, ScheduledTaskInfo(name=task_name, kind="interval"))
        info.status = "running"
        info.started_at = self._utc_now()

        if not run_immediately:
            info.next_run_at = self._utc_now_after(interval_seconds)
            await asyncio.sleep(interval_seconds)

        while self._running and not self._stopping:
            try:
                info.last_run_at = self._utc_now()
                result = func(*args, **kwargs)
                await self._maybe_await(result)
                info.run_count += 1
                info.status = "running"
                info.error = None

            except asyncio.CancelledError:
                info.status = "cancelled"
                info.finished_at = self._utc_now()
                raise

            except Exception as exc:
                info.status = "failed"
                info.error = f"{type(exc).__name__}: {exc}"
                self.logger.exception("Interval task failed: %s", task_name)

                if self.stop_on_error:
                    self._running = False
                    break

            info.next_run_at = self._utc_now_after(interval_seconds)

            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                info.status = "cancelled"
                info.finished_at = self._utc_now()
                raise

        if info.status != "cancelled":
            info.status = "completed"
            info.finished_at = self._utc_now()

    # ------------------------------------------------------------------
    # Status / health
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "stopping": self._stopping,
            "started_at": self._started_at,
            "uptime_seconds": self.uptime_seconds(),
            "pending_count": len(self._pending),
            "active_count": len(self._tasks),
            "tasks": {
                name: info.to_dict()
                for name, info in self._task_info.items()
            },
        }

    def task_status(self, name: str) -> Optional[dict[str, Any]]:
        info = self._task_info.get(str(name or "").strip())
        return info.to_dict() if info else None

    def has_task(self, name: str) -> bool:
        task_name = str(name or "").strip()
        return task_name in self._task_info

    def healthy(self) -> bool:
        if not self._running:
            return True

        for info in self._task_info.values():
            if info.status == "failed":
                return False

        return True

    def uptime_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return max(time.time() - self._started_at, 0.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call_target(self, target: Callable[..., Any] | Awaitable[Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.isawaitable(target):
            if args or kwargs:
                raise TypeError(
                    "Cannot pass args/kwargs when target is already an awaitable")
            return target

        if callable(target):
            return target(*args, **kwargs)

        raise TypeError("Scheduled target must be callable or awaitable")

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _infer_name(self, target: Any) -> str:
        if callable(target):
            return getattr(target, "__name__", target.__class__.__name__)

        coroutine_name = getattr(target, "__name__", "")
        if coroutine_name:
            return coroutine_name

        code = getattr(target, "cr_code", None)
        if code is not None:
            return getattr(code, "co_name", "task")

        return "task"

    def _unique_name(self, base_name: str) -> str:
        base = str(base_name or "task").strip() or "task"

        if base not in self._task_info:
            return base

        index = 2
        while f"{base}_{index}" in self._task_info:
            index += 1

        return f"{base}_{index}"

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _utc_now_after(self, seconds: float) -> str:
        return datetime.fromtimestamp(
            time.time() + seconds, tz=timezone.utc
        ).isoformat()

    async def _interval_marker(self) -> None:
           """Internal marker used for pending interval jobs."""
           return None
