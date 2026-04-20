from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sopotek.core.event_bus import AsyncEventBus
from sopotek.core.event_types import EventType
from sopotek.core.models import PortfolioSnapshot

from risk.exposure_manager import ExposureManager


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PortfolioRiskState:
    equity: float
    cash: float
    gross_exposure: float
    net_exposure: float
    realized_pnl: float
    unrealized_pnl: float
    drawdown_pct: float
    day_start_equity: float
    day_start_realized_pnl: float
    daily_realized_pnl: float
    daily_loss_amount: float
    trading_halted: bool = False
    halt_reason: str | None = None
    timestamp: datetime = field(default_factory=_utc_now)


class PortfolioMonitor:
    """Monitors portfolio equity, exposure concentration, and daily loss limits."""

    def __init__(
        self,
        event_bus: AsyncEventBus,
        *,
        exposure_manager: ExposureManager | None = None,
        max_daily_loss_pct: float = 0.03,
        starting_equity: float = 100000.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.exposure_manager = exposure_manager
        self.max_daily_loss_pct = max(0.0, float(max_daily_loss_pct))
        self.logger = logger or logging.getLogger("PortfolioMonitor")
        self.current_trading_day = _utc_now().date()
        self.latest_snapshot = PortfolioSnapshot(
            cash=float(starting_equity),
            equity=float(starting_equity),
        )
        self.state = PortfolioRiskState(
            equity=float(starting_equity),
            cash=float(starting_equity),
            gross_exposure=0.0,
            net_exposure=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            drawdown_pct=0.0,
            day_start_equity=float(starting_equity),
            day_start_realized_pnl=0.0,
            daily_realized_pnl=0.0,
            daily_loss_amount=0.0,
        )
        self.bus.subscribe(EventType.PORTFOLIO_SNAPSHOT, self._on_portfolio_snapshot)

    @property
    def equity(self) -> float:
        return float(self.state.equity)

    @property
    def daily_loss_amount(self) -> float:
        return float(self.state.daily_loss_amount)

    @property
    def trading_halted(self) -> bool:
        return bool(self.state.trading_halted)

    def can_open_new_risk(self) -> bool:
        return not self.trading_halted

    def get_state(self) -> PortfolioRiskState:
        return self.state

    async def _on_portfolio_snapshot(self, event) -> None:
        snapshot = getattr(event, "data", None)
        if snapshot is None:
            return
        if not isinstance(snapshot, PortfolioSnapshot):
            snapshot = PortfolioSnapshot(**dict(snapshot))

        timestamp = self._coerce_timestamp(getattr(snapshot, "timestamp", None))
        trade_day = timestamp.date()
        if self.current_trading_day != trade_day:
            self.current_trading_day = trade_day
            self.state.day_start_equity = float(snapshot.equity or self.state.equity)
            self.state.day_start_realized_pnl = float(snapshot.realized_pnl or 0.0)
            self.state.trading_halted = False
            self.state.halt_reason = None

        daily_realized_pnl = float(snapshot.realized_pnl or 0.0) - float(self.state.day_start_realized_pnl or 0.0)
        daily_loss_amount = max(0.0, -daily_realized_pnl)
        daily_loss_limit = max(0.0, float(self.state.day_start_equity or snapshot.equity or 0.0)) * self.max_daily_loss_pct
        trading_halted = daily_loss_limit > 0.0 and daily_loss_amount >= daily_loss_limit
        halt_reason = None
        if trading_halted:
            halt_reason = f"Max daily loss breached: {daily_loss_amount:.2f} >= {daily_loss_limit:.2f}"

        self.latest_snapshot = snapshot
        self.state = PortfolioRiskState(
            equity=float(snapshot.equity or 0.0),
            cash=float(snapshot.cash or 0.0),
            gross_exposure=float(snapshot.gross_exposure or 0.0),
            net_exposure=float(snapshot.net_exposure or 0.0),
            realized_pnl=float(snapshot.realized_pnl or 0.0),
            unrealized_pnl=float(snapshot.unrealized_pnl or 0.0),
            drawdown_pct=float(snapshot.drawdown_pct or 0.0),
            day_start_equity=float(self.state.day_start_equity or snapshot.equity or 0.0),
            day_start_realized_pnl=float(self.state.day_start_realized_pnl or 0.0),
            daily_realized_pnl=daily_realized_pnl,
            daily_loss_amount=daily_loss_amount,
            trading_halted=trading_halted,
            halt_reason=halt_reason,
            timestamp=timestamp,
        )

        if self.exposure_manager is not None:
            self.exposure_manager.update_from_portfolio(getattr(snapshot, "positions", {}) or {})

        if trading_halted:
            self.logger.warning(halt_reason)
            await self.bus.publish(
                EventType.RISK_ALERT,
                {
                    "reason": halt_reason,
                    "equity": self.state.equity,
                    "daily_loss_amount": daily_loss_amount,
                    "daily_loss_limit": daily_loss_limit,
                },
                priority=5,
                source="portfolio_monitor",
            )

    @staticmethod
    def _coerce_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return _utc_now()
