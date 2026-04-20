from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class PredictableModel(Protocol):
    def predict_proba(self, rows):
        ...

    def predict(self, rows):
        ...


@dataclass(slots=True)
class ModelArtifact:
    name: str
    version: str
    path: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelPrediction:
    model_name: str
    version: str
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelManager:
    """Versioned model registry for live and backtest parity."""

    def __init__(self, *, registry_path: str = "data/model_registry.json") -> None:
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, list[ModelArtifact]] = {}
        self._models: dict[tuple[str, str], Any] = {}
        self._load_registry()

    def register(self, name: str, version: str, model: Any, *, path: str, metadata: dict[str, Any] | None = None, created_at: str = "") -> ModelArtifact:
        artifact = ModelArtifact(
            name=str(name),
            version=str(version),
            path=str(path),
            created_at=str(created_at),
            metadata=dict(metadata or {}),
        )
        self._artifacts.setdefault(artifact.name, []).append(artifact)
        self._models[(artifact.name, artifact.version)] = model
        self._persist_registry()
        return artifact

    def latest(self, name: str) -> ModelArtifact | None:
        versions = self._artifacts.get(str(name), [])
        return versions[-1] if versions else None

    def get_model(self, name: str, version: str | None = None) -> Any | None:
        artifact = self.latest(name) if version is None else next((item for item in self._artifacts.get(str(name), []) if item.version == version), None)
        if artifact is None:
            return None
        return self._models.get((artifact.name, artifact.version))

    def predict(self, name: str, row: dict[str, float], *, version: str | None = None) -> ModelPrediction:
        artifact = self.latest(name) if version is None else next((item for item in self._artifacts.get(str(name), []) if item.version == version), None)
        if artifact is None:
            raise KeyError(f"Unknown model: {name}")
        model = self._models.get((artifact.name, artifact.version))
        if model is None:
            raise KeyError(f"Model instance not loaded: {artifact.name}:{artifact.version}")
        rows = [dict(row or {})]
        if hasattr(model, "predict_proba"):
            raw = model.predict_proba(rows)
            value = float(raw[0][-1] if isinstance(raw[0], (list, tuple)) else raw[0])
        else:
            raw = model.predict(rows)
            value = float(raw[0])
        return ModelPrediction(model_name=artifact.name, version=artifact.version, value=value, metadata=dict(artifact.metadata))

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            return
        records = json.loads(self.registry_path.read_text(encoding="utf-8") or "[]")
        for row in list(records or []):
            artifact = ModelArtifact(**dict(row))
            self._artifacts.setdefault(artifact.name, []).append(artifact)

    def _persist_registry(self) -> None:
        records = [asdict(artifact) for items in self._artifacts.values() for artifact in items]
        self.registry_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
