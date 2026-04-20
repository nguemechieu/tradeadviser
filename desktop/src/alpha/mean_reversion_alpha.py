from __future__ import annotations

import numpy as np

from alpha.base_alpha import AlphaContext, AlphaSignal, BaseAlphaModel


class MeanReversionAlpha(BaseAlphaModel):
    name = "mean_reversion_alpha"
    supported_regimes = frozenset({"MEAN_REVERTING", "LOW_LIQUIDITY"})

    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        row, frame = self._row(context)
        if row is None or frame is None:
            return None

        close_price = self._safe_float(row.get("close"), 0.0)
        if close_price <= 0:
            return None
        rsi = self._safe_float(row.get("rsi"), 50.0)
        lower_band = self._safe_float(row.get("lower_band"), close_price)
        upper_band = self._safe_float(row.get("upper_band"), close_price)
        atr_pct = max(self._safe_float(row.get("atr_pct"), 0.0), 0.002)

        recent = frame.tail(20)
        volume = recent["volume"].replace(0.0, np.nan).ffill().fillna(1.0)
        vwap = float((recent["close"] * volume).sum() / max(volume.sum(), 1.0))
        deviation = (close_price - vwap) / vwap if vwap > 0 else 0.0

        if (close_price <= lower_band and rsi <= 37.0) or deviation <= -0.012:
            expected_return = min(0.018, abs(deviation) * 0.9 + max(0.0, (40.0 - rsi) / 1000.0))
            confidence = min(0.92, 0.44 + (abs(deviation) * 16.0) + max(0.0, (35.0 - rsi) / 45.0))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="intraday",
                risk_estimate=atr_pct,
                reason="RSI and VWAP/Bollinger stretch favor a mean-reversion long.",
                metadata={"rsi": rsi, "vwap_deviation": deviation},
            )

        if (close_price >= upper_band and rsi >= 63.0) or deviation >= 0.012:
            expected_return = -min(0.018, abs(deviation) * 0.9 + max(0.0, (rsi - 60.0) / 1000.0))
            confidence = min(0.92, 0.44 + (abs(deviation) * 16.0) + max(0.0, (rsi - 65.0) / 45.0))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="intraday",
                risk_estimate=atr_pct,
                reason="RSI and VWAP/Bollinger stretch favor a mean-reversion short.",
                metadata={"rsi": rsi, "vwap_deviation": deviation},
            )

        return None
