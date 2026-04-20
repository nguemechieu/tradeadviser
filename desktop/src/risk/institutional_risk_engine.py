from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from sopotek.core.event_bus import AsyncEventBus
from sopotek.core.event_types import EventType
from sopotek.core.models import PortfolioSnapshot, Signal, TradeReview

from risk.exposure_manager import ExposureManager
from risk.position_sizer import PositionSizer, PositionSizingInput


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _side_multiplier(side: str) -> float:
    return 1.0 if str(side).lower() == "buy" else -1.0


class PortfolioStateProvider(Protocol):
    @property
    def equity(self) -> float:
        ...

    @property
    def daily_loss_amount(self) -> float:
        ...

    @property
    def trading_halted(self) -> bool:
        ...


@dataclass(slots=True)
class InstitutionalRiskLimits:
    max_risk_per_trade_pct: float = 0.01
    max_position_exposure_pct: float = 0.30
    max_trade_drawdown_pct: float = 0.05
    max_daily_loss_pct: float = 0.03
    default_risk_reward_ratio: float = 2.0
    default_atr_multiplier: float = 1.5
    allow_quantity_resize: bool = True
    quantity_step: float = 0.0001


@dataclass(slots=True)
class InstitutionalTradeRequest:
    symbol: str
    side: str
    entry_price: float
    requested_quantity: float
    strategy_name: str = "unknown"
    reason: str = ""
    stop_loss: float | None = None
    take_profit: float | None = None
    atr: float | None = None
    structure_price: float | None = None
    risk_reward_ratio: float = 2.0
    pip_value: float = 1.0
    contract_size: float = 1.0
    quantity_step: float = 0.0001
    allow_trailing_stop: bool = True
    allow_break_even: bool = True
    trailing_stop_distance: float | None = None
    break_even_trigger_distance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(slots=True)
class RiskValidationResult:
    approved: bool
    reason: str
    quantity: float = 0.0
    risk_amount: float = 0.0
    max_loss: float = 0.0
    stop_distance: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    projected_notional: float = 0.0
    risk_reward_ratio: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class InstitutionalRiskEngine:
    """Event-driven risk approval engine for hidden-stop institutional execution."""

    def __init__(
        self,
        event_bus: AsyncEventBus,
        *,
        exposure_manager: ExposureManager | None = None,
        position_sizer: PositionSizer | None = None,
        portfolio_monitor: PortfolioStateProvider | None = None,
        limits: InstitutionalRiskLimits | None = None,
        starting_equity: float = 100000.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.exposure_manager = exposure_manager or ExposureManager()
        self.position_sizer = position_sizer or PositionSizer()
        self.portfolio_monitor = portfolio_monitor
        self.limits = limits or InstitutionalRiskLimits()
        self.logger = logger or logging.getLogger("InstitutionalRiskEngine")
        self.latest_snapshot = PortfolioSnapshot(
            cash=float(starting_equity),
            equity=float(starting_equity),
        )

        self.bus.subscribe(EventType.SIGNAL, self._on_signal)
        self.bus.subscribe(EventType.PORTFOLIO_SNAPSHOT, self._on_portfolio_snapshot)

    def calculate_risk_amount(self, equity: float) -> float:
        return max(0.0, float(equity or 0.0)) * self.limits.max_risk_per_trade_pct

    def compute_stop_distance(
        self,
        entry_price: float,
        *,
        atr: float | None = None,
        structure: float | None = None,
        side: str = "buy",
        atr_multiplier: float | None = None,
    ) -> float:
        del side
        entry = max(0.0, float(entry_price or 0.0))
        if structure is not None:
            distance = abs(entry - float(structure))
        elif atr is not None:
            distance = max(0.0, float(atr or 0.0)) * float(atr_multiplier or self.limits.default_atr_multiplier)
        else:
            raise ValueError("Either atr or structure must be provided to compute stop distance")
        if distance <= 0.0:
            raise ValueError("Computed stop distance must be positive")
        return distance

    def compute_take_profit(
        self,
        entry_price: float,
        stop_distance: float,
        risk_reward_ratio: float,
        *,
        side: str = "buy",
    ) -> float:
        entry = float(entry_price)
        distance = abs(float(stop_distance))
        ratio = max(0.0, float(risk_reward_ratio or 0.0))
        direction = _side_multiplier(side)
        return entry + (direction * distance * ratio)

    def validate_trade(self, trade: InstitutionalTradeRequest | Signal | Mapping[str, Any]) -> RiskValidationResult:
        request = self._coerce_request(trade)
        equity = self._current_equity()
        if equity <= 0.0:
            return RiskValidationResult(approved=False, reason="Account equity is unavailable")

        if self._daily_loss_breached():
            return RiskValidationResult(
                approved=False,
                reason="Max daily loss limit breached",
                metadata={"daily_loss_amount": self._daily_loss_amount()},
            )

        if request.entry_price <= 0.0:
            return RiskValidationResult(approved=False, reason="Entry price must be positive")

        if str(request.side).lower() not in {"buy", "sell"}:
            return RiskValidationResult(approved=False, reason="Trade side must be 'buy' or 'sell'")

        try:
            stop_loss, stop_distance = self._resolve_stop(request)
        except ValueError as exc:
            return RiskValidationResult(approved=False, reason=str(exc))

        if str(request.side).lower() == "buy" and stop_loss >= request.entry_price:
            return RiskValidationResult(approved=False, reason="Long trades require stop loss below entry")
        if str(request.side).lower() == "sell" and stop_loss <= request.entry_price:
            return RiskValidationResult(approved=False, reason="Short trades require stop loss above entry")

        drawdown_pct = stop_distance / max(request.entry_price, 1e-12)
        if drawdown_pct > self.limits.max_trade_drawdown_pct + 1e-12:
            return RiskValidationResult(
                approved=False,
                reason="Per-trade drawdown exceeds limit",
                metadata={
                    "drawdown_pct": drawdown_pct,
                    "drawdown_limit_pct": self.limits.max_trade_drawdown_pct,
                },
            )

        take_profit = (
            float(request.take_profit)
            if request.take_profit is not None
            else self.compute_take_profit(
                request.entry_price,
                stop_distance,
                request.risk_reward_ratio or self.limits.default_risk_reward_ratio,
                side=request.side,
            )
        )
        risk_reward_ratio = self._derive_risk_reward_ratio(
            entry_price=request.entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            side=request.side,
        )
        if risk_reward_ratio <= 0.0:
            return RiskValidationResult(approved=False, reason="Take profit must be on the reward side of the trade")

        sizing = self.position_sizer.size_position(
            PositionSizingInput(
                equity=equity,
                risk_pct=self.limits.max_risk_per_trade_pct,
                stop_distance=stop_distance,
                pip_value=request.pip_value,
                contract_size=request.contract_size,
                quantity_step=request.quantity_step or self.limits.quantity_step,
            )
        )
        if sizing.position_size <= 0.0:
            return RiskValidationResult(approved=False, reason="Position size resolved to zero")

        approved_quantity = sizing.position_size
        resized = False
        if request.requested_quantity > 0.0:
            if request.requested_quantity <= sizing.position_size + 1e-12:
                approved_quantity = request.requested_quantity
            elif self.limits.allow_quantity_resize:
                resized = True
                approved_quantity = sizing.position_size
            else:
                return RiskValidationResult(
                    approved=False,
                    reason="Requested quantity exceeds the allowed risk budget",
                    metadata={
                        "requested_quantity": request.requested_quantity,
                        "max_quantity": sizing.position_size,
                    },
                )

        projected_notional = approved_quantity * request.entry_price * request.contract_size
        exposure_ok, exposure_reason, exposure_metrics = self.exposure_manager.evaluate_position(
            equity,
            symbol=request.symbol,
            proposed_notional=projected_notional,
            max_symbol_exposure_pct=self.limits.max_position_exposure_pct,
        )
        if not exposure_ok:
            return RiskValidationResult(
                approved=False,
                reason=exposure_reason,
                metadata=exposure_metrics,
            )

        risk_amount = min(sizing.risk_amount, approved_quantity * sizing.loss_per_unit)
        return RiskValidationResult(
            approved=True,
            reason="Approved" if not resized else "Approved after size normalization",
            quantity=approved_quantity,
            risk_amount=risk_amount,
            max_loss=approved_quantity * sizing.loss_per_unit,
            stop_distance=stop_distance,
            stop_loss=stop_loss,
            take_profit=take_profit,
            projected_notional=projected_notional,
            risk_reward_ratio=risk_reward_ratio,
            metadata={
                **dict(request.metadata or {}),
                **exposure_metrics,
                "entry_reason": request.reason,
                "signal_data": dict(request.metadata or {}),
                "requested_quantity": request.requested_quantity,
                "approved_quantity": approved_quantity,
                "resized": resized,
                "risk_amount": risk_amount,
                "max_loss": approved_quantity * sizing.loss_per_unit,
                "stop_distance": stop_distance,
                "virtual_stop_loss": stop_loss,
                "virtual_take_profit": take_profit,
                "risk_reward_ratio": risk_reward_ratio,
                "contract_size": request.contract_size,
                "pip_value": request.pip_value,
                "trailing_stop_distance": request.trailing_stop_distance or stop_distance,
                "break_even_trigger_distance": request.break_even_trigger_distance or stop_distance,
                "allow_trailing_stop": bool(request.allow_trailing_stop),
                "allow_break_even": bool(request.allow_break_even),
            },
        )

    def review_signal(self, signal: Signal | Mapping[str, Any]) -> TradeReview:
        if not isinstance(signal, Signal):
            signal = Signal(**dict(signal))
        validation = self.validate_trade(signal)
        if not validation.approved:
            return TradeReview(
                approved=False,
                symbol=signal.symbol,
                side=signal.side,
                quantity=0.0,
                price=signal.price,
                reason=validation.reason,
                strategy_name=signal.strategy_name,
                metadata={**dict(signal.metadata or {}), **validation.metadata},
                timestamp=signal.timestamp,
            )

        return TradeReview(
            approved=True,
            symbol=signal.symbol,
            side=signal.side,
            quantity=validation.quantity,
            price=signal.price,
            reason=validation.reason,
            risk_score=0.0 if self._current_equity() <= 0.0 else validation.risk_amount / self._current_equity(),
            stop_price=validation.stop_loss,
            take_profit=validation.take_profit,
            strategy_name=signal.strategy_name,
            metadata={
                **dict(signal.metadata or {}),
                **validation.metadata,
                "signal_reason": signal.reason,
                "confidence": signal.confidence,
            },
            timestamp=signal.timestamp,
        )

    async def _on_signal(self, event) -> None:
        signal = getattr(event, "data", None)
        if signal is None:
            return
        review = self.review_signal(signal)
        event_type = EventType.RISK_APPROVED if review.approved else EventType.RISK_REJECTED
        await self.bus.publish(event_type, review, priority=70 if review.approved else 10, source="institutional_risk_engine")
        if not review.approved:
            await self.bus.publish(
                EventType.RISK_ALERT,
                {
                    "symbol": review.symbol,
                    "reason": review.reason,
                    "strategy_name": review.strategy_name,
                },
                priority=5,
                source="institutional_risk_engine",
            )

    async def _on_portfolio_snapshot(self, event) -> None:
        snapshot = getattr(event, "data", None)
        if snapshot is None:
            return
        if not isinstance(snapshot, PortfolioSnapshot):
            snapshot = PortfolioSnapshot(**dict(snapshot))
        self.latest_snapshot = snapshot
        self.exposure_manager.update_from_portfolio(getattr(snapshot, "positions", {}) or {})

    def _resolve_stop(self, request: InstitutionalTradeRequest) -> tuple[float, float]:
        if request.stop_loss is not None:
            stop_loss = float(request.stop_loss)
            stop_distance = abs(float(request.entry_price) - stop_loss)
        else:
            stop_distance = self.compute_stop_distance(
                request.entry_price,
                atr=request.atr,
                structure=request.structure_price,
                side=request.side,
            )
            stop_loss = self._compute_stop_price(request.entry_price, stop_distance, request.side)

        if stop_distance <= 0.0:
            raise ValueError("A valid virtual stop loss is required")
        return stop_loss, stop_distance

    @staticmethod
    def _compute_stop_price(entry_price: float, stop_distance: float, side: str) -> float:
        direction = _side_multiplier(side)
        return float(entry_price) - (direction * abs(float(stop_distance)))

    @staticmethod
    def _derive_risk_reward_ratio(*, entry_price: float, stop_loss: float, take_profit: float, side: str) -> float:
        risk = abs(float(entry_price) - float(stop_loss))
        reward = abs(float(take_profit) - float(entry_price))
        if risk <= 0.0:
            return 0.0
        if str(side).lower() == "sell" and take_profit > entry_price:
            return 0.0
        if str(side).lower() == "buy" and take_profit < entry_price:
            return 0.0
        return reward / risk

    def _coerce_request(self, trade: InstitutionalTradeRequest | Signal | Mapping[str, Any]) -> InstitutionalTradeRequest:
        if isinstance(trade, InstitutionalTradeRequest):
            return trade
        if isinstance(trade, Signal):
            payload = dict(trade.metadata or {})
            return InstitutionalTradeRequest(
                symbol=trade.symbol,
                side=trade.side,
                entry_price=float(trade.price or 0.0),
                requested_quantity=float(trade.quantity or 0.0),
                strategy_name=trade.strategy_name,
                reason=trade.reason,
                stop_loss=trade.stop_price,
                take_profit=trade.take_profit,
                atr=self._safe_float(payload.get("atr")),
                structure_price=self._safe_float(payload.get("structure_price", payload.get("market_structure_stop"))),
                risk_reward_ratio=self._safe_float(payload.get("risk_reward_ratio"), self.limits.default_risk_reward_ratio),
                pip_value=self._safe_float(payload.get("pip_value"), 1.0),
                contract_size=self._safe_float(payload.get("contract_size"), 1.0),
                quantity_step=self._safe_float(payload.get("quantity_step"), self.limits.quantity_step),
                allow_trailing_stop=bool(payload.get("allow_trailing_stop", True)),
                allow_break_even=bool(payload.get("allow_break_even", True)),
                trailing_stop_distance=self._safe_float(payload.get("trailing_stop_distance")),
                break_even_trigger_distance=self._safe_float(payload.get("break_even_trigger_distance")),
                metadata=payload,
                timestamp=trade.timestamp,
            )

        payload = dict(trade or {})
        return InstitutionalTradeRequest(
            symbol=str(payload.get("symbol") or ""),
            side=str(payload.get("side") or ""),
            entry_price=float(payload.get("entry_price", payload.get("price", 0.0)) or 0.0),
            requested_quantity=float(payload.get("requested_quantity", payload.get("quantity", 0.0)) or 0.0),
            strategy_name=str(payload.get("strategy_name") or "unknown"),
            reason=str(payload.get("reason") or ""),
            stop_loss=self._safe_float(payload.get("stop_loss", payload.get("stop_price"))),
            take_profit=self._safe_float(payload.get("take_profit")),
            atr=self._safe_float(payload.get("atr")),
            structure_price=self._safe_float(payload.get("structure_price")),
            risk_reward_ratio=self._safe_float(payload.get("risk_reward_ratio"), self.limits.default_risk_reward_ratio),
            pip_value=self._safe_float(payload.get("pip_value"), 1.0),
            contract_size=self._safe_float(payload.get("contract_size"), 1.0),
            quantity_step=self._safe_float(payload.get("quantity_step"), self.limits.quantity_step),
            allow_trailing_stop=bool(payload.get("allow_trailing_stop", True)),
            allow_break_even=bool(payload.get("allow_break_even", True)),
            trailing_stop_distance=self._safe_float(payload.get("trailing_stop_distance")),
            break_even_trigger_distance=self._safe_float(payload.get("break_even_trigger_distance")),
            metadata=dict(payload.get("metadata") or payload),
            timestamp=payload.get("timestamp") if isinstance(payload.get("timestamp"), datetime) else _utc_now(),
        )

    def _current_equity(self) -> float:
        if self.portfolio_monitor is not None:
            return max(0.0, float(getattr(self.portfolio_monitor, "equity", 0.0) or 0.0))
        return max(0.0, float(self.latest_snapshot.equity or 0.0))

    def _daily_loss_amount(self) -> float:
        if self.portfolio_monitor is not None:
            return max(0.0, float(getattr(self.portfolio_monitor, "daily_loss_amount", 0.0) or 0.0))
        return max(0.0, float(getattr(self.latest_snapshot, "realized_pnl", 0.0) or 0.0) * -1.0)

    def _daily_loss_breached(self) -> bool:
        if self.portfolio_monitor is not None and getattr(self.portfolio_monitor, "trading_halted", False):
            return True
        equity_reference = self._current_equity()
        return self._daily_loss_amount() >= (equity_reference * self.limits.max_daily_loss_pct) and equity_reference > 0.0

    @staticmethod
    def _safe_float(value: Any, default: float | None = None) -> float | None:
        if value is None and default is None:
            return None
        try:
            return float(value)
        except Exception:
            return default
