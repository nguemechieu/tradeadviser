from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text


def _clean_lower(value: Any, default: str = "") -> str:
    return _clean_text(value, default).lower()


def _clean_upper(value: Any, default: str = "") -> str:
    return _clean_text(value, default).upper()


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception as ex:
        print(ex)
        return None


def _positive_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception as ec:
        number = float(default)
        print(ec)
    return max(0.0, number)


@dataclass(slots=True)
class HybridExecutionRequest:
    """Server/hybrid order execution request.

    This is the desktop-to-server payload used when AppController submits an order
    through hybrid server execution instead of local broker execution.
    """

    client_order_id: str
    broker: Any
    identifier: Any
    side: str
    order_type: str
    quantity: float

    limit_price: float | None = None
    stop_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None

    time_in_force: str = "gtc"
    source: str = "desktop"
    strategy_name: str = "Manual"
    reason: str = ""
    correlation_id: str = ""

    reduce_only: bool = False
    post_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.client_order_id = _clean_text(self.client_order_id)
        if not self.client_order_id:
            raise ValueError("client_order_id is required")

        self.side = _clean_lower(self.side)
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")

        self.order_type = _clean_lower(self.order_type or "market")
        if self.order_type not in {
            "market",
            "limit",
            "stop",
            "stop_limit",
            "take_profit",
            "take_profit_limit",
        }:
            raise ValueError(f"Unsupported order_type: {self.order_type}")

        self.quantity = _positive_float(self.quantity)
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        self.limit_price = _optional_float(self.limit_price)
        self.stop_price = _optional_float(self.stop_price)
        self.stop_loss = _optional_float(self.stop_loss)
        self.take_profit = _optional_float(self.take_profit)

        if self.order_type in {"limit", "stop_limit", "take_profit_limit"}:
            if self.limit_price is None or self.limit_price <= 0:
                raise ValueError(f"limit_price is required for {self.order_type} orders")

        if self.order_type in {"stop", "stop_limit"}:
            if self.stop_price is None or self.stop_price <= 0:
                raise ValueError(f"stop_price is required for {self.order_type} orders")

        self.time_in_force = _clean_lower(self.time_in_force or "gtc")
        self.source = _clean_lower(self.source or "desktop")
        self.strategy_name = _clean_text(self.strategy_name or "Manual")
        self.reason = _clean_text(self.reason)
        self.correlation_id = _clean_text(self.correlation_id)
        self.reduce_only = bool(self.reduce_only)
        self.post_only = bool(self.post_only)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if hasattr(value, "to_dict") and callable(value.to_dict):
                return value.to_dict()
            if hasattr(value, "model_dump") and callable(value.model_dump):
                return value.model_dump()
            if hasattr(value, "dict") and callable(value.dict):
                return value.dict()
            if hasattr(value, "__dataclass_fields__"):
                return asdict(value)
            return value

        return {
            "client_order_id": self.client_order_id,
            "broker": convert(self.broker),
            "identifier": convert(self.identifier),
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "time_in_force": self.time_in_force,
            "source": self.source,
            "strategy_name": self.strategy_name,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "reduce_only": self.reduce_only,
            "post_only": self.post_only,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HybridExecutionRequest":
        data = dict(payload or {})
        return cls(
            client_order_id=data.get("client_order_id") or data.get("clientOrderId") or "",
            broker=data.get("broker"),
            identifier=data.get("identifier"),
            side=data.get("side"),
            order_type=data.get("order_type") or data.get("orderType") or "market",
            quantity=data.get("quantity") or data.get("amount") or 0.0,
            limit_price=data.get("limit_price") or data.get("limitPrice"),
            stop_price=data.get("stop_price") or data.get("stopPrice"),
            stop_loss=data.get("stop_loss") or data.get("stopLoss"),
            take_profit=data.get("take_profit") or data.get("takeProfit"),
            time_in_force=data.get("time_in_force") or data.get("timeInForce") or "gtc",
            source=data.get("source") or "desktop",
            strategy_name=data.get("strategy_name") or data.get("strategyName") or "Manual",
            reason=data.get("reason") or "",
            correlation_id=data.get("correlation_id") or data.get("correlationId") or "",
            reduce_only=bool(data.get("reduce_only") or data.get("reduceOnly") or False),
            post_only=bool(data.get("post_only") or data.get("postOnly") or False),
            metadata=dict(data.get("metadata") or {}),
        )