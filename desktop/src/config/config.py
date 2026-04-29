"""Configuration module for trading advisor application."""

from typing import Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - lightweight fallback for stripped test environments
    class BaseModel:
        def __init__(self, **kwargs):
            annotations = getattr(self.__class__, "__annotations__", {})
            for field_name in annotations:
                if field_name in kwargs:
                    value = kwargs[field_name]
                else:
                    value = getattr(self.__class__, field_name)
                    if isinstance(value, dict):
                        value = dict(value)
                setattr(self, field_name, value)

    def Field(default=None, description=None, default_factory=None):
        if default_factory is not None:
            return default_factory()
        return default


# ==========================================
# Broker Configuration
# ==========================================

class BrokerConfig(BaseModel):

    type: str = Field(..., description="crypto / forex / stocks / options / futures / derivatives / paper")



    exchange: Optional[str] = Field(
        default=None,
        description="Exchange or broker name (binance, coinbase, solana, stellar, alpaca, oanda, schwab, ibkr, amp, tradovate)"
    )

    customer_region: Optional[str] = Field(
        default=None,
        description="Customer jurisdiction hint such as us or global"
    )

    mode: str = Field(
        default="paper",
        description="paper or live trading"
    )

    api_key: Optional[str] = None
    secret: Optional[str] = None
    password: Optional[str] = None
    username: Optional[str] = None
    passphrase: Optional[str] = None
    uid: Optional[str] = None
    account_id: Optional[str] = None
    sandbox: bool = False
    timeout: int = 30000
    options: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    close: Optional[float] = Field(
        default=None,
        description="Close broker"
    )


# ==========================================
# Risk Configuration
# ==========================================

class RiskConfig(BaseModel):

    risk_percent: float = Field(
        default=2,
        description="% risk per trade"
    )

    max_portfolio_risk: float = 1000
    max_daily_drawdown: float = 10

    max_position_size_pct: float = 5
    max_gross_exposure_pct: float = 100


# ==========================================
# System Configuration
# ==========================================

class SystemConfig(BaseModel):

    limit: int = Field(
        default=50000,
        description="Max candles stored in memory"
    )

    equity_refresh: int = Field(
        default=60,
        description="Equity refresh interval seconds"
    )

    rate_limit: int = Field(
        default=3,
        description="API request rate limit"
    )

    timeframe: str = "1h"


# ==========================================
# Main Application Config
# ==========================================

class AppConfig(BaseModel):

    broker: BrokerConfig
    risk: RiskConfig
    system: SystemConfig

    strategy: str = "LSTM"


# ==========================================
# Example Configuration Instance
# ==========================================

config = AppConfig(

    broker=BrokerConfig(
        type="crypto",
        exchange="coinbase",
        mode="live",
        api_key="wtwey",
        secret="qtyqi"
    ),

    risk=RiskConfig(
        risk_percent=2
    ),

    system=SystemConfig(
        limit=50000,
        rate_limit=30,
        timeframe="1h"
    ),

    strategy="LSTM",
)
