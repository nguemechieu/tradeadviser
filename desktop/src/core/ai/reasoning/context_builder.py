from __future__ import annotations

"""
InvestPro ReasoningContextBuilder

Builds a compact, JSON-safe context payload for the reasoning engine.

The context is designed for:
- heuristic reasoning
- LLM reasoning
- trade review explanations
- audit logs
- agent memory
- Telegram/status messages

It combines:
- symbol/timeframe
- strategy signal
- latest indicators/features
- market regime snapshot
- portfolio snapshot
- risk limits
- execution hints
"""

import math
from datetime import datetime, timezone
from typing import Any, Optional


class ReasoningContextBuilder:
    FEATURE_KEYS = (
        "rsi",
        "ema_fast",
        "ema_slow",
        "sma_fast",
        "sma_slow",
        "atr",
        "atr_pct",
        "macd",
        "macd_signal",
        "macd_hist",
        "adx",
        "trend_strength",
        "momentum",
        "band_position",
        "volume",
        "volume_ratio",
        "open",
        "high",
        "low",
        "close",
        "return",
        "log_return",
        "realized_volatility",
        "spread_bps",
        "liquidity_score",
    )

    SIGNAL_KEYS = (
        "side",
        "action",
        "decision",
        "amount",
        "price",
        "confidence",
        "reason",
        "strategy_name",
        "execution_strategy",
        "expected_return",
        "risk_estimate",
        "alpha_score",
        "horizon",
        "stop_loss",
        "take_profit",
        "stop_price",
        "timeframe",
        "decision_id",
        "signal_source_agent",
        "consensus_status",
        "adaptive_weight",
        "adaptive_score",
    )

    DEFAULT_RISK_LIMITS = {
        "max_risk_per_trade": 0.02,
        "max_portfolio_risk": 0.10,
        "max_position_size_pct": 0.10,
        "max_gross_exposure_pct": 2.0,
    }

    def build(
        self,
        *,
        symbol: str,
        signal: dict[str, Any],
        dataset: Any = None,
        timeframe: str = "1h",
        regime_snapshot: dict[str, Any] | None = None,
        portfolio_snapshot: dict[str, Any] | None = None,
        risk_limits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_signal = dict(signal or {})
        normalized_symbol = str(symbol or normalized_signal.get(
            "symbol") or "").strip().upper()
        normalized_timeframe = str(
            timeframe
            or normalized_signal.get("timeframe")
            or "1h"
        ).strip() or "1h"

        indicators = self._extract_indicators(dataset)
        latest_candle = self._extract_latest_candle(dataset)

        portfolio = dict(portfolio_snapshot or {})
        regime = dict(regime_snapshot or {})
        risk = {**self.DEFAULT_RISK_LIMITS, **dict(risk_limits or {})}

        price = self._first_float(
            normalized_signal.get("price"),
            normalized_signal.get("expected_price"),
            indicators.get("close"),
            latest_candle.get("close"),
        )

        quantity = self._coerce_float(normalized_signal.get("amount"))
        notional = abs(quantity * price) if quantity and price else 0.0

        equity = self._coerce_float(portfolio.get("equity"))
        gross_exposure = self._coerce_float(portfolio.get("gross_exposure"))
        net_exposure = self._coerce_float(portfolio.get("net_exposure"))

        gross_exposure_pct = gross_exposure / equity if equity > 0 else 0.0
        net_exposure_pct = net_exposure / equity if equity > 0 else 0.0
        order_notional_pct = notional / equity if equity > 0 else 0.0

        side = self._normalize_side(
            normalized_signal.get("side")
            or normalized_signal.get("action")
            or normalized_signal.get("decision")
        )

        context = {
            "schema_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "decision_id": str(normalized_signal.get("decision_id") or "").strip(),
            "price": price,
            "quantity": quantity,
            "notional": notional,
            "order_notional_pct": order_notional_pct,
            "strategy_signal": side,
            "strategy_name": str(normalized_signal.get("strategy_name") or "").strip() or "Bot",
            "signal_confidence": self._coerce_float(normalized_signal.get("confidence")),
            "signal_reason": str(normalized_signal.get("reason") or "").strip(),
            "execution_strategy": str(normalized_signal.get("execution_strategy") or "").strip(),
            "expected_return": self._coerce_float(normalized_signal.get("expected_return")),
            "risk_estimate": self._coerce_float(normalized_signal.get("risk_estimate")),
            "alpha_score": self._coerce_float(normalized_signal.get("alpha_score")),
            "horizon": normalized_signal.get("horizon"),
            "stop_loss": self._coerce_float(normalized_signal.get("stop_loss")),
            "take_profit": self._coerce_float(normalized_signal.get("take_profit")),
            "stop_price": self._coerce_float(normalized_signal.get("stop_price")),
            "signal_source_agent": str(normalized_signal.get("signal_source_agent") or "").strip(),
            "consensus_status": str(normalized_signal.get("consensus_status") or "").strip(),
            "adaptive_weight": self._coerce_float(normalized_signal.get("adaptive_weight"), default=1.0),
            "adaptive_score": self._coerce_float(normalized_signal.get("adaptive_score")),
            "regime": {
                "state": str(
                    regime.get("regime")
                    or regime.get("state")
                    or regime.get("primary")
                    or normalized_signal.get("regime")
                    or "unknown"
                ).strip().lower(),
                "volatility": str(regime.get("volatility") or "unknown").strip().lower(),
                "atr_pct": self._coerce_float(regime.get("atr_pct")),
                "trend_strength": self._coerce_float(regime.get("trend_strength")),
                "momentum": self._coerce_float(regime.get("momentum")),
                "band_position": self._coerce_float(regime.get("band_position")),
                "active_regimes": list(regime.get("active_regimes") or []),
                "adx": self._coerce_float(regime.get("adx")),
                "realized_volatility": self._coerce_float(regime.get("realized_volatility")),
                "liquidity_score": self._coerce_float(regime.get("liquidity_score")),
                "metadata": self._json_safe(regime.get("metadata") or {}),
            },
            "indicators": indicators,
            "latest_candle": latest_candle,
            "portfolio": {
                "equity": equity,
                "cash": self._coerce_float(portfolio.get("cash")),
                "gross_exposure": gross_exposure,
                "net_exposure": net_exposure,
                "gross_exposure_pct": gross_exposure_pct,
                "net_exposure_pct": net_exposure_pct,
                "position_count": int(self._coerce_float(portfolio.get("position_count"), 0.0)),
                "positions": self._normalize_positions(portfolio.get("positions")),
            },
            "risk_limits": {
                "max_risk_per_trade": self._coerce_float(risk.get("max_risk_per_trade")),
                "max_portfolio_risk": self._coerce_float(risk.get("max_portfolio_risk")),
                "max_position_size_pct": self._coerce_float(risk.get("max_position_size_pct")),
                "max_gross_exposure_pct": self._coerce_float(risk.get("max_gross_exposure_pct")),
            },
            "raw_signal": self._filtered_signal(normalized_signal),
        }

        return self._json_safe(context)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_indicators(self, dataset: Any) -> dict[str, Any]:
        frame = getattr(dataset, "frame", None)
        if frame is None or getattr(frame, "empty", True):
            return {}

        try:
            row = frame.iloc[-1]
        except Exception:
            return {}

        indicators: dict[str, Any] = {}

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

    def _extract_latest_candle(self, dataset: Any) -> dict[str, Any]:
        frame = getattr(dataset, "frame", None)

        if frame is not None and not getattr(frame, "empty", True):
            try:
                row = frame.iloc[-1]
                return {
                    "timestamp": self._string_value(row.get("timestamp")),
                    "open": self._coerce_float(row.get("open")),
                    "high": self._coerce_float(row.get("high")),
                    "low": self._coerce_float(row.get("low")),
                    "close": self._coerce_float(row.get("close")),
                    "volume": self._coerce_float(row.get("volume")),
                }
            except Exception:
                pass

        to_candles = getattr(dataset, "to_candles", None)
        if callable(to_candles):
            try:
                candles = list(to_candles() or [])
            except Exception:
                candles = []

            if candles:
                candle = candles[-1]
                return {
                    "timestamp": self._string_value(self._field(candle, "timestamp")),
                    "open": self._coerce_float(self._field(candle, "open")),
                    "high": self._coerce_float(self._field(candle, "high")),
                    "low": self._coerce_float(self._field(candle, "low")),
                    "close": self._coerce_float(self._field(candle, "close")),
                    "volume": self._coerce_float(self._field(candle, "volume")),
                }

        return {}

    def _normalize_positions(self, positions: Any) -> list[dict[str, Any]]:
        if not positions:
            return []

        if isinstance(positions, dict):
            iterable = []
            for symbol, position in positions.items():
                if isinstance(position, dict):
                    payload = dict(position)
                    payload.setdefault("symbol", symbol)
                    iterable.append(payload)
                else:
                    iterable.append(
                        {
                            "symbol": symbol,
                            "quantity": self._field(position, "quantity"),
                            "avg_price": self._field(position, "avg_price"),
                            "last_price": self._field(position, "last_price"),
                            "absolute_exposure": self._field(position, "absolute_exposure"),
                            "signed_exposure": self._field(position, "signed_exposure"),
                        }
                    )
        elif isinstance(positions, list):
            iterable = positions
        else:
            return []

        output: list[dict[str, Any]] = []

        for position in iterable:
            if isinstance(position, dict):
                symbol = position.get("symbol")
                quantity = position.get("quantity", position.get(
                    "amount", position.get("size")))
                avg_price = position.get(
                    "avg_price", position.get("entry_price"))
                last_price = position.get("last_price", position.get(
                    "price", position.get("mark_price")))
                absolute_exposure = position.get(
                    "absolute_exposure", position.get("exposure"))
                signed_exposure = position.get("signed_exposure")
            else:
                symbol = self._field(position, "symbol")
                quantity = self._field(position, "quantity")
                avg_price = self._field(position, "avg_price")
                last_price = self._field(position, "last_price")
                absolute_exposure = self._field(position, "absolute_exposure")
                signed_exposure = self._field(position, "signed_exposure")

            output.append(
                {
                    "symbol": str(symbol or "").strip().upper(),
                    "quantity": self._coerce_float(quantity),
                    "avg_price": self._coerce_float(avg_price),
                    "last_price": self._coerce_float(last_price),
                    "absolute_exposure": self._coerce_float(absolute_exposure),
                    "signed_exposure": self._coerce_float(signed_exposure),
                }
            )

        return output

    def _filtered_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        return {
            key: self._json_safe(signal.get(key))
            for key in self.SIGNAL_KEYS
            if key in signal
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _normalize_side(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in {"LONG", "BUY"}:
            return "BUY"
        if text in {"SHORT", "SELL"}:
            return "SELL"
        if text in {"HOLD", "WAIT", "NONE", "NEUTRAL"}:
            return "HOLD"
        return text or "HOLD"

    def _first_float(self, *values: Any, default: float = 0.0) -> float:
        for value in values:
            numeric = self._coerce_float(value, default=None)
            if numeric is not None:
                return numeric
        return default

    def _field(self, obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def _string_value(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)

    def _coerce_float(self, value: Any, default: Optional[float] = 0.0) -> Optional[float]:
        if value in (None, ""):
            return default

        try:
            number = float(value)
        except Exception:
            return default

        if not math.isfinite(number):
            return default

        return number

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, (str, int, bool)):
            return value

        if isinstance(value, float):
            if not math.isfinite(value):
                return None
            return value

        if isinstance(value, dict):
            return {
                str(key): self._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._json_safe(item)
                for item in value
            ]

        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass

        return str(value)
