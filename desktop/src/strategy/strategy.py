# strategy/strategy.py

import pandas as pd
import numpy as np

from quant.feature_pipeline import FeaturePipeline, FeaturePipelineConfig
from quant.signal_schema import SignalDecision


CORE_STRATEGY_NAMES = (
    "Trend Following",
    "Mean Reversion",
    "Breakout",
    "AI Hybrid",
    "EMA Cross",
    "Momentum Continuation",
    "Pullback Trend",
    "Volatility Breakout",
    "MACD Trend",
    "Range Fade",
    "Donchian Trend",
    "Bollinger Squeeze",
    "ATR Compression Breakout",
    "RSI Failure Swing",
    "Volume Spike Reversal",
    "ML Model",
    "Adaptive Momentum Pullback",
)

VARIANT_STYLE_PROFILES = (
    ("Scalp", {"rsi_period": 7, "ema_fast": 8, "ema_slow": 21, "atr_period": 7, "breakout_lookback": 8}),
    ("Intraday", {"rsi_period": 9, "ema_fast": 12, "ema_slow": 26, "atr_period": 10, "breakout_lookback": 12}),
    ("Swing", {"rsi_period": 14, "ema_fast": 20, "ema_slow": 50, "atr_period": 14, "breakout_lookback": 20}),
    ("Position", {"rsi_period": 21, "ema_fast": 34, "ema_slow": 89, "atr_period": 21, "breakout_lookback": 34}),
    ("Asia Session", {"rsi_period": 10, "ema_fast": 13, "ema_slow": 34, "atr_period": 10, "breakout_lookback": 10}),
    ("London Session", {"rsi_period": 11, "ema_fast": 15, "ema_slow": 35, "atr_period": 12, "breakout_lookback": 14}),
    ("New York Session", {"rsi_period": 12, "ema_fast": 17, "ema_slow": 40, "atr_period": 12, "breakout_lookback": 16}),
    ("Volatility Focus", {"rsi_period": 10, "ema_fast": 18, "ema_slow": 45, "atr_period": 20, "breakout_lookback": 18}),
    ("Mean Revert Focus", {"rsi_period": 6, "ema_fast": 10, "ema_slow": 24, "atr_period": 9, "breakout_lookback": 12, "oversold_threshold": 30, "overbought_threshold": 70}),
    ("Trend Strength", {"rsi_period": 16, "ema_fast": 24, "ema_slow": 55, "atr_period": 16, "breakout_lookback": 24}),
    ("Multi Confirm", {"rsi_period": 14, "ema_fast": 21, "ema_slow": 55, "atr_period": 18, "breakout_lookback": 21}),
)

VARIANT_RISK_PROFILES = (
    ("Conservative", {"oversold_threshold": 32, "overbought_threshold": 68, "min_confidence": 0.64, "signal_amount": 0.50}),
    ("Balanced", {"oversold_threshold": 35, "overbought_threshold": 65, "min_confidence": 0.58, "signal_amount": 1.00}),
    ("Aggressive", {"oversold_threshold": 38, "overbought_threshold": 62, "min_confidence": 0.54, "signal_amount": 1.35}),
    ("Institutional", {"oversold_threshold": 34, "overbought_threshold": 66, "min_confidence": 0.60, "signal_amount": 0.85}),
    ("Quant", {"oversold_threshold": 33, "overbought_threshold": 67, "min_confidence": 0.57, "signal_amount": 1.15}),
)

VARIANT_MARKET_CONTEXT_PROFILES = (
    ("FX Core", {"ema_fast": 13, "ema_slow": 34, "atr_period": 10, "breakout_lookback": 12, "min_confidence": 0.60}),
    ("Crypto Expansion", {"ema_fast": 21, "ema_slow": 55, "atr_period": 18, "breakout_lookback": 24, "signal_amount": 1.20}),
    ("Equities Macro", {"ema_fast": 34, "ema_slow": 89, "atr_period": 20, "breakout_lookback": 34, "min_confidence": 0.62}),
    ("Futures Carry", {"ema_fast": 18, "ema_slow": 48, "atr_period": 16, "breakout_lookback": 20, "signal_amount": 1.10}),
    ("Commodities Trend", {"ema_fast": 21, "ema_slow": 60, "atr_period": 22, "breakout_lookback": 28, "min_confidence": 0.61}),
    ("Index Rotation", {"ema_fast": 26, "ema_slow": 65, "atr_period": 18, "breakout_lookback": 26, "signal_amount": 0.95}),
)

