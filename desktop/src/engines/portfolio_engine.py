from event_bus.event_types import EventType


class PortfolioEngine:

    def __init__(self, bus):
        self.positions = {}

        bus.subscribe(EventType.FILL, self.update)

    async def update(self, event):
        fill = event.data

        symbol = fill["symbol"]

        self.positions[symbol] = self.positions.get(symbol, 0) + fill["qty"]
