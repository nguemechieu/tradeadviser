from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from uuid import uuid4

from core.config import ExecutionConfig
from core.event_bus import AsyncEventBus
from execution.order_manager import ManagedOrder, OrderManager
from execution.smart_router import SmartRouter
from portfolio.capital_allocator import CapitalAllocationPlan
from core.event_bus.event_types import EventType
from core.models import ClosePositionRequest, ExecutionReport, OrderIntent, TradeReview


class OrderLifecycle(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    FAILED = "failed"


class ExecutionEngine:
    """Central execution engine enforcing Strategy -> Risk -> Execution -> Broker."""

    def __init__(
        self,
        broker,
        event_bus: AsyncEventBus | None = None,
        *,
        router: SmartRouter | None = None,
        order_manager: OrderManager | None = None,
        config: ExecutionConfig | None = None,
        listen_event_type: str = EventType.RISK_APPROVED,
        queue_maxsize: int = 512,
        worker_count: int = 1,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.0,
        paper_mode: bool = False,
        market_hours_engine=None,
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
        self._queue: asyncio.PriorityQueue[tuple[int, int, object]] = asyncio.PriorityQueue(maxsize=max(0, int(queue_maxsize)))
        self._workers: list[asyncio.Task[None]] = []
        self._worker_count = max(1, int(worker_count or 1))
        self._shutdown = False

        self.brokers = self._normalize_brokers(broker)
        self.default_broker_name = next(iter(self.brokers))
        self.routers: dict[str, SmartRouter] = {}
        for name, venue in self.brokers.items():
            if hasattr(venue, "create_order"):
                self.routers[name] = router or SmartRouter(
                    venue,
                    twap_slices=self.config.twap_slices,
                    vwap_buckets=self.config.vwap_default_buckets,
                )

        if self.bus is not None:
            self.bus.subscribe(self.listen_event_type, self._on_risk_approved)
            self.bus.subscribe(EventType.CLOSE_POSITION, self._on_close_position)

    async def start(self) -> None:
        if self._workers:
            return
        self._shutdown = False
        for index in range(self._worker_count):
            self._workers.append(asyncio.create_task(self._worker_loop(), name=f"execution-worker-{index + 1}"))

    async def shutdown(self) -> None:
        await self.flush()
        self._shutdown = True
        workers = list(self._workers)
        self._workers.clear()
        for task in workers:
            task.cancel()
        for task in workers:
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def flush(self) -> None:
        await self._queue.join()

    @property
    def queue_depth(self) -> int:
        return int(self._queue.qsize())

    async def _on_risk_approved(self, event) -> None:
        review = getattr(event, "data", None)
        if review is None:
            return
        review = self._coerce_trade_review(review)
        await self.enqueue(review, priority=int(getattr(event, "priority", 70) or 70))

    async def _on_close_position(self, event) -> None:
        request = getattr(event, "data", None)
        if request is None:
            return
        request = self._coerce_close_request(request)
        await self.enqueue(request, priority=int(getattr(event, "priority", 75) or 75))

    async def enqueue(self, payload: TradeReview | ClosePositionRequest, *, priority: int = 70) -> None:
        await self.start()
        self._sequence += 1
        await self._queue.put((int(priority), int(self._sequence), payload))
        self._log("execution_enqueued", priority=priority, queue_depth=self.queue_depth)

    async def _worker_loop(self) -> None:
        while True:
            _, _, payload = await self._queue.get()
            try:
                if isinstance(payload, ClosePositionRequest):
                    report = await self.execute_close_request(payload)
                else:
                    report = await self.execute_review(payload)
                await self._publish_execution_events(report)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.exception("execution_worker_failed error=%s", exc)
            finally:
                self._queue.task_done()

    async def execute(
        self,
        plan: CapitalAllocationPlan | TradeReview | Mapping[str, object],
        *,
        price: float | None = None,
        order_type: str = "market",
        paper_mode: bool | None = None,
    ) -> dict | ExecutionReport:
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
            raise TypeError("ExecutionEngine.execute() requires 'price' when called with a capital allocation plan")
        report = await self.execute_plan(plan, price=float(price), order_type=order_type, paper_mode=paper_mode)
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
            symbol=plan.symbol,
            side=plan.side,
            quantity=float(plan.target_quantity or 0.0),
            price=float(price or 0.0),
            reason="Approved capital allocation plan",
            strategy_name=plan.strategy_name,
            metadata={
                **dict(plan.metadata or {}),
                "target_notional": float(plan.target_notional or 0.0),
                "portfolio_weight": float(plan.portfolio_weight or 0.0),
                "risk_estimate": float(plan.risk_estimate or 0.0),
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
        destination = self._resolve_destination(dict(review.metadata or {}))
        broker = self.brokers[destination]
        order_id = str(review.metadata.get("order_id") or uuid4().hex)
        market_hours_rejection = self._market_hours_rejection_report(
            order_id=order_id,
            broker_name=destination,
            review=review,
        )
        if market_hours_rejection is not None:
            self.order_manager.register(
                ManagedOrder(
                    order_id=order_id,
                    symbol=review.symbol,
                    side=review.side,
                    quantity=float(review.quantity),
                    order_type=str(order_type or "market"),
                    status=OrderLifecycle.REJECTED.value,
                    metadata={**dict(review.metadata or {}), "broker": destination},
                )
            )
            self._update_order_state(market_hours_rejection)
            self._log(
                "execution_rejected_market_hours",
                order_id=market_hours_rejection.order_id,
                symbol=market_hours_rejection.symbol,
                side=market_hours_rejection.side,
                broker=destination,
            )
            return market_hours_rejection
        lifecycle = ManagedOrder(
            order_id=order_id,
            symbol=review.symbol,
            side=review.side,
            quantity=float(review.quantity),
            order_type=str(order_type or "market"),
            status=OrderLifecycle.PENDING.value,
            metadata={**dict(review.metadata or {}), "broker": destination},
        )
        self.order_manager.register(lifecycle)
        await self._publish_order_submitted(lifecycle, review, broker_name=destination)

        requested_price = float(review.price or 0.0)
        raw = await self._submit_order(
            broker_name=destination,
            broker=broker,
            order_id=order_id,
            symbol=review.symbol,
            side=review.side,
            quantity=float(review.quantity or 0.0),
            price=requested_price,
            order_type=str(order_type or "market"),
            stop_price=review.stop_price,
            take_profit=review.take_profit,
            strategy_name=review.strategy_name,
            metadata=dict(review.metadata or {}),
            paper_mode=self.paper_mode if paper_mode is None else bool(paper_mode),
        )
        report = self._build_report(raw=raw, order_id=order_id, broker_name=destination, review=review)
        self._update_order_state(report)
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

    def _market_hours_rejection_report(
        self,
        *,
        order_id: str,
        broker_name: str,
        review: TradeReview,
    ) -> ExecutionReport | None:
        if self.market_hours_engine is None:
            return None
        decision = self.market_hours_engine.evaluate_trade_window(
            asset_type=self.default_asset_type,
            symbol=review.symbol,
            metadata={**dict(review.metadata or {}), "symbol": review.symbol},
            now=review.timestamp,
            require_high_liquidity=self.require_high_liquidity_for_forex,
        )
        if decision.trade_allowed:
            return None
        return ExecutionReport(
            order_id=order_id,
            symbol=review.symbol,
            side=review.side,
            quantity=float(review.quantity),
            requested_price=review.price,
            fill_price=review.price,
            status="rejected_market_hours",
            latency_ms=0.0,
            slippage_bps=0.0,
            strategy_name=review.strategy_name,
            stop_price=review.stop_price,
            take_profit=review.take_profit,
            filled_quantity=0.0,
            remaining_quantity=float(review.quantity),
            partial=False,
            fee=0.0,
            metadata={
                **dict(review.metadata or {}),
                "broker": broker_name,
                "error": decision.reason,
                "market_hours": decision.to_metadata(),
            },
            timestamp=review.timestamp,
        )

    async def execute_close_request(self, request: ClosePositionRequest) -> ExecutionReport:
        review = TradeReview(
            approved=True,
            symbol=request.symbol,
            side=request.side,
            quantity=float(request.quantity or 0.0),
            price=request.price,
            reason=request.reason,
            strategy_name=request.strategy_name,
            stop_price=request.stop_price,
            take_profit=request.take_profit,
            metadata={**dict(request.metadata or {}), "close_position": True, "close_reason": request.reason},
            timestamp=request.timestamp,
        )
        return await self.execute_review(review)

    async def _submit_order(
        self,
        *,
        broker_name: str,
        broker,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_type: str,
        stop_price: float | None,
        take_profit: float | None,
        strategy_name: str,
        metadata: dict,
        paper_mode: bool,
    ) -> dict:
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
            "liquidity_score": float((metadata.get("regime") or {}).get("liquidity_score", metadata.get("liquidity_score", 1.0)) or 1.0),
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
                    raw = await self.routers[broker_name].execute(payload)
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
                    raw = await broker.place_order(order)
                raw = dict(raw or {})
                raw.setdefault("id", order_id)
                raw.setdefault("status", "filled")
                raw.setdefault("latency_ms", (time.perf_counter() - start) * 1000.0)
                raw.setdefault("filled_quantity", float(raw.get("filled") or quantity))
                raw.setdefault("remaining_quantity", max(0.0, quantity - float(raw.get("filled_quantity") or 0.0)))
                raw.setdefault("partial", bool(raw.get("remaining_quantity")))
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
                    await asyncio.sleep(self.retry_backoff_seconds)
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

    def _simulate_fill(self, *, order_id: str, quantity: float, price: float, side: str, notional: float) -> dict:
        slippage_bps = min(
            self.config.max_slippage_bps,
            max(0.5, (float(notional or 0.0) / max(self.config.partial_fill_threshold_notional, 1.0)) * 6.0),
        )
        partial = float(notional or 0.0) >= self.config.partial_fill_threshold_notional
        fill_multiplier = 1.0 + (slippage_bps / 10000.0 if str(side).lower() == "buy" else -(slippage_bps / 10000.0))
        fill_price = float(price or 0.0) * fill_multiplier if float(price or 0.0) > 0.0 else float(price or 0.0)
        filled_quantity = float(quantity or 0.0) * (0.70 if partial else 1.0)
        remaining_quantity = max(0.0, float(quantity or 0.0) - filled_quantity)
        return {
            "id": order_id,
            "status": "partially_filled" if partial else "filled",
            "price": price,
            "fill_price": fill_price,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "partial": partial,
            "slippage_bps": slippage_bps,
            "latency_ms": self.config.base_latency_ms,
            "fee": 0.0,
        }

    def _build_report(self, *, raw: Mapping[str, object], order_id: str, broker_name: str, review: TradeReview) -> ExecutionReport:
        fill_price = self._extract_fill_price(raw, fallback=review.price)
        filled_quantity = self._extract_quantity(raw, fallback=review.quantity)
        remaining_quantity = max(0.0, float(raw.get("remaining_quantity") or max(0.0, review.quantity - filled_quantity)))
        partial = bool(raw.get("partial") or remaining_quantity > 0.0)
        fee = self._extract_fee(raw)
        status = str(raw.get("status") or ("partially_filled" if partial else "filled"))
        return ExecutionReport(
            order_id=str(raw.get("id") or order_id),
            symbol=review.symbol,
            side=review.side,
            quantity=float(review.quantity),
            requested_price=review.price,
            fill_price=fill_price,
            status=status,
            latency_ms=float(raw.get("latency_ms") or self.config.base_latency_ms),
            slippage_bps=float(raw.get("slippage_bps") or self._slippage_bps(review.price, fill_price, review.side)),
            strategy_name=review.strategy_name,
            stop_price=review.stop_price,
            take_profit=review.take_profit,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            partial=partial,
            fee=fee,
            metadata={**dict(review.metadata or {}), "broker": broker_name, "raw": dict(raw or {})},
            timestamp=review.timestamp,
        )

    async def _publish_order_submitted(self, order: ManagedOrder, review: TradeReview, *, broker_name: str) -> None:
        self.order_manager.update(order.order_id, status=OrderLifecycle.SUBMITTED.value)
        if self.bus is None:
            return
        await self.bus.publish(
            EventType.ORDER_SUBMITTED,
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": float(order.quantity),
                "remaining_quantity": float(order.quantity),
                "strategy_name": review.strategy_name,
                "status": OrderLifecycle.SUBMITTED.value,
                "broker": broker_name,
            },
            priority=75,
            source="execution_engine",
        )

    async def _publish_execution_events(self, report: ExecutionReport) -> None:
        if self.bus is None:
            return
        await self.bus.publish(EventType.ORDER_UPDATE, report, priority=78, source="execution_engine")
        await self.bus.publish(EventType.ORDER_EVENT, self._report_to_payload(report), priority=79, source="execution_engine")
        await self.bus.publish(EventType.ORDER_EXECUTED, report, priority=79, source="execution_engine")
        status = str(report.status).lower()
        if status in {OrderLifecycle.FILLED.value, OrderLifecycle.PARTIALLY_FILLED.value} or report.filled_quantity:
            if report.partial:
                await self.bus.publish(EventType.ORDER_PARTIALLY_FILLED, report, priority=79, source="execution_engine")
            await self.bus.publish(EventType.ORDER_FILLED, report, priority=80, source="execution_engine")
        await self.bus.publish(EventType.EXECUTION_REPORT, report, priority=85, source="execution_engine")

    def _update_order_state(self, report: ExecutionReport) -> None:
        status = str(report.status or "").strip().lower()
        if status in {"rejected", "rejected_market_hours"}:
            normalized = OrderLifecycle.REJECTED.value
        elif status in {"failed"}:
            normalized = OrderLifecycle.FAILED.value
        elif report.partial or status == "partially_filled":
            normalized = OrderLifecycle.PARTIALLY_FILLED.value
        else:
            normalized = OrderLifecycle.FILLED.value
        self.order_manager.update(
            report.order_id,
            status=normalized,
            filled_quantity=float(report.filled_quantity or 0.0),
            average_price=float(report.fill_price or report.requested_price or 0.0),
        )

    def _resolve_destination(self, metadata: Mapping[str, object]) -> str:
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
        return self.default_broker_name

    @staticmethod
    def _looks_like_trade_review(value: object) -> bool:
        required = ("approved", "symbol", "side", "quantity", "price", "reason")
        return all(hasattr(value, field) for field in required)

    @staticmethod
    def _looks_like_close_request(value: object) -> bool:
        required = ("symbol", "side", "quantity", "reason")
        return all(hasattr(value, field) for field in required)

    @classmethod
    def _coerce_trade_review(cls, value: TradeReview | Mapping[str, object] | object) -> TradeReview:
        if isinstance(value, TradeReview):
            return value
        payload = cls._object_payload(value)
        return TradeReview(**payload)

    @classmethod
    def _coerce_close_request(
        cls,
        value: ClosePositionRequest | Mapping[str, object] | object,
    ) -> ClosePositionRequest:
        if isinstance(value, ClosePositionRequest):
            return value
        payload = cls._object_payload(value)
        return ClosePositionRequest(**payload)

    @staticmethod
    def _object_payload(value: Mapping[str, object] | object) -> dict[str, object]:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return dict(vars(value))
        raise TypeError(f"Unsupported execution payload: {type(value)!r}")

    @staticmethod
    def _normalize_brokers(broker) -> dict[str, object]:
        if isinstance(broker, Mapping):
            normalized = {str(name): value for name, value in dict(broker).items() if value is not None}
            if not normalized:
                raise ValueError("ExecutionEngine requires at least one broker instance")
            return normalized
        return {"default": broker}

    @staticmethod
    def _extract_fill_price(payload: Mapping[str, object], *, fallback):
        for key in ("fill_price", "average", "price", "avgPrice", "last"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return fallback

    @staticmethod
    def _extract_quantity(payload: Mapping[str, object], *, fallback) -> float:
        for key in ("filled_quantity", "filled", "amount", "executedQty", "quantity"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return float(fallback)

    @staticmethod
    def _extract_fee(payload: Mapping[str, object]) -> float:
        fee = payload.get("fee")
        if isinstance(fee, Mapping):
            try:
                return float(fee.get("cost") or 0.0)
            except (TypeError, ValueError):
                return 0.0
        try:
            return float(fee or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _slippage_bps(requested_price, fill_price, side: str) -> float:
        try:
            requested = float(requested_price)
            filled = float(fill_price)
        except (TypeError, ValueError):
            return 0.0
        if requested <= 0.0:
            return 0.0
        raw_bps = ((filled - requested) / requested) * 10000.0
        return raw_bps if str(side).lower() == "buy" else -raw_bps

    @staticmethod
    def _report_to_payload(report: ExecutionReport) -> dict:
        return asdict(report)

    def _log(self, event_name: str, **payload) -> None:
        try:
            message = json.dumps({"event": event_name, **payload}, default=str, sort_keys=True)
        except Exception:
            message = f"{event_name} {payload}"
        self.logger.info(message)


__all__ = ["ExecutionEngine", "OrderLifecycle"]
