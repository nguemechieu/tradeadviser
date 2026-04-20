import math


class RiskEngineV2:
    """
    Institutional Risk Engine:
    - ATR-based stop loss
    - Volatility-based position sizing
    - Fixed % risk per trade
    """

    def __init__(
            self,
            account_equity: float,
            risk_per_trade: float = 0.01,  # 1%
            atr_multiplier: float = 2.0,
            max_position_pct: float = 0.1,
    ):
        self.account_equity = account_equity
        self.risk_per_trade = risk_per_trade
        self.atr_multiplier = atr_multiplier
        self.max_position_pct = max_position_pct

    # =========================
    # POSITION SIZING
    # =========================
    def size_position(self, price, atr):

        if price <= 0 or atr <= 0:
            return 0.0, None

        stop_distance = atr * self.atr_multiplier

        risk_amount = self.account_equity * self.risk_per_trade

        position_size = risk_amount / stop_distance

        # Cap max position
        max_size = (self.account_equity * self.max_position_pct) / price
        position_size = min(position_size, max_size)

        return position_size, stop_distance

    # =========================
    # STOP LOSS
    # =========================
    def compute_sl_tp(self, price, atr, side):

        stop_distance = atr * self.atr_multiplier

        if side == "BUY":
            sl = price - stop_distance
            tp = price + (stop_distance * 2)  # RR = 1:2
        else:
            sl = price + stop_distance
            tp = price - (stop_distance * 2)

        return sl, tp