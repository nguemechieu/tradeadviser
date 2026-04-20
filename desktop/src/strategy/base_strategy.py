from collections import defaultdict, deque

from event_bus.event import Event
from event_bus.event_types import EventType


class BaseStrategy:
    """Shared helpers for simple event-driven and backtest-friendly strategies."""

    def __init__(self, event_bus=None, *, signal_amount=0.01, max_history=500):
        self.bus = event_bus
        self.signal_amount = float(signal_amount or 0.01)
        self.max_history = max(10, int(max_history or 500))
        self.price_history = defaultdict(lambda: deque(maxlen=self.max_history))
        self._last_signal_side = {}

    def _append_price(self, symbol, price):
        normalized_symbol = str(symbol or "").strip().upper()
        numeric_price = float(price)
        self.price_history[normalized_symbol].append(numeric_price)
        return list(self.price_history[normalized_symbol])

    def _normalize_symbol(self, symbol, fallback="BACKTEST"):
        normalized = str(symbol or "").strip().upper()
        return normalized or str(fallback or "BACKTEST").strip().upper() or "BACKTEST"

    def _normalize_signal_amount(self, amount=None):
        return float(amount if amount not in (None, "") else self.signal_amount)

    def _build_signal(self, symbol, side, amount=None, **metadata):
        signal = {
            "symbol": self._normalize_symbol(symbol),
            "side": str(side or "").strip().lower(),
            "amount": self._normalize_signal_amount(amount),
            "type": str(metadata.pop("type", "market") or "market").strip().lower(),
        }
        signal.update({key: value for key, value in metadata.items() if value is not None})
        return signal

    def _should_emit_signal(self, symbol, side):
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_side = str(side or "").strip().lower()
        if not normalized_side:
            return False
        previous = self._last_signal_side.get(normalized_symbol)
        if previous == normalized_side:
            return False
        self._last_signal_side[normalized_symbol] = normalized_side
        return True

    async def signal(self, symbol, side, amount=None, **metadata):
        order = self._build_signal(symbol, side, amount=amount, **metadata)
        if self.bus is None:
            return order

        event_order = dict(order)
        event_order["side"] = str(event_order.get("side") or "").upper()
        event = Event(EventType.ORDER, event_order)
        await self.bus.publish(event)
        return event_order
