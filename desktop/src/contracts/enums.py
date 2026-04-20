"""Cross-cutting enums shared by desktop and server contracts.

This module is the source of truth for enum values that need to survive across
process boundaries and over time.
"""

from __future__ import annotations

from enum import Enum


class EnvironmentName(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class MessageTopic(str, Enum):
    SESSION = "session"
    MARKET = "market"
    SIGNAL = "signal"
    DECISION = "decision"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    LEARNING = "learning"
    REPORTING = "reporting"


class ProducerRole(str, Enum):
    DESKTOP = "desktop"
    SERVER = "server"
    WORKER = "worker"
    SERVICE = "service"
    USER = "user"
    AUTOMATION = "automation"


class VenueKind(str, Enum):
    UNKNOWN = "unknown"
    PAPER = "paper"
    COINBASE = "coinbase"
    BINANCE = "binance"
    OANDA = "oanda"
    ALPACA = "alpaca"
    IBKR = "ibkr"
    SCHWAB = "schwab"


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    EQUITY = "equity"
    FOREX = "forex"
    FUTURE = "future"
    OPTION = "option"
    ETF = "etf"
    INDEX = "index"
    UNKNOWN = "unknown"


class MarketType(str, Enum):
    """Market types traded on the platform: spot, futures, perpetuals, stocks, indices, commodities."""

    SPOT = "spot"
    FUTURES = "futures"
    PERPS = "perps"
    STOCKS = "stocks"
    INDICES = "indices"
    COMMODITIES = "commodities"
    UNKNOWN = "unknown"


class MarketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    HALTED = "halted"
    AUCTION = "auction"
    UNKNOWN = "unknown"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    FLAT = "flat"


class DecisionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    SKIP = "skip"
    REDUCE = "reduce"
    CLOSE = "close"
    REVERSE = "reverse"


class RiskDisposition(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REDUCED = "reduced"
    ESCALATED = "escalated"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    DAY = "day"


class ExecutionStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class LearningOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    SCRATCH = "scratch"
    REJECTED = "rejected"


class ReportKind(str, Enum):
    SESSION = "session"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INCIDENT = "incident"
    POST_TRADE = "post_trade"


class SessionMode(str, Enum):
    PAPER = "paper"
    PRACTICE = "practice"
    SANDBOX = "sandbox"
    LIVE = "live"


class SessionState(str, Enum):
    STARTING = "starting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    PAUSED = "paused"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class SessionRole(str, Enum):
    OPERATOR = "operator"
    TRADER = "trader"
    RISK_MANAGER = "risk_manager"
    OBSERVER = "observer"
    SERVICE = "service"


class AuthMethod(str, Enum):
    PASSWORD = "password"
    API_KEY = "api_key"
    OAUTH = "oauth"
    SSO = "sso"
    TOKEN_REFRESH = "token_refresh"

