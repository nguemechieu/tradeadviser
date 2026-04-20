import numpy as np
import pandas as pd


# =========================================================
# MOVING AVERAGES
# =========================================================

def sma(series: pd.Series, window: int):
    """
    Simple Moving Average
    """
    return series.rolling(window).mean()


def ema(series: pd.Series, window: int):
    """
    Exponential Moving Average
    """
    return series.ewm(span=window, adjust=False).mean()


# =========================================================
# MOMENTUM INDICATORS
# =========================================================

def rsi(series: pd.Series, window: int = 14):
    """
    Relative Strength Index
    """

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


def macd(series: pd.Series, fast=12, slow=26, signal=9):

    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)

    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)

    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


# =========================================================
# VOLATILITY INDICATORS
# =========================================================

def bollinger_bands(series: pd.Series, window=20, num_std=2):

    mean = series.rolling(window).mean()

    std = series.rolling(window).std()

    upper = mean + num_std * std
    lower = mean - num_std * std

    return upper, lower


def atr(high, low, close, window=14):

    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    atr = tr.rolling(window).mean()

    return atr


# =========================================================
# TREND INDICATORS
# =========================================================

def ema_cross(close, fast=12, slow=26):

    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)

    signal = np.where(ema_fast > ema_slow, 1, -1)

    return signal


# =========================================================
# VOLUME INDICATORS
# =========================================================

def volume_sma(volume, window=20):

    return volume.rolling(window).mean()


def volume_spike(volume, window=20):

    avg = volume.rolling(window).mean()

    return volume / avg


# =========================================================
# STATISTICAL FEATURES
# =========================================================

def zscore(series, window=20):

    mean = series.rolling(window).mean()

    std = series.rolling(window).std()

    return (series - mean) / std


def rolling_volatility(series, window=20):

    return series.pct_change().rolling(window).std()