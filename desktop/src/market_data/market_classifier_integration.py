"""Market Classifier Integration with WebSocket Manager.

This module integrates the market classification system with the WebSocket
manager to subscribe to appropriate market data streams based on instrument
type, market type, and trading mode.

The classifier provides deterministic instrument classification that enables
the WebSocket manager to select optimal data stream subscriptions without
hard-coded symbol parsing logic.
"""

from typing import Optional, Dict, List, Set, Any, Callable
import logging
from enum import Enum

from domain.market import (
    MarketClassifier,
    MarketDescriptor,
    InstrumentType,
    MarketType,
    MarketDataType,
    Venue,
    TradingMode,
)


logger = logging.getLogger(__name__)


class StreamPriority(str, Enum):
    """Priority level for WebSocket subscriptions."""
    CRITICAL = "critical"      # Must have for trading
    HIGH = "high"              # Important for decision making
    NORMAL = "normal"          # Standard data stream
    LOW = "low"                # Nice to have
    OPTIONAL = "optional"      # Only if bandwidth available


class DataStreamSubscription:
    """Represents a subscription to a market data stream.
    
    Attributes:
        symbol: Trading symbol
        data_type: MarketDataType enum
        priority: StreamPriority enum
        interval: Update interval in seconds (for candles)
        depth: Order book depth (for order book data)
    """
    
    def __init__(
        self,
        symbol: str,
        data_type: MarketDataType,
        priority: StreamPriority = StreamPriority.NORMAL,
        interval: Optional[float] = None,
        depth: Optional[int] = None,
    ):
        self.symbol = symbol
        self.data_type = data_type
        self.priority = priority
        self.interval = interval
        self.depth = depth
        
    def __hash__(self):
        return hash((self.symbol, self.data_type.value, self.interval))
    
    def __eq__(self, other):
        if not isinstance(other, DataStreamSubscription):
            return False
        return (
            self.symbol == other.symbol
            and self.data_type == other.data_type
            and self.interval == other.interval
        )
    
    def __repr__(self):
        return f"DataStreamSubscription({self.symbol}, {self.data_type.value}, {self.priority.value})"


