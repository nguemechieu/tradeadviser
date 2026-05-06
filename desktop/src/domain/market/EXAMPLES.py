"""Market Classification Domain Model - Usage Examples & Integration Guide

This document provides comprehensive examples and integration guidance for the
market classification domain model in a multi-asset trading platform.

================================================================================
QUICK START - Basic Classification Examples
================================================================================
"""

from domain.market import (
    MarketClassifier,
    MarketDescriptor,
    Venue,
    MarketType,
    InstrumentType,
    VenueType,
    TradingMode,
)


def example_basic_classification():
    """Example 1: Basic symbol classification."""
    classifier = MarketClassifier()
    
    # Classify BTC-USD on Coinbase (crypto spot exchange)
    btc_usd = classifier.classify("BTC-USD", Venue.COINBASE)
    
    print("=== BTC-USD on Coinbase ===")
    print(f"Symbol: {btc_usd.symbol}")
    print(f"Market Type: {btc_usd.market_type}")
    print(f"Instrument Type: {btc_usd.instrument_type}")
    print(f"Venue: {btc_usd.venue.display_name}")
    print(f"Venue Type: {btc_usd.venue_type}")
    print(f"Asset Class: {btc_usd.asset_class}")
    print(f"Settlement Type: {btc_usd.settlement_type}")
    print(f"Tradable: {btc_usd.tradable}")
    print(f"Is Crypto: {btc_usd.is_crypto}")
    print(f"Is Spot: {btc_usd.is_spot}")
    print(f"Is Derivative: {btc_usd.is_derivative}")
    print(f"Is Perpetual: {btc_usd.is_perpetual}")
    
    assert btc_usd.market_type == MarketType.CRYPTO
    assert btc_usd.instrument_type == InstrumentType.SPOT
    assert btc_usd.venue_type == VenueType.CENTRALIZED_EXCHANGE
    assert btc_usd.is_crypto
    assert not btc_usd.is_derivative
    print("✓ All assertions passed\n")


def example_forex_classification():
    """Example 2: Forex pair on broker."""
    classifier = MarketClassifier()
    
    # Classify EUR/USD on OANDA (forex margin broker)
    eur_usd = classifier.classify("EUR/USD", Venue.OANDA)
    
    print("=== EUR/USD on OANDA ===")
    print(f"Symbol: {eur_usd.symbol}")
    print(f"Base Asset: {eur_usd.base_asset}")
    print(f"Quote Asset: {eur_usd.quote_asset}")
    print(f"Market Type: {eur_usd.market_type}")
    print(f"Instrument Type: {eur_usd.instrument_type}")
    print(f"Is Forex: {eur_usd.is_forex}")
    print(f"Is Margin: {eur_usd.is_margin}")
    print(f"Shortable: {eur_usd.shortable}")
    print(f"Venue Type: {eur_usd.venue_type}")
    
    assert eur_usd.market_type == MarketType.FOREX
    assert eur_usd.base_asset == "EUR"
    assert eur_usd.quote_asset == "USD"
    assert eur_usd.is_forex
    assert eur_usd.shortable
    print("✓ All assertions passed\n")


def example_stock_classification():
    """Example 3: Stock on equity broker."""
    classifier = MarketClassifier()
    
    # Classify AAPL on Alpaca (stock broker)
    aapl = classifier.classify("AAPL", Venue.ALPACA)
    
    print("=== AAPL on Alpaca ===")
    print(f"Symbol: {aapl.symbol}")
    print(f"Market Type: {aapl.market_type}")
    print(f"Instrument Type: {aapl.instrument_type}")
    print(f"Is Stock: {aapl.is_stock}")
    print(f"Venue: {aapl.venue.display_name}")
    print(f"Venue Type: {aapl.venue_type}")
    print(f"Tradable: {aapl.tradable}")
    
    assert aapl.market_type == MarketType.STOCK
    assert aapl.instrument_type == InstrumentType.STOCK
    assert aapl.is_stock
    assert aapl.venue.is_broker
    print("✓ All assertions passed\n")


