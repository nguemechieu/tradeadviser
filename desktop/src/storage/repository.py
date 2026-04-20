"""Legacy quant storage models preserved for compatibility."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from storage.database import Base, SessionLocal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_text(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    return json.dumps(value, ensure_ascii=True, default=str)


_CLASS_REGISTRY = getattr(Base.registry, "_class_registry", {})


if isinstance(_CLASS_REGISTRY.get("QuantFeatureVector"), type):
    QuantFeatureVector = _CLASS_REGISTRY["QuantFeatureVector"]
elif "quant_feature_vectors" in Base.metadata.tables:
    class QuantFeatureVector(Base):
        __table__ = Base.metadata.tables["quant_feature_vectors"]
else:
    class QuantFeatureVector(Base):
        __tablename__ = "quant_feature_vectors"

        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(64), nullable=False, index=True)
        timeframe = Column(String(32), nullable=True, index=True)
        feature_name = Column(String(128), nullable=True)
        features_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


if isinstance(_CLASS_REGISTRY.get("QuantModelScore"), type):
    QuantModelScore = _CLASS_REGISTRY["QuantModelScore"]
elif "quant_model_scores" in Base.metadata.tables:
    class QuantModelScore(Base):
        __table__ = Base.metadata.tables["quant_model_scores"]
else:
    class QuantModelScore(Base):
        __tablename__ = "quant_model_scores"

        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(64), nullable=False, index=True)
        model_name = Column(String(128), nullable=False, index=True)
        score = Column(Float, nullable=True)
        metadata_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


if isinstance(_CLASS_REGISTRY.get("QuantPerformanceMetric"), type):
    QuantPerformanceMetric = _CLASS_REGISTRY["QuantPerformanceMetric"]
elif "quant_performance_metrics" in Base.metadata.tables:
    class QuantPerformanceMetric(Base):
        __table__ = Base.metadata.tables["quant_performance_metrics"]
else:
    class QuantPerformanceMetric(Base):
        __tablename__ = "quant_performance_metrics"

        id = Column(Integer, primary_key=True, autoincrement=True)
        metric_name = Column(String(128), nullable=False, index=True)
        value = Column(Float, nullable=True)
        scope = Column(String(64), nullable=True, index=True)
        payload_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


if isinstance(_CLASS_REGISTRY.get("QuantTradeFeedback"), type):
    QuantTradeFeedback = _CLASS_REGISTRY["QuantTradeFeedback"]
elif "quant_trade_feedback" in Base.metadata.tables:
    class QuantTradeFeedback(Base):
        __table__ = Base.metadata.tables["quant_trade_feedback"]
else:
    class QuantTradeFeedback(Base):
        __tablename__ = "quant_trade_feedback"

        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(64), nullable=False, index=True)
        strategy_name = Column(String(128), nullable=True, index=True)
        timeframe = Column(String(32), nullable=True, index=True)
        side = Column(String(16), nullable=True)
        pnl = Column(Float, nullable=True)
        feedback = Column(Text, nullable=True)
        payload_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


if isinstance(_CLASS_REGISTRY.get("QuantTradeJournalEntry"), type):
    QuantTradeJournalEntry = _CLASS_REGISTRY["QuantTradeJournalEntry"]
elif "quant_trade_journal_entries" in Base.metadata.tables:
    class QuantTradeJournalEntry(Base):
        __table__ = Base.metadata.tables["quant_trade_journal_entries"]
else:
    class QuantTradeJournalEntry(Base):
        __tablename__ = "quant_trade_journal_entries"

        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(64), nullable=False, index=True)
        strategy_name = Column(String(128), nullable=True, index=True)
        note = Column(Text, nullable=True)
        payload_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


if isinstance(_CLASS_REGISTRY.get("QuantTradeJournalSummary"), type):
    QuantTradeJournalSummary = _CLASS_REGISTRY["QuantTradeJournalSummary"]
elif "quant_trade_journal_summaries" in Base.metadata.tables:
    class QuantTradeJournalSummary(Base):
        __table__ = Base.metadata.tables["quant_trade_journal_summaries"]
else:
    class QuantTradeJournalSummary(Base):
        __tablename__ = "quant_trade_journal_summaries"

        id = Column(Integer, primary_key=True, autoincrement=True)
        summary_key = Column(String(128), nullable=False, index=True)
        summary = Column(Text, nullable=True)
        payload_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


class QuantRepository:
    """Small compatibility repository for legacy quant persistence paths."""

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or SessionLocal

    def _save(self, model) -> Any:
        session = self._session_factory()
        try:
            session.add(model)
            session.commit()
            session.refresh(model)
            return model
        finally:
            session.close()

    def save_feature_vector(
        self,
        *,
        symbol: str,
        timeframe: str | None = None,
        feature_name: str | None = None,
        features: Any = None,
    ) -> QuantFeatureVector:
        return self._save(
            QuantFeatureVector(
                symbol=str(symbol),
                timeframe=timeframe,
                feature_name=feature_name,
                features_json=_json_text(features),
            )
        )

    def save_model_score(
        self,
        *,
        symbol: str,
        model_name: str,
        score: float | None = None,
        metadata: Any = None,
    ) -> QuantModelScore:
        return self._save(
            QuantModelScore(
                symbol=str(symbol),
                model_name=str(model_name),
                score=None if score is None else float(score),
                metadata_json=_json_text(metadata),
            )
        )

    def save_performance_metric(
        self,
        *,
        metric_name: str,
        value: float | None = None,
        scope: str | None = None,
        payload: Any = None,
    ) -> QuantPerformanceMetric:
        return self._save(
            QuantPerformanceMetric(
                metric_name=str(metric_name),
                value=None if value is None else float(value),
                scope=scope,
                payload_json=_json_text(payload),
            )
        )

    def save_trade_feedback(
        self,
        *,
        symbol: str,
        strategy_name: str | None = None,
        timeframe: str | None = None,
        side: str | None = None,
        pnl: float | None = None,
        feedback: str | None = None,
        payload: Any = None,
    ) -> QuantTradeFeedback:
        return self._save(
            QuantTradeFeedback(
                symbol=str(symbol),
                strategy_name=strategy_name,
                timeframe=timeframe,
                side=side,
                pnl=None if pnl is None else float(pnl),
                feedback=feedback,
                payload_json=_json_text(payload),
            )
        )

    def save_trade_journal_entry(
        self,
        *,
        symbol: str,
        strategy_name: str | None = None,
        note: str | None = None,
        payload: Any = None,
    ) -> QuantTradeJournalEntry:
        return self._save(
            QuantTradeJournalEntry(
                symbol=str(symbol),
                strategy_name=strategy_name,
                note=note,
                payload_json=_json_text(payload),
            )
        )

    def save_trade_journal_summary(
        self,
        *,
        summary_key: str,
        summary: str | None = None,
        payload: Any = None,
    ) -> QuantTradeJournalSummary:
        return self._save(
            QuantTradeJournalSummary(
                summary_key=str(summary_key),
                summary=summary,
                payload_json=_json_text(payload),
            )
        )


__all__ = [
    "QuantFeatureVector",
    "QuantModelScore",
    "QuantPerformanceMetric",
    "QuantRepository",
    "QuantTradeFeedback",
    "QuantTradeJournalEntry",
    "QuantTradeJournalSummary",
]
