from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from models.instrument import Instrument


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    BRACKET = "bracket"


@dataclass(slots=True)
class OrderLeg:
    instrument: Instrument
    side: OrderSide
    quantity: float
    ratio: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            self.instrument = Instrument.from_mapping(self.instrument)
        if not isinstance(self.side, OrderSide):
            self.side = OrderSide(str(self.side).strip().lower())
        self.quantity = float(self.quantity)
        self.ratio = float(self.ratio or 1.0)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["instrument"] = self.instrument.to_dict()
        payload["side"] = self.side.value
        return payload


@dataclass(slots=True)
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    instrument: Optional[Instrument] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    broker: Optional[str] = None
    time_in_force: str = "DAY"
    source: str = "bot"
    client_order_id: Optional[str] = None
    account_id: Optional[str] = None
    strategy_name: Optional[str] = None
    execution_strategy: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    legs: list[OrderLeg] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").strip().upper()
        if not self.symbol and self.instrument is not None:
            self.symbol = self.instrument.symbol
        if not self.symbol:
            raise ValueError("Order symbol is required")
        if self.instrument is not None and not isinstance(self.instrument, Instrument):
            self.instrument = Instrument.from_mapping(self.instrument)
        if not isinstance(self.side, OrderSide):
            self.side = OrderSide(str(self.side).strip().lower())
        if not isinstance(self.order_type, OrderType):
            normalized_type = str(self.order_type or OrderType.MARKET.value).strip().lower().replace(" ", "_")
            self.order_type = OrderType(normalized_type)
        self.quantity = float(self.quantity)
        if self.price is not None:
            self.price = float(self.price)
        if self.stop_price is not None:
            self.stop_price = float(self.stop_price)
        if self.take_profit is not None:
            self.take_profit = float(self.take_profit)
        if self.stop_loss is not None:
            self.stop_loss = float(self.stop_loss)
        self.time_in_force = str(self.time_in_force or "DAY").strip().upper()
        self.source = str(self.source or "bot").strip().lower() or "bot"
        if self.broker:
            self.broker = str(self.broker).strip().lower()
        if self.client_order_id:
            self.client_order_id = str(self.client_order_id).strip()
        if self.account_id:
            self.account_id = str(self.account_id).strip()
        normalized_legs = []
        for leg in list(self.legs or []):
            normalized_legs.append(leg if isinstance(leg, OrderLeg) else OrderLeg(**dict(leg)))
        self.legs = normalized_legs

    @property
    def instrument_type(self) -> Optional[str]:
        if self.instrument is not None:
            return self.instrument.type.value
        return None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "symbol": self.symbol,
            "side": self.side.value,
            "amount": self.quantity,
            "quantity": self.quantity,
            "type": self.order_type.value,
            "order_type": self.order_type.value,
            "price": self.price,
            "stop_price": self.stop_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "broker": self.broker,
            "time_in_force": self.time_in_force,
            "source": self.source,
            "client_order_id": self.client_order_id,
            "account_id": self.account_id,
            "strategy_name": self.strategy_name,
            "execution_strategy": self.execution_strategy,
            "created_at": self.created_at.isoformat(),
            "instrument": self.instrument.to_dict() if self.instrument is not None else None,
            "instrument_type": self.instrument_type,
            "legs": [leg.to_dict() for leg in self.legs],
            "params": dict(self.params or {}),
            "metadata": dict(self.metadata or {}),
        }
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "Order") -> "Order":
        if isinstance(value, Order):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("Order payload must be a mapping")
        return cls(
            symbol=value.get("symbol") or value.get("instrument", {}).get("symbol"),
            side=value.get("side") or value.get("signal"),
            quantity=value.get("quantity", value.get("amount", value.get("size"))),
            order_type=value.get("order_type") or value.get("type") or OrderType.MARKET.value,
            instrument=value.get("instrument"),
            price=value.get("price") or value.get("limit_price"),
            stop_price=value.get("stop_price"),
            take_profit=value.get("take_profit"),
            stop_loss=value.get("stop_loss"),
            broker=value.get("broker") or value.get("exchange"),
            time_in_force=value.get("time_in_force", "DAY"),
            source=value.get("source", "bot"),
            client_order_id=value.get("client_order_id") or value.get("clientOrderId"),
            account_id=value.get("account_id") or value.get("account"),
            strategy_name=value.get("strategy_name"),
            execution_strategy=value.get("execution_strategy"),
            legs=list(value.get("legs") or []),
            params=dict(value.get("params") or {}),
            metadata=dict(value.get("metadata") or {}),
        )
