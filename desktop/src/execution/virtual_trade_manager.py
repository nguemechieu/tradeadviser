from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from journal.trade_journal import TradeJournal
from sopotek.core.event_bus import AsyncEventBus
from sopotek.core.event_types import EventType
from sopotek.core.models import ClosePositionRequest, ExecutionReport


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return _utc_now()


def _close_side(side: str) -> str:
    return "sell" if str(side).lower() == "long" else "buy"


def _position_side(order_side: str) -> str:
    return "long" if str(order_side).lower() == "buy" else "short"


@dataclass(slots=True)
class VirtualExitDecision:
    trade_id: str
    symbol: str
    action: str
    reason: str
    trigger_price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(slots=True)
class VirtualTrade:
    trade_id: str
    symbol: str
    side: str
    position_size: float
    entry_price: float
    initial_stop_loss: float
    initial_take_profit: float
    virtual_stop_loss: float
    virtual_take_profit: float
    risk_amount: float
    strategy_name: str
    entry_reason: str = ""
    signal_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    stop_distance: float = 0.0
    risk_reward_ratio: float = 0.0
    trailing_stop_distance: float = 0.0
    break_even_trigger_distance: float = 0.0
    allow_trailing_stop: bool = True
    allow_break_even: bool = True
    break_even_armed: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0
    state: str = "open"
    opened_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    close_requested_at: datetime | None = None
    close_reason: str | None = None
    close_price: float | None = None


