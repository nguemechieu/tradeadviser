"""Simple model training pipeline for quant ML experiments."""

import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from src.quant.ml.model_manager import ModelManager


class TrainingPipeline:
    """Model lifecycle helper for dataset preparation, training, and persistence."""

    def __init__(self):
        self.model_manager = ModelManager()

    # =====================================
    # TRAIN MODEL
    # =====================================

    def train(self, dataset_path):
        df = pd.read_csv(dataset_path)

        X = df.drop("target", axis=1)

        y = df["target"]

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2
        )

        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=6
        )

        model.fit(X_train, y_train)

        predictions = model.predict(X_test)

        accuracy = accuracy_score(y_test, predictions)

        print("Model accuracy:", accuracy)

        self.model_manager.save(model)

        return model
