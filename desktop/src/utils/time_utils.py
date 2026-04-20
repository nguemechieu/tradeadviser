from datetime import datetime, timedelta, timezone
import pandas as pd


# =========================================================
# TIMEFRAME PARSING
# =========================================================

TIMEFRAME_MAP = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}


def timeframe_to_seconds(timeframe: str) -> int:
    """
    Convert timeframe string to seconds
    """
    return int(TIMEFRAME_MAP.get(timeframe))


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    """
    Convert timeframe to timedelta
    """
    seconds = timeframe_to_seconds(timeframe)

    if seconds is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    return timedelta(seconds=seconds)


# =========================================================
# TIMESTAMP UTILITIES
# =========================================================

def now_utc():
    """
    Current UTC timestamp
    """
    return datetime.now(timezone.utc)


def timestamp_to_datetime(ts):
    """
    Convert timestamp to datetime
    """

    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, timezone.utc)

    return pd.to_datetime(ts, utc=True)


def datetime_to_timestamp(dt: datetime):
    """
    Convert datetime to unix timestamp
    """
    return int(dt.timestamp())


# =========================================================
# CANDLE ALIGNMENT
# =========================================================

def align_timestamp(timestamp: datetime, timeframe: str):
    """
    Align timestamp to timeframe candle
    """

    seconds = timeframe_to_seconds(timeframe)

    ts = int(timestamp.timestamp())

    aligned = ts - (ts % seconds)

    return datetime.fromtimestamp(aligned, timezone.utc)


# =========================================================
# NEXT CANDLE TIME
# =========================================================

def next_candle_time(timestamp: datetime, timeframe: str):

    delta = timeframe_to_timedelta(timeframe)

    aligned = align_timestamp(timestamp, timeframe)

    return aligned + delta


# =========================================================
# DATAFRAME TIME NORMALIZATION
# =========================================================

def normalize_dataframe_time(df: pd.DataFrame, column="timestamp"):
    """
    Ensure dataframe timestamps are UTC datetime
    """

    df[column] = pd.to_datetime(df[column], utc=True)

    df = df.sort_values(column)

    df = df.drop_duplicates(subset=[column])

    return df


# =========================================================
# RESAMPLE CANDLES
# =========================================================

def resample_candles(df: pd.DataFrame, timeframe: str):

    rule_map = {
        "1m": "1T",
        "5m": "5T",
        "15m": "15T",
        "30m": "30T",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
    }

    rule = rule_map.get(timeframe)

    if rule is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    df = df.set_index("timestamp")

    resampled = df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })

    return resampled.dropna().reset_index()


# =========================================================
# SESSION FILTER
# =========================================================

def filter_trading_session(df, start="09:30", end="16:00"):
    """
    Filter dataframe to trading hours (stocks)
    """

    df["time"] = df["timestamp"].dt.time

    start_time = datetime.strptime(start, "%H:%M").time()
    end_time = datetime.strptime(end, "%H:%M").time()

    return df[(df["time"] >= start_time) & (df["time"] <= end_time)]