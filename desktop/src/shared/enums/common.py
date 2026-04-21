"""Transport-safe enums used by Sopotek desktop and server boundaries."""

from __future__ import annotations

from enum import Enum


class BrokerKind(str, Enum):
    PAPER = "paper"
    COINBASE = "coinbase"
    BINANCE = "binance"
    OANDA = "oanda"
    ALPACA = "alpaca"
    IBKR = "ibkr"
    SCHWAB = "schwab"


class SessionStatus(str, Enum):
    PENDING = "pending"
    AUTHENTICATED = "authenticated"
    ACTIVE = "active"
    DEGRADED = "degraded"
    STALE = "stale"
    CLOSED = "closed"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class DecisionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    SKIP = "skip"
    REDUCE = "reduce"
    CLOSE = "close"


class ExecutionStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReportKind(str, Enum):
    SESSION = "session"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EventSource(str, Enum):
    DESKTOP = "desktop"
    SERVER = "server"
    SERVICE = "service"
    WORKER = "worker"

