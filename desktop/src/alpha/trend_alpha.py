from __future__ import annotations

from alpha.base_alpha import AlphaContext, AlphaSignal, BaseAlphaModel


class TrendAlpha(BaseAlphaModel):
    name = "trend_alpha"
    supported_regimes = frozenset({"TRENDING", "HIGH_VOLATILITY"})

    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        row, frame = self._row(context)
        if row is None or frame is None:
            return None

        close_price = self._safe_float(row.get("close"), 0.0)
        if close_price <= 0:
            return None
        ema_fast = self._safe_float(row.get("ema_fast"), close_price)
        ema_slow = self._safe_float(row.get("ema_slow"), close_price)
        breakout_high = self._safe_float(row.get("breakout_high"), close_price)
        breakout_low = self._safe_float(row.get("breakout_low"), close_price)
        atr_pct = max(self._safe_float(row.get("atr_pct"), 0.0), 0.002)
        adx = self._safe_float((context.regime or {}).adx if context.regime is not None else 0.0, 0.0)

        ema_gap = (ema_fast - ema_slow) / close_price if close_price else 0.0
        breakout_up = max(0.0, (close_price - breakout_high) / close_price) if breakout_high > 0 else 0.0
        breakout_down = max(0.0, (breakout_low - close_price) / close_price) if breakout_low > 0 else 0.0

        if ema_gap > 0.0015 and (breakout_up > 0.0 or adx >= 20.0):
            expected_return = min(0.025, ema_gap * 1.8 + breakout_up * 2.6 + (adx / 3000.0))
            confidence = min(0.96, 0.48 + (ema_gap * 40.0) + (breakout_up * 30.0) + (adx / 100.0))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="swing",
                risk_estimate=atr_pct,
                reason="EMA structure and breakout slope support a long trend continuation.",
                metadata={"ema_gap": ema_gap, "breakout_distance": breakout_up, "adx": adx},
            )

        if ema_gap < -0.0015 and (breakout_down > 0.0 or adx >= 20.0):
            expected_return = -min(0.025, abs(ema_gap) * 1.8 + breakout_down * 2.6 + (adx / 3000.0))
            confidence = min(0.96, 0.48 + (abs(ema_gap) * 40.0) + (breakout_down * 30.0) + (adx / 100.0))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="swing",
                risk_estimate=atr_pct,
                reason="EMA structure and downside range expansion support a short trend continuation.",
                metadata={"ema_gap": ema_gap, "breakout_distance": breakout_down, "adx": adx},
            )

        return None
