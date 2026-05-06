"""Market Classifier Integration with Broker Router.

This module integrates the market classification system with the broker router
to automatically select the correct broker handler based on market type,
instrument type, and venue classification.

The classifier provides deterministic, type-safe market classification that
enables the router to make routing decisions without hard-coded venue logic.
"""

from typing import Optional, Dict, Any, Callable, Type
import logging

from domain.market import (
    MarketClassifier,
    MarketDescriptor,
    MarketType,
    InstrumentType,
    Venue,
    VenueType,
    AssetClass,
    TradingMode,
    SettlementType,
    MarketRoute,
)
from broker.base_broker import BaseBroker


logger = logging.getLogger(__name__)


class BrokerRouter:
    """Routes trading symbols to the correct broker handler using market classification.
    
    This router uses the MarketClassifier to deterministically classify each symbol,
    then routes to the appropriate broker based on market type, instrument type,
    venue, and trading mode.
    
    Features:
    - Type-safe routing decisions using enums
    - Deterministic classification (same symbol → same route)
    - Extensible handler registry
    - Fallback handling for unknown symbols
    - Support for multi-venue trading
    
    Example:
        router = BrokerRouter()
        router.register_handler(MarketRoute.CRYPTO_SPOT_CEX, crypto_spot_handler)
        
        handler = router.route("BTC-USD", Venue.COINBASE)
        result = handler.execute_trade(descriptor, order)
    """
    
    def __init__(self):
        """Initialize broker router with market classifier."""
        self.classifier = MarketClassifier()
        self.handlers: Dict[MarketRoute, BaseBroker] = {}
        self.venue_handlers: Dict[Venue, BaseBroker] = {}
        self.fallback_handler: Optional[BaseBroker] = None
        self._handler_cache: Dict[str, BaseBroker] = {}
        
    def register_handler(self, route: MarketRoute, handler: BaseBroker) -> None:
        """Register a broker handler for a specific market route.
        
        Args:
            route: MarketRoute enum value (CRYPTO_SPOT_CEX, FOREX_MARGIN_BROKER, etc.)
            handler: BaseBroker instance to handle trades for this route
        """
        if not isinstance(route, MarketRoute):
            raise TypeError(f"route must be MarketRoute, got {type(route)}")
        if not isinstance(handler, BaseBroker):
            raise TypeError(f"handler must be BaseBroker, got {type(handler)}")
        
        self.handlers[route] = handler
        logger.debug(f"Registered handler for route {route.value}: {handler.__class__.__name__}")
        
    def register_venue_handler(self, venue: Venue, handler: BaseBroker) -> None:
        """Register a broker handler for a specific venue.
        
        Args:
            venue: Venue enum value (COINBASE, ALPACA, OANDA, etc.)
            handler: BaseBroker instance for this venue
        """
        if not isinstance(venue, Venue):
            raise TypeError(f"venue must be Venue, got {type(venue)}")
        if not isinstance(handler, BaseBroker):
            raise TypeError(f"handler must be BaseBroker, got {type(handler)}")
        
        self.venue_handlers[venue] = handler
        logger.debug(f"Registered handler for venue {venue.value}: {handler.__class__.__name__}")
        
    def set_fallback_handler(self, handler: Optional[BaseBroker]) -> None:
        """Set the fallback handler for unknown symbols.
        
        Args:
            handler: BaseBroker instance or None to clear fallback
        """
        if handler is not None and not isinstance(handler, BaseBroker):
            raise TypeError(f"handler must be BaseBroker or None, got {type(handler)}")
        
        self.fallback_handler = handler
        logger.debug(f"Set fallback handler: {handler.__class__.__name__ if handler else 'None'}")
        
    def route(
        self,
        symbol: str,
        venue: Venue,
        trading_mode: TradingMode = TradingMode.LIVE,
    ) -> Optional[BaseBroker]:
        """Route a symbol to the appropriate broker handler.
        
        This method classifies the symbol using the market classifier, then
        selects the appropriate handler based on:
        1. Market route (primary decision)
        2. Venue handler (secondary fallback)
        3. Fallback handler (tertiary fallback)
        
        Args:
            symbol: Trading symbol (e.g., "BTC-USD", "EUR/USD", "AAPL")
            venue: Venue enum value
            trading_mode: TradingMode enum value (default LIVE)
            
        Returns:
            BaseBroker instance for this symbol, or None if no handler found
            
        Example:
            handler = router.route("BTC-USD", Venue.COINBASE)
            if handler:
                await handler.execute_trade(symbol, order)
        """
        # Check cache first
        cache_key = f"{symbol}:{venue.value}:{trading_mode.value}"
        if cache_key in self._handler_cache:
            return self._handler_cache[cache_key]
        
        try:
            # Classify the symbol
            descriptor = self.classifier.classify(symbol, venue, trading_mode)
            
            if not descriptor.tradable:
                logger.warning(f"Symbol {symbol} on {venue.value} is not tradable")
                handler = self.fallback_handler
            else:
                # Route by market route (primary)
                handler = self.handlers.get(descriptor.market_route)
                
                # Fallback to venue handler (secondary)
                if handler is None:
                    handler = self.venue_handlers.get(venue)
                
                # Fallback to global fallback (tertiary)
                if handler is None:
                    handler = self.fallback_handler
            
            # Cache the result
            if handler is not None:
                self._handler_cache[cache_key] = handler
                logger.debug(
                    f"Routed {symbol} on {venue.value} via {descriptor.market_route.value} "
                    f"to {handler.__class__.__name__}"
                )
            
            return handler
            
        except Exception as e:
            logger.exception(f"Error routing {symbol} on {venue.value}: {e}")
            return self.fallback_handler
    
    def route_descriptor(self, descriptor: MarketDescriptor) -> Optional[BaseBroker]:
        """Route using a pre-classified descriptor.
        
        Useful when you already have a MarketDescriptor and want to avoid
        re-classification.
        
        Args:
            descriptor: MarketDescriptor from previous classification
            
        Returns:
            BaseBroker instance for this descriptor
        """
        if not isinstance(descriptor, MarketDescriptor):
            raise TypeError(f"descriptor must be MarketDescriptor, got {type(descriptor)}")
        
        if not descriptor.tradable:
            logger.warning(f"Symbol {descriptor.symbol} is not tradable")
            return self.fallback_handler
        
        # Route by market route (primary)
        handler = self.handlers.get(descriptor.market_route)
        
        # Fallback to venue handler (secondary)
        if handler is None:
            handler = self.venue_handlers.get(descriptor.venue)
        
        # Fallback to global fallback (tertiary)
        if handler is None:
            handler = self.fallback_handler
        
        if handler is not None:
            logger.debug(
                f"Routed descriptor {descriptor.symbol} via {descriptor.market_route.value} "
                f"to {handler.__class__.__name__}"
            )
        
        return handler
    
    def get_descriptor(
        self,
        symbol: str,
        venue: Venue,
        trading_mode: TradingMode = TradingMode.LIVE,
    ) -> MarketDescriptor:
        """Classify and return a descriptor for a symbol.
        
        Args:
            symbol: Trading symbol
            venue: Venue enum value
            trading_mode: TradingMode enum value
            
        Returns:
            MarketDescriptor with complete market information
        """
        return self.classifier.classify(symbol, venue, trading_mode)
    
    def clear_cache(self) -> None:
        """Clear the routing decision cache.
        
        Useful after registering new handlers or rebalancing routes.
        """
        self._handler_cache.clear()
        logger.debug("Cleared broker router cache")


