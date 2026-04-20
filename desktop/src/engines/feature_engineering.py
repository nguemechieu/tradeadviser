import pandas as pd
import numpy as np

from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import BollingerBands
from ta.volatility import AverageTrueRange


class FeatureEngineering:
    """
    Generates ML features from market data
    """

    def __init__(self):
        pass

    # ------------------------------------------------
    # BASIC FEATURES
    # ------------------------------------------------

    def basic_features(self, df: pd.DataFrame) -> pd.DataFrame:

        df["return"] = df["close"].pct_change()

        df["log_return"] = np.log(df["close"] / df["close"].shift(1))

        df["price_change"] = df["close"] - df["open"]

        return df

    # ------------------------------------------------
    # MOMENTUM INDICATORS
    # ------------------------------------------------

    def momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:

        rsi = RSIIndicator(close=df["close"], window=14)
        df["rsi"] = rsi.rsi()

        macd = MACD(close=df["close"])

        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_diff"] = macd.macd_diff()

        return df

    # ------------------------------------------------
    # TREND FEATURES
    # ------------------------------------------------

    def trend_features(self, df: pd.DataFrame) -> pd.DataFrame:

        ema_fast = EMAIndicator(close=df["close"], window=12)
        ema_slow = EMAIndicator(close=df["close"], window=26)

        df["ema_fast"] = ema_fast.ema_indicator()
        df["ema_slow"] = ema_slow.ema_indicator()

        df["ema_spread"] = df["ema_fast"] - df["ema_slow"]

        return df

    # ------------------------------------------------
    # VOLATILITY FEATURES
    # ------------------------------------------------

    def volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:

        bb = BollingerBands(close=df["close"], window=20)

        df["bb_high"] = bb.bollinger_hband()
        df["bb_low"] = bb.bollinger_lband()

        atr = AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14
        )

        df["atr"] = atr.average_true_range()

        return df

    # ------------------------------------------------
    # VOLUME FEATURES
    # ------------------------------------------------

    def volume_features(self, df: pd.DataFrame) -> pd.DataFrame:

        df["volume_change"] = df["volume"].pct_change()

        df["volume_ma"] = df["volume"].rolling(20).mean()

        return df

    # ------------------------------------------------
    # TARGET GENERATION
    # ------------------------------------------------

    def create_target(self, df: pd.DataFrame, horizon=1) -> pd.DataFrame:
        """
        Create prediction target
        """

        df["future_return"] = df["close"].shift(-horizon) / df["close"] - 1

        df["target"] = (df["future_return"] > 0).astype(int)

        return df

    # ------------------------------------------------
    # COMPLETE PIPELINE
    # ------------------------------------------------

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:

        df = self.basic_features(df)

        df = self.momentum_features(df)

        df = self.trend_features(df)

        df = self.volatility_features(df)

        df = self.volume_features(df)

        df = df.dropna()

        return df