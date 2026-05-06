"""Domain model for market classification - Multi-asset trading platform.

This package provides a clean, professional market classification layer for
multi-asset trading platforms. It handles cryptographic assets, forex, equities,
derivatives, and simulated venues with deterministic classification logic.

Key components:
- Enums: Market types, instruments, venues, trading modes, settlement types
- Descriptor: Immutable market description (MarketDescriptor)
- Classifier: Deterministic symbol classification engine

Type hierarchy:
    MarketType -> InstrumentType -> Venue -> AssetClass -> ...

Usage example:
    from domain.market import MarketClassifier, MarketDescriptor, Venue
    
    classifier = MarketClassifier()
    
    # Classify BTC-USD on Coinbase
    btc_usd = classifier.classify("BTC-USD", Venue.COINBASE)
    assert btc_usd.market_type.is_crypto
    assert btc_usd.is_spot
    assert btc_usd.venue_type.is_exchange
    
    # Classify EUR/USD on OANDA
    eur_usd = classifier.classify("EUR/USD", Venue.OANDA)
    assert eur_usd.market_type.is_forex
    assert eur_usd.is_margin
    assert eur_usd.venue.is_broker
    
    # Classify AAPL on Alpaca
    aapl = classifier.classify("AAPL", Venue.ALPACA)
    assert aapl.market_type == MarketType.STOCK
    assert aapl.is_stock
    assert aapl.venue_type == VenueType.BROKER

Design principles:
1. No side effects: All methods are pure functions
2. Deterministic: Same input -> same output, always
3. Type-safe: Full type hints throughout
4. Safe defaults: UNKNOWN instead of None for unclassifiable symbols
5. Offline: No API/DB/network calls within classifiers
6. Immutable: MarketDescriptor uses frozen dataclass

Venue support:
- Centralized Exchanges: Coinbase, Binance, Kraken, OKX, Bybit
- Brokers: Alpaca, OANDA, Forex.com, Interactive Brokers, Charles Schwab
- Blockchain Networks: Stellar, Ethereum, Solana
- Simulation: Paper trading, Backtest
"""

from .enums import (
    MarketType,
    InstrumentType,
    VenueType,
    Venue,
    AssetClass,
    TradingMode,
    SettlementType,
    MarketDataType,
    MarketRoute,
)
from .descriptor import MarketDescriptor
from .classifier import MarketClassifier

__all__ = [
    # Enums
    "MarketType",
    "InstrumentType",
    "VenueType",
    "Venue",
    "AssetClass",
    "TradingMode",
    "SettlementType",
    "MarketDataType",
    "MarketRoute",
    # Classes
    "MarketDescriptor",
    "MarketClassifier",
]

__version__ = "1.0.0"
__author__ = "Multi-Asset Trading Platform Team"
__description__ = "Clean market classification domain model for multi-asset trading"
