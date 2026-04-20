from __future__ import annotations

from alpha.base_alpha import AlphaContext, AlphaSignal, BaseAlphaModel


class MicrostructureAlpha(BaseAlphaModel):
    name = "microstructure_alpha"
    supported_regimes = frozenset({"TRENDING", "LOW_LIQUIDITY", "HIGH_VOLATILITY"})
    minimum_history = 10

    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        row, _frame = self._row(context)
        if row is None:
            return None

        imbalance = self._safe_float(row.get("order_book_imbalance"), 0.0)
        spread_bps = self._safe_float(row.get("order_book_spread_bps"), 0.0)
        wall_imbalance = self._safe_float(row.get("liquidity_wall_imbalance"), 0.0)
        atr_pct = max(self._safe_float(row.get("atr_pct"), 0.0), 0.0025)

        if spread_bps > 25.0:
            return None
        directional_edge = imbalance + (0.5 * wall_imbalance)
        if directional_edge >= 0.18:
            expected_return = min(0.012, directional_edge / 18.0)
            confidence = min(0.88, 0.50 + directional_edge)
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="scalp",
                risk_estimate=atr_pct,
                reason="Order-book depth is materially bid-heavy with supportive liquidity walls.",
                metadata={"order_book_imbalance": imbalance, "liquidity_wall_imbalance": wall_imbalance, "spread_bps": spread_bps},
            )
        if directional_edge <= -0.18:
            expected_return = -min(0.012, abs(directional_edge) / 18.0)
            confidence = min(0.88, 0.50 + abs(directional_edge))
            return self._signal(
                context,
                expected_return=expected_return,
                confidence=confidence,
                horizon="scalp",
                risk_estimate=atr_pct,
                reason="Order-book depth is materially ask-heavy with adverse liquidity pressure.",
                metadata={"order_book_imbalance": imbalance, "liquidity_wall_imbalance": wall_imbalance, "spread_bps": spread_bps},
            )
        return None
