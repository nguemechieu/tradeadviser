from __future__ import annotations

import numpy as np
import pandas as pd

from alpha.base_alpha import AlphaContext, AlphaSignal, BaseAlphaModel


class StatisticalArbitrageAlpha(BaseAlphaModel):
    name = "stat_arb_alpha"
    supported_regimes = frozenset({"MEAN_REVERTING", "HIGH_VOLATILITY"})

    def _best_pair(self, context: AlphaContext, base_returns: pd.Series) -> tuple[str | None, pd.DataFrame | None]:
        best_symbol = None
        best_frame = None
        best_corr = 0.0
        for symbol, frame in dict(context.cross_sectional_frames or {}).items():
            candidate = pd.DataFrame(frame).copy()
            if candidate.empty or "close" not in candidate.columns:
                continue
            aligned = pd.concat(
                [base_returns.reset_index(drop=True), candidate["close"].pct_change().dropna().reset_index(drop=True)],
                axis=1,
                join="inner",
            ).dropna()
            if len(aligned) < 30:
                continue
            corr = abs(float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]) or 0.0))
            if corr > best_corr:
                best_corr = corr
                best_symbol = str(symbol)
                best_frame = candidate
        return best_symbol, best_frame

    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        row, frame = self._row(context)
        if row is None or frame is None or "close" not in frame.columns:
            return None

        base_returns = frame["close"].pct_change().dropna()
        pair_symbol, pair_frame = self._best_pair(context, base_returns)
        if pair_symbol is None or pair_frame is None:
            return None

        aligned = pd.concat(
            [frame["close"].reset_index(drop=True), pair_frame["close"].reset_index(drop=True)],
            axis=1,
            join="inner",
        ).dropna()
        if len(aligned) < 40:
            return None

        x = np.log(aligned.iloc[:, 1].clip(lower=1e-9))
        y = np.log(aligned.iloc[:, 0].clip(lower=1e-9))
        beta = float(np.cov(y, x)[0][1] / max(np.var(x), 1e-9))
        spread = y - (beta * x)
        zscore = float((spread.iloc[-1] - spread.mean()) / max(spread.std(ddof=0), 1e-9))
        atr_pct = max(self._safe_float(row.get("atr_pct"), 0.0), 0.002)

        if abs(zscore) < 1.4:
            return None

        expected_return = min(0.02, abs(zscore) / 120.0)
        expected_return = -expected_return if zscore > 0 else expected_return
        confidence = min(0.90, 0.46 + min(0.34, abs(zscore) / 6.0))
        return self._signal(
            context,
            expected_return=expected_return,
            confidence=confidence,
            horizon="intraday",
            risk_estimate=atr_pct,
            reason="Spread z-score is dislocated relative to its correlated pair and favors convergence.",
            metadata={"pair_symbol": pair_symbol, "spread_zscore": zscore, "hedge_ratio": beta},
        )
