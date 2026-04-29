from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from derivatives.core.config import EngineConfig
from derivatives.core.live_market_cache import LiveMarketCache
from derivatives.core.models import ExecutionUpdate, OrderCommand
from derivatives.core.symbols import SymbolRegistry

from execution.smart_router import SmartRouter
from core.ai.learning_engine import LearningEngine

if TYPE_CHECKING:
    from events.event_bus import EventBus


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if number != number:
            return default
        if number in (float("inf"), float("-inf")):
            return default
        return number
    except Exception:
        return default


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    if side in {"buy", "long"}:
        return "buy"
    if side in {"sell", "short"}:
        return "sell"
    return "buy"


def _normalize_order_type(value: Any) -> str:
    order_type = str(value or "").strip().lower()
    if order_type in {"market", "limit", "stop", "stop_limit", "stop-limit"}:
        return order_type.replace("-", "_")
    return "market"


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class ExecutionEngine:
    """
    Executes risk-approved orders.

    Responsibilities:
    - listens for risk.approved events
    - resolves broker route from SymbolRegistry
    - submits orders through SmartRouter or direct broker methods
    - publishes order.submitted, order.executed, risk.alert, and learning events
    - records executed trade metadata into LearningEngine safely

    Expected event input from risk engine:
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "approved_size": 0.01,
            "broker_key": "binanceus",
            "exchange": "binanceus",
            "order_type": "market",
            "limit_price": 65000,
            "stop_loss": 64000,
            "take_profit": 67000,
            "strategy_name": "Trend Following",
            "confidence": 0.82,
            "metadata": {...}
        }
    """

    def __init__(
            self,
            event_bus: EventBus,
            cache: LiveMarketCache,
            symbol_registry: SymbolRegistry,
            brokers: dict[str, Any],
            *,
            config: EngineConfig | None = None,
            logger: logging.Logger | None = None,
            learning_engine: LearningEngine | None = None,
    ) -> None:
        self.bus = event_bus
        self.cache = cache
        self.symbol_registry = symbol_registry
        self.brokers = dict(brokers or {})
        self.config = config or EngineConfig()
        self.logger = logger or logging.getLogger("DerivativesExecutionEngine")

        self.learning_engine = learning_engine or LearningEngine()
        self._routers: dict[str, SmartRouter] = {}

        self.bus.subscribe("risk.approved", self._on_risk_approved)

    # ------------------------------------------------------------------
    # Router management
    # ------------------------------------------------------------------

    def _router_for(self, broker_key: str, broker: Any) -> SmartRouter:
        broker_key = str(broker_key or "").strip().lower()
        router = self._routers.get(broker_key)

        if router is None:
            router = SmartRouter(broker)
            self._routers[broker_key] = router

        return router

    # ------------------------------------------------------------------
    # Cache compatibility
    # ------------------------------------------------------------------

    def _latest_price(self, symbol: str) -> float | None:
        """
        Supports multiple LiveMarketCache method names:
        - latest_price(symbol)
        - get_latest_price(symbol)
        - get_price(symbol)
        """

        for method_name in ("latest_price", "get_latest_price", "get_price"):
            method = getattr(self.cache, method_name, None)
            if not callable(method):
                continue

            try:
                value = method(symbol)
                price = _safe_float(value)
                if price is not None and price > 0:
                    return price
            except Exception:
                continue

        latest_tick = None
        for method_name in ("get_latest_tick", "latest_tick"):
            method = getattr(self.cache, method_name, None)
            if not callable(method):
                continue

            try:
                latest_tick = method(symbol)
                break
            except Exception:
                continue

        if isinstance(latest_tick, Mapping):
            for key in ("mid", "price", "last", "close", "bid", "ask"):
                price = _safe_float(latest_tick.get(key))
                if price is not None and price > 0:
                    return price

        return None

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_risk_approved(self, event: Any) -> None:
        payload = _safe_dict(getattr(event, "data", None))

        symbol = str(payload.get("symbol") or "").strip()
        if not symbol:
            await self._publish_risk_alert(
                symbol="",
                reason="Risk-approved event did not include a symbol.",
                metadata=payload,
            )
            return

        try:
            route = self.symbol_registry.primary_route(
                symbol,
                broker_key=payload.get("broker_key"),
                exchange=payload.get("exchange"),
            )
        except Exception as exc:
            self.logger.exception("route_resolution_failed symbol=%s", symbol)
            await self._publish_risk_alert(
                symbol=symbol,
                reason=f"Route resolution failed: {exc}",
                metadata=payload,
            )
            return

        if route is None:
            await self._publish_risk_alert(
                symbol=symbol,
                reason="No broker route available for approved signal.",
                metadata=dict(payload.get("metadata") or {}),
            )
            return

        broker = self.brokers.get(route.broker_key)
        if broker is None:
            await self._publish_risk_alert(
                symbol=symbol,
                reason=f"Broker {route.broker_key} is not registered.",
                metadata=dict(payload.get("metadata") or {}),
            )
            return

        size = _safe_float(payload.get("approved_size") or payload.get("size"), 0.0) or 0.0
        if size <= 0:
            await self._publish_risk_alert(
                symbol=symbol,
                reason="Approved order size is missing or invalid.",
                metadata=dict(payload.get("metadata") or {}),
            )
            return

        metadata = {
            **dict(payload.get("metadata") or {}),
            "raw_symbol": getattr(route, "raw_symbol", symbol),
            "account_id": getattr(route, "account_id", None),
            "risk_payload": payload,
            "confidence": payload.get("confidence"),
            "decision": payload.get("decision"),
            "regime_snapshot": payload.get("regime_snapshot"),
            "created_at": _utc_now_iso(),
        }

        command = OrderCommand(
            symbol=symbol,
            side=_normalize_side(payload.get("side")),
            size=size,
            broker_key=str(route.broker_key),
            exchange=str(getattr(route, "exchange", "") or payload.get("exchange") or ""),
            order_type=_normalize_order_type(payload.get("order_type")),
            limit_price=payload.get("limit_price"),
            stop_price=payload.get("stop_loss") or payload.get("stop_price"),
            take_profit=payload.get("take_profit"),
            strategy_name=str(payload.get("strategy_name") or "unknown").strip() or "unknown",
            metadata=metadata,
        )

        await self.execute(command, broker=broker)

    # ------------------------------------------------------------------
    # Public execution API
    # ------------------------------------------------------------------

    async def execute(
            self,
            command: OrderCommand,
            *,
            broker: Any,
            entry_price: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Execute an OrderCommand.

        Returns:
            Normalized broker result dict, or None if execution failed.
        """

        if broker is None:
            await self._publish_risk_alert(
                symbol=command.symbol,
                reason="Cannot execute order because broker is missing.",
                metadata=dict(command.metadata or {}),
            )
            return None

        order_id = f"{command.broker_key}-{uuid.uuid4().hex[:16]}"
        raw_symbol = str(command.metadata.get("raw_symbol") or command.symbol)

        expected_price = (
                _safe_float(command.limit_price)
                or self._latest_price(command.symbol)
                or _safe_float(entry_price)
                or 0.0
        )

        submission = {
            "order_id": order_id,
            "symbol": command.symbol,
            "raw_symbol": raw_symbol,
            "side": command.side,
            "size": command.size,
            "broker_key": command.broker_key,
            "exchange": command.exchange,
            "status": "submitted",
            "requested_price": expected_price or None,
            "strategy_name": command.strategy_name,
            "account_id": command.metadata.get("account_id"),
            "metadata": dict(command.metadata or {}),
            "timestamp": _utc_now_iso(),
        }

        await self.bus.publish(
            "order.submitted",
            submission,
            source="execution_engine",
        )

        retries = max(0, int(getattr(self.config, "execution_retry_attempts", 0) or 0))

        for attempt in range(retries + 1):
            try:
                raw_result = await self._send_order(
                    command,
                    raw_symbol=raw_symbol,
                    broker=broker,
                )

                result = self._normalize_broker_result(
                    command,
                    raw_result,
                    fallback_order_id=order_id,
                    raw_symbol=raw_symbol,
                    requested_price=expected_price,
                )

                await self._publish_execution_update(
                    command,
                    result=result,
                    fallback_order_id=order_id,
                    raw_symbol=raw_symbol,
                )

                await self._record_learning_trade(
                    command,
                    result=result,
                    entry_price=entry_price or expected_price,
                )

                return result

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                self.logger.exception(
                    "order_execution_failed broker=%s symbol=%s attempt=%s/%s",
                    command.broker_key,
                    raw_symbol,
                    attempt + 1,
                    retries + 1,
                    )

                if attempt >= retries:
                    await self._publish_risk_alert(
                        symbol=command.symbol,
                        reason=f"Execution failed: {exc}",
                        metadata=dict(command.metadata or {}),
                    )
                    return None

                await asyncio.sleep(min(2 ** attempt, 5.0))

        return None

    # ------------------------------------------------------------------
    # Broker order submission
    # ------------------------------------------------------------------

    async def _send_order(
            self,
            command: OrderCommand,
            *,
            raw_symbol: str,
            broker: Any,
    ) -> Any:
        latest_price = self._latest_price(command.symbol)

        order = {
            "symbol": raw_symbol,
            "side": command.side,
            "type": command.order_type,
            "amount": command.size,
            "price": command.limit_price,
            "expected_price": latest_price or command.limit_price,
            "stop_price": command.stop_price,
            "take_profit": command.take_profit,
            "params": dict(command.metadata.get("params") or {}),
            "liquidity_score": float(command.metadata.get("liquidity_score") or 1.0),
            "client_order_id": command.metadata.get("client_order_id"),
        }

        if command.stop_price is not None:
            order["params"]["stop_price"] = command.stop_price

        if command.take_profit is not None:
            order["params"]["take_profit"] = command.take_profit

        use_router = bool(command.metadata.get("use_router", True))

        if use_router:
            router = self._router_for(command.broker_key, broker)
            return await _maybe_await(router.execute(order))

        if hasattr(broker, "create_order") and callable(getattr(broker, "create_order")):
            return await _maybe_await(
                broker.create_order(
                    symbol=raw_symbol,
                    side=command.side,
                    amount=command.size,
                    type=command.order_type,
                    price=command.limit_price,
                    stop_price=command.stop_price,
                    params=dict(command.metadata.get("params") or {}),
                    take_profit=command.take_profit,
                )
            )

        if hasattr(broker, "place_order") and callable(getattr(broker, "place_order")):
            return await _maybe_await(broker.place_order(order))

        raise RuntimeError(
            f"Broker {command.broker_key} does not support create_order or place_order."
        )

    # ------------------------------------------------------------------
    # Result normalization
    # ------------------------------------------------------------------

    def _normalize_broker_result(
            self,
            command: OrderCommand,
            raw_result: Any,
            *,
            fallback_order_id: str,
            raw_symbol: str,
            requested_price: float | None,
    ) -> dict[str, Any]:
        payload = dict(raw_result or {}) if isinstance(raw_result, Mapping) else {"raw": raw_result}

        status = str(
            payload.get("status")
            or payload.get("state")
            or payload.get("order_status")
            or payload.get("result")
            or "executed"
        ).strip().lower()

        fill_price = (
                payload.get("average")
                or payload.get("avgPrice")
                or payload.get("avg_price")
                or payload.get("fill_price")
                or payload.get("filled_price")
                or payload.get("price")
                or command.limit_price
                or requested_price
        )

        filled_size = (
                payload.get("filled")
                or payload.get("filled_size")
                or payload.get("executedQty")
                or payload.get("amount")
                or payload.get("size")
                or command.size
        )

        fee_value = 0.0
        raw_fee = payload.get("fee")
        raw_fees = payload.get("fees")

        if isinstance(raw_fee, Mapping):
            fee_value = _safe_float(raw_fee.get("cost"), 0.0) or 0.0
        elif isinstance(raw_fees, list):
            total = 0.0
            for item in raw_fees:
                if isinstance(item, Mapping):
                    total += _safe_float(item.get("cost"), 0.0) or 0.0
                else:
                    total += _safe_float(item, 0.0) or 0.0
            fee_value = total
        else:
            fee_value = _safe_float(raw_fee or raw_fees, 0.0) or 0.0

        return {
            "id": str(
                payload.get("id")
                or payload.get("order_id")
                or payload.get("clientOrderId")
                or payload.get("client_order_id")
                or fallback_order_id
            ),
            "symbol": command.symbol,
            "raw_symbol": raw_symbol,
            "side": command.side,
            "size": _safe_float(filled_size, command.size) or command.size,
            "requested_size": command.size,
            "broker_key": command.broker_key,
            "exchange": command.exchange,
            "status": status,
            "fill_price": _safe_float(fill_price),
            "requested_price": _safe_float(requested_price),
            "fees": fee_value,
            "strategy_name": command.strategy_name,
            "account_id": command.metadata.get("account_id"),
            "timestamp": _utc_now_iso(),
            "raw_response": payload,
        }

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def _publish_execution_update(
            self,
            command: OrderCommand,
            *,
            result: Any,
            fallback_order_id: str,
            raw_symbol: str,
    ) -> None:
        payload = dict(result or {}) if isinstance(result, Mapping) else {"raw": result}

        status = str(
            payload.get("status")
            or payload.get("state")
            or payload.get("order_status")
            or "executed"
        ).strip().lower()

        fill_price = (
                payload.get("fill_price")
                or payload.get("average")
                or payload.get("avgPrice")
                or payload.get("price")
                or command.limit_price
        )

        update = ExecutionUpdate(
            order_id=str(
                payload.get("id")
                or payload.get("order_id")
                or payload.get("clientOrderId")
                or fallback_order_id
            ),
            symbol=command.symbol,
            side=command.side,
            size=float(
                payload.get("filled")
                or payload.get("amount")
                or payload.get("size")
                or command.size
            ),
            broker_key=command.broker_key,
            exchange=command.exchange,
            status=status,
            fill_price=float(fill_price) if fill_price not in (None, "") else None,
            requested_price=command.limit_price,
            fees=float(payload.get("fees") or payload.get("fee") or 0.0),
            strategy_name=command.strategy_name,
            account_id=command.metadata.get("account_id"),
            metadata={
                **dict(command.metadata or {}),
                "raw_symbol": raw_symbol,
                "raw_response": payload,
            },
        )

        await self.bus.publish(
            "order.executed",
            update.to_dict(),
            source="execution_engine",
        )

    async def _publish_risk_alert(
            self,
            *,
            symbol: str,
            reason: str,
            metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.bus.publish(
            "risk.alert",
            {
                "approved": False,
                "symbol": symbol,
                "reason": reason,
                "metadata": dict(metadata or {}),
                "timestamp": _utc_now_iso(),
            },
            source="execution_engine",
        )

    # ------------------------------------------------------------------
    # Learning feedback
    # ------------------------------------------------------------------

    async def _record_learning_trade(
            self,
            command: OrderCommand,
            *,
            result: dict[str, Any],
            entry_price: float | None,
    ) -> None:
        """
        Record a safe execution snapshot into LearningEngine.

        Important:
        This does NOT pretend the trade is closed. PnL is only recorded if the
        caller or broker result already provides it. Otherwise pnl is 0.0 and
        status remains the actual order status.
        """

        if self.learning_engine is None:
            return

        metadata = dict(command.metadata or {})
        risk_payload = dict(metadata.get("risk_payload") or {})
        regime_snapshot = dict(
            metadata.get("regime_snapshot")
            or risk_payload.get("regime_snapshot")
            or {}
        )

        fill_price = _safe_float(result.get("fill_price"))
        requested_price = _safe_float(result.get("requested_price"))
        entry_value = _safe_float(entry_price) or requested_price or fill_price or 0.0

        pnl = _safe_float(
            result.get("pnl")
            or result.get("realized_pnl")
            or result.get("profit")
            or metadata.get("pnl"),
            0.0,
            ) or 0.0

        confidence = _safe_float(
            metadata.get("confidence")
            or risk_payload.get("confidence"),
            0.0,
            ) or 0.0

        trade_payload = {
            "symbol": command.symbol,
            "broker_key": command.broker_key,
            "exchange": command.exchange,
            "side": command.side,
            "size": result.get("size", command.size),
            "status": result.get("status"),
            "pnl": pnl,
            "entry_price": entry_value,
            "fill_price": fill_price,
            "exit_price": result.get("exit_price"),
            "fees": result.get("fees", 0.0),
            "confidence": confidence,
            "decision": metadata.get("decision") or risk_payload.get("decision") or command.side,
            "strategy": command.strategy_name,
            "strategy_name": command.strategy_name,
            "market_regime": regime_snapshot.get("regime"),
            "atr": regime_snapshot.get("atr_pct") or regime_snapshot.get("atr"),
            "sl_hit": bool(result.get("sl_hit", False)),
            "tp_hit": bool(result.get("tp_hit", False)),
            "duration": result.get("duration") or result.get("trade_duration_seconds"),
            "order_id": result.get("id"),
            "timestamp": result.get("timestamp") or _utc_now_iso(),
            "metadata": {
                **metadata,
                "execution_result": result,
            },
        }

        try:
            record_trade = getattr(self.learning_engine, "record_trade", None)
            if callable(record_trade):
                await _maybe_await(record_trade(trade_payload))

            await self.bus.publish(
                "learning.trade_recorded",
                trade_payload,
                source="execution_engine",
            )

        except Exception:
            self.logger.debug(
                "learning_trade_record_failed symbol=%s order_id=%s",
                command.symbol,
                result.get("id"),
                exc_info=True,
            )