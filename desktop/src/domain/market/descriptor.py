"""Market descriptor - Immutable description of a tradable market/symbol.

This module defines MarketDescriptor, a frozen dataclass that provides complete
classification and metadata for any tradable symbol. It serves as the canonical
reference for market type, instrument type, venue, and trading characteristics
throughout the platform.

Key design:
- Frozen dataclass (immutable, hashable, serializable)
- Type-safe with full type hints
- Complete metadata for any trading venue and symbol
- Safe UNKNOWN fallback instead of None
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


@dataclass(frozen=True)
class MarketDescriptor:
    """Immutable description of a tradable market, symbol, or instrument.
    
    This dataclass serves as the canonical reference for market classification,
    providing complete metadata about:
    - Symbol and asset composition (symbol, base_asset, quote_asset)
    - Market type and product structure (market_type, instrument_type)
    - Asset class and trading characteristics (asset_class, venue, venue_type)
    - Settlement and trading mode (settlement_type, trading_mode)
    - Risk profile and tradability (leveraged, shortable, tradable)
    
    All fields are immutable (frozen=True), making instances hashable and suitable
    for use as dictionary keys or in sets. UNKNOWN is used as a safe default instead
    of None to ensure the descriptor is always valid.
    
    Attributes:
        symbol: Canonical trading symbol (e.g., "BTC-USD", "EUR/USD", "AAPL")
        base_asset: Primary asset (e.g., "BTC", "EUR", "AAPL")
        quote_asset: Denominating asset if applicable (e.g., "USD", "USDT")
        market_type: Broad market category (CRYPTO, FOREX, STOCK, etc.)
        instrument_type: Product structure (SPOT, PERPETUAL_FUTURE, OPTION, etc.)
        asset_class: Portfolio grouping (CRYPTO_ASSET, EQUITY, DERIVATIVE, etc.)
        venue: Specific execution venue (COINBASE, ALPACA, BINANCE, etc.)
        venue_type: Type of venue (BROKER, CENTRALIZED_EXCHANGE, etc.)
        settlement_type: Settlement mechanism (CASH, CRYPTO, PERPETUAL, etc.)
        trading_mode: Execution environment (LIVE, PAPER, BACKTEST, etc.)
        market_route: Composite routing rule for strategy/risk/order routing
        leveraged: True if trading with leverage/margin
        shortable: True if short selling is allowed
        tradable: True if this symbol is currently tradable
    """
    
    symbol: str
    base_asset: str
    quote_asset: Optional[str]
    market_type: MarketType
    instrument_type: InstrumentType
    asset_class: AssetClass
    venue: Venue
    venue_type: VenueType
    settlement_type: SettlementType
    trading_mode: TradingMode
    market_route: MarketRoute
    leveraged: bool = False
    shortable: bool = False
    tradable: bool = True
    
    @classmethod
    def unknown(cls, symbol: str) -> MarketDescriptor:
        """Create an UNKNOWN descriptor for an unclassifiable symbol.
        
        Useful for graceful degradation when symbol classification fails.
        The descriptor will have UNKNOWN values for all market classifications
        but will still be a valid, hashable instance.
        
        Args:
            symbol: The symbol that could not be classified
            
        Returns:
            MarketDescriptor with UNKNOWN classifications
        """
        return cls(
            symbol=symbol,
            base_asset=symbol,
            quote_asset=None,
            market_type=MarketType.UNKNOWN,
            instrument_type=InstrumentType.UNKNOWN,
            asset_class=AssetClass.UNKNOWN,
            venue=Venue.UNKNOWN,
            venue_type=VenueType.UNKNOWN,
            settlement_type=SettlementType.UNKNOWN,
            trading_mode=TradingMode.LIVE,
            market_route=MarketRoute.UNKNOWN_ROUTE,
            leveraged=False,
            shortable=False,
            tradable=False,
        )
    
    @property
    def is_derivative(self) -> bool:
        """True if this is a derivative product (futures, options, perpetuals, etc.)."""
        return self.instrument_type.is_derivative
    
    @property
    def is_crypto(self) -> bool:
        """True if this is cryptocurrency-based trading."""
        return self.market_type.is_crypto
    
    @property
    def is_forex(self) -> bool:
        """True if this is foreign exchange trading."""
        return self.market_type.is_forex
    
    @property
    def is_stock(self) -> bool:
        """True if this is stock/equity trading."""
        return self.market_type == MarketType.STOCK
    
    @property
    def is_etf(self) -> bool:
        """True if this is ETF trading."""
        return self.market_type == MarketType.ETF
    
    @property
    def is_index(self) -> bool:
        """True if this is index-based (INDEX market type or CFD on index)."""
        return self.market_type == MarketType.INDEX or (
            self.market_type == MarketType.CFD
            and self.instrument_type == InstrumentType.CFD
        )
    
    @property
    def is_perpetual(self) -> bool:
        """True if this is a perpetual contract (never expires)."""
        return self.instrument_type == InstrumentType.PERPETUAL_FUTURE
    
    @property
    def is_margin(self) -> bool:
        """True if margin/leverage is involved."""
        return self.leveraged or self.instrument_type.is_margin_product
    
    @property
    def is_spot(self) -> bool:
        """True if this is a spot/physical settlement instrument."""
        return self.instrument_type.is_spot
    
    @property
    def is_broker_traded(self) -> bool:
        """True if traded through a broker venue."""
        return self.venue.is_broker
    
    @property
    def is_exchange_traded(self) -> bool:
        """True if traded on an exchange venue."""
        return self.venue_type.is_exchange
    
    @property
    def is_blockchain_native(self) -> bool:
        """True if traded on blockchain-native venue (DEX or blockchain network)."""
        return self.venue_type.is_blockchain_native
    
    @property
    def is_simulated(self) -> bool:
        """True if trading mode is paper, backtest, or simulation."""
        return self.trading_mode.is_test_mode
    
    @property
    def requires_jwt_or_api_key(self) -> bool:
        """True if this venue requires API key/JWT authentication."""
        return self.venue_type.requires_account_credentials
    
    @property
    def requires_wallet_secret(self) -> bool:
        """True if this venue requires wallet secret/mnemonic (blockchain venue)."""
        return self.venue_type.requires_wallet_credentials
    
    @property
    def normalized_symbol(self) -> str:
        """Normalized symbol for database/logging (uppercase, no special chars).
        
        Example:
            "btc-usd" -> "BTCUSD"
            "EUR/USD" -> "EURUSD"
        """
        return self.symbol.upper().replace("-", "").replace("/", "").replace("_", "")
    
    @property
    def display_symbol(self) -> str:
        """Display symbol with venue context (e.g., "BTC-USD @ COINBASE").
        
        Useful for UI and logging.
        """
        return f"{self.symbol} @ {self.venue.display_name}"
    
    def __str__(self) -> str:
        """String representation: symbol (market_type/instrument_type)."""
        return f"{self.symbol} ({self.market_type}/{self.instrument_type})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"MarketDescriptor(symbol={self.symbol!r}, "
            f"market_type={self.market_type}, "
            f"instrument_type={self.instrument_type}, "
            f"venue={self.venue}, "
            f"trading_mode={self.trading_mode})"
        )
