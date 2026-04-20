"""Shared transport primitives for Sopotek desktop and server boundaries.

The shared contracts layer is the source of truth for wire-level envelopes,
correlation metadata, and transport-neutral runtime context. Domain services
own payload values; this package owns payload shape and validation rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from contracts.enums import EnvironmentName, MessageTopic, ProducerRole


PayloadT = TypeVar("PayloadT")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for message envelopes."""

    return datetime.now(timezone.utc)


def new_message_id() -> str:
    """Create a stable message identifier for commands, events, and responses."""

    return uuid4().hex


class ContractModel(BaseModel):
    """Base class for every shared contract in the desktop/server boundary.

    The shared contracts package owns validation strictness, field naming, and
    serialization behavior for transport models. Runtime services should not
    subclass ``BaseModel`` directly for cross-boundary payloads.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class CorrelationIds(ContractModel):
    """Correlation and causation identifiers owned by the message transport.

    The publisher creating a message is the source of truth for ``message_id``.
    The workflow that started the broader business action is the source of
    truth for ``correlation_id``.
    """

    message_id: str = Field(default_factory=new_message_id, min_length=1)
    correlation_id: str = Field(default_factory=new_message_id, min_length=1)
    causation_id: str | None = None


class ProducerIdentity(ContractModel):
    """Identity of the component that published a message.

    The producing runtime is the source of truth for this structure. It should
    describe the concrete desktop or server process that serialized the payload.
    """

    name: str = Field(min_length=1)
    role: ProducerRole
    instance_id: str | None = None
    version: str = Field(default="1.0.0", min_length=1)


class RuntimeContext(ContractModel):
    """Shared execution context that both desktop and server can understand.

    Desktop is the source of truth for interactive session state such as the
    active device and operator. Server is the source of truth for tenant,
    account, and policy-scoped identifiers once a request is admitted.
    """

    environment: EnvironmentName = EnvironmentName.DEVELOPMENT
    producer: ProducerIdentity
    tenant_id: str | None = None
    user_id: str | None = None
    account_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    locale: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class EnvelopeHeaders(ContractModel):
    """Versioned metadata carried by every command and event envelope.

    The shared contracts package is the source of truth for header shape and
    versioning. Producers own the concrete values.
    """

    schema_version: str = Field(default="1.0.0", min_length=1)
    ids: CorrelationIds = Field(default_factory=CorrelationIds)
    context: RuntimeContext
    topic: MessageTopic
    occurred_at: datetime = Field(default_factory=utc_now)
    partition_key: str | None = None


class EventEnvelope(ContractModel, Generic[PayloadT]):
    """Versioned event envelope for asynchronous state propagation.

    Event publishers are the source of truth for the payload, while the shared
    layer is the source of truth for the envelope itself.
    """

    headers: EnvelopeHeaders
    event_name: str = Field(min_length=1)
    payload: PayloadT


class CommandEnvelope(ContractModel, Generic[PayloadT]):
    """Versioned command envelope for intent-bearing requests.

    Command initiators are the source of truth for the desired action. Services
    consuming the command should treat the envelope contract as authoritative.
    """

    headers: EnvelopeHeaders
    command_name: str = Field(min_length=1)
    payload: PayloadT
    reply_to: str | None = None


class ErrorDetail(ContractModel):
    """Normalized error payload used in response envelopes."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ResponseEnvelope(ContractModel, Generic[PayloadT]):
    """Versioned response envelope returned by desktop and server services.

    The responding component is the source of truth for ``success`` and
    ``error``. The shared layer remains the source of truth for wire shape.
    """

    headers: EnvelopeHeaders
    response_name: str = Field(min_length=1)
    success: bool = True
    data: PayloadT | None = None
    error: ErrorDetail | None = None

