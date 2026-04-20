class PnLEngine:

    def __init__(self):
        self.realized = 0
        self.unrealized = 0

    # ===================================
    # UNREALIZED PNL
    # ===================================

    def calculate_unrealized(self, position, market_price):
        pnl = (market_price - position.avg_price) * position.quantity

        return pnl

    # ===================================
    # TOTAL PNL
    # ===================================

    def total(self):
        return self.realized + self.unrealized
