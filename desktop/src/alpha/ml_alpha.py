from __future__ import annotations

import numpy as np

from alpha.base_alpha import AlphaContext, AlphaSignal, BaseAlphaModel

try:
    from sklearn.linear_model import LogisticRegression
except Exception:  # pragma: no cover - optional dependency guard
    LogisticRegression = None


class MLAlpha(BaseAlphaModel):
    name = "ml_alpha"
    supported_regimes = frozenset({"TRENDING", "MEAN_REVERTING", "HIGH_VOLATILITY", "LOW_LIQUIDITY"})
    minimum_history = 60

    FEATURE_COLUMNS = (
        "return_1",
        "return_5",
        "rsi",
        "trend_strength",
        "atr_pct",
        "band_position",
        "momentum",
        "volume_ratio",
    )

    def _heuristic_probability(self, row) -> float:
        rsi = self._safe_float(row.get("rsi"), 50.0)
        trend_strength = self._safe_float(row.get("trend_strength"), 0.0)
        momentum = self._safe_float(row.get("momentum"), 0.0)
        volume_ratio = self._safe_float(row.get("volume_ratio"), 1.0)
        score = 0.0
        score += max(-1.0, min(1.0, momentum * 30.0))
        score += max(-1.0, min(1.0, trend_strength * 90.0))
        score += max(-0.5, min(0.5, (volume_ratio - 1.0) * 1.5))
        score += max(-0.8, min(0.8, (50.0 - rsi) / 35.0))
        probability = 1.0 / (1.0 + np.exp(-score))
        return float(probability)

    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        row, frame = self._row(context)
        if row is None or frame is None:
            return None

        working = frame.copy()
        for column in self.FEATURE_COLUMNS:
            if column not in working.columns:
                return None
        working = working.dropna(subset=list(self.FEATURE_COLUMNS) + ["close"])
        if len(working) < self.minimum_history:
            return None

        future_return = working["close"].shift(-1) / working["close"] - 1.0
        train = working.iloc[:-1].copy()
        train["target"] = (future_return.iloc[:-1] > 0).astype(int)
        train = train.dropna(subset=list(self.FEATURE_COLUMNS) + ["target"])
        latest_features = working.iloc[[-1]][list(self.FEATURE_COLUMNS)]
        probability_up = None

        if LogisticRegression is not None and len(train) >= 40 and train["target"].nunique() >= 2:
            try:
                model = LogisticRegression(max_iter=300)
                model.fit(train[list(self.FEATURE_COLUMNS)], train["target"])
                probability_up = float(model.predict_proba(latest_features)[0][1])
            except Exception:
                probability_up = None

        if probability_up is None:
            probability_up = self._heuristic_probability(working.iloc[-1])

        confidence = abs(probability_up - 0.5) * 2.0
        if confidence < 0.08:
            return None
        atr_pct = max(self._safe_float(row.get("atr_pct"), 0.0), 0.002)
        realized = working["close"].pct_change().dropna().tail(20).std(ddof=0)
        risk_estimate = max(atr_pct, self._safe_float(realized, 0.0))
        signed_edge = ((probability_up - 0.5) * 2.0) * max(atr_pct, 0.004)
        expected_return = max(-0.025, min(0.025, signed_edge))
        return self._signal(
            context,
            expected_return=expected_return,
            confidence=min(0.94, max(0.0, confidence)),
            horizon="intraday",
            risk_estimate=risk_estimate,
            reason="Statistical classifier forecasts the next return direction with a positive edge.",
            metadata={"probability_up": probability_up, "feature_columns": list(self.FEATURE_COLUMNS)},
        )
