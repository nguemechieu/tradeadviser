from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, select
from sqlalchemy.exc import SQLAlchemyError

try:
    from storage import database as storage_db
except Exception as ex:
    from src.storage import database as storage_db  # type: ignore


def utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PaperTradeEventRow(storage_db.Base):
    __tablename__ = "paper_trade_events"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(255), index=True)
    decision_id = Column(String(255), index=True)
    symbol = Column(String(255), index=True)
    exchange = Column(String(255), index=True)
    source = Column(String(255), index=True)
    strategy_name = Column(String(255), index=True)
    timeframe = Column(String(255), index=True)
    side = Column(String(255), index=True)
    signal = Column(String(255), index=True)
    event_type = Column(String(255), index=True)
    order_status = Column(String(255), index=True)
    order_id = Column(String(255), index=True)
    price = Column(Float)
    quantity = Column(Float)
    confidence = Column(Float)
    message = Column(Text)
    payload_json = Column(Text)
    timestamp = Column(DateTime, default=utc_naive_now, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "source": self.source,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "side": self.side,
            "signal": self.signal,
            "event_type": self.event_type,
            "order_status": self.order_status,
            "order_id": self.order_id,
            "price": self.price,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "message": self.message,
            "payload": PaperTradeLearningRepository.deserialize_payload_static(self.payload_json),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class PaperTradeRecordRow(storage_db.Base):
    __tablename__ = "paper_trade_records"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(255), index=True, unique=True)
    decision_id = Column(String(255), index=True)
    symbol = Column(String(255), index=True)
    exchange = Column(String(255), index=True)
    source = Column(String(255), index=True)
    strategy_name = Column(String(255), index=True)
    timeframe = Column(String(255), index=True)
    signal = Column(String(255), index=True)
    side = Column(String(255), index=True)
    market_regime = Column(String(255), index=True)
    volatility_regime = Column(String(255), index=True)
    feature_version = Column(String(255), index=True)
    outcome = Column(String(255), index=True)
    entry_order_id = Column(String(255), index=True)
    exit_order_id = Column(String(255), index=True)

    signal_timestamp = Column(DateTime, index=True)
    entry_timestamp = Column(DateTime, index=True)
    exit_timestamp = Column(DateTime, index=True)

    duration_seconds = Column(Float)
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    confidence = Column(Float)

    rsi = Column(Float)
    ema_fast = Column(Float)
    ema_slow = Column(Float)
    atr = Column(Float)
    volume = Column(Float)
    return_1 = Column(Float)
    return_5 = Column(Float)
    volume_ratio = Column(Float)
    momentum = Column(Float)
    macd_line = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    atr_pct = Column(Float)
    trend_strength = Column(Float)
    pullback_gap = Column(Float)
    band_position = Column(Float)

    close = Column(Float)
    mean_close = Column(Float)
    median_close = Column(Float)
    return_3 = Column(Float)
    return_10 = Column(Float)
    momentum_3 = Column(Float)
    momentum_5 = Column(Float)
    momentum_10 = Column(Float)
    log_return_1 = Column(Float)
    realized_volatility = Column(Float)
    realized_volatility_5 = Column(Float)
    realized_volatility_10 = Column(Float)
    high_low_range = Column(Float)
    candle_range_pct = Column(Float)
    body_pct = Column(Float)
    upper_wick_pct = Column(Float)
    lower_wick_pct = Column(Float)
    average_volume = Column(Float)
    volume_change = Column(Float)
    sma_5 = Column(Float)
    sma_10 = Column(Float)
    sma_20 = Column(Float)
    ema_diff = Column(Float)
    ema_diff_pct = Column(Float)
    zscore_close_20 = Column(Float)
    drawdown_from_high = Column(Float)
    distance_from_low = Column(Float)

    signal_is_buy = Column(Float)
    features_json = Column(Text)
    regime_json = Column(Text)
    metadata_json = Column(Text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "source": self.source,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "signal": self.signal,
            "side": self.side,
            "market_regime": self.market_regime,
            "volatility_regime": self.volatility_regime,
            "feature_version": self.feature_version,
            "outcome": self.outcome,
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "signal_timestamp": self.signal_timestamp.isoformat() if self.signal_timestamp else None,
            "entry_timestamp": self.entry_timestamp.isoformat() if self.entry_timestamp else None,
            "exit_timestamp": self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            "duration_seconds": self.duration_seconds,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "confidence": self.confidence,
            "signal_is_buy": self.signal_is_buy,
            "feature_values": PaperTradeLearningRepository.deserialize_payload_static(self.features_json),
            "regime_snapshot": PaperTradeLearningRepository.deserialize_payload_static(self.regime_json),
            "metadata": PaperTradeLearningRepository.deserialize_payload_static(self.metadata_json),
        }