def example_perpetual_classification():
    """Example 4: Perpetual futures on crypto exchange."""
    classifier = MarketClassifier()
    
    # Classify BTC-PERP on Coinbase (perpetual future)
    btc_perp = classifier.classify("BTC-PERP", Venue.COINBASE)
    
    print("=== BTC-PERP on Coinbase ===")
    print(f"Symbol: {btc_perp.symbol}")
    print(f"Market Type: {btc_perp.market_type}")
    print(f"Instrument Type: {btc_perp.instrument_type}")
    print(f"Is Perpetual: {btc_perp.is_perpetual}")
    print(f"Is Derivative: {btc_perp.is_derivative}")
    print(f"Settlement Type: {btc_perp.settlement_type}")
    print(f"Shortable: {btc_perp.shortable}")
    print(f"Leveraged: {btc_perp.leveraged}")
    
    assert btc_perp.market_type == MarketType.CRYPTO
    assert btc_perp.instrument_type == InstrumentType.PERPETUAL_FUTURE
    assert btc_perp.is_perpetual
    assert btc_perp.is_derivative
    assert btc_perp.shortable
    print("✓ All assertions passed\n")


def example_eth_stellar():
    """Example 5: Crypto on blockchain network (Stellar)."""
    classifier = MarketClassifier()
    
    # Classify XLM/USDC on Stellar (blockchain network swap)
    xlm_usdc = classifier.classify("XLM/USDC", Venue.STELLAR)
    
    print("=== XLM/USDC on Stellar ===")
    print(f"Symbol: {xlm_usdc.symbol}")
    print(f"Market Type: {xlm_usdc.market_type}")
    print(f"Venue: {xlm_usdc.venue.display_name}")
    print(f"Venue Type: {xlm_usdc.venue_type}")
    print(f"Is Blockchain Native: {xlm_usdc.venue_type.is_blockchain_native}")
    print(f"Settlement Type: {xlm_usdc.settlement_type}")
    print(f"Requires Wallet Secret: {xlm_usdc.requires_wallet_secret}")
    
    assert xlm_usdc.market_type == MarketType.CRYPTO
    assert xlm_usdc.venue.is_blockchain_network
    assert xlm_usdc.requires_wallet_secret
    print("✓ All assertions passed\n")


def example_index_cfd():
    """Example 6: Index CFD on broker."""
    classifier = MarketClassifier()
    
    # Classify SPX500 on OANDA (index CFD)
    spx = classifier.classify("SPX500", Venue.OANDA)
    
    print("=== SPX500 on OANDA ===")
    print(f"Symbol: {spx.symbol}")
    print(f"Market Type: {spx.market_type}")
    print(f"Instrument Type: {spx.instrument_type}")
    print(f"Is Index: {spx.is_index}")
    print(f"Is Derivative: {spx.is_derivative}")
    print(f"Settlement Type: {spx.settlement_type}")
    print(f"Shortable: {spx.shortable}")
    
    assert spx.market_type == MarketType.INDEX
    assert spx.instrument_type == InstrumentType.CFD
    assert spx.shortable
    print("✓ All assertions passed\n")


def example_paper_trading():
    """Example 7: Paper trading (simulated) mode."""
    classifier = MarketClassifier()
    
    # Classify in paper trading mode
    btc_paper = classifier.classify(
        "BTC-USD",
        Venue.PAPER,
        trading_mode=TradingMode.PAPER,
    )
    
    print("=== BTC-USD on Paper Trading ===")
    print(f"Trading Mode: {btc_paper.trading_mode}")
    print(f"Is Simulated: {btc_paper.is_simulated}")
    print(f"Venue: {btc_paper.venue.display_name}")
    print(f"Venue Type: {btc_paper.venue_type}")
    
    assert btc_paper.trading_mode == TradingMode.PAPER
    assert btc_paper.is_simulated
    assert btc_paper.venue.is_simulated
    print("✓ All assertions passed\n")


