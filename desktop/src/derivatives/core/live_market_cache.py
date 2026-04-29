from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if number != number:  # NaN check
            return default
        return number
    except Exception:
        return default


def _normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def _normalize_timeframe(timeframe: Any) -> str:
    text = str(timeframe or "").strip().lower()
    return text or "1m"


def _normalize_timestamp(value: Any = None) -> datetime:
    if value is None or value == "":
        return _utc_now()

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)

    text = str(value).strip()
    if not text:
        return _utc_now()

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return _utc_now()


@dataclass(slots=True)
class MarketCandle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source": self.source,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(slots=True)
class MarketTick:
    symbol: str
    timestamp: datetime
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def spread(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return max(0.0, self.ask - self.bid)

    @property
    def mid(self) -> float:
        if self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "spread": self.spread,
            "mid": self.mid,
            "source": self.source,
            "metadata": dict(self.metadata or {}),
        }


class LiveMarketCache:
    """
    Thread-safe live market cache for the trading engine.

    Stores:
    - rolling candles by symbol/timeframe
    - latest ticks/prices by symbol
    - latest order book by symbol
    - latest features by symbol/timeframe
    - latest signals by symbol/timeframe
    - arbitrary runtime metadata

    Example:
        self.cache = LiveMarketCache(
            window_size=int(self.config.engine.history_window)
        )
    """

    def __init__(self, window_size: int = 500, default_timeframe: str = "1m") -> None:
        self.window_size = max(1, int(window_size or 500))
        self.default_timeframe = _normalize_timeframe(default_timeframe)

        self._lock = RLock()

        self._candles: Dict[str, Dict[str, Deque[MarketCandle]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=self.window_size))
        )

        self._ticks: Dict[str, Deque[MarketTick]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )

        self._latest_tick: Dict[str, MarketTick] = {}
        self._latest_price: Dict[str, float] = {}

        self._orderbooks: Dict[str, Dict[str, Any]] = {}
        self._features: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._signals: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._metadata: Dict[str, Dict[str, Any]] = defaultdict(dict)

    # ---------------------------------------------------------------------
    # Candle API
    # ---------------------------------------------------------------------

    def add_candle(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
            candle: Optional[Dict[str, Any]] = None,
            *,
            timestamp: Any = None,
            open: Any = None,
            high: Any = None,
            low: Any = None,
            close: Any = None,
            volume: Any = 0.0,
            source: str = "",
            metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MarketCandle]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        if not symbol:
            return None

        payload = dict(candle or {})

        timestamp_value = _normalize_timestamp(
            payload.get("timestamp")
            or payload.get("time")
            or payload.get("datetime")
            or timestamp
        )

        open_value = _safe_float(payload.get("open", open))
        high_value = _safe_float(payload.get("high", high))
        low_value = _safe_float(payload.get("low", low))
        close_value = _safe_float(payload.get("close", close))
        volume_value = _safe_float(payload.get("volume", volume), 0.0) or 0.0

        if open_value is None or high_value is None or low_value is None or close_value is None:
            return None

        item = MarketCandle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp_value,
            open=open_value,
            high=high_value,
            low=low_value,
            close=close_value,
            volume=volume_value,
            source=str(payload.get("source") or source or ""),
            metadata=dict(metadata or payload.get("metadata") or {}),
        )

        with self._lock:
            candles = self._candles[symbol][timeframe]

            if candles and candles[-1].timestamp == item.timestamp:
                candles[-1] = item
            else:
                candles.append(item)

            self._latest_price[symbol] = item.close

        return item

    def add_candles(
            self,
            symbol: str,
            timeframe: Optional[str],
            candles: Iterable[Dict[str, Any]],
            *,
            source: str = "",
    ) -> int:
        count = 0
        for candle in candles or []:
            item = self.add_candle(
                symbol=symbol,
                timeframe=timeframe,
                candle=candle,
                source=source,
            )
            if item is not None:
                count += 1
        return count

    def get_candles(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
            limit: Optional[int] = None,
            as_dict: bool = True,
    ) -> List[Any]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        with self._lock:
            items = list(self._candles.get(symbol, {}).get(timeframe, []))

        if limit is not None:
            items = items[-max(0, int(limit)):]

        if as_dict:
            return [item.to_dict() for item in items]
        return items

    def get_latest_candle(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
            as_dict: bool = True,
    ) -> Optional[Any]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        with self._lock:
            candles = self._candles.get(symbol, {}).get(timeframe)
            item = candles[-1] if candles else None

        if item is None:
            return None
        return item.to_dict() if as_dict else item

    def candle_count(self, symbol: str, timeframe: Optional[str] = None) -> int:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        with self._lock:
            return len(self._candles.get(symbol, {}).get(timeframe, []))

    def has_enough_candles(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
            minimum: int = 50,
    ) -> bool:
        return self.candle_count(symbol, timeframe) >= int(minimum)

    # ---------------------------------------------------------------------
    # Tick / ticker API
    # ---------------------------------------------------------------------

    def update_tick(
            self,
            symbol: str,
            price: Any = None,
            *,
            bid: Any = None,
            ask: Any = None,
            volume: Any = None,
            timestamp: Any = None,
            source: str = "",
            metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MarketTick]:
        symbol = _normalize_symbol(symbol)
        if not symbol:
            return None

        bid_value = _safe_float(bid)
        ask_value = _safe_float(ask)
        price_value = _safe_float(price)

        if price_value is None:
            if bid_value is not None and ask_value is not None and bid_value > 0 and ask_value > 0:
                price_value = (bid_value + ask_value) / 2.0
            elif bid_value is not None and bid_value > 0:
                price_value = bid_value
            elif ask_value is not None and ask_value > 0:
                price_value = ask_value

        if price_value is None or price_value <= 0:
            return None

        item = MarketTick(
            symbol=symbol,
            timestamp=_normalize_timestamp(timestamp),
            price=price_value,
            bid=bid_value,
            ask=ask_value,
            volume=_safe_float(volume),
            source=source,
            metadata=dict(metadata or {}),
        )

        with self._lock:
            self._ticks[symbol].append(item)
            self._latest_tick[symbol] = item
            self._latest_price[symbol] = item.mid

        return item

    def update_ticker(self, symbol: str, ticker: Dict[str, Any], *, source: str = "") -> Optional[MarketTick]:
        ticker = dict(ticker or {})

        return self.update_tick(
            symbol=symbol,
            price=(
                    ticker.get("last")
                    or ticker.get("close")
                    or ticker.get("price")
                    or ticker.get("mark")
            ),
            bid=ticker.get("bid"),
            ask=ticker.get("ask"),
            volume=ticker.get("volume") or ticker.get("baseVolume") or ticker.get("quoteVolume"),
            timestamp=ticker.get("timestamp") or ticker.get("datetime"),
            source=str(ticker.get("source") or source or ""),
            metadata=ticker,
        )

    def get_latest_tick(self, symbol: str, as_dict: bool = True) -> Optional[Any]:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            item = self._latest_tick.get(symbol)

        if item is None:
            return None
        return item.to_dict() if as_dict else item

    def get_ticks(
            self,
            symbol: str,
            limit: Optional[int] = None,
            as_dict: bool = True,
    ) -> List[Any]:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            items = list(self._ticks.get(symbol, []))

        if limit is not None:
            items = items[-max(0, int(limit)):]

        if as_dict:
            return [item.to_dict() for item in items]
        return items

    def get_latest_price(self, symbol: str, default: Optional[float] = None) -> Optional[float]:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            return self._latest_price.get(symbol, default)

    # ---------------------------------------------------------------------
    # Order book API
    # ---------------------------------------------------------------------

    def update_orderbook(
            self,
            symbol: str,
            bids: Optional[List[Any]] = None,
            asks: Optional[List[Any]] = None,
            *,
            timestamp: Any = None,
            source: str = "",
            metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        symbol = _normalize_symbol(symbol)

        payload = {
            "symbol": symbol,
            "bids": list(bids or []),
            "asks": list(asks or []),
            "timestamp": _normalize_timestamp(timestamp).isoformat(),
            "source": source,
            "metadata": dict(metadata or {}),
        }

        with self._lock:
            self._orderbooks[symbol] = payload

            best_bid = self._best_book_price(payload["bids"], reverse=True)
            best_ask = self._best_book_price(payload["asks"], reverse=False)

            if best_bid is not None and best_ask is not None:
                self._latest_price[symbol] = (best_bid + best_ask) / 2.0
            elif best_bid is not None:
                self._latest_price[symbol] = best_bid
            elif best_ask is not None:
                self._latest_price[symbol] = best_ask

        return payload

    def get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            value = self._orderbooks.get(symbol)

        return dict(value) if isinstance(value, dict) else None

    @staticmethod
    def _best_book_price(levels: List[Any], *, reverse: bool) -> Optional[float]:
        prices = []

        for level in levels or []:
            if isinstance(level, dict):
                price = _safe_float(level.get("price"))
            elif isinstance(level, (list, tuple)) and level:
                price = _safe_float(level[0])
            else:
                price = None

            if price is not None and price > 0:
                prices.append(price)

        if not prices:
            return None

        return max(prices) if reverse else min(prices)

    # ---------------------------------------------------------------------
    # Feature / signal API
    # ---------------------------------------------------------------------

    def update_features(
            self,
            symbol: str,
            timeframe: Optional[str],
            features: Dict[str, Any],
    ) -> Dict[str, Any]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        payload = dict(features or {})
        payload["symbol"] = symbol
        payload["timeframe"] = timeframe
        payload["updated_at"] = _utc_now().isoformat()

        with self._lock:
            self._features[symbol][timeframe] = payload

        return payload

    def get_features(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        with self._lock:
            return dict(self._features.get(symbol, {}).get(timeframe, {}) or {})

    def update_signal(
            self,
            symbol: str,
            timeframe: Optional[str],
            signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        payload = dict(signal or {})
        payload["symbol"] = symbol
        payload["timeframe"] = timeframe
        payload["updated_at"] = _utc_now().isoformat()

        with self._lock:
            self._signals[symbol][timeframe] = payload

        return payload

    def get_signal(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
    ) -> Dict[str, Any]:
        symbol = _normalize_symbol(symbol)
        timeframe = _normalize_timeframe(timeframe or self.default_timeframe)

        with self._lock:
            return dict(self._signals.get(symbol, {}).get(timeframe, {}) or {})

    # ---------------------------------------------------------------------
    # Metadata / snapshot API
    # ---------------------------------------------------------------------

    def set_metadata(self, symbol: str, key: str, value: Any) -> None:
        symbol = _normalize_symbol(symbol)
        key = str(key or "").strip()
        if not symbol or not key:
            return

        with self._lock:
            self._metadata[symbol][key] = value

    def get_metadata(self, symbol: str, key: Optional[str] = None, default: Any = None) -> Any:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            data = dict(self._metadata.get(symbol, {}) or {})

        if key is None:
            return data

        return data.get(key, default)

    def symbols(self) -> List[str]:
        with self._lock:
            values = set(self._candles.keys())
            values.update(self._ticks.keys())
            values.update(self._latest_price.keys())
            values.update(self._orderbooks.keys())
            values.update(self._features.keys())
            values.update(self._signals.keys())

        return sorted(values)

    def timeframes(self, symbol: str) -> List[str]:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            return sorted(self._candles.get(symbol, {}).keys())

    def snapshot(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if symbol:
            normalized_symbol = _normalize_symbol(symbol)
            return {
                "symbol": normalized_symbol,
                "latest_price": self.get_latest_price(normalized_symbol),
                "latest_tick": self.get_latest_tick(normalized_symbol),
                "orderbook": self.get_orderbook(normalized_symbol),
                "timeframes": {
                    timeframe: {
                        "count": self.candle_count(normalized_symbol, timeframe),
                        "latest": self.get_latest_candle(normalized_symbol, timeframe),
                        "features": self.get_features(normalized_symbol, timeframe),
                        "signal": self.get_signal(normalized_symbol, timeframe),
                    }
                    for timeframe in self.timeframes(normalized_symbol)
                },
                "metadata": self.get_metadata(normalized_symbol),
            }

        return {
            "window_size": self.window_size,
            "default_timeframe": self.default_timeframe,
            "symbols": self.symbols(),
            "latest_prices": self.latest_prices(),
        }

    def latest_prices(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._latest_price)

    # ---------------------------------------------------------------------
    # Maintenance API
    # ---------------------------------------------------------------------

    def clear_symbol(self, symbol: str) -> None:
        symbol = _normalize_symbol(symbol)

        with self._lock:
            self._candles.pop(symbol, None)
            self._ticks.pop(symbol, None)
            self._latest_tick.pop(symbol, None)
            self._latest_price.pop(symbol, None)
            self._orderbooks.pop(symbol, None)
            self._features.pop(symbol, None)
            self._signals.pop(symbol, None)
            self._metadata.pop(symbol, None)

    def clear(self) -> None:
        with self._lock:
            self._candles.clear()
            self._ticks.clear()
            self._latest_tick.clear()
            self._latest_price.clear()
            self._orderbooks.clear()
            self._features.clear()
            self._signals.clear()
            self._metadata.clear()

    def resize(self, window_size: int) -> None:
        new_size = max(1, int(window_size or self.window_size))

        with self._lock:
            self.window_size = new_size

            new_candles: Dict[str, Dict[str, Deque[MarketCandle]]] = defaultdict(
                lambda: defaultdict(lambda: deque(maxlen=self.window_size))
            )

            for symbol, tf_map in self._candles.items():
                for timeframe, candles in tf_map.items():
                    new_candles[symbol][timeframe] = deque(
                        list(candles)[-new_size:],
                        maxlen=new_size,
                    )

            self._candles = new_candles

            new_ticks: Dict[str, Deque[MarketTick]] = defaultdict(
                lambda: deque(maxlen=self.window_size)
            )

            for symbol, ticks in self._ticks.items():
                new_ticks[symbol] = deque(
                    list(ticks)[-new_size:],
                    maxlen=new_size,
                )

            self._ticks = new_ticks

    # ---------------------------------------------------------------------
    # Compatibility helpers
    # ---------------------------------------------------------------------

    def update_price(self, symbol: str, price: Any, **kwargs: Any) -> Optional[MarketTick]:
        return self.update_tick(symbol=symbol, price=price, **kwargs)

    def get_price(self, symbol: str, default: Optional[float] = None) -> Optional[float]:
        return self.get_latest_price(symbol, default=default)

    def append_candle(self, symbol: str, timeframe: str, candle: Dict[str, Any]) -> Optional[MarketCandle]:
        return self.add_candle(symbol=symbol, timeframe=timeframe, candle=candle)

    def latest_candle(self, symbol: str, timeframe: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.get_latest_candle(symbol=symbol, timeframe=timeframe, as_dict=True)

    def history(
            self,
            symbol: str,
            timeframe: Optional[str] = None,
            limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return self.get_candles(symbol=symbol, timeframe=timeframe, limit=limit, as_dict=True)