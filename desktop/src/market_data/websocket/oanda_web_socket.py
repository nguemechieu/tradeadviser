import json

import aiohttp

from broker.oanda_broker import OandaBroker
from event_bus.event import Event
from event_bus.event_types import EventType


class OandaWebSocket:
    def __init__(self, token, account_id, symbols, event_bus, *, mode="practice"):
        self.token = token
        self.account_id = account_id
        self.symbols = [
            str(symbol or "").strip().upper().replace("/", "_")
            for symbol in (symbols or [])
            if str(symbol or "").strip()
        ]
        self.bus = event_bus
        self.mode = str(mode or "practice").strip().lower() or "practice"
        self.url = (
            "https://stream-fxpractice.oanda.com"
            if self.mode in {"paper", "practice", "sandbox"}
            else "https://stream-fxtrade.oanda.com"
        )
        self.url = f"{self.url}/v3/accounts/{self.account_id}/pricing/stream"

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def connect(self):
        if not self.symbols:
            return

        timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=None)
        params = {"instruments": ",".join(self.symbols)}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request("GET", self.url, headers=self._headers, params=params) as response:
                response.raise_for_status()

                async for raw_line in response.content:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ticker = OandaBroker.pricing_stream_payload_to_tick(payload)
                    if ticker is None:
                        continue

                    event = Event(type=EventType.MARKET_TICK, data=ticker)
                    await self.bus.publish(event)

        raise RuntimeError("Oanda pricing stream closed unexpectedly.")

    async def stream(self):
        await self.connect()
