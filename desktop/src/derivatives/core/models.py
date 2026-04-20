from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class DerivativesEvent:
    topic: str
    data: Any
    source: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class BrokerRoute:
    broker_key: str
    exchange: str
    account_id: str | None
    raw_symbol: str
    normalized_symbol: str
    market_type: str = "future"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MarketTicker:
    symbol: str
    exchange: str
    broker_key: str
    account_id: str | None
    price: float
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    raw_symbol: str | None = None
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class OrderBookSnapshot:
    symbol: str
    exchange: str
    broker_key: str
    account_id: str | None
    bids: list[tuple[float, float]] = field(default_factory=list)
    asks: list[tuple[float, float]] = field(default_factory=list)
    raw_symbol: str | None = None
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class MarketTrade:
    symbol: str
    exchange: str
    broker_key: str
    account_id: str | None
    side: str
    price: float
    size: float
    raw_symbol: str | None = None
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class TradingSignal:
    symbol: str
    side: str
    confidence: float
    size: float
    strategy_name: str
    exchange: str | None = None
    broker_key: str | None = None
    order_type: str = "market"
    limit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    duration: float = 3600.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class RiskAssessment:
    approved: bool
    symbol: str
    side: str
    approved_size: float
    confidence: float
    reason: str
    order_type: str = "market"
    limit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    broker_key: str | None = None
    exchange: str | None = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class OrderCommand:
    symbol: str
    side: str
    size: float
    broker_key: str
    exchange: str
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class ExecutionUpdate:
    order_id: str
    symbol: str
    side: str
    size: float
    broker_key: str
    exchange: str
    status: str
    fill_price: float | None = None
    requested_price: float | None = None
    fees: float = 0.0
    strategy_name: str = "unknown"
    account_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class PositionState:
    symbol: str
    broker_key: str
    exchange: str
    account_id: str | None
    quantity: float = 0.0
    entry_price: float = 0.0
    mark_price: float = 0.0
    leverage: float = 1.0
    used_margin: float = 0.0
    realized_pnl: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def market_value(self) -> float:
        return float(self.quantity) * float(self.mark_price)

    @property
    def unrealized_pnl(self) -> float:
        if self.quantity == 0:
            return 0.0
        return (float(self.mark_price) - float(self.entry_price)) * float(self.quantity)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["market_value"] = self.market_value
        payload["unrealized_pnl"] = self.unrealized_pnl
        return payload


@dataclass(slots=True)
class PortfolioState:
    equity: float
    cash: float
    free_margin: float
    used_margin: float
    positions: dict[str, PositionState] = field(default_factory=dict)
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    timestamp: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["positions"] = {key: value.to_dict() for key, value in self.positions.items()}
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class BacktestMetrics:
    total_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    ending_equity: float
    equity_curve: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
