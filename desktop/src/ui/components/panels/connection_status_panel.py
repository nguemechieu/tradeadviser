"""Connection Status Indicator - Shows connection status and feed quality."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum
import logging


class ConnectionStatus(str, Enum):
    """Connection status states."""
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DEGRADED = "degraded"  # Connected but with data quality issues


class ConnectionStatusIndicator(ttk.Frame):
    """Widget showing connection status and metrics."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.status = ConnectionStatus.DISCONNECTED
        self.last_update: Optional[datetime] = None
        self.latency_ms: float = 0.0
        self.data_quality: float = 100.0  # 0-100%
        self.message_count: int = 0
        self.error_count: int = 0
        self.callbacks: Dict[str, list] = {
            'status_changed': [],
            'reconnect': []
        }
        
        self._create_ui()
        self._update_display()
    
    def _create_ui(self):
        """Create UI elements."""
        # Main frame horizontal layout
        self.pack(fill=tk.X, padx=5, pady=5)
        
        # Status indicator (colored circle)
        indicator_frame = ttk.Frame(self)
        indicator_frame.pack(side=tk.LEFT, padx=10)
        
        self.indicator_canvas = tk.Canvas(
            indicator_frame,
            width=20,
            height=20,
            bg='white',
            relief=tk.SUNKEN
        )
        self.indicator_canvas.pack()
        
        # Status text
        self.status_label = ttk.Label(self, text="Disconnected", font=('Arial', 10, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Latency
        ttk.Label(self, text="Latency:").pack(side=tk.LEFT, padx=2)
        self.latency_label = ttk.Label(self, text="N/A", font=('Arial', 9, 'bold'), foreground='blue')
        self.latency_label.pack(side=tk.LEFT, padx=2)
        
        # Data quality
        ttk.Label(self, text="Data Quality:").pack(side=tk.LEFT, padx=2)
        self.quality_label = ttk.Label(self, text="N/A", font=('Arial', 9, 'bold'), foreground='blue')
        self.quality_label.pack(side=tk.LEFT, padx=2)
        
        # Message count
        ttk.Label(self, text="Messages:").pack(side=tk.LEFT, padx=2)
        self.message_label = ttk.Label(self, text="0", font=('Arial', 9))
        self.message_label.pack(side=tk.LEFT, padx=2)
        
        # Last update
        ttk.Label(self, text="Updated:").pack(side=tk.LEFT, padx=2)
        self.update_time_label = ttk.Label(self, text="Never", font=('Arial', 9), foreground='gray')
        self.update_time_label.pack(side=tk.LEFT, padx=2)
        
        # Separator
        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Reconnect button
        self.reconnect_button = ttk.Button(
            self,
            text="Reconnect",
            command=self._on_reconnect
        )
        self.reconnect_button.pack(side=tk.RIGHT, padx=5)
        
        # Details button
        self.details_button = ttk.Button(
            self,
            text="Details",
            command=self._on_details
        )
        self.details_button.pack(side=tk.RIGHT, padx=2)
    
    def set_status(self, status: ConnectionStatus, message: str = None):
        """Set connection status."""
        if self.status != status:
            self.status = status
            for callback in self.callbacks.get('status_changed', []):
                callback(status)
        
        self._update_display()
        
        if message:
            self.logger.info(f"Connection status: {status.value} - {message}")
    
    def set_latency(self, latency_ms: float):
        """Set API latency in milliseconds."""
        self.latency_ms = latency_ms
        self._update_display()
    
    def set_data_quality(self, quality: float):
        """Set data feed quality (0-100%)."""
        self.data_quality = max(0, min(100, quality))
        self._update_display()
    
    def increment_message_count(self):
        """Increment received message counter."""
        self.message_count += 1
    
    def increment_error_count(self):
        """Increment error counter."""
        self.error_count += 1
    
    def update_timestamp(self):
        """Update last update timestamp."""
        self.last_update = datetime.utcnow()
    
    def _update_display(self):
        """Update UI to reflect current state."""
        # Update status indicator circle
        status_colors = {
            ConnectionStatus.CONNECTED: 'green',
            ConnectionStatus.CONNECTING: 'yellow',
            ConnectionStatus.DISCONNECTED: 'red',
            ConnectionStatus.ERROR: 'red',
            ConnectionStatus.DEGRADED: 'orange',
        }
        
        color = status_colors.get(self.status, 'gray')
        self.indicator_canvas.delete('all')
        self.indicator_canvas.create_oval(2, 2, 18, 18, fill=color, outline='black', width=2)
        
        # Update status text
        status_text = self.status.value.replace('_', ' ').title()
        self.status_label.config(text=status_text)
        
        # Update latency
        if self.latency_ms > 0:
            latency_text = f"{self.latency_ms:.1f}ms"
            latency_color = 'green' if self.latency_ms < 100 else 'orange' if self.latency_ms < 500 else 'red'
            self.latency_label.config(text=latency_text, foreground=latency_color)
        else:
            self.latency_label.config(text="N/A", foreground='gray')
        
        # Update data quality
        if self.data_quality >= 95:
            quality_text = f"{self.data_quality:.0f}%"
            quality_color = 'green'
        elif self.data_quality >= 80:
            quality_text = f"{self.data_quality:.0f}%"
            quality_color = 'orange'
        else:
            quality_text = f"{self.data_quality:.0f}%"
            quality_color = 'red'
        
        self.quality_label.config(text=quality_text, foreground=quality_color)
        
        # Update message count
        self.message_label.config(text=str(self.message_count))
        
        # Update last update time
        if self.last_update:
            elapsed = (datetime.utcnow() - self.last_update).total_seconds()
            if elapsed < 60:
                time_text = "< 1 min ago"
            elif elapsed < 3600:
                time_text = f"{int(elapsed/60)} min ago"
            else:
                time_text = f"{int(elapsed/3600)}h ago"
            
            self.update_time_label.config(text=time_text, foreground='gray')
        else:
            self.update_time_label.config(text="Never", foreground='red')
        
        # Update reconnect button state
        if self.status == ConnectionStatus.CONNECTED:
            self.reconnect_button.config(state=tk.DISABLED)
        else:
            self.reconnect_button.config(state=tk.NORMAL)
    
    def _on_reconnect(self):
        """Handle reconnect button."""
        for callback in self.callbacks.get('reconnect', []):
            callback()
        
        self.set_status(ConnectionStatus.CONNECTING, "Attempting to reconnect...")
    
    def _on_details(self):
        """Show detailed connection info."""
        # Create details window
        details_window = tk.Toplevel(self)
        details_window.title("Connection Details")
        details_window.geometry("400x300")
        
        frame = ttk.Frame(details_window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Add details
        details = [
            ("Status", self.status.value),
            ("Latency", f"{self.latency_ms:.2f}ms"),
            ("Data Quality", f"{self.data_quality:.1f}%"),
            ("Messages Received", str(self.message_count)),
            ("Errors", str(self.error_count)),
            ("Last Update", self.last_update.isoformat() if self.last_update else "Never"),
            ("Connected Duration", self._get_uptime()),
        ]
        
        for label, value in details:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=5)
            
            ttk.Label(row, text=label + ":", width=15).pack(side=tk.LEFT)
            ttk.Label(row, text=value, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _get_uptime(self) -> str:
        """Get connection uptime."""
        # TODO: Implement uptime tracking
        return "N/A"
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback."""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)


class MultiConnectionIndicator(ttk.Frame):
    """Shows multiple broker/data feed connections."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.connections: Dict[str, ConnectionStatusIndicator] = {}
        
        self._create_ui()
    
    def _create_ui(self):
        """Create UI."""
        # Header
        header = ttk.Label(self, text="Broker & Data Connections", font=('Arial', 10, 'bold'))
        header.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)
        
        # Container for connection indicators
        self.connections_frame = ttk.Frame(self)
        self.connections_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def add_connection(self, name: str, broker_or_feed: str):
        """Add a new connection indicator."""
        frame = ttk.LabelFrame(self.connections_frame, text=f"{name} ({broker_or_feed})", padding=5)
        frame.pack(fill=tk.X, pady=5)
        
        indicator = ConnectionStatusIndicator(frame)
        self.connections[name] = indicator
        
        return indicator
    
    def get_connection(self, name: str) -> Optional[ConnectionStatusIndicator]:
        """Get a connection indicator by name."""
        return self.connections.get(name)
