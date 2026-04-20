from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def normalize_side(value) -> str | None:
    text = str(value or "").strip().upper()
    if text in {"BUY", "LONG"}:
        return "BUY"
    if text in {"SELL", "SHORT"}:
        return "SELL"
    return None


def coerce_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_datetime(value, default=None):
    if value is None:
        return default or datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    try:
        numeric = float(value)
        if abs(numeric) > 1e11:
            return datetime.fromtimestamp(numeric / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    except Exception:
        pass

    text = str(value or "").strip()
    if not text:
        return default or datetime.now(timezone.utc)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return default or datetime.now(timezone.utc)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


@dataclass
class PaperSignalSnapshot:
    decision_id: str
    symbol: str
    signal: str
    timeframe: str = "1h"
    strategy_name: str | None = None
    source: str = "bot"
    exchange: str = "paper"
    confidence: float | None = None
    signal_price: float | None = None
    signal_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    feature_values: dict[str, float] = field(default_factory=dict)
    feature_version: str | None = None
    market_regime: str | None = None
    volatility_regime: str | None = None
    regime_snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "signal": self.signal,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "source": self.source,
            "exchange": self.exchange,
            "confidence": self.confidence,
            "signal_price": self.signal_price,
            "signal_timestamp": self.signal_timestamp.isoformat(),
            "feature_values": dict(self.feature_values or {}),
            "feature_version": self.feature_version,
            "market_regime": self.market_regime,
            "volatility_regime": self.volatility_regime,
            "regime_snapshot": dict(self.regime_snapshot or {}),
            "metadata": dict(self.metadata or {}),
        }


@dataclass
class PaperTradeEvent:
    event_type: str
    symbol: str
    timestamp: datetime
    trade_id: str | None = None
    decision_id: str | None = None
    exchange: str | None = None
    source: str | None = None
    strategy_name: str | None = None
    timeframe: str | None = None
    side: str | None = None
    signal: str | None = None
    order_status: str | None = None
    order_id: str | None = None
    price: float | None = None
    quantity: float | None = None
    confidence: float | None = None
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "trade_id": self.trade_id,
            "decision_id": self.decision_id,
            "exchange": self.exchange,
            "source": self.source,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "side": self.side,
            "signal": self.signal,
            "order_status": self.order_status,
            "order_id": self.order_id,
            "price": self.price,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "message": self.message,
            "payload": dict(self.payload or {}),
        }


@dataclass
class TradeRecord:
    trade_id: str
    decision_id: str | None
    symbol: str
    exchange: str
    source: str
    strategy_name: str | None
    timeframe: str
    signal: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    outcome: str
    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    duration_seconds: float
    confidence: float | None = None
    feature_values: dict[str, float] = field(default_factory=dict)
    feature_version: str | None = None
    market_regime: str | None = None
    volatility_regime: str | None = None
    regime_snapshot: dict[str, Any] = field(default_factory=dict)
    entry_order_id: str | None = None
    exit_order_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "source": self.source,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "signal": self.signal,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "outcome": self.outcome,
            "signal_timestamp": self.signal_timestamp.isoformat(),
            "entry_timestamp": self.entry_timestamp.isoformat(),
            "exit_timestamp": self.exit_timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "confidence": self.confidence,
            "feature_values": dict(self.feature_values or {}),
            "feature_version": self.feature_version,
            "market_regime": self.market_regime,
            "volatility_regime": self.volatility_regime,
            "regime_snapshot": dict(self.regime_snapshot or {}),
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "metadata": dict(self.metadata or {}),
        }

    @property
    def timestamp(self):
        return self.signal_timestamp or self.entry_timestamp


