from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from core.event_bus import AsyncEventBus

from core.event_bus.event_types import EventType
from core.models import Candle
from models.order_book_snap_shot import OrderBookSnapshot

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1e11:
            numeric /= 1000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    return _utc_now()


def timeframe_to_seconds(timeframe: str) -> int:
    text = str(timeframe or "1m").strip().lower()
    if not text:
        return 60
    value = int(text[:-1] or 1)
    suffix = text[-1]
    if suffix == "s":
        return value
    if suffix == "m":
        return value * 60
    if suffix == "h":
        return value * 3600
    if suffix == "d":
        return value * 86400
    return 60


@dataclass(slots=True)
class FeedSubscription:
    symbol: str
    venue: str = "primary"
    started_at: datetime = field(default_factory=_utc_now)


class LiveFeedManager:
    def __init__(
        self,
        feed: Any,
        event_bus: AsyncEventBus,
        *,
        poll_interval: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.feed = feed
        self.bus = event_bus
        self.poll_interval = max(0.1, float(poll_interval or 1.0))
        self.logger = logger or logging.getLogger("MarketDataLiveFeed")
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    async def start_symbol(self, symbol: str) -> None:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            return
        if normalized in self._tasks and not self._tasks[normalized].done():
            return
        self._tasks[normalized] = asyncio.create_task(
            self._run_symbol(normalized),
            name=f"market_data:{normalized}",
        )

    async def stop(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run_symbol(self, symbol: str) -> None:
        if hasattr(self.feed, "stream_ticks"):
            await self._stream_symbol(symbol)
            return
        await self._poll_symbol(symbol)

    async def _stream_symbol(self, symbol: str) -> None:
        async for tick in self.feed.stream_ticks(symbol):
            payload = dict(tick or {})
            payload.setdefault("symbol", symbol)
            await self._publish_tick(payload, source="market_data.stream")

    async def _poll_symbol(self, symbol: str) -> None:
        while True:
            try:
                ticker = await self.feed.fetch_ticker(symbol)
                payload = dict(ticker or {})
                payload.setdefault("symbol", symbol)
                payload.setdefault("price", payload.get("last") or payload.get("close"))
                payload.setdefault("timestamp", _utc_now())
                await self._publish_tick(payload, source="market_data.poll")
            except Exception as exc:
                self.logger.warning("market_data_poll_failed symbol=%s error=%s", symbol, exc)
            await asyncio.sleep(self.poll_interval)

    async def _publish_tick(self, payload: Mapping[str, Any], *, source: str) -> None:
        await self.bus.publish(EventType.MARKET_DATA_EVENT, dict(payload), priority=19, source=source)
        await self.bus.publish(EventType.MARKET_DATA, dict(payload), priority=19, source=source)
        await self.bus.publish(EventType.MARKET_DATA_TOPIC, dict(payload), priority=19, source=source)
        await self.bus.publish(EventType.MARKET_TICK, dict(payload), priority=20, source=source)
        await self.bus.publish(EventType.PRICE_UPDATE, dict(payload), priority=21, source=source)


class CandleAggregator:
    def __init__(self, event_bus: AsyncEventBus, *, timeframe: str = "1m") -> None:
        self.bus = event_bus
        self.timeframe = timeframe
        self._seconds = timeframe_to_seconds(timeframe)
        self._candles: dict[tuple[str, str], Candle] = {}
        self.bus.subscribe(EventType.MARKET_TICK, self.on_tick)

    async def on_tick(self, event) -> None:
        payload = dict(getattr(event, "data", {}) or {})
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        price = float(payload.get("price") or payload.get("last") or payload.get("close") or 0.0)
        if price <= 0.0:
            return
        volume = float(payload.get("volume") or 0.0)
        timestamp = _normalize_timestamp(payload.get("timestamp"))
        start_epoch = math.floor(timestamp.timestamp() / self._seconds) * self._seconds
        start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
        end = start + timedelta(seconds=self._seconds)

        key = (symbol, self.timeframe)
        current = self._candles.get(key)
        if current is None or current.start != start:
            if current is not None:
                await self.bus.publish(EventType.CANDLE, current, priority=40, source="candle_aggregator")
            self._candles[key] = Candle(
                symbol=symbol,
                timeframe=self.timeframe,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                start=start,
                end=end,
            )
            return

        current.high = max(current.high, price)
        current.low = min(current.low, price)
        current.close = price
        current.volume += volume

    async def flush(self) -> None:
        pending = list(self._candles.values())
        self._candles.clear()
        for candle in pending:
            await self.bus.publish(EventType.CANDLE, candle, priority=40, source="candle_aggregator")


class OrderBookEngine:
    def __init__(self, event_bus: AsyncEventBus) -> None:
        self.bus = event_bus
        self.snapshots: dict[str, OrderBookSnapshot] = {}

    async def publish_snapshot(self, snapshot: OrderBookSnapshot | Mapping[str, Any]) -> OrderBookSnapshot:
        if not isinstance(snapshot, OrderBookSnapshot):
            payload = dict(snapshot or {})
            snapshot = OrderBookSnapshot(
                symbol=str(payload.get("symbol") or "").strip().upper(),
                bids=list(payload.get("bids") or []),
                asks=list(payload.get("asks") or []),
                timestamp=_normalize_timestamp(payload.get("timestamp")),
            )
        self.snapshots[snapshot.symbol] = snapshot
        await self.bus.publish(EventType.ORDER_BOOK, snapshot, priority=30, source="order_book_engine")
        return snapshot


class MarketDataEngine:
    """Canonical market-data gateway for live and historical multi-asset feeds."""

    def __init__(
        self,
        feed: Any,
        event_bus: AsyncEventBus,
        *,
        candle_timeframes: list[str] | None = None,
        poll_interval: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.feed = feed
        self.bus = event_bus
        self.logger = logger or logging.getLogger("MarketDataEngine")
        self.subscriptions: dict[str, FeedSubscription] = {}
        self.latest_ticks: dict[str, dict[str, Any]] = {}
        self.history_cache: dict[tuple[str, str, int], list[Candle]] = {}
        self.live_feed = LiveFeedManager(feed, event_bus, poll_interval=poll_interval, logger=self.logger)
        self.order_books = OrderBookEngine(event_bus)
        self.aggregators = [CandleAggregator(event_bus, timeframe=timeframe) for timeframe in (candle_timeframes or ["1m"])]

    async def start(self, symbols: list[str]) -> None:
        for symbol in list(symbols or []):
            normalized = str(symbol or "").strip().upper()
            if not normalized:
                continue
            self.subscriptions[normalized] = FeedSubscription(symbol=normalized)
            await self.live_feed.start_symbol(normalized)
        self._log("market_data_started", symbols=list(self.subscriptions))

    async def stop(self) -> None:
        await self.live_feed.stop()
        for aggregator in self.aggregators:
            await aggregator.flush()
        self._log("market_data_stopped", symbols=list(self.subscriptions))

    async def publish_tick(self, symbol: str, tick: Mapping[str, Any]) -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        payload = dict(tick or {})
        payload["symbol"] = payload.get("symbol", normalized)
        payload["timestamp"] = _normalize_timestamp(payload.get("timestamp"))
        if hasattr(self.feed, "update_market_price"):
            try:
                self.feed.update_market_price(payload["symbol"], float(payload.get("price") or payload.get("last") or payload.get("close") or 0.0))
            except Exception:
                self.logger.debug("market_price_update_skipped symbol=%s", payload["symbol"])
        self.latest_ticks[payload["symbol"]] = dict(payload)
        await self.bus.publish(EventType.MARKET_DATA_EVENT, dict(payload), priority=19, source="market_data_engine")
        await self.bus.publish(EventType.MARKET_DATA, dict(payload), priority=19, source="market_data_engine")
        await self.bus.publish(EventType.MARKET_DATA_TOPIC, dict(payload), priority=19, source="market_data_engine")
        await self.bus.publish(EventType.MARKET_TICK, dict(payload), priority=20, source="market_data_engine")
        await self.bus.publish(EventType.PRICE_UPDATE, dict(payload), priority=21, source="market_data_engine")
        return payload

    async def publish_order_book(self, snapshot: OrderBookSnapshot | Mapping[str, Any]) -> OrderBookSnapshot:
        return await self.order_books.publish_snapshot(snapshot)

    async def fetch_history(self, symbol: str, *, timeframe: str = "1m", limit: int = 200) -> list[Candle]:
        cache_key = (str(symbol or "").strip().upper(), str(timeframe or "1m"), int(limit))
        if cache_key in self.history_cache:
            return list(self.history_cache[cache_key])

        rows = await self.feed.fetch_ohlcv(cache_key[0], timeframe=cache_key[1], limit=cache_key[2])
        seconds = timeframe_to_seconds(cache_key[1])
        candles: list[Candle] = []
        for row in rows or []:
            try:
                timestamp_ms, open_, high, low, close, volume = row[:6]
            except Exception:
                continue
            start = _normalize_timestamp(timestamp_ms)
            candles.append(
                Candle(
                    symbol=cache_key[0],
                    timeframe=cache_key[1],
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                    start=start,
                    end=start + timedelta(seconds=seconds),
                )
            )
        self.history_cache[cache_key] = list(candles)
        return candles

    async def publish_history(self, symbol: str, *, timeframe: str = "1m", limit: int = 200) -> list[Candle]:
        candles = await self.fetch_history(symbol, timeframe=timeframe, limit=limit)
        for candle in candles:
            await self.bus.publish(EventType.HISTORICAL_CANDLE, candle, priority=35, source="market_data_engine")
            await self.bus.publish(EventType.CANDLE, candle, priority=40, source="market_data_engine")
            await self.publish_tick(
                candle.symbol,
                {"symbol": candle.symbol, "price": candle.close, "timestamp": candle.end, "volume": candle.volume},
            )
        return candles

    def latest_price(self, symbol: str) -> float | None:
        payload = self.latest_ticks.get(str(symbol or "").strip().upper())
        if payload is None:
            return None
        try:
            return float(payload.get("price") or payload.get("last") or payload.get("close"))
        except (TypeError, ValueError):
            return None

    def _log(self, event_name: str, **payload: Any) -> None:
        try:
            message = json.dumps({"event": event_name, **payload}, default=str, sort_keys=True)
        except Exception:
            message = f"{event_name} {payload}"
        self.logger.info(message)


__all__ = [
    "CandleAggregator",
    "LiveFeedManager",
    "MarketDataEngine",
    "OrderBookEngine",
    "FeedSubscription",
    "timeframe_to_seconds",
]
