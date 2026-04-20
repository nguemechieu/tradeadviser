"""Market bounded-context contracts shared by desktop and server.

Market data services own the truth for ticks, candles, and order books. Desktop
and server both consume the same DTOs so visualization and strategy logic can
stay decoupled from venue SDKs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import AssetClass, MarketStatus, MarketType, VenueKind


class MarketCommandName(str, Enum):
    SUBSCRIBE_MARKET_DATA_V1 = "market.subscribe.v1"
    UNSUBSCRIBE_MARKET_DATA_V1 = "market.unsubscribe.v1"
    REQUEST_MARKET_SNAPSHOT_V1 = "market.snapshot.request.v1"


class MarketEventName(str, Enum):
    MARKET_TICK_V1 = "market.tick.v1"
    MARKET_CANDLE_CLOSED_V1 = "market.candle.closed.v1"
    MARKET_ORDER_BOOK_UPDATED_V1 = "market.order_book.updated.v1"
    MARKET_REGIME_UPDATED_V1 = "market.regime.updated.v1"


class InstrumentRef(ContractModel):
    """Canonical instrument reference shared across runtime boundaries."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    asset_class: AssetClass = AssetClass.UNKNOWN
    market_type: MarketType = MarketType.UNKNOWN
    base_asset: str | None = None
    quote_asset: str | None = None
    tick_size: float | None = None
    lot_size: float | None = None
    contract_size: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PriceLevel(ContractModel):
    """Normalized order-book level from the market data source of truth."""

    price: float
    size: float
    order_count: int | None = None


class MarketTick(ContractModel):
    """Best-effort market tick owned by the market data layer."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    bid: float | None = None
    ask: float | None = None
    last_price: float
    last_size: float | None = None
    spread: float | None = None
    mid_price: float | None = None
    market_status: MarketStatus = MarketStatus.UNKNOWN
    timestamp: datetime = Field(default_factory=utc_now)


class Candle(ContractModel):
    """OHLCV candle that can be consumed by desktop charts and server logic."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    timeframe: str = Field(min_length=1)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    open_interest: float | None = None
    start_at: datetime
    end_at: datetime
    finalized: bool = True


class OrderBookSnapshot(ContractModel):
    """Order-book snapshot owned by the market data source."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    depth: int = 10
    bids: list[PriceLevel] = Field(default_factory=list)
    asks: list[PriceLevel] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)


class MarketRegimeSnapshot(ContractModel):
    """Shared market regime label derived from market and feature inputs."""

    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    confidence: float = 0.0
    volatility: float | None = None
    trend: str | None = None
    liquidity_state: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketSnapshot(ContractModel):
    """Composite market payload for request-response style consumers."""

    instrument: InstrumentRef
    tick: MarketTick | None = None
    candle: Candle | None = None
    order_book: OrderBookSnapshot | None = None
    regime: MarketRegimeSnapshot | None = None


class SubscribeMarketDataCommand(ContractModel):
    """Request to start publishing market data for the given symbols."""

    symbols: list[str] = Field(min_length=1)
    timeframes: list[str] = Field(default_factory=list)
    include_order_book: bool = False
    depth: int = 10


class UnsubscribeMarketDataCommand(ContractModel):
    """Request to stop publishing market data for the given symbols."""

    symbols: list[str] = Field(min_length=1)


class RequestMarketSnapshotCommand(ContractModel):
    """Request the latest authoritative market snapshot for one instrument."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    timeframe: str | None = None

