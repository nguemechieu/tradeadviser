"""Shared session and identity contracts for Sopotek."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from sopotek.shared.contracts.base import SharedModel, UserContext, utc_now
from sopotek.shared.enums.common import BrokerKind, SessionStatus


class BrokerSessionSummary(SharedModel):
    """Authoritative broker session summary supplied by the server."""

    user_id: str
    account_id: str
    broker: BrokerKind
    permissions: list[str] = Field(default_factory=list)


class SessionState(SharedModel):
    """Server-authoritative session state consumed by the desktop client."""

    session_id: str
    status: SessionStatus
    user: BrokerSessionSummary
    access_token: str | None = None
    refresh_token: str | None = None
    heartbeat_interval_seconds: int = 15
    resumable: bool = True
    last_heartbeat_at: datetime = Field(default_factory=utc_now)


class LoginRequest(SharedModel):
    """Desktop-originated login request."""

    username: str
    password: str


class SessionResumeRequest(SharedModel):
    """Desktop request to resume an existing authoritative session."""

    session_id: str
