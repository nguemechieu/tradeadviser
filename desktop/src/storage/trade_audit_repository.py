import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, select

from storage import database as storage_db


class TradeAudit(storage_db.Base):
    __tablename__ = "trade_audits"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(255), index=True)
    status = Column(String(255), index=True)
    exchange = Column(String(255), index=True)
    account_label = Column(String(255), index=True)
    symbol = Column(String(255), index=True)
    requested_symbol = Column(String(255), index=True)
    side = Column(String(255))
    order_type = Column(String(255))
    venue = Column(String(255), index=True)
    source = Column(String(255))
    order_id = Column(String(255), index=True)
    message = Column(Text)
    payload_json = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)


class TradeAuditRepository:
    def record_event(
        self,
        *,
        action,
        status=None,
        exchange=None,
        account_label=None,
        symbol=None,
        requested_symbol=None,
        side=None,
        order_type=None,
        venue=None,
        source=None,
        order_id=None,
        message=None,
        payload=None,
        timestamp=None,
    ):
        event = TradeAudit(
            action=str(action or "").strip() or "unknown",
            status=self._normalize_text(status),
            exchange=self._normalize_text(exchange),
            account_label=self._normalize_text(account_label),
            symbol=self._normalize_text(symbol),
            requested_symbol=self._normalize_text(requested_symbol),
            side=self._normalize_text(side),
            order_type=self._normalize_text(order_type),
            venue=self._normalize_text(venue),
            source=self._normalize_text(source),
            order_id=self._normalize_text(order_id),
            message=self._normalize_text(message),
            payload_json=self._normalize_payload(payload),
            timestamp=self._normalize_timestamp(timestamp),
        )
        with storage_db.SessionLocal() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def get_recent(self, limit=200):
        with storage_db.SessionLocal() as session:
            stmt = select(TradeAudit).order_by(TradeAudit.timestamp.desc(), TradeAudit.id.desc()).limit(int(limit))
            return list(session.execute(stmt).scalars().all())

    def _normalize_timestamp(self, value):
        if value is None:
            return datetime.now(timezone.utc).replace(tzinfo=None)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value
            return value.astimezone(timezone.utc).replace(tzinfo=None)
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

    def _normalize_payload(self, payload):
        if payload is None:
            return None
        try:
            return json.dumps(payload, default=str, sort_keys=True)
        except Exception:
            return json.dumps({"raw": str(payload)}, default=str)
