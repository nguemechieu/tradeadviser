"""License and subscription models for institutional platform."""

from datetime import datetime
from sqlalchemy import String, DateTime, Float, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
import uuid

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LicenseType(str, enum.Enum):
    """License types for different trader tiers."""
    TRIAL = "trial"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    INSTITUTIONAL = "institutional"


class LicenseStatus(str, enum.Enum):
    """License status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class License(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """License/subscription model for user entitlements."""
    __tablename__ = "licenses"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    license_type: Mapped[LicenseType] = mapped_column(Enum(LicenseType), nullable=False)
    status: Mapped[LicenseStatus] = mapped_column(Enum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False)
    
    # License details
    key: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    
    # Validity
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Limits
    max_agents: Mapped[int] = mapped_column(default=1, nullable=False)
    max_symbols: Mapped[int] = mapped_column(default=100, nullable=False)
    max_positions: Mapped[int] = mapped_column(default=50, nullable=False)
    max_portfolio_value: Mapped[float] = mapped_column(Float, nullable=True)  # In base currency
    
    # Features
    has_backtesting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_paper_trading: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_live_trading: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_multi_broker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_api_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relations
    user = relationship("User", back_populates="licenses")


class LicenseAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Track license changes for compliance."""
    __tablename__ = "license_audits"

    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # created, renewed, upgraded, suspended, revoked
    details: Mapped[str] = mapped_column(String(512), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(128), nullable=True)  # admin email or system
