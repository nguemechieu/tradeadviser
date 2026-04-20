class Position:

    def __init__(self, symbol):

        self.symbol = symbol

        self.quantity = 0
        self.avg_price = 0

    # ============================
    # UPDATE POSITION
    # ============================

    def update(self, side, price, qty):

        if side == "BUY":

            total_cost = (self.avg_price * self.quantity) + (price * qty)

            self.quantity += qty

            if self.quantity > 0:
                self.avg_price = total_cost / self.quantity

        elif side == "SELL":

            self.quantity -= qty

            if self.quantity == 0:
                self.avg_price = 0

    # ============================
    # MARKET VALUE
    # ============================

    def market_value(self, price):

        return self.quantity * price
