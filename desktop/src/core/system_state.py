from __future__ import annotations

"""
InvestPro SystemState

Central runtime state object for the trading workspace.

Tracks:
- running/stopped lifecycle
- connection status
- exchange/broker
- symbols
- start/stop timestamps
- uptime
- mode: paper/live/backtest
- kill switch state
- health status
- active strategy
- selected timeframe
- last heartbeat
- error/warning history
- metadata

This class is intentionally lightweight and dependency-free so it can be used by:
- desktop UI
- backend API
- Telegram service
- health checks
- execution controller
- broker controller
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass(slots=True)
class SystemStateSnapshot:
    running: bool = False
    connected: bool = False

    exchange: Optional[str] = None
    broker: Optional[str] = None
    account_id: Optional[str] = None

    symbols: list[str] = field(default_factory=list)
    active_symbol: Optional[str] = None
    timeframe: Optional[str] = None
    strategy_name: Optional[str] = None

    mode: str = "paper"  # paper, live, backtest, research
    environment: str = "local"  # local, docker, cloud

    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    last_connected_at: Optional[str] = None
    last_disconnected_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None

    uptime_seconds: float = 0.0

    kill_switch_active: bool = False
    paused: bool = False

    health: str = "stopped"  # stopped, healthy, warning, error
    status_message: str = "System is stopped."

    last_error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SystemState:
    """Runtime state manager for InvestPro."""

    MAX_WARNINGS = 50
    MAX_ERRORS = 50

    def __init__(
        self,
        *,
        mode: str = "paper",
        environment: str = "local",
        exchange: Optional[str] = None,
        broker: Optional[str] = None,
        symbols: Optional[list[str]] = None,
    ) -> None:
        self.running = False
        self.connected = False

        self.exchange = exchange
        self.broker = broker
        self.account_id: Optional[str] = None

        self.symbols: list[str] = self._normalize_symbols(symbols or [])
        self.active_symbol: Optional[str] = self.symbols[0] if self.symbols else None
        self.timeframe: Optional[str] = None
        self.strategy_name: Optional[str] = None

        self.mode = self._normalize_mode(mode)
        self.environment = str(
            environment or "local").strip().lower() or "local"

        self.start_time: Optional[datetime] = None
        self.stop_time: Optional[datetime] = None
        self.last_connected_at: Optional[datetime] = None
        self.last_disconnected_at: Optional[datetime] = None
        self.last_heartbeat_at: Optional[datetime] = None

        self.kill_switch_active = False
        self.paused = False

        self.health = "stopped"
        self.status_message = "System is stopped."

        self.last_error: Optional[str] = None
        self.warnings: list[str] = []
        self.errors: list[str] = []

        self.metadata: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, message: str = "System started.") -> None:
        self.running = True
        self.paused = False
        self.start_time = utc_now()
        self.stop_time = None
        self.health = "healthy" if self.connected else "warning"
        self.status_message = message if self.connected else "System started but broker is not connected."

    def stop(self, message: str = "System stopped.") -> None:
        self.running = False
        self.paused = False
        self.stop_time = utc_now()
        self.health = "stopped"
        self.status_message = message

    def pause(self, message: str = "System paused.") -> None:
        self.paused = True
        self.status_message = message
        if self.running:
            self.health = "warning"

    def resume(self, message: str = "System resumed.") -> None:
        self.paused = False
        self.status_message = message
        if self.running:
            self.health = "healthy" if self.connected and not self.kill_switch_active else "warning"

    def heartbeat(self) -> None:
        self.last_heartbeat_at = utc_now()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(
        self,
        *,
        exchange: Optional[str] = None,
        broker: Optional[str] = None,
        account_id: Optional[str] = None,
        message: str = "Connected.",
    ) -> None:
        self.connected = True
        self.last_connected_at = utc_now()
        self.last_disconnected_at = None

        if exchange is not None:
            self.exchange = str(exchange).strip() or None

        if broker is not None:
            self.broker = str(broker).strip() or None

        if account_id is not None:
            self.account_id = str(account_id).strip() or None

        if self.running and not self.kill_switch_active:
            self.health = "healthy"

        self.status_message = message

    def disconnect(self, message: str = "Disconnected.") -> None:
        self.connected = False
        self.last_disconnected_at = utc_now()

        if self.running:
            self.health = "warning"
        else:
            self.health = "stopped"

        self.status_message = message

    # ------------------------------------------------------------------
    # Safety controls
    # ------------------------------------------------------------------

    def activate_kill_switch(self, reason: str = "Kill switch activated.") -> None:
        self.kill_switch_active = True
        self.paused = True
        self.health = "error"
        self.status_message = reason
        self.add_error(reason)

    def clear_kill_switch(self, message: str = "Kill switch cleared.") -> None:
        self.kill_switch_active = False
        self.paused = False

        if self.running:
            self.health = "healthy" if self.connected else "warning"
        else:
            self.health = "stopped"

        self.status_message = message

    # ------------------------------------------------------------------
    # Configuration setters
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self.mode = self._normalize_mode(mode)

    def set_environment(self, environment: str) -> None:
        self.environment = str(
            environment or "local").strip().lower() or "local"

    def set_exchange(self, exchange: Optional[str]) -> None:
        self.exchange = str(exchange).strip() if exchange else None

    def set_broker(self, broker: Optional[str]) -> None:
        self.broker = str(broker).strip() if broker else None

    def set_account_id(self, account_id: Optional[str]) -> None:
        self.account_id = str(account_id).strip() if account_id else None

    def set_symbols(self, symbols: list[str]) -> None:
        self.symbols = self._normalize_symbols(symbols)
        if self.active_symbol not in self.symbols:
            self.active_symbol = self.symbols[0] if self.symbols else None

    def add_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        if normalized and normalized not in self.symbols:
            self.symbols.append(normalized)
        if self.active_symbol is None:
            self.active_symbol = normalized

    def remove_symbol(self, symbol: str) -> None:
        normalized = self._normalize_symbol(symbol)
        self.symbols = [item for item in self.symbols if item != normalized]
        if self.active_symbol == normalized:
            self.active_symbol = self.symbols[0] if self.symbols else None

    def set_active_symbol(self, symbol: Optional[str]) -> None:
        normalized = self._normalize_symbol(symbol)
        if normalized and normalized not in self.symbols:
            self.symbols.append(normalized)
        self.active_symbol = normalized or None

    def set_timeframe(self, timeframe: Optional[str]) -> None:
        self.timeframe = str(timeframe or "").strip() or None

    def set_strategy_name(self, strategy_name: Optional[str]) -> None:
        self.strategy_name = str(strategy_name or "").strip() or None

    def update_metadata(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    # ------------------------------------------------------------------
    # Warnings / errors
    # ------------------------------------------------------------------

    def add_warning(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return

        self.warnings.append(f"{utc_now_iso()} | {text}")
        self.warnings = self.warnings[-self.MAX_WARNINGS:]

        if self.health == "healthy":
            self.health = "warning"

        self.status_message = text

    def add_error(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return

        self.last_error = text
        self.errors.append(f"{utc_now_iso()} | {text}")
        self.errors = self.errors[-self.MAX_ERRORS:]

        self.health = "error"
        self.status_message = text

    def clear_errors(self) -> None:
        self.last_error = None
        self.errors.clear()

        if self.running:
            self.health = "healthy" if self.connected else "warning"
        else:
            self.health = "stopped"

    def clear_warnings(self) -> None:
        self.warnings.clear()

        if self.running:
            self.health = "healthy" if self.connected and not self.kill_switch_active else "warning"
        else:
            self.health = "stopped"

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------

    def uptime_seconds(self) -> float:
        if self.start_time is None:
            return 0.0

        end = utc_now() if self.running else (self.stop_time or utc_now())
        return max((end - self.start_time).total_seconds(), 0.0)

    def is_ready(self) -> bool:
        return bool(
            self.running
            and self.connected
            and not self.paused
            and not self.kill_switch_active
            and self.health in {"healthy", "warning"}
        )

    def can_trade(self) -> bool:
        return bool(
            self.running
            and self.connected
            and not self.paused
            and not self.kill_switch_active
            and self.mode in {"paper", "live"}
        )

    def connection_label(self) -> str:
        if self.connected:
            broker = self.broker or self.exchange or "broker"
            return f"Connected to {broker}"
        return "Disconnected"

    def status_label(self) -> str:
        if self.kill_switch_active:
            return "KILL SWITCH ACTIVE"
        if self.paused:
            return "PAUSED"
        if self.running and self.connected:
            return "RUNNING"
        if self.running and not self.connected:
            return "RUNNING / DISCONNECTED"
        return "STOPPED"

    # ------------------------------------------------------------------
    # Snapshot / export
    # ------------------------------------------------------------------

    def snapshot(self) -> SystemStateSnapshot:
        return SystemStateSnapshot(
            running=self.running,
            connected=self.connected,
            exchange=self.exchange,
            broker=self.broker,
            account_id=self.account_id,
            symbols=list(self.symbols),
            active_symbol=self.active_symbol,
            timeframe=self.timeframe,
            strategy_name=self.strategy_name,
            mode=self.mode,
            environment=self.environment,
            start_time=self._dt_to_iso(self.start_time),
            stop_time=self._dt_to_iso(self.stop_time),
            last_connected_at=self._dt_to_iso(self.last_connected_at),
            last_disconnected_at=self._dt_to_iso(self.last_disconnected_at),
            last_heartbeat_at=self._dt_to_iso(self.last_heartbeat_at),
            uptime_seconds=self.uptime_seconds(),
            kill_switch_active=self.kill_switch_active,
            paused=self.paused,
            health=self.health,
            status_message=self.status_message,
            last_error=self.last_error,
            warnings=list(self.warnings),
            errors=list(self.errors),
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return self.snapshot().to_dict()

    def summary_text(self) -> str:
        broker = self.broker or self.exchange or "-"
        symbols = ", ".join(self.symbols[:8]) if self.symbols else "-"
        if len(self.symbols) > 8:
            symbols += f", +{len(self.symbols) - 8} more"

        return (
            f"Status: {self.status_label()}\n"
            f"Health: {self.health}\n"
            f"Mode: {self.mode}\n"
            f"Broker: {broker}\n"
            f"Connected: {self.connected}\n"
            f"Active Symbol: {self.active_symbol or '-'}\n"
            f"Timeframe: {self.timeframe or '-'}\n"
            f"Strategy: {self.strategy_name or '-'}\n"
            f"Symbols: {symbols}\n"
            f"Uptime: {int(self.uptime_seconds())}s\n"
            f"Message: {self.status_message}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_mode(self, mode: str) -> str:
        value = str(mode or "paper").strip().lower()
        if value in {"live", "paper", "backtest", "research"}:
            return value
        return "paper"

    def _normalize_symbol(self, symbol: Optional[str]) -> str:
        return str(symbol or "").strip().upper()

    def _normalize_symbols(self, symbols: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()

        for symbol in symbols or []:
            normalized = self._normalize_symbol(symbol)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append(normalized)

        return output

    def _dt_to_iso(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
