from dataclasses import dataclass
from core.ai.learning_engine import LearningEngine

@dataclass
class FilterResult:
    approved: bool
    reason: str
    score: float


class TradeFilter:

    def __init__(
            self,
            min_confidence=0.65,
            min_vote_margin=0.10,
            max_risk_score=0.7,
            allow_ranging=False,
            max_portfolio_exposure=0.85,
    ):
        self.min_confidence = min_confidence
        self.min_vote_margin = min_vote_margin
        self.max_risk_score = max_risk_score
        self.allow_ranging = allow_ranging
        self.max_portfolio_exposure = max_portfolio_exposure

        self.learning_engine=LearningEngine()


    def evaluate(self, decision, portfolio_snapshot=None):
        if decision is None:
            return FilterResult(True, "Approved", 1.0)

        if isinstance(decision, str):
            if decision.strip().upper() == "HOLD":
                return FilterResult(False, "HOLD decision", 0.0)
            return FilterResult(True, "Approved", 1.0)

        if decision.decision == "HOLD":
            return FilterResult(False, "HOLD decision", 0.0)

        if decision.confidence < self.min_confidence:
            return FilterResult(False, "Low confidence", decision.confidence)

        vote_margin = getattr(decision, "vote_margin", 0.0)
        if vote_margin < self.min_vote_margin:
            return FilterResult(False, "Weak signal", vote_margin)

        risk_score = getattr(decision, "risk_score", 0.5)
        if risk_score > self.max_risk_score:
            return FilterResult(False, "Too risky", 1 - risk_score)

        regime = getattr(decision, "market_regime", None)
        if regime == "RANGING" and not self.allow_ranging:
            return FilterResult(False, "Ranging market", 0.3)


        if portfolio_snapshot:
            exposure = portfolio_snapshot.get("gross_exposure", 0.0)
            equity = portfolio_snapshot.get("equity", 1.0)
            if equity > 0 and (exposure / equity) > self.max_portfolio_exposure:
                return FilterResult(False, "Overexposed portfolio", 0.2)

        score = (
                decision.confidence * 0.6
                + vote_margin * 0.3
                + (1 - risk_score) * 0.1
        )
        if hasattr(self, "learning_engine"):
         self.min_confidence = self.learning_engine.get_dynamic_confidence_threshold()
        strategy_scores = self.learning_engine.strategy_scores()
        if hasattr(self, "learning_engine"):
         dynamic_threshold = self.learning_engine.get_dynamic_confidence_threshold()
         if decision.confidence < dynamic_threshold:
             return FilterResult(False, "confidence < dynamic_threshold", decision.confidence)



        score = strategy_scores

        if score < 0:
           return FilterResult(False, "Strategy underperforming", 0.2)

        regime_perf = self.learning_engine.regime_performance()

        current_regime = decision.market_regime

        if regime_perf.get(current_regime, 0) < 0:
            return FilterResult(False, "Bad regime performance", 0.3)
        return FilterResult(True, "Approved", score)
