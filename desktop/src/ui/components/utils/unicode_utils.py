"""UTF-8 Encoding Configuration for Windows Compatibility.

This module provides utilities to ensure UTF-8 encoding is used for logging
and console output on Windows systems, preventing 'charmap' codec errors
when handling Unicode characters (emoji, special characters, etc.).

Usage:
    from src.ui.components.utils.unicode_utils import configure_utf8_encoding
    configure_utf8_encoding()
"""

import sys
import logging


def configure_utf8_encoding() -> None:
    """Configure UTF-8 encoding for stdout/stderr on Windows.
    
    On Windows, the default console encoding is often CP1252 (charmap) which
    doesn't support Unicode characters like emoji. This function reconfigures
    stdout and stderr to use UTF-8 with error replacement, allowing Unicode
    characters to be safely logged or printed.
    
    This should be called early in application startup, before any logging
    or console output occurs.
    """
    if sys.platform == "win32":
        # Reconfigure stdout and stderr to use UTF-8
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError, RuntimeError):
                pass
        
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            try:
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError, RuntimeError):
                pass


class UTF8StreamHandler(logging.StreamHandler):
    """Logging handler that safely handles Unicode characters on Windows.
    
    This handler wraps the parent StreamHandler and encodes log messages
    with UTF-8 encoding and error replacement, preventing 'charmap' codec
    errors when the message contains Unicode characters.
    """
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record with UTF-8 safe encoding.
        
        Args:
            record: The log record to emit
        """
        try:
            msg = self.format(record)
            
            # Ensure the message can be encoded to the stream's encoding
            if hasattr(self.stream, 'encoding'):
                try:
                    # Try to encode with the stream's encoding first
                    msg.encode(self.stream.encoding or 'utf-8', errors='replace')
                except (LookupError, AttributeError):
                    # If that fails, encode to UTF-8 as fallback
                    msg = msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            
            # Call parent emit method
            super().emit(record)
        except Exception:
            self.handleError(record)


def configure_logger_for_utf8(logger: logging.Logger) -> None:
    """Configure a logger to use UTF-8 safe handlers.
    
    Replaces stream handlers with UTF8StreamHandler to prevent encoding
    errors when logging Unicode characters.
    
    Args:
        logger: The logger instance to configure
    """
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            # Keep the existing formatter and level
            utf8_handler = UTF8StreamHandler(handler.stream)
            utf8_handler.setFormatter(handler.formatter)
            utf8_handler.setLevel(handler.level)
            
            # Replace the handler
            logger.removeHandler(handler)
            logger.addHandler(utf8_handler)
