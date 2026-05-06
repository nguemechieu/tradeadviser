"""System Health Monitoring and Diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
from typing import Any, Callable

import psutil


class HealthStatus(Enum):
    """Overall system health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ResourceMetrics:
    """System resource usage metrics."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    disk_percent: float = 0.0
    open_files: int = 0
    network_connections: int = 0
    process_count: int = 0


@dataclass
class HealthCheck:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_healthy(self) -> bool:
        """Check if healthy."""
        return self.status == HealthStatus.HEALTHY


class SystemMonitor:
    """Monitor system resources and health."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("SystemMonitor")
        self._metrics_history: list[ResourceMetrics] = []
        self._max_history: int = 100

    def get_metrics(self) -> ResourceMetrics:
        """Get current system metrics.
        
        Returns:
            ResourceMetrics with current system state
        """
        try:
            process = psutil.Process()
            metrics = ResourceMetrics(
                cpu_percent=psutil.cpu_percent(interval=0.1),
                memory_percent=psutil.virtual_memory().percent,
                memory_mb=process.memory_info().rss / 1024 / 1024,
                disk_percent=psutil.disk_usage("/").percent,
                open_files=len(process.open_files()),
                network_connections=len(process.net_connections()),
                process_count=len(psutil.pids()),
            )
            
            # Keep history
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history:
                self._metrics_history.pop(0)
            
            return metrics
        except Exception as e:
            self.logger.error("Error getting metrics: %s", e)
            return ResourceMetrics()

    def get_avg_metrics(self, window: int = 10) -> ResourceMetrics:
        """Get average metrics over recent window.
        
        Args:
            window: Number of recent readings to average
            
        Returns:
            Averaged metrics
        """
        if not self._metrics_history:
            return ResourceMetrics()

        recent = self._metrics_history[-window:]
        if not recent:
            return ResourceMetrics()

        avg = ResourceMetrics(
            cpu_percent=sum(m.cpu_percent for m in recent) / len(recent),
            memory_percent=sum(m.memory_percent for m in recent) / len(recent),
            memory_mb=sum(m.memory_mb for m in recent) / len(recent),
            disk_percent=sum(m.disk_percent for m in recent) / len(recent),
            open_files=int(sum(m.open_files for m in recent) / len(recent)),
            network_connections=int(sum(m.network_connections for m in recent) / len(recent)),
            process_count=int(sum(m.process_count for m in recent) / len(recent)),
        )
        return avg

    def check_resources(self, thresholds: dict[str, float] | None = None) -> HealthCheck:
        """Check resource usage against thresholds.
        
        Args:
            thresholds: Dict of metric_name -> threshold_value
            
        Returns:
            HealthCheck result
        """
        thresholds = thresholds or {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
        }

        metrics = self.get_metrics()
        status = HealthStatus.HEALTHY
        issues = []

        for metric_name, threshold in thresholds.items():
            value = getattr(metrics, metric_name, 0)
            if value > threshold:
                status = HealthStatus.CRITICAL
                issues.append(f"{metric_name} at {value:.1f}% (threshold: {threshold}%)")

        message = ", ".join(issues) if issues else "All resources within limits"
        
        return HealthCheck(
            name="resource_check",
            status=status,
            message=message,
            details=vars(metrics),
        )


class ApplicationHealthMonitor:
    """Monitor application health across subsystems."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("AppHealthMonitor")
        self.system_monitor = SystemMonitor(logger)
        self._health_checks: dict[str, Callable[[], HealthCheck]] = {}
        self._last_results: dict[str, HealthCheck] = {}

    def register_check(self, name: str, check_func: Callable[[], HealthCheck]) -> None:
        """Register a health check.
        
        Args:
            name: Name of the check
            check_func: Async or sync function that returns HealthCheck
        """
        self._health_checks[name] = check_func
        self.logger.debug("Registered health check: %s", name)

    async def run_checks(self) -> dict[str, HealthCheck]:
        """Run all registered health checks.
        
        Returns:
            Dict of check_name -> HealthCheck result
        """
        results = {}
        
        # Always include resource check
        results["resources"] = self.system_monitor.check_resources()

        # Run registered checks
        for name, check_func in self._health_checks.items():
            try:
                if hasattr(check_func, "__await__"):
                    result = await check_func()
                else:
                    result = check_func()
                results[name] = result
            except Exception as e:
                self.logger.error("Health check %s failed: %s", name, e)
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.CRITICAL,
                    message=f"Check failed: {str(e)}",
                )

        self._last_results = results
        return results

    def get_overall_health(self) -> HealthStatus:
        """Get overall health status.
        
        Returns:
            Overall HealthStatus
        """
        if not self._last_results:
            return HealthStatus.UNKNOWN

        has_critical = any(
            c.status == HealthStatus.CRITICAL
            for c in self._last_results.values()
        )
        if has_critical:
            return HealthStatus.CRITICAL

        has_degraded = any(
            c.status == HealthStatus.DEGRADED
            for c in self._last_results.values()
        )
        if has_degraded:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_report(self) -> dict[str, Any]:
        """Get comprehensive health report.
        
        Returns:
            Detailed health report
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": self.get_overall_health().value,
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "details": check.details,
                }
                for name, check in self._last_results.items()
            },
        }

    def __repr__(self) -> str:
        health = self.get_overall_health()
        return f"AppHealth({health.value}, {len(self._last_results)} checks)"


class DiagnosticsEngine:
    """Comprehensive diagnostics and troubleshooting."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("DiagnosticsEngine")
        self.health_monitor = ApplicationHealthMonitor(logger)

    async def diagnose(self) -> dict[str, Any]:
        """Run comprehensive diagnostics.
        
        Returns:
            Diagnostic report
        """
        checks = await self.health_monitor.run_checks()
        
        issues = []
        for name, check in checks.items():
            if not check.is_healthy():
                issues.append({
                    "component": name,
                    "status": check.status.value,
                    "message": check.message,
                })

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": self.health_monitor.get_overall_health().value,
            "issues": issues,
            "check_details": self.health_monitor.get_report()["checks"],
        }

    def get_debug_info(self) -> dict[str, Any]:
        """Get detailed debug information.
        
        Returns:
            Debug information
        """
        try:
            import sys
            return {
                "python_version": sys.version,
                "platform": sys.platform,
                "process_info": {
                    "pid": psutil.os.getpid(),
                    "memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                    "cpu_percent": psutil.cpu_percent(),
                },
                "system_info": {
                    "cpu_count": psutil.cpu_count(),
                    "total_memory_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
                    "disk_usage_percent": psutil.disk_usage("/").percent,
                },
            }
        except Exception as e:
            self.logger.error("Error getting debug info: %s", e)
            return {"error": str(e)}
