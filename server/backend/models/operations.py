"""System health and operations monitoring models."""

from sqlalchemy import String, Float, Boolean, Enum, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
import enum

from server.backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ServiceStatus(str, enum.Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class SystemHealth(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-wide health metrics."""
    __tablename__ = "system_health"

    # Database
    database_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    database_response_ms: Mapped[float] = mapped_column(default=0.0, nullable=False)
    
    # Broker connectivity
    broker_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    broker_details: Mapped[dict] = mapped_column(JSON, nullable=True)  # Per-broker status
    
    # Cache/Redis
    cache_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    
    # Message queue
    queue_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    pending_messages: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # API health
    api_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    api_response_ms: Mapped[float] = mapped_column(default=0.0, nullable=False)
    active_connections: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # WebSocket health
    ws_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    connected_clients: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Resource usage
    cpu_percent: Mapped[float] = mapped_column(default=0.0, nullable=False)
    memory_percent: Mapped[float] = mapped_column(default=0.0, nullable=False)
    disk_percent: Mapped[float] = mapped_column(default=0.0, nullable=False)
    
    # Overall
    overall_status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), default=ServiceStatus.OFFLINE, nullable=False)
    status_message: Mapped[str] = mapped_column(String(256), nullable=True)


class TradeStats(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Aggregate trading statistics for platform."""
    __tablename__ = "trade_stats"

    # Aggregates
    total_trades: Mapped[int] = mapped_column(default=0, nullable=False)
    total_users: Mapped[int] = mapped_column(default=0, nullable=False)
    active_users: Mapped[int] = mapped_column(default=0, nullable=False)  # Traded in last 24h
    
    # P&L
    total_platform_pnl: Mapped[float] = mapped_column(default=0.0, nullable=False)
    average_trade_pnl: Mapped[float] = mapped_column(default=0.0, nullable=False)
    average_win_rate: Mapped[float] = mapped_column(default=0.0, nullable=False)
    
    # Volume
    total_volume: Mapped[float] = mapped_column(default=0.0, nullable=False)  # In base currency
    average_trade_size: Mapped[float] = mapped_column(default=0.0, nullable=False)
    
    # Orders
    total_orders: Mapped[int] = mapped_column(default=0, nullable=False)
    filled_orders: Mapped[int] = mapped_column(default=0, nullable=False)
    cancelled_orders: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Agents
    active_agents: Mapped[int] = mapped_column(default=0, nullable=False)
    total_agents: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Period
    period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # "1h", "1d", "1w", "all"


class PerformanceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Periodic performance snapshots for trending."""
    __tablename__ = "performance_snapshots"

    # Identifiers
    period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # ISO timestamp or period label
    
    # Market
    market_return: Mapped[float] = mapped_column(default=0.0, nullable=False)  # %
    
    # Platform
    platform_total_return: Mapped[float] = mapped_column(default=0.0, nullable=False)  # %
    platform_sharpe: Mapped[float] = mapped_column(nullable=True)
    platform_max_drawdown: Mapped[float] = mapped_column(nullable=True)
    
    # Breakdown
    top_agent_name: Mapped[str] = mapped_column(String(128), nullable=True)
    top_agent_return: Mapped[float] = mapped_column(nullable=True)
    
    top_trader_name: Mapped[str] = mapped_column(String(128), nullable=True)
    top_trader_return: Mapped[float] = mapped_column(nullable=True)
    
    # Risk
    max_daily_loss: Mapped[float] = mapped_column(nullable=True)
    risk_breaches_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Details
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
