from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional


class InstrumentType(str, Enum):
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"
    CRYPTO = "crypto"


class OptionRight(str, Enum):
    CALL = "call"
    PUT = "put"


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(slots=True)
class Instrument:
    symbol: str
    type: InstrumentType = InstrumentType.STOCK
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
    option_type: Optional[OptionRight] = None
    contract_size: Optional[int] = None
    exchange: Optional[str] = None
    currency: str = "USD"
    multiplier: float = 1.0
    underlying: Optional[str] = None
    broker_hint: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").strip().upper()
        if not self.symbol:
            raise ValueError("Instrument symbol is required")
        if not isinstance(self.type, InstrumentType):
            self.type = InstrumentType(str(self.type or InstrumentType.STOCK.value).strip().lower())
        if self.option_type is not None and not isinstance(self.option_type, OptionRight):
            self.option_type = OptionRight(str(self.option_type).strip().lower())
        self.expiry = _parse_datetime(self.expiry)
        if self.strike is not None:
            self.strike = float(self.strike)
        if self.contract_size is not None:
            self.contract_size = int(self.contract_size)
        self.multiplier = float(self.multiplier or 1.0)
        if self.underlying:
            self.underlying = str(self.underlying).strip().upper()
        if self.exchange:
            self.exchange = str(self.exchange).strip().lower()
        if self.broker_hint:
            self.broker_hint = str(self.broker_hint).strip().lower()

    @property
    def is_derivative(self) -> bool:
        return self.type in {InstrumentType.OPTION, InstrumentType.FUTURE}

    @property
    def root_symbol(self) -> str:
        if self.underlying:
            return self.underlying
        return self.symbol.split(" ", 1)[0].split("/", 1)[0]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = self.type.value
        payload["option_type"] = self.option_type.value if self.option_type is not None else None
        payload["expiry"] = self.expiry.isoformat() if self.expiry is not None else None
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "Instrument") -> "Instrument":
        if isinstance(value, Instrument):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("Instrument payload must be a mapping")
        return cls(
            symbol=value.get("symbol") or value.get("underlyingSymbol") or value.get("localSymbol"),
            type=value.get("type") or value.get("instrument_type") or InstrumentType.STOCK.value,
            expiry=value.get("expiry") or value.get("expiration") or value.get("expirationDate"),
            strike=value.get("strike"),
            option_type=value.get("option_type") or value.get("right") or value.get("putCall"),
            contract_size=value.get("contract_size") or value.get("contractSize"),
            exchange=value.get("exchange"),
            currency=value.get("currency") or "USD",
            multiplier=value.get("multiplier") or value.get("contract_multiplier") or 1.0,
            underlying=value.get("underlying") or value.get("underlyingSymbol"),
            broker_hint=value.get("broker_hint") or value.get("broker"),
            metadata=dict(value.get("metadata") or {}),
        )
