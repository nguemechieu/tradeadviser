"""Market Classification Domain Model - Architecture & Design Documentation

================================================================================
ARCHITECTURE OVERVIEW
================================================================================

The market classification domain model provides a clean, type-safe layer for
describing and classifying tradable markets across crypto, forex, equities,
derivatives, and simulated venues. It consists of four main components:

1. ENUMS (enums.py)
   ├─ MarketType      : Broad market category (CRYPTO, FOREX, STOCK, etc.)
   ├─ InstrumentType  : Product structure (SPOT, PERPETUAL_FUTURE, OPTION, etc.)
   ├─ VenueType       : Venue type (BROKER, CENTRALIZED_EXCHANGE, etc.)
   ├─ Venue           : Specific broker/exchange/network
   ├─ AssetClass      : Portfolio grouping (CRYPTO_ASSET, EQUITY, etc.)
   ├─ TradingMode     : Execution environment (LIVE, PAPER, BACKTEST)
   ├─ SettlementType  : Settlement mechanism (CASH, CRYPTO, PERPETUAL)
   ├─ MarketDataType  : Data stream types (TICKER, QUOTE, TRADE, etc.)
   └─ MarketRoute     : Composite routing rule

2. DESCRIPTOR (descriptor.py)
   └─ MarketDescriptor : Frozen dataclass describing a tradable symbol
      ├─ symbol, base_asset, quote_asset
      ├─ market_type, instrument_type, asset_class
      ├─ venue, venue_type, settlement_type
      ├─ trading_mode, market_route
      ├─ leveraged, shortable, tradable
      └─ ~30 computed properties for decision logic

3. CLASSIFIER (classifier.py)
   └─ MarketClassifier : Deterministic symbol → MarketDescriptor mapper
      ├─ classify(symbol, venue, mode) → MarketDescriptor
      ├─ infer_market_type()
      ├─ infer_instrument_type()
      ├─ infer_asset_class()
      ├─ infer_settlement_type()
      ├─ infer_shortable()
      └─ parse_base_asset() / parse_quote_asset()

4. INTEGRATION (__init__.py)
   └─ Public API exports for downstream consumers

================================================================================
DESIGN PRINCIPLES
================================================================================

1. TYPE SAFETY
   - Full type hints throughout (Python 3.11+ compatible)
   - StrEnum for serializable string enums
   - Frozen dataclass for immutable, hashable descriptors
   - No Optional[Enum] - always use UNKNOWN variant

2. DETERMINISM
   - Same symbol + venue → always same MarketDescriptor
   - No state, no mutable globals, no randomness
   - Pure functions (no side effects)

3. OFFLINE CLASSIFICATION
   - No API calls
   - No database queries
   - No network requests
   - Only static rules and string parsing

4. SAFE DEFAULTS
   - Unknown symbols don't crash
   - Returns MarketDescriptor.unknown() instead of None
   - Graceful degradation over exceptions

5. COMPLETE METADATA
   - Every descriptor has all fields populated
   - No None values (use UNKNOWN instead)
   - Computed properties for common decision patterns

================================================================================
CORE CONCEPTS
================================================================================

MARKET TYPE (What market category is this?)
    CRYPTO         : Cryptocurrency market
    FOREX          : Foreign exchange market
    STOCK          : Individual stock
    ETF            : Exchange-traded fund
    INDEX          : Stock/commodity index
    COMMODITY      : Physical commodity (gold, oil, etc.)
    BOND           : Fixed income security
    FUTURES        : Futures contract
    OPTIONS        : Options contract
    CFD            : Contract for difference
    SYNTHETIC      : Synthetic/constructed instrument
    UNKNOWN        : Unclassifiable market

INSTRUMENT TYPE (What is the exact product structure?)
    SPOT           : Physical/cash settlement
    MARGIN_SPOT    : Spot with leverage
    FOREX_SPOT     : FX spot (no leverage indicated)
    MARGIN_FX      : FX with margin/leverage
    CFD            : Contract for difference
    STOCK          : Individual stock
    ETF            : Exchange-traded fund
    INDEX          : Index (not tradable directly, usually CFD)
    FUTURE         : Expiring futures contract
    PERPETUAL_FUT. : Perpetual (no expiry) futures
    OPTION         : Options contract
    WARRANT        : Warrant (structured derivative)
    BOND           : Bond security
    COMMODITY_SPOT : Physical commodity spot
    TOKENIZED_*    : On-chain versions of traditional assets

VENUE TYPE (What kind of execution venue?)
    CENTRALIZED_EXCHANGE : Traditional exchange (Coinbase, Binance, NYSE)
    DECENTRALIZED_EXCHANGE : DEX (Uniswap, PancakeSwap)
    BROKER             : FX/CFD/equity broker (OANDA, Alpaca, IB)
    BANK_LIQUIDITY_PROVIDER : Bank LP (rare in retail)
    ECN                : Electronic Communication Network
    BLOCKCHAIN_NETWORK : Native blockchain (Ethereum, Solana)
    OTC_DESK           : Over-the-counter desk
    CLEARING_EXCHANGE  : Futures clearing house
    SIMULATED          : Paper trading or backtest
    UNKNOWN            : Unknown venue

VENUE (Which specific execution venue?)
    COINBASE, BINANCE, KRAKEN, OKX, BYBIT, BINANCE_US
    STELLAR, ETHEREUM, SOLANA
    OANDA, FOREX_COM
    ALPACA, INTERACTIVE_BROKERS, SCHWAB
    PAPER, BACKTEST
    UNKNOWN

ASSET CLASS (Portfolio/risk grouping)
    CRYPTO_ASSET       : Cryptocurrency
    FIAT_CURRENCY      : Traditional currency
    EQUITY             : Stock/equity
    EQUITY_INDEX       : Stock index
    COMMODITY          : Commodity
    FIXED_INCOME       : Bond/debt
    DERIVATIVE         : Derivative product
    CASH               : Cash position
    SYNTHETIC          : Constructed/synthetic
    UNKNOWN            : Unknown

TRADING MODE (Execution environment)
    LIVE               : Real orders, real money
    PAPER              : Simulated orders, no money
    BACKTEST           : Historical data replay
    FORWARD_TEST       : Walk-forward testing
    SIMULATION         : Generic simulation
    SANDBOX            : Venue-provided sandbox
    
    Properties: .sends_real_orders, .is_test_mode

SETTLEMENT TYPE (How does trade settle?)
    PHYSICAL           : Physical delivery (commodities)
    CASH               : Cash settlement
    CRYPTO             : Cryptocurrency settlement
    FIAT               : Fiat currency settlement
    STABLECOIN         : Stablecoin settlement (USDT, USDC)
    PERPETUAL          : Perpetual (no settlement)
    NONE               : No settlement
    UNKNOWN            : Unknown

================================================================================
CLASSIFICATION EXAMPLES
================================================================================

Symbol: BTC-USD, Venue: COINBASE
    Market Type       : CRYPTO
    Instrument Type   : SPOT
    Venue Type        : CENTRALIZED_EXCHANGE
    Asset Class       : CRYPTO_ASSET
    Settlement Type   : CRYPTO
    Trading Mode      : LIVE
    Is Spot?          : YES
    Is Derivative?    : NO
    Shortable?        : YES (via margin)
    Market Route      : CRYPTO_SPOT_CEX

Symbol: BTC-PERP, Venue: COINBASE
    Market Type       : CRYPTO
    Instrument Type   : PERPETUAL_FUTURE
    Venue Type        : CENTRALIZED_EXCHANGE
    Asset Class       : DERIVATIVE
    Settlement Type   : PERPETUAL
    Trading Mode      : LIVE
    Is Perpetual?     : YES
    Is Derivative?    : YES
    Shortable?        : YES
    Market Route      : CRYPTO_PERPETUAL_CEX

Symbol: EUR/USD, Venue: OANDA
    Market Type       : FOREX
    Instrument Type   : MARGIN_FX
    Venue Type        : BROKER
    Asset Class       : FIAT_CURRENCY
    Settlement Type   : FIAT
    Trading Mode      : LIVE
    Is Forex?         : YES
    Is Margin?        : YES
    Shortable?        : YES
    Market Route      : FOREX_MARGIN_BROKER

Symbol: AAPL, Venue: ALPACA
    Market Type       : STOCK
    Instrument Type   : STOCK
    Venue Type        : BROKER
    Asset Class       : EQUITY
    Settlement Type   : CASH
    Trading Mode      : LIVE
    Is Stock?         : YES
    Is Derivative?    : NO
    Shortable?        : YES (via margin)
    Market Route      : STOCK_BROKER

Symbol: SPY, Venue: ALPACA
    Market Type       : ETF
    Instrument Type   : ETF
    Venue Type        : BROKER
    Asset Class       : EQUITY
    Settlement Type   : CASH
    Trading Mode      : LIVE
    Is ETF?           : YES
    Is Derivative?    : NO
    Shortable?        : YES (via margin)
    Market Route      : ETF_BROKER

Symbol: SPX500, Venue: OANDA
    Market Type       : INDEX
    Instrument Type   : CFD
    Venue Type        : BROKER
    Asset Class       : EQUITY_INDEX
    Settlement Type   : CASH
    Trading Mode      : LIVE
    Is Index?         : YES
    Is Derivative?    : YES
    Shortable?        : YES (CFD)
    Market Route      : INDEX_CFD_BROKER

Symbol: XLM/USDC, Venue: STELLAR
    Market Type       : CRYPTO
    Instrument Type   : SPOT
    Venue Type        : BLOCKCHAIN_NETWORK
    Asset Class       : CRYPTO_ASSET
    Settlement Type   : STABLECOIN
    Trading Mode      : LIVE
    Is Crypto?        : YES
    Is Blockchain?    : YES
    Needs Wallet?     : YES
    Market Route      : CRYPTO_NETWORK_SWAP

Symbol: BTC-USD, Venue: BACKTEST
    Market Type       : CRYPTO
    Instrument Type   : SPOT
    Venue Type        : SIMULATED
    Asset Class       : CRYPTO_ASSET
    Settlement Type   : CRYPTO
    Trading Mode      : BACKTEST
    Is Simulated?     : YES
    Sends Real Orders?: NO
    Market Route      : BACKTEST_ROUTE

================================================================================
USAGE PATTERNS
================================================================================

BASIC CLASSIFICATION
--------------------
from domain.market import MarketClassifier, Venue

classifier = MarketClassifier()
desc = classifier.classify("BTC-USD", Venue.COINBASE)

assert desc.is_crypto
assert desc.is_spot
assert not desc.is_derivative

ROUTER DECISION LOGIC
---------------------
if descriptor.market_type == MarketType.CRYPTO:
    if descriptor.instrument_type == InstrumentType.PERPETUAL_FUTURE:
        return crypto_perpetual_handler
    else:
        return crypto_spot_handler
elif descriptor.market_type == MarketType.FOREX:
    return forex_handler
elif descriptor.market_type == MarketType.STOCK:
    return equity_handler

RISK LIMIT ASSIGNMENT
---------------------
risk_limits = {
    AssetClass.CRYPTO_ASSET: 0.15,   # 15% max
    AssetClass.EQUITY: 0.05,         # 5% max
    AssetClass.DERIVATIVE: 0.20,     # 20% max
}
limit = risk_limits[descriptor.asset_class]

WEBSOCKET SUBSCRIPTION
----------------------
if descriptor.instrument_type == InstrumentType.PERPETUAL_FUTURE:
    subscribe_to(descriptor, MarketDataType.FUNDING_RATE)
    subscribe_to(descriptor, MarketDataType.LIQUIDATION)
else:
    subscribe_to(descriptor, MarketDataType.TRADE)

ORDER VALIDATION
----------------
if order_type == "SHORT" and not descriptor.shortable:
    raise OrderError("Short not allowed for this symbol")

if order_type == "MARGIN" and not descriptor.is_margin:
    raise OrderError("Margin not supported for this product")

SYMBOL NORMALIZATION
--------------------
# Use descriptor.symbol (already normalized)
api_call(endpoint, symbol=descriptor.symbol)

# Or normalized version for logging/DB
db.save(normalized=descriptor.normalized_symbol)

================================================================================
INTEGRATION POINTS
================================================================================

1. BROKER ROUTER
   Location: broker/router.py
   Usage: Route symbols to correct broker handler
   
   router = BrokerRouter()
   handler = router.route(descriptor)
   result = handler.execute_trade(descriptor, order)

2. RISK ENGINE
   Location: risk/risk_engine.py
   Usage: Apply risk limits and monitoring
   
   risk_manager = RiskManager()
   limit = risk_manager.get_position_limit(descriptor)
   risk_manager.validate_order(descriptor, order)

3. STRATEGY SELECTOR
   Location: strategy/selector.py
   Usage: Select appropriate strategy for market type
   
   strategies = strategy_manager.get_compatible_strategies(descriptor)
   best_strategy = strategy_selector.select(descriptor, strategies)

4. WEBSOCKET MANAGER
   Location: market_data/websocket_manager.py
   Usage: Subscribe to appropriate data streams
   
   subscriptions = data_manager.get_subscriptions(descriptor)
   ws_manager.subscribe(descriptor, subscriptions)

5. DATABASE/ORM
   Location: models/market_model.py
   Usage: Store market metadata with trades
   
   trade = Trade(
       symbol=descriptor.symbol,
       market_type=descriptor.market_type,
       normalized_symbol=descriptor.normalized_symbol,
       asset_class=descriptor.asset_class,
   )

6. API PARAMETER BUILDER
   Location: broker/api_builder.py
   Usage: Format symbol for broker API
   
   api_symbol = descriptor.symbol  # Already correct format
   params = build_order_params(descriptor, order)

================================================================================
PERFORMANCE CONSIDERATIONS
================================================================================

CLASSIFICATION TIME
- Single symbol classification: ~1-5 microseconds
- No external calls: deterministic, fast
- Can classify 100k+ symbols per second
- Safe for initialization and hot paths

MEMORY USAGE
- MarketDescriptor: ~300 bytes (frozen dataclass)
- Enum values: negligible (interned strings)
- Can cache descriptors in memory: descriptor -> data

CACHING STRATEGY
- Cache frequent classifications
- Use symbol + venue as cache key
- Invalidation: never (deterministic)

cache = {}
key = (symbol, venue)
if key not in cache:
    cache[key] = classifier.classify(symbol, venue)
return cache[key]

================================================================================
EXTENDING THE MODEL
================================================================================

ADDING A NEW MARKET TYPE
1. Add enum value to MarketType
2. Update MarketType properties if needed
3. Update MarketClassifier.infer_market_type()
4. Add example in EXAMPLES.py
5. Update this documentation

ADDING A NEW VENUE
1. Add enum value to Venue
2. Add metadata to Venue._METADATA dict
3. Update MarketClassifier if special logic needed
4. Test classification for all markets on this venue

ADDING A NEW TRADING MODE
1. Add enum value to TradingMode
2. Update TradingMode properties
3. Update MarketClassifier if needed
4. Update routing rules for new mode

================================================================================
TESTING & VALIDATION
================================================================================

The classifier includes:
- 50+ example classification cases
- Type safety throughout
- Unknown symbol fallback
- Deterministic output
- No external dependencies

Test coverage should include:
- Each market type on each venue type
- Symbol normalization for each venue
- Perpetual vs expiring instruments
- Margin vs spot products
- Shortable vs non-shortable symbols
- Paper/backtest modes
- Unknown symbols
- Symbol variations (BTC-USD, BTC/USD, BTCUSD)

================================================================================
BEST PRACTICES
================================================================================

1. ALWAYS USE CLASSIFIER FOR NEW CLASSIFICATIONS
   - Don't manually construct MarketDescriptor
   - Classifier handles all edge cases
   - Ensures consistency

2. USE DESCRIPTOR PROPERTIES FOR DECISIONS
   - Use .is_crypto instead of checking enum directly
   - Use .is_derivative, .is_perpetual, etc.
   - Properties are the public API

3. SAFE HANDLING OF UNKNOWN
   - Check .tradable before using descriptor
   - Don't assume market_type != UNKNOWN
   - Handle gracefully with fallback strategies

4. CACHE DESCRIPTORS WHEN POSSIBLE
   - Classification is deterministic
   - Safe to cache indefinitely
   - (symbol, venue) -> descriptor mapping

5. USE APPROPRIATE MARKET ROUTE
   - Rely on .market_route for routing decisions
   - Don't hard-code venue logic
   - Allows new venues/markets without code changes

6. SERIALIZE VENUE PROPERLY
   - Use Venue enum (not string)
   - Serializes as string automatically
   - Deserialize carefully in load/restore

================================================================================
DEPENDENCIES & COMPATIBILITY
================================================================================

PYTHON VERSION
- Requires Python 3.11+ (for StrEnum)
- No external dependencies
- Pure standard library enums/dataclasses

COMPATIBILITY
- Frozen dataclass compatible with JSON serialization
- Enum string values for database storage
- No pickle-specific features (safe for distributed systems)

================================================================================
"""