@dataclass
class ActivePaperTrade:
    trade_id: str
    symbol: str
    exchange: str
    source: str
    strategy_name: str | None
    timeframe: str
    signal: str
    side: str
    decision_id: str | None
    signal_timestamp: datetime
    entry_timestamp: datetime
    entry_price: float
    quantity: float
    remaining_quantity: float
    confidence: float | None = None
    feature_values: dict[str, float] = field(default_factory=dict)
    feature_version: str | None = None
    market_regime: str | None = None
    volatility_regime: str | None = None
    regime_snapshot: dict[str, Any] = field(default_factory=dict)
    entry_order_id: str | None = None
    exit_order_id: str | None = None
    closed_quantity: float = 0.0
    exit_notional: float = 0.0
    realized_pnl: float = 0.0
    exit_timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def direction(self):
        return 1.0 if self.side == "BUY" else -1.0

    @property
    def average_exit_price(self):
        if self.closed_quantity <= 0:
            return None
        return self.exit_notional / self.closed_quantity

    @property
    def is_closed(self):
        return self.remaining_quantity <= 1e-12

    def absorb_entry(
        self,
        *,
        quantity,
        price,
        timestamp=None,
        order_id=None,
        confidence=None,
        decision_id=None,
    ):
        entry_qty = max(0.0, coerce_float(quantity, 0.0) or 0.0)
        entry_price = max(0.0, coerce_float(price, 0.0) or 0.0)
        if entry_qty <= 0 or entry_price <= 0:
            return

        total_qty = self.quantity + entry_qty
        if total_qty > 0:
            self.entry_price = ((self.entry_price * self.quantity) + (entry_price * entry_qty)) / total_qty
        self.quantity = total_qty
        self.remaining_quantity += entry_qty
        self.entry_timestamp = min(self.entry_timestamp, coerce_datetime(timestamp, self.entry_timestamp))
        self.entry_order_id = order_id or self.entry_order_id
        if confidence is not None:
            current_confidence = coerce_float(self.confidence, 0.0) or 0.0
            new_confidence = coerce_float(confidence, current_confidence) or current_confidence
            if total_qty > 0:
                self.confidence = ((current_confidence * (total_qty - entry_qty)) + (new_confidence * entry_qty)) / total_qty
        if decision_id:
            self.metadata["latest_entry_decision_id"] = str(decision_id)

    def realize_exit(self, *, quantity, price, timestamp=None, order_id=None, decision_id=None):
        exit_qty = min(max(0.0, coerce_float(quantity, 0.0) or 0.0), self.remaining_quantity)
        exit_price = max(0.0, coerce_float(price, 0.0) or 0.0)
        if exit_qty <= 0 or exit_price <= 0:
            return 0.0

        self.closed_quantity += exit_qty
        self.remaining_quantity = max(0.0, self.remaining_quantity - exit_qty)
        self.exit_notional += exit_qty * exit_price
        self.realized_pnl += (exit_price - self.entry_price) * exit_qty * self.direction
        self.exit_timestamp = coerce_datetime(timestamp, self.exit_timestamp or self.entry_timestamp)
        self.exit_order_id = order_id or self.exit_order_id
        if decision_id:
            self.metadata["latest_exit_decision_id"] = str(decision_id)
        return exit_qty

    def to_trade_record(self):
        if not self.is_closed:
            raise ValueError("Cannot finalize an active paper trade before it is fully closed")

        exit_time = self.exit_timestamp or self.entry_timestamp
        avg_exit_price = coerce_float(self.average_exit_price, self.entry_price) or self.entry_price
        duration_seconds = max(0.0, (exit_time - self.entry_timestamp).total_seconds())
        entry_notional = self.entry_price * max(self.quantity, 0.0)
        pnl_pct = (self.realized_pnl / entry_notional) if entry_notional > 0 else 0.0
        if self.realized_pnl > 0:
            outcome = "WIN"
        elif self.realized_pnl < 0:
            outcome = "LOSS"
        else:
            outcome = "BREAKEVEN"

        return TradeRecord(
            trade_id=self.trade_id,
            decision_id=self.decision_id,
            symbol=self.symbol,
            exchange=self.exchange,
            source=self.source,
            strategy_name=self.strategy_name,
            timeframe=self.timeframe,
            signal=self.signal,
            side=self.side,
            quantity=self.quantity,
            entry_price=self.entry_price,
            exit_price=avg_exit_price,
            pnl=self.realized_pnl,
            pnl_pct=pnl_pct,
            outcome=outcome,
            signal_timestamp=self.signal_timestamp,
            entry_timestamp=self.entry_timestamp,
            exit_timestamp=exit_time,
            duration_seconds=duration_seconds,
            confidence=self.confidence,
            feature_values=dict(self.feature_values or {}),
            feature_version=self.feature_version,
            market_regime=self.market_regime,
            volatility_regime=self.volatility_regime,
            regime_snapshot=dict(self.regime_snapshot or {}),
            entry_order_id=self.entry_order_id,
            exit_order_id=self.exit_order_id,
            metadata=dict(self.metadata or {}),
        )

    @classmethod
    def from_signal_snapshot(cls, snapshot: PaperSignalSnapshot, *, quantity, price, timestamp=None, order_id=None):
        trade_time = coerce_datetime(timestamp, snapshot.signal_timestamp)
        normalized_qty = max(0.0, coerce_float(quantity, 0.0) or 0.0)
        return cls(
            trade_id=uuid4().hex,
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            source=snapshot.source,
            strategy_name=snapshot.strategy_name,
            timeframe=snapshot.timeframe,
            signal=snapshot.signal,
            side=snapshot.signal,
            decision_id=snapshot.decision_id,
            signal_timestamp=snapshot.signal_timestamp,
            entry_timestamp=trade_time,
            entry_price=max(0.0, coerce_float(price, 0.0) or 0.0),
            quantity=normalized_qty,
            remaining_quantity=normalized_qty,
            confidence=snapshot.confidence,
            feature_values=dict(snapshot.feature_values or {}),
            feature_version=snapshot.feature_version,
            market_regime=snapshot.market_regime,
            volatility_regime=snapshot.volatility_regime,
            regime_snapshot=dict(snapshot.regime_snapshot or {}),
            entry_order_id=order_id,
            metadata=dict(snapshot.metadata or {}),
        )
