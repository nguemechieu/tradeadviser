from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PositionSizingInput:
    equity: float
    risk_pct: float
    stop_distance: float
    pip_value: float = 1.0
    contract_size: float = 1.0
    quantity_step: float = 0.0001
    min_quantity: float = 0.0
    max_quantity: float | None = None


@dataclass(slots=True)
class PositionSizingResult:
    position_size: float
    risk_amount: float
    max_loss: float
    loss_per_unit: float


class PositionSizer:
    """Institutional position sizer that caps max loss at the configured risk budget."""

    def size_position(self, request: PositionSizingInput) -> PositionSizingResult:
        stop_distance = max(0.0, float(request.stop_distance or 0.0))
        if stop_distance <= 0.0:
            raise ValueError("stop_distance must be positive")

        equity = max(0.0, float(request.equity or 0.0))
        risk_pct = max(0.0, float(request.risk_pct or 0.0))
        risk_amount = equity * risk_pct
        pip_value = max(1e-12, float(request.pip_value or 1.0))
        contract_size = max(1e-12, float(request.contract_size or 1.0))
        loss_per_unit = stop_distance * pip_value * contract_size
        raw_quantity = 0.0 if loss_per_unit <= 0.0 else risk_amount / loss_per_unit

        quantity = self._round_down(raw_quantity, float(request.quantity_step or 0.0))
        quantity = max(float(request.min_quantity or 0.0), quantity)
        if request.max_quantity is not None:
            quantity = min(quantity, float(request.max_quantity))

        max_loss = quantity * loss_per_unit
        if max_loss > risk_amount + 1e-9:
            quantity = self._round_down(risk_amount / loss_per_unit, float(request.quantity_step or 0.0))
            quantity = max(0.0, quantity)
            max_loss = quantity * loss_per_unit

        return PositionSizingResult(
            position_size=quantity,
            risk_amount=risk_amount,
            max_loss=max_loss,
            loss_per_unit=loss_per_unit,
        )

    def calculate_position_size(
        self,
        *,
        equity: float,
        risk_pct: float,
        stop_distance: float,
        pip_value: float = 1.0,
        contract_size: float = 1.0,
        quantity_step: float = 0.0001,
        min_quantity: float = 0.0,
        max_quantity: float | None = None,
    ) -> PositionSizingResult:
        return self.size_position(
            PositionSizingInput(
                equity=equity,
                risk_pct=risk_pct,
                stop_distance=stop_distance,
                pip_value=pip_value,
                contract_size=contract_size,
                quantity_step=quantity_step,
                min_quantity=min_quantity,
                max_quantity=max_quantity,
            )
        )

    @staticmethod
    def _round_down(value: float, step: float) -> float:
        numeric = max(0.0, float(value or 0.0))
        normalized_step = float(step or 0.0)
        if normalized_step <= 0.0:
            return numeric
        return (numeric // normalized_step) * normalized_step
