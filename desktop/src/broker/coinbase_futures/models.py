from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _datetime(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


class CoinbaseConfig(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True, str_strip_whitespace=True)

    api_key: str
    api_secret: str = Field(..., alias="secret")
    rest_url: str = "https://api.coinbase.com"
    ws_url: str = "wss://advanced-trade-ws.coinbase.com"
    timeout_seconds: float = 20.0
    max_retries: int = 3
    rate_limit_per_second: float = 8.0
    product_cache_ttl_seconds: float = 300.0
    product_refresh_interval_seconds: float = 300.0
    ws_reconnect_delay_seconds: float = 1.0
    ws_max_reconnect_delay_seconds: float = 30.0
    ws_heartbeat_seconds: float = 30.0
    jwt_ttl_seconds: int = 120
    jwt_issuer: str | None = "coinbase-cloud"
    default_contract_size: float = 1.0
    default_initial_margin_ratio: float = 0.1
    min_available_margin_ratio: float = 0.05
    max_order_contracts: float | None = None
    max_order_notional: float | None = None
    account_id: str | None = None
    portfolio_id: str | None = None
    customer_region: str | None = None

    @field_validator("rest_url", "ws_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return str(value or "").rstrip("/")

    @field_validator(
        "timeout_seconds",
        "rate_limit_per_second",
        "product_cache_ttl_seconds",
        "product_refresh_interval_seconds",
        "ws_reconnect_delay_seconds",
        "ws_max_reconnect_delay_seconds",
        "ws_heartbeat_seconds",
        "default_contract_size",
        "default_initial_margin_ratio",
        "min_available_margin_ratio",
    )
    @classmethod
    def _positive_float(cls, value: float) -> float:
        numeric = float(value)
        if numeric <= 0:
            raise ValueError("value must be positive")
        return numeric

    @field_validator("jwt_ttl_seconds", "max_retries")
    @classmethod
    def _positive_int(cls, value: int) -> int:
        numeric = int(value)
        if numeric < 0:
            raise ValueError("value must be non-negative")
        return numeric

    @classmethod
    def from_broker_config(cls, config: Any) -> "CoinbaseConfig":
        if isinstance(config, CoinbaseConfig):
            return config

        if isinstance(config, Mapping):
            options = dict(config.get("options") or {})
            params = dict(config.get("params") or {})
            payload = {
                "api_key": config.get("api_key") or options.get("api_key") or params.get("api_key"),
                "api_secret": (
                    config.get("api_secret")
                    or config.get("secret")
                    or options.get("api_secret")
                    or options.get("secret")
                    or params.get("api_secret")
                    or params.get("secret")
                ),
                "rest_url": config.get("rest_url") or options.get("rest_url") or params.get("rest_url") or options.get("base_url"),
                "ws_url": config.get("ws_url") or options.get("ws_url") or params.get("ws_url"),
                "timeout_seconds": config.get("timeout_seconds") or options.get("timeout_seconds") or params.get("timeout_seconds") or config.get("timeout"),
                "max_retries": config.get("max_retries") or options.get("max_retries") or params.get("max_retries"),
                "rate_limit_per_second": config.get("rate_limit_per_second") or options.get("rate_limit_per_second") or params.get("rate_limit_per_second"),
                "product_cache_ttl_seconds": config.get("product_cache_ttl_seconds") or options.get("product_cache_ttl_seconds") or params.get("product_cache_ttl_seconds"),
                "product_refresh_interval_seconds": config.get("product_refresh_interval_seconds") or options.get("product_refresh_interval_seconds") or params.get("product_refresh_interval_seconds"),
                "ws_reconnect_delay_seconds": config.get("ws_reconnect_delay_seconds") or options.get("ws_reconnect_delay_seconds") or params.get("ws_reconnect_delay_seconds"),
                "ws_max_reconnect_delay_seconds": config.get("ws_max_reconnect_delay_seconds") or options.get("ws_max_reconnect_delay_seconds") or params.get("ws_max_reconnect_delay_seconds"),
                "ws_heartbeat_seconds": config.get("ws_heartbeat_seconds") or options.get("ws_heartbeat_seconds") or params.get("ws_heartbeat_seconds"),
                "jwt_ttl_seconds": config.get("jwt_ttl_seconds") or options.get("jwt_ttl_seconds") or params.get("jwt_ttl_seconds"),
                "jwt_issuer": config.get("jwt_issuer") or options.get("jwt_issuer") or params.get("jwt_issuer"),
                "default_contract_size": config.get("default_contract_size") or options.get("default_contract_size") or params.get("default_contract_size"),
                "default_initial_margin_ratio": config.get("default_initial_margin_ratio") or options.get("default_initial_margin_ratio") or params.get("default_initial_margin_ratio"),
                "min_available_margin_ratio": config.get("min_available_margin_ratio") or options.get("min_available_margin_ratio") or params.get("min_available_margin_ratio"),
                "max_order_contracts": config.get("max_order_contracts") or options.get("max_order_contracts") or params.get("max_order_contracts"),
                "max_order_notional": config.get("max_order_notional") or options.get("max_order_notional") or params.get("max_order_notional"),
                "account_id": config.get("account_id") or options.get("account_id") or params.get("account_id"),
                "portfolio_id": config.get("portfolio_id") or options.get("portfolio_id") or params.get("portfolio_id"),
                "customer_region": config.get("customer_region") or options.get("customer_region") or params.get("customer_region"),
            }
            compact_payload = {key: value for key, value in payload.items() if value not in (None, "")}
            return cls.model_validate(compact_payload)

        options = dict(getattr(config, "options", None) or {})
        params = dict(getattr(config, "params", None) or {})
        payload = {
            "api_key": getattr(config, "api_key", None) or options.get("api_key") or params.get("api_key"),
            "api_secret": (
                getattr(config, "api_secret", None)
                or getattr(config, "secret", None)
                or options.get("api_secret")
                or options.get("secret")
                or params.get("api_secret")
                or params.get("secret")
            ),
            "rest_url": options.get("rest_url") or params.get("rest_url") or options.get("base_url"),
            "ws_url": options.get("ws_url") or params.get("ws_url"),
            "timeout_seconds": options.get("timeout_seconds") or params.get("timeout_seconds") or getattr(config, "timeout", None),
            "max_retries": options.get("max_retries") or params.get("max_retries"),
            "rate_limit_per_second": options.get("rate_limit_per_second") or params.get("rate_limit_per_second"),
            "product_cache_ttl_seconds": options.get("product_cache_ttl_seconds") or params.get("product_cache_ttl_seconds"),
            "product_refresh_interval_seconds": options.get("product_refresh_interval_seconds") or params.get("product_refresh_interval_seconds"),
            "ws_reconnect_delay_seconds": options.get("ws_reconnect_delay_seconds") or params.get("ws_reconnect_delay_seconds"),
            "ws_max_reconnect_delay_seconds": options.get("ws_max_reconnect_delay_seconds") or params.get("ws_max_reconnect_delay_seconds"),
            "ws_heartbeat_seconds": options.get("ws_heartbeat_seconds") or params.get("ws_heartbeat_seconds"),
            "jwt_ttl_seconds": options.get("jwt_ttl_seconds") or params.get("jwt_ttl_seconds"),
            "jwt_issuer": options.get("jwt_issuer") or params.get("jwt_issuer"),
            "default_contract_size": options.get("default_contract_size") or params.get("default_contract_size"),
            "default_initial_margin_ratio": options.get("default_initial_margin_ratio") or params.get("default_initial_margin_ratio"),
            "min_available_margin_ratio": options.get("min_available_margin_ratio") or params.get("min_available_margin_ratio"),
            "max_order_contracts": options.get("max_order_contracts") or params.get("max_order_contracts"),
            "max_order_notional": options.get("max_order_notional") or params.get("max_order_notional"),
            "account_id": getattr(config, "account_id", None) or options.get("account_id") or params.get("account_id"),
            "portfolio_id": options.get("portfolio_id") or params.get("portfolio_id"),
            "customer_region": options.get("customer_region") or params.get("customer_region"),
        }
        compact_payload = {key: value for key, value in payload.items() if value not in (None, "")}
        return cls.model_validate(compact_payload)


class ProductStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class CoinbaseFuturesProduct:
    product_id: str
    normalized_symbol: str
    native_symbol: str
    base_currency: str
    quote_currency: str
    settlement_currency: str
    contract_expiry_type: str
    contract_size: float
    status: ProductStatus = ProductStatus.UNKNOWN
    expiry: datetime | None = None
    display_name: str | None = None
    product_venue: str | None = None
    price_increment: float | None = None
    size_increment: float | None = None
    last_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_perpetual(self) -> bool:
        return self.contract_expiry_type.upper() == "PERPETUAL"

    @property
    def is_tradable(self) -> bool:
        return self.status == ProductStatus.ONLINE

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["expiry"] = self.expiry.isoformat() if self.expiry is not None else None
        return payload


@dataclass(slots=True)
class TickerEvent:
    symbol: str
    product_id: str
    price: float
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    timestamp: str | None = None
    exchange: str = "coinbase_futures"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OrderBookLevel:
    price: float
    size: float

    def to_dict(self) -> dict[str, float]:
        return {"price": self.price, "size": self.size}


@dataclass(slots=True)
class OrderBookEvent:
    symbol: str
    product_id: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: str | None = None
    sequence_num: int | None = None
    exchange: str = "coinbase_futures"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "product_id": self.product_id,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "timestamp": self.timestamp,
            "sequence_num": self.sequence_num,
            "exchange": self.exchange,
            "raw": dict(self.raw or {}),
        }


@dataclass(slots=True)
class BalanceSnapshot:
    equity: float
    cash: float
    available_margin: float
    buying_power: float
    unrealized_pnl: float = 0.0
    exchange: str = "coinbase_futures"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["free"] = {"USD": self.available_margin}
        payload["cash"] = self.cash
        return payload


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    product_id: str
    side: str
    contracts: float
    entry_price: float | None = None
    mark_price: float | None = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    expiry: str | None = None
    exchange: str = "coinbase_futures"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["amount"] = self.contracts
        payload["quantity"] = self.contracts
        payload["position_side"] = self.side
        return payload


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: str
    size: float
    order_type: str = "market"
    price: float | None = None
    client_order_id: str | None = None
    time_in_force: str = "GTC"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OrderResult:
    order_id: str
    symbol: str
    product_id: str
    side: str
    order_type: str
    size: float
    status: str
    price: float | None = None
    client_order_id: str | None = None
    exchange: str = "coinbase_futures"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["amount"] = self.size
        payload["quantity"] = self.size
        payload["type"] = self.order_type
        payload["id"] = self.order_id
        return payload


def coerce_product_status(raw_product: Mapping[str, Any]) -> ProductStatus:
    trading_disabled = raw_product.get("trading_disabled")
    if isinstance(trading_disabled, bool):
        return ProductStatus.OFFLINE if trading_disabled else ProductStatus.ONLINE

    cancel_only = raw_product.get("cancel_only")
    if isinstance(cancel_only, bool) and cancel_only:
        return ProductStatus.OFFLINE

    status_text = _text(
        raw_product.get("status")
        or raw_product.get("trading_disabled")
        or raw_product.get("product_status")
    ).lower()
    if status_text in {"online", "active", "tradable"}:
        return ProductStatus.ONLINE
    if status_text in {"offline", "paused"}:
        return ProductStatus.OFFLINE
    if status_text in {"expired", "view_only"}:
        return ProductStatus.EXPIRED
    return ProductStatus.UNKNOWN


def product_from_api_payload(raw_product: Mapping[str, Any], normalized_symbol: str) -> CoinbaseFuturesProduct:
    future_details = raw_product.get("future_product_details")
    future_details = future_details if isinstance(future_details, Mapping) else {}
    settlement_currency = _text(
        raw_product.get("settlement_currency_id")
        or future_details.get("settlement_currency_id")
        or raw_product.get("quote_currency_id")
        or raw_product.get("quote_currency")
    ).upper() or "USD"
    contract_size = _float(
        raw_product.get("contract_size")
        or future_details.get("contract_size")
        or raw_product.get("future_contract_size")
        or 1.0,
        default=1.0,
    )
    return CoinbaseFuturesProduct(
        product_id=_text(raw_product.get("product_id") or raw_product.get("id")).upper(),
        native_symbol=_text(raw_product.get("product_id") or raw_product.get("id")).upper(),
        normalized_symbol=_text(normalized_symbol).upper(),
        base_currency=_text(raw_product.get("base_currency_id") or raw_product.get("base_currency")).upper(),
        quote_currency=_text(raw_product.get("quote_currency_id") or raw_product.get("quote_currency")).upper() or settlement_currency,
        settlement_currency=settlement_currency,
        contract_expiry_type=_text(
            future_details.get("contract_expiry_type") or raw_product.get("contract_expiry_type")
        ).upper() or "EXPIRING",
        contract_size=contract_size,
        status=coerce_product_status(raw_product),
        expiry=_datetime(
            future_details.get("expiration_time")
            or raw_product.get("expiration_time")
            or raw_product.get("expiry_time")
        ),
        display_name=_optional_text(raw_product.get("display_name")),
        product_venue=_optional_text(raw_product.get("product_venue")),
        price_increment=_float(raw_product.get("price_increment"), default=0.0) or None,
        size_increment=_float(raw_product.get("base_increment"), default=0.0) or None,
        last_price=_float(raw_product.get("price"), default=0.0) or None,
        metadata=dict(raw_product),
    )


__all__ = [
    "BalanceSnapshot",
    "CoinbaseConfig",
    "CoinbaseFuturesProduct",
    "OrderBookEvent",
    "OrderBookLevel",
    "OrderRequest",
    "OrderResult",
    "PositionSnapshot",
    "ProductStatus",
    "TickerEvent",
    "coerce_product_status",
    "product_from_api_payload",
]
