from __future__ import annotations

"""
InvestPro paper-trading trade models.

These models preserve the complete paper trade lifecycle:

    signal snapshot
        -> entry execution
        -> active paper trade
        -> partial exits / full exit
        -> final TradeRecord
        -> learning engine / model research lab

Designed for:
- paper trading
- backtesting parity
- learning datasets
- model retraining
- dashboard/audit events
"""

import math
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from uuid import uuid4


# ----------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_side(value: Any, *, allow_hold: bool = False) -> str | None:
    text = str(value or "").strip().upper()

    if text in {"BUY", "LONG"}:
        return "BUY"

    if text in {"SELL", "SHORT"}:
        return "SELL"

    if allow_hold and text in {"HOLD", "WAIT", "NONE", "NEUTRAL", ""}:
        return "HOLD"

    return None


def opposite_side(side: Any) -> str | None:
    normalized = normalize_side(side)

    if normalized == "BUY":
        return "SELL"

    if normalized == "SELL":
        return "BUY"

    return None


def coerce_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def coerce_datetime(value: Any, default: datetime | None = None) -> datetime:
    fallback = default or utc_now()

    if value is None:
        return fallback

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
        return fallback

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return fallback

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, datetime):
        return value.isoformat()

    if is_dataclass(value):
        try:
            return json_safe(asdict(value))
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            json_safe(item)
            for item in value
        ]

    if hasattr(value, "value"):
        return json_safe(value.value)

    return str(value)


def object_to_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, Mapping):
        return dict(value)

    if is_dataclass(value):
        return asdict(value)

    if hasattr(value, "to_dict") and callable(value.to_dict):
        result = value.to_dict()
        if isinstance(result, Mapping):
            return dict(result)

    if hasattr(value, "__dict__"):
        return dict(vars(value))

    return {}


# ----------------------------------------------------------------------
# Signal snapshot
# ----------------------------------------------------------------------

@dataclass(slots=True)
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
    signal_timestamp: datetime = field(default_factory=utc_now)

    feature_values: dict[str, float] = field(default_factory=dict)
    feature_version: str | None = None

    market_regime: str | None = None
    volatility_regime: str | None = None
    regime_snapshot: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.decision_id = str(self.decision_id or uuid4().hex)
        self.symbol = str(self.symbol or "").strip().upper()
        self.signal = normalize_side(self.signal, allow_hold=True) or "HOLD"
        self.timeframe = str(self.timeframe or "1h").strip() or "1h"
        self.source = str(self.source or "bot").strip() or "bot"
        self.exchange = str(
            self.exchange or "paper").strip().lower() or "paper"
        self.confidence = coerce_float(self.confidence, None)
        self.signal_price = coerce_float(self.signal_price, None)
        self.signal_timestamp = coerce_datetime(self.signal_timestamp)
        self.feature_values = {
            str(key): float(coerce_float(value, 0.0) or 0.0)
            for key, value in dict(self.feature_values or {}).items()
        }
        self.regime_snapshot = dict(self.regime_snapshot or {})
        self.metadata = dict(self.metadata or {})

        if not self.symbol:
            raise ValueError("PaperSignalSnapshot.symbol is required")

    @property
    def side(self) -> str:
        return self.signal

    @property
    def is_actionable(self) -> bool:
        return self.signal in {"BUY", "SELL"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "signal": self.signal,
            "side": self.side,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "source": self.source,
            "exchange": self.exchange,
            "confidence": self.confidence,
            "signal_price": self.signal_price,
            "signal_timestamp": self.signal_timestamp.isoformat(),
            "feature_values": json_safe(self.feature_values),
            "feature_version": self.feature_version,
            "market_regime": self.market_regime,
            "volatility_regime": self.volatility_regime,
            "regime_snapshot": json_safe(self.regime_snapshot),
            "metadata": json_safe(self.metadata),
        }

    @classmethod
    def from_signal(
        cls,
        signal: Any,
        *,
        decision_id: str | None = None,
        source: str = "bot",
        exchange: str = "paper",
        feature_values: dict[str, float] | None = None,
        regime_snapshot: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PaperSignalSnapshot":
        payload = object_to_mapping(signal)
        meta = {
            **dict(payload.get("metadata") or {}),
            **dict(metadata or {}),
        }

        side = (
            payload.get("signal")
            or payload.get("side")
            or payload.get("action")
            or payload.get("decision")
        )

        return cls(
            decision_id=str(decision_id or payload.get(
                "decision_id") or meta.get("decision_id") or uuid4().hex),
            symbol=str(payload.get("symbol") or meta.get("symbol") or ""),
            signal=str(side or "HOLD"),
            timeframe=str(payload.get("timeframe")
                          or meta.get("timeframe") or "1h"),
            strategy_name=payload.get("strategy_name") or payload.get(
                "source_strategy") or meta.get("strategy_name"),
            source=source,
            exchange=str(payload.get("exchange")
                         or meta.get("exchange") or exchange),
            confidence=payload.get("confidence"),
            signal_price=payload.get("price") or payload.get("signal_price"),
            signal_timestamp=payload.get("timestamp") or payload.get(
                "signal_timestamp") or utc_now(),
            feature_values=dict(feature_values or payload.get(
                "feature_values") or meta.get("feature_values") or {}),
            feature_version=payload.get(
                "feature_version") or meta.get("feature_version"),
            market_regime=payload.get(
                "market_regime") or meta.get("market_regime"),
            volatility_regime=payload.get(
                "volatility_regime") or meta.get("volatility_regime"),
            regime_snapshot=dict(regime_snapshot or payload.get(
                "regime_snapshot") or meta.get("regime_snapshot") or {}),
            metadata=meta,
        )


# ----------------------------------------------------------------------
# Paper events
# ----------------------------------------------------------------------

@dataclass(slots=True)
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

    def __post_init__(self) -> None:
        self.event_type = str(self.event_type or "").strip()
        self.symbol = str(self.symbol or "").strip().upper()
        self.timestamp = coerce_datetime(self.timestamp)
        self.side = normalize_side(
            self.side, allow_hold=True) if self.side is not None else None
        self.signal = normalize_side(
            self.signal, allow_hold=True) if self.signal is not None else self.side
        self.price = coerce_float(self.price, None)
        self.quantity = coerce_float(self.quantity, None)
        self.confidence = coerce_float(self.confidence, None)
        self.payload = dict(self.payload or {})

    def to_dict(self) -> dict[str, Any]:
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
            "payload": json_safe(self.payload),
        }


