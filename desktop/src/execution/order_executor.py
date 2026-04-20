from __future__ import annotations

import asyncio
import logging
import time
from uuid import uuid4

from execution.virtual_trade_manager import VirtualTradeManager
from sopotek.broker.base import BaseBroker
from sopotek.core.event_bus import AsyncEventBus
from sopotek.core.event_types import EventType
from sopotek.core.models import ClosePositionRequest, ExecutionReport, OrderIntent, TradeReview


class OrderExecutor:
    """Executes approved trades without exposing stop-loss or take-profit to the broker."""

    def __init__(
        self,
        broker: BaseBroker,
        event_bus: AsyncEventBus,
        virtual_trade_manager: VirtualTradeManager,
        *,
        max_retries: int = 2,
        logger: logging.Logger | None = None,
    ) -> None:
        self.broker = broker
        self.bus = event_bus
        self.virtual_trade_manager = virtual_trade_manager
        self.max_retries = max(1, int(max_retries))
        self.logger = logger or logging.getLogger("OrderExecutor")

        self.bus.subscribe(EventType.RISK_APPROVED, self._on_risk_approved)
        self.bus.subscribe(EventType.CLOSE_POSITION, self._on_close_position)

    async def _on_risk_approved(self, event) -> None:
        review = getattr(event, "data", None)
        if review is None:
            return
        if not isinstance(review, TradeReview):
            review = TradeReview(**dict(review))
        report = await self.execute_review(review)
        await self._publish_execution_events(report)

    async def _on_close_position(self, event) -> None:
        request = getattr(event, "data", None)
        if request is None:
            return
        if not isinstance(request, ClosePositionRequest):
            request = ClosePositionRequest(**dict(request))
        report = await self.execute_close_request(request)
        await self._publish_execution_events(report)

    async def execute_review(self, review: TradeReview) -> ExecutionReport:
        metadata = dict(review.metadata or {})
        virtual_stop = metadata.get("virtual_stop_loss", review.stop_price)
        virtual_take_profit = metadata.get("virtual_take_profit", review.take_profit)
        if virtual_stop is None or virtual_take_profit is None:
            return self._failed_report(
                symbol=review.symbol,
                side=review.side,
                quantity=review.quantity,
                requested_price=review.price,
                strategy_name=review.strategy_name,
                metadata={**metadata, "error": "Virtual stop loss and take profit are required"},
                timestamp=review.timestamp,
                status="rejected_missing_virtual_exit",
            )

        trade_id = str(metadata.get("trade_id") or uuid4().hex)
        order = OrderIntent(
            symbol=review.symbol,
            side=review.side,
            quantity=float(review.quantity),
            price=review.price,
            order_type="market",
            stop_price=None,
            take_profit=None,
            strategy_name=review.strategy_name,
            metadata={
                **metadata,
                "trade_id": trade_id,
                "virtual_stop_loss": float(virtual_stop),
                "virtual_take_profit": float(virtual_take_profit),
                "close_position": False,
            },
        )

        start = time.perf_counter()
        raw, error = await self._submit_order(order)
        if error is not None:
            return self._failed_report(
                symbol=review.symbol,
                side=review.side,
                quantity=review.quantity,
                requested_price=review.price,
                strategy_name=review.strategy_name,
                metadata={**order.metadata, "error": str(error)},
                timestamp=review.timestamp,
            )

        latency_ms = (time.perf_counter() - start) * 1000.0
        fill_price = self._extract_fill_price(raw, fallback=review.price)
        stop_distance = float(metadata.get("stop_distance") or abs(fill_price - float(virtual_stop)))
        risk_reward_ratio = float(metadata.get("risk_reward_ratio") or self._derive_risk_reward(fill_price, float(virtual_stop), float(virtual_take_profit)))
        rebased_stop, rebased_take_profit = self._rebase_virtual_levels(
            side=review.side,
            fill_price=fill_price,
            stop_distance=stop_distance,
            risk_reward_ratio=risk_reward_ratio,
            fallback_stop=float(virtual_stop),
            fallback_take_profit=float(virtual_take_profit),
        )
        report = ExecutionReport(
            order_id=str((raw or {}).get("id") or trade_id),
            symbol=review.symbol,
            side=review.side,
            quantity=float(review.quantity),
            requested_price=review.price,
            fill_price=fill_price,
            status=str((raw or {}).get("status") or "filled"),
            latency_ms=float((raw or {}).get("latency_ms") or latency_ms),
            slippage_bps=float((raw or {}).get("slippage_bps") or self._slippage_bps(review.price, fill_price, review.side)),
            strategy_name=review.strategy_name,
            stop_price=rebased_stop,
            take_profit=rebased_take_profit,
            filled_quantity=self._extract_quantity(raw, fallback=review.quantity),
            remaining_quantity=float((raw or {}).get("remaining_quantity") or 0.0),
            partial=bool((raw or {}).get("partial") or float((raw or {}).get("remaining_quantity") or 0.0) > 0.0),
            fee=float((raw or {}).get("fee") or 0.0),
            metadata={
                **order.metadata,
                "virtual_stop_loss": rebased_stop,
                "virtual_take_profit": rebased_take_profit,
                "stop_distance": stop_distance,
                "risk_reward_ratio": risk_reward_ratio,
                "raw": raw or {},
            },
            timestamp=review.timestamp,
        )
        if str(report.status).lower() not in {"failed", "rejected"}:
            await self.virtual_trade_manager.register_entry(report)
        return report

    async def execute_close_request(self, request: ClosePositionRequest) -> ExecutionReport:
        metadata = {
            **dict(request.metadata or {}),
            "close_position": True,
            "close_reason": request.reason,
        }
        order_id = str(metadata.get("trade_id") or uuid4().hex)
        order = OrderIntent(
            symbol=request.symbol,
            side=request.side,
            quantity=float(request.quantity),
            price=request.price,
            order_type="market",
            stop_price=None,
            take_profit=None,
            strategy_name=request.strategy_name,
            metadata=metadata,
        )

        start = time.perf_counter()
        raw, error = await self._submit_order(order)
        if error is not None:
            return self._failed_report(
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                requested_price=request.price,
                strategy_name=request.strategy_name,
                metadata={**metadata, "error": str(error)},
                timestamp=request.timestamp,
            )

        latency_ms = (time.perf_counter() - start) * 1000.0
        return ExecutionReport(
            order_id=str((raw or {}).get("id") or order_id),
            symbol=request.symbol,
            side=request.side,
            quantity=float(request.quantity),
            requested_price=request.price,
            fill_price=self._extract_fill_price(raw, fallback=request.price),
            status=str((raw or {}).get("status") or "filled"),
            latency_ms=float((raw or {}).get("latency_ms") or latency_ms),
            slippage_bps=float((raw or {}).get("slippage_bps") or 0.0),
            strategy_name=request.strategy_name,
            stop_price=request.stop_price,
            take_profit=request.take_profit,
            filled_quantity=self._extract_quantity(raw, fallback=request.quantity),
            remaining_quantity=float((raw or {}).get("remaining_quantity") or 0.0),
            partial=bool((raw or {}).get("partial") or float((raw or {}).get("remaining_quantity") or 0.0) > 0.0),
            fee=float((raw or {}).get("fee") or 0.0),
            metadata={**metadata, "raw": raw or {}},
            timestamp=request.timestamp,
        )

    async def _submit_order(self, order: OrderIntent) -> tuple[dict | None, Exception | None]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                raw = await self.broker.place_order(order)
                return raw if isinstance(raw, dict) else dict(raw or {}), None
            except Exception as exc:
                last_error = exc
                self.logger.warning("Order attempt %s failed for %s: %s", attempt, order.symbol, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(0)
        return None, last_error

    async def _publish_execution_events(self, report: ExecutionReport) -> None:
        await self.bus.publish(EventType.ORDER_UPDATE, report, priority=78, source="order_executor")
        status = str(report.status).lower()
        if status not in {"failed", "rejected", "rejected_missing_virtual_exit", "rejected_market_hours"}:
            if report.partial:
                await self.bus.publish(EventType.ORDER_PARTIALLY_FILLED, report, priority=79, source="order_executor")
            await self.bus.publish(EventType.ORDER_FILLED, report, priority=80, source="order_executor")
        await self.bus.publish(EventType.EXECUTION_REPORT, report, priority=85, source="order_executor")

    def _failed_report(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        requested_price: float | None,
        strategy_name: str,
        metadata: dict,
        timestamp,
        status: str = "failed",
    ) -> ExecutionReport:
        return ExecutionReport(
            order_id=str(metadata.get("trade_id") or uuid4().hex),
            symbol=symbol,
            side=side,
            quantity=float(quantity),
            requested_price=requested_price,
            fill_price=None,
            status=status,
            latency_ms=0.0,
            strategy_name=strategy_name,
            metadata=metadata,
            timestamp=timestamp,
        )

    @staticmethod
    def _extract_fill_price(payload, *, fallback):
        if not isinstance(payload, dict):
            return fallback
        for key in ("fill_price", "average", "price", "avgPrice", "last"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except Exception:
                continue
        return fallback

    @staticmethod
    def _extract_quantity(payload, *, fallback):
        if not isinstance(payload, dict):
            return float(fallback)
        for key in ("filled_quantity", "filled", "amount", "executedQty", "quantity"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except Exception:
                continue
        return float(fallback)

    @staticmethod
    def _slippage_bps(requested_price, fill_price, side: str) -> float:
        try:
            requested = float(requested_price)
            filled = float(fill_price)
        except Exception:
            return 0.0
        if requested <= 0:
            return 0.0
        raw_bps = ((filled - requested) / requested) * 10000.0
        return raw_bps if str(side).lower() == "buy" else -raw_bps

    @staticmethod
    def _derive_risk_reward(entry_price: float, stop_loss: float, take_profit: float) -> float:
        risk = abs(float(entry_price) - float(stop_loss))
        reward = abs(float(take_profit) - float(entry_price))
        if risk <= 0.0:
            return 0.0
        return reward / risk

    @staticmethod
    def _rebase_virtual_levels(
        *,
        side: str,
        fill_price: float,
        stop_distance: float,
        risk_reward_ratio: float,
        fallback_stop: float,
        fallback_take_profit: float,
    ) -> tuple[float, float]:
        if stop_distance <= 0.0:
            return fallback_stop, fallback_take_profit
        direction = 1.0 if str(side).lower() == "buy" else -1.0
        stop_price = fill_price - (direction * stop_distance)
        take_profit = fill_price + (direction * stop_distance * max(0.0, risk_reward_ratio))
        return stop_price, take_profit