def example_backtest_mode():
    """Example 8: Backtest mode."""
    classifier = MarketClassifier()
    
    # Classify in backtest mode
    eth_backtest = classifier.classify(
        "ETH-USD",
        Venue.BACKTEST,
        trading_mode=TradingMode.BACKTEST,
    )
    
    print("=== ETH-USD on Backtest ===")
    print(f"Trading Mode: {eth_backtest.trading_mode}")
    print(f"Is Simulated: {eth_backtest.is_simulated}")
    print(f"Venue: {eth_backtest.venue.display_name}")
    
    assert eth_backtest.trading_mode == TradingMode.BACKTEST
    assert eth_backtest.is_simulated
    print("✓ All assertions passed\n")


# ============================================================================
# INTEGRATION EXAMPLES
# ============================================================================


def example_broker_router_integration():
    """Example: Broker Router - Using MarketDescriptor for routing."""
    print("=== Broker Router Integration ===")
    
    classifier = MarketClassifier()
    
    # Different venues handle different markets
    routes = {
        ("BTC-USD", Venue.COINBASE): "CRYPTO_SPOT_HANDLER",
        ("BTC-PERP", Venue.COINBASE): "CRYPTO_PERPETUAL_HANDLER",
        ("EUR/USD", Venue.OANDA): "FOREX_HANDLER",
        ("AAPL", Venue.ALPACA): "STOCK_HANDLER",
        ("XLM/USDC", Venue.STELLAR): "BLOCKCHAIN_HANDLER",
    }
    
    for (symbol, venue), expected_handler in routes.items():
        descriptor = classifier.classify(symbol, venue)
        
        # Route based on market route
        if descriptor.market_route.market_type == MarketType.CRYPTO:
            if descriptor.instrument_type == InstrumentType.PERPETUAL_FUTURE:
                handler = "CRYPTO_PERPETUAL_HANDLER"
            else:
                handler = "CRYPTO_SPOT_HANDLER"
        elif descriptor.market_route.market_type == MarketType.FOREX:
            handler = "FOREX_HANDLER"
        elif descriptor.market_route.market_type == MarketType.STOCK:
            handler = "STOCK_HANDLER"
        elif descriptor.venue_type.is_blockchain_native:
            handler = "BLOCKCHAIN_HANDLER"
        else:
            handler = "DEFAULT_HANDLER"
        
        print(f"{symbol:15} @ {venue.display_name:20} -> {handler}")
        assert handler == expected_handler, f"Expected {expected_handler}, got {handler}"
    
    print("✓ All routing decisions correct\n")


def example_risk_engine_integration():
    """Example: Risk Engine - Classification for risk limits."""
    print("=== Risk Engine Integration ===")
    
    classifier = MarketClassifier()
    
    # Different asset classes get different risk limits
    positions = [
        ("BTC-USD", Venue.COINBASE),
        ("EUR/USD", Venue.OANDA),
        ("AAPL", Venue.ALPACA),
        ("SPX500", Venue.OANDA),
    ]
    
    risk_limits = {
        "CRYPTO_ASSET": 0.15,  # 15% max per position
        "FIAT_CURRENCY": 0.10,  # 10% max per position
        "EQUITY": 0.05,  # 5% max per position
        "EQUITY_INDEX": 0.08,  # 8% max per position
    }
    
    for symbol, venue in positions:
        descriptor = classifier.classify(symbol, venue)
        limit = risk_limits.get(str(descriptor.asset_class), 0.05)
        print(
            f"{symbol:15} @ {venue.display_name:20} "
            f"({descriptor.asset_class:20}) -> {limit:.1%} limit"
        )
    
    print("✓ Risk limits applied\n")


