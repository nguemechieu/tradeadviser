"""Professional Logging Configuration System."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",   # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors."""
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}"
                f"{record.levelname}"
                f"{self.RESET}"
            )
        return super().format(record)


class LoggingConfigurator:
    """Configure logging for the application."""

    def __init__(self):
        self.logger = logging.getLogger("LoggingConfigurator")
        self._configured = False

    def setup(
        self,
        log_level: str | int = logging.INFO,
        log_file: Optional[str | Path] = None,
        console_enabled: bool = True,
        file_enabled: bool = True,
        backup_count: int = 5,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    ) -> None:
        """Configure logging system.
        
        Args:
            log_level: Logging level
            log_file: Path to log file
            console_enabled: Enable console output
            file_enabled: Enable file output
            backup_count: Number of backup files
            max_bytes: Max file size before rotation
        """
        # Convert string level to logging level
        if isinstance(log_level, str):
            log_level = getattr(logging, log_level.upper(), logging.INFO)

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Format
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        formatter = logging.Formatter(format_string)

        # Console handler
        if console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(ColoredFormatter(format_string))
            root_logger.addHandler(console_handler)

        # File handler
        if file_enabled and log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            self.logger.info("File logging configured: %s", log_path)

        self._configured = True
        self.logger.info("Logging configured with level: %s", logging.getLevelName(log_level))

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get a logger with the given name.
        
        Args:
            name: Logger name
            
        Returns:
            Logger instance
        """
        return logging.getLogger(name)

    @staticmethod
    def set_level(name: str, level: str | int) -> None:
        """Set logging level for a specific logger.
        
        Args:
            name: Logger name
            level: Logging level
        """
        logger = logging.getLogger(name)
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(level)

    @staticmethod
    def enable_debug_logging() -> None:
        """Enable debug logging everywhere."""
        logging.getLogger().setLevel(logging.DEBUG)
        for logger_name in logging.Logger.manager.loggerDict:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)

    @staticmethod
    def create_module_logger(module_name: str) -> logging.Logger:
        """Create a logger for a module.
        
        Args:
            module_name: Name of module
            
        Returns:
            Configured logger
        """
        return logging.getLogger(module_name)


# Convenience functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = "logs/app.log",
    console_enabled: bool = True,
    file_enabled: bool = True,
) -> None:
    """Quick logging setup.
    
    Args:
        log_level: Logging level
        log_file: Path to log file
        console_enabled: Enable console output
        file_enabled: Enable file output
    """
    configurator = LoggingConfigurator()
    configurator.setup(
        log_level=log_level,
        log_file=log_file,
        console_enabled=console_enabled,
        file_enabled=file_enabled,
    )


def enable_debug() -> None:
    """Enable debug logging."""
    LoggingConfigurator.enable_debug_logging()


# Context managers for temporary logging level changes
class DebugLogging:
    """Context manager for temporary debug logging."""

    def __init__(self, logger_name: str | None = None):
        self.logger_name = logger_name
        self.old_level = None

    def __enter__(self) -> None:
        logger = logging.getLogger(self.logger_name)
        self.old_level = logger.level
        logger.setLevel(logging.DEBUG)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.old_level is not None:
            logging.getLogger(self.logger_name).setLevel(self.old_level)


class QuietLogging:
    """Context manager for temporary quiet logging."""

    def __init__(self, logger_name: str | None = None):
        self.logger_name = logger_name
        self.old_level = None

    def __enter__(self) -> None:
        logger = logging.getLogger(self.logger_name)
        self.old_level = logger.level
        logger.setLevel(logging.WARNING)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.old_level is not None:
            logging.getLogger(self.logger_name).setLevel(self.old_level)


# Example usage patterns
"""
# Setup logging at application start
setup_logging(
    log_level="INFO",
    log_file="logs/tradeadviser.log",
    console_enabled=True,
    file_enabled=True,
)

# Get logger for a module
logger = get_logger(__name__)

# Use in code
logger.info("Application started")
logger.debug("Debug message")
logger.error("Error occurred", exc_info=True)

# Temporary debug logging
with DebugLogging():
    # Debug logging enabled here
    logger.debug("Detailed debugging info")

# Temporary quiet logging  
with QuietLogging():
    # Only warnings and errors logged here
    logger.debug("This won't appear")
    logger.warning("This will appear")
"""
