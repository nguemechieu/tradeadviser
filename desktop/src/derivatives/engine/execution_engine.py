from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Mapping
from typing import Any

from derivatives.core.config import EngineConfig
from derivatives.core.event_bus import EventBus
from derivatives.core.models import ExecutionUpdate, OrderCommand
from derivatives.core.symbols import SymbolRegistry

from derivatives.data.live_cache.cache.live_market_cache import LiveMarketCache
from execution.smart_router import SmartRouter
from  core.ai.learning_engine import LearningEngine

from execution.smart_router import SmartRouter



class ExecutionEngine:
    def __init__(
        self,
        event_bus: EventBus,
        cache: LiveMarketCache,
        symbol_registry: SymbolRegistry,
        brokers: dict[str, Any],
        *,
        config: EngineConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.cache = cache
        self.symbol_registry = symbol_registry
        self.brokers = dict(brokers or {})
        self.config = config or EngineConfig()
        self.logger = logger or logging.getLogger("DerivativesExecutionEngine")
        self._routers: dict[str, SmartRouter] = {}
        self.bus.subscribe("risk.approved", self._on_risk_approved)


        self.learning_engine=LearningEngine()

    def _router_for(self, broker_key: str, broker: Any) -> SmartRouter:
        router = self._routers.get(broker_key)
        if router is None:
            router = SmartRouter(broker)
            self._routers[broker_key] = router
        return router

    async def _on_risk_approved(self, event) -> None:
        payload = dict(event.data or {})
        symbol = str(payload.get("symbol") or "").strip()
        if not symbol:
            return
        route = self.symbol_registry.primary_route(
            symbol,
            broker_key=payload.get("broker_key"),
            exchange=payload.get("exchange"),
        )
        if route is None:
            await self.bus.publish(
                "risk.alert",
                {
                    "approved": False,
                    "symbol": symbol,
                    "reason": "No broker route available for approved signal.",
                    "metadata": dict(payload.get("metadata") or {}),
                },
                source="execution_engine",
            )
            return

        broker = self.brokers.get(route.broker_key)
        if broker is None:
            await self.bus.publish(
                "risk.alert",
                {
                    "approved": False,
                    "symbol": symbol,
                    "reason": f"Broker {route.broker_key} is not registered.",
                    "metadata": dict(payload.get("metadata") or {}),
                },
                source="execution_engine",
            )
            return

        command = OrderCommand(
            symbol=symbol,
            side=str(payload.get("side") or "buy").strip().lower(),
            size=float(payload.get("approved_size") or 0.0),
            broker_key=route.broker_key,
            exchange=route.exchange,
            order_type=str(payload.get("order_type") or "market").strip().lower(),
            limit_price=payload.get("limit_price"),
            stop_price=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
            strategy_name=str(payload.get("strategy_name") or "unknown"),
            metadata={
                **dict(payload.get("metadata") or {}),
                "raw_symbol": route.raw_symbol,
                "account_id": route.account_id,
            },
        )
        await self.execute(command, broker=broker)

    async def execute(self, command: OrderCommand, *, broker: Any) -> dict[str, Any] | None:
        order_id = f"{command.broker_key}-{uuid.uuid4().hex[:16]}"
        raw_symbol = str(command.metadata.get("raw_symbol") or command.symbol)
        expected_price = float(command.limit_price or self.cache.latest_price(command.symbol) or 0.0)
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
            "metadata": dict(command.metadata),
        }
        await self.bus.publish("order.submitted", submission, source="execution_engine")

        retries = max(0, int(self.config.execution_retry_attempts or 0))
        for attempt in range(retries + 1):
            try:
                result = await self._send_order(command, raw_symbol=raw_symbol, broker=broker)
                await self._publish_execution_update(command, result=result, fallback_order_id=order_id, raw_symbol=raw_symbol)

                self.learning_engine.record_trade({
                "pnl": pnl,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "confidence": review.get("confidence"),
                "decision": review.get("decision"),
                "strategy": review.get("strategy_name"),
                "market_regime": review.get("regime_snapshot", {}).get("regime"),
                "atr": review.get("regime_snapshot", {}).get("atr_pct"),
                "sl_hit": hit_stop_loss,
                "tp_hit": hit_take_profit,
                "duration": trade_duration_seconds,
            })


                return result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.exception(
                    "order_execution_failed broker=%s symbol=%s attempt=%s",
                    command.broker_key,
                    raw_symbol,
                    attempt + 1,
                )
                if attempt >= retries:
                    await self.bus.publish(
                        "risk.alert",
                        {
                            "approved": False,
                            "symbol": command.symbol,
                            "reason": f"Execution failed: {exc}",
                            "metadata": dict(command.metadata),
                        },
                        source="execution_engine",
                    )
                    return None
                await asyncio.sleep(min(2 ** attempt, 5.0))
        return None

    async def _send_order(self, command: OrderCommand, *, raw_symbol: str, broker: Any) -> Any:
        order = {
            "symbol": raw_symbol,
            "side": command.side,
            "type": command.order_type,
            "amount": command.size,
            "price": command.limit_price,
            "expected_price": self.cache.latest_price(command.symbol) or command.limit_price,
            "stop_price": command.stop_price,
            "take_profit": command.take_profit,
            "params": dict(command.metadata.get("params") or {}),
            "liquidity_score": float(command.metadata.get("liquidity_score") or 1.0),
        }
        if command.stop_price is not None:
            order["params"]["stop_price"] = command.stop_price
        if command.metadata.get("use_router", True):
            router = self._router_for(command.broker_key, broker)
            return await router.execute(order)
        if hasattr(broker, "create_order"):
            return await broker.create_order(
                symbol=raw_symbol,
                side=command.side,
                amount=command.size,
                type=command.order_type,
                price=command.limit_price,
                stop_price=command.stop_price,
                params=dict(command.metadata.get("params") or {}),
                take_profit=command.take_profit,
            )
        return await broker.place_order(order)

    async def _publish_execution_update(
        self,
        command: OrderCommand,
        *,
        result: Any,
        fallback_order_id: str,
        raw_symbol: str,
    ) -> None:
        payload = dict(result or {}) if isinstance(result, Mapping) else {"raw": result}
        status = str(payload.get("status") or payload.get("state") or payload.get("order_status") or "executed").strip().lower()
        fill_price = payload.get("average") or payload.get("avgPrice") or payload.get("fill_price") or payload.get("price") or command.limit_price
        fees = payload.get("fees") or payload.get("fee") or 0.0
        update = ExecutionUpdate(
            order_id=str(payload.get("id") or payload.get("order_id") or payload.get("clientOrderId") or fallback_order_id),
            symbol=command.symbol,
            side=command.side,
            size=float(payload.get("filled") or payload.get("amount") or payload.get("size") or command.size),
            broker_key=command.broker_key,
            exchange=command.exchange,
            status=status,
            fill_price=float(fill_price) if fill_price not in (None, "") else None,
            requested_price=command.limit_price,
            fees=float(fees or 0.0),
            strategy_name=command.strategy_name,
            account_id=command.metadata.get("account_id"),
            metadata={**dict(command.metadata), "raw_symbol": raw_symbol, "raw_response": payload},
        )
        await self.bus.publish("order.executed", update.to_dict(), source="execution_engine")