class MultiVenueRouter:
    """Routes orders across multiple venues based on market type and strategy.
    
    This router extends BrokerRouter to support:
    - Multiple venues for the same symbol (order splitting)
    - Venue selection based on execution quality metrics
    - Fallback venue selection
    - Rebate-aware venue selection
    
    Example:
        router = MultiVenueRouter()
        router.register_venue_handler(Venue.COINBASE, coinbase_handler)
        router.register_venue_handler(Venue.BINANCE, binance_handler)
        
        # Get best venue for a symbol
        handler = router.route_by_quality("BTC-USD", MarketType.CRYPTO)
    """
    
    def __init__(self):
        """Initialize multi-venue router."""
        self.broker_router = BrokerRouter()
        self.venue_quality_metrics: Dict[Venue, Dict[str, Any]] = {}
        
    def register_venue_handler(self, venue: Venue, handler: BaseBroker) -> None:
        """Register handler for a specific venue."""
        self.broker_router.register_venue_handler(venue, handler)
        
    def register_handler(self, route: MarketRoute, handler: BaseBroker) -> None:
        """Register handler for a market route."""
        self.broker_router.register_handler(route, handler)
    
    def set_venue_quality_metrics(
        self,
        venue: Venue,
        metrics: Dict[str, Any],
    ) -> None:
        """Set quality metrics for a venue (latency, fees, rebates, etc.).
        
        Args:
            venue: Venue enum value
            metrics: Dict with keys like 'latency_ms', 'maker_fee', 'taker_fee', 'rebate_pct'
        """
        self.venue_quality_metrics[venue] = metrics
        logger.debug(f"Updated quality metrics for {venue.value}: {metrics}")
    
    def route_by_quality(
        self,
        symbol: str,
        market_type: MarketType,
    ) -> Optional[BaseBroker]:
        """Route to venue with best execution quality for a market type.
        
        Selects venue based on:
        1. Latency (lower is better)
        2. Maker fees (lower is better for limit orders)
        3. Taker fees (lower is better for market orders)
        4. Rebates (higher is better)
        
        Args:
            symbol: Trading symbol
            market_type: MarketType enum value
            
        Returns:
            BaseBroker instance for best-quality venue
        """
        try:
            # Find all venues supporting this market type
            suitable_venues = [
                venue for venue, metrics in self.venue_quality_metrics.items()
                if metrics.get("supports_market_type", market_type) == market_type
            ]
            
            if not suitable_venues:
                logger.warning(f"No venues support {market_type.value}")
                return None
            
            # Score each venue (lower is better)
            scored_venues = []
            for venue in suitable_venues:
                metrics = self.venue_quality_metrics.get(venue, {})
                
                # Quality score = latency + fees - rebates
                latency = metrics.get("latency_ms", 100)
                maker_fee = metrics.get("maker_fee", 0.0005)  # 0.05%
                taker_fee = metrics.get("taker_fee", 0.001)   # 0.1%
                rebate = metrics.get("rebate_pct", 0.0)
                
                # Normalize to comparable units
                fee_score = (maker_fee + taker_fee) * 10000  # Convert to basis points
                rebate_score = rebate * 10000
                
                # Total score (lower is better)
                score = latency + fee_score - rebate_score
                
                scored_venues.append((venue, score))
            
            # Sort by score and return handler for best venue
            best_venue = min(scored_venues, key=lambda x: x[1])[0]
            
            descriptor = self.broker_router.get_descriptor(symbol, best_venue)
            handler = self.broker_router.route_descriptor(descriptor)
            
            if handler is not None:
                logger.debug(f"Routed {symbol} to {best_venue.value} by quality metrics")
            
            return handler
            
        except Exception as e:
            logger.exception(f"Error routing by quality: {e}")
            return None


# Default global router instance
_default_router: Optional[BrokerRouter] = None


def get_default_router() -> BrokerRouter:
    """Get or create the default global broker router.
    
    Returns:
        BrokerRouter instance
    """
    global _default_router
    if _default_router is None:
        _default_router = BrokerRouter()
    return _default_router


def set_default_router(router: BrokerRouter) -> None:
    """Set the default global broker router.
    
    Args:
        router: BrokerRouter instance
    """
    global _default_router
    _default_router = router
