from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from core.event_bus import AsyncEventBus
from risk.exposure_manager import ExposureManager
from core.event_bus.event_types import EventType
from core.models import ExecutionReport, PerformanceMetrics, PortfolioSnapshot, Position, PositionUpdate


class PortfolioEngine:
    """Institutional portfolio engine tracking positions, PnL, and exposure."""

    def __init__(
        self,
        event_bus: AsyncEventBus,
        *,
        starting_cash: float = 100000.0,
        base_currency: str = "USD",
        symbol_sectors: Mapping[str, str] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.base_currency = str(base_currency or "USD").upper()
        self.starting_cash = float(starting_cash)
        self.cash = float(starting_cash)
        self.peak_equity = float(starting_cash)
        self.positions: dict[str, Position] = {}
        self.position_metadata: dict[str, dict[str, Any]] = {}
        self.symbol_sectors: dict[str, str] = {str(symbol).upper(): str(sector) for symbol, sector in dict(symbol_sectors or {}).items()}
        self.exposure_manager = ExposureManager()
        self.total_fills = 0
        self.closed_trades = 0
        self.latest_snapshot = PortfolioSnapshot(cash=self.cash, equity=self.cash)
        self.logger = logger or logging.getLogger("PortfolioEngine")

        self.bus.subscribe(EventType.ORDER_FILLED, self._on_fill)
        self.bus.subscribe(EventType.MARKET_TICK, self._on_tick)
        self.bus.subscribe(EventType.PRICE_UPDATE, self._on_tick)

    @property
    def equity(self) -> float:
        return float(self.latest_snapshot.equity)

    @property
    def daily_loss_amount(self) -> float:
        return max(0.0, self.starting_cash - self.equity)

    @property
    def trading_halted(self) -> bool:
        return False

    def snapshot(self) -> PortfolioSnapshot:
        return self.latest_snapshot

    def symbol_exposure(self, symbol: str) -> float:
        return self.exposure_manager.symbol_exposure(symbol)

    def sector_exposure(self, sector: str) -> float:
        target = str(sector or "").strip().lower()
        if not target:
            return 0.0
        total = 0.0
        for symbol, position in self.positions.items():
            mapped = self.symbol_sectors.get(symbol, str(self.position_metadata.get(symbol, {}).get("sector") or "unknown"))
            if str(mapped).strip().lower() == target:
                total += abs(position.market_value)
        return total

    def global_exposure(self) -> float:
        return self.exposure_manager.total_exposure()

    def update_symbol_sector(self, symbol: str, sector: str) -> None:
        key = str(symbol or "").strip().upper()
        if key:
            self.symbol_sectors[key] = str(sector or "unknown")

    def allocate_capital(
        self,
        *,
        symbol: str,
        confidence: float,
        price: float,
        max_position_fraction: float = 0.10,
        strategy_weight: float = 1.0,
    ) -> float:
        reference_price = max(float(price or 0.0), 1e-9)
        free_cash = max(0.0, self.cash)
        conviction = min(1.0, max(0.0, float(confidence or 0.0)))
        weight = min(1.0, max(0.0, float(max_position_fraction or 0.0) * max(0.1, float(strategy_weight or 1.0))))
        exposure_headroom = max(0.0, (self.equity * weight) - self.symbol_exposure(symbol))
        allocatable_notional = min(free_cash, exposure_headroom)
        return max(0.0, allocatable_notional * conviction / reference_price)

    async def _on_fill(self, event) -> None:
        report = getattr(event, "data", None)
        if report is None:
            return
        if not isinstance(report, ExecutionReport):
            report = ExecutionReport(**dict(report))

        fill_price = float(report.fill_price or report.requested_price or 0.0)
        fill_quantity = float(report.filled_quantity if report.filled_quantity is not None else report.quantity)
        if fill_quantity <= 0.0 or fill_price <= 0.0:
            return

        self.total_fills += 1
        signed_quantity = fill_quantity if str(report.side).lower() == "buy" else -fill_quantity
        symbol = str(report.symbol or "").strip().upper()
        position = self.positions.setdefault(symbol, Position(symbol=symbol))
        prior_quantity = float(position.quantity)
        prior_average_price = float(position.average_price)
        previous_trade_id = str(self.position_metadata.get(symbol, {}).get("trade_id") or report.order_id)

        if position.quantity == 0.0 or (position.quantity > 0.0) == (signed_quantity > 0.0):
            new_quantity = position.quantity + signed_quantity
            if abs(new_quantity) > 1e-12:
                position.average_price = (
                    (position.quantity * position.average_price) + (signed_quantity * fill_price)
                ) / new_quantity
            position.quantity = new_quantity
        else:
            closing_quantity = min(abs(position.quantity), abs(signed_quantity))
            pnl_direction = 1.0 if position.quantity > 0.0 else -1.0
            position.realized_pnl += (fill_price - position.average_price) * closing_quantity * pnl_direction
            position.quantity += signed_quantity
            if abs(position.quantity) <= 1e-12:
                position.quantity = 0.0
                position.average_price = 0.0
                self.closed_trades += 1
            elif (prior_quantity > 0.0 and position.quantity < 0.0) or (prior_quantity < 0.0 and position.quantity > 0.0):
                position.average_price = fill_price
                self.closed_trades += 1

        position.last_price = fill_price
        self.cash -= signed_quantity * fill_price
        self.position_metadata[symbol] = self._build_position_metadata(
            report,
            position=position,
            trade_id=report.metadata.get("trade_id") or previous_trade_id,
        )
        self._sync_exposure(position)
        await self._publish_position_update(position, timestamp=report.timestamp)
        await self._publish_snapshot(timestamp=report.timestamp)

        if abs(prior_quantity) <= 1e-12 and abs(position.quantity) > 1e-12:
            await self.bus.publish(
                EventType.POSITIONS_OPEN,
                {
                    "trade_id": self.position_metadata[symbol]["trade_id"],
                    "symbol": symbol,
                    "quantity": position.quantity,
                    "entry_price": position.average_price,
                    "entry_time": report.timestamp,
                    "metadata": dict(self.position_metadata[symbol]),
                },
                priority=87,
                source="portfolio_engine",
            )
        elif abs(prior_quantity) > 1e-12 and abs(position.quantity) <= 1e-12:
            await self.bus.publish(
                EventType.POSITIONS_CLOSED,
                {
                    "trade_id": previous_trade_id,
                    "symbol": symbol,
                    "quantity": prior_quantity,
                    "entry_price": prior_average_price,
                    "exit_price": fill_price,
                    "close_time": report.timestamp,
                    "reason": report.metadata.get("close_reason") or "position_closed",
                    "metadata": dict(self.position_metadata.get(symbol, {})),
                },
                priority=89,
                source="portfolio_engine",
            )
            self.exposure_manager.remove(symbol)

    async def _on_tick(self, event) -> None:
        payload = dict(getattr(event, "data", {}) or {})
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol or symbol not in self.positions:
            return
        price = float(payload.get("price") or payload.get("last") or payload.get("close") or 0.0)
        if price <= 0.0:
            return
        position = self.positions[symbol]
        position.last_price = price
        self._sync_exposure(position)
        await self._publish_position_update(position, timestamp=payload.get("timestamp"))
        await self._publish_snapshot(timestamp=payload.get("timestamp"))

    def _sync_exposure(self, position: Position) -> None:
        if abs(position.quantity) <= 1e-12:
            self.exposure_manager.remove(position.symbol)
            return
        asset_class = self.position_metadata.get(position.symbol, {}).get("asset_class", "unknown")
        self.exposure_manager.update_position(
            position.symbol,
            quantity=position.quantity,
            price=position.last_price or position.average_price,
            asset_class=asset_class,
        )

    async def _publish_position_update(self, position: Position, *, timestamp: Any = None) -> None:
        payload = dict(
            symbol=position.symbol,
            quantity=float(position.quantity),
            average_price=float(position.average_price),
            current_price=float(position.last_price),
            unrealized_pnl=float(position.unrealized_pnl),
            realized_pnl=float(position.realized_pnl),
            market_value=float(position.market_value),
            metadata=dict(self.position_metadata.get(position.symbol, {})),
        )
        if timestamp is not None:
            payload["timestamp"] = timestamp
        await self.bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(**payload),
            priority=88,
            source="portfolio_engine",
        )

    async def _publish_snapshot(self, *, timestamp: Any = None) -> None:
        unrealized = sum(position.unrealized_pnl for position in self.positions.values())
        realized = sum(position.realized_pnl for position in self.positions.values())
        gross_exposure = self.exposure_manager.total_exposure()
        net_exposure = self.exposure_manager.net_exposure()
        equity = self.cash + net_exposure
        self.peak_equity = max(self.peak_equity, equity)
        drawdown_pct = 0.0 if self.peak_equity <= 0.0 else max(0.0, (self.peak_equity - equity) / self.peak_equity)
        snapshot_payload = dict(
            cash=self.cash,
            equity=equity,
            positions={symbol: position for symbol, position in self.positions.items()},
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            drawdown_pct=drawdown_pct,
        )
        if timestamp is not None:
            snapshot_payload["timestamp"] = timestamp
        snapshot = PortfolioSnapshot(**snapshot_payload)
        self.latest_snapshot = snapshot
        await self.bus.publish(EventType.PORTFOLIO_SNAPSHOT, snapshot, priority=90, source="portfolio_engine")

        metrics = PerformanceMetrics(
            total_trades=self.total_fills,
            closed_trades=self.closed_trades,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            equity=equity,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            max_drawdown_pct=drawdown_pct,
            symbols=sorted(self.positions.keys()),
            metadata={"base_currency": self.base_currency},
            win_rate=0.0,
        )
        await self.bus.publish(EventType.PERFORMANCE_METRICS, metrics, priority=91, source="portfolio_engine")
        self._log("portfolio_snapshot", **asdict(metrics))

    def _build_position_metadata(self, report: ExecutionReport, *, position: Position, trade_id: str) -> dict[str, Any]:
        metadata = dict(self.position_metadata.get(report.symbol, {}))
        metadata.update(dict(report.metadata or {}))
        sector = str(metadata.get("sector") or self.symbol_sectors.get(report.symbol) or "unknown")
        self.symbol_sectors[report.symbol] = sector
        metadata.update(
            {
                "trade_id": str(trade_id or report.order_id),
                "strategy_name": str(report.strategy_name or metadata.get("strategy_name") or "unknown"),
                "asset_class": str(metadata.get("asset_class") or "unknown"),
                "sector": sector,
                "entry_price": float(position.average_price or report.fill_price or report.requested_price or 0.0),
                "last_update": report.timestamp,
            }
        )
        return metadata

    def _log(self, event_name: str, **payload: Any) -> None:
        try:
            message = json.dumps({"event": event_name, **payload}, default=str, sort_keys=True)
        except Exception:
            message = f"{event_name} {payload}"
        self.logger.info(message)


__all__ = ["PortfolioEngine"]
