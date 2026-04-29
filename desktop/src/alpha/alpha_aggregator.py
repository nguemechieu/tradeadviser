from __future__ import annotations

from dataclasses import dataclass

from alpha.base_alpha import AlphaContext, AggregatedAlphaOpportunity, AlphaSignal, MarketRegime
from alpha.mean_reversion_alpha import MeanReversionAlpha
from alpha.microstructure_alpha import MicrostructureAlpha
from alpha.ml_alpha import MLAlpha
from alpha.momentum_alpha import MomentumAlpha
from alpha.regime_engine import RegimeEngine
from alpha.stat_arb_alpha import StatisticalArbitrageAlpha
from alpha.trend_alpha import TrendAlpha
from core.regime_engine_config import AlphaAggregationConfig, TradingSystemConfig


@dataclass(slots=True)
class ModelPerformanceState:
    ewma_pnl: float = 0.0
    hit_rate: float = 0.5
    sample_count: int = 0


class AlphaAggregator:
    """Fusion layer that turns multiple alpha models into ranked trade opportunities."""

    def __init__(
        self,
        models=None,
        *,
        regime_engine: RegimeEngine | None = None,
        config: AlphaAggregationConfig | None = None,
    ) -> None:
        system_config = TradingSystemConfig()
        self.config = config or system_config.alpha_aggregation
        self.regime_engine = regime_engine or RegimeEngine(system_config.regime)
        self.models = list(
            models
            or [
                TrendAlpha(),
                MeanReversionAlpha(),
                MomentumAlpha(),
                StatisticalArbitrageAlpha(),
                MicrostructureAlpha(),
                MLAlpha(),
            ]
        )
        self.performance: dict[str, ModelPerformanceState] = {model.name: ModelPerformanceState() for model in self.models}

    def model_names(self) -> list[str]:
        return [model.name for model in self.models]

    def record_outcome(self, model_name: str, *, pnl: float, hit: bool | None = None) -> None:
        state = self.performance.setdefault(str(model_name), ModelPerformanceState())
        decay = self.config.recent_performance_decay
        pnl_value = float(pnl or 0.0)
        state.ewma_pnl = ((1.0 - decay) * state.ewma_pnl) + (decay * pnl_value)
        if hit is None:
            hit = pnl_value > 0
        state.hit_rate = ((1.0 - decay) * state.hit_rate) + (decay * (1.0 if hit else 0.0))
        state.sample_count += 1

    def _performance_weight(self, model_name: str) -> float:
        state = self.performance.get(model_name)
        if state is None or state.sample_count == 0:
            return 1.0
        weight = 1.0 + (state.ewma_pnl * 4.0) + ((state.hit_rate - 0.5) * 0.8)
        return max(self.config.recent_performance_floor, min(self.config.recent_performance_ceiling, weight))

    def _regime_weight(self, signal: AlphaSignal, regime: MarketRegime) -> float:
        weight = 1.0
        if signal.model_name == "trend_alpha" and "TRENDING" in regime.active_regimes:
            weight *= self.config.regime_boost
        if signal.model_name == "mean_reversion_alpha" and "MEAN_REVERTING" in regime.active_regimes:
            weight *= self.config.regime_boost
        if signal.model_name == "microstructure_alpha" and "LOW_LIQUIDITY" in regime.active_regimes:
            weight *= self.config.regime_boost
        if signal.model_name == "momentum_alpha" and "HIGH_VOLATILITY" in regime.active_regimes:
            weight *= self.config.regime_boost
        return weight

    def _volatility_weight(self, signal: AlphaSignal, regime: MarketRegime) -> float:
        realized = max(1e-6, float(regime.realized_volatility or 0.0))
        risk_estimate = max(1e-6, float(signal.risk_estimate or 0.0))
        weight = min(1.25, max(self.config.volatility_penalty_floor, realized / max(risk_estimate, realized)))
        if "HIGH_VOLATILITY" in regime.active_regimes and signal.model_name in {"mean_reversion_alpha", "microstructure_alpha"}:
            weight *= 0.95
        return weight

    def _weighted_components(self, context: AlphaContext, allowed_models: set[str] | None = None) -> tuple[MarketRegime, list[tuple[float, AlphaSignal]]]:
        frame = context.feature_frame if context.feature_frame is not None and not context.feature_frame.empty else context.frame
        regime = context.regime or self.regime_engine.classify_frame(frame, order_book=dict(context.order_book or {}))
        weighted: list[tuple[float, AlphaSignal]] = []
        for model in self.models:
            if allowed_models is not None and model.name not in allowed_models:
                continue
            if not model.is_active(regime):
                continue
            signal = model.generate(
                AlphaContext(
                    symbol=context.symbol,
                    timeframe=context.timeframe,
                    frame=context.frame,
                    feature_frame=context.feature_frame,
                    candles=list(context.candles or []),
                    order_book=context.order_book,
                    cross_sectional_frames=dict(context.cross_sectional_frames or {}),
                    regime=regime,
                    metadata=dict(context.metadata or {}),
                )
            )
            if signal is None:
                continue
            weight = signal.score
            weight *= self._performance_weight(model.name)
            weight *= self._regime_weight(signal, regime)
            weight *= self._volatility_weight(signal, regime)
            weighted.append((weight, signal))
        weighted.sort(key=lambda item: item[0], reverse=True)
        return regime, weighted

    def evaluate_symbol(self, context: AlphaContext, *, allowed_models: list[str] | None = None) -> AggregatedAlphaOpportunity | None:
        allowed = {str(item).strip() for item in list(allowed_models or []) if str(item).strip()} or None
        regime, weighted = self._weighted_components(context, allowed_models=allowed)
        if not weighted:
            return None

        buy_bucket = [(weight, signal) for weight, signal in weighted if signal.expected_return > 0]
        sell_bucket = [(weight, signal) for weight, signal in weighted if signal.expected_return < 0]
        selected = buy_bucket if sum(weight for weight, _ in buy_bucket) >= sum(weight for weight, _ in sell_bucket) else sell_bucket
        if not selected:
            return None

        total_weight = sum(weight for weight, _ in selected)
        if total_weight <= 0:
            return None
        expected_return = sum(weight * signal.expected_return for weight, signal in selected) / total_weight
        confidence = sum(weight * signal.confidence for weight, signal in selected) / total_weight
        risk_estimate = sum(weight * signal.risk_estimate for weight, signal in selected) / total_weight
        alpha_score = (abs(expected_return) / max(risk_estimate, 1e-6)) * confidence
        if confidence < self.config.minimum_confidence or alpha_score < self.config.minimum_alpha_score:
            return None

        components = [signal for _, signal in selected]
        dominant = components[0]
        model_names = [signal.model_name for signal in components]
        reason = "; ".join(signal.reason for signal in components[:3] if signal.reason)
        return AggregatedAlphaOpportunity(
            symbol=context.symbol,
            side=dominant.side,
            expected_return=expected_return,
            confidence=confidence,
            horizon=dominant.horizon,
            risk_estimate=risk_estimate,
            alpha_score=alpha_score,
            regime=regime,
            selected_models=model_names,
            reason=reason or "Alpha fusion layer found a directional edge.",
            components=components,
            metadata={"component_count": len(components), "timeframe": context.timeframe},
        )

    def rank_opportunities(self, contexts: list[AlphaContext], *, allowed_models: dict[str, list[str]] | None = None) -> list[AggregatedAlphaOpportunity]:
        ranked: list[AggregatedAlphaOpportunity] = []
        for context in list(contexts or []):
            symbol = str(getattr(context, "symbol", "") or "").strip().upper()
            opportunity = self.evaluate_symbol(context, allowed_models=(allowed_models or {}).get(symbol))
            if opportunity is not None:
                ranked.append(opportunity)
        ranked.sort(key=lambda item: item.alpha_score, reverse=True)
        return ranked[: self.config.maximum_ranked_opportunities]
