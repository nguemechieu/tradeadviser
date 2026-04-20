from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backtesting.experiment_tracker import ExperimentTracker
from quant.ml_dataset import MLDataset, MLDatasetBuilder
from quant.ml_models import LinearSignalClassifier, SequenceLinearClassifier, TreeThresholdEnsembleClassifier
from quant.model_registry import ModelRegistry


@dataclass
class MLResearchResult:
    model_name: str
    model: object
    metrics: dict = field(default_factory=dict)
    dataset_metadata: dict = field(default_factory=dict)
    experiment_id: str | None = None


@dataclass
class MLAutoResearchCandidate:
    model_name: str
    model_family: str
    sequence_length: int
    result: MLResearchResult
    walk_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    walk_predictions: pd.DataFrame = field(default_factory=pd.DataFrame)
    selection_score: float = 0.0
    selection_metrics: dict = field(default_factory=dict)


@dataclass
class MLAutoResearchSummary:
    best_candidate: MLAutoResearchCandidate | None = None
    candidates: list[MLAutoResearchCandidate] = field(default_factory=list)
    leaderboard: pd.DataFrame = field(default_factory=pd.DataFrame)


class MLResearchPipeline:
    VERSION = "ml-research-v1"

    def __init__(self, model_registry=None, experiment_tracker=None, dataset_builder=None):
        self.model_registry = model_registry or ModelRegistry()
        self.experiment_tracker = experiment_tracker or ExperimentTracker()
        self.dataset_builder = dataset_builder or MLDatasetBuilder()

    def build_dataset(self, candles, **kwargs):
        return self.dataset_builder.build_from_candles(candles, **kwargs)

    def _build_model(self, model_family="linear", sequence_length=4):
        family = str(model_family or "linear").strip().lower()
        if family in {"linear", "logistic"}:
            return LinearSignalClassifier(model_name="linear_signal_classifier"), "linear"
        if family in {"tree", "tree_ensemble", "stump_ensemble"}:
            return TreeThresholdEnsembleClassifier(model_name="tree_threshold_ensemble"), "tree"
        if family in {"sequence", "sequence_linear", "temporal"}:
            return SequenceLinearClassifier(sequence_length=max(2, int(sequence_length or 4)), model_name="sequence_linear_classifier"), "sequence"
        raise ValueError(f"Unsupported model family: {model_family}")

    def _classification_metrics(self, actual, predicted, probabilities):
        actual = np.asarray(actual, dtype=int)
        predicted = np.asarray(predicted, dtype=int)
        probabilities = np.asarray(probabilities, dtype=float).reshape(-1)
        if len(actual) == 0:
            return {
                "samples": 0,
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "positive_rate": 0.0,
                "avg_confidence": 0.0,
            }

        accuracy = float((actual == predicted).mean())
        predicted_positive = predicted == 1
        actual_positive = actual == 1
        tp = int(np.logical_and(predicted_positive, actual_positive).sum())
        fp = int(np.logical_and(predicted_positive, ~actual_positive).sum())
        fn = int(np.logical_and(~predicted_positive, actual_positive).sum())
        precision = float(tp / max(1, tp + fp))
        recall = float(tp / max(1, tp + fn))
        return {
            "samples": int(len(actual)),
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "positive_rate": float(actual_positive.mean()),
            "avg_confidence": float(np.mean(np.maximum(probabilities, 1.0 - probabilities))),
        }

    def _walk_forward_metrics(self, walk_summary):
        frame = walk_summary if isinstance(walk_summary, pd.DataFrame) else pd.DataFrame()
        if frame.empty:
            return {
                "walk_forward_windows": 0,
                "walk_forward_accuracy": 0.0,
                "walk_forward_precision": 0.0,
                "walk_forward_recall": 0.0,
                "walk_forward_avg_confidence": 0.0,
            }

        return {
            "walk_forward_windows": int(len(frame)),
            "walk_forward_accuracy": float(frame["accuracy"].mean()) if "accuracy" in frame.columns else 0.0,
            "walk_forward_precision": float(frame["precision"].mean()) if "precision" in frame.columns else 0.0,
            "walk_forward_recall": float(frame["recall"].mean()) if "recall" in frame.columns else 0.0,
            "walk_forward_avg_confidence": float(frame["avg_confidence"].mean()) if "avg_confidence" in frame.columns else 0.0,
        }

    def _candidate_selection_metrics(self, result, walk_summary):
        training_metrics = dict(getattr(result, "metrics", {}) or {})
        walk_metrics = self._walk_forward_metrics(walk_summary)
        selection_score = (
            (walk_metrics["walk_forward_accuracy"] * 0.32)
            + (walk_metrics["walk_forward_precision"] * 0.20)
            + (walk_metrics["walk_forward_recall"] * 0.08)
            + (float(training_metrics.get("test_accuracy", 0.0) or 0.0) * 0.22)
            + (float(training_metrics.get("test_precision", 0.0) or 0.0) * 0.12)
            + (float(training_metrics.get("avg_test_confidence", 0.0) or 0.0) * 0.06)
        )
        return {
            "selection_score": float(selection_score),
            "test_accuracy": float(training_metrics.get("test_accuracy", 0.0) or 0.0),
            "test_precision": float(training_metrics.get("test_precision", 0.0) or 0.0),
            "test_recall": float(training_metrics.get("test_recall", 0.0) or 0.0),
            "avg_test_confidence": float(training_metrics.get("avg_test_confidence", 0.0) or 0.0),
            **walk_metrics,
        }

    def _candidate_leaderboard_frame(self, candidates):
        rows = []
        for candidate in list(candidates or []):
            metrics = dict(getattr(candidate, "selection_metrics", {}) or {})
            rows.append(
                {
                    "model_name": candidate.model_name,
                    "model_family": candidate.model_family,
                    "sequence_length": int(candidate.sequence_length or 1),
                    **metrics,
                }
            )
        leaderboard = pd.DataFrame(rows)
        if leaderboard.empty:
            return leaderboard
        sort_columns = [
            "selection_score",
            "walk_forward_accuracy",
            "test_accuracy",
            "walk_forward_precision",
            "test_precision",
        ]
        available_columns = [column for column in sort_columns if column in leaderboard.columns]
        if available_columns:
            leaderboard = leaderboard.sort_values(available_columns, ascending=False).reset_index(drop=True)
        return leaderboard

    def _auto_research_sequence_lengths(self, sequence_length=4, candidate_sequence_lengths=None):
        if candidate_sequence_lengths is not None:
            lengths = []
            for value in list(candidate_sequence_lengths or []):
                try:
                    numeric = max(2, int(value))
                except (TypeError, ValueError):
                    continue
                if numeric not in lengths:
                    lengths.append(numeric)
            return lengths or [max(2, int(sequence_length or 4))]

        base = max(2, int(sequence_length or 4))
        lengths = []
        for value in (max(2, base - 1), base, min(12, base + 2)):
            if value not in lengths:
                lengths.append(value)
        return lengths

    def train_classifier(
        self,
        dataset: MLDataset,
        model_name="ml_model_v1",
        model_family="linear",
        sequence_length=4,
        test_size=0.25,
        experiment_name="ml_research",
        notes="",
    ):
        if dataset is None or dataset.empty:
            raise ValueError("Dataset is empty; unable to train ML classifier")

        model, normalized_family = self._build_model(model_family=model_family, sequence_length=sequence_length)
        working_dataset = dataset.to_sequence_dataset(sequence_length=sequence_length) if normalized_family == "sequence" else dataset
        train_frame, test_frame = working_dataset.train_test_split(test_size=test_size)
        if train_frame.empty or test_frame.empty:
            raise ValueError("Dataset split produced an empty train or test window")

        feature_columns = list(working_dataset.feature_columns)
        x_train = train_frame[feature_columns].to_numpy(dtype=float)
        y_train = train_frame[working_dataset.target_column].to_numpy(dtype=int)
        x_test = test_frame[feature_columns].to_numpy(dtype=float)
        y_test = test_frame[working_dataset.target_column].to_numpy(dtype=int)

        model.model_name = str(model_name or "ml_model_v1")
        model.fit(x_train, y_train, feature_names=feature_columns)
        train_prob = model.predict_proba(x_train)[:, 1]
        test_prob = model.predict_proba(x_test)[:, 1]
        train_pred = (train_prob >= 0.5).astype(int)
        test_pred = (test_prob >= 0.5).astype(int)

        metrics = {
            "version": self.VERSION,
            "train_accuracy": self._classification_metrics(y_train, train_pred, train_prob)["accuracy"],
            "test_accuracy": self._classification_metrics(y_test, test_pred, test_prob)["accuracy"],
            "test_precision": self._classification_metrics(y_test, test_pred, test_prob)["precision"],
            "test_recall": self._classification_metrics(y_test, test_pred, test_prob)["recall"],
            "avg_test_confidence": self._classification_metrics(y_test, test_pred, test_prob)["avg_confidence"],
            "train_samples": int(len(train_frame)),
            "test_samples": int(len(test_frame)),
        }
        metadata = {
            "dataset": dict(working_dataset.metadata or {}),
            "feature_columns": feature_columns,
            "model_family": normalized_family,
        }
        self.model_registry.register(model_name, model, metadata={**metadata, **metrics})
        record = self.experiment_tracker.add_record(
            name=experiment_name,
            strategy_name="ML Model",
            symbol=str((working_dataset.metadata or {}).get("symbol") or "BACKTEST"),
            timeframe=str((working_dataset.metadata or {}).get("timeframe") or "1h"),
            parameters={
                "model_name": model_name,
                "model_family": normalized_family,
                "test_size": test_size,
                "feature_count": len(feature_columns),
                "sequence_length": sequence_length if normalized_family == "sequence" else 1,
            },
            dataset_metadata=dict(working_dataset.metadata or {}),
            metrics=dict(metrics),
            notes=str(notes or "").strip(),
        )
        return MLResearchResult(
            model_name=str(model_name),
            model=model,
            metrics=metrics,
            dataset_metadata=metadata,
            experiment_id=record.experiment_id,
        )

    def run_walk_forward(
        self,
        dataset: MLDataset,
        model_family="linear",
        sequence_length=4,
        train_size=80,
        test_size=30,
        step_size=None,
    ):
        if dataset is None or dataset.empty:
            return pd.DataFrame(), pd.DataFrame()

        model_template, normalized_family = self._build_model(model_family=model_family, sequence_length=sequence_length)
        working_dataset = dataset.to_sequence_dataset(sequence_length=sequence_length) if normalized_family == "sequence" else dataset
        frame = working_dataset.frame.reset_index(drop=True)
        feature_columns = list(working_dataset.feature_columns)
        target_column = working_dataset.target_column
        if frame.empty or len(frame) < max(3, int(train_size) + int(test_size)):
            return pd.DataFrame(), pd.DataFrame()

        train_size = max(8, int(train_size))
        test_size = max(4, int(test_size))
        step = max(1, int(step_size or test_size))
        summary_rows = []
        prediction_rows = []

        for window_index, train_start in enumerate(range(0, len(frame) - train_size - test_size + 1, step)):
            train_end = train_start + train_size
            test_end = train_end + test_size
            train_frame = frame.iloc[train_start:train_end].copy()
            test_frame = frame.iloc[train_end:test_end].copy()
            if train_frame.empty or test_frame.empty:
                continue

            model, _ = self._build_model(model_family=normalized_family, sequence_length=sequence_length)
            model.model_name = getattr(model_template, "model_name", "ml_model")
            x_train = train_frame[feature_columns].to_numpy(dtype=float)
            y_train = train_frame[target_column].to_numpy(dtype=int)
            x_test = test_frame[feature_columns].to_numpy(dtype=float)
            y_test = test_frame[target_column].to_numpy(dtype=int)
            model.fit(x_train, y_train, feature_names=feature_columns)
            test_prob = model.predict_proba(x_test)[:, 1]
            test_pred = (test_prob >= 0.5).astype(int)
            metrics = self._classification_metrics(y_test, test_pred, test_prob)
            summary_rows.append(
                {
                    "window_index": window_index,
                    "train_rows": len(train_frame),
                    "test_rows": len(test_frame),
                    "train_start": train_frame.iloc[0].get("timestamp"),
                    "train_end": train_frame.iloc[-1].get("timestamp"),
                    "test_start": test_frame.iloc[0].get("timestamp"),
                    "test_end": test_frame.iloc[-1].get("timestamp"),
                    "accuracy": metrics["accuracy"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "avg_confidence": metrics["avg_confidence"],
                    "model_family": normalized_family,
                }
            )
            for row_idx, probability in enumerate(test_prob):
                prediction_rows.append(
                    {
                        "window_index": window_index,
                        "timestamp": test_frame.iloc[row_idx].get("timestamp"),
                        "actual": int(y_test[row_idx]),
                        "predicted": int(test_pred[row_idx]),
                        "probability": float(probability),
                        "regime": test_frame.iloc[row_idx].get("regime"),
                    }
                )

        summary_df = pd.DataFrame(summary_rows)
        prediction_df = pd.DataFrame(prediction_rows)
        if not summary_df.empty:
            metrics = {
                "walk_forward_windows": int(len(summary_df)),
                "walk_forward_accuracy": float(summary_df["accuracy"].mean()),
                "walk_forward_precision": float(summary_df["precision"].mean()),
                "walk_forward_recall": float(summary_df["recall"].mean()),
            }
            self.experiment_tracker.add_record(
                name=f"walk-forward-{normalized_family}",
                strategy_name="ML Model",
                symbol=str((working_dataset.metadata or {}).get("symbol") or "BACKTEST"),
                timeframe=str((working_dataset.metadata or {}).get("timeframe") or "1h"),
                parameters={
                    "model_family": normalized_family,
                    "train_size": train_size,
                    "test_size": test_size,
                    "step_size": step,
                    "sequence_length": sequence_length if normalized_family == "sequence" else 1,
                },
                dataset_metadata=dict(working_dataset.metadata or {}),
                metrics=metrics,
                notes="ml_walk_forward",
            )
        return summary_df, prediction_df

    def deploy_to_strategy_registry(self, strategy_registry, model_name, strategy_name="ML Model"):
        from strategy.strategy import Strategy

        model = self.model_registry.get(model_name)
        if model is None:
            raise KeyError(f"Model '{model_name}' is not registered")

        deployed_strategy = Strategy(model=model, strategy_name=strategy_name)
        strategy_registry.register(strategy_name, deployed_strategy)
        if hasattr(strategy_registry, "set_active"):
            strategy_registry.set_active(strategy_name)
        return deployed_strategy

    def auto_research(
        self,
        dataset: MLDataset,
        model_families=None,
        sequence_length=4,
        test_size=0.25,
        train_size=80,
        test_window=30,
        step_size=None,
        model_name_prefix="ml_auto_research",
        experiment_name="ml_auto_research",
        notes="",
        candidate_sequence_lengths=None,
    ):
        if dataset is None or dataset.empty:
            raise ValueError("Dataset is empty; unable to run auto research")

        families = []
        for family in list(model_families or ["linear", "tree", "sequence"]):
            normalized = str(family or "").strip().lower()
            if normalized and normalized not in families:
                families.append(normalized)
        if not families:
            raise ValueError("At least one model family is required for auto research")

        sequence_lengths = self._auto_research_sequence_lengths(
            sequence_length=sequence_length,
            candidate_sequence_lengths=candidate_sequence_lengths,
        )
        timestamp_suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        prefix = str(model_name_prefix or "ml_auto_research").strip() or "ml_auto_research"
        candidates = []
        candidate_index = 0

        for family in families:
            family_sequence_lengths = sequence_lengths if family == "sequence" else [1]
            for candidate_sequence_length in family_sequence_lengths:
                candidate_index += 1
                model_name = f"{prefix}_{family}"
                if family == "sequence":
                    model_name += f"_seq{int(candidate_sequence_length)}"
                model_name += f"_{timestamp_suffix}_{candidate_index:02d}"

                result = self.train_classifier(
                    dataset,
                    model_name=model_name,
                    model_family=family,
                    sequence_length=int(candidate_sequence_length),
                    test_size=test_size,
                    experiment_name=experiment_name,
                    notes=notes or "auto_research_training",
                )
                walk_summary, walk_predictions = self.run_walk_forward(
                    dataset,
                    model_family=family,
                    sequence_length=int(candidate_sequence_length),
                    train_size=train_size,
                    test_size=test_window,
                    step_size=step_size,
                )
                selection_metrics = self._candidate_selection_metrics(result, walk_summary)
                candidates.append(
                    MLAutoResearchCandidate(
                        model_name=model_name,
                        model_family=family,
                        sequence_length=int(candidate_sequence_length),
                        result=result,
                        walk_summary=walk_summary,
                        walk_predictions=walk_predictions,
                        selection_score=float(selection_metrics.get("selection_score", 0.0) or 0.0),
                        selection_metrics=selection_metrics,
                    )
                )

        leaderboard = self._candidate_leaderboard_frame(candidates)
        best_candidate = None
        if not leaderboard.empty:
            best_model_name = str(leaderboard.iloc[0].get("model_name") or "").strip()
            for candidate in candidates:
                if candidate.model_name == best_model_name:
                    best_candidate = candidate
                    break

        return MLAutoResearchSummary(
            best_candidate=best_candidate,
            candidates=candidates,
            leaderboard=leaderboard,
        )
