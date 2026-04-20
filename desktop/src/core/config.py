from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RegimeEngineConfig:
    adx_trending_threshold: float = 22.0
    atr_high_vol_threshold: float = 0.025
    realized_vol_high_threshold: float = 0.32
    low_liquidity_volume_ratio: float = 0.75
    low_liquidity_spread_bps: float = 18.0
    volatility_cluster_threshold: float = 1.2
    minimum_history: int = 40
    volatility_window: int = 20


@dataclass(slots=True)
class AlphaModelConfig:
    minimum_confidence: float = 0.54
    minimum_expected_return: float = 0.0008
    minimum_history: int = 48
    minimum_alpha_score: float = 0.12


@dataclass(slots=True)
class AlphaAggregationConfig:
    recent_performance_decay: float = 0.20
    recent_performance_floor: float = 0.70
    recent_performance_ceiling: float = 1.35
    regime_boost: float = 1.15
    volatility_penalty_floor: float = 0.75
    minimum_confidence: float = 0.55
    minimum_alpha_score: float = 0.12
    maximum_ranked_opportunities: int = 12


@dataclass(slots=True)
class PortfolioConfig:
    top_opportunities: int = 5
    max_position_pct: float = 0.12
    target_portfolio_volatility: float = 0.18
    max_asset_class_exposure_pct: float = 0.45
    max_correlation: float = 0.80


@dataclass(slots=True)
class RiskConfig:
    max_risk_per_trade: float = 0.015
    max_portfolio_drawdown: float = 0.10
    max_symbol_exposure_pct: float = 0.20
    max_gross_leverage: float = 1.75
    abnormal_volatility_threshold: float = 0.05


@dataclass(slots=True)
class TimeStopConfig:
    short_horizon_seconds: float = 45.0 * 60.0
    medium_horizon_seconds: float = 4.0 * 60.0 * 60.0
    long_horizon_seconds: float = 24.0 * 60.0 * 60.0
    strict_basic_time_stop: bool = True
    soft_time_stop_fraction: float = 0.85
    min_expected_return: float = 0.0010
    trend_regime_multiplier: float = 1.40
    range_regime_multiplier: float = 0.70
    high_volatility_multiplier: float = 0.75
    low_liquidity_multiplier: float = 0.55
    target_volatility: float = 0.020
    min_volatility_factor: float = 0.60
    max_volatility_factor: float = 1.60
    aging_duration_weight: float = 0.35
    aging_pnl_weight: float = 0.30
    aging_volatility_weight: float = 0.15
    aging_signal_weight: float = 0.20
    aging_score_threshold: float = 0.34
    minimum_age_before_aging_exit_fraction: float = 0.40
    alert_before_close_seconds: float = 5.0 * 60.0
    strategy_duration_overrides_seconds: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionConfig:
    base_latency_ms: float = 35.0
    max_slippage_bps: float = 20.0
    partial_fill_threshold_notional: float = 25000.0
    twap_slices: int = 4
    vwap_default_buckets: int = 4


@dataclass(slots=True)
class TradingSystemConfig:
    regime: RegimeEngineConfig = field(default_factory=RegimeEngineConfig)
    alpha_models: AlphaModelConfig = field(default_factory=AlphaModelConfig)
    alpha_aggregation: AlphaAggregationConfig = field(default_factory=AlphaAggregationConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    time_stop: TimeStopConfig = field(default_factory=TimeStopConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
