from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SignalCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    strategy: str = Field(min_length=1, max_length=128)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    timeframe: str = Field(min_length=1, max_length=32)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    strategy: str
    confidence: Decimal
    timeframe: str
    timestamp: datetime
    user_id: str

