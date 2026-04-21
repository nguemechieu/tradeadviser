"""Database base module alias - re-exports from app.backend.db.base"""

from app.backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["Base", "TimestampMixin", "UUIDPrimaryKeyMixin"]
