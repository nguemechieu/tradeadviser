"""Console loading system package initialization.

Exports all public components for easy importing.
"""

from .loader import (
    LoadingState,
    LoadingTask,
    LoadingManager,
    LoadingWorker,
    LoadingIndicator,
    ConsoleLoaderIntegration,
)
from .system_console import SystemConsole

__all__ = [
    "LoadingState",
    "LoadingTask",
    "LoadingManager",
    "LoadingWorker",
    "LoadingIndicator",
    "ConsoleLoaderIntegration",
    "SystemConsole",
]

__version__ = "1.0.0"
__description__ = "Non-blocking terminal/console loading system for Sopotek Quant System"
