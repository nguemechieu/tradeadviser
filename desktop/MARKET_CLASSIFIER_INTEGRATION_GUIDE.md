"""Market Classification System - Complete Integration Guide

This guide shows how to integrate the market classification system with all
platform components (broker router, risk engine, WebSocket manager, order
validation) to enable deterministic, type-safe multi-asset trading.

================================================================================
PROJECT OVERVIEW
================================================================================

The market classification system consists of:

1. CORE DOMAIN MODEL (domain/market/)
   - enums.py: 9 enum types (MarketType, InstrumentType, Venue, etc.)
   - descriptor.py: Frozen dataclass with 25+ computed properties
   - classifier.py: Deterministic symbol classification engine
   - README.md, QUICK_REFERENCE.md: Complete documentation

2. INTEGRATION MODULES
   - broker/market_classifier_integration.py: BrokerRouter class
   - risk/market_classifier_integration.py: RiskEngineLimits class
   - market_data/market_classifier_integration.py: WebSocketDataManager class
   - execution/market_classifier_integration.py: OrderValidator class

3. UI COMPONENTS
   - ui/components/panels/venue_panel.py: Professional venue monitoring
   - ui/components/terminal.py: Terminal integration
   - ui/components/panels/system_panels.py: Panel creation factory

================================================================================
QUICK START
================================================================================

1. CLASSIFY A SYMBOL
====================

from domain.market import MarketClassifier, Venue

classifier = MarketClassifier()
descriptor = classifier.classify("BTC-USD", Venue.COINBASE)

print(descriptor.symbol)              # "BTC-USD"
print(descriptor.market_type)         # MarketType.CRYPTO
print(descriptor.instrument_type)     # InstrumentType.SPOT
print(descriptor.asset_class)         # AssetClass.CRYPTO_ASSET
print(descriptor.is_crypto)           # True
print(descriptor.shortable)           # True
print(descriptor.display_symbol)      # "BTC-USD @ Coinbase"

2. ROUTE TO BROKER
==================

from broker.market_classifier_integration import BrokerRouter

router = BrokerRouter()
router.register_handler(MarketRoute.CRYPTO_SPOT_CEX, crypto_spot_handler)
router.register_venue_handler(Venue.COINBASE, coinbase_handler)

handler = router.route("BTC-USD", Venue.COINBASE)
await handler.execute_trade(symbol, order)

3. APPLY RISK LIMITS
====================

from risk.market_classifier_integration import RiskEngineLimits

risk_engine = RiskEngineLimits()
risk_engine.set_portfolio_value(100_000)

descriptor = classifier.classify("BTC-USD", Venue.COINBASE)
max_position = risk_engine.get_max_position_size(descriptor)
max_quantity = risk_engine.get_max_position_quantity(descriptor, entry_price=45000)

is_valid, error = risk_engine.validate_order(descriptor, quantity=0.5, entry_price=45000)

4. SUBSCRIBE TO DATA
====================

from market_data.market_classifier_integration import WebSocketDataManager

ws_manager = WebSocketDataManager()
subscriptions = ws_manager.subscribe_to_symbol("BTC-USD", Venue.COINBASE)

# Subscriptions automatically selected per instrument type:
# SPOT: TICKER, QUOTE, TRADE, ORDER_BOOK
# PERPETUAL: TICKER, QUOTE, TRADE, ORDER_BOOK, FUNDING_RATE, LIQUIDATION
# FOREX: QUOTE, CANDLE, TRADE

for sub in subscriptions:
    print(f"Subscribed to {sub.data_type.value} for {sub.symbol}")

5. VALIDATE ORDERS
==================

from execution.market_classifier_integration import OrderValidator, Order

validator = OrderValidator()
order = Order("BTC-USD", Venue.COINBASE, 0.5, 45000, "BUY", "LIMIT")

validator.validate(order)  # Raises OrderValidationError if invalid

# Or get detailed report
report = validator.validate_with_report(order)
if report.is_valid:
    print("Order is valid!")
else:
    print(f"Errors: {report.errors}")
    print(f"Recommendations: {report.recommendations}")

================================================================================
INTEGRATION PATTERN: END-TO-END TRADING WORKFLOW
================================================================================

Here's a complete example of trading with all components:

from domain.market import (
    MarketClassifier, Venue, TradingMode,
    AssetClass, MarketRoute
)
from broker.market_classifier_integration import BrokerRouter
from risk.market_classifier_integration import RiskEngineLimits
from market_data.market_classifier_integration import WebSocketDataManager
from execution.market_classifier_integration import (
    OrderValidator, Order
)


async def execute_trade(symbol: str, venue: Venue, quantity: float, price: float):
    \"\"\"Execute a trade with full validation and management.\"\"\"
    
    # Step 1: Classify the symbol
    classifier = MarketClassifier()
    descriptor = classifier.classify(symbol, venue)
    
    if not descriptor.tradable:
        raise ValueError(f"{symbol} is not tradable")
    
    print(f"Classification: {descriptor.display_symbol}")
    print(f"  Market Type: {descriptor.market_type.value}")
    print(f"  Asset Class: {descriptor.asset_class.value}")
    print(f"  Settlement: {descriptor.settlement_type.value}")
    
    # Step 2: Check risk limits
    risk_engine = RiskEngineLimits()
    risk_engine.set_portfolio_value(100_000)
    
    max_qty = risk_engine.get_max_position_quantity(descriptor, price)
    if quantity > max_qty:
        raise ValueError(f"Order size {quantity} exceeds max {max_qty:.4f}")
    
    risk_metrics = risk_engine.get_risk_metrics(descriptor)
    print(f"Risk Metrics: {risk_metrics}")
    
    # Step 3: Subscribe to market data
    ws_manager = WebSocketDataManager()
    subscriptions = ws_manager.subscribe_to_symbol(symbol, venue)
    print(f"Subscribed to {len(subscriptions)} data streams")
    
    # Step 4: Validate order
    validator = OrderValidator()
    order = Order(
        symbol=symbol,
        venue=venue,
        quantity=quantity,
        price=price,
        side="BUY",
        order_type="LIMIT",
    )
    
    report = validator.validate_with_report(order)
    if not report.is_valid:
        raise ValueError(f"Order validation failed: {report.errors}")
    
    print(f"Order validation: {len(report.recommendations)} recommendations")
    
    # Step 5: Route to broker
    router = BrokerRouter()
    handler = router.route(symbol, venue)
    
    if not handler:
        raise ValueError(f"No handler available for {symbol} on {venue.value}")
    
    print(f"Routed to {handler.__class__.__name__}")
    
    # Step 6: Execute trade
    try:
        result = await handler.execute_trade(order)
        print(f"Trade executed: {result}")
        return result
    except Exception as e:
        print(f"Trade failed: {e}")
        raise


# Usage
await execute_trade("BTC-USD", Venue.COINBASE, 0.5, 45000)

================================================================================
BROKER ROUTER USAGE
================================================================================

BASIC ROUTING
=============

from broker.market_classifier_integration import BrokerRouter
from domain.market import MarketRoute, Venue

router = BrokerRouter()

# Register handlers by market route
router.register_handler(MarketRoute.CRYPTO_SPOT_CEX, crypto_handler)
router.register_handler(MarketRoute.FOREX_MARGIN_BROKER, forex_handler)
router.register_handler(MarketRoute.STOCK_BROKER, equity_handler)

# Route a symbol
handler = router.route("BTC-USD", Venue.COINBASE)
# Routes via CRYPTO_SPOT_CEX → crypto_handler

handler = router.route("EUR/USD", Venue.OANDA)
# Routes via FOREX_MARGIN_BROKER → forex_handler

handler = router.route("AAPL", Venue.ALPACA)
# Routes via STOCK_BROKER → equity_handler


VENUE-SPECIFIC HANDLING
=======================

# Register venue-specific handlers
router.register_venue_handler(Venue.COINBASE, coinbase_handler)
router.register_venue_handler(Venue.ALPACA, alpaca_handler)

# This takes precedence when no market route handler exists
handler = router.route("UNKNOWN", Venue.COINBASE)
# Routes to coinbase_handler (venue handler)


QUALITY-BASED ROUTING
=======================

from broker.market_classifier_integration import MultiVenueRouter

multi_router = MultiVenueRouter()
multi_router.register_venue_handler(Venue.COINBASE, coinbase_handler)
multi_router.register_venue_handler(Venue.BINANCE, binance_handler)

# Set quality metrics
multi_router.set_venue_quality_metrics(Venue.COINBASE, {
    "latency_ms": 45,
    "maker_fee": 0.0004,
    "taker_fee": 0.0006,
    "rebate_pct": 0.0001,
})

multi_router.set_venue_quality_metrics(Venue.BINANCE, {
    "latency_ms": 78,
    "maker_fee": 0.0001,
    "taker_fee": 0.0002,
    "rebate_pct": 0.00005,
})

# Route to best-quality venue
handler = multi_router.route_by_quality("BTC-USD", MarketType.CRYPTO)
# Selects best based on latency + fees - rebates

================================================================================
RISK ENGINE USAGE
================================================================================

ASSET CLASS LIMITS
==================

from risk.market_classifier_integration import RiskEngineLimits, RiskLimits
from domain.market import AssetClass

risk_engine = RiskEngineLimits()
risk_engine.set_portfolio_value(100_000)

# Customize limits for crypto (15% per position, 40% total exposure)
custom_limits = RiskLimits(
    max_position_size_pct=0.15,
    max_asset_class_exposure_pct=0.40,
    max_gross_exposure_pct=1.50,
    max_leverage=3.0,
    daily_loss_limit_pct=0.10,
)
risk_engine.set_asset_class_limits(AssetClass.CRYPTO_ASSET, custom_limits)

# Get limits for a classified symbol
descriptor = classifier.classify("BTC-USD", Venue.COINBASE)
limits = risk_engine.get_limits_for_descriptor(descriptor)
print(f"Max leverage: {limits.max_leverage}x")


POSITION SIZING
===============

# Calculate max position value
max_position_value = risk_engine.get_max_position_size(descriptor)
print(f"Max position: ${max_position_value:,.2f}")

# Calculate max quantity at a specific price
max_qty = risk_engine.get_max_position_quantity(descriptor, entry_price=45000)
print(f"Can buy up to {max_qty:.4f} BTC at $45,000")


ORDER VALIDATION
================

# Validate single order
is_valid, error = risk_engine.validate_order(
    descriptor,
    quantity=0.5,
    entry_price=45000,
    order_type="LIMIT",
)

if not is_valid:
    print(f"Order invalid: {error}")


RISK METRICS
============

# Get comprehensive risk metrics
metrics = risk_engine.get_risk_metrics(descriptor)
print(f"Asset class: {metrics['asset_class']}")
print(f"Max position: ${metrics['max_position_value']:,.2f}")
print(f"Max leverage: {metrics['max_leverage']}x")
print(f"Daily loss limit: ${metrics['daily_loss_limit_value']:,.2f}")

================================================================================
WEBSOCKET DATA MANAGER USAGE
================================================================================

SUBSCRIPTION MANAGEMENT
=======================

from market_data.market_classifier_integration import WebSocketDataManager
from domain.market import MarketDataType, StreamPriority

ws_manager = WebSocketDataManager()

# Subscribe to a symbol - automatically selects data streams per type
subscriptions = ws_manager.subscribe_to_symbol("BTC-USD", Venue.COINBASE)
# Auto-subscribed to: TICKER, QUOTE, TRADE, ORDER_BOOK (for spot)

subscriptions = ws_manager.subscribe_to_symbol("BTC-PERP", Venue.COINBASE)
# Auto-subscribed to: TICKER, QUOTE, TRADE, ORDER_BOOK, FUNDING_RATE, LIQUIDATION

# Get subscription details
subs = ws_manager.get_subscriptions_for_symbol("BTC-USD")
for sub in subs:
    print(f"  {sub.data_type.value} (Priority: {sub.priority.value})")


BANDWIDTH MANAGEMENT
====================

# Set bandwidth limit
ws_manager.handle_bandwidth_constraint(available_mbps=10.0)
# Automatically drops low-priority subscriptions

# Get status for a venue
status = ws_manager.get_venue_status(Venue.COINBASE)
print(f"Coinbase: {status['total_subscriptions']} subscriptions, "
      f"{status['bandwidth_usage_mbps']:.2f} Mbps")


CUSTOM SUBSCRIPTIONS
====================

from market_data.market_classifier_integration import DataStreamSubscription

# Create custom subscription
sub = DataStreamSubscription(
    "BTC-USD",
    MarketDataType.CANDLE,
    priority=StreamPriority.HIGH,
    interval=60.0,  # 1-minute candles
)

# Or manually select subscriptions
subs = [
    DataStreamSubscription("BTC-USD", MarketDataType.QUOTE),
    DataStreamSubscription("BTC-USD", MarketDataType.TRADE),
    DataStreamSubscription("BTC-USD", MarketDataType.FUNDING_RATE),
]

================================================================================
ORDER VALIDATION USAGE
================================================================================

ORDER VALIDATION WITH REPORT
============================

from execution.market_classifier_integration import OrderValidator, Order

validator = OrderValidator()

# Create order
order = Order(
    symbol="BTC-USD",
    venue=Venue.COINBASE,
    quantity=0.5,
    price=45000,
    side="BUY",
    order_type="LIMIT",
    time_in_force="GTC",
)

# Get detailed validation report
report = validator.validate_with_report(order)

print(f"Valid: {report.is_valid}")
print(f"Errors: {report.errors}")
print(f"Recommendations: {report.recommendations}")

# Market type is available via descriptor
if report.descriptor:
    print(f"Market: {report.descriptor.market_type.value}")


VALIDATION WITHOUT EXCEPTION
=============================

# Validate and continue on error
try:
    validator.validate(order)
    print("Order is valid")
except OrderValidationError as e:
    print(f"Order invalid: {e}")


CUSTOMIZING VALIDATION RULES
============================

# Extend OrderValidator for custom rules
class CustomOrderValidator(OrderValidator):
    def _validate_against_descriptor(self, order, descriptor):
        super()._validate_against_descriptor(order, descriptor)
        
        # Add custom rule: disallow large crypto orders at market price
        if descriptor.is_crypto and order.order_type == "MARKET":
            if order.quantity > 1.0:
                raise OrderValidationError("Large market orders use limit orders only")

================================================================================
VENUE PANEL INTEGRATION
================================================================================

The venue panel is already integrated into terminal.py:

1. Terminal initialization calls _setup_panels()
2. _setup_panels() includes _create_venue_panel()
3. Venue panel displays:
   - Overall connection status
   - Connected venue count
   - Average latency
   - 24h trading volume
   - Per-venue metrics table with color-coded status indicators

ACCESS IN CODE
==============

# From within Terminal class:
self.venue_panel_dock          # QDockWidget reference
self.venue_overall_status      # Overall status indicator
self.venue_table               # Main table widget
self.venue_connected_count     # Connected venues label

# Update venue panel data
from ui.components.panels.venue_panel import update_venue_panel, VenueConnectionStatus

venues = {
    "Coinbase": VenueConnectionStatus("Coinbase", "Crypto", "healthy"),
    "Alpaca": VenueConnectionStatus("Alpaca", "US Equities", "healthy"),
}

venues["Coinbase"].latency_ms = 45
venues["Coinbase"].connections = 5
venues["Coinbase"].uptime_pct = 99.98
venues["Coinbase"].volume_24h = 5_200_000_000

update_venue_panel(terminal, venues)

================================================================================
COMPLETE END-TO-END EXAMPLE
================================================================================

Here's a complete trading system initialization:

import asyncio
from domain.market import MarketClassifier, Venue, MarketRoute
from broker.market_classifier_integration import BrokerRouter
from risk.market_classifier_integration import RiskEngineLimits
from market_data.market_classifier_integration import WebSocketDataManager
from execution.market_classifier_integration import OrderValidator


class TradingSystem:
    def __init__(self, portfolio_value: float = 100_000):
        self.classifier = MarketClassifier()
        
        self.router = BrokerRouter()
        self.risk_engine = RiskEngineLimits()
        self.risk_engine.set_portfolio_value(portfolio_value)
        
        self.ws_manager = WebSocketDataManager()
        self.validator = OrderValidator()
    
    def classify_symbol(self, symbol: str, venue: Venue):
        return self.classifier.classify(symbol, venue)
    
    def get_best_handler(self, symbol: str, venue: Venue):
        return self.router.route(symbol, venue)
    
    def check_position_size(self, symbol: str, venue: Venue, quantity: float, price: float):
        descriptor = self.classify_symbol(symbol, venue)
        max_qty = self.risk_engine.get_max_position_quantity(descriptor, price)
        return quantity <= max_qty, max_qty
    
    def subscribe_to_market_data(self, symbol: str, venue: Venue):
        return self.ws_manager.subscribe_to_symbol(symbol, venue)
    
    async def execute_trade(self, symbol: str, venue: Venue, quantity: float, price: float):
        # Classify
        descriptor = self.classify_symbol(symbol, venue)
        
        # Check risk
        is_valid_size, max_qty = self.check_position_size(symbol, venue, quantity, price)
        if not is_valid_size:
            raise ValueError(f"Quantity {quantity} exceeds max {max_qty}")
        
        # Validate order
        from execution.market_classifier_integration import Order
        order = Order(symbol, venue, quantity, price, "BUY", "LIMIT")
        self.validator.validate(order)
        
        # Subscribe to data
        self.subscribe_to_market_data(symbol, venue)
        
        # Execute
        handler = self.get_best_handler(symbol, venue)
        return await handler.execute_trade(order)


# Usage
system = TradingSystem()
await system.execute_trade("BTC-USD", Venue.COINBASE, 0.5, 45000)

================================================================================
DEPLOYMENT CHECKLIST
================================================================================

✓ Copy domain/market/ to src/domain/
✓ Copy market_classifier_integration.py to broker/
✓ Copy market_classifier_integration.py to risk/
✓ Copy market_classifier_integration.py to market_data/
✓ Copy market_classifier_integration.py to execution/
✓ Register all broker handlers in BrokerRouter
✓ Set portfolio value in RiskEngineLimits
✓ Configure venue quality metrics in MultiVenueRouter
✓ Subscribe to initial symbols in WebSocketDataManager
✓ Test order validation with sample orders
✓ Verify venue panel displays correctly
✓ Test end-to-end trading workflow
✓ Monitor risk metrics in production
✓ Set up logging/alerting for validation errors

================================================================================
PERFORMANCE CONSIDERATIONS
================================================================================

CLASSIFICATION PERFORMANCE
- Single classification: ~1-5 microseconds
- Can classify 100k+ symbols per second
- Safe for initialization and hot paths
- Cache results for frequently-classified symbols

ROUTER PERFORMANCE
- Route lookup: O(1) via dict
- Cached after first lookup
- Clear cache when registering new handlers

RISK ENGINE PERFORMANCE
- Position size calculation: < 1 microsecond
- Validation checks: < 10 microseconds
- Risk metrics compilation: < 100 microseconds

WEBSOCKET MANAGER PERFORMANCE
- Subscribe: O(1) per symbol
- Bandwidth calculation: O(n) where n = subscription count
- Query subscriptions: O(1) per symbol

================================================================================
TROUBLESHOOTING
================================================================================

Q: Symbol classified as UNKNOWN
A: Likely unmapped symbol. Check symbol format for venue and add to classifier
   if needed. MarketDescriptor.unknown() provides safe fallback.

Q: Order validation failing unexpectedly
A: Check order.side/order_type are uppercase. Review validation report for
   specific errors. Check descriptor.tradable.

Q: No handler available after routing
A: Register handlers for market routes or venues. Set fallback handler.
   Check that route is correct for symbol.

Q: WebSocket subscriptions not working
A: Verify venue and symbol are correct. Check bandwidth constraints. Verify
   venue supports subscription data type.

Q: Venue panel not showing
A: Check venue panel dock is visible (dock.show()). Update with valid venue
   data. Check terminal is properly initialized.

================================================================================
"""
