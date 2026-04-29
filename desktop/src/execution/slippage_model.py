class SlippageModel:

    def __init__(self, slippage_pct=0.001):
        """Model execution slippage by adjusting prices with a fixed percentage buffer. Provides a simple
    way to approximate less favorable real-world execution prices for backtests or simulations.

    The model applies an upward adjustment for buy orders and a downward adjustment for sell orders,
    leaving prices unchanged for other sides. This helps conservatively account for execution costs
    without modeling full order book dynamics.

    Args:
        slippage_pct: The fractional slippage applied to the price (e.g., 0.001 for 0.1%).
    """

        self.slippage_pct = slippage_pct

    def apply(self, price, side):

        if side == "BUY":
            return price * (1 + self.slippage_pct)

        if side == "SELL":
            return price * (1 - self.slippage_pct)

        return price
