import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, select

from storage import database as storage_db


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
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)


class PaperTradeRecordRow(storage_db.Base):
    __tablename__ = "paper_trade_records"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(255), index=True)
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
    signal_is_buy = Column(Float)
    features_json = Column(Text)
    regime_json = Column(Text)
    metadata_json = Column(Text)


class PaperTradeLearningRepository:
    """Append-only persistence for paper trade lifecycle analytics and ML records."""

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
    ]

    def append_trade_event(self, event=None, **kwargs):
        payload = event.to_dict() if hasattr(event, "to_dict") else dict(kwargs or {})
        row = PaperTradeEventRow(
            trade_id=self._normalize_text(payload.get("trade_id")),
            decision_id=self._normalize_text(payload.get("decision_id")),
            symbol=self._normalize_text(payload.get("symbol")),
            exchange=self._normalize_text(payload.get("exchange")),
            source=self._normalize_text(payload.get("source")),
            strategy_name=self._normalize_text(payload.get("strategy_name")),
            timeframe=self._normalize_text(payload.get("timeframe")),
            side=self._normalize_text(payload.get("side")),
            signal=self._normalize_text(payload.get("signal")),
            event_type=self._normalize_text(payload.get("event_type")) or "unknown",
            order_status=self._normalize_text(payload.get("order_status")),
            order_id=self._normalize_text(payload.get("order_id")),
            price=self._normalize_float(payload.get("price")),
            quantity=self._normalize_float(payload.get("quantity")),
            confidence=self._normalize_float(payload.get("confidence")),
            message=self._normalize_text(payload.get("message")),
            payload_json=self._normalize_payload(payload.get("payload")),
            timestamp=self._normalize_timestamp(payload.get("timestamp")),
        )
        with storage_db.SessionLocal() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            row.payload_json = self._deserialize_payload(row.payload_json)
            return row

    def append_trade_record(self, record=None, **kwargs):
        payload = record.to_dict() if hasattr(record, "to_dict") else dict(kwargs or {})
        features = dict(payload.get("feature_values") or {})
        row = PaperTradeRecordRow(
            trade_id=self._normalize_text(payload.get("trade_id")),
            decision_id=self._normalize_text(payload.get("decision_id")),
            symbol=self._normalize_text(payload.get("symbol")),
            exchange=self._normalize_text(payload.get("exchange")),
            source=self._normalize_text(payload.get("source")),
            strategy_name=self._normalize_text(payload.get("strategy_name")),
            timeframe=self._normalize_text(payload.get("timeframe")),
            signal=self._normalize_text(payload.get("signal")),
            side=self._normalize_text(payload.get("side")),
            market_regime=self._normalize_text(payload.get("market_regime")),
            volatility_regime=self._normalize_text(payload.get("volatility_regime")),
            feature_version=self._normalize_text(payload.get("feature_version")),
            outcome=self._normalize_text(payload.get("outcome")),
            entry_order_id=self._normalize_text(payload.get("entry_order_id")),
            exit_order_id=self._normalize_text(payload.get("exit_order_id")),
            signal_timestamp=self._normalize_timestamp(payload.get("signal_timestamp")),
            entry_timestamp=self._normalize_timestamp(payload.get("entry_timestamp")),
            exit_timestamp=self._normalize_timestamp(payload.get("exit_timestamp")),
            duration_seconds=self._normalize_float(payload.get("duration_seconds")),
            quantity=self._normalize_float(payload.get("quantity")),
            entry_price=self._normalize_float(payload.get("entry_price")),
            exit_price=self._normalize_float(payload.get("exit_price")),
            pnl=self._normalize_float(payload.get("pnl")),
            pnl_pct=self._normalize_float(payload.get("pnl_pct")),
            confidence=self._normalize_float(payload.get("confidence")),
            rsi=self._normalize_float(features.get("rsi")),
            ema_fast=self._normalize_float(features.get("ema_fast")),
            ema_slow=self._normalize_float(features.get("ema_slow")),
            atr=self._normalize_float(features.get("atr")),
            volume=self._normalize_float(features.get("volume")),
            return_1=self._normalize_float(features.get("return_1")),
            return_5=self._normalize_float(features.get("return_5")),
            volume_ratio=self._normalize_float(features.get("volume_ratio")),
            momentum=self._normalize_float(features.get("momentum")),
            macd_line=self._normalize_float(features.get("macd_line")),
            macd_signal=self._normalize_float(features.get("macd_signal")),
            macd_hist=self._normalize_float(features.get("macd_hist")),
            atr_pct=self._normalize_float(features.get("atr_pct")),
            trend_strength=self._normalize_float(features.get("trend_strength")),
            pullback_gap=self._normalize_float(features.get("pullback_gap")),
            band_position=self._normalize_float(features.get("band_position")),
            signal_is_buy=1.0 if str(payload.get("signal") or "").upper() == "BUY" else 0.0,
            features_json=self._normalize_payload(features),
            regime_json=self._normalize_payload(payload.get("regime_snapshot")),
            metadata_json=self._normalize_payload(payload.get("metadata")),
        )
        with storage_db.SessionLocal() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            row.features_json = self._deserialize_payload(row.features_json)
            row.regime_json = self._deserialize_payload(row.regime_json)
            row.metadata_json = self._deserialize_payload(row.metadata_json)
            return row

    def get_trade_events(self, limit=500, symbol=None, decision_id=None, trade_id=None):
        with storage_db.SessionLocal() as session:
            stmt = select(PaperTradeEventRow)
            if symbol:
                stmt = stmt.where(PaperTradeEventRow.symbol == self._normalize_text(symbol))
            if decision_id:
                stmt = stmt.where(PaperTradeEventRow.decision_id == self._normalize_text(decision_id))
            if trade_id:
                stmt = stmt.where(PaperTradeEventRow.trade_id == self._normalize_text(trade_id))
            stmt = stmt.order_by(PaperTradeEventRow.timestamp.desc(), PaperTradeEventRow.id.desc()).limit(int(limit))
            rows = list(session.execute(stmt).scalars().all())
            for row in rows:
                row.payload_json = self._deserialize_payload(row.payload_json)
            return rows

    def get_trade_records(self, limit=5000, symbol=None, strategy_name=None, timeframe=None, exchange=None, outcome=None):
        with storage_db.SessionLocal() as session:
            stmt = select(PaperTradeRecordRow)
            if symbol:
                stmt = stmt.where(PaperTradeRecordRow.symbol == self._normalize_text(symbol))
            if strategy_name:
                stmt = stmt.where(PaperTradeRecordRow.strategy_name == self._normalize_text(strategy_name))
            if timeframe:
                stmt = stmt.where(PaperTradeRecordRow.timeframe == self._normalize_text(timeframe))
            if exchange:
                stmt = stmt.where(PaperTradeRecordRow.exchange == self._normalize_text(exchange))
            if outcome:
                stmt = stmt.where(PaperTradeRecordRow.outcome == self._normalize_text(outcome))
            stmt = stmt.order_by(PaperTradeRecordRow.exit_timestamp.desc(), PaperTradeRecordRow.id.desc()).limit(int(limit))
            rows = list(session.execute(stmt).scalars().all())
            for row in rows:
                row.features_json = self._deserialize_payload(row.features_json)
                row.regime_json = self._deserialize_payload(row.regime_json)
                row.metadata_json = self._deserialize_payload(row.metadata_json)
            return rows

    def _normalize_timestamp(self, value):
        if value is None:
            return datetime.now(timezone.utc).replace(tzinfo=None)
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
            return datetime.now(timezone.utc).replace(tzinfo=None)
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    def _normalize_text(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_float(self, value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _normalize_payload(self, payload):
        if payload in (None, "", {}):
            return None
        try:
            return json.dumps(payload, default=str, sort_keys=True)
        except Exception:
            return json.dumps({"raw": str(payload)}, default=str, sort_keys=True)

    def _deserialize_payload(self, payload):
        if payload in (None, ""):
            return {}
        if isinstance(payload, dict):
            return dict(payload)
        try:
            return json.loads(payload)
        except Exception:
            return {}
