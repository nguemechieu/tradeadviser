from __future__ import annotations

from dataclasses import dataclass, field

from alpha.base_alpha import AggregatedAlphaOpportunity
from core.regime_engine_config import PortfolioConfig
from portfolio.capital_allocator import CapitalAllocationPlan, CapitalAllocator
from portfolio.position_manager import PositionManager


@dataclass(slots=True)
class PortfolioConstructionResult:
    selected: list[CapitalAllocationPlan] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


class PortfolioManager:
    def __init__(
        self,
        *,
        allocator: CapitalAllocator | None = None,
        position_manager: PositionManager | None = None,
        config: PortfolioConfig | None = None,
    ) -> None:
        self.config = config or PortfolioConfig()
        self.allocator = allocator or CapitalAllocator(self.config)
        self.position_manager = position_manager or PositionManager()

    def construct(
        self,
        opportunities: list[AggregatedAlphaOpportunity],
        *,
        capital_base: float,
        correlation_matrix: dict[tuple[str, str], float] | None = None,
    ) -> PortfolioConstructionResult:
        plans = self.allocator.allocate(opportunities, capital_base=capital_base)
        exposures = self.position_manager.exposure_by_asset_class()
        selected: list[CapitalAllocationPlan] = []
        rejected: list[dict] = []
        used_symbols: list[str] = []
        for plan in plans:
            asset_class = str(plan.metadata.get("asset_class") or "unknown")
            projected_asset_exposure = exposures.get(asset_class, 0.0) + plan.target_notional
            if capital_base > 0 and (projected_asset_exposure / capital_base) > self.config.max_asset_class_exposure_pct:
                rejected.append({"symbol": plan.symbol, "reason": "asset class exposure limit"})
                continue
            correlated = False
            for selected_symbol in used_symbols:
                corr_value = abs(float((correlation_matrix or {}).get((plan.symbol, selected_symbol), 0.0)))
                if corr_value > self.config.max_correlation:
                    correlated = True
                    break
            if correlated:
                rejected.append({"symbol": plan.symbol, "reason": "correlation limit"})
                continue
            selected.append(plan)
            used_symbols.append(plan.symbol)
            exposures[asset_class] = projected_asset_exposure
        return PortfolioConstructionResult(selected=selected, rejected=rejected)
