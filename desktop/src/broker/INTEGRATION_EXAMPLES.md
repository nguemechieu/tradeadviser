"""Integration Examples - Broker Classification System

Practical examples showing how to integrate the broker classification system
into existing code without breaking backward compatibility.
"""

# ============================================================================
# EXAMPLE 1: Update Broker Factory
# ============================================================================

"""
Current broker_factory.py usage:
    broker = BrokerFactory.create(config)

New integrated factory with profile support:
"""

from broker import BrokerSelector, BrokerValidator, get_broker_profile
from broker.broker_factory import BrokerFactory as LegacyBrokerFactory
import logging

logger = logging.getLogger(__name__)


class EnhancedBrokerFactory:
    """Enhanced factory that integrates broker classification system."""

    @staticmethod
    def create(config):
        """Create broker with profile-based validation and routing."""

        # Get broker profile from legacy config
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange=getattr(config.broker, "exchange", None),
            broker_type=getattr(config.broker, "type", None),
            customer_region=getattr(config.broker, "customer_region", None),
        )

        if not profile:
            # Fall back to legacy factory
            logger.info(
                f"No profile for {config.broker.exchange}/{config.broker.type}, "
                "using legacy factory"
            )
            return LegacyBrokerFactory.create(config)

        # Validate profile
        is_valid, msg = BrokerValidator.validate_connection(profile)
        if not is_valid:
            raise ValueError(f"Broker profile validation failed: {msg}")

        logger.info(f"Using broker profile: {profile.display_name}")

        # Create broker using legacy factory
        broker = LegacyBrokerFactory.create(config)

        # Attach profile for later reference
        broker.profile = profile

        return broker


# ============================================================================
# EXAMPLE 2: Order Validation Before Execution
# ============================================================================

"""
Updated order execution with broker profile validation.
"""

from broker import BrokerValidator, validate_broker_for_trade, AssetClass


async def execute_order(broker, symbol, side, quantity, price=None, order_type="market"):
    """
    Execute order with broker profile validation.

    Args:
        broker: Connected broker instance (now has .profile attribute)
        symbol: Trading symbol
        side: BUY or SELL
        quantity: Trade size
        price: Optional price (required for limit orders)
        order_type: market or limit
    """

    # Get broker profile
    profile = getattr(broker, "profile", None)
    if not profile:
        # Try to load profile by broker name
        profile = get_broker_profile(
            getattr(broker, "exchange_name", "paper")
        )

    # Validate broker can execute this order
    is_valid, msg = BrokerValidator.validate_order_parameters(
        profile, side=side, quantity=quantity, price=price, order_type=order_type
    )

    if not is_valid:
        logger.error(f"Order validation failed: {msg}")
        raise ValueError(f"Order validation failed: {msg}")

    # Validate symbol for this broker
    is_valid, msg = BrokerValidator.validate_symbol(profile, symbol=symbol)

    if not is_valid:
        logger.error(f"Symbol validation failed: {msg}")
        raise ValueError(f"Symbol validation failed: {msg}")

    logger.info(
        f"Order validation passed: {symbol} {side} {quantity} "
        f"on {profile.display_name}"
    )

    # Execute order
    return await broker.submit_order(symbol, side, quantity, price, order_type)


# ============================================================================
# EXAMPLE 3: Smart Broker Selection
# ============================================================================

"""
Select best broker for a specific trading requirement.
"""

from broker import route_broker_for_trade, AssetClass, MarketType


async def find_broker_for_trade(
    asset_class,
    requires_margin=False,
    requires_leverage=False,
    requires_shorting=False,
    region=None,
):
    """
    Find the best broker for a trade and return it ready to use.

    Returns:
        (primary_broker, alternative_brokers) - broker instances
    """

    # Find broker profiles matching requirements
    primary_profile, alternative_profiles = route_broker_for_trade(
        asset_class=asset_class,
        requires_margin=requires_margin,
        requires_leverage=requires_leverage,
        requires_shorting=requires_shorting,
        region=region,
    )

    if not primary_profile:
        raise ValueError(
            f"No broker found for asset_class={asset_class}, "
            f"margin={requires_margin}, leverage={requires_leverage}, "
            f"shorting={requires_shorting}, region={region}"
        )

    logger.info(f"Selected broker: {primary_profile.display_name}")

    # Create broker instances
    primary_broker = _create_broker_from_profile(primary_profile)

    alternative_brokers = [
        _create_broker_from_profile(p) for p in alternative_profiles
    ]

    return primary_broker, alternative_brokers


def _create_broker_from_profile(profile):
    """Create broker instance from profile (implementation-specific)."""
    # This would load the actual broker config and create it
    # For now, just return the profile as reference
    return profile


# ============================================================================
# EXAMPLE 4: Risk Engine Selection
# ============================================================================

"""
Automatically select risk engine based on market type.
"""

from broker import get_risk_engine_key, MarketType


def get_risk_engine_for_trade(broker_profile, market_type=None):
    """
    Get the appropriate risk engine for a trade.

    Args:
        broker_profile: BrokerProfile instance
        market_type: Optional specific market type (overrides broker default)

    Returns:
        risk_engine: Risk engine instance
    """

    # Use provided market type or broker's default
    market = market_type or broker_profile.default_market_type

    # Get risk engine key from market type
    engine_key = get_risk_engine_key(market)

    logger.info(f"Market type {market.value} -> Risk engine: {engine_key}")

    # Get risk engine instance (implementation-specific)
    # This would look up the actual risk engine by key
    risk_engine = load_risk_engine(engine_key)

    return risk_engine


# ============================================================================
# EXAMPLE 5: Position Management by Broker
# ============================================================================

"""
Different position management strategies by broker and market type.
"""

from broker import get_broker_profile, MarketType


class PositionManager:
    """Manages positions across multiple brokers with specialized logic."""

    def __init__(self):
        self.positions = {}  # symbol -> position data

    async def open_position(
        self, broker, symbol, side, quantity, market_type=None
    ):
        """
        Open position with broker-specific handling.

        Brokers with different capabilities (shorting, fractional, margin)
        need different position tracking and risk management.
        """

        profile = getattr(broker, "profile", None)
        if not profile:
            profile = get_broker_profile(getattr(broker, "exchange_name", "paper"))

        # Validate broker capabilities
        is_valid, msg = validate_broker_for_trade(
            profile,
            market_type=market_type,
            requires_shorting=(side.upper() == "SELL" and quantity > 0),
        )

        if not is_valid:
            raise ValueError(f"Cannot open position: {msg}")

        # Get position size constraints from broker profile
        position_constraints = self._get_position_constraints(profile)

        if quantity > position_constraints["max_quantity"]:
            logger.warning(
                f"Position size {quantity} exceeds max "
                f"{position_constraints['max_quantity']} on {profile.display_name}"
            )
            quantity = position_constraints["max_quantity"]

        # Execute and track
        order_result = await broker.submit_order(symbol, side, quantity)

        self.positions[symbol] = {
            "broker_id": profile.broker_id,
            "side": side,
            "quantity": quantity,
            "market_type": market_type or profile.default_market_type,
            "order_id": order_result.get("id"),
        }

        return order_result

    def _get_position_constraints(self, profile):
        """Get position size constraints based on broker capabilities."""

        constraints = {
            "max_quantity": 1000000,  # Default unlimited
            "min_quantity": 1,
            "supports_fractional": profile.supports_fractional,
            "supports_shorting": profile.supports_shorting,
            "supports_margin": profile.supports_margin,
        }

        # Broker-specific constraints
        if profile.broker_id == "alpaca":
            constraints["max_quantity"] = 10000  # Alpaca example limit
            if profile.supports_fractional:
                constraints["min_quantity"] = 0.01  # Fractional shares

        elif profile.broker_id == "oanda_us":
            constraints["max_quantity"] = 10000000  # OANDA micro lots
            constraints["min_quantity"] = 1000  # 1 micro lot

        return constraints


# ============================================================================
# EXAMPLE 6: Multi-Broker Strategy Execution
# ============================================================================

"""
Execute strategy across multiple brokers based on asset class.
"""

from broker import select_brokers, AssetClass


