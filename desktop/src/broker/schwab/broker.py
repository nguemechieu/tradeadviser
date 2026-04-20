from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from broker.base_broker import BaseDerivativeBroker
from models.instrument import InstrumentType

from core.oauth.session import OAuthSessionManager
from .auth import SchwabOAuthService
from .client import SchwabApiClient
from .config import build_schwab_config
from .exceptions import SchwabConfigurationError
from .mapper import SchwabMapper
from .token_store import SchwabTokenStore
from .validators import validate_schwab_config

class SchwabBroker(BaseDerivativeBroker):
    """Dedicated Charles Schwab broker adapter with reusable OAuth session handling."""

    supported_instrument_types = {
        InstrumentType.STOCK.value,
        InstrumentType.OPTION.value,
    }

    def __init__(self, config: Any, event_bus: Any = None) -> None:
        super().__init__(config, event_bus=event_bus)
        self.exchange_name = "schwab"
        self.logger = logging.getLogger("SchwabBroker")
        self.controller = None
        self.mapper = SchwabMapper(
            default_contract_size=int(
                self.options.get("default_contract_size")
                or self.params.get("default_contract_size")
                or 100
            )
        )
        self.schwab_config = validate_schwab_config(build_schwab_config(config))
        self.token_store = SchwabTokenStore()
        self.oauth_session = OAuthSessionManager(
            provider="schwab",
            profile_key=str(self.schwab_config.token_profile_key or "schwab").strip(),
            environment=self.schwab_config.environment,
            token_store=self.token_store,
        )
        self.auth = SchwabOAuthService(
            self.schwab_config,
            session_manager=self.oauth_session,
            logger=self.logger.getChild("auth"),
        )
        self.client = SchwabApiClient(
            self.schwab_config,
            self.auth,
            mapper=self.mapper,
            logger=self.logger.getChild("client"),
        )
        self.account_hash = str(self.schwab_config.account_hash or "").strip() or None
        self.account_id = str(self.schwab_config.account_id or self.account_id or "").strip() or None
        self._account_cache: list[dict[str, Any]] = []

    @property
    def session_state(self):
        return self.oauth_session.state

    async def _publish_state(self) -> None:
        payload = self.session_state.to_dict()
        payload["broker"] = self.exchange_name
        payload["connected"] = bool(self._connected)
        payload["account_id"] = self.account_id
        payload["account_hash"] = self.account_hash
        if self.event_bus is not None and hasattr(self, "_publish_event"):
            await self._publish_event("BROKER_STATE_EVENT", payload)

    async def connect(self):
        self.auth.controller = self.controller
        self.oauth_session.mark_status("connecting", authenticated=False)
        await self.client.open()
        await self.auth.ensure_session(interactive=True)
        await self._refresh_account_cache()
        self._connected = True
        self.oauth_session.mark_status(
            "authenticated",
            authenticated=True,
            metadata={"account_id": self.account_id, "account_hash": self.account_hash},
        )
        await self._publish_state()
        self.logger.info(
            "Schwab session authenticated environment=%s account_id=%s",
            self.schwab_config.environment,
            self.account_id or "not-set",
        )
        return True

    async def login(self):
        return await self.connect()

    async def logout(self):
        self.auth.clear()
        await self.close()

    def is_authenticated(self):
        return bool(self.oauth_session.has_valid_access_token(skew_seconds=self.schwab_config.refresh_skew_seconds))

    async def refresh_session(self):
        await self.auth.refresh_tokens()
        await self._publish_state()
        return self.session_state.to_dict()

    async def close(self):
        await self.client.close()
        self._connected = False
        self.oauth_session.mark_status("disconnected", authenticated=False)
        await self._publish_state()

    async def get_accounts(self):
        if self._account_cache:
            return [dict(item) for item in self._account_cache]
        await self._refresh_account_cache()
        return [dict(item) for item in self._account_cache]

    async def get_account_balances(self, account_id=None):
        resolved_account_id, resolved_hash = await self._resolve_account(account_id)
        return await self.client.get_account_balances(resolved_hash, account_id=resolved_account_id)

    async def get_account_info(self):
        payload = await self.get_account_balances()
        await self._emit_account_event(payload)
        return payload

    async def get_positions(self, account_id=None):
        resolved_account_id, resolved_hash = await self._resolve_account(account_id)
        positions = await self.client.get_positions(resolved_hash, account_id=resolved_account_id)
        for position in positions:
            await self._emit_position_event(position)
        return positions

    async def get_quotes(self, symbols):
        return await self.client.get_quotes(list(symbols or []))

    async def fetch_ticker(self, symbol):
        quotes = await self.get_quotes([symbol])
        if quotes:
            payload = dict(quotes[0])
            payload.setdefault("price", payload.get("last") or payload.get("mark") or payload.get("close"))
            return payload
        return {"symbol": str(symbol or "").strip().upper(), "broker": self.exchange_name}

    async def get_historical_bars(self, symbol, timeframe, start=None, end=None, limit=None):
        return await self.client.get_historical_bars(
            str(symbol or "").strip().upper(),
            str(timeframe or "1h"),
            start=start,
            end=end,
            limit=limit,
        )

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        return await self.get_historical_bars(symbol, timeframe, start=start_time, end=end_time, limit=limit)

    async def list_orders(self, account_id=None, filters=None):
        filters = dict(filters or {})
        resolved_account_id, resolved_hash = await self._resolve_account(account_id)
        return await self.client.list_orders(
            resolved_hash,
            account_id=resolved_account_id,
            symbol=filters.get("symbol"),
            status=filters.get("status"),
            limit=filters.get("limit"),
        )

    async def fetch_orders(self, symbol=None, limit=None):
        return await self.list_orders(filters={"symbol": symbol, "limit": limit})

    async def fetch_open_orders(self, symbol=None, limit=None):
        return await self.list_orders(filters={"symbol": symbol, "status": "open", "limit": limit})

    async def fetch_closed_orders(self, symbol=None, limit=None):
        return await self.list_orders(filters={"symbol": symbol, "status": "closed", "limit": limit})

    async def fetch_order(self, order_id, symbol=None):
        resolved_account_id, resolved_hash = await self._resolve_account(None)
        payload = await self.client.get_order(resolved_hash, resolved_account_id, str(order_id))
        if not payload:
            return None
        if symbol and str(payload.get("symbol") or "").strip().upper() != str(symbol).strip().upper():
            return None
        return payload

    async def get_order(self, account_id, order_id):
        resolved_account_id, resolved_hash = await self._resolve_account(account_id)
        return await self.client.get_order(resolved_hash, resolved_account_id, str(order_id))

    async def place_order(self, account_id, order_request=None):
        request = account_id if order_request is None and isinstance(account_id, Mapping) else dict(order_request or {})
        requested_account = str(
            request.get("account_id")
            or request.get("account")
            or account_id
            or self.account_id
            or ""
        ).strip()
        resolved_account_id, resolved_hash = await self._resolve_account(requested_account or None)
        execution = await self.client.place_order(resolved_hash, resolved_account_id, request)
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
        resolved_account_id, _resolved_hash = await self._resolve_account(None)
        return await self.place_order(
            resolved_account_id,
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

    async def cancel_order(self, order_or_account_id, order_id=None, *, symbol=None):
        if order_id is None:
            resolved_account_id, resolved_hash = await self._resolve_account(None)
            target_order_id = str(order_or_account_id)
        else:
            resolved_account_id, resolved_hash = await self._resolve_account(order_or_account_id)
            target_order_id = str(order_id)
        execution = await self.client.cancel_order(
            resolved_hash,
            resolved_account_id,
            target_order_id,
            symbol=symbol,
        )
        await self._emit_order_event(execution)
        return execution

    async def fetch_symbol(self):
        symbols = []
        configured = self.options.get("symbols") or self.options.get("watchlist_symbols") or []
        if isinstance(configured, str):
            configured = [item.strip() for item in configured.split(",") if item.strip()]
        for value in configured:
            normalized = str(value or "").strip().upper()
            if normalized and normalized not in symbols:
                symbols.append(normalized)
        for position in await self.get_positions():
            normalized = str(position.get("symbol") or "").strip().upper()
            if normalized and normalized not in symbols:
                symbols.append(normalized)
        return symbols

    async def get_option_chain(self, symbol, **kwargs):
        return await self.client.get_option_chain(str(symbol or "").strip().upper(), **kwargs)

    async def fetch_status(self):
        payload = self.session_state.to_dict()
        payload["broker"] = self.exchange_name
        payload["connected"] = bool(self._connected)
        payload["account_id"] = self.account_id
        payload["account_hash"] = self.account_hash
        return payload

    async def _refresh_account_cache(self) -> list[dict[str, Any]]:
        accounts = await self.client.get_accounts()
        if not accounts and self.account_hash:
            accounts = [
                {
                    "broker": self.exchange_name,
                    "account_id": self.account_id or self.account_hash,
                    "account_hash": self.account_hash,
                    "alias": None,
                    "account_type": None,
                    "currency": "USD",
                    "raw": {},
                }
            ]
        self._account_cache = [dict(item) for item in list(accounts or []) if isinstance(item, Mapping)]
        selected = None
        if self.account_id:
            selected = self._account_from_cache(self.account_id)
        if selected is None and self.account_hash:
            selected = self._account_from_cache(self.account_hash)
        if selected is None and self._account_cache:
            selected = self._account_cache[0]
        if selected is not None:
            self.account_id = str(selected.get("account_id") or self.account_id or "").strip() or None
            self.account_hash = str(selected.get("account_hash") or self.account_hash or "").strip() or None
        return [dict(item) for item in self._account_cache]

    def _account_from_cache(self, selector: str | None) -> dict[str, Any] | None:
        normalized = str(selector or "").strip()
        if not normalized:
            return None
        for account in self._account_cache:
            if str(account.get("account_id") or "").strip() == normalized:
                return dict(account)
            if str(account.get("account_hash") or "").strip() == normalized:
                return dict(account)
        return None

    async def _resolve_account(self, account_id: str | None) -> tuple[str, str]:
        requested = str(account_id or "").strip()
        account = self._account_from_cache(requested)
        if account is None and not self._account_cache:
            await self._refresh_account_cache()
            account = self._account_from_cache(requested)
        if account is None and requested and self.account_hash:
            return (requested, str(self.account_hash))
        if account is None and self._account_cache:
            account = dict(self._account_cache[0])
        if account is None and self.account_hash:
            fallback_id = requested or self.account_id or self.account_hash
            return (str(fallback_id), str(self.account_hash))
        if account is None:
            raise SchwabConfigurationError("No Schwab account is available for this session.")
        resolved_id = str(account.get("account_id") or requested or self.account_id or "").strip()
        resolved_hash = str(account.get("account_hash") or self.account_hash or "").strip()
        if not resolved_hash:
            raise SchwabConfigurationError("Schwab account hash could not be resolved.")
        self.account_id = resolved_id or self.account_id
        self.account_hash = resolved_hash or self.account_hash
        return (self.account_id or resolved_hash, resolved_hash)
