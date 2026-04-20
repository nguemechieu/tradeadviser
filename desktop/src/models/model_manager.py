import os
import joblib


class ModelManager:

    def __init__(self):
        self.model_dir = "models/trained"

        os.makedirs(self.model_dir, exist_ok=True)

    # ===============================
    # SAVE MODEL
    # ===============================

    def save(self, model, name):
        path = os.path.join(self.model_dir, name)

        joblib.dump(model, path)

    # ===============================
    # LOAD MODEL
    # ===============================

    def load(self, name):
        path = os.path.join(self.model_dir, name)

        if not os.path.exists(path):
            return None

        return joblib.load(path)
