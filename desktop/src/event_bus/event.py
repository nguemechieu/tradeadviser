"""Shared event model used across runtime components."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
import time
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Event:
    """Simple event envelope for the trading runtime."""

    type: str
    data: Any = None
    priority: int = 5
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    correlation_id: str | None = None
    replayed: bool = False

    def __post_init__(self) -> None:
        self.type = str(self.type or "")
        self.priority = int(self.priority or 0)
        self.sequence = int(self.sequence or 0)
        try:
            self.timestamp = float(self.timestamp)
        except Exception:
            self.timestamp = time.time()
        self.source = None if self.source in (None, "") else str(self.source)
        self.metadata = dict(self.metadata or {})
        self.id = str(self.id or uuid4().hex)
        self.correlation_id = None if self.correlation_id in (None, "") else str(self.correlation_id)
        self.replayed = bool(self.replayed)

    def copy(self, **updates: Any) -> "Event":
        payload = {
            "type": self.type,
            "data": self.data,
            "priority": self.priority,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "source": self.source,
            "metadata": dict(self.metadata),
            "id": self.id,
            "correlation_id": self.correlation_id,
            "replayed": self.replayed,
        }
        payload.update(updates)
        return Event(**payload)

    def to_record(self) -> dict[str, Any]:
        data = self.data
        if is_dataclass(data):
            data = asdict(data)
        return {
            "id": self.id,
            "type": self.type,
            "data": data,
            "priority": self.priority,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "replayed": self.replayed,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "Event":
        raw_timestamp = record.get("timestamp", time.time())
        try:
            timestamp = float(raw_timestamp)
        except Exception:
            try:
                timestamp = datetime.fromisoformat(str(raw_timestamp)).timestamp()
            except Exception:
                timestamp = time.time()
        return cls(
            type=str(record.get("type") or ""),
            data=record.get("data"),
            priority=record.get("priority", 5),
            sequence=record.get("sequence", 0),
            timestamp=timestamp,
            source=record.get("source"),
            correlation_id=record.get("correlation_id"),
            metadata=record.get("metadata"),
            id=record.get("id"),
            replayed=record.get("replayed", False),
        )


__all__ = ["Event"]
