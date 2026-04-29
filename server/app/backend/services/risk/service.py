"""Risk service interface for server-side deterministic controls."""

from __future__ import annotations

from typing import Protocol

from shared.contracts.trading import ExecutionRequest, RiskDecision


class RiskService(Protocol):
    """Server-side risk authority interface."""

    async def evaluate(self, request: ExecutionRequest) -> RiskDecision:
        ...


class InMemoryRiskService:
    """Placeholder risk service for the first migration phase."""

    async def evaluate(self, request: ExecutionRequest) -> RiskDecision:
        return RiskDecision(
            intent_id=request.client_order_id,
            approved=True,
            position_size=request.quantity,
            notes=["Skeleton risk service approved the request."],
        )

