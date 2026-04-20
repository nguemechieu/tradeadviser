from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from core.config import RiskConfig
from core.event_bus import AsyncEventBus
from portfolio.capital_allocator import CapitalAllocationPlan
from risk.drawdown_controller import DrawdownController
from risk.exposure_manager import ExposureManager
from risk.position_sizer import PositionSizer, PositionSizingInput
from sopotek.core.event_types import EventType
from sopotek.core.models import PortfolioSnapshot, Signal, SignalStatus, TraderDecision, TradeReview


class PortfolioStateProvider(Protocol):
    @property
    def equity(self) -> float:
        ...

    @property
    def daily_loss_amount(self) -> float:
        ...

    def snapshot(self) -> PortfolioSnapshot:
        ...


@dataclass(slots=True)
class RiskDecision:
    approved: bool
    reason: str
    adjusted_notional: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskLimits:
    max_risk_per_trade_pct: float = 0.01
    max_portfolio_exposure_pct: float = 1.50
    max_drawdown_limit_pct: float = 0.10
    per_symbol_exposure_cap_pct: float = 0.20
    daily_loss_limit_pct: float = 0.03
    default_stop_distance_pct: float = 0.01
    min_order_notional: float = 10.0
    quantity_step: float = 0.0001
    allow_quantity_resize: bool = True
    loss_streak_pause: int = 3
    loss_streak_reduce: int = 2
    performance_review_min_trades: int = 5
    performance_loss_rate_threshold: float = 0.60


