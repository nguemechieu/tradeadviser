from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from contracts.portfolio import PortfolioSnapshot
from core.regime_engine_config import RiskConfig, TimeStopConfig

from ..event_bus.async_event_bus import AsyncEventBus
from ..event_bus.event_types import EventType
from portfolio.position_manager import PositionManager
from portfolio.trade_lifecycle import (
    TradeLifecycleDecision,
    TradeLifecycleState,
    clamp,
    coerce_datetime,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _close_side(quantity: float) -> str:
    return "sell" if float(quantity) > 0.0 else "buy"


def _normalize_regime(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    return text or "UNKNOWN"


class TimeStopEngine:
    """
    Event-driven position lifecycle manager that turns stale or decayed positions
    into close orders while remaining portfolio-aware and risk-aware.
    """

    def __init__(
        self,
        event_bus: AsyncEventBus,
        *,
        position_manager: PositionManager | None = None,
        risk_engine: Any | None = None,
        portfolio_engine: Any | None = None,
        time_stop_config: TimeStopConfig | None = None,
        risk_config: RiskConfig | None = None,
        logger: logging.Logger | None = None,
        **config_overrides: Any,
    ) -> None:
        self.bus = event_bus
        self.position_manager = position_manager or PositionManager()
        self.risk_engine = risk_engine
        self.portfolio_engine = portfolio_engine
        self.config = self._build_config(time_stop_config, **config_overrides)
        self.risk_config = risk_config or RiskConfig()
        self.logger = logger or logging.getLogger("TimeStopEngine")
        self.latest_snapshot = PortfolioSnapshot(cash=0.0, equity=0.0)
        self.pending_close_symbols: set[str] = set()

        self.bus.subscribe(EventType.POSITIONS_OPEN, self._on_position_open)
        self.bus.subscribe(EventType.POSITIONS_CLOSED, self._on_position_closed)
        self.bus.subscribe(EventType.POSITION_UPDATE, self._on_position_update)
        self.bus.subscribe(EventType.MARKET_DATA_TOPIC, self._on_market_data)
        self.bus.subscribe(EventType.REGIME_UPDATES, self._on_regime_update)
        self.bus.subscribe(EventType.REGIME, self._on_regime_update)
        self.bus.subscribe(EventType.PORTFOLIO_SNAPSHOT, self._on_portfolio_snapshot)
        self.bus.subscribe(EventType.CLOSE_POSITION, self._on_close_request)
        self.bus.subscribe(EventType.EXECUTION_REPORT, self._on_execution_report)

    def get_state(self, symbol: str) -> TradeLifecycleState | None:
        """Return the current lifecycle state for an open trade in the given symbol. Wraps the
        underlying position manager so callers can query whether a position is being tracked.

        The method simply delegates to the PositionManager and returns whatever state is stored
        for the symbol, or None if no open trade exists. It does not modify any state or trigger
        additional evaluation.

        Args:
            symbol: The instrument symbol whose open trade state should be retrieved.

        Returns:
            TradeLifecycleState | None: The lifecycle state object for the symbol, or None if
                there is no open trade being tracked.
        """
        return self.position_manager.get_open_trade(symbol)

    def ui_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for trade in self.position_manager.iter_open_trades():
            max_duration = self._dynamic_max_duration(trade)
            aging_score = self._aging_score(trade, max_duration=max_duration)
            rows.append(trade.to_ui_payload(max_duration=max_duration, aging_score=aging_score))
        rows.sort(key=lambda item: (item.get("time_remaining_seconds") is None, item.get("time_remaining_seconds") or 0.0))
        return rows

    def _build_config(self, config: TimeStopConfig | None, **overrides: Any) -> TimeStopConfig:
        resolved = config or TimeStopConfig()
        for key, value in dict(overrides or {}).items():
            if hasattr(resolved, key):
                setattr(resolved, key, value)
        return resolved

    async def _on_position_open(self, event) -> None:
        payload = dict(getattr(event, "data", {}) or {})
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        metadata = dict(payload.get("metadata") or {})
        state = self.position_manager.open_trade(
            symbol=symbol,
            quantity=_safe_float(payload.get("quantity")),
            entry_price=_safe_float(payload.get("entry_price") or payload.get("current_price")),
            entry_time=payload.get("entry_time"),
            trade_id=str(payload.get("trade_id") or metadata.get("trade_id") or ""),
            strategy_name=str(payload.get("strategy_name") or metadata.get("strategy_name") or "unknown"),
            expected_horizon=str(payload.get("expected_horizon") or metadata.get("expected_horizon") or "medium"),
            signal_expiry_time=payload.get("signal_expiry_time") or metadata.get("signal_expiry_time"),
            volatility_at_entry=_safe_float(payload.get("volatility_at_entry") or metadata.get("volatility_at_entry") or metadata.get("volatility")),
            signal_strength=_safe_float(payload.get("signal_strength") or metadata.get("signal_strength") or metadata.get("confidence")),
            asset_class=str(payload.get("asset_class") or metadata.get("asset_class") or "unknown"),
            regime=self.position_manager.latest_regimes.get(symbol),
            metadata={**metadata, "position_open_source": getattr(event, "source", "unknown")},
        )
        await self._evaluate_trade(state, as_of=state.last_update_time, trigger=EventType.POSITIONS_OPEN)

    async def _on_position_closed(self, event) -> None:
        payload = dict(getattr(event, "data", {}) or {})
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        self.pending_close_symbols.discard(symbol)
        self.position_manager.close_trade(
            symbol,
            timestamp=payload.get("close_time"),
            reason=str(payload.get("reason") or "position_closed"),
            exit_price=_safe_float(payload.get("exit_price")),
            metadata=dict(payload.get("metadata") or {}),
        )

    async def _on_position_update(self, event) -> None:
        update = getattr(event, "data", None)
        if update is None:
            return
        if not isinstance(update, PositionUpdate):
            update = PositionUpdate(**dict(update))
        symbol = str(update.symbol or "").strip().upper()
        metadata = dict(update.metadata or {})
        state = self.position_manager.sync_position_update(
            update.symbol,
            quantity=update.quantity,
            average_price=update.average_price,
            current_price=update.current_price,
            timestamp=update.timestamp,
            metadata=metadata,
        )
        if state is None:
            self.pending_close_symbols.discard(symbol)
            return
        close_related = bool(
            metadata.get("close_position")
            or metadata.get("close_reason")
            or metadata.get("time_stop_reason")
            or str(metadata.get("action") or "").strip().lower() in {"close", "exit", "reduce"}
        )
        if symbol in self.pending_close_symbols and not close_related:
            return
        if close_related:
            self.pending_close_symbols.discard(symbol)
        await self._evaluate_trade(state, as_of=coerce_datetime(update.timestamp), trigger=EventType.POSITION_UPDATE)

    async def _on_market_data(self, event) -> None:
        payload = dict(getattr(event, "data", {}) or {})
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        price = _safe_float(payload.get("price") or payload.get("last") or payload.get("close"))
        if price <= 0:
            return
        state = self.position_manager.get_open_trade(symbol)
        if state is None:
            return
        timestamp = coerce_datetime(payload.get("timestamp"))
        self.position_manager.mark_price(symbol, price, timestamp=timestamp)
        refreshed = self.position_manager.get_open_trade(symbol)
        if refreshed is not None:
            await self._evaluate_trade(refreshed, as_of=timestamp, trigger=EventType.MARKET_DATA_TOPIC)

    async def _on_regime_update(self, event) -> None:
        payload = getattr(event, "data", None)
        if payload is None:
            return
        if isinstance(payload, RegimeSnapshot):
            symbol = payload.symbol
            regime = payload.regime
            timestamp = payload.timestamp
            metadata = {
                "timeframe": payload.timeframe,
                "volatility_regime": payload.volatility_regime,
                "trend_strength": payload.trend_strength,
                "atr_pct": payload.atr_pct,
                **dict(payload.metadata or {}),
            }
        else:
            raw = dict(payload or {})
            symbol = raw.get("symbol")
            regime = raw.get("regime")
            timestamp = raw.get("timestamp")
            metadata = dict(raw.get("metadata") or {})
        state = self.position_manager.update_regime(
            str(symbol or ""),
            _normalize_regime(regime),
            timestamp=timestamp,
            metadata=metadata,
        )
        if state is not None:
            await self._evaluate_trade(state, as_of=coerce_datetime(timestamp), trigger=EventType.REGIME_UPDATES)

    async def _on_portfolio_snapshot(self, event) -> None:
        snapshot = getattr(event, "data", None)
        if snapshot is None:
            return
        if not isinstance(snapshot, PortfolioSnapshot):
            snapshot = PortfolioSnapshot(**dict(snapshot))
        self.latest_snapshot = snapshot
        for trade in self.position_manager.iter_open_trades():
            await self._evaluate_trade(trade, as_of=coerce_datetime(snapshot.timestamp), trigger=EventType.PORTFOLIO_SNAPSHOT)

    async def _on_close_request(self, event) -> None:
        request = getattr(event, "data", None)
        if request is None:
            return
        if not isinstance(request, ClosePositionRequest):
            request = ClosePositionRequest(**dict(request))
        symbol = str(request.symbol or "").strip().upper()
        if symbol:
            self.pending_close_symbols.add(symbol)

    async def _on_execution_report(self, event) -> None:
        report = getattr(event, "data", None)
        if report is None:
            return
        if not isinstance(report, ExecutionReport):
            report = ExecutionReport(**dict(report))
        symbol = str(report.symbol or "").strip().upper()
        if not symbol:
            return
        if str(report.status).lower() == "failed" and bool((report.metadata or {}).get("close_position")):
            self.pending_close_symbols.discard(symbol)

    async def _evaluate_trade(self, trade: TradeLifecycleState, *, as_of: datetime, trigger: str) -> None:
        if trade.status != "open":
            return
        if trade.symbol in self.pending_close_symbols:
            return
        max_duration = self._dynamic_max_duration(trade)
        aging_score = self._aging_score(trade, max_duration=max_duration)
        risk_flags = self._risk_flags(trade)
        await self._maybe_emit_alert(trade, max_duration=max_duration, aging_score=aging_score, as_of=as_of)

        reason: str | None = None
        if trade.signal_expiry_time is not None and as_of >= trade.signal_expiry_time:
            reason = "Alpha signal expired"
        elif self._kill_switch_active() and trade.duration.total_seconds() >= max_duration.total_seconds() * 0.25:
            reason = "Risk kill switch forced lifecycle exit"
        else:
            soft_deadline_seconds = max_duration.total_seconds() * clamp(self.config.soft_time_stop_fraction, 0.10, 1.0)
            if (
                self.config.strict_basic_time_stop
                and clamp(self.config.soft_time_stop_fraction, 0.10, 1.0) >= 1.0
                and trade.duration > max_duration
            ):
                reason = "Basic time stop reached"
            elif trade.duration.total_seconds() >= soft_deadline_seconds and trade.pnl_pct < self.config.min_expected_return:
                reason = "Soft time stop: underperforming stale position"
            elif (
                trade.duration.total_seconds() >= max_duration.total_seconds() * clamp(self.config.minimum_age_before_aging_exit_fraction, 0.0, 1.0)
                and aging_score < self.config.aging_score_threshold
            ):
                reason = f"Trade aging score deteriorated ({aging_score:.2f})"
            elif self.config.strict_basic_time_stop and trade.duration > max_duration:
                reason = "Basic time stop reached"
        if reason is None:
            return
        await self._emit_close_request(
            trade,
            reason=reason,
            max_duration=max_duration,
            aging_score=aging_score,
            risk_flags=risk_flags,
            trigger=trigger,
        )

    def _dynamic_max_duration(self, trade: TradeLifecycleState) -> timedelta:
        base_seconds = self._base_duration_seconds(trade)
        regime_factor = 1.0
        regime = _normalize_regime(trade.regime)
        if any(token in regime for token in ("TREND", "BULL", "BEAR")):
            regime_factor *= self.config.trend_regime_multiplier
        if any(token in regime for token in ("RANGE", "MEAN_REVERT", "NEUTRAL")):
            regime_factor *= self.config.range_regime_multiplier
        if "HIGH_VOL" in regime or "VOLATILITY" in regime:
            regime_factor *= self.config.high_volatility_multiplier
        if "LOW_LIQ" in regime or "ILLIQ" in regime:
            regime_factor *= self.config.low_liquidity_multiplier

        volatility_factor = 1.0
        if trade.volatility_at_entry > 0 and self.config.target_volatility > 0:
            volatility_factor = clamp(
                self.config.target_volatility / max(trade.volatility_at_entry, 1e-9),
                self.config.min_volatility_factor,
                self.config.max_volatility_factor,
            )

        portfolio_factor = 1.0
        equity = max(_safe_float(self.latest_snapshot.equity), 1e-9)
        symbol_exposure = self.position_manager.symbol_exposure(trade.symbol)
        if equity > 0 and (symbol_exposure / equity) > self.risk_config.max_symbol_exposure_pct:
            portfolio_factor *= 0.80
        if self.latest_snapshot.drawdown_pct >= self.risk_config.max_portfolio_drawdown * 0.75:
            portfolio_factor *= 0.85

        seconds = max(60.0, float(base_seconds) * regime_factor * volatility_factor * portfolio_factor)
        return timedelta(seconds=seconds)

    def _base_duration_seconds(self, trade: TradeLifecycleState) -> float:
        strategy_key = str(trade.strategy_name or "").strip().lower()
        for key, seconds in dict(self.config.strategy_duration_overrides_seconds or {}).items():
            if str(key).strip().lower() == strategy_key:
                return max(60.0, _safe_float(seconds, self.config.medium_horizon_seconds))
        if trade.expected_horizon == "short":
            return max(60.0, self.config.short_horizon_seconds)
        if trade.expected_horizon == "long":
            return max(60.0, self.config.long_horizon_seconds)
        return max(60.0, self.config.medium_horizon_seconds)

    def _aging_score(self, trade: TradeLifecycleState, *, max_duration: timedelta) -> float:
        max_seconds = max(max_duration.total_seconds(), 1.0)
        duration_ratio = clamp(trade.duration.total_seconds() / max_seconds, 0.0, 2.0)
        duration_component = clamp(1.0 - duration_ratio, 0.0, 1.0)

        expected_floor = max(abs(self.config.min_expected_return), 1e-6)
        pnl_component = clamp(0.5 + (trade.pnl_pct / (expected_floor * 4.0)), 0.0, 1.0)

        volatility_component = 1.0
        if trade.volatility_at_entry > 0 and self.config.target_volatility > 0:
            volatility_component = clamp(self.config.target_volatility / trade.volatility_at_entry, 0.0, 1.0)

        signal_component = clamp(trade.signal_strength or 0.5, 0.0, 1.0)
        if trade.signal_expiry_time is not None and trade.last_update_time >= trade.signal_expiry_time:
            signal_component = 0.0

        numerator = (
            duration_component * self.config.aging_duration_weight
            + pnl_component * self.config.aging_pnl_weight
            + volatility_component * self.config.aging_volatility_weight
            + signal_component * self.config.aging_signal_weight
        )
        denominator = max(
            self.config.aging_duration_weight
            + self.config.aging_pnl_weight
            + self.config.aging_volatility_weight
            + self.config.aging_signal_weight,
            1e-9,
        )
        score = numerator / denominator
        if self.latest_snapshot.drawdown_pct >= self.risk_config.max_portfolio_drawdown:
            score = max(0.0, score - 0.15)
        return clamp(score, 0.0, 1.0)

    def _risk_flags(self, trade: TradeLifecycleState) -> list[str]:
        flags: list[str] = []
        equity = max(_safe_float(self.latest_snapshot.equity), 1e-9)
        symbol_exposure = self.position_manager.symbol_exposure(trade.symbol)
        gross_exposure = _safe_float(self.latest_snapshot.gross_exposure)
        if self._kill_switch_active():
            flags.append("kill_switch")
        if self.latest_snapshot.drawdown_pct >= self.risk_config.max_portfolio_drawdown:
            flags.append("drawdown_breach")
        elif self.latest_snapshot.drawdown_pct >= self.risk_config.max_portfolio_drawdown * 0.75:
            flags.append("drawdown_pressure")
        if equity > 0 and (symbol_exposure / equity) > self.risk_config.max_symbol_exposure_pct:
            flags.append("symbol_exposure_breach")
        if equity > 0 and (gross_exposure / equity) > self.risk_config.max_gross_leverage:
            flags.append("gross_leverage_breach")
        return flags

    def _kill_switch_active(self) -> bool:
        return bool(getattr(self.risk_engine, "kill_switch_active", False))

    async def _maybe_emit_alert(
        self,
        trade: TradeLifecycleState,
        *,
        max_duration: timedelta,
        aging_score: float,
        as_of: datetime,
    ) -> None:
        time_remaining_seconds = trade.time_remaining_seconds(max_duration)
        if time_remaining_seconds <= 0:
            return
        if time_remaining_seconds > max(1.0, self.config.alert_before_close_seconds):
            return
        if aging_score > max(self.config.aging_score_threshold, 0.45):
            return
        alert_key = f"preclose:{int(max_duration.total_seconds())}"
        if alert_key in trade.alerts_emitted:
            return
        trade.alerts_emitted.add(alert_key)
        alert = AlertEvent(
            alert_id=f"time_stop:{trade.trade_id}:{alert_key}",
            title="Time Stop Approaching",
            message=(
                f"{trade.symbol} has {time_remaining_seconds:.0f}s remaining before its time-stop window closes. "
                f"PnL={trade.pnl_pct:.2%}, regime={trade.regime}, aging_score={aging_score:.2f}."
            ),
            severity="warning",
            category="time_stop",
            event_type=EventType.TIME_STOP_DECISION,
            symbol=trade.symbol,
            strategy_name=trade.strategy_name,
            action="monitor",
            metadata={
                "trade_id": trade.trade_id,
                "time_remaining_seconds": time_remaining_seconds,
                "max_duration_seconds": max_duration.total_seconds(),
                "aging_score": aging_score,
                "at": as_of.isoformat(),
            },
        )
        await self.bus.publish(EventType.ALERT_EVENT, alert, priority=84, source="time_stop_engine")

    async def _emit_close_request(
        self,
        trade: TradeLifecycleState,
        *,
        reason: str,
        max_duration: timedelta,
        aging_score: float,
        risk_flags: list[str],
        trigger: str,
    ) -> None:
        quantity = abs(_safe_float(trade.quantity))
        if quantity <= 1e-12:
            return
        decision = TradeLifecycleDecision(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            action="close",
            reason=reason,
            close_quantity=quantity,
            regime=trade.regime,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            duration_seconds=trade.duration.total_seconds(),
            max_duration_seconds=max_duration.total_seconds(),
            time_remaining_seconds=trade.time_remaining_seconds(max_duration),
            aging_score=aging_score,
            risk_flags=list(risk_flags),
            metadata={
                **trade.to_ui_payload(max_duration=max_duration, aging_score=aging_score),
                "trigger": trigger,
                "risk_flags": list(risk_flags),
            },
        )
        request = ClosePositionRequest(
            symbol=trade.symbol,
            side=_close_side(trade.quantity),
            quantity=quantity,
            reason=reason,
            price=trade.current_price,
            strategy_name="time_stop_engine",
            metadata={
                "trade_id": trade.trade_id,
                "time_stop_reason": reason,
                "aging_score": aging_score,
                "time_remaining_seconds": trade.time_remaining_seconds(max_duration),
                "max_duration_seconds": max_duration.total_seconds(),
                "expected_horizon": trade.expected_horizon,
                "signal_expiry_time": trade.signal_expiry_time.isoformat() if trade.signal_expiry_time is not None else None,
                "volatility_at_entry": trade.volatility_at_entry,
                "signal_strength": trade.signal_strength,
                "risk_flags": list(risk_flags),
                "trigger": trigger,
                **dict(trade.metadata or {}),
            },
        )
        self.pending_close_symbols.add(trade.symbol)
        await self.bus.publish(EventType.TIME_STOP_DECISION, decision, priority=76, source="time_stop_engine")
        await self.bus.publish(EventType.ORDERS_CLOSE, request, priority=77, source="time_stop_engine")
        await self.bus.publish(EventType.CLOSE_POSITION, request, priority=77, source="time_stop_engine")
        self.logger.info(
            "Time stop close %s quantity=%.6f reason=%s duration=%.0fs pnl=%.2f%% regime=%s",
            trade.symbol,
            quantity,
            reason,
            trade.duration.total_seconds(),
            trade.pnl_pct * 100.0,
            trade.regime,
        )
