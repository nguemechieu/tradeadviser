from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

import aiohttp

from .auth import CoinbaseJWTAuth
from .client import CoinbaseAdvancedTradeClient
from .models import CoinbaseConfig, OrderBookEvent, OrderBookLevel, TickerEvent
from .normalizer import normalize_lookup_symbol
from .products import CoinbaseFuturesProductService


class CoinbaseFuturesMarketDataService:
    def __init__(
        self,
        client: CoinbaseAdvancedTradeClient,
        products: CoinbaseFuturesProductService,
        *,
        event_bus: Any = None,
        auth: CoinbaseJWTAuth | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.products = products
        self.event_bus = event_bus
        self.auth = auth or client.auth
        self.config = CoinbaseConfig.from_broker_config(client.config)
        self.logger = logger or logging.getLogger("CoinbaseFuturesMarketData")
        self._subscription_tasks: dict[tuple[str, tuple[str, ...]], asyncio.Task[Any]] = {}
        self._books: dict[str, dict[str, dict[float, float]]] = defaultdict(lambda: {"bids": {}, "asks": {}})
        self._latest_tickers: dict[str, TickerEvent] = {}
        self._closing = False

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        product = await self.products.resolve_product(symbol)
        payload = await self.client.get_public_ticker(product.product_id)
        ticker = self._normalize_ticker(product.normalized_symbol, product.product_id, payload)
        await self._publish_ticker(ticker)
        return ticker.to_dict()

    async def fetch_orderbook(self, symbol: str, *, limit: int = 50) -> dict[str, Any]:
        product = await self.products.resolve_product(symbol)
        payload = await self.client.get_product_book(product.product_id, limit=limit)
        snapshot = self._normalize_rest_orderbook(product.normalized_symbol, product.product_id, payload)
        await self._publish_orderbook(snapshot)
        return snapshot.to_dict()

    async def subscribe_ticker(self, symbols: list[str]) -> asyncio.Task[Any]:
        return await self._subscribe("ticker", symbols)

    async def subscribe_orderbook(self, symbols: list[str]) -> asyncio.Task[Any]:
        return await self._subscribe("level2", symbols)

    async def _subscribe(self, channel: str, symbols: list[str]) -> asyncio.Task[Any]:
        product_ids = []
        for symbol in list(symbols or []):
            product_ids.append(await self.products.product_id_for(symbol))
        key = (channel, tuple(sorted(set(product_ids))))
        existing = self._subscription_tasks.get(key)
        if existing is not None and not existing.done():
            return existing
        task = asyncio.create_task(self._run_subscription(channel, product_ids), name=f"coinbase_futures_ws:{channel}")
        self._subscription_tasks[key] = task
        return task

    async def _run_subscription(self, channel: str, product_ids: list[str]) -> None:
        backoff = self.config.ws_reconnect_delay_seconds
        resolved_products = [await self.products.resolve_product(product_id) for product_id in product_ids]
        product_index = {product.product_id: product for product in resolved_products}
        while not self._closing:
            websocket = None
            try:
                websocket = await self.client.open_websocket()
                await websocket.send_json(
                    {
                        "type": "subscribe",
                        "channel": channel,
                        "product_ids": list(product_ids),
                        "jwt": self.auth.build_ws_token(),
                    }
                )
                await websocket.send_json(
                    {
                        "type": "subscribe",
                        "channel": "heartbeats",
                        "jwt": self.auth.build_ws_token(),
                    }
                )
                backoff = self.config.ws_reconnect_delay_seconds

                while not self._closing:
                    message = await websocket.receive()
                    if message.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_ws_payload(channel, product_index, json.loads(message.data))
                        continue
                    if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.ERROR}:
                        break
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("coinbase_futures_ws_failure channel=%s", channel)
            finally:
                if websocket is not None:
                    await websocket.close()

            if self._closing:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, self.config.ws_max_reconnect_delay_seconds)

    async def _handle_ws_payload(self, channel: str, product_index: dict[str, Any], payload: dict[str, Any]) -> None:
        if str(payload.get("channel") or "").strip().lower() != channel:
            return
        if channel == "ticker":
            for event in list(payload.get("events") or []):
                for row in list(event.get("tickers") or []):
                    product_id = str(row.get("product_id") or "").strip().upper()
                    product = product_index.get(product_id)
                    if product is None:
                        continue
                    ticker = self._normalize_ticker(product.normalized_symbol, product_id, row, timestamp=payload.get("timestamp"))
                    await self._publish_ticker(ticker)
            return
        if channel == "level2":
            for event in list(payload.get("events") or []):
                product_id = str(event.get("product_id") or payload.get("product_id") or "").strip().upper()
                product = product_index.get(product_id)
                if product is None:
                    continue
                snapshot = self._apply_level2_event(product.normalized_symbol, product_id, event, payload)
                if snapshot is not None:
                    await self._publish_orderbook(snapshot)

    def _normalize_ticker(
        self,
        symbol: str,
        product_id: str,
        payload: dict[str, Any],
        *,
        timestamp: str | None = None,
    ) -> TickerEvent:
        return TickerEvent(
            symbol=symbol,
            product_id=product_id,
            price=float(payload.get("price", 0.0) or 0.0),
            bid=float(payload.get("best_bid", payload.get("bid", 0.0)) or 0.0) or None,
            ask=float(payload.get("best_ask", payload.get("ask", 0.0)) or 0.0) or None,
            volume=float(payload.get("volume_24_h", payload.get("volume_24h", 0.0)) or 0.0) or None,
            timestamp=str(payload.get("time") or timestamp or "").strip() or None,
            raw=dict(payload or {}),
        )

    def _normalize_rest_orderbook(self, symbol: str, product_id: str, payload: dict[str, Any]) -> OrderBookEvent:
        bids = []
        asks = []
        pricebook = payload.get("pricebook") if isinstance(payload.get("pricebook"), dict) else payload
        for row in list(pricebook.get("bids") or []):
            bids.append(OrderBookLevel(price=float(row.get("price", 0.0) or 0.0), size=float(row.get("size", 0.0) or 0.0)))
        for row in list(pricebook.get("asks") or []):
            asks.append(OrderBookLevel(price=float(row.get("price", 0.0) or 0.0), size=float(row.get("size", 0.0) or 0.0)))
        return OrderBookEvent(
            symbol=symbol,
            product_id=product_id,
            bids=bids,
            asks=asks,
            timestamp=str(pricebook.get("time") or "").strip() or None,
            raw=dict(payload or {}),
        )

    def _apply_level2_event(
        self,
        symbol: str,
        product_id: str,
        event: dict[str, Any],
        envelope: dict[str, Any],
    ) -> OrderBookEvent | None:
        book = self._books[product_id]
        event_type = str(event.get("type") or "").strip().lower()
        updates = list(event.get("updates") or [])

        if event_type == "snapshot":
            book["bids"].clear()
            book["asks"].clear()

        for update in updates:
            side = "bids" if str(update.get("side") or "").strip().lower().startswith("bid") else "asks"
            price = float(update.get("price_level", update.get("price", 0.0)) or 0.0)
            size = float(update.get("new_quantity", update.get("size", 0.0)) or 0.0)
            if price <= 0:
                continue
            if size <= 0:
                book[side].pop(price, None)
            else:
                book[side][price] = size

        bids = [OrderBookLevel(price=price, size=size) for price, size in sorted(book["bids"].items(), reverse=True)]
        asks = [OrderBookLevel(price=price, size=size) for price, size in sorted(book["asks"].items())]
        return OrderBookEvent(
            symbol=symbol,
            product_id=product_id,
            bids=bids[:50],
            asks=asks[:50],
            timestamp=str(envelope.get("timestamp") or "").strip() or None,
            sequence_num=int(envelope.get("sequence_num", 0) or 0) or None,
            raw={"envelope": dict(envelope or {}), "event": dict(event or {})},
        )

    async def _publish_ticker(self, ticker: TickerEvent) -> None:
        self._latest_tickers[normalize_lookup_symbol(ticker.symbol)] = ticker
        self._latest_tickers[normalize_lookup_symbol(ticker.product_id)] = ticker
        if self.event_bus is None:
            return
        payload = ticker.to_dict()
        await self.event_bus.publish("ticker_event", payload)
        await self.event_bus.publish("market.ticker", payload)

    async def _publish_orderbook(self, snapshot: OrderBookEvent) -> None:
        if self.event_bus is None:
            return
        payload = snapshot.to_dict()
        await self.event_bus.publish("orderbook_event", payload)
        await self.event_bus.publish("market.orderbook", payload)

    async def close(self) -> None:
        self._closing = True
        for task in list(self._subscription_tasks.values()):
            task.cancel()
        if self._subscription_tasks:
            await asyncio.gather(*self._subscription_tasks.values(), return_exceptions=True)
        self._subscription_tasks.clear()

    def latest_price_for(self, symbol: str) -> float | None:
        ticker = self._latest_tickers.get(normalize_lookup_symbol(symbol))
        if ticker is None or ticker.price <= 0:
            return None
        return float(ticker.price)


__all__ = ["CoinbaseFuturesMarketDataService"]
