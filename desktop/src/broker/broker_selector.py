"""Broker selector and router with backward compatibility.

Integrates the broker classification system with the existing broker factory,
providing a seamless way to:
- Select brokers by asset class and market type
- Validate brokers before order execution
- Route to appropriate risk engines
- Maintain backward compatibility with legacy configurations
"""

from __future__ import annotations

import logging
from typing import Optional

from broker.broker_classification import (
    AssetClass,
    BrokerProfile,
    BROKER_PROFILES,
    MarketType,
    get_broker_profile,
    get_risk_engine_key,
    select_brokers as _filter_brokers,
    validate_broker_for_trade,
)


logger = logging.getLogger(__name__)


class BrokerSelector:
    """Select and validate brokers based on trading requirements."""

    # Mapping from legacy broker/type to broker profile ID
    LEGACY_TO_PROFILE: dict[tuple[str, str], str] = {
        # (exchange, type) -> profile_id
        ("oanda", "forex"): "oanda_us",  # Default OANDA to US profile
        ("coinbase", "crypto"): "coinbase",
        ("coinbase", "spot"): "coinbase",
        ("coinbase_futures", "crypto"): "coinbase_futures",
        ("coinbase_futures", "futures"): "coinbase_futures",
        ("alpaca", "stocks"): "alpaca",
        ("alpaca", "equity"): "alpaca",
        ("schwab", "stocks"): "schwab",
        ("schwab", "equity"): "schwab",
        ("schwab", "options"): "schwab",
        ("ibkr", "stocks"): "ibkr",
        ("ibkr", "equity"): "ibkr",
        ("ibkr", "forex"): "ibkr",
        ("ibkr", "futures"): "ibkr",
        ("ibkr", "options"): "ibkr",
        ("binance_futures", "crypto"): "binance_futures",
        ("binance_futures", "futures"): "binance_futures",
        ("bybit", "crypto"): "bybit_futures",
        ("bybit", "futures"): "bybit_futures",
        ("bybit_futures", "crypto"): "bybit_futures",
        ("bybit_futures", "futures"): "bybit_futures",
        ("paper", "crypto"): "paper",
        ("paper", "forex"): "paper",
        ("paper", "stocks"): "paper",
        ("paper", "equity"): "paper",
        ("paper", "options"): "paper",
        ("paper", "futures"): "paper",
    }

    # Mapping from legacy asset class strings to enums
    ASSET_CLASS_MAP: dict[str, AssetClass] = {
        "forex": AssetClass.FOREX,
        "crypto": AssetClass.CRYPTO,
        "stocks": AssetClass.STOCK,
        "stock": AssetClass.STOCK,
        "equity": AssetClass.EQUITY,
        "futures": AssetClass.FUTURES,
        "options": AssetClass.OPTIONS,
        "cfd": AssetClass.CFD,
    }

    @staticmethod
    def get_profile_from_legacy_config(
        exchange: str, broker_type: str, customer_region: Optional[str] = None
    ) -> Optional[BrokerProfile]:
        """
        Map legacy broker configuration to broker profile.

        Args:
            exchange: Legacy exchange name (e.g., "oanda", "coinbase")
            broker_type: Legacy broker type (e.g., "forex", "crypto", "stocks")
            customer_region: Customer region (e.g., "US", "Global")

        Returns:
            BrokerProfile or None if not found
        """
        # Normalize inputs
        exchange = str(exchange or "").strip().lower()
        broker_type = str(broker_type or "").strip().lower()
        region = str(customer_region or "").strip().lower() if customer_region else None

        # Try exact match first
        profile_id = BrokerSelector.LEGACY_TO_PROFILE.get((exchange, broker_type))

        # Special case: OANDA with region consideration
        if exchange == "oanda":
            if region in {"us", "usa"}:
                profile_id = "oanda_us"
            elif profile_id is None:
                profile_id = "oanda_us"  # Default OANDA to US

        if profile_id:
            return get_broker_profile(profile_id)

        # Log warning and return None
        logger.warning(f"No profile mapping for exchange={exchange}, type={broker_type}")
        return None

    @staticmethod
    def select_brokers(
        asset_class: Optional[str] = None,
        market_type: Optional[str] = None,
        region: Optional[str] = None,
        requires_margin: bool = False,
        requires_leverage: bool = False,
        requires_shorting: bool = False,
        requires_fractional: bool = False,
    ) -> list[BrokerProfile]:
        """
        Select brokers matching the given criteria.

        Accepts both enum and string values for flexibility.

        Args:
            asset_class: Asset class (str or AssetClass enum)
            market_type: Market type (str or MarketType enum)
            region: Customer region
            requires_margin: Must support margin
            requires_leverage: Must support leverage
            requires_shorting: Must support short selling
            requires_fractional: Must support fractional shares

        Returns:
            List of matching broker profiles
        """
        # Convert strings to enums
        asset_class_enum = None
        if asset_class:
            if isinstance(asset_class, str):
                asset_class_enum = BrokerSelector.ASSET_CLASS_MAP.get(
                    asset_class.lower()
                )
            else:
                asset_class_enum = asset_class

        market_type_enum = None
        if market_type:
            if isinstance(market_type, str):
                try:
                    market_type_enum = MarketType(market_type.lower())
                except ValueError:
                    pass
            else:
                market_type_enum = market_type

        # Filter using the classification system
        return _filter_brokers(
            asset_class=asset_class_enum,
            market_type=market_type_enum,
            region=region,
            requires_margin=requires_margin,
            requires_leverage=requires_leverage,
            requires_shorting=requires_shorting,
            requires_fractional=requires_fractional,
        )

    @staticmethod
    def validate_broker_order(
        broker_profile: BrokerProfile,
        asset_class: Optional[AssetClass] = None,
        market_type: Optional[MarketType] = None,
        requires_margin: bool = False,
        requires_leverage: bool = False,
        requires_shorting: bool = False,
        requires_fractional: bool = False,
    ) -> tuple[bool, str]:
        """
        Validate if broker can execute an order with given requirements.

        Returns:
            (is_valid, error_message)
        """
        return validate_broker_for_trade(
            broker_profile=broker_profile,
            asset_class=asset_class,
            market_type=market_type,
            requires_margin=requires_margin,
            requires_leverage=requires_leverage,
            requires_shorting=requires_shorting,
            requires_fractional=requires_fractional,
        )

    @staticmethod
    def get_risk_engine_for_market(market_type: MarketType) -> str:
        """Get the risk engine key for a specific market type."""
        return get_risk_engine_key(market_type)

    @staticmethod
    def route_to_risk_engine(broker_profile: BrokerProfile) -> str:
        """
        Determine which risk engine to use for a broker.

        Uses the broker's risk_engine_key as primary routing,
        with fallback to default.
        """
        return broker_profile.risk_engine_key or "default"


