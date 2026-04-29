import json

import websockets

from events.event import Event
from events.event_bus.event_types import EventType
from websocket.coinbase_web_socket import _event_name


class AlpacaWebSocket:
    def __init__(self, api_key, secret_key, symbols, event_bus, *, feed="iex", sandbox=False, max_symbols=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbols = list(dict.fromkeys(str(symbol or "").strip().upper() for symbol in (symbols or []) if str(symbol or "").strip()))
        self.bus = event_bus
        self.feed = str(feed or "iex").strip().lower() or "iex"
        self.sandbox = bool(sandbox)
        self.max_symbols = int(max_symbols or (30 if self.feed == "iex" else 50))

        host = "stream.data.alpaca.markets"
        self.url = f"wss://{host}/v2/{self.feed}"

    async def connect(self):
        async with websockets.connect(self.url) as ws:
            auth = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.secret_key,
            }
            await ws.send(json.dumps(auth))

            subscribe = {
                "action": "subscribe",
                "trades": self.symbols[: self.max_symbols],
                "quotes": self.symbols[: self.max_symbols],
            }
            await ws.send(json.dumps(subscribe))

            while True:
                message = await ws.recv()
                data = json.loads(message)

                for tick in data:
                    tick_type = str(tick.get("T") or "").strip().lower()
                    if tick_type not in {"q", "t"}:
                        continue

                    ticker = {
                        "exchange": "alpaca",
                        "symbol": str(tick.get("S") or "").strip().upper(),
                        "timestamp": tick.get("t"),
                    }
                    if tick_type == "q":
                        ticker["bid"] = tick.get("bp")
                        ticker["ask"] = tick.get("ap")
                    if tick_type == "t":
                        ticker["last"] = tick.get("p")
                        ticker["price"] = tick.get("p")
                        ticker["size"] = tick.get("s")

                    event = Event(type=_event_name(getattr(EventType, "MARKET_TICK", None), "market.tick"), data=ticker)
                    await self.bus.publish(event)
