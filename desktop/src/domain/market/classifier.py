"""Market classifier - Deterministic symbol classification to MarketDescriptor.

This module provides MarketClassifier, a utility class for deterministically
classifying trading symbols and venues into complete MarketDescriptor objects.

Key principles:
- Deterministic: Same input always produces same output
- No API/DB/network calls: Works offline with static rules
- Symbol-agnostic: Works with any symbol format (BTC-USD, BTC/USD, BTCUSD, etc.)
- Venue-aware: Uses venue metadata to inform classification
- Safe defaults: Returns UNKNOWN instead of crashing on ambiguous symbols

Symbol patterns handled:
- Crypto: BTC-USD, BTC-USDT, BTC/USD, BTCUSD, BTC-PERP, BTC-PERP:USDT
- Forex: EUR/USD, GBP_USD, EURUSD
- Stocks: AAPL, SPY, TSLA
- Indices: SPX500, SPX.USD (CFD format)
- Commodities: XAU/USD, GOLD
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from .enums import (
    MarketType,
    InstrumentType,
    VenueType,
    Venue,
    AssetClass,
    TradingMode,
    SettlementType,
    MarketRoute,
)
from .descriptor import MarketDescriptor


class MarketClassifier:
    """Deterministic market classification engine.
    
    Provides static/class methods to classify symbols and venues into complete
    MarketDescriptor objects. All methods are pure functions with no side effects.
    """
    
    # ========================================================================
    # CRYPTO ASSET DEFINITIONS
    # ========================================================================
    
    # Known crypto base assets
    CRYPTO_BASES = {
        "BTC", "ETH", "XRP", "ADA", "SOL", "AVAX", "DOGE", "DOT",
        "LINK", "MATIC", "UNI", "AAVE", "LDO", "ARB", "OP",
        "XLM", "USDC", "USDT", "BUSD", "TUSD", "FRAX", "DAI",
        "TRON", "TRX", "XMR", "ZEC", "BCH", "LTC", "ETC",
        "SHIB", "PEPE", "MEME", "INJ", "NEAR", "ATOM", "OSMO",
        "ALGO", "APTOS", "SUI", "BLUR", "ENS",
    }
    
    # Known crypto quote assets (settlement currencies)
    CRYPTO_QUOTES = {
        "USD", "USDT", "USDC", "BUSD", "TUSD", "FRAX", "DAI",
        "BTC", "ETH",
    }
    
    # Stablecoins (for settlement classification)
    STABLECOINS = {
        "USDT", "USDC", "BUSD", "TUSD", "FRAX", "DAI", "UST",
        "USDP", "GUSD", "PAX",
    }
    
    # ========================================================================
    # FOREX PAIR DEFINITIONS
    # ========================================================================
    
    # Known forex base currencies
    FOREX_BASES = {
        "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD",
        "SGD", "HKD", "SEK", "NOK", "DKK", "INR", "IDR",
        "THB", "MYR", "PHP", "KRW", "CNY", "RUB", "ZAR",
        "BRL", "MXN", "TRY", "AED", "SAR", "QAR", "ARS",
    }
    
    # ========================================================================
    # EQUITY/ETF DEFINITIONS
    # ========================================================================
    
    # Index-like symbols (often found as CFDs on brokers)
    INDEX_SYMBOLS = {
        "SPX", "SPX500", "INDU", "NDX", "IXIC",  # US indices
        "FTSE", "DAX", "CAC", "IBEX",  # European
        "N225", "HSI", "AORD", "SSE",  # Asian/Pacific
    }
    
    # Known index suffixes (CFD format)
    INDEX_SUFFIXES = {".DE", ".UK", ".AU", ".HK", ".JP"}
    
    # Known commodity symbols
    COMMODITY_SYMBOLS = {
        "XAU", "GOLD", "GC",  # Gold
        "XAG", "SILVER", "SI",  # Silver
        "CL", "WTI", "CRUDE",  # Oil
        "NG", "NATGAS",  # Natural gas
        "COPPER", "CU",  # Copper
        "WHEAT", "ZWH",  # Wheat
    }
    
    # ========================================================================
    # SYMBOL PARSING
    # ========================================================================
    
    @staticmethod
    def parse_base_asset(symbol: str) -> str:
        """Parse base asset from symbol.
        
        Examples:
            "BTC-USD" -> "BTC"
            "BTC/USD" -> "BTC"
            "EUR_USD" -> "EUR"
            "BTCUSD" -> "BTC" or "BTC"
            "AAPL" -> "AAPL"
        
        Args:
            symbol: Raw symbol string
            
        Returns:
            Base asset (uppercase)
        """
        # Normalize separators
        normalized = symbol.upper().replace("_", "-").replace("/", "-")
        
        # Split by separator
        if "-" in normalized:
            parts = normalized.split("-")
            return parts[0].strip()
        
        # For single-token symbols, try to extract base
        # For crypto, use leading portion; for stocks, return as-is
        if len(normalized) <= 5 or normalized[0].isalpha():
            # Likely stock ticker or forex pair prefix
            return normalized[:5].rstrip("0123456789")
        
        return normalized
    
    @staticmethod
    def parse_quote_asset(symbol: str) -> Optional[str]:
        """Parse quote asset from symbol.
        
        Examples:
            "BTC-USD" -> "USD"
            "BTC/USD" -> "USD"
            "EUR_USD" -> "USD"
            "AAPL" -> None
        
        Args:
            symbol: Raw symbol string
            
        Returns:
            Quote asset (uppercase) or None if not found
        """
        normalized = symbol.upper().replace("_", "-").replace("/", "-")
        
        if "-" in normalized:
            parts = normalized.split("-")
            if len(parts) >= 2:
                # Return everything after first dash as quote
                return parts[1].strip()
        
        return None
    
    @staticmethod
    def normalize_symbol(symbol: str, venue: Venue) -> str:
        """Normalize symbol to venue's preferred format.
        
        Each venue uses different conventions (BTC-USD, BTC/USD, BTCUSD).
        This method normalizes to a consistent format.
        
        Args:
            symbol: Raw symbol
            venue: Target venue
            
        Returns:
            Normalized symbol
        """
        normalized = symbol.upper().strip()
        
        # Coinbase uses BTC-USD format
        if venue in (Venue.COINBASE, Venue.BINANCE, Venue.KRAKEN):
            normalized = normalized.replace("/", "-").replace("_", "-")
        # OANDA uses EUR/USD or GBP_USD format
        elif venue in (Venue.OANDA, Venue.FOREX_COM):
            normalized = normalized.replace("-", "/").replace("_", "/")
        # Alpaca uses AAPL format
        elif venue == Venue.ALPACA:
            normalized = normalized.replace("-", "").replace("/", "").replace("_", "")
        
        return normalized
    
    # ========================================================================
    # MARKET TYPE INFERENCE
    # ========================================================================
    
    @classmethod
    def infer_market_type(
        cls,
        symbol: str,
        venue: Venue,
        instrument_type: Optional[InstrumentType] = None,
    ) -> MarketType:
        """Infer market type from symbol and venue.
        
        Strategy:
        1. Check if symbol indicates perpetual (PERP suffix) -> CRYPTO + PERPETUAL
        2. Check if symbol is in crypto bases -> CRYPTO
        3. Check if symbol is forex pair and venue supports forex -> FOREX
        4. Check if symbol is in equity/ETF universe -> STOCK/ETF
        5. Check if symbol is index-like -> INDEX
        6. Check venue support
        
        Args:
            symbol: Trading symbol
            venue: Trading venue
            instrument_type: Optional explicit instrument type (for disambiguation)
            
        Returns:
            Inferred MarketType
        """
        base_asset = cls.parse_base_asset(symbol).upper()
        quote_asset = cls.parse_quote_asset(symbol)
        upper_symbol = symbol.upper()
        
        # Check for perpetual indicator
        if "PERP" in upper_symbol or "-PERP" in upper_symbol:
            return MarketType.CRYPTO
        
        # Crypto exchange -> likely crypto
        if venue.is_centralized_exchange and venue.supports_crypto:
            if base_asset in cls.CRYPTO_BASES:
                return MarketType.CRYPTO
        
        # Blockchain network -> always crypto
        if venue.is_blockchain_network:
            return MarketType.CRYPTO
        
        # Check for forex pair (two 3-letter codes)
        if (
            base_asset in cls.FOREX_BASES
            and (quote_asset and quote_asset in cls.FOREX_BASES or len(base_asset) == 3)
        ):
            if venue in (Venue.OANDA, Venue.FOREX_COM) or venue.supports_fiat:
                return MarketType.FOREX
        
        # Check for commodity
        if base_asset in cls.COMMODITY_SYMBOLS:
            return MarketType.COMMODITY
        
        # Check for index
        if base_asset in cls.INDEX_SYMBOLS:
            return MarketType.INDEX
        
        # Stock broker -> likely stock
        if venue == Venue.ALPACA:
            # Alpaca only trades stocks and ETFs
            if upper_symbol == "SPY":
                return MarketType.ETF
            # Check if known ETF
            if any(etf in upper_symbol for etf in ["SPY", "QQQ", "IVV", "EEM", "GLD"]):
                return MarketType.ETF
            return MarketType.STOCK
        
        # Check for explicit instrument type hint
        if instrument_type == InstrumentType.CFD:
            if base_asset in cls.COMMODITY_SYMBOLS:
                return MarketType.COMMODITY
            return MarketType.INDEX
        
        # Default to unknown
        return MarketType.UNKNOWN
    
    # ========================================================================
    # INSTRUMENT TYPE INFERENCE
    # ========================================================================
    
    @classmethod
    def infer_instrument_type(
        cls,
        symbol: str,
        venue: Venue,
        instrument_type: Optional[InstrumentType] = None,
    ) -> InstrumentType:
        """Infer instrument type from symbol and venue.
        
        Strategy:
        1. If explicit instrument_type provided, use it
        2. Check symbol for perpetual indicator -> PERPETUAL_FUTURE
        3. Infer market type, then match instrument based on venue
        
        Args:
            symbol: Trading symbol
            venue: Trading venue
            instrument_type: Optional explicit instrument type
            
        Returns:
            Inferred InstrumentType
        """
        if instrument_type and instrument_type != InstrumentType.UNKNOWN:
            return instrument_type
        
        upper_symbol = symbol.upper()
        
        # Check for perpetual
        if "PERP" in upper_symbol:
            return InstrumentType.PERPETUAL_FUTURE
        
        # Infer market type to guide instrument type
        market_type = cls.infer_market_type(symbol, venue, instrument_type)
        
        # Centralized crypto exchange
        if venue.is_centralized_exchange and venue.supports_crypto:
            if market_type == MarketType.CRYPTO:
                return InstrumentType.SPOT
            elif market_type == MarketType.FUTURES:
                return InstrumentType.PERPETUAL_FUTURE
        
        # Blockchain network
        if venue.is_blockchain_network:
            return InstrumentType.SPOT
        
        # Forex broker
        if market_type == MarketType.FOREX:
            return InstrumentType.MARGIN_FX
        
        # Stock broker
        if venue == Venue.ALPACA:
            if market_type == MarketType.ETF:
                return InstrumentType.ETF
            return InstrumentType.STOCK
        
        # CFD brokers
        if venue in (Venue.OANDA, Venue.FOREX_COM):
            base_asset = cls.parse_base_asset(symbol).upper()
            if base_asset in cls.COMMODITY_SYMBOLS:
                return InstrumentType.CFD
            if base_asset in cls.INDEX_SYMBOLS or market_type == MarketType.INDEX:
                return InstrumentType.CFD
            return InstrumentType.MARGIN_FX
        
        # Default based on market type
        if market_type in (MarketType.STOCK, MarketType.ETF):
            return InstrumentType.STOCK
        elif market_type == MarketType.CRYPTO:
            return InstrumentType.SPOT
        
        return InstrumentType.UNKNOWN
    
    # ========================================================================
    # ASSET CLASS INFERENCE
    # ========================================================================
    
    @classmethod
    def infer_asset_class(
        cls,
        market_type: MarketType,
        instrument_type: InstrumentType,
    ) -> AssetClass:
        """Infer asset class from market and instrument types.
        
        Args:
            market_type: Market type classification
            instrument_type: Instrument type classification
            
        Returns:
            Inferred AssetClass
        """
        if market_type == MarketType.CRYPTO:
            return AssetClass.CRYPTO_ASSET
        elif market_type == MarketType.FOREX:
            return AssetClass.FIAT_CURRENCY
        elif market_type == MarketType.STOCK:
            return AssetClass.EQUITY
        elif market_type == MarketType.ETF:
            return AssetClass.EQUITY
        elif market_type == MarketType.INDEX:
            return AssetClass.EQUITY_INDEX
        elif market_type == MarketType.COMMODITY:
            return AssetClass.COMMODITY
        elif market_type == MarketType.BOND:
            return AssetClass.FIXED_INCOME
        elif market_type == MarketType.SYNTHETIC:
            return AssetClass.SYNTHETIC
        elif market_type in (MarketType.FUTURES, MarketType.OPTIONS, MarketType.CFD):
            return AssetClass.DERIVATIVE
        
        return AssetClass.UNKNOWN
    
    # ========================================================================
    # SETTLEMENT TYPE INFERENCE
    # ========================================================================
    
    @classmethod
    def infer_settlement_type(
        cls,
        market_type: MarketType,
        instrument_type: InstrumentType,
        venue: Venue,
        quote_asset: Optional[str] = None,
    ) -> SettlementType:
        """Infer settlement type from market/instrument and venue.
        
        Args:
            market_type: Market type
            instrument_type: Instrument type
            venue: Trading venue
            quote_asset: Quote asset if available
            
        Returns:
            Inferred SettlementType
        """
        # Perpetual -> no settlement
        if instrument_type == InstrumentType.PERPETUAL_FUTURE:
            return SettlementType.PERPETUAL
        
        # Crypto spot settlement
        if market_type == MarketType.CRYPTO and instrument_type.is_spot:
            if quote_asset and quote_asset.upper() in cls.STABLECOINS:
                return SettlementType.STABLECOIN
            return SettlementType.CRYPTO
        
        # Forex/CFD settlement
        if market_type in (MarketType.FOREX, MarketType.INDEX, MarketType.COMMODITY):
            if instrument_type == InstrumentType.CFD:
                return SettlementType.CASH
            return SettlementType.FIAT
        
        # Stock/ETF settlement
        if market_type in (MarketType.STOCK, MarketType.ETF):
            return SettlementType.CASH
        
        # Futures -> physical or cash
        if instrument_type == InstrumentType.FUTURE:
            if market_type == MarketType.COMMODITY:
                return SettlementType.PHYSICAL
            return SettlementType.CASH
        
        return SettlementType.UNKNOWN
    
    # ========================================================================
    # SHORTABLE INFERENCE
    # ========================================================================
    
    @classmethod
    def infer_shortable(
        cls,
        market_type: MarketType,
        instrument_type: InstrumentType,
        venue: Venue,
    ) -> bool:
        """Infer if symbol is shortable on the venue.
        
        Args:
            market_type: Market type
            instrument_type: Instrument type
            venue: Trading venue
            
        Returns:
            True if shortable
        """
        # Perpetuals -> always shortable
        if instrument_type == InstrumentType.PERPETUAL_FUTURE:
            return True
        
        # Margin instruments -> shortable
        if instrument_type.is_margin_product:
            return True
        
        # CFDs -> shortable
        if instrument_type == InstrumentType.CFD:
            return True
        
        # Alpaca stocks -> check if shortable (simplified: most are)
        if venue == Venue.ALPACA:
            return True
        
        # Spot crypto on centralized exchange -> typically shortable on margin
        if (
            market_type == MarketType.CRYPTO
            and instrument_type == InstrumentType.SPOT
            and venue.is_centralized_exchange
        ):
            return venue.venue_type == VenueType.CENTRALIZED_EXCHANGE
        
        return False
    
    # ========================================================================
    # MARKET ROUTE RESOLUTION
    # ========================================================================
    
    @classmethod
    def infer_market_route(
        cls,
        market_type: MarketType,
        instrument_type: InstrumentType,
        venue: Venue,
    ) -> MarketRoute:
        """Infer appropriate market route from classifications.
        
        Args:
            market_type: Market type
            instrument_type: Instrument type
            venue: Venue
            
        Returns:
            Matched or best-fit MarketRoute
        """
        venue_type = venue.venue_type
        
        # Try exact match first
        resolved = MarketRoute.resolve(market_type, instrument_type, venue_type)
        if resolved != MarketRoute.UNKNOWN_ROUTE:
            return resolved
        
        # Fallback heuristics
        if venue.is_simulated:
            if venue == Venue.PAPER:
                return MarketRoute.PAPER_ROUTE
            else:
                return MarketRoute.BACKTEST_ROUTE
        
        # Crypto CEX spot
        if (
            market_type == MarketType.CRYPTO
            and instrument_type == InstrumentType.SPOT
            and venue_type == VenueType.CENTRALIZED_EXCHANGE
        ):
            return MarketRoute.CRYPTO_SPOT_CEX
        
        # Crypto blockchain swap
        if (
            market_type == MarketType.CRYPTO
            and venue_type == VenueType.BLOCKCHAIN_NETWORK
        ):
            return MarketRoute.CRYPTO_NETWORK_SWAP
        
        # Forex on broker
        if market_type == MarketType.FOREX and venue_type == VenueType.BROKER:
            return MarketRoute.FOREX_MARGIN_BROKER
        
        # Stock on broker
        if market_type == MarketType.STOCK and venue == Venue.ALPACA:
            return MarketRoute.STOCK_BROKER
        
        return MarketRoute.UNKNOWN_ROUTE
    
    # ========================================================================
    # MAIN CLASSIFICATION METHOD
    # ========================================================================
    
    @classmethod
    def classify(
        cls,
        symbol: str,
        venue: Venue,
        instrument_type: Optional[InstrumentType] = None,
        trading_mode: TradingMode = TradingMode.LIVE,
    ) -> MarketDescriptor:
        """Classify a symbol on a venue into a complete MarketDescriptor.
        
        This is the main entry point for market classification. It performs
        deterministic inference of all market characteristics from symbol
        and venue.
        
        Args:
            symbol: Trading symbol (e.g., "BTC-USD", "EUR/USD", "AAPL")
            venue: Execution venue
            instrument_type: Optional explicit instrument type (overrides inference)
            trading_mode: Trading mode (LIVE, PAPER, BACKTEST)
            
        Returns:
            Complete MarketDescriptor
            
        Example:
            >>> classifier = MarketClassifier()
            >>> desc = classifier.classify("BTC-USD", Venue.COINBASE)
            >>> desc.market_type
            <MarketType.CRYPTO: 'crypto'>
            >>> desc.is_perpetual
            False
            >>> desc.venue.display_name
            'Coinbase'
        """
        try:
            # Parse symbol
            base_asset = cls.parse_base_asset(symbol)
            quote_asset = cls.parse_quote_asset(symbol)
            
            # Infer classifications
            market_type = cls.infer_market_type(symbol, venue, instrument_type)
            inferred_instrument_type = cls.infer_instrument_type(
                symbol, venue, instrument_type
            )
            asset_class = cls.infer_asset_class(market_type, inferred_instrument_type)
            settlement_type = cls.infer_settlement_type(
                market_type, inferred_instrument_type, venue, quote_asset
            )
            shortable = cls.infer_shortable(market_type, inferred_instrument_type, venue)
            market_route = cls.infer_market_route(
                market_type, inferred_instrument_type, venue
            )
            
            # Determine if leveraged
            leveraged = inferred_instrument_type.is_margin_product
            
            # Create descriptor
            return MarketDescriptor(
                symbol=cls.normalize_symbol(symbol, venue),
                base_asset=base_asset.upper(),
                quote_asset=quote_asset.upper() if quote_asset else None,
                market_type=market_type,
                instrument_type=inferred_instrument_type,
                asset_class=asset_class,
                venue=venue,
                venue_type=venue.venue_type,
                settlement_type=settlement_type,
                trading_mode=trading_mode,
                market_route=market_route,
                leveraged=leveraged,
                shortable=shortable,
                tradable=True,
            )
        
        except Exception as e:
            # Safe fallback: return UNKNOWN descriptor
            return MarketDescriptor.unknown(symbol)
