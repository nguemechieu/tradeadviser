from __future__ import annotations

import logging
from typing import Any

from broker.ibkr.config import IBKRTwsConfig
from broker.ibkr.models import IBKRSessionStatus
from broker.ibkr.tws.session import IBKRTwsSession
from broker.ibkr.tws.wrappers import create_default_tws_adapter


class IBKRTwsClient:
    """TWS/IB Gateway client facade around a runtime adapter."""

    def __init__(
        self,
        session: IBKRTwsSession,
        *,
        logger: logging.Logger | None = None,
        adapter_factory=None,
    ) -> None:
        self.session = session
        self.logger = logger or logging.getLogger("IBKRTwsClient")
        self.adapter_factory = adapter_factory or create_default_tws_adapter
        self.adapter = self.adapter_factory(logger=self.logger.getChild("adapter"))

    @property
    def config(self) -> IBKRTwsConfig:
        return self.session.config

    async def connect(self) -> None:
        self.session.update_state(status=IBKRSessionStatus.CONNECTING)
        await self.adapter.connect()
        self.session.update_state(
            status=IBKRSessionStatus.AUTHENTICATED,
            connected=True,
            authenticated=True,
            last_error="",
        )

    async def disconnect(self) -> None:
        await self.adapter.disconnect()
        self.session.update_state(
            status=IBKRSessionStatus.DISCONNECTED,
            connected=False,
            authenticated=False,
        )

    async def request_account_summary(self, account_id: str | None = None) -> dict[str, Any]:
        return await self.adapter.request_account_summary(account_id or self.config.account_id)

    async def request_positions(self, account_id: str | None = None) -> list[dict[str, Any]]:
        return await self.adapter.request_positions(account_id or self.config.account_id)

    async def request_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        return await self.adapter.request_quotes(symbols)

    async def request_historical_bars(self, symbol: str, timeframe: str, limit: int | None = None) -> list[list[float]]:
        return await self.adapter.request_historical_bars(symbol, timeframe, limit=limit)

    async def place_order(self, account_id: str, order: dict[str, Any]) -> dict[str, Any]:
        return await self.adapter.place_order(account_id, order)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        return await self.adapter.cancel_order(order_id)
