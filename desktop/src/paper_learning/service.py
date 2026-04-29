from __future__ import annotations

import inspect
import logging
from collections import defaultdict, deque
from typing import Any

try:
    from events.event_bus.event_types import EventType
except Exception:
    try:
        from events.event_bus.event_types import EventType  # type: ignore
    except Exception:
        class EventType:  # type: ignore
            SIGNAL = "signal"
            SIGNAL_CREATED = "signal.created"
            EXECUTION_REPORT = "execution.report"


from paper_learning.feature_extractor import PaperTradeFeatureExtractor
from paper_learning.models import (
    ActivePaperTrade,
    PaperSignalSnapshot,
    PaperTradeEvent,
    coerce_datetime,
    coerce_float,
    normalize_side,
)
from paper_learning.trade_logger import PaperTradeLogger


def _event_name(name: str, fallback: str) -> Any:
    member = getattr(EventType, name, fallback)
    if hasattr(member, "value"):
        try:
            return member.value
        except Exception:
            pass
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


class PaperTradingLearningService:
    """Tracks paper trade lifecycle state from signals and execution reports."""

    FILLED_STATUSES = {"filled", "closed"}
    TERMINAL_STATUSES = {"filled", "closed", "canceled", "cancelled", "rejected", "expired", "failed"}

    def __init__(
            self,
            *,
            event_bus: Any,
            repository: Any,
            feature_extractor: Any = None,
            trade_logger: Any = None,
            exchange_resolver: Any = None,
            enabled: bool = True,
            tracked_sources: set[str] | list[str] | tuple[str, ...] | None = None,
            pending_signal_limit: int = 1024,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        self.event_bus = event_bus
        self.repository = repository
        self.feature_extractor = feature_extractor or PaperTradeFeatureExtractor()
        self.trade_logger = trade_logger or PaperTradeLogger(repository=repository, event_bus=event_bus)
        self.exchange_resolver = exchange_resolver
        self.enabled = bool(enabled)
        self.tracked_sources = {
            str(item).strip().lower()
            for item in (tracked_sources or {"bot"})
            if str(item).strip()
        }
        self.pending_signal_limit = max(16, int(pending_signal_limit or 1024))

        self._pending_signals: dict[str, PaperSignalSnapshot] = {}
        self._signal_index_by_symbol: dict[str, deque[str]] = defaultdict(deque)
        self._active_trades: dict[str, ActivePaperTrade] = {}
        self._subscriptions: list[tuple[Any, Any]] = []

        self._subscribe_events()

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        subscribe = getattr(self.event_bus, "subscribe", None)

        if not callable(subscribe):
            self.logger.warning(
                "PaperTradingLearningService received invalid event_bus=%r; service will not receive events.",
                self.event_bus,
            )
            return

        self._safe_subscribe(_event_name("SIGNAL", "signal"), self._on_signal)
        self._safe_subscribe(_event_name("SIGNAL_CREATED", "signal.created"), self._on_signal)
        self._safe_subscribe(_event_name("EXECUTION_REPORT", "execution.report"), self._on_execution_report)

    def _safe_subscribe(self, event_type: Any, handler: Any) -> None:
        try:
            self.event_bus.subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))
        except Exception:
            self.logger.debug("Unable to subscribe to event_type=%s", event_type, exc_info=True)

    def unsubscribe_all(self) -> None:
        unsubscribe = getattr(self.event_bus, "unsubscribe", None)
        if not callable(unsubscribe):
            self._subscriptions.clear()
            return

        for event_type, handler in list(self._subscriptions):
            try:
                unsubscribe(event_type, handler)
            except Exception:
                pass

        self._subscriptions.clear()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def active_trades_snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            symbol: trade.to_dict()
            for symbol, trade in self._active_trades.items()
            if hasattr(trade, "to_dict")
        }

    def pending_signal_count(self) -> int:
        return len(self._pending_signals)

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "tracked_sources": sorted(self.tracked_sources),
            "pending_signal_count": len(self._pending_signals),
            "active_trade_count": len(self._active_trades),
            "active_symbols": sorted(self._active_trades.keys()),
            "subscriptions": [
                str(event_type.value if hasattr(event_type, "value") else event_type)
                for event_type, _handler in self._subscriptions
            ],
        }

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_signal(self, event: Any) -> None:
        if not self.enabled:
            return

        context = _event_data(event)
        if not isinstance(context, dict):
            return

        try:
            snapshot = self.feature_extractor.build_signal_snapshot(context)
            snapshot = await _maybe_await(snapshot)
        except Exception:
            self.logger.debug("Unable to build paper signal snapshot", exc_info=True)
            return

        if snapshot is None:
            return

        if not self._should_capture_exchange(snapshot.exchange):
            return

        snapshot_source = str(snapshot.source or "").strip().lower()
        if self.tracked_sources and snapshot_source not in self.tracked_sources:
            return

        self._store_pending_signal(snapshot)

        await self._log_event(
            PaperTradeEvent(
                event_type="signal_received",
                symbol=snapshot.symbol,
                timestamp=snapshot.signal_timestamp,
                decision_id=snapshot.decision_id,
                exchange=snapshot.exchange,
                source=snapshot.source,
                strategy_name=snapshot.strategy_name,
                timeframe=snapshot.timeframe,
                side=snapshot.signal,
                signal=snapshot.signal,
                price=snapshot.signal_price,
                confidence=snapshot.confidence,
                payload=snapshot.to_dict(),
            )
        )

    async def _on_execution_report(self, event: Any) -> None:
        if not self.enabled:
            return

        report = _event_data(event)
        if not isinstance(report, dict):
            return

        symbol = str(report.get("symbol") or "").strip().upper()
        if not symbol:
            return

        exchange = str(report.get("exchange") or self._active_exchange() or "").strip().lower() or "paper"
        source = str(report.get("source") or "bot").strip().lower() or "bot"

        if not self._should_capture_exchange(exchange):
            return

        if self.tracked_sources and source not in self.tracked_sources:
            return

        timestamp = coerce_datetime(report.get("timestamp"))
        side = normalize_side(report.get("side"))
        status = str(report.get("status") or "").strip().lower() or "unknown"
        decision_id = str(report.get("decision_id") or "").strip() or None
        order_id = str(report.get("order_id") or "").strip() or None

        quantity = max(
            0.0,
            coerce_float(report.get("filled_size"), None)
            or coerce_float(report.get("filled_quantity"), None)
            or coerce_float(report.get("quantity"), None)
            or coerce_float(report.get("qty"), None)
            or coerce_float(report.get("size"), 0.0)
            or 0.0,
            )
        price = (
                coerce_float(report.get("price"), None)
                or coerce_float(report.get("average_price"), None)
                or coerce_float(report.get("fill_price"), None)
                or coerce_float(report.get("expected_price"), None)
        )

        trade = self._active_trades.get(symbol)
        snapshot = self._resolve_signal_snapshot(symbol=symbol, decision_id=decision_id)

        await self._log_event(
            PaperTradeEvent(
                event_type="execution_report",
                symbol=symbol,
                timestamp=timestamp,
                trade_id=trade.trade_id if trade is not None else None,
                decision_id=decision_id,
                exchange=exchange,
                source=source,
                strategy_name=str(report.get("strategy_name") or "").strip() or None,
                timeframe=str(report.get("timeframe") or "").strip() or None,
                side=side,
                signal=snapshot.signal if snapshot is not None else side,
                order_status=status,
                order_id=order_id,
                price=price,
                quantity=quantity,
                confidence=coerce_float(report.get("confidence"), None),
                payload=report,
            )
        )

        if side is None or price is None or quantity <= 0:
            return

        if status not in self.FILLED_STATUSES:
            # Non-filled reports are logged above but should not alter lifecycle state.
            return

        await self._apply_filled_execution(
            report=report,
            symbol=symbol,
            exchange=exchange,
            source=source,
            side=side,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            decision_id=decision_id,
            order_id=order_id,
            snapshot=snapshot,
            status=status,
        )

    # ------------------------------------------------------------------
    # Lifecycle logic
    # ------------------------------------------------------------------

    async def _apply_filled_execution(
            self,
            *,
            report: dict[str, Any],
            symbol: str,
            exchange: str,
            source: str,
            side: str,
            quantity: float,
            price: float,
            timestamp: Any,
            decision_id: str | None,
            order_id: str | None,
            snapshot: PaperSignalSnapshot | None,
            status: str,
    ) -> None:
        trade = self._active_trades.get(symbol)

        if trade is None:
            await self._open_trade(
                report=report,
                symbol=symbol,
                exchange=exchange,
                source=source,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                order_id=order_id,
                snapshot=snapshot,
                status=status,
            )
            return

        if trade.side == side:
            await self._scale_trade(
                trade=trade,
                report=report,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                decision_id=decision_id,
                order_id=order_id,
                status=status,
            )
            return

        await self._exit_or_reverse_trade(
            report=report,
            symbol=symbol,
            exchange=exchange,
            source=source,
            side=side,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            decision_id=decision_id,
            order_id=order_id,
            snapshot=snapshot,
            status=status,
        )

    async def _open_trade(
            self,
            *,
            report: dict[str, Any],
            symbol: str,
            exchange: str,
            source: str,
            side: str,
            quantity: float,
            price: float,
            timestamp: Any,
            order_id: str | None,
            snapshot: PaperSignalSnapshot | None,
            status: str,
    ) -> ActivePaperTrade:
        opening_snapshot = snapshot or self._synthetic_snapshot(
            report,
            exchange=exchange,
            source=source,
            side=side,
            timestamp=timestamp,
        )

        trade = ActivePaperTrade.from_signal_snapshot(
            opening_snapshot,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            order_id=order_id,
        )

        self._active_trades[symbol] = trade

        await self._log_event(
            PaperTradeEvent(
                event_type="trade_opened",
                symbol=symbol,
                timestamp=timestamp,
                trade_id=trade.trade_id,
                decision_id=trade.decision_id,
                exchange=trade.exchange,
                source=trade.source,
                strategy_name=trade.strategy_name,
                timeframe=trade.timeframe,
                side=trade.side,
                signal=trade.signal,
                order_status=status,
                order_id=trade.entry_order_id,
                price=trade.entry_price,
                quantity=trade.quantity,
                confidence=trade.confidence,
                payload={
                    "trade_id": trade.trade_id,
                    "entry_price": trade.entry_price,
                    "quantity": trade.quantity,
                },
            )
        )

        return trade

    async def _scale_trade(
            self,
            *,
            trade: ActivePaperTrade,
            report: dict[str, Any],
            side: str,
            quantity: float,
            price: float,
            timestamp: Any,
            decision_id: str | None,
            order_id: str | None,
            status: str,
    ) -> None:
        trade.absorb_entry(
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            order_id=order_id,
            confidence=coerce_float(report.get("confidence"), None),
            decision_id=decision_id,
        )

        await self._log_event(
            PaperTradeEvent(
                event_type="trade_scaled",
                symbol=trade.symbol,
                timestamp=timestamp,
                trade_id=trade.trade_id,
                decision_id=decision_id,
                exchange=trade.exchange,
                source=trade.source,
                strategy_name=trade.strategy_name,
                timeframe=trade.timeframe,
                side=side,
                signal=trade.signal,
                order_status=status,
                order_id=order_id,
                price=price,
                quantity=quantity,
                confidence=trade.confidence,
                payload={
                    "trade_id": trade.trade_id,
                    "entry_price": trade.entry_price,
                    "quantity": trade.quantity,
                    "remaining_quantity": trade.remaining_quantity,
                },
            )
        )

    async def _exit_or_reverse_trade(
            self,
            *,
            report: dict[str, Any],
            symbol: str,
            exchange: str,
            source: str,
            side: str,
            quantity: float,
            price: float,
            timestamp: Any,
            decision_id: str | None,
            order_id: str | None,
            snapshot: PaperSignalSnapshot | None,
            status: str,
    ) -> None:
        remaining = quantity
        trade = self._active_trades.get(symbol)

        while remaining > 1e-12 and trade is not None:
            closed = trade.realize_exit(
                quantity=remaining,
                price=price,
                timestamp=timestamp,
                order_id=order_id,
                decision_id=decision_id,
            )

            remaining = max(0.0, remaining - closed)

            await self._log_event(
                PaperTradeEvent(
                    event_type="trade_exit",
                    symbol=symbol,
                    timestamp=timestamp,
                    trade_id=trade.trade_id,
                    decision_id=decision_id,
                    exchange=trade.exchange,
                    source=trade.source,
                    strategy_name=trade.strategy_name,
                    timeframe=trade.timeframe,
                    side=side,
                    signal=trade.signal,
                    order_status=status,
                    order_id=order_id,
                    price=price,
                    quantity=closed,
                    confidence=trade.confidence,
                    payload={
                        "trade_id": trade.trade_id,
                        "remaining_quantity": trade.remaining_quantity,
                        "realized_pnl": trade.realized_pnl,
                    },
                )
            )

            if not trade.is_closed:
                break

            record = trade.to_trade_record()
            await self._log_record(record)

            await self._log_event(
                PaperTradeEvent(
                    event_type="trade_closed",
                    symbol=symbol,
                    timestamp=record.exit_timestamp,
                    trade_id=record.trade_id,
                    decision_id=record.decision_id,
                    exchange=record.exchange,
                    source=record.source,
                    strategy_name=record.strategy_name,
                    timeframe=record.timeframe,
                    side=record.side,
                    signal=record.signal,
                    order_status="closed",
                    order_id=record.exit_order_id,
                    price=record.exit_price,
                    quantity=record.quantity,
                    confidence=record.confidence,
                    payload=record.to_dict(),
                )
            )

            self._active_trades.pop(symbol, None)
            trade = None

            if remaining > 1e-12:
                opening_snapshot = snapshot or self._synthetic_snapshot(
                    report,
                    exchange=exchange,
                    source=source,
                    side=side,
                    timestamp=timestamp,
                )

                trade = ActivePaperTrade.from_signal_snapshot(
                    opening_snapshot,
                    quantity=remaining,
                    price=price,
                    timestamp=timestamp,
                    order_id=order_id,
                )

                self._active_trades[symbol] = trade

                await self._log_event(
                    PaperTradeEvent(
                        event_type="trade_reversed",
                        symbol=symbol,
                        timestamp=timestamp,
                        trade_id=trade.trade_id,
                        decision_id=trade.decision_id,
                        exchange=trade.exchange,
                        source=trade.source,
                        strategy_name=trade.strategy_name,
                        timeframe=trade.timeframe,
                        side=trade.side,
                        signal=trade.signal,
                        order_status="filled",
                        order_id=trade.entry_order_id,
                        price=trade.entry_price,
                        quantity=trade.quantity,
                        confidence=trade.confidence,
                        payload={
                            "trade_id": trade.trade_id,
                            "quantity": trade.quantity,
                        },
                    )
                )

    # ------------------------------------------------------------------
    # Signal cache
    # ------------------------------------------------------------------

    def _store_pending_signal(self, snapshot: PaperSignalSnapshot) -> None:
        self._pending_signals[snapshot.decision_id] = snapshot

        queue = self._signal_index_by_symbol[snapshot.symbol]
        queue.append(snapshot.decision_id)

        self._prune_pending_signals()

    def _prune_pending_signals(self) -> None:
        while len(self._pending_signals) > self.pending_signal_limit:
            pruned = None

            for symbol_queue in self._signal_index_by_symbol.values():
                while symbol_queue:
                    candidate_id = symbol_queue.popleft()
                    if candidate_id in self._pending_signals:
                        pruned = candidate_id
                        break
                if pruned is not None:
                    break

            if pruned is None:
                break

            self._pending_signals.pop(pruned, None)

    def _resolve_signal_snapshot(self, *, symbol: str, decision_id: str | None = None) -> PaperSignalSnapshot | None:
        if decision_id:
            snapshot = self._pending_signals.pop(decision_id, None)
            if snapshot is not None:
                return snapshot

        queue = self._signal_index_by_symbol.get(symbol) or deque()

        while queue:
            candidate_id = queue.pop()
            snapshot = self._pending_signals.pop(candidate_id, None)
            if snapshot is not None:
                return snapshot

        return None

    # ------------------------------------------------------------------
    # Snapshot synthesis / filters
    # ------------------------------------------------------------------

    def _synthetic_snapshot(
            self,
            report: dict[str, Any],
            *,
            exchange: str,
            source: str,
            side: str,
            timestamp: Any,
    ) -> PaperSignalSnapshot:
        signal_time = coerce_datetime(report.get("signal_timestamp"), timestamp)
        regime_snapshot = dict(report.get("regime_snapshot") or {})

        decision_id = str(report.get("decision_id") or "").strip()
        if not decision_id:
            decision_id = f"synthetic-{str(report.get('order_id') or '').strip() or id(report)}"

        return PaperSignalSnapshot(
            decision_id=decision_id,
            symbol=str(report.get("symbol") or "").strip().upper(),
            signal=side,
            timeframe=str(report.get("timeframe") or "1h").strip() or "1h",
            strategy_name=str(report.get("strategy_name") or "").strip() or None,
            source=source,
            exchange=exchange,
            confidence=coerce_float(report.get("confidence"), None),
            signal_price=coerce_float(report.get("expected_price"), None)
                         or coerce_float(report.get("price"), None),
            signal_timestamp=signal_time,
            feature_values=dict(report.get("feature_snapshot") or {}),
            feature_version=str(report.get("feature_version") or "").strip() or None,
            market_regime=str(
                report.get("market_regime")
                or regime_snapshot.get("regime")
                or "unknown"
            ).strip()
                          or "unknown",
            volatility_regime=str(
                report.get("volatility_regime")
                or regime_snapshot.get("volatility")
                or "unknown"
            ).strip()
                              or "unknown",
            regime_snapshot=regime_snapshot,
            metadata={
                "reason": str(report.get("reason") or "").strip() or None,
                "signal_source_agent": str(report.get("signal_source_agent") or "").strip() or None,
                "synthetic": True,
            },
        )

    def _active_exchange(self) -> str | None:
        resolver = self.exchange_resolver
        if not callable(resolver):
            return None

        try:
            value = resolver()
        except Exception:
            return None

        return str(value or "").strip().lower() or None

    def _should_capture_exchange(self, exchange: Any) -> bool:
        normalized = str(exchange or self._active_exchange() or "").strip().lower()
        return normalized == "paper"

    # ------------------------------------------------------------------
    # Logging wrappers
    # ------------------------------------------------------------------

    async def _log_event(self, event: PaperTradeEvent) -> None:
        try:
            result = self.trade_logger.log_event(event)
            await _maybe_await(result)
        except Exception:
            self.logger.debug("Failed to log paper trade event=%s", getattr(event, "event_type", None), exc_info=True)

    async def _log_record(self, record: Any) -> None:
        try:
            result = self.trade_logger.log_record(record)
            await _maybe_await(result)
        except Exception:
            self.logger.debug("Failed to log paper trade record=%s", getattr(record, "trade_id", None), exc_info=True)


__all__ = ["PaperTradingLearningService"]