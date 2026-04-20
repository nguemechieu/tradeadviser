from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from execution.virtual_trade_manager import VirtualTradeManager
from sopotek.core.event_bus import AsyncEventBus
from sopotek.core.event_types import EventType


class TradeWatcher:
    """Non-blocking watcher that feeds live prices into the virtual exit manager."""

    def __init__(
        self,
        event_bus: AsyncEventBus,
        virtual_trade_manager: VirtualTradeManager,
        *,
        poll_interval: float = 0.25,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.virtual_trade_manager = virtual_trade_manager
        self.poll_interval = max(0.01, float(poll_interval))
        self.logger = logger or logging.getLogger("TradeWatcher")
        self.latest_prices: dict[str, float] = {}
        self._task: asyncio.Task[Any] | None = None
        self._running = False

        self.bus.subscribe(EventType.PRICE_UPDATE, self._on_price_event)
        self.bus.subscribe(EventType.MARKET_TICK, self._on_price_event)

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="trade_watcher")

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def check_once(self) -> None:
        await self.virtual_trade_manager.check_exit_conditions(self.latest_prices)

    async def _run(self) -> None:
        try:
            while self._running:
                await self.check_once()
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger.exception("TradeWatcher loop failed")
            raise

    async def _on_price_event(self, event) -> None:
        payload = getattr(event, "data", None)
        if payload is None:
            return
        if not isinstance(payload, dict):
            payload = getattr(payload, "__dict__", {})
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        price = float(payload.get("price") or payload.get("last") or payload.get("close") or 0.0)
        if price <= 0.0:
            return
        self.latest_prices[symbol] = price
