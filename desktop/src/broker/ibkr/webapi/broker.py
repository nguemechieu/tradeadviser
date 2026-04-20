from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Mapping
from typing import Any

from broker.ibkr.config import IBKRConfig
from broker.ibkr.exceptions import IBKRConfigurationError
from broker.ibkr.family import IBKRBrokerFamilyAdapter
from broker.ibkr.models import IBKRSessionStatus
from broker.ibkr.webapi.auth import IBKRWebApiAuthenticator
from broker.ibkr.webapi.client import IBKRWebApiClient
from broker.ibkr.webapi.session import IBKRWebApiSession
from broker.ibkr.webapi.websocket import IBKRWebApiWebSocket
from models.instrument import InstrumentType


class IBKRWebApiBroker(IBKRBrokerFamilyAdapter):
    supported_instrument_types = {
        InstrumentType.STOCK.value,
        InstrumentType.OPTION.value,
        InstrumentType.FUTURE.value,
        InstrumentType.FOREX.value,
    }

    def __init__(self, config: Any, *, ibkr_config: IBKRConfig | None = None, event_bus: Any = None) -> None:
        super().__init__(config, ibkr_config=ibkr_config, event_bus=event_bus)
        self.session_transport = IBKRWebApiSession(self.ibkr_config.webapi, logger=self.logger.getChild("session"))
        self.auth = IBKRWebApiAuthenticator(self.session_transport, logger=self.logger.getChild("auth"))
        self.client = IBKRWebApiClient(
            self.session_transport,
            self.auth,
            mapper=self.mapper,
            logger=self.logger.getChild("client"),
        )
        self.account_id = self.ibkr_config.account_id
        self._streaming_task: asyncio.Task[Any] | None = None
        self._ws_client: IBKRWebApiWebSocket | None = None

    @property
    def session_state(self):
        return self.session_transport.state

    async def _publish_state(self) -> None:
        payload = self.session_state.to_dict()
        payload["broker"] = self.exchange_name
        if self.event_bus is not None and hasattr(self, "_publish_event"):
            await self._publish_event("BROKER_STATE_EVENT", payload)

    async def connect(self):
        await self.session_transport.open()
        await self.auth.bootstrap()
        self._connected = True
        self.account_id = self.session_state.account_id or self.account_id
        await self._publish_state()
        return True

    async def login(self):
        return await self.connect()

    async def logout(self):
        await self.close()

    def is_authenticated(self) -> bool:
        return bool(self.session_state.authenticated)

    async def refresh_session(self):
        payload = await self.auth.refresh()
        self.account_id = self.session_state.account_id or self.account_id
        await self._publish_state()
        return payload

    async def close(self):
        self.stop_market_data_stream()
        if self._streaming_task is not None and not self._streaming_task.done():
            self._streaming_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._streaming_task
        if self._ws_client is not None:
            await self._ws_client.close()
            self._ws_client = None
        await self.session_transport.close()
        self._connected = False
        await self._publish_state()

    async def get_accounts(self):
        accounts = await self.client.get_accounts()
        if accounts and not self.account_id:
            self.account_id = str(accounts[0].get("account_id") or "").strip() or None
            self.session_transport.state.account_id = self.account_id
        return accounts

    async def _resolved_account_id(self) -> str:
        account_id = str(self.account_id or self.session_transport.state.account_id or "").strip()
        if account_id:
            return account_id
        accounts = await self.get_accounts()
        if not accounts:
            raise IBKRConfigurationError("No Interactive Brokers account was returned by the Web API.")
        account_id = str(accounts[0].get("account_id") or "").strip()
        self.account_id = account_id or None
        self.session_transport.state.account_id = self.account_id
        return account_id

    async def get_account_balances(self, account_id=None):
        resolved = str(account_id or await self._resolved_account_id()).strip()
        return await self.client.get_account_balances(resolved)

    async def get_account_info(self):
        balances = await self.get_account_balances()
        payload = dict(balances or {})
        payload["broker"] = self.exchange_name
        await self._emit_account_event(payload)
        return payload

    async def get_positions(self, account_id=None):
        resolved = str(account_id or await self._resolved_account_id()).strip()
        positions = await self.client.get_positions(resolved)
        for position in positions:
            await self._emit_position_event(position)
        return positions

    async def get_quotes(self, symbols):
        return await self.client.get_quotes(list(symbols or []))

    async def fetch_ticker(self, symbol):
        quotes = await self.get_quotes([symbol])
        if quotes:
            return quotes[0]
        return {"symbol": str(symbol).strip().upper(), "broker": self.exchange_name}

    async def get_historical_bars(self, symbol, timeframe, start=None, end=None, limit=None):
        return await self.client.get_historical_bars(
            str(symbol).strip().upper(),
            str(timeframe or "1h"),
            start=start,
            end=end,
            limit=limit,
        )

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        return await self.get_historical_bars(symbol, timeframe, start=start_time, end=end_time, limit=limit)

    async def list_orders(self, account_id=None, filters=None):
        filters = dict(filters or {})
        return await self.client.list_orders(
            symbol=filters.get("symbol"),
            status=filters.get("status"),
            limit=filters.get("limit"),
        )

    async def fetch_orders(self, symbol=None, limit=None):
        return await self.client.list_orders(symbol=symbol, limit=limit)

    async def fetch_open_orders(self, symbol=None, limit=None):
        return await self.client.list_orders(symbol=symbol, status="open", limit=limit)

    async def fetch_closed_orders(self, symbol=None, limit=None):
        return await self.client.list_orders(symbol=symbol, status="closed", limit=limit)

    async def fetch_order(self, order_id, symbol=None):
        for order in await self.client.list_orders(symbol=symbol):
            if str(order.get("id")) == str(order_id):
                return order
        return None

    async def get_order(self, account_id, order_id):
        _ = account_id
        return await self.fetch_order(order_id)

    async def place_order(self, account_id, order_request=None):
        request = account_id if order_request is None and isinstance(account_id, Mapping) else order_request
        resolved_account = str(
            (request or {}).get("account_id")
            or (request or {}).get("account")
            or account_id
            or await self._resolved_account_id()
        ).strip()
        execution = await self.client.place_order(resolved_account, dict(request or {}))
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
            await self._resolved_account_id(),
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
        execution = await self.client.cancel_order(await self._resolved_account_id(), str(order_id), symbol=symbol)
        await self._emit_order_event(execution)
        return execution

    async def fetch_symbol(self):
        accounts = await self.get_accounts()
        symbols = []
        configured = self.options.get("symbols") or self.options.get("watchlist_symbols") or []
        if isinstance(configured, str):
            configured = [item.strip() for item in configured.split(",") if item.strip()]
        for value in configured:
            normalized = str(value or "").strip().upper()
            if normalized and normalized not in symbols:
                symbols.append(normalized)
        for position in await self.get_positions(account_id=(accounts[0]["account_id"] if accounts else None)):
            normalized = str(position.get("symbol") or "").strip().upper()
            if normalized and normalized not in symbols:
                symbols.append(normalized)
        return symbols

    async def subscribe_market_data(self, symbols):
        topics = []
        for symbol in list(symbols or []):
            contract = await self.client.resolve_contract(symbol)
            if contract.conid:
                topics.append(f"smd+{contract.conid}")
        if not topics or not self.ibkr_config.webapi.websocket_enabled:
            return False
        self._ws_client = IBKRWebApiWebSocket(
            self.ibkr_config.webapi.resolved_websocket_url(),
            logger=self.logger.getChild("websocket"),
        )
        await self._ws_client.connect()
        await self._ws_client.subscribe_topics(topics)
        return True

    async def unsubscribe_market_data(self, symbols):
        _ = symbols
        self.stop_market_data_stream()
        return True

    def stop_market_data_stream(self):
        super().stop_market_data_stream()
        task = self._streaming_task
        if task is not None and not task.done():
            task.cancel()

    async def stream_market_data(self, symbols):
        try:
            subscribed = await self.subscribe_market_data(symbols)
        except Exception:
            self.logger.debug("IBKR Web API websocket subscribe failed; falling back to polling", exc_info=True)
            subscribed = False
        if not subscribed or self._ws_client is None:
            await super().stream_market_data(symbols)
            return
        self._streaming_market_data = True
        try:
            async for raw_message in self._ws_client.receive_forever():
                if not self._streaming_market_data:
                    break
                if isinstance(raw_message, Mapping):
                    payload = dict(raw_message)
                else:
                    payload = {"raw": raw_message}
                payload.setdefault("broker", self.exchange_name)
                await self._emit_market_data_event(payload)
        finally:
            self._streaming_market_data = False

    async def fetch_status(self):
        payload = self.session_state.to_dict()
        payload["broker"] = self.exchange_name
        return payload
