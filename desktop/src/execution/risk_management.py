"""
Risk management utilities for modifying TP/SL and trailing stops on active
positions and orders.

This module is designed for InvestPro / TradeAdviser-style trading systems.

Main responsibilities:
- Validate stop-loss prices.
- Validate take-profit prices.
- Validate trailing stop settings.
- Modify live broker position/order risk parameters.
- Safely update local PositionSnapshot objects.
- Support both async and sync broker methods.
- Avoid hardcoded position side assumptions.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Protocol, runtime_checkable


try:
    from contracts.execution import (
        ModifyOrderStopLossCommand,
        ModifyOrderTakeProfitCommand,
        EnableTrailingStopCommand as ExecutionEnableTrailingStopCommand,
    )
except Exception:  # pragma: no cover
    ModifyOrderStopLossCommand = Any  # type: ignore
    ModifyOrderTakeProfitCommand = Any  # type: ignore
    ExecutionEnableTrailingStopCommand = Any  # type: ignore


try:
    from contracts.portfolio import (
        ModifyPositionStopLossCommand,
        ModifyPositionTakeProfitCommand,
        EnableTrailingStopCommand as PortfolioEnableTrailingStopCommand,
        PositionSnapshot,
    )
except Exception:  # pragma: no cover
    ModifyPositionStopLossCommand = Any  # type: ignore
    ModifyPositionTakeProfitCommand = Any  # type: ignore
    PortfolioEnableTrailingStopCommand = Any  # type: ignore
    PositionSnapshot = Any  # type: ignore


Side = str

LONG_SIDES = {"buy", "long", "bull", "bullish"}
SHORT_SIDES = {"sell", "short", "bear", "bearish"}

DEFAULT_MIN_DISTANCE_PERCENT = 0.10
DEFAULT_MAX_WARNING_DISTANCE_PERCENT = 50.0


@dataclass(slots=True)
class RiskActionResult:
    """Standard result returned by risk-management operations."""

    success: bool
    message: str
    action: str
    symbol: Optional[str] = None
    position_id: Optional[str] = None
    order_id: Optional[str] = None
    new_stop_loss: Optional[float] = None
    new_take_profit: Optional[float] = None
    trailing_stop_distance: Optional[float] = None
    trailing_stop_percent: Optional[float] = None
    broker_result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": bool(self.success),
            "message": str(self.message or ""),
            "action": str(self.action or ""),
            "symbol": self.symbol,
            "position_id": self.position_id,
            "order_id": self.order_id,
            "new_stop_loss": self.new_stop_loss,
            "new_take_profit": self.new_take_profit,
            "trailing_stop_distance": self.trailing_stop_distance,
            "trailing_stop_percent": self.trailing_stop_percent,
            "broker_result": self.broker_result,
            "metadata": dict(self.metadata or {}),
        }


@runtime_checkable
class RiskBrokerProtocol(Protocol):
    """Optional broker method contract.

    Your actual broker does not need to inherit this. The engine checks methods
    dynamically with hasattr, but this protocol documents expected broker methods.
    """

    async def modify_stop_loss(self, **kwargs: Any) -> Any:
        ...

    async def modify_take_profit(self, **kwargs: Any) -> Any:
        ...

    async def enable_trailing_stop(self, **kwargs: Any) -> Any:
        ...

    async def modify_order_stop_loss(self, **kwargs: Any) -> Any:
        ...

    async def modify_order_take_profit(self, **kwargs: Any) -> Any:
        ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_float(value: Any, *, default: Optional[float] = None) -> Optional[float]:
    """Safely convert numeric values to float."""
    if value is None or value == "":
        return default

    try:
        number = float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return default

    if number != number:
        return default

    if number in {float("inf"), float("-inf")}:
        return default

    return number


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_id(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _normalize_side(side: Any) -> str:
    """Normalize side text into long/short/unknown."""
    text = str(side or "").strip().lower()

    if text in LONG_SIDES:
        return "long"

    if text in SHORT_SIDES:
        return "short"

    return "unknown"


def _distance_percent(current_price: float, target_price: float) -> float:
    if current_price <= 0:
        return 0.0
    return abs(target_price - current_price) / current_price * 100.0


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first available attribute or mapping key."""
    if obj is None:
        return default

    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)

        if hasattr(obj, name):
            return getattr(obj, name)

    return default


