from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Candle:
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    start: datetime = field(default_factory=utcnow)
    end: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class OrderBookSnapshot:
    symbol: str
    bids: list[tuple[float, float]] = field(default_factory=list)
    asks: list[tuple[float, float]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utcnow)


class SignalStatus:
    CREATED = "CREATED"
    FILTERED = "FILTERED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    CLOSED = "CLOSED"


@dataclass(slots=True)
class SignalConfidencePoint:
    stage: str
    confidence: float
    timestamp: datetime = field(default_factory=utcnow)
    note: str = ""


@dataclass(slots=True)
class Signal:
    symbol: str
    side: str
    quantity: float
    price: float
    confidence: float = 0.0
    strategy_name: str = "unknown"
    reason: str = ""
    stop_price: float | None = None
    take_profit: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: str(uuid4()))
    source_strategy: str = ""
    confidence_history: list[SignalConfidencePoint] = field(default_factory=list)
    status: str = SignalStatus.CREATED

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").strip()
        self.side = str(self.side or "").strip().lower()
        self.strategy_name = str(self.strategy_name or "unknown").strip() or "unknown"
        self.source_strategy = str(self.source_strategy or self.strategy_name).strip() or self.strategy_name
        self.status = str(self.status or SignalStatus.CREATED).strip().upper() or SignalStatus.CREATED
        self.confidence = float(self.confidence or 0.0)
        normalized_history: list[SignalConfidencePoint] = []
        for point in list(self.confidence_history or []):
            if isinstance(point, SignalConfidencePoint):
                normalized_history.append(point)
                continue
            try:
                normalized_history.append(SignalConfidencePoint(**dict(point or {})))
            except Exception:
                continue
        if not normalized_history:
            normalized_history.append(
                SignalConfidencePoint(
                    stage="created",
                    confidence=self.confidence,
                    timestamp=self.timestamp,
                    note=f"Signal created by {self.source_strategy}",
                )
            )
        self.confidence_history = normalized_history

    def clone(self, **changes: Any) -> "Signal":
        return replace(self, **changes)

    def transition(
        self,
        *,
        stage: str,
        status: str | None = None,
        confidence: float | None = None,
        note: str = "",
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> "Signal":
        next_confidence = float(self.confidence if confidence is None else confidence)
        next_metadata = {**dict(self.metadata or {}), **dict(metadata or {})}
        next_history = list(self.confidence_history or [])
        next_history.append(
            SignalConfidencePoint(
                stage=str(stage or "").strip().lower() or "updated",
                confidence=next_confidence,
                timestamp=timestamp or utcnow(),
                note=str(note or "").strip(),
            )
        )
        return self.clone(
            confidence=next_confidence,
            status=str(status or self.status or SignalStatus.CREATED).strip().upper(),
            metadata=next_metadata,
            confidence_history=next_history,
        )


@dataclass(slots=True)
class TradeReview:
    approved: bool
    symbol: str
    side: str
    quantity: float
    price: float
    reason: str
    risk_score: float = 0.0
    stop_price: float | None = None
    take_profit: float | None = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str = "market"
    stop_price: float | None = None
    take_profit: float | None = None
    strategy_name: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    order_id: str
    symbol: str
    side: str
    quantity: float
    requested_price: float | None
    fill_price: float | None
    status: str
    latency_ms: float
    slippage_bps: float = 0.0
    strategy_name: str = "unknown"
    stop_price: float | None = None
    take_profit: float | None = None
    filled_quantity: float | None = None
    remaining_quantity: float = 0.0
    partial: bool = False
    fee: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0
    last_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        if self.quantity == 0:
            return 0.0
        return (self.last_price - self.average_price) * self.quantity


@dataclass(slots=True)
class PortfolioSnapshot:
    cash: float
    equity: float
    positions: dict[str, Position] = field(default_factory=dict)
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class AnalystInsight:
    symbol: str
    regime: str
    momentum: float = 0.0
    volatility: float = 1.0
    preferred_strategy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class RegimeSnapshot:
    symbol: str
    timeframe: str
    regime: str
    volatility_regime: str = "unknown"
    trend_strength: float = 0.0
    momentum: float = 0.0
    band_position: float = 0.0
    atr_pct: float = 0.0
    cluster_id: int | None = None
    preferred_strategy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class PositionUpdate:
    symbol: str
    quantity: float
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    market_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class FeatureVector:
    symbol: str
    timeframe: str
    values: dict[str, float] = field(default_factory=dict)
    strategy_name: str = "market"
    close: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class ClosePositionRequest:
    symbol: str
    side: str
    quantity: float
    reason: str
    price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    strategy_name: str = "profit_protection_engine"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class ModelDecision:
    symbol: str
    strategy_name: str
    model_name: str
    probability: float
    threshold: float
    approved: bool
    side: str = ""
    features: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class ReasoningDecision:
    symbol: str
    strategy_name: str
    side: str
    decision: str
    confidence: float
    reasoning: str
    risk: str = "medium"
    regime: str = "unknown"
    model_probability: float | None = None
    warnings: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class TraderDecision:
    profile_id: str
    symbol: str
    action: str
    side: str
    quantity: float
    price: float
    confidence: float
    selected_strategy: str
    reasoning: str
    model_probability: float | None = None
    applied_constraints: list[str] = field(default_factory=list)
    votes: dict[str, float] = field(default_factory=dict)
    features: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class ProfitProtectionDecision:
    symbol: str
    action: str
    reason: str
    quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None
    unrealized_pnl: float = 0.0
    profit_pct: float = 0.0
    model_probability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class TradeFeedback:
    symbol: str
    strategy_name: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    success: bool
    timeframe: str = "1m"
    model_name: str | None = None
    model_probability: float | None = None
    features: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class TradeJournalEntry:
    symbol: str
    strategy_name: str
    side: str
    quantity: float
    pnl: float
    success: bool
    outcome: str
    summary: str
    why_it_lost: list[str] = field(default_factory=list)
    what_worked: list[str] = field(default_factory=list)
    what_to_improve: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confidence: float | None = None
    model_probability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class TradeJournalSummary:
    trades_analyzed: int
    wins: int
    losses: int
    win_rate: float
    average_pnl: float
    average_win: float
    average_loss: float
    recurring_loss_patterns: list[str] = field(default_factory=list)
    recurring_strengths: list[str] = field(default_factory=list)
    improvement_priorities: list[str] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class AlertEvent:
    alert_id: str
    title: str
    message: str
    severity: str
    category: str
    event_type: str
    symbol: str | None = None
    strategy_name: str | None = None
    action: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class MobileDashboardSnapshot:
    status: str = "ok"
    cash: float = 0.0
    equity: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    open_positions: int = 0
    latest_alert: dict[str, Any] = field(default_factory=dict)
    latest_decision: dict[str, Any] = field(default_factory=dict)
    latest_execution: dict[str, Any] = field(default_factory=dict)
    latest_performance: dict[str, Any] = field(default_factory=dict)
    latest_trade_journal_summary: dict[str, Any] = field(default_factory=dict)
    positions: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class PerformanceMetrics:
    total_trades: int = 0
    closed_trades: int = 0
    win_rate: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_like: float = 0.0
    symbols: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)
