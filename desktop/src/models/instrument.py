from __future__ import annotations

"""
InvestPro Instrument Model

Canonical multi-asset instrument representation.

Supports:
- stocks
- ETFs
- options
- futures
- forex
- crypto
- crypto perpetuals
- CFDs
- indices

Designed to normalize broker/exchange payloads from:
- Alpaca
- OANDA
- Coinbase
- Binance/CCXT
- Interactive Brokers
- MetaTrader 4/5 bridges
"""

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional


class InstrumentType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    OPTION = "option"
    FUTURE = "future"
    FUTURE_OPTION = "future_option"
    FOREX = "forex"
    CRYPTO = "crypto"
    CRYPTO_PERP = "crypto_perp"
    CFD = "cfd"
    INDEX = "index"
    CASH = "cash"
    UNKNOWN = "unknown"


class OptionRight(str, Enum):
    CALL = "call"
    PUT = "put"


class SettlementType(str, Enum):
    PHYSICAL = "physical"
    CASH = "cash"
    UNKNOWN = "unknown"


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        try:
            number = float(value)
            if abs(number) > 1e11:
                number = number / 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except Exception:
            return None

    text = str(value).strip()
    if not text:
        return None

    # Common broker formats: 20260425, 2026-04-25, 2026-04-25T00:00:00Z
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def _optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _normalize_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_exchange(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    return text or None


def _coerce_instrument_type(value: Any) -> InstrumentType:
    text = str(value or "").strip().lower()

    aliases = {
        "equity": InstrumentType.STOCK,
        "stock": InstrumentType.STOCK,
        "stocks": InstrumentType.STOCK,
        "share": InstrumentType.STOCK,
        "shares": InstrumentType.STOCK,
        "etf": InstrumentType.ETF,
        "option": InstrumentType.OPTION,
        "options": InstrumentType.OPTION,
        "opt": InstrumentType.OPTION,
        "future": InstrumentType.FUTURE,
        "futures": InstrumentType.FUTURE,
        "fut": InstrumentType.FUTURE,
        "future_option": InstrumentType.FUTURE_OPTION,
        "fop": InstrumentType.FUTURE_OPTION,
        "forex": InstrumentType.FOREX,
        "fx": InstrumentType.FOREX,
        "currency": InstrumentType.FOREX,
        "crypto": InstrumentType.CRYPTO,
        "spot": InstrumentType.CRYPTO,
        "perp": InstrumentType.CRYPTO_PERP,
        "perpetual": InstrumentType.CRYPTO_PERP,
        "swap": InstrumentType.CRYPTO_PERP,
        "crypto_perp": InstrumentType.CRYPTO_PERP,
        "cfd": InstrumentType.CFD,
        "index": InstrumentType.INDEX,
        "cash": InstrumentType.CASH,
    }

    if text in aliases:
        return aliases[text]

    try:
        return InstrumentType(text)
    except Exception:
        return InstrumentType.UNKNOWN


def _coerce_option_right(value: Any) -> Optional[OptionRight]:
    if value in (None, ""):
        return None

    text = str(value).strip().lower()

    aliases = {
        "c": OptionRight.CALL,
        "call": OptionRight.CALL,
        "calls": OptionRight.CALL,
        "p": OptionRight.PUT,
        "put": OptionRight.PUT,
        "puts": OptionRight.PUT,
    }

    if text in aliases:
        return aliases[text]

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
    quote_currency: Optional[str] = None
    base_currency: Optional[str] = None

    multiplier: float = 1.0
    tick_size: Optional[float] = None
    lot_size: Optional[float] = None
    min_notional: Optional[float] = None

    underlying: Optional[str] = None
    broker_hint: Optional[str] = None
    broker_symbol: Optional[str] = None
    venue_id: Optional[str] = None

    settlement: SettlementType = SettlementType.UNKNOWN
    marginable: bool = True
    shortable: bool = True
    active: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        if not self.symbol:
            raise ValueError("Instrument symbol is required")

        self.type = _coerce_instrument_type(self.type)
        self.option_type = _coerce_option_right(self.option_type)
        self.expiry = _parse_datetime(self.expiry)

        self.strike = _optional_float(self.strike)
        self.contract_size = _optional_int(self.contract_size)

        self.exchange = _normalize_exchange(self.exchange)
        self.currency = str(self.currency or "USD").strip().upper() or "USD"

        if self.quote_currency:
            self.quote_currency = str(
                self.quote_currency).strip().upper() or None
        if self.base_currency:
            self.base_currency = str(
                self.base_currency).strip().upper() or None

        self.multiplier = float(self.multiplier or 1.0)
        if not math.isfinite(self.multiplier) or self.multiplier <= 0:
            self.multiplier = 1.0

        self.tick_size = _optional_float(self.tick_size)
        self.lot_size = _optional_float(self.lot_size)
        self.min_notional = _optional_float(self.min_notional)

        if self.underlying:
            self.underlying = _normalize_symbol(self.underlying)
        if self.broker_hint:
            self.broker_hint = str(self.broker_hint).strip().lower() or None
        if self.broker_symbol:
            self.broker_symbol = str(self.broker_symbol).strip() or None
        if self.venue_id:
            self.venue_id = str(self.venue_id).strip() or None

        if not isinstance(self.settlement, SettlementType):
            try:
                self.settlement = SettlementType(
                    str(self.settlement or "").strip().lower())
            except Exception:
                self.settlement = SettlementType.UNKNOWN

        self.marginable = bool(self.marginable)
        self.shortable = bool(self.shortable)
        self.active = bool(self.active)
        self.metadata = dict(self.metadata or {})

        self._infer_base_quote()
        self._infer_underlying_for_derivative()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_derivative(self) -> bool:
        return self.type in {
            InstrumentType.OPTION,
            InstrumentType.FUTURE,
            InstrumentType.FUTURE_OPTION,
            InstrumentType.CRYPTO_PERP,
            InstrumentType.CFD,
        }

    @property
    def is_option(self) -> bool:
        return self.type in {InstrumentType.OPTION, InstrumentType.FUTURE_OPTION}

    @property
    def is_future_like(self) -> bool:
        return self.type in {InstrumentType.FUTURE, InstrumentType.FUTURE_OPTION, InstrumentType.CRYPTO_PERP}

    @property
    def is_spot(self) -> bool:
        return self.type in {InstrumentType.STOCK, InstrumentType.ETF, InstrumentType.FOREX, InstrumentType.CRYPTO, InstrumentType.CASH}

    @property
    def root_symbol(self) -> str:
        if self.underlying:
            return self.underlying

        symbol = self.symbol

        if "/" in symbol:
            return symbol.split("/", 1)[0]

        if "_" in symbol:
            return symbol.split("_", 1)[0]

        if "-" in symbol:
            return symbol.split("-", 1)[0]

        if " " in symbol:
            return symbol.split(" ", 1)[0]

        return symbol

    @property
    def contract_multiplier(self) -> float:
        if self.contract_size and self.contract_size > 0:
            return float(self.contract_size) * float(self.multiplier)
        return float(self.multiplier)

    @property
    def display_symbol(self) -> str:
        if self.broker_symbol:
            return self.broker_symbol
        return self.symbol

    @property
    def expiry_date(self) -> Optional[date]:
        return self.expiry.date() if self.expiry is not None else None

    @property
    def canonical_key(self) -> str:
        parts = [
            self.type.value,
            self.symbol,
            self.exchange or "",
            self.currency,
            self.expiry.isoformat() if self.expiry else "",
            str(self.strike or ""),
            self.option_type.value if self.option_type else "",
        ]
        return "|".join(parts)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _infer_base_quote(self) -> None:
        if self.base_currency and self.quote_currency:
            return

        symbol = self.symbol

        if "/" in symbol:
            base, quote = symbol.split("/", 1)
            quote = quote.split(":", 1)[0]
            self.base_currency = self.base_currency or base.strip().upper()
            self.quote_currency = self.quote_currency or quote.strip().upper()
            return

        if "_" in symbol and self.type in {InstrumentType.CRYPTO, InstrumentType.CRYPTO_PERP, InstrumentType.FOREX}:
            base, quote = symbol.split("_", 1)
            self.base_currency = self.base_currency or base.strip().upper()
            self.quote_currency = self.quote_currency or quote.strip().upper()
            return

        if self.type == InstrumentType.FOREX and len(symbol) == 6:
            self.base_currency = self.base_currency or symbol[:3]
            self.quote_currency = self.quote_currency or symbol[3:]
            return

    def _infer_underlying_for_derivative(self) -> None:
        if self.underlying:
            return

        if self.type in {InstrumentType.OPTION, InstrumentType.FUTURE, InstrumentType.FUTURE_OPTION, InstrumentType.CRYPTO_PERP}:
            self.underlying = self.root_symbol

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def notional_value(self, quantity: float, price: float) -> float:
        return abs(float(quantity or 0.0) * float(price or 0.0) * self.contract_multiplier)

    def normalize_quantity(self, quantity: float) -> float:
        qty = float(quantity or 0.0)

        if self.lot_size is None or self.lot_size <= 0:
            return qty

        return math.floor(qty / self.lot_size) * self.lot_size

    def normalize_price(self, price: float) -> float:
        value = float(price or 0.0)

        if self.tick_size is None or self.tick_size <= 0:
            return value

        return round(round(value / self.tick_size) * self.tick_size, 12)

    def has_valid_option_fields(self) -> bool:
        if not self.is_option:
            return True
        return self.expiry is not None and self.strike is not None and self.option_type is not None

    def with_metadata(self, **metadata: Any) -> "Instrument":
        payload = self.to_dict()
        payload["metadata"] = {**dict(self.metadata or {}), **metadata}
        return Instrument.from_mapping(payload)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = self.type.value
        payload["option_type"] = self.option_type.value if self.option_type is not None else None
        payload["expiry"] = self.expiry.isoformat(
        ) if self.expiry is not None else None
        payload["settlement"] = self.settlement.value
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "Instrument") -> "Instrument":
        if isinstance(value, Instrument):
            return value

        if not isinstance(value, Mapping):
            raise TypeError("Instrument payload must be a mapping")

        metadata = dict(value.get("metadata") or {})

        symbol = (
            value.get("symbol")
            or value.get("underlyingSymbol")
            or value.get("underlying_symbol")
            or value.get("localSymbol")
            or value.get("local_symbol")
            or value.get("pair")
            or value.get("instrument")
            or value.get("name")
        )

        return cls(
            symbol=symbol,
            type=(
                value.get("type")
                or value.get("instrument_type")
                or value.get("asset_class")
                or value.get("secType")
                or value.get("security_type")
                or InstrumentType.STOCK.value
            ),
            expiry=(
                value.get("expiry")
                or value.get("expiration")
                or value.get("expirationDate")
                or value.get("expiration_date")
                or value.get("lastTradeDateOrContractMonth")
            ),
            strike=value.get("strike") or value.get("strike_price"),
            option_type=(
                value.get("option_type")
                or value.get("right")
                or value.get("putCall")
                or value.get("put_call")
            ),
            contract_size=value.get(
                "contract_size") or value.get("contractSize"),
            exchange=value.get("exchange") or value.get(
                "primaryExchange") or value.get("venue"),
            currency=value.get("currency") or value.get(
                "quote_currency") or "USD",
            quote_currency=value.get(
                "quote_currency") or value.get("quoteCurrency"),
            base_currency=value.get(
                "base_currency") or value.get("baseCurrency"),
            multiplier=value.get("multiplier") or value.get(
                "contract_multiplier") or 1.0,
            tick_size=value.get("tick_size") or value.get(
                "min_tick") or value.get("price_increment"),
            lot_size=value.get("lot_size") or value.get(
                "min_qty") or value.get("quantity_increment"),
            min_notional=value.get(
                "min_notional") or value.get("min_order_value"),
            underlying=value.get("underlying") or value.get(
                "underlyingSymbol") or value.get("root"),
            broker_hint=value.get("broker_hint") or value.get("broker"),
            broker_symbol=value.get("broker_symbol") or value.get(
                "localSymbol") or value.get("local_symbol"),
            venue_id=value.get("venue_id") or value.get(
                "conId") or value.get("instrument_id"),
            settlement=value.get("settlement") or SettlementType.UNKNOWN.value,
            marginable=value.get("marginable", True),
            shortable=value.get("shortable", True),
            active=value.get("active", True),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def stock(cls, symbol: str, *, exchange: str | None = None, currency: str = "USD", **metadata: Any) -> "Instrument":
        return cls(
            symbol=symbol,
            type=InstrumentType.STOCK,
            exchange=exchange,
            currency=currency,
            metadata=metadata,
        )

    @classmethod
    def crypto(cls, symbol: str, *, exchange: str | None = None, **metadata: Any) -> "Instrument":
        return cls(
            symbol=symbol,
            type=InstrumentType.CRYPTO,
            exchange=exchange,
            metadata=metadata,
        )

    @classmethod
    def forex(cls, symbol: str, *, broker_hint: str | None = None, **metadata: Any) -> "Instrument":
        return cls(
            symbol=symbol,
            type=InstrumentType.FOREX,
            broker_hint=broker_hint,
            metadata=metadata,
        )

    @classmethod
    def option(
        cls,
        underlying: str,
        *,
        expiry: Any,
        strike: float,
        option_type: str | OptionRight,
        exchange: str | None = None,
        currency: str = "USD",
        multiplier: float = 100.0,
        **metadata: Any,
    ) -> "Instrument":
        right = _coerce_option_right(option_type)
        if right is None:
            raise ValueError("option_type must be call or put")

        exp = _parse_datetime(expiry)
        exp_text = exp.strftime("%Y%m%d") if exp else str(expiry)

        symbol = f"{_normalize_symbol(underlying)} {exp_text} {right.value.upper()} {float(strike):g}"

        return cls(
            symbol=symbol,
            type=InstrumentType.OPTION,
            expiry=expiry,
            strike=strike,
            option_type=right,
            exchange=exchange,
            currency=currency,
            multiplier=multiplier,
            underlying=underlying,
            metadata=metadata,
        )

    @classmethod
    def future(
        cls,
        symbol: str,
        *,
        expiry: Any = None,
        exchange: str | None = None,
        multiplier: float = 1.0,
        **metadata: Any,
    ) -> "Instrument":
        return cls(
            symbol=symbol,
            type=InstrumentType.FUTURE,
            expiry=expiry,
            exchange=exchange,
            multiplier=multiplier,
            metadata=metadata,
        )

    @classmethod
    def crypto_perp(
        cls,
        symbol: str,
        *,
        exchange: str | None = None,
        multiplier: float = 1.0,
        **metadata: Any,
    ) -> "Instrument":
        return cls(
            symbol=symbol,
            type=InstrumentType.CRYPTO_PERP,
            exchange=exchange,
            multiplier=multiplier,
            metadata=metadata,
        )
