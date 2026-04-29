"""Shared desktop command contracts for the hybrid Sopotek architecture."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from shared.contracts.base import CorrelationIds, SessionContext, SharedModel, utc_now
from shared.contracts.trading import ExecutionRequest
from shared.enums.common import ReportKind


class UICommand(SharedModel):
    """Thin desktop-originated command envelope.

    Desktop owns the creation of UI commands. Server owns the authoritative
    execution of those commands once accepted.
    """

    command_type: str
    session_id: str
    account_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation: CorrelationIds = Field(default_factory=CorrelationIds)
    issued_at: datetime = Field(default_factory=utc_now)
    operator_note: str | None = None


class ConnectBrokerCommand(SharedModel):
    """Command requesting a server-side broker session bind."""

    session_context: SessionContext
    broker_secret_ref: str | None = None


class RequestMarketDataSubscriptionCommand(SharedModel):
    """Command requesting authoritative market-watch subscriptions."""

    session_id: str
    symbols: list[str] = Field(default_factory=list)
    timeframe: str | None = None
    include_candles: bool = True
    include_quotes: bool = True


class PlaceOrderCommand(SharedModel):
    """Command requesting a server-authoritative order placement."""

    execution_request: ExecutionRequest


class CancelOrderCommand(SharedModel):
    """Command requesting cancellation of a working order."""

    order_id: str
    session_id: str


class ClosePositionCommand(SharedModel):
    """Command requesting closure of an existing position."""

    position_id: str
    session_id: str


class ToggleStrategyCommand(SharedModel):
    """Command enabling or disabling one strategy for an account or symbol."""

    session_id: str
    strategy_name: str
    enabled: bool


class SetAutomationStateCommand(SharedModel):
    """Command arming or disarming automated trading."""

    session_id: str
    enabled: bool
    reason: str | None = None


class RequestReportCommand(SharedModel):
    """Command requesting asynchronous report generation."""

    session_id: str
    report_kind: ReportKind


class TriggerKillSwitchCommand(SharedModel):
    """Command requesting activation of the global kill switch."""

    session_id: str
    reason: str
