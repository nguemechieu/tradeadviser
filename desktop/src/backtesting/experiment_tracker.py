"""Experiment tracking utilities for backtest records.

This module provides a lightweight in-memory experiment tracker that collects
backtest metadata, parameters, dataset details, and metrics. It also exposes a
convenience method to convert stored experiments into a pandas DataFrame for
analysis or reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd


@dataclass
class ExperimentRecord:
    """Immutable record structure for a single experiment run."""

    experiment_id: str
    name: str
    strategy_name: str
    symbol: str
    timeframe: str
    parameters: dict = field(default_factory=dict)
    dataset_metadata: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExperimentTracker:
    """In-memory manager for experiment records."""

    def __init__(self):
        """Create a new experiment tracker with an empty record list."""
        self.records = []

    def add_record(
        self,
        name,
        strategy_name,
        symbol,
        timeframe="1h",
        parameters=None,
        dataset_metadata=None,
        metrics=None,
        notes="",
    ):
        """Add a new experiment record and return the created record.

        The tracker normalizes common fields and assigns a stable experiment ID.
        Parameters with missing values are coerced into dictionaries so downstream
        export logic can safely iterate over them.
        """
        record = ExperimentRecord(
            experiment_id=f"exp-{len(self.records) + 1:04d}",
            name=str(name or "experiment").strip() or "experiment",
            strategy_name=str(strategy_name or "unknown").strip() or "unknown",
            symbol=str(symbol or "BACKTEST").strip() or "BACKTEST",
            timeframe=str(timeframe or "1h").strip() or "1h",
            parameters=dict(parameters or {}),
            dataset_metadata=dict(dataset_metadata or {}),
            metrics=dict(metrics or {}),
            notes=str(notes or "").strip(),
        )
        self.records.append(record)
        return record

    def to_frame(self):
        """Convert all tracked experiment records into a pandas DataFrame.

        The DataFrame includes basic experiment metadata and expands each record's
        parameter and dataset metadata dictionaries into prefixed columns.
        """
        rows = []
        for record in self.records:
            row = {
                "experiment_id": record.experiment_id,
                "name": record.name,
                "strategy_name": record.strategy_name,
                "symbol": record.symbol,
                "timeframe": record.timeframe,
                "created_at": record.created_at,
                "notes": record.notes,
            }
            # Expand parameter and metadata dictionaries into flat columns.
            row.update({f"param_{key}": value for key, value in record.parameters.items()})
            row.update({f"data_{key}": value for key, value in record.dataset_metadata.items()})
            row.update(record.metrics)
            rows.append(row)
        return pd.DataFrame(rows)
