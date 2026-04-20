"""Reporting bounded-context contracts shared by desktop and server.

Reporting services own summaries and notification payloads that need to move
between the trading runtime, dashboards, and external channels.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import ReportKind


class ReportingCommandName(str, Enum):
    GENERATE_REPORT_V1 = "reporting.generate.v1"
    DISPATCH_NOTIFICATION_V1 = "reporting.notification.dispatch.v1"


class ReportingEventName(str, Enum):
    REPORT_GENERATED_V1 = "reporting.report.generated.v1"
    NOTIFICATION_DISPATCHED_V1 = "reporting.notification.dispatched.v1"


class ReportSection(ContractModel):
    """One report section owned by the reporting source of truth."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    metrics: dict[str, float] = Field(default_factory=dict)
    items: list[str] = Field(default_factory=list)


class ReportArtifact(ContractModel):
    """Reference to a rendered report artifact such as JSON, PDF, or HTML."""

    artifact_id: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    checksum: str | None = None


class NotificationMessage(ContractModel):
    """Channel-neutral notification payload for reporting and alerting."""

    notification_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    recipients: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportSummary(ContractModel):
    """High-level report payload shared with desktop, APIs, and bots."""

    report_id: str = Field(min_length=1)
    kind: ReportKind
    title: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=utc_now)
    highlights: list[str] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    artifacts: list[ReportArtifact] = Field(default_factory=list)


class ReportingSnapshot(ContractModel):
    """Combined reporting and notification view for a session or account."""

    summary: ReportSummary
    notifications: list[NotificationMessage] = Field(default_factory=list)


class GenerateReportCommand(ContractModel):
    """Command payload requesting generation of a report."""

    kind: ReportKind
    account_id: str = Field(min_length=1)
    session_id: str | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None


class DispatchNotificationCommand(ContractModel):
    """Command payload requesting notification delivery."""

    message: NotificationMessage

