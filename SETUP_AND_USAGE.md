# TradeAdviser System Improvements - Setup & Usage Guide

## Quick Start

### 1. Initial Setup

```bash
# Install dependencies
pip install -r requirements-prod.txt

# Initialize configuration
python -c "
from config.config_manager import ConfigManager
config_mgr = ConfigManager('config.json')
config_mgr.save()
"

# Setup logging
python -c "
from system.logging_setup import setup_logging
setup_logging(
    log_level='INFO',
    log_file='logs/app.log',
    console_enabled=True,
    file_enabled=True
)
"
```

### 2. Application Startup

```python
import asyncio
from config.config_manager import ConfigManager
from session.session_manager import SessionManager
from system.logging_setup import setup_logging
from ui.components.terminal_professional import ProfessionalTerminal, TerminalConfig

async def main():
    # Setup logging
    setup_logging(log_level='INFO')
    
    # Load configuration
    config_mgr = ConfigManager('config.json')
    config_mgr.load()
    
    # Initialize terminal
    terminal_config = TerminalConfig()
    terminal = ProfessionalTerminal(config=terminal_config)
    
    # Create session manager
    session_mgr = SessionManager(parent_controller=None)
    
    # Create trading session
    config = config_mgr.config.broker
    session = await session_mgr.create_session(config)
    
    terminal.set_active_session(session.session_id)
    terminal.show()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Configuration Management

### Basic Configuration

```python
from config.config_manager import ConfigManager

# Load configuration
config_mgr = ConfigManager('config.json')
config_mgr.load()

# Access settings
exchange = config_mgr.get('broker.exchange')
api_key = config_mgr.get('broker.api_key')

# Update settings
config_mgr.set('broker.mode', 'live')
config_mgr.set('risk.max_drawdown_pct', 15.0)

# Save changes
config_mgr.save()

# Validate
is_valid, error = config_mgr.validate()
```

### Configuration Structure

```json
{
  "app_name": "TradeAdviser",
  "version": "2.0.0",
  "debug": false,
  "broker": {
    "exchange": "alpaca",
    "mode": "paper",
    "api_key": "your_key",
    "api_secret": "your_secret"
  },
  "strategy": {
    "name": "TrendFollowing",
    "timeframe": "1h",
    "symbols": ["AAPL", "MSFT", "GOOGL"]
  },
  "risk": {
    "max_drawdown_pct": 10.0,
    "max_position_size_pct": 5.0,
    "max_gross_exposure_pct": 100.0
  },
  "terminal": {
    "chart_buffer_size": 500,
    "theme": "dark",
    "max_panels": 8
  },
  "logging": {
    "level": "INFO",
    "file_path": "logs/app.log",
    "console_enabled": true
  }
}
```

---

## Session Management

### Creating and Managing Sessions

```python
from session.session_manager import SessionManager
from session.lifecycle_manager import SessionLifecycleManager

# Create session manager
session_manager = SessionManager(parent_controller=controller)

# Create a session
config = BrokerConfig(
    exchange="alpaca",
    mode="paper",
    api_key="your_key"
)
session = await session_manager.create_session(config)

# Activate session
await session_manager.activate_session(session.session_id)

# Start trading
await session_manager.start_session(session.session_id)

# Stop trading
await session_manager.stop_session(session.session_id)

# Destroy session
await session_manager.destroy_session(session.session_id)
```

### Session Lifecycle Management

```python
from session.lifecycle_manager import SessionLifecycleManager

lifecycle = SessionLifecycleManager(session_id="session-123")

# Initialize with timeout protection
async def init_session():
    # Your initialization code
    pass

success = await lifecycle.initialize(init_session)

# Health monitoring
async def check_health():
    # Your health check code
    pass

is_healthy = await lifecycle.heartbeat(check_health)

# Error handling
def handle_error(error_type: str, exception: Exception):
    print(f"Error: {error_type} - {exception}")

lifecycle.register_error_handler("connection_error", handle_error)

# Get metrics
metrics = lifecycle.get_metrics()
print(f"Errors: {metrics.consecutive_errors}")
print(f"Health: {lifecycle.get_health()}")
```

---

## Portfolio Analysis & Risk Management

### Risk Analysis

```python
from analysis.portfolio_optimizer import RiskManager, Portfolio

