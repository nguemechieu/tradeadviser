"""Execution service interface for server-side broker routing."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from shared.contracts.trading import ExecutionRequest, ExecutionResult, RiskDecision
from shared.enums.common import ExecutionStatus


class ExecutionService(Protocol):
    """Server-side execution authority interface."""

    async def submit(self, request: ExecutionRequest, risk: RiskDecision) -> ExecutionResult:
        ...


class InMemoryExecutionService:
    """Placeholder execution service for the first migration phase."""

    async def submit(self, request: ExecutionRequest, risk: RiskDecision) -> ExecutionResult:
        status = ExecutionStatus.ACCEPTED if risk.approved else ExecutionStatus.REJECTED
        return ExecutionResult(
            order_id=f"order_{uuid4().hex[:12]}",
            status=status,
            client_order_id=request.client_order_id,
            filled_quantity=0.0,
            average_fill_price=request.limit_price,
            message="Execution skeleton accepted the request." if risk.approved else "Execution skeleton rejected the request.",
        )

