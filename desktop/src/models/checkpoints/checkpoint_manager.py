import joblib
import os


class CheckpointManager:

    def __init__(self):
        self.dir = "models/checkpoints"

        os.makedirs(self.dir, exist_ok=True)

    def save_checkpoint(self, model, epoch):
        path = os.path.join(self.dir, f"model_epoch_{epoch}.pkl")

        joblib.dump(model, path)
