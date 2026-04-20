"""Repository layer for storing and querying agent decision history.

This module defines the SQLAlchemy model used to persist agent decisions and
provides repository helpers for saving decisions, filtering recent records, and
reconstructing the latest decision chain for a symbol.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, select

from storage import database as storage_db


class AgentDecision(storage_db.Base):
    """SQLAlchemy model representing a single agent decision record."""
    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(String(255), index=True)
    exchange = Column(String(255), index=True)
    account_label = Column(String(255), index=True)
    symbol = Column(String(255), index=True)
    agent_name = Column(String(255), index=True)
    stage = Column(String(255), index=True)
    strategy_name = Column(String(255), index=True)
    timeframe = Column(String(255), index=True)
    side = Column(String(255))
    confidence = Column(Float)
    approved = Column(Integer)
    reason = Column(String(255))
    payload_json = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)


class AgentDecisionRepository:
    """Repository for persisting and retrieving agent decision records.

    This class normalizes input values, stores decisions in the database, and
    exposes helper methods to query recent decisions and reconstruct the latest
    decision chain for a symbol.
    """

    def save_decision(
        self,
        agent_name,
        stage,
        symbol=None,
        decision_id=None,
        exchange=None,
        account_label=None,
        strategy_name=None,
        timeframe=None,
        side=None,
        confidence=None,
        approved=None,
        reason=None,
        payload=None,
        timestamp=None,
    ):
        """Persist an agent decision and return the saved database row."""
        row = AgentDecision(
            decision_id=str(decision_id or "").strip() or None,
            exchange=str(exchange or "").lower() or None,
            account_label=str(account_label or "").strip() or None,
            symbol=str(symbol or "").strip().upper() or None,
            agent_name=str(agent_name or "").strip() or None,
            stage=str(stage or "").strip() or None,
            strategy_name=str(strategy_name or "").strip() or None,
            timeframe=str(timeframe or "").strip() or None,
            side=str(side or "").strip().lower() or None,
            confidence=self._normalize_float(confidence),
            approved=self._normalize_bool(approved),
            reason=self._normalize_text(reason),
            payload_json=self._normalize_payload(payload),
            timestamp=self._normalize_timestamp(timestamp),
        )

        with storage_db.SessionLocal() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_decisions(self, limit=200, symbol=None, decision_id=None, exchange=None, account_label=None):
        """Return recent agent decisions filtered by optional identifiers."""
        with storage_db.SessionLocal() as session:
            stmt = select(AgentDecision)
            normalized_symbol = str(symbol or "").strip().upper() or None
            normalized_decision_id = str(decision_id or "").strip() or None
            normalized_exchange = str(exchange or "").lower() or None
            normalized_account = str(account_label or "").strip() or None
            if normalized_symbol:
                stmt = stmt.where(AgentDecision.symbol == normalized_symbol)
            if normalized_decision_id:
                stmt = stmt.where(AgentDecision.decision_id == normalized_decision_id)
            if normalized_exchange:
                stmt = stmt.where(AgentDecision.exchange == normalized_exchange)
            if normalized_account:
                stmt = stmt.where(AgentDecision.account_label == normalized_account)
            stmt = stmt.order_by(AgentDecision.timestamp.desc(), AgentDecision.id.desc()).limit(int(limit))
            return list(session.execute(stmt).scalars().all())

    def latest_chain_for_symbol(self, symbol, limit=50, exchange=None, account_label=None):
        """Return the most recent decision chain for the provided symbol.

        If decision records include a shared `decision_id`, the chain is built using
        that identifier. Otherwise the chain is reconstructed from the newest symbol
        entries.
        """
        rows = self.get_decisions(limit=max(int(limit) * 4, 100), symbol=symbol, exchange=exchange, account_label=account_label)
        if not rows:
            return []
        latest_decision_id = next((str(getattr(row, "decision_id", "") or "").strip() for row in rows if str(getattr(row, "decision_id", "") or "").strip()), "")
        if latest_decision_id:
            chain = [row for row in rows if str(getattr(row, "decision_id", "") or "").strip() == latest_decision_id]
        else:
            newest_symbol = str(getattr(rows[0], "symbol", "") or "").strip().upper()
            chain = [row for row in rows if str(getattr(row, "symbol", "") or "").strip().upper() == newest_symbol]
        chain = list(reversed(chain))
        return chain[-max(1, int(limit)):]

    def _normalize_timestamp(self, value):
        """Normalize input into a UTC naive datetime for storage."""
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

    def _normalize_bool(self, value):
        """Normalize boolean-like values to integer storage values 1 or 0."""
        if value in (None, ""):
            return None
        return 1 if bool(value) else 0

    def _normalize_text(self, value):
        """Trim text values and treat empty strings as None."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_payload(self, payload):
        """Serialize payload values to JSON text with a fallback for unsupported types."""
        if payload in (None, ""):
            return None
        try:
            return json.dumps(payload, default=str)
        except Exception:
            return json.dumps({"value": str(payload)})
