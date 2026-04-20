from __future__ import annotations

import copy
from collections import defaultdict, deque
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Iterable

from core.event_bus import AsyncEventBus
from core.models import Candle, ExecutionReport, OrderBookSnapshot, PortfolioSnapshot, PositionUpdate
class RuntimeStateCache:
    """Maintain a replayable in-memory view of the event-driven runtime."""

    def __init__(
        self,
        *,
        candle_capacity: int = 512,
        recent_event_capacity: int = 256,
        seen_event_capacity: int = 4096,
    ) -> None:
        self.candle_capacity = max(1, int(candle_capacity))
        self.recent_event_capacity = max(1, int(recent_event_capacity))
        self.seen_event_capacity = max(1, int(seen_event_capacity))
        self._attached_bus: AsyncEventBus | None = None
        self.clear()

    def clear(self) -> None:
        self.latest_by_event_type: dict[str, Any] = {}
        self.market_ticks: dict[str, dict[str, Any]] = {}
        self.order_books: dict[str, dict[str, Any]] = {}
        self.candles: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.candle_capacity)
        )
        self.signals: dict[str, dict[str, Any]] = {}
        self.trade_reviews: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.order_ids_by_symbol: dict[str, deque[str]] = defaultdict(
            lambda: deque(maxlen=self.recent_event_capacity)
        )
        self.positions: dict[str, dict[str, Any]] = {}
        self.portfolio_snapshot: dict[str, Any] | None = None
        self.performance_metrics: dict[str, Any] | None = None
        self.mobile_dashboard_snapshot: dict[str, Any] | None = None
        self.risk_alerts: deque[dict[str, Any]] = deque(maxlen=self.recent_event_capacity)
        self.alerts: deque[dict[str, Any]] = deque(maxlen=self.recent_event_capacity)
        self.trade_feedback: deque[dict[str, Any]] = deque(maxlen=self.recent_event_capacity)
        self.trade_journal_entries: deque[dict[str, Any]] = deque(maxlen=self.recent_event_capacity)
        self.trade_journal_summaries: deque[dict[str, Any]] = deque(maxlen=self.recent_event_capacity)
        self.recent_events: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.recent_event_capacity)
        )
        self._seen_event_ids: deque[str] = deque()
        self._seen_event_id_set: set[str] = set()

    def attach(self, bus: AsyncEventBus) -> "RuntimeStateCache":
        if self._attached_bus is bus:
            return self
        if self._attached_bus is not None:
            self._attached_bus.unsubscribe(AsyncEventBus.ALL_EVENTS, self.apply_event)
        bus.subscribe(AsyncEventBus.ALL_EVENTS, self.apply_event)
        self._attached_bus = bus
        return self

    async def rebuild_from_bus(
        self,
        bus: AsyncEventBus,
        *,
        event_types: Iterable[str] | None = None,
        limit: int | None = None,
        clear: bool = False,
    ) -> int:
        if clear:
            self.clear()
        events = await bus.replay(event_types=event_types, limit=limit, handler=self.apply_event)
        return len(events)

    async def apply_event(self, event) -> None:
        event_id = str(getattr(event, "id", "") or "").strip()
        if event_id and not self._remember_event_id(event_id):
            return

        event_type = str(getattr(event, "type", "") or "")
        payload = self._normalize_payload(getattr(event, "data", None))
        self.latest_by_event_type[event_type] = copy.deepcopy(payload)
        self.recent_events[event_type].append(self._event_record(event_type, payload, event))

        symbol = str((payload or {}).get("symbol") or "").strip()

        if event_type in {"MARKET_DATA", "MARKET_DATA_EVENT", "MARKET_TICK", "PRICE_UPDATE"} and symbol:
            self.market_ticks[symbol] = copy.deepcopy(payload)
            return

        if event_type in {"CANDLE", "HISTORICAL_CANDLE"}:
            candle = self._normalize_payload(getattr(event, "data", None), model=Candle)
            candle_symbol = str(candle.get("symbol") or "").strip()
            timeframe = str(candle.get("timeframe") or "").strip()
            if candle_symbol and timeframe:
                self.candles[(candle_symbol, timeframe)].append(candle)
            return

        if event_type == "ORDER_BOOK" and symbol:
            self.order_books[symbol] = self._normalize_payload(getattr(event, "data", None), model=OrderBookSnapshot)
            return

        if event_type in {"SIGNAL", "SIGNAL_EVENT", "SIGNAL_CREATED", "SIGNAL_VALIDATED", "DECISION_EVENT", "DECISION_MADE"} and symbol:
            self.signals[symbol] = copy.deepcopy(payload)
            return

        if event_type in {"RISK_APPROVED", "RISK_REJECTED"} and symbol:
            self.trade_reviews[symbol] = copy.deepcopy(payload)
            return

        if event_type in {
            "ORDER_SUBMITTED",
            "ORDER_UPDATE",
            "ORDER_PARTIALLY_FILLED",
            "ORDER_FILLED",
            "EXECUTION_REPORT",
        }:
            if event_type != "ORDER_SUBMITTED":
                payload = self._normalize_payload(getattr(event, "data", None), model=ExecutionReport)
            order_id = str((payload or {}).get("order_id") or (payload or {}).get("id") or "").strip()
            if order_id:
                snapshot = {**self.orders.get(order_id, {}), **dict(payload or {})}
                snapshot["event_type"] = event_type
                self.orders[order_id] = snapshot
                if symbol:
                    order_ids = self.order_ids_by_symbol[symbol]
                    if order_id not in order_ids:
                        order_ids.append(order_id)
            return

        if event_type in {"POSITION", "POSITION_EVENT", "POSITION_UPDATE"} and symbol:
            if event_type == "POSITION_UPDATE":
                payload = self._normalize_payload(getattr(event, "data", None), model=PositionUpdate)
            self.positions[symbol] = copy.deepcopy(payload)
            return

        if event_type == "PORTFOLIO_SNAPSHOT":
            self.portfolio_snapshot = self._normalize_payload(getattr(event, "data", None), model=PortfolioSnapshot)
            return

        if event_type == "PERFORMANCE_METRICS":
            self.performance_metrics = copy.deepcopy(payload)
            return

        if event_type == "MOBILE_DASHBOARD_UPDATE":
            self.mobile_dashboard_snapshot = copy.deepcopy(payload)
            return

        if event_type == "RISK_ALERT":
            self.risk_alerts.append(copy.deepcopy(payload))
            return

        if event_type == "ALERT_EVENT":
            self.alerts.append(copy.deepcopy(payload))
            return

        if event_type == "TRADE_FEEDBACK":
            self.trade_feedback.append(copy.deepcopy(payload))
            return

        if event_type == "TRADE_JOURNAL_ENTRY":
            self.trade_journal_entries.append(copy.deepcopy(payload))
            return

        if event_type == "TRADE_JOURNAL_SUMMARY":
            self.trade_journal_summaries.append(copy.deepcopy(payload))

    def latest_price(self, symbol: str) -> float | None:
        payload = self.market_ticks.get(str(symbol or "").strip())
        if not payload:
            return None
        for key in ("price", "last", "close"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except Exception:
                continue
        return None

    def latest_candles(
        self,
        symbol: str,
        timeframe: str | None = None,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        symbol_value = str(symbol or "").strip()
        if timeframe is not None:
            rows = list(self.candles.get((symbol_value, str(timeframe).strip()), ()))
        else:
            rows = []
            for (entry_symbol, _entry_timeframe), values in self.candles.items():
                if entry_symbol == symbol_value:
                    rows.extend(values)
            rows.sort(key=lambda row: self._sort_key(row.get("end") or row.get("start")))
        if limit is not None and limit >= 0:
            rows = rows[-int(limit) :]
        return copy.deepcopy(rows)

    def latest_order(self, order_id: str) -> dict[str, Any] | None:
        payload = self.orders.get(str(order_id or "").strip())
        return copy.deepcopy(payload) if payload is not None else None

    def orders_for_symbol(self, symbol: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        order_ids = list(self.order_ids_by_symbol.get(str(symbol or "").strip(), ()))
        if limit is not None and limit >= 0:
            order_ids = order_ids[-int(limit) :]
        return [copy.deepcopy(self.orders[order_id]) for order_id in order_ids if order_id in self.orders]

    def position(self, symbol: str) -> dict[str, Any] | None:
        payload = self.positions.get(str(symbol or "").strip())
        return copy.deepcopy(payload) if payload is not None else None

    def recent_event_payloads(self, event_type: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        rows = list(self.recent_events.get(str(event_type or "").strip(), ()))
        if limit is not None and limit >= 0:
            rows = rows[-int(limit) :]
        return copy.deepcopy(rows)

    def snapshot(self) -> dict[str, Any]:
        candle_snapshot = {
            f"{symbol}:{timeframe}": list(values)
            for (symbol, timeframe), values in self.candles.items()
        }
        recent_events = {
            event_type: list(rows)
            for event_type, rows in self.recent_events.items()
        }
        return self._serialize(
            {
                "latest_by_event_type": self.latest_by_event_type,
                "market_ticks": self.market_ticks,
                "order_books": self.order_books,
                "candles": candle_snapshot,
                "signals": self.signals,
                "trade_reviews": self.trade_reviews,
                "orders": self.orders,
                "positions": self.positions,
                "portfolio_snapshot": self.portfolio_snapshot,
                "performance_metrics": self.performance_metrics,
                "mobile_dashboard_snapshot": self.mobile_dashboard_snapshot,
                "risk_alerts": list(self.risk_alerts),
                "alerts": list(self.alerts),
                "trade_feedback": list(self.trade_feedback),
                "trade_journal_entries": list(self.trade_journal_entries),
                "trade_journal_summaries": list(self.trade_journal_summaries),
                "recent_events": recent_events,
            }
        )

    def _remember_event_id(self, event_id: str) -> bool:
        if event_id in self._seen_event_id_set:
            return False
        while len(self._seen_event_ids) >= self.seen_event_capacity:
            stale = self._seen_event_ids.popleft()
            self._seen_event_id_set.discard(stale)
        self._seen_event_ids.append(event_id)
        self._seen_event_id_set.add(event_id)
        return True

    def _event_record(self, event_type: str, payload: Any, event) -> dict[str, Any]:
        return {
            "id": getattr(event, "id", None),
            "type": event_type,
            "timestamp": getattr(event, "timestamp", None),
            "source": getattr(event, "source", None),
            "sequence": getattr(event, "sequence", None),
            "replayed": bool(getattr(event, "replayed", False)),
            "data": copy.deepcopy(payload),
        }

    def _normalize_payload(self, data: Any, *, model: type | None = None) -> dict[str, Any]:
        value = data
        if model is not None and value is not None and not isinstance(value, model) and isinstance(value, dict):
            try:
                value = model(**dict(value))
            except Exception:
                value = dict(value)
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return dict(value)
        if value is None:
            return {}
        return {"value": value}

    def _serialize(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._serialize(asdict(value))
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): self._serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, deque)):
            return [self._serialize(item) for item in value]
        return value

    @staticmethod
    def _sort_key(value: Any) -> float:
        if isinstance(value, datetime):
            return value.timestamp()
        return 0.0