class BrokerValidator:
    """Validate broker suitability before order execution."""

    @staticmethod
    def validate_connection(broker_profile: BrokerProfile) -> tuple[bool, str]:
        """
        Validate broker profile has required configuration.

        Returns:
            (is_valid, error_message)
        """
        if not broker_profile:
            return False, "Broker profile is required"

        if not broker_profile.broker_id:
            return False, "Broker ID is missing"

        if not broker_profile.asset_classes:
            return False, f"Broker {broker_profile.broker_id} has no asset classes"

        if not broker_profile.market_types:
            return False, f"Broker {broker_profile.broker_id} has no market types"

        return True, "OK"

    @staticmethod
    def validate_symbol(
        broker_profile: BrokerProfile,
        symbol: str,
        asset_class: Optional[AssetClass] = None,
        market_type: Optional[MarketType] = None,
    ) -> tuple[bool, str]:
        """
        Validate if symbol belongs to supported market for broker.

        Returns:
            (is_valid, error_message)
        """
        if not symbol:
            return False, "Symbol is required"

        # Validate broker supports requested asset/market
        if asset_class and not broker_profile.supports_asset_class(asset_class):
            return (
                False,
                f"Broker {broker_profile.display_name} does not support {asset_class.value}",
            )

        if market_type and not broker_profile.supports_market_type(market_type):
            return (
                False,
                f"Broker {broker_profile.display_name} does not support {market_type.value}",
            )

        return True, f"Symbol {symbol} is valid for {broker_profile.display_name}"

    @staticmethod
    def validate_order_parameters(
        broker_profile: BrokerProfile,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> tuple[bool, str]:
        """
        Validate order parameters for broker.

        Returns:
            (is_valid, error_message)
        """
        if not side or side.upper() not in {"BUY", "SELL"}:
            return False, "Side must be BUY or SELL"

        if quantity <= 0:
            return False, "Quantity must be positive"

        if order_type.lower() == "limit" and (price is None or price <= 0):
            return False, "Limit orders require a positive price"

        # Check shorting support for sell orders
        if side.upper() == "SELL" and not broker_profile.supports_shorting:
            if not broker_profile.supports_margin:
                return (
                    False,
                    f"Broker {broker_profile.display_name} does not support selling/shorting",
                )

        return True, "Order parameters valid"


def route_broker_for_trade(
    asset_class: AssetClass,
    market_type: Optional[MarketType] = None,
    requires_margin: bool = False,
    requires_leverage: bool = False,
    requires_shorting: bool = False,
    requires_fractional: bool = False,
    region: Optional[str] = None,
) -> tuple[Optional[BrokerProfile], list[BrokerProfile]]:
    """
    Find best broker for a trade, with alternatives.

    Returns:
        (primary_broker, alternative_brokers)
    """
    candidates = BrokerSelector.select_brokers(
        asset_class=asset_class,
        market_type=market_type,
        region=region,
        requires_margin=requires_margin,
        requires_leverage=requires_leverage,
        requires_shorting=requires_shorting,
        requires_fractional=requires_fractional,
    )

    if not candidates:
        return None, []

    # Return first as primary, rest as alternatives
    return candidates[0], candidates[1:]