class PaperTradeLearningRepository:
    """Persistence layer for paper trade events and completed paper trade records."""

    FEATURE_COLUMNS = [
        "rsi",
        "ema_fast",
        "ema_slow",
        "atr",
        "volume",
        "return_1",
        "return_5",
        "volume_ratio",
        "momentum",
        "macd_line",
        "macd_signal",
        "macd_hist",
        "atr_pct",
        "trend_strength",
        "pullback_gap",
        "band_position",
        "close",
        "mean_close",
        "median_close",
        "return_3",
        "return_10",
        "momentum_3",
        "momentum_5",
        "momentum_10",
        "log_return_1",
        "realized_volatility",
        "realized_volatility_5",
        "realized_volatility_10",
        "high_low_range",
        "candle_range_pct",
        "body_pct",
        "upper_wick_pct",
        "lower_wick_pct",
        "average_volume",
        "volume_change",
        "sma_5",
        "sma_10",
        "sma_20",
        "ema_diff",
        "ema_diff_pct",
        "zscore_close_20",
        "drawdown_from_high",
        "distance_from_low",
    ]

    def __init__(self, session_factory: Any | None = None) -> None:
        self.session_factory = session_factory or storage_db.SessionLocal

    def create_tables(self) -> None:
        """Create missing paper-learning tables."""
        bind = getattr(storage_db, "engine", None)
        if bind is None:
            raise RuntimeError("storage.database.engine is not available")
        storage_db.Base.metadata.create_all(bind=bind)

    def append_trade_event(self, event: Any = None, **kwargs: Any) -> PaperTradeEventRow:
        payload = self._payload_from(event, kwargs)

        row = PaperTradeEventRow(
            trade_id=self._normalize_text(payload.get("trade_id")),
            decision_id=self._normalize_text(payload.get("decision_id")),
            symbol=self._normalize_symbol(payload.get("symbol")),
            exchange=self._normalize_text(payload.get("exchange")),
            source=self._normalize_text(payload.get("source")),
            strategy_name=self._normalize_text(payload.get("strategy_name")),
            timeframe=self._normalize_text(payload.get("timeframe")),
            side=self._normalize_side(payload.get("side")),
            signal=self._normalize_side(payload.get("signal")),
            event_type=self._normalize_text(
                payload.get("event_type")) or "unknown",
            order_status=self._normalize_text(payload.get("order_status")),
            order_id=self._normalize_text(payload.get("order_id")),
            price=self._normalize_float(payload.get("price")),
            quantity=self._normalize_float(payload.get("quantity")),
            confidence=self._normalize_float(payload.get("confidence")),
            message=self._normalize_text(payload.get("message")),
            payload_json=self._normalize_payload(payload.get("payload")),
            timestamp=self._normalize_timestamp(payload.get("timestamp")),
        )

        return self._commit_row(row)

    def append_trade_record(
        self,
        record: Any = None,
        *,
        upsert: bool = True,
        **kwargs: Any,
    ) -> PaperTradeRecordRow:
        payload = self._payload_from(record, kwargs)
        features = dict(payload.get("feature_values") or {})

        row_data = self._record_row_payload(payload, features)

        with self.session_factory() as session:
            try:
                row = None

                if upsert and row_data.get("trade_id"):
                    row = session.execute(
                        select(PaperTradeRecordRow).where(
                            PaperTradeRecordRow.trade_id == row_data["trade_id"]
                        )
                    ).scalars().first()

                if row is None:
                    row = PaperTradeRecordRow(**row_data)
                    session.add(row)
                else:
                    for key, value in row_data.items():
                        setattr(row, key, value)

                session.commit()
                session.refresh(row)
                return row

            except SQLAlchemyError:
                session.rollback()
                raise

    def get_trade_events(
        self,
        limit: int = 500,
        symbol: str | None = None,
        decision_id: str | None = None,
        trade_id: str | None = None,
        event_type: str | None = None,
    ) -> list[PaperTradeEventRow]:
        with self.session_factory() as session:
            stmt = select(PaperTradeEventRow)

            if symbol:
                stmt = stmt.where(PaperTradeEventRow.symbol ==
                                  self._normalize_symbol(symbol))
            if decision_id:
                stmt = stmt.where(PaperTradeEventRow.decision_id ==
                                  self._normalize_text(decision_id))
            if trade_id:
                stmt = stmt.where(PaperTradeEventRow.trade_id ==
                                  self._normalize_text(trade_id))
            if event_type:
                stmt = stmt.where(PaperTradeEventRow.event_type ==
                                  self._normalize_text(event_type))

            stmt = stmt.order_by(
                PaperTradeEventRow.timestamp.desc(),
                PaperTradeEventRow.id.desc(),
            ).limit(max(1, int(limit or 500)))

            return list(session.execute(stmt).scalars().all())

    def get_trade_records(
        self,
        limit: int = 5000,
        symbol: str | None = None,
        strategy_name: str | None = None,
        timeframe: str | None = None,
        exchange: str | None = None,
        outcome: str | None = None,
    ) -> list[PaperTradeRecordRow]:
        with self.session_factory() as session:
            stmt = select(PaperTradeRecordRow)

            if symbol:
                stmt = stmt.where(PaperTradeRecordRow.symbol ==
                                  self._normalize_symbol(symbol))
            if strategy_name:
                stmt = stmt.where(PaperTradeRecordRow.strategy_name ==
                                  self._normalize_text(strategy_name))
            if timeframe:
                stmt = stmt.where(PaperTradeRecordRow.timeframe ==
                                  self._normalize_text(timeframe))
            if exchange:
                stmt = stmt.where(PaperTradeRecordRow.exchange ==
                                  self._normalize_text(exchange))
            if outcome:
                stmt = stmt.where(PaperTradeRecordRow.outcome ==
                                  self._normalize_text(outcome))

            stmt = stmt.order_by(
                PaperTradeRecordRow.exit_timestamp.desc(),
                PaperTradeRecordRow.id.desc(),
            ).limit(max(1, int(limit or 5000)))

            return list(session.execute(stmt).scalars().all())

    def get_trade_record_by_trade_id(self, trade_id: str) -> PaperTradeRecordRow | None:
        with self.session_factory() as session:
            return session.execute(
                select(PaperTradeRecordRow).where(
                    PaperTradeRecordRow.trade_id == self._normalize_text(
                        trade_id)
                )
            ).scalars().first()

    def export_dataset(
        self,
        *,
        limit: int = 10000,
        symbol: str | None = None,
        strategy_name: str | None = None,
        timeframe: str | None = None,
        exchange: str | None = None,
        include_breakeven: bool = False,
    ) -> list[dict[str, Any]]:
        rows = self.get_trade_records(
            limit=limit,
            symbol=symbol,
            strategy_name=strategy_name,
            timeframe=timeframe,
            exchange=exchange,
        )

        dataset: list[dict[str, Any]] = []

        for row in rows:
            outcome = str(row.outcome or "").upper()
            if not include_breakeven and outcome == "BREAKEVEN":
                continue

            item = {
                "trade_id": row.trade_id,
                "symbol": row.symbol,
                "strategy_name": row.strategy_name,
                "timeframe": row.timeframe,
                "exchange": row.exchange,
                "outcome": outcome,
                "label": 1.0 if outcome == "WIN" else 0.0,
                "pnl": row.pnl,
                "pnl_pct": row.pnl_pct,
                "confidence": row.confidence,
                "signal_is_buy": row.signal_is_buy,
                "features": self.deserialize_payload_static(row.features_json),
            }

            for column in self.FEATURE_COLUMNS:
                item[column] = self._normalize_float(
                    getattr(row, column, None)) or 0.0

            dataset.append(item)

        return dataset

    def summary(
        self,
        *,
        symbol: str | None = None,
        strategy_name: str | None = None,
        timeframe: str | None = None,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        rows = self.get_trade_records(
            limit=100000,
            symbol=symbol,
            strategy_name=strategy_name,
            timeframe=timeframe,
            exchange=exchange,
        )

        total = len(rows)
        wins = sum(1 for row in rows if str(
            row.outcome or "").upper() == "WIN")
        losses = sum(1 for row in rows if str(
            row.outcome or "").upper() == "LOSS")
        breakeven = sum(1 for row in rows if str(
            row.outcome or "").upper() == "BREAKEVEN")
        pnl = sum(float(row.pnl or 0.0) for row in rows)

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": wins / max(1, wins + losses),
            "realized_pnl": pnl,
            "average_pnl": pnl / total if total else 0.0,
        }

    def _record_row_payload(self, payload: dict[str, Any], features: dict[str, Any]) -> dict[str, Any]:
        row_data = {
            "trade_id": self._normalize_text(payload.get("trade_id")),
            "decision_id": self._normalize_text(payload.get("decision_id")),
            "symbol": self._normalize_symbol(payload.get("symbol")),
            "exchange": self._normalize_text(payload.get("exchange")),
            "source": self._normalize_text(payload.get("source")),
            "strategy_name": self._normalize_text(payload.get("strategy_name")),
            "timeframe": self._normalize_text(payload.get("timeframe")),
            "signal": self._normalize_side(payload.get("signal")),
            "side": self._normalize_side(payload.get("side")),
            "market_regime": self._normalize_text(payload.get("market_regime")),
            "volatility_regime": self._normalize_text(payload.get("volatility_regime")),
            "feature_version": self._normalize_text(payload.get("feature_version")),
            "outcome": self._normalize_text(payload.get("outcome")),
            "entry_order_id": self._normalize_text(payload.get("entry_order_id")),
            "exit_order_id": self._normalize_text(payload.get("exit_order_id")),
            "signal_timestamp": self._normalize_timestamp(payload.get("signal_timestamp")),
            "entry_timestamp": self._normalize_timestamp(payload.get("entry_timestamp")),
            "exit_timestamp": self._normalize_timestamp(payload.get("exit_timestamp")),
            "duration_seconds": self._normalize_float(payload.get("duration_seconds")),
            "quantity": self._normalize_float(payload.get("quantity")),
            "entry_price": self._normalize_float(payload.get("entry_price")),
            "exit_price": self._normalize_float(payload.get("exit_price")),
            "pnl": self._normalize_float(payload.get("pnl")),
            "pnl_pct": self._normalize_float(payload.get("pnl_pct")),
            "confidence": self._normalize_float(payload.get("confidence")),
            "signal_is_buy": 1.0 if str(payload.get("signal") or payload.get("side") or "").upper() == "BUY" else 0.0,
            "features_json": self._normalize_payload(features),
            "regime_json": self._normalize_payload(payload.get("regime_snapshot")),
            "metadata_json": self._normalize_payload(payload.get("metadata")),
        }

        for column in self.FEATURE_COLUMNS:
            db_column = "macd_line" if column == "macd" else column

            source_keys = [column]
            if column == "macd_line":
                source_keys = ["macd_line", "macd"]
            elif column == "momentum":
                source_keys = ["momentum", "momentum_1"]

            value = None
            for key in source_keys:
                if key in features:
                    value = features.get(key)
                    break

            row_data[db_column] = self._normalize_float(value)

        return row_data

    def _commit_row(self, row: Any) -> Any:
        with self.session_factory() as session:
            try:
                session.add(row)
                session.commit()
                session.refresh(row)
                return row
            except SQLAlchemyError:
                session.rollback()
                raise

    def _payload_from(self, obj: Any, fallback: dict[str, Any]) -> dict[str, Any]:
        if obj is None:
            return dict(fallback or {})

        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            try:
                payload = obj.to_dict()
                if isinstance(payload, Mapping):
                    return dict(payload)
            except Exception:
                pass

        if is_dataclass(obj):
            try:
                return asdict(obj)
            except Exception:
                raise

        if isinstance(obj, Mapping):
            return dict(obj)

        if hasattr(obj, "__dict__"):
            return dict(vars(obj))

        return dict(fallback or {})

    def _normalize_timestamp(self, value: Any) -> datetime:
        if value is None:
            return utc_naive_now()

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        try:
            numeric = float(value)
            if abs(numeric) > 1e11:
                return datetime.fromtimestamp(numeric / 1000.0, tz=timezone.utc).replace(tzinfo=None)
            return datetime.fromtimestamp(numeric, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

        text = str(value or "").strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return utc_naive_now()

        if parsed.tzinfo is None:
            return parsed

        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    def _normalize_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_symbol(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        return text.upper() if text else None

    def _normalize_side(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        if not text:
            return None

        upper = text.upper()

        if upper in {"LONG", "BUY"}:
            return "BUY"
        if upper in {"SHORT", "SELL"}:
            return "SELL"
        if upper in {"HOLD", "WAIT", "NONE", "NEUTRAL"}:
            return "HOLD"

        return upper

    def _normalize_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None

        try:
            number = float(value)
        except Exception:
            return None

        if not math.isfinite(number):
            return None

        return number

    def _normalize_payload(self, payload: Any) -> str | None:
        if payload in (None, "", {}):
            return None

        try:
            return json.dumps(self._json_safe(payload), default=str, sort_keys=True)
        except Exception:
            return json.dumps({"raw": str(payload)}, default=str, sort_keys=True)

    @staticmethod
    def deserialize_payload_static(payload: Any) -> dict[str, Any]:
        if payload in (None, ""):
            return {}

        if isinstance(payload, dict):
            return dict(payload)

        try:
            result = json.loads(payload)
            return dict(result) if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _json_safe(self, value: Any) -> Any:
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
                return self._json_safe(asdict(value))
            except Exception:
                pass
        if isinstance(value, Mapping):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        if hasattr(value, "value"):
            return self._json_safe(value)
        return str(value)


__all__ = [
    "PaperTradeEventRow",
    "PaperTradeRecordRow",
    "PaperTradeLearningRepository",
]
