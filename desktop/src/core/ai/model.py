from dataclasses import dataclass
import numpy as np


@dataclass
class AIDecision:
    action: str
    confidence: float


class AIModel:
    def __init__(self, model=None):
        self.model = model

    def predict(self, features: np.ndarray) -> AIDecision:
        if self.model is None:
            return AIDecision("HOLD", 0.0)

        probs = self.model.predict_proba([features])[0]

        idx = int(np.argmax(probs))
        confidence = float(probs[idx])

        mapping = {0: "SELL", 1: "HOLD", 2: "BUY"}
        action = mapping.get(idx, "HOLD")

        return AIDecision(action, confidence)
