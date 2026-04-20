from __future__ import annotations

import logging
from typing import Any

from broker.ibkr.config import IBKRConfig
from broker.ibkr.family import IBKRBrokerFamilyAdapter
from broker.ibkr.tws.client import IBKRTwsClient
from broker.ibkr.tws.contracts import build_tws_contract
from broker.ibkr.tws.session import IBKRTwsSession
from models.instrument import InstrumentType


class IBKRTwsBroker(IBKRBrokerFamilyAdapter):
    """Dedicated TWS/IB Gateway transport path.

    TODO:
    - Replace the default placeholder adapter with an ibapi-backed runtime adapter.
    - Expand historical bars and live market-data subscriptions once the callback bridge is wired.
    - Add order-status callback normalization for live fills and partial fills.
    """

    supported_instrument_types = {
        InstrumentType.STOCK.value,
        InstrumentType.OPTION.value,
        InstrumentType.FUTURE.value,
        InstrumentType.FOREX.value,
    }

    def __init__(self, config: Any, *, ibkr_config: IBKRConfig | None = None, event_bus: Any = None) -> None:
        super().__init__(config, ibkr_config=ibkr_config, event_bus=event_bus)
        self.session_runtime = IBKRTwsSession(self.ibkr_config.tws, logger=self.logger.getChild("session"))
        self.client = IBKRTwsClient(self.session_runtime, logger=self.logger.getChild("client"))

    @property
    def session_state(self):
        return self.session_runtime.state

    async def _publish_state(self) -> None:
        if self.event_bus is not None and hasattr(self, "_publish_event"):
            payload = self.session_state.to_dict()
            payload["broker"] = self.exchange_name
            await self._publish_event("BROKER_STATE_EVENT", payload)

    async def connect(self):
        await self.client.connect()
        self._connected = True
        await self._publish_state()
        return True

    async def login(self):
        return await self.connect()

    async def logout(self):
        await self.close()

    def is_authenticated(self) -> bool:
        return bool(self.session_state.authenticated)

    async def refresh_session(self):
        await self._publish_state()
        return self.session_state.to_dict()

    async def close(self):
        await self.client.disconnect()
        self._connected = False
        await self._publish_state()

    async def get_accounts(self):
        if self.account_id:
            return self._canonical_accounts([{"account_id": self.account_id, "alias": None, "broker": self.exchange_name}])
        summary = await self.client.request_account_summary(self.account_id)
        account_id = str(summary.get("account_id") or self.account_id or "").strip()
        if account_id:
            self.account_id = account_id
            self.session_runtime.state.account_id = account_id
            return self._canonical_accounts([summary])
        return []

    async def get_account_balances(self, account_id=None):
        resolved_account = str(account_id or self.account_id or "").strip()
        summary = await self.client.request_account_summary(resolved_account or None)
        normalized_account = str(summary.get("account_id") or resolved_account or "").strip()
        if normalized_account:
            self.account_id = normalized_account
            self.session_runtime.state.account_id = normalized_account
        return self._canonical_balance_payload(summary, account_id=normalized_account or resolved_account or "ibkr")

    async def get_account_info(self):
        payload = await self.get_account_balances()
        await self._emit_account_event(payload)
        return payload

    async def get_positions(self, account_id=None):
        resolved_account = str(account_id or self.account_id or "").strip()
        positions = await self.client.request_positions(resolved_account or None)
        normalized = self._canonical_positions(
            positions,
            account_id=resolved_account or str(self.session_runtime.state.account_id or self.account_id or "ibkr"),
        )
        for position in normalized:
            await self._emit_position_event(position)
        return normalized

    async def get_quotes(self, symbols):
        quotes = await self.client.request_quotes(list(symbols or []))
        return self._canonical_quotes(quotes)

    async def fetch_ticker(self, symbol):
        quotes = await self.get_quotes([symbol])
        if quotes:
            return quotes[0]
        return {"symbol": str(symbol).strip().upper(), "broker": self.exchange_name}

    async def get_historical_bars(self, symbol, timeframe, start=None, end=None, limit=None):
        _ = (start, end)
        return await self.client.request_historical_bars(str(symbol).strip().upper(), str(timeframe or "1h"), limit=limit)

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        return await self.get_historical_bars(symbol, timeframe, start=start_time, end=end_time, limit=limit)

    async def list_orders(self, account_id=None, filters=None):
        _ = (account_id, filters)
        return []

    async def fetch_orders(self, symbol=None, limit=None):
        _ = (symbol, limit)
        return []

    async def fetch_open_orders(self, symbol=None, limit=None):
        _ = (symbol, limit)
        return []

    async def fetch_closed_orders(self, symbol=None, limit=None):
        _ = (symbol, limit)
        return []

    async def fetch_order(self, order_id, symbol=None):
        _ = (order_id, symbol)
        return None

    async def get_order(self, account_id, order_id):
        _ = account_id
        return await self.fetch_order(order_id)

    async def place_order(self, account_id, order_request=None):
        request = account_id if order_request is None and isinstance(account_id, dict) else dict(order_request or {})
        resolved_account = str(request.get("account_id") or request.get("account") or account_id or self.account_id or "").strip()
        contract = request.get("contract")
        if contract is not None:
            request.setdefault("contract", build_tws_contract(contract))
        normalized_request = self.mapper.order_request_from_order(request, account_id=resolved_account)
        execution = await self.client.place_order(resolved_account, request)
        execution = self._canonical_order_payload(execution, request=normalized_request)
        await self._emit_order_event(execution)
        return execution

    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        return await self.place_order(
            self.account_id or "",
            {
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "type": type,
                "price": price,
                "stop_price": stop_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "params": dict(params or {}),
            },
        )

    async def cancel_order(self, order_id, symbol=None):
        _ = symbol
        payload = await self.client.cancel_order(str(order_id))
        await self._emit_order_event(payload)
        return payload

    async def fetch_symbol(self):
        return list(self.options.get("symbols") or self.options.get("watchlist_symbols") or [])

    async def fetch_status(self):
        payload = self.session_state.to_dict()
        payload["broker"] = self.exchange_name
        return payload
