# Professional Venue Panel - Implementation Guide

## Overview

The Professional Venue Panel is a new desktop UI component that displays trading venue and broker connection status in a professional, investpro-style table format. It provides real-time monitoring of:

- **Connection Status**: Health indicators (healthy, degraded, unhealthy, offline)
- **Latency Metrics**: Real-time network latency in milliseconds with color-coded thresholds
- **Uptime Tracking**: Venue uptime percentage with visual indicators
- **Volume Metrics**: 24-hour trading volume formatted appropriately
- **Connection Count**: Active connections per venue
- **Summary Statistics**: Overall status, connected venue count, average latency, total volume

## File Structure

```
desktop/src/ui/components/panels/
├── venue_panel.py              # NEW: Professional venue monitoring panel
├── system_panels.py             # UPDATED: Import venue panel
├── __init__.py
└── ... other panels
```

## Key Components

### VenueConnectionStatus (Data Class)
```python
class VenueConnectionStatus:
    name: str                   # Venue name (e.g., "Alpaca", "Interactive Brokers")
    venue_type: str            # Venue type (e.g., "US Equities", "Crypto")
    status: str                # Connection status (healthy/degraded/unhealthy/offline)
    latency_ms: int            # Network latency in milliseconds
    connections: int           # Number of active connections
    uptime_pct: float          # Uptime percentage (0-100)
    volume_24h: float          # 24-hour trading volume
    last_update: datetime      # Timestamp of last update
    error_message: str         # Error description if applicable
```

### Core Functions

#### `create_venue_panel(terminal) -> QDockWidget`
Creates the professional venue monitoring dock widget and integrates it into the terminal.

**Returns**: Configured QDockWidget with venue panel

**Example**:
```python
from ui.components.panels.system_panels import create_venue_panel

# In terminal initialization
venue_dock = create_venue_panel(terminal)
```

#### `update_venue_panel(terminal, venues: Dict[str, VenueConnectionStatus])`
Updates the venue panel table with current venue status data.

**Parameters**:
- `terminal`: Main terminal window instance
- `venues`: Dictionary mapping venue names to VenueConnectionStatus objects

**Example**:
```python
from ui.components.panels.venue_panel import update_venue_panel, VenueConnectionStatus

venues = {
    "Alpaca": VenueConnectionStatus("Alpaca", "US Equities", "healthy"),
    "Interactive Brokers": VenueConnectionStatus("IB", "Global", "healthy"),
}

venues["Alpaca"].latency_ms = 45
venues["Alpaca"].connections = 5
venues["Alpaca"].uptime_pct = 99.98
venues["Alpaca"].volume_24h = 5_200_000_000

update_venue_panel(terminal, venues)
```

#### `populate_sample_venues(terminal)`
Populates the venue panel with realistic sample data for testing and demonstration.

**Example**:
```python
from ui.components.panels.venue_panel import populate_sample_venues

populate_sample_venues(terminal)
```

## UI Styling

The venue panel uses the application's dark theme with the following color scheme:

### Status Indicators
- **Healthy**: `#10b981` (green)
- **Degraded**: `#f59e0b` (amber)
- **Unhealthy**: `#ef4444` (red)
- **Offline**: `#6b7280` (gray)

### Latency Color Coding
- **Low** (<100ms): `#67e2a3` (green)
- **Medium** (100-200ms): `#f7b666` (orange)
- **High** (>200ms): `#ff7d8d` (red)

### Uptime Color Coding
- **Excellent** (≥99%): `#67e2a3` (green)
- **Good** (95-99%): `#f7b666` (orange)
- **Poor** (<95%): `#ff7d8d` (red)

## Integration with Terminal

To integrate the venue panel into the main terminal:

1. **Import the venue panel creation function** in `terminal.py`:
```python
from ui.components.panels.system_panels import create_venue_panel
```

2. **Create the dock widget** during terminal initialization:
```python
def __init__(self, ...):
    # ... other initialization ...
    self.venue_dock = create_venue_panel(self)
```

3. **Update venue data** periodically or on broker status changes:
```python
def on_broker_status_update(self, status_data):
    from ui.components.panels.venue_panel import update_venue_panel
    update_venue_panel(self, status_data.venues)
```

4. **Show/hide the panel** through the View menu or keyboard shortcut:
```python
def show_venue_panel(self):
    if hasattr(self, 'venue_panel_dock'):
        self.venue_panel_dock.show()
        self.venue_panel_dock.raise_()
```

## Data Flow Architecture

