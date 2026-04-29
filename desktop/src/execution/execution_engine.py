from __future__ import annotations

"""
InvestPro ExecutionEngine

Central execution engine enforcing:

    Strategy / Signal
        -> RiskEngine approval
        -> ExecutionEngine queue
        -> SmartRouter / Broker
        -> OrderManager lifecycle
        -> ExecutionReport events

Designed for live trading, paper trading, backtesting parity, and broker abstraction.
"""

import asyncio
import contextlib
import inspect
import json
import logging
import math
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

try:
    from core.regime_engine_config import ExecutionConfig
except Exception:  # pragma: no cover
    @dataclass(slots=True)
    class ExecutionConfig:  # type: ignore
        base_latency_ms: float = 35.0
        max_slippage_bps: float = 20.0
        partial_fill_threshold_notional: float = 25_000.0
        twap_slices: int = 4
        vwap_default_buckets: int = 4


try:
    from events.event_bus import AsyncEventBus
except Exception:  # pragma: no cover
    AsyncEventBus = Any  # type: ignore


try:
    from events.event_bus.event_types import EventType
except Exception:  # pragma: no cover
    class EventType:  # type: ignore
        RISK_APPROVED = "risk.approved"
        CLOSE_POSITION = "close.position"
        ORDER_SUBMITTED = "order.submitted"
        ORDER_UPDATE = "order.update"
        ORDER_EVENT = "order.event"
        ORDER_EXECUTED = "order.executed"
        ORDER_PARTIALLY_FILLED = "order.partially_filled"
        ORDER_FILLED = "order.filled"
        ORDER_REJECTED = "order.rejected"
        ORDER_FAILED = "order.failed"
        EXECUTION_REPORT = "execution.report"


try:
    from execution.order_manager import ManagedOrder, OrderManager
except Exception:  # pragma: no cover
    @dataclass(slots=True)
    class ManagedOrder:  # type: ignore
        order_id: str
        symbol: str
        side: str
        quantity: float
        order_type: str = "market"
        status: str = "pending"
        filled_quantity: float = 0.0
        average_price: float = 0.0
        metadata: dict[str, Any] = field(default_factory=dict)

    class OrderManager:  # type: ignore
        def __init__(self) -> None:
            self.orders: dict[str, ManagedOrder] = {}

        def register(self, order: ManagedOrder) -> ManagedOrder:
            self.orders[order.order_id] = order
            return order

        def update(self, order_id: str, **updates: Any) -> ManagedOrder | None:
            order = self.orders.get(order_id)
            if order is None:
                return None
            for key, value in updates.items():
                with contextlib.suppress(Exception):
                    setattr(order, key, value)
            return order


try:
    from execution.smart_router import SmartRouter
except Exception:  # pragma: no cover
    class SmartRouter:  # type: ignore
        def __init__(self, broker: Any, *, twap_slices: int = 4, vwap_buckets: int = 4) -> None:
            self.broker = broker

        async def execute(self, order: dict[str, Any]) -> dict[str, Any]:
            if hasattr(self.broker, "create_order"):
                result = self.broker.create_order(
                    order.get("symbol"),
                    order.get("type", "market"),
                    order.get("side"),
                    order.get("amount"),
                    order.get("price"),
                    order.get("params") or {},
                )
                if inspect.isawaitable(result):
                    result = await result
                return dict(result or {})
            if hasattr(self.broker, "place_order"):
                result = self.broker.place_order(order)
                if inspect.isawaitable(result):
                    result = await result
                return dict(result or {})
            raise RuntimeError("Broker has no supported order method.")


try:
    from portfolio.capital_allocator import CapitalAllocationPlan
except Exception:  # pragma: no cover
    @dataclass(slots=True)
    class CapitalAllocationPlan:  # type: ignore
        symbol: str
        side: str
        target_quantity: float
        target_notional: float = 0.0
        portfolio_weight: float = 0.0
        risk_estimate: float = 0.0
        strategy_name: str = "unknown"
        metadata: dict[str, Any] = field(default_factory=dict)


try:
    from risk.risk_engine import TradeReview
except Exception:  # pragma: no cover
    @dataclass(slots=True)
    class TradeReview:  # type: ignore
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
        timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


try:
    from models.signal import ClosePositionRequest