# ----------------------------------------------------------------------
# Final closed trade record
# ----------------------------------------------------------------------

@dataclass(slots=True)
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

    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.trade_id = str(self.trade_id or uuid4().hex)
        self.symbol = str(self.symbol or "").strip().upper()
        self.exchange = str(self.exchange or "paper").strip().lower()
        self.source = str(self.source or "bot").strip()
        self.timeframe = str(self.timeframe or "1h").strip()
        self.signal = normalize_side(self.signal, allow_hold=True) or "HOLD"
        self.side = normalize_side(self.side) or self.signal
        self.quantity = float(coerce_float(self.quantity, 0.0) or 0.0)
        self.entry_price = float(coerce_float(self.entry_price, 0.0) or 0.0)
        self.exit_price = float(coerce_float(self.exit_price, 0.0) or 0.0)
        self.pnl = float(coerce_float(self.pnl, 0.0) or 0.0)
        self.pnl_pct = float(coerce_float(self.pnl_pct, 0.0) or 0.0)
        self.outcome = str(self.outcome or "BREAKEVEN").strip().upper()
        self.signal_timestamp = coerce_datetime(self.signal_timestamp)
        self.entry_timestamp = coerce_datetime(self.entry_timestamp)
        self.exit_timestamp = coerce_datetime(self.exit_timestamp)
        self.duration_seconds = float(
            coerce_float(self.duration_seconds, 0.0) or 0.0)
        self.confidence = coerce_float(self.confidence, None)
        self.feature_values = {
            str(key): float(coerce_float(value, 0.0) or 0.0)
            for key, value in dict(self.feature_values or {}).items()
        }
        self.regime_snapshot = dict(self.regime_snapshot or {})
        self.metadata = dict(self.metadata or {})

    @property
    def timestamp(self) -> datetime:
        return self.signal_timestamp or self.entry_timestamp

    @property
    def holding_minutes(self) -> float:
        return self.duration_seconds / 60.0

    @property
    def risk_reward_score(self) -> float:
        adverse = abs(float(self.max_adverse_excursion or 0.0))
        if adverse <= 1e-12:
            return float("inf") if self.pnl > 0 else 0.0
        return float(self.max_favorable_excursion or 0.0) / adverse

    def to_dict(self) -> dict[str, Any]:
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
            "holding_minutes": self.holding_minutes,
            "confidence": self.confidence,
            "feature_values": json_safe(self.feature_values),
            "feature_version": self.feature_version,
            "market_regime": self.market_regime,
            "volatility_regime": self.volatility_regime,
            "regime_snapshot": json_safe(self.regime_snapshot),
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "max_favorable_excursion": self.max_favorable_excursion,
            "max_adverse_excursion": self.max_adverse_excursion,
            "risk_reward_score": self.risk_reward_score if math.isfinite(self.risk_reward_score) else None,
            "metadata": json_safe(self.metadata),
        }


