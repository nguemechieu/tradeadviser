from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from derivatives.core.config import EngineConfig

from derivatives.core.live_market_cache import LiveMarketCache
from derivatives.core.models import MarketTicker, OrderBookSnapshot
from derivatives.core.symbols import SymbolRegistry, normalize_symbol
from events.event_bus.event_bus import EventBus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MarketDataEngine:
    def __init__(
        self,
        event_bus: EventBus,
        cache: LiveMarketCache,
        symbol_registry: SymbolRegistry,
        brokers: dict[str, Any],
        *,
        config: EngineConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.cache = cache
        self.symbol_registry = symbol_registry
        self.brokers = dict(brokers or {})
        self.config = config or EngineConfig()
        self.logger = logger or logging.getLogger("DerivativesMarketDataEngine")
        self._tasks: list[asyncio.Task[Any]] = []
        self._started = False

    async def bootstrap_markets(self) -> dict[str, list[str]]:
        discovered: dict[str, list[str]] = {}
        for broker_key, broker in self.brokers.items():
            exchange = str(getattr(broker, "exchange_name", broker_key) or broker_key).lower()
            account_id = getattr(broker, "account_id", None)
            symbols: list[str] = []
            try:
                markets = await broker.fetch_markets()
            except Exception:
                self.logger.exception("market_bootstrap_failed broker=%s", broker_key)
                markets = {}

            if isinstance(markets, Mapping) and markets:
                for raw_symbol, market in markets.items():
                    route = self.symbol_registry.register(
                        broker_key=broker_key,
                        exchange=exchange,
                        account_id=account_id,
                        raw_symbol=str(raw_symbol),
                        market=market if isinstance(market, Mapping) else {},
                        market_type=str((market or {}).get("type") or (market or {}).get("market_type") or "future"),
                        metadata={"priority": getattr(broker, "priority", 100)},
                    )
                    symbols.append(route.normalized_symbol)
            else:
                try:
                    fetched = await broker.fetch_symbol()
                except Exception:
                    self.logger.exception("market_symbol_fetch_failed broker=%s", broker_key)
                    fetched = []
                for raw_symbol in list(fetched or []):
                    route = self.symbol_registry.register(
                        broker_key=broker_key,
                        exchange=exchange,
                        account_id=account_id,
                        raw_symbol=str(raw_symbol),
                        market=None,
                        market_type="future",
                        metadata={"priority": getattr(broker, "priority", 100)},
                    )
                    symbols.append(route.normalized_symbol)
            discovered[broker_key] = list(dict.fromkeys(symbols))
        return discovered

    async def start(self, *, symbols: Sequence[str] | None = None) -> None:
        if self._started:
            return
        self._started = True
        discovered = await self.bootstrap_markets()
        requested = set(str(symbol).strip() for symbol in list(symbols or []) if str(symbol).strip())
        for broker_key, broker in self.brokers.items():
            broker_symbols = [item for item in discovered.get(broker_key, []) if not requested or item in requested]
            for symbol in broker_symbols:
                route = self.symbol_registry.primary_route(symbol, broker_key=broker_key)
                if route is None:
                    continue
                self._tasks.append(asyncio.create_task(self._poll_ticker(route, broker), name=f"{broker_key}:{symbol}:ticker"))
                self._tasks.append(asyncio.create_task(self._poll_orderbook(route, broker), name=f"{broker_key}:{symbol}:orderbook"))

    async def stop(self) -> None:
        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._started = False

    async def _poll_ticker(self, route, broker) -> None:
        retry_delay = float(self.config.market_data_poll_seconds or 1.0)
        while self._started:
            try:
                payload = await broker.fetch_ticker(route.raw_symbol)
                if isinstance(payload, Mapping):
                    await self._publish_ticker(route, payload)
                retry_delay = float(self.config.market_data_poll_seconds or 1.0)
                await asyncio.sleep(max(0.2, float(self.config.market_data_poll_seconds)))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("ticker_poll_failed broker=%s symbol=%s", route.broker_key, route.raw_symbol)
                await asyncio.sleep(min(retry_delay, float(self.config.max_reconnect_delay_seconds)))
                retry_delay = min(retry_delay * 2.0, float(self.config.max_reconnect_delay_seconds))

    async def _poll_orderbook(self, route, broker) -> None:
        poll_seconds = max(0.5, float(self.config.orderbook_poll_seconds or 2.0))
        retry_delay = poll_seconds
        while self._started:
            try:
                payload = await broker.fetch_orderbook(route.raw_symbol, limit=25)
                if isinstance(payload, Mapping):
                    await self._publish_orderbook(route, payload)
                retry_delay = poll_seconds
                await asyncio.sleep(poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("orderbook_poll_failed broker=%s symbol=%s", route.broker_key, route.raw_symbol)
                await asyncio.sleep(min(retry_delay, float(self.config.max_reconnect_delay_seconds)))
                retry_delay = min(retry_delay * 2.0, float(self.config.max_reconnect_delay_seconds))

    async def _publish_ticker(self, route, payload: Mapping[str, Any]) -> None:
        raw_symbol = str(payload.get("symbol") or route.raw_symbol)
        normalized_symbol = normalize_symbol(route.exchange, raw_symbol, market=route.metadata)
        price = float(payload.get("price") or payload.get("last") or payload.get("mark") or payload.get("close") or 0.0)
        bid = payload.get("bid")
        ask = payload.get("ask")
        volume = payload.get("volume") or payload.get("base_volume")
        ticker = MarketTicker(
            symbol=normalized_symbol,
            exchange=route.exchange,
            broker_key=route.broker_key,
            account_id=route.account_id,
            price=price,
            bid=float(bid) if bid not in (None, "") else None,
            ask=float(ask) if ask not in (None, "") else None,
            volume=float(volume) if volume not in (None, "") else None,
            raw_symbol=raw_symbol,
            timestamp=self._payload_time(payload),
            metadata=dict(payload),
        )
        self.cache.update_ticker(ticker.to_dict())
        await self.bus.publish("market.ticker", ticker.to_dict(), source=f"market_data:{route.broker_key}")

    async def _publish_orderbook(self, route, payload: Mapping[str, Any]) -> None:
        raw_symbol = str(payload.get("symbol") or route.raw_symbol)
        normalized_symbol = normalize_symbol(route.exchange, raw_symbol, market=route.metadata)
        snapshot = OrderBookSnapshot(
            symbol=normalized_symbol,
            exchange=route.exchange,
            broker_key=route.broker_key,
            account_id=route.account_id,
            bids=self._coerce_levels(payload.get("bids")),
            asks=self._coerce_levels(payload.get("asks")),
            raw_symbol=raw_symbol,
            timestamp=self._payload_time(payload),
            metadata=dict(payload),
        )
        self.cache.update_orderbook(snapshot.to_dict())
        await self.bus.publish("market.orderbook", snapshot.to_dict(), source=f"market_data:{route.broker_key}")

    @staticmethod
    def _coerce_levels(rows: Any) -> list[tuple[float, float]]:
        levels: list[tuple[float, float]] = []
        for row in list(rows or []):
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            try:
                levels.append((float(row[0]), float(row[1])))
            except (TypeError, ValueError):
                continue
        return levels

    @staticmethod
    def _payload_time(payload: Mapping[str, Any]) -> datetime:
        raw = payload.get("timestamp") or payload.get("time") or payload.get("datetime")
        if isinstance(raw, datetime):
            return raw.astimezone(timezone.utc)
        if raw not in (None, ""):
            text = str(raw).replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text).astimezone(timezone.utc)
            except ValueError:
                pass
            try:
                return datetime.fromtimestamp(float(raw) / (1000.0 if float(raw) > 10_000_000_000 else 1.0), tz=timezone.utc)
            except (TypeError, ValueError):
                pass
        return _utcnow()
