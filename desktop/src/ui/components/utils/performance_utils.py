"""Performance optimization utilities for UI responsiveness.

This module provides tools to prevent UI blocking:
- Throttled/debounced signal handlers
- Batch table updates
- Lazy loading for large datasets
- Performance monitoring
"""

import time
from PySide6.QtCore import QTimer


class ThrottledHandler:
    """Throttles callback invocations to prevent UI blocking from frequent signals."""
    
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
    
    def trigger(self, *args, **kwargs):
        """Request callback invocation (throttled)."""
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
            self.timer.start(int(self.throttle_ms - elapsed))
    
    def _invoke(self):
        """Execute callback with latest args."""
        try:
            self.callback(*self.last_args, **self.last_kwargs)
        finally:
            self.last_call = time.time()
    
    def _on_throttle_timeout(self):
        """Handle timer timeout."""
        if self.pending:
            self.pending = False
            self._invoke()
            if self.pending:
                self.timer.start(self.throttle_ms)
    
    def stop(self):
        """Stop pending operations."""
        self.timer.stop()
        self.pending = False


class DebouncedHandler:
    """Debounces callback invocations to wait for activity to settle."""
    
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
    
    def trigger(self, *args, **kwargs):
        """Request callback invocation (debounced)."""
        self.last_args = args
        self.last_kwargs = kwargs
        self.timer.stop()
        self.timer.start(self.debounce_ms)
    
    def _on_debounce_timeout(self):
        """Execute callback after debounce period."""
        try:
            self.callback(*self.last_args, **self.last_kwargs)
        finally:
            pass
    
    def stop(self):
        """Stop pending operations."""
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
    """Lazy-loads table rows in batches to prevent UI blocking."""
    
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
        """Start lazy loading process."""
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
                    self.populate_row(self.table, row, self.rows_data[row])
        
        self.current_row = end_row
        
        # Schedule next batch if more rows exist
        if self.current_row < len(self.rows_data):
            self.timer.start(10)  # 10ms delay between batches


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