def _replace_position_snapshot(position: Any, **updates: Any) -> Any:
    """Replace fields on PositionSnapshot safely.

    Works with:
    - dataclasses
    - pydantic v2 models with model_copy
    - pydantic v1 models with copy
    - dict snapshots
    - plain objects as fallback
    """
    if position is None:
        return None

    if isinstance(position, dict):
        snapshot = dict(position)
        snapshot.update(updates)
        return snapshot

    if hasattr(position, "model_copy"):
        try:
            return position.model_copy(update=updates)
        except Exception:
            pass

    if hasattr(position, "copy"):
        try:
            return position.copy(update=updates)
        except TypeError:
            pass
        except Exception:
            pass

    try:
        from dataclasses import is_dataclass, replace

        if is_dataclass(position):
            return replace(position, **updates)
    except Exception:
        pass

    field_names = [
        "position_id",
        "symbol",
        "venue",
        "exchange",
        "side",
        "position_side",
        "quantity",
        "qty",
        "size",
        "average_price",
        "entry_price",
        "last_price",
        "current_price",
        "realized_pnl",
        "unrealized_pnl",
        "exposure_pct",
        "stop_loss",
        "take_profit",
        "trailing_stop_enabled",
        "trailing_stop_distance",
        "trailing_stop_percent",
        "opened_at",
        "updated_at",
        "metadata",
    ]

    values = {name: getattr(position, name, None) for name in field_names if hasattr(position, name)}
    values.update(updates)

    try:
        return PositionSnapshot(**values)
    except Exception:
        for key, value in updates.items():
            try:
                setattr(position, key, value)
            except Exception:
                pass
        return position