def example_websocket_subscription():
    """Example: WebSocket Subscription Manager - Market data type routing."""
    print("=== WebSocket Subscription Manager ===")
    
    classifier = MarketClassifier()
    
    # Different instruments require different data streams
    subscriptions = [
        ("BTC-USD", Venue.COINBASE, ["TICKER", "ORDER_BOOK", "TRADE"]),
        ("BTC-PERP", Venue.COINBASE, ["TICKER", "FUNDING_RATE", "LIQUIDATION"]),
        ("EUR/USD", Venue.OANDA, ["QUOTE", "CANDLE"]),
        ("AAPL", Venue.ALPACA, ["QUOTE", "TRADE"]),
    ]
    
    for symbol, venue, expected_streams in subscriptions:
        descriptor = classifier.classify(symbol, venue)
        
        # Subscribe based on instrument type
        streams = []
        if descriptor.instrument_type == InstrumentType.PERPETUAL_FUTURE:
            streams = ["TICKER", "FUNDING_RATE", "LIQUIDATION"]
        elif descriptor.is_crypto:
            streams = ["TICKER", "ORDER_BOOK", "TRADE"]
        elif descriptor.is_forex:
            streams = ["QUOTE", "CANDLE"]
        else:
            streams = ["QUOTE", "TRADE"]
        
        print(f"{symbol:15} @ {venue.display_name:20} -> {', '.join(streams)}")
        assert streams == expected_streams
    
    print("✓ All subscriptions correct\n")


def example_order_validation():
    """Example: Order Validation - Checking order type support."""
    print("=== Order Validation ===")
    
    classifier = MarketClassifier()
    
    test_cases = [
        ("BTC-USD", Venue.COINBASE, "SHORT", True),   # Can short spot via margin
        ("BTC-PERP", Venue.COINBASE, "SHORT", True),  # Can short perpetuals
        ("EUR/USD", Venue.OANDA, "SHORT", True),      # Can short forex
        ("AAPL", Venue.ALPACA, "SHORT", True),        # Can short stocks
        ("XLM/USDC", Venue.STELLAR, "SHORT", False),  # Can't short on DEX
    ]
    
    for symbol, venue, order_type, can_execute in test_cases:
        descriptor = classifier.classify(symbol, venue)
        is_shortable = descriptor.shortable or descriptor.is_perpetual
        
        print(
            f"{symbol:15} @ {venue.display_name:20} "
            f"{order_type:6} -> {'✓ OK' if is_shortable == can_execute else '✗ BLOCKED'}"
        )
        assert is_shortable == can_execute
    
    print("✓ All order validations correct\n")


def example_symbol_normalization():
    """Example: Symbol Normalization - Venue-specific formats."""
    print("=== Symbol Normalization ===")
    
    classifier = MarketClassifier()
    venues_and_symbols = [
        (Venue.COINBASE, "BTC-USD"),
        (Venue.BINANCE, "BTC/USD"),
        (Venue.OANDA, "EUR_USD"),
        (Venue.ALPACA, "AAPL"),
    ]
    
    for venue, symbol in venues_and_symbols:
        descriptor = classifier.classify(symbol, venue)
        normalized = descriptor.symbol
        
        # Coinbase/Binance use BTC-USD format
        if venue in (Venue.COINBASE, Venue.BINANCE):
            assert "-" in normalized or normalized == "AAPL"
        # OANDA uses EUR/USD format
        elif venue == Venue.OANDA:
            assert "/" in normalized or normalized == "AAPL"
        
        print(f"{symbol:15} @ {venue.display_name:20} -> {normalized}")
    
    print("✓ All symbols normalized\n")


# ============================================================================
# PROPERTY EXAMPLES
# ============================================================================