except Exception:  # pragma: no cover
    @dataclass(slots=True)
    class ClosePositionRequest:  # type: ignore
        symbol: str
        side: str
        quantity: float
        price: float = 0.0
        reason: str = "Close position"
        strategy_name: str = "ClosePosition"
        stop_price: float | None = None
        take_profit: float | None = None
        metadata: dict[str, Any] = field(default_factory=dict)
        timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: float
    price: float = 0.0
    order_type: str = "market"
    stop_price: float | None = None
    take_profit: float | None = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    order_id: str
    symbol: str
    side: str
    quantity: float
    requested_price: float
    fill_price: float
    status: str
    latency_ms: float = 0.0
    slippage_bps: float = 0.0
    strategy_name: str = "unknown"
    stop_price: float | None = None
    take_profit: float | None = None
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    partial: bool = False
    fee: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def filled_notional(self) -> float:
        return abs(float(self.filled_quantity or 0.0) * float(self.fill_price or 0.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "requested_price": self.requested_price,
            "fill_price": self.fill_price,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "slippage_bps": self.slippage_bps,
            "strategy_name": self.strategy_name,
            "stop_price": self.stop_price,
            "take_profit": self.take_profit,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "partial": self.partial,
            "fee": self.fee,
            "filled_notional": self.filled_notional,
            "metadata": _json_safe(self.metadata),
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
        }


class OrderLifecycle(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionEngine:
    """Central execution engine enforcing Risk -> Execution -> Broker."""

    def __init__(
        self,
        broker: Any,
        event_bus: AsyncEventBus | None = None,
        *,
        router: SmartRouter | Mapping[str, SmartRouter] | None = None,
        order_manager: OrderManager | None = None,
        config: ExecutionConfig | None = None,
        listen_event_type: str = EventType.RISK_APPROVED,
        queue_maxsize: int = 512,
        worker_count: int = 1,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.0,
        paper_mode: bool = False,
        market_hours_engine: Any = None,
        default_asset_type: str | None = None,
        require_high_liquidity_for_forex: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config or ExecutionConfig()
        self.bus = event_bus
        self.listen_event_type = str(listen_event_type or EventType.RISK_APPROVED)
        self.logger = logger or logging.getLogger("ExecutionEngine")
        self.order_manager = order_manager or OrderManager()
        self.paper_mode = bool(paper_mode)
        self.max_retries = max(1, int(max_retries or 1))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds or 0.0))
        self.market_hours_engine = market_hours_engine
        self.default_asset_type = default_asset_type
        self.require_high_liquidity_for_forex = bool(require_high_liquidity_for_forex)

        self._sequence = 0
        self._queue: asyncio.PriorityQueue[tuple[int, int, Any]] = asyncio.PriorityQueue(
            maxsize=max(0, int(queue_maxsize or 0))
        )
        self._workers: list[asyncio.Task[None]] = []
        self._worker_count = max(1, int(worker_count or 1))
        self._shutdown = False

        self.brokers = self._normalize_brokers(broker)
        self.default_broker_name = next(iter(self.brokers))

        self.routers: dict[str, SmartRouter] = self._build_routers(router)

        self.submitted_count = 0
        self.completed_count = 0
        self.failed_count = 0
        self.rejected_count = 0
        self.last_report: ExecutionReport | None = None
        self.last_error: str = ""

        if self.bus is not None:
            self._subscribe_bus()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _subscribe_bus(self) -> None:
        subscribe = getattr(self.bus, "subscribe", None)
        if not callable(subscribe):
            return

        try:
            result = subscribe(self.listen_event_type, self._on_risk_approved)
            if inspect.isawaitable(result):
                # Cannot await inside __init__; event bus should usually be sync subscribe.
                pass
        except Exception:
            self.logger.debug("ExecutionEngine failed to subscribe to risk topic", exc_info=True)

        try:
            subscribe(EventType.CLOSE_POSITION, self._on_close_position)
        except Exception:
            self.logger.debug("ExecutionEngine failed to subscribe to close position topic", exc_info=True)

    async def start(self) -> None:
        if self._workers:
            return

        self._shutdown = False

        for index in range(self._worker_count):
            self._workers.append(
                asyncio.create_task(
                    self._worker_loop(),
                    name=f"execution-worker-{index + 1}",
                )
            )

    async def shutdown(self) -> None:
        await self.flush()
        self._shutdown = True

        workers = list(self._workers)
        self._workers.clear()

        for task in workers:
            task.cancel()

        for task in workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def flush(self) -> None:
        await self._queue.join()

    @property
    def queue_depth(self) -> int:
        return int(self._queue.qsize())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_risk_approved(self, event: Any) -> None:
        review = getattr(event, "data", event)

        if review is None:
            return

        review = self._coerce_trade_review(review)

        if not bool(getattr(review, "approved", False)):
            return

        await self.enqueue(review, priority=int(getattr(event, "priority", 70) or 70))

    async def _on_close_position(self, event: Any) -> None:
        request = getattr(event, "data", event)

        if request is None:
            return

        request = self._coerce_close_request(request)
        await self.enqueue(request, priority=int(getattr(event, "priority", 75) or 75))

    async def enqueue(self, payload: TradeReview | ClosePositionRequest | Mapping[str, Any], *, priority: int = 70) -> None:
        await self.start()

        if isinstance(payload, Mapping):
            if self._mapping_looks_like_close_request(payload):
                payload = self._coerce_close_request(payload)
            else:
                payload = self._coerce_trade_review(payload)

        self._sequence += 1
        await self._queue.put((int(priority), int(self._sequence), payload))
        self._log("execution_enqueued", priority=priority, queue_depth=self.queue_depth)

    async def _worker_loop(self) -> None:
        while True:
            _, _, payload = await self._queue.get()

            try:
                if isinstance(payload, ClosePositionRequest) or self._looks_like_close_request(payload):
                    report = await self.execute_close_request(self._coerce_close_request(payload))
                else:
                    report = await self.execute_review(
                        review=self._coerce_trade_review(payload),
                        order_type="market",
                        paper_mode=self.paper_mode,
                    )

                await self._publish_execution_events(report)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.failed_count += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.logger.exception("execution_worker_failed error=%s", exc)
            finally:
                self._queue.task_done()

    # ------------------------------------------------------------------
    # Main execution API
    # ------------------------------------------------------------------

    async def execute(
        self,
        plan: CapitalAllocationPlan | TradeReview | Mapping[str, Any],
        *,
        price: float | None = None,
        order_type: str = "market",
        paper_mode: bool | None = None,
    ) -> dict[str, Any] | ExecutionReport:
        if isinstance(plan, TradeReview) or self._looks_like_trade_review(plan):
            return await self.execute_review(
                self._coerce_trade_review(plan),
                order_type=order_type,
                paper_mode=paper_mode,
            )

        if isinstance(plan, Mapping):
            payload = dict(plan)
            if {"approved", "symbol", "side", "quantity", "price", "reason"} <= set(payload):
                return await self.execute_review(
                    self._coerce_trade_review(payload),
                    order_type=order_type,
                    paper_mode=paper_mode,
                )

        if price is None:
            raise TypeError(
                "ExecutionEngine.execute() requires 'price' when called with a capital allocation plan."
            )

        report = await self.execute_plan(
            plan,  # type: ignore[arg-type]
            price=float(price),
            order_type=order_type,
            paper_mode=paper_mode,
        )
        return self._report_to_payload(report)

    async def execute_plan(
        self,
        plan: CapitalAllocationPlan,
        *,
        price: float,
        order_type: str = "market",
        paper_mode: bool | None = None,
    ) -> ExecutionReport:
        review = TradeReview(
            approved=True,
            symbol=str(plan.symbol),
            side=str(plan.side),
            quantity=float(plan.target_quantity or 0.0),
            price=float(price or 0.0),
            reason="Approved capital allocation plan",
            strategy_name=str(getattr(plan, "strategy_name", "CapitalAllocation")),
            metadata={
                **dict(getattr(plan, "metadata", {}) or {}),
                "target_notional": float(getattr(plan, "target_notional", 0.0) or 0.0),
                "portfolio_weight": float(getattr(plan, "portfolio_weight", 0.0) or 0.0),
                "risk_estimate": float(getattr(plan, "risk_estimate", 0.0) or 0.0),
            },
        )
        return await self.execute_review(review, order_type=order_type, paper_mode=paper_mode)

    async def execute_review(
        self,
        review: TradeReview,
        *,
        order_type: str = "market",
        paper_mode: bool | None = None,
    ) -> ExecutionReport:
        review = self._coerce_trade_review(review)

        if not bool(review.approved):
            report = self._rejected_report(
                order_id=str(self._metadata(review).get("order_id") or uuid4().hex),
                broker_name=self.default_broker_name,
                review=review,
                reason=f"TradeReview was not approved: {review.reason}",
                status="rejected",
            )
            self._update_order_state(report)
            self.rejected_count += 1
            self.last_report = report
            return report

        destination = self._resolve_destination(self._metadata(review))

        if destination not in self.brokers:
            report = self._rejected_report(
                order_id=str(self._metadata(review).get("order_id") or uuid4().hex),
                broker_name=self.default_broker_name,
                review=review,
                reason=f"Unknown broker destination: {destination}",
                status="rejected",
            )
            self._update_order_state(report)
            self.rejected_count += 1
            self.last_report = report
            return report

        broker = self.brokers[destination]
        order_id = str(self._metadata(review).get("order_id") or uuid4().hex)

        validation_error = self._validate_review(review)
        if validation_error:
            report = self._rejected_report(
                order_id=order_id,
                broker_name=destination,
                review=review,
                reason=validation_error,
                status="rejected",
            )
            self._update_order_state(report)
            self.rejected_count += 1
            self.last_report = report
            return report

        market_hours_rejection = self._market_hours_rejection_report(
            order_id=order_id,
            broker_name=destination,
            review=review,
        )
        if market_hours_rejection is not None:
            self._register_order(
                order_id=order_id,
                review=review,
                order_type=order_type,
                status=OrderLifecycle.REJECTED.value,
                broker_name=destination,
            )
            self._update_order_state(market_hours_rejection)
            self.rejected_count += 1
            self.last_report = market_hours_rejection
            self._log(
                "execution_rejected_market_hours",
                order_id=market_hours_rejection.order_id,
                symbol=market_hours_rejection.symbol,
                side=market_hours_rejection.side,
                broker=destination,
            )
            return market_hours_rejection

        lifecycle = self._register_order(
            order_id=order_id,
            review=review,
            order_type=order_type,
            status=OrderLifecycle.PENDING.value,
            broker_name=destination,
        )

        await self._publish_order_submitted(lifecycle, review, broker_name=destination)

        requested_price = _safe_float(review.price, 0.0)

        raw = await self._submit_order(
            broker_name=destination,
            broker=broker,
            order_id=order_id,
            symbol=str(review.symbol),
            side=str(review.side),
            quantity=float(review.quantity or 0.0),
            price=requested_price,
            order_type=str(order_type or "market"),
            stop_price=getattr(review, "stop_price", None),
            take_profit=getattr(review, "take_profit", None),
            strategy_name=str(getattr(review, "strategy_name", "unknown") or "unknown"),
            metadata=self._metadata(review),
            paper_mode=self.paper_mode if paper_mode is None else bool(paper_mode),
        )

        report = self._build_report(
            raw=raw,
            order_id=order_id,
            broker_name=destination,
            review=review,
        )
        self._update_order_state(report)
        self._record_report(report)

        self._log(
            "execution_completed",
            order_id=report.order_id,
            symbol=report.symbol,
            side=report.side,
            status=report.status,
            fill_price=report.fill_price,
            filled_quantity=report.filled_quantity,
            broker=destination,
        )

        return report

    def _register_order(
        self,
        *,
        order_id: str,
        review: TradeReview,
        order_type: str,
        status: str,
        broker_name: str,
    ) -> ManagedOrder:
        order = ManagedOrder(
            order_id=order_id,
            symbol=str(review.symbol),
            side=str(review.side),
            quantity=float(review.quantity or 0.0),
            order_type=str(order_type or "market"),
            status=status,
            metadata={**self._metadata(review), "broker": broker_name},
        )
        self.order_manager.register(order)
        return order

    # ------------------------------------------------------------------
    # Market hours / close request
    # ------------------------------------------------------------------

    def _market_hours_rejection_report(
        self,
        *,
        order_id: str,
        broker_name: str,
        review: TradeReview,
    ) -> ExecutionReport | None:
        if self.market_hours_engine is None:
            return None

        evaluate = getattr(self.market_hours_engine, "evaluate_trade_window", None)
        if not callable(evaluate):
            return None

        decision = evaluate(
            asset_type=self.default_asset_type,
            symbol=review.symbol,
            metadata={**self._metadata(review), "symbol": review.symbol},
            now=getattr(review, "timestamp", datetime.now(timezone.utc)),
            require_high_liquidity=self.require_high_liquidity_for_forex,
        )

        if bool(getattr(decision, "trade_allowed", False)):
            return None

        reason = str(getattr(decision, "reason", "Market hours rejected trade"))

        metadata = {
            **self._metadata(review),
            "broker": broker_name,
            "error": reason,
        }

        if hasattr(decision, "to_metadata") and callable(decision.to_metadata):
            with contextlib.suppress(Exception):
                metadata["market_hours"] = decision.to_metadata()

        return ExecutionReport(
            order_id=order_id,
            symbol=str(review.symbol),
            side=str(review.side),
            quantity=float(review.quantity or 0.0),
            requested_price=float(review.price or 0.0),
            fill_price=float(review.price or 0.0),
            status="rejected_market_hours",
            latency_ms=0.0,
            slippage_bps=0.0,
            strategy_name=str(getattr(review, "strategy_name", "unknown") or "unknown"),
            stop_price=getattr(review, "stop_price", None),
            take_profit=getattr(review, "take_profit", None),
            filled_quantity=0.0,
            remaining_quantity=float(review.quantity or 0.0),
            partial=False,
            fee=0.0,
            metadata=metadata,
            timestamp=getattr(review, "timestamp", datetime.now(timezone.utc)),
        )

    async def execute_close_request(self, request: ClosePositionRequest) -> ExecutionReport:
        request = self._coerce_close_request(request)

        review = TradeReview(
            approved=True,
            symbol=str(request.symbol),
            side=str(request.side),
            quantity=float(request.quantity or 0.0),
            price=float(getattr(request, "price", 0.0) or 0.0),
            reason=str(getattr(request, "reason", "Close position") or "Close position"),
            strategy_name=str(getattr(request, "strategy_name", "ClosePosition") or "ClosePosition"),
            stop_price=getattr(request, "stop_price", None),
            take_profit=getattr(request, "take_profit", None),
            metadata={
                **dict(getattr(request, "metadata", {}) or {}),
                "close_position": True,
                "close_reason": str(getattr(request, "reason", "Close position") or "Close position"),
            },
            timestamp=getattr(request, "timestamp", datetime.now(timezone.utc)),
        )
        return await self.execute_review(review)

    # ------------------------------------------------------------------
    # Broker submission
    # ------------------------------------------------------------------

    async def _submit_order(
        self,
        *,
        broker_name: str,
        broker: Any,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_type: str,
        stop_price: float | None,
        take_profit: float | None,
        strategy_name: str,
        metadata: dict[str, Any],
        paper_mode: bool,
    ) -> dict[str, Any]:
        payload = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": quantity,
            "quantity": quantity,
            "price": price,
            "expected_price": price,
            "type": order_type,
            "order_type": order_type,
            "stop_price": stop_price,
            "take_profit": take_profit,
            "strategy_name": strategy_name,
            "broker": broker_name,
            "liquidity_score": _safe_float(
                (metadata.get("regime") or {}).get("liquidity_score", metadata.get("liquidity_score", 1.0))
                if isinstance(metadata.get("regime"), Mapping)
                else metadata.get("liquidity_score", 1.0),
                1.0,
            ),
            "metadata": dict(metadata or {}),
            "params": dict(metadata.get("params") or {}),
        }

        if paper_mode:
            simulated = self._simulate_fill(
                order_id=order_id,
                quantity=quantity,
                price=price,
                side=side,
                notional=quantity * price,
            )
            simulated["attempt"] = 1
            return simulated

        last_error: Exception | None = None
        start = time.perf_counter()

        for attempt in range(1, self.max_retries + 1):
            try:
                if broker_name in self.routers:
                    raw = self.routers[broker_name].execute(payload)
                    raw = await _maybe_await(raw)
                else:
                    order = OrderIntent(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        order_type=order_type,
                        stop_price=stop_price,
                        take_profit=take_profit,
                        strategy_name=strategy_name,
                        metadata={**metadata, "order_id": order_id, "broker": broker_name},
                    )
                    raw = await self._place_order_fallback(broker, order, payload)

                raw = dict(raw or {})
                raw.setdefault("id", order_id)
                raw.setdefault("status", "filled")
                raw.setdefault("latency_ms", (time.perf_counter() - start) * 1000.0)

                filled_qty = _safe_float(
                    raw.get("filled_quantity", raw.get("filled", raw.get("executedQty", quantity))),
                    quantity,
                )
                raw["filled_quantity"] = filled_qty
                raw.setdefault("remaining_quantity", max(0.0, quantity - filled_qty))
                raw.setdefault("partial", bool(_safe_float(raw.get("remaining_quantity"), 0.0)))
                raw.setdefault("attempt", attempt)
                return raw

            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "execution_attempt_failed order_id=%s symbol=%s broker=%s attempt=%s error=%s",
                    order_id,
                    symbol,
                    broker_name,
                    attempt,
                    exc,
                )
                if attempt < self.max_retries and self.retry_backoff_seconds > 0.0:
                    await asyncio.sleep(self.retry_backoff_seconds * attempt)

        return {
            "id": order_id,
            "status": "failed",
            "latency_ms": (time.perf_counter() - start) * 1000.0,
            "filled_quantity": 0.0,
            "remaining_quantity": quantity,
            "partial": False,
            "attempt": self.max_retries,
            "error": str(last_error) if last_error is not None else "Unknown execution error",
        }

    async def _place_order_fallback(self, broker: Any, order: OrderIntent, payload: dict[str, Any]) -> dict[str, Any]:
        if hasattr(broker, "place_order") and callable(broker.place_order):
            result = broker.place_order(order)
            return dict(await _maybe_await(result) or {})

        if hasattr(broker, "create_order") and callable(broker.create_order):
            result = broker.create_order(
                order.symbol,
                order.order_type,
                order.side,
                order.quantity,
                order.price if order.price > 0 else None,
                dict(payload.get("params") or {}),
            )
            return dict(await _maybe_await(result) or {})

        if hasattr(broker, "submit_order") and callable(broker.submit_order):
            result = broker.submit_order(payload)
            return dict(await _maybe_await(result) or {})

        raise RuntimeError("Broker has no supported order method: place_order/create_order/submit_order.")

    def _simulate_fill(
        self,
        *,
        order_id: str,
        quantity: float,
        price: float,
        side: str,
        notional: float,
    ) -> dict[str, Any]:
        quantity = max(0.0, float(quantity or 0.0))
        price = max(0.0, float(price or 0.0))
        notional = abs(float(notional or 0.0))

        slippage_bps = min(
            float(self.config.max_slippage_bps),
            max(
                0.5,
                (notional / max(float(self.config.partial_fill_threshold_notional), 1.0)) * 6.0,
            ),
        )

        partial = notional >= float(self.config.partial_fill_threshold_notional)
        fill_multiplier = 1.0 + (
            slippage_bps / 10000.0 if str(side).lower() == "buy" else -(slippage_bps / 10000.0)
        )
        fill_price = price * fill_multiplier if price > 0.0 else price
        filled_quantity = quantity * (0.70 if partial else 1.0)
        remaining_quantity = max(0.0, quantity - filled_quantity)

        return {
            "id": order_id,
            "status": OrderLifecycle.PARTIALLY_FILLED.value if partial else OrderLifecycle.FILLED.value,
            "price": price,
            "fill_price": fill_price,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "partial": partial,
            "slippage_bps": slippage_bps,
            "latency_ms": float(self.config.base_latency_ms),
            "fee": 0.0,
            "paper_mode": True,
        }

    # ------------------------------------------------------------------
    # Report and events
    # ------------------------------------------------------------------

    def _build_report(
        self,
        *,
        raw: Mapping[str, Any],
        order_id: str,
        broker_name: str,
        review: TradeReview,
    ) -> ExecutionReport:
        fill_price = self._extract_fill_price(raw, fallback=review.price)
        filled_quantity = self._extract_quantity(raw, fallback=0.0 if str(raw.get("status")) == "failed" else review.quantity)
        remaining_quantity = max(
            0.0,
            _safe_float(raw.get("remaining_quantity"), max(0.0, float(review.quantity or 0.0) - filled_quantity)),
        )
        partial = bool(raw.get("partial") or remaining_quantity > 0.0)
        fee = self._extract_fee(raw)
        status = str(raw.get("status") or (OrderLifecycle.PARTIALLY_FILLED.value if partial else OrderLifecycle.FILLED.value))

        return ExecutionReport(
            order_id=str(raw.get("id") or order_id),
            symbol=str(review.symbol),
            side=str(review.side),
            quantity=float(review.quantity or 0.0),
            requested_price=float(review.price or 0.0),
            fill_price=float(fill_price or 0.0),
            status=status,
            latency_ms=_safe_float(raw.get("latency_ms"), float(self.config.base_latency_ms)),
            slippage_bps=_safe_float(raw.get("slippage_bps"), self._slippage_bps(review.price, fill_price, review.side)),
            strategy_name=str(getattr(review, "strategy_name", "unknown") or "unknown"),
            stop_price=getattr(review, "stop_price", None),
            take_profit=getattr(review, "take_profit", None),
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            partial=partial,
            fee=fee,
            metadata={
                **self._metadata(review),
                "broker": broker_name,
                "raw": dict(raw or {}),
            },
            timestamp=getattr(review, "timestamp", datetime.now(timezone.utc)),
        )

    async def _publish_order_submitted(self, order: ManagedOrder, review: TradeReview, *, broker_name: str) -> None:
        self.order_manager.update(order.order_id, status=OrderLifecycle.SUBMITTED.value)

        self.submitted_count += 1

        if self.bus is None:
            return

        await self._publish(
            EventType.ORDER_SUBMITTED,
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": float(order.quantity),
                "remaining_quantity": float(order.quantity),
                "strategy_name": getattr(review, "strategy_name", "unknown"),
                "status": OrderLifecycle.SUBMITTED.value,
                "broker": broker_name,
            },
            priority=75,
            source="execution_engine",
        )

    async def _publish_execution_events(self, report: ExecutionReport) -> None:
        if self.bus is None:
            return

        status = str(report.status).lower()

        await self._publish(EventType.ORDER_UPDATE, report, priority=78, source="execution_engine")
        await self._publish(EventType.ORDER_EVENT, self._report_to_payload(report), priority=79, source="execution_engine")
        await self._publish(EventType.ORDER_EXECUTED, report, priority=79, source="execution_engine")

        if status in {OrderLifecycle.REJECTED.value, "rejected_market_hours"}:
            await self._publish(getattr(EventType, "ORDER_REJECTED", "order.rejected"), report, priority=80, source="execution_engine")
        elif status == OrderLifecycle.FAILED.value:
            await self._publish(getattr(EventType, "ORDER_FAILED", "order.failed"), report, priority=80, source="execution_engine")
        elif status == OrderLifecycle.PARTIALLY_FILLED.value or report.partial:
            await self._publish(EventType.ORDER_PARTIALLY_FILLED, report, priority=79, source="execution_engine")
        elif status == OrderLifecycle.FILLED.value or report.filled_quantity:
            await self._publish(EventType.ORDER_FILLED, report, priority=80, source="execution_engine")

        await self._publish(EventType.EXECUTION_REPORT, report, priority=85, source="execution_engine")

    async def _publish(self, event_type: Any, payload: Any, *, priority: int, source: str) -> None:
        if self.bus is None:
            return

        publish = getattr(self.bus, "publish", None)
        if not callable(publish):
            return

        try:
            try:
                result = publish(event_type, payload, priority=priority, source=source)
            except TypeError:
                result = publish(event_type, payload)

            await _maybe_await(result)

        except Exception as exc:
            self.logger.debug("execution_publish_failed event=%s error=%s", event_type, exc)

    def _update_order_state(self, report: ExecutionReport) -> None:
        status = str(report.status or "").strip().lower()

        if status in {"rejected", "rejected_market_hours"}:
            normalized = OrderLifecycle.REJECTED.value
        elif status in {"failed"}:
            normalized = OrderLifecycle.FAILED.value
        elif report.partial or status == OrderLifecycle.PARTIALLY_FILLED.value:
            normalized = OrderLifecycle.PARTIALLY_FILLED.value
        elif status in {"cancelled", "canceled"}:
            normalized = OrderLifecycle.CANCELLED.value
        else:
            normalized = OrderLifecycle.FILLED.value

        self.order_manager.update(
            report.order_id,
            status=normalized,
            filled_quantity=float(report.filled_quantity or 0.0),
            average_price=float(report.fill_price or report.requested_price or 0.0),
        )

    def _record_report(self, report: ExecutionReport) -> None:
        self.last_report = report
        status = str(report.status or "").lower()

        if status in {OrderLifecycle.FILLED.value, OrderLifecycle.PARTIALLY_FILLED.value} or report.filled_quantity > 0:
            self.completed_count += 1
        elif status in {"rejected", "rejected_market_hours"}:
            self.rejected_count += 1
        elif status == "failed":
            self.failed_count += 1

    # ------------------------------------------------------------------
    # Validation / rejection
    # ------------------------------------------------------------------

    def _validate_review(self, review: TradeReview) -> str:
        if not str(review.symbol or "").strip():
            return "Missing symbol."

        side = str(review.side or "").strip().lower()
        if side not in {"buy", "sell"}:
            return f"Invalid side: {review.side}"

        if float(review.quantity or 0.0) <= 0.0:
            return "Quantity must be positive."

        order_type = str(self._metadata(review).get("order_type") or "").strip().lower()
        if order_type in {"limit", "stop_limit"} and float(review.price or 0.0) <= 0.0:
            return "Limit/stop-limit orders require a positive price."

        return ""

    def _rejected_report(
        self,
        *,
        order_id: str,
        broker_name: str,
        review: TradeReview,
        reason: str,
        status: str,
    ) -> ExecutionReport:
        return ExecutionReport(
            order_id=order_id,
            symbol=str(getattr(review, "symbol", "")),
            side=str(getattr(review, "side", "")),
            quantity=float(getattr(review, "quantity", 0.0) or 0.0),
            requested_price=float(getattr(review, "price", 0.0) or 0.0),
            fill_price=float(getattr(review, "price", 0.0) or 0.0),
            status=status,
            latency_ms=0.0,
            slippage_bps=0.0,
            strategy_name=str(getattr(review, "strategy_name", "unknown") or "unknown"),
            stop_price=getattr(review, "stop_price", None),
            take_profit=getattr(review, "take_profit", None),
            filled_quantity=0.0,
            remaining_quantity=float(getattr(review, "quantity", 0.0) or 0.0),
            partial=False,
            fee=0.0,
            metadata={
                **self._metadata(review),
                "broker": broker_name,
                "error": reason,
            },
            timestamp=getattr(review, "timestamp", datetime.now(timezone.utc)),
        )

    # ------------------------------------------------------------------
    # Coercion helpers
    # ------------------------------------------------------------------

    def _resolve_destination(self, metadata: Mapping[str, Any]) -> str:
        candidates = [
            metadata.get("broker"),
            metadata.get("broker_name"),
            metadata.get("execution_broker"),
            metadata.get("exchange"),
        ]

        for candidate in candidates:
            if candidate is None:
                continue

            key = str(candidate).strip()
            if key in self.brokers:
                return key

            lowered = key.lower()
            for broker_name in self.brokers:
                if broker_name.lower() == lowered:
                    return broker_name

        return self.default_broker_name

    @staticmethod
    def _looks_like_trade_review(value: Any) -> bool:
        if isinstance(value, Mapping):
            return {"approved", "symbol", "side", "quantity", "price", "reason"} <= set(value)
        required = ("approved", "symbol", "side", "quantity", "price", "reason")
        return all(hasattr(value, field_name) for field_name in required)

    @staticmethod
    def _looks_like_close_request(value: Any) -> bool:
        if isinstance(value, Mapping):
            return {"symbol", "side", "quantity", "reason"} <= set(value) and bool(value.get("close_position"))
        required = ("symbol", "side", "quantity", "reason")
        return all(hasattr(value, field_name) for field_name in required) and bool(
            getattr(value, "close_position", True)
        )

    @staticmethod
    def _mapping_looks_like_close_request(value: Mapping[str, Any]) -> bool:
        return bool(value.get("close_position") or value.get("close_reason")) and {
            "symbol",
            "side",
            "quantity",
        } <= set(value)

    @classmethod
    def _coerce_trade_review(cls, value: TradeReview | Mapping[str, Any] | Any) -> TradeReview:
        if isinstance(value, TradeReview):
            return value

        payload = cls._object_payload(value)
        payload = cls._filter_dataclass_payload(TradeReview, payload)

        return TradeReview(**payload)

    @classmethod
    def _coerce_close_request(
        cls,
        value: ClosePositionRequest | Mapping[str, Any] | Any,
    ) -> ClosePositionRequest:
        if isinstance(value, ClosePositionRequest):
            return value

        payload = cls._object_payload(value)
        payload = cls._filter_dataclass_payload(ClosePositionRequest, payload)

        return ClosePositionRequest(**payload)

    @staticmethod
    def _object_payload(value: Mapping[str, Any] | Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "to_dict") and callable(value.to_dict):
            result = value.to_dict()
            if isinstance(result, Mapping):
                return dict(result)
        if hasattr(value, "__dict__"):
            return dict(vars(value))
        raise TypeError(f"Unsupported execution payload: {type(value)!r}")

    @staticmethod
    def _filter_dataclass_payload(cls_type: Any, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            allowed = {item.name for item in fields(cls_type)}
            return {key: value for key, value in dict(payload or {}).items() if key in allowed}
        except Exception:
            return dict(payload or {})

    @staticmethod
    def _normalize_brokers(broker: Any) -> dict[str, Any]:
        if isinstance(broker, Mapping):
            normalized = {
                str(name): value
                for name, value in dict(broker).items()
                if value is not None
            }
            if not normalized:
                raise ValueError("ExecutionEngine requires at least one broker instance.")
            return normalized

        if broker is None:
            raise ValueError("ExecutionEngine requires a broker instance.")

        return {"default": broker}

    def _build_routers(self, router: SmartRouter | Mapping[str, SmartRouter] | None) -> dict[str, SmartRouter]:
        routers: dict[str, SmartRouter] = {}

        if isinstance(router, Mapping):
            for name, item in router.items():
                if item is not None:
                    routers[str(name)] = item
            return routers

        for name, venue in self.brokers.items():
            if router is not None and len(self.brokers) == 1:
                routers[name] = router
            elif hasattr(venue, "create_order") or hasattr(venue, "place_order") or hasattr(venue, "submit_order"):
                routers[name] = SmartRouter(
                    venue,
                    twap_slices=int(getattr(self.config, "twap_slices", 4) or 4),
                    vwap_buckets=int(getattr(self.config, "vwap_default_buckets", 4) or 4),
                )

        return routers

    @staticmethod
    def _metadata(review: TradeReview) -> dict[str, Any]:
        return dict(getattr(review, "metadata", {}) or {})

    # ------------------------------------------------------------------
    # Extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_fill_price(payload: Mapping[str, Any], *, fallback: Any) -> float:
        for key in ("fill_price", "average", "avg_price", "average_price", "price", "avgPrice", "last"):
            value = payload.get(key)
            if value is None:
                continue
            number = _safe_float(value, None)
            if number is not None:
                return float(number)
        return _safe_float(fallback, 0.0)

    @staticmethod
    def _extract_quantity(payload: Mapping[str, Any], *, fallback: Any) -> float:
        for key in ("filled_quantity", "filled", "amount", "executedQty", "executed_qty", "quantity"):
            value = payload.get(key)
            if value is None:
                continue
            number = _safe_float(value, None)
            if number is not None:
                return float(number)
        return _safe_float(fallback, 0.0)

    @staticmethod
    def _extract_fee(payload: Mapping[str, Any]) -> float:
        fee = payload.get("fee")

        if isinstance(fee, Mapping):
            return _safe_float(fee.get("cost") or fee.get("amount"), 0.0)

        if isinstance(fee, list):
            total = 0.0
            for item in fee:
                if isinstance(item, Mapping):
                    total += _safe_float(item.get("cost") or item.get("amount"), 0.0)
            return total

        return _safe_float(fee, 0.0)

    @staticmethod
    def _slippage_bps(requested_price: Any, fill_price: Any, side: str) -> float:
        requested = _safe_float(requested_price, 0.0)
        filled = _safe_float(fill_price, 0.0)

        if requested <= 0.0:
            return 0.0

        raw_bps = ((filled - requested) / requested) * 10000.0
        return raw_bps if side.lower() == "buy" else -raw_bps

    @staticmethod
    def _report_to_payload(report: ExecutionReport) -> dict[str, Any]:
        if hasattr(report, "to_dict") and callable(report.to_dict):
            return report.to_dict()
        return _json_safe(asdict(report))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "queue_depth": self.queue_depth,
            "worker_count": len(self._workers),
            "shutdown": self._shutdown,
            "paper_mode": self.paper_mode,
            "brokers": list(self.brokers.keys()),
            "default_broker_name": self.default_broker_name,
            "routers": list(self.routers.keys()),
            "submitted_count": self.submitted_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "rejected_count": self.rejected_count,
            "last_error": self.last_error,
            "last_report": self.last_report.to_dict() if self.last_report else None,
        }

    def healthy(self) -> bool:
        """Check if the engine is healthy based on failure rates."""
        if self._shutdown:
            return True

        if self.failed_count > max(5, self.completed_count * 2):
            return False

        return True

    def _log(self, event_name: str, **payload: Any) -> None:
        try:
            message = json.dumps(
                {"event": event_name, **_json_safe(payload)},
                default=str,
                sort_keys=True,
            )
        except Exception:
            message = f"{event_name} {payload}"

        self.logger.info(message)


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _safe_float(value: Any, default: Any = 0.0) -> Any:
    if value in (None, ""):
        return default

    try:
        number = float(value)
    except Exception:
        return default

    return number if math.isfinite(number) else default


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value) and not isinstance(value, type):
        try:
            return _json_safe(asdict(value))
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item)
            for item in value
        ]

    return str(value)


__all__ = [
    "ExecutionEngine",
    "ExecutionReport",
    "OrderIntent",
    "OrderLifecycle",
]