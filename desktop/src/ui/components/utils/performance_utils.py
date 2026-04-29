"""Performance optimization utilities for UI responsiveness.

This module provides tools to prevent UI blocking:
- Throttled/debounced signal handlers
- Batch table updates
- Lazy loading for large datasets
- Performance monitoring
"""

import time
import threading
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def _is_main_thread() -> bool:
    """Check if currently running on the main Qt thread."""
    try:
        return QApplication.instance() and threading.current_thread() is threading.main_thread()
    except Exception:
        traceback.print_exc()
        return False


def safe_timer_start(timer: QTimer, interval_ms: int) -> None:
    """Safely start a QTimer from any thread.
    
    If called from the main Qt thread, starts the timer directly.
    If called from a background thread, uses QTimer.singleShot (thread-safe).
    
    Args:
        timer: QTimer instance to start
        interval_ms: Interval in milliseconds
    """
    if timer is None:
        return
    
    try:
        if _is_main_thread():
            if not timer.isActive():
                timer.start(interval_ms)
        else:
            # From background thread: use singleShot to emit timeout on main thread
            if hasattr(timer, 'timeout'):
                # Cancel any pending single shots and schedule new one
                QTimer.singleShot(interval_ms, timer.timeout.emit)
    except RuntimeError:
        # Timer may have been deleted or is invalid
        pass
    except Exception:
        # Suppress any other Qt-related errors
        pass


class ThrottledHandler:
    """Throttles callback invocations to prevent UI blocking from frequent signals.
    
    Thread-safe: Can be triggered from any thread. Timer operations are marshalled
    to the main Qt thread automatically.
    """
    
    def __init__(self, callback, throttle_ms=500):
        """
        Initialize throttled handler.
        
        Args:
            callback: Function to call (must be re-entrant safe)
            throttle_ms: Minimum milliseconds between calls (default 500ms)
        """
        self.callback = callback
        self.throttle_ms = throttle_ms
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_throttle_timeout)
        self.pending = False
        self.last_call = 0
        self._lock = threading.Lock()
    
    def trigger(self, *args, **kwargs):
        """Request callback invocation (throttled). Thread-safe."""
        with self._lock:
            self.last_args = args
            self.last_kwargs = kwargs
            
            if self.timer.isActive():
                self.pending = True
                return
            
            elapsed = (time.time() - self.last_call) * 1000
            if elapsed >= self.throttle_ms:
                self._invoke()
            else:
                self.pending = True
                # Use QTimer.singleShot (thread-safe) instead of timer.start()
                delay = int(self.throttle_ms - elapsed)
                if _is_main_thread():
                    self.timer.start(delay)
                else:
                    QTimer.singleShot(delay, self._on_throttle_timeout)
    
    def _invoke(self):
        """Execute callback with latest args."""
        try:
            self.callback(*self.last_args, **self.last_kwargs)
        except Exception:
            pass
        finally:
            self.last_call = time.time()
    
    def _on_throttle_timeout(self):
        """Handle timer timeout."""
        with self._lock:
            if self.pending:
                self.pending = False
                self._invoke()
                if self.pending:
                    if _is_main_thread():
                        self.timer.start(self.throttle_ms)
                    else:
                        QTimer.singleShot(self.throttle_ms, self._on_throttle_timeout)
    
    def stop(self):
        """Stop pending operations."""
        with self._lock:
            self.timer.stop()
            self.pending = False


class DebouncedHandler:
    """Debounces callback invocations to wait for activity to settle.
    
    Thread-safe: Can be triggered from any thread. Timer operations are marshalled
    to the main Qt thread automatically.
    """
    
    def __init__(self, callback, debounce_ms=300):
        """
        Initialize debounced handler.
        
        Args:
            callback: Function to call after activity settles
            debounce_ms: Milliseconds to wait after last trigger (default 300ms)
        """
        self.callback = callback
        self.debounce_ms = debounce_ms
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_debounce_timeout)
        self._lock = threading.Lock()
    
    def trigger(self, *args, **kwargs):
        """Request callback invocation (debounced). Thread-safe."""
        with self._lock:
            self.last_args = args
            self.last_kwargs = kwargs
            self.timer.stop()
            # Use QTimer.singleShot (thread-safe) instead of timer.start()
            if _is_main_thread():
                self.timer.start(self.debounce_ms)
            else:
                QTimer.singleShot(self.debounce_ms, self._on_debounce_timeout)
    
    def _on_debounce_timeout(self):
        """Execute callback after debounce period."""
        with self._lock:
            try:
                self.callback(*self.last_args, **self.last_kwargs)
            except Exception:
                pass
    
    def stop(self):
        """Stop pending operations."""
        with self._lock:
            self.timer.stop()


