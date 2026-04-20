import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=max(1, int(period)), min_periods=1).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=max(1, int(period)), adjust=False).mean()


def wilders(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1.0 / max(1, int(period)), adjust=False).mean()


def smma(series: pd.Series, period: int) -> pd.Series:
    return wilders(series, period)


def lwma(series: pd.Series, period: int) -> pd.Series:
    period = max(1, int(period))
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(window=period, min_periods=1).apply(
        lambda values: np.dot(values, weights[-len(values):]) / weights[-len(values):].sum(),
        raw=True,
    )


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1).fillna(close.iloc[0] if len(close) else 0.0)
    return pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    return wilders(true_range(high, low, close), period)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int):
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )

    tr = true_range(high, low, close).replace(0, np.nan)
    atr_series = wilders(tr.fillna(0.0), period).replace(0, np.nan)
    plus_di = 100.0 * wilders(plus_dm, period) / atr_series
    minus_di = 100.0 * wilders(minus_dm, period) / atr_series
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_line = wilders(dx.fillna(0.0), period)
    return adx_line.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


def bollinger(close: pd.Series, period: int, deviation: float = 2.0):
    mid = sma(close, period)
    std = close.rolling(window=max(1, int(period)), min_periods=1).std().fillna(0.0)
    return mid, mid + deviation * std, mid - deviation * std


def envelopes(close: pd.Series, period: int, deviation_pct: float = 0.1):
    mid = sma(close, period)
    factor = deviation_pct / 100.0
    return mid, mid * (1.0 + factor), mid * (1.0 - factor)


def standard_deviation(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=max(1, int(period)), min_periods=1).std().fillna(0.0)


def parabolic_sar(high: pd.Series, low: pd.Series, step: float = 0.02, maximum: float = 0.2) -> pd.Series:
    if len(high) == 0:
        return pd.Series(dtype=float)

    high_values = high.astype(float).to_numpy()
    low_values = low.astype(float).to_numpy()
    sar = np.zeros(len(high_values), dtype=float)

    bull = True
    af = step
    ep = high_values[0]
    sar[0] = low_values[0]

    for index in range(1, len(high_values)):
        previous_sar = sar[index - 1]
        sar[index] = previous_sar + af * (ep - previous_sar)

        if bull:
            if index >= 2:
                sar[index] = min(sar[index], low_values[index - 1], low_values[index - 2])
            else:
                sar[index] = min(sar[index], low_values[index - 1])

            if low_values[index] < sar[index]:
                bull = False
                sar[index] = ep
                ep = low_values[index]
                af = step
            else:
                if high_values[index] > ep:
                    ep = high_values[index]
                    af = min(af + step, maximum)
        else:
            if index >= 2:
                sar[index] = max(sar[index], high_values[index - 1], high_values[index - 2])
            else:
                sar[index] = max(sar[index], high_values[index - 1])

            if high_values[index] > sar[index]:
                bull = True
                sar[index] = ep
                ep = high_values[index]
                af = step
            else:
                if low_values[index] < ep:
                    ep = low_values[index]
                    af = min(af + step, maximum)

    return pd.Series(sar, index=high.index, dtype=float)


def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series):
    tenkan = (high.rolling(9, min_periods=1).max() + low.rolling(9, min_periods=1).min()) / 2.0
    kijun = (high.rolling(26, min_periods=1).max() + low.rolling(26, min_periods=1).min()) / 2.0
    span_a = ((tenkan + kijun) / 2.0).shift(26)
    span_b = ((high.rolling(52, min_periods=1).max() + low.rolling(52, min_periods=1).min()) / 2.0).shift(26)
    chikou = close.shift(-26)
    return tenkan, kijun, span_a, span_b, chikou


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff().fillna(0.0)
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    avg_gain = wilders(gains, period)
    avg_loss = wilders(losses, period).replace(0, np.nan)
    rs = avg_gain / avg_loss
    return (100.0 - (100.0 / (1.0 + rs))).fillna(0.0)


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int, slowing: int = 3, signal: int = 3):
    lowest = low.rolling(window=max(1, int(period)), min_periods=1).min()
    highest = high.rolling(window=max(1, int(period)), min_periods=1).max()
    spread = (highest - lowest).replace(0, np.nan)
    percent_k = 100.0 * (close - lowest) / spread
    slow_k = sma(percent_k.fillna(0.0), slowing)
    percent_d = sma(slow_k, signal)
    return slow_k.fillna(0.0), percent_d.fillna(0.0)


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    lowest = low.rolling(window=max(1, int(period)), min_periods=1).min()
    highest = high.rolling(window=max(1, int(period)), min_periods=1).max()
    return (-100.0 * (highest - close) / (highest - lowest).replace(0, np.nan)).fillna(0.0)


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    typical = (high + low + close) / 3.0
    mean = sma(typical, period)
    mean_dev = typical.rolling(window=max(1, int(period)), min_periods=1).apply(
        lambda values: np.mean(np.abs(values - np.mean(values))),
        raw=True,
    )
    denom = (0.015 * mean_dev).replace(0, np.nan)
    return ((typical - mean) / denom).fillna(0.0)


