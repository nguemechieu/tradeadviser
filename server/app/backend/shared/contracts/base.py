"""Common shared contracts for identifiers, envelopes, and context objects."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from sopotek.shared.enums.common import BrokerKind, SessionStatus


PayloadT = TypeVar("PayloadT")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class SharedModel(BaseModel):
    """Base class for all shared transport models.

    Shared models must remain free of Qt, broker-SDK, and ORM imports so they
    can serve as the canonical contract surface for desktop and server.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class CorrelationIds(SharedModel):
    """Canonical message correlation metadata for all commands and events."""

    correlation_id: str = Field(default_factory=lambda: uuid4().hex)
    causation_id: str | None = None
    command_id: str = Field(default_factory=lambda: uuid4().hex)
    client_order_id: str | None = None


class UserContext(SharedModel):
    """Shared user identity context used across desktop and server."""

    user_id: str
    username: str
    display_name: str | None = None
    roles: list[str] = Field(default_factory=list)


class BrokerIdentifier(SharedModel):
    """Transport-safe broker identifier and venue scope."""

    broker: BrokerKind
    account_id: str
    tenant_id: str | None = None


class SymbolIdentifier(SharedModel):
    """Canonical symbol identifier used across market and trading contexts."""

    symbol: str
    broker: BrokerKind
    market: str | None = None
    timeframe: str | None = None


class SessionContext(SharedModel):
    """Cross-boundary session context used by desktop and server."""

    session_id: str
    user: UserContext
    broker: BrokerIdentifier
    status: SessionStatus
    permissions: list[str] = Field(default_factory=list)
    correlation: CorrelationIds = Field(default_factory=CorrelationIds)
    resumable: bool = True
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentContext(SharedModel):
    """Agent execution context shared between decision, reasoning, and monitoring."""

    agent_name: str
    agent_role: str
    decision_scope: str
    correlation: CorrelationIds = Field(default_factory=CorrelationIds)


class ErrorEnvelope(SharedModel):
    """Normalized error envelope for APIs and event consumers."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False


class ApiResponseEnvelope(SharedModel, Generic[PayloadT]):
    """Standardized REST response envelope shared by desktop and server."""

    success: bool
    correlation_id: str = Field(default_factory=lambda: uuid4().hex)
    message: str = ""
    data: PayloadT | None = None
    error: ErrorEnvelope | None = None

    @classmethod
    def success_envelope(cls, *, data: PayloadT, message: str = "") -> "ApiResponseEnvelope[PayloadT]":
        return cls(success=True, message=message, data=data, error=None)

    @classmethod
    def error_envelope(cls, *, error: ErrorEnvelope) -> "ApiResponseEnvelope[PayloadT]":
        return cls(success=False, message=error.message, data=None, error=error)

