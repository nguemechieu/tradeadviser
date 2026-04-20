from dataclasses import dataclass

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange


@dataclass
class FeaturePipelineConfig:
    rsi_period: int = 14
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    breakout_lookback: int = 20


class FeaturePipeline:
    BASE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
    FEATURE_VERSION = "quant-v1"

    def normalize_candles(self, candles):
        if isinstance(candles, pd.DataFrame):
            if candles.empty:
                return pd.DataFrame(columns=self.BASE_COLUMNS)
            df = candles.copy()
            missing = [column for column in self.BASE_COLUMNS if column not in df.columns]
            if missing:
                return pd.DataFrame(columns=self.BASE_COLUMNS)
            numeric_cols = ["open", "high", "low", "close", "volume"]
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
            df.dropna(subset=numeric_cols, inplace=True)
            return df[self.BASE_COLUMNS].copy()

        if not candles:
            return pd.DataFrame(columns=self.BASE_COLUMNS)

        normalized = []
        for row in candles:
            if isinstance(row, (list, tuple)) and len(row) >= 6:
                normalized.append(list(row[:6]))

        if not normalized:
            return pd.DataFrame(columns=self.BASE_COLUMNS)

        df = pd.DataFrame(normalized, columns=self.BASE_COLUMNS)
        numeric_cols = ["open", "high", "low", "close", "volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        df.dropna(subset=numeric_cols, inplace=True)
        return df

    def infer_regime(self, row) -> str:
        trend_strength = float(row.get("trend_strength", 0.0) or 0.0)
        atr_pct = float(row.get("atr_pct", 0.0) or 0.0)
        momentum = float(row.get("momentum", 0.0) or 0.0)

        if trend_strength >= 0.01 and momentum > 0:
            return "trending_up"
        if trend_strength >= 0.01 and momentum < 0:
            return "trending_down"
        if atr_pct >= 0.03:
            return "high_volatility"
        return "range"

    def compute(self, candles, config: FeaturePipelineConfig | None = None):
        cfg = config or FeaturePipelineConfig()
        df = self.normalize_candles(candles)
        if df.empty:
            return df

        min_length = max(int(cfg.ema_slow), int(cfg.atr_period), int(cfg.rsi_period))
        if len(df) < min_length:
            return pd.DataFrame(columns=df.columns)

        df["return_1"] = df["close"].pct_change().fillna(0.0)
        df["return_5"] = df["close"].pct_change(5).fillna(0.0)

        df["rsi"] = RSIIndicator(df["close"], int(cfg.rsi_period)).rsi()
        df["ema_fast"] = EMAIndicator(df["close"], int(cfg.ema_fast)).ema_indicator()
        df["ema_slow"] = EMAIndicator(df["close"], int(cfg.ema_slow)).ema_indicator()
        df["atr"] = AverageTrueRange(
            df["high"],
            df["low"],
            df["close"],
            int(cfg.atr_period),
        ).average_true_range()

        bb_period = max(int(cfg.ema_fast), 2)
        rolling_mean = df["close"].rolling(window=bb_period, min_periods=1).mean()
        rolling_std = df["close"].rolling(window=bb_period, min_periods=1).std().fillna(0.0)
        df["upper_band"] = rolling_mean + (2.0 * rolling_std)
        df["lower_band"] = rolling_mean - (2.0 * rolling_std)

        breakout_period = max(int(cfg.breakout_lookback), 2)
        df["breakout_high"] = df["high"].rolling(window=breakout_period, min_periods=1).max().shift(1)
        df["breakout_low"] = df["low"].rolling(window=breakout_period, min_periods=1).min().shift(1)

        volume_window = max(5, min(int(cfg.ema_fast), 30))
        df["volume_ma"] = df["volume"].rolling(window=volume_window, min_periods=1).mean()
        df["volume_ratio"] = np.where(df["volume_ma"] > 0, df["volume"] / df["volume_ma"], 1.0)

        momentum_period = max(2, min(int(cfg.rsi_period // 2) or 2, 10))
        df["momentum"] = df["close"].pct_change(momentum_period).fillna(0.0)

        macd_fast = df["close"].ewm(span=12, adjust=False).mean()
        macd_slow = df["close"].ewm(span=26, adjust=False).mean()
        df["macd_line"] = macd_fast - macd_slow
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd_line"] - df["macd_signal"]

        df["atr_pct"] = np.where(df["close"] != 0, df["atr"] / df["close"], 0.0)
        df["trend_strength"] = np.where(df["close"] != 0, (df["ema_fast"] - df["ema_slow"]).abs() / df["close"], 0.0)
        df["pullback_gap"] = np.where(df["atr"] != 0, (df["close"] - df["ema_fast"]) / df["atr"], 0.0)

        band_width = (df["upper_band"] - df["lower_band"]).replace(0, np.nan)
        df["band_position"] = ((df["close"] - df["lower_band"]) / band_width).clip(lower=0.0, upper=1.0).fillna(0.5)
        df["regime"] = [self.infer_regime(row) for _, row in df.iterrows()]
        df["feature_version"] = self.FEATURE_VERSION

        df.dropna(inplace=True)
        return df
