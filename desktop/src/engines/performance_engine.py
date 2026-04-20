import time
from datetime import datetime

import numpy as np

from quant.analytics.metrics import Metrics
from quant.analytics.risk_metrics import RiskMetrics


class PerformanceEngine:

    def __init__(self):
        self.equity_curve = []
        self.equity_history = self.equity_curve
        self.equity_timestamps = []
        self.equity_time_history = self.equity_timestamps
        self.trades = []

    @staticmethod
    def _coerce_timestamp(timestamp, default=None):
        fallback = float(default if default is not None else time.time())
        if timestamp in (None, ""):
            return fallback

        try:
            numeric = float(timestamp)
        except Exception:
            numeric = None

        if numeric is not None and np.isfinite(numeric):
            if numeric > 1_000_000_000_000:
                numeric /= 1000.0
            return float(numeric)

        text = str(timestamp).strip()
        if not text:
            return fallback

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return float(parsed.timestamp())
        except Exception:
            return fallback

    # =====================================
    # UPDATE EQUITY
    # =====================================

    def update_equity(self, equity, timestamp=None):
        try:
            numeric = float(equity)
        except Exception:
            return
        if not np.isfinite(numeric):
            return

        self.equity_curve.append(numeric)
        self.equity_timestamps.append(self._coerce_timestamp(timestamp))

    def load_equity_history(self, history):
        self.equity_curve.clear()
        self.equity_timestamps.clear()

        entries = list(history or [])
        fallback_end = time.time()
        fallback_start = fallback_end - max(len(entries) - 1, 0) * 60.0

        for index, value in enumerate(entries):
            timestamp = None
            if isinstance(value, dict):
                timestamp = value.get("timestamp")
                value = value.get("equity", value.get("value"))

            try:
                numeric = float(value)
            except Exception:
                continue
            if not np.isfinite(numeric):
                continue

            self.equity_curve.append(numeric)
            fallback_timestamp = fallback_start + (index * 60.0)
            self.equity_timestamps.append(self._coerce_timestamp(timestamp, default=fallback_timestamp))

    def record_trade(self, trade):
        if trade is None:
            return
        payload = dict(trade)
        order_id = str(payload.get("order_id") or payload.get("id") or "").strip()
        if order_id:
            for index, existing in enumerate(self.trades):
                existing_order_id = str(existing.get("order_id") or existing.get("id") or "").strip()
                if existing_order_id == order_id:
                    merged = dict(existing)
                    for key, item in payload.items():
                        if item not in (None, ""):
                            merged[key] = item
                    self.trades[index] = merged
                    return
        self.trades.append(payload)

    def load_trades(self, trades):
        self.trades.clear()
        for trade in list(trades or []):
            if isinstance(trade, dict):
                self.record_trade(trade)

    # =====================================
    # REPORT
    # =====================================

    def report(self):
        equity = Metrics._finite_array(self.equity_curve)
        if len(equity) < 2:
            return {}
        returns = Metrics.returns(equity)

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            report = {
                "cumulative_return": Metrics.cumulative_return(equity),
                "volatility": Metrics.volatility(returns),
                "sharpe_ratio": Metrics.sharpe_ratio(returns),
                "sortino_ratio": Metrics.sortino_ratio(returns),
                "max_drawdown": RiskMetrics.max_drawdown(equity),
                "value_at_risk": RiskMetrics.var(returns),
                "conditional_var": RiskMetrics.cvar(returns),
            }

        return report