class RiskManagementEngine:
    """Engine for managing TP/SL and trailing stops.

    Broker methods may be async or sync.

    Supported broker methods:
    - modify_stop_loss(...)
    - modify_take_profit(...)
    - enable_trailing_stop(...)
    - modify_order_stop_loss(...)
    - modify_order_take_profit(...)
    """

    def __init__(
            self,
            broker: Optional[Any] = None,
            logger: Optional[logging.Logger] = None,
            *,
            min_distance_percent: float = DEFAULT_MIN_DISTANCE_PERCENT,
            max_warning_distance_percent: float = DEFAULT_MAX_WARNING_DISTANCE_PERCENT,
    ) -> None:
        self.broker = broker
        self.logger = logger or logging.getLogger(__name__)
        self.min_distance_percent = max(0.0, float(min_distance_percent))
        self.max_warning_distance_percent = max(
            self.min_distance_percent,
            float(max_warning_distance_percent),
        )

    def set_broker(self, broker: Any) -> None:
        self.broker = broker

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _call_broker_method(
            self,
            method_name: str,
            *,
            fallback_method_names: tuple[str, ...] = (),
            **kwargs: Any,
    ) -> Any:
        """Call broker method safely, supporting sync and async brokers."""
        if self.broker is None:
            raise RuntimeError("Broker not initialized")

        candidate_names = (method_name, *fallback_method_names)

        last_error: Exception | None = None

        for name in candidate_names:
            method = getattr(self.broker, name, None)
            if method is None or not callable(method):
                continue

            try:
                return await self._maybe_await(method(**kwargs))
            except TypeError as exc:
                last_error = exc

                # Fallback for brokers that expect a single payload dictionary.
                try:
                    return await self._maybe_await(method(dict(kwargs)))
                except TypeError as inner_exc:
                    last_error = inner_exc
                    continue

        if last_error is not None:
            raise last_error

        raise NotImplementedError(
            f"Broker does not support any of: {', '.join(candidate_names)}"
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_side(self, side: Any) -> tuple[bool, str, str]:
        normalized_side = _normalize_side(side)

        if normalized_side == "unknown":
            return False, f"Unknown position side: {side!r}", normalized_side

        return True, "", normalized_side

    def validate_stop_loss(
            self,
            current_price: float,
            stop_loss_price: float,
            side: Side,
            *,
            min_distance_percent: Optional[float] = None,
    ) -> tuple[bool, str]:
        current_price = _to_float(current_price, default=-1.0) or -1.0
        stop_loss_price = _to_float(stop_loss_price, default=-1.0) or -1.0
        min_pct = (
            self.min_distance_percent
            if min_distance_percent is None
            else max(0.0, float(min_distance_percent))
        )

        if current_price <= 0 or stop_loss_price <= 0:
            return False, "Current price and stop loss must be positive numbers"

        side_valid, reason, normalized_side = self.validate_side(side)
        if not side_valid:
            return False, reason

        distance_pct = _distance_percent(current_price, stop_loss_price)

        if normalized_side == "long":
            if stop_loss_price >= current_price:
                return False, "Stop loss must be below current price for long positions"
            if distance_pct < min_pct:
                return False, f"Stop loss too close: {distance_pct:.3f}% below current price"

        if normalized_side == "short":
            if stop_loss_price <= current_price:
                return False, "Stop loss must be above current price for short positions"
            if distance_pct < min_pct:
                return False, f"Stop loss too close: {distance_pct:.3f}% above current price"

        if distance_pct > self.max_warning_distance_percent:
            self.logger.warning(
                "Stop loss is very far from current price: %.3f%% current=%s stop_loss=%s side=%s",
                distance_pct,
                current_price,
                stop_loss_price,
                normalized_side,
            )

        return True, ""

    def validate_take_profit(
            self,
            current_price: float,
            take_profit_price: float,
            side: Side,
            *,
            min_distance_percent: Optional[float] = None,
    ) -> tuple[bool, str]:
        current_price = _to_float(current_price, default=-1.0) or -1.0
        take_profit_price = _to_float(take_profit_price, default=-1.0) or -1.0
        min_pct = (
            self.min_distance_percent
            if min_distance_percent is None
            else max(0.0, float(min_distance_percent))
        )

        if current_price <= 0 or take_profit_price <= 0:
            return False, "Current price and take profit must be positive numbers"

        side_valid, reason, normalized_side = self.validate_side(side)
        if not side_valid:
            return False, reason

        distance_pct = _distance_percent(current_price, take_profit_price)

        if normalized_side == "long":
            if take_profit_price <= current_price:
                return False, "Take profit must be above current price for long positions"
            if distance_pct < min_pct:
                return False, f"Take profit too close: {distance_pct:.3f}% above current price"

        if normalized_side == "short":
            if take_profit_price >= current_price:
                return False, "Take profit must be below current price for short positions"
            if distance_pct < min_pct:
                return False, f"Take profit too close: {distance_pct:.3f}% below current price"

        return True, ""

    def validate_stop_loss_take_profit_pair(
            self,
            current_price: float,
            side: Side,
            *,
            stop_loss: Optional[float] = None,
            take_profit: Optional[float] = None,
    ) -> tuple[bool, str]:
        if stop_loss is not None:
            valid, reason = self.validate_stop_loss(current_price, stop_loss, side)
            if not valid:
                return False, reason

        if take_profit is not None:
            valid, reason = self.validate_take_profit(current_price, take_profit, side)
            if not valid:
                return False, reason

        normalized_side = _normalize_side(side)

        if stop_loss is not None and take_profit is not None:
            sl = _to_float(stop_loss)
            tp = _to_float(take_profit)

            if sl is None or tp is None:
                return False, "Stop loss and take profit must be valid numbers"

            if normalized_side == "long" and sl >= tp:
                return False, "For long positions, stop loss must be below take profit"

            if normalized_side == "short" and sl <= tp:
                return False, "For short positions, stop loss must be above take profit"

        return True, ""

    def validate_trailing_stop(
            self,
            trailing_distance: Optional[float] = None,
            trailing_percent: Optional[float] = None,
            *,
            allow_both: bool = False,
    ) -> tuple[bool, str]:
        trailing_distance = _to_float(trailing_distance)
        trailing_percent = _to_float(trailing_percent)

        if trailing_distance is None and trailing_percent is None:
            return False, "Either trailing distance or trailing percent must be specified"

        if not allow_both and trailing_distance is not None and trailing_percent is not None:
            return False, "Use either trailing distance or trailing percent, not both"

        if trailing_distance is not None:
            if trailing_distance <= 0:
                return False, "Trailing stop distance must be positive"
            if trailing_distance < 0.000001:
                return False, "Trailing stop distance is too small"

        if trailing_percent is not None:
            if trailing_percent <= 0 or trailing_percent >= 100:
                return False, "Trailing stop percent must be greater than 0 and less than 100"
            if trailing_percent < 0.01:
                return False, "Trailing stop percent is too small"

        return True, ""

    # ------------------------------------------------------------------
    # Position inference
    # ------------------------------------------------------------------

    def infer_position_side(self, position: Any) -> str:
        explicit_side = _get_attr(
            position,
            "side",
            "position_side",
            "direction",
            default=None,
        )
        normalized = _normalize_side(explicit_side)
        if normalized != "unknown":
            return normalized

        quantity = _to_float(
            _get_attr(position, "quantity", "qty", "size", default=None),
            default=0.0,
        ) or 0.0

        if quantity > 0:
            return "long"

        if quantity < 0:
            return "short"

        return "unknown"

    # ------------------------------------------------------------------
    # Broker operations: position TP/SL
    # ------------------------------------------------------------------

    async def modify_position_stop_loss(
            self,
            command: ModifyPositionStopLossCommand,
            current_price: float,
            *,
            side: Optional[str] = None,
    ) -> dict[str, Any]:
        position_id = _normalize_id(_get_attr(command, "position_id", default=""))
        symbol = _normalize_symbol(_get_attr(command, "symbol", default=""))
        new_stop_loss = _to_float(
            _get_attr(command, "new_stop_loss_price", "stop_loss", default=None)
        )
        command_side = side or _get_attr(
            command,
            "side",
            "position_side",
            "direction",
            default=None,
        )

        if not position_id:
            return RiskActionResult(
                success=False,
                message="Position id is required",
                action="modify_position_stop_loss",
                symbol=symbol,
            ).to_dict()

        if new_stop_loss is None:
            return RiskActionResult(
                success=False,
                message="New stop loss price is required",
                action="modify_position_stop_loss",
                symbol=symbol,
                position_id=position_id,
            ).to_dict()

        valid, reason = self.validate_stop_loss(current_price, new_stop_loss, command_side)
        if not valid:
            return RiskActionResult(
                success=False,
                message=reason,
                action="modify_position_stop_loss",
                symbol=symbol,
                position_id=position_id,
                new_stop_loss=new_stop_loss,
            ).to_dict()

        try:
            broker_result = await self._call_broker_method(
                "modify_stop_loss",
                fallback_method_names=("modify_position_stop_loss", "set_stop_loss"),
                position_id=position_id,
                symbol=symbol,
                stop_loss_price=new_stop_loss,
                stop_loss=new_stop_loss,
            )

            return RiskActionResult(
                success=True,
                message=f"Stop loss modified to {new_stop_loss}",
                action="modify_position_stop_loss",
                symbol=symbol,
                position_id=position_id,
                new_stop_loss=new_stop_loss,
                broker_result=broker_result,
            ).to_dict()

        except Exception as exc:
            self.logger.exception("Failed to modify position stop loss")
            return RiskActionResult(
                success=False,
                message=f"Failed to modify stop loss: {exc}",
                action="modify_position_stop_loss",
                symbol=symbol,
                position_id=position_id,
                new_stop_loss=new_stop_loss,
            ).to_dict()

    async def modify_position_take_profit(
            self,
            command: ModifyPositionTakeProfitCommand,
            current_price: float,
            *,
            side: Optional[str] = None,
    ) -> dict[str, Any]:
        position_id = _normalize_id(_get_attr(command, "position_id", default=""))
        symbol = _normalize_symbol(_get_attr(command, "symbol", default=""))
        new_take_profit = _to_float(
            _get_attr(command, "new_take_profit_price", "take_profit", default=None)
        )
        command_side = side or _get_attr(
            command,
            "side",
            "position_side",
            "direction",
            default=None,
        )

        if not position_id:
            return RiskActionResult(
                success=False,
                message="Position id is required",
                action="modify_position_take_profit",
                symbol=symbol,
            ).to_dict()

        if new_take_profit is None:
            return RiskActionResult(
                success=False,
                message="New take profit price is required",
                action="modify_position_take_profit",
                symbol=symbol,
                position_id=position_id,
            ).to_dict()

        valid, reason = self.validate_take_profit(
            current_price,
            new_take_profit,
            command_side,
        )
        if not valid:
            return RiskActionResult(
                success=False,
                message=reason,
                action="modify_position_take_profit",
                symbol=symbol,
                position_id=position_id,
                new_take_profit=new_take_profit,
            ).to_dict()

        try:
            broker_result = await self._call_broker_method(
                "modify_take_profit",
                fallback_method_names=("modify_position_take_profit", "set_take_profit"),
                position_id=position_id,
                symbol=symbol,
                take_profit_price=new_take_profit,
                take_profit=new_take_profit,
            )

            return RiskActionResult(
                success=True,
                message=f"Take profit modified to {new_take_profit}",
                action="modify_position_take_profit",
                symbol=symbol,
                position_id=position_id,
                new_take_profit=new_take_profit,
                broker_result=broker_result,
            ).to_dict()

        except Exception as exc:
            self.logger.exception("Failed to modify position take profit")
            return RiskActionResult(
                success=False,
                message=f"Failed to modify take profit: {exc}",
                action="modify_position_take_profit",
                symbol=symbol,
                position_id=position_id,
                new_take_profit=new_take_profit,
            ).to_dict()

    # ------------------------------------------------------------------
    # Broker operations: order TP/SL
    # ------------------------------------------------------------------

    async def modify_order_stop_loss(
            self,
            command: ModifyOrderStopLossCommand,
            current_price: float,
            *,
            side: Optional[str] = None,
    ) -> dict[str, Any]:
        order_id = _normalize_id(_get_attr(command, "order_id", default=""))
        symbol = _normalize_symbol(_get_attr(command, "symbol", default=""))
        new_stop_loss = _to_float(
            _get_attr(command, "new_stop_loss_price", "stop_loss", default=None)
        )
        command_side = side or _get_attr(
            command,
            "side",
            "order_side",
            "direction",
            default=None,
        )

        if not order_id:
            return RiskActionResult(
                success=False,
                message="Order id is required",
                action="modify_order_stop_loss",
                symbol=symbol,
            ).to_dict()

        if new_stop_loss is None:
            return RiskActionResult(
                success=False,
                message="New stop loss price is required",
                action="modify_order_stop_loss",
                symbol=symbol,
                order_id=order_id,
            ).to_dict()

        valid, reason = self.validate_stop_loss(current_price, new_stop_loss, command_side)
        if not valid:
            return RiskActionResult(
                success=False,
                message=reason,
                action="modify_order_stop_loss",
                symbol=symbol,
                order_id=order_id,
                new_stop_loss=new_stop_loss,
            ).to_dict()

        try:
            broker_result = await self._call_broker_method(
                "modify_order_stop_loss",
                fallback_method_names=("modify_stop_loss", "set_stop_loss"),
                order_id=order_id,
                symbol=symbol,
                stop_loss_price=new_stop_loss,
                stop_loss=new_stop_loss,
            )

            return RiskActionResult(
                success=True,
                message=f"Order stop loss modified to {new_stop_loss}",
                action="modify_order_stop_loss",
                symbol=symbol,
                order_id=order_id,
                new_stop_loss=new_stop_loss,
                broker_result=broker_result,
            ).to_dict()

        except Exception as exc:
            self.logger.exception("Failed to modify order stop loss")
            return RiskActionResult(
                success=False,
                message=f"Failed to modify order stop loss: {exc}",
                action="modify_order_stop_loss",
                symbol=symbol,
                order_id=order_id,
                new_stop_loss=new_stop_loss,
            ).to_dict()

    async def modify_order_take_profit(
            self,
            command: ModifyOrderTakeProfitCommand,
            current_price: float,
            *,
            side: Optional[str] = None,
    ) -> dict[str, Any]:
        order_id = _normalize_id(_get_attr(command, "order_id", default=""))
        symbol = _normalize_symbol(_get_attr(command, "symbol", default=""))
        new_take_profit = _to_float(
            _get_attr(command, "new_take_profit_price", "take_profit", default=None)
        )
        command_side = side or _get_attr(
            command,
            "side",
            "order_side",
            "direction",
            default=None,
        )

        if not order_id:
            return RiskActionResult(
                success=False,
                message="Order id is required",
                action="modify_order_take_profit",
                symbol=symbol,
            ).to_dict()

        if new_take_profit is None:
            return RiskActionResult(
                success=False,
                message="New take profit price is required",
                action="modify_order_take_profit",
                symbol=symbol,
                order_id=order_id,
            ).to_dict()

        valid, reason = self.validate_take_profit(
            current_price,
            new_take_profit,
            command_side,
        )
        if not valid:
            return RiskActionResult(
                success=False,
                message=reason,
                action="modify_order_take_profit",
                symbol=symbol,
                order_id=order_id,
                new_take_profit=new_take_profit,
            ).to_dict()

        try:
            broker_result = await self._call_broker_method(
                "modify_order_take_profit",
                fallback_method_names=("modify_take_profit", "set_take_profit"),
                order_id=order_id,
                symbol=symbol,
                take_profit_price=new_take_profit,
                take_profit=new_take_profit,
            )

            return RiskActionResult(
                success=True,
                message=f"Order take profit modified to {new_take_profit}",
                action="modify_order_take_profit",
                symbol=symbol,
                order_id=order_id,
                new_take_profit=new_take_profit,
                broker_result=broker_result,
            ).to_dict()

        except Exception as exc:
            self.logger.exception("Failed to modify order take profit")
            return RiskActionResult(
                success=False,
                message=f"Failed to modify order take profit: {exc}",
                action="modify_order_take_profit",
                symbol=symbol,
                order_id=order_id,
                new_take_profit=new_take_profit,
            ).to_dict()

    # ------------------------------------------------------------------
    # Broker operation: trailing stop
    # ------------------------------------------------------------------

    async def enable_trailing_stop(self, command: Any) -> dict[str, Any]:
        order_id = _normalize_id(_get_attr(command, "order_id", default=None))
        position_id = _normalize_id(_get_attr(command, "position_id", default=None))
        symbol = _normalize_symbol(_get_attr(command, "symbol", default=""))

        trailing_distance = _to_float(
            _get_attr(
                command,
                "trailing_stop_distance",
                "trailing_distance",
                default=None,
            )
        )
        trailing_percent = _to_float(
            _get_attr(
                command,
                "trailing_stop_percent",
                "trailing_percent",
                default=None,
            )
        )

        valid, reason = self.validate_trailing_stop(
            trailing_distance,
            trailing_percent,
        )
        if not valid:
            return RiskActionResult(
                success=False,
                message=reason,
                action="enable_trailing_stop",
                symbol=symbol,
                order_id=order_id,
                position_id=position_id,
                trailing_stop_distance=trailing_distance,
                trailing_stop_percent=trailing_percent,
            ).to_dict()

        if not order_id and not position_id:
            return RiskActionResult(
                success=False,
                message="Either order_id or position_id is required",
                action="enable_trailing_stop",
                symbol=symbol,
            ).to_dict()

        try:
            broker_result = await self._call_broker_method(
                "enable_trailing_stop",
                fallback_method_names=("set_trailing_stop", "modify_trailing_stop"),
                position_id=position_id,
                order_id=order_id,
                symbol=symbol,
                trailing_distance=trailing_distance,
                trailing_stop_distance=trailing_distance,
                trailing_percent=trailing_percent,
                trailing_stop_percent=trailing_percent,
            )

            distance_text = (
                f"{trailing_distance}"
                if trailing_distance is not None
                else f"{trailing_percent}%"
            )

            return RiskActionResult(
                success=True,
                message=f"Trailing stop enabled with distance: {distance_text}",
                action="enable_trailing_stop",
                symbol=symbol,
                order_id=order_id,
                position_id=position_id,
                trailing_stop_distance=trailing_distance,
                trailing_stop_percent=trailing_percent,
                broker_result=broker_result,
            ).to_dict()

        except Exception as exc:
            self.logger.exception("Failed to enable trailing stop")
            return RiskActionResult(
                success=False,
                message=f"Failed to enable trailing stop: {exc}",
                action="enable_trailing_stop",
                symbol=symbol,
                order_id=order_id,
                position_id=position_id,
                trailing_stop_distance=trailing_distance,
                trailing_stop_percent=trailing_percent,
            ).to_dict()

    # ------------------------------------------------------------------
    # Local position snapshot updates
    # ------------------------------------------------------------------

    def update_position_with_risk_params(
            self,
            position: PositionSnapshot,
            *,
            stop_loss: Optional[float] = None,
            take_profit: Optional[float] = None,
            validate: bool = True,
    ) -> PositionSnapshot:
        current_price = _to_float(
            _get_attr(position, "last_price", "current_price", "mark_price", default=None)
        )
        side = self.infer_position_side(position)

        if validate and current_price is not None and side != "unknown":
            valid, reason = self.validate_stop_loss_take_profit_pair(
                current_price,
                side,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            if not valid:
                raise ValueError(reason)

        updates: dict[str, Any] = {
            "updated_at": _utc_now(),
        }

        if stop_loss is not None:
            updates["stop_loss"] = float(stop_loss)

        if take_profit is not None:
            updates["take_profit"] = float(take_profit)

        metadata = dict(_get_attr(position, "metadata", default={}) or {})
        metadata["risk_updated_at"] = _utc_now().isoformat()
        updates["metadata"] = metadata

        return _replace_position_snapshot(position, **updates)

    def enable_trailing_stop_on_position(
            self,
            position: PositionSnapshot,
            *,
            trailing_distance: Optional[float] = None,
            trailing_percent: Optional[float] = None,
            validate: bool = True,
    ) -> PositionSnapshot:
        trailing_distance = _to_float(trailing_distance)
        trailing_percent = _to_float(trailing_percent)

        if validate:
            valid, reason = self.validate_trailing_stop(
                trailing_distance,
                trailing_percent,
            )
            if not valid:
                raise ValueError(reason)

        metadata = dict(_get_attr(position, "metadata", default={}) or {})
        metadata["trailing_stop_enabled_at"] = _utc_now().isoformat()

        return _replace_position_snapshot(
            position,
            trailing_stop_enabled=True,
            trailing_stop_distance=trailing_distance,
            trailing_stop_percent=trailing_percent,
            updated_at=_utc_now(),
            metadata=metadata,
        )

    def disable_trailing_stop_on_position(
            self,
            position: PositionSnapshot,
    ) -> PositionSnapshot:
        metadata = dict(_get_attr(position, "metadata", default={}) or {})
        metadata["trailing_stop_disabled_at"] = _utc_now().isoformat()

        return _replace_position_snapshot(
            position,
            trailing_stop_enabled=False,
            trailing_stop_distance=None,
            trailing_stop_percent=None,
            updated_at=_utc_now(),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Protection builders
    # ------------------------------------------------------------------

    def build_default_protection(
            self,
            *,
            entry_price: float,
            side: Side,
            stop_loss_percent: Optional[float] = None,
            take_profit_percent: Optional[float] = None,
            risk_reward_ratio: Optional[float] = None,
    ) -> dict[str, Optional[float]]:
        """Build default SL/TP prices from percent settings.

        Example:
            long entry 100, stop_loss_percent 2, risk_reward_ratio 2
            -> SL 98, TP 104
        """
        entry_price = _to_float(entry_price, default=-1.0) or -1.0
        if entry_price <= 0:
            raise ValueError("Entry price must be positive")

        side_valid, reason, normalized_side = self.validate_side(side)
        if not side_valid:
            raise ValueError(reason)

        stop_loss_percent = _to_float(stop_loss_percent)
        take_profit_percent = _to_float(take_profit_percent)
        risk_reward_ratio = _to_float(risk_reward_ratio)

        if stop_loss_percent is None and take_profit_percent is None:
            raise ValueError(
                "At least one of stop_loss_percent or take_profit_percent is required"
            )

        if stop_loss_percent is not None and stop_loss_percent <= 0:
            raise ValueError("stop_loss_percent must be positive")

        if take_profit_percent is not None and take_profit_percent <= 0:
            raise ValueError("take_profit_percent must be positive")

        if take_profit_percent is None and risk_reward_ratio is not None:
            if risk_reward_ratio <= 0:
                raise ValueError("risk_reward_ratio must be positive")
            if stop_loss_percent is None:
                raise ValueError(
                    "stop_loss_percent is required when using risk_reward_ratio"
                )
            take_profit_percent = stop_loss_percent * risk_reward_ratio

        stop_loss: Optional[float] = None
        take_profit: Optional[float] = None

        if normalized_side == "long":
            if stop_loss_percent is not None:
                stop_loss = entry_price * (1.0 - stop_loss_percent / 100.0)
            if take_profit_percent is not None:
                take_profit = entry_price * (1.0 + take_profit_percent / 100.0)

        elif normalized_side == "short":
            if stop_loss_percent is not None:
                stop_loss = entry_price * (1.0 + stop_loss_percent / 100.0)
            if take_profit_percent is not None:
                take_profit = entry_price * (1.0 - take_profit_percent / 100.0)

        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def build_atr_protection(
            self,
            *,
            entry_price: float,
            side: Side,
            atr: float,
            stop_loss_atr_multiple: float = 1.5,
            take_profit_atr_multiple: Optional[float] = None,
            risk_reward_ratio: Optional[float] = None,
    ) -> dict[str, Optional[float]]:
        """Build SL/TP using ATR distance."""
        entry = _to_float(entry_price, default=-1.0) or -1.0
        atr_value = _to_float(atr, default=-1.0) or -1.0

        if entry <= 0:
            raise ValueError("Entry price must be positive")

        if atr_value <= 0:
            raise ValueError("ATR must be positive")

        side_valid, reason, normalized_side = self.validate_side(side)
        if not side_valid:
            raise ValueError(reason)

        sl_multiple = _to_float(stop_loss_atr_multiple, default=1.5) or 1.5
        tp_multiple = _to_float(take_profit_atr_multiple)

        if sl_multiple <= 0:
            raise ValueError("stop_loss_atr_multiple must be positive")

        if tp_multiple is None and risk_reward_ratio is not None:
            rr = _to_float(risk_reward_ratio, default=None)
            if rr is None or rr <= 0:
                raise ValueError("risk_reward_ratio must be positive")
            tp_multiple = sl_multiple * rr

        stop_distance = atr_value * sl_multiple
        take_profit_distance = atr_value * tp_multiple if tp_multiple is not None else None

        if normalized_side == "long":
            stop_loss = entry - stop_distance
            take_profit = entry + take_profit_distance if take_profit_distance is not None else None
        else:
            stop_loss = entry + stop_distance
            take_profit = entry - take_profit_distance if take_profit_distance is not None else None

        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def build_trailing_stop_params(
            self,
            *,
            entry_price: Optional[float] = None,
            trailing_distance: Optional[float] = None,
            trailing_percent: Optional[float] = None,
            trailing_percent_from_price: Optional[float] = None,
    ) -> dict[str, Optional[float]]:
        """Build valid trailing stop settings.

        You can pass either:
        - trailing_distance directly
        - trailing_percent directly
        - entry_price + trailing_percent_from_price to calculate distance
        """
        trailing_distance = _to_float(trailing_distance)
        trailing_percent = _to_float(trailing_percent)
        trailing_percent_from_price = _to_float(trailing_percent_from_price)

        if trailing_distance is None and trailing_percent is None:
            if entry_price is not None and trailing_percent_from_price is not None:
                entry = _to_float(entry_price, default=-1.0) or -1.0
                if entry <= 0:
                    raise ValueError("entry_price must be positive")
                if trailing_percent_from_price <= 0:
                    raise ValueError("trailing_percent_from_price must be positive")
                trailing_distance = entry * trailing_percent_from_price / 100.0

        valid, reason = self.validate_trailing_stop(
            trailing_distance,
            trailing_percent,
        )
        if not valid:
            raise ValueError(reason)

        return {
            "trailing_distance": trailing_distance,
            "trailing_percent": trailing_percent,
        }

    # ------------------------------------------------------------------
    # Convenience high-level helpers
    # ------------------------------------------------------------------

    async def apply_default_protection_to_position(
            self,
            *,
            position_id: str,
            symbol: str,
            current_price: float,
            side: Side,
            stop_loss_percent: Optional[float] = None,
            take_profit_percent: Optional[float] = None,
            risk_reward_ratio: Optional[float] = None,
    ) -> dict[str, Any]:
        protection = self.build_default_protection(
            entry_price=current_price,
            side=side,
            stop_loss_percent=stop_loss_percent,
            take_profit_percent=take_profit_percent,
            risk_reward_ratio=risk_reward_ratio,
        )

        results: dict[str, Any] = {
            "success": True,
            "symbol": _normalize_symbol(symbol),
            "position_id": _normalize_id(position_id),
            "stop_loss_result": None,
            "take_profit_result": None,
        }

        if protection.get("stop_loss") is not None:
            stop_command = {
                "position_id": position_id,
                "symbol": symbol,
                "new_stop_loss_price": protection["stop_loss"],
                "side": side,
            }
            results["stop_loss_result"] = await self.modify_position_stop_loss(
                stop_command,
                current_price,
                side=side,
            )

        if protection.get("take_profit") is not None:
            take_profit_command = {
                "position_id": position_id,
                "symbol": symbol,
                "new_take_profit_price": protection["take_profit"],
                "side": side,
            }
            results["take_profit_result"] = await self.modify_position_take_profit(
                take_profit_command,
                current_price,
                side=side,
            )

        for key in ("stop_loss_result", "take_profit_result"):
            item = results.get(key)
            if isinstance(item, dict) and not item.get("success", False):
                results["success"] = False

        return results

    async def apply_default_protection_to_order(
            self,
            *,
            order_id: str,
            symbol: str,
            current_price: float,
            side: Side,
            stop_loss_percent: Optional[float] = None,
            take_profit_percent: Optional[float] = None,
            risk_reward_ratio: Optional[float] = None,
    ) -> dict[str, Any]:
        protection = self.build_default_protection(
            entry_price=current_price,
            side=side,
            stop_loss_percent=stop_loss_percent,
            take_profit_percent=take_profit_percent,
            risk_reward_ratio=risk_reward_ratio,
        )

        results: dict[str, Any] = {
            "success": True,
            "symbol": _normalize_symbol(symbol),
            "order_id": _normalize_id(order_id),
            "stop_loss_result": None,
            "take_profit_result": None,
        }

        if protection.get("stop_loss") is not None:
            stop_command = {
                "order_id": order_id,
                "symbol": symbol,
                "new_stop_loss_price": protection["stop_loss"],
                "side": side,
            }
            results["stop_loss_result"] = await self.modify_order_stop_loss(
                stop_command,
                current_price,
                side=side,
            )

        if protection.get("take_profit") is not None:
            take_profit_command = {
                "order_id": order_id,
                "symbol": symbol,
                "new_take_profit_price": protection["take_profit"],
                "side": side,
            }
            results["take_profit_result"] = await self.modify_order_take_profit(
                take_profit_command,
                current_price,
                side=side,
            )

        for key in ("stop_loss_result", "take_profit_result"):
            item = results.get(key)
            if isinstance(item, dict) and not item.get("success", False):
                results["success"] = False

        return results


__all__ = [
    "RiskActionResult",
    "RiskBrokerProtocol",
    "RiskManagementEngine",
    "DEFAULT_MIN_DISTANCE_PERCENT",
    "DEFAULT_MAX_WARNING_DISTANCE_PERCENT",
]