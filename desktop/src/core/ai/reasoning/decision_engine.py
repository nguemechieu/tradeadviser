from __future__ import annotations

import time
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from models.signal import Signal
from core.ai.reasoning.reasoning_decision import ReasoningDecision
from core.market.regime_detector import MarketRegimeDetector
from core.ai.model import AIModel
from core.ai.features import build_features


@dataclass(slots=True)
class DecisionOutcome:
    votes: dict[str, float] = field(default_factory=lambda: {"buy": 0.0, "sell": 0.0})
    best_by_side: dict[str, Signal] = field(default_factory=dict)

    winning_side: Optional[str] = None
    selected_signal: Optional[Signal] = None
    selected_strategy: str = "none"

    confidence: float = 0.0
    vote_margin: float = 0.0

    reasoning: Optional[ReasoningDecision] = None

class DecisionEngine:
    def __init__(self, fusion_engine, reasoning_engine, regime_detector, ai_model):
        self.fusion = fusion_engine
        self.reasoning = reasoning_engine
        self.regime = regime_detector
        self.ai_model = ai_model

    async def decide(self, ctx: ReasoningContext):
        if not ctx.signals:
            return self._empty(ctx)

        # 🔹 Regime
        regime = self.regime.detect(ctx.candles)

        # 🔹 Fusion
        decision, confidence, vote_margin = self.fusion.fuse(ctx.signals)

        # 🔹 AI Features
        features = build_features(ctx.candles)
        ai_decision = self.ai_model.predict(features)

        # 🔹 AI Reasoning (LLM or heuristic)
        reasoning = await self.reasoning.reason({
            "signals": ctx.signals,
            "regime": regime.name,
            "ai": ai_decision.action,
        })

        # 🔹 AI override
        if ai_decision.confidence > 0.8:
            decision = ai_decision.action
            confidence = ai_decision.confidence

        # 🔹 Build decision
        best_signal = max(ctx.signals, key=lambda s: s.confidence)

        return ReasoningDecision(
            signal=best_signal,
            decision=decision,
            confidence=confidence,
            reasons=[
                f"Regime: {regime.name}",
                f"AI: {ai_decision.action}",
                reasoning.get("explanation", "")
            ],
            strategy_name="QuantFusion",
            model_name="HybridAI",
        )