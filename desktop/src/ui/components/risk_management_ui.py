"""UI utilities for managing TP/SL modifications on active orders and positions.

This module provides high-level functions for the UI to interact with risk management
features like modifying stop loss, take profit, and enabling trailing stops.
"""

from typing import Optional

from contracts.enums import VenueKind
from contracts.execution import (
    ModifyOrderStopLossCommand,
    ModifyOrderTakeProfitCommand,
    EnableTrailingStopCommand,
)
from execution.risk_management import RiskManagementEngine


class RiskManagementUI:
    """High-level UI interface for risk management operations."""

    def __init__(self, risk_manager: RiskManagementEngine, controller=None):
        self.risk_manager = risk_manager
        self.controller = controller

    async def modify_stop_loss(
        self, order_id: str, symbol: str, venue: VenueKind, new_sl: float, current_price: float
    ) -> dict:
        """User action: Modify stop loss on an active order/position.

        Args:
            order_id: Order or position ID
            symbol: Trading symbol
            venue: Exchange venue
            new_sl: New stop loss price
            current_price: Current market price

        Returns:
            Status dictionary
        """
        command = ModifyOrderStopLossCommand(
            order_id=order_id,
            symbol=symbol,
            venue=venue,
            new_stop_loss_price=new_sl,
            reason="User modified stop loss from UI",
        )
        return await self.risk_manager.modify_position_stop_loss(command, current_price)

    async def modify_take_profit(
        self, order_id: str, symbol: str, venue: VenueKind, new_tp: float, current_price: float
    ) -> dict:
        """User action: Modify take profit on an active order/position.

        Args:
            order_id: Order or position ID
            symbol: Trading symbol
            venue: Exchange venue
            new_tp: New take profit price
            current_price: Current market price

        Returns:
            Status dictionary
        """
        command = ModifyOrderTakeProfitCommand(
            order_id=order_id,
            symbol=symbol,
            venue=venue,
            new_take_profit_price=new_tp,
            reason="User modified take profit from UI",
        )
        return await self.risk_manager.modify_position_take_profit(command, current_price)

    async def activate_trailing_stop(
        self,
        order_id: str,
        symbol: str,
        venue: VenueKind,
        distance: Optional[float] = None,
        percent: Optional[float] = None,
    ) -> dict:
        """User action: Activate trailing stop on an active order/position.

        Args:
            order_id: Order or position ID
            symbol: Trading symbol
            venue: Exchange venue
            distance: Absolute trailing distance (e.g., 100 for $100)
            percent: Percentage trailing distance (e.g., 2.5 for 2.5%)

        Returns:
            Status dictionary
        """
        command = EnableTrailingStopCommand(
            order_id=order_id,
            symbol=symbol,
            venue=venue,
            trailing_stop_distance=distance,
            trailing_stop_percent=percent,
            reason="User activated trailing stop from UI",
        )
        return await self.risk_manager.enable_trailing_stop(command)

    def get_position_risk_info(self, position: dict) -> dict:
        """Extract risk information from a position for display.

        Args:
            position: Position data dictionary

        Returns:
            Risk info dictionary with TP, SL, trailing stop status
        """
        return {
            "symbol": position.get("symbol"),
            "quantity": position.get("quantity"),
            "average_price": position.get("average_price"),
            "last_price": position.get("last_price"),
            "stop_loss": position.get("stop_loss"),
            "take_profit": position.get("take_profit"),
            "trailing_stop_enabled": position.get("trailing_stop_enabled", False),
            "trailing_stop_distance": position.get("trailing_stop_distance"),
            "trailing_stop_percent": position.get("trailing_stop_percent"),
            "unrealized_pnl": position.get("unrealized_pnl"),
        }

    def format_risk_level_display(self, position: dict) -> str:
        """Format risk management status for terminal display.

        Args:
            position: Position data dictionary

        Returns:
            Formatted string showing TP/SL/trailing stop status
        """
        parts = []

        if position.get("stop_loss"):
            parts.append(f"SL: {position['stop_loss']:.2f}")

        if position.get("take_profit"):
            parts.append(f"TP: {position['take_profit']:.2f}")

        if position.get("trailing_stop_enabled"):
            if position.get("trailing_stop_distance"):
                parts.append(f"Trail: ±{position['trailing_stop_distance']:.2f}")
            elif position.get("trailing_stop_percent"):
                parts.append(f"Trail: ±{position['trailing_stop_percent']:.2f}%")

        return " | ".join(parts) if parts else "No risk limits set"

    @staticmethod
    def validate_modification_input(
        current_price: float, new_price: float, modification_type: str, side: str
    ) -> tuple[bool, str]:
        """Validate user input for TP/SL modification.

        Args:
            current_price: Current market price
            new_price: User's proposed new price
            modification_type: "sl" or "tp"
            side: Position side ("buy", "sell")

        Returns:
            (is_valid, error_message)
        """
        if new_price <= 0:
            return False, "Price must be positive"

        if abs(new_price - current_price) / current_price * 100 < 0.01:
            return False, "Price change too small (less than 0.01%)"

        normalized_side = str(side).lower()

        if modification_type.lower() == "sl":
            if normalized_side in {"buy", "long"}:
                if new_price >= current_price:
                    return False, "Stop loss must be below current price for long positions"
            elif normalized_side in {"sell", "short"}:
                if new_price <= current_price:
                    return False, "Stop loss must be above current price for short positions"

        elif modification_type.lower() == "tp":
            if normalized_side in {"buy", "long"}:
                if new_price <= current_price:
                    return False, "Take profit must be above current price for long positions"
            elif normalized_side in {"sell", "short"}:
                if new_price >= current_price:
                    return False, "Take profit must be below current price for short positions"

        return True, ""
