"""Market Classifier Integration with Order Validation & Execution.

This module integrates the market classification system with order validation
and execution to ensure only valid orders are submitted to brokers.

The classifier provides deterministic market information that enables
comprehensive validation of order parameters, settlement methods, and
execution constraints before submission.
"""

from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from domain.market import (
    MarketClassifier,
    MarketDescriptor,
    InstrumentType,
    MarketType,
    Venue,
    TradingMode,
    SettlementType,
)


logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Order specification with full parameters.
    
    Attributes:
        symbol: Trading symbol
        venue: Venue enum
        quantity: Order quantity
        price: Order price (None for market orders)
        side: "BUY" or "SELL"
        order_type: "MARKET", "LIMIT", "STOP", "STOP_LIMIT"
        time_in_force: "GTC", "IOC", "FOK", "DAY", "GTD"
        stop_price: Stop price for stop orders
        post_only: Only post as maker order
        reduce_only: Only reduce existing position (for derivatives)
        expires_at: Expiration datetime (for GTD orders)
    """
    symbol: str
    venue: Venue
    quantity: float
    price: Optional[float] = None
    side: str = "BUY"
    order_type: str = "MARKET"
    time_in_force: str = "GTC"
    stop_price: Optional[float] = None
    post_only: bool = False
    reduce_only: bool = False
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    
    def __post_init__(self):
        """Normalize order fields."""
        self.symbol = str(self.symbol or "").strip().upper()
        self.side = str(self.side or "BUY").strip().upper()
        self.order_type = str(self.order_type or "MARKET").strip().upper()
        self.time_in_force = str(self.time_in_force or "GTC").strip().upper()


class OrderValidationError(Exception):
    """Raised when order validation fails."""
    pass


class OrderValidator:
    """Validates orders against market classification and broker rules.
    
    Features:
    - Instrument-specific validation
    - Price/quantity constraints
    - Expiration validation
    - Leverage constraints
    - Settlement type validation
    - Venue-specific rules
    
    Example:
        validator = OrderValidator()
        
        order = Order("BTC-USD", Venue.COINBASE, 0.5, 45000, "BUY", "LIMIT")
        validator.validate(order)  # Raises if invalid
        
        # Get validation report
        report = validator.validate_with_report(order)
        if not report.is_valid:
            print(f"Validation failed: {report.errors}")
    """
    
    def __init__(self):
        """Initialize order validator with classifier."""
        self.classifier = MarketClassifier()
        self.max_order_value_usd = 1_000_000.0
        self.min_order_value_usd = 10.0
        
    def validate(self, order: Order) -> bool:
        """Validate an order, raising exception if invalid.
        
        Args:
            order: Order object to validate
            
        Returns:
            True if valid
            
        Raises:
            OrderValidationError if validation fails
        """
        descriptor = self.classifier.classify(order.symbol, order.venue)
        
        # Check if symbol is tradable
        if not descriptor.tradable:
            raise OrderValidationError(f"Symbol {order.symbol} is not tradable on {order.venue.value}")
        
        # Basic order parameters
        if order.quantity <= 0:
            raise OrderValidationError(f"Order quantity must be positive, got {order.quantity}")
        
        if order.side not in {"BUY", "SELL"}:
            raise OrderValidationError(f"Invalid order side '{order.side}', must be BUY or SELL")
        
        if order.order_type not in {"MARKET", "LIMIT", "STOP", "STOP_LIMIT"}:
            raise OrderValidationError(f"Invalid order type '{order.order_type}'")
        
        # Price validation for limit/stop orders
        if order.order_type in {"LIMIT", "STOP_LIMIT"}:
            if order.price is None or order.price <= 0:
                raise OrderValidationError(f"Limit orders require positive price, got {order.price}")
        
        if order.order_type in {"STOP", "STOP_LIMIT"}:
            if order.stop_price is None or order.stop_price <= 0:
                raise OrderValidationError(f"Stop orders require positive stop price, got {order.stop_price}")
        
        # Validate against descriptor constraints
        self._validate_against_descriptor(order, descriptor)
        
        # Validate order timing
        self._validate_order_timing(order, descriptor)
        
        # Validate settlement compatibility
        self._validate_settlement(order, descriptor)
        
        return True
    
    def validate_with_report(self, order: Order) -> "ValidationReport":
        """Validate an order and return a detailed report.
        
        Args:
            order: Order object to validate
            
        Returns:
            ValidationReport with results and recommendations
        """
        report = ValidationReport()
        
        try:
            descriptor = self.classifier.classify(order.symbol, order.venue)
            report.descriptor = descriptor
            
            # Check if symbol is tradable
            if not descriptor.tradable:
                report.add_error(f"Symbol {order.symbol} is not tradable")
                return report
            
            # Validate basic parameters
            if order.quantity <= 0:
                report.add_error(f"Order quantity must be positive")
            
            if order.side not in {"BUY", "SELL"}:
                report.add_error(f"Invalid order side")
            
            if order.order_type not in {"MARKET", "LIMIT", "STOP", "STOP_LIMIT"}:
                report.add_error(f"Invalid order type")
            
            # Price validation
            if order.order_type in {"LIMIT", "STOP_LIMIT"} and order.price is None:
                report.add_error("Limit orders require a price")
            
            if order.order_type in {"STOP", "STOP_LIMIT"} and order.stop_price is None:
                report.add_error("Stop orders require a stop price")
            
            # Validate against descriptor
            try:
                self._validate_against_descriptor(order, descriptor)
            except OrderValidationError as e:
                report.add_error(str(e))
            
            # Validate timing
            try:
                self._validate_order_timing(order, descriptor)
            except OrderValidationError as e:
                report.add_error(str(e))
            
            # Validate settlement
            try:
                self._validate_settlement(order, descriptor)
            except OrderValidationError as e:
                report.add_error(str(e))
            
            # Generate recommendations
            self._generate_recommendations(report, descriptor)
            
        except Exception as e:
            report.add_error(f"Unexpected validation error: {e}")
            logger.exception(f"Error validating order: {e}")
        
        return report
    
    def _validate_against_descriptor(self, order: Order, descriptor: MarketDescriptor) -> None:
        """Validate order against classified market descriptor.
        
        Args:
            order: Order object
            descriptor: MarketDescriptor
            
        Raises:
            OrderValidationError if validation fails
        """
        # Check short selling
        if order.side == "SELL" and not descriptor.shortable:
            raise OrderValidationError(
                f"Short selling not allowed for {descriptor.symbol} on {descriptor.venue.value}"
            )
        
        # Check leverage
        if descriptor.leveraged and order.order_type == "MARKET":
            logger.warning(f"Market order with leverage on {descriptor.symbol} may have slippage")
        
        # Check reduce-only for spot markets
        if order.reduce_only and descriptor.is_spot:
            raise OrderValidationError(
                f"Reduce-only orders not supported for spot markets like {descriptor.symbol}"
            )
        
        # Check post-only for market orders
        if order.post_only and order.order_type == "MARKET":
            raise OrderValidationError("Post-only not valid for market orders")
        
        # Check order type support per venue type
        if descriptor.venue_type.is_blockchain_native:
            if order.order_type not in {"MARKET", "LIMIT"}:
                raise OrderValidationError(
                    f"Order type {order.order_type} not supported on blockchain venues"
                )
    
    def _validate_order_timing(self, order: Order, descriptor: MarketDescriptor) -> None:
        """Validate order expiration and timing.
        
        Args:
            order: Order object
            descriptor: MarketDescriptor
            
        Raises:
            OrderValidationError if validation fails
        """
        # Check GTD expiration
        if order.time_in_force == "GTD":
            if order.expires_at is None:
                raise OrderValidationError("GTD orders require expires_at")
            
            now = datetime.now(timezone.utc)
            if order.expires_at <= now:
                raise OrderValidationError("Order expiration must be in the future")
            
            # Max 90 days
            if (order.expires_at - now).days > 90:
                raise OrderValidationError("Order expiration cannot exceed 90 days")
        
        # DAY orders only valid on market hours (simplified)
        if order.time_in_force == "DAY":
            if descriptor.is_crypto or descriptor.is_forex:
                logger.warning("DAY time in force not applicable to 24/7 markets")
    
    def _validate_settlement(self, order: Order, descriptor: MarketDescriptor) -> None:
        """Validate order settlement compatibility.
        
        Args:
            order: Order object
            descriptor: MarketDescriptor
            
        Raises:
            OrderValidationError if validation fails
        """
        # Perpetual orders must use reduce-only or position sizing
        if descriptor.settlement_type == SettlementType.PERPETUAL:
            if not descriptor.is_perpetual:
                raise OrderValidationError("Perpetual settlement type mismatch")
        
        # Physical settlement products (commodities, bonds)
        if descriptor.settlement_type == SettlementType.PHYSICAL:
            if descriptor.is_derivative:
                raise OrderValidationError("Derivative products cannot have physical settlement")
    
    def _generate_recommendations(self, report: "ValidationReport", descriptor: MarketDescriptor) -> None:
        """Generate recommendations based on market descriptor.
        
        Args:
            report: ValidationReport to add recommendations to
            descriptor: MarketDescriptor
        """
        # Recommend limit orders for volatile markets
        if descriptor.is_perpetual and descriptor.is_crypto:
            report.add_recommendation("Consider limit orders for better pricing on perpetual futures")
        
        # Recommend stop losses for derivatives
        if descriptor.is_derivative:
            report.add_recommendation("Use stop losses to limit downside risk on derivatives")
        
        # Warn about funding rates on perpetuals
        if descriptor.is_perpetual:
            report.add_recommendation("Review funding rates before holding perpetual positions")
        
        # Recommend order batching for large orders
        if descriptor.market_route.is_blockchain_native:
            report.add_recommendation("Consider order batching to reduce on-chain transaction costs")


class ValidationReport:
    """Detailed order validation report.
    
    Attributes:
        is_valid: True if order passed all validations
        errors: List of validation errors
        warnings: List of validation warnings
        recommendations: List of recommendations
        descriptor: Classified MarketDescriptor
    """
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []
        self.descriptor: Optional[MarketDescriptor] = None
    
    @property
    def is_valid(self) -> bool:
        """Return True if order is valid (no errors)."""
        return len(self.errors) == 0
    
    def add_error(self, message: str) -> None:
        """Add a validation error."""
        self.errors.append(message)
        logger.debug(f"Validation error: {message}")
    
    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)
        logger.warning(f"Validation warning: {message}")
    
    def add_recommendation(self, message: str) -> None:
        """Add a recommendation."""
        self.recommendations.append(message)
    
    def summary(self) -> Dict[str, Any]:
        """Get a summary of the validation report.
        
        Returns:
            Dict with validation results
        """
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "recommendation_count": len(self.recommendations),
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "symbol": self.descriptor.symbol if self.descriptor else None,
            "market_type": self.descriptor.market_type.value if self.descriptor else None,
            "asset_class": self.descriptor.asset_class.value if self.descriptor else None,
        }


# Default global order validator instance
_default_validator: Optional[OrderValidator] = None


def get_default_validator() -> OrderValidator:
    """Get or create the default global order validator.
    
    Returns:
        OrderValidator instance
    """
    global _default_validator
    if _default_validator is None:
        _default_validator = OrderValidator()
    return _default_validator


def set_default_validator(validator: OrderValidator) -> None:
    """Set the default global order validator.
    
    Args:
        validator: OrderValidator instance
    """
    global _default_validator
    _default_validator = validator
