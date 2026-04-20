"""Repository layer for equity snapshot persistence and retrieval.

This module defines the SQLAlchemy model for equity snapshot records and
provides repository helpers to save snapshots, query recent records, and
load the latest snapshot for an exchange/account combination.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, select

from storage import database as storage_db


class EquitySnapshot(storage_db.Base):
    """SQLAlchemy model for a single equity snapshot record."""

    __tablename__ = "equity_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(255), index=True)
    account_label = Column(String(255), index=True)
    equity = Column(Float, index=True)
    balance = Column(Float)
    free_margin = Column(Float)
    used_margin = Column(Float)
    payload_json = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)


class EquitySnapshotRepository:
    """Repository for persisting and querying equity snapshot history.

    The repository normalizes incoming values, serializes optional payloads, and
    exposes helper methods to fetch recent snapshots or the latest snapshot for
    a given exchange/account label.
    """

    def save_snapshot(
        self,
        equity,
        exchange=None,
        account_label=None,
        timestamp=None,
        balance=None,
        free_margin=None,
        used_margin=None,
        payload=None,
    ):
        """Persist an equity snapshot and return the saved database row."""
        snapshot = EquitySnapshot(
            exchange=str(exchange or "").lower() or None,
            account_label=str(account_label or "").strip() or None,
            equity=float(equity),
            balance=self._normalize_float(balance),
            free_margin=self._normalize_float(free_margin),
            used_margin=self._normalize_float(used_margin),
            payload_json=self._normalize_payload(payload),
            timestamp=self._normalize_timestamp(timestamp),
        )

        with storage_db.SessionLocal() as session:
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            return snapshot

    def get_snapshots(self, limit=2000, exchange=None, account_label=None):
        """Return recent equity snapshots optionally filtered by exchange and account."""
        with storage_db.SessionLocal() as session:
            stmt = select(EquitySnapshot)
            normalized_exchange = str(exchange or "").lower() or None
            normalized_account = str(account_label or "").strip() or None
            if normalized_exchange:
                stmt = stmt.where(EquitySnapshot.exchange == normalized_exchange)
            if normalized_account:
                stmt = stmt.where(EquitySnapshot.account_label == normalized_account)
            stmt = stmt.order_by(EquitySnapshot.timestamp.desc(), EquitySnapshot.id.desc()).limit(int(limit))
            return list(session.execute(stmt).scalars().all())

    def latest_snapshot(self, exchange=None, account_label=None):
        """Return the most recent equity snapshot for an optional exchange/account."""
        rows = self.get_snapshots(limit=1, exchange=exchange, account_label=account_label)
        return rows[0] if rows else None

    def _normalize_timestamp(self, value):
        """Normalize input into a UTC-naive datetime for storage."""
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
        text_value = str(value).strip()
        if text_value.endswith("Z"):
            text_value = text_value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text_value)
        except ValueError:
            return datetime.now(timezone.utc).replace(tzinfo=None)
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    def _normalize_float(self, value):
        """Convert a value to float, returning None for invalid inputs."""
        if value in (None, ""):
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _normalize_payload(self, payload):
        """Serialize payloads as JSON text or return None for empty values."""
        if payload in (None, ""):
            return None
        try:
            return json.dumps(payload, default=str)
        except Exception:
            return json.dumps({"value": str(payload)})
