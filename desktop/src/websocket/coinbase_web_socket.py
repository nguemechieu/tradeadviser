from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from typing import Any

import websockets

from events.event import Event

try:
    from events.event_bus.event_types import EventType
except Exception:
    class EventType:  # type: ignore
        MARKET_TICK = "market.tick"


def _event_name(event_type: Any, fallback: str) -> str:
    """Return a safe event name even if EventType import is broken."""
    try:
        if hasattr(event_type, "value"):
            return str(event_type.value)
        text = str(event_type or "").strip()
        return text or fallback
    except Exception:
        return fallback


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class CoinbaseWebSocket:
    """Coinbase Advanced Trade public ticker WebSocket."""

    def __init__(
            self,
            symbols,
            event_bus,
            *,
            url: str = "wss://advanced-trade-ws.coinbase.com",
            logger: logging.Logger | None = None,
            reconnect_delay: float = 3.0,
            max_reconnect_delay: float = 30.0,
    ) -> None:
        self.symbols = list(symbols or [])
        self.bus = event_bus
        self.url = str(url)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.reconnect_delay = max(0.5, float(reconnect_delay or 3.0))
        self.max_reconnect_delay = max(self.reconnect_delay, float(max_reconnect_delay or 30.0))
        self.running = False

        self.market_tick_event = _event_name(
            getattr(EventType, "MARKET_TICK", None),
            "market.tick",
        )

    @staticmethod
    def _looks_like_native_contract_symbol(product_id: Any) -> bool:
        symbol = str(product_id or "").strip().upper()
        if not symbol or "/" in symbol or "_" in symbol:
            return False
        if "PERP" in symbol:
            return True
        return bool(
            re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", symbol)
            or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", symbol)
        )

    @classmethod
    def _to_coinbase_product_id(cls, symbol: Any) -> str:
        """Convert app symbol BTC/USD to Coinbase product BTC-USD."""
        value = str(symbol or "").strip().upper()
        if not value:
            return value

        if cls._looks_like_native_contract_symbol(value):
            return value

        if "/" in value:
            base, quote = value.split("/", 1)
            return f"{base}-{quote}"

        return value

    @classmethod
    def _normalize_symbol(cls, product_id: Any) -> str:
        """Convert Coinbase product BTC-USD to app symbol BTC/USD."""
        symbol = str(product_id or "").strip().upper()
        if not symbol:
            return symbol

        if cls._looks_like_native_contract_symbol(symbol):
            return symbol

        if "-" in symbol and "/" not in symbol:
            base, quote = symbol.split("-", 1)
            if base and quote:
                return f"{base}/{quote}"

        return symbol

    @staticmethod
    def _iter_ticker_rows(message: Any):
        data = dict(message or {})
        events = data.get("events")

        if isinstance(events, list) and events:
            for event in events:
                if not isinstance(event, dict):
                    continue

                tickers = event.get("tickers")
                if isinstance(tickers, list):
                    for ticker in tickers:
                        if isinstance(ticker, dict):
                            yield ticker

        elif data.get("type") == "ticker":
            yield data

    def _subscription_products(self) -> list[str]:
        products = []
        seen = set()

        for symbol in self.symbols:
            product_id = self._to_coinbase_product_id(symbol)
            if not product_id or product_id in seen:
                continue
            products.append(product_id)
            seen.add(product_id)

        return products

    async def _publish_tick(self, ticker: dict[str, Any]) -> None:
        publish = getattr(self.bus, "publish", None)

        if not callable(publish):
            return

        event = Event(
            type=self.market_tick_event,
            data=ticker,
            source="coinbase.websocket",
        )

        try:
            await _maybe_await(publish(event))
        except TypeError:
            # Some buses use publish(type, data) instead of publish(Event).
            try:
                await _maybe_await(publish(self.market_tick_event, ticker))
            except Exception:
                self.logger.debug("Unable to publish Coinbase ticker", exc_info=True)
        except Exception:
            # Publishing failure should not kill the Coinbase WebSocket connection.
            self.logger.debug("Unable to publish Coinbase ticker", exc_info=True)

    def _parse_ticker(self, row: dict[str, Any], message: dict[str, Any]) -> dict[str, Any] | None:
        product_id = row.get("product_id") or row.get("product_id_raw")
        symbol = self._normalize_symbol(product_id)

        price = _safe_float(row.get("price"), 0.0)
        bid = _safe_float(row.get("best_bid") or row.get("bid"), 0.0)
        ask = _safe_float(row.get("best_ask") or row.get("ask"), 0.0)
        volume = _safe_float(row.get("volume_24h") or row.get("volume_24_h") or row.get("volume"), 0.0)

        if not symbol:
            return None

        # Do not publish useless empty ticks.
        if price <= 0 and bid <= 0 and ask <= 0:
            return None

        return {
            "symbol": symbol,
            "product_id": str(product_id or "").strip().upper(),
            "price": price,
            "bid": bid,
            "ask": ask,
            "volume": volume,
            "timestamp": row.get("time") or message.get("timestamp"),
            "exchange": "coinbase",
        }

    async def connect(self) -> None:
        """Connect forever until stop() is called."""
        self.running = True
        delay = self.reconnect_delay

        while self.running:
            try:
                await self._connect_once()
                delay = self.reconnect_delay

            except asyncio.CancelledError:
                self.running = False
                raise

            except Exception as exc:
                self.logger.warning("Coinbase WebSocket disconnected: %s", exc)

                if not self.running:
                    break

                await asyncio.sleep(delay)
                delay = min(self.max_reconnect_delay, delay * 1.5)

    async def _connect_once(self) -> None:
        products = self._subscription_products()

        if not products:
            self.logger.warning("Coinbase WebSocket has no products to subscribe to.")
            return

        async with websockets.connect(
                self.url,
                ping_interval=30,
                ping_timeout=60,
                close_timeout=10,
                max_queue=2048,
        ) as ws:
            subscribe_msg = {
                "type": "subscribe",
                "channel": "ticker",
                "product_ids": products,
            }

            await ws.send(json.dumps(subscribe_msg))
            self.logger.info("Coinbase WebSocket subscribed to %s", products)

            while self.running:
                raw_message = await ws.recv()

                try:
                    data = json.loads(raw_message)
                except Exception:
                    self.logger.debug("Invalid Coinbase WebSocket JSON: %r", raw_message)
                    continue

                channel = str(data.get("channel") or data.get("type") or "").strip().lower()
                if channel not in {"ticker", "subscriptions"}:
                    continue

                if channel == "subscriptions":
                    continue

                for row in self._iter_ticker_rows(data):
                    ticker = self._parse_ticker(row, data)
                    if ticker is None:
                        continue

                    await self._publish_tick(ticker)

    def stop(self) -> None:
        self.running = False


__all__ = ["CoinbaseWebSocket"]