"""Risk management utilities for modifying TP/SL and trailing stops on active positions and orders."""

import logging
from typing import Optional

from contracts.execution import (
    ModifyOrderStopLossCommand,
    ModifyOrderTakeProfitCommand,
    EnableTrailingStopCommand,
)
from contracts.portfolio import (
    ModifyPositionStopLossCommand,
    ModifyPositionTakeProfitCommand,
    EnableTrailingStopCommand as PortfolioEnableTrailingStopCommand,
    PositionSnapshot,
)


class RiskManagementEngine:
    """Engine for managing TP/SL modifications and trailing stops on live positions."""

    def __init__(self, broker=None, logger=None):
        self.broker = broker
        self.logger = logger or logging.getLogger(__name__)

    def validate_stop_loss(self, current_price: float, stop_loss_price: float, side: str) -> tuple[bool, str]:
        """Validate that stop loss is at reasonable distance from current price.

        Args:
            current_price: Current market price
            stop_loss_price: Proposed stop loss price
            side: Position side ('buy', 'sell', 'long', 'short')

        Returns:
            (is_valid, reason)
        """
        if current_price <= 0 or stop_loss_price <= 0:
            return False, "Prices must be positive"

        normalized_side = str(side or "").strip().lower()
        distance_pct = abs(stop_loss_price - current_price) / current_price * 100

        if normalized_side in {"buy", "long"}:
            if stop_loss_price >= current_price:
                return False, "Stop loss must be below current price for long positions"
            if distance_pct < 0.1:
                return False, f"Stop loss too close (only {distance_pct:.2f}% below current price)"

        elif normalized_side in {"sell", "short"}:
            if stop_loss_price <= current_price:
                return False, "Stop loss must be above current price for short positions"
            if distance_pct < 0.1:
                return False, f"Stop loss too close (only {distance_pct:.2f}% above current price)"

        if distance_pct > 50:
            self.logger.warning(f"Stop loss is very far from current price: {distance_pct:.2f}%")

        return True, ""

    def validate_take_profit(self, current_price: float, take_profit_price: float, side: str) -> tuple[bool, str]:
        """Validate that take profit is at reasonable distance from current price.

        Args:
            current_price: Current market price
            take_profit_price: Proposed take profit price
            side: Position side ('buy', 'sell', 'long', 'short')

        Returns:
            (is_valid, reason)
        """
        if current_price <= 0 or take_profit_price <= 0:
            return False, "Prices must be positive"

        normalized_side = str(side or "").strip().lower()
        distance_pct = abs(take_profit_price - current_price) / current_price * 100

        if normalized_side in {"buy", "long"}:
            if take_profit_price <= current_price:
                return False, "Take profit must be above current price for long positions"
            if distance_pct < 0.1:
                return False, f"Take profit too close (only {distance_pct:.2f}% above current price)"

        elif normalized_side in {"sell", "short"}:
            if take_profit_price >= current_price:
                return False, "Take profit must be below current price for short positions"
            if distance_pct < 0.1:
                return False, f"Take profit too close (only {distance_pct:.2f}% below current price)"

        return True, ""

    def validate_trailing_stop(
        self, trailing_distance: Optional[float] = None, trailing_percent: Optional[float] = None
    ) -> tuple[bool, str]:
        """Validate trailing stop parameters.

        Args:
            trailing_distance: Absolute distance for trailing stop
            trailing_percent: Percentage distance for trailing stop

        Returns:
            (is_valid, reason)
        """
        if trailing_distance is None and trailing_percent is None:
            return False, "Either distance or percentage must be specified for trailing stop"

        if trailing_distance is not None:
            if trailing_distance <= 0:
                return False, "Trailing stop distance must be positive"
            if trailing_distance < 0.01:
                return False, "Trailing stop distance too small"

        if trailing_percent is not None:
            if trailing_percent <= 0 or trailing_percent >= 100:
                return False, "Trailing stop percent must be between 0 and 100"
            if trailing_percent < 0.1:
                return False, "Trailing stop percent too small"

        return True, ""

    async def modify_position_stop_loss(self, command: ModifyPositionStopLossCommand, current_price: float) -> dict:
        """Modify stop loss on an open position.

        Args:
            command: Modification command
            current_price: Current market price

        Returns:
            Result dictionary with status and message
        """
        is_valid, reason = self.validate_stop_loss(current_price, command.new_stop_loss_price, "buy")
        if not is_valid:
            return {"success": False, "message": reason}

        if self.broker is None:
            return {"success": False, "message": "Broker not initialized"}

        # Check if broker supports SL modification
        if not hasattr(self.broker, "modify_stop_loss"):
            return {"success": False, "message": "Broker does not support stop loss modification"}

        try:
            result = await self.broker.modify_stop_loss(
                position_id=command.position_id, stop_loss_price=command.new_stop_loss_price
            )
            return {
                "success": True,
                "message": f"Stop loss modified to {command.new_stop_loss_price}",
                "position_id": command.position_id,
                "new_stop_loss": command.new_stop_loss_price,
            }
        except Exception as e:
            self.logger.exception(f"Failed to modify stop loss: {e}")
            return {"success": False, "message": f"Failed to modify stop loss: {str(e)}"}

    async def modify_position_take_profit(self, command: ModifyPositionTakeProfitCommand, current_price: float) -> dict:
        """Modify take profit on an open position.

        Args:
            command: Modification command
            current_price: Current market price

        Returns:
            Result dictionary with status and message
        """
        is_valid, reason = self.validate_take_profit(current_price, command.new_take_profit_price, "buy")
        if not is_valid:
            return {"success": False, "message": reason}

        if self.broker is None:
            return {"success": False, "message": "Broker not initialized"}

        # Check if broker supports TP modification
        if not hasattr(self.broker, "modify_take_profit"):
            return {"success": False, "message": "Broker does not support take profit modification"}

        try:
            result = await self.broker.modify_take_profit(
                position_id=command.position_id, take_profit_price=command.new_take_profit_price
            )
            return {
                "success": True,
                "message": f"Take profit modified to {command.new_take_profit_price}",
                "position_id": command.position_id,
                "new_take_profit": command.new_take_profit_price,
            }
        except Exception as e:
            self.logger.exception(f"Failed to modify take profit: {e}")
            return {"success": False, "message": f"Failed to modify take profit: {str(e)}"}

    async def enable_trailing_stop(self, command: EnableTrailingStopCommand) -> dict:
        """Enable a trailing stop on an open position.

        Args:
            command: Enable trailing stop command

        Returns:
            Result dictionary with status and message
        """
        is_valid, reason = self.validate_trailing_stop(command.trailing_stop_distance, command.trailing_stop_percent)
        if not is_valid:
            return {"success": False, "message": reason}

        if self.broker is None:
            return {"success": False, "message": "Broker not initialized"}

        # Check if broker supports trailing stops
        if not hasattr(self.broker, "enable_trailing_stop"):
            return {"success": False, "message": "Broker does not support trailing stops"}

        try:
            result = await self.broker.enable_trailing_stop(
                position_id=command.order_id,
                symbol=command.symbol,
                trailing_distance=command.trailing_stop_distance,
                trailing_percent=command.trailing_stop_percent,
            )
            distance_text = (
                f"{command.trailing_stop_distance}" if command.trailing_stop_distance else f"{command.trailing_stop_percent}%"
            )
            return {
                "success": True,
                "message": f"Trailing stop enabled with distance: {distance_text}",
                "order_id": command.order_id,
                "trailing_stop_distance": command.trailing_stop_distance,
                "trailing_stop_percent": command.trailing_stop_percent,
            }
        except Exception as e:
            self.logger.exception(f"Failed to enable trailing stop: {e}")
            return {"success": False, "message": f"Failed to enable trailing stop: {str(e)}"}

    def update_position_with_risk_params(
        self, position: PositionSnapshot, stop_loss: float = None, take_profit: float = None
    ) -> PositionSnapshot:
        """Update a position snapshot with new risk management parameters.

        Args:
            position: Original position snapshot
            stop_loss: New stop loss price
            take_profit: New take profit price

        Returns:
            Updated position snapshot
        """
        updated = PositionSnapshot(
            position_id=position.position_id,
            symbol=position.symbol,
            venue=position.venue,
            quantity=position.quantity,
            average_price=position.average_price,
            last_price=position.last_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=position.unrealized_pnl,
            exposure_pct=position.exposure_pct,
            stop_loss=stop_loss if stop_loss is not None else position.stop_loss,
            take_profit=take_profit if take_profit is not None else position.take_profit,
            trailing_stop_enabled=position.trailing_stop_enabled,
            trailing_stop_distance=position.trailing_stop_distance,
            trailing_stop_percent=position.trailing_stop_percent,
            opened_at=position.opened_at,
            updated_at=position.updated_at,
            metadata=position.metadata,
        )
        return updated

    def enable_trailing_stop_on_position(
        self,
        position: PositionSnapshot,
        trailing_distance: float = None,
        trailing_percent: float = None,
    ) -> PositionSnapshot:
        """Enable trailing stop on a position snapshot.

        Args:
            position: Original position snapshot
            trailing_distance: Absolute distance for trailing stop
            trailing_percent: Percentage distance for trailing stop

        Returns:
            Updated position snapshot
        """
        updated = PositionSnapshot(
            position_id=position.position_id,
            symbol=position.symbol,
            venue=position.venue,
            quantity=position.quantity,
            average_price=position.average_price,
            last_price=position.last_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=position.unrealized_pnl,
            exposure_pct=position.exposure_pct,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            trailing_stop_enabled=True,
            trailing_stop_distance=trailing_distance,
            trailing_stop_percent=trailing_percent,
            opened_at=position.opened_at,
            updated_at=position.updated_at,
            metadata=position.metadata,
        )
        return updated
