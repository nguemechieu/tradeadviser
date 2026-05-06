"""Enhanced Session Lifecycle Management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Callable, Optional


class SessionHealth(Enum):
    """Session health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    RECOVERING = "recovering"


@dataclass
class SessionMetrics:
    """Session performance metrics."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    connections_failed: int = 0
    data_sync_errors: int = 0
    order_rejections: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    consecutive_errors: int = 0
    total_errors: int = 0

    def reset_error_counter(self) -> None:
        """Reset consecutive error counter."""
        self.consecutive_errors = 0

    def increment_error(self) -> int:
        """Increment error counters."""
        self.consecutive_errors += 1
        self.total_errors += 1
        return self.consecutive_errors

    def is_critical(self, threshold: int = 5) -> bool:
        """Check if session is in critical state."""
        return self.consecutive_errors >= threshold


@dataclass
class SessionLifecycleConfig:
    """Session lifecycle configuration."""
    # Timeouts
    connection_timeout_sec: float = 30.0
    initialization_timeout_sec: float = 60.0
    heartbeat_interval_sec: float = 30.0
    cleanup_timeout_sec: float = 15.0

    # Retry policy
    max_connection_retries: int = 3
    retry_backoff_ms: int = 1000

    # Health monitoring
    error_threshold: int = 5
    recovery_window_sec: float = 300.0


class SessionLifecycleManager:
    """Manages session lifecycle with robust error handling."""

    def __init__(
        self,
        session_id: str,
        config: SessionLifecycleConfig | None = None,
        logger: logging.Logger | None = None,
    ):
        self.session_id = session_id
        self.config = config or SessionLifecycleConfig()
        self.logger = logger or logging.getLogger(f"SessionLifecycle.{session_id}")
        self.metrics = SessionMetrics()
        self._health = SessionHealth.HEALTHY
        self._error_handlers: dict[str, list[Callable]] = {}
        self._state_callbacks: list[Callable[[SessionHealth], None]] = []
        self._lock = asyncio.Lock()

    async def initialize(self, init_func: Callable) -> bool:
        """Initialize session with timeout and error handling.
        
        Args:
            init_func: Async function to run for initialization
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Initializing session %s", self.session_id)
            await asyncio.wait_for(
                init_func(),
                timeout=self.config.initialization_timeout_sec
            )
            self.metrics.reset_error_counter()
            self.logger.info("Session %s initialized successfully", self.session_id)
            return True
        except asyncio.TimeoutError:
            self.logger.error(
                "Initialization timeout for session %s (%.1fs)",
                self.session_id,
                self.config.initialization_timeout_sec
            )
            await self._handle_error("initialization_timeout")
            return False
        except Exception as e:
            self.logger.error(
                "Initialization failed for session %s: %s",
                self.session_id, e,
                exc_info=True
            )
            await self._handle_error("initialization_error", e)
            return False

    async def heartbeat(self, check_func: Callable) -> bool:
        """Perform health check with error handling.
        
        Args:
            check_func: Async function to check health
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            await asyncio.wait_for(
                check_func(),
                timeout=self.config.heartbeat_interval_sec / 2
            )
            self.metrics.last_heartbeat = datetime.utcnow()
            self.metrics.reset_error_counter()
            self._set_health(SessionHealth.HEALTHY)
            return True
        except asyncio.TimeoutError:
            self.logger.warning("Heartbeat timeout for session %s", self.session_id)
            await self._handle_error("heartbeat_timeout")
            return False
        except Exception as e:
            self.logger.warning(
                "Heartbeat failed for session %s: %s",
                self.session_id, e
            )
            await self._handle_error("heartbeat_error", e)
            return False

    async def cleanup(self, cleanup_func: Callable) -> None:
        """Cleanup session with timeout.
        
        Args:
            cleanup_func: Async function to run for cleanup
        """
        try:
            self.logger.info("Cleaning up session %s", self.session_id)
            await asyncio.wait_for(
                cleanup_func(),
                timeout=self.config.cleanup_timeout_sec
            )
            self.logger.info("Session %s cleanup complete", self.session_id)
        except asyncio.TimeoutError:
            self.logger.error(
                "Cleanup timeout for session %s",
                self.session_id
            )
        except Exception as e:
            self.logger.error(
                "Cleanup failed for session %s: %s",
                self.session_id, e
            )

    async def retry_operation(
        self,
        operation: Callable,
        operation_name: str = "operation",
        max_retries: int | None = None,
    ) -> Any:
        """Execute operation with retry logic.
        
        Args:
            operation: Async function to execute
            operation_name: Name for logging
            max_retries: Max retry attempts (uses config if None)
            
        Returns:
            Result of operation or None
        """
        max_retries = max_retries or self.config.max_connection_retries
        backoff_ms = self.config.retry_backoff_ms

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(
                    "Executing %s (attempt %d/%d) for session %s",
                    operation_name, attempt + 1, max_retries + 1, self.session_id
                )
                result = await operation()
                self.metrics.reset_error_counter()
                return result
            except Exception as e:
                if attempt < max_retries:
                    wait_time = backoff_ms * (2 ** attempt) / 1000  # exponential backoff
                    self.logger.warning(
                        "Attempt %d failed for %s, retrying in %.1fs: %s",
                        attempt + 1, operation_name, wait_time, e
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        "All %d attempts failed for %s in session %s: %s",
                        max_retries + 1, operation_name, self.session_id, e
                    )
                    await self._handle_error(f"{operation_name}_failed", e)
                    return None

    def register_error_handler(
        self,
        error_type: str,
        handler: Callable[[str, Optional[Exception]], None]
    ) -> None:
        """Register error handler for specific error type.
        
        Args:
            error_type: Type of error to handle
            handler: Async function to handle error
        """
        if error_type not in self._error_handlers:
            self._error_handlers[error_type] = []
        self._error_handlers[error_type].append(handler)

    def register_state_callback(self, callback: Callable[[SessionHealth], None]) -> None:
        """Register callback for health state changes.
        
        Args:
            callback: Function to call when health changes
        """
        self._state_callbacks.append(callback)

    def get_health(self) -> SessionHealth:
        """Get current session health."""
        return self._health

    def get_metrics(self) -> SessionMetrics:
        """Get session metrics."""
        return self.metrics

    async def _handle_error(
        self,
        error_type: str,
        exception: Exception | None = None
    ) -> None:
        """Handle error with registered handlers.
        
        Args:
            error_type: Type of error
            exception: Exception if available
        """
        async with self._lock:
            self.metrics.increment_error()

            if self.metrics.is_critical(self.config.error_threshold):
                self._set_health(SessionHealth.CRITICAL)
            else:
                self._set_health(SessionHealth.WARNING)

            # Call registered handlers
            handlers = self._error_handlers.get(error_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(error_type, exception)
                    else:
                        handler(error_type, exception)
                except Exception as e:
                    self.logger.error("Error in error handler: %s", e)

    def _set_health(self, health: SessionHealth) -> None:
        """Update health state and notify callbacks."""
        if self._health == health:
            return

        old_health = self._health
        self._health = health
        self.logger.info(
            "Session %s health changed: %s -> %s",
            self.session_id, old_health.value, health.value
        )

        for callback in self._state_callbacks:
            try:
                callback(health)
            except Exception as e:
                self.logger.error("Error in state callback: %s", e)

    def __repr__(self) -> str:
        return (
            f"SessionLifecycle(id={self.session_id}, "
            f"health={self._health.value}, "
            f"errors={self.metrics.total_errors})"
        )
