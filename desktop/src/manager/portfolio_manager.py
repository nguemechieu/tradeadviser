from event_bus.event_types import EventType
from portfolio.portfolio import Portfolio
from portfolio.pnl_engine import PnLEngine


class PortfolioManager:

    def __init__(self, event_bus):
        self.bus = event_bus

        self.portfolio = Portfolio()

        self.pnl_engine = PnLEngine()

        self.market_prices = {}

        # Subscribe to events
        self.bus.subscribe(EventType.FILL, self.on_fill)

        self.bus.subscribe(EventType.MARKET_TICK, self.on_tick)

    # ===================================
    # TRADE FILL
    # ===================================

    async def on_fill(self, event):
        fill = event.data

        symbol = fill["symbol"]
        side = fill["side"]
        price = fill["price"]
        qty = fill["qty"]

        self.portfolio.update_position(symbol, side, price, qty)

    # ===================================
    # MARKET PRICE UPDATE
    # ===================================

    async def on_tick(self, event):
        tick = event.data

        symbol = tick["symbol"]

        price = tick.get("price")

        self.market_prices[symbol] = price

    # ===================================
    # PORTFOLIO VALUE
    # ===================================

    def equity(self):
        return self.portfolio.equity(self.market_prices)