def example_properties():
    """Example: MarketDescriptor properties for decision logic."""
    print("=== MarketDescriptor Properties ===")
    
    classifier = MarketClassifier()
    
    descriptors = [
        ("BTC-USD", Venue.COINBASE),
        ("BTC-PERP", Venue.COINBASE),
        ("EUR/USD", Venue.OANDA),
        ("AAPL", Venue.ALPACA),
    ]
    
    properties_to_check = [
        ("is_crypto", "Is cryptocurrency"),
        ("is_derivative", "Is derivative product"),
        ("is_perpetual", "Is perpetual (no expiry)"),
        ("is_margin", "Requires margin/leverage"),
        ("shortable", "Can be short sold"),
        ("is_simulated", "Is paper/backtest mode"),
        ("requires_jwt_or_api_key", "Needs API key"),
        ("requires_wallet_secret", "Needs wallet secret"),
    ]
    
    for symbol, venue in descriptors:
        descriptor = classifier.classify(symbol, venue)
        print(f"\n{descriptor.display_symbol}:")
        for prop, description in properties_to_check:
            value = getattr(descriptor, prop)
            print(f"  {description:30} -> {value}")
    
    print("\n✓ All properties demonstrated\n")


# ============================================================================
# COMPREHENSIVE BATCH CLASSIFICATION
# ============================================================================


def example_batch_classification():
    """Example: Classify multiple symbols for a portfolio."""
    print("=== Batch Classification ===")
    
    classifier = MarketClassifier()
    
    # Portfolio across multiple venues
    portfolio = [
        ("BTC-USD", Venue.COINBASE),
        ("ETH-USD", Venue.BINANCE),
        ("EUR/USD", Venue.OANDA),
        ("AAPL", Venue.ALPACA),
        ("SPY", Venue.ALPACA),
        ("XLM/USDC", Venue.STELLAR),
    ]
    
    print(f"{'Symbol':15} {'Venue':20} {'Market':15} {'Instrument':20} {'Asset Class':15}")
    print("-" * 85)
    
    for symbol, venue in portfolio:
        descriptor = classifier.classify(symbol, venue)
        print(
            f"{descriptor.symbol:15} {venue.display_name:20} "
            f"{str(descriptor.market_type):15} {str(descriptor.instrument_type):20} "
            f"{str(descriptor.asset_class):15}"
        )
    
    print(f"\nTotal symbols classified: {len(portfolio)}\n")


# ============================================================================
# ERROR HANDLING & UNKNOWN FALLBACK
# ============================================================================


def example_unknown_symbol():
    """Example: Handling unknown/unclassifiable symbols."""
    print("=== Unknown Symbol Handling ===")
    
    classifier = MarketClassifier()
    
    # Symbol that can't be classified
    unknown = classifier.classify("XYZABC", Venue.UNKNOWN)
    
    print(f"Symbol: {unknown.symbol}")
    print(f"Market Type: {unknown.market_type}")
    print(f"Tradable: {unknown.tradable}")
    print(f"Is Unknown: {unknown.market_type == MarketType.UNKNOWN}")
    
    assert not unknown.tradable
    assert unknown.market_type == MarketType.UNKNOWN
    print("✓ Unknown symbol handled gracefully (no crash)\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MARKET CLASSIFICATION DOMAIN MODEL - EXAMPLES")
    print("=" * 80 + "\n")
    
    # Basic classification examples
    example_basic_classification()
    example_forex_classification()
    example_stock_classification()
    example_perpetual_classification()
    example_eth_stellar()
    example_index_cfd()
    example_paper_trading()
    example_backtest_mode()
    
    # Integration examples
    example_broker_router_integration()
    example_risk_engine_integration()
    example_websocket_subscription()
    example_order_validation()
    example_symbol_normalization()
    
    # Property examples
    example_properties()
    
    # Batch classification
    example_batch_classification()
    
    # Error handling
    example_unknown_symbol()
    
    print("=" * 80)
    print("✓ ALL EXAMPLES COMPLETED SUCCESSFULLY")
    print("=" * 80)