BASE_STRATEGY_ALIASES = {
    "DEFAULT": "Trend Following",
    "EMA_RSI": "Trend Following",
    "TREND": "Trend Following",
    "TREND FOLLOWING": "Trend Following",
    "MEAN REVERSION": "Mean Reversion",
    "MEAN_REVERSION": "Mean Reversion",
    "BREAKOUT": "Breakout",
    "EMA CROSS": "EMA Cross",
    "EMA_CROSS": "EMA Cross",
    "MOMENTUM": "Momentum Continuation",
    "MOMENTUM CONTINUATION": "Momentum Continuation",
    "PULLBACK": "Pullback Trend",
    "PULLBACK TREND": "Pullback Trend",
    "VOLATILITY": "Volatility Breakout",
    "VOLATILITY BREAKOUT": "Volatility Breakout",
    "MACD": "MACD Trend",
    "MACD_TREND": "MACD Trend",
    "MACD TREND": "MACD Trend",
    "RANGE": "Range Fade",
    "RANGE FADE": "Range Fade",
    "DONCHIAN": "Donchian Trend",
    "DONCHIAN TREND": "Donchian Trend",
    "BOLLINGER": "Bollinger Squeeze",
    "BOLLINGER SQUEEZE": "Bollinger Squeeze",
    "ATR COMPRESSION": "ATR Compression Breakout",
    "ATR_COMPRESSION": "ATR Compression Breakout",
    "ATR COMPRESSION BREAKOUT": "ATR Compression Breakout",
    "RSI FAILURE": "RSI Failure Swing",
    "RSI FAILURE SWING": "RSI Failure Swing",
    "VOLUME SPIKE": "Volume Spike Reversal",
    "VOLUME SPIKE REVERSAL": "Volume Spike Reversal",
    "RSI_MEAN_REVERSION": "Mean Reversion",
    "AI": "AI Hybrid",
    "AI HYBRID": "AI Hybrid",
    "LSTM": "AI Hybrid",
    "ML": "ML Model",
    "ML MODEL": "ML Model",
}


def _combine_strategy_params(*param_sets):
    merged = {}
    for params in param_sets:
        if not isinstance(params, dict):
            continue
        merged.update(params)
    return merged


def _build_strategy_catalog():
    catalog = []
    seen_names = set()

    def append_variant(name, base_name, params=None):
        normalized_name = str(name or "").strip()
        normalized_base_name = str(base_name or "").strip()
        if not normalized_name or not normalized_base_name or normalized_name in seen_names:
            return
        seen_names.add(normalized_name)
        catalog.append(
            {
                "name": normalized_name,
                "base_name": normalized_base_name,
                "params": dict(params or {}),
            }
        )

    for base_name in CORE_STRATEGY_NAMES:
        append_variant(base_name, base_name, {})
        for style_label, style_params in VARIANT_STYLE_PROFILES:
            for profile_label, profile_params in VARIANT_RISK_PROFILES:
                append_variant(
                    f"{base_name} | {style_label} {profile_label}",
                    base_name,
                    _combine_strategy_params(style_params, profile_params),
                )
                for context_label, context_params in VARIANT_MARKET_CONTEXT_PROFILES:
                    append_variant(
                        f"{base_name} | {style_label} {profile_label} {context_label}",
                        base_name,
                        _combine_strategy_params(style_params, profile_params, context_params),
                    )

    append_variant(
        "AI Hybrid | Institutional Prime",
        "AI Hybrid",
        {
            "rsi_period": 18,
            "ema_fast": 34,
            "ema_slow": 89,
            "atr_period": 21,
            "breakout_lookback": 34,
            "oversold_threshold": 34,
            "overbought_threshold": 66,
            "min_confidence": 0.66,
            "signal_amount": 0.90,
        },
    )

    expected_count = (
        len(CORE_STRATEGY_NAMES)
        * (1 + (len(VARIANT_STYLE_PROFILES) * len(VARIANT_RISK_PROFILES) * (1 + len(VARIANT_MARKET_CONTEXT_PROFILES))))
        + 1
    )
    if len(catalog) != expected_count:
        raise RuntimeError(f"Expected {expected_count} strategy catalog entries, found {len(catalog)}.")
    return tuple(catalog)


