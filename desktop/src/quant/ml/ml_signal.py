import numpy as np


class MLSignal:

    def __init__(self, model):

        self.model = model

    # =====================================
    # PREDICT SIGNAL
    # =====================================

    def predict(self, features):

        X = np.array(features).reshape(1, -1)

        prediction = self.model.predict(X)[0]

        if prediction > 0.6:
            return "BUY"

        if prediction < 0.4:
            return "SELL"

        return "HOLD"
