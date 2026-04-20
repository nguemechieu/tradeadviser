import numpy as np


class RiskMetrics:

    @staticmethod
    def _finite_array(values):
        if values is None:
            return np.array([], dtype=float)
        try:
            array = np.asarray(values, dtype=float)
        except Exception:
            return np.array([], dtype=float)
        if array.ndim == 0:
            array = np.array([float(array)], dtype=float)
        return array[np.isfinite(array)]

    # =====================================
    # MAX DRAWDOWN
    # =====================================

    @staticmethod
    def max_drawdown(equity_curve):
        equity = RiskMetrics._finite_array(equity_curve)
        if len(equity) == 0:
            return 0.0

        peak = float(equity[0])

        max_dd = 0.0

        for value in equity:
            value = float(value)

            if value > peak:
                peak = value

            if peak <= 0:
                continue
            dd = (peak - value) / peak

            if dd > max_dd:
                max_dd = dd

        return max_dd

    # =====================================
    # VALUE AT RISK
    # =====================================

    @staticmethod
    def var(returns, confidence=0.95):
        finite_returns = RiskMetrics._finite_array(returns)
        if len(finite_returns) == 0:
            return 0.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            value = np.percentile(finite_returns, (1 - confidence) * 100)
        return float(value) if np.isfinite(value) else 0.0

    # =====================================
    # CONDITIONAL VAR
    # =====================================

    @staticmethod
    def cvar(returns, confidence=0.95):
        finite_returns = RiskMetrics._finite_array(returns)
        if len(finite_returns) == 0:
            return 0.0
        var = RiskMetrics.var(finite_returns, confidence)
        losses = finite_returns[finite_returns <= var]
        if len(losses) == 0:
            return 0.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            value = np.mean(losses)
        return float(value) if np.isfinite(value) else 0.0
