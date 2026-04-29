"""Shared event model used across runtime components."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_event_type(value: Any) -> str:
    """Normalize strings, enums, and event-like objects into a stable event name."""
    if value is None:
        return ""

    if hasattr(value, "type"):
        try:
            nested = getattr(value, "type")
            if nested is not value:
                return _normalize_event_type(nested)
        except Exception:
            pass

    if hasattr(value, "topic"):
        try:
            nested = getattr(value, "topic")
            if nested is not value:
                return _normalize_event_type(nested)
        except Exception:
            pass

    if hasattr(value, "value"):
        try:
            return str(value.value)
        except Exception:
            pass

    text = str(value or "").strip()

    # Defensive cleanup for bad enum string conversions:
    # str(EventType.MARKET_TICK) can become "EventType.MARKET_TICK"
    # in some enum implementations/import mistakes.
    if text.startswith("EventType."):
        return text.split(".", 1)[1].strip().lower().replace("_", ".")

    return text


def _coerce_timestamp(value: Any) -> float:
    if value in (None, ""):
        return time.time()

    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()

    try:
        numeric = float(value)
        if not math.isfinite(numeric):
            return time.time()

        # Treat millisecond timestamps as seconds.
        if abs(numeric) > 1e11:
            numeric /= 1000.0

        return numeric
    except Exception:
        pass

    text = str(value or "").strip()
    if not text:
        return time.time()

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    except Exception:
        return time.time()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    if is_dataclass(value):
        try:
            return _json_safe(asdict(value))
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item)
            for item in value
        ]

    if hasattr(value, "value"):
        try:
            return _json_safe(value.value)
        except Exception:
            pass

    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass

    return str(value)


@dataclass(slots=True)
class Event:
    """
    Event envelope for TradeAdviser / InvestPro runtime.

    This class intentionally supports both naming styles:

    - event.type
    - event.topic

    That keeps compatibility with:
    - generic AsyncEventBus
    - derivatives EventBus
    - old handlers expecting event.event_type
    - old handlers expecting event.payload
    """

    type: Any
    data: Any = None
    priority: int = 5
    sequence: int = 0
    timestamp: float | datetime | str = field(default_factory=time.time)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    correlation_id: str | None = None
    replayed: bool = False

    def __post_init__(self) -> None:
        self.type = _normalize_event_type(self.type)
        self.priority = int(self.priority or 0)
        self.sequence = int(self.sequence or 0)
        self.timestamp = _coerce_timestamp(self.timestamp)
        self.source = None if self.source in (None, "") else str(self.source)
        self.metadata = dict(self.metadata or {})
        self.id = str(self.id or uuid4().hex)
        self.correlation_id = (
            None
            if self.correlation_id in (None, "")
            else str(self.correlation_id)
        )
        self.replayed = bool(self.replayed)

    # ------------------------------------------------------------------
    # Compatibility aliases
    # ------------------------------------------------------------------

    @property
    def event_type(self) -> str:
        """Compatibility alias used by older runtime components."""
        return str(self.type)

    @event_type.setter
    def event_type(self, value: Any) -> None:
        self.type = _normalize_event_type(value)

    @property
    def topic(self) -> str:
        """Compatibility alias used by derivatives/runtime event buses."""
        return str(self.type)

    @topic.setter
    def topic(self, value: Any) -> None:
        self.type = _normalize_event_type(value)

    @property
    def payload(self) -> Any:
        """Compatibility alias for handlers that expect event.payload."""
        return self.data

    @payload.setter
    def payload(self, value: Any) -> None:
        self.data = value

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(float(self.timestamp), tz=timezone.utc)

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - float(self.timestamp))

    # ------------------------------------------------------------------
    # Copy / conversion
    # ------------------------------------------------------------------

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

        if "topic" in updates and "type" not in updates:
            updates["type"] = updates.pop("topic")

        if "payload" in updates and "data" not in updates:
            updates["data"] = updates.pop("payload")

        if "event_type" in updates and "type" not in updates:
            updates["type"] = updates.pop("event_type")

        payload.update(updates)
        return Event(**payload)

    def with_metadata(self, **metadata: Any) -> "Event":
        merged = dict(self.metadata or {})
        merged.update(metadata)
        return self.copy(metadata=merged)


    @topic.setter
    def topic(self, value: Any) -> None:
     self.type = _normalize_event_type(value)

    def to_record(self) -> dict[str, Any]:
        event_type = _normalize_event_type(self.type)

        return {
            "id": self.id,
            "type": event_type,
            "topic": event_type,
            "event_type": event_type,
            "data": _json_safe(self.data),
            "payload": _json_safe(self.data),
            "priority": int(self.priority),
            "sequence": int(self.sequence),
            "timestamp": float(self.timestamp),
            "datetime": self.datetime.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": _json_safe(self.metadata),
            "replayed": bool(self.replayed),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_record()

    @classmethod
    def from_record(cls, record: dict[str, Any] | Mapping[str, Any]) -> "Event":
        payload = dict(record or {})

        return cls(
            type=(
                    payload.get("type")
                    or payload.get("topic")
                    or payload.get("event_type")
                    or ""
            ),
            data=payload.get("data", payload.get("payload")),
            priority=payload.get("priority", 5),
            sequence=payload.get("sequence", 0),
            timestamp=payload.get("timestamp", payload.get("datetime", time.time())),
            source=payload.get("source"),
            correlation_id=payload.get("correlation_id"),
            metadata=payload.get("metadata") or {},
            id=payload.get("id") or uuid4().hex,
            replayed=payload.get("replayed", False),
        )


__all__ = ["Event"]