"""Broker classification system with asset classes, market types, and venue types.

This module provides a comprehensive broker profile system that:
- Classifies brokers by asset class and market/product type
- Routes orders to appropriate risk engines based on market type
- Validates broker capabilities before trading
- Maintains backward compatibility with existing broker configurations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AssetClass(str, Enum):
    """Asset classes supported by brokers."""

    FOREX = "forex"  # Foreign exchange
    CRYPTO = "crypto"  # Cryptocurrencies
    STOCK = "stock"  # Individual stocks/equities (user-facing label)
    EQUITY = "equity"  # Internal term for stocks
    FUTURES = "futures"  # Futures contracts
    OPTIONS = "options"  # Options contracts
    CFD = "cfd"  # Contracts for Difference


class MarketType(str, Enum):
    """Specific market types for trading products."""

    # Forex
    SPOT_FX = "spot_fx"  # Spot forex (no leverage, direct settlement)
    MARGIN_FX = "margin_fx"  # Leveraged OTC forex (e.g., OANDA for US)
    FX_CFD = "fx_cfd"  # CFD-based forex (typically non-US)
    FX_FORWARD = "fx_forward"  # Forward contracts
    FX_FUTURE = "fx_future"  # Futures-based forex
    FX_OPTION = "fx_option"  # Options on forex

    # Crypto
    SPOT_CRYPTO = "spot_crypto"  # Spot cryptocurrency (e.g., Coinbase)
    CRYPTO_MARGIN = "crypto_margin"  # Leveraged crypto
    CRYPTO_PERPETUAL = "crypto_perpetual"  # Perpetual contracts (e.g., Binance)
    CRYPTO_FUTURE = "crypto_future"  # Futures contracts
    CRYPTO_OPTION = "crypto_option"  # Options on crypto

    # Stocks/Equities
    CASH_STOCK = "cash_stock"  # Stocks with cash settlement (no leverage)
    CASH_EQUITY = "cash_equity"  # Equities with cash settlement (no leverage)
    FRACTIONAL_STOCK = "fractional_stock"  # Fractional shares
    STOCK_MARGIN = "stock_margin"  # Margin trading on stocks
    EQUITY_MARGIN = "equity_margin"  # Margin trading on equities
    SHORT_STOCK = "short_stock"  # Short selling
    STOCK_CFD = "stock_cfd"  # CFD-based stocks
    EQUITY_CFD = "equity_cfd"  # CFD-based equities
    STOCK_OPTION = "stock_option"  # Stock options
    EQUITY_OPTION = "equity_option"  # Equity options

    # Futures
    LISTED_FUTURE = "listed_future"  # Exchange-listed futures

    # Options
    LISTED_OPTION = "listed_option"  # Exchange-listed options

    # Generic CFD
    CFD = "cfd"  # Generic CFD


class VenueType(str, Enum):
    """Venue types for trading."""

    EXCHANGE = "exchange"  # Centralized exchange
    OTC = "otc"  # Over-the-counter (broker-dealer)
    BROKER_DEALER = "broker_dealer"  # Traditional broker-dealer
    ECN = "ecn"  # Electronic Communication Network
    HYBRID = "hybrid"  # Hybrid (mix of exchange and OTC)


@dataclass(frozen=True)
class BrokerProfile:
    """Complete broker profile with capabilities and risk routing."""

    # Identification
    broker_id: str  # e.g., "oanda_us", "coinbase_spot"
    display_name: str  # e.g., "OANDA (US)", "Coinbase Pro"
    region: str  # e.g., "US", "Global", "EU"

    # Asset classes and market types supported
    asset_classes: tuple[AssetClass, ...] = field(default_factory=tuple)
    market_types: tuple[MarketType, ...] = field(default_factory=tuple)
    venue_type: VenueType = VenueType.OTC

    # Capabilities
    supports_leverage: bool = False
    supports_margin: bool = False
    supports_shorting: bool = False
    supports_fractional: bool = False
    supports_derivatives: bool = False
    supports_options: bool = False
    supports_futures: bool = False
    is_cfd_broker: bool = False
    is_otc: bool = True

    # Default and risk routing
    default_market_type: MarketType = MarketType.SPOT_CRYPTO
    risk_engine_key: str = "default"  # Key to select appropriate risk engine

    # Additional info
    notes: str = ""

    def supports_asset_class(self, asset_class: AssetClass) -> bool:
        """Check if broker supports a specific asset class."""
        return asset_class in self.asset_classes

    def supports_market_type(self, market_type: MarketType) -> bool:
        """Check if broker supports a specific market type."""
        return market_type in self.market_types

    def can_trade(
        self,
        asset_class: Optional[AssetClass] = None,
        market_type: Optional[MarketType] = None,
        requires_margin: bool = False,
        requires_leverage: bool = False,
        requires_shorting: bool = False,
        requires_fractional: bool = False,
    ) -> tuple[bool, str]:
        """
        Validate if broker can execute a trade with given requirements.

        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        if asset_class and not self.supports_asset_class(asset_class):
            return False, f"Broker does not support {asset_class.value}"

        if market_type and not self.supports_market_type(market_type):
            return False, f"Broker does not support {market_type.value}"

        if requires_margin and not self.supports_margin:
            return False, "Broker does not support margin trading"

        if requires_leverage and not self.supports_leverage:
            return False, "Broker does not support leverage"

        if requires_shorting and not self.supports_shorting:
            return False, "Broker does not support short selling"

        if requires_fractional and not self.supports_fractional:
            return False, "Broker does not support fractional shares"

        return True, "OK"


