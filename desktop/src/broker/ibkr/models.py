from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IBKRTransport(str, Enum):
    WEBAPI = "webapi"
    TWS = "tws"


class IBKRSessionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    SESSION_EXPIRED = "session_expired"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"


@dataclass(slots=True)
class IBKRSessionState:
    transport: IBKRTransport
    status: IBKRSessionStatus = IBKRSessionStatus.DISCONNECTED
    connected: bool = False
    authenticated: bool = False
    account_id: str | None = None
    profile_name: str | None = None
    last_error: str = ""
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["transport"] = self.transport.value
        payload["status"] = self.status.value
        payload["updated_at"] = self.updated_at.isoformat()
        return payload


@dataclass(slots=True)
class IBKRContract:
    symbol: str
    conid: str | None = None
    sec_type: str = "STK"
    exchange: str = "SMART"
    primary_exchange: str | None = None
    currency: str = "USD"
    local_symbol: str | None = None
    multiplier: float | None = None
    expiry: str | None = None
    strike: float | None = None
    right: str | None = None
    underlying: str | None = None
    trading_class: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IBKRAccount:
    account_id: str
    alias: str | None = None
    account_type: str | None = None
    currency: str = "USD"
    brokerage_access: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IBKRBalance:
    account_id: str
    currency: str = "USD"
    cash: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    available_funds: float = 0.0
    maintenance_requirement: float = 0.0
    margin_used: float = 0.0
    net_liquidation: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IBKRPosition:
    account_id: str
    symbol: str
    quantity: float
    avg_price: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    side: str = "long"
    contract: IBKRContract | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["contract"] = self.contract.to_dict() if self.contract is not None else None
        return payload


@dataclass(slots=True)
class IBKRQuote:
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    close: float = 0.0
    mark: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    timestamp: str = field(default_factory=lambda: _utc_now().isoformat())
    contract: IBKRContract | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["contract"] = self.contract.to_dict() if self.contract is not None else None
        return payload


@dataclass(slots=True)
class IBKROrderRequest:
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None = None
    tif: str = "DAY"
    contract: IBKRContract | None = None
    stop_price: float | None = None
    client_order_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["contract"] = self.contract.to_dict() if self.contract is not None else None
        return payload


@dataclass(slots=True)
class IBKROrderResponse:
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    order_id: str
    status: str
    price: float | None = None
    tif: str = "DAY"
    client_order_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
