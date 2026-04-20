from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None

from broker.ibkr.exceptions import IBKRConfigurationError


class IBKRWebApiWebSocket:
    """Thin websocket wrapper.

    IBKR's websocket topics are intentionally left configurable so the broker can
    evolve without hardcoding a topic grammar here.
    """

    def __init__(self, websocket_url: str, *, logger: logging.Logger | None = None) -> None:
        self.websocket_url = str(websocket_url or "").strip()
        self.logger = logger or logging.getLogger("IBKRWebApiWebSocket")
        self._connection = None

    async def connect(self):
        if websockets is None:
            raise IBKRConfigurationError("websockets is required for IBKR Web API websocket streaming.")
        self._connection = await websockets.connect(self.websocket_url)
        return self._connection

    async def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            await connection.close()

    async def send(self, payload: Any) -> None:
        if self._connection is None:
            await self.connect()
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
        await self._connection.send(payload)

    async def receive_forever(self):
        if self._connection is None:
            await self.connect()
        async for message in self._connection:
            yield message

    async def subscribe_topics(self, topics: list[str]) -> None:
        if not topics:
            return
        for topic in topics:
            await self.send(topic)
            await asyncio.sleep(0)
