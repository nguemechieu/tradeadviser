"""Market Classifier Integration with Risk Engine.

This module integrates the market classification system with the risk engine
to apply asset-class-based risk limits, position sizing constraints, and
risk monitoring rules.

The classifier provides deterministic asset class assignment that enables
the risk engine to apply consistent, portfolio-aware risk management.
"""

from typing import Optional, Dict, Any, Tuple
import logging

from domain.market import (
    MarketClassifier,
    MarketDescriptor,
    AssetClass,
    MarketType,
    InstrumentType,
    Venue,
    TradingMode,
)


logger = logging.getLogger(__name__)


class RiskLimits:
    """Asset-class-based risk limit configuration.
    
    Defines position sizing, margin, and exposure constraints per asset class.
    
    Attributes:
        max_position_size_pct: Max single position as % of portfolio
        max_asset_class_exposure_pct: Max total exposure to asset class as % of portfolio
        max_gross_exposure_pct: Max total gross exposure as % of portfolio
        max_leverage: Maximum allowed leverage for this asset class
        min_days_to_hold: Minimum holding period (days)
        max_days_to_hold: Maximum holding period (days)
        requires_stop_loss: Whether stop loss is mandatory
        requires_take_profit: Whether take profit target is mandatory
        daily_loss_limit_pct: Maximum daily loss limit as % of portfolio
    """
    
    def __init__(
        self,
        max_position_size_pct: float = 0.10,
        max_asset_class_exposure_pct: float = 0.30,
        max_gross_exposure_pct: float = 1.00,
        max_leverage: float = 1.0,
        min_days_to_hold: float = 0.0,
        max_days_to_hold: float = 365.0,
        requires_stop_loss: bool = False,
        requires_take_profit: bool = False,
        daily_loss_limit_pct: float = 0.05,
    ):
        self.max_position_size_pct = max_position_size_pct
        self.max_asset_class_exposure_pct = max_asset_class_exposure_pct
        self.max_gross_exposure_pct = max_gross_exposure_pct
        self.max_leverage = max_leverage
        self.min_days_to_hold = min_days_to_hold
        self.max_days_to_hold = max_days_to_hold
        self.requires_stop_loss = requires_stop_loss
        self.requires_take_profit = requires_take_profit
        self.daily_loss_limit_pct = daily_loss_limit_pct


