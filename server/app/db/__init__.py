"""Database module alias - re-exports from app.backend.db"""

from app.backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.backend.db.session import get_db_session

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "get_db_session",
]
