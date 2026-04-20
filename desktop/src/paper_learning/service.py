from __future__ import annotations

from collections import defaultdict, deque

from event_bus.event_types import EventType
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


class PaperTradingLearningService:
    """Tracks paper trade lifecycle state from signals and execution reports."""

    FILLED_STATUSES = {"filled", "closed"}

    def __init__(
        self,
        *,
        event_bus,
        repository,
        feature_extractor=None,
        trade_logger=None,
        exchange_resolver=None,
        enabled=True,
        tracked_sources=None,
        pending_signal_limit=1024,
    ):
        self.event_bus = event_bus
        self.repository = repository
        self.feature_extractor = feature_extractor or PaperTradeFeatureExtractor()
        self.trade_logger = trade_logger or PaperTradeLogger(repository=repository, event_bus=event_bus)
        self.exchange_resolver = exchange_resolver
        self.enabled = bool(enabled)
        self.tracked_sources = {str(item).strip().lower() for item in (tracked_sources or {"bot"}) if str(item).strip()}
        self.pending_signal_limit = max(16, int(pending_signal_limit or 1024))
        self._pending_signals = {}
        self._signal_index_by_symbol = defaultdict(deque)
        self._active_trades = {}

        self.event_bus.subscribe(EventType.SIGNAL, self._on_signal)
        self.event_bus.subscribe(EventType.EXECUTION_REPORT, self._on_execution_report)

    async def _on_signal(self, event):
        if not self.enabled:
            return

        context = dict(getattr(event, "data", {}) or {})
        snapshot = self.feature_extractor.build_signal_snapshot(context)
        if snapshot is None or not self._should_capture_exchange(snapshot.exchange):
            return
        if self.tracked_sources and snapshot.source not in self.tracked_sources:
            return

        self._pending_signals[snapshot.decision_id] = snapshot
        queue = self._signal_index_by_symbol[snapshot.symbol]
        queue.append(snapshot.decision_id)
        while len(self._pending_signals) > self.pending_signal_limit:
            pruned = None
            for symbol_queue in self._signal_index_by_symbol.values():
                if symbol_queue:
                    pruned = symbol_queue.popleft()
                    break
            if pruned is None:
                break
            self._pending_signals.pop(pruned, None)

        await self.trade_logger.log_event(
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

    async def _on_execution_report(self, event):
        if not self.enabled:
            return

        report = dict(getattr(event, "data", {}) or {})
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
        quantity = max(
            0.0,
            coerce_float(report.get("filled_size"), None)
            or coerce_float(report.get("size"), 0.0)
            or 0.0,
        )
        price = coerce_float(report.get("price"), None)
        status = str(report.get("status") or "").strip().lower() or "unknown"
        decision_id = str(report.get("decision_id") or "").strip() or None
        trade = self._active_trades.get(symbol)
        snapshot = self._resolve_signal_snapshot(symbol=symbol, decision_id=decision_id)

        await self.trade_logger.log_event(
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
                order_id=str(report.get("order_id") or "").strip() or None,
                price=price,
                quantity=quantity,
                confidence=coerce_float(report.get("confidence"), None),
                payload=report,
            )
        )

        if side is None or price is None or quantity <= 0 or status not in self.FILLED_STATUSES:
            return

        if trade is None:
            opening_snapshot = snapshot or self._synthetic_snapshot(report, exchange=exchange, source=source, side=side, timestamp=timestamp)
            trade = ActivePaperTrade.from_signal_snapshot(
                opening_snapshot,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                order_id=report.get("order_id"),
            )
            self._active_trades[symbol] = trade
            await self.trade_logger.log_event(
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
            return

        if trade.side == side:
            trade.absorb_entry(
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                order_id=report.get("order_id"),
                confidence=coerce_float(report.get("confidence"), None),
                decision_id=decision_id,
            )
            await self.trade_logger.log_event(
                PaperTradeEvent(
                    event_type="trade_scaled",
                    symbol=symbol,
                    timestamp=timestamp,
                    trade_id=trade.trade_id,
                    decision_id=decision_id,
                    exchange=trade.exchange,
                    source=trade.source,
                    strategy_name=trade.strategy_name,
                    timeframe=trade.timeframe,
                    side=trade.side,
                    signal=trade.signal,
                    order_status=status,
                    order_id=str(report.get("order_id") or "").strip() or None,
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
            return

        remaining = quantity
        while remaining > 1e-12 and trade is not None:
            closed = trade.realize_exit(
                quantity=remaining,
                price=price,
                timestamp=timestamp,
                order_id=report.get("order_id"),
                decision_id=decision_id,
            )
            remaining = max(0.0, remaining - closed)
            await self.trade_logger.log_event(
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
                    order_id=str(report.get("order_id") or "").strip() or None,
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
            if trade.is_closed:
                record = trade.to_trade_record()
                await self.trade_logger.log_record(record)
                await self.trade_logger.log_event(
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
                        order_id=report.get("order_id"),
                    )
                    self._active_trades[symbol] = trade
                    await self.trade_logger.log_event(
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
                            payload={"trade_id": trade.trade_id, "quantity": trade.quantity},
                        )
                    )

    def _resolve_signal_snapshot(self, *, symbol, decision_id=None):
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

    def _synthetic_snapshot(self, report, *, exchange, source, side, timestamp):
        signal_time = coerce_datetime(report.get("signal_timestamp"), timestamp)
        regime_snapshot = dict(report.get("regime_snapshot") or {})
        return PaperSignalSnapshot(
            decision_id=str(report.get("decision_id") or "").strip() or "synthetic",
            symbol=str(report.get("symbol") or "").strip().upper(),
            signal=side,
            timeframe=str(report.get("timeframe") or "1h").strip() or "1h",
            strategy_name=str(report.get("strategy_name") or "").strip() or None,
            source=source,
            exchange=exchange,
            confidence=coerce_float(report.get("confidence"), None),
            signal_price=coerce_float(report.get("expected_price"), None) or coerce_float(report.get("price"), None),
            signal_timestamp=signal_time,
            feature_values=dict(report.get("feature_snapshot") or {}),
            feature_version=str(report.get("feature_version") or "").strip() or None,
            market_regime=str(report.get("market_regime") or regime_snapshot.get("regime") or "unknown").strip() or "unknown",
            volatility_regime=str(report.get("volatility_regime") or regime_snapshot.get("volatility") or "unknown").strip() or "unknown",
            regime_snapshot=regime_snapshot,
            metadata={
                "reason": str(report.get("reason") or "").strip() or None,
                "signal_source_agent": str(report.get("signal_source_agent") or "").strip() or None,
            },
        )

    def _active_exchange(self):
        resolver = self.exchange_resolver
        if not callable(resolver):
            return None
        try:
            return resolver()
        except Exception:
            return None

    def _should_capture_exchange(self, exchange):
        normalized = str(exchange or self._active_exchange() or "").strip().lower()
        return normalized == "paper"
