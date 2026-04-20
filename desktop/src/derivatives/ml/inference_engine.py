from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from derivatives.core.config import MLConfig


class DerivativesInferenceEngine:
    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or MLConfig()
        self.bundle: dict[str, Any] = {}
        self.feature_columns: list[str] = []

    @property
    def is_ready(self) -> bool:
        return bool(self.bundle.get("models"))

    def load(self, model_path: str | Path | None = None) -> "DerivativesInferenceEngine":
        payload = joblib.load(model_path or Path(self.config.model_dir) / "derivatives_model_bundle.joblib")
        self.bundle = dict(payload or {})
        self.feature_columns = list(self.bundle.get("feature_columns") or [])
        return self

    def score(self, features: dict[str, float]) -> dict[str, Any]:
        if not self.is_ready:
            return {
                "approved": False,
                "probability": 0.5,
                "confidence": 0.0,
                "regime": "unknown",
                "model_scores": {},
            }

        row = {column: float(features.get(column, 0.0)) for column in self.feature_columns}
        frame = pd.DataFrame([row], columns=self.feature_columns).fillna(0.0)
        models = dict(self.bundle.get("models") or {})
        scores: dict[str, float] = {}
        probabilities: list[float] = []
        regime = "unknown"

        for name, model in models.items():
            if name == "hmm":
                state = int(model.predict(frame[["return_1", "volatility"]])[0])
                regime = f"regime_{state}"
                continue
            probability = float(model.predict_proba(frame)[:, 1][0])
            scores[name] = probability
            probabilities.append(probability)

        probability = sum(probabilities) / len(probabilities) if probabilities else 0.5
        confidence = abs(probability - 0.5) * 2.0
        approved = probability >= float(self.config.inference_threshold)
        return {
            "approved": approved,
            "probability": probability,
            "confidence": confidence,
            "regime": regime,
            "model_scores": scores,
        }
