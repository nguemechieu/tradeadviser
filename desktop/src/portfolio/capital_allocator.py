from __future__ import annotations

from dataclasses import dataclass, field

from alpha.base_alpha import AggregatedAlphaOpportunity
from core.config import PortfolioConfig


@dataclass(slots=True)
class CapitalAllocationPlan:
    symbol: str
    side: str
    target_notional: float
    target_quantity: float
    portfolio_weight: float
    alpha_score: float
    expected_return: float
    confidence: float
    risk_estimate: float
    strategy_name: str = "alpha_fusion"
    metadata: dict = field(default_factory=dict)


class CapitalAllocator:
    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self.config = config or PortfolioConfig()

    def allocate(self, opportunities: list[AggregatedAlphaOpportunity], *, capital_base: float) -> list[CapitalAllocationPlan]:
        candidates = [item for item in list(opportunities or []) if item is not None and item.alpha_score > 0]
        if not candidates or capital_base <= 0:
            return []
        ranked = sorted(candidates, key=lambda item: item.alpha_score, reverse=True)[: self.config.top_opportunities]

        raw_scores: dict[str, float] = {}
        for opportunity in ranked:
            risk = max(float(opportunity.risk_estimate or 0.0), 1e-6)
            quality = max(0.0, float(opportunity.confidence or 0.0) * abs(float(opportunity.expected_return or 0.0)))
            raw_scores[opportunity.symbol] = quality / risk

        total_score = sum(raw_scores.values())
        if total_score <= 0:
            return []

        plans: list[CapitalAllocationPlan] = []
        for opportunity in ranked:
            raw_weight = raw_scores[opportunity.symbol] / total_score
            volatility_scale = min(1.20, max(0.25, self.config.target_portfolio_volatility / max(opportunity.risk_estimate, 1e-6)))
            adjusted_weight = min(self.config.max_position_pct, raw_weight * volatility_scale)
            target_notional = capital_base * adjusted_weight
            target_quantity = target_notional / max(1e-9, float(opportunity.metadata.get("price") or 0.0) or 1.0)
            plans.append(
                CapitalAllocationPlan(
                    symbol=opportunity.symbol,
                    side=opportunity.side,
                    target_notional=target_notional,
                    target_quantity=target_quantity,
                    portfolio_weight=adjusted_weight,
                    alpha_score=opportunity.alpha_score,
                    expected_return=opportunity.expected_return,
                    confidence=opportunity.confidence,
                    risk_estimate=opportunity.risk_estimate,
                    metadata={"selected_models": list(opportunity.selected_models), "regime": opportunity.regime.to_dict()},
                )
            )
        return plans
