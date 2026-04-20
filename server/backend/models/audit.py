"""Audit logging and compliance models."""

from sqlalchemy import String, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
import uuid

from server.backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditAction(str, enum.Enum):
    """Audit log action types."""
    LOGIN = "login"
    LOGOUT = "logout"
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_CLOSED = "position_closed"
    KILL_SWITCH = "kill_switch"
    SETTINGS_CHANGED = "settings_changed"
    AGENT_DEPLOYED = "agent_deployed"
    AGENT_STOPPED = "agent_stopped"
    LICENSE_UPGRADED = "license_upgraded"
    USER_CREATED = "user_created"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_SUSPENDED = "user_suspended"
    ADMIN_ACTION = "admin_action"
    API_ACCESS = "api_access"
    EXPORT = "export"


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Compliance and activity audit trail."""
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=True)  # "order", "position", "agent", etc.
    resource_id: Mapped[str] = mapped_column(String(256), nullable=True)
    
    # Details
    details: Mapped[str] = mapped_column(Text, nullable=True)
    audit_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Impact
    impact: Mapped[str] = mapped_column(String(64), nullable=True)  # "success", "error", "warning"
    result: Mapped[str] = mapped_column(Text, nullable=True)
    
    # IP/User agent for security
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # Support IPv4 and IPv6
    user_agent: Mapped[str] = mapped_column(String(256), nullable=True)
    
    user = relationship("User", back_populates="audit_logs")


class RiskLimit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Risk management limits per user."""
    __tablename__ = "risk_limits"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True, unique=True)
    
    # Position limits
    max_position_size: Mapped[float] = mapped_column(nullable=True)  # In base currency
    max_total_positions: Mapped[int] = mapped_column(default=50, nullable=False)
    max_open_orders: Mapped[int] = mapped_column(default=100, nullable=False)
    
    # Daily limits
    daily_loss_limit: Mapped[float] = mapped_column(nullable=True)  # Max daily loss
    daily_win_limit: Mapped[float] = mapped_column(nullable=True)  # Take profits target
    max_trades_per_day: Mapped[int] = mapped_column(default=1000, nullable=False)
    
    # Portfolio limits
    max_leverage: Mapped[float] = mapped_column(default=1.0, nullable=False)
    max_portfolio_value: Mapped[float] = mapped_column(nullable=True)
    
    # Trading hours
    trading_start_hour: Mapped[int] = mapped_column(default=0, nullable=False)  # 0-23
    trading_end_hour: Mapped[int] = mapped_column(default=24, nullable=False)  # 0-24
    
    user = relationship("User")


class RiskBreach(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Log risk limit breaches for compliance."""
    __tablename__ = "risk_breaches"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)  # "daily_loss", "position_size", etc.
    value: Mapped[float] = mapped_column(nullable=False)
    limit: Mapped[float] = mapped_column(nullable=False)
    action_taken: Mapped[str] = mapped_column(String(128), nullable=True)  # "kill_switch", "notification", etc.
    details: Mapped[str] = mapped_column(Text, nullable=True)
    
    user = relationship("User")
