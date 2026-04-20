"""Alert Engine - Core logic for managing trading alerts.

Handles price alerts, percentage alerts, volume alerts, indicator alerts,
and system alerts with multi-channel notifications.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class AlertType(str, Enum):
    """Alert trigger types."""
    PRICE_CROSS_ABOVE = "price_cross_above"
    PRICE_CROSS_BELOW = "price_cross_below"
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_RANGE = "price_range"  # Between min and max
    PERCENTAGE_UP = "percentage_up"
    PERCENTAGE_DOWN = "percentage_down"
    VOLUME_SPIKE = "volume_spike"
    INDICATOR_RSI_OVERBOUGHT = "indicator_rsi_overbought"
    INDICATOR_RSI_OVERSOLD = "indicator_rsi_oversold"
    INDICATOR_MACD_CROSS = "indicator_macd_cross"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    MARGIN_WARNING = "margin_warning"
    CONNECTION_LOST = "connection_lost"


class AlertChannel(str, Enum):
    """Notification channels."""
    IN_APP = "in_app"
    SOUND = "sound"
    EMAIL = "email"
    WEBHOOK = "webhook"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    INACTIVE = "inactive"
    EXPIRED = "expired"


@dataclass
class AlertRule:
    """Configuration for a single alert rule."""
    id: str
    name: str
    alert_type: AlertType
    symbol: Optional[str] = None
    enabled: bool = True
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.IN_APP, AlertChannel.SOUND])
    
    # Condition parameters (vary by alert type)
    price_level: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    percentage: Optional[float] = None
    volume_threshold: Optional[float] = None
    rsi_threshold: Optional[int] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    triggered_count: int = 0
    one_time: bool = False  # If True, alert disables after first trigger
    
    # Notification settings
    email_address: Optional[str] = None
    webhook_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['alert_type'] = self.alert_type.value
        data['channels'] = [c.value for c in self.channels]
        data['created_at'] = self.created_at.isoformat()
        data['last_triggered'] = self.last_triggered.isoformat() if self.last_triggered else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlertRule':
        """Construct from dictionary."""
        data = dict(data)  # Make a copy
        data['alert_type'] = AlertType(data['alert_type'])
        data['channels'] = [AlertChannel(c) for c in data.get('channels', [])]
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('last_triggered'), str) and data['last_triggered']:
            data['last_triggered'] = datetime.fromisoformat(data['last_triggered'])
        return cls(**data)


@dataclass
class AlertEvent:
    """An alert that has been triggered."""
    alert_id: str
    alert_name: str
    alert_type: AlertType
    symbol: Optional[str]
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertEngine:
    """Core alert engine for managing and evaluating alert rules."""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.alerts: Dict[str, AlertRule] = {}
        self.listeners: List[Callable[[AlertEvent], None]] = []
        self._market_data_cache: Dict[str, Dict[str, float]] = {}  # symbol -> {price, volume, ...}
        self._price_history: Dict[str, List[float]] = {}  # Track price for cross detection
        self._evaluation_task = None
    
    # ===================
    # Alert Management
    # ===================
    
    def create_alert(self, alert_rule: AlertRule) -> str:
        """Create and store a new alert."""
        self.alerts[alert_rule.id] = alert_rule
        self.logger.info(f"Alert created: {alert_rule.id} ({alert_rule.name})")
        return alert_rule.id
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert by ID."""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            self.logger.info(f"Alert deleted: {alert_id}")
            return True
        return False
    
    def get_alert(self, alert_id: str) -> Optional[AlertRule]:
        """Get alert by ID."""
        return self.alerts.get(alert_id)
    
    def get_all_alerts(self) -> List[AlertRule]:
        """Get all alerts."""
        return list(self.alerts.values())
    
    def enable_alert(self, alert_id: str) -> bool:
        """Enable an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = True
            return True
        return False
    
    def disable_alert(self, alert_id: str) -> bool:
        """Disable an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = False
            return True
        return False
    
    # ===================
    # Event Handling
    # ===================
    
    def subscribe(self, callback: Callable[[AlertEvent], None]) -> None:
        """Subscribe to alert events."""
        self.listeners.append(callback)
    
    def unsubscribe(self, callback: Callable[[AlertEvent], None]) -> None:
        """Unsubscribe from alert events."""
        if callback in self.listeners:
            self.listeners.remove(callback)
    
    def _trigger_alert(self, alert: AlertRule, message: str, metadata: Dict[str, Any] = None) -> None:
        """Trigger an alert and notify listeners."""
        if not alert.enabled:
            return
        
        alert.last_triggered = datetime.utcnow()
        alert.triggered_count += 1
        
        event = AlertEvent(
            alert_id=alert.id,
            alert_name=alert.name,
            alert_type=alert.alert_type,
            symbol=alert.symbol,
            message=message,
            metadata=metadata or {}
        )
        
        # Notify all listeners
        for listener in self.listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.exception(f"Error in alert listener: {e}")
        
        # Disable if one-time
        if alert.one_time:
            alert.enabled = False
        
        self.logger.info(f"Alert triggered: {alert.name} - {message}")
    
    # ===================
    # Market Data Updates
    # ===================
    
    def on_market_data(self, symbol: str, price: float, volume: float = None) -> None:
        """Called when new market data arrives."""
        self._market_data_cache[symbol] = {
            'price': price,
            'volume': volume,
            'timestamp': datetime.utcnow()
        }
        
        # Track price history for cross detection
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(price)
        
        # Keep only last 100 prices
        if len(self._price_history[symbol]) > 100:
            self._price_history[symbol] = self._price_history[symbol][-100:]
        
        # Evaluate all alerts for this symbol
        self._evaluate_alerts_for_symbol(symbol)
    
    def on_order_filled(self, order_id: str, symbol: str, side: str, price: float, quantity: float) -> None:
        """Called when an order is filled."""
        for alert in self.alerts.values():
            if alert.alert_type == AlertType.ORDER_FILLED and alert.enabled:
                message = f"Order filled: {side.upper()} {quantity} {symbol} @ ${price:.2f}"
                self._trigger_alert(alert, message, {
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'price': price,
                    'quantity': quantity
                })
    
    def on_position_opened(self, symbol: str, side: str, quantity: float, entry_price: float) -> None:
        """Called when a position is opened."""
        for alert in self.alerts.values():
            if alert.alert_type == AlertType.POSITION_OPENED and alert.enabled:
                message = f"Position opened: {side.upper()} {quantity} {symbol} @ ${entry_price:.2f}"
                self._trigger_alert(alert, message, {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price
                })
    
    def on_position_closed(self, symbol: str, close_price: float, pnl: float) -> None:
        """Called when a position is closed."""
        for alert in self.alerts.values():
            if alert.alert_type == AlertType.POSITION_CLOSED and alert.enabled:
                message = f"Position closed: {symbol} @ ${close_price:.2f}, P/L: ${pnl:.2f}"
                self._trigger_alert(alert, message, {
                    'symbol': symbol,
                    'close_price': close_price,
                    'pnl': pnl
                })
    
    def on_margin_warning(self, margin_level: float) -> None:
        """Called when margin level falls below threshold."""
        for alert in self.alerts.values():
            if alert.alert_type == AlertType.MARGIN_WARNING and alert.enabled:
                message = f"Margin warning: Level at {margin_level:.1f}%"
                self._trigger_alert(alert, message, {'margin_level': margin_level})
    
    def on_connection_lost(self) -> None:
        """Called when broker connection is lost."""
        for alert in self.alerts.values():
            if alert.alert_type == AlertType.CONNECTION_LOST and alert.enabled:
                message = "Connection to broker lost"
                self._trigger_alert(alert, message)
    
    # ===================
    # Alert Evaluation
    # ===================
    
    def _evaluate_alerts_for_symbol(self, symbol: str) -> None:
        """Evaluate all alerts for a given symbol."""
        data = self._market_data_cache.get(symbol)
        if not data:
            return
        
        for alert in self.alerts.values():
            if not alert.enabled or alert.symbol != symbol:
                continue
            
            self._evaluate_alert(alert, data)
    
    def _evaluate_alert(self, alert: AlertRule, market_data: Dict[str, Any]) -> None:
        """Evaluate if an alert should trigger."""
        price = market_data.get('price')
        volume = market_data.get('volume')
        
        if alert.alert_type == AlertType.PRICE_ABOVE:
            if alert.price_level and price >= alert.price_level:
                self._trigger_alert(alert, f"{alert.symbol} price reached ${price:.2f}")
        
        elif alert.alert_type == AlertType.PRICE_BELOW:
            if alert.price_level and price <= alert.price_level:
                self._trigger_alert(alert, f"{alert.symbol} price dropped to ${price:.2f}")
        
        elif alert.alert_type == AlertType.PRICE_RANGE:
            if alert.price_min and alert.price_max and alert.price_min <= price <= alert.price_max:
                self._trigger_alert(alert, f"{alert.symbol} price in range ${alert.price_min:.2f}-${alert.price_max:.2f}")
        
        elif alert.alert_type == AlertType.PRICE_CROSS_ABOVE:
            if self._check_price_cross_above(alert.symbol, alert.price_level):
                self._trigger_alert(alert, f"{alert.symbol} crossed above ${alert.price_level:.2f}")
        
        elif alert.alert_type == AlertType.PRICE_CROSS_BELOW:
            if self._check_price_cross_below(alert.symbol, alert.price_level):
                self._trigger_alert(alert, f"{alert.symbol} crossed below ${alert.price_level:.2f}")
        
        elif alert.alert_type == AlertType.PERCENTAGE_UP:
            if self._check_percentage_move(alert.symbol, alert.percentage, direction='up'):
                self._trigger_alert(alert, f"{alert.symbol} up {alert.percentage:.1f}%")
        
        elif alert.alert_type == AlertType.PERCENTAGE_DOWN:
            if self._check_percentage_move(alert.symbol, alert.percentage, direction='down'):
                self._trigger_alert(alert, f"{alert.symbol} down {alert.percentage:.1f}%")
        
        elif alert.alert_type == AlertType.VOLUME_SPIKE:
            if alert.volume_threshold and volume and volume > alert.volume_threshold:
                self._trigger_alert(alert, f"{alert.symbol} volume spike: {volume:.2f}")
    
    def _check_price_cross_above(self, symbol: str, level: float) -> bool:
        """Check if price crossed above a level."""
        history = self._price_history.get(symbol, [])
        if len(history) < 2:
            return False
        
        prev_price = history[-2]
        curr_price = history[-1]
        return prev_price < level <= curr_price
    
    def _check_price_cross_below(self, symbol: str, level: float) -> bool:
        """Check if price crossed below a level."""
        history = self._price_history.get(symbol, [])
        if len(history) < 2:
            return False
        
        prev_price = history[-2]
        curr_price = history[-1]
        return prev_price > level >= curr_price
    
    def _check_percentage_move(self, symbol: str, percent: float, direction: str) -> bool:
        """Check if price moved by percentage."""
        history = self._price_history.get(symbol, [])
        if len(history) < 2:
            return False
        
        start_price = history[0]
        current_price = history[-1]
        
        if start_price <= 0:
            return False
        
        pct_change = ((current_price - start_price) / start_price) * 100
        
        if direction == 'up':
            return pct_change >= percent
        else:
            return pct_change <= -percent
