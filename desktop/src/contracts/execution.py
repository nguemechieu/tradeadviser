"""Execution bounded-context contracts shared by desktop and server.

Execution services own routing, order translation, and fill state. Desktop may
request or render these payloads but must not redefine them.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import ExecutionStatus, OrderType, TimeInForce, TradeSide, VenueKind


class ExecutionCommandName(str, Enum):
    SUBMIT_ORDER_V1 = "execution.submit.v1"
    CANCEL_ORDER_V1 = "execution.cancel.v1"
    MODIFY_ORDER_TP_V1 = "execution.modify.tp.v1"
    MODIFY_ORDER_SL_V1 = "execution.modify.sl.v1"
    ENABLE_TRAILING_STOP_V1 = "execution.trailing_stop.enable.v1"


class ExecutionEventName(str, Enum):
    ORDER_SUBMITTED_V1 = "execution.order.submitted.v1"
    ORDER_FILLED_V1 = "execution.order.filled.v1"
    ORDER_UPDATED_V1 = "execution.order.updated.v1"


class OrderLeg(ContractModel):
    """Single leg of an order or multi-leg execution plan."""

    symbol: str = Field(min_length=1)
    side: TradeSide
    quantity: float
    limit_price: float | None = None


class OrderRequest(ContractModel):
    """Broker-neutral order request produced by the execution planner."""

    client_order_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    side: TradeSide
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.GTC
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    trailing_stop_distance: float | None = None
    trailing_stop_percent: float | None = None
    reduce_only: bool = False
    post_only: bool = False
    legs: list[OrderLeg] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(ContractModel):
    """Execution-layer handoff from approval into broker routing."""

    plan_id: str = Field(min_length=1)
    order: OrderRequest
    routing_strategy: str = Field(min_length=1)
    allowed_retries: int = 0
    idempotency_key: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    notes: list[str] = Field(default_factory=list)


class FillReport(ContractModel):
    """One broker fill owned by the execution source of truth."""

    fill_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    fill_price: float
    fill_quantity: float
    fee: float = 0.0
    liquidity_flag: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class ExecutionReport(ContractModel):
    """Normalized execution state emitted by the execution service."""

    order_id: str = Field(min_length=1)
    client_order_id: str = Field(min_length=1)
    venue: VenueKind
    status: ExecutionStatus
    submitted_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    average_fill_price: float | None = None
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    slippage_bps: float | None = None
    venue_order_id: str | None = None
    fills: list[FillReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubmitOrderCommand(ContractModel):
    """Command payload requesting broker submission of an execution plan."""

    plan: ExecutionPlan


class CancelOrderCommand(ContractModel):
    """Command payload requesting cancellation of a working order."""

    order_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ModifyOrderTakeProfitCommand(ContractModel):
    """Command to modify take profit price on an active order or position."""

    order_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    new_take_profit_price: float
    reason: str | None = None


class ModifyOrderStopLossCommand(ContractModel):
    """Command to modify stop loss price on an active order or position."""

    order_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    new_stop_loss_price: float
    reason: str | None = None


class EnableTrailingStopCommand(ContractModel):
    """Command to activate a trailing stop on an active order or position."""

    order_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    trailing_stop_distance: float | None = None
    trailing_stop_percent: float | None = None
    reason: str | None = None

