from portfolio.position import Position


class Portfolio:

    def __init__(self, starting_cash=100000):

        self.cash = starting_cash

        self.positions = {}

    # ===================================
    # GET POSITION
    # ===================================

    def get_position(self, symbol):

        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)

        return self.positions[symbol]

    # ===================================
    # UPDATE POSITION
    # ===================================

    def update_position(self, symbol, side, price, qty):

        pos = self.get_position(symbol)

        pos.update(side, price, qty)

        if side == "BUY":
            self.cash -= price * qty

        if side == "SELL":
            self.cash += price * qty

    # ===================================
    # TOTAL EQUITY
    # ===================================

    def get_equity(self, market_prices=None):

        market_prices = market_prices or {}

        total = self.cash

        for symbol, pos in self.positions.items():

            price = market_prices.get(symbol)

            if price:
                total += pos.market_value(price)

        return total

    def equity(self, market_prices=None):
        return self.get_equity(market_prices)
