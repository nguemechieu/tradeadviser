from __future__ import annotations

"""
Compatibility wrapper for paper trade learning storage models.

The canonical implementation lives in:
    paper_learning.repository

This file exists because storage.database.init_database() imports:
    storage.paper_trade_learning_repository

Do not define SQLAlchemy ORM tables here, or SQLAlchemy will register
paper_trade_events / paper_trade_records twice in the same metadata.
"""

from repository.repository import (
    PaperTradeEventRow,
    PaperTradeLearningRepository,
    PaperTradeRecordRow,
)

__all__ = [
    "PaperTradeEventRow",
    "PaperTradeLearningRepository",
    "PaperTradeRecordRow",
]
