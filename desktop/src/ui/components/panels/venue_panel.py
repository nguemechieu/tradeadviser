"""Professional Venue/Broker Panel - InvestPro Style Display.

This module provides a professional venue and broker connection monitoring panel
with real-time status, latency, uptime, and connection metrics displayed in a
professional table format inspired by investment platforms like InvestPro.
"""

from typing import Optional, Dict, Any
import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QProgressBar, QGridLayout,
    QStyleFactory
)
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QBrush


logger = logging.getLogger("VenuePanel")


class VenueConnectionStatus:
    """Data class for venue connection status."""
    def __init__(self, name: str, venue_type: str = "Broker", status: str = "offline"):
        self.name = name
        self.venue_type = venue_type
        self.status = status  # healthy, degraded, unhealthy, offline
        self.latency_ms = 0
        self.connections = 0
        self.uptime_pct = 100.0
        self.volume_24h = 0
        self.last_update = None
        self.error_message = ""


def create_venue_panel(terminal):
    """Create the professional venue monitoring panel.
    
    Args:
        terminal: The main terminal window
        
    Returns:
        QDockWidget: The configured venue panel dock widget
    """
    dock = QDockWidget("Trading Venues", terminal)
    dock.setObjectName("venue_panel_dock")
    dock.setMinimumHeight(250)
    dock.setMinimumWidth(600)
    
    container = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(12)
    
    # Header with summary metrics
    summary_layout = QHBoxLayout()
    summary_layout.setSpacing(20)
    
    # Overall status indicator
    terminal.venue_overall_status = QLabel("●")
    terminal.venue_overall_status.setFont(QFont("Arial", 14, QFont.Weight.Bold))
    terminal.venue_overall_status.setStyleSheet("color: #6b7280;")  # offline gray
    
    terminal.venue_overall_label = QLabel("Overall Status: Offline")
    terminal.venue_overall_label.setStyleSheet("color: #e6edf7; font-weight: 600;")
    
    summary_layout.addWidget(terminal.venue_overall_status)
    summary_layout.addWidget(terminal.venue_overall_label)
    summary_layout.addSpacing(20)
    
    # Connected venues count
    terminal.venue_connected_count = QLabel("Connected: 0/0")
    terminal.venue_connected_count.setStyleSheet("color: #a8b4c6;")
    summary_layout.addWidget(terminal.venue_connected_count)
    
    # Average latency
    terminal.venue_avg_latency = QLabel("Avg Latency: --ms")
    terminal.venue_avg_latency.setStyleSheet("color: #a8b4c6;")
    summary_layout.addWidget(terminal.venue_avg_latency)
    
    # Total 24h volume
    terminal.venue_24h_volume = QLabel("24h Volume: $0")
    terminal.venue_24h_volume.setStyleSheet("color: #a8b4c6;")
    summary_layout.addWidget(terminal.venue_24h_volume)
    
    summary_layout.addStretch()
    layout.addLayout(summary_layout)
    
    # Professional venue table
    terminal.venue_table = QTableWidget()
    terminal.venue_table.setColumnCount(7)
    terminal.venue_table.setHorizontalHeaderLabels([
        "Status",
        "Venue Name",
        "Type",
        "Latency",
        "Active Connections",
        "Uptime",
        "24h Volume"
    ])
    
    # Table styling
    terminal.venue_table.setStyleSheet("""
        QTableWidget {
            background-color: transparent;
            gridline-color: #1e293b;
            border: 1px solid rgba(136, 168, 203, 0.16);
            border-radius: 8px;
            font-size: 10pt;
        }
        QTableWidget::item {
            padding: 4px;
            border-bottom: 1px solid rgba(136, 168, 203, 0.08);
        }
        QHeaderView::section {
            background-color: rgba(18, 33, 53, 0.8);
            color: #8fa3bf;
            padding: 6px;
            border: none;
            font-weight: bold;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QTableWidget::item:selected {
            background-color: rgba(83, 180, 255, 0.15);
        }
    """)
    
    # Set column widths
    header = terminal.venue_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Status
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Venue Name
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Latency
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Connections
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Uptime
    header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Volume
    
    terminal.venue_table.verticalHeader().setVisible(False)
    terminal.venue_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
    )
    terminal.venue_table.setSelectionMode(
        QTableWidget.SelectionMode.SingleSelection
    )
    terminal.venue_table.setAlternatingRowColors(False)
    terminal.venue_table.setRowCount(0)
    
    layout.addWidget(terminal.venue_table)
    
    container.setLayout(layout)
    dock.setWidget(container)
    
    terminal.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    dock.hide()
    
    terminal.venue_panel = container
    terminal.venue_panel_dock = dock
    
    return dock


