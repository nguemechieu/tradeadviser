from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1e11:
            numeric = numeric / 1000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    return utc_now()


def normalize_horizon(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    if text in {"short", "medium", "long"}:
        return text
    return "medium"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(float(lower), min(float(upper), float(value)))


@dataclass(slots=True)
class TradeLifecycleState:
    trade_id: str
    symbol: str
    quantity: float
    entry_time: datetime
    entry_price: float
    current_price: float
    strategy_name: str
    expected_horizon: str = "medium"
    signal_expiry_time: datetime | None = None
    volatility_at_entry: float = 0.0
    signal_strength: float = 0.0
    asset_class: str = "unknown"
    regime: str = "UNKNOWN"
    status: str = "open"
    exit_time: datetime | None = None
    exit_reason: str | None = None
    last_update_time: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    alerts_emitted: set[str] = field(default_factory=set)
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_percent: float = 2.0
    reward_risk_ratio: float = 1.5

    def __post_init__(self) -> None:
        self.trade_id = str(self.trade_id or "").strip()
        self.symbol = str(self.symbol or "").strip().upper()
        self.quantity = float(self.quantity or 0.0)
        self.entry_time = coerce_datetime(self.entry_time)
        self.entry_price = float(self.entry_price or 0.0)
        self.current_price = float(self.current_price or self.entry_price or 0.0)
        self.strategy_name = str(self.strategy_name or "unknown").strip()
        self.expected_horizon = normalize_horizon(self.expected_horizon)
        self.signal_expiry_time = None if self.signal_expiry_time is None else coerce_datetime(self.signal_expiry_time)
        self.volatility_at_entry = max(0.0, float(self.volatility_at_entry or 0.0))
        self.signal_strength = clamp(float(self.signal_strength or 0.0), 0.0, 1.0)
        self.asset_class = str(self.asset_class or "unknown").strip() or "unknown"
        self.regime = str(self.regime or "UNKNOWN").strip().upper() or "UNKNOWN"
        self.status = str(self.status or "open").strip().lower()
        self.exit_time = None if self.exit_time is None else coerce_datetime(self.exit_time)
        self.last_update_time = coerce_datetime(self.last_update_time)
        self.risk_percent = max(0.1, min(10.0, float(self.risk_percent or 2.0)))
        self.reward_risk_ratio = max(0.5, float(self.reward_risk_ratio or 1.5))
        # Initialize SL/TP if not provided
        if self.stop_loss is None or self.take_profit is None:
            self._calculate_sl_tp()

    @property
    def duration(self) -> timedelta:
        effective_end = self.exit_time or self.last_update_time
        return max(timedelta(0), effective_end - self.entry_time)

    @property
    def pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        reference = abs(self.entry_price) * max(abs(self.quantity), 1e-12)
        if reference <= 0:
            return 0.0
        return self.pnl / reference

    @property
    def side(self) -> str:
        return "long" if self.quantity >= 0 else "short"

    def time_remaining(self, max_duration: timedelta) -> timedelta:
        return max(timedelta(0), max_duration - self.duration)

    def time_remaining_seconds(self, max_duration: timedelta) -> float:
        return self.time_remaining(max_duration).total_seconds()

    def _calculate_sl_tp(self) -> None:
        """Calculate SL/TP based on risk management rules."""
        if self.entry_price <= 0:
            return

        is_long = self.quantity >= 0
        stop_distance = self.entry_price * (self.risk_percent / 100.0)

        if is_long:
            # For long: SL below entry, TP above entry
            self.stop_loss = self.entry_price - stop_distance
            reward_distance = stop_distance * self.reward_risk_ratio
            self.take_profit = self.entry_price + reward_distance
        else:
            # For short: SL above entry, TP below entry
            self.stop_loss = self.entry_price + stop_distance
            reward_distance = stop_distance * self.reward_risk_ratio
            self.take_profit = self.entry_price - reward_distance

    def update_sl_tp(self, stop_loss: float | None = None, take_profit: float | None = None) -> None:
        """Update stop loss and take profit levels."""
        if stop_loss is not None and stop_loss > 0:
            self.stop_loss = float(stop_loss)
        if take_profit is not None and take_profit > 0:
            self.take_profit = float(take_profit)

    def adjust_sl_tp_for_breakeven(self) -> None:
        """Move SL to breakeven once profitable."""
        if self.entry_price <= 0:
            return

        is_long = self.quantity >= 0
        if is_long:
            if self.current_price > self.entry_price and self.stop_loss is not None:
                self.stop_loss = max(self.stop_loss, self.entry_price)
        else:
            if self.current_price < self.entry_price and self.stop_loss is not None:
                self.stop_loss = min(self.stop_loss, self.entry_price)

    def adjust_sl_tp_by_volatility(self, volatility: float) -> None:
        """Adjust SL/TP based on current volatility levels."""
        if self.entry_price <= 0 or volatility <= 0:
            return

        volatility_multiplier = volatility / max(self.volatility_at_entry, 0.01)
        is_long = self.quantity >= 0

        if is_long:
            if self.stop_loss is not None:
                sl_distance = self.entry_price - self.stop_loss
                adjusted_distance = sl_distance * volatility_multiplier
                self.stop_loss = self.entry_price - adjusted_distance
            if self.take_profit is not None:
                tp_distance = self.take_profit - self.entry_price
                adjusted_distance = tp_distance * volatility_multiplier
                self.take_profit = self.entry_price + adjusted_distance
        else:
            if self.stop_loss is not None:
                sl_distance = self.stop_loss - self.entry_price
                adjusted_distance = sl_distance * volatility_multiplier
                self.stop_loss = self.entry_price + adjusted_distance
            if self.take_profit is not None:
                tp_distance = self.entry_price - self.take_profit
                adjusted_distance = tp_distance * volatility_multiplier
                self.take_profit = self.entry_price - adjusted_distance

    def should_close_for_tp(self) -> bool:
        """Check if position should close at take profit."""
        if self.take_profit is None or self.entry_price <= 0:
            return False
        is_long = self.quantity >= 0
        return (is_long and self.current_price >= self.take_profit) or (not is_long and self.current_price <= self.take_profit)

    def should_close_for_sl(self) -> bool:
        """Check if position should close at stop loss."""
        if self.stop_loss is None or self.entry_price <= 0:
            return False
        is_long = self.quantity >= 0
        return (is_long and self.current_price <= self.stop_loss) or (not is_long and self.current_price >= self.stop_loss)

    def max_favorable_excursion(self) -> float:
        """Calculate maximum favorable price reached."""
        is_long = self.quantity >= 0
        if is_long:
            return max(self.entry_price, self.current_price)
        else:
            return min(self.entry_price, self.current_price)

    def max_adverse_excursion(self) -> float:
        """Calculate maximum adverse price reached."""
        is_long = self.quantity >= 0
        if is_long:
            return min(self.entry_price, self.current_price)
        else:
            return max(self.entry_price, self.current_price)

    def to_ui_payload(self, *, max_duration: timedelta | None = None, aging_score: float | None = None) -> dict[str, Any]:
        payload = {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "side": self.side,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_percent": self.risk_percent,
            "reward_risk_ratio": self.reward_risk_ratio,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "duration_seconds": self.duration.total_seconds(),
            "strategy_name": self.strategy_name,
            "expected_horizon": self.expected_horizon,
            "signal_expiry_time": self.signal_expiry_time.isoformat() if self.signal_expiry_time is not None else None,
            "volatility_at_entry": self.volatility_at_entry,
            "signal_strength": self.signal_strength,
            "regime": self.regime,
            "status": self.status,
            "should_close_tp": self.should_close_for_tp(),
            "should_close_sl": self.should_close_for_sl(),
            "time_remaining_seconds": None,
            "aging_score": aging_score,
            "metadata": dict(self.metadata),
        }
        if max_duration is not None:
            payload["time_remaining_seconds"] = self.time_remaining_seconds(max_duration)
            payload["max_duration_seconds"] = max_duration.total_seconds()
        return payload


@dataclass(slots=True)
class TradeLifecycleDecision:
    trade_id: str
    symbol: str
    action: str
    reason: str
    close_quantity: float
    regime: str
    pnl: float
    pnl_pct: float
    duration_seconds: float
    max_duration_seconds: float
    time_remaining_seconds: float
    aging_score: float
    risk_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

