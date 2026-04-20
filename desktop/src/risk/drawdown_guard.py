class DrawdownGuard:

    def __init__(self, max_drawdown=0.2):

        self.max_drawdown = max_drawdown

        self.peak_equity = None

    # =====================================
    # UPDATE EQUITY
    # =====================================

    def update(self, equity):

        if self.peak_equity is None:
            self.peak_equity = equity

        if equity > self.peak_equity:
            self.peak_equity = equity

    # =====================================
    # CHECK DRAWDOWN
    # =====================================

    def check(self, equity):

        if self.peak_equity is None:
            return True

        drawdown = (self.peak_equity - equity) / self.peak_equity

        return drawdown < self.max_drawdown
