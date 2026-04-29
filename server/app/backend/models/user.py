from typing import Any

from sqlalchemy import Boolean, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from server.app.backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    """User roles for institutional platform."""
    TRADER = "trader"
    RISK_MANAGER = "risk_manager"
    OPERATIONS = "operations"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    
    def __init__(self, **kw: Any):
        super().__init__(kw)
        self.permissions = None
        self.user_id = None

    is_deleted = False
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    firstname: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    lastname: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    middlename:Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    phonenumber:Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.TRADER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="user", cascade="all, delete-orphan")
    licenses = relationship("License", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
