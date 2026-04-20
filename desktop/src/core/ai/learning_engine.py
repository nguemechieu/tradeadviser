import numpy as np
from collections import deque
import json
import time


class LearningEngine:

    def __init__(self, max_history=50000):
        self.history = deque(maxlen=max_history)

        # 🔥 adaptive parameters
        self.confidence_threshold = 0.65
        self.atr_multiplier = 2.0


    # =========================
    # RECORD TRADE OUTCOME
    # =========================
    def record_trade(self, trade_data: dict):

        pnl = float(trade_data.get("pnl", 0.0))
        confidence = float(trade_data.get("confidence", 0.5))

        outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

        record = {
            "timestamp": time.time(),
            "pnl": pnl,
            "outcome": outcome,
            "confidence": confidence,
            "decision": trade_data.get("decision"),
            "strategy": trade_data.get("strategy"),
            "market_regime": trade_data.get("market_regime"),
            "atr": float(trade_data.get("atr", 0.0)),
            "sl_hit": trade_data.get("sl_hit", False),
            "tp_hit": trade_data.get("tp_hit", False),
            "duration": trade_data.get("duration", 0),
        }

        self.history.append(record)

    # =========================
    # DYNAMIC CONFIDENCE THRESHOLD
    # =========================
    def get_dynamic_confidence_threshold(self):

        if len(self.history) < 30:
            return self.confidence_threshold

        # 🔥 Use recent trades only (last 100)
        recent = list(self.history)[-100:]

        wins = [h for h in recent if h["outcome"] == "win"]
        losses = [h for h in recent if h["outcome"] == "loss"]

        if not wins or not losses:
            return self.confidence_threshold

        win_conf = np.mean([h["confidence"] for h in wins])
        loss_conf = np.mean([h["confidence"] for h in losses])

        # 🔥 Smooth update (avoid jumps)
        new_threshold = (win_conf + loss_conf) / 2
        self.confidence_threshold = (
                0.8 * self.confidence_threshold + 0.2 * new_threshold
        )

        return self.confidence_threshold

    # =========================
    # ATR ADAPTATION (VERY IMPORTANT)
    # =========================
    def update_atr_multiplier(self):

        if len(self.history) < 50:
            return self.atr_multiplier

        recent = list(self.history)[-100:]

        sl_losses = [h for h in recent if h["sl_hit"]]
        tp_wins = [h for h in recent if h["tp_hit"]]

        if len(sl_losses) > len(tp_wins):
            self.atr_multiplier *= 1.05  # widen stops
        else:
            self.atr_multiplier *= 0.98  # tighten stops

        # clamp values
        self.atr_multiplier = max(1.2, min(3.5, self.atr_multiplier))

        return self.atr_multiplier

    # =========================
    # STRATEGY PERFORMANCE
    # =========================
    def strategy_scores(self):

        scores = {}

        for h in self.history:
            s = h["strategy"]
            scores.setdefault(s, []).append(h["pnl"])

        return {s: np.mean(v) for s, v in scores.items()}

    # =========================
    # REGIME PERFORMANCE
    # =========================
    def regime_performance(self):

        regimes = {}

        for h in self.history:
            r = h["market_regime"]
            regimes.setdefault(r, []).append(h["pnl"])

        return {r: np.mean(v) for r, v in regimes.items()}

    # =========================
    # SAVE / LOAD (CRITICAL)
    # =========================
    def save(self, path="learning.json"):
        try:
            with open(path, "w") as f:
                json.dump(list(self.history), f)
        except Exception:
            pass

    def load(self, path="learning.json"):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                self.history = deque(data, maxlen=self.history.maxlen)
        except Exception:
            pass