class PerformanceMonitor:
    """Context manager for measuring operation duration and logging slow operations."""
    
    def __init__(self, name, threshold_ms=100, logger=None):
        """
        Initialize performance monitor.
        
        Args:
            name: Operation name for logging
            threshold_ms: Log warning if exceeds threshold (default 100ms)
            logger: Logger instance (optional)
        """
        self.name = name
        self.threshold_ms = threshold_ms
        self.logger = logger
        self.start = None
        self.elapsed_ms = 0
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed_ms = (time.time() - self.start) * 1000
        if self.elapsed_ms > self.threshold_ms:
            msg = f"⚠️ {self.name} took {self.elapsed_ms:.1f}ms (threshold: {self.threshold_ms}ms)"
            if self.logger:
                self.logger.warning(msg)
            else:
                print(msg)


def batch_table_updates(table_widget):
    """Context manager for batch table updates with disabled rendering."""
    
    class BatchUpdateContext:
        def __init__(self, table):
            self.table = table
            self.previous_enabled = None
        
        def __enter__(self):
            try:
                self.previous_enabled = self.table.updatesEnabled()
                self.table.setUpdatesEnabled(False)
            except Exception:
                self.previous_enabled = None
            return self
        
        def __exit__(self, *args):
            try:
                if self.previous_enabled is not None:
                    self.table.setUpdatesEnabled(self.previous_enabled)
                else:
                    self.table.setUpdatesEnabled(True)
                self.table.update()
            except Exception:
                pass
    
    return BatchUpdateContext(table_widget)


class LazyTableLoader:
    """Lazy-loads table rows in batches to prevent UI blocking.
    
    Note: Intended for main-thread use. All timer operations occur on main thread.
    """
    
    def __init__(self, table_widget, rows_data, batch_size=50, populate_row_callback=None):
        """
        Initialize lazy table loader.
        
        Args:
            table_widget: QTableWidget to populate
            rows_data: List of row data to load
            batch_size: Number of rows per batch (default 50)
            populate_row_callback: Function(table, row_index, row_data) to populate each row
        """
        self.table = table_widget
        self.rows_data = rows_data
        self.batch_size = batch_size
        self.populate_row = populate_row_callback
        self.current_row = 0
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._load_batch)
    
    def start(self):
        """Start lazy loading process. Must be called from main thread."""
        if not self.rows_data:
            return
        
        # Set total row count upfront
        with batch_table_updates(self.table):
            self.table.setRowCount(len(self.rows_data))
        
        self._load_batch()
    
    def _load_batch(self):
        """Load next batch of rows."""
        end_row = min(self.current_row + self.batch_size, len(self.rows_data))
        
        with batch_table_updates(self.table):
            for row in range(self.current_row, end_row):
                if self.populate_row:
                    try:
                        self.populate_row(self.table, row, self.rows_data[row])
                    except Exception:
                        pass
        
        self.current_row = end_row
        
        # Schedule next batch if more rows exist (use singleShot for thread safety)
        if self.current_row < len(self.rows_data):
            if _is_main_thread():
                self.timer.start(10)
            else:
                QTimer.singleShot(10, self._load_batch)


class TableDataCache:
    """Caches table data to avoid redundant updates."""
    
    def __init__(self):
        self.data = {}
        self.signature = None
    
    def compute_signature(self, data):
        """Compute hash signature of data."""
        if not data:
            return None
        
        try:
            # Create a simple signature from data
            parts = []
            for item in (data[:5] if len(data) > 5 else data):
                if isinstance(item, dict):
                    parts.append(str(sorted(item.items())))
                else:
                    parts.append(str(item))
            return hash(tuple(parts))
        except Exception:
            return None
    
    def should_update(self, new_data):
        """Check if data has changed."""
        new_sig = self.compute_signature(new_data)
        if new_sig != self.signature:
            self.signature = new_sig
            return True
        return False
    
    def clear(self):
        """Clear cache."""
        self.data.clear()
        self.signature = None
