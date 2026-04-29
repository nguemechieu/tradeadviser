"""Base event envelopes for server-to-desktop streaming."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import Field

from shared.contracts.base import SharedModel, utc_now
from shared.enums.common import EventSource


PayloadT = TypeVar("PayloadT")


class ServerEventEnvelope(SharedModel, Generic[PayloadT]):
    """Versioned server event envelope with correlation metadata.

    The server is authoritative for event ordering and sequence assignment.
    Desktop uses this envelope for resumable state rehydration.
    """

    protocol_version: str = "1.0"
    event_type: str
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    correlation_id: str | None = None
    causation_id: str | None = None
    source: EventSource = EventSource.SERVER
    sequence: int = 0
    emitted_at: datetime = Field(default_factory=utc_now)
    payload: PayloadT

    @classmethod
    def heartbeat(
        cls,
        *,
        event_type: str,
        correlation_id: str | None,
        sequence: int,
        payload: dict[str, Any],
    ) -> "ServerEventEnvelope[dict[str, Any]]":
        return cls(
            event_type=event_type,
            correlation_id=correlation_id,
            sequence=sequence,
            payload=payload,
        )

