from __future__ import annotations

import logging
from datetime import datetime, timezone


from derivatives.core.live_market_cache import LiveMarketCache
from derivatives.core.models import ExecutionUpdate, PortfolioState, PositionState
from events.event_bus.event_bus import EventBus


class PortfolioEngine:
    def __init__(
        self,
        event_bus: EventBus,
        cache: LiveMarketCache,
        *,
        starting_equity: float = 500.0,
        base_currency: str = "USD",
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.cache = cache
        self.base_currency = str(base_currency or "USD").upper()
        self.logger = logger or logging.getLogger("DerivativesPortfolioEngine")
        self.starting_equity = float(starting_equity or 100000.0)
        self.cash = self.starting_equity
        self.positions: dict[str, PositionState] = {}
        self.equity_high_watermark = self.starting_equity
        self.bus.subscribe("order.executed", self._on_execution)
        self.bus.subscribe("market.ticker", self._on_ticker)

    def _position_key(self, broker_key: str, symbol: str, account_id: str | None) -> str:
        return f"{broker_key}:{account_id or 'default'}:{symbol}"

    async def _on_execution(self, event) -> None:
        payload = dict(event.data or {})
        update = ExecutionUpdate(
            order_id=str(payload.get("order_id") or payload.get("id") or ""),
            symbol=str(payload.get("symbol") or "").strip(),
            side=str(payload.get("side") or "buy").strip().lower(),
            size=float(payload.get("size") or payload.get("amount") or 0.0),
            broker_key=str(payload.get("broker_key") or payload.get("broker") or "unknown"),
            exchange=str(payload.get("exchange") or payload.get("broker") or "unknown"),
            status=str(payload.get("status") or "submitted"),
            fill_price=payload.get("fill_price") if payload.get("fill_price") is not None else payload.get("price"),
            requested_price=payload.get("requested_price"),
            fees=float(payload.get("fees") or 0.0),
            strategy_name=str(payload.get("strategy_name") or "unknown"),
            account_id=payload.get("account_id"),
            metadata=dict(payload.get("metadata") or {}),
        )
        self.update_position(update)
        await self._publish_state(symbol=update.symbol)

    async def _on_ticker(self, event) -> None:
        payload = dict(event.data or {})
        symbol = str(payload.get("symbol") or "").strip()
        if not symbol:
            return
        price = float(payload.get("price") or 0.0)
        if price <= 0:
            return
        updated = False
        for position in self.positions.values():
            if position.symbol != symbol or abs(float(position.quantity)) <= 1e-12:
                continue
            position.mark_price = price
            updated = True
        if updated:
            await self._publish_state(symbol=symbol)

    def update_position(self, update: ExecutionUpdate) -> PositionState:
        key = self._position_key(update.broker_key, update.symbol, update.account_id)
        position = self.positions.get(key)
        if position is None:
            position = PositionState(
                symbol=update.symbol,
                broker_key=update.broker_key,
                exchange=update.exchange,
                account_id=update.account_id,
                quantity=0.0,
                entry_price=0.0,
                mark_price=float(update.fill_price or update.requested_price or self.cache.latest_price(update.symbol) or 0.0),
                leverage=float((update.metadata or {}).get("leverage") or 1.0),
                used_margin=0.0,
                realized_pnl=0.0,
                metadata=dict(update.metadata or {}),
            )
            self.positions[key] = position

        fill_price = float(update.fill_price or update.requested_price or position.mark_price or 0.0)
        fees = float(update.fees or 0.0)
        position.mark_price = fill_price or position.mark_price
        signed_size = abs(float(update.size or 0.0))
        if update.side == "sell":
            signed_size *= -1.0

        existing_qty = float(position.quantity)
        realized = 0.0
        if abs(existing_qty) <= 1e-12:
            position.quantity = signed_size
            position.entry_price = fill_price
        elif existing_qty * signed_size > 0:
            new_qty = existing_qty + signed_size
            weighted_cost = (existing_qty * position.entry_price) + (signed_size * fill_price)
            position.quantity = new_qty
            if abs(new_qty) > 1e-12:
                position.entry_price = weighted_cost / new_qty
        else:
            closed_qty = min(abs(existing_qty), abs(signed_size))
            realized = (fill_price - position.entry_price) * closed_qty * (1.0 if existing_qty > 0 else -1.0)
            remaining_qty = existing_qty + signed_size
            position.quantity = remaining_qty
            position.realized_pnl += realized
            self.cash += realized
            if abs(remaining_qty) <= 1e-12:
                position.quantity = 0.0
                position.entry_price = 0.0
            elif remaining_qty * existing_qty < 0:
                position.entry_price = fill_price

        position.metadata.update(update.metadata or {})
        leverage = float(position.metadata.get("leverage") or position.leverage or 1.0)
        position.leverage = max(1.0, leverage)
        position.used_margin = abs(position.quantity * position.mark_price) / position.leverage if position.mark_price else 0.0
        if fees:
            position.realized_pnl -= fees
            self.cash -= fees
        return position

    def calculate_pnl(self) -> tuple[float, float]:
        realized = sum(float(position.realized_pnl or 0.0) for position in self.positions.values())
        unrealized = sum(float(position.unrealized_pnl or 0.0) for position in self.positions.values())
        return realized, unrealized

    def calculate_exposure(self) -> tuple[float, float, float]:
        gross = 0.0
        net = 0.0
        used_margin = 0.0
        for position in self.positions.values():
            market_value = float(position.market_value or 0.0)
            gross += abs(market_value)
            net += market_value
            used_margin += float(position.used_margin or 0.0)
        return gross, net, used_margin

    async def _publish_state(self, *, symbol: str | None = None) -> None:
        realized, unrealized = self.calculate_pnl()
        gross, net, used_margin = self.calculate_exposure()
        equity = self.starting_equity + realized + unrealized
        self.equity_high_watermark = max(self.equity_high_watermark, equity)
        free_margin = equity - used_margin
        drawdown_pct = 0.0
        if self.equity_high_watermark > 0:
            drawdown_pct = max(0.0, (self.equity_high_watermark - equity) / self.equity_high_watermark)

        state = PortfolioState(
            equity=equity,
            cash=self.cash + realized,
            free_margin=free_margin,
            used_margin=used_margin,
            positions=dict(self.positions),
            gross_exposure=gross,
            net_exposure=net,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            drawdown_pct=drawdown_pct,
            timestamp=datetime.now(timezone.utc),
        )
        if symbol:
            for key, position in list(self.positions.items()):
                if position.symbol == symbol:
                    await self.bus.publish("position.updated", position.to_dict(), source="portfolio_engine")
        await self.bus.publish("portfolio.updated", state.to_dict(), source="portfolio_engine")
