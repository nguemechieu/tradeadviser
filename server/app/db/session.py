"""Database session module alias - re-exports from app.backend.db.session"""

from app.backend.db.session import get_db_session

__all__ = ["get_db_session"]