# ----------------------------------------------------------------------
# Active paper trade
# ----------------------------------------------------------------------

@dataclass(slots=True)
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

    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    highest_price: float | None = None
    lowest_price: float | None = None

    events: list[PaperTradeEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.trade_id = str(self.trade_id or uuid4().hex)
        self.symbol = str(self.symbol or "").strip().upper()
        self.exchange = str(self.exchange or "paper").strip().lower()
        self.source = str(self.source or "bot").strip() or "bot"
        self.timeframe = str(self.timeframe or "1h").strip() or "1h"
        self.signal = normalize_side(self.signal, allow_hold=True) or "HOLD"
        self.side = normalize_side(self.side) or self.signal
        self.signal_timestamp = coerce_datetime(self.signal_timestamp)
        self.entry_timestamp = coerce_datetime(self.entry_timestamp)
        self.entry_price = float(coerce_float(self.entry_price, 0.0) or 0.0)
        self.quantity = max(0.0, float(
            coerce_float(self.quantity, 0.0) or 0.0))
        self.remaining_quantity = max(0.0, float(coerce_float(
            self.remaining_quantity, self.quantity) or 0.0))
        self.confidence = coerce_float(self.confidence, None)
        self.feature_values = {
            str(key): float(coerce_float(value, 0.0) or 0.0)
            for key, value in dict(self.feature_values or {}).items()
        }
        self.regime_snapshot = dict(self.regime_snapshot or {})
        self.metadata = dict(self.metadata or {})
        self.highest_price = coerce_float(self.highest_price, self.entry_price)
        self.lowest_price = coerce_float(self.lowest_price, self.entry_price)

        if self.side not in {"BUY", "SELL"}:
            raise ValueError("ActivePaperTrade.side must be BUY or SELL")

    @property
    def direction(self) -> float:
        return 1.0 if self.side == "BUY" else -1.0

    @property
    def average_exit_price(self) -> float | None:
        if self.closed_quantity <= 0:
            return None
        return self.exit_notional / self.closed_quantity

    @property
    def is_closed(self) -> bool:
        return self.remaining_quantity <= 1e-12

    @property
    def open_notional(self) -> float:
        return abs(self.remaining_quantity * self.entry_price)

    @property
    def entry_notional(self) -> float:
        return abs(self.quantity * self.entry_price)

    def unrealized_pnl(self, mark_price: float) -> float:
        mark = float(coerce_float(mark_price, self.entry_price)
                     or self.entry_price)
        return (mark - self.entry_price) * self.remaining_quantity * self.direction

    def total_pnl(self, mark_price: float | None = None) -> float:
        if mark_price is None:
            return self.realized_pnl
        return self.realized_pnl + self.unrealized_pnl(mark_price)

    def update_mark(self, price: float, *, timestamp: Any = None) -> None:
        mark = float(coerce_float(price, self.entry_price) or self.entry_price)
        if mark <= 0:
            return

        self.highest_price = max(float(self.highest_price or mark), mark)
        self.lowest_price = min(float(self.lowest_price or mark), mark)

        current_unrealized = (mark - self.entry_price) * \
            max(self.remaining_quantity, 0.0) * self.direction
        self.max_favorable_excursion = max(
            self.max_favorable_excursion, current_unrealized)
        self.max_adverse_excursion = min(
            self.max_adverse_excursion, current_unrealized)

        self.events.append(
            PaperTradeEvent(
                event_type="mark",
                symbol=self.symbol,
                timestamp=coerce_datetime(timestamp, utc_now()),
                trade_id=self.trade_id,
                decision_id=self.decision_id,
                exchange=self.exchange,
                source=self.source,
                strategy_name=self.strategy_name,
                timeframe=self.timeframe,
                side=self.side,
                price=mark,
                quantity=self.remaining_quantity,
                message="Paper trade marked to market.",
                payload={
                    "unrealized_pnl": current_unrealized,
                    "highest_price": self.highest_price,
                    "lowest_price": self.lowest_price,
                },
            )
        )

    def absorb_entry(
        self,
        *,
        quantity: Any,
        price: Any,
        timestamp: Any = None,
        order_id: str | None = None,
        confidence: Any = None,
        decision_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry_qty = max(0.0, float(coerce_float(quantity, 0.0) or 0.0))
        entry_price = max(0.0, float(coerce_float(price, 0.0) or 0.0))

        if entry_qty <= 0 or entry_price <= 0:
            return

        previous_qty = self.quantity
        total_qty = self.quantity + entry_qty

        if total_qty > 0:
            self.entry_price = (
                (self.entry_price * self.quantity) + (entry_price * entry_qty)) / total_qty

        self.quantity = total_qty
        self.remaining_quantity += entry_qty
        self.entry_timestamp = min(
            self.entry_timestamp, coerce_datetime(timestamp, self.entry_timestamp))
        self.entry_order_id = order_id or self.entry_order_id

        if confidence is not None:
            current_confidence = coerce_float(self.confidence, 0.0) or 0.0
            new_confidence = coerce_float(
                confidence, current_confidence) or current_confidence
            self.confidence = ((current_confidence * previous_qty) +
                               (new_confidence * entry_qty)) / max(total_qty, 1e-12)

        if decision_id:
            self.metadata["latest_entry_decision_id"] = str(decision_id)

        if metadata:
            self.metadata.update(dict(metadata))

        self.update_mark(entry_price, timestamp=timestamp)

        self.events.append(
            PaperTradeEvent(
                event_type="entry_add",
                symbol=self.symbol,
                timestamp=coerce_datetime(timestamp, utc_now()),
                trade_id=self.trade_id,
                decision_id=decision_id or self.decision_id,
                exchange=self.exchange,
                source=self.source,
                strategy_name=self.strategy_name,
                timeframe=self.timeframe,
                side=self.side,
                order_id=order_id,
                price=entry_price,
                quantity=entry_qty,
                confidence=self.confidence,
                message="Added to active paper trade.",
                payload={
                    "new_average_entry_price": self.entry_price,
                    "total_quantity": self.quantity,
                    "remaining_quantity": self.remaining_quantity,
                },
            )
        )

    def realize_exit(
        self,
        *,
        quantity: Any,
        price: Any,
        timestamp: Any = None,
        order_id: str | None = None,
        decision_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> float:
        exit_qty = min(
            max(0.0, float(coerce_float(quantity, 0.0) or 0.0)),
            self.remaining_quantity,
        )
        exit_price = max(0.0, float(coerce_float(price, 0.0) or 0.0))

        if exit_qty <= 0 or exit_price <= 0:
            return 0.0

        realized_delta = (exit_price - self.entry_price) * \
            exit_qty * self.direction

        self.closed_quantity += exit_qty
        self.remaining_quantity = max(0.0, self.remaining_quantity - exit_qty)
        self.exit_notional += exit_qty * exit_price
        self.realized_pnl += realized_delta
        self.exit_timestamp = coerce_datetime(
            timestamp, self.exit_timestamp or self.entry_timestamp)
        self.exit_order_id = order_id or self.exit_order_id

        if decision_id:
            self.metadata["latest_exit_decision_id"] = str(decision_id)

        if metadata:
            self.metadata.update(dict(metadata))

        self.update_mark(exit_price, timestamp=timestamp)

        self.events.append(
            PaperTradeEvent(
                event_type="exit_partial" if not self.is_closed else "exit_full",
                symbol=self.symbol,
                timestamp=self.exit_timestamp,
                trade_id=self.trade_id,
                decision_id=decision_id or self.decision_id,
                exchange=self.exchange,
                source=self.source,
                strategy_name=self.strategy_name,
                timeframe=self.timeframe,
                side=opposite_side(self.side),
                order_id=order_id,
                price=exit_price,
                quantity=exit_qty,
                message="Paper trade exit realized.",
                payload={
                    "realized_delta": realized_delta,
                    "realized_pnl": self.realized_pnl,
                    "closed_quantity": self.closed_quantity,
                    "remaining_quantity": self.remaining_quantity,
                },
            )
        )

        return exit_qty

    def to_trade_record(self) -> TradeRecord:
        if not self.is_closed:
            raise ValueError(
                "Cannot finalize an active paper trade before it is fully closed")

        exit_time = self.exit_timestamp or self.entry_timestamp
        avg_exit_price = coerce_float(
            self.average_exit_price, self.entry_price) or self.entry_price
        duration_seconds = max(
            0.0, (exit_time - self.entry_timestamp).total_seconds())
        entry_notional = self.entry_price * max(self.quantity, 0.0)
        pnl_pct = (self.realized_pnl /
                   entry_notional) if entry_notional > 0 else 0.0

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
            max_favorable_excursion=self.max_favorable_excursion,
            max_adverse_excursion=self.max_adverse_excursion,
            metadata={
                **dict(self.metadata or {}),
                "event_count": len(self.events),
                "highest_price": self.highest_price,
                "lowest_price": self.lowest_price,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "source": self.source,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "signal": self.signal,
            "side": self.side,
            "decision_id": self.decision_id,
            "signal_timestamp": self.signal_timestamp.isoformat(),
            "entry_timestamp": self.entry_timestamp.isoformat(),
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "confidence": self.confidence,
            "feature_values": json_safe(self.feature_values),
            "feature_version": self.feature_version,
            "market_regime": self.market_regime,
            "volatility_regime": self.volatility_regime,
            "regime_snapshot": json_safe(self.regime_snapshot),
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "closed_quantity": self.closed_quantity,
            "exit_notional": self.exit_notional,
            "realized_pnl": self.realized_pnl,
            "exit_timestamp": self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            "average_exit_price": self.average_exit_price,
            "max_favorable_excursion": self.max_favorable_excursion,
            "max_adverse_excursion": self.max_adverse_excursion,
            "highest_price": self.highest_price,
            "lowest_price": self.lowest_price,
            "is_closed": self.is_closed,
            "events": [event.to_dict() for event in self.events],
            "metadata": json_safe(self.metadata),
        }

    @classmethod
    def from_signal_snapshot(
        cls,
        snapshot: PaperSignalSnapshot,
        *,
        quantity: Any,
        price: Any,
        timestamp: Any = None,
        order_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ActivePaperTrade":
        if not snapshot.is_actionable:
            raise ValueError(
                "Cannot open ActivePaperTrade from non-actionable HOLD signal")

        trade_time = coerce_datetime(timestamp, snapshot.signal_timestamp)
        normalized_qty = max(0.0, float(coerce_float(quantity, 0.0) or 0.0))
        normalized_price = max(0.0, float(coerce_float(price, 0.0) or 0.0))

        trade = cls(
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
            entry_price=normalized_price,
            quantity=normalized_qty,
            remaining_quantity=normalized_qty,
            confidence=snapshot.confidence,
            feature_values=dict(snapshot.feature_values or {}),
            feature_version=snapshot.feature_version,
            market_regime=snapshot.market_regime,
            volatility_regime=snapshot.volatility_regime,
            regime_snapshot=dict(snapshot.regime_snapshot or {}),
            entry_order_id=order_id,
            metadata={**dict(snapshot.metadata or {}), **dict(metadata or {})},
        )

        trade.events.append(
            PaperTradeEvent(
                event_type="entry_open",
                symbol=trade.symbol,
                timestamp=trade.entry_timestamp,
                trade_id=trade.trade_id,
                decision_id=trade.decision_id,
                exchange=trade.exchange,
                source=trade.source,
                strategy_name=trade.strategy_name,
                timeframe=trade.timeframe,
                side=trade.side,
                signal=trade.signal,
                order_id=order_id,
                price=normalized_price,
                quantity=normalized_qty,
                confidence=trade.confidence,
                message="Opened active paper trade.",
            )
        )

        trade.update_mark(normalized_price, timestamp=trade_time)
        return trade

    @classmethod
    def from_execution_report(
        cls,
        snapshot: PaperSignalSnapshot,
        report: Any,
    ) -> "ActivePaperTrade":
        payload = object_to_mapping(report)

        return cls.from_signal_snapshot(
            snapshot,
            quantity=payload.get("filled_quantity") or payload.get(
                "quantity") or payload.get("amount"),
            price=payload.get("fill_price") or payload.get("price") or payload.get(
                "requested_price") or snapshot.signal_price,
            timestamp=payload.get("timestamp") or utc_now(),
            order_id=payload.get("order_id") or payload.get("id"),
            metadata={
                "execution_report": json_safe(payload),
            },
        )