STRATEGY_CATALOG = _build_strategy_catalog()
STRATEGY_DEFINITIONS = {entry["name"]: entry for entry in STRATEGY_CATALOG}
STRATEGY_VARIANT_BASE_MAP = {entry["name"]: entry["base_name"] for entry in STRATEGY_CATALOG}
STRATEGY_NAME_ALIASES = dict(BASE_STRATEGY_ALIASES)
for _entry in STRATEGY_CATALOG:
    _name = str(_entry["name"])
    STRATEGY_NAME_ALIASES[_name.upper()] = _name


class Strategy:
    CORE_STRATEGIES = list(CORE_STRATEGY_NAMES)
    AVAILABLE_STRATEGIES = [entry["name"] for entry in STRATEGY_CATALOG]
    PRESET_ALIASES = STRATEGY_NAME_ALIASES
    STRATEGY_CATALOG = STRATEGY_CATALOG
    STRATEGY_DEFINITIONS = STRATEGY_DEFINITIONS
    STRATEGY_VARIANT_BASE_MAP = STRATEGY_VARIANT_BASE_MAP

    def __init__(self, model=None, strategy_name="Trend Following", feature_pipeline=None):

        self.model = model
        self.strategy_name = self.normalize_strategy_name(strategy_name)
        self.feature_pipeline = feature_pipeline or FeaturePipeline()

        # Strategy parameters
        self.rsi_period = 14
        self.ema_fast = 20
        self.ema_slow = 50
        self.atr_period = 14
        self.oversold_threshold = 35
        self.overbought_threshold = 65
        self.breakout_lookback = 20
        self.signal_amount = 1.0

        self.min_confidence = 0.55

    @classmethod
    def normalize_strategy_name(cls, strategy_name):
        label = str(strategy_name or "Trend Following").strip()
        if not label:
            return "Trend Following"
        return cls.PRESET_ALIASES.get(label.upper(), label)

    @classmethod
    def resolve_signal_strategy_name(cls, strategy_name):
        normalized = cls.normalize_strategy_name(strategy_name)
        return cls.STRATEGY_VARIANT_BASE_MAP.get(normalized, normalized)

    @classmethod
    def strategy_definition(cls, strategy_name):
        normalized = cls.normalize_strategy_name(strategy_name)
        definition = cls.STRATEGY_DEFINITIONS.get(normalized)
        if definition is not None:
            return dict(definition)
        return {
            "name": normalized,
            "base_name": cls.resolve_signal_strategy_name(normalized),
            "params": {},
        }

    def set_strategy_name(self, strategy_name):
        self.strategy_name = self.normalize_strategy_name(strategy_name)

    def apply_parameters(self, **params):
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # ==========================================================
    # FEATURE ENGINEERING
    # ==========================================================

    def compute_features(self, candles):
        return self.feature_pipeline.compute(
            candles,
            FeaturePipelineConfig(
                rsi_period=int(self.rsi_period),
                ema_fast=int(self.ema_fast),
                ema_slow=int(self.ema_slow),
                atr_period=int(self.atr_period),
                breakout_lookback=int(self.breakout_lookback),
            ),
        )

    def _signal(self, side, confidence, reason, price=None, row=None, **metadata):
        regime = "unknown"
        if row is not None:
            try:
                regime = str(row.get("regime", "unknown") or "unknown")
            except Exception:
                regime = "unknown"
        return SignalDecision(
            side=str(side).lower(),
            amount=self.signal_amount,
            confidence=float(confidence),
            reason=str(reason),
            price=price,
            regime=regime,
            metadata=metadata,
        ).to_dict()

    # ==========================================================
    # SIGNAL GENERATION
    # ==========================================================

    def generate_signal(self, candles, strategy_name=None):
        df = self.compute_features(candles)
        return self.generate_signal_from_features(df, strategy_name=strategy_name)

    def generate_signal_from_features(self, df, strategy_name=None):
        selected_name = self.resolve_signal_strategy_name(strategy_name or self.strategy_name)
        if selected_name == "AI Hybrid":
            ai_signal = self.generate_ai_signal_from_features(df)
            if ai_signal:
                return ai_signal
            selected_name = "Trend Following"
        elif selected_name == "ML Model":
            return self.generate_ai_signal_from_features(df, model_reason="ML classifier prediction")

        if df.empty:
            return None

        row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else row
        close_price = float(row["close"])
        prev_close = float(prev_row.get("close", close_price) or close_price)

        # Trend
        trend_up = row["ema_fast"] > row["ema_slow"]
        trend_down = row["ema_fast"] < row["ema_slow"]

        # RSI
        rsi = row["rsi"]

        if selected_name == "Trend Following":
            if trend_up and rsi < self.oversold_threshold:
                return self._signal("buy", 0.60, "EMA trend up + RSI oversold", row=row)
            if trend_down and rsi > self.overbought_threshold:
                return self._signal("sell", 0.60, "EMA trend down + RSI overbought", row=row)

        elif selected_name == "Mean Reversion":
            if close_price <= float(row["lower_band"]) and rsi <= self.oversold_threshold:
                return self._signal("buy", 0.58, "Lower band reversion + RSI oversold", row=row)
            if close_price >= float(row["upper_band"]) and rsi >= self.overbought_threshold:
                return self._signal("sell", 0.58, "Upper band reversion + RSI overbought", row=row)

        elif selected_name == "Breakout":
            breakout_high = row.get("breakout_high")
            breakout_low = row.get("breakout_low")
            if pd.notna(breakout_high) and close_price > float(breakout_high) and trend_up:
                return self._signal("buy", 0.62, "Breakout above prior range high", price=close_price, row=row)
            if pd.notna(breakout_low) and close_price < float(breakout_low) and trend_down:
                return self._signal("sell", 0.62, "Breakout below prior range low", price=close_price, row=row)

        elif selected_name == "EMA Cross":
            bullish_cross = float(prev_row["ema_fast"]) <= float(prev_row["ema_slow"]) and trend_up and rsi >= 50
            bearish_cross = float(prev_row["ema_fast"]) >= float(prev_row["ema_slow"]) and trend_down and rsi <= 50
            if bullish_cross:
                return self._signal("buy", 0.59, "EMA fast crossed above EMA slow with bullish momentum", price=close_price, row=row)
            if bearish_cross:
                return self._signal("sell", 0.59, "EMA fast crossed below EMA slow with bearish momentum", price=close_price, row=row)

        elif selected_name == "Momentum Continuation":
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            momentum = float(row.get("momentum", 0.0) or 0.0)
            if trend_up and momentum > 0.01 and volume_ratio >= 1.05 and 52 <= rsi <= 78:
                return self._signal("buy", 0.64, "Uptrend with positive momentum and rising participation", price=close_price, row=row)
            if trend_down and momentum < -0.01 and volume_ratio >= 1.05 and 22 <= rsi <= 48:
                return self._signal("sell", 0.64, "Downtrend with negative momentum and rising participation", price=close_price, row=row)

        elif selected_name == "Pullback Trend":
            pullback_gap = abs(float(row.get("pullback_gap", 0.0) or 0.0))
            if trend_up and pullback_gap <= 0.4 and 45 <= rsi <= 62 and close_price >= float(row["ema_fast"]):
                return self._signal("buy", 0.61, "Healthy pullback into uptrend support near fast EMA", price=close_price, row=row)
            if trend_down and pullback_gap <= 0.4 and 38 <= rsi <= 55 and close_price <= float(row["ema_fast"]):
                return self._signal("sell", 0.61, "Bearish pullback failed near fast EMA resistance", price=close_price, row=row)

        elif selected_name == "Adaptive Momentum Pullback":
            momentum = float(row.get("momentum", 0.0) or 0.0)
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            pullback_gap = abs(float(row.get("pullback_gap", 0.0) or 0.0))
            min_momentum = 0.003
            min_volume = 0.9
            max_pullback = 0.6
            if trend_up and momentum > min_momentum and volume_ratio >= min_volume and pullback_gap <= max_pullback and rsi < 70:
                return self._signal("buy", 0.65, "Adaptive momentum pullback in uptrend", price=close_price, row=row)
            if trend_down and momentum < -min_momentum and volume_ratio >= min_volume and pullback_gap <= max_pullback and rsi > 30:
                return self._signal("sell", 0.65, "Adaptive momentum pullback in downtrend", price=close_price, row=row)

        elif selected_name == "Volatility Breakout":
            breakout_high = row.get("breakout_high")
            breakout_low = row.get("breakout_low")
            atr_pct = float(row.get("atr_pct", 0.0) or 0.0)
            prev_atr_pct = float(prev_row.get("atr_pct", atr_pct) or atr_pct)
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            if (
                pd.notna(breakout_high)
                and trend_up
                and close_price > float(breakout_high)
                and atr_pct >= prev_atr_pct
                and volume_ratio >= 1.0
            ):
                return self._signal("buy", 0.67, "Range expansion breakout with volatility confirmation", price=close_price, row=row)
            if (
                pd.notna(breakout_low)
                and trend_down
                and close_price < float(breakout_low)
                and atr_pct >= prev_atr_pct
                and volume_ratio >= 1.0
            ):
                return self._signal("sell", 0.67, "Range expansion breakdown with volatility confirmation", price=close_price, row=row)

        elif selected_name == "MACD Trend":
            prev_macd = float(prev_row.get("macd_line", 0.0) or 0.0)
            prev_signal = float(prev_row.get("macd_signal", 0.0) or 0.0)
            macd_line = float(row.get("macd_line", 0.0) or 0.0)
            macd_signal = float(row.get("macd_signal", 0.0) or 0.0)
            if trend_up and prev_macd <= prev_signal and macd_line > macd_signal and macd_line >= 0:
                return self._signal("buy", 0.63, "MACD bullish crossover aligned with prevailing trend", price=close_price, row=row)
            if trend_down and prev_macd >= prev_signal and macd_line < macd_signal and macd_line <= 0:
                return self._signal("sell", 0.63, "MACD bearish crossover aligned with prevailing trend", price=close_price, row=row)

        elif selected_name == "Range Fade":
            trend_strength = float(row.get("trend_strength", 0.0) or 0.0)
            band_position = float(row.get("band_position", 0.5) or 0.5)
            if trend_strength <= 0.003 and band_position <= 0.08 and rsi <= 40:
                return self._signal("buy", 0.57, "Weak trend range fade from lower volatility band", price=close_price, row=row)
            if trend_strength <= 0.003 and band_position >= 0.92 and rsi >= 60:
                return self._signal("sell", 0.57, "Weak trend range fade from upper volatility band", price=close_price, row=row)

        elif selected_name == "Donchian Trend":
            breakout_high = row.get("breakout_high")
            breakout_low = row.get("breakout_low")
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            momentum = float(row.get("momentum", 0.0) or 0.0)
            if pd.notna(breakout_high) and trend_up and close_price > float(breakout_high) and volume_ratio >= 0.95 and momentum >= 0:
                return self._signal("buy", 0.65, "Donchian breakout aligned with trend strength and participation", price=close_price, row=row)
            if pd.notna(breakout_low) and trend_down and close_price < float(breakout_low) and volume_ratio >= 0.95 and momentum <= 0:
                return self._signal("sell", 0.65, "Donchian breakdown aligned with trend strength and participation", price=close_price, row=row)

        elif selected_name == "Bollinger Squeeze":
            breakout_high = row.get("breakout_high")
            breakout_low = row.get("breakout_low")
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            momentum = float(row.get("momentum", 0.0) or 0.0)
            band_position = float(row.get("band_position", 0.5) or 0.5)
            prev_close_safe = prev_close if prev_close else 1.0
            prev_band_width_pct = max(
                0.0,
                (
                    float(prev_row.get("upper_band", close_price) or close_price)
                    - float(prev_row.get("lower_band", close_price) or close_price)
                ) / prev_close_safe,
            )
            if (
                pd.notna(breakout_high)
                and prev_band_width_pct <= 0.05
                and close_price > float(breakout_high)
                and volume_ratio >= 1.05
                and momentum > 0
                and band_position >= 0.80
            ):
                return self._signal("buy", 0.66, "Bollinger squeeze expansion resolved upward with volume confirmation", price=close_price, row=row)
            if (
                pd.notna(breakout_low)
                and prev_band_width_pct <= 0.05
                and close_price < float(breakout_low)
                and volume_ratio >= 1.05
                and momentum < 0
                and band_position <= 0.20
            ):
                return self._signal("sell", 0.66, "Bollinger squeeze expansion resolved downward with volume confirmation", price=close_price, row=row)

        elif selected_name == "ATR Compression Breakout":
            breakout_high = row.get("breakout_high")
            breakout_low = row.get("breakout_low")
            atr_pct = float(row.get("atr_pct", 0.0) or 0.0)
            prev_atr_pct = float(prev_row.get("atr_pct", atr_pct) or atr_pct)
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            volatility_expanding = prev_atr_pct > 0 and atr_pct >= (prev_atr_pct * 1.15)
            if (
                pd.notna(breakout_high)
                and prev_atr_pct <= 0.02
                and volatility_expanding
                and close_price > float(breakout_high)
                and volume_ratio >= 1.05
            ):
                return self._signal("buy", 0.68, "ATR compression released into bullish breakout expansion", price=close_price, row=row)
            if (
                pd.notna(breakout_low)
                and prev_atr_pct <= 0.02
                and volatility_expanding
                and close_price < float(breakout_low)
                and volume_ratio >= 1.05
            ):
                return self._signal("sell", 0.68, "ATR compression released into bearish breakout expansion", price=close_price, row=row)

        elif selected_name == "RSI Failure Swing":
            prev_rsi = float(prev_row.get("rsi", rsi) or rsi)
            prev_lower_band = float(prev_row.get("lower_band", close_price) or close_price)
            prev_upper_band = float(prev_row.get("upper_band", close_price) or close_price)
            if (
                prev_close <= prev_lower_band
                and prev_rsi <= self.oversold_threshold
                and rsi >= min(55.0, self.oversold_threshold + 6)
                and rsi > prev_rsi
                and close_price >= float(row["ema_fast"])
            ):
                return self._signal("buy", 0.60, "RSI failure swing reclaimed from oversold rejection", price=close_price, row=row)
            if (
                prev_close >= prev_upper_band
                and prev_rsi >= self.overbought_threshold
                and rsi <= max(45.0, self.overbought_threshold - 6)
                and rsi < prev_rsi
                and close_price <= float(row["ema_fast"])
            ):
                return self._signal("sell", 0.60, "RSI failure swing rolled over from overbought rejection", price=close_price, row=row)

        elif selected_name == "Volume Spike Reversal":
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            band_position = float(row.get("band_position", 0.5) or 0.5)
            trend_strength = float(row.get("trend_strength", 0.0) or 0.0)
            if volume_ratio >= 1.35 and band_position <= 0.12 and trend_strength <= 0.012 and rsi <= 38 and close_price > prev_close:
                return self._signal("buy", 0.59, "Volume spike reversal from lower band exhaustion", price=close_price, row=row)
            if volume_ratio >= 1.35 and band_position >= 0.88 and trend_strength <= 0.012 and rsi >= 62 and close_price < prev_close:
                return self._signal("sell", 0.59, "Volume spike reversal from upper band exhaustion", price=close_price, row=row)

        return None

    # ==========================================================
    # AI SIGNAL
    # ==========================================================

    def generate_ai_signal(self, candles):
        df = self.compute_features(candles)
        return self.generate_ai_signal_from_features(df)

    def generate_ai_signal_from_features(self, df, model_reason="AI model prediction"):
        if self.model is None:
            return None

        if df.empty:
            return None

        model_feature_names = list(getattr(self.model, "feature_names_", []) or [])
        default_features = ["rsi", "ema_fast", "ema_slow", "atr", "volume"]
        sequence_length = max(1, int(getattr(self.model, "sequence_length", 1) or 1))
        if sequence_length > 1:
            base_columns = []
            for feature_name in model_feature_names:
                if "_t-" in feature_name:
                    base_name = feature_name.split("_t-", 1)[0]
                    if base_name not in base_columns:
                        base_columns.append(base_name)
            base_columns = [name for name in base_columns if name in df.columns] or [name for name in default_features if name in df.columns]
            if len(df) < sequence_length or not base_columns:
                return None
            window = df[base_columns].tail(sequence_length)
            flattened = []
            for _, row in window.iterrows():
                flattened.extend([float(row[column]) for column in base_columns])
            features = np.asarray(flattened, dtype=float).reshape(1, -1)
        else:
            selected_columns = [name for name in model_feature_names if name in df.columns] or default_features
            features = df.iloc[-1][selected_columns].values.reshape(1, -1)

        prob = self.model.predict_proba(features)[0]

        confidence = max(prob)

        if confidence < self.min_confidence:
            return None

        side = "buy" if prob[1] > prob[0] else "sell"

        regime = "unknown"
        try:
            regime = str(df.iloc[-1].get("regime", "unknown") or "unknown")
        except Exception:
            pass

        return SignalDecision(
            side=side,
            amount=self.signal_amount,
            confidence=float(confidence),
            reason=str(model_reason),
            regime=regime,
            metadata={"model_name": getattr(self.model, "model_name", "strategy_model")},
        ).to_dict()
