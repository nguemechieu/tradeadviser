import json

import websockets

from event_bus.event import Event
from event_bus.event_types import EventType


class BinanceUsWebSocket:

    def __init__(self, symbols, event_bus, exchange_name="binanceus"):
        self.symbols = symbols
        self.bus = event_bus
        exchange_code = str(exchange_name or "binanceus").strip().lower()
        self.url = (
            "wss://stream.binance.com:9443/ws"
            if exchange_code == "binance"
            else "wss://stream.binance.us:9443/ws"
        )

    async def connect(self):
        streams = "/".join(
            f"{s.replace('/', '').lower()}@ticker"
            for s in self.symbols
        )

        url = f"{self.url}/{streams}"

        async with websockets.connect(url) as ws:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                symbol = data.get("s", "")
                if symbol and "/" not in symbol and len(symbol) >= 6:
                    # Simple heuristic for display fallback (e.g., BTCUSDT -> BTC/USDT)
                    if symbol.endswith("USDT"):
                        symbol = symbol[:-4] + "/USDT"
                    elif symbol.endswith("USD"):
                        symbol = symbol[:-3] + "/USD"

                ticker = {
                    "symbol": symbol or data.get("s"),
                    "price": float(data.get("c", 0) or 0),
                    "bid": float(data.get("b", 0) or 0),
                    "ask": float(data.get("a", 0) or 0),
                    "volume": float(data.get("v", 0) or 0),
                    "timestamp": data.get("E"),
                }

                await self.bus.publish(Event(type=EventType.MARKET_TICK, data=ticker))