class RiskEngineLimits:
    """Risk engine with market classification integration.
    
    Features:
    - Asset-class-based position limits
    - Automatic position sizing
    - Margin utilization tracking
    - Daily loss monitoring
    - Leverage constraints
    - Trade duration limits
    
    Example:
        risk_engine = RiskEngineLimits()
        risk_engine.set_asset_class_limits(AssetClass.CRYPTO_ASSET, limits)
        
        descriptor = classifier.classify("BTC-USD", Venue.COINBASE)
        max_size = risk_engine.get_max_position_size(descriptor, portfolio_value=100000)
        risk_engine.validate_order(descriptor, order_quantity=0.5, order_price=45000)
    """
    
    # Default risk limits per asset class
    DEFAULT_LIMITS: Dict[AssetClass, RiskLimits] = {
        AssetClass.CRYPTO_ASSET: RiskLimits(
            max_position_size_pct=0.15,          # 15% max per position
            max_asset_class_exposure_pct=0.40,   # 40% max crypto exposure
            max_gross_exposure_pct=1.50,         # 150% max gross
            max_leverage=3.0,                    # Up to 3x leverage
            requires_stop_loss=False,
            daily_loss_limit_pct=0.10,           # 10% daily loss limit
        ),
        AssetClass.FIAT_CURRENCY: RiskLimits(
            max_position_size_pct=0.10,          # 10% max per position
            max_asset_class_exposure_pct=0.30,   # 30% max FX exposure
            max_gross_exposure_pct=1.00,         # 100% max gross
            max_leverage=10.0,                   # Up to 10x leverage (forex typical)
            requires_stop_loss=True,
            daily_loss_limit_pct=0.05,           # 5% daily loss limit
        ),
        AssetClass.EQUITY: RiskLimits(
            max_position_size_pct=0.08,          # 8% max per position
            max_asset_class_exposure_pct=0.50,   # 50% max equity exposure
            max_gross_exposure_pct=2.00,         # 200% max gross
            max_leverage=2.0,                    # Up to 2x leverage
            min_days_to_hold=0.0,
            max_days_to_hold=365.0,
            requires_stop_loss=False,
            daily_loss_limit_pct=0.03,           # 3% daily loss limit
        ),
        AssetClass.DERIVATIVE: RiskLimits(
            max_position_size_pct=0.10,          # 10% max per position
            max_asset_class_exposure_pct=0.25,   # 25% max derivative exposure
            max_gross_exposure_pct=0.50,         # 50% max gross
            max_leverage=5.0,                    # Up to 5x leverage
            requires_stop_loss=True,
            requires_take_profit=True,
            daily_loss_limit_pct=0.08,           # 8% daily loss limit
        ),
        AssetClass.COMMODITY: RiskLimits(
            max_position_size_pct=0.05,          # 5% max per position
            max_asset_class_exposure_pct=0.20,   # 20% max commodity exposure
            max_gross_exposure_pct=0.75,         # 75% max gross
            max_leverage=2.0,
            requires_stop_loss=True,
            daily_loss_limit_pct=0.04,           # 4% daily loss limit
        ),
        AssetClass.FIXED_INCOME: RiskLimits(
            max_position_size_pct=0.12,          # 12% max per position
            max_asset_class_exposure_pct=0.60,   # 60% max bond exposure
            max_gross_exposure_pct=2.00,         # 200% max gross
            max_leverage=1.5,
            min_days_to_hold=30.0,               # 30-day minimum hold
            daily_loss_limit_pct=0.02,           # 2% daily loss limit
        ),
        AssetClass.CASH: RiskLimits(
            max_position_size_pct=1.0,           # 100% allowed (cash positions)
            max_asset_class_exposure_pct=1.0,    # No limit for cash
            max_gross_exposure_pct=1.0,          # Cash counts 1:1
            max_leverage=1.0,                    # No leverage on cash
            daily_loss_limit_pct=0.0,            # No loss possible (cash)
        ),
        AssetClass.SYNTHETIC: RiskLimits(
            max_position_size_pct=0.05,          # 5% max per position
            max_asset_class_exposure_pct=0.15,   # 15% max synthetic exposure
            max_gross_exposure_pct=0.30,         # 30% max gross
            max_leverage=2.0,
            requires_stop_loss=True,
            daily_loss_limit_pct=0.10,           # 10% daily loss limit
        ),
    }
    
    def __init__(self):
        """Initialize risk engine with default limits and classifier."""
        self.classifier = MarketClassifier()
        self.limits: Dict[AssetClass, RiskLimits] = dict(self.DEFAULT_LIMITS)
        self.portfolio_value = 0.0
        self.current_positions: Dict[str, float] = {}  # symbol -> position value
        self.daily_loss = 0.0
        self.daily_loss_start_time = None
        
    def set_asset_class_limits(self, asset_class: AssetClass, limits: RiskLimits) -> None:
        """Set custom risk limits for an asset class.
        
        Args:
            asset_class: AssetClass enum value
            limits: RiskLimits instance with custom configuration
        """
        if not isinstance(asset_class, AssetClass):
            raise TypeError(f"asset_class must be AssetClass, got {type(asset_class)}")
        if not isinstance(limits, RiskLimits):
            raise TypeError(f"limits must be RiskLimits, got {type(limits)}")
        
        self.limits[asset_class] = limits
        logger.debug(f"Updated limits for {asset_class.value}")
    
    def set_portfolio_value(self, value: float) -> None:
        """Set current portfolio value for calculating position limits.
        
        Args:
            value: Current total portfolio value
        """
        if value < 0:
            raise ValueError(f"Portfolio value must be non-negative, got {value}")
        self.portfolio_value = value
        
    def get_limits_for_descriptor(self, descriptor: MarketDescriptor) -> RiskLimits:
        """Get risk limits for a classified symbol.
        
        Args:
            descriptor: MarketDescriptor from classification
            
        Returns:
            RiskLimits instance for this symbol's asset class
        """
        limits = self.limits.get(descriptor.asset_class)
        if limits is None:
            logger.warning(f"No limits defined for {descriptor.asset_class.value}, using crypto defaults")
            limits = self.limits[AssetClass.CRYPTO_ASSET]
        return limits
    
    def get_max_position_size(
        self,
        descriptor: MarketDescriptor,
        portfolio_value: Optional[float] = None,
    ) -> float:
        """Calculate maximum position size for a symbol.
        
        Args:
            descriptor: MarketDescriptor from classification
            portfolio_value: Override portfolio value (uses self.portfolio_value if None)
            
        Returns:
            Maximum position value in base currency
        """
        value = portfolio_value if portfolio_value is not None else self.portfolio_value
        if value <= 0:
            logger.warning("Portfolio value is zero or negative, cannot calculate position size")
            return 0.0
        
        limits = self.get_limits_for_descriptor(descriptor)
        max_position = value * limits.max_position_size_pct
        
        return max_position
    
    def get_max_position_quantity(
        self,
        descriptor: MarketDescriptor,
        entry_price: float,
        portfolio_value: Optional[float] = None,
    ) -> float:
        """Calculate maximum position quantity for a symbol at a given price.
        
        Args:
            descriptor: MarketDescriptor from classification
            entry_price: Entry price for the position
            portfolio_value: Override portfolio value
            
        Returns:
            Maximum quantity to trade
        """
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        
        max_position_value = self.get_max_position_size(descriptor, portfolio_value)
        max_quantity = max_position_value / entry_price
        
        # Apply leverage limits
        limits = self.get_limits_for_descriptor(descriptor)
        if limits.max_leverage < 1.0:
            max_quantity *= limits.max_leverage
        
        return max_quantity
    
    def validate_order(
        self,
        descriptor: MarketDescriptor,
        quantity: float,
        entry_price: float,
        order_type: str = "MARKET",
    ) -> Tuple[bool, str]:
        """Validate an order against risk limits.
        
        Args:
            descriptor: MarketDescriptor from classification
            quantity: Order quantity
            entry_price: Entry price
            order_type: Order type (MARKET, LIMIT, STOP, etc.)
            
        Returns:
            Tuple[bool, str] - (is_valid, error_message)
        """
        try:
            limits = self.get_limits_for_descriptor(descriptor)
            
            # Check position size
            max_quantity = self.get_max_position_quantity(descriptor, entry_price)
            if quantity > max_quantity:
                return False, f"Order quantity {quantity} exceeds max {max_quantity:.4f}"
            
            # Check leverage requirements
            if descriptor.leveraged and limits.max_leverage < 1.1:
                return False, f"Leverage not allowed for {descriptor.asset_class.value}"
            
            # Check short selling
            if descriptor.is_derivative and not descriptor.shortable:
                return False, f"Short selling not allowed for {descriptor.symbol}"
            
            # Check daily loss limit
            if self.daily_loss >= self.portfolio_value * limits.daily_loss_limit_pct:
                return False, f"Daily loss limit reached ({self.daily_loss:.2f} / {self.portfolio_value * limits.daily_loss_limit_pct:.2f})"
            
            # Check stop loss requirement
            if limits.requires_stop_loss and order_type not in {"STOP", "STOP_LIMIT"}:
                logger.warning(f"Stop loss recommended for {descriptor.symbol}")
            
            # Check take profit requirement
            if limits.requires_take_profit and order_type != "LIMIT":
                logger.warning(f"Take profit recommended for {descriptor.symbol}")
            
            return True, ""
            
        except Exception as e:
            logger.exception(f"Error validating order for {descriptor.symbol}: {e}")
            return False, str(e)
    
    def get_risk_metrics(self, descriptor: MarketDescriptor) -> Dict[str, Any]:
        """Get comprehensive risk metrics for a symbol.
        
        Args:
            descriptor: MarketDescriptor from classification
            
        Returns:
            Dict with risk metrics and constraints
        """
        limits = self.get_limits_for_descriptor(descriptor)
        max_position = self.get_max_position_size(descriptor)
        
        return {
            "symbol": descriptor.symbol,
            "asset_class": descriptor.asset_class.value,
            "market_type": descriptor.market_type.value,
            "max_position_size_pct": limits.max_position_size_pct,
            "max_position_value": max_position,
            "max_leverage": limits.max_leverage,
            "requires_stop_loss": limits.requires_stop_loss,
            "requires_take_profit": limits.requires_take_profit,
            "daily_loss_limit_pct": limits.daily_loss_limit_pct,
            "daily_loss_limit_value": self.portfolio_value * limits.daily_loss_limit_pct,
            "current_daily_loss": self.daily_loss,
            "portfolio_value": self.portfolio_value,
        }


# Default global risk engine instance
_default_risk_engine: Optional[RiskEngineLimits] = None


def get_default_risk_engine() -> RiskEngineLimits:
    """Get or create the default global risk engine.
    
    Returns:
        RiskEngineLimits instance
    """
    global _default_risk_engine
    if _default_risk_engine is None:
        _default_risk_engine = RiskEngineLimits()
    return _default_risk_engine


def set_default_risk_engine(engine: RiskEngineLimits) -> None:
    """Set the default global risk engine.
    
    Args:
        engine: RiskEngineLimits instance
    """
    global _default_risk_engine
    _default_risk_engine = engine
