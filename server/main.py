"""Entry point for the FastAPI backend.

This module provides the FastAPI application instance for deployment.
"""

# Import the app from the backend module
from server.backend.main import app

__all__ = ["app"]