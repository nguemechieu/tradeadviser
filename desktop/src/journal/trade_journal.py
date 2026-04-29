from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_naive(value: datetime | None = None) -> datetime:
    timestamp = value or _utc_now()
    if timestamp.tzinfo is not None:
        return timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    return timestamp


def _dump_json(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, sort_keys=True)


def _load_json(payload: str | None) -> Any:
    if not payload:
        return {}
    return json.loads(payload)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DATABASE_URL = os.getenv(
    "TRADE_JOURNAL_DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'institutional_trade_journal.db').as_posix()}",
)

Base = declarative_base()


class TradeJournalRow(Base):
    __tablename__ = "institutional_trade_journal"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(255), unique=True, nullable=False, index=True)
    symbol = Column(String(255), nullable=False, index=True)
    side = Column(String(32), nullable=False)
    strategy_name = Column(String(255), nullable=False, index=True)
    status = Column(String(64), nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    position_size = Column(Float, nullable=False)
    risk_taken = Column(Float, nullable=False)
    virtual_stop_loss = Column(Float, nullable=False)
    virtual_take_profit = Column(Float, nullable=False)
    entry_reason = Column(Text)
    exit_reason = Column(Text)
    pnl = Column(Float)
    signal_data_json = Column(Text)
    metadata_json = Column(Text)
    opened_at = Column(DateTime, default=_utc_naive, nullable=False, index=True)
    closed_at = Column(DateTime)
    updated_at = Column(DateTime, default=_utc_naive, nullable=False, index=True)


@dataclass(slots=True)
class TradeJournalRecord:
    trade_id: str
    symbol: str
    side: str
    strategy_name: str
    status: str
    entry_price: float
    position_size: float
    risk_taken: float
    virtual_stop_loss: float
    virtual_take_profit: float
    entry_reason: str = ""
    exit_reason: str | None = None
    exit_price: float | None = None
    pnl: float | None = None
    signal_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    opened_at: datetime = field(default_factory=_utc_now)
    closed_at: datetime | None = None
    updated_at: datetime = field(default_factory=_utc_now)


class TradeJournal:
    """Persist institutional trade lifecycle records to SQLite or Postgres."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = str(database_url or DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL
        connect_args = {"check_same_thread": False} if self.database_url.startswith("sqlite") else {}
        self.engine = create_engine(self.database_url, echo=False, future=True, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    async def record_entry(
        self,
        *,
        trade_id: str,
        symbol: str,
        side: str,
        strategy_name: str,
        entry_price: float,
        position_size: float,
        risk_taken: float,
        virtual_stop_loss: float,
        virtual_take_profit: float,
        entry_reason: str = "",
        signal_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        opened_at: datetime | None = None,
    ) -> TradeJournalRecord:
        now = _utc_now()
        with self.session_factory() as session:
            row = self._find_row(session, trade_id)
            if row is None:
                row = TradeJournalRow(trade_id=str(trade_id))
                session.add(row)
            row.symbol = str(symbol)
            row.side = str(side)
            row.strategy_name = str(strategy_name or "unknown")
            row.status = "open"
            row.entry_price = float(entry_price)
            row.position_size = float(position_size)
            row.risk_taken = float(risk_taken)
            row.virtual_stop_loss = float(virtual_stop_loss)
            row.virtual_take_profit = float(virtual_take_profit)
            row.entry_reason = str(entry_reason or "")
            row.signal_data_json = _dump_json(signal_data or {})
            row.metadata_json = _dump_json(metadata or {})
            row.opened_at = _utc_naive(opened_at or now)
            row.updated_at = _utc_naive(now)
            session.commit()
            session.refresh(row)
            return self._to_record(row)

    async def record_exit(
        self,
        *,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        pnl: float,
        status: str = "closed",
        metadata: dict[str, Any] | None = None,
        closed_at: datetime | None = None,
    ) -> TradeJournalRecord | None:
        now = _utc_now()
        with self.session_factory() as session:
            row = self._find_row(session, trade_id)
            if row is None:
                return None
            merged_metadata = _load_json(row.metadata_json)
            merged_metadata.update(dict(metadata or {}))
            row.exit_price = float(exit_price)
            row.exit_reason = str(exit_reason or "")
            row.pnl = float(pnl)
            row.status = str(status or "closed")
            row.metadata_json = _dump_json(merged_metadata)
            row.closed_at = _utc_naive(closed_at or now)
            row.updated_at = _utc_naive(now)
            session.commit()
            session.refresh(row)
            return self._to_record(row)

    def fetch_trade(self, trade_id: str) -> TradeJournalRecord | None:
        with self.session_factory() as session:
            row = self._find_row(session, trade_id)
            return None if row is None else self._to_record(row)

    def list_trades(self, *, limit: int = 100) -> list[TradeJournalRecord]:
        with self.session_factory() as session:
            stmt = select(TradeJournalRow).order_by(TradeJournalRow.updated_at.desc(), TradeJournalRow.id.desc()).limit(int(limit))
            rows = list(session.execute(stmt).scalars().all())
            return [self._to_record(row) for row in rows]

    @staticmethod
    def _find_row(session: Session, trade_id: str) -> TradeJournalRow | None:
        stmt = select(TradeJournalRow).where(TradeJournalRow.trade_id == str(trade_id)).limit(1)
        return session.execute(stmt).scalars().first()

    @staticmethod
    def _to_record(row: TradeJournalRow) -> TradeJournalRecord:
        return TradeJournalRecord(
            trade_id=row.trade_id,
            symbol=row.symbol,
            side=row.side,
            strategy_name=row.strategy_name,
            status=row.status,
            entry_price=float(row.entry_price or 0.0),
            exit_price=None if row.exit_price is None else float(row.exit_price),
            position_size=float(row.position_size or 0.0),
            risk_taken=float(row.risk_taken or 0.0),
            virtual_stop_loss=float(row.virtual_stop_loss or 0.0),
            virtual_take_profit=float(row.virtual_take_profit or 0.0),
            entry_reason=row.entry_reason or "",
            exit_reason=row.exit_reason,
            pnl=None if row.pnl is None else float(row.pnl),
            signal_data=dict(_load_json(row.signal_data_json)),
            metadata=dict(_load_json(row.metadata_json)),
            opened_at=(row.opened_at.replace(tzinfo=timezone.utc) if row.opened_at and row.opened_at.tzinfo is None else row.opened_at) or _utc_now(),
            closed_at=None if row.closed_at is None else (row.closed_at.replace(tzinfo=timezone.utc) if row.closed_at.tzinfo is None else row.closed_at),
            updated_at=(row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at and row.updated_at.tzinfo is None else row.updated_at) or _utc_now(),
        )
