import asyncio
from datetime import datetime, timezone

from events.event import Event
from events.event_bus.event_types import EventType


class PaperWebSocket:
    """Synthetic stream for paper mode using broker/controller prices."""

    def __init__(self, broker, symbols, event_bus, interval=1.0):
        self.broker = broker
        self.symbols = symbols or []
        self.bus = event_bus
        self.interval = interval

    async def connect(self):
        while True:
            for symbol in self.symbols:
                price = await self._get_price(symbol)
                if price is None:
                    continue

                # Small synthetic spread for UI display.
                bid = float(price) * 0.9998
                ask = float(price) * 1.0002

                payload = {
                    "symbol": symbol,
                    "price": float(price),
                    "bid": bid,
                    "ask": ask,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                await self.bus.publish(Event(type=EventType.MARKET_TICK, data=payload))

            await asyncio.sleep(self.interval)

    async def _get_price(self, symbol):
        try:
            if hasattr(self.broker, "fetch_ticker"):
                tick = await self.broker.fetch_ticker(symbol)
                if isinstance(tick, dict):
                    return tick.get("price") or tick.get("last")
                return tick

            if hasattr(self.broker, "fetch_price"):
                return await self.broker.fetch_price(symbol)

        except Exception:
            return None

        return None
