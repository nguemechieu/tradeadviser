"""WebSocket connection manager for authoritative server event streams."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from fastapi import WebSocket

from sopotek.shared.events.base import ServerEventEnvelope


class WebSocketManager:
    """Tracks active desktop connections and broadcasts typed server events."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        self._connections[session_id].discard(websocket)
        if not self._connections[session_id]:
            self._connections.pop(session_id, None)

    async def send_event(self, session_id: str, envelope: ServerEventEnvelope) -> None:
        for connection in list(self._connections.get(session_id, set())):
            await connection.send_text(envelope.model_dump_json())

    async def broadcast(self, session_ids: Iterable[str], envelope: ServerEventEnvelope) -> None:
        for session_id in session_ids:
            await self.send_event(session_id, envelope)