def momentum(close: pd.Series, period: int) -> pd.Series:
    shifted = close.shift(max(1, int(period))).replace(0, np.nan)
    return (100.0 * close / shifted).fillna(100.0)


def demarker(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    demax = high.diff().clip(lower=0.0).fillna(0.0)
    demin = (-low.diff()).clip(lower=0.0).fillna(0.0)
    demax_avg = sma(demax, period)
    demin_avg = sma(demin, period)
    denom = (demax_avg + demin_avg).replace(0, np.nan)
    return (demax_avg / denom).fillna(0.0)


def rvi(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, period: int):
    numerator = (
        (close - open_)
        + 2.0 * (close.shift(1) - open_.shift(1))
        + 2.0 * (close.shift(2) - open_.shift(2))
        + (close.shift(3) - open_.shift(3))
    ) / 6.0
    denominator = (
        (high - low)
        + 2.0 * (high.shift(1) - low.shift(1))
        + 2.0 * (high.shift(2) - low.shift(2))
        + (high.shift(3) - low.shift(3))
    ) / 6.0
    rvi_line = sma((numerator / denominator.replace(0, np.nan)).fillna(0.0), period)
    signal = (
        rvi_line
        + 2.0 * rvi_line.shift(1)
        + 2.0 * rvi_line.shift(2)
        + rvi_line.shift(3)
    ) / 6.0
    return rvi_line.fillna(0.0), signal.fillna(0.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def awesome(high: pd.Series, low: pd.Series) -> pd.Series:
    median = (high + low) / 2.0
    return sma(median, 5) - sma(median, 34)


def accelerator(high: pd.Series, low: pd.Series) -> pd.Series:
    ao = awesome(high, low)
    return ao - sma(ao, 5)


def money_flow_index(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
    typical = (high + low + close) / 3.0
    money_flow = typical * volume
    delta = typical.diff().fillna(0.0)
    positive = pd.Series(np.where(delta > 0, money_flow, 0.0), index=typical.index)
    negative = pd.Series(np.where(delta < 0, money_flow, 0.0), index=typical.index)
    pos_sum = positive.rolling(window=max(1, int(period)), min_periods=1).sum()
    neg_sum = negative.rolling(window=max(1, int(period)), min_periods=1).sum().replace(0, np.nan)
    ratio = pos_sum / neg_sum
    return (100.0 - (100.0 / (1.0 + ratio))).fillna(100.0)


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume).cumsum().fillna(0.0)


def accumulation_distribution(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    spread = (high - low).replace(0, np.nan)
    multiplier = ((close - low) - (high - close)) / spread
    return (multiplier.fillna(0.0) * volume).cumsum().fillna(0.0)


def force_index(close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
    raw = close.diff().fillna(0.0) * volume
    return ema(raw, period)


def bulls_power(high: pd.Series, close: pd.Series, period: int = 13) -> pd.Series:
    base = ema(close, period)
    return (high - base).fillna(0.0)


def bears_power(low: pd.Series, close: pd.Series, period: int = 13) -> pd.Series:
    base = ema(close, period)
    return (low - base).fillna(0.0)


def alligator(high: pd.Series, low: pd.Series):
    median = (high + low) / 2.0
    jaw = smma(median, 13).shift(8)
    teeth = smma(median, 8).shift(5)
    lips = smma(median, 5).shift(3)
    return jaw.bfill().fillna(0.0), teeth.bfill().fillna(0.0), lips.bfill().fillna(0.0)


def gator(high: pd.Series, low: pd.Series):
    jaw, teeth, lips = alligator(high, low)
    return (jaw - teeth).abs().fillna(0.0), -(teeth - lips).abs().fillna(0.0)


def market_facilitation_index(high: pd.Series, low: pd.Series, volume: pd.Series):
    raw = ((high - low) / volume.replace(0, np.nan)).fillna(0.0)
    raw_delta = raw.diff().fillna(0.0)
    volume_delta = volume.diff().fillna(0.0)

    colors = []
    for raw_move, volume_move in zip(raw_delta.to_numpy(), volume_delta.to_numpy()):
        if raw_move >= 0 and volume_move >= 0:
            colors.append("#32d296")
        elif raw_move < 0 and volume_move < 0:
            colors.append("#8d6e63")
        elif raw_move >= 0 and volume_move < 0:
            colors.append("#42a5f5")
        else:
            colors.append("#ec407a")
    return raw, colors
