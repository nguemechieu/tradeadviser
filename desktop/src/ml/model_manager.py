from __future__ import annotations

"""
InvestPro Model Registry

Versioned runtime registry for live, paper, research, and backtest model parity.

This manager is different from a simple artifact saver:
- It tracks model name/version/path metadata.
- It can register already-loaded model instances.
- It can lazy-load models from disk.
- It can predict using a specific model version or the latest version.
- It keeps live and backtest model selection consistent.

Recommended use:
    manager.register(...)
    prediction = manager.predict("PERP_USD_sequence", row)

Registry file:
    data/model_registry.json
"""

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol

import joblib


class PredictableModel(Protocol):
    def predict_proba(self, rows: Any) -> Any:
        ...

    def predict(self, rows: Any) -> Any:
        ...


@dataclass(slots=True)
class ModelArtifact:
    name: str
    version: str
    path: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        return self.name, self.version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModelPrediction:
    model_name: str
    version: str
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any = None

    @property
    def probability(self) -> float:
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "value": self.value,
            "probability": self.probability,
            "metadata": dict(self.metadata or {}),
            "raw": _json_safe(self.raw),
        }


@dataclass(slots=True)
class ModelPackage:
    model: Any
    feature_columns: list[str] = field(default_factory=list)
    scaler: Any = None
    threshold: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelManager:
    """Versioned model registry for live and backtest parity."""

    def __init__(
        self,
        *,
        registry_path: str | os.PathLike[str] = "data/model_registry.json",
        auto_load: bool = True,
        strict_features: bool = False,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self.auto_load = bool(auto_load)
        self.strict_features = bool(strict_features)

        self._artifacts: dict[str, list[ModelArtifact]] = {}
        self._models: dict[tuple[str, str], Any] = {}

        self._load_registry()

    # ------------------------------------------------------------------
    # Register / unregister
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        version: str,
        model: Any = None,
        *,
        path: str,
        metadata: dict[str, Any] | None = None,
        created_at: str = "",
        replace: bool = True,
        persist: bool = True,
    ) -> ModelArtifact:
        """Register a model artifact and optionally a live model instance."""
        artifact = ModelArtifact(
            name=self._clean_name(name),
            version=self._clean_version(version),
            path=str(path),
            created_at=str(created_at or datetime.now(
                timezone.utc).isoformat()),
            metadata=_json_safe(dict(metadata or {})),
        )

        versions = self._artifacts.setdefault(artifact.name, [])

        existing_index = next(
            (
                index
                for index, item in enumerate(versions)
                if item.version == artifact.version
            ),
            None,
        )

        if existing_index is not None:
            if not replace:
                raise ValueError(
                    f"Model artifact already registered: {artifact.name}:{artifact.version}")
            versions[existing_index] = artifact
        else:
            versions.append(artifact)

        versions.sort(key=self._artifact_sort_key)

        if model is not None:
            self._models[artifact.key] = model

        if persist:
            self._persist_registry()

        return artifact

    def unregister(self, name: str, version: str | None = None, *, persist: bool = True) -> bool:
        clean_name = self._clean_name(name)

        if clean_name not in self._artifacts:
            return False

        if version is None:
            removed = bool(self._artifacts.pop(clean_name, None))
            for key in list(self._models):
                if key[0] == clean_name:
                    self._models.pop(key, None)
        else:
            clean_version = self._clean_version(version)
            before = len(self._artifacts.get(clean_name, []))
            self._artifacts[clean_name] = [
                artifact
                for artifact in self._artifacts.get(clean_name, [])
                if artifact.version != clean_version
            ]
            self._models.pop((clean_name, clean_version), None)
            removed = len(self._artifacts.get(clean_name, [])) != before

            if not self._artifacts.get(clean_name):
                self._artifacts.pop(clean_name, None)

        if removed and persist:
            self._persist_registry()

        return removed

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def latest(self, name: str) -> ModelArtifact | None:
        versions = self._artifacts.get(self._clean_name(name), [])
        return versions[-1] if versions else None

    def artifact(self, name: str, version: str | None = None) -> ModelArtifact | None:
        clean_name = self._clean_name(name)

        if version is None:
            return self.latest(clean_name)

        clean_version = self._clean_version(version)

        return next(
            (
                item
                for item in self._artifacts.get(clean_name, [])
                if item.version == clean_version
            ),
            None,
        )

    def list_artifacts(self, name: str | None = None) -> list[ModelArtifact]:
        if name is not None:
            return list(self._artifacts.get(self._clean_name(name), []))

        output: list[ModelArtifact] = []
        for versions in self._artifacts.values():
            output.extend(versions)

        output.sort(key=self._artifact_sort_key)
        return output

    def get_model(
        self,
        name: str,
        version: str | None = None,
        *,
        load_if_missing: bool | None = None,
    ) -> Any | None:
        artifact = self.artifact(name, version)

        if artifact is None:
            return None

        key = artifact.key

        if key in self._models:
            return self._models[key]

        should_load = self.auto_load if load_if_missing is None else bool(
            load_if_missing)

        if not should_load:
            return None

        model = self._load_model_from_artifact(artifact)
        if model is not None:
            self._models[key] = model

        return model

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        name: str,
        row: Mapping[str, Any] | list[Any] | tuple[Any, ...],
        *,
        version: str | None = None,
        positive_class_index: int = -1,
        use_threshold: bool = False,
    ) -> ModelPrediction:
        artifact = self.artifact(name, version)

        if artifact is None:
            raise KeyError(f"Unknown model: {name}")

        model_or_package = self.get_model(artifact.name, artifact.version)

        if model_or_package is None:
            raise KeyError(
                f"Model instance not loaded: {artifact.name}:{artifact.version}")

        model, package_metadata = self._unwrap_model(model_or_package)
        rows = self._prepare_rows(row, model_or_package)

        raw: Any

        if hasattr(model, "predict_proba"):
            raw = model.predict_proba(rows)
            value = self._extract_probability(
                raw, positive_class_index=positive_class_index)
        elif hasattr(model, "predict"):
            raw = model.predict(rows)
            value = self._extract_prediction_value(raw)
        else:
            raise TypeError(
                f"Model is not predictable: {artifact.name}:{artifact.version}")

        metadata = {
            **dict(artifact.metadata or {}),
            **dict(package_metadata or {}),
            "path": artifact.path,
            "created_at": artifact.created_at,
        }

        if use_threshold:
            threshold = self._safe_float(metadata.get("threshold"), 0.5)
            metadata["threshold"] = threshold
            metadata["class_prediction"] = int(value >= threshold)

        return ModelPrediction(
            model_name=artifact.name,
            version=artifact.version,
            value=float(value),
            metadata=metadata,
            raw=raw,
        )

    def predict_batch(
        self,
        name: str,
        rows: list[Mapping[str, Any]] | list[list[Any]],
        *,
        version: str | None = None,
        positive_class_index: int = -1,
    ) -> list[ModelPrediction]:
        artifact = self.artifact(name, version)

        if artifact is None:
            raise KeyError(f"Unknown model: {name}")

        model_or_package = self.get_model(artifact.name, artifact.version)

        if model_or_package is None:
            raise KeyError(
                f"Model instance not loaded: {artifact.name}:{artifact.version}")

        model, package_metadata = self._unwrap_model(model_or_package)
        prepared_rows = self._prepare_batch_rows(rows, model_or_package)

        if hasattr(model, "predict_proba"):
            raw = model.predict_proba(prepared_rows)
            values = self._extract_probability_list(
                raw, positive_class_index=positive_class_index)
        elif hasattr(model, "predict"):
            raw = model.predict(prepared_rows)
            values = [float(item) for item in list(raw)]
        else:
            raise TypeError(
                f"Model is not predictable: {artifact.name}:{artifact.version}")

        metadata = {
            **dict(artifact.metadata or {}),
            **dict(package_metadata or {}),
            "path": artifact.path,
            "created_at": artifact.created_at,
        }

        return [
            ModelPrediction(
                model_name=artifact.name,
                version=artifact.version,
                value=float(value),
                metadata=dict(metadata),
                raw=None,
            )
            for value in values
        ]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            return

        try:
            records = json.loads(
                self.registry_path.read_text(encoding="utf-8") or "[]")
        except Exception:
            records = []

        for row in list(records or []):
            if not isinstance(row, dict):
                continue

            try:
                artifact = ModelArtifact(
                    name=self._clean_name(row.get("name")),
                    version=self._clean_version(row.get("version")),
                    path=str(row.get("path") or ""),
                    created_at=str(row.get("created_at") or ""),
                    metadata=dict(row.get("metadata") or {}),
                )
            except Exception:
                continue

            self._artifacts.setdefault(artifact.name, []).append(artifact)

        for versions in self._artifacts.values():
            versions.sort(key=self._artifact_sort_key)

    def _persist_registry(self) -> None:
        records = [
            artifact.to_dict()
            for name in sorted(self._artifacts)
            for artifact in self._artifacts[name]
        ]

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.registry_path.parent),
            prefix=f".{self.registry_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(_json_safe(records), handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)

        try:
            os.replace(temp_path, self.registry_path)
        finally:
            temp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Save artifact helper
    # ------------------------------------------------------------------

    def save_and_register(
        self,
        name: str,
        version: str,
        model: Any,
        *,
        path: str,
        metadata: dict[str, Any] | None = None,
        feature_columns: list[str] | None = None,
        scaler: Any = None,
        threshold: float = 0.5,
        package: bool = True,
    ) -> ModelArtifact:
        """Save a model to disk and register it in the runtime registry."""
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if package:
            payload = ModelPackage(
                model=model,
                feature_columns=list(feature_columns or []),
                scaler=scaler,
                threshold=float(threshold),
                metadata=dict(metadata or {}),
            )
        else:
            payload = model

        self._atomic_joblib_dump(payload, target_path)

        merged_metadata = dict(metadata or {})
        if feature_columns:
            merged_metadata["feature_columns"] = list(feature_columns)
        if threshold is not None:
            merged_metadata["threshold"] = float(threshold)

        return self.register(
            name=name,
            version=version,
            model=payload,
            path=str(target_path),
            metadata=merged_metadata,
            replace=True,
            persist=True,
        )

    def _atomic_joblib_dump(self, payload: Any, path: Path) -> None:
        with tempfile.NamedTemporaryFile(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        try:
            joblib.dump(payload, temp_path)
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Model loading / unwrapping
    # ------------------------------------------------------------------

    def _load_model_from_artifact(self, artifact: ModelArtifact) -> Any | None:
        path = Path(artifact.path)

        if not path.exists():
            return None

        return joblib.load(path)

    def _unwrap_model(self, value: Any) -> tuple[Any, dict[str, Any]]:
        if isinstance(value, ModelPackage):
            metadata = {
                **dict(value.metadata or {}),
                "feature_columns": list(value.feature_columns or []),
                "threshold": value.threshold,
            }
            return value.model, metadata

        if isinstance(value, dict) and "model" in value:
            metadata = dict(value.get("metadata") or {})
            if "feature_columns" in value:
                metadata["feature_columns"] = list(
                    value.get("feature_columns") or [])
            if "threshold" in value:
                metadata["threshold"] = value.get("threshold")
            return value["model"], metadata

        return value, {}

    # ------------------------------------------------------------------
    # Row preparation
    # ------------------------------------------------------------------

    def _prepare_rows(self, row: Mapping[str, Any] | list[Any] | tuple[Any, ...], model_or_package: Any) -> list[Any]:
        return self._prepare_batch_rows([row], model_or_package)

    def _prepare_batch_rows(self, rows: list[Any], model_or_package: Any) -> list[Any]:
        feature_columns = self._feature_columns(model_or_package)

        prepared: list[Any] = []

        for row in list(rows or []):
            if isinstance(row, Mapping):
                if feature_columns:
                    missing = [
                        column for column in feature_columns if column not in row]
                    if missing and self.strict_features:
                        raise ValueError(f"Missing feature columns: {missing}")
                    prepared.append([self._safe_float(row.get(column), 0.0)
                                    for column in feature_columns])
                else:
                    prepared.append(dict(row))
            else:
                prepared.append(list(row))

        scaler = self._scaler(model_or_package)
        if scaler is not None:
            try:
                return scaler.transform(prepared)
            except Exception:
                # Let the raw prepared rows continue; some scalers are not compatible.
                return prepared

        return prepared

    def _feature_columns(self, model_or_package: Any) -> list[str]:
        if isinstance(model_or_package, ModelPackage):
            return list(model_or_package.feature_columns or [])

        if isinstance(model_or_package, dict):
            return list(model_or_package.get("feature_columns") or [])

        return list(getattr(model_or_package, "feature_columns", []) or [])

    def _scaler(self, model_or_package: Any) -> Any:
        if isinstance(model_or_package, ModelPackage):
            return model_or_package.scaler

        if isinstance(model_or_package, dict):
            return model_or_package.get("scaler")

        return getattr(model_or_package, "scaler", None)

    # ------------------------------------------------------------------
    # Prediction extraction
    # ------------------------------------------------------------------

    def _extract_probability(self, raw: Any, *, positive_class_index: int = -1) -> float:
        if hasattr(raw, "tolist"):
            raw = raw.tolist()

        first = raw[0] if isinstance(raw, (list, tuple)) and raw else raw

        if hasattr(first, "tolist"):
            first = first.tolist()

        if isinstance(first, (list, tuple)):
            if not first:
                return 0.0
            return self._safe_float(first[positive_class_index], 0.0)

        return self._safe_float(first, 0.0)

    def _extract_probability_list(self, raw: Any, *, positive_class_index: int = -1) -> list[float]:
        if hasattr(raw, "tolist"):
            raw = raw.tolist()

        values: list[float] = []

        for item in list(raw or []):
            if hasattr(item, "tolist"):
                item = item.tolist()

            if isinstance(item, (list, tuple)):
                values.append(self._safe_float(
                    item[positive_class_index], 0.0) if item else 0.0)
            else:
                values.append(self._safe_float(item, 0.0))

        return values

    def _extract_prediction_value(self, raw: Any) -> float:
        if hasattr(raw, "tolist"):
            raw = raw.tolist()

        if isinstance(raw, (list, tuple)):
            if not raw:
                return 0.0
            return self._safe_float(raw[0], 0.0)

        return self._safe_float(raw, 0.0)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "registry_path": str(self.registry_path),
            "artifact_count": sum(len(items) for items in self._artifacts.values()),
            "loaded_model_count": len(self._models),
            "models": {
                name: [artifact.to_dict() for artifact in versions]
                for name, versions in self._artifacts.items()
            },
            "auto_load": self.auto_load,
            "strict_features": self.strict_features,
        }

    def healthy(self) -> bool:
        return self.registry_path.parent.exists()

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    def _clean_name(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Model name is required")
        return text

    def _clean_version(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Model version is required")
        return text

    def _artifact_sort_key(self, artifact: ModelArtifact) -> tuple[str, str]:
        return artifact.created_at or "", artifact.version

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return float(default)

        try:
            number = float(value)
        except Exception:
            return float(default)

        if not math.isfinite(number):
            return float(default)

        return number
