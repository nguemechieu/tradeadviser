from __future__ import annotations

from typing import Any


class ReasoningContextBuilder:
    FEATURE_KEYS = (
        "rsi",
        "ema_fast",
        "ema_slow",
        "atr",
        "atr_pct",
        "macd",
        "macd_signal",
        "macd_hist",
        "trend_strength",
        "momentum",
        "band_position",
        "volume_ratio",
        "close",
    )

    def build(
        self,
        *,
        symbol: str,
        signal: dict[str, Any],
        dataset=None,
        timeframe: str = "1h",
        regime_snapshot: dict[str, Any] | None = None,
        portfolio_snapshot: dict[str, Any] | None = None,
        risk_limits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_signal = dict(signal or {})
        indicators = self._extract_indicators(dataset)
        portfolio = dict(portfolio_snapshot or {})
        regime = dict(regime_snapshot or {})

        return {
            "symbol": str(symbol or "").strip().upper(),
            "timeframe": str(timeframe or "1h").strip() or "1h",
            "price": self._coerce_float(normalized_signal.get("price")),
            "strategy_signal": str(normalized_signal.get("side") or "").strip().upper(),
            "strategy_name": str(normalized_signal.get("strategy_name") or "").strip() or "Bot",
            "signal_confidence": self._coerce_float(normalized_signal.get("confidence")),
            "signal_reason": str(normalized_signal.get("reason") or "").strip(),
            "execution_strategy": str(normalized_signal.get("execution_strategy") or "").strip(),
            "quantity": self._coerce_float(normalized_signal.get("amount")),
            "regime": {
                "state": str(regime.get("regime") or normalized_signal.get("regime") or "unknown").strip().lower(),
                "volatility": str(regime.get("volatility") or "unknown").strip().lower(),
                "atr_pct": self._coerce_float(regime.get("atr_pct")),
                "trend_strength": self._coerce_float(regime.get("trend_strength")),
                "momentum": self._coerce_float(regime.get("momentum")),
                "band_position": self._coerce_float(regime.get("band_position")),
            },
            "indicators": indicators,
            "portfolio": {
                "equity": self._coerce_float(portfolio.get("equity")),
                "cash": self._coerce_float(portfolio.get("cash")),
                "gross_exposure": self._coerce_float(portfolio.get("gross_exposure")),
                "net_exposure": self._coerce_float(portfolio.get("net_exposure")),
                "position_count": int(self._coerce_float(portfolio.get("position_count"), 0.0)),
            },
            "risk_limits": {
                "max_risk_per_trade": self._coerce_float((risk_limits or {}).get("max_risk_per_trade")),
                "max_portfolio_risk": self._coerce_float((risk_limits or {}).get("max_portfolio_risk")),
                "max_position_size_pct": self._coerce_float((risk_limits or {}).get("max_position_size_pct")),
                "max_gross_exposure_pct": self._coerce_float((risk_limits or {}).get("max_gross_exposure_pct")),
            },
        }

    def _extract_indicators(self, dataset) -> dict[str, Any]:
        frame = getattr(dataset, "frame", None)
        if frame is None or getattr(frame, "empty", True):
            return {}
        try:
            row = frame.iloc[-1]
        except Exception:
            return {}

        indicators = {}
        for key in self.FEATURE_KEYS:
            try:
                value = row.get(key)
            except Exception:
                value = None
            if value in (None, ""):
                continue
            numeric = self._coerce_float(value, default=None)
            indicators[key] = numeric if numeric is not None else str(value)
        return indicators

    @staticmethod
    def _coerce_float(value, default=0.0):
        if value in (None, ""):
            return default
        try:
            return float(value)
        except Exception:
            return default
