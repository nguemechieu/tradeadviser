from __future__ import annotations

"""
InvestPro MarketDataEngine

Canonical market-data gateway for live and historical multi-asset feeds.

Responsibilities:
- stream or poll ticks from broker/feed adapters
- publish market-data events
- aggregate ticks into candles
- fetch/cache historical OHLCV
- publish historical candles
- manage order book snapshots
- expose latest price/candle snapshots for UI, strategy, and risk layers
"""
import json
import asyncio
import contextlib
import inspect

import logging
import math
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


try:
    from ..event_bus import EventType
except Exception:  # pragma: no cover
    class EventType:  # type: ignore
        MARKET_DATA_EVENT = "market.data.event"
        MARKET_DATA = "market.data"
        MARKET_DATA_TOPIC = "market.data.topic"
        MARKET_TICK = "market.tick"
        PRICE_UPDATE = "price.update"
        CANDLE = "market.candle"
        HISTORICAL_CANDLE = "market.historical_candle"
        ORDER_BOOK = "market.order_book"

try:
    from models.candle import Candle
except Exception:  # pragma: no cover
    @dataclass
    class Candle:  # type: ignore
        symbol: str
        timeframe: str
        open: float
        high: float
        low: float
        close: float
        volume: float
        start: datetime
        end: datetime
        metadata: dict[str, Any] = field(default_factory=dict)

try:
    from models.order_book_snap_shot import OrderBookSnapshot
except Exception:  # pragma: no cover
    @dataclass
    class OrderBookSnapshot:  # type: ignore
        symbol: str
        bids: list[Any] = field(default_factory=list)
        asks: list[Any] = field(default_factory=list)
        timestamp: datetime = field(
            default_factory=lambda: datetime.now(timezone.utc))
        metadata: dict[str, Any] = field(default_factory=dict)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default

    try:
        number = float(value)
    except Exception:
        return default

    if not math.isfinite(number):
        return default

    return number


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        numeric = float(value)
        if abs(numeric) > 1e11:
            numeric /= 1000.0
        try:
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
        except Exception:
            return _utc_now()

    text = str(value or "").strip()
    if not text:
        return _utc_now()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return _utc_now()


def timeframe_to_seconds(timeframe: str) -> int:
    text = str(timeframe or "1m").strip().lower()

    if not text:
        return 60

    aliases = {
        "tick": 1,
        "1tick": 1,
        "1sec": 1,
        "1second": 1,
        "1min": 60,
        "1minute": 60,
        "1mn": 60,
        "1hour": 3600,
        "1day": 86400,
        "1week": 604800,
        "1mo": 2592000,
        "1mon": 2592000,
        "1month": 2592000,
    }

    if text in aliases:
        return aliases[text]

    if len(text) < 2:
        return 60

    number_text = text[:-1]
    suffix = text[-1]

    try:
        value = int(number_text or 1)
    except Exception:
        return 60

    if suffix == "s":
        return max(1, value)

    if suffix == "m":
        return max(1, value * 60)

    if suffix == "h":
        return max(1, value * 3600)

    if suffix == "d":
        return max(1, value * 86400)

    if suffix == "w":
        return max(1, value * 604800)

    return 60


def _event_name(name: str, fallback: str) -> Any:
    return getattr(EventType, name, fallback)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, datetime):
        return value.isoformat()

    if is_dataclass(value):
        try:
            return _json_safe(asdict(value))
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item)
            for item in value
        ]

    return str(value)


@dataclass(slots=True)
class FeedSubscription:
    symbol: str
    venue: str = "primary"
    started_at: datetime = field(default_factory=_utc_now)
    last_tick_at: Optional[datetime] = None
    tick_count: int = 0
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(slots=True)
class HistoricalCacheEntry:
    candles: list[Any]
    created_at: float

    def fresh(self, ttl_seconds: float) -> bool:
        return (time.time() - self.created_at) <= ttl_seconds