class VirtualTradeManager:
    """Maintains broker-hidden stops and take-profit levels for live positions."""

    def __init__(
        self,
        event_bus: AsyncEventBus,
        *,
        journal: TradeJournal | None = None,
        close_retry_seconds: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.journal = journal
        self.close_retry_seconds = max(0.1, float(close_retry_seconds))
        self.logger = logger or logging.getLogger("VirtualTradeManager")
        self.trades: dict[str, VirtualTrade] = {}
        self.latest_prices: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

        self.bus.subscribe(EventType.EXECUTION_REPORT, self._on_execution_report)
        self.bus.subscribe(EventType.POSITIONS_CLOSED, self._on_position_closed)

    def get_trade(self, trade_id: str) -> VirtualTrade | None:
        return self.trades.get(str(trade_id))

    def list_open_trades(self, symbol: str | None = None) -> list[VirtualTrade]:
        normalized_symbol = str(symbol or "").strip().upper()
        trades = [trade for trade in self.trades.values() if trade.state != "closed"]
        if normalized_symbol:
            trades = [trade for trade in trades if trade.symbol == normalized_symbol]
        return trades

    async def register_entry(self, report: ExecutionReport) -> VirtualTrade | None:
        if str(report.status).lower() in {"failed", "rejected", "rejected_market_hours"}:
            return None

        metadata = dict(report.metadata or {})
        trade_id = str(metadata.get("trade_id") or report.order_id)
        entry_price = float(report.fill_price or report.requested_price or 0.0)
        if entry_price <= 0.0:
            return None

        stop_loss = float(metadata.get("virtual_stop_loss", report.stop_price) or 0.0)
        take_profit = float(metadata.get("virtual_take_profit", report.take_profit) or 0.0)
        quantity = float(report.filled_quantity if report.filled_quantity is not None else report.quantity)
        side = _position_side(report.side)
        stop_distance = abs(entry_price - stop_loss)
        trade = VirtualTrade(
            trade_id=trade_id,
            symbol=str(report.symbol).upper(),
            side=side,
            position_size=abs(quantity),
            entry_price=entry_price,
            initial_stop_loss=stop_loss,
            initial_take_profit=take_profit,
            virtual_stop_loss=stop_loss,
            virtual_take_profit=take_profit,
            risk_amount=float(metadata.get("risk_amount") or 0.0),
            strategy_name=str(report.strategy_name or metadata.get("strategy_name") or "unknown"),
            entry_reason=str(metadata.get("entry_reason") or metadata.get("signal_reason") or ""),
            signal_data=dict(metadata.get("signal_data") or {}),
            metadata=metadata,
            stop_distance=stop_distance,
            risk_reward_ratio=float(metadata.get("risk_reward_ratio") or 0.0),
            trailing_stop_distance=float(metadata.get("trailing_stop_distance") or stop_distance),
            break_even_trigger_distance=float(metadata.get("break_even_trigger_distance") or stop_distance),
            allow_trailing_stop=bool(metadata.get("allow_trailing_stop", True)),
            allow_break_even=bool(metadata.get("allow_break_even", True)),
            highest_price=entry_price,
            lowest_price=entry_price,
            opened_at=_coerce_timestamp(report.timestamp),
            updated_at=_coerce_timestamp(report.timestamp),
        )
        self.trades[trade_id] = trade
        self._locks.setdefault(trade_id, asyncio.Lock())

        if self.journal is not None:
            await self.journal.record_entry(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                side=trade.side,
                strategy_name=trade.strategy_name,
                entry_price=trade.entry_price,
                position_size=trade.position_size,
                risk_taken=trade.risk_amount,
                virtual_stop_loss=trade.virtual_stop_loss,
                virtual_take_profit=trade.virtual_take_profit,
                entry_reason=trade.entry_reason,
                signal_data=trade.signal_data,
                metadata=trade.metadata,
                opened_at=trade.opened_at,
            )
        return trade

    async def check_exit_conditions(self, latest_prices: dict[str, float] | None = None) -> list[VirtualExitDecision]:
        if latest_prices:
            self.latest_prices.update({str(symbol).upper(): float(price) for symbol, price in latest_prices.items() if float(price or 0.0) > 0.0})

        decisions: list[VirtualExitDecision] = []
        now = _utc_now()
        for trade in list(self.trades.values()):
            if trade.state == "closed":
                continue
            price = float(self.latest_prices.get(trade.symbol) or 0.0)
            if price <= 0.0:
                continue
            await self._evaluate_trade(trade, price, now, decisions)
        return decisions

    async def _evaluate_trade(
        self,
        trade: VirtualTrade,
        current_price: float,
        now: datetime,
        decisions: list[VirtualExitDecision],
    ) -> None:
        async with self._locks[trade.trade_id]:
            self._refresh_closing_state(trade, now)
            if trade.state != "open":
                return

            trade.updated_at = now
            trade.highest_price = max(trade.highest_price, current_price)
            trade.lowest_price = min(trade.lowest_price, current_price)
            self._apply_break_even(trade, current_price)
            self._apply_trailing_stop(trade, current_price)

            if self._hit_stop(trade, current_price):
                decisions.append(await self._request_exit(trade, current_price, "Virtual stop loss hit"))
                return
            if self._hit_take_profit(trade, current_price):
                decisions.append(await self._request_exit(trade, current_price, "Virtual take profit hit"))

    async def _request_exit(self, trade: VirtualTrade, current_price: float, reason: str) -> VirtualExitDecision:
        trade.state = "closing"
        trade.close_requested_at = _utc_now()
        trade.close_reason = reason
        request = ClosePositionRequest(
            symbol=trade.symbol,
            side=_close_side(trade.side),
            quantity=trade.position_size,
            reason=reason,
            price=current_price,
            stop_price=trade.virtual_stop_loss,
            take_profit=trade.virtual_take_profit,
            strategy_name="virtual_trade_manager",
            metadata={
                **dict(trade.metadata or {}),
                "trade_id": trade.trade_id,
                "close_position": True,
                "virtual_exit_reason": reason,
            },
        )
        await self.bus.publish(EventType.CLOSE_POSITION, request, priority=77, source="virtual_trade_manager")
        self.logger.info(
            "Virtual exit requested trade_id=%s symbol=%s reason=%s price=%.6f",
            trade.trade_id,
            trade.symbol,
            reason,
            current_price,
        )
        return VirtualExitDecision(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            action="exit",
            reason=reason,
            trigger_price=current_price,
            stop_loss=trade.virtual_stop_loss,
            take_profit=trade.virtual_take_profit,
        )

    async def _on_execution_report(self, event) -> None:
        report = getattr(event, "data", None)
        if report is None:
            return
        if not isinstance(report, ExecutionReport):
            report = ExecutionReport(**dict(report))

        metadata = dict(report.metadata or {})
        if not metadata.get("close_position"):
            return

        trade_id = str(metadata.get("trade_id") or report.order_id)
        trade = self.trades.get(trade_id)
        if trade is None:
            return

        if str(report.status).lower() in {"failed", "rejected"}:
            trade.state = "open"
            trade.close_requested_at = None
            return

        trade.state = "closing"
        trade.updated_at = _coerce_timestamp(report.timestamp)

    async def _on_position_closed(self, event) -> None:
        payload = dict(getattr(event, "data", {}) or {})
        trade_id = str(payload.get("trade_id") or "")
        symbol = str(payload.get("symbol") or "").upper()
        trade = self.trades.get(trade_id)
        if trade is None and symbol:
            trade = next((item for item in self.trades.values() if item.symbol == symbol and item.state != "closed"), None)
        if trade is None:
            return

        exit_price = float(payload.get("exit_price") or 0.0)
        close_time = _coerce_timestamp(payload.get("close_time"))
        trade.state = "closed"
        trade.close_price = exit_price
        trade.close_reason = str(payload.get("reason") or trade.close_reason or "closed")
        trade.updated_at = close_time

        pnl = self._calculate_pnl(trade, exit_price)
        if self.journal is not None:
            await self.journal.record_exit(
                trade_id=trade.trade_id,
                exit_price=exit_price,
                exit_reason=trade.close_reason,
                pnl=pnl,
                closed_at=close_time,
                metadata={
                    "virtual_stop_loss": trade.virtual_stop_loss,
                    "virtual_take_profit": trade.virtual_take_profit,
                },
            )

    def _apply_break_even(self, trade: VirtualTrade, current_price: float) -> None:
        if not trade.allow_break_even or trade.break_even_armed:
            return
        trigger_distance = max(0.0, float(trade.break_even_trigger_distance or trade.stop_distance or 0.0))
        if trigger_distance <= 0.0:
            return
        if trade.side == "long" and current_price - trade.entry_price >= trigger_distance:
            trade.virtual_stop_loss = max(trade.virtual_stop_loss, trade.entry_price)
            trade.break_even_armed = True
        elif trade.side == "short" and trade.entry_price - current_price >= trigger_distance:
            trade.virtual_stop_loss = min(trade.virtual_stop_loss, trade.entry_price)
            trade.break_even_armed = True

    def _apply_trailing_stop(self, trade: VirtualTrade, current_price: float) -> None:
        del current_price
        if not trade.allow_trailing_stop:
            return
        trailing_distance = max(0.0, float(trade.trailing_stop_distance or trade.stop_distance or 0.0))
        if trailing_distance <= 0.0:
            return
        if trade.side == "long":
            candidate = trade.highest_price - trailing_distance
            if trade.break_even_armed:
                candidate = max(candidate, trade.entry_price)
            if candidate > trade.virtual_stop_loss:
                trade.virtual_stop_loss = candidate
        else:
            candidate = trade.lowest_price + trailing_distance
            if trade.break_even_armed:
                candidate = min(candidate, trade.entry_price)
            if candidate < trade.virtual_stop_loss:
                trade.virtual_stop_loss = candidate

    @staticmethod
    def _hit_stop(trade: VirtualTrade, current_price: float) -> bool:
        if trade.side == "long":
            return current_price <= trade.virtual_stop_loss
        return current_price >= trade.virtual_stop_loss

    @staticmethod
    def _hit_take_profit(trade: VirtualTrade, current_price: float) -> bool:
        if trade.side == "long":
            return current_price >= trade.virtual_take_profit
        return current_price <= trade.virtual_take_profit

    def _refresh_closing_state(self, trade: VirtualTrade, now: datetime) -> None:
        if trade.state != "closing" or trade.close_requested_at is None:
            return
        age = (now - trade.close_requested_at).total_seconds()
        if age >= self.close_retry_seconds:
            trade.state = "open"
            trade.close_requested_at = None

    @staticmethod
    def _calculate_pnl(trade: VirtualTrade, exit_price: float) -> float:
        if trade.side == "long":
            return (exit_price - trade.entry_price) * trade.position_size
        return (trade.entry_price - exit_price) * trade.position_size
