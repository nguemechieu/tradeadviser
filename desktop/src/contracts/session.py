"""Session bounded-context contracts shared by desktop and server.

Desktop owns interactive device state. Server owns admitted account/session
state after authentication and policy checks.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import AuthMethod, SessionMode, SessionRole, SessionState, VenueKind


class SessionCommandName(str, Enum):
    START_SESSION_V1 = "session.start.v1"
    STOP_SESSION_V1 = "session.stop.v1"
    REFRESH_SESSION_V1 = "session.refresh.v1"


class SessionEventName(str, Enum):
    SESSION_STARTED_V1 = "session.started.v1"
    SESSION_HEARTBEAT_V1 = "session.heartbeat.v1"
    SESSION_CLOSED_V1 = "session.closed.v1"


class UserIdentity(ContractModel):
    """Canonical user identity payload used outside persistence layers."""

    user_id: str = Field(min_length=1)
    email: str | None = None
    display_name: str | None = None
    roles: list[SessionRole] = Field(default_factory=list)
    tenant_id: str | None = None


class DeviceContext(ContractModel):
    """Desktop-owned device metadata for a trading session."""

    device_id: str = Field(min_length=1)
    hostname: str | None = None
    ip_address: str | None = None
    locale: str | None = None
    app_version: str | None = None


class BrokerSessionRef(ContractModel):
    """Transport-safe broker/session reference without any SDK dependency."""

    connection_id: str = Field(min_length=1)
    venue: VenueKind
    account_id: str = Field(min_length=1)
    mode: SessionMode


class SessionSnapshot(ContractModel):
    """Server-admitted session snapshot shared with desktop observers."""

    session_id: str = Field(min_length=1)
    state: SessionState
    mode: SessionMode
    user: UserIdentity
    device: DeviceContext
    broker_session: BrokerSessionRef | None = None
    auth_method: AuthMethod = AuthMethod.PASSWORD
    started_at: datetime = Field(default_factory=utc_now)
    last_heartbeat_at: datetime = Field(default_factory=utc_now)
    entitlements: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SessionHeartbeat(ContractModel):
    """Lightweight heartbeat emitted by the session owner."""

    session_id: str = Field(min_length=1)
    state: SessionState
    sent_at: datetime = Field(default_factory=utc_now)
    latency_ms: float = 0.0
    open_positions: int = 0
    open_orders: int = 0


class StartSessionCommand(ContractModel):
    """Desktop-originated request to open or resume a trading session."""

    user_id: str = Field(min_length=1)
    requested_mode: SessionMode
    account_id: str = Field(min_length=1)
    venue: VenueKind
    device: DeviceContext


class StopSessionCommand(ContractModel):
    """Request to close a trading session cleanly."""

    session_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RefreshSessionCommand(ContractModel):
    """Request for the latest authoritative session snapshot."""

    session_id: str = Field(min_length=1)

