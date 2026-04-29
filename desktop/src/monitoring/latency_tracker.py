from __future__ import annotations

import math
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


def _now() -> float:
    return time.time()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


@dataclass(slots=True)
class LatencySnapshot:
    count: int = 0
    errors: int = 0
    total: int = 0
    avg: float = 0.0
    min: float = 0.0
    max: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    error_rate: float = 0.0
    last_latency: float | None = None
    last_error_at: float | None = None
    last_success_at: float | None = None
    updated_at: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "errors": self.errors,
            "total": self.total,
            "avg": self.avg,
            "min": self.min,
            "max": self.max,
            "p50": self.p50,
            "p90": self.p90,
            "p95": self.p95,
            "p99": self.p99,
            "error_rate": self.error_rate,
            "last_latency": self.last_latency,
            "last_error_at": self.last_error_at,
            "last_success_at": self.last_success_at,
            "updated_at": self.updated_at,
        }


class LatencyTracker:
    """Small rolling latency/error tracker for broker and API health.

    Store latencies in seconds.

    Example:
        tracker = LatencyTracker()
        tracker.record(0.123)
        tracker.record_error()
        print(tracker.stats())
    """

    def __init__(
            self,
            maxlen: int = 1000,
            *,
            slow_threshold_seconds: float = 1.0,
    ) -> None:
        self.maxlen = max(10, int(maxlen or 1000))
        self.slow_threshold_seconds = max(0.001, float(slow_threshold_seconds or 1.0))

        self._latencies: deque[float] = deque(maxlen=self.maxlen)
        self._events: deque[tuple[float, bool, float | None]] = deque(maxlen=self.maxlen)
        self._error_count = 0
        self._success_count = 0
        self._last_latency: float | None = None
        self._last_error_at: float | None = None
        self._last_success_at: float | None = None
        self._started_at = _now()

    def record(self, latency_seconds: float) -> float:
        """Record a successful request latency in seconds."""
        latency = max(0.0, _safe_float(latency_seconds, 0.0))
        now = _now()

        self._latencies.append(latency)
        self._events.append((now, False, latency))
        self._success_count += 1
        self._last_latency = latency
        self._last_success_at = now

        return latency

    def record_ms(self, latency_ms: float) -> float:
        """Record a successful request latency in milliseconds."""
        return self.record(_safe_float(latency_ms, 0.0) / 1000.0)

    def record_error(self, latency_seconds: float | None = None) -> None:
        """Record a failed request.

        Optionally include elapsed latency before failure.
        """
        now = _now()
        latency = None

        if latency_seconds is not None:
            latency = max(0.0, _safe_float(latency_seconds, 0.0))
            self._latencies.append(latency)
            self._last_latency = latency

        self._events.append((now, True, latency))
        self._error_count += 1
        self._last_error_at = now

    def reset(self) -> None:
        self._latencies.clear()
        self._events.clear()
        self._error_count = 0
        self._success_count = 0
        self._last_latency = None
        self._last_error_at = None
        self._last_success_at = None
        self._started_at = _now()

    def stats(self, *, window_seconds: float | None = None) -> dict[str, Any]:
        """Return latency stats.

        Compatible with your scheduler:

            stats["avg"]
            stats["p95"]
            stats["error_rate"]
        """
        events = list(self._events)

        if window_seconds is not None:
            cutoff = _now() - max(0.0, float(window_seconds))
            events = [event for event in events if event[0] >= cutoff]

        latencies = [
            float(latency)
            for _timestamp, is_error, latency in events
            if not is_error and latency is not None
        ]

        error_count = sum(1 for _timestamp, is_error, _latency in events if is_error)
        success_count = len(latencies)
        total = success_count + error_count

        if not events and window_seconds is None:
            latencies = list(self._latencies)
            error_count = self._error_count
            success_count = self._success_count
            total = success_count + error_count

        snapshot = LatencySnapshot(
            count=success_count,
            errors=error_count,
            total=total,
            avg=self._mean(latencies),
            min=min(latencies) if latencies else 0.0,
            max=max(latencies) if latencies else 0.0,
            p50=self._percentile(latencies, 50),
            p90=self._percentile(latencies, 90),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            error_rate=(error_count / total) if total else 0.0,
            last_latency=self._last_latency,
            last_error_at=self._last_error_at,
            last_success_at=self._last_success_at,
            updated_at=_now(),
        )

        return snapshot.to_dict()

    def health(self) -> dict[str, Any]:
        stats = self.stats()
        avg = float(stats.get("avg") or 0.0)
        p95 = float(stats.get("p95") or 0.0)
        error_rate = float(stats.get("error_rate") or 0.0)

        if error_rate >= 0.25:
            status = "degraded"
            reason = "high_error_rate"
        elif p95 >= self.slow_threshold_seconds * 2:
            status = "degraded"
            reason = "high_p95_latency"
        elif avg >= self.slow_threshold_seconds:
            status = "slow"
            reason = "high_average_latency"
        else:
            status = "healthy"
            reason = "ok"

        return {
            **stats,
            "status": status,
            "reason": reason,
            "slow_threshold_seconds": self.slow_threshold_seconds,
        }

    def is_healthy(self) -> bool:
        return self.health().get("status") in {"healthy", "slow"}

    def recent_latencies(self, limit: int = 100) -> list[float]:
        limit = max(1, int(limit or 100))
        return list(self._latencies)[-limit:]

    @staticmethod
    def _mean(values: list[float]) -> float:
        if not values:
            return 0.0
        try:
            return float(statistics.mean(values))
        except Exception:
            return sum(values) / max(1, len(values))

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0

        ordered = sorted(float(value) for value in values)
        if len(ordered) == 1:
            return ordered[0]

        pct = max(0.0, min(100.0, float(percentile)))
        rank = (pct / 100.0) * (len(ordered) - 1)
        lower = int(math.floor(rank))
        upper = int(math.ceil(rank))

        if lower == upper:
            return ordered[lower]

        weight = rank - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


__all__ = ["LatencySnapshot", "LatencyTracker"]