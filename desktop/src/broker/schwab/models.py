from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.oauth.models import OAuthSessionState, OAuthTokenSet
from models.instrument import Instrument


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchwabOrderStatus(str, Enum):
    UNKNOWN = "unknown"
    SUBMITTED = "submitted"
    WORKING = "working"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(slots=True)
class SchwabTokenSet(OAuthTokenSet):
    provider: str = field(default="schwab", init=False)


@dataclass(slots=True)
class SchwabAuthState(OAuthSessionState):
    provider: str = field(default="schwab", init=False)


@dataclass(slots=True)
class SchwabAccount:
    account_id: str
    account_hash: str | None = None
    alias: str | None = None
    account_type: str | None = None
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchwabBalance:
    account_id: str
    account_hash: str | None = None
    currency: str = "USD"
    cash: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    available_funds: float = 0.0
    maintenance_requirement: float = 0.0
    margin_used: float = 0.0
    liquidation_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchwabPosition:
    account_id: str
    account_hash: str | None
    symbol: str
    quantity: float
    side: str = "long"
    instrument: Instrument | None = None
    avg_price: float = 0.0
    mark_price: float | None = None
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["instrument"] = self.instrument.to_dict() if self.instrument is not None else None
        return payload


@dataclass(slots=True)
class SchwabQuote:
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    close: float = 0.0
    mark: float = 0.0
    timestamp: str = field(default_factory=lambda: _utc_now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchwabOrderRequest:
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    time_in_force: str = "DAY"
    price: float | None = None
    stop_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    instrument: Instrument | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["instrument"] = self.instrument.to_dict() if self.instrument is not None else None
        return payload


@dataclass(slots=True)
class SchwabOrderResponse:
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    order_id: str
    status: SchwabOrderStatus = SchwabOrderStatus.SUBMITTED
    time_in_force: str = "DAY"
    price: float | None = None
    stop_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
