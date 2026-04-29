from __future__ import annotations

"""
InvestPro TrainingPipeline

Lightweight training scheduler/registrar for versioned models.

Responsibilities:
- validate training rows/labels
- train model using a provided trainer callable
- compute optional basic metrics
- save and register trained model
- preserve feature ordering
- support scalers/preprocessors
- return structured training result
- keep live/backtest model registry consistent
"""

import inspect
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

try:
    from ml.model_manager import ModelArtifact, ModelManager
except Exception:  # pragma: no cover
    from ml.model_registry import ModelArtifact, ModelManager  # type: ignore


@dataclass(slots=True)
class TrainingJobResult:
    artifact: ModelArtifact
    sample_count: int
    feature_names: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    status: str = "success"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrainingDataset:
    rows: list[dict[str, float]]
    labels: list[float]
    feature_names: list[str]

    @property
    def sample_count(self) -> int:
        return len(self.rows)


class TrainingPipeline:
    """Train, save, and register versioned models."""

    def __init__(
        self,
        model_manager: ModelManager | None = None,
        *,
        strict_features: bool = True,
        min_samples: int = 10,
        logger: Any = None,
    ) -> None:
        self.model_manager = model_manager or ModelManager()
        self.strict_features = bool(strict_features)
        self.min_samples = max(1, int(min_samples or 10))
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(
        self,
        *,
        model_name: str,
        version: str,
        trainer: Callable[[list[dict[str, float]], list[float]], Any],
        rows: list[dict[str, float]],
        labels: list[float],
        artifact_path: str,
        metrics: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
        scaler: Any = None,
        threshold: float = 0.5,
        package: bool = True,
        persist_model: bool = True,
        feature_names: list[str] | None = None,
    ) -> TrainingJobResult:
        """Train a model and register the artifact.

        trainer signature:
            trainer(rows, labels) -> model

        If your trainer needs feature ordering, read feature_names from metadata
        or build inside the trainer from the rows.
        """
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        dataset = self._prepare_dataset(
            rows=rows,
            labels=labels,
            feature_names=feature_names,
        )

        model = trainer(list(dataset.rows), list(dataset.labels))

        if inspect.isawaitable(model):
            raise TypeError(
                "TrainingPipeline.train() received an awaitable model. "
                "Use async_train() for async trainers."
            )

        computed_metrics = self._compute_basic_metrics(
            model=model,
            rows=dataset.rows,
            labels=dataset.labels,
        )

        merged_metrics = {
            **computed_metrics,
            **self._clean_float_dict(metrics or {}),
        }

        completed_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = time.perf_counter() - started

        merged_metadata = {
            **dict(metadata or {}),
            "model_name": str(model_name),
            "version": str(version),
            "feature_names": list(dataset.feature_names),
            "sample_count": dataset.sample_count,
            "trained_at": completed_at,
            "training_duration_seconds": duration_seconds,
            "threshold": float(threshold),
        }

        artifact = self._save_or_register(
            model_name=model_name,
            version=version,
            model=model,
            artifact_path=artifact_path,
            metadata=merged_metadata,
            metrics=merged_metrics,
            feature_names=dataset.feature_names,
            scaler=scaler,
            threshold=threshold,
            package=package,
            persist_model=persist_model,
            created_at=completed_at,
        )

        return TrainingJobResult(
            artifact=artifact,
            sample_count=dataset.sample_count,
            feature_names=list(dataset.feature_names),
            metrics=merged_metrics,
            metadata=merged_metadata,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            status="success",
        )

    async def async_train(
        self,
        *,
        model_name: str,
        version: str,
        trainer: Callable[[list[dict[str, float]], list[float]], Any],
        rows: list[dict[str, float]],
        labels: list[float],
        artifact_path: str,
        metrics: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
        scaler: Any = None,
        threshold: float = 0.5,
        package: bool = True,
        persist_model: bool = True,
        feature_names: list[str] | None = None,
    ) -> TrainingJobResult:
        """Async version for async trainers."""
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        dataset = self._prepare_dataset(
            rows=rows,
            labels=labels,
            feature_names=feature_names,
        )

        model = trainer(list(dataset.rows), list(dataset.labels))
        if inspect.isawaitable(model):
            model = await model

        computed_metrics = self._compute_basic_metrics(
            model=model,
            rows=dataset.rows,
            labels=dataset.labels,
        )

        merged_metrics = {
            **computed_metrics,
            **self._clean_float_dict(metrics or {}),
        }

        completed_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = time.perf_counter() - started

        merged_metadata = {
            **dict(metadata or {}),
            "model_name": str(model_name),
            "version": str(version),
            "feature_names": list(dataset.feature_names),
            "sample_count": dataset.sample_count,
            "trained_at": completed_at,
            "training_duration_seconds": duration_seconds,
            "threshold": float(threshold),
        }

        artifact = self._save_or_register(
            model_name=model_name,
            version=version,
            model=model,
            artifact_path=artifact_path,
            metadata=merged_metadata,
            metrics=merged_metrics,
            feature_names=dataset.feature_names,
            scaler=scaler,
            threshold=threshold,
            package=package,
            persist_model=persist_model,
            created_at=completed_at,
        )

        return TrainingJobResult(
            artifact=artifact,
            sample_count=dataset.sample_count,
            feature_names=list(dataset.feature_names),
            metrics=merged_metrics,
            metadata=merged_metadata,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            status="success",
        )

    # ------------------------------------------------------------------
    # Data prep
    # ------------------------------------------------------------------

    def _prepare_dataset(
        self,
        *,
        rows: list[dict[str, float]],
        labels: list[float],
        feature_names: list[str] | None = None,
    ) -> TrainingDataset:
        clean_rows = [dict(row or {}) for row in list(rows or [])]
        clean_labels = [float(label) for label in list(labels or [])]

        if not clean_rows:
            raise ValueError("Training rows are required")

        if not clean_labels:
            raise ValueError("Training labels are required")

        if len(clean_rows) != len(clean_labels):
            raise ValueError(
                f"Rows/labels length mismatch: {len(clean_rows)} rows vs {len(clean_labels)} labels"
            )

        if len(clean_rows) < self.min_samples:
            raise ValueError(
                f"Not enough samples for training: {len(clean_rows)} < {self.min_samples}"
            )

        resolved_features = list(
            feature_names or self._infer_feature_names(clean_rows))

        if not resolved_features:
            raise ValueError("No feature names were found")

        normalized_rows = [
            self._normalize_row(row, resolved_features)
            for row in clean_rows
        ]

        return TrainingDataset(
            rows=normalized_rows,
            labels=clean_labels,
            feature_names=resolved_features,
        )

    def _infer_feature_names(self, rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []

        if self.strict_features:
            first_keys = list(rows[0].keys())
            first_set = set(first_keys)

            for index, row in enumerate(rows[1:], start=1):
                current_set = set(row.keys())
                if current_set != first_set:
                    missing = sorted(first_set - current_set)
                    extra = sorted(current_set - first_set)
                    raise ValueError(
                        f"Inconsistent feature columns at row {index}. "
                        f"Missing={missing}, extra={extra}"
                    )

            return sorted(first_keys)

        features: set[str] = set()
        for row in rows:
            features.update(str(key) for key in row.keys())
        return sorted(features)

    def _normalize_row(self, row: dict[str, Any], feature_names: list[str]) -> dict[str, float]:
        normalized: dict[str, float] = {}

        for name in feature_names:
            value = row.get(name)

            if value in (None, ""):
                if self.strict_features:
                    raise ValueError(f"Missing feature value: {name}")
                value = 0.0

            normalized[name] = self._safe_float(value, 0.0)

        return normalized

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _compute_basic_metrics(
        self,
        *,
        model: Any,
        rows: list[dict[str, float]],
        labels: list[float],
    ) -> dict[str, float]:
        if model is None:
            return {}

        if not hasattr(model, "predict"):
            return {}

        try:
            predictions = model.predict(rows)
        except Exception:
            return {}

        predicted = list(predictions or [])
        if len(predicted) != len(labels):
            return {}

        correct = 0
        total = len(labels)

        for pred, label in zip(predicted, labels):
            try:
                pred_value = float(pred)
                label_value = float(label)
            except Exception:
                continue

            pred_class = int(pred_value >= 0.5)
            label_class = int(label_value >= 0.5)
            if pred_class == label_class:
                correct += 1

        if total <= 0:
            return {}

        return {
            "train_accuracy": correct / total,
        }

    # ------------------------------------------------------------------
    # Save/register compatibility
    # ------------------------------------------------------------------

    def _save_or_register(
        self,
        *,
        model_name: str,
        version: str,
        model: Any,
        artifact_path: str,
        metadata: dict[str, Any],
        metrics: dict[str, float],
        feature_names: list[str],
        scaler: Any,
        threshold: float,
        package: bool,
        persist_model: bool,
        created_at: str,
    ) -> ModelArtifact:
        manager = self.model_manager

        if persist_model and hasattr(manager, "save_and_register"):
            return manager.save_and_register(
                name=model_name,
                version=version,
                model=model,
                path=artifact_path,
                metadata={
                    **metadata,
                    "metrics": dict(metrics or {}),
                },
                feature_columns=feature_names,
                scaler=scaler,
                threshold=threshold,
                package=package,
            )

        if persist_model and hasattr(manager, "save"):
            record = manager.save(
                model=model,
                name=artifact_path,
                scaler=scaler,
                feature_columns=feature_names,
                target_name="target",
                config={
                    "model_name": model_name,
                    "version": version,
                },
                metrics=metrics,
                metadata=metadata,
                overwrite=True,
                package=package,
            )

            # File artifact manager returns ModelRecord, not always ModelArtifact.
            return ModelArtifact(
                name=str(model_name),
                version=str(version),
                path=str(getattr(record, "path", artifact_path)),
                created_at=created_at,
                metadata={
                    **metadata,
                    "metrics": dict(metrics or {}),
                    "record": record.to_dict() if hasattr(record, "to_dict") else str(record),
                },
            )

        # Last fallback: registry only. This does not save to disk.
        return manager.register(
            model_name,
            version,
            model,
            path=artifact_path,
            metadata={
                **metadata,
                "metrics": dict(metrics or {}),
                "warning": "Model was registered without being saved to disk.",
            },
            created_at=created_at,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _clean_float_dict(self, value: dict[str, Any]) -> dict[str, float]:
        output: dict[str, float] = {}

        for key, item in dict(value or {}).items():
            numeric = self._safe_float(item, default=None)
            if numeric is not None:
                output[str(key)] = numeric

        return output

    def _safe_float(self, value: Any, default: float | None = 0.0) -> float | None:
        if value in (None, ""):
            return default

        try:
            number = float(value)
        except Exception:
            return default

        if not math.isfinite(number):
            return default

        return number
