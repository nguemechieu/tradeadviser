from __future__ import annotations

"""
InvestPro ModelManager

Manages trained ML models for the InvestPro ML Research Lab.

Features:
- save/load joblib models
- safe filenames
- metadata sidecar files
- model package format
- latest model lookup
- model listing
- model deletion
- atomic writes
- feature column tracking
- scaler/config bundling
- lightweight model registry

Recommended model naming:
    BTC_USDT_1h_auto_sequence_seq8_20260425151319_05.joblib
"""

import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib


@dataclass(slots=True)
class ModelRecord:
    name: str
    path: str
    metadata_path: str
    created_at: str
    model_type: str = ""
    symbol: str = ""
    timeframe: str = ""
    family: str = ""
    horizon: int | None = None
    sequence_length: int | None = None
    score: float | None = None
    test_accuracy: float | None = None
    walk_forward_accuracy: float | None = None
    feature_count: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModelPackage:
    model: Any
    scaler: Any = None
    feature_columns: list[str] = field(default_factory=list)
    target_name: str = "target"
    config: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelManager:
    """Save, load, list, and manage trained InvestPro ML models."""

    DEFAULT_EXTENSION = ".joblib"

    def __init__(
        self,
        model_dir: str | os.PathLike[str] = "models/trained",
        *,
        metadata_extension: str = ".json",
        create_dir: bool = True,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.metadata_extension = str(metadata_extension or ".json")

        if create_dir:
            self.model_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Save / load
    # ------------------------------------------------------------------

    def save(
        self,
        model: Any,
        name: str,
        *,
        scaler: Any = None,
        feature_columns: list[str] | tuple[str, ...] | None = None,
        target_name: str = "target",
        config: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
        overwrite: bool = True,
        package: bool = True,
    ) -> ModelRecord:
        """Save a model.

        Args:
            model:
                Trained model object.
            name:
                Model filename or logical model name.
            scaler:
                Optional scaler/preprocessor.
            feature_columns:
                Ordered feature list used during training.
            target_name:
                Target column name.
            config:
                Training config.
            metrics:
                Training/test/walk-forward metrics.
            metadata:
                Extra model metadata.
            tags:
                Search tags.
            overwrite:
                Whether to overwrite an existing model file.
            package:
                If True, save ModelPackage instead of raw model.

        Returns:
            ModelRecord describing the saved model.
        """
        safe_name = self._safe_model_filename(name)
        model_path = self.model_dir / safe_name
        metadata_path = self._metadata_path_for(model_path)

        if model_path.exists() and not overwrite:
            raise FileExistsError(f"Model already exists: {model_path}")

        created_at = datetime.now(timezone.utc).isoformat()

        clean_feature_columns = [str(col)
                                 for col in list(feature_columns or [])]
        clean_config = self._json_safe(config or {})
        clean_metrics = self._json_safe(metrics or {})
        clean_metadata = self._json_safe(metadata or {})
        clean_tags = [str(tag).strip()
                      for tag in list(tags or []) if str(tag).strip()]

        payload: Any

        if package:
            payload = ModelPackage(
                model=model,
                scaler=scaler,
                feature_columns=clean_feature_columns,
                target_name=str(target_name or "target"),
                config=clean_config,
                metrics=clean_metrics,
                metadata=clean_metadata,
            )
        else:
            payload = model

        self._atomic_joblib_dump(payload, model_path)

        record = ModelRecord(
            name=model_path.name,
            path=str(model_path),
            metadata_path=str(metadata_path),
            created_at=created_at,
            model_type=self._model_type(model),
            symbol=str(clean_metadata.get("symbol")
                       or clean_config.get("symbol") or ""),
            timeframe=str(clean_metadata.get("timeframe")
                          or clean_config.get("timeframe") or ""),
            family=str(clean_metadata.get("family")
                       or clean_config.get("family") or ""),
            horizon=self._optional_int(clean_metadata.get(
                "horizon", clean_config.get("horizon"))),
            sequence_length=self._optional_int(
                clean_metadata.get("sequence_length",
                                   clean_config.get("sequence_length"))
            ),
            score=self._optional_float(clean_metrics.get(
                "score", clean_metrics.get("selection_score"))),
            test_accuracy=self._optional_float(
                clean_metrics.get("test_accuracy")),
            walk_forward_accuracy=self._optional_float(
                clean_metrics.get("walk_forward_accuracy")),
            feature_count=len(clean_feature_columns),
            tags=clean_tags,
            metadata={
                **clean_metadata,
                "config": clean_config,
                "metrics": clean_metrics,
                "target_name": str(target_name or "target"),
                "package": bool(package),
            },
        )

        self._atomic_json_dump(record.to_dict(), metadata_path)

        return record

    def load(
        self,
        name: str,
        *,
        return_package: bool = False,
        default: Any = None,
    ) -> Any:
        """Load a model by name.

        Args:
            name:
                Model filename or logical model name.
            return_package:
                If True, returns ModelPackage when available.
                If False, returns package.model when a package was saved.
            default:
                Returned when the model is missing.

        Returns:
            Model object, ModelPackage, or default.
        """
        model_path = self._resolve_model_path(name)

        if model_path is None or not model_path.exists():
            return default

        payload = joblib.load(model_path)

        if return_package:
            return payload

        if isinstance(payload, ModelPackage):
            return payload.model

        if isinstance(payload, dict) and "model" in payload:
            return payload.get("model")

        return payload

    def load_package(self, name: str, *, default: Any = None) -> Any:
        return self.load(name, return_package=True, default=default)

    def load_latest(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        family: str | None = None,
        return_package: bool = False,
        default: Any = None,
    ) -> Any:
        record = self.latest_record(
            symbol=symbol, timeframe=timeframe, family=family)

        if record is None:
            return default

        return self.load(record.name, return_package=return_package, default=default)

    # ------------------------------------------------------------------
    # Records / metadata
    # ------------------------------------------------------------------

    def get_record(self, name: str) -> ModelRecord | None:
        model_path = self._resolve_model_path(name)

        if model_path is None:
            return None

        metadata_path = self._metadata_path_for(model_path)

        if not metadata_path.exists():
            return self._record_from_file(model_path)

        try:
            with metadata_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return self._record_from_dict(data)
        except Exception:
            return self._record_from_file(model_path)

    def list_records(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        family: str | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
        limit: int | None = None,
        sort_by: str = "created_at",
        descending: bool = True,
    ) -> list[ModelRecord]:
        records = []

        for path in self.model_dir.glob(f"*{self.DEFAULT_EXTENSION}"):
            record = self.get_record(path.name)
            if record is not None:
                records.append(record)

        symbol_filter = str(symbol or "").strip().upper()
        timeframe_filter = str(timeframe or "").strip().lower()
        family_filter = str(family or "").strip().lower()
        tag_filter = {str(tag).strip().lower()
                      for tag in list(tags or []) if str(tag).strip()}

        if symbol_filter:
            records = [
                record
                for record in records
                if str(record.symbol or "").strip().upper() == symbol_filter
            ]

        if timeframe_filter:
            records = [
                record
                for record in records
                if str(record.timeframe or "").strip().lower() == timeframe_filter
            ]

        if family_filter:
            records = [
                record
                for record in records
                if str(record.family or "").strip().lower() == family_filter
            ]

        if tag_filter:
            records = [
                record
                for record in records
                if tag_filter.issubset({str(tag).strip().lower() for tag in record.tags})
            ]

        records.sort(
            key=lambda record: self._sort_value(record, sort_by),
            reverse=bool(descending),
        )

        if limit is not None:
            records = records[: max(0, int(limit))]

        return records

    def latest_record(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        family: str | None = None,
    ) -> ModelRecord | None:
        records = self.list_records(
            symbol=symbol,
            timeframe=timeframe,
            family=family,
            limit=1,
            sort_by="created_at",
            descending=True,
        )
        return records[0] if records else None

    def exists(self, name: str) -> bool:
        path = self._resolve_model_path(name)
        return bool(path is not None and path.exists())

    def delete(self, name: str) -> bool:
        path = self._resolve_model_path(name)

        if path is None or not path.exists():
            return False

        metadata_path = self._metadata_path_for(path)

        path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

        return True

    def prune(
        self,
        *,
        keep_latest: int = 10,
        symbol: str | None = None,
        timeframe: str | None = None,
        family: str | None = None,
    ) -> list[str]:
        """Delete older models after keeping the newest N."""
        keep = max(0, int(keep_latest))
        records = self.list_records(
            symbol=symbol,
            timeframe=timeframe,
            family=family,
            sort_by="created_at",
            descending=True,
        )

        deleted: list[str] = []

        for record in records[keep:]:
            if self.delete(record.name):
                deleted.append(record.name)

        return deleted

    # ------------------------------------------------------------------
    # Compatibility aliases
    # ------------------------------------------------------------------

    def save_model(self, model: Any, name: str, **kwargs: Any) -> ModelRecord:
        return self.save(model, name, **kwargs)

    def load_model(self, name: str, **kwargs: Any) -> Any:
        return self.load(name, **kwargs)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _safe_model_filename(self, name: str) -> str:
        text = str(name or "").strip()

        if not text:
            raise ValueError("Model name is required")

        text = text.replace("\\", "/").split("/")[-1]
        text = re.sub(r"[^A-Za-z0-9_.:\-]+", "_", text)
        text = text.strip("._ ")

        if not text:
            raise ValueError("Model name is invalid")

        if not text.endswith(self.DEFAULT_EXTENSION):
            text += self.DEFAULT_EXTENSION

        return text

    def _resolve_model_path(self, name: str) -> Path | None:
        safe_name = self._safe_model_filename(name)
        path = self.model_dir / safe_name

        if path.exists():
            return path

        # Allow caller to pass a name without extension already handled above.
        return path

    def _metadata_path_for(self, model_path: Path) -> Path:
        return model_path.with_suffix(model_path.suffix + self.metadata_extension)

    # ------------------------------------------------------------------
    # Atomic writes
    # ------------------------------------------------------------------

    def _atomic_joblib_dump(self, payload: Any, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

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
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _atomic_json_dump(self, payload: dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(self._json_safe(payload),
                      handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)

        try:
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Record helpers
    # ------------------------------------------------------------------

    def _record_from_file(self, path: Path) -> ModelRecord:
        stat = path.stat()
        created_at = datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc).isoformat()

        return ModelRecord(
            name=path.name,
            path=str(path),
            metadata_path=str(self._metadata_path_for(path)),
            created_at=created_at,
            model_type="unknown",
            metadata={},
        )

    def _record_from_dict(self, data: dict[str, Any]) -> ModelRecord:
        return ModelRecord(
            name=str(data.get("name") or ""),
            path=str(data.get("path") or ""),
            metadata_path=str(data.get("metadata_path") or ""),
            created_at=str(data.get("created_at") or ""),
            model_type=str(data.get("model_type") or ""),
            symbol=str(data.get("symbol") or ""),
            timeframe=str(data.get("timeframe") or ""),
            family=str(data.get("family") or ""),
            horizon=self._optional_int(data.get("horizon")),
            sequence_length=self._optional_int(data.get("sequence_length")),
            score=self._optional_float(data.get("score")),
            test_accuracy=self._optional_float(data.get("test_accuracy")),
            walk_forward_accuracy=self._optional_float(
                data.get("walk_forward_accuracy")),
            feature_count=int(data.get("feature_count") or 0),
            tags=[str(tag) for tag in list(data.get("tags") or [])],
            metadata=dict(data.get("metadata") or {}),
        )

    def _sort_value(self, record: ModelRecord, sort_by: str) -> Any:
        key = str(sort_by or "created_at")

        if key == "score":
            return record.score if record.score is not None else -float("inf")

        if key == "test_accuracy":
            return record.test_accuracy if record.test_accuracy is not None else -float("inf")

        if key == "walk_forward_accuracy":
            return record.walk_forward_accuracy if record.walk_forward_accuracy is not None else -float("inf")

        return getattr(record, key, record.created_at)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _model_type(self, model: Any) -> str:
        if model is None:
            return "none"
        return f"{model.__class__.__module__}.{model.__class__.__name__}"

    def _optional_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except Exception:
            return None
        if number != number or number in {float("inf"), float("-inf")}:
            return None
        return number

    def _optional_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except Exception:
            return None

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, (str, int, bool)):
            return value

        if isinstance(value, float):
            if value != value or value in {float("inf"), float("-inf")}:
                return None
            return value

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if is_dataclass(value):
            try:
                return self._json_safe(asdict(value))
            except Exception:
                pass

        if isinstance(value, dict):
            return {
                str(key): self._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._json_safe(item)
                for item in value
            ]

        return str(value)