class WebSocketDataManager:
    """Manages WebSocket subscriptions based on market classification.
    
    Features:
    - Automatic subscription selection per instrument type
    - Priority-based subscription queueing
    - Bandwidth management
    - Connection pooling per venue
    - Graceful degradation under bandwidth constraints
    
    Example:
        manager = WebSocketDataManager()
        manager.subscribe_to_symbol("BTC-USD", Venue.COINBASE)
        manager.connect()
        
        for event in manager.stream():
            print(event)
    """
    
    # Subscription templates per instrument type
    SUBSCRIPTION_TEMPLATES: Dict[InstrumentType, List[MarketDataType]] = {
        # Spot products
        InstrumentType.SPOT: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
        ],
        InstrumentType.MARGIN_SPOT: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
            MarketDataType.FUNDING_RATE,  # margin interest
        ],
        InstrumentType.FOREX_SPOT: [
            MarketDataType.QUOTE,
            MarketDataType.CANDLE,
            MarketDataType.TRADE,
        ],
        InstrumentType.MARGIN_FX: [
            MarketDataType.QUOTE,
            MarketDataType.CANDLE,
            MarketDataType.TRADE,
            MarketDataType.FUNDING_RATE,
        ],
        # Derivatives
        InstrumentType.PERPETUAL_FUTURE: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
            MarketDataType.FUNDING_RATE,
            MarketDataType.OPEN_INTEREST,
            MarketDataType.LIQUIDATION,
        ],
        InstrumentType.FUTURE: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
            MarketDataType.OPEN_INTEREST,
        ],
        InstrumentType.OPTION: [
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
        ],
        InstrumentType.CFD: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.CANDLE,
        ],
        # Traditional products
        InstrumentType.STOCK: [
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
            MarketDataType.CANDLE,
        ],
        InstrumentType.ETF: [
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.ORDER_BOOK,
            MarketDataType.CANDLE,
        ],
        InstrumentType.INDEX: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.CANDLE,
        ],
        InstrumentType.BOND: [
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.CANDLE,
        ],
        InstrumentType.COMMODITY_SPOT: [
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.CANDLE,
        ],
    }
    
    # Priority levels per data type
    DATA_TYPE_PRIORITIES: Dict[MarketDataType, StreamPriority] = {
        MarketDataType.TICKER: StreamPriority.HIGH,
        MarketDataType.QUOTE: StreamPriority.CRITICAL,
        MarketDataType.TRADE: StreamPriority.NORMAL,
        MarketDataType.ORDER_BOOK: StreamPriority.NORMAL,
        MarketDataType.CANDLE: StreamPriority.NORMAL,
        MarketDataType.FUNDING_RATE: StreamPriority.HIGH,
        MarketDataType.OPEN_INTEREST: StreamPriority.HIGH,
        MarketDataType.LIQUIDATION: StreamPriority.NORMAL,
        MarketDataType.NEWS: StreamPriority.LOW,
        MarketDataType.ECONOMIC_CALENDAR: StreamPriority.LOW,
    }
    
    def __init__(self):
        """Initialize WebSocket data manager with classifier."""
        self.classifier = MarketClassifier()
        self.subscriptions: Dict[str, Set[DataStreamSubscription]] = {}  # symbol -> subscriptions
        self.venue_connections: Dict[Venue, Dict[str, Any]] = {}
        self.bandwidth_limit_mbps: float = 50.0  # Default 50 Mbps
        self.current_bandwidth_usage_mbps: float = 0.0
        self._connected_venues: Set[Venue] = set()
        
    def subscribe_to_symbol(
        self,
        symbol: str,
        venue: Venue,
        trading_mode: TradingMode = TradingMode.LIVE,
    ) -> List[DataStreamSubscription]:
        """Subscribe to all recommended data streams for a symbol.
        
        Uses market classification to determine the optimal set of data streams
        based on instrument type and market type.
        
        Args:
            symbol: Trading symbol
            venue: Venue enum value
            trading_mode: TradingMode enum value
            
        Returns:
            List of DataStreamSubscription objects
        """
        try:
            # Classify the symbol
            descriptor = self.classifier.classify(symbol, venue, trading_mode)
            
            if not descriptor.tradable:
                logger.warning(f"Symbol {symbol} is not tradable, skipping subscriptions")
                return []
            
            # Get template for this instrument type
            data_types = self.SUBSCRIPTION_TEMPLATES.get(
                descriptor.instrument_type,
                [MarketDataType.QUOTE, MarketDataType.TRADE]  # Fallback
            )
            
            # Create subscriptions with appropriate priorities
            subscriptions = []
            for data_type in data_types:
                priority = self.DATA_TYPE_PRIORITIES.get(data_type, StreamPriority.NORMAL)
                
                # Add special handling for specific data types
                if data_type == MarketDataType.ORDER_BOOK:
                    # Full order book depth for crypto, limited for others
                    depth = 20 if descriptor.is_crypto else 10
                    sub = DataStreamSubscription(
                        descriptor.symbol,
                        data_type,
                        priority=priority,
                        depth=depth,
                    )
                elif data_type == MarketDataType.CANDLE:
                    # 1-minute candles standard
                    sub = DataStreamSubscription(
                        descriptor.symbol,
                        data_type,
                        priority=priority,
                        interval=60.0,
                    )
                else:
                    sub = DataStreamSubscription(
                        descriptor.symbol,
                        data_type,
                        priority=priority,
                    )
                
                subscriptions.append(sub)
            
            # Store subscriptions
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = set()
            self.subscriptions[symbol].update(subscriptions)
            
            # Track venue connection needed
            if venue not in self.venue_connections:
                self.venue_connections[venue] = {
                    "symbols": set(),
                    "status": "pending",
                }
            self.venue_connections[venue]["symbols"].add(symbol)
            
            logger.debug(
                f"Subscribed to {len(subscriptions)} data streams for {descriptor.display_symbol}"
            )
            
            return subscriptions
            
        except Exception as e:
            logger.exception(f"Error subscribing to {symbol}: {e}")
            return []
    
    def unsubscribe_from_symbol(self, symbol: str) -> bool:
        """Remove all subscriptions for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if subscriptions were removed
        """
        if symbol in self.subscriptions:
            count = len(self.subscriptions[symbol])
            del self.subscriptions[symbol]
            logger.debug(f"Unsubscribed from {count} data streams for {symbol}")
            return True
        return False
    
    def get_subscriptions_for_symbol(self, symbol: str) -> Set[DataStreamSubscription]:
        """Get all subscriptions for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Set of DataStreamSubscription objects
        """
        return self.subscriptions.get(symbol, set())
    
    def get_subscriptions_by_priority(
        self,
        min_priority: StreamPriority = StreamPriority.NORMAL,
    ) -> List[DataStreamSubscription]:
        """Get all subscriptions, optionally filtered by priority.
        
        Useful for bandwidth throttling or connection quality adaptation.
        
        Args:
            min_priority: Minimum priority level to include
            
        Returns:
            List of subscriptions, sorted by priority
        """
        priority_order = {
            StreamPriority.CRITICAL: 0,
            StreamPriority.HIGH: 1,
            StreamPriority.NORMAL: 2,
            StreamPriority.LOW: 3,
            StreamPriority.OPTIONAL: 4,
        }
        
        all_subs = []
        for subs in self.subscriptions.values():
            for sub in subs:
                if priority_order[sub.priority] <= priority_order[min_priority]:
                    all_subs.append(sub)
        
        # Sort by priority
        all_subs.sort(key=lambda s: priority_order[s.priority])
        
        return all_subs
    
    def handle_bandwidth_constraint(self, available_mbps: float) -> List[DataStreamSubscription]:
        """Adjust subscriptions to fit available bandwidth.
        
        Removes low-priority subscriptions when bandwidth is constrained.
        
        Args:
            available_mbps: Available bandwidth in Mbps
            
        Returns:
            List of subscriptions that should be dropped
        """
        self.bandwidth_limit_mbps = available_mbps
        
        # Estimate bandwidth per subscription (rough)
        # Quote: 1 Kbps, Trade: 2 Kbps, OrderBook: 5 Kbps, Candle: 0.1 Kbps
        bandwidth_per_type = {
            MarketDataType.QUOTE: 0.001,
            MarketDataType.TRADE: 0.002,
            MarketDataType.ORDER_BOOK: 0.005,
            MarketDataType.CANDLE: 0.0001,
            MarketDataType.TICKER: 0.001,
            MarketDataType.FUNDING_RATE: 0.001,
            MarketDataType.OPEN_INTEREST: 0.001,
            MarketDataType.LIQUIDATION: 0.002,
        }
        
        # Get all subscriptions sorted by priority
        all_subs = self.get_subscriptions_by_priority()
        
        # Calculate bandwidth for critical and high priority
        current_bw = 0.0
        to_keep = []
        to_drop = []
        
        for sub in all_subs:
            estimated_bw = bandwidth_per_type.get(sub.data_type, 0.002)
            
            if current_bw + estimated_bw <= available_mbps:
                to_keep.append(sub)
                current_bw += estimated_bw
            else:
                if sub.priority in {StreamPriority.CRITICAL, StreamPriority.HIGH}:
                    # Keep critical subscriptions even if over budget
                    to_keep.append(sub)
                    current_bw += estimated_bw
                else:
                    to_drop.append(sub)
        
        # Update subscriptions to only keep prioritized ones
        for symbol in list(self.subscriptions.keys()):
            self.subscriptions[symbol] = {
                sub for sub in self.subscriptions[symbol]
                if sub in to_keep
            }
            if not self.subscriptions[symbol]:
                del self.subscriptions[symbol]
        
        self.current_bandwidth_usage_mbps = current_bw
        
        if to_drop:
            logger.warning(
                f"Dropped {len(to_drop)} low-priority subscriptions due to bandwidth constraint "
                f"({current_bw:.1f} Mbps used, {available_mbps:.1f} Mbps available)"
            )
        
        return to_drop
    
    def get_venue_status(self, venue: Venue) -> Dict[str, Any]:
        """Get connection status for a venue.
        
        Args:
            venue: Venue enum value
            
        Returns:
            Dict with venue status, subscription count, etc.
        """
        venue_info = self.venue_connections.get(venue, {})
        symbols = venue_info.get("symbols", set())
        status = venue_info.get("status", "unknown")
        
        # Count subscriptions
        total_subs = 0
        for symbol in symbols:
            total_subs += len(self.subscriptions.get(symbol, set()))
        
        return {
            "venue": venue.value,
            "status": status,
            "symbols_count": len(symbols),
            "total_subscriptions": total_subs,
            "bandwidth_usage_mbps": self.current_bandwidth_usage_mbps,
        }


# Default global WebSocket manager instance
_default_ws_manager: Optional[WebSocketDataManager] = None


def get_default_ws_manager() -> WebSocketDataManager:
    """Get or create the default global WebSocket manager.
    
    Returns:
        WebSocketDataManager instance
    """
    global _default_ws_manager
    if _default_ws_manager is None:
        _default_ws_manager = WebSocketDataManager()
    return _default_ws_manager


def set_default_ws_manager(manager: WebSocketDataManager) -> None:
    """Set the default global WebSocket manager.
    
    Args:
        manager: WebSocketDataManager instance
    """
    global _default_ws_manager
    _default_ws_manager = manager
