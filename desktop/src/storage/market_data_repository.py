from datetime import datetime, timezone
import math

from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, and_, or_, select

from storage import database as storage_db


class Candle(storage_db.Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True)
    exchange = Column(String(255), index=True)
    symbol = Column(String(255), index=True, nullable=False)
    timeframe = Column(String(255), index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime, index=True)
    timestamp_ms = Column(BigInteger, index=True)


class MarketDataRepository:
    def _normalize_timestamp(self, value):
        """Normalize a timestamp value to a naive UTC datetime and millisecond epoch."""
        if value is None:
            return None, None

        if isinstance(value, datetime):
            timestamp = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return timestamp.replace(tzinfo=None), int(timestamp.timestamp() * 1000)

        try:
            numeric = float(value)
            if abs(numeric) > 1e11:
                ms_value = int(numeric)
                return datetime.fromtimestamp(ms_value / 1000.0, tz=timezone.utc).replace(tzinfo=None), ms_value
            seconds_value = float(numeric)
            return datetime.fromtimestamp(seconds_value, tz=timezone.utc).replace(tzinfo=None), int(seconds_value * 1000)
        except Exception:
            pass

        text_value = str(value).strip()
        if not text_value:
            return None, None

        if text_value.endswith("Z"):
            text_value = text_value[:-1] + "+00:00"

        try:
            timestamp = datetime.fromisoformat(text_value)
        except ValueError:
            return None, None

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

        return timestamp.replace(tzinfo=None), int(timestamp.timestamp() * 1000)

    def _normalize_candle(self, symbol, timeframe, candle, exchange=None):
        """Normalize a raw OHLCV candle into a storage-ready dictionary.

        Accepts either a dict with named fields or a sequence of values. Returns
        None for malformed candles, invalid timestamps, or non-finite prices.
        """
        if isinstance(candle, dict):
            timestamp_value = candle.get("timestamp")
            open_value = candle.get("open")
            high_value = candle.get("high")
            low_value = candle.get("low")
            close_value = candle.get("close")
            volume_value = candle.get("volume", 0.0)
        elif isinstance(candle, (list, tuple)):
            candle_values = list(candle)
            if len(candle_values) == 5:
                # Some providers return [timestamp, open, high, low, close].
                candle_values.append(0.0)
            if len(candle_values) >= 6:
                timestamp_value, open_value, high_value, low_value, close_value, volume_value = candle_values[:6]
            else:
                return None
        else:
            return None

        normalized_ts, timestamp_ms = self._normalize_timestamp(timestamp_value)
        if normalized_ts is None or timestamp_ms is None:
            return None

        try:
            open_numeric = float(open_value)
            high_numeric = float(high_value)
            low_numeric = float(low_value)
            close_numeric = float(close_value)
            volume_numeric = float(volume_value or 0.0)
        except Exception:
            return None

        ohlc_values = [open_numeric, high_numeric, low_numeric, close_numeric]
        if any((not math.isfinite(value)) or value <= 0 for value in ohlc_values):
            return None
        if not math.isfinite(volume_numeric):
            volume_numeric = 0.0

        try:
            return {
                "exchange": str(exchange or "").lower() or None,
                "symbol": str(symbol),
                "timeframe": str(timeframe or "1h"),
                "open": open_numeric,
                "high": max(ohlc_values),
                "low": min(ohlc_values),
                "close": close_numeric,
                "volume": max(volume_numeric, 0.0),
                "timestamp": normalized_ts,
                "timestamp_ms": int(timestamp_ms),
            }
        except Exception:
            return None

    def _normalize_boundary_timestamp_ms(self, value, *, end_of_day=False):
        if value is None:
            return None

        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return None
            if "T" not in text_value and len(text_value) <= 10:
                text_value = (
                    f"{text_value}T23:59:59.999999+00:00"
                    if end_of_day
                    else f"{text_value}T00:00:00+00:00"
                )
            value = text_value
        elif isinstance(value, datetime) and end_of_day:
            if value.tzinfo is None:
                value = value.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999)

        _timestamp, timestamp_ms = self._normalize_timestamp(value)
        return timestamp_ms

    def save_candles(self, symbol, timeframe, candles, exchange=None):
        normalized_rows = []
        seen = set()

        for candle in candles or []:
            normalized = self._normalize_candle(symbol=symbol, timeframe=timeframe, candle=candle, exchange=exchange)
            if normalized is None:
                continue

            dedupe_key = (
                normalized["exchange"],
                normalized["symbol"],
                normalized["timeframe"],
                normalized["timestamp_ms"],
            )
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized_rows.append(normalized)

        if not normalized_rows:
            return 0

        exchange_value = normalized_rows[0]["exchange"]
        timestamp_values = [row["timestamp_ms"] for row in normalized_rows]

        with storage_db.SessionLocal() as session:
            stmt = select(Candle.timestamp_ms).where(
                Candle.symbol == str(symbol),
                Candle.timeframe == str(timeframe or "1h"),
                Candle.timestamp_ms.in_(timestamp_values),
            )
            if exchange_value:
                stmt = stmt.where(or_(Candle.exchange == exchange_value, Candle.exchange.is_(None)))

            existing = set(session.execute(stmt).scalars().all())
            pending = [
                Candle(**row)
                for row in normalized_rows
                if row["timestamp_ms"] not in existing
            ]

            if not pending:
                return 0

            session.add_all(pending)
            session.commit()
            return len(pending)

    def get_candles(self, symbol, timeframe="1h", limit=300, exchange=None, start_time=None, end_time=None):
        with storage_db.SessionLocal() as session:
            stmt = select(Candle).where(Candle.symbol == str(symbol))

            timeframe_value = str(timeframe or "1h")
            stmt = stmt.where(or_(Candle.timeframe == timeframe_value, Candle.timeframe.is_(None)))

            if exchange:
                exchange_value = str(exchange).lower()
                stmt = stmt.where(or_(Candle.exchange == exchange_value, Candle.exchange.is_(None)))

            start_timestamp_ms = self._normalize_boundary_timestamp_ms(start_time, end_of_day=False)
            end_timestamp_ms = self._normalize_boundary_timestamp_ms(end_time, end_of_day=True)
            if start_timestamp_ms is not None:
                stmt = stmt.where(Candle.timestamp_ms >= int(start_timestamp_ms))
            if end_timestamp_ms is not None:
                stmt = stmt.where(Candle.timestamp_ms <= int(end_timestamp_ms))

            range_requested = start_timestamp_ms is not None or end_timestamp_ms is not None
            if range_requested:
                stmt = stmt.order_by(Candle.timestamp_ms.asc())
                rows = list(session.execute(stmt).scalars().all())
                if limit is not None:
                    rows = rows[-max(1, int(limit)) :]
            else:
                stmt = stmt.order_by(Candle.timestamp_ms.desc()).limit(int(limit))
                rows = list(session.execute(stmt).scalars().all())
                rows.reverse()

            return [
                [
                    row.timestamp.isoformat() if row.timestamp else row.timestamp_ms,
                    row.open,
                    row.high,
                    row.low,
                    row.close,
                    row.volume,
                ]
                for row in rows
            ]
