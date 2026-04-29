from __future__ import annotations

import inspect
import logging
from typing import Any
from events.event_bus.event_types import EventType
from portfolio.portfolio import Portfolio
from portfolio.pnl_engine import PnLEngine


def _event_name(name: str, fallback: str) -> Any:
    member = getattr(EventType, name, fallback)

    # Enum member -> value
    if hasattr(member, "value"):
        try:
            return member.value
        except Exception as ex:
            print(ex)

    return member


def _event_data(event: Any) -> Any:
    if isinstance(event, dict):
        return event.get("data", event)
    if hasattr(event, "data"):
        return event.data
    if hasattr(event, "payload"):
        return event.payload
    return event


class _LocalEventBus:
    """Small fallback bus so Portfolio Manager never crashes during startup."""

    def __init__(self) -> None:
        self.handlers: dict[str, list[Any]] = {}

    def _key(self, value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        return str(value or "").strip()

    def subscribe(self, event_type: Any, handler: Any) -> Any:
        self.handlers.setdefault(self._key(event_type), []).append(handler)
        return handler

    def unsubscribe(self, event_type: Any, handler: Any) -> None:
        key = self._key(event_type)
        self.handlers[key] = [
            item for item in self.handlers.get(key, [])
            if item is not handler
        ]

    async def publish(self, event_or_type: Any, data: Any = None, **kwargs: Any) -> Any:
        try:
            from events.event import Event
            if hasattr(event_or_type, "type") and hasattr(event_or_type, "data"):
                event = event_or_type
                key = self._key(event.type)
            else:
                event = Event(type=self._key(event_or_type), data=data, **kwargs)
                key = self._key(event_or_type)
        except Exception:
            event = {"type": self._key(event_or_type), "data": data, **kwargs}
            key = self._key(event_or_type)

        handlers = list(self.handlers.get(key, []))
        handlers.extend(self.handlers.get("*", []))

        for handler in handlers:
            result = handler(event)
            if inspect.isawaitable(result):
                await result

        return event

    def publish_nowait(self, event_or_type: Any, data: Any = None, **kwargs: Any) -> Any:
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            return loop.create_task(self.publish(event_or_type, data, **kwargs))
        except RuntimeError:
            return None


class PortfolioManager:
    def __init__(self, event_bus: Any = None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        if event_bus is None or not hasattr(event_bus, "subscribe"):
            self.logger.warning(
                "PortfolioManager received invalid event_bus=%r; using LocalEventBus fallback.",
                event_bus,
            )
            event_bus = _LocalEventBus()

        self.bus = event_bus
        self.portfolio = Portfolio()
        self.pnl_engine = PnLEngine()
        self.market_prices: dict[str, float] = {}

        self._subscriptions: list[tuple[Any, Any]] = []
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        # Support both your old FILL event and your execution engine ORDER_FILLED event.
        self._safe_subscribe(_event_name("FILL", "fill"), self.on_fill)
        self._safe_subscribe(_event_name("ORDER_FILLED", "order.filled"), self.on_fill)

        # Support both market ticks and generic price updates.
        self._safe_subscribe(_event_name("MARKET_TICK", "market.tick"), self.on_tick)
        self._safe_subscribe(_event_name("PRICE_UPDATE", "price.update"), self.on_tick)

    def _safe_subscribe(self, event_type: Any, handler: Any) -> None:
        subscribe = getattr(self.bus, "subscribe", None)
        if not callable(subscribe):
            return

        try:
            subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))
        except Exception:
            self.logger.debug("Unable to subscribe to event_type=%s", event_type, exc_info=True)

    def unsubscribe_all(self) -> None:
        unsubscribe = getattr(self.bus, "unsubscribe", None)
        if not callable(unsubscribe):
            self._subscriptions.clear()
            return

        for event_type, handler in list(self._subscriptions):
            try:
                unsubscribe(event_type, handler)
            except Exception:
                pass

        self._subscriptions.clear()

    async def on_fill(self, event: Any) -> None:
        fill = _event_data(event)

        if not isinstance(fill, dict):
            return

        symbol = str(fill.get("symbol") or "").strip().upper()
        side = str(fill.get("side") or "").strip().lower()

        price = (
                fill.get("price")
                or fill.get("fill_price")
                or fill.get("average_price")
                or fill.get("avg_price")
        )
        qty = (
                fill.get("qty")
                or fill.get("quantity")
                or fill.get("amount")
                or fill.get("filled_quantity")
                or fill.get("filled")
        )

        if not symbol or side not in {"buy", "sell"}:
            return

        try:
            price_value = float(price or 0.0)
            qty_value = float(qty or 0.0)
        except Exception:
            return

        if price_value <= 0 or qty_value <= 0:
            return

        self.portfolio.update_position(symbol, side, price_value, qty_value)

        # Keep last fill price as market price fallback.
        self.market_prices[symbol] = price_value

    async def on_tick(self, event: Any) -> None:
        tick = _event_data(event)

        if not isinstance(tick, dict):
            return

        symbol = str(tick.get("symbol") or "").strip().upper()
        price = (
                tick.get("price")
                or tick.get("last")
                or tick.get("close")
                or tick.get("mark")
        )

        if not symbol:
            return

        try:
            price_value = float(price or 0.0)
        except Exception:
            return

        if price_value <= 0:
            return

        self.market_prices[symbol] = price_value

    def equity(self) -> float:
        try:
            return float(self.portfolio.equity(self.market_prices))
        except Exception:
            self.logger.debug("Portfolio equity calculation failed", exc_info=True)
            return 0.0

    def snapshot(self) -> dict[str, Any]:
        positions = getattr(self.portfolio, "positions", {}) or {}

        return {
            "equity": self.equity(),
            "market_prices": dict(self.market_prices),
            "position_count": len(positions),
            "positions": positions,
            "subscriptions": [
                str(event_type.value if hasattr(event_type, "value") else event_type)
                for event_type, _handler in self._subscriptions
            ],
        }


__all__ = ["PortfolioManager"]