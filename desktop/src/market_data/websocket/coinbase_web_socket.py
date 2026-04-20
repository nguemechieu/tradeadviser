import asyncio
import json
import re
import websockets

from event_bus.event import Event
from event_bus.event_types import EventType


class CoinbaseWebSocket:

    def __init__(self, symbols, event_bus):

        self.symbols = symbols
        self.bus = event_bus

        self.url = "wss://advanced-trade-ws.coinbase.com"

    @staticmethod
    def _looks_like_native_contract_symbol(product_id):
        symbol = str(product_id or "").strip().upper()
        if not symbol or "/" in symbol or "_" in symbol:
            return False
        if "PERP" in symbol:
            return True
        return bool(
            re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", symbol)
            or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", symbol)
        )

    def _normalize_symbol(self, product_id):
        symbol = str(product_id or "").strip().upper()
        if not symbol:
            return symbol
        if self._looks_like_native_contract_symbol(symbol):
            return symbol
        if "-" in symbol and "/" not in symbol:
            base, quote = symbol.split("-", 1)
            if base and quote:
                return f"{base}/{quote}"
        return symbol

    @staticmethod
    def _iter_ticker_rows(message):
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

    # ==========================================
    # CONNECT
    # ==========================================

    async def connect(self):

        async with websockets.connect(self.url) as ws:

            subscribe_msg = {
                "type": "subscribe",
                "channel": "ticker",
                "product_ids": self.symbols,
            }

            await ws.send(json.dumps(subscribe_msg))

            while True:

                message = await ws.recv()

                data = json.loads(message)

                channel = str(data.get("channel") or data.get("type") or "").strip().lower()
                if channel != "ticker":
                    continue

                for row in self._iter_ticker_rows(data):
                    ticker = {
                        "symbol": self._normalize_symbol(row.get("product_id")),
                        "price": float(row.get("price", 0)),
                        "bid": float(row.get("best_bid", 0)),
                        "ask": float(row.get("best_ask", 0)),
                        "volume": float(row.get("volume_24h", row.get("volume_24_h", 0))),
                        "timestamp": row.get("time") or data.get("timestamp"),
                    }

                    event = Event(
                        type=EventType.MARKET_TICK,
                        data=ticker
                    )

                    await self.bus.publish(event)
