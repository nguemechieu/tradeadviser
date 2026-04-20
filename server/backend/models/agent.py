"""AI Agent deployment and management models."""

from sqlalchemy import String, Float, Boolean, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
import uuid

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentStatus(str, enum.Enum):
    """Agent deployment status."""
    CREATED = "created"
    DEPLOYING = "deploying"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    STOPPED = "stopped"


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """AI agent deployment and configuration."""
    __tablename__ = "agents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.CREATED, nullable=False)
    
    # Strategy/Model details
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)  # "ml", "rules", "hybrid", "llm"
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Configuration
    config: Mapped[dict] = mapped_column(JSON, nullable=True)  # Strategy parameters
    
    # Performance tracking
    total_trades: Mapped[int] = mapped_column(default=0, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cumulative_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_return: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # percentage
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Limits
    max_position_size: Mapped[float] = mapped_column(Float, nullable=True)
    daily_loss_limit: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Control
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_trade_time: Mapped[str] = mapped_column(String(32), nullable=True)  # ISO timestamp
    
    user = relationship("User")
    audit_logs = relationship("AgentAudit", back_populates="agent", cascade="all, delete-orphan")


class AgentAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Track agent deployment changes."""
    __tablename__ = "agent_audits"

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # created, deployed, paused, stopped, failed
    details: Mapped[str] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(128), nullable=True)  # admin email or system
    
    agent = relationship("Agent", back_populates="audit_logs")
