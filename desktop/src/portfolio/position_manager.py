from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from portfolio.trade_lifecycle import TradeLifecycleState, coerce_datetime, normalize_horizon


@dataclass(slots=True)
class ManagedPosition:
    symbol: str
    asset_class: str = "unknown"
    quantity: float = 0.0
    average_price: float = 0.0
    last_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return float(self.quantity) * float(self.last_price)


class PositionManager:
    def __init__(self) -> None:
        self.positions: dict[str, ManagedPosition] = {}
        self.open_trades: dict[str, TradeLifecycleState] = {}
        self.closed_trades: deque[TradeLifecycleState] = deque(maxlen=256)
        self.latest_regimes: dict[str, str] = {}

    def mark_price(self, symbol: str, price: float, *, timestamp: datetime | None = None) -> None:
        key = str(symbol or "").strip().upper()
        if key not in self.positions:
            return
        self.positions[key].last_price = float(price or 0.0)
        trade = self.open_trades.get(key)
        if trade is not None:
            trade.current_price = float(price or 0.0)
            trade.last_update_time = coerce_datetime(timestamp)

    def update_fill(
        self,
        symbol: str,
        *,
        side: str,
        quantity: float,
        price: float,
        asset_class: str = "unknown",
        timestamp: datetime | None = None,
        trade_id: str | None = None,
        strategy_name: str = "unknown",
        expected_horizon: str = "medium",
        signal_expiry_time: datetime | None = None,
        volatility_at_entry: float = 0.0,
        signal_strength: float = 0.0,
        metadata: dict | None = None,
    ) -> ManagedPosition:
        key = str(symbol or "").strip().upper()
        signed = abs(float(quantity or 0.0)) * (1.0 if str(side).lower() == "buy" else -1.0)
        position = self.positions.setdefault(key, ManagedPosition(symbol=key, asset_class=asset_class))
        prior_quantity = float(position.quantity)
        if position.quantity == 0 or (position.quantity > 0) == (signed > 0):
            new_quantity = position.quantity + signed
            if new_quantity != 0:
                position.average_price = ((position.quantity * position.average_price) + (signed * float(price or 0.0))) / new_quantity
            position.quantity = new_quantity
        else:
            closing = min(abs(position.quantity), abs(signed))
            pnl_direction = 1.0 if position.quantity > 0 else -1.0
            position.realized_pnl += (float(price or 0.0) - position.average_price) * closing * pnl_direction
            position.quantity += signed
            if position.quantity == 0:
                position.average_price = 0.0
            elif (position.quantity > 0) != (signed > 0):
                position.average_price = float(price or 0.0)
        position.last_price = float(price or 0.0)
        position.asset_class = asset_class
        self._sync_trade_after_fill(
            key,
            position=position,
            prior_quantity=prior_quantity,
            timestamp=timestamp,
            trade_id=trade_id,
            strategy_name=strategy_name,
            expected_horizon=expected_horizon,
            signal_expiry_time=signal_expiry_time,
            volatility_at_entry=volatility_at_entry,
            signal_strength=signal_strength,
            metadata=metadata,
        )
        return position

    def open_trade(
        self,
        *,
        symbol: str,
        quantity: float,
        entry_price: float,
        entry_time: datetime | None = None,
        trade_id: str | None = None,
        strategy_name: str = "unknown",
        expected_horizon: str = "medium",
        signal_expiry_time: datetime | None = None,
        volatility_at_entry: float = 0.0,
        signal_strength: float = 0.0,
        asset_class: str = "unknown",
        regime: str | None = None,
        metadata: dict | None = None,
    ) -> TradeLifecycleState:
        key = str(symbol or "").strip().upper()
        observed_at = coerce_datetime(entry_time)
        position = self.positions.setdefault(key, ManagedPosition(symbol=key, asset_class=asset_class))
        position.quantity = float(quantity or 0.0)
        position.average_price = float(entry_price or 0.0)
        position.last_price = float(entry_price or 0.0)
        position.asset_class = asset_class
        state = TradeLifecycleState(
            trade_id=str(trade_id or uuid4().hex),
            symbol=key,
            quantity=float(quantity or 0.0),
            entry_time=observed_at,
            entry_price=float(entry_price or 0.0),
            current_price=float(entry_price or 0.0),
            strategy_name=str(strategy_name or "unknown"),
            expected_horizon=normalize_horizon(expected_horizon),
            signal_expiry_time=signal_expiry_time,
            volatility_at_entry=float(volatility_at_entry or 0.0),
            signal_strength=float(signal_strength or 0.0),
            asset_class=asset_class,
            regime=str(regime or self.latest_regimes.get(key) or "UNKNOWN"),
            last_update_time=observed_at,
            metadata=dict(metadata or {}),
        )
        self.open_trades[key] = state
        return state

    def get_open_trade(self, symbol: str) -> TradeLifecycleState | None:
        return self.open_trades.get(str(symbol or "").strip().upper())

    def iter_open_trades(self) -> list[TradeLifecycleState]:
        return list(self.open_trades.values())

    def sync_position_update(
        self,
        symbol: str,
        *,
        quantity: float,
        average_price: float,
        current_price: float,
        timestamp: datetime | None = None,
        metadata: dict | None = None,
    ) -> TradeLifecycleState | None:
        key = str(symbol or "").strip().upper()
        observed_at = coerce_datetime(timestamp)
        position = self.positions.setdefault(key, ManagedPosition(symbol=key))
        position.quantity = float(quantity or 0.0)
        position.average_price = float(average_price or 0.0)
        position.last_price = float(current_price or average_price or 0.0)
        trade = self.open_trades.get(key)
        if abs(position.quantity) <= 1e-12:
            if trade is not None:
                self.close_trade(
                    key,
                    timestamp=observed_at,
                    reason=str((metadata or {}).get("close_reason") or "position_flat"),
                    exit_price=float(current_price or average_price or 0.0),
                    metadata=metadata,
                )
            return None
        if trade is None:
            trade = self.open_trade(
                symbol=key,
                quantity=position.quantity,
                entry_price=float(average_price or current_price or 0.0),
                entry_time=observed_at,
                trade_id=str((metadata or {}).get("trade_id") or uuid4().hex),
                strategy_name=str((metadata or {}).get("strategy_name") or "unknown"),
                expected_horizon=str((metadata or {}).get("expected_horizon") or "medium"),
                signal_expiry_time=(metadata or {}).get("signal_expiry_time"),
                volatility_at_entry=float((metadata or {}).get("volatility_at_entry") or (metadata or {}).get("volatility") or 0.0),
                signal_strength=float((metadata or {}).get("signal_strength") or (metadata or {}).get("confidence") or 0.0),
                asset_class=str((metadata or {}).get("asset_class") or position.asset_class or "unknown"),
                regime=self.latest_regimes.get(key),
                metadata=metadata,
            )
        trade.quantity = position.quantity
        trade.entry_price = float(average_price or trade.entry_price or current_price or 0.0)
        trade.current_price = float(current_price or average_price or trade.current_price or 0.0)
        trade.last_update_time = observed_at
        trade.regime = self.latest_regimes.get(key, trade.regime)
        if metadata:
            trade.metadata.update(dict(metadata))
            if metadata.get("strategy_name"):
                trade.strategy_name = str(metadata.get("strategy_name"))
            if metadata.get("expected_horizon"):
                trade.expected_horizon = normalize_horizon(metadata.get("expected_horizon"))
            if metadata.get("signal_expiry_time"):
                trade.signal_expiry_time = coerce_datetime(metadata.get("signal_expiry_time"))
            if metadata.get("volatility_at_entry") is not None or metadata.get("volatility") is not None:
                trade.volatility_at_entry = float(metadata.get("volatility_at_entry") or metadata.get("volatility") or 0.0)
            if metadata.get("signal_strength") is not None or metadata.get("confidence") is not None:
                trade.signal_strength = float(metadata.get("signal_strength") or metadata.get("confidence") or 0.0)
        return trade

    def update_regime(
        self,
        symbol: str,
        regime: str,
        *,
        timestamp: datetime | None = None,
        metadata: dict | None = None,
    ) -> TradeLifecycleState | None:
        key = str(symbol or "").strip().upper()
        normalized = str(regime or "UNKNOWN").strip().upper() or "UNKNOWN"
        self.latest_regimes[key] = normalized
        trade = self.open_trades.get(key)
        if trade is None:
            return None
        trade.regime = normalized
        trade.last_update_time = coerce_datetime(timestamp)
        if metadata:
            trade.metadata.update(dict(metadata))
        return trade

    def refresh_signal(
        self,
        symbol: str,
        *,
        strategy_name: str | None = None,
        expected_horizon: str | None = None,
        signal_expiry_time: datetime | None = None,
        signal_strength: float | None = None,
        metadata: dict | None = None,
    ) -> TradeLifecycleState | None:
        trade = self.open_trades.get(str(symbol or "").strip().upper())
        if trade is None:
            return None
        if strategy_name:
            trade.strategy_name = str(strategy_name)
        if expected_horizon:
            trade.expected_horizon = normalize_horizon(expected_horizon)
        if signal_expiry_time is not None:
            trade.signal_expiry_time = coerce_datetime(signal_expiry_time)
        if signal_strength is not None:
            trade.signal_strength = float(signal_strength)
        if metadata:
            trade.metadata.update(dict(metadata))
        return trade

    def close_trade(
        self,
        symbol: str,
        *,
        timestamp: datetime | None = None,
        reason: str | None = None,
        exit_price: float | None = None,
        metadata: dict | None = None,
    ) -> TradeLifecycleState | None:
        key = str(symbol or "").strip().upper()
        trade = self.open_trades.pop(key, None)
        if trade is None:
            return None
        trade.status = "closed"
        trade.exit_time = coerce_datetime(timestamp)
        trade.exit_reason = str(reason or "").strip() or "closed"
        if exit_price is not None:
            trade.current_price = float(exit_price or 0.0)
        trade.last_update_time = trade.exit_time
        if metadata:
            trade.metadata.update(dict(metadata))
        self.closed_trades.append(trade)
        return trade

    def symbol_exposure(self, symbol: str) -> float:
        position = self.positions.get(str(symbol or "").strip().upper())
        return abs(position.market_value) if position is not None else 0.0

    def gross_exposure(self) -> float:
        return sum(abs(position.market_value) for position in self.positions.values())

    def exposure_by_asset_class(self) -> dict[str, float]:
        exposures: dict[str, float] = {}
        for position in self.positions.values():
            exposures[position.asset_class] = exposures.get(position.asset_class, 0.0) + abs(position.market_value)
        return exposures

    def _sync_trade_after_fill(
        self,
        symbol: str,
        *,
        position: ManagedPosition,
        prior_quantity: float,
        timestamp: datetime | None,
        trade_id: str | None,
        strategy_name: str,
        expected_horizon: str,
        signal_expiry_time: datetime | None,
        volatility_at_entry: float,
        signal_strength: float,
        metadata: dict | None,
    ) -> None:
        observed_at = coerce_datetime(timestamp)
        current_quantity = float(position.quantity)
        existing = self.open_trades.get(symbol)
        if abs(current_quantity) <= 1e-12:
            if existing is not None:
                self.close_trade(
                    symbol,
                    timestamp=observed_at,
                    reason=str((metadata or {}).get("close_reason") or "filled_flat"),
                    exit_price=position.last_price,
                    metadata=metadata,
                )
            return
        if existing is None or (prior_quantity > 0) != (current_quantity > 0):
            if existing is not None:
                self.close_trade(
                    symbol,
                    timestamp=observed_at,
                    reason="position_reversed",
                    exit_price=position.last_price,
                    metadata=metadata,
                )
            self.open_trade(
                symbol=symbol,
                quantity=current_quantity,
                entry_price=position.average_price or position.last_price,
                entry_time=observed_at,
                trade_id=trade_id,
                strategy_name=strategy_name,
                expected_horizon=expected_horizon,
                signal_expiry_time=signal_expiry_time,
                volatility_at_entry=volatility_at_entry,
                signal_strength=signal_strength,
                asset_class=position.asset_class,
                regime=self.latest_regimes.get(symbol),
                metadata=metadata,
            )
            return
        self.sync_position_update(
            symbol,
            quantity=current_quantity,
            average_price=position.average_price,
            current_price=position.last_price,
            timestamp=observed_at,
            metadata={
                **dict(existing.metadata if existing is not None else {}),
                **dict(metadata or {}),
                "strategy_name": strategy_name or (existing.strategy_name if existing is not None else "unknown"),
                "expected_horizon": expected_horizon or (existing.expected_horizon if existing is not None else "medium"),
                "signal_expiry_time": signal_expiry_time or (existing.signal_expiry_time if existing is not None else None),
                "volatility_at_entry": volatility_at_entry or (existing.volatility_at_entry if existing is not None else 0.0),
                "signal_strength": signal_strength or (existing.signal_strength if existing is not None else 0.0),
                "trade_id": trade_id or (existing.trade_id if existing is not None else uuid4().hex),
                "asset_class": position.asset_class,
            },
        )