# ==========================================
# Predefined Broker Profiles
# ==========================================

BROKER_PROFILES: dict[str, BrokerProfile] = {
    # OANDA
    "oanda_us": BrokerProfile(
        broker_id="oanda_us",
        display_name="OANDA (US)",
        region="US",
        asset_classes=(AssetClass.FOREX,),
        market_types=(MarketType.MARGIN_FX,),
        venue_type=VenueType.OTC,
        supports_leverage=True,
        supports_margin=True,
        supports_shorting=False,
        is_cfd_broker=False,
        is_otc=True,
        default_market_type=MarketType.MARGIN_FX,
        risk_engine_key="margin_fx",
        notes="Leveraged OTC forex for US customers (not CFD)",
    ),
    "oanda_cfd": BrokerProfile(
        broker_id="oanda_cfd",
        display_name="OANDA CFD",
        region="Global",
        asset_classes=(AssetClass.FOREX, AssetClass.CFD),
        market_types=(MarketType.FX_CFD, MarketType.STOCK_CFD, MarketType.EQUITY_CFD),
        venue_type=VenueType.OTC,
        supports_leverage=True,
        supports_margin=True,
        is_cfd_broker=True,
        is_otc=True,
        default_market_type=MarketType.FX_CFD,
        risk_engine_key="cfd",
        notes="CFD-based forex and stocks (non-US)",
    ),
    # Coinbase
    "coinbase": BrokerProfile(
        broker_id="coinbase",
        display_name="Coinbase",
        region="Global",
        asset_classes=(AssetClass.CRYPTO,),
        market_types=(MarketType.SPOT_CRYPTO,),
        venue_type=VenueType.EXCHANGE,
        supports_leverage=False,
        supports_margin=False,
        supports_shorting=False,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.SPOT_CRYPTO,
        risk_engine_key="spot_crypto",
        notes="Spot crypto trading on centralized exchange",
    ),
    "coinbase_futures": BrokerProfile(
        broker_id="coinbase_futures",
        display_name="Coinbase Futures",
        region="Global",
        asset_classes=(AssetClass.CRYPTO, AssetClass.FUTURES),
        market_types=(MarketType.CRYPTO_PERPETUAL,),
        venue_type=VenueType.EXCHANGE,
        supports_leverage=True,
        supports_margin=True,
        supports_derivatives=True,
        supports_futures=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CRYPTO_PERPETUAL,
        risk_engine_key="perpetual",
        notes="Leveraged perpetual crypto futures",
    ),
    # Alpaca
    "alpaca": BrokerProfile(
        broker_id="alpaca",
        display_name="Alpaca",
        region="US",
        asset_classes=(AssetClass.STOCK, AssetClass.EQUITY),
        market_types=(MarketType.CASH_STOCK, MarketType.CASH_EQUITY, MarketType.FRACTIONAL_STOCK),
        venue_type=VenueType.BROKER_DEALER,
        supports_leverage=False,
        supports_margin=False,
        supports_shorting=False,
        supports_fractional=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CASH_STOCK,
        risk_engine_key="stock",
        notes="US stocks with optional margin account",
    ),
    "alpaca_margin": BrokerProfile(
        broker_id="alpaca_margin",
        display_name="Alpaca (Margin)",
        region="US",
        asset_classes=(AssetClass.STOCK, AssetClass.EQUITY),
        market_types=(
            MarketType.CASH_STOCK,
            MarketType.CASH_EQUITY,
            MarketType.FRACTIONAL_STOCK,
            MarketType.STOCK_MARGIN,
            MarketType.EQUITY_MARGIN,
        ),
        venue_type=VenueType.BROKER_DEALER,
        supports_leverage=True,
        supports_margin=True,
        supports_shorting=False,
        supports_fractional=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CASH_STOCK,
        risk_engine_key="stock_margin",
        notes="US stocks with margin trading enabled",
    ),
    # Schwab
    "schwab": BrokerProfile(
        broker_id="schwab",
        display_name="Charles Schwab",
        region="US",
        asset_classes=(AssetClass.STOCK, AssetClass.EQUITY, AssetClass.OPTIONS),
        market_types=(
            MarketType.CASH_STOCK,
            MarketType.CASH_EQUITY,
            MarketType.STOCK_OPTION,
            MarketType.EQUITY_OPTION,
        ),
        venue_type=VenueType.BROKER_DEALER,
        supports_leverage=False,
        supports_margin=False,
        supports_shorting=False,
        supports_fractional=False,
        supports_derivatives=False,
        supports_options=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CASH_STOCK,
        risk_engine_key="stock_options",
        notes="US stocks and equity options",
    ),
    "schwab_margin": BrokerProfile(
        broker_id="schwab_margin",
        display_name="Charles Schwab (Margin)",
        region="US",
        asset_classes=(AssetClass.STOCK, AssetClass.EQUITY, AssetClass.OPTIONS),
        market_types=(
            MarketType.CASH_STOCK,
            MarketType.CASH_EQUITY,
            MarketType.STOCK_MARGIN,
            MarketType.EQUITY_MARGIN,
            MarketType.STOCK_OPTION,
            MarketType.EQUITY_OPTION,
            MarketType.SHORT_STOCK,
        ),
        venue_type=VenueType.BROKER_DEALER,
        supports_leverage=True,
        supports_margin=True,
        supports_shorting=True,
        supports_fractional=False,
        supports_derivatives=False,
        supports_options=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CASH_STOCK,
        risk_engine_key="stock_margin",
        notes="US stocks, equities, and options with margin",
    ),
    # Interactive Brokers
    "ibkr": BrokerProfile(
        broker_id="ibkr",
        display_name="Interactive Brokers",
        region="Global",
        asset_classes=(
            AssetClass.STOCK,
            AssetClass.EQUITY,
            AssetClass.FOREX,
            AssetClass.FUTURES,
            AssetClass.OPTIONS,
        ),
        market_types=(
            MarketType.CASH_STOCK,
            MarketType.CASH_EQUITY,
            MarketType.STOCK_MARGIN,
            MarketType.EQUITY_MARGIN,
            MarketType.SHORT_STOCK,
            MarketType.SPOT_FX,
            MarketType.MARGIN_FX,
            MarketType.FX_FUTURE,
            MarketType.LISTED_FUTURE,
            MarketType.LISTED_OPTION,
            MarketType.STOCK_OPTION,
            MarketType.EQUITY_OPTION,
        ),
        venue_type=VenueType.HYBRID,
        supports_leverage=True,
        supports_margin=True,
        supports_shorting=True,
        supports_fractional=True,
        supports_derivatives=True,
        supports_options=True,
        supports_futures=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CASH_STOCK,
        risk_engine_key="multi_asset",
        notes="Full-service global broker with all asset classes",
    ),
    # Crypto derivatives exchanges
    "binance_futures": BrokerProfile(
        broker_id="binance_futures",
        display_name="Binance Futures",
        region="Global",
        asset_classes=(AssetClass.CRYPTO, AssetClass.FUTURES),
        market_types=(MarketType.CRYPTO_PERPETUAL, MarketType.CRYPTO_FUTURE),
        venue_type=VenueType.EXCHANGE,
        supports_leverage=True,
        supports_margin=True,
        supports_derivatives=True,
        supports_futures=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CRYPTO_PERPETUAL,
        risk_engine_key="perpetual",
        notes="Leveraged crypto perpetuals and futures",
    ),
    "bybit_futures": BrokerProfile(
        broker_id="bybit_futures",
        display_name="Bybit",
        region="Global",
        asset_classes=(AssetClass.CRYPTO, AssetClass.FUTURES),
        market_types=(MarketType.CRYPTO_PERPETUAL, MarketType.CRYPTO_FUTURE),
        venue_type=VenueType.EXCHANGE,
        supports_leverage=True,
        supports_margin=True,
        supports_derivatives=True,
        supports_futures=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.CRYPTO_PERPETUAL,
        risk_engine_key="perpetual",
        notes="Leveraged crypto perpetuals and futures",
    ),
    # Paper trading
    "paper": BrokerProfile(
        broker_id="paper",
        display_name="Paper Trading",
        region="Global",
        asset_classes=(
            AssetClass.FOREX,
            AssetClass.CRYPTO,
            AssetClass.STOCK,
            AssetClass.EQUITY,
            AssetClass.FUTURES,
            AssetClass.OPTIONS,
        ),
        market_types=(
            MarketType.MARGIN_FX,
            MarketType.SPOT_CRYPTO,
            MarketType.CASH_STOCK,
            MarketType.CASH_EQUITY,
            MarketType.LISTED_FUTURE,
            MarketType.LISTED_OPTION,
        ),
        venue_type=VenueType.HYBRID,
        supports_leverage=True,
        supports_margin=True,
        supports_shorting=True,
        supports_fractional=True,
        supports_derivatives=True,
        supports_options=True,
        supports_futures=True,
        is_cfd_broker=False,
        is_otc=False,
        default_market_type=MarketType.MARGIN_FX,
        risk_engine_key="default",
        notes="Simulated trading for backtesting and paper trading",
    ),
}


