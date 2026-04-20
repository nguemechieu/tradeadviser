import joblib
import os


class ModelManager:

    def __init__(self, model_path="models/trained/model.pkl"):
        self.model_path = model_path
        self.model = None

    # =====================================
    # LOAD MODEL
    # =====================================

    def load(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError("Model not found")

        self.model = joblib.load(self.model_path)

        return self.model

    # =====================================
    # SAVE MODEL
    # =====================================

    def save(self, model):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

        joblib.dump(model, self.model_path)

        self.model = model
