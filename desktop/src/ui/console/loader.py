"""Loading system for terminal/console to prevent UI freezing.

Provides async loading utilities and progress tracking for long-running operations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from PySide6.QtCore import QThread, Signal, QObject


T = TypeVar("T")


class LoadingState(str, Enum):
    """Loading state enumeration."""
    IDLE = "idle"
    LOADING = "loading"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class LoadingTask:
    """Represents a loading task."""
    task_id: str
    name: str
    status: LoadingState = LoadingState.IDLE
    progress: float = 0.0  # 0-100
    message: str = ""
    start_time: float = field(default_factory=time.time)
    error: Optional[str] = None
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    def __str__(self) -> str:
        if self.status == LoadingState.LOADING:
            return f"⟳ {self.name} ({self.progress:.0f}%) - {self.message}"
        elif self.status == LoadingState.COMPLETE:
            return f"✓ {self.name} - Complete ({self.elapsed:.2f}s)"
        elif self.status == LoadingState.ERROR:
            return f"✗ {self.name} - Error: {self.error}"
        else:
            return f"○ {self.name}"


class LoadingWorker(QObject):
    """Worker thread for async operations.
    
    IMPORTANT: Do NOT create a new event loop here. The main application
    uses qasync which manages a single event loop. Creating a separate loop
    causes "not the running loop" RuntimeErrors.
    """
    
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int)
    
    def __init__(self, coroutine, task_id: str):
        super().__init__()
        self.coroutine = coroutine
        self.task_id = task_id
        self.loop = None
    
    def run(self):
        """Run the async task.
        
        This runs on a worker thread but should NOT create a new event loop.
        Instead, get the main loop and use run_coroutine_threadsafe.
        """
        try:
            import asyncio
            # Get the main event loop (set up by qasync in main thread)
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                # Not in main thread, get the event loop that was set
                try:
                    self.loop = asyncio.get_event_loop()
                except RuntimeError:
                    self.error.emit("No event loop available")
                    self.finished.emit()
                    return
            
            # If we can get a running loop via asyncio.all_tasks, use run_coroutine_threadsafe
            # Otherwise, just run it directly with a new loop (fallback)
            try:
                # Try to use the main loop
                future = asyncio.run_coroutine_threadsafe(self.coroutine, self.loop)
                result = future.result(timeout=300)  # 5 minute timeout
                self.result.emit(result)
            except RuntimeError:
                # Fallback: if we can't reach the main loop, don't create a new one
                # Just report the error
                self.error.emit("Could not execute coroutine: event loop not accessible")
            
            self.finished.emit()
        except Exception as e:
            import traceback
            self.error.emit(f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
            self.finished.emit()


class LoadingManager(QObject):
    """Manages loading tasks and prevents UI freezing."""
    
    # Signals
    task_started = Signal(str, str)  # task_id, name
    task_progress = Signal(str, float, str)  # task_id, progress, message
    task_completed = Signal(str, float)  # task_id, elapsed_time
    task_error = Signal(str, str)  # task_id, error
    all_tasks_complete = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.tasks: dict[str, LoadingTask] = {}
        self.workers: dict[str, LoadingWorker] = {}
        self.threads: dict[str, QThread] = {}
    
    async def load_async(
        self,
        task_id: str,
        name: str,
        coro: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Load data asynchronously without freezing UI.
        
        Args:
            task_id: Unique task identifier
            name: Display name for the loading task
            coro: Async callable or coroutine
            *args: Positional arguments for coro
            **kwargs: Keyword arguments for coro
            
        Returns:
            Result from the coroutine
        """
        task = LoadingTask(task_id=task_id, name=name)
        self.tasks[task_id] = task
        
        try:
            # Emit task started signal
            self.task_started.emit(task_id, name)
            task.status = LoadingState.LOADING
            task.message = "Starting..."
            self._emit_progress(task)
            
            # Call the coroutine
            if asyncio.iscoroutinefunction(coro):
                result = await coro(*args, **kwargs)
            else:
                # If it's already a coroutine, just await it
                result = await coro
            
            # Mark as complete
            task.status = LoadingState.COMPLETE
            task.progress = 100.0
            task.message = "Complete"
            self._emit_progress(task)
            
            self.logger.info(f"Task {task_id} completed in {task.elapsed:.2f}s")
            self.task_completed.emit(task_id, task.elapsed)
            
            # Check if all tasks are complete
            self._check_all_complete()
            
            return result
            
        except Exception as e:
            task.status = LoadingState.ERROR
            task.error = str(e)
            self.logger.error(f"Task {task_id} failed: {e}")
            self.task_error.emit(task_id, str(e))
            self._emit_progress(task)
            self._check_all_complete()
            raise
    
    def update_progress(
        self,
        task_id: str,
        progress: float,
        message: str = ""
    ) -> None:
        """Update progress for a loading task.
        
        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)
            message: Status message
        """
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.progress = min(100.0, max(0.0, progress))
        task.message = message
        task.status = LoadingState.LOADING
        
        self._emit_progress(task)
    
    def _emit_progress(self, task: LoadingTask) -> None:
        """Emit progress signal."""
        self.task_progress.emit(
            task.task_id,
            task.progress,
            str(task)
        )
    
    def _check_all_complete(self) -> None:
        """Check if all tasks are complete."""
        active_tasks = [
            t for t in self.tasks.values()
            if t.status == LoadingState.LOADING
        ]
        if not active_tasks:
            self.all_tasks_complete.emit()
    
    def get_task(self, task_id: str) -> Optional[LoadingTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> list[LoadingTask]:
        """Get all tasks."""
        return list(self.tasks.values())
    
    def clear_tasks(self) -> None:
        """Clear completed tasks."""
        self.tasks = {
            task_id: task
            for task_id, task in self.tasks.items()
            if task.status == LoadingState.LOADING
        }


class LoadingIndicator:
    """ASCII loading indicators for console output."""
    
    SPINNERS = [
        ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],  # Braille
        ["|", "/", "-", "\\"],  # Simple
        ["◜", "◝", "◞", "◟"],  # Circular
        ["◐", "◓", "◑", "◒"],  # Moon
    ]
    
    @staticmethod
    def get_spinner(frame: int, style: int = 0) -> str:
        """Get spinner character for frame."""
        style = min(style, len(LoadingIndicator.SPINNERS) - 1)
        frames = LoadingIndicator.SPINNERS[style]
        return frames[frame % len(frames)]
    
    @staticmethod
    def get_progress_bar(progress: float, width: int = 20) -> str:
        """Get progress bar visualization.
        
        Args:
            progress: Progress percentage (0-100)
            width: Bar width in characters
            
        Returns:
            Progress bar string
        """
        filled = int(width * progress / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {progress:.0f}%"


class ConsoleLoaderIntegration:
    """Integration helper for console with loading system."""
    
    def __init__(self, system_console, loading_manager):
        """Initialize console loader integration.
        
        Args:
            system_console: SystemConsole instance
            loading_manager: LoadingManager instance
        """
        self.console = system_console
        self.loading_manager = loading_manager
        self.active_task_line = None
        
        # Connect signals
        loading_manager.task_started.connect(self._on_task_started)
        loading_manager.task_progress.connect(self._on_task_progress)
        loading_manager.task_completed.connect(self._on_task_completed)
        loading_manager.task_error.connect(self._on_task_error)
    
    def _on_task_started(self, task_id: str, name: str) -> None:
        """Handle task started."""
        self.console.log(f"⟳ Loading: {name}", level="INFO")
    
    def _on_task_progress(self, task_id: str, progress: float, message: str) -> None:
        """Handle task progress."""
        if progress < 100:
            bar = LoadingIndicator.get_progress_bar(progress)
            self.console.log(f"{bar} {message}", level="PROGRESS")
    
    def _on_task_completed(self, task_id: str, elapsed: float) -> None:
        """Handle task completed."""
        self.console.log(
            f"✓ Loading complete ({elapsed:.2f}s)",
            level="SUCCESS"
        )
    
    def _on_task_error(self, task_id: str, error: str) -> None:
        """Handle task error."""
        self.console.log(f"✗ Loading failed: {error}", level="ERROR")