class MarketDataPublisher:
    """Small helper to publish market data safely to async/sync event buses."""

    def __init__(self, event_bus: Any, *, logger: logging.Logger | None = None) -> None:
        self.bus = event_bus
        self.logger = logger or logging.getLogger("MarketDataPublisher")

    async def publish(self, event_type: Any, payload: Any, *, priority: int = 20, source: str = "market_data") -> None:
        if self.bus is None:
            return

        publish = getattr(self.bus, "publish", None)
        if not callable(publish):
            return

        try:
            try:
                result = publish(event_type, payload,
                                 priority=priority, source=source)
            except TypeError:
                result = publish(event_type, payload)

            await _maybe_await(result)

        except Exception as exc:
            self.logger.debug(
                "market_data_publish_failed event=%s error=%s", event_type, exc)

    async def publish_tick(self, payload: Mapping[str, Any], *, source: str) -> None:
        data = dict(payload or {})

        events = [
            (_event_name("MARKET_DATA_EVENT", "market.data.event"), 19),
            (_event_name("MARKET_DATA", "market.data"), 19),
            (_event_name("MARKET_DATA_TOPIC", "market.data.topic"), 19),
            (_event_name("MARKET_TICK", "market.tick"), 20),
            (_event_name("PRICE_UPDATE", "price.update"), 21),
        ]

        for event_type, priority in events:
            await self.publish(event_type, dict(data), priority=priority, source=source)


class LiveFeedManager:
    def __init__(
        self,
        feed: Any,
        event_bus: Any,
        *,
        poll_interval: float = 1.0,
        logger: logging.Logger | None = None,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        self.feed = feed
        self.bus = event_bus
        self.publisher = MarketDataPublisher(event_bus, logger=logger)
        self.poll_interval = max(0.1, float(poll_interval or 1.0))
        self.max_backoff_seconds = max(1.0, float(max_backoff_seconds or 30.0))
        self.logger = logger or logging.getLogger("MarketDataLiveFeed")
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._running = True
        self.error_counts: dict[str, int] = {}

    async def start_symbol(self, symbol: str) -> None:
        normalized = _normalize_symbol(symbol)

        if not normalized:
            return

        if normalized in self._tasks and not self._tasks[normalized].done():
            return

        self._running = True
        self._tasks[normalized] = asyncio.create_task(
            self._run_symbol_guarded(normalized),
            name=f"market_data:{normalized}",
        )

    async def stop_symbol(self, symbol: str) -> None:
        normalized = _normalize_symbol(symbol)
        task = self._tasks.pop(normalized, None)

        if task is None:
            return

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def stop(self) -> None:
        self._running = False

        tasks = list(self._tasks.values())
        self._tasks.clear()

        for task in tasks:
            task.cancel()

        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run_symbol_guarded(self, symbol: str) -> None:
        backoff = self.poll_interval

        while self._running:
            try:
                await self._run_symbol(symbol)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error_counts[symbol] = self.error_counts.get(
                    symbol, 0) + 1
                self.logger.warning(
                    "market_data_symbol_task_failed symbol=%s error=%s", symbol, exc)
                await asyncio.sleep(backoff)
                backoff = min(self.max_backoff_seconds, backoff * 2.0)

    async def _run_symbol(self, symbol: str) -> None:
        if hasattr(self.feed, "stream_ticks") and callable(self.feed.stream_ticks):
            await self._stream_symbol(symbol)
            return

        await self._poll_symbol(symbol)

    async def _stream_symbol(self, symbol: str) -> None:
        stream = self.feed.stream_ticks(symbol)

        if inspect.isawaitable(stream):
            stream = await stream

        async for tick in stream:
            payload = self._normalize_tick(symbol, tick)
            if payload is not None:
                await self.publisher.publish_tick(payload, source="market_data.stream")

    async def _poll_symbol(self, symbol: str) -> None:
        while self._running:
            try:
                ticker = self.feed.fetch_ticker(symbol)
                ticker = await _maybe_await(ticker)

                payload = self._normalize_tick(symbol, ticker)

                if payload is not None:
                    await self.publisher.publish_tick(payload, source="market_data.poll")

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error_counts[symbol] = self.error_counts.get(
                    symbol, 0) + 1
                self.logger.warning(
                    "market_data_poll_failed symbol=%s error=%s", symbol, exc)

            await asyncio.sleep(self.poll_interval)

    def _normalize_tick(self, symbol: str, tick: Any) -> dict[str, Any] | None:
        payload = dict(tick or {}) if isinstance(
            tick, Mapping) else _object_to_dict(tick)
        payload.setdefault("symbol", symbol)

        price = _safe_float(
            payload.get("price")
            or payload.get("last")
            or payload.get("close")
            or payload.get("mark")
            or payload.get("mid"),
            0.0,
        )

        bid = _safe_float(payload.get("bid"), 0.0)
        ask = _safe_float(payload.get("ask"), 0.0)

        if price <= 0 and bid > 0 and ask > 0:
            price = (bid + ask) / 2.0

        if price <= 0:
            return None

        payload["symbol"] = _normalize_symbol(payload.get("symbol"))
        payload["price"] = price
        payload["timestamp"] = _normalize_timestamp(payload.get("timestamp"))

        return payload

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "tasks": {
                symbol: not task.done()
                for symbol, task in self._tasks.items()
            },
            "error_counts": dict(self.error_counts),
        }


