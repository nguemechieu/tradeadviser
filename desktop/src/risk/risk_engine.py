from __future__ import annotations

"""
InvestPro RiskEngine

Central institutional risk engine enforcing pre-trade portfolio controls.

Responsibilities:
- Normalize incoming Signal / TraderDecision / ReasoningDecision-style inputs
- Enforce kill switch
- Enforce max drawdown
- Enforce daily loss limit
- Validate signal side, price, and quantity
- Compute risk-based max position size
- Resize quantity if allowed
- Enforce minimum notional
- Enforce per-symbol and gross portfolio exposure
- Apply performance controls such as loss-streak pause/reduction
- Publish risk.approved / risk.rejected / risk.alert events
"""

import inspect
import json
import logging
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

from contracts.portfolio import PortfolioSnapshot
from core.regime_engine_config import RiskConfig
from event_bus.async_event_bus import AsyncEventBus
from event_bus.event_types import EventType
from portfolio.capital_allocator import CapitalAllocationPlan
from risk.drawdown_controller import DrawdownController
from risk.exposure_manager import ExposureManager
from risk.position_sizer import PositionSizer, PositionSizingInput

try:
    from models.signal import Signal, SignalStatus
except Exception:  # pragma: no cover
    try:
        from core.models import Signal, SignalStatus
    except Exception:  # pragma: no cover
        Signal = None  # type: ignore

        class SignalStatus:  # type: ignore
            CREATED = "created"
            APPROVED = "approved"
            REJECTED = "rejected"


class PortfolioStateProvider(Protocol):
    """Protocol for providing portfolio state information."""

    @property
    def equity(self) -> float:
        ...

    @property
    def daily_loss_amount(self) -> float:
        ...

    def snapshot(self) -> PortfolioSnapshot:
        ...


