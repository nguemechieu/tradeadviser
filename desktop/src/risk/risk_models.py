import numpy as np


class RiskModels:

    # =====================================
    # VALUE AT RISK
    # =====================================

    @staticmethod
    def var(returns, confidence=0.95):
        return np.percentile(returns, (1 - confidence) * 100)

    # =====================================
    # CONDITIONAL VAR
    # =====================================

    @staticmethod
    def cvar(returns, confidence=0.95):
        var = RiskModels.var(returns, confidence)

        losses = returns[returns <= var]

        return np.mean(losses)

    # =====================================
    # KELLY POSITION SIZING
    # =====================================

    @staticmethod
    def kelly(win_rate, win_loss_ratio):
        return win_rate - ((1 - win_rate) / win_loss_ratio)
