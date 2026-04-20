import asyncio
import math
from datetime import datetime, timezone


class SmartExecution:
    DEFAULT_TWAP_SLICES = 4
    DEFAULT_TWAP_DURATION_SECONDS = 20
    DEFAULT_ICEBERG_VISIBLE_RATIO = 0.25

    def __init__(self, broker, sleep_fn=None):
        self.broker = broker
        self._sleep = sleep_fn or asyncio.sleep

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _normalize_side(self, side):
        return str(side or "").strip().lower() or "buy"

    async def _submit_child(self, order, amount, price=None, order_type=None):
        child_type = order_type or order.get("type", "market")
        params = dict(order.get("params") or {})
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
            "client_order_id": order.get("client_order_id"),
            "account_id": order.get("account_id"),
            "strategy_name": order.get("strategy_name"),
            "execution_strategy": order.get("execution_strategy"),
            "metadata": dict(order.get("metadata") or {}),
        }
        if order.get("stop_price") is not None:
            payload["stop_price"] = order.get("stop_price")
        if hasattr(self.broker, "place_order"):
            return await self.broker.place_order(payload)
        return await self.broker.create_order(
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

    def _extract_realized_price(self, execution, fallback_price=None):
        execution = execution or {}
        for key in ("average", "average_price", "avgPrice", "filled_avg_price", "price"):
            value = execution.get(key)
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return self._safe_float(fallback_price, 0.0)

    def _extract_filled_amount(self, execution, fallback_amount):
        execution = execution or {}
        for key in ("filled", "filled_qty", "filled_amount", "executed_qty", "executedQty", "amount", "qty", "quantity"):
            value = execution.get(key)
            if value in (None, ""):
                continue
            amount = abs(self._safe_float(value, 0.0))
            if amount > 0:
                return amount
        return abs(self._safe_float(fallback_amount, 0.0))

    def _extract_fee(self, execution):
        execution = execution or {}
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
        return 0.0

    def _aggregate(self, order, children, algorithm, expected_price=None):
        total_filled = 0.0
        notional = 0.0
        total_fee = 0.0
        statuses = []

        for child in children:
            filled = self._extract_filled_amount(child, child.get("amount", 0.0))
            realized_price = self._extract_realized_price(child, fallback_price=expected_price or order.get("price"))
            total_filled += filled
            notional += filled * realized_price
            total_fee += self._extract_fee(child)
            statuses.append(str(child.get("status") or "").strip().lower() or "unknown")

        average_price = (notional / total_filled) if total_filled > 0 else self._safe_float(expected_price or order.get("price"), 0.0)
        normalized_side = self._normalize_side(order.get("side"))
        benchmark_price = self._safe_float(expected_price or order.get("expected_price") or order.get("price"), average_price)
        direction = 1.0 if normalized_side == "buy" else -1.0
        slippage_abs = 0.0
        slippage_bps = 0.0
        if benchmark_price > 0 and average_price > 0:
            slippage_abs = (average_price - benchmark_price) * direction
            slippage_bps = (slippage_abs / benchmark_price) * 10000.0

        status = "filled"
        if len(children) == 1:
            status = statuses[0] if statuses else "unknown"
        elif children and any(status_name in {"submitted", "open", "pending"} for status_name in statuses):
            status = "open"
        elif children and all(status_name in {"rejected", "failed"} for status_name in statuses):
            status = "rejected"

        algo_id = None
        if len(children) == 1:
            algo_id = children[0].get("id")
        if not algo_id:
            algo_id = f"{algorithm}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        return {
            "id": algo_id,
            "broker": order.get("broker") or getattr(self.broker, "exchange_name", None),
            "symbol": order["symbol"],
            "side": normalized_side,
            "amount": total_filled or self._safe_float(order.get("amount"), 0.0),
            "filled": total_filled,
            "type": order.get("type", "market"),
            "price": average_price,
            "average": average_price,
            "status": status,
            "source": order.get("source"),
            "params": dict(order.get("params") or {}),
            "stop_price": order.get("stop_price"),
            "stop_loss": order.get("stop_loss"),
            "take_profit": order.get("take_profit"),
            "expected_price": benchmark_price,
            "fee": {"cost": total_fee} if total_fee else None,
            "children": children,
            "execution_strategy": algorithm,
            "child_count": len(children),
            "execution_quality": {
                "algorithm": algorithm,
                "child_count": len(children),
                "expected_price": benchmark_price,
                "average_price": average_price,
                "slippage_abs": slippage_abs,
                "slippage_bps": slippage_bps,
                "filled_amount": total_filled,
                "total_fee": total_fee,
                "benchmark_venue": getattr(self.broker, "exchange_name", None),
            },
        }

    async def market(self, order):
        expected_price = order.get("expected_price") or order.get("price")
        child = await self._submit_child(order, amount=order["amount"], price=order.get("price"), order_type=order.get("type", "market"))
        return self._aggregate(order, [child], algorithm="market", expected_price=expected_price)

    async def limit(self, order):
        child = await self._submit_child(order, amount=order["amount"], price=order.get("price"), order_type="limit")
        return self._aggregate(order, [child], algorithm="limit", expected_price=order.get("expected_price") or order.get("price"))

    async def stop_limit(self, order):
        child = await self._submit_child(order, amount=order["amount"], price=order.get("price"), order_type="stop_limit")
        return self._aggregate(order, [child], algorithm="stop_limit", expected_price=order.get("expected_price") or order.get("price"))

    async def twap(self, order):
        params = dict(order.get("params") or {})
        total_amount = self._safe_float(order.get("amount"), 0.0)
        slices = max(1, int(params.get("twap_slices", params.get("slices", self.DEFAULT_TWAP_SLICES)) or self.DEFAULT_TWAP_SLICES))
        duration = max(0.0, self._safe_float(params.get("twap_duration_seconds", params.get("duration_seconds", self.DEFAULT_TWAP_DURATION_SECONDS)), self.DEFAULT_TWAP_DURATION_SECONDS))
        interval = duration / slices if slices > 1 else 0.0
        remaining = total_amount
        children = []
        for slice_index in range(slices):
            if remaining <= 0:
                break
            if slice_index == slices - 1:
                child_amount = remaining
            else:
                child_amount = remaining / (slices - slice_index)
            child = await self._submit_child(order, amount=child_amount, price=order.get("price"), order_type=order.get("type", "market"))
            children.append(child)
            remaining -= child_amount
            if interval > 0 and slice_index < slices - 1:
                await self._sleep(interval)
        return self._aggregate(order, children, algorithm="twap", expected_price=order.get("expected_price") or order.get("price"))

    async def vwap(self, order):
        params = dict(order.get("params") or {})
        profile = list(params.get("market_volumes") or params.get("volume_profile") or [])
        if not profile:
            return await self.twap({**order, "params": {**params, "twap_slices": 4, "twap_duration_seconds": 0}})

        sanitized = [max(0.0, self._safe_float(item, 0.0)) for item in profile]
        total_profile = sum(sanitized)
        if total_profile <= 0:
            return await self.twap({**order, "params": {**params, "twap_slices": max(1, len(profile)), "twap_duration_seconds": 0}})

        total_amount = self._safe_float(order.get("amount"), 0.0)
        remaining = total_amount
        children = []
        for index, bucket in enumerate(sanitized):
            if remaining <= 0:
                break
            if index == len(sanitized) - 1:
                child_amount = remaining
            else:
                child_amount = total_amount * (bucket / total_profile)
                child_amount = min(child_amount, remaining)
            child = await self._submit_child(order, amount=child_amount, price=order.get("price"), order_type=order.get("type", "market"))
            children.append(child)
            remaining -= child_amount
        return self._aggregate(order, children, algorithm="vwap", expected_price=order.get("expected_price") or order.get("price"))

    async def iceberg(self, order):
        params = dict(order.get("params") or {})
        total_amount = self._safe_float(order.get("amount"), 0.0)
        visible_size = self._safe_float(params.get("visible_size"), 0.0)
        if visible_size <= 0:
            visible_size = total_amount * self.DEFAULT_ICEBERG_VISIBLE_RATIO
        visible_size = max(1e-8, visible_size)
        pause_seconds = max(0.0, self._safe_float(params.get("iceberg_pause_seconds", 1.0), 1.0))

        remaining = total_amount
        children = []
        while remaining > 0:
            child_amount = min(visible_size, remaining)
            child = await self._submit_child(order, amount=child_amount, price=order.get("price"), order_type="limit" if order.get("price") is not None else order.get("type", "market"))
            children.append(child)
            remaining -= child_amount
            if remaining > 0 and pause_seconds > 0:
                await self._sleep(pause_seconds)
        return self._aggregate(order, children, algorithm="iceberg", expected_price=order.get("expected_price") or order.get("price"))

    async def execute(self, order):
        params = dict(order.get("params") or {})
        requested = str(
            order.get("execution_strategy")
            or params.get("execution_strategy")
            or params.get("algorithm")
            or "default"
        ).strip().lower()

        if requested in {"", "default"}:
            normalized_type = str(order.get("type") or "market").strip().lower()
            requested = normalized_type if normalized_type in {"limit", "stop_limit"} else "market"

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

        raise ValueError(f"Unsupported smart execution strategy: {requested}")
