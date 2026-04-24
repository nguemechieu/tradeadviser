from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.trade import TradeSide


class TradeCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    side: TradeSide
    amount: Decimal = Field(gt=Decimal("0"))
    pnl: Decimal = Decimal("0")
    strategy: str = Field(min_length=1, max_length=128)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    side: TradeSide
    amount: Decimal
    pnl: Decimal
    strategy: str
    timestamp: datetime
    user_id: str

