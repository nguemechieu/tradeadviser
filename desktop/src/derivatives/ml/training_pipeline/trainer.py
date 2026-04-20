from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from derivatives.core.config import MLConfig
from derivatives.ml.feature_engineering.features import FEATURE_COLUMNS, build_feature_frame

try:  # pragma: no cover - optional dependency
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional dependency
    XGBClassifier = None

try:  # pragma: no cover - optional dependency
    from hmmlearn.hmm import GaussianHMM
except Exception:  # pragma: no cover - optional dependency
    GaussianHMM = None


class DerivativesTrainingPipeline:
    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or MLConfig()

    def build_training_frame(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = build_feature_frame(data)
        horizon = max(1, int(self.config.training_label_horizon or 12))
        future_return = frame["close"].shift(-horizon) / frame["close"].replace(0.0, pd.NA) - 1.0
        frame["target"] = (future_return > 0).astype(float)
        frame["future_return"] = future_return.fillna(0.0)
        return frame.dropna(subset=["close"]).reset_index(drop=True)

    def train(self, data: pd.DataFrame, *, output_dir: str | Path | None = None) -> dict[str, Any]:
        frame = self.build_training_frame(data)
        if len(frame) < int(self.config.min_training_rows):
            raise ValueError(f"Not enough training rows for derivatives ML pipeline: {len(frame)}")

        X = frame[FEATURE_COLUMNS].fillna(0.0)
        y = frame["target"].astype(int)

        models: dict[str, Any] = {}
        metrics: dict[str, float] = {}

        if self.config.use_random_forest:
            forest = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)
            forest.fit(X, y)
            models["random_forest"] = forest
            metrics["random_forest_in_sample_accuracy"] = float(forest.score(X, y))

        if self.config.use_xgboost and XGBClassifier is not None:
            xgb = XGBClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="logloss",
                random_state=42,
            )
            xgb.fit(X, y)
            models["xgboost"] = xgb
            metrics["xgboost_in_sample_accuracy"] = float(xgb.score(X, y))

        if self.config.use_hmm and GaussianHMM is not None:
            hmm = GaussianHMM(n_components=3, covariance_type="diag", n_iter=200, random_state=42)
            hmm.fit(frame[["return_1", "volatility"]].fillna(0.0))
            models["hmm"] = hmm

        bundle = {
            "feature_columns": list(FEATURE_COLUMNS),
            "models": models,
            "metrics": metrics,
            "metadata": {
                "training_rows": int(len(frame)),
                "label_horizon": int(self.config.training_label_horizon),
            },
        }

        model_dir = Path(output_dir or self.config.model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, model_dir / "derivatives_model_bundle.joblib")
        return bundle