```
Broker API / Connection Manager
         ↓
   Broker Status Event
         ↓
   Terminal Event Handler
         ↓
   Create VenueConnectionStatus objects
         ↓
   update_venue_panel(terminal, venues)
         ↓
   Venue Panel UI Update
         ↓
   Visual Display (Table, Metrics, Indicators)
```

## Summary Display

The panel header displays four key metrics:

1. **Overall Status**: Aggregated connection status (online/offline)
   - Indicated by colored status dot (●)
   - Updates based on connected venue count

2. **Connected Venues**: Shows ratio (e.g., "Connected: 3/5")
   - Green when > 0 venues connected
   - Gray when all offline

3. **Average Latency**: Mean latency across all connected venues
   - Shows "--ms" if no venues connected
   - Color-coded based on latency ranges

4. **24h Volume**: Total trading volume across all venues
   - Formatted in billions, millions, or thousands
   - Real-time update capability

## Column Descriptions

| Column | Purpose | Notes |
|--------|---------|-------|
| Status | Visual health indicator | Single colored dot |
| Venue Name | Broker/exchange name | Bold, prominent |
| Type | Venue classification | e.g., "US Equities", "Crypto" |
| Latency | Network response time | Color-coded (green/orange/red) |
| Active Connections | Count of live connections | Center-aligned number |
| Uptime | Service availability | Percentage with color coding |
| 24h Volume | Trading volume | Formatted (B/M/K) |

## Performance Considerations

- **Table Updates**: O(n) where n = number of venues (typically 5-15)
- **Rendering**: Optimized with ResizeToContents headers
- **Memory**: Minimal overhead, single instance per terminal
- **Refresh Rate**: Can update every 1-5 seconds without lag

## Example Integration in Terminal.py

```python
# At the top of terminal.py
from ui.components.panels.system_panels import create_venue_panel
from ui.components.panels.venue_panel import update_venue_panel, VenueConnectionStatus

# In Terminal.__init__()
self.venue_dock = create_venue_panel(self)

# In a broker status update handler
def on_broker_connectivity_update(self, broker_data):
    """Handle broker connection status updates."""
    venues = {}
    
    for broker_name, broker_status in broker_data.items():
        venue = VenueConnectionStatus(
            name=broker_name,
            venue_type=broker_status.get("type", "Broker"),
            status=broker_status.get("status", "offline")
        )
        venue.latency_ms = broker_status.get("latency_ms", 0)
        venue.connections = broker_status.get("connections", 0)
        venue.uptime_pct = broker_status.get("uptime_pct", 0.0)
        venue.volume_24h = broker_status.get("volume_24h", 0)
        
        venues[broker_name] = venue
    
    update_venue_panel(self, venues)
```

## Testing the Venue Panel

To test with sample data:

```python
from ui.components.panels.venue_panel import populate_sample_venues

# In your test or during development
populate_sample_venues(terminal)

# This populates with realistic sample venues:
# - Alpaca (healthy, low latency)
# - Interactive Brokers (healthy, medium latency)
# - Charles Schwab (degraded, higher latency)
# - Coinbase (unhealthy, high latency)
# - Binance (offline)
```

## Future Enhancements

Potential improvements for future versions:

1. **Real-time Updates**: WebSocket connection for continuous status updates
2. **Alert System**: Notifications for status changes or latency spikes
3. **Latency Graphs**: Mini charts showing latency trends over time
4. **Connection Details**: Click-to-expand rows showing detailed connection information
5. **Historical Data**: Store and display historical uptime and latency trends
6. **Configuration**: User-defined latency thresholds and color schemes
7. **Export**: Download venue status reports in CSV/JSON format

## Troubleshooting

### Panel Not Showing
- Ensure `create_venue_panel(terminal)` is called during terminal initialization
- Check that the dock widget area is properly configured (BottomDockWidgetArea)
- Verify the import statement: `from ui.components.panels.system_panels import create_venue_panel`

### Data Not Updating
- Ensure `update_venue_panel()` is called with proper VenueConnectionStatus objects
- Check that all required attributes are set (status, latency_ms, etc.)
- Verify the terminal object has proper attributes (venue_table, venue_overall_status, etc.)

### Styling Issues
- Verify the dark theme CSS is properly applied
- Check for conflicting stylesheets in parent widgets
- Ensure QTableWidget styling is not overridden elsewhere

## Dependencies

- **PyQt6/PySide6**: GUI framework
- **logging**: Standard Python logging module
- **typing**: Type hints for better code documentation

All other dependencies are standard Python libraries.