@dataclass(slots=True)
class TraderDecision:
    symbol: str
    side: str
    quantity: float
    price: float
    confidence: float = 0.0
    selected_strategy: str = "unknown"
    reasoning: str = ""
    profile_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class TradeReview:
    approved: bool
    symbol: str
    side: str
    quantity: float
    price: float
    reason: str
    risk_score: float = 0.0
    stop_price: float | None = None
    take_profit: float | None = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "stop_price": self.stop_price,
            "take_profit": self.take_profit,
            "strategy_name": self.strategy_name,
            "metadata": dict(self.metadata or {}),
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
        }


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

    def __post_init__(self) -> None:
        self.max_risk_per_trade_pct = _clamp(
            self.max_risk_per_trade_pct, 0.0001, 1.0)
        self.max_portfolio_exposure_pct = max(
            0.01, float(self.max_portfolio_exposure_pct))
        self.max_drawdown_limit_pct = _clamp(
            self.max_drawdown_limit_pct, 0.001, 1.0)
        self.per_symbol_exposure_cap_pct = _clamp(
            self.per_symbol_exposure_cap_pct, 0.001, 1.0)
        self.daily_loss_limit_pct = _clamp(
            self.daily_loss_limit_pct, 0.001, 1.0)
        self.default_stop_distance_pct = max(
            0.000001, float(self.default_stop_distance_pct))
        self.min_order_notional = max(0.0, float(self.min_order_notional))
        self.quantity_step = max(0.0, float(self.quantity_step))
        self.loss_streak_pause = max(1, int(self.loss_streak_pause))
        self.loss_streak_reduce = max(1, int(self.loss_streak_reduce))
        self.performance_review_min_trades = max(
            1, int(self.performance_review_min_trades))
        self.performance_loss_rate_threshold = _clamp(
            self.performance_loss_rate_threshold, 0.0, 1.0)


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
        listen_event_type: str | None = None,
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
            max_risk_per_trade_pct=float(
                max_risk_per_trade or self.config.max_risk_per_trade),
            max_portfolio_exposure_pct=float(
                max_portfolio_exposure or self.config.max_gross_leverage),
            max_drawdown_limit_pct=float(
                max_drawdown_limit
                or daily_drawdown_limit
                or self.config.max_portfolio_drawdown
            ),
            per_symbol_exposure_cap_pct=float(
                per_symbol_exposure_cap or self.config.max_symbol_exposure_pct),
            daily_loss_limit_pct=float(
                daily_loss_limit or self.config.max_portfolio_drawdown / 2.0),
        )

        self.drawdown_controller = drawdown_controller or DrawdownController(
            self.limits.max_drawdown_limit_pct)
        self.exposure_manager = exposure_manager or ExposureManager()
        self.position_sizer = position_sizer or PositionSizer()
        self.logger = logger or logging.getLogger("RiskEngine")

        self.listen_event_type = str(
            listen_event_type or getattr(EventType, "SIGNAL", "signal"))

        self.kill_switch_reason: str | None = None
        self.starting_equity = max(1.0, float(starting_equity or 100000.0))
        self.latest_snapshot = PortfolioSnapshot(
            cash=self.starting_equity, equity=self.starting_equity)

        self._session_date = date.today()
        self._session_start_equity = self.starting_equity

        self.review_count = 0
        self.approved_count = 0
        self.rejected_count = 0
        self.last_review: TradeReview | None = None

        if self.bus is not None:
            self._subscribe_bus()

    # ------------------------------------------------------------------
    # Bus lifecycle
    # ------------------------------------------------------------------

    def _subscribe_bus(self) -> None:
        subscribe = getattr(self.bus, "subscribe", None)
        if not callable(subscribe):
            return

        try:
            subscribe(self.listen_event_type, self._on_signal)
        except Exception:
            self.logger.debug(
                "Unable to subscribe RiskEngine to signal topic", exc_info=True)

        try:
            subscribe(getattr(EventType, "PORTFOLIO_SNAPSHOT",
                      "portfolio.snapshot"), self._on_portfolio_snapshot)
        except Exception:
            self.logger.debug(
                "Unable to subscribe RiskEngine to portfolio snapshot topic", exc_info=True)

    # ------------------------------------------------------------------
    # Properties / controls
    # ------------------------------------------------------------------

    @property
    def kill_switch_active(self) -> bool:
        return bool(self.kill_switch_reason)

    @property
    def equity(self) -> float:
        return float(getattr(self.latest_snapshot, "equity", None) or self.starting_equity)

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
        self.kill_switch_reason = str(
            reason or "Risk kill switch activated").strip()

    def reset_kill_switch(self) -> None:
        self.kill_switch_reason = None

    def activate_kill_switch(self, reason: str) -> None:
        self.arm_kill_switch(reason)

    def deactivate_kill_switch(self) -> None:
        self.reset_kill_switch()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_portfolio_snapshot(self, event: Any) -> None:
        snapshot = getattr(event, "data", event)

        if snapshot is None:
            return

        if not isinstance(snapshot, PortfolioSnapshot):
            snapshot = PortfolioSnapshot(**dict(snapshot))

        self.latest_snapshot = snapshot
        self.exposure_manager.update_from_portfolio(
            getattr(snapshot, "positions", {}) or {})
        self._roll_session(getattr(snapshot, "timestamp", None),
                           float(snapshot.equity or 0.0))

        drawdown_status = self.drawdown_controller.evaluate(snapshot.equity)
        if drawdown_status.breached:
            self.arm_kill_switch("Max portfolio drawdown breached")

        if self.daily_loss_ratio() >= self.limits.daily_loss_limit_pct:
            self.arm_kill_switch("Daily loss limit breached")

    async def _on_signal(self, event: Any) -> None:
        signal = getattr(event, "data", event)

        if signal is None:
            return

        review = self.review_signal(signal)

        event_type = (
            getattr(EventType, "RISK_APPROVED", "risk.approved")
            if review.approved
            else getattr(EventType, "RISK_REJECTED", "risk.rejected")
        )
        priority = 70 if review.approved else 12

        if self.bus is not None:
            await self._publish(event_type, review, priority=priority, source="risk_engine")

        self._log(
            "risk_decision",
            approved=review.approved,
            symbol=review.symbol,
            side=review.side,
            quantity=review.quantity,
            reason=review.reason,
            risk_score=review.risk_score,
        )

        if not review.approved and self.bus is not None:
            await self._publish(
                getattr(EventType, "RISK_ALERT", "risk.alert"),
                {
                    "symbol": review.symbol,
                    "reason": review.reason,
                    "kill_switch_active": self.kill_switch_active,
                    "metadata": dict(review.metadata or {}),
                },
                priority=5,
                source="risk_engine",
            )

    async def _publish(self, event_type: Any, payload: Any, *, priority: int, source: str) -> Any:
        if self.bus is None:
            return None

        publish = getattr(self.bus, "publish", None)
        if not callable(publish):
            return None

        try:
            result = publish(event_type, payload,
                             priority=priority, source=source)
        except TypeError:
            result = publish(event_type, payload)

        if inspect.isawaitable(result):
            return await result

        return result

    # ------------------------------------------------------------------
    # Main review
    # ------------------------------------------------------------------

    def review_signal(self, signal: Any) -> TradeReview:
        self.review_count += 1

        normalized, reasoning = self._normalize_review_input(signal)
        equity = self._current_equity()

        if equity <= 0.0:
            return self._store_review(self._reject(normalized, "Account equity is unavailable"))

        if self.kill_switch_active:
            return self._store_review(
                self._reject(
                    normalized, self.kill_switch_reason or "Risk kill switch active")
            )

        drawdown_status = self.drawdown_controller.evaluate(equity)
        if drawdown_status.breached:
            self.arm_kill_switch("Max portfolio drawdown breached")
            return self._store_review(
                self._reject(
                    normalized,
                    self.kill_switch_reason or "Max portfolio drawdown breached",
                    drawdown_pct=drawdown_status.drawdown_pct,
                )
            )

        if self.daily_loss_ratio() >= self.limits.daily_loss_limit_pct:
            self.arm_kill_switch("Daily loss limit breached")
            return self._store_review(
                self._reject(
                    normalized,
                    self.kill_switch_reason or "Daily loss limit breached",
                    daily_loss_amount=self.daily_loss_amount,
                    daily_loss_ratio=self.daily_loss_ratio(),
                )
            )

        if float(getattr(reasoning, "confidence", 1.0) or 1.0) < 0.4:
            return self._store_review(self._reject(normalized, "Low confidence decision"))

        if normalized.price <= 0.0:
            return self._store_review(self._reject(normalized, "Signal price must be positive"))

        if str(normalized.side).lower() not in {"buy", "sell"}:
            return self._store_review(self._reject(normalized, "Signal side must be 'buy' or 'sell'"))

        if float(normalized.quantity or 0.0) <= 0.0:
            return self._store_review(self._reject(normalized, "Signal quantity must be positive"))

        profile_drawdown = self._profile_max_drawdown(normalized)
        if profile_drawdown > 0.0 and float(getattr(self.latest_snapshot, "drawdown_pct", 0.0) or 0.0) >= profile_drawdown:
            return self._store_review(
                self._reject(
                    normalized,
                    f"Profile drawdown limit breached: {self.latest_snapshot.drawdown_pct:.2%} >= {profile_drawdown:.2%}",
                    drawdown_pct=self.latest_snapshot.drawdown_pct,
                    profile_max_drawdown=profile_drawdown,
                )
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

        max_quantity = float(getattr(sizing, "position_size", 0.0) or 0.0)
        requested_quantity = float(normalized.quantity or 0.0)
        requested_quantity, performance_constraints = self._apply_performance_controls(
            normalized,
            requested_quantity,
        )

        if "loss_streak_pause" in performance_constraints:
            return self._store_review(
                self._reject(
                    normalized,
                    "Loss-streak pause triggered by centralized risk engine",
                    risk_constraints=performance_constraints,
                )
            )

        if requested_quantity <= 0.0:
            return self._store_review(self._reject(normalized, "Risk engine reduced the order to zero"))

        approved_quantity = requested_quantity
        resized = False

        if requested_quantity > max_quantity + 1e-12:
            if not self.limits.allow_quantity_resize:
                return self._store_review(
                    self._reject(
                        normalized,
                        "Requested quantity exceeds risk budget",
                        requested_quantity=requested_quantity,
                        max_quantity=max_quantity,
                    )
                )

            approved_quantity = max_quantity
            resized = True

        if approved_quantity <= 0.0:
            return self._store_review(self._reject(normalized, "Risk engine reduced the order to zero"))

        projected_notional = approved_quantity * normalized.price

        if projected_notional < self.limits.min_order_notional:
            return self._store_review(
                self._reject(
                    normalized,
                    "Order notional is below institutional minimum",
                    projected_notional=projected_notional,
                )
            )

        exposure_ok, exposure_reason, exposure_metrics = self.exposure_manager.evaluate_position(
            equity,
            symbol=normalized.symbol,
            proposed_notional=projected_notional,
            max_symbol_exposure_pct=self._symbol_exposure_cap(normalized),
            max_total_exposure_pct=self._gross_exposure_cap(normalized),
        )

        if not exposure_ok:
            return self._store_review(
                self._reject(normalized, exposure_reason, **exposure_metrics)
            )

        direction = 1.0 if str(normalized.side).lower() == "buy" else -1.0
        stop_price = normalized.stop_price

        if stop_price is None:
            stop_price = normalized.price - (direction * stop_distance)

        loss_per_unit = float(
            getattr(sizing, "loss_per_unit", stop_distance) or stop_distance)
        risk_amount = float(getattr(sizing, "risk_amount",
                            equity * adjusted_risk_pct) or 0.0)
        max_loss = float(approved_quantity * loss_per_unit)

        metadata = {
            **dict(normalized.metadata or {}),
            **exposure_metrics,
            "requested_quantity": requested_quantity,
            "approved_quantity": approved_quantity,
            "resized": resized,
            "stop_distance": stop_distance,
            "risk_amount": risk_amount,
            "max_loss": max_loss,
            "daily_loss_amount": self.daily_loss_amount,
            "daily_loss_ratio": self.daily_loss_ratio(),
            "drawdown_pct": drawdown_status.drawdown_pct,
            "projected_notional": projected_notional,
            "risk_constraints": performance_constraints,
            "signal_id": normalized.id,
            "signal_status": getattr(SignalStatus, "APPROVED", "approved"),
        }

        self._merge_reasoning_metadata(metadata, reasoning, adjusted_risk_pct)

        risk_score = 0.0 if equity <= 0.0 else min(1.0, max_loss / equity)
        reason = "Approved" if not resized else "Approved after quantity normalization"

        return self._store_review(
            TradeReview(
                approved=True,
                symbol=normalized.symbol,
                side=normalized.side,
                quantity=approved_quantity,
                price=normalized.price,
                reason=reason,
                risk_score=risk_score,
                stop_price=stop_price,
                take_profit=normalized.take_profit,
                strategy_name=normalized.strategy_name,
                metadata=metadata,
                timestamp=normalized.timestamp,
            )
        )

    # ------------------------------------------------------------------
    # Allocation plan review
    # ------------------------------------------------------------------

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

        max_trade_notional = equity * self.config.max_risk_per_trade / \
            max(float(plan.risk_estimate or 0.0), 1e-6)
        adjusted_notional = min(
            float(plan.target_notional or 0.0), max_trade_notional)

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

    # ------------------------------------------------------------------
    # Compatibility method for TradingCore-style simple sizing
    # ------------------------------------------------------------------

    def adjust_trade(self, price: float, amount: float) -> tuple[bool, float, str]:
        price_value = max(0.0, float(price or 0.0))
        amount_value = max(0.0, float(amount or 0.0))

        if self.kill_switch_active:
            return False, 0.0, self.kill_switch_reason or "Risk kill switch active"

        if price_value <= 0.0:
            return False, 0.0, "Invalid price"

        if amount_value <= 0.0:
            return False, 0.0, "Invalid amount"

        equity = self._current_equity()
        max_notional = equity * self.limits.max_risk_per_trade_pct / max(
            self.limits.default_stop_distance_pct,
            1e-9,
        )
        max_amount = max_notional / price_value

        if amount_value > max_amount:
            if not self.limits.allow_quantity_resize:
                return False, 0.0, "Requested amount exceeds risk budget"
            return True, max_amount, "Amount resized by risk engine"

        return True, amount_value, "Approved"

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

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
                self.exposure_manager.update_from_portfolio(
                    getattr(snapshot, "positions", {}) or {})
                self._roll_session(
                    getattr(snapshot, "timestamp", None), float(snapshot.equity or 0.0))
                return float(snapshot.equity or 0.0)

        return float(getattr(self.latest_snapshot, "equity", None) or self.starting_equity)

    def _roll_session(self, timestamp: Any, equity: float) -> None:
        session_date = self._coerce_session_date(timestamp)

        if session_date != self._session_date:
            self._session_date = session_date
            self._session_start_equity = max(
                1.0, float(equity or self.starting_equity))

    # ------------------------------------------------------------------
    # Signal normalization
    # ------------------------------------------------------------------

    def _normalize_review_input(self, value: Any) -> tuple[Any, Any | None]:
        reasoning = None
        candidate = value

        if hasattr(value, "signal") and hasattr(value, "confidence") and hasattr(value, "decision"):
            reasoning = value
            candidate = getattr(value, "signal")

        return self._coerce_signal(candidate), reasoning

    def _coerce_signal(self, value: Any) -> Any:
        if Signal is not None:
            try:
                if isinstance(value, Signal):
                    return value
            except Exception:
                pass

        if isinstance(value, TraderDecision):
            return self._build_signal(
                {
                    "symbol": value.symbol,
                    "side": value.side,
                    "quantity": value.quantity,
                    "price": value.price,
                    "confidence": value.confidence,
                    "strategy_name": value.selected_strategy,
                    "reason": value.reasoning,
                    "metadata": {**dict(value.metadata or {}), "profile_id": value.profile_id},
                    "timestamp": value.timestamp,
                }
            )

        if isinstance(value, Mapping):
            payload = dict(value or {})
            if "quantity" not in payload and "amount" in payload:
                payload["quantity"] = payload.get("amount")
            if "side" not in payload and "action" in payload:
                payload["side"] = payload.get("action")
            return self._build_signal(payload)

        payload = {
            "symbol": getattr(value, "symbol", ""),
            "side": getattr(value, "side", getattr(value, "action", "")),
            "quantity": getattr(value, "quantity", getattr(value, "amount", getattr(value, "size", 0.0))),
            "price": getattr(value, "price", 0.0),
            "confidence": getattr(value, "confidence", 0.0),
            "strategy_name": getattr(value, "strategy_name", getattr(value, "strategy", "unknown")),
            "reason": getattr(value, "reason", getattr(value, "reasoning", "")),
            "stop_price": getattr(value, "stop_price", getattr(value, "stop_loss", None)),
            "take_profit": getattr(value, "take_profit", None),
            "metadata": dict(getattr(value, "metadata", {}) or {}),
            "timestamp": getattr(value, "timestamp", datetime.now(timezone.utc)),
        }

        identifier = getattr(value, "id", None)
        status = getattr(value, "status", None)

        if identifier is not None:
            payload["id"] = identifier
        if status is not None:
            payload["status"] = status

        return self._build_signal(payload)

    def _build_signal(self, payload: Mapping[str, Any]) -> Any:
        data = dict(payload or {})

        data["symbol"] = str(data.get("symbol") or "").strip().upper()
        data["side"] = self._normalize_side(
            data.get("side") or data.get("action") or data.get("decision"))
        data["quantity"] = _safe_float(
            data.get("quantity", data.get("amount", data.get("size", 0.0))), 0.0)
        data["price"] = _safe_float(data.get("price"), 0.0)
        data["confidence"] = _clamp(_safe_float(
            data.get("confidence"), 0.0), 0.0, 1.0)
        data["strategy_name"] = str(data.get("strategy_name") or data.get(
            "strategy") or "unknown").strip() or "unknown"
        data["reason"] = str(
            data.get("reason") or data.get("note") or "").strip()
        data["metadata"] = dict(data.get("metadata") or {})
        data["timestamp"] = _coerce_datetime(data.get("timestamp"))

        if data.get("id") is None:
            data["id"] = data["metadata"].get("signal_id")

        if data.get("status") is None:
            data["status"] = getattr(SignalStatus, "CREATED", "created")

        if Signal is not None:
            try:
                return Signal(**data)
            except Exception:
                pass

        return _SimpleSignal(**data)

    @staticmethod
    def _normalize_side(value: Any) -> str:
        text = str(value or "").strip().lower()

        if text in {"buy", "long"}:
            return "buy"

        if text in {"sell", "short"}:
            return "sell"

        if text in {"hold", "wait", "neutral", "none", ""}:
            return "hold"

        return text

    # ------------------------------------------------------------------
    # Risk helper logic
    # ------------------------------------------------------------------

    def _resolve_stop_distance(self, signal: Any) -> float:
        if getattr(signal, "stop_price", None) is not None:
            return max(1e-9, abs(float(signal.price or 0.0) - float(signal.stop_price)))

        metadata = dict(getattr(signal, "metadata", {}) or {})

        for key in ("stop_distance", "atr", "volatility", "risk_estimate"):
            value = metadata.get(key)
            if value is None:
                continue

            numeric = abs(_safe_float(value, 0.0))

            if numeric > 0.0:
                if key in {"volatility", "risk_estimate"}:
                    return max(1e-9, float(signal.price or 0.0) * numeric)
                return numeric

        return max(1e-9, float(signal.price or 0.0) * self.limits.default_stop_distance_pct)

    def _profile_max_drawdown(self, signal: Any) -> float:
        metadata = dict(getattr(signal, "metadata", {}) or {})
        return max(0.0, _safe_float(metadata.get("profile_max_drawdown"), 0.0))

    def _risk_level(self, signal: Any) -> str:
        metadata = dict(getattr(signal, "metadata", {}) or {})
        return str(metadata.get("risk_level") or "medium").strip().lower() or "medium"

    def _symbol_exposure_cap(self, signal: Any) -> float:
        profile_cap = {
            "low": 0.12,
            "medium": 0.18,
            "high": 0.25,
        }.get(self._risk_level(signal), self.limits.per_symbol_exposure_cap_pct)

        return min(float(self.limits.per_symbol_exposure_cap_pct), float(profile_cap))

    def _gross_exposure_cap(self, signal: Any) -> float:
        profile_cap = {
            "low": 0.55,
            "medium": 0.80,
            "high": 1.00,
        }.get(self._risk_level(signal), self.limits.max_portfolio_exposure_pct)

        return min(float(self.limits.max_portfolio_exposure_pct), float(profile_cap))

    def _apply_performance_controls(self, signal: Any, requested_quantity: float) -> tuple[float, list[str]]:
        metadata = dict(getattr(signal, "metadata", {}) or {})
        performance_context = dict(metadata.get("performance_context") or {})

        loss_streak = max(
            int(performance_context.get("loss_streak", 0) or 0),
            int(performance_context.get("symbol_loss_streak", 0) or 0),
        )

        trades = float(performance_context.get("trades", 0.0) or 0.0)
        losses = float(performance_context.get("losses", 0.0) or 0.0)
        realized_pnl = float(performance_context.get(
            "realized_pnl", 0.0) or 0.0)

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

        confidence = max(0.0, min(1.2, _safe_float(
            getattr(reasoning, "confidence", 1.0), 1.0)))
        multiplier = max(0.3, confidence)

        if bool(getattr(reasoning, "ai_override", False)):
            multiplier *= 1.1

        conflict_penalty = getattr(reasoning, "conflict_penalty", None)
        if conflict_penalty not in (None, ""):
            multiplier *= max(0.1, _safe_float(conflict_penalty, 1.0))

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
                "decision_confidence": _safe_float(getattr(reasoning, "confidence", 0.0), 0.0),
                "market_regime": getattr(reasoning, "market_regime", None),
                "regime_confidence": getattr(reasoning, "regime_confidence", None),
                "ai_override": bool(getattr(reasoning, "ai_override", False)),
                "conflict_penalty": getattr(reasoning, "conflict_penalty", None),
                "vote_margin": getattr(reasoning, "vote_margin", None),
                "adjusted_risk_pct": adjusted_risk_pct,
            }
        )

    # ------------------------------------------------------------------
    # Review helpers
    # ------------------------------------------------------------------

    def _store_review(self, review: TradeReview) -> TradeReview:
        self.last_review = review

        if review.approved:
            self.approved_count += 1
        else:
            self.rejected_count += 1

        return review

    def _reject(self, signal: Any, reason: str, **metadata: Any) -> TradeReview:
        return TradeReview(
            approved=False,
            symbol=getattr(signal, "symbol", ""),
            side=getattr(signal, "side", ""),
            quantity=0.0,
            price=float(getattr(signal, "price", 0.0) or 0.0),
            reason=str(reason),
            strategy_name=str(
                getattr(signal, "strategy_name", "unknown") or "unknown"),
            metadata={
                **dict(getattr(signal, "metadata", {}) or {}),
                "signal_id": getattr(signal, "id", None),
                "signal_status": getattr(signal, "status", None),
                **metadata,
            },
            timestamp=getattr(signal, "timestamp", datetime.now(timezone.utc)),
        )

    # ------------------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "starting_equity": self.starting_equity,
            "session_start_equity": self._session_start_equity,
            "daily_loss_amount": self.daily_loss_amount,
            "daily_loss_ratio": self.daily_loss_ratio(),
            "kill_switch_active": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason,
            "limits": asdict(self.limits),
            "review_count": self.review_count,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "last_review": self.last_review.to_dict() if self.last_review else None,
        }

    def healthy(self) -> bool:
        return not self.kill_switch_active

    def _log(self, event_name: str, **payload: Any) -> None:
        try:
            message = json.dumps(
                {"event": event_name, **payload}, default=str, sort_keys=True)
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


@dataclass(slots=True)
class _SimpleSignal:
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    confidence: float = 0.0
    strategy_name: str = "unknown"
    reason: str = ""
    stop_price: float | None = None
    take_profit: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))
    id: Any = None
    status: Any = None


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return float(default)

    try:
        number = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if value in (None, ""):
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number) > 1e11:
            number = number / 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)

    text = str(value or "").strip()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


__all__ = [
    "PortfolioStateProvider",
    "RiskDecision",
    "RiskEngine",
    "RiskLimits",
    "TradeReview",
    "TraderDecision",
]