def update_venue_panel(terminal, venues: Dict[str, VenueConnectionStatus]):
    """Update the venue panel with venue status data.
    
    Args:
        terminal: The main terminal window
        venues: Dictionary mapping venue names to VenueConnectionStatus objects
    """
    if not hasattr(terminal, 'venue_table'):
        logger.warning("Venue table not initialized")
        return
    
    try:
        # Clear existing rows
        terminal.venue_table.setRowCount(0)
        
        # Calculate summary metrics
        total_venues = len(venues)
        connected_venues = sum(1 for v in venues.values() if v.status == "healthy")
        avg_latency = 0
        total_volume = 0
        
        latencies = [v.latency_ms for v in venues.values() if v.latency_ms > 0]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        
        total_volume = sum(v.volume_24h for v in venues.values())
        
        # Update summary metrics
        overall_status = "online" if connected_venues > 0 else "offline"
        status_color = _get_status_color(overall_status)
        
        terminal.venue_overall_status.setText("●")
        terminal.venue_overall_status.setStyleSheet(f"color: {status_color};")
        terminal.venue_overall_label.setText(f"Overall Status: {overall_status.upper()}")
        terminal.venue_connected_count.setText(f"Connected: {connected_venues}/{total_venues}")
        terminal.venue_avg_latency.setText(f"Avg Latency: {int(avg_latency)}ms")
        
        # Format volume (millions or billions)
        if total_volume >= 1e9:
            volume_text = f"24h Volume: ${total_volume/1e9:.2f}B"
        else:
            volume_text = f"24h Volume: ${total_volume/1e6:.1f}M"
        terminal.venue_24h_volume.setText(volume_text)
        
        # Populate venue table
        for venue_name, venue in venues.items():
            row = terminal.venue_table.rowCount()
            terminal.venue_table.insertRow(row)
            
            # Status indicator
            status_item = QTableWidgetItem("●")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_color = _get_status_color(venue.status)
            status_item.setForeground(QColor(status_color))
            status_font = QFont()
            status_font.setPointSize(12)
            status_item.setFont(status_font)
            status_item.setToolTip(f"Status: {venue.status}")
            terminal.venue_table.setItem(row, 0, status_item)
            
            # Venue name with type icon
            name_item = QTableWidgetItem(venue_name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            name_font = QFont()
            name_font.setBold(True)
            name_item.setFont(name_font)
            name_item.setForeground(QColor("#e6edf7"))
            terminal.venue_table.setItem(row, 1, name_item)
            
            # Venue type
            type_item = QTableWidgetItem(venue.venue_type)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            type_item.setForeground(QColor("#a8b4c6"))
            terminal.venue_table.setItem(row, 2, type_item)
            
            # Latency with color coding
            latency_text = f"{int(venue.latency_ms)}ms"
            latency_item = QTableWidgetItem(latency_text)
            latency_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            latency_color = "#67e2a3"  # green for low latency
            if venue.latency_ms > 200:
                latency_color = "#ff7d8d"  # red for high latency
            elif venue.latency_ms > 100:
                latency_color = "#f7b666"  # orange for medium latency
            
            latency_item.setForeground(QColor(latency_color))
            latency_font = QFont()
            latency_font.setWeight(QFont.Weight.Bold)
            latency_item.setFont(latency_font)
            terminal.venue_table.setItem(row, 3, latency_item)
            
            # Active connections
            conn_item = QTableWidgetItem(str(venue.connections))
            conn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            conn_item.setForeground(QColor("#a8b4c6"))
            terminal.venue_table.setItem(row, 4, conn_item)
            
            # Uptime with progress bar display
            uptime_item = QTableWidgetItem(f"{venue.uptime_pct:.1f}%")
            uptime_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            uptime_color = "#67e2a3"  # green
            if venue.uptime_pct < 95:
                uptime_color = "#ff7d8d"  # red
            elif venue.uptime_pct < 99:
                uptime_color = "#f7b666"  # orange
            
            uptime_item.setForeground(QColor(uptime_color))
            uptime_font = QFont()
            uptime_font.setWeight(QFont.Weight.Bold)
            uptime_item.setFont(uptime_font)
            terminal.venue_table.setItem(row, 5, uptime_item)
            
            # 24h Volume
            volume_item = QTableWidgetItem(_format_volume(venue.volume_24h))
            volume_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            volume_item.setForeground(QColor("#a8b4c6"))
            terminal.venue_table.setItem(row, 6, volume_item)
            
            # Row styling based on status
            for col in range(7):
                item = terminal.venue_table.item(row, col)
                if venue.status == "healthy":
                    item.setBackground(QColor(0, 0, 0, 0))  # transparent
                elif venue.status == "degraded":
                    item.setBackground(QColor(247, 182, 102, 15))  # orange tint
                elif venue.status == "unhealthy":
                    item.setBackground(QColor(255, 125, 141, 15))  # red tint
                else:  # offline
                    item.setBackground(QColor(107, 114, 128, 10))  # gray tint
        
        terminal.venue_table.resizeRowsToContents()
        
    except Exception as e:
        logger.exception(f"Error updating venue panel: {e}")


def _get_status_color(status: str) -> str:
    """Get the color for a status value.
    
    Args:
        status: Status string (healthy, degraded, unhealthy, offline, online)
        
    Returns:
        Hex color code for the status
    """
    status_colors = {
        "healthy": "#10b981",     # green
        "degraded": "#f59e0b",    # amber
        "unhealthy": "#ef4444",   # red
        "offline": "#6b7280",     # gray
        "online": "#10b981",      # green
    }
    return status_colors.get(status, "#6b7280")


def _format_volume(volume: float) -> str:
    """Format volume value with appropriate unit.
    
    Args:
        volume: Volume in absolute value
        
    Returns:
        Formatted volume string
    """
    if volume >= 1e9:
        return f"${volume/1e9:.2f}B"
    elif volume >= 1e6:
        return f"${volume/1e6:.1f}M"
    elif volume >= 1e3:
        return f"${volume/1e3:.0f}K"
    else:
        return f"${volume:.0f}"


def populate_sample_venues(terminal):
    """Populate the venue panel with sample data for testing.
    
    Args:
        terminal: The main terminal window
    """
    venues = {
        "Alpaca": VenueConnectionStatus("Alpaca", "US Equities", "healthy"),
        "Interactive Brokers": VenueConnectionStatus("Interactive Brokers", "Global", "healthy"),
        "Charles Schwab": VenueConnectionStatus("Charles Schwab", "US Equities", "degraded"),
        "Coinbase": VenueConnectionStatus("Coinbase", "Crypto", "unhealthy"),
        "Binance": VenueConnectionStatus("Binance", "Crypto", "offline"),
    }
    
    # Set sample metrics
    venues["Alpaca"].latency_ms = 45
    venues["Alpaca"].connections = 5
    venues["Alpaca"].uptime_pct = 99.98
    venues["Alpaca"].volume_24h = 5_200_000_000
    
    venues["Interactive Brokers"].latency_ms = 78
    venues["Interactive Brokers"].connections = 8
    venues["Interactive Brokers"].uptime_pct = 99.95
    venues["Interactive Brokers"].volume_24h = 12_400_000_000
    
    venues["Charles Schwab"].latency_ms = 156
    venues["Charles Schwab"].connections = 3
    venues["Charles Schwab"].uptime_pct = 98.7
    venues["Charles Schwab"].volume_24h = 2_100_000_000
    
    venues["Coinbase"].latency_ms = 287
    venues["Coinbase"].connections = 1
    venues["Coinbase"].uptime_pct = 92.3
    venues["Coinbase"].volume_24h = 890_000_000
    
    venues["Binance"].latency_ms = 0
    venues["Binance"].connections = 0
    venues["Binance"].uptime_pct = 0.0
    venues["Binance"].volume_24h = 0
    
    update_venue_panel(terminal, venues)
