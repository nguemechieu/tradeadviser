from event_bus.event import Event
from event_bus.event_types import EventType


class StrategyEngine:

    def __init__(self, event_bus):
        self.bus = event_bus

        self.bus.subscribe(EventType.MARKET_TICK, self.on_tick)

    async def on_tick(self, event):
        tick = event.data

        price = tick["last"]

        if price > 50000:
            signal = Event(
                EventType.SIGNAL,
                {"symbol": "BTC/USDT", "side": "BUY"}
            )

            await self.bus.publish(signal)