class RiskEngine:
    """Central institutional risk engine enforcing pre-trade portfolio controls."""

    def __init__(
        self,
        event_bus: AsyncEventBus | None = None,
        portfolio_engine: PortfolioStateProvider | None = None,
        *,
        config: RiskConfig | None = None,
        limits: RiskLimits | None = None,
        drawdown_controller: DrawdownController | None = None,
        exposure_manager: ExposureManager | None = None,
        position_sizer: PositionSizer | None = None,
        starting_equity: float = 100000.0,
        listen_event_type: str = EventType.SIGNAL,
        max_risk_per_trade: float | None = None,
        max_portfolio_exposure: float | None = None,
        max_drawdown_limit: float | None = None,
        daily_drawdown_limit: float | None = None,
        per_symbol_exposure_cap: float | None = None,
        daily_loss_limit: float | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.portfolio_engine = portfolio_engine
        self.config = config or RiskConfig()
        self.limits = limits or RiskLimits(
            max_risk_per_trade_pct=float(max_risk_per_trade or self.config.max_risk_per_trade),
            max_portfolio_exposure_pct=float(max_portfolio_exposure or self.config.max_gross_leverage),
            max_drawdown_limit_pct=float(
                max_drawdown_limit or daily_drawdown_limit or self.config.max_portfolio_drawdown
            ),
            per_symbol_exposure_cap_pct=float(per_symbol_exposure_cap or self.config.max_symbol_exposure_pct),
            daily_loss_limit_pct=float(daily_loss_limit or self.config.max_portfolio_drawdown / 2.0),
        )
        self.drawdown_controller = drawdown_controller or DrawdownController(self.limits.max_drawdown_limit_pct)
        self.exposure_manager = exposure_manager or ExposureManager()
        self.position_sizer = position_sizer or PositionSizer()
        self.logger = logger or logging.getLogger("RiskEngine")
        self.listen_event_type = str(listen_event_type or EventType.SIGNAL)
        self.kill_switch_reason: str | None = None
        self.starting_equity = max(1.0, float(starting_equity))
        self.latest_snapshot = PortfolioSnapshot(cash=self.starting_equity, equity=self.starting_equity)
        self._session_date = date.today()
        self._session_start_equity = self.starting_equity

        if self.bus is not None:
            self.bus.subscribe(self.listen_event_type, self._on_signal)
            self.bus.subscribe(EventType.PORTFOLIO_SNAPSHOT, self._on_portfolio_snapshot)

    @property
    def kill_switch_active(self) -> bool:
        return bool(self.kill_switch_reason)

    @property
    def equity(self) -> float:
        return float(self.latest_snapshot.equity or self.starting_equity)

    @property
    def daily_loss_amount(self) -> float:
        return max(0.0, float(self._session_start_equity) - float(self.equity))

    @property
    def trading_halted(self) -> bool:
        return self.kill_switch_active

    @property
    def max_risk_per_trade(self) -> float:
        return float(self.limits.max_risk_per_trade_pct)

    @max_risk_per_trade.setter
    def max_risk_per_trade(self, value: float) -> None:
        self.limits.max_risk_per_trade_pct = max(0.0001, float(value))

    @property
    def max_portfolio_exposure(self) -> float:
        return float(self.limits.max_portfolio_exposure_pct)

    @max_portfolio_exposure.setter
    def max_portfolio_exposure(self, value: float) -> None:
        self.limits.max_portfolio_exposure_pct = max(0.01, float(value))

    @property
    def daily_drawdown_limit(self) -> float:
        return float(self.limits.max_drawdown_limit_pct)

    @daily_drawdown_limit.setter
    def daily_drawdown_limit(self, value: float) -> None:
        self.limits.max_drawdown_limit_pct = max(0.001, float(value))

    def arm_kill_switch(self, reason: str) -> None:
        self.kill_switch_reason = str(reason or "Risk kill switch activated").strip()

    def reset_kill_switch(self) -> None:
        self.kill_switch_reason = None

    def activate_kill_switch(self, reason: str) -> None:
        self.arm_kill_switch(reason)

    def deactivate_kill_switch(self) -> None:
        self.reset_kill_switch()

    async def _on_portfolio_snapshot(self, event) -> None:
        snapshot = getattr(event, "data", None)
        if snapshot is None:
            return
        if not isinstance(snapshot, PortfolioSnapshot):
            snapshot = PortfolioSnapshot(**dict(snapshot))
        self.latest_snapshot = snapshot
        self.exposure_manager.update_from_portfolio(snapshot.positions)
        self._roll_session(snapshot.timestamp, snapshot.equity)
        drawdown_status = self.drawdown_controller.evaluate(snapshot.equity)
        if drawdown_status.breached:
            self.arm_kill_switch("Max portfolio drawdown breached")
        if self.daily_loss_ratio() >= self.limits.daily_loss_limit_pct:
            self.arm_kill_switch("Daily loss limit breached")

    async def _on_signal(self, event) -> None:
        signal = getattr(event, "data", None)
        if signal is None:
            return
        review = self.review_signal(signal)
        event_type = EventType.RISK_APPROVED if review.approved else EventType.RISK_REJECTED
        priority = 70 if review.approved else 12
        if self.bus is None:
            return
        await self.bus.publish(event_type, review, priority=priority, source="risk_engine")
        self._log(
            "risk_decision",
            approved=review.approved,
            symbol=review.symbol,
            side=review.side,
            quantity=review.quantity,
            reason=review.reason,
            risk_score=review.risk_score,
        )
        if not review.approved:
            await self.bus.publish(
                EventType.RISK_ALERT,
                {
                    "symbol": review.symbol,
                    "reason": review.reason,
                    "kill_switch_active": self.kill_switch_active,
                    "metadata": dict(review.metadata or {}),
                },
                priority=5,
                source="risk_engine",
            )

    def review_signal(self, signal: Signal | TraderDecision | Mapping[str, Any] | object) -> TradeReview:
        normalized, reasoning = self._normalize_review_input(signal)
        equity = self._current_equity()
        if equity <= 0.0:
            return self._reject(normalized, "Account equity is unavailable")
        if self.kill_switch_active:
            return self._reject(normalized, self.kill_switch_reason or "Risk kill switch active")

        drawdown_status = self.drawdown_controller.evaluate(equity)
        if drawdown_status.breached:
            self.arm_kill_switch("Max portfolio drawdown breached")
            return self._reject(
                normalized,
                self.kill_switch_reason or "Max portfolio drawdown breached",
                drawdown_pct=drawdown_status.drawdown_pct,
            )

        if self.daily_loss_ratio() >= self.limits.daily_loss_limit_pct:
            self.arm_kill_switch("Daily loss limit breached")
            return self._reject(
                normalized,
                self.kill_switch_reason or "Daily loss limit breached",
                daily_loss_amount=self.daily_loss_amount,
            )

        if float(getattr(reasoning, "confidence", 1.0) or 1.0) < 0.4:
            return self._reject(normalized, "Low confidence decision")

        if normalized.price <= 0.0:
            return self._reject(normalized, "Signal price must be positive")
        if str(normalized.side).lower() not in {"buy", "sell"}:
            return self._reject(normalized, "Signal side must be 'buy' or 'sell'")
        if float(normalized.quantity or 0.0) <= 0.0:
            return self._reject(normalized, "Signal quantity must be positive")

        profile_drawdown = self._profile_max_drawdown(normalized)
        if profile_drawdown > 0.0 and float(self.latest_snapshot.drawdown_pct or 0.0) >= profile_drawdown:
            return self._reject(
                normalized,
                f"Profile drawdown limit breached: {self.latest_snapshot.drawdown_pct:.2%} >= {profile_drawdown:.2%}",
                drawdown_pct=self.latest_snapshot.drawdown_pct,
                profile_max_drawdown=profile_drawdown,
            )

        stop_distance = self._resolve_stop_distance(normalized)
        adjusted_risk_pct = self._adjusted_risk_pct(reasoning)
        sizing = self.position_sizer.size_position(
            PositionSizingInput(
                equity=equity,
                risk_pct=adjusted_risk_pct,
                stop_distance=stop_distance,
                quantity_step=self.limits.quantity_step,
            )
        )
        max_quantity = float(sizing.position_size or 0.0)
        requested_quantity = float(normalized.quantity or 0.0)
        requested_quantity, performance_constraints = self._apply_performance_controls(normalized, requested_quantity)
        if "loss_streak_pause" in performance_constraints:
            return self._reject(
                normalized,
                "Loss-streak pause triggered by centralized risk engine",
                risk_constraints=performance_constraints,
            )
        if requested_quantity <= 0.0:
            return self._reject(normalized, "Risk engine reduced the order to zero")

        approved_quantity = requested_quantity
        resized = False
        if requested_quantity > max_quantity + 1e-12:
            if not self.limits.allow_quantity_resize:
                return self._reject(
                    normalized,
                    "Requested quantity exceeds risk budget",
                    requested_quantity=requested_quantity,
                    max_quantity=max_quantity,
                )
            approved_quantity = max_quantity
            resized = True

        if approved_quantity <= 0.0:
            return self._reject(normalized, "Risk engine reduced the order to zero")

        projected_notional = approved_quantity * normalized.price
        if projected_notional < self.limits.min_order_notional:
            return self._reject(
                normalized,
                "Order notional is below institutional minimum",
                projected_notional=projected_notional,
            )

        exposure_ok, exposure_reason, exposure_metrics = self.exposure_manager.evaluate_position(
            equity,
            symbol=normalized.symbol,
            proposed_notional=projected_notional,
            max_symbol_exposure_pct=self._symbol_exposure_cap(normalized),
            max_total_exposure_pct=self._gross_exposure_cap(normalized),
        )
        if not exposure_ok:
            return self._reject(normalized, exposure_reason, **exposure_metrics)

        direction = 1.0 if str(normalized.side).lower() == "buy" else -1.0
        stop_price = normalized.stop_price
        if stop_price is None:
            stop_price = normalized.price - (direction * stop_distance)

        metadata = {
            **dict(normalized.metadata or {}),
            **exposure_metrics,
            "requested_quantity": requested_quantity,
            "approved_quantity": approved_quantity,
            "resized": resized,
            "stop_distance": stop_distance,
            "risk_amount": float(sizing.risk_amount),
            "max_loss": float(approved_quantity * sizing.loss_per_unit),
            "daily_loss_amount": self.daily_loss_amount,
            "drawdown_pct": drawdown_status.drawdown_pct,
            "projected_notional": projected_notional,
            "risk_constraints": performance_constraints,
            "signal_id": normalized.id,
            "signal_status": SignalStatus.APPROVED,
        }
        self._merge_reasoning_metadata(metadata, reasoning, adjusted_risk_pct)
        reason = "Approved" if not resized else "Approved after quantity normalization"
        return TradeReview(
            approved=True,
            symbol=normalized.symbol,
            side=normalized.side,
            quantity=approved_quantity,
            price=normalized.price,
            reason=reason,
            risk_score=0.0 if equity <= 0.0 else min(1.0, (approved_quantity * sizing.loss_per_unit) / equity),
            stop_price=stop_price,
            take_profit=normalized.take_profit,
            strategy_name=normalized.strategy_name,
            metadata=metadata,
            timestamp=normalized.timestamp,
        )

    def review(
        self,
        plan: CapitalAllocationPlan,
        *,
        account_equity: float,
        gross_exposure: float = 0.0,
        realized_volatility: float = 0.0,
        symbol_exposure: float = 0.0,
    ) -> RiskDecision:
        equity = max(0.0, float(account_equity or 0.0))
        if equity <= 0.0:
            return RiskDecision(False, "Account equity is zero.", 0.0, {})
        if self.kill_switch_active:
            return RiskDecision(False, self.kill_switch_reason or "Kill switch active.", 0.0, {})

        drawdown_status = self.drawdown_controller.evaluate(equity)
        if drawdown_status.breached:
            self.arm_kill_switch("Max portfolio drawdown breached.")
            return RiskDecision(
                False,
                self.kill_switch_reason or "Max portfolio drawdown breached.",
                0.0,
                {"drawdown": drawdown_status.drawdown_pct},
            )

        if float(realized_volatility or 0.0) >= self.config.abnormal_volatility_threshold:
            self.arm_kill_switch("Abnormal volatility kill switch triggered.")
            return RiskDecision(
                False,
                self.kill_switch_reason or "Abnormal volatility kill switch triggered.",
                0.0,
                {"realized_volatility": realized_volatility},
            )

        max_trade_notional = equity * self.config.max_risk_per_trade / max(float(plan.risk_estimate or 0.0), 1e-6)
        adjusted_notional = min(float(plan.target_notional or 0.0), max_trade_notional)
        projected_symbol = symbol_exposure + adjusted_notional
        if projected_symbol / equity > self.config.max_symbol_exposure_pct:
            return RiskDecision(
                False,
                "Max symbol exposure would be breached.",
                0.0,
                {"projected_symbol_exposure_pct": projected_symbol / equity},
            )
        projected_gross = gross_exposure + adjusted_notional
        if projected_gross / equity > self.config.max_gross_leverage:
            return RiskDecision(
                False,
                "Max leverage would be breached.",
                0.0,
                {"projected_gross_leverage": projected_gross / equity},
            )
        if adjusted_notional <= 0.0:
            return RiskDecision(False, "Risk engine scaled the order to zero.", 0.0, {})
        return RiskDecision(
            True,
            "Approved by institutional risk engine.",
            adjusted_notional,
            {
                "drawdown_pct": drawdown_status.drawdown_pct,
                "max_trade_notional": max_trade_notional,
                "projected_gross_leverage": projected_gross / equity,
            },
        )

    def daily_loss_ratio(self) -> float:
        baseline = max(1.0, float(self._session_start_equity))
        return self.daily_loss_amount / baseline

    def _current_equity(self) -> float:
        if self.portfolio_engine is not None:
            try:
                snapshot = self.portfolio_engine.snapshot()
            except Exception:
                snapshot = None
            if snapshot is not None:
                self.latest_snapshot = snapshot
                self.exposure_manager.update_from_portfolio(snapshot.positions)
                self._roll_session(snapshot.timestamp, snapshot.equity)
                return float(snapshot.equity or 0.0)
        return float(self.latest_snapshot.equity or self.starting_equity)

    def _roll_session(self, timestamp: Any, equity: float) -> None:
        session_date = self._coerce_session_date(timestamp)
        if session_date != self._session_date:
            self._session_date = session_date
            self._session_start_equity = max(1.0, float(equity or self.starting_equity))

    def _resolve_stop_distance(self, signal: Signal) -> float:
        if signal.stop_price is not None:
            return max(1e-9, abs(float(signal.price or 0.0) - float(signal.stop_price)))
        metadata = dict(signal.metadata or {})
        for key in ("stop_distance", "atr", "volatility", "risk_estimate"):
            value = metadata.get(key)
            if value is None:
                continue
            numeric = abs(float(value or 0.0))
            if numeric > 0.0:
                if key in {"volatility", "risk_estimate"}:
                    return max(1e-9, float(signal.price or 0.0) * numeric)
                return numeric
        return max(1e-9, float(signal.price or 0.0) * self.limits.default_stop_distance_pct)

    def _normalize_review_input(self, value: Signal | TraderDecision | Mapping[str, Any] | object) -> tuple[Signal, Any | None]:
        reasoning = None
        candidate = value
        if hasattr(value, "signal") and hasattr(value, "confidence") and hasattr(value, "decision"):
            reasoning = value
            candidate = getattr(value, "signal")
        return self._coerce_signal(candidate), reasoning

    def _coerce_signal(self, value: Signal | TraderDecision | Mapping[str, Any] | object) -> Signal:
        if isinstance(value, Signal):
            return value
        if isinstance(value, TraderDecision):
            return Signal(
                symbol=value.symbol,
                side=value.side,
                quantity=value.quantity,
                price=value.price,
                confidence=value.confidence,
                strategy_name=value.selected_strategy,
                reason=value.reasoning,
                metadata={**dict(value.metadata or {}), "profile_id": value.profile_id},
                timestamp=value.timestamp,
            )
        if isinstance(value, Mapping):
            return Signal(**dict(value or {}))

        payload = {
            "symbol": getattr(value, "symbol", ""),
            "side": getattr(value, "side", getattr(value, "action", "")),
            "quantity": getattr(value, "quantity", getattr(value, "size", 0.0)),
            "price": getattr(value, "price", 0.0),
            "confidence": getattr(value, "confidence", 0.0),
            "strategy_name": getattr(value, "strategy_name", getattr(value, "strategy", "unknown")),
            "reason": getattr(value, "reason", getattr(value, "reasoning", "")),
            "stop_price": getattr(value, "stop_price", getattr(value, "stop_loss", None)),
            "take_profit": getattr(value, "take_profit", None),
            "metadata": dict(getattr(value, "metadata", {}) or {}),
            "timestamp": getattr(value, "timestamp", datetime.utcnow()),
        }
        identifier = getattr(value, "id", None)
        status = getattr(value, "status", None)
        if identifier is not None:
            payload["id"] = identifier
        if status is not None:
            payload["status"] = status
        return Signal(**payload)

    def _profile_max_drawdown(self, signal: Signal) -> float:
        metadata = dict(signal.metadata or {})
        return max(0.0, float(metadata.get("profile_max_drawdown") or 0.0))

    def _risk_level(self, signal: Signal) -> str:
        metadata = dict(signal.metadata or {})
        return str(metadata.get("risk_level") or "medium").strip().lower() or "medium"

    def _symbol_exposure_cap(self, signal: Signal) -> float:
        profile_cap = {
            "low": 0.12,
            "medium": 0.18,
            "high": 0.25,
        }.get(self._risk_level(signal), self.limits.per_symbol_exposure_cap_pct)
        return min(float(self.limits.per_symbol_exposure_cap_pct), float(profile_cap))

    def _gross_exposure_cap(self, signal: Signal) -> float:
        profile_cap = {
            "low": 0.55,
            "medium": 0.80,
            "high": 1.00,
        }.get(self._risk_level(signal), self.limits.max_portfolio_exposure_pct)
        return min(float(self.limits.max_portfolio_exposure_pct), float(profile_cap))

    def _apply_performance_controls(self, signal: Signal, requested_quantity: float) -> tuple[float, list[str]]:
        metadata = dict(signal.metadata or {})
        performance_context = dict(metadata.get("performance_context") or {})
        loss_streak = max(
            int(performance_context.get("loss_streak", 0) or 0),
            int(performance_context.get("symbol_loss_streak", 0) or 0),
        )
        trades = float(performance_context.get("trades", 0.0) or 0.0)
        losses = float(performance_context.get("losses", 0.0) or 0.0)
        realized_pnl = float(performance_context.get("realized_pnl", 0.0) or 0.0)
        constraints: list[str] = []

        if loss_streak >= self.limits.loss_streak_pause:
            return 0.0, ["loss_streak_pause"]
        if loss_streak >= self.limits.loss_streak_reduce:
            requested_quantity *= 0.5
            constraints.append("loss_streak_reduce")
        if (
            trades >= float(self.limits.performance_review_min_trades)
            and realized_pnl < 0.0
            and losses / max(trades, 1.0) >= float(self.limits.performance_loss_rate_threshold)
        ):
            requested_quantity *= 0.75
            constraints.append("performance_reduce")
        return max(0.0, requested_quantity), constraints

    def _adjusted_risk_pct(self, reasoning: Any | None) -> float:
        if reasoning is None:
            return float(self.limits.max_risk_per_trade_pct)

        confidence = max(0.0, min(1.2, float(getattr(reasoning, "confidence", 1.0) or 1.0)))
        multiplier = max(0.3, confidence)
        if bool(getattr(reasoning, "ai_override", False)):
            multiplier *= 1.1
        conflict_penalty = getattr(reasoning, "conflict_penalty", None)
        if conflict_penalty not in (None, ""):
            multiplier *= max(0.1, float(conflict_penalty))
        regime = str(getattr(reasoning, "market_regime", "") or "").upper()
        if regime == "RANGING":
            multiplier *= 0.5
        elif regime == "VOLATILE":
            multiplier *= 0.7
        return max(0.0001, float(self.limits.max_risk_per_trade_pct) * multiplier)

    def _merge_reasoning_metadata(self, metadata: dict[str, Any], reasoning: Any | None, adjusted_risk_pct: float) -> None:
        if reasoning is None:
            return
        metadata.update(
            {
                "decision_confidence": float(getattr(reasoning, "confidence", 0.0) or 0.0),
                "market_regime": getattr(reasoning, "market_regime", None),
                "regime_confidence": getattr(reasoning, "regime_confidence", None),
                "ai_override": bool(getattr(reasoning, "ai_override", False)),
                "conflict_penalty": getattr(reasoning, "conflict_penalty", None),
                "vote_margin": getattr(reasoning, "vote_margin", None),
                "adjusted_risk_pct": adjusted_risk_pct,
            }
        )

    def _reject(self, signal: Signal, reason: str, **metadata: Any) -> TradeReview:
        return TradeReview(
            approved=False,
            symbol=signal.symbol,
            side=signal.side,
            quantity=0.0,
            price=signal.price,
            reason=str(reason),
            strategy_name=signal.strategy_name,
            metadata={**dict(signal.metadata or {}), "signal_id": signal.id, "signal_status": signal.status, **metadata},
            timestamp=signal.timestamp,
        )

    def _log(self, event_name: str, **payload: Any) -> None:
        try:
            message = json.dumps({"event": event_name, **payload}, default=str, sort_keys=True)
        except Exception:
            message = f"{event_name} {payload}"
        self.logger.info(message)

    @staticmethod
    def _coerce_session_date(timestamp: Any) -> date:
        if isinstance(timestamp, datetime):
            return timestamp.date()
        if hasattr(timestamp, "date"):
            try:
                return timestamp.date()
            except Exception:
                pass
        text = str(timestamp or "").strip()
        if text:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
            except ValueError:
                pass
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                pass
        return date.today()


__all__ = ["RiskDecision", "RiskEngine", "RiskLimits"]
