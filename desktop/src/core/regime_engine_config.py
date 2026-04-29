
"""
InvestPro Trading System Config

Central typed configuration for:
- regime detection
- alpha models
- alpha aggregation
- portfolio construction
- risk management
- time stops
- execution routing

This file is intentionally dependency-light so it can be imported by:
- desktop app
- backend server
- research lab
- backtester
- execution workers
- Telegram/status services
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, TypeVar


T = TypeVar("T")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return int(default)
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return int(default)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _positive(value: float, default: float = 0.0) -> float:
    try:
        number = value
    except (ValueError, TypeError):
        return default
    return max(0.0, number)


def _positive_int(value: int, default: int = 1) -> int:
    try:
        number = int(value)
    except (ValueError, TypeError):
        return int(default)
    return max(1, number)


def _update_dataclass_from_dict(instance: T, values: dict[str, Any]) -> T:
    if not is_dataclass(instance):
        return instance  # type: ignore[return-value]

    valid_names = {item.name for item in fields(instance.__class__)}
    for key, value in dict(values or {}).items():
        if key not in valid_names:
            continue
        setattr(instance, key, value)

    post_init = getattr(instance, "__post_init__", None)
    if callable(post_init):
        post_init()

    return instance


# ---------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------


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

    # Extra InvestPro controls
    breakout_score_threshold: float = 0.70
    trend_confidence_threshold: float = 0.55
    range_confidence_threshold: float = 0.50
    regime_cache_seconds: float = 10.0

    def __post_init__(self) -> None:
        self.adx_trending_threshold = _positive(
            self.adx_trending_threshold, 22.0)
        self.atr_high_vol_threshold = _positive(
            self.atr_high_vol_threshold, 0.025)
        self.realized_vol_high_threshold = _positive(
            self.realized_vol_high_threshold, 0.32)
        self.low_liquidity_volume_ratio = _clamp(
            self.low_liquidity_volume_ratio, 0.0, 10.0)
        self.low_liquidity_spread_bps = _positive(
            self.low_liquidity_spread_bps, 18.0)
        self.volatility_cluster_threshold = _positive(
            self.volatility_cluster_threshold, 1.2)
        self.minimum_history = _positive_int(self.minimum_history, 40)
        self.volatility_window = _positive_int(self.volatility_window, 20)
        self.breakout_score_threshold = _clamp(
            self.breakout_score_threshold, 0.0, 1.0)
        self.trend_confidence_threshold = _clamp(
            self.trend_confidence_threshold, 0.0, 1.0)
        self.range_confidence_threshold = _clamp(
            self.range_confidence_threshold, 0.0, 1.0)
        self.regime_cache_seconds = _positive(self.regime_cache_seconds, 10.0)


# ---------------------------------------------------------------------
# Alpha model
# ---------------------------------------------------------------------


@dataclass(slots=True)
class AlphaModelConfig:
    """Configure individual alpha models that generate 
    trading signals based on market data and regime.
    Defines thresholds, feature requirements, and model-specific parameters that govern when and how each alpha model produces signals. The config controls minimum confidence and expected return thresholds, required historical data length, and feature quality limits to ensure that alpha models only generate signals when conditions are favorable. It also includes extra controls for handling stale data, NaN values, and probability scaling to help maintain signal integrity."""  
    minimum_confidence: float = 0.54
    minimum_expected_return: float = 0.0008
    minimum_history: int = 48
    minimum_alpha_score: float = 0.12

    # Extra model controls
    hold_below_minimum_confidence: bool = True
    max_feature_nan_ratio: float = 0.20
    stale_feature_seconds: float = 180.0
    probability_temperature: float = 1.0

    def __post_init__(self) -> None:
        self.minimum_confidence = _clamp(self.minimum_confidence, 0.0, 1.0)
        self.minimum_expected_return = float(self.minimum_expected_return)
        self.minimum_history = _positive_int(self.minimum_history, 48)
        self.minimum_alpha_score = float(self.minimum_alpha_score)
        self.hold_below_minimum_confidence = bool(
            self.hold_below_minimum_confidence)
        self.max_feature_nan_ratio = _clamp(
            self.max_feature_nan_ratio, 0.0, 1.0)
        self.stale_feature_seconds = _positive(
            self.stale_feature_seconds, 180.0)
        self.probability_temperature = max(
            0.05, float(self.probability_temperature))


# ---------------------------------------------------------------------
# Alpha aggregation
# ---------------------------------------------------------------------


@dataclass(slots=True)
class AlphaAggregationConfig:
    """Configure how individual alpha model signals are combined into a consensus view. Defines
    weights, thresholds, and limits that govern how recent performance, regime, volatility, and
    agreement between models influence the aggregated signal.

    The config controls decay and clamping of recent performance scores, minimum confidence and
    alpha thresholds, and the maximum number of ranked opportunities to keep. It also specifies
    penalties for conflicting signals, maximum signal age, and the margin of directional agreement
    required before a combined alpha is considered tradable.
    """
    recent_performance_decay: float = 0.20
    recent_performance_floor: float = 0.70
    recent_performance_ceiling: float = 1.35
    regime_boost: float = 1.15
    volatility_penalty_floor: float = 0.75
    minimum_confidence: float = 0.55
    minimum_alpha_score: float = 0.12
    maximum_ranked_opportunities: int = 12

    # Extra aggregation controls
    conflict_penalty: float = 0.20
    max_signal_age_seconds: float = 300.0
    require_direction_agreement: bool = False
    min_vote_margin: float = 0.10

    def __post_init__(self) -> None:
        self.recent_performance_decay = _clamp(
            self.recent_performance_decay, 0.0, 1.0)
        self.recent_performance_floor = _positive(
            self.recent_performance_floor, 0.70)
        self.recent_performance_ceiling = max(
            self.recent_performance_floor, float(self.recent_performance_ceiling))
        self.regime_boost = _positive(self.regime_boost, 1.15)
        self.volatility_penalty_floor = _clamp(
            self.volatility_penalty_floor, 0.0, 1.0)
        self.minimum_confidence = _clamp(self.minimum_confidence, 0.0, 1.0)
        self.minimum_alpha_score = float(self.minimum_alpha_score)
        self.maximum_ranked_opportunities = _positive_int(
            self.maximum_ranked_opportunities, 12)
        self.conflict_penalty = _clamp(self.conflict_penalty, 0.0, 1.0)
        self.max_signal_age_seconds = _positive(
            self.max_signal_age_seconds, 300.0)
        self.require_direction_agreement = bool(
            self.require_direction_agreement)
        self.min_vote_margin = _clamp(self.min_vote_margin, 0.0, 1.0)


# ---------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------


@dataclass(slots=True)
class PortfolioConfig:
    """Configure portfolio construction and position sizing limits for the trading system. Defines
    how many opportunities can be held, how concentrated positions may be, and how overall risk
    and correlation should be managed.

    The config controls constraints such as maximum position size, asset-class exposure, and
    correlation thresholds, as well as practical settings like minimum cash buffer and rebalance
    triggers. It also determines whether fractional positions are allowed and how far back to look
    when estimating correlations.
    """
    top_opportunities: int = 5
    max_position_pct: float = 0.12
    target_portfolio_volatility: float = 0.18
    max_asset_class_exposure_pct: float = 0.45
    max_correlation: float = 0.80

    # Extra portfolio controls
    max_open_positions: int = 8
    min_cash_buffer_pct: float = 0.05
    rebalance_threshold_pct: float = 0.03
    allow_fractional_position: bool = True
    correlation_lookback: int = 120

    def __post_init__(self) -> None:
        self.top_opportunities = _positive_int(self.top_opportunities, 5)
        self.max_position_pct = _clamp(self.max_position_pct, 0.0, 1.0)
        self.target_portfolio_volatility = _positive(
            self.target_portfolio_volatility, 0.18)
        self.max_asset_class_exposure_pct = _clamp(
            self.max_asset_class_exposure_pct, 0.0, 1.0)
        self.max_correlation = _clamp(self.max_correlation, 0.0, 1.0)
        self.max_open_positions = _positive_int(self.max_open_positions, 8)
        self.min_cash_buffer_pct = _clamp(self.min_cash_buffer_pct, 0.0, 1.0)
        self.rebalance_threshold_pct = _clamp(
            self.rebalance_threshold_pct, 0.0, 1.0)
        self.allow_fractional_position = bool(self.allow_fractional_position)
        self.correlation_lookback = _positive_int(
            self.correlation_lookback, 120)


# ---------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------


@dataclass(slots=True)
class RiskConfig:
    """Configure portfolio- and trade-level risk limits for the trading system. Encapsulates position
    sizing, drawdown thresholds, leverage caps, and safety switches that govern when trading should
    slow down or stop.

    The config is used to bound per-trade risk, portfolio losses, symbol concentration, and leverage,
    as well as to parameterize default stop-loss/take-profit distances and kill-switch behavior. It
    also controls limits such as daily loss caps, maximum consecutive losses, and stale-data timeouts
    that help protect the account from adverse conditions."""
    max_risk_per_trade: float = 0.015
    max_portfolio_drawdown: float = 0.10
    max_symbol_exposure_pct: float = 0.20
    max_gross_leverage: float = 1.75
    abnormal_volatility_threshold: float = 0.05

    # Extra risk controls
    max_daily_loss_pct: float = 0.04
    max_consecutive_losses: int = 4
    min_reward_risk_ratio: float = 1.20
    default_stop_loss_atr_multiple: float = 1.8
    default_take_profit_atr_multiple: float = 2.5
    kill_switch_drawdown_pct: float = 0.15
    block_trading_on_stale_data_seconds: float = 300.0

    def __post_init__(self) -> None:
        self.max_risk_per_trade = _clamp(self.max_risk_per_trade, 0.0, 1.0)
        self.max_portfolio_drawdown = _clamp(
            self.max_portfolio_drawdown, 0.0, 1.0)
        self.max_symbol_exposure_pct = _clamp(
            self.max_symbol_exposure_pct, 0.0, 1.0)
        self.max_gross_leverage = max(1.0, float(self.max_gross_leverage))
        self.abnormal_volatility_threshold = _positive(
            self.abnormal_volatility_threshold, 0.05)
        self.max_daily_loss_pct = _clamp(self.max_daily_loss_pct, 0.0, 1.0)
        self.max_consecutive_losses = _positive_int(
            self.max_consecutive_losses, 4)
        self.min_reward_risk_ratio = _positive(
            self.min_reward_risk_ratio, 1.20)
        self.default_stop_loss_atr_multiple = _positive(
            self.default_stop_loss_atr_multiple, 1.8)
        self.default_take_profit_atr_multiple = _positive(
            self.default_take_profit_atr_multiple, 2.5)
        self.kill_switch_drawdown_pct = _clamp(
            self.kill_switch_drawdown_pct, 0.0, 1.0)
        self.block_trading_on_stale_data_seconds = _positive(
            self.block_trading_on_stale_data_seconds, 300.0)


# ---------------------------------------------------------------------
# Time stop
# ---------------------------------------------------------------------


@dataclass(slots=True)
class TimeStopConfig:
    """Configure time-based exit rules and position aging logic for open trades. Defines base holding
    horizons, regime- and volatility-aware multipliers, and scoring weights used to decide when a
    trade has overstayed its edge.

    The config controls strict and soft time stops, aging thresholds, and per-strategy duration
    overrides so that trades can be closed proactively based on time, PnL, volatility, and signal
    quality. It normalizes durations, weights, and factors to safe ranges during post-initialization.
    This helps ensure that the time stop logic behaves predictably and prevents extreme values from causing unintended consequences."""
    
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
    strategy_duration_overrides_seconds: dict[str, float] = field(
        default_factory=dict)

    def __post_init__(self) -> None:
        self.short_horizon_seconds = _positive(
            self.short_horizon_seconds, 45.0 * 60.0)
        self.medium_horizon_seconds = max(self.short_horizon_seconds, _positive(
            self.medium_horizon_seconds, 4.0 * 60.0 * 60.0))
        self.long_horizon_seconds = max(self.medium_horizon_seconds, _positive(
            self.long_horizon_seconds, 24.0 * 60.0 * 60.0))
        self.strict_basic_time_stop = bool(self.strict_basic_time_stop)
        self.soft_time_stop_fraction = _clamp(
            self.soft_time_stop_fraction, 0.0, 1.0)
        self.trend_regime_multiplier = _positive(
            self.trend_regime_multiplier, 1.40)
        self.range_regime_multiplier = _positive(
            self.range_regime_multiplier, 0.70)
        self.high_volatility_multiplier = _positive(
            self.high_volatility_multiplier, 0.75)
        self.low_liquidity_multiplier = _positive(
            self.low_liquidity_multiplier, 0.55)
        self.target_volatility = _positive(self.target_volatility, 0.020)
        self.min_volatility_factor = _positive(
            self.min_volatility_factor, 0.60)
        self.max_volatility_factor = max(
            self.min_volatility_factor, _positive(self.max_volatility_factor, 1.60))
        self.aging_score_threshold = _clamp(
            self.aging_score_threshold, 0.0, 1.0)
        self.minimum_age_before_aging_exit_fraction = _clamp(
            self.minimum_age_before_aging_exit_fraction, 0.0, 1.0)
        self.alert_before_close_seconds = _positive(
            self.alert_before_close_seconds, 5.0 * 60.0)

        total_weight = (
            float(self.aging_duration_weight)
            + float(self.aging_pnl_weight)
            + float(self.aging_volatility_weight)
            + float(self.aging_signal_weight)
        )
        if total_weight <= 0:
            self.aging_duration_weight = 0.35
            self.aging_pnl_weight = 0.30
            self.aging_volatility_weight = 0.15
            self.aging_signal_weight = 0.20

        self.strategy_duration_overrides_seconds = {
            str(key): _positive(value, 0.0)
            for key, value in dict(self.strategy_duration_overrides_seconds or {}).items()
        }


# ---------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------


@dataclass(slots=True)
class ExecutionConfig:
    """Configure execution behavior and smart order routing for the trading system. Defines latency,
    slippage limits, order sizing thresholds, and routing options that control how orders are sliced
    and sent to the market.

    The config is used to parameterize execution algorithms such as TWAP/VWAP and iceberg orders,
    as well as safety limits like maximum slippage and timeouts. It also controls whether smart
    routing and post-only behavior are enabled by default."""

    base_latency_ms: float = 35.0
    max_slippage_bps: float = 20.0
    partial_fill_threshold_notional: float = 25_000.0
    twap_slices: int = 4
    vwap_default_buckets: int = 4

    # Extra smart execution controls
    default_order_type: str = "market"
    large_order_threshold_notional: float = 50_000.0
    iceberg_threshold_notional: float = 100_000.0
    max_child_order_notional: float = 15_000.0
    smart_routing_enabled: bool = True
    order_timeout_seconds: float = 30.0
    retry_attempts: int = 2
    retry_delay_seconds: float = 1.0
    post_only_by_default: bool = False

    def __post_init__(self) -> None:
        self.base_latency_ms = _positive(self.base_latency_ms, 35.0)
        self.max_slippage_bps = _positive(self.max_slippage_bps, 20.0)
        self.partial_fill_threshold_notional = _positive(
            self.partial_fill_threshold_notional, 25_000.0)
        self.twap_slices = _positive_int(self.twap_slices, 4)
        self.vwap_default_buckets = _positive_int(self.vwap_default_buckets, 4)
        self.default_order_type = str(
            self.default_order_type or "market").strip().lower()
        self.large_order_threshold_notional = _positive(
            self.large_order_threshold_notional, 50_000.0)
        self.iceberg_threshold_notional = _positive(
            self.iceberg_threshold_notional, 100_000.0)
        self.max_child_order_notional = _positive(
            self.max_child_order_notional, 15_000.0)
        self.smart_routing_enabled = bool(self.smart_routing_enabled)
        self.order_timeout_seconds = _positive(
            self.order_timeout_seconds, 30.0)
        self.retry_attempts = max(0, int(self.retry_attempts))
        self.retry_delay_seconds = _positive(self.retry_delay_seconds, 1.0)
        self.post_only_by_default = bool(self.post_only_by_default)


# ---------------------------------------------------------------------
# Full config
# ---------------------------------------------------------------------


@dataclass(slots=True)
class TradingSystemConfig:
    """Aggregate configuration for the full trading system across all major components. Encapsulates
    regime detection, alpha generation, portfolio construction, risk, time stops, and execution
    settings into a single, serializable object.

    The config is designed to be created from code, dictionaries, or environment variables so that
    different runtimes (desktop, backend, research, workers) can share consistent parameters. It
    validates and normalizes key fields such as mode and environment while delegating section-level
    validation to the individual sub-config dataclasses."""
    regime: RegimeEngineConfig = field(default_factory=RegimeEngineConfig)
    alpha_models: AlphaModelConfig = field(default_factory=AlphaModelConfig)
    alpha_aggregation: AlphaAggregationConfig = field(
        default_factory=AlphaAggregationConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    time_stop: TimeStopConfig = field(default_factory=TimeStopConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    app_name: str = "InvestPro"
    mode: str = "paper"
    environment: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.app_name = str(
            self.app_name or "InvestPro").strip() or "InvestPro"
        self.mode = str(self.mode or "paper").strip().lower()
        if self.mode not in {"paper", "live", "backtest", "research"}:
            self.mode = "paper"

        self.environment = str(
            self.environment or "local").strip().lower() or "local"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "TradingSystemConfig":
        values = dict(values or {})
        config = cls()

        for section_name in (
            "regime",
            "alpha_models",
            "alpha_aggregation",
            "portfolio",
            "risk",
            "time_stop",
            "execution",
        ):
            section_values = values.pop(section_name, None)
            if isinstance(section_values, dict):
                _update_dataclass_from_dict(
                    getattr(config, section_name), section_values)

        for key, value in values.items():
            if hasattr(config, key):
                setattr(config, key, value)

        config.__post_init__()
        return config

    @classmethod
    def from_env(cls, prefix: str = "INVESTPRO") -> "TradingSystemConfig":
        """Create config using environment variable overrides.

        Example:
            INVESTPRO_MODE=paper
            INVESTPRO_RISK_MAX_RISK_PER_TRADE=0.01
            INVESTPRO_EXECUTION_TWAP_SLICES=6
        """
        config = cls()

        config.app_name = os.getenv(f"{prefix}_APP_NAME", config.app_name)
        config.mode = os.getenv(f"{prefix}_MODE", config.mode)
        config.environment = os.getenv(
            f"{prefix}_ENVIRONMENT", config.environment)

        config.risk.max_risk_per_trade = _float_env(
            f"{prefix}_RISK_MAX_RISK_PER_TRADE",
            config.risk.max_risk_per_trade,
        )
        config.risk.max_portfolio_drawdown = _float_env(
            f"{prefix}_RISK_MAX_PORTFOLIO_DRAWDOWN",
            config.risk.max_portfolio_drawdown,
        )
        config.risk.max_symbol_exposure_pct = _float_env(
            f"{prefix}_RISK_MAX_SYMBOL_EXPOSURE_PCT",
            config.risk.max_symbol_exposure_pct,
        )
        config.risk.max_gross_leverage = _float_env(
            f"{prefix}_RISK_MAX_GROSS_LEVERAGE",
            config.risk.max_gross_leverage,
        )

        config.execution.twap_slices = _int_env(
            f"{prefix}_EXECUTION_TWAP_SLICES",
            config.execution.twap_slices,
        )
        config.execution.vwap_default_buckets = _int_env(
            f"{prefix}_EXECUTION_VWAP_DEFAULT_BUCKETS",
            config.execution.vwap_default_buckets,
        )
        config.execution.max_slippage_bps = _float_env(
            f"{prefix}_EXECUTION_MAX_SLIPPAGE_BPS",
            config.execution.max_slippage_bps,
        )
        config.execution.smart_routing_enabled = _bool_env(
            f"{prefix}_EXECUTION_SMART_ROUTING_ENABLED",
            config.execution.smart_routing_enabled,
        )

        config.alpha_models.minimum_confidence = _float_env(
            f"{prefix}_ALPHA_MINIMUM_CONFIDENCE",
            config.alpha_models.minimum_confidence,
        )
        config.alpha_aggregation.minimum_confidence = _float_env(
            f"{prefix}_ALPHA_AGGREGATION_MINIMUM_CONFIDENCE",
            config.alpha_aggregation.minimum_confidence,
        )

        config.portfolio.top_opportunities = _int_env(
            f"{prefix}_PORTFOLIO_TOP_OPPORTUNITIES",
            config.portfolio.top_opportunities,
        )
        config.portfolio.max_position_pct = _float_env(
            f"{prefix}_PORTFOLIO_MAX_POSITION_PCT",
            config.portfolio.max_position_pct,
        )

        for section in (
            config.regime,
            config.alpha_models,
            config.alpha_aggregation,
            config.portfolio,
            config.risk,
            config.time_stop,
            config.execution,
        ):
            post_init = getattr(section, "__post_init__", None)
            if callable(post_init):
                post_init()

        config.__post_init__()
        return config


def default_trading_system_config() -> TradingSystemConfig:
    return TradingSystemConfig()


__all__ = [
    "AlphaAggregationConfig",
    "AlphaModelConfig",
    "ExecutionConfig",
    "PortfolioConfig",
    "RegimeEngineConfig",
    "RiskConfig",
    "TimeStopConfig",
    "TradingSystemConfig",
    "default_trading_system_config",
]
