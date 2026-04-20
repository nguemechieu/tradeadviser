from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

from models.instrument import Instrument


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: float
    side: str = "long"
    instrument: Optional[Instrument] = None
    avg_price: float = 0.0
    mark_price: Optional[float] = None
    leverage: Optional[float] = None
    margin_used: float = 0.0
    liquidation_price: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    broker: Optional[str] = None
    account_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").strip().upper()
        if not self.symbol and self.instrument is not None:
            self.symbol = self.instrument.symbol
        if not self.symbol:
            raise ValueError("Position symbol is required")
        if self.instrument is not None and not isinstance(self.instrument, Instrument):
            self.instrument = Instrument.from_mapping(self.instrument)
        self.quantity = float(self.quantity)
        self.side = str(self.side or ("long" if self.quantity >= 0 else "short")).strip().lower()
        self.avg_price = float(self.avg_price or 0.0)
        if self.mark_price is not None:
            self.mark_price = float(self.mark_price)
        if self.leverage is not None:
            self.leverage = float(self.leverage)
        self.margin_used = float(self.margin_used or 0.0)
        if self.liquidation_price is not None:
            self.liquidation_price = float(self.liquidation_price)
        self.unrealized_pnl = float(self.unrealized_pnl or 0.0)
        self.realized_pnl = float(self.realized_pnl or 0.0)
        self.delta = float(self.delta or 0.0)
        self.gamma = float(self.gamma or 0.0)
        self.theta = float(self.theta or 0.0)
        self.vega = float(self.vega or 0.0)
        if self.broker:
            self.broker = str(self.broker).strip().lower()

    @property
    def contract_multiplier(self) -> float:
        if self.instrument is None:
            return 1.0
        if self.instrument.contract_size not in (None, 0):
            return float(self.instrument.contract_size)
        return float(self.instrument.multiplier or 1.0)

    def market_value(self) -> float:
        price = self.mark_price if self.mark_price is not None else self.avg_price
        return float(price or 0.0) * self.quantity * self.contract_multiplier

    def notional_exposure(self) -> float:
        return abs(self.market_value())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["instrument"] = self.instrument.to_dict() if self.instrument is not None else None
        payload["market_value"] = self.market_value()
        payload["notional_exposure"] = self.notional_exposure()
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "Position") -> "Position":
        if isinstance(value, Position):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("Position payload must be a mapping")
        return cls(
            symbol=value.get("symbol"),
            quantity=value.get("quantity", value.get("qty", value.get("amount", 0.0))),
            side=value.get("side") or value.get("position_side") or "long",
            instrument=value.get("instrument"),
            avg_price=value.get("avg_price", value.get("entry_price", 0.0)),
            mark_price=value.get("mark_price", value.get("price")),
            leverage=value.get("leverage"),
            margin_used=value.get("margin_used", 0.0),
            liquidation_price=value.get("liquidation_price"),
            unrealized_pnl=value.get("unrealized_pnl", value.get("pnl", 0.0)),
            realized_pnl=value.get("realized_pnl", 0.0),
            delta=value.get("delta", 0.0),
            gamma=value.get("gamma", 0.0),
            theta=value.get("theta", 0.0),
            vega=value.get("vega", 0.0),
            broker=value.get("broker") or value.get("exchange"),
            account_id=value.get("account_id") or value.get("account"),
            metadata=dict(value.get("metadata") or {}),
        )
