import numpy as np


class Metrics:

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
    # RETURNS
    # =====================================

    @staticmethod
    def returns(equity_curve):
        equity = Metrics._finite_array(equity_curve)
        if len(equity) < 2:
            return np.array([])

        previous = equity[:-1]
        current = equity[1:]
        valid_mask = previous != 0
        if not np.any(valid_mask):
            return np.array([], dtype=float)

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            returns = (current[valid_mask] - previous[valid_mask]) / previous[valid_mask]
        return returns[np.isfinite(returns)]

    # =====================================
    # CUMULATIVE RETURN
    # =====================================

    @staticmethod
    def cumulative_return(equity_curve):
        equity = Metrics._finite_array(equity_curve)
        if len(equity) < 2:
            return 0.0
        starting_equity = float(equity[0])
        if starting_equity == 0:
            return 0.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            value = float(equity[-1] / starting_equity) - 1.0
        return value if np.isfinite(value) else 0.0

    # =====================================
    # VOLATILITY
    # =====================================

    @staticmethod
    def volatility(returns):
        finite_returns = Metrics._finite_array(returns)
        if len(finite_returns) == 0:
            return 0.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            volatility = float(np.std(finite_returns)) * float(np.sqrt(252))
        return volatility if np.isfinite(volatility) else 0.0

    # =====================================
    # SHARPE RATIO
    # =====================================

    @staticmethod
    def sharpe_ratio(returns, risk_free_rate=0):
        finite_returns = Metrics._finite_array(returns)
        if len(finite_returns) == 0:
            return 0.0
        try:
            risk_free = float(risk_free_rate or 0.0)
        except Exception:
            risk_free = 0.0
        if not np.isfinite(risk_free):
            risk_free = 0.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            excess = finite_returns - risk_free
            std = float(np.std(excess))
        if std <= 0 or not np.isfinite(std):
            return 0.0

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            ratio = float(np.mean(excess)) / std
        return ratio if np.isfinite(ratio) else 0.0

    # =====================================
    # SORTINO RATIO
    # =====================================

    @staticmethod
    def sortino_ratio(returns):
        finite_returns = Metrics._finite_array(returns)
        if len(finite_returns) == 0:
            return 0.0
        negative_returns = finite_returns[finite_returns < 0]
        if len(negative_returns) == 0:
            return 0.0

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            downside_std = np.std(negative_returns)
        if downside_std == 0 or not np.isfinite(downside_std):
            return 0.0
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            ratio = float(np.mean(finite_returns)) / float(downside_std)
        return ratio if np.isfinite(ratio) else 0.0
