from __future__ import annotations

import logging
from typing import Any, Protocol

from broker.ibkr.exceptions import IBKRConfigurationError


class IBKRTwsAdapterProtocol(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def request_account_summary(self, account_id: str | None = None) -> dict[str, Any]: ...
    async def request_positions(self, account_id: str | None = None) -> list[dict[str, Any]]: ...
    async def request_quotes(self, symbols: list[str]) -> list[dict[str, Any]]: ...
    async def request_historical_bars(self, symbol: str, timeframe: str, limit: int | None = None) -> list[list[float]]: ...
    async def place_order(self, account_id: str, order: dict[str, Any]) -> dict[str, Any]: ...
    async def cancel_order(self, order_id: str) -> dict[str, Any]: ...


class MissingIBKRTwsAdapter:
    """Default placeholder until a project-specific ibapi runtime adapter is provided."""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("MissingIBKRTwsAdapter")

    async def connect(self) -> None:
        raise IBKRConfigurationError(
            "IBKR TWS mode requires a runtime adapter backed by Trader Workstation or IB Gateway. "
            "Install ibapi and provide an adapter factory to enable live TWS connectivity."
        )

    async def disconnect(self) -> None:
        return None

    async def request_account_summary(self, account_id: str | None = None) -> dict[str, Any]:
        raise IBKRConfigurationError("IBKR TWS account summary is not available without a runtime adapter.")

    async def request_positions(self, account_id: str | None = None) -> list[dict[str, Any]]:
        raise IBKRConfigurationError("IBKR TWS positions are not available without a runtime adapter.")

    async def request_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        raise IBKRConfigurationError("IBKR TWS quotes are not available without a runtime adapter.")

    async def request_historical_bars(self, symbol: str, timeframe: str, limit: int | None = None) -> list[list[float]]:
        raise IBKRConfigurationError(
            "IBKR TWS historical bars are scaffolded but still need an ibapi-backed request/callback adapter."
        )

    async def place_order(self, account_id: str, order: dict[str, Any]) -> dict[str, Any]:
        raise IBKRConfigurationError("IBKR TWS order placement is not available without a runtime adapter.")

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        raise IBKRConfigurationError("IBKR TWS order cancelation is not available without a runtime adapter.")


def create_default_tws_adapter(*, logger: logging.Logger | None = None) -> IBKRTwsAdapterProtocol:
    _ = logger
    return MissingIBKRTwsAdapter(logger=logger)
