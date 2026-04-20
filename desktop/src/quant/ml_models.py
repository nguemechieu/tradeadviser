from dataclasses import dataclass, field

import numpy as np


def _sigmoid(values):
    clipped = np.clip(values, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


@dataclass
class LinearSignalClassifier:
    learning_rate: float = 0.05
    iterations: int = 600
    l2_penalty: float = 0.001
    random_state: int = 7
    feature_names_: list[str] = field(default_factory=list)
    class_labels_: tuple[int, int] = (0, 1)
    coef_: np.ndarray | None = None
    intercept_: float = 0.0
    mean_: np.ndarray | None = None
    scale_: np.ndarray | None = None
    trained_: bool = False
    model_name: str = "linear_signal_classifier"

    def _prepare(self, features):
        matrix = np.asarray(features, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return matrix

    def fit(self, features, labels, feature_names=None):
        x = self._prepare(features)
        y = np.asarray(labels, dtype=float).reshape(-1)
        if len(x) != len(y):
            raise ValueError("Feature and label lengths must match")
        if len(x) < 8:
            raise ValueError("At least 8 samples are required to train the ML classifier")

        self.feature_names_ = [str(name) for name in (feature_names or [])] or [f"f{i}" for i in range(x.shape[1])]
        self.mean_ = x.mean(axis=0)
        self.scale_ = x.std(axis=0)
        self.scale_[self.scale_ == 0] = 1.0
        x_scaled = (x - self.mean_) / self.scale_

        rng = np.random.default_rng(self.random_state)
        weights = rng.normal(0.0, 0.05, size=x.shape[1])
        bias = 0.0
        sample_count = max(1, len(x_scaled))

        for _ in range(int(self.iterations)):
            logits = np.dot(x_scaled, weights) + bias
            predictions = _sigmoid(logits)
            errors = predictions - y
            grad_w = (np.dot(x_scaled.T, errors) / sample_count) + (self.l2_penalty * weights)
            grad_b = float(errors.mean())
            weights -= self.learning_rate * grad_w
            bias -= self.learning_rate * grad_b

        self.coef_ = weights
        self.intercept_ = float(bias)
        self.trained_ = True
        return self

    def predict_proba(self, features):
        if not self.trained_ or self.coef_ is None or self.mean_ is None or self.scale_ is None:
            raise RuntimeError("Model must be trained before predict_proba()")
        x = self._prepare(features)
        x_scaled = (x - self.mean_) / self.scale_
        logits = np.dot(x_scaled, self.coef_) + self.intercept_
        positive = _sigmoid(logits)
        negative = 1.0 - positive
        return np.column_stack([negative, positive])

    def predict(self, features):
        probabilities = self.predict_proba(features)
        return (probabilities[:, 1] >= 0.5).astype(int)


@dataclass
class TreeThresholdEnsembleClassifier:
    max_splits_per_feature: int = 4
    feature_names_: list[str] = field(default_factory=list)
    trees_: list[dict] = field(default_factory=list)
    trained_: bool = False
    model_name: str = "tree_threshold_ensemble"

    def _prepare(self, features):
        matrix = np.asarray(features, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return matrix

    def fit(self, features, labels, feature_names=None):
        x = self._prepare(features)
        y = np.asarray(labels, dtype=int).reshape(-1)
        if len(x) != len(y):
            raise ValueError("Feature and label lengths must match")
        if len(x) < 8:
            raise ValueError("At least 8 samples are required to train the tree ensemble")

        self.feature_names_ = [str(name) for name in (feature_names or [])] or [f"f{i}" for i in range(x.shape[1])]
        trees = []
        for feature_index in range(x.shape[1]):
            column = x[:, feature_index]
            thresholds = np.quantile(column, np.linspace(0.2, 0.8, num=max(2, self.max_splits_per_feature)))
            best = None
            for threshold in thresholds:
                for polarity in (1.0, -1.0):
                    predictions = ((column >= threshold).astype(int) if polarity > 0 else (column < threshold).astype(int))
                    accuracy = float((predictions == y).mean())
                    if best is None or accuracy > best["accuracy"]:
                        best = {
                            "feature_index": feature_index,
                            "threshold": float(threshold),
                            "polarity": polarity,
                            "accuracy": accuracy,
                        }
            if best is not None and best["accuracy"] > 0.5:
                trees.append(best)
        self.trees_ = trees[: max(1, min(len(trees), 24))]
        self.trained_ = bool(self.trees_)
        if not self.trained_:
            raise ValueError("Unable to find useful tree thresholds for the dataset")
        return self

    def predict_proba(self, features):
        if not self.trained_:
            raise RuntimeError("Model must be trained before predict_proba()")
        x = self._prepare(features)
        scores = np.zeros(len(x), dtype=float)
        total_weight = max(1e-6, sum(max(tree["accuracy"] - 0.5, 0.01) for tree in self.trees_))
        for tree in self.trees_:
            weight = max(tree["accuracy"] - 0.5, 0.01)
            column = x[:, tree["feature_index"]]
            votes = ((column >= tree["threshold"]).astype(float) if tree["polarity"] > 0 else (column < tree["threshold"]).astype(float))
            scores += weight * votes
        positive = np.clip(scores / total_weight, 0.0, 1.0)
        negative = 1.0 - positive
        return np.column_stack([negative, positive])

    def predict(self, features):
        probabilities = self.predict_proba(features)
        return (probabilities[:, 1] >= 0.5).astype(int)


@dataclass
class SequenceLinearClassifier(LinearSignalClassifier):
    sequence_length: int = 4
    model_name: str = "sequence_linear_classifier"

    def fit(self, features, labels, feature_names=None):
        feature_names = [str(name) for name in (feature_names or [])]
        if feature_names:
            expanded = []
            for step in range(self.sequence_length):
                for name in feature_names:
                    expanded.append(f"{name}_t-{self.sequence_length - step - 1}")
            feature_names = expanded
        return super().fit(features, labels, feature_names=feature_names)
