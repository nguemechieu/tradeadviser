from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BrokerConfig(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str
    exchange: str
    type: Literal["crypto", "future", "futures", "derivative", "derivatives", "options", "paper"] = "futures"
    mode: Literal["live", "paper", "backtest"] = "paper"
    broker_class: str | None = None
    account_id: str | None = None
    customer_region: str | None = None
    api_key: str | None = None
    secret: str | None = None
    password: str | None = None
    symbols: list[str] = Field(default_factory=list)
    priority: int = 100
    market_type: str = "derivative"
    default_subtype: str | None = "future"
    timeout_seconds: float = 20.0
    max_retries: int = 3
    rate_limit_per_second: float = 6.0
    options: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)


class RiskConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_portfolio_risk_pct: float = 0.12
    max_daily_drawdown_pct: float = 0.05
    max_concurrent_positions: int = 12
    max_risk_per_trade_pct: float = 0.015
    max_exposure_per_asset_pct: float = 0.25
    max_leverage: float = 3.0
    kill_switch_loss_pct: float = 0.06
    volatility_position_floor: float = 0.25
    volatility_position_ceiling: float = 1.0
    min_margin_buffer_pct: float = 0.08
    default_stop_atr_multiple: float = 2.0


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbols: list[str] = Field(default_factory=list)
    strategy_classes: list[str] = Field(
        default_factory=lambda: [
            "derivatives.engine.strategies.TrendFollowingStrategy",
            "derivatives.engine.strategies.MeanReversionStrategy",
            "derivatives.engine.strategies.BreakoutStrategy",
            "derivatives.engine.strategies.MLStrategy",
        ]
    )
    signal_cooldown_seconds: float = 15.0
    min_confidence: float = 0.55
    default_order_type: str = "market"
    default_signal_duration_seconds: float = 3600.0
    strategy_params: dict[str, dict] = Field(default_factory=dict)


class MLConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_dir: str = "data/models/derivatives"
    inference_threshold: float = 0.57
    training_label_horizon: int = 12
    min_training_rows: int = 250
    use_xgboost: bool = True
    use_random_forest: bool = True
    use_hmm: bool = True
    persist_predictions: bool = True
    retrain_interval_minutes: int = 60


class EngineConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    ticker_poll_interval_seconds: float = 2.0
    orderbook_poll_interval_seconds: float = 3.0
    trade_poll_interval_seconds: float = 5.0
    market_data_poll_seconds: float = 2.0
    orderbook_poll_seconds: float = 3.0
    trade_poll_seconds: float = 5.0
    history_window: int = 240
    candle_timeframe: str = "1m"
    default_commission_bps: float = 1.5
    default_slippage_bps: float = 2.0
    commission_bps: float = 1.5
    slippage_bps: float = 2.0
    auto_reconnect: bool = True
    reconnect_backoff_seconds: float = 1.0
    max_reconnect_backoff_seconds: float = 30.0
    max_reconnect_delay_seconds: float = 30.0
    execution_retry_attempts: int = 2

    def model_post_init(self, __context) -> None:
        if self.market_data_poll_seconds == 2.0 and self.ticker_poll_interval_seconds != 2.0:
            self.market_data_poll_seconds = self.ticker_poll_interval_seconds
        if self.orderbook_poll_seconds == 3.0 and self.orderbook_poll_interval_seconds != 3.0:
            self.orderbook_poll_seconds = self.orderbook_poll_interval_seconds
        if self.trade_poll_seconds == 5.0 and self.trade_poll_interval_seconds != 5.0:
            self.trade_poll_seconds = self.trade_poll_interval_seconds
        if self.commission_bps == 1.5 and self.default_commission_bps != 1.5:
            self.commission_bps = self.default_commission_bps
        if self.slippage_bps == 2.0 and self.default_slippage_bps != 2.0:
            self.slippage_bps = self.default_slippage_bps
        if self.max_reconnect_delay_seconds == 30.0 and self.max_reconnect_backoff_seconds != 30.0:
            self.max_reconnect_delay_seconds = self.max_reconnect_backoff_seconds


class DerivativesSystemConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    brokers: list[BrokerConfig] = Field(default_factory=list)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    starting_equity: float = 100000.0
    base_currency: str = "USD"