class MultiAssetStrategy:
    """Execute trades across different asset classes using appropriate brokers."""

    def __init__(self):
        self.brokers = {}

    async def setup_brokers(self):
        """Initialize brokers for each supported asset class."""

        asset_classes = [
            AssetClass.FOREX,
            AssetClass.CRYPTO,
            AssetClass.STOCK,
            AssetClass.FUTURES,
            AssetClass.OPTIONS,
        ]

        for asset_class in asset_classes:
            # Select best broker for this asset class
            profiles = select_brokers(asset_class=asset_class)

            if profiles:
                profile = profiles[0]  # Use primary
                logger.info(
                    f"Using {profile.display_name} for {asset_class.value}"
                )

                # Create and initialize broker
                broker = await self._create_and_connect_broker(profile)
                self.brokers[asset_class] = broker

    async def execute_trade(self, asset_class, symbol, side, quantity):
        """
        Execute trade on appropriate broker for asset class.

        Automatically routes to correct broker based on asset class,
        validates against broker capabilities, and applies appropriate
        risk management.
        """

        if asset_class not in self.brokers:
            raise ValueError(f"No broker configured for {asset_class.value}")

        broker = self.brokers[asset_class]
        profile = getattr(broker, "profile")

        # Validate
        is_valid, msg = validate_broker_for_trade(
            profile,
            asset_class=asset_class,
            requires_shorting=(side.upper() == "SELL"),
        )

        if not is_valid:
            raise ValueError(f"Trade validation failed: {msg}")

        # Execute
        logger.info(
            f"Executing {asset_class.value} trade on {profile.display_name}: "
            f"{symbol} {side} {quantity}"
        )

        return await execute_order(broker, symbol, side, quantity)

    async def _create_and_connect_broker(self, profile):
        """Create and connect broker (implementation-specific)."""
        # Implementation would load config, create broker, and connect
        pass


# ============================================================================
# EXAMPLE 7: Backward Compatibility Mode
# ============================================================================

"""
Use the new system while maintaining 100% backward compatibility.
"""


def legacy_create_broker(config):
    """
    Legacy function - still works exactly as before.

    Now internally uses the new broker classification system,
    but the API and behavior remain unchanged.
    """

    # Method 1: Just use legacy factory (no changes)
    # broker = BrokerFactory.create(config)

    # Method 2: Use enhanced factory (transparent upgrade)
    try:
        broker = EnhancedBrokerFactory.create(config)
        logger.info(f"Broker created with profile: {broker.profile.display_name}")
    except Exception as e:
        # If new system fails, fall back to legacy
        logger.warning(f"Enhanced factory failed, using legacy: {e}")
        broker = LegacyBrokerFactory.create(config)

    return broker


# ============================================================================
# EXAMPLE 8: Testing with Broker Profiles
# ============================================================================

"""
Unit test example using broker profiles.
"""


def test_margin_fx_execution():
    """Test that MARGIN_FX orders execute correctly."""

    from broker import get_broker_profile, MarketType

    oanda_us = get_broker_profile("oanda_us")

    # Verify profile
    assert oanda_us.broker_id == "oanda_us"
    assert MarketType.MARGIN_FX in oanda_us.market_types
    assert not oanda_us.is_cfd_broker

    # Validate order for MARGIN_FX
    is_valid, msg = validate_broker_for_trade(
        oanda_us, market_type=MarketType.MARGIN_FX, requires_leverage=True
    )
    assert is_valid, f"MARGIN_FX order failed: {msg}"

    # Verify risk engine routing
    risk_engine_key = get_risk_engine_key(MarketType.MARGIN_FX)
    assert risk_engine_key == "margin_fx"


def test_alpaca_margin_upgrade():
    """Test upgrading from cash to margin trading on Alpaca."""

    from broker import get_broker_profile, MarketType

    # Cash account (default)
    cash_alpaca = get_broker_profile("alpaca")
    assert not cash_alpaca.supports_margin
    assert MarketType.CASH_STOCK in cash_alpaca.market_types

    # Margin account
    margin_alpaca = get_broker_profile("alpaca_margin")
    assert margin_alpaca.supports_margin
    assert MarketType.STOCK_MARGIN in margin_alpaca.market_types


# ============================================================================
# INTEGRATION CHECKLIST
# ============================================================================

"""
When integrating the broker classification system:

☐ 1. Import the new modules:
     from broker import BrokerSelector, BrokerValidator, get_broker_profile

☐ 2. Update broker factory to use profiles (optional but recommended):
     broker.profile = get_profile_from_legacy_config(...)

☐ 3. Add profile-based validation before order execution:
     validate_broker_for_trade(broker.profile, ...)

☐ 4. Use risk engine routing:
     engine_key = get_risk_engine_key(market_type)

☐ 5. Test backward compatibility:
     Existing code should still work without changes

☐ 6. Update documentation with new capabilities

☐ 7. Run comprehensive test suite:
     pytest src/broker/tests/test_broker_classification.py -v

☐ 8. Monitor logs for:
     - "Using broker profile: X" (successful integration)
     - "No profile for X/Y" (falling back to legacy)

Important: The new system is fully backward compatible. Gradual migration
is possible - add profiles to new code while legacy code continues to work.
"""
