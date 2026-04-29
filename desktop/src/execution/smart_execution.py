"""
Smart execution engine for InvestPro / TradeAdviser.

Supports:
- Market execution
- Limit execution
- Stop-limit execution
- TWAP execution
- VWAP execution
- Iceberg execution
- POV execution
- Retry handling
- Broker compatibility layer
- Child-order aggregation
- Slippage calculation
- Fee aggregation
- Execution-quality reporting

The goal is to avoid sending every order as one large market order.
Instead, this engine can split orders intelligently and return one clean
aggregated execution report.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional


SleepFn = Callable[[float], Awaitable[None]]


VALID_SIDES = {"buy", "sell"}
VALID_ORDER_TYPES = {
    "market",
    "limit",
    "stop",
    "stop_limit",
    "stop-limit",
    "take_profit",
    "take_profit_limit",
}
ACTIVE_STATUSES = {"submitted", "open", "pending",
                   "new", "accepted", "partially_filled", "partial"}
FAILED_STATUSES = {"rejected", "failed", "canceled", "cancelled", "expired"}
FILLED_STATUSES = {"filled", "closed", "done"}


@dataclass(slots=True)
class ExecutionReport:
    """Aggregated smart-execution result."""

    id: str
    broker: Optional[str]
    symbol: str
    side: str
    amount: float
    filled: float
    type: str
    price: float
    average: float
    status: str
    source: Optional[str] = None
    params: dict[str, Any] = field(default_factory=dict)
    stop_price: Optional[float] = None
    stop_loss: Any = None
    take_profit: Any = None
    expected_price: float = 0.0
    fee: Optional[dict[str, float]] = None
    children: list[dict[str, Any]] = field(default_factory=list)
    execution_strategy: str = "market"
    child_count: int = 0
    execution_quality: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "broker": self.broker,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "filled": self.filled,
            "type": self.type,
            "price": self.price,
            "average": self.average,
            "status": self.status,
            "source": self.source,
            "params": self.params,
            "stop_price": self.stop_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "expected_price": self.expected_price,
            "fee": self.fee,
            "children": self.children,
            "execution_strategy": self.execution_strategy,
            "child_count": self.child_count,
            "execution_quality": self.execution_quality,
            "metadata": self.metadata,
        }


class SmartExecution:
    """Smart execution router.

    The broker object may expose either:

        await broker.place_order(payload)

    or:

        await broker.create_order(
            symbol=...,
            side=...,
            amount=...,
            price=...,
            type=...,
            params=...
        )

    Sync broker methods are also supported.
    """

    DEFAULT_TWAP_SLICES = 4
    DEFAULT_TWAP_DURATION_SECONDS = 20.0
    DEFAULT_ICEBERG_VISIBLE_RATIO = 0.25
    DEFAULT_POV_PARTICIPATION_RATE = 0.10
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_RETRY_DELAY_SECONDS = 0.50
    MIN_CHILD_AMOUNT = 1e-12

    def __init__(
        self,
        broker: Any,
        sleep_fn: Optional[SleepFn] = None,
        logger: Optional[logging.Logger] = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
        dry_run: bool = False,
    ) -> None:
        if broker is None:
            raise ValueError("broker is required")

        self.broker = broker
        self._sleep = sleep_fn or asyncio.sleep
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = max(0, int(max_retries))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.dry_run = bool(dry_run)

    # ---------------------------------------------------------------------
    # Basic helpers
    # ---------------------------------------------------------------------

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)

        if math.isnan(number) or math.isinf(number):
            return float(default)

        return number

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_side(self, side: Any) -> str:
        normalized = str(side or "").strip().lower()

        if normalized in {"long", "bid"}:
            return "buy"

        if normalized in {"short", "ask"}:
            return "sell"

        if normalized not in VALID_SIDES:
            raise ValueError(f"Unsupported order side: {side!r}")

        return normalized

    def _normalize_order_type(self, order_type: Any, default: str = "market") -> str:
        normalized = str(order_type or default).strip(
        ).lower().replace("-", "_")

        if normalized == "stoplimit":
            normalized = "stop_limit"

        if normalized not in {item.replace("-", "_") for item in VALID_ORDER_TYPES}:
            raise ValueError(f"Unsupported order type: {order_type!r}")

        return normalized

    def _new_algo_id(self, algorithm: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        short_id = uuid.uuid4().hex[:8]
        return f"{algorithm}-{timestamp}-{short_id}"

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _validate_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(order, dict):
            raise TypeError("order must be a dictionary")

        symbol = str(order.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("order.symbol is required")

        side = self._normalize_side(order.get("side"))
        amount = self._safe_float(
            order.get("amount", order.get("quantity")), 0.0)

        if amount <= 0:
            raise ValueError("order.amount must be greater than 0")

        order_type = self._normalize_order_type(order.get("type", "market"))

        price = order.get("price")
        if order_type in {"limit", "stop_limit", "take_profit_limit"} and price in (None, ""):
            raise ValueError(
                f"order.price is required for {order_type} orders")

        stop_price = order.get("stop_price")
        if order_type in {"stop", "stop_limit"} and stop_price in (None, ""):
            raise ValueError(
                f"order.stop_price is required for {order_type} orders")

        normalized = dict(order)
        normalized["symbol"] = symbol
        normalized["side"] = side
        normalized["amount"] = amount
        normalized["quantity"] = amount
        normalized["type"] = order_type
        normalized["params"] = dict(order.get("params") or {})
        normalized["metadata"] = dict(order.get("metadata") or {})

        return normalized

    def _extract_order_id(self, execution: Any) -> Optional[str]:
        if not isinstance(execution, dict):
            return None

        for key in ("id", "order_id", "client_order_id", "clientOrderId"):
            value = execution.get(key)
            if value not in (None, ""):
                return str(value)

        return None

    # ---------------------------------------------------------------------
    # Broker submission
    # ---------------------------------------------------------------------

    async def _submit_child(
        self,
        order: dict[str, Any],
        amount: float,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        *,
        child_index: int = 0,
        child_count: int = 1,
        algorithm: str = "market",
    ) -> dict[str, Any]:
        amount = self._safe_float(amount, 0.0)

        if amount <= self.MIN_CHILD_AMOUNT:
            raise ValueError(f"child amount too small: {amount}")

        child_type = self._normalize_order_type(
            order_type or order.get("type", "market"))
        params = dict(order.get("params") or {})
        metadata = dict(order.get("metadata") or {})

        parent_client_order_id = order.get("client_order_id")
        child_client_order_id = (
            f"{parent_client_order_id}-{algorithm}-{child_index + 1}"
            if parent_client_order_id
            else f"{algorithm}-{uuid.uuid4().hex[:12]}"
        )

        metadata.update(
            {
                "smart_execution": True,
                "parent_client_order_id": parent_client_order_id,
                "child_client_order_id": child_client_order_id,
                "algorithm": algorithm,
                "child_index": child_index,
                "child_count": child_count,
                "created_at": self._utc_now_iso(),
            }
        )

        payload = {
            "symbol": order["symbol"],
            "side": order["side"],
            "amount": amount,
            "quantity": amount,
            "price": price,
            "type": child_type,
            "order_type": child_type,
            "params": params,
            "stop_loss": order.get("stop_loss"),
            "take_profit": order.get("take_profit"),
            "instrument": order.get("instrument"),
            "instrument_type": order.get("instrument_type"),
            "legs": list(order.get("legs") or []),
            "broker": order.get("broker"),
            "time_in_force": order.get("time_in_force"),
            "client_order_id": child_client_order_id,
            "account_id": order.get("account_id"),
            "strategy_name": order.get("strategy_name"),
            "execution_strategy": algorithm,
            "metadata": metadata,
        }

        if order.get("stop_price") is not None:
            payload["stop_price"] = order.get("stop_price")

        if self.dry_run:
            return {
                "id": child_client_order_id,
                "client_order_id": child_client_order_id,
                "symbol": payload["symbol"],
                "side": payload["side"],
                "amount": payload["amount"],
                "quantity": payload["quantity"],
                "filled": 0.0,
                "price": payload.get("price"),
                "average": payload.get("price") or order.get("expected_price") or 0.0,
                "type": payload["type"],
                "status": "dry_run",
                "params": payload["params"],
                "metadata": payload["metadata"],
            }

        last_error: Optional[BaseException] = None

        for attempt in range(self.max_retries + 1):
            try:
                if hasattr(self.broker, "place_order") and callable(self.broker.place_order):
                    result = await self._maybe_await(self.broker.place_order(payload))
                elif hasattr(self.broker, "create_order") and callable(self.broker.create_order):
                    result = await self._maybe_await(
                        self.broker.create_order(
                            symbol=payload["symbol"],
                            side=payload["side"],
                            amount=payload["amount"],
                            price=payload.get("price"),
                            type=payload["type"],
                            params=payload.get("params"),
                            stop_loss=payload.get("stop_loss"),
                            take_profit=payload.get("take_profit"),
                            stop_price=payload.get("stop_price"),
                        )
                    )
                else:
                    raise NotImplementedError(
                        "Broker must implement place_order(payload) or create_order(...)"
                    )

                if not isinstance(result, dict):
                    result = {"raw": result}

                result.setdefault("symbol", payload["symbol"])
                result.setdefault("side", payload["side"])
                result.setdefault("amount", payload["amount"])
                result.setdefault("quantity", payload["quantity"])
                result.setdefault("type", payload["type"])
                result.setdefault("client_order_id", child_client_order_id)
                result.setdefault("metadata", metadata)

                return result

            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "Child order failed attempt=%s/%s symbol=%s amount=%s algorithm=%s error=%s",
                    attempt + 1,
                    self.max_retries + 1,
                    order.get("symbol"),
                    amount,
                    algorithm,
                    exc,
                )

                if attempt < self.max_retries and self.retry_delay_seconds > 0:
                    await self._sleep(self.retry_delay_seconds)

        raise RuntimeError(
            f"Child order submission failed after retries: {last_error}") from last_error

    # ---------------------------------------------------------------------
    # Execution extraction / aggregation
    # ---------------------------------------------------------------------

    def _extract_realized_price(self, execution: Any, fallback_price: Any = None) -> float:
        execution = execution or {}

        if not isinstance(execution, dict):
            return self._safe_float(fallback_price, 0.0)

        for key in (
            "average",
            "average_price",
            "avgPrice",
            "filled_avg_price",
            "executed_price",
            "price",
        ):
            value = execution.get(key)
            if value in (None, ""):
                continue

            price = self._safe_float(value, 0.0)
            if price > 0:
                return price

        return self._safe_float(fallback_price, 0.0)

    def _extract_filled_amount(self, execution: Any, fallback_amount: Any) -> float:
        execution = execution or {}

        if not isinstance(execution, dict):
            return abs(self._safe_float(fallback_amount, 0.0))

        for key in (
            "filled",
            "filled_qty",
            "filled_amount",
            "executed_qty",
            "executedQty",
            "amount_filled",
            "amount",
            "qty",
            "quantity",
        ):
            value = execution.get(key)
            if value in (None, ""):
                continue

            amount = abs(self._safe_float(value, 0.0))
            if amount > 0:
                return amount

        return abs(self._safe_float(fallback_amount, 0.0))

    def _extract_fee(self, execution: Any) -> float:
        execution = execution or {}

        if not isinstance(execution, dict):
            return 0.0

        fee = execution.get("fee")
        if isinstance(fee, dict):
            cost = fee.get("cost")
            if cost not in (None, ""):
                return self._safe_float(cost, 0.0)

        fees = execution.get("fees")
        if isinstance(fees, list):
            total = 0.0
            found = False

            for item in fees:
                if not isinstance(item, dict):
                    continue

                cost = item.get("cost")
                if cost in (None, ""):
                    continue

                total += self._safe_float(cost, 0.0)
                found = True

            if found:
                return total

        direct_fee = execution.get("commission")
        if direct_fee not in (None, ""):
            return self._safe_float(direct_fee, 0.0)

        return 0.0

    def _normalize_status(self, status: Any) -> str:
        text = str(status or "").strip().lower()

        if not text:
            return "unknown"

        if text in {"cancelled"}:
            return "canceled"

        if text in {"partial"}:
            return "partially_filled"

        return text

    def _aggregate(
        self,
        order: dict[str, Any],
        children: list[dict[str, Any]],
        algorithm: str,
        expected_price: Any = None,
    ) -> dict[str, Any]:
        total_filled = 0.0
        submitted_amount = 0.0
        notional = 0.0
        total_fee = 0.0
        statuses: list[str] = []

        for child in children:
            if not isinstance(child, dict):
                child = {"raw": child}

            child_amount = self._safe_float(
                child.get("amount", child.get("quantity")), 0.0)
            submitted_amount += abs(child_amount)

            filled = self._extract_filled_amount(child, child_amount)
            realized_price = self._extract_realized_price(
                child,
                fallback_price=expected_price or order.get("price"),
            )

            total_filled += filled
            notional += filled * realized_price
            total_fee += self._extract_fee(child)
            statuses.append(self._normalize_status(child.get("status")))

        order_amount = self._safe_float(order.get("amount"), 0.0)
        fallback_price = self._safe_float(
            expected_price or order.get("price"), 0.0)
        average_price = (
            notional / total_filled) if total_filled > 0 else fallback_price

        normalized_side = self._normalize_side(order.get("side"))
        benchmark_price = self._safe_float(
            expected_price or order.get(
                "expected_price") or order.get("price"),
            average_price,
        )

        direction = 1.0 if normalized_side == "buy" else -1.0

        slippage_abs = 0.0
        slippage_bps = 0.0

        if benchmark_price > 0 and average_price > 0 and total_filled > 0:
            slippage_abs = (average_price - benchmark_price) * direction
            slippage_bps = (slippage_abs / benchmark_price) * 10000.0

        status = self._aggregate_status(statuses, total_filled, order_amount)

        algo_id = None
        if len(children) == 1:
            algo_id = self._extract_order_id(children[0])

        if not algo_id:
            algo_id = self._new_algo_id(algorithm)

        broker_name = (
            order.get("broker")
            or getattr(self.broker, "exchange_name", None)
            or getattr(self.broker, "name", None)
        )

        execution_quality = {
            "algorithm": algorithm,
            "child_count": len(children),
            "expected_price": benchmark_price,
            "average_price": average_price,
            "slippage_abs": slippage_abs,
            "slippage_bps": slippage_bps,
            "filled_amount": total_filled,
            "requested_amount": order_amount,
            "submitted_child_amount": submitted_amount,
            "fill_ratio": (total_filled / order_amount) if order_amount > 0 else 0.0,
            "total_fee": total_fee,
            "benchmark_venue": getattr(self.broker, "exchange_name", None),
            "statuses": statuses,
            "created_at": self._utc_now_iso(),
        }

        return ExecutionReport(
            id=algo_id,
            broker=broker_name,
            symbol=order["symbol"],
            side=normalized_side,
            amount=total_filled or order_amount,
            filled=total_filled,
            type=order.get("type", "market"),
            price=average_price,
            average=average_price,
            status=status,
            source=order.get("source"),
            params=dict(order.get("params") or {}),
            stop_price=order.get("stop_price"),
            stop_loss=order.get("stop_loss"),
            take_profit=order.get("take_profit"),
            expected_price=benchmark_price,
            fee={"cost": total_fee} if total_fee else None,
            children=children,
            execution_strategy=algorithm,
            child_count=len(children),
            execution_quality=execution_quality,
            metadata=dict(order.get("metadata") or {}),
        ).to_dict()

    def _aggregate_status(
        self,
        statuses: list[str],
        total_filled: float,
        requested_amount: float,
    ) -> str:
        if not statuses:
            return "unknown"

        if all(status == "dry_run" for status in statuses):
            return "dry_run"

        if total_filled > 0 and requested_amount > 0 and total_filled < requested_amount:
            if any(status in ACTIVE_STATUSES for status in statuses):
                return "partially_filled"
            return "partially_filled"

        if total_filled >= requested_amount > 0:
            return "filled"

        if any(status in ACTIVE_STATUSES for status in statuses):
            return "open"

        if all(status in FAILED_STATUSES for status in statuses):
            return "rejected"

        if any(status in FILLED_STATUSES for status in statuses):
            return "filled"

        return statuses[-1] or "unknown"

    # ---------------------------------------------------------------------
    # Algorithms
    # ---------------------------------------------------------------------

    async def market(self, order: dict[str, Any]) -> dict[str, Any]:
        order = self._validate_order(order)
        expected_price = order.get("expected_price") or order.get("price")

        child = await self._submit_child(
            order,
            amount=order["amount"],
            price=order.get("price"),
            order_type=order.get("type", "market"),
            child_index=0,
            child_count=1,
            algorithm="market",
        )

        return self._aggregate(order, [child], algorithm="market", expected_price=expected_price)

    async def limit(self, order: dict[str, Any]) -> dict[str, Any]:
        order = self._validate_order({**order, "type": "limit"})

        child = await self._submit_child(
            order,
            amount=order["amount"],
            price=order.get("price"),
            order_type="limit",
            child_index=0,
            child_count=1,
            algorithm="limit",
        )

        return self._aggregate(
            order,
            [child],
            algorithm="limit",
            expected_price=order.get("expected_price") or order.get("price"),
        )

    async def stop_limit(self, order: dict[str, Any]) -> dict[str, Any]:
        order = self._validate_order({**order, "type": "stop_limit"})

        child = await self._submit_child(
            order,
            amount=order["amount"],
            price=order.get("price"),
            order_type="stop_limit",
            child_index=0,
            child_count=1,
            algorithm="stop_limit",
        )

        return self._aggregate(
            order,
            [child],
            algorithm="stop_limit",
            expected_price=order.get("expected_price") or order.get("price"),
        )

    async def twap(self, order: dict[str, Any]) -> dict[str, Any]:
        order = self._validate_order(order)
        params = dict(order.get("params") or {})

        total_amount = self._safe_float(order.get("amount"), 0.0)
        slices = max(
            1,
            self._safe_int(
                params.get("twap_slices", params.get("slices")),
                self.DEFAULT_TWAP_SLICES,
            ),
        )

        duration = max(
            0.0,
            self._safe_float(
                params.get("twap_duration_seconds",
                           params.get("duration_seconds")),
                self.DEFAULT_TWAP_DURATION_SECONDS,
            ),
        )

        interval = duration / slices if slices > 1 else 0.0
        remaining = total_amount
        children: list[dict[str, Any]] = []

        for slice_index in range(slices):
            if remaining <= self.MIN_CHILD_AMOUNT:
                break

            if slice_index == slices - 1:
                child_amount = remaining
            else:
                child_amount = total_amount / slices
                child_amount = min(child_amount, remaining)

            child = await self._submit_child(
                order,
                amount=child_amount,
                price=order.get("price"),
                order_type=order.get("type", "market"),
                child_index=slice_index,
                child_count=slices,
                algorithm="twap",
            )

            children.append(child)
            remaining -= child_amount

            if interval > 0 and slice_index < slices - 1:
                await self._sleep(interval)

        return self._aggregate(
            order,
            children,
            algorithm="twap",
            expected_price=order.get("expected_price") or order.get("price"),
        )

    async def vwap(self, order: dict[str, Any]) -> dict[str, Any]:
        order = self._validate_order(order)
        params = dict(order.get("params") or {})

        profile = list(params.get("market_volumes")
                       or params.get("volume_profile") or [])

        if not profile:
            fallback_params = {
                **params,
                "twap_slices": 4,
                "twap_duration_seconds": 0,
            }
            return await self.twap({**order, "params": fallback_params, "execution_strategy": "twap"})

        sanitized = [max(0.0, self._safe_float(item, 0.0)) for item in profile]
        total_profile = sum(sanitized)

        if total_profile <= 0:
            fallback_params = {
                **params,
                "twap_slices": max(1, len(profile)),
                "twap_duration_seconds": 0,
            }
            return await self.twap({**order, "params": fallback_params, "execution_strategy": "twap"})

        total_amount = self._safe_float(order.get("amount"), 0.0)
        remaining = total_amount
        children: list[dict[str, Any]] = []

        for index, bucket in enumerate(sanitized):
            if remaining <= self.MIN_CHILD_AMOUNT:
                break

            if index == len(sanitized) - 1:
                child_amount = remaining
            else:
                child_amount = total_amount * (bucket / total_profile)
                child_amount = min(child_amount, remaining)

            if child_amount <= self.MIN_CHILD_AMOUNT:
                continue

            child = await self._submit_child(
                order,
                amount=child_amount,
                price=order.get("price"),
                order_type=order.get("type", "market"),
                child_index=index,
                child_count=len(sanitized),
                algorithm="vwap",
            )

            children.append(child)
            remaining -= child_amount

        return self._aggregate(
            order,
            children,
            algorithm="vwap",
            expected_price=order.get("expected_price") or order.get("price"),
        )

    async def iceberg(self, order: dict[str, Any]) -> dict[str, Any]:
        order = self._validate_order(order)
        params = dict(order.get("params") or {})

        total_amount = self._safe_float(order.get("amount"), 0.0)
        visible_size = self._safe_float(params.get("visible_size"), 0.0)

        if visible_size <= 0:
            visible_size = total_amount * self.DEFAULT_ICEBERG_VISIBLE_RATIO

        visible_size = max(self.MIN_CHILD_AMOUNT, visible_size)
        pause_seconds = max(
            0.0,
            self._safe_float(params.get("iceberg_pause_seconds"), 1.0),
        )

        max_children = max(1, self._safe_int(
            params.get("max_iceberg_children"), 1000))

        remaining = total_amount
        children: list[dict[str, Any]] = []
        index = 0

        while remaining > self.MIN_CHILD_AMOUNT and index < max_children:
            child_amount = min(visible_size, remaining)

            child_type = "limit" if order.get(
                "price") is not None else order.get("type", "market")

            child = await self._submit_child(
                order,
                amount=child_amount,
                price=order.get("price"),
                order_type=child_type,
                child_index=index,
                child_count=max_children,
                algorithm="iceberg",
            )

            children.append(child)
            remaining -= child_amount
            index += 1

            if remaining > self.MIN_CHILD_AMOUNT and pause_seconds > 0:
                await self._sleep(pause_seconds)

        if remaining > self.MIN_CHILD_AMOUNT:
            self.logger.warning(
                "Iceberg execution stopped before full amount due to max_iceberg_children. remaining=%s",
                remaining,
            )

        return self._aggregate(
            order,
            children,
            algorithm="iceberg",
            expected_price=order.get("expected_price") or order.get("price"),
        )

    async def pov(self, order: dict[str, Any]) -> dict[str, Any]:
        """Percent-of-volume execution.

        Expected params:
            market_volumes: list[float]
            participation_rate: 0.05 means execute 5% of each volume bucket
            pov_pause_seconds: optional pause between buckets

        This is useful when you do not want your order to dominate market volume.
        """
        order = self._validate_order(order)
        params = dict(order.get("params") or {})

        market_volumes = list(params.get("market_volumes")
                              or params.get("volume_profile") or [])

        if not market_volumes:
            return await self.vwap(order)

        participation_rate = self._safe_float(
            params.get("participation_rate", params.get(
                "pov_participation_rate")),
            self.DEFAULT_POV_PARTICIPATION_RATE,
        )

        if participation_rate <= 0 or participation_rate > 1:
            raise ValueError(
                "participation_rate must be greater than 0 and less than or equal to 1")

        pause_seconds = max(0.0, self._safe_float(
            params.get("pov_pause_seconds"), 0.0))
        total_amount = self._safe_float(order.get("amount"), 0.0)

        remaining = total_amount
        children: list[dict[str, Any]] = []
        sanitized = [max(0.0, self._safe_float(item, 0.0))
                     for item in market_volumes]

        for index, bucket_volume in enumerate(sanitized):
            if remaining <= self.MIN_CHILD_AMOUNT:
                break

            child_amount = min(bucket_volume * participation_rate, remaining)

            if index == len(sanitized) - 1:
                child_amount = remaining

            if child_amount <= self.MIN_CHILD_AMOUNT:
                continue

            child = await self._submit_child(
                order,
                amount=child_amount,
                price=order.get("price"),
                order_type=order.get("type", "market"),
                child_index=index,
                child_count=len(sanitized),
                algorithm="pov",
            )

            children.append(child)
            remaining -= child_amount

            if pause_seconds > 0 and remaining > self.MIN_CHILD_AMOUNT:
                await self._sleep(pause_seconds)

        return self._aggregate(
            order,
            children,
            algorithm="pov",
            expected_price=order.get("expected_price") or order.get("price"),
        )

    # ---------------------------------------------------------------------
    # Main dispatcher
    # ---------------------------------------------------------------------

    async def execute(self, order: dict[str, Any]) -> dict[str, Any]:
        """Execute an order using the requested smart execution algorithm."""
        order = self._validate_order(order)
        params = dict(order.get("params") or {})

        requested = str(
            order.get("execution_strategy")
            or params.get("execution_strategy")
            or params.get("algorithm")
            or "default"
        ).strip().lower().replace("-", "_")

        if requested in {"", "default", "auto"}:
            normalized_type = self._normalize_order_type(
                order.get("type") or "market")
            requested = normalized_type if normalized_type in {
                "limit", "stop_limit"} else "market"

        if requested == "market":
            return await self.market(order)

        if requested == "limit":
            return await self.limit(order)

        if requested == "stop_limit":
            return await self.stop_limit(order)

        if requested == "twap":
            return await self.twap(order)

        if requested == "vwap":
            return await self.vwap(order)

        if requested == "iceberg":
            return await self.iceberg(order)

        if requested == "pov":
            return await self.pov(order)

        raise ValueError(f"Unsupported smart execution strategy: {requested}")
