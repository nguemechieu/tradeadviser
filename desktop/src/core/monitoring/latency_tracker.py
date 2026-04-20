import time
from collections import deque
import numpy as np


class LatencyTracker:

    def __init__(self, max_samples=100):
        self.samples = deque(maxlen=max_samples)
        self.errors = 0

    # =========================
    # RECORD LATENCY
    # =========================
    def record(self, duration: float):
        self.samples.append(duration)

    # =========================
    # RECORD ERROR
    # =========================
    def record_error(self):
        self.errors += 1

    # =========================
    # GET METRICS
    # =========================
    def stats(self):
        if not self.samples:
            return {
                "avg": 0.1,
                "p95": 0.2,
                "error_rate": 0.0,
            }

        avg = np.mean(self.samples)
        p95 = np.percentile(self.samples, 95)

        error_rate = self.errors / max(1, len(self.samples))

        return {
            "avg": avg,
            "p95": p95,
            "error_rate": error_rate,
        }