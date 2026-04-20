from __future__ import annotations

from alpha.base_alpha import AlphaContext, AlphaSignal, BaseAlphaModel


class MomentumAlpha(BaseAlphaModel):
    name = "momentum_alpha"
    supported_regimes = frozenset({"TRENDING", "HIGH_VOLATILITY"})

    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        row, frame = self._row(context)
        if row is None or frame is None:
            return None

        momentum = self._safe_float(row.get("momentum"), 0.0)
        volume_ratio = self._safe_float(row.get("volume_ratio"), 1.0)
        atr_pct = max(self._safe_float(row.get("atr_pct"), 0.0), 0.002)
        prev_row = frame.iloc[-2]
        prev_atr_pct = max(self._safe_float(prev_row.get("atr_pct"), atr_pct), 1e-6)
        atr_expansion = atr_pct / prev_atr_pct

        if momentum >= 0.01 and volume_ratio >= 1.08 and atr_expansion >= 1.02:
            expected_return = min(0.03, momentum * 1.35 + (volume_ratio - 1.0) / 12.0)
            confidence = min(0.95, 0.47 + min(0.30, momentum * 8.0) + min(0.20, (volume_ratio - 1.0) * 0.8))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="intraday",
                risk_estimate=atr_pct,
                reason="Volume-backed volatility expansion favors momentum continuation higher.",
                metadata={"momentum": momentum, "volume_ratio": volume_ratio, "atr_expansion": atr_expansion},
            )

        if momentum <= -0.01 and volume_ratio >= 1.08 and atr_expansion >= 1.02:
            expected_return = -min(0.03, abs(momentum) * 1.35 + (volume_ratio - 1.0) / 12.0)
            confidence = min(0.95, 0.47 + min(0.30, abs(momentum) * 8.0) + min(0.20, (volume_ratio - 1.0) * 0.8))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="intraday",
                risk_estimate=atr_pct,
                reason="Volume-backed volatility expansion favors downside momentum continuation.",
                metadata={"momentum": momentum, "volume_ratio": volume_ratio, "atr_expansion": atr_expansion},
            )

        return None
