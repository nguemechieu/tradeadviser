"""Quick Reference Card for Market Classification System

This is a one-page cheat sheet for the most common operations.
See README.md for full documentation.

================================================================================
IMPORTS
================================================================================

from domain.market import (
    MarketClassifier,
    MarketDescriptor,
    MarketType,
    InstrumentType,
    Venue,
    VenueType,
    AssetClass,
    TradingMode,
    SettlementType,
    MarketRoute,
)

================================================================================
CLASSIFY A SYMBOL (MAIN OPERATION)
================================================================================

classifier = MarketClassifier()
desc = classifier.classify("BTC-USD", Venue.COINBASE)

# Now you have a complete MarketDescriptor with all information needed

================================================================================
MAKE DECISIONS USING PROPERTIES
================================================================================

# Type checks
if desc.is_crypto:
    # Market is cryptocurrency
    
if desc.is_derivative:
    # Market is derivative (perpetual, option, future, CFD)
    
if desc.is_perpetual:
    # Market is perpetual future (no expiry)
    
if desc.is_margin:
    # Trading with leverage is available

if desc.is_blockchain_native:
    # Needs wallet/keys, not traditional API

# Operational checks
if not desc.shortable:
    raise Error("Can't short this symbol")
    
if not desc.tradable:
    raise Error("Symbol not tradable")

if desc.requires_wallet_secret:
    # Need private key/seed, not just API key

# Portfolio checks
if desc.asset_class == AssetClass.CRYPTO_ASSET:
    position_limit = 0.15  # 15% max
elif desc.asset_class == AssetClass.EQUITY:
    position_limit = 0.05  # 5% max
else:
    position_limit = 0.10  # default

================================================================================
ROUTING DECISIONS
================================================================================

# Option 1: Use market_route (recommended)
route = desc.market_route
handler = route_handlers[route]

# Option 2: Use market type
if desc.market_type == MarketType.CRYPTO:
    handler = crypto_handler
elif desc.market_type == MarketType.FOREX:
    handler = forex_handler

# Option 3: Use specific properties
if desc.is_crypto and desc.is_perpetual:
    handler = crypto_perpetual_handler
elif desc.is_crypto and desc.is_spot:
    handler = crypto_spot_handler

================================================================================
WEBSOCKET SUBSCRIPTIONS
================================================================================

from domain.market import MarketDataType

if desc.instrument_type == InstrumentType.PERPETUAL_FUTURE:
    subscribe_to(descriptor, [
        MarketDataType.TICKER,
        MarketDataType.FUNDING_RATE,
        MarketDataType.LIQUIDATION,
    ])
elif desc.is_forex:
    subscribe_to(descriptor, [
        MarketDataType.QUOTE,
        MarketDataType.CANDLE,
    ])
else:
    subscribe_to(descriptor, [
        MarketDataType.TRADE,
        MarketDataType.ORDER_BOOK,
    ])

================================================================================
VENUE INFORMATION
================================================================================

print(desc.venue)           # Venue.COINBASE
print(desc.venue_type)      # VenueType.CENTRALIZED_EXCHANGE
print(desc.symbol)          # "BTC-USD" (normalized)
print(desc.display_symbol)  # "BTC-USD @ Coinbase"

# Venue metadata
if desc.venue.is_broker:
    # Traditional broker interface
    
if desc.venue.is_centralized_exchange:
    # CEX interface (REST + WebSocket)

if desc.venue.is_blockchain_network:
    # Blockchain network (needs wallet)

================================================================================
HANDLING UNKNOWN SYMBOLS
================================================================================

desc = classifier.classify("UNKNOWNSYMBOL", Venue.COINBASE)

if not desc.tradable:
    # This is the safe way to detect unknowns
    logger.warn(f"Symbol {desc.symbol} is not tradable")
    # Use fallback strategy
else:
    # Process normally
    execute_trade(desc)

# Safe constructor for truly unknown symbols
unknown_desc = MarketDescriptor.unknown("WEIRDXYZ")

================================================================================
SYMBOL NORMALIZATION
================================================================================

# Automatic: descriptor.symbol is already normalized for venue
print(desc.symbol)  # "BTC-USD" (correct format for this venue)

# Manual normalization if needed
normalized = classifier.normalize_symbol("BTC/USD", Venue.BINANCE)
# Returns "BTC-USD" (Binance format)

================================================================================
SETTLEMENT & ASSET CLASSES
================================================================================

# Settlement type tells you how position settles
if desc.settlement_type == SettlementType.PERPETUAL:
    # No physical settlement, only mark price
    
if desc.settlement_type == SettlementType.CRYPTO:
    # Settled in cryptocurrency
    
if desc.settlement_type == SettlementType.CASH:
    # Cash settlement (traditional)

# Asset class for portfolio grouping
if desc.asset_class == AssetClass.CRYPTO_ASSET:
    # Treat as alternative asset
elif desc.asset_class == AssetClass.EQUITY:
    # Treat as traditional equity

================================================================================
COMMON PATTERNS
================================================================================

PATTERN: Router
================

route = desc.market_route
handler = route_handlers[route]
result = handler.execute(desc, order)

PATTERN: Risk Limits
====================

limit = risk_limits[desc.asset_class]
if position_size > limit * portfolio_value:
    raise RiskError("Position too large")

PATTERN: Data Subscriptions
===========================

subscriptions = get_subscriptions(desc.instrument_type)
for sub in subscriptions:
    ws.subscribe(descriptor, sub)

PATTERN: Order Validation
==========================

if order.side == "SHORT" and not desc.shortable:
    raise OrderError("Can't short")

PATTERN: Display
================

print(f"{desc.display_symbol}: {desc.market_type}")

PATTERN: Database Storage
==========================

db_record = {
    "symbol": desc.symbol,
    "market_type": desc.market_type.value,
    "asset_class": desc.asset_class.value,
    "normalized_symbol": desc.normalized_symbol,
}

================================================================================
ENUM VALUES (QUICK LOOKUP)
================================================================================

MarketType:
    CRYPTO, FOREX, STOCK, ETF, INDEX, COMMODITY, BOND,
    FUTURES, OPTIONS, CFD, SYNTHETIC, UNKNOWN

InstrumentType:
    SPOT, MARGIN_SPOT, FOREX_SPOT, MARGIN_FX, CFD,
    STOCK, ETF, INDEX, FUTURE, PERPETUAL_FUTURE,
    OPTION, WARRANT, BOND, COMMODITY_SPOT, SYNTHETIC, UNKNOWN

Venue:
    COINBASE, BINANCE, BINANCE_US, KRAKEN, BYBIT, OKX,
    STELLAR, ETHEREUM, SOLANA,
    OANDA, FOREX_COM,
    ALPACA, INTERACTIVE_BROKERS, SCHWAB,
    PAPER, BACKTEST, UNKNOWN

TradingMode:
    LIVE, PAPER, BACKTEST, FORWARD_TEST, SIMULATION, SANDBOX

AssetClass:
    CRYPTO_ASSET, FIAT_CURRENCY, EQUITY, EQUITY_INDEX,
    COMMODITY, FIXED_INCOME, DERIVATIVE, CASH, SYNTHETIC, UNKNOWN

MarketRoute:
    CRYPTO_SPOT_CEX, CRYPTO_SPOT_DEX, CRYPTO_PERPETUAL_CEX,
    CRYPTO_PERPETUAL_DEX, CRYPTO_NETWORK_SWAP,
    FOREX_MARGIN_BROKER,
    STOCK_BROKER, STOCK_MARGIN_BROKER, ETF_BROKER,
    INDEX_CFD_BROKER,
    FUTURES_EXCHANGE,
    OPTIONS_BROKER,
    COMMODITY_CFD_BROKER,
    PAPER_ROUTE, BACKTEST_ROUTE, UNKNOWN_ROUTE

================================================================================
COMPLETE EXAMPLE
================================================================================

from domain.market import MarketClassifier, Venue, AssetClass

classifier = MarketClassifier()

# Classify symbol
desc = classifier.classify("BTC-USD", Venue.COINBASE)

# Extract key info
print(f"Symbol: {desc.display_symbol}")
print(f"Type: {desc.market_type}")
print(f"Venue: {desc.venue}")
print(f"Route: {desc.market_route}")

# Make decisions
risk_limits = {
    AssetClass.CRYPTO_ASSET: 0.15,
    AssetClass.EQUITY: 0.05,
}

portfolio_value = 100000
max_position = risk_limits[desc.asset_class] * portfolio_value
print(f"Max position: ${max_position:,.2f}")

# Use properties
if desc.is_perpetual:
    subscribe_to_funding_rates(desc)
elif desc.is_spot:
    subscribe_to_order_book(desc)

if not desc.shortable:
    print(f"Warning: Can't short {desc.symbol}")

================================================================================
PERFORMANCE TIPS
================================================================================

1. Cache classifier instance
   classifier = MarketClassifier()  # Create once
   desc = classifier.classify(...)  # Reuse many times

2. Cache results by (symbol, venue)
   cache[(symbol, venue)] = classifier.classify(symbol, venue)

3. Use properties instead of re-checking enums
   # Good: if desc.is_crypto
   # Bad:  if desc.market_type == MarketType.CRYPTO

4. All operations are fast (<5µs)
   Safe for hot paths and initialization

================================================================================
"""
