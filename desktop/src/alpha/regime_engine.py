from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from alpha.base_alpha import MarketRegime
from core.config import RegimeEngineConfig

try:
    from ta.trend import ADXIndicator
except Exception:  # pragma: no cover - optional dependency guard
    ADXIndicator = None


class RegimeEngine:
    """Institutional regime classifier using trend, volatility, and liquidity state."""

    def __init__(self, config: RegimeEngineConfig | None = None) -> None:
        self.config = config or RegimeEngineConfig()

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _adx(self, frame: pd.DataFrame) -> float:
        if ADXIndicator is None or len(frame) < 20:
            trend_strength = self._safe_float(frame.iloc[-1].get("trend_strength"), 0.0)
            return min(50.0, max(5.0, trend_strength * 2000.0))
        try:
            indicator = ADXIndicator(frame["high"], frame["low"], frame["close"], window=14)
            series = indicator.adx().dropna()
            if series.empty:
                return 0.0
            return self._safe_float(series.iloc[-1], 0.0)
        except Exception:
            return 0.0

    def classify_frame(self, frame: pd.DataFrame | None, order_book: dict[str, Any] | None = None) -> MarketRegime:
        if frame is None or getattr(frame, "empty", True):
            return MarketRegime(primary="MEAN_REVERTING", active_regimes=("MEAN_REVERTING",), liquidity_score=0.0)

        working = pd.DataFrame(frame).copy()
        if len(working) < self.config.minimum_history:
            return MarketRegime(primary="MEAN_REVERTING", active_regimes=("MEAN_REVERTING",), liquidity_score=0.5)

        row = working.iloc[-1]
        returns = working["close"].pct_change().dropna()
        vol_window = max(5, min(self.config.volatility_window, len(returns)))
        realized_vol = self._safe_float(returns.tail(vol_window).std(ddof=0), 0.0) * np.sqrt(252.0)
        atr_pct = self._safe_float(row.get("atr_pct"), 0.0)
        adx = self._adx(working)
        trend_strength = self._safe_float(row.get("trend_strength"), 0.0)
        band_position = self._safe_float(row.get("band_position"), 0.5)
        volume_ratio = self._safe_float(row.get("volume_ratio"), 1.0)
        spread_bps = self._safe_float(row.get("order_book_spread_bps"), 0.0)
        if order_book:
            spread_bps = max(spread_bps, self._safe_float(order_book.get("spread_bps"), spread_bps))

        cluster_baseline = self._safe_float(
            returns.tail(max(10, vol_window * 2)).std(ddof=0),
            returns.tail(vol_window).std(ddof=0) if not returns.empty else 0.0,
        )
        cluster_ratio = 1.0
        if cluster_baseline > 0:
            cluster_ratio = (self._safe_float(returns.tail(vol_window).std(ddof=0), 0.0) / cluster_baseline)

        trending = adx >= self.config.adx_trending_threshold or trend_strength >= 0.008
        high_volatility = (
            atr_pct >= self.config.atr_high_vol_threshold
            or realized_vol >= self.config.realized_vol_high_threshold
            or cluster_ratio >= self.config.volatility_cluster_threshold
        )
        low_liquidity = (
            volume_ratio <= self.config.low_liquidity_volume_ratio
            or spread_bps >= self.config.low_liquidity_spread_bps
        )
        mean_reverting = not trending or (0.15 <= band_position <= 0.85 and adx < self.config.adx_trending_threshold)

        active: list[str] = []
        active.append("TRENDING" if trending else "MEAN_REVERTING")
        if high_volatility:
            active.append("HIGH_VOLATILITY")
        if low_liquidity:
            active.append("LOW_LIQUIDITY")
        if mean_reverting and "MEAN_REVERTING" not in active:
            active.append("MEAN_REVERTING")

        primary = "TRENDING" if trending else "MEAN_REVERTING"
        if low_liquidity and not trending:
            primary = "LOW_LIQUIDITY"
        elif high_volatility and not trending:
            primary = "HIGH_VOLATILITY"

        liquidity_score = max(0.0, min(1.0, volume_ratio / max(1.0, 1.0 + (spread_bps / 10.0))))
        return MarketRegime(
            primary=primary,
            active_regimes=tuple(dict.fromkeys(active)),
            adx=adx,
            atr_pct=atr_pct,
            realized_volatility=realized_vol,
            liquidity_score=liquidity_score,
            metadata={
                "trend_strength": trend_strength,
                "band_position": band_position,
                "volume_ratio": volume_ratio,
                "spread_bps": spread_bps,
                "volatility_cluster_ratio": cluster_ratio,
                "hmm_available": False,
            },
        )
