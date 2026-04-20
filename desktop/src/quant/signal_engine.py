from typing import Any

from alpha import AlphaAggregator, AlphaContext
from quant.regime_engine import RegimeEngine
from strategy.strategy import Strategy


class SignalEngine:
    VERSION = "signal-engine-v2"

    _ALPHA_MODEL_MAP = {
        "Trend Following": ["trend_alpha", "momentum_alpha", "ml_alpha"],
        "Breakout": ["trend_alpha", "momentum_alpha", "ml_alpha"],
        "EMA Cross": ["trend_alpha", "ml_alpha"],
        "Momentum Continuation": ["momentum_alpha", "trend_alpha", "ml_alpha"],
        "Pullback Trend": ["trend_alpha", "mean_reversion_alpha", "ml_alpha"],
        "Volatility Breakout": ["momentum_alpha", "trend_alpha", "ml_alpha"],
        "MACD Trend": ["trend_alpha", "momentum_alpha", "ml_alpha"],
        "Mean Reversion": ["mean_reversion_alpha", "ml_alpha"],
        "Range Fade": ["mean_reversion_alpha", "stat_arb_alpha", "ml_alpha"],
        "Donchian Trend": ["trend_alpha", "momentum_alpha", "ml_alpha"],
        "Bollinger Squeeze": ["momentum_alpha", "trend_alpha", "ml_alpha"],
        "ATR Compression Breakout": ["momentum_alpha", "trend_alpha", "ml_alpha"],
        "RSI Failure Swing": ["mean_reversion_alpha", "ml_alpha"],
        "Volume Spike Reversal": ["mean_reversion_alpha", "momentum_alpha", "ml_alpha"],
        "ML Model": ["ml_alpha"],
        "AI Hybrid": ["trend_alpha", "momentum_alpha", "mean_reversion_alpha", "ml_alpha"],
    }

    def __init__(self, strategy_registry, regime_engine=None, alpha_aggregator=None):
        self.strategy_registry = strategy_registry
        self.regime_engine = regime_engine or RegimeEngine()
        self.alpha_aggregator = alpha_aggregator or AlphaAggregator()

    def _resolve_strategy(self, strategy_name=None):
        if hasattr(self.strategy_registry, "resolve_strategy"):
            return self.strategy_registry.resolve_strategy(strategy_name)

        resolve_method = getattr(self.strategy_registry, "_resolve_strategy", None)
        if callable(resolve_method):
            return resolve_method(strategy_name)

        return self.strategy_registry

    def _base_strategy_name(self, strategy_name=None):
        return Strategy.resolve_signal_strategy_name(strategy_name)

    def _feature_frame(self, strategy, candles=None, dataset=None):
        if strategy is None:
            return getattr(dataset, "frame", None)
        candle_rows = candles or []
        if not candle_rows and dataset is not None and hasattr(dataset, "to_candles"):
            try:
                candle_rows = dataset.to_candles()
            except Exception:
                candle_rows = []
        if candle_rows and hasattr(strategy, "compute_features"):
            feature_frame = strategy.compute_features(candle_rows)
            if feature_frame is not None and not feature_frame.empty:
                return feature_frame
        return getattr(dataset, "frame", None)

    def _allowed_alpha_models(self, strategy_name=None):
        base_name = self._base_strategy_name(strategy_name)
        return list(self._ALPHA_MODEL_MAP.get(base_name, ["trend_alpha", "mean_reversion_alpha", "momentum_alpha", "ml_alpha"]))

    def _alpha_amount(self, strategy, opportunity):
        base_amount = float(getattr(strategy, "signal_amount", 1.0) or 1.0)
        scale = 0.45 + float(opportunity.confidence or 0.0) + min(0.35, float(opportunity.alpha_score or 0.0))
        scale = max(0.35, min(1.75, scale))
        return base_amount * scale

    def _build_alpha_signal(self, *, strategy, strategy_name, symbol, feature_frame, opportunity):
        feature_version = "quant-v1"
        latest_price = 0.0
        if feature_frame is not None and not getattr(feature_frame, "empty", True):
            try:
                row = feature_frame.iloc[-1]
                feature_version = str(row.get("feature_version", feature_version) or feature_version)
                latest_price = float(row.get("close") or 0.0)
            except Exception:
                latest_price = 0.0
        opportunity.metadata["price"] = latest_price
        signal = {
            "symbol": str(symbol or "").upper().strip(),
            "side": opportunity.side,
            "amount": self._alpha_amount(strategy, opportunity),
            "confidence": float(opportunity.confidence or 0.0),
            "reason": str(opportunity.reason or "Alpha fusion layer found a directional edge.").strip(),
            "price": latest_price if latest_price > 0 else None,
            "regime": opportunity.regime.primary.lower(),
            "feature_version": feature_version,
            "signal_engine_version": self.VERSION,
            "strategy_name": str(strategy_name or getattr(strategy, "strategy_name", "Alpha Fusion")),
            "expected_return": float(opportunity.expected_return or 0.0),
            "risk_estimate": float(opportunity.risk_estimate or 0.0),
            "alpha_score": float(opportunity.alpha_score or 0.0),
            "alpha_models": list(opportunity.selected_models),
            "alpha_model_count": len(list(opportunity.selected_models)),
            "alpha_breakdown": [component.to_dict() for component in list(opportunity.components or [])],
            "horizon": str(opportunity.horizon or "intraday"),
            "regime_snapshot": opportunity.regime.to_dict(),
        }
        if signal["price"] is None:
            signal.pop("price")
        return signal

    def _legacy_signal(self, *, strategy, candles=None, dataset=None, strategy_name=None, symbol=None):
        feature_frame = self._feature_frame(strategy, candles=candles, dataset=dataset)
        if feature_frame is None or feature_frame.empty:
            return None

        regime = self.regime_engine.classify_frame(feature_frame)
        signal = None
        if hasattr(strategy, "generate_signal_from_features"):
            signal = strategy.generate_signal_from_features(feature_frame, strategy_name=strategy_name)
        elif candles is not None and hasattr(strategy, "generate_signal"):
            signal = strategy.generate_signal(candles, strategy_name=strategy_name)

        if not signal:
            return None

        normalized = dict(signal)
        normalized.setdefault("regime", regime)
        normalized.setdefault("feature_version", feature_frame.iloc[-1].get("feature_version", "quant-v1"))
        normalized.setdefault("signal_engine_version", self.VERSION)
        normalized.setdefault(
            "regime_snapshot",
            {
                "primary": regime.upper(),
                "active_regimes": [regime.upper()],
                "metadata": {},
            },
        )
        if symbol:
            normalized["symbol"] = str(symbol).upper().strip()
        if strategy_name:
            normalized["strategy_name"] = str(strategy_name)
        if normalized.get("price") is None:
            try:
                normalized["price"] = float(feature_frame.iloc[-1]["close"])
            except Exception:
                pass
        return normalized

    def generate_signal(self, candles=None, dataset=None, strategy_name=None, symbol=None):
        strategy: Any = self._resolve_strategy(strategy_name)
        if strategy is None:
            return None

        feature_frame = self._feature_frame(strategy, candles=candles, dataset=dataset)
        base_strategy = self._base_strategy_name(strategy_name or getattr(strategy, "strategy_name", None))
        prefer_legacy = base_strategy == "ML Model"
        if feature_frame is not None and not feature_frame.empty and not prefer_legacy:
            opportunity = self.alpha_aggregator.evaluate_symbol(
                AlphaContext(
                    symbol=str(symbol or "").upper().strip(),
                    timeframe=str(getattr(dataset, "timeframe", None) or "1h"),
                    frame=getattr(dataset, "frame", None),
                    feature_frame=feature_frame,
                    candles=list(candles or []),
                ),
                allowed_models=self._allowed_alpha_models(strategy_name or getattr(strategy, "strategy_name", None)),
            )
            if opportunity is not None and float(opportunity.confidence or 0.0) >= float(getattr(strategy, "min_confidence", 0.55) or 0.55):
                return self._build_alpha_signal(
                    strategy=strategy,
                    strategy_name=strategy_name or getattr(strategy, "strategy_name", None),
                    symbol=symbol,
                    feature_frame=feature_frame,
                    opportunity=opportunity,
                )

        return self._legacy_signal(
            strategy=strategy,
            candles=candles,
            dataset=dataset,
            strategy_name=strategy_name,
            symbol=symbol,
        )
