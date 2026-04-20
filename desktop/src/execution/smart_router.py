from __future__ import annotations

from execution.smart_execution import SmartExecution


class SmartRouter:
    def __init__(self, broker, *, twap_slices: int = 4, vwap_buckets: int = 4) -> None:
        self.broker = broker
        self.smart_execution = SmartExecution(broker)
        self.twap_slices = max(1, int(twap_slices or 4))
        self.vwap_buckets = max(1, int(vwap_buckets or 4))

    def choose_route(self, *, order_type: str, notional: float, liquidity_score: float) -> str:
        normalized = str(order_type or "market").strip().lower() or "market"
        if normalized in {"limit", "stop_limit"}:
            return normalized
        if notional >= 50000.0 and liquidity_score < 0.8:
            return "twap"
        if notional >= 25000.0:
            return "vwap"
        return normalized

    async def execute(self, order: dict) -> dict:
        route = self.choose_route(
            order_type=order.get("type"),
            notional=float(order.get("amount", 0.0) or 0.0) * float(order.get("price") or order.get("expected_price") or 1.0),
            liquidity_score=float(order.get("liquidity_score") or 1.0),
        )
        if route == "twap":
            params = dict(order.get("params") or {})
            params.setdefault("twap_slices", self.twap_slices)
            params.setdefault("twap_duration_seconds", 0)
            return await self.smart_execution.twap({**order, "params": params})
        if route == "vwap":
            params = dict(order.get("params") or {})
            params.setdefault("market_volumes", [1.0] * self.vwap_buckets)
            return await self.smart_execution.vwap({**order, "params": params})
        if route == "limit":
            return await self.smart_execution.limit(order)
        if route == "stop_limit":
            return await self.smart_execution.stop_limit(order)
        return await self.smart_execution.market(order)