risk_mgr = RiskManager()

# Create portfolio
portfolio = Portfolio(
    symbols=["AAPL", "MSFT", "GOOGL"],
    weights={"AAPL": 0.3, "MSFT": 0.4, "GOOGL": 0.3},
    cash=10000,
    total_value=100000
)

# Analyze risk
returns = [0.01, 0.02, -0.01, 0.03, ...]  # Historical returns
analysis = risk_mgr.analyze_portfolio(portfolio, returns)

print(f"VaR (95%): {analysis.var_95:.4f}")
print(f"Sharpe Ratio: {analysis.sharpe_ratio:.4f}")
print(f"Max Drawdown: {analysis.max_drawdown:.4f}")
print(f"Health: {analysis.is_healthy()}")
```

### Portfolio Optimization

```python
# Optimize weights
assets = {
    "AAPL": [0.01, 0.02, -0.01, 0.03, ...],
    "MSFT": [0.02, 0.01, 0.02, 0.04, ...],
    "GOOGL": [0.01, -0.01, 0.03, 0.02, ...]
}

optimal_weights = risk_mgr.optimize_weights(assets)
print(f"Optimized weights: {optimal_weights}")
```

### Rebalancing Recommendations

```python
# Get rebalancing recommendations
recommendations = risk_mgr.recommend_rebalance(
    portfolio,
    target_concentration=0.15
)

for symbol, change in recommendations.items():
    print(f"{symbol}: {change:+.2%}")
```

### Stress Testing

```python
# Stress test portfolio
stress_analysis = risk_mgr.stress_test(portfolio, returns)

print(f"Worst case (95%): {stress_analysis.var_95:.4f}")
print(f"Black swan (99%): {stress_analysis.var_99:.4f}")
```

---

## System Health Monitoring

### Monitor System Resources

```python
from system.health_monitor import SystemMonitor, ApplicationHealthMonitor

monitor = SystemMonitor()

# Get current metrics
metrics = monitor.get_metrics()
print(f"CPU: {metrics.cpu_percent:.1f}%")
print(f"Memory: {metrics.memory_mb:.1f}MB")
print(f"Disk: {metrics.disk_percent:.1f}%")

# Check resource health
check = monitor.check_resources(
    thresholds={
        "cpu_percent": 80,
        "memory_percent": 85,
        "disk_percent": 90,
    }
)

if check.is_healthy():
    print("✓ All resources healthy")
else:
    print(f"✗ {check.message}")
```

### Application Health Monitoring

```python
from system.health_monitor import ApplicationHealthMonitor

health_monitor = ApplicationHealthMonitor()

# Register custom health checks
async def check_database():
    # Your database health check
    from system.health_monitor import HealthCheck, HealthStatus
    # Try to connect and query
    return HealthCheck(
        name="database",
        status=HealthStatus.HEALTHY,
        message="Database connected"
    )

health_monitor.register_check("database", check_database)

# Run all checks
checks = await health_monitor.run_checks()

# Get overall health
overall = health_monitor.get_overall_health()
print(f"Overall Health: {overall.value}")

# Get report
report = health_monitor.get_report()
print(report)
```

### Diagnostics

```python
from system.health_monitor import DiagnosticsEngine

diag = DiagnosticsEngine()

# Run diagnostics
diagnostics = await diag.diagnose()

print(f"Health: {diagnostics['overall_health']}")
for issue in diagnostics['issues']:
    print(f"  - {issue['component']}: {issue['message']}")

# Get debug info
debug_info = diag.get_debug_info()
print(f"Python Version: {debug_info['python_version']}")
print(f"Memory: {debug_info['process_info']['memory_mb']:.1f}MB")
```

---

## Professional Logging

### Setup Logging

```python
from system.logging_setup import setup_logging, get_logger

# Configure logging
setup_logging(
    log_level="INFO",
    log_file="logs/app.log",
    console_enabled=True,
    file_enabled=True
)

# Get logger
logger = get_logger(__name__)

# Use logging
logger.info("Application started")
logger.debug("Debug message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### Temporary Logging Level Changes

```python
from system.logging_setup import DebugLogging, QuietLogging

logger = get_logger(__name__)

# Enable debug logging temporarily
with DebugLogging():
    logger.debug("Detailed debug info")

# Reduce logging temporarily
with QuietLogging():
    logger.debug("This won't show")
    logger.warning("This will show")
```

---

## Professional Terminal

### Setup Terminal

```python
from ui.components.terminal_professional import (
    ProfessionalTerminal,
    TerminalConfig,
    TerminalPanel
)

# Configure terminal
config = TerminalConfig(
    chart_buffer_size=500,
    update_interval_ms=500,
    max_panels=8,
    theme="dark",
    font_size=10
)

# Create terminal
terminal = ProfessionalTerminal(config=config)

# Register custom panels
class MyPanel(TerminalPanel):
    def create_widget(self):
        # Create your widget
        pass
    
    def update(self, data):
        # Update widget
        pass
    
    def on_session_changed(self, session_id):
        # Handle session change
        pass

terminal.register_panel(MyPanel("my_panel", "My Panel"))

# Set active session
terminal.set_active_session("session-123")

# Update panel
terminal.update_panel("my_panel", {"data": "value"})

# Show terminal
terminal.show()
```

### Terminal Signals

```python
# Connect to signals
terminal.signals.state_changed.connect(on_state_changed)
terminal.signals.session_changed.connect(on_session_changed)
terminal.signals.panel_updated.connect(on_panel_updated)
terminal.signals.error_occurred.connect(on_error)
```

---

## Shared Utilities

### Using Shared Utils

```python
from shared.utils import (
    safe_float,
    safe_int,
    normalized_text,
    normalize_symbol_text,
    clamp,
    format_currency,
    format_percentage,
    merge_dicts,
    get_nested,
    set_nested
)

# Safe conversions
value = safe_float("123.45", default=0.0)
count = safe_int("invalid", default=0)

# Text normalization
text = normalized_text(None, "", "Hello", "World")

# Symbol normalization
symbol = normalize_symbol_text("AAPL_USD")

# Value clamping
percentage = clamp(1.5, 0.0, 1.0)

# Formatting
price_str = format_currency(123.45)
pct_str = format_percentage(0.15)

# Dictionary operations
merged = merge_dicts({"a": 1}, {"b": 2})
value = get_nested(obj, "parent.child.value", default=0)
set_nested(d, "a.b.c", value)
```

---

## Best Practices

### 1. Always Use Lifecycle Management
```python
lifecycle = SessionLifecycleManager(session_id)
success = await lifecycle.initialize(init_func)
if not success:
    # Handle failure with proper cleanup
```

### 2. Monitor Health
```python
health = lifecycle.get_health()
if health == SessionHealth.CRITICAL:
    # Take corrective action
```

### 3. Use Shared Utils
```python
# Bad
value = float(data) if data else 0.0

# Good
value = safe_float(data, default=0.0)
```

### 4. Proper Logging
```python
# Bad
print("Error occurred")

# Good
logger.error("Error occurred", exc_info=True)
```

### 5. Configuration Management
```python
# Bad
api_key = "hardcoded_key"

# Good
config_mgr = ConfigManager('config.json')
api_key = config_mgr.get('broker.api_key')
```

---

## Troubleshooting

### Session Not Initializing
1. Check health monitor: `lifecycle.get_health()`
2. Review logs: Check `logs/app.log`
3. Verify configuration: `config_mgr.validate()`
4. Check resources: `monitor.check_resources()`

### Memory Issues
1. Get metrics: `monitor.get_metrics()`
2. Check history: `monitor.get_avg_metrics()`
3. Enable debug logging: `enable_debug()`

### UI Issues
1. Check terminal state: `terminal.get_state()`
2. Verify panels: `terminal._panels`
3. Check signals: `terminal.signals`

---

## Support

For issues or questions:
1. Check logs: `logs/app.log`
2. Run diagnostics: `diag.diagnose()`
3. Review this guide
4. Check IMPROVEMENTS.md for architecture details

---

**Last Updated**: 2026-05-05
**Version**: 2.0.0
**Status**: Production Ready