class CandleAggregator:
    def __init__(
        self,
        event_bus: Any,
        *,
        timeframe: str = "1m",
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.publisher = MarketDataPublisher(event_bus, logger=logger)
        self.timeframe = str(timeframe or "1m")
        self._seconds = timeframe_to_seconds(self.timeframe)
        self._candles: dict[tuple[str, str], Candle] = {}
        self.latest_closed: dict[tuple[str, str], Candle] = {}
        self.logger = logger or logging.getLogger(
            f"CandleAggregator[{self.timeframe}]")

        subscribe = getattr(self.bus, "subscribe", None)
        if callable(subscribe):
            try:
                subscribe(_event_name("MARKET_TICK",
                          "market.tick"), self.on_tick)
            except Exception:
                self.logger.debug(
                    "candle_aggregator_subscribe_failed", exc_info=True)

    async def on_tick(self, event: Any) -> None:
        payload = dict(getattr(event, "data", event) or {})
        symbol = _normalize_symbol(payload.get("symbol"))

        if not symbol:
            return

        price = _safe_float(
            payload.get("price")
            or payload.get("last")
            or payload.get("close")
            or payload.get("mark")
            or payload.get("mid"),
            0.0,
        )

        if price <= 0.0:
            return

        volume = _safe_float(payload.get("volume"), 0.0)
        timestamp = _normalize_timestamp(payload.get("timestamp"))

        candle = await self.update(symbol=symbol, price=price, volume=volume, timestamp=timestamp)

        # Open candle is intentionally not published as final CANDLE every tick.
        _ = candle

    async def update(self, *, symbol: str, price: float, volume: float = 0.0, timestamp: datetime | None = None) -> Candle:
        timestamp = timestamp or _utc_now()
        start_epoch = math.floor(
            timestamp.timestamp() / self._seconds) * self._seconds
        start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
        end = start + timedelta(seconds=self._seconds)

        key = (_normalize_symbol(symbol), self.timeframe)
        current = self._candles.get(key)

        if current is None or getattr(current, "start", None) != start:
            if current is not None:
                await self._publish_closed(current)

            current = Candle(
                symbol=key[0],
                timeframe=self.timeframe,
                open=float(price),
                high=float(price),
                low=float(price),
                close=float(price),
                volume=float(volume),
                start=start,
                end=end,
            )
            self._candles[key] = current
            return current

        current.high = max(float(current.high), float(price))
        current.low = min(float(current.low), float(price))
        current.close = float(price)
        current.volume = float(current.volume or 0.0) + float(volume or 0.0)

        return current

    async def _publish_closed(self, candle: Candle) -> None:
        key = (_normalize_symbol(getattr(candle, "symbol", "")), self.timeframe)
        self.latest_closed[key] = candle

        await self.publisher.publish(
            _event_name("CANDLE", "market.candle"),
            candle,
            priority=40,
            source="candle_aggregator",
        )

    async def flush(self) -> None:
        pending = list(self._candles.values())
        self._candles.clear()

        for candle in pending:
            await self._publish_closed(candle)

    def latest_open(self, symbol: str) -> Candle | None:
        return self._candles.get((_normalize_symbol(symbol), self.timeframe))

    def latest_closed_candle(self, symbol: str) -> Candle | None:
        return self.latest_closed.get((_normalize_symbol(symbol), self.timeframe))


class OrderBookEngine:
    def __init__(self, event_bus: Any, *, logger: logging.Logger | None = None) -> None:
        self.bus = event_bus
        self.publisher = MarketDataPublisher(event_bus, logger=logger)
        self.snapshots: dict[str, OrderBookSnapshot] = {}
        self.logger = logger or logging.getLogger("OrderBookEngine")

    async def publish_snapshot(self, snapshot: OrderBookSnapshot | Mapping[str, Any]) -> OrderBookSnapshot:
        normalized = self._normalize_snapshot(snapshot)

        if not normalized.symbol:
            raise ValueError("Order book snapshot symbol is required")

        self.snapshots[normalized.symbol] = normalized

        await self.publisher.publish(
            _event_name("ORDER_BOOK", "market.order_book"),
            normalized,
            priority=30,
            source="order_book_engine",
        )

        return normalized

    def latest(self, symbol: str) -> OrderBookSnapshot | None:
        return self.snapshots.get(_normalize_symbol(symbol))

    def _normalize_snapshot(self, snapshot: OrderBookSnapshot | Mapping[str, Any]) -> OrderBookSnapshot:
        if isinstance(snapshot, OrderBookSnapshot):
            return snapshot

        payload = dict(snapshot or {})

        return OrderBookSnapshot(
            symbol=_normalize_symbol(payload.get("symbol")),
            bids=list(payload.get("bids") or []),
            asks=list(payload.get("asks") or []),
            timestamp=_normalize_timestamp(payload.get("timestamp")),
        )


class MarketDataEngine:
    """Canonical market-data gateway for live and historical multi-asset feeds."""

    def __init__(
        self,
        feed: Any,
        event_bus: Any,
        *,
        candle_timeframes: list[str] | None = None,
        poll_interval: float = 1.0,
        history_cache_ttl_seconds: float = 15.0,
        stale_tick_seconds: float = 15.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.feed = feed
        self.bus = event_bus
        self.publisher = MarketDataPublisher(event_bus, logger=logger)
        self.logger = logger or logging.getLogger("MarketDataEngine")

        self.history_cache_ttl_seconds = max(
            0.0, float(history_cache_ttl_seconds or 0.0))
        self.stale_tick_seconds = max(1.0, float(stale_tick_seconds or 15.0))

        self.subscriptions: dict[str, FeedSubscription] = {}
        self.latest_ticks: dict[str, dict[str, Any]] = {}
        self.history_cache: dict[tuple[str, str, int],
                                 HistoricalCacheEntry] = {}

        self.live_feed = LiveFeedManager(
            feed,
            event_bus,
            poll_interval=poll_interval,
            logger=self.logger,
        )

        self.order_books = OrderBookEngine(event_bus, logger=self.logger)

        timeframes = candle_timeframes or ["1m"]
        self.aggregators = [
            CandleAggregator(event_bus, timeframe=timeframe,
                             logger=self.logger)
            for timeframe in timeframes
        ]

        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.error_count = 0
        self.history_fetch_count = 0

    async def start(self, symbols: list[str]) -> None:
        self.started_at = _utc_now()
        self.stopped_at = None

        for symbol in list(symbols or []):
            normalized = _normalize_symbol(symbol)

            if not normalized:
                continue

            self.subscriptions[normalized] = FeedSubscription(
                symbol=normalized)
            await self.live_feed.start_symbol(normalized)

        self._log("market_data_started", symbols=list(self.subscriptions))

    async def stop(self) -> None:
        self.stopped_at = _utc_now()

        await self.live_feed.stop()

        for aggregator in self.aggregators:
            await aggregator.flush()

        self._log("market_data_stopped", symbols=list(self.subscriptions))

    async def subscribe(self, symbol: str, *, venue: str = "primary") -> None:
        normalized = _normalize_symbol(symbol)

        if not normalized:
            return

        self.subscriptions[normalized] = FeedSubscription(
            symbol=normalized, venue=str(venue or "primary"))
        await self.live_feed.start_symbol(normalized)

    async def unsubscribe(self, symbol: str) -> None:
        normalized = _normalize_symbol(symbol)

        if not normalized:
            return

        self.subscriptions.pop(normalized, None)
        await self.live_feed.stop_symbol(normalized)

    async def publish_tick(self, symbol: str, tick: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _normalize_symbol(symbol)
        payload = dict(tick or {})
        payload["symbol"] = _normalize_symbol(
            payload.get("symbol") or normalized)

        price = _safe_float(
            payload.get("price")
            or payload.get("last")
            or payload.get("close")
            or payload.get("mark")
            or payload.get("mid"),
            0.0,
        )

        bid = _safe_float(payload.get("bid"), 0.0)
        ask = _safe_float(payload.get("ask"), 0.0)

        if price <= 0 and bid > 0 and ask > 0:
            price = (bid + ask) / 2.0

        payload["price"] = price
        payload["timestamp"] = _normalize_timestamp(payload.get("timestamp"))

        if price <= 0:
            raise ValueError(
                f"Invalid market tick price for {payload['symbol']}")

        await self._update_feed_price(payload)

        self.latest_ticks[payload["symbol"]] = dict(payload)

        subscription = self.subscriptions.get(payload["symbol"])
        if subscription is not None:
            subscription.last_tick_at = payload["timestamp"]
            subscription.tick_count += 1

        await self.publisher.publish_tick(payload, source="market_data_engine")

        return payload

    async def _update_feed_price(self, payload: Mapping[str, Any]) -> None:
        update_market_price = getattr(self.feed, "update_market_price", None)

        if not callable(update_market_price):
            return

        try:
            result = update_market_price(
                payload["symbol"], float(payload.get("price") or 0.0))
            await _maybe_await(result)
        except Exception:
            self.logger.debug(
                "market_price_update_skipped symbol=%s", payload.get("symbol"))

    async def publish_order_book(self, snapshot: OrderBookSnapshot | Mapping[str, Any]) -> OrderBookSnapshot:
        return await self.order_books.publish_snapshot(snapshot)

    async def fetch_history(
        self,
        symbol: str,
        *,
        timeframe: str = "1m",
        limit: int = 200,
        use_cache: bool = True,
    ) -> list[Candle]:
        normalized_symbol = _normalize_symbol(symbol)
        normalized_timeframe = str(timeframe or "1m").strip() or "1m"
        normalized_limit = max(1, int(limit or 200))

        cache_key = (normalized_symbol, normalized_timeframe, normalized_limit)

        if use_cache and cache_key in self.history_cache:
            entry = self.history_cache[cache_key]
            if entry.fresh(self.history_cache_ttl_seconds):
                return list(entry.candles)

        fetch_ohlcv = getattr(self.feed, "fetch_ohlcv", None)

        if not callable(fetch_ohlcv):
            raise RuntimeError("Feed does not expose fetch_ohlcv()")

        rows = fetch_ohlcv(
            normalized_symbol, timeframe=normalized_timeframe, limit=normalized_limit)
        rows = await _maybe_await(rows)

        seconds = timeframe_to_seconds(normalized_timeframe)
        candles = [
            candle
            for candle in (
                self._row_to_candle(
                    row, symbol=normalized_symbol, timeframe=normalized_timeframe, seconds=seconds)
                for row in list(rows or [])
            )
            if candle is not None
        ]

        self.history_cache[cache_key] = HistoricalCacheEntry(
            candles=list(candles),
            created_at=time.time(),
        )
        self.history_fetch_count += 1

        return candles

    async def publish_history(self, symbol: str, *, timeframe: str = "1m", limit: int = 200) -> list[Candle]:
        candles = await self.fetch_history(symbol, timeframe=timeframe, limit=limit)

        for candle in candles:
            await self.publisher.publish(
                _event_name("HISTORICAL_CANDLE", "market.historical_candle"),
                candle,
                priority=35,
                source="market_data_engine",
            )
            await self.publisher.publish(
                _event_name("CANDLE", "market.candle"),
                candle,
                priority=40,
                source="market_data_engine",
            )
            await self.publish_tick(
                candle.symbol,
                {
                    "symbol": candle.symbol,
                    "price": candle.close,
                    "timestamp": candle.end,
                    "volume": candle.volume,
                },
            )

        return candles

    def _row_to_candle(self, row: Any, *, symbol: str, timeframe: str, seconds: int) -> Candle | None:
        try:
            if isinstance(row, Mapping):
                timestamp = (
                    row.get("timestamp")
                    or row.get("time")
                    or row.get("date")
                    or row.get("start")
                    or row.get("t")
                )
                open_ = row.get("open", row.get("o"))
                high = row.get("high", row.get("h"))
                low = row.get("low", row.get("l"))
                close = row.get("close", row.get("c"))
                volume = row.get("volume", row.get("v", 0.0))
            else:
                timestamp, open_, high, low, close, volume = list(row)[:6]

            start = _normalize_timestamp(timestamp)

            return Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=_safe_float(open_),
                high=_safe_float(high),
                low=_safe_float(low),
                close=_safe_float(close),
                volume=_safe_float(volume),
                start=start,
                end=start + timedelta(seconds=seconds),
            )
        except Exception:
            return None

    def latest_price(self, symbol: str) -> float | None:
        payload = self.latest_ticks.get(_normalize_symbol(symbol))

        if payload is None:
            return None

        price = _safe_float(payload.get("price") or payload.get(
            "last") or payload.get("close"), 0.0)
        return price if price > 0 else None

    def latest_tick_age_seconds(self, symbol: str) -> float | None:
        payload = self.latest_ticks.get(_normalize_symbol(symbol))

        if payload is None:
            return None

        timestamp = _normalize_timestamp(payload.get("timestamp"))
        return max(0.0, (_utc_now() - timestamp).total_seconds())

    def is_stale(self, symbol: str, *, max_age_seconds: float | None = None) -> bool:
        age = self.latest_tick_age_seconds(symbol)

        if age is None:
            return True

        threshold = self.stale_tick_seconds if max_age_seconds is None else float(
            max_age_seconds)
        return age > threshold

    def latest_candle(self, symbol: str, *, timeframe: str = "1m", closed: bool = False) -> Candle | None:
        normalized_timeframe = str(timeframe or "1m")

        for aggregator in self.aggregators:
            if aggregator.timeframe != normalized_timeframe:
                continue

            if closed:
                return aggregator.latest_closed_candle(symbol)

            return aggregator.latest_open(symbol)

        return None

    def clear_history_cache(self) -> None:
        self.history_cache.clear()

    def snapshot(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "subscriptions": {
                symbol: subscription.to_dict()
                for symbol, subscription in self.subscriptions.items()
            },
            "latest_prices": {
                symbol: self.latest_price(symbol)
                for symbol in self.latest_ticks
            },
            "latest_tick_age_seconds": {
                symbol: self.latest_tick_age_seconds(symbol)
                for symbol in self.latest_ticks
            },
            "history_cache_size": len(self.history_cache),
            "history_fetch_count": self.history_fetch_count,
            "order_book_symbols": list(self.order_books.snapshots),
            "aggregators": [aggregator.timeframe for aggregator in self.aggregators],
            "live_feed": self.live_feed.snapshot(),
            "error_count": self.error_count,
        }

    def healthy(self) -> bool:
        if self.error_count > 10:
            return False

        for symbol in self.subscriptions:
            if self.is_stale(symbol, max_age_seconds=self.stale_tick_seconds * 4):
                return False

        return True

    def _log(self, event_name: str, **payload: Any) -> None:
        try:
            message = json.dumps(
                {"event": event_name, **payload}, default=str, sort_keys=True)
        except Exception:
            message = f"{event_name} {payload}"

        self.logger.info(message)


def _object_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, Mapping):
        return dict(value)

    if is_dataclass(value):
        try:
            return asdict(value)
        except Exception:
            return {}

    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            result = value.to_dict()
            return dict(result or {}) if isinstance(result, Mapping) else {}
        except Exception:
            return {}

    output: dict[str, Any] = {}

    for key in (
        "symbol",
        "price",
        "last",
        "close",
        "bid",
        "ask",
        "volume",
        "timestamp",
        "time",
        "metadata",
    ):
        if hasattr(value, key):
            output[key] = getattr(value, key)

    return output


__all__ = [
    "CandleAggregator",
    "FeedSubscription",
    "HistoricalCacheEntry",
    "LiveFeedManager",
    "MarketDataEngine",
    "MarketDataPublisher",
    "OrderBookEngine",
    "timeframe_to_seconds",
]
