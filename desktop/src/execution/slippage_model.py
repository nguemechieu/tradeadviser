class SlippageModel:

    def __init__(self, slippage_pct=0.001):

        self.slippage_pct = slippage_pct

    def apply(self, price, side):

        if side == "BUY":
            return price * (1 + self.slippage_pct)

        if side == "SELL":
            return price * (1 - self.slippage_pct)

        return price
