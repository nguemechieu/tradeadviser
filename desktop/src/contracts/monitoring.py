"""Monitoring bounded-context contracts shared by desktop and server.

Monitoring services own operational alerts and health summaries. Desktop
renders these payloads; server-side monitoring and safety services emit them.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import AlertSeverity, HealthStatus


class MonitoringCommandName(str, Enum):
    ACKNOWLEDGE_ALERT_V1 = "monitoring.alert.acknowledge.v1"
    EMERGENCY_FLATTEN_V1 = "monitoring.emergency.flatten.v1"


class MonitoringEventName(str, Enum):
    ALERT_CREATED_V1 = "monitoring.alert.created.v1"
    MONITORING_SNAPSHOT_V1 = "monitoring.snapshot.v1"


class Alert(ContractModel):
    """Operational alert emitted by monitoring, risk, or execution services."""

    alert_id: str = Field(min_length=1)
    severity: AlertSeverity
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    source_component: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceHealth(ContractModel):
    """Health report for one monitored service or subsystem."""

    component: str = Field(min_length=1)
    status: HealthStatus
    checked_at: datetime = Field(default_factory=utc_now)
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PositionMonitor(ContractModel):
    """Live monitoring summary for one open position."""

    position_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    current_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    holding_duration_seconds: int = 0
    stale: bool = False


class MonitoringSnapshot(ContractModel):
    """Aggregated monitoring payload for UI, APIs, and notifications."""

    snapshot_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=utc_now)
    health: list[ServiceHealth] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    positions: list[PositionMonitor] = Field(default_factory=list)


class AcknowledgeAlertCommand(ContractModel):
    """Command payload marking an alert as acknowledged by an operator."""

    alert_id: str = Field(min_length=1)
    acknowledged_by: str = Field(min_length=1)
    acknowledged_at: datetime = Field(default_factory=utc_now)


class EmergencyFlattenCommand(ContractModel):
    """Command payload requesting an emergency flatten-all workflow."""

    account_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)

