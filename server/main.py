#!/usr/bin/env python3
"""Main entry point for SQS (Sopotek Quant System) Server.

This script starts the FastAPI server with proper environment configuration,
logging setup, and error handling.

Usage:
    python main.py

Environment Variables:
    HOST: Server host (default: 0.0.0.0)
    PORT: Server port (default: 8000)
    LOG_LEVEL: Logging level (default: info)
    ENV: Environment (development/production, default: production)
"""

import sys
import logging
from pathlib import Path
from os import environ

# Add parent directory to Python path for imports (so we can import server.app.backend)
server_root = Path(__file__).resolve().parent
parent_root = server_root.parent
if str(parent_root) not in sys.path:
    sys.path.insert(0, str(parent_root))
if str(server_root) not in sys.path:
    sys.path.insert(0, str(server_root))

# Configure logging before imports
log_level = environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI server."""
    try:
        import uvicorn
        from app.backend.main import app

        # Configuration
        host = environ.get("HOST", "0.0.0.0")
        port = int(environ.get("PORT", "8000"))
        env = environ.get("ENV", "production")
        reload = env == "development"

        logger.info(f"Starting Sopotek Quant System Server")
        logger.info(f"Host: {host}")
        logger.info(f"Port: {port}")
        logger.info(f"Environment: {env}")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Reload: {reload}")

        # Run the server
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level.lower(),
            reload=reload,
            access_log=True,
        )
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
