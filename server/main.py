"""DEPRECATED: Use app/backend/main.py instead.

This file is kept for compatibility but should not be used directly.
The correct entry point is sqs_server/main.py which imports app/backend/main.py.
"""

# Legacy import compatibility - redirect to the real app
from app.backend.main import app

__all__ = ["app"]