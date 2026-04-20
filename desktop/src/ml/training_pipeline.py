from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ml.model_manager import ModelArtifact, ModelManager


@dataclass(slots=True)
class TrainingJobResult:
    artifact: ModelArtifact
    sample_count: int
    feature_names: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


class TrainingPipeline:
    """Lightweight training scheduler/registrar for versioned models."""

    def __init__(self, model_manager: ModelManager | None = None) -> None:
        self.model_manager = model_manager or ModelManager()

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
    ) -> TrainingJobResult:
        model = trainer(list(rows or []), list(labels or []))
        artifact = self.model_manager.register(
            model_name,
            version,
            model,
            path=artifact_path,
            metadata=metadata,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return TrainingJobResult(
            artifact=artifact,
            sample_count=len(list(rows or [])),
            feature_names=sorted((rows or [{}])[0].keys()) if rows else [],
            metrics=dict(metrics or {}),
        )
