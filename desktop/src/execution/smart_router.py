from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from execution.smart_execution import SmartExecution


@dataclass(slots=True)
class SmartRouteDecision:
    """Decision returned by SmartRouter before execution."""

    route: str
    reason: str
    notional: float
    amount: float
    reference_price: float
    liquidity_score: float
    spread_bps: Optional[float] = None
    urgency: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "reason": self.reason,
            "notional": self.notional,
            "amount": self.amount,
            "reference_price": self.reference_price,
            "liquidity_score": self.liquidity_score,
            "spread_bps": self.spread_bps,
            "urgency": self.urgency,
            "metadata": self.metadata,
        }


class SmartRouter:
    """Smart execution route selector.

    This class chooses the best execution algorithm before handing the order to
    SmartExecution.

    Supported routes:
    - market
    - limit
    - stop_limit
    - twap
    - vwap
    - iceberg
    - pov

    Routing logic considers:
    - order type
    - notional size
    - liquidity score
    - spread in basis points
    - urgency
    - explicit execution strategy
    - optional market volume profile
    """

    DEFAULT_TWAP_SLICES = 4
    DEFAULT_VWAP_BUCKETS = 4
    DEFAULT_TWAP_DURATION_SECONDS = 20.0

    def __init__(
        self,
        broker: Any,
        *,
        smart_execution: Optional[SmartExecution] = None,
        twap_slices: int = DEFAULT_TWAP_SLICES,
        vwap_buckets: int = DEFAULT_VWAP_BUCKETS,
        twap_duration_seconds: float = DEFAULT_TWAP_DURATION_SECONDS,
        large_notional_threshold: float = 50_000.0,
        medium_notional_threshold: float = 25_000.0,
        iceberg_notional_threshold: float = 100_000.0,
        low_liquidity_threshold: float = 0.40,
        medium_liquidity_threshold: float = 0.80,
        wide_spread_bps_threshold: float = 15.0,
        pov_participation_rate: float = 0.10,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if broker is None:
            raise ValueError("broker is required")

        self.broker = broker
        self.smart_execution = smart_execution or SmartExecution(broker)

        self.twap_slices = max(1, int(twap_slices or self.DEFAULT_TWAP_SLICES))
        self.vwap_buckets = max(
            1, int(vwap_buckets or self.DEFAULT_VWAP_BUCKETS))
        self.twap_duration_seconds = max(0.0, float(twap_duration_seconds))

        self.large_notional_threshold = max(
            0.0, float(large_notional_threshold))
        self.medium_notional_threshold = max(
            0.0, float(medium_notional_threshold))
        self.iceberg_notional_threshold = max(
            0.0, float(iceberg_notional_threshold))

        self.low_liquidity_threshold = self._clamp(
            float(low_liquidity_threshold), 0.0, 1.0)
        self.medium_liquidity_threshold = self._clamp(
            float(medium_liquidity_threshold), 0.0, 1.0)

        self.wide_spread_bps_threshold = max(
            0.0, float(wide_spread_bps_threshold))
        self.pov_participation_rate = self._clamp(
            float(pov_participation_rate), 0.0001, 1.0)

        self.logger = logger or logging.getLogger(__name__)

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)

        if math.isnan(number) or math.isinf(number):
            return float(default)

        return number

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _normalize_order_type(self, order_type: Any) -> str:
        normalized = str(order_type or "market").strip(
        ).lower().replace("-", "_")
        if not normalized:
            return "market"
        if normalized == "stoplimit":
            return "stop_limit"
        return normalized

    def _normalize_urgency(self, urgency: Any) -> str:
        normalized = str(urgency or "normal").strip().lower()
        if normalized in {"now", "immediate", "urgent", "high"}:
            return "high"
        if normalized in {"slow", "patient", "low"}:
            return "low"
        return "normal"

    def _normalize_route(self, route: Any) -> str:
        normalized = str(route or "").strip().lower().replace("-", "_")
        if normalized == "stoplimit":
            normalized = "stop_limit"
        return normalized

    def _reference_price(self, order: dict[str, Any]) -> float:
        """Find the best available price for notional/routing decisions."""
        for key in (
            "expected_price",
            "mark_price",
            "mid_price",
            "last_price",
            "price",
            "ask",
            "bid",
        ):
            value = order.get(key)
            price = self._safe_float(value, 0.0)
            if price > 0:
                return price

        return 1.0

    def _calculate_spread_bps(self, order: dict[str, Any]) -> Optional[float]:
        """Calculate spread in basis points if bid/ask are available."""
        bid = self._safe_float(order.get("bid"), 0.0)
        ask = self._safe_float(order.get("ask"), 0.0)

        if bid <= 0 or ask <= 0 or ask < bid:
            spread = order.get("spread_bps")
            if spread is None:
                return None
            return max(0.0, self._safe_float(spread, 0.0))

        mid = (bid + ask) / 2.0
        if mid <= 0:
            return None

        return ((ask - bid) / mid) * 10_000.0

    def _calculate_notional(self, order: dict[str, Any]) -> tuple[float, float, float]:
        amount = self._safe_float(
            order.get("amount", order.get("quantity")), 0.0)
        reference_price = self._reference_price(order)
        notional = abs(amount * reference_price)
        return notional, amount, reference_price

    def _liquidity_score(self, order: dict[str, Any]) -> float:
        return self._clamp(self._safe_float(order.get("liquidity_score"), 1.0), 0.0, 1.0)

    def _has_volume_profile(self, order: dict[str, Any]) -> bool:
        params = dict(order.get("params") or {})
        profile = (
            params.get("market_volumes")
            or params.get("volume_profile")
            or order.get("market_volumes")
            or order.get("volume_profile")
        )

        if not isinstance(profile, list):
            return False

        return any(self._safe_float(item, 0.0) > 0 for item in profile)

    def _requested_route(self, order: dict[str, Any]) -> Optional[str]:
        params = dict(order.get("params") or {})

        requested = (
            order.get("execution_strategy")
            or order.get("route")
            or params.get("execution_strategy")
            or params.get("algorithm")
            or params.get("route")
        )

        route = self._normalize_route(requested)

        if route in {"market", "limit", "stop_limit", "twap", "vwap", "iceberg", "pov"}:
            return route

        return None

    # ---------------------------------------------------------------------
    # Route decision
    # ---------------------------------------------------------------------

    def choose_route(
        self,
        *,
        order_type: str = "market",
        notional: float = 0.0,
        liquidity_score: float = 1.0,
        spread_bps: Optional[float] = None,
        urgency: str = "normal",
        has_volume_profile: bool = False,
        explicit_route: Optional[str] = None,
    ) -> SmartRouteDecision:
        """Choose the best route based on order conditions."""

        normalized_type = self._normalize_order_type(order_type)
        normalized_urgency = self._normalize_urgency(urgency)

        notional = max(0.0, self._safe_float(notional, 0.0))
        liquidity_score = self._clamp(
            self._safe_float(liquidity_score, 1.0), 0.0, 1.0)

        if spread_bps is not None:
            spread_bps = max(0.0, self._safe_float(spread_bps, 0.0))

        explicit = self._normalize_route(explicit_route)

        # Explicit route wins as long as it is valid.
        if explicit in {"market", "limit", "stop_limit", "twap", "vwap", "iceberg", "pov"}:
            return SmartRouteDecision(
                route=explicit,
                reason=f"Explicit route requested: {explicit}",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Native limit/stop-limit order type should preserve its route.
        if normalized_type in {"limit", "stop_limit"}:
            return SmartRouteDecision(
                route=normalized_type,
                reason=f"Order type requires {normalized_type} execution",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Very urgent orders favor market unless spread is extremely wide.
        if normalized_urgency == "high":
            if spread_bps is not None and spread_bps >= self.wide_spread_bps_threshold * 2:
                return SmartRouteDecision(
                    route="limit",
                    reason="Urgent order but spread is extremely wide, using limit protection",
                    notional=notional,
                    amount=0.0,
                    reference_price=0.0,
                    liquidity_score=liquidity_score,
                    spread_bps=spread_bps,
                    urgency=normalized_urgency,
                )

            return SmartRouteDecision(
                route="market",
                reason="High urgency order, using market execution",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Widespread means market orders can be expensive.
        if spread_bps is not None and spread_bps >= self.wide_spread_bps_threshold:
            if notional >= self.medium_notional_threshold:
                return SmartRouteDecision(
                    route="twap",
                    reason="Wide spread and medium/large notional, using TWAP to reduce impact",
                    notional=notional,
                    amount=0.0,
                    reference_price=0.0,
                    liquidity_score=liquidity_score,
                    spread_bps=spread_bps,
                    urgency=normalized_urgency,
                )

            return SmartRouteDecision(
                route="limit",
                reason="Wide spread on smaller order, using limit protection",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Very large and weak liquidity: hide size with iceberg.
        if notional >= self.iceberg_notional_threshold and liquidity_score <= self.low_liquidity_threshold:
            return SmartRouteDecision(
                route="iceberg",
                reason="Very large order with low liquidity, using iceberg",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Large order with poor liquidity: TWAP.
        if notional >= self.large_notional_threshold and liquidity_score < self.medium_liquidity_threshold:
            return SmartRouteDecision(
                route="twap",
                reason="Large order with below-average liquidity, using TWAP",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Large order with available volume profile: VWAP.
        if notional >= self.medium_notional_threshold and has_volume_profile:
            return SmartRouteDecision(
                route="vwap",
                reason="Medium/large order with volume profile, using VWAP",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Medium/large order without profile: TWAP is safer than fake VWAP.
        if notional >= self.medium_notional_threshold:
            return SmartRouteDecision(
                route="twap",
                reason="Medium/large order without volume profile, using TWAP",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        # Patient low-urgency orders can use limit.
        if normalized_urgency == "low":
            return SmartRouteDecision(
                route="limit",
                reason="Low urgency order, using limit execution",
                notional=notional,
                amount=0.0,
                reference_price=0.0,
                liquidity_score=liquidity_score,
                spread_bps=spread_bps,
                urgency=normalized_urgency,
            )

        return SmartRouteDecision(
            route=normalized_type or "market",
            reason="Small normal-urgency order, using default order type",
            notional=notional,
            amount=0.0,
            reference_price=0.0,
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            urgency=normalized_urgency,
        )

    def decide(self, order: dict[str, Any]) -> SmartRouteDecision:
        """Build a complete route decision from an order dictionary."""

        if not isinstance(order, dict):
            raise TypeError("order must be a dictionary")

        notional, amount, reference_price = self._calculate_notional(order)
        liquidity_score = self._liquidity_score(order)
        spread_bps = self._calculate_spread_bps(order)
        urgency = self._normalize_urgency(order.get("urgency"))
        has_volume_profile = self._has_volume_profile(order)
        explicit_route = self._requested_route(order)

        decision = self.choose_route(
            order_type=order.get("type", "market"),
            notional=notional,
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            urgency=urgency,
            has_volume_profile=has_volume_profile,
            explicit_route=explicit_route,
        )

        decision.amount = amount
        decision.reference_price = reference_price
        decision.metadata.update(
            {
                "has_volume_profile": has_volume_profile,
                "explicit_route": explicit_route,
                "order_type": self._normalize_order_type(order.get("type", "market")),
            }
        )

        return decision

    # ---------------------------------------------------------------------
    # Order preparation
    # ---------------------------------------------------------------------

    def _prepare_order_for_route(
        self,
        order: dict[str, Any],
        decision: SmartRouteDecision,
    ) -> dict[str, Any]:
        """Attach smart-routing parameters before execution."""

        params = dict(order.get("params") or {})
        metadata = dict(order.get("metadata") or {})

        route = decision.route

        if route == "twap":
            params.setdefault("twap_slices", self.twap_slices)
            params.setdefault("twap_duration_seconds",
                              self.twap_duration_seconds)

        elif route == "vwap":
            profile = (
                params.get("market_volumes")
                or params.get("volume_profile")
                or order.get("market_volumes")
                or order.get("volume_profile")
            )

            if not profile:
                params.setdefault("market_volumes", [1.0] * self.vwap_buckets)
            else:
                params.setdefault("market_volumes", list(profile))

        elif route == "iceberg":
            if "visible_size" not in params:
                params["visible_size"] = max(
                    abs(decision.amount) * 0.25, 1e-12)
            params.setdefault("iceberg_pause_seconds", 1.0)

        elif route == "pov":
            params.setdefault("participation_rate",
                              self.pov_participation_rate)

            profile = (
                params.get("market_volumes")
                or params.get("volume_profile")
                or order.get("market_volumes")
                or order.get("volume_profile")
            )

            if profile:
                params.setdefault("market_volumes", list(profile))

        metadata["smart_router"] = {
            "route": decision.route,
            "reason": decision.reason,
            "notional": decision.notional,
            "amount": decision.amount,
            "reference_price": decision.reference_price,
            "liquidity_score": decision.liquidity_score,
            "spread_bps": decision.spread_bps,
            "urgency": decision.urgency,
            **decision.metadata,
        }

        prepared = {
            **order,
            "execution_strategy": route,
            "params": params,
            "metadata": metadata,
        }

        # If low-urgency route selected limit but no price is available,
        # fall back to market because SmartExecution.limit requires price.
        if route == "limit" and prepared.get("price") is None:
            fallback_price = (
                prepared.get("expected_price")
                or prepared.get("mid_price")
                or prepared.get("last_price")
                or prepared.get("mark_price")
            )
            if fallback_price is not None:
                prepared["price"] = fallback_price
            else:
                prepared["execution_strategy"] = "market"
                prepared["metadata"]["smart_router"]["route"] = "market"
                prepared["metadata"]["smart_router"]["reason"] = (
                    "Limit route selected but no usable price was available; falling back to market"
                )

        return prepared

    # ---------------------------------------------------------------------
    # Execution
    # ---------------------------------------------------------------------

    async def execute(self, order: dict[str, Any]) -> dict[str, Any]:
        """Route and execute an order."""

        decision = self.decide(order)
        prepared_order = self._prepare_order_for_route(order, decision)

        self.logger.info(
            "SmartRouter selected route=%s symbol=%s notional=%.2f liquidity=%.3f spread_bps=%s reason=%s",
            prepared_order.get("execution_strategy"),
            prepared_order.get("symbol"),
            decision.notional,
            decision.liquidity_score,
            decision.spread_bps,
            decision.reason,
        )

        result = await self.smart_execution.execute(prepared_order)

        result_metadata = dict(result.get("metadata") or {})
        result_metadata.setdefault("smart_router", prepared_order.get(
            "metadata", {}).get("smart_router"))
        result["metadata"] = result_metadata

        execution_quality = dict(result.get("execution_quality") or {})
        execution_quality.setdefault(
            "smart_router_route", prepared_order.get("execution_strategy"))
        execution_quality.setdefault("smart_router_reason", prepared_order.get(
            "metadata", {}).get("smart_router", {}).get("reason"))
        execution_quality.setdefault(
            "smart_router_notional", decision.notional)
        execution_quality.setdefault(
            "smart_router_liquidity_score", decision.liquidity_score)
        execution_quality.setdefault(
            "smart_router_spread_bps", decision.spread_bps)
        result["execution_quality"] = execution_quality

        return result
