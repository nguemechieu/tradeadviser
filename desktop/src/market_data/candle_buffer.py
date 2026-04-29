"""Buffer for managing candle (OHLCV) data per symbol and time frame."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from threading import RLock
from typing import Any, Iterable

import pandas as pd

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def _normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def _normalize_timeframe(timeframe: Any) -> str:
    text = str(timeframe or "").strip().lower()
    return text or "default"


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if not pd.notna(number):
            return default
        return number
    except Exception:
        return default


def _normalize_timestamp(value: Any) -> pd.Timestamp:
    if value is None or value == "":
        return pd.Timestamp.now(tz="UTC")

    if isinstance(value, pd.Timestamp):
        timestamp = value
    elif isinstance(value, datetime):
        timestamp = pd.Timestamp(value)
    elif isinstance(value, (int, float)):

        timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    else:
        timestamp = pd.to_datetime(value, errors="coerce", utc=True)

    if pd.isna(timestamp):
        return pd.Timestamp.now(tz="UTC")

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    return timestamp


def _timestamp_key(value: Any) -> int:
    timestamp = _normalize_timestamp(value)
    return int(timestamp.value)


def _normalize_candle(candle: Any) -> dict[str, Any] | None:
    """
    Accepts:
    - dict: {"timestamp", "open", "high", "low", "close", "volume"}
    - list/tuple: [timestamp, open, high, low, close, volume]
    - object/dataclass with OHLCV attributes
    """

    if candle is None:
        return None

    if isinstance(candle, dict):
        raw = dict(candle)
    elif isinstance(candle, (list, tuple)):
        if len(candle) < 5:
            return None

        raw = {
            "timestamp": candle[0],
            "open": candle[1],
            "high": candle[2],
            "low": candle[3],
            "close": candle[4],
            "volume": candle[5] if len(candle) > 5 else 0.0,
        }
    else:
        raw = {
            "timestamp": getattr(candle, "timestamp", getattr(candle, "time", None)),
            "open": getattr(candle, "open", None),
            "high": getattr(candle, "high", None),
            "low": getattr(candle, "low", None),
            "close": getattr(candle, "close", None),
            "volume": getattr(candle, "volume", 0.0),
        }

    timestamp = (
            raw.get("timestamp")
            or raw.get("time")
            or raw.get("datetime")
            or raw.get("date")
    )

    open_price = _safe_float(raw.get("open", raw.get("o")))
    high_price = _safe_float(raw.get("high", raw.get("h")))
    low_price = _safe_float(raw.get("low", raw.get("l")))
    close_price = _safe_float(raw.get("close", raw.get("c")))
    volume = _safe_float(raw.get("volume", raw.get("v")), 0.0)

    if open_price is None or high_price is None or low_price is None or close_price is None:
        return None

    timestamp_value = _normalize_timestamp(timestamp)

    normalized = {
        "timestamp": timestamp_value,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume or 0.0,
    }

    for key, value in raw.items():
        if key not in normalized and key not in {"o", "h", "l", "c", "v", "time", "datetime", "date"}:
            normalized[key] = value

    return normalized


class CandleBuffer:
    """
    Thread-safe candle buffer for managing OHLCV data.

    Supports:
    - per-symbol candles
    - optional per-timeframe candles
    - deduplication by timestamp
    - pandas DataFrame export
    - rolling max length
    - compatibility with old `.update(symbol, candle)` and `.get(symbol)` API
    """

    def __init__(self, max_length: int = 5000) -> None:
        self.max_length = max(1, int(max_length or 5000))
        self.buffers: dict[str, dict[str, deque[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=self.max_length))
        )
        self._timestamp_indexes: dict[str, dict[str, dict[int, int]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Update API
    # ------------------------------------------------------------------

    def update(
            self,
            symbol: str,
            candle: Any,
            timeframe: str | None = None,
            *,
            replace_existing: bool = True,
    ) -> bool:
        """
        Add or replace one candle.

        Returns True when the candle was accepted, False when invalid.
        """

        symbol_key = _normalize_symbol(symbol)
        timeframe_key = _normalize_timeframe(timeframe)

        if not symbol_key:
            return False

        normalized = _normalize_candle(candle)
        if normalized is None:
            return False

        timestamp_id = _timestamp_key(normalized["timestamp"])

        with self._lock:
            buffer = self.buffers[symbol_key][timeframe_key]
            index = self._timestamp_indexes[symbol_key][timeframe_key]

            if replace_existing and timestamp_id in index:
                position = index[timestamp_id]

                if 0 <= position < len(buffer):
                    buffer_list = list(buffer)
                    buffer_list[position] = normalized
                    buffer.clear()
                    buffer.extend(buffer_list[-self.max_length :])
                    self._rebuild_index(symbol_key, timeframe_key)
                    return True

            buffer.append(normalized)
            self._rebuild_index(symbol_key, timeframe_key)

        return True

    def extend(
            self,
            symbol: str,
            candles: Iterable[Any],
            timeframe: str | None = None,
            *,
            replace_existing: bool = True,
    ) -> int:
        count = 0

        for candle in candles or []:
            if self.update(
                    symbol,
                    candle,
                    timeframe=timeframe,
                    replace_existing=replace_existing,
            ):
                count += 1

        return count

    def _rebuild_index(self, symbol: str, timeframe: str) -> None:
        buffer = self.buffers[symbol][timeframe]
        self._timestamp_indexes[symbol][timeframe] = {
            _timestamp_key(row.get("timestamp")): index
            for index, row in enumerate(buffer)
        }

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get(
            self,
            symbol: str,
            timeframe: str | None = None,
            *,
            limit: int | None = None,
            as_dataframe: bool = True,
    ) -> pd.DataFrame | list[dict[str, Any]] | None:
        symbol_key = _normalize_symbol(symbol)
        timeframe_key = _normalize_timeframe(timeframe)

        with self._lock:
            data = list(self.buffers.get(symbol_key, {}).get(timeframe_key, []))

        if not data:
            return None

        if limit is not None:
            data = data[-max(0, int(limit)) :]

        if not as_dataframe:
            return [dict(row) for row in data]

        return self.to_dataframe(data)

    def latest(
            self,
            symbol: str,
            timeframe: str | None = None,
    ) -> dict[str, Any] | None:
        symbol_key = _normalize_symbol(symbol)
        timeframe_key = _normalize_timeframe(timeframe)

        with self._lock:
            buffer = self.buffers.get(symbol_key, {}).get(timeframe_key)

            if not buffer:
                return None

            return dict(buffer[-1])

    def latest_price(
            self,
            symbol: str,
            timeframe: str | None = None,
    ) -> float | None:
        candle = self.latest(symbol, timeframe)
        if not candle:
            return None
        return _safe_float(candle.get("close"))

    def count(self, symbol: str, timeframe: str | None = None) -> int:
        symbol_key = _normalize_symbol(symbol)
        timeframe_key = _normalize_timeframe(timeframe)

        with self._lock:
            return len(self.buffers.get(symbol_key, {}).get(timeframe_key, []))

    def symbols(self) -> list[str]:
        with self._lock:
            return sorted(self.buffers.keys())

    def timeframes(self, symbol: str) -> list[str]:
        symbol_key = _normalize_symbol(symbol)

        with self._lock:
            return sorted(self.buffers.get(symbol_key, {}).keys())

    # ------------------------------------------------------------------
    # DataFrame API
    # ------------------------------------------------------------------

    def to_dataframe(self, data: Iterable[dict[str, Any]]) -> pd.DataFrame:
        rows = list(data or [])

        if not rows:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        df = pd.DataFrame(rows)

        if "timestamp" not in df.columns:
            df["timestamp"] = pd.Timestamp.now(tz="UTC")

        ts = df["timestamp"]

        if pd.api.types.is_numeric_dtype(ts):
            numeric_ts = pd.to_numeric(ts, errors="coerce")
            median = numeric_ts
            unit = "ms" if pd.notna(median) and abs(float(median)) > 1e11 else "s"
            df["timestamp"] = pd.to_datetime( numeric_ts,unit=unit, errors="coerce")
        else:
            df["timestamp"] = pd.to_datetime(ts, errors="coerce", utc=True)

        for column in ("open", "high", "low", "close", "volume"):
            if column not in df.columns:
                df[column] = 0.0
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df.dropna(subset=["timestamp", "open", "high", "low", "close"], inplace=True)
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    # ------------------------------------------------------------------
    # Maintenance API
    # ------------------------------------------------------------------

    def clear(self, symbol: str | None = None, timeframe: str | None = None) -> None:
        with self._lock:
            if symbol is None:
                self.buffers.clear()
                self._timestamp_indexes.clear()
                return

            symbol_key = _normalize_symbol(symbol)

            if timeframe is None:
                self.buffers.pop(symbol_key, None)
                self._timestamp_indexes.pop(symbol_key, None)
                return

            timeframe_key = _normalize_timeframe(timeframe)

            self.buffers.get(symbol_key, {}).pop(timeframe_key, None)
            self._timestamp_indexes.get(symbol_key, {}).pop(timeframe_key, None)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                symbol: {
                    timeframe: [dict(row) for row in rows]
                    for timeframe, rows in timeframe_map.items()
                }
                for symbol, timeframe_map in self.buffers.items()
            }

    # ------------------------------------------------------------------
    # Compatibility aliases
    # ------------------------------------------------------------------

    def append(self, symbol: str, candle: Any, timeframe: str | None = None) -> bool:
        return self.update(symbol, candle, timeframe=timeframe)

    def add(self, symbol: str, candle: Any, timeframe: str | None = None) -> bool:
        return self.update(symbol, candle, timeframe=timeframe)

    def get_dataframe(
            self,
            symbol: str,
            timeframe: str | None = None,
            *,
            limit: int | None = None,
    ) -> pd.DataFrame | None:
        result = self.get(
            symbol,
            timeframe=timeframe,
            limit=limit,
            as_dataframe=True,
        )
        return result if isinstance(result, pd.DataFrame) else None

    def get_list(
            self,
            symbol: str,
            timeframe: str | None = None,
            *,
            limit: int | None = None,
    ) -> list[dict[str, Any]]:
        result = self.get(
            symbol,
            timeframe=timeframe,
            limit=limit,
            as_dataframe=False,
        )
        return result if isinstance(result, list) else []