# ==========================================
# Risk Engine Routing
# ==========================================

MARKET_TYPE_TO_RISK_ENGINE: dict[MarketType, str] = {
    # Forex
    MarketType.SPOT_FX: "spot_fx",
    MarketType.MARGIN_FX: "margin_fx",
    MarketType.FX_CFD: "cfd",
    MarketType.FX_FUTURE: "futures",
    MarketType.FX_OPTION: "options",
    # Crypto
    MarketType.SPOT_CRYPTO: "spot_crypto",
    MarketType.CRYPTO_MARGIN: "crypto_margin",
    MarketType.CRYPTO_PERPETUAL: "perpetual",
    MarketType.CRYPTO_FUTURE: "futures",
    MarketType.CRYPTO_OPTION: "options",
    # Stocks
    MarketType.CASH_STOCK: "stock",
    MarketType.CASH_EQUITY: "stock",
    MarketType.FRACTIONAL_STOCK: "fractional_stock",
    MarketType.STOCK_MARGIN: "stock_margin",
    MarketType.EQUITY_MARGIN: "stock_margin",
    MarketType.SHORT_STOCK: "short_stock",
    MarketType.STOCK_CFD: "cfd",
    MarketType.EQUITY_CFD: "cfd",
    MarketType.STOCK_OPTION: "options",
    MarketType.EQUITY_OPTION: "options",
    # Futures
    MarketType.LISTED_FUTURE: "futures",
    # Options
    MarketType.LISTED_OPTION: "options",
    # Generic
    MarketType.CFD: "cfd",
}


logger = logging.getLogger(__name__)


def get_broker_profile(broker_id: str) -> Optional[BrokerProfile]:
    """Get broker profile by ID."""
    return BROKER_PROFILES.get(broker_id)


def get_risk_engine_key(market_type: MarketType) -> str:
    """Get risk engine key for a market type."""
    return MARKET_TYPE_TO_RISK_ENGINE.get(market_type, "default")


def select_brokers(
    asset_class: Optional[AssetClass] = None,
    market_type: Optional[MarketType] = None,
    region: Optional[str] = None,
    requires_margin: bool = False,
    requires_leverage: bool = False,
    requires_shorting: bool = False,
    requires_fractional: bool = False,
) -> list[BrokerProfile]:
    """
    Select brokers matching the given criteria.

    Args:
        asset_class: Filter by asset class
        market_type: Filter by market type
        region: Filter by region (e.g., "US", "Global")
        requires_margin: Must support margin
        requires_leverage: Must support leverage
        requires_shorting: Must support short selling
        requires_fractional: Must support fractional shares

    Returns:
        List of matching broker profiles
    """
    results = []

    for profile in BROKER_PROFILES.values():
        # Region filter
        if region and profile.region != region:
            continue

        # Capability checks
        can_trade, _ = profile.can_trade(
            asset_class=asset_class,
            market_type=market_type,
            requires_margin=requires_margin,
            requires_leverage=requires_leverage,
            requires_shorting=requires_shorting,
            requires_fractional=requires_fractional,
        )

        if can_trade:
            results.append(profile)

    return results


def validate_broker_for_trade(
    broker_profile: BrokerProfile,
    asset_class: Optional[AssetClass] = None,
    market_type: Optional[MarketType] = None,
    requires_margin: bool = False,
    requires_leverage: bool = False,
    requires_shorting: bool = False,
    requires_fractional: bool = False,
) -> tuple[bool, str]:
    """
    Validate if a broker can execute a trade with given requirements.

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    can_trade, reason = broker_profile.can_trade(
        asset_class=asset_class,
        market_type=market_type,
        requires_margin=requires_margin,
        requires_leverage=requires_leverage,
        requires_shorting=requires_shorting,
        requires_fractional=requires_fractional,
    )

    if not can_trade:
        return False, f"Broker validation failed: {reason}"

    return True, "OK"
