from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import math
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from events.event import Event


try:
    from broker.broker_errors import BrokerOperationError
except Exception:
    class BrokerOperationError(Exception):  # type: ignore
        category: str = "broker_error"
        raw_message: str = ""
        cooldown_seconds: float = 0.0
        rejection: bool = False
    raise




try:
    from events.event_bus.event_types import EventType
except Exception:
    try:
        from events.event_bus.event_types import EventType  # type: ignore
    except Exception:
        class EventType:  # type: ignore
            ORDER = "order"
            FILL = "fill"
            EXECUTION_REPORT = "execution.report"
            ORDER_UPDATE = "order.update"
            ORDER_FILLED = "order.filled"
        raise
    raise



if TYPE_CHECKING:
    from models.instrument import Instrument
    from models.order import Order


def _event_name(name: str, fallback: str) -> Any:
    member = getattr(EventType, name, fallback)
    if hasattr(member, "value"):
        try:
            return member.value
        except Exception:
            raise
    return member


def _event_data(event: Any) -> Any:
    if isinstance(event, dict):
        return event.get("data", event)
    if hasattr(event, "data"):
        return event.data
    if hasattr(event, "payload"):
        return event.payload
    return event


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class ExecutionManager:
    """Manages order execution and trade life cycle."""

    TERMINAL_ORDER_STATUSES = {
        "filled",
        "closed",
        "canceled",
        "cancelled",
        "rejected",
        "expired",
        "failed",
    }
    FILLED_ORDER_STATUSES = {"filled", "closed"}

    def __init__(
            self,
            broker: Any,
            event_bus: Any,
            router: Any,
            trade_repository: Any = None,
            trade_notifier: Any = None,
            behavior_guard: Any = None,
    ) -> None:
        self.broker = broker
        self.bus = event_bus
        self.router = router
        self.trade_repository = trade_repository
        self.trade_notifier = trade_notifier
        self.behavior_guard = behavior_guard
        self.logger = logging.getLogger("ExecutionManager")

        self.running = False
        self._symbol_cooldowns: dict[str, float] = {}
        self._symbol_skip_reasons: dict[str, str | None] = {}
        self._execution_lock = asyncio.Lock()
        self._balance_buffer = 0.98
        self._order_tracking_tasks: dict[str, asyncio.Task[Any]] = {}
        self._tracked_orders: dict[str, dict[str, Any]] = {}
        self._order_tracking_interval = 2.0
        self._order_tracking_timeout = 900.0

        self._subscriptions: list[tuple[Any, Any]] = []
        self._subscribe_events()

    # ------------------------------------------------------------------
    # Event bus helpers
    # ------------------------------------------------------------------

    def _bus_has_method(self, name: str) -> bool:
        return self.bus is not None and callable(getattr(self.bus, name, None))

    def _subscribe_events(self) -> None:
        if not self._bus_has_method("subscribe"):
            self.logger.warning("ExecutionManager received invalid event bus: %r", self.bus)
            return

        self._safe_subscribe(_event_name("ORDER", "order"), self.on_order)

    def _safe_subscribe(self, event_type: Any, handler: Any) -> None:
        try:
            self.bus.subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))
        except Exception as ex:
            self.logger.error("Unable to subscribe to event_type=%s\n"+ex.__str__(), event_type, exc_info=True)

    async def _publish(self, event_type: Any, payload: Any) -> Any:
        if not self._bus_has_method("publish"):
            return None

        try:
            try:
                return await _maybe_await(self.bus.publish(event_type, payload))
            except TypeError:
                return await _maybe_await(self.bus.publish(Event(event_type, payload)))
        except Exception as ex:
            self.logger.debug("Failed to publish event_type=%s "+ex.__str__(), event_type, exc_info=True)
            return None

    def _bus_has_subscribers(self, event_type: Any) -> bool:
        if self.bus is None:
            return False

        key = event_type.value if hasattr(event_type, "value") else str(event_type)

        subscribers = getattr(self.bus, "subscribers", None)
        if isinstance(subscribers, dict):
            return bool(subscribers.get(key) or subscribers.get("*"))

        internal = getattr(self.bus, "_subscribers", None)
        if isinstance(internal, dict):
            return bool(internal.get(key) or internal.get("*"))

        # If the bus does not expose subscribers, publish anyway.
        return True

    # ------------------------------------------------------------------
    # Life cycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False

        for task in list(self._order_tracking_tasks.values()):
            if task is not None and not task.done():
                task.cancel()

        for task in list(self._order_tracking_tasks.values()):
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._order_tracking_tasks.clear()
        self._tracked_orders.clear()

    async def on_order(self, event: Any) -> None:
        if not self.running:
            return

        payload = _event_data(event)

        try:
            await self.execute(payload)
        except Exception as ex:
            self.logger.exception("Execution error while handling order payload",ex)

    # ------------------------------------------------------------------
    # Cooldown / error classification
    # ------------------------------------------------------------------

    def _cooldown_remaining(self, symbol: str) -> float:
        expires_at = self._symbol_cooldowns.get(symbol)
        if expires_at is None:
            return 0.0

        remaining = expires_at - time.monotonic()
        if remaining <= 0:
            self._symbol_cooldowns.pop(symbol, None)
            return 0.0

        return remaining

    def _set_cooldown(self, symbol: str, seconds: float, reason: Any) -> None:
        self._symbol_cooldowns[symbol] = time.monotonic() + float(seconds or 0.0)
        self._symbol_skip_reasons[symbol] = str(reason or "").strip() or None
        self.logger.warning("Skipping %s for %.0fs: %s", symbol, seconds, reason)

    def last_skip_reason(self, symbol: str) -> str | None:
        return self._symbol_skip_reasons.get(symbol)

    def _classify_execution_exception(self, exc: Exception) -> dict[str, Any] | None:
        if isinstance(exc, BrokerOperationError):
            category = str(getattr(exc, "category", None) or "broker_error").strip().lower()
            defaults = {
                "rate_limit": 300.0,
                "network_error": 120.0,
                "insufficient_funds": 120.0,
                "invalid_order": 180.0,
                "unsupported_symbol": 300.0,
                "authentication_error": 600.0,
                "broker_error": 0.0,
            }
            rejected_categories = {
                "insufficient_funds",
                "invalid_order",
                "unsupported_symbol",
                "authentication_error",
            }
            return {
                "category": category,
                "reason": str(exc),
                "raw_message": getattr(exc, "raw_message", str(exc)),
                "cooldown_seconds": float(getattr(exc, "cooldown_seconds", 0.0) or defaults.get(category, 0.0) or 0.0),
                "rejected": bool(getattr(exc, "rejection", False) or category in rejected_categories),
            }

        message = str(exc or "")
        lowered = message.lower()

        for tokens, category, cooldown_seconds, rejected in (
                (("too many requests", "429"), "rate_limit", 300.0, False),
                (("market is closed", "min_notional", "minimum order", "minimum notional"), "invalid_order", 300.0, False),
                (
                        ("insufficient margin", "insufficient funds", "order rejected", "rejected", "rejectreason"),
                        "invalid_order",
                        120.0,
                        True,
                ),
        ):
            if any(token in lowered for token in tokens):
                return {
                    "category": category,
                    "reason": message,
                    "raw_message": message,
                    "cooldown_seconds": cooldown_seconds,
                    "rejected": rejected,
                }

        return None

    # ------------------------------------------------------------------
    # Numeric / broker helpers
    # ------------------------------------------------------------------

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
            return number if math.isfinite(number) else float(default)
        except Exception as ex:
            self.logger.error(ex)
            return float(default)

    async def _fetch_reference_price(self, symbol: str, side: str, requested_price: Any = None) -> float | None:
        if requested_price is not None:
            price = self._safe_float(requested_price, 0.0)
            return price if price > 0 else None

        if not hasattr(self.broker, "fetch_ticker"):
            return None

        try:
            ticker = await self.broker.fetch_ticker(symbol)
        except Exception as exc:
            self.logger.debug("Reference price fetch failed for %s: %s", symbol, exc)
            return None

        if not isinstance(ticker, dict):
            return None

        candidates = (
            ("ask", "askPrice", "price", "last", "close")
            if str(side).lower() == "buy"
            else ("bid", "bidPrice", "price", "last", "close")
        )

        for key in candidates:
            price = self._safe_float(ticker.get(key), 0.0)
            if price > 0:
                return price

        return None

    def _extract_free_balances(self, balance: Any) -> dict[str, Any]:
        if not isinstance(balance, dict):
            return {}

        if isinstance(balance.get("free"), dict):
            return dict(balance["free"])

        skip = {"free", "used", "total", "info", "raw", "equity", "cash", "currency"}
        return {k: v for k, v in balance.items() if k not in skip}

    def _get_market(self, symbol: str) -> dict[str, Any] | None:
        exchange = getattr(self.broker, "exchange", None)
        markets = getattr(exchange, "markets", None)
        if isinstance(markets, dict):
            market = markets.get(symbol)
            return dict(market) if isinstance(market, dict) else None
        return None

    def _uses_inventory_balance_checks(
            self,
            order: dict[str, Any],
            market: dict[str, Any] | None = None,
            balance: dict[str, Any] | None = None,
    ) -> bool:
        order = order or {}
        market = market if isinstance(market, dict) else {}
        balance = balance if isinstance(balance, dict) else {}

        exchange_name = str(order.get("exchange") or getattr(self.broker, "exchange_name", "") or "").strip().lower()
        if exchange_name == "oanda":
            return False

        requested_mode = str(order.get("requested_quantity_mode") or "").strip().lower()
        if requested_mode == "lots":
            return False

        instrument_type = str(order.get("instrument_type") or "").strip().lower()
        if not instrument_type and isinstance(order.get("instrument"), dict):
            instrument_type = str(order["instrument"].get("type") or "").strip().lower()
        if instrument_type in {"option", "future", "derivative"}:
            return False

        market_type = str(
            market.get("type")
            or market.get("market_type")
            or market.get("venue")
            or ""
        ).strip().lower()

        if market.get("otc") or market_type in {"otc", "margin", "swap", "future", "option", "derivative"}:
            return False
        if bool(market.get("contract")):
            return False

        raw_balance = balance.get("raw") if isinstance(balance, dict) else {}
        if isinstance(raw_balance, dict) and market.get("otc"):
            return False

        return True

    def _apply_amount_precision(self, symbol: str, amount: Any) -> float:
        amount_value = self._safe_float(amount, 0.0)

        exchange = getattr(self.broker, "exchange", None)
        if exchange and hasattr(exchange, "amount_to_precision"):
            try:
                return float(exchange.amount_to_precision(symbol, amount_value))
            except Exception as ex:
                self.logger.error(ex)
        return amount_value

    def _minimum_order_amount(self, market: dict[str, Any] | None, price: float | None) -> tuple[float, float, float]:
        limits = market.get("limits", {}) if isinstance(market, dict) else {}
        min_amount = self._safe_float(((limits.get("amount") or {}).get("min")), 0.0)
        min_cost = self._safe_float(((limits.get("cost") or {}).get("min")), 0.0)

        candidates = []
        if min_amount > 0:
            candidates.append(min_amount)
        if price and price > 0 and min_cost > 0:
            candidates.append(min_cost / price)

        return (max(candidates) if candidates else 0.0), min_amount, min_cost

    def _minimum_order_reason(
            self,
            symbol: str,
            amount: float,
            minimum_amount: float,
            base_currency: str | None = None,
            quote_currency: str | None = None,
            min_cost: float = 0.0,
    ) -> str:
        unit_label = base_currency or "units"
        reason = (
            f"Computed order size for {symbol} ({amount:.8f} {unit_label}) is below the venue minimum "
            f"({minimum_amount:.8f} {unit_label})."
        )
        if min_cost > 0:
            quote_label = quote_currency or "quote"
            reason += f" Minimum notional is {min_cost:.8f} {quote_label}."
        return reason

    # ------------------------------------------------------------------
    # Order status / extraction helpers
    # ------------------------------------------------------------------

    def _normalize_order_status(self, status: Any) -> str:
        normalized = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "cancelled": "canceled",
            "partiallyfilled": "partially_filled",
            "partial_fill": "partially_filled",
            "partial_filled": "partially_filled",
            "pending_new": "open",
            "accepted_for_bidding": "open",
            "done_for_day": "expired",
        }
        return mapping.get(normalized, normalized or "unknown")

    def _is_terminal_order_status(self, status: Any) -> bool:
        return self._normalize_order_status(status) in self.TERMINAL_ORDER_STATUSES

    def _extract_order_amount(self, execution: Any, fallback_amount: Any = 0.0) -> float:
        if not isinstance(execution, dict):
            return abs(self._safe_float(fallback_amount, 0.0))

        for key in ("amount", "qty", "quantity", "size", "filled_qty", "filled"):
            value = execution.get(key)
            if value is None:
                continue
            amount = abs(self._safe_float(value, 0.0))
            if amount > 0:
                return amount

        return abs(self._safe_float(fallback_amount, 0.0))

    def _extract_filled_amount(self, execution: Any, fallback_amount: Any = 0.0, status: Any = None) -> float:
        if not isinstance(execution, dict):
            return 0.0

        for key in ("filled", "filled_qty", "filled_amount", "executed_qty", "executedQty", "filled_quantity"):
            value = execution.get(key)
            if value is None:
                continue
            filled = abs(self._safe_float(value, 0.0))
            if filled > 0:
                return filled

        normalized_status = self._normalize_order_status(status or execution.get("status"))
        if normalized_status in self.FILLED_ORDER_STATUSES:
            return self._extract_order_amount(execution, fallback_amount=fallback_amount)

        return 0.0

    def _extract_order_price(self, execution: Any, fallback_price: Any = None) -> float | None:
        if not isinstance(execution, dict):
            return self._safe_float(fallback_price, 0.0) if fallback_price not in (None, "") else None

        for key in ("average", "average_price", "avgPrice", "filled_avg_price", "fill_price", "price"):
            value = execution.get(key)
            if value is None:
                continue
            price = self._safe_float(value, 0.0)
            if price > 0:
                return price

        return self._safe_float(fallback_price, 0.0) if fallback_price not in (None, "") else None

    def _extract_fee_cost(self, execution: Any) -> float | None:
        if not isinstance(execution, dict):
            return None

        fee = execution.get("fee")
        if isinstance(fee, dict):
            value = fee.get("cost")
            if value not in (None, ""):
                return self._safe_float(value, 0.0)

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

        return None

    def _extract_fee_currency(self, execution: Any) -> str | None:
        if not isinstance(execution, dict):
            return None

        fee = execution.get("fee")
        if isinstance(fee, dict):
            currency = fee.get("currency")
            if currency:
                return str(currency)

        fees = execution.get("fees")
        if isinstance(fees, list):
            for item in fees:
                if not isinstance(item, dict):
                    continue
                currency = item.get("currency")
                if currency:
                    return str(currency)

        return None

    # ------------------------------------------------------------------
    # Trade payload / persistence / publishing
    # ------------------------------------------------------------------

    def _build_trade_payload(self, execution: Any, submitted_order: Any) -> dict[str, Any]:
        execution = dict(execution or {}) if isinstance(execution, dict) else {}
        submitted_order = dict(submitted_order or {}) if isinstance(submitted_order, dict) else {}

        status = self._normalize_order_status(execution.get("status") or submitted_order.get("status"))
        timestamp = execution.get("timestamp") or submitted_order.get("timestamp") or datetime.now(timezone.utc).isoformat()

        actual_price = self._extract_order_price(execution, fallback_price=submitted_order.get("price"))
        expected_price = execution.get("expected_price", submitted_order.get("expected_price"))
        expected_price = self._safe_float(expected_price, 0.0) if expected_price not in (None, "") else None

        size = self._extract_order_amount(execution, fallback_amount=submitted_order.get("amount", 0.0))
        filled_size = self._extract_filled_amount(
            execution,
            fallback_amount=submitted_order.get("amount", 0.0),
            status=status,
        )

        side = str(execution.get("side") or submitted_order.get("side") or "").upper()

        slippage_abs = None
        slippage_bps = None
        slippage_cost = None

        if actual_price not in (None, "") and expected_price not in (None, 0, ""):
            direction = 1.0 if side == "BUY" else -1.0 if side == "SELL" else 1.0
            slippage_abs = (float(actual_price) - float(expected_price)) * direction
            slippage_bps = (slippage_abs / float(expected_price)) * 10000.0
            executed_size = filled_size if filled_size > 0 else size
            slippage_cost = slippage_abs * float(executed_size or 0.0)

        fee_cost = execution.get("fee", submitted_order.get("fee"))
        if fee_cost in (None, ""):
            fee_cost = self._extract_fee_cost(execution)

        fee_currency = (
                execution.get("fee_currency")
                or submitted_order.get("fee_currency")
                or self._extract_fee_currency(execution)
        )

        execution_quality = execution.get("execution_quality") or submitted_order.get("execution_quality") or {}
        execution_strategy = (
                execution.get("execution_strategy")
                or submitted_order.get("execution_strategy")
                or (execution_quality.get("algorithm") if isinstance(execution_quality, dict) else None)
        )

        return {
            "symbol": execution.get("symbol") or submitted_order.get("symbol"),
            "side": side,
            "source": str(execution.get("source") or submitted_order.get("source") or "bot").strip().lower() or "bot",
            "exchange": execution.get("exchange") or submitted_order.get("exchange") or getattr(self.broker, "exchange_name", None),
            "price": actual_price,
            "size": size,
            "filled_size": filled_size,
            "order_type": execution.get("type") or submitted_order.get("type"),
            "status": status,
            "order_id": execution.get("id") or execution.get("order_id") or submitted_order.get("id") or submitted_order.get("order_id"),
            "timestamp": timestamp,
            "stop_price": execution.get("stop_price", submitted_order.get("stop_price")),
            "stop_loss": execution.get("stop_loss", submitted_order.get("stop_loss")),
            "take_profit": execution.get("take_profit", submitted_order.get("take_profit")),
            "pnl": execution.get("pnl", submitted_order.get("pnl")),
            "reason": execution.get("reason") or submitted_order.get("reason"),
            "strategy_name": execution.get("strategy_name") or submitted_order.get("strategy_name"),
            "confidence": execution.get("confidence", submitted_order.get("confidence")),
            "expected_price": expected_price,
            "spread_abs": execution.get("spread_abs", submitted_order.get("spread_abs")),
            "spread_bps": execution.get("spread_bps", submitted_order.get("spread_bps")),
            "slippage_abs": slippage_abs,
            "slippage_bps": slippage_bps,
            "slippage_cost": slippage_cost,
            "fee": fee_cost,
            "fee_currency": fee_currency,
            "setup": execution.get("setup") or submitted_order.get("setup"),
            "outcome": execution.get("outcome") or submitted_order.get("outcome"),
            "lessons": execution.get("lessons") or submitted_order.get("lessons"),
            "blocked_by_guard": bool(execution.get("blocked_by_guard", submitted_order.get("blocked_by_guard", False))),
            "execution_strategy": execution_strategy,
            "execution_quality": execution_quality if isinstance(execution_quality, dict) else {},
            "timeframe": execution.get("timeframe") or submitted_order.get("timeframe"),
            "decision_id": execution.get("decision_id") or submitted_order.get("decision_id"),
            "signal_timestamp": execution.get("signal_timestamp") or submitted_order.get("signal_timestamp"),
            "feature_snapshot": execution.get("feature_snapshot") or submitted_order.get("feature_snapshot"),
            "feature_version": execution.get("feature_version") or submitted_order.get("feature_version"),
            "regime_snapshot": execution.get("regime_snapshot") or submitted_order.get("regime_snapshot"),
            "market_regime": execution.get("market_regime") or submitted_order.get("market_regime"),
            "volatility_regime": execution.get("volatility_regime") or submitted_order.get("volatility_regime"),
            "signal_source_agent": execution.get("signal_source_agent") or submitted_order.get("signal_source_agent"),
            "consensus_status": execution.get("consensus_status") or submitted_order.get("consensus_status"),
            "adaptive_weight": execution.get("adaptive_weight", submitted_order.get("adaptive_weight")),
            "adaptive_score": execution.get("adaptive_score", submitted_order.get("adaptive_score")),
            "requested_amount": execution.get("requested_amount", submitted_order.get("requested_amount")),
            "requested_quantity_mode": execution.get("requested_quantity_mode", submitted_order.get("requested_quantity_mode")),
            "requested_amount_units": execution.get("requested_amount_units", submitted_order.get("requested_amount_units")),
            "error_category": execution.get("error_category", submitted_order.get("error_category")),
            "deterministic_amount_units": execution.get("deterministic_amount_units", submitted_order.get("deterministic_amount_units")),
            "amount_units": execution.get("amount_units", submitted_order.get("amount_units")),
            "applied_requested_mode_amount": execution.get("applied_requested_mode_amount", submitted_order.get("applied_requested_mode_amount")),
            "size_adjusted": bool(execution.get("size_adjusted", submitted_order.get("size_adjusted", False))),
            "ai_adjusted": bool(execution.get("ai_adjusted", submitted_order.get("ai_adjusted", False))),
            "sizing_summary": execution.get("sizing_summary") or submitted_order.get("sizing_summary"),
            "sizing_notes": execution.get("sizing_notes") or submitted_order.get("sizing_notes"),
            "ai_sizing_reason": execution.get("ai_sizing_reason") or submitted_order.get("ai_sizing_reason"),
        }

    def _payload_fingerprint(self, payload: dict[str, Any]) -> tuple[Any, ...]:
        return (
            payload.get("status"),
            payload.get("price"),
            payload.get("size"),
            payload.get("filled_size"),
            payload.get("pnl"),
            payload.get("slippage_bps"),
            payload.get("fee"),
            payload.get("timestamp"),
        )

    async def _persist_trade_update(self, payload: dict[str, Any]) -> None:
        if self.trade_repository is not None:
            try:
                saver = getattr(self.trade_repository, "save_or_update_trade", None)
                if saver is None:
                    saver = getattr(self.trade_repository, "save_trade")

                await asyncio.to_thread(
                    saver,
                    payload.get("symbol"),
                    payload.get("side"),
                    payload.get("size", 0.0),
                    payload.get("price") if payload.get("price") is not None else 0.0,
                    getattr(self.broker, "exchange_name", None),
                    payload.get("order_id"),
                    payload.get("order_type"),
                    payload.get("status"),
                    payload.get("timestamp"),
                    payload.get("source"),
                    payload.get("pnl"),
                    payload.get("strategy_name"),
                    payload.get("reason"),
                    payload.get("confidence"),
                    payload.get("expected_price"),
                    payload.get("spread_bps"),
                    payload.get("slippage_bps"),
                    payload.get("fee"),
                    payload.get("stop_loss"),
                    payload.get("take_profit"),
                    payload.get("setup"),
                    payload.get("outcome"),
                    payload.get("lessons"),
                    payload.get("timeframe"),
                    payload.get("signal_source_agent"),
                    payload.get("consensus_status"),
                    payload.get("adaptive_weight"),
                    payload.get("adaptive_score"),
                )
            except Exception as exc:
                self.logger.debug("Trade persistence failed for %s: %s", payload.get("symbol"), exc)

        if callable(self.trade_notifier):
            try:
                self.trade_notifier(dict(payload))
            except Exception as exc:
                self.logger.debug("Trade notification failed for %s: %s", payload.get("symbol"), exc)

    async def _publish_execution_report(self, payload: dict[str, Any], execution: Any, submitted_order: Any) -> None:
        if not self._bus_has_subscribers(_event_name("EXECUTION_REPORT", "execution.report")):
            return

        report = dict(payload or {})
        if isinstance(execution, dict):
            report["raw_execution"] = dict(execution)
        if isinstance(submitted_order, dict):
            report["submitted_order"] = dict(submitted_order)

        await self._publish(_event_name("EXECUTION_REPORT", "execution.report"), report)

    async def _publish_fill_delta(self, payload: dict[str, Any], tracker_state: dict[str, Any]) -> None:
        filled_size = max(self._safe_float(payload.get("filled_size"), 0.0), 0.0)
        previous_filled = max(self._safe_float(tracker_state.get("filled_size"), 0.0), 0.0)
        delta = filled_size - previous_filled

        if delta <= 0:
            return

        fill_payload = {
            "symbol": payload.get("symbol"),
            "side": payload.get("side"),
            "qty": delta,
            "quantity": delta,
            "price": payload.get("price"),
            "order_id": payload.get("order_id"),
            "timestamp": payload.get("timestamp"),
        }

        await self._publish(_event_name("FILL", "fill"), fill_payload)
        await self._publish(_event_name("ORDER_FILLED", "order.filled"), fill_payload)

    async def _handle_order_update(self, execution: Any, submitted_order: Any, allow_tracking: bool = True) -> dict[str, Any]:
        payload = self._build_trade_payload(execution, submitted_order)
        order_id = str(payload.get("order_id") or "").strip()
        tracker_state = self._tracked_orders.get(order_id, {}) if order_id else {}

        await self._publish_fill_delta(payload, tracker_state)

        if self.behavior_guard is not None:
            try:
                self.behavior_guard.record_trade_update(payload)
            except Exception as exc:
                self.logger.debug("Behavior guard trade update failed for %s: %s", payload.get("symbol"), exc)

        fingerprint = self._payload_fingerprint(payload)

        if fingerprint != tracker_state.get("fingerprint"):
            await self._persist_trade_update(payload)
            await self._publish_execution_report(payload, execution, submitted_order)
            await self._publish(_event_name("ORDER_UPDATE", "order.update"), payload)

        if order_id:
            self._tracked_orders[order_id] = {
                "fingerprint": fingerprint,
                "filled_size": payload.get("filled_size", 0.0),
                "status": payload.get("status"),
                "symbol": payload.get("symbol"),
            }

        if order_id and allow_tracking and not self._is_terminal_order_status(payload.get("status")):
            self._ensure_order_tracking(order_id, payload.get("symbol"), dict(submitted_order or {}))

        if order_id and self._is_terminal_order_status(payload.get("status")):
            task = self._order_tracking_tasks.pop(order_id, None)
            if task is not None and not task.done():
                task.cancel()
            self._tracked_orders.pop(order_id, None)

        return payload

    # ------------------------------------------------------------------
    # Order tracking
    # ------------------------------------------------------------------

    def _ensure_order_tracking(self, order_id: str, symbol: str, submitted_order: dict[str, Any]) -> None:
        if not order_id or not hasattr(self.broker, "fetch_order"):
            return

        task = self._order_tracking_tasks.get(order_id)
        if task is not None and not task.done():
            return

        self._order_tracking_tasks[order_id] = asyncio.create_task(
            self._track_order_until_terminal(order_id, symbol, submitted_order)
        )

    async def _track_order_until_terminal(self, order_id: str, symbol: str, submitted_order: dict[str, Any]) -> None:
        started_at = time.monotonic()

        try:
            while time.monotonic() - started_at <= self._order_tracking_timeout:
                await asyncio.sleep(self._order_tracking_interval)

                try:
                    try:
                        snapshot = await self.broker.fetch_order(order_id, symbol=symbol)
                    except TypeError:
                        snapshot = await self.broker.fetch_order(order_id)
                except NotImplementedError:
                    self.logger.debug("Broker does not support fetch_order tracking for %s", order_id)
                    return
                except Exception as exc:
                    self.logger.debug("Order status refresh failed for %s: %s", order_id, exc)
                    continue

                if not isinstance(snapshot, dict):
                    continue

                payload = await self._handle_order_update(snapshot, submitted_order, allow_tracking=False)
                if self._is_terminal_order_status(payload.get("status")):
                    return

        except asyncio.CancelledError:
            raise
        finally:
            await self._order_tracking_tasks.pop(order_id, None)

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    async def _prepare_order(self, order: dict[str, Any]) -> dict[str, Any] | None:
        symbol = str(order["symbol"]).strip().upper()
        side = str(order["side"]).strip().lower()

        if self._cooldown_remaining(symbol) > 0:
            return None

        market = self._get_market(symbol)
        if market is not None and market.get("active") is False:
            self._set_cooldown(symbol, 300, "market is inactive")
            return None

        price = await self._fetch_reference_price(symbol, side, order.get("price"))

        spread_abs = None
        spread_bps = None

        if hasattr(self.broker, "fetch_ticker"):
            try:
                ticker = await self.broker.fetch_ticker(symbol)
            except Exception as ex:
                ticker = None
                self.logger.error(ex)


            if isinstance(ticker, dict):
                bid = self._safe_float(ticker.get("bid") or ticker.get("bidPrice"), 0.0)
                ask = self._safe_float(ticker.get("ask") or ticker.get("askPrice"), 0.0)

                if 0 < bid <= ask and ask > 0:
                    spread_abs = ask - bid
                    denominator = float(price or ask or bid or 0.0)
                    if denominator > 0:
                        spread_bps = (spread_abs / denominator) * 10000.0

        amount = self._safe_float(order["amount"], 0.0)

        parts = str(symbol).split("/", 1)
        base_currency = parts[0] if parts else None
        quote_currency = parts[1] if len(parts) > 1 else None

        balance_snapshot: dict[str, Any] = {}
        balance: dict[str, Any] = {}

        if hasattr(self.broker, "fetch_balance"):
            try:
                balance_snapshot = await self.broker.fetch_balance()
                balance = self._extract_free_balances(balance_snapshot)
            except Exception as exc:
                self.logger.debug("Balance fetch failed for %s: %s", symbol, exc)

        enforce_inventory_checks = self._uses_inventory_balance_checks(
            order,
            market=market,
            balance=balance_snapshot,
        )

        available_quote = None
        available_base = None

        if quote_currency and enforce_inventory_checks:
            available_quote = self._safe_float(balance.get(quote_currency), 0.0)
        if base_currency and enforce_inventory_checks:
            available_base = self._safe_float(balance.get(base_currency), 0.0)

        if side == "buy" and price and available_quote is not None:
            spendable_quote = available_quote * self._balance_buffer
            if spendable_quote <= 0:
                self._set_cooldown(symbol, 120, f"no available {quote_currency} balance")
                return None
            amount = min(amount, spendable_quote / price)

        if side == "sell" and available_base is not None:
            liquid_base = available_base * self._balance_buffer
            if liquid_base <= 0:
                self._set_cooldown(symbol, 120, f"no available {base_currency} balance")
                return None
            amount = min(amount, liquid_base)

        minimum_amount, _min_amount, min_cost = self._minimum_order_amount(market, price)

        if minimum_amount > 0 and amount + 1e-12 < minimum_amount:
            self._set_cooldown(
                symbol,
                120,
                self._minimum_order_reason(
                    symbol,
                    amount,
                    minimum_amount,
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    min_cost=min_cost,
                ),
            )
            return None

        amount = self._apply_amount_precision(symbol, amount)

        if amount <= 0:
            self._set_cooldown(symbol, 120, "computed order amount is zero")
            return None

        if minimum_amount > 0 and amount + 1e-12 < minimum_amount:
            self._set_cooldown(
                symbol,
                120,
                self._minimum_order_reason(
                    symbol,
                    amount,
                    minimum_amount,
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    min_cost=min_cost,
                ),
            )
            return None

        if (
                side == "buy"
                and price
                and available_quote is not None
                and amount * price > (available_quote * self._balance_buffer) + 1e-12
        ):
            self._set_cooldown(symbol, 120, f"insufficient {quote_currency} balance")
            return None

        if (
                side == "sell"
                and available_base is not None
                and amount > (available_base * self._balance_buffer) + 1e-12
        ):
            self._set_cooldown(symbol, 120, f"insufficient {base_currency} balance")
            return None

        prepared = dict(order)
        prepared["symbol"] = symbol
        prepared["side"] = side
        prepared["amount"] = amount
        prepared["quantity"] = amount
        prepared["expected_price"] = price
        prepared["spread_abs"] = spread_abs
        prepared["spread_bps"] = spread_bps

        if order.get("price") is not None:
            prepared["price"] = order["price"]

        return prepared

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, signal: Any = None, **kwargs: Any) -> dict[str, Any] | None:
        try:
            from models.instrument import Instrument
        except Exception as ex:
            Instrument = None  # type: ignore
            self.logger.error(ex)

        try:
            from models.order import Order
        except Exception as ex:
            Order = None  # type: ignore
            self.logger.error(ex)

        if signal is None:
            signal = {}
        elif Order is not None and isinstance(signal, Order):
            signal = signal.to_dict()
        elif isinstance(signal, Mapping):
            signal = dict(signal)
        elif hasattr(signal, "to_dict") and callable(getattr(signal, "to_dict")):
            signal = dict(signal.to_dict())
        elif not isinstance(signal, dict):
            raise TypeError("signal must be a dict when provided")

        order = {**dict(signal), **kwargs}

        instrument_payload = order.get("instrument")
        instrument = None

        if instrument_payload and Instrument is not None:
            try:
                instrument = Instrument.from_mapping(instrument_payload)
            except Exception as ex:
                instrument = None
                self.logger.error(ex)

        symbol = order.get("symbol") or (instrument.symbol if instrument is not None else None)
        side = order.get("side") or order.get("signal")
        amount = order.get("amount")
        if amount is None:
            amount = order.get("size", order.get("quantity"))

        price = order.get("price")
        order_type = str(order.get("order_type") or order.get("type", "market") or "market").strip().lower().replace(" ", "_")
        stop_price = order.get("stop_price")
        stop_loss = order.get("stop_loss")
        take_profit = order.get("take_profit")
        params = dict(order.get("params") or {})

        if not symbol:
            raise ValueError("Order symbol is required")
        if not side:
            raise ValueError("Order side is required")
        if amount is None:
            raise ValueError("Order amount is required")

        normalized_side = str(side).lower().strip()
        if normalized_side not in {"buy", "sell"}:
            raise ValueError(f"Unsupported order side: {side}")

        if order_type == "stop_limit":
            if price is None:
                raise ValueError("stop_limit orders require a limit price")
            if stop_price is None:
                raise ValueError("stop_limit orders require a stop_price trigger")

        normalized_order: dict[str, Any] = {
            "symbol": str(symbol).strip().upper(),
            "side": normalized_side,
            "source": str(order.get("source") or "bot").strip().lower() or "bot",
            "exchange": order.get("exchange") or getattr(self.broker, "exchange_name", None),
            "amount": amount,
            "quantity": amount,
            "type": order_type,
            "order_type": order_type,
        }

        if instrument is not None:
            normalized_order["instrument"] = instrument.to_dict()
            normalized_order["instrument_type"] = instrument.type.value
        elif order.get("instrument") is not None:
            normalized_order["instrument"] = order.get("instrument")
        elif order.get("instrument_type") is not None:
            normalized_order["instrument_type"] = order.get("instrument_type")

        if price is not None:
            normalized_order["price"] = price
        if stop_price is not None:
            normalized_order["stop_price"] = stop_price
        if stop_loss is not None:
            normalized_order["stop_loss"] = stop_loss
        if take_profit is not None:
            normalized_order["take_profit"] = take_profit

        for extra_key in (
                "reason",
                "confidence",
                "strategy_name",
                "expected_price",
                "spread_abs",
                "spread_bps",
                "pnl",
                "execution_strategy",
                "timeframe",
                "decision_id",
                "signal_timestamp",
                "feature_snapshot",
                "feature_version",
                "regime_snapshot",
                "market_regime",
                "volatility_regime",
                "signal_source_agent",
                "consensus_status",
                "adaptive_weight",
                "adaptive_score",
                "broker",
                "time_in_force",
                "client_order_id",
                "account_id",
                "requested_amount",
                "requested_quantity_mode",
                "requested_amount_units",
                "deterministic_amount_units",
                "amount_units",
                "applied_requested_mode_amount",
                "size_adjusted",
                "ai_adjusted",
                "sizing_summary",
                "sizing_notes",
                "ai_sizing_reason",
                "metadata",
        ):
            if order.get(extra_key) is not None:
                normalized_order[extra_key] = order.get(extra_key)

        if order.get("legs") is not None:
            normalized_order["legs"] = list(order.get("legs") or [])
        if params:
            normalized_order["params"] = params

        async with self._execution_lock:
            if self.behavior_guard is not None:
                try:
                    allowed, guard_reason, _guard_snapshot = self.behavior_guard.evaluate_order(normalized_order)
                except Exception as exc:
                    self.logger.debug("Behavior guard evaluation failed for %s: %s", symbol, exc)
                    allowed, guard_reason = True, "Allowed"

                if not allowed:
                    blocked_order = dict(normalized_order)
                    blocked_order["timestamp"] = datetime.now(timezone.utc).isoformat()
                    blocked_order["reason"] = guard_reason
                    blocked_order["blocked_by_guard"] = True

                    with contextlib.suppress(Exception):
                        self.behavior_guard.record_order_attempt(blocked_order, allowed=False, reason=guard_reason)

                    rejected_execution = {
                        "symbol": symbol,
                        "side": normalized_order["side"],
                        "source": normalized_order.get("source", "bot"),
                        "amount": normalized_order.get("amount"),
                        "type": normalized_order.get("type", order_type),
                        "price": normalized_order.get("price"),
                        "status": "rejected",
                        "reason": guard_reason,
                        "blocked_by_guard": True,
                        "raw": {"error": guard_reason},
                    }
                    await self._handle_order_update(rejected_execution, blocked_order, allow_tracking=False)
                    return rejected_execution

            prepared_order = await self._prepare_order(normalized_order)
            if prepared_order is None:
                return None

            if self.behavior_guard is not None:
                with contextlib.suppress(Exception):
                    self.behavior_guard.record_order_attempt(prepared_order, allowed=True, reason="submitted")

            try:
                route = getattr(self.router, "route", None)
                if not callable(route):
                    raise RuntimeError("Order router does not expose route(order)")

                execution = route(prepared_order)
                execution = await _maybe_await(execution)

            except Exception as exc:
                classification = self._classify_execution_exception(exc)
                if classification is None:
                    raise

                reason = classification["reason"]
                cooldown_seconds = float(classification.get("cooldown_seconds") or 0.0)

                if cooldown_seconds > 0:
                    self._set_cooldown(str(symbol), cooldown_seconds, reason)

                if not classification.get("rejected"):
                    return None

                prepared_order["timestamp"] = datetime.now(timezone.utc).isoformat()

                rejected_execution = {
                    "symbol": symbol,
                    "side": normalized_order["side"],
                    "source": prepared_order.get("source", normalized_order.get("source", "bot")),
                    "amount": prepared_order.get("amount"),
                    "type": prepared_order.get("type", order_type),
                    "price": prepared_order.get("price"),
                    "status": "rejected",
                    "reason": reason,
                    "error_category": classification.get("category"),
                    "raw": {
                        "error": classification.get("raw_message", reason),
                        "category": classification.get("category"),
                    },
                }
                await self._handle_order_update(rejected_execution, prepared_order, allow_tracking=False)
                return rejected_execution

            prepared_order["timestamp"] = datetime.now(timezone.utc).isoformat()

            if isinstance(execution, dict):
                execution.setdefault("source", prepared_order.get("source", normalized_order.get("source", "bot")))
            else:
                execution = {
                    "status": "submitted",
                    "raw": execution,
                    "symbol": prepared_order.get("symbol"),
                    "side": prepared_order.get("side"),
                    "amount": prepared_order.get("amount"),
                    "price": prepared_order.get("price"),
                }

            await self._handle_order_update(execution, prepared_order)
            self._symbol_skip_reasons.pop(str(symbol), None)

            return execution

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "cooldowns": dict(self._symbol_cooldowns),
            "skip_reasons": dict(self._symbol_skip_reasons),
            "tracked_orders": dict(self._tracked_orders),
            "tracking_tasks": len(self._order_tracking_tasks),
            "balance_buffer": self._balance_buffer,
        }


__all__ = ["ExecutionManager"]