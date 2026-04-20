from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from core.monitoring.latency_tracker import LatencyTracker

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional dependency in stripped test environments
    aiohttp = None

try:
    import websockets
except ImportError:  # pragma: no cover - optional dependency in stripped test environments
    websockets = None

from broker.market_venues import supported_market_venues_for_profile
from core.event_bus.event import Event
from core.event_bus.event_types import EventType
from models.instrument import Instrument
from models.order import Order

from core.monitoring.latency_tracker import LatencyTracker

class BaseBroker(ABC):
    DEFAULT_STREAM_POLL_SECONDS = 1.0

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(self.__class__.__name__)
        self._streaming_market_data = False
        self.latency_tracker = LatencyTracker()  # ✅ FIX

    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def close(self):
        pass

    async def disconnect(self):
        await self.close()

    async def login(self):
        return await self.connect()

    async def logout(self):
        await self.close()

    def is_authenticated(self):
        connected = getattr(self, "_connected", None)
        if isinstance(connected, bool):
            return connected
        return False

    async def refresh_session(self):
        return {"authenticated": bool(self.is_authenticated())}

    def attach_event_bus(self, event_bus):
        self.event_bus = event_bus
        return self

    async def _publish_event(self, event_type, payload):
        if self.event_bus is None:
            return None
        event = Event(event_type, payload)
        await self.event_bus.publish(event)
        return event

    async def _emit_market_data_event(self, payload):
        payload = dict(payload or {})
        payload.setdefault("broker", getattr(self, "exchange_name", None))
        await self._publish_event(EventType.MARKET_DATA_EVENT, payload)
        await self._publish_event(EventType.MARKET_DATA, payload)
        await self._publish_event(EventType.MARKET_TICK, payload)

    async def _emit_order_event(self, payload):
        payload = dict(payload or {})
        payload.setdefault("broker", getattr(self, "exchange_name", None))
        await self._publish_event(EventType.ORDER_EVENT, payload)
        await self._publish_event(EventType.EXECUTION_REPORT, payload)

    async def _emit_position_event(self, payload):
        await self._publish_event(EventType.POSITION_EVENT, dict(payload or {}))
        await self._publish_event(EventType.POSITION, dict(payload or {}))

    async def _emit_account_event(self, payload):
        await self._publish_event(EventType.ACCOUNT_EVENT, dict(payload or {}))
        await self._publish_event(EventType.PORTFOLIO_SNAPSHOT, dict(payload or {}))

    @staticmethod
    def _coerce_mapping(value):
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
            return dict(value.to_dict())
        if is_dataclass(value):
            return dict(value.__dict__)
        raise TypeError(f"Expected a mapping-compatible value, got {type(value)!r}")

    @staticmethod
    def _symbol_from_order_payload(payload):
        if payload.get("symbol"):
            return str(payload["symbol"]).strip().upper()
        instrument = payload.get("instrument")
        if instrument is not None:
            if isinstance(instrument, Instrument):
                return instrument.symbol
            if isinstance(instrument, Mapping):
                symbol = instrument.get("symbol")
                if symbol:
                    return str(symbol).strip().upper()
        return ""

    # ===============================
    # MARKET DATA
    # ===============================

    @abstractmethod
    async def fetch_ticker(self, symbol):
        pass

    async def fetch_tickers(self, symbols=None):
        symbols = list(symbols or [])
        snapshots = []
        for symbol in symbols:
            snapshots.append(await self.fetch_ticker(symbol))
        return snapshots

    async def get_quotes(self, symbols):
        return await self.fetch_tickers(symbols)

    async def fetch_orderbook(self, symbol, limit=50):
        raise NotImplementedError("fetch_orderbook is not implemented for this broker")

    async def fetch_order_book(self, symbol, limit=50):
        return await self.fetch_orderbook(symbol, limit=limit)

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        raise NotImplementedError("fetch_ohlcv is not implemented for this broker")

    async def get_historical_bars(self, symbol, timeframe, start=None, end=None, limit=None):
        kwargs = {"timeframe": timeframe, "limit": limit}
        if start is not None:
            kwargs["start_time"] = start
        if end is not None:
            kwargs["end_time"] = end
        return await self.fetch_ohlcv(symbol, **kwargs)

    async def fetch_trades(self, symbol, limit=None):
        raise NotImplementedError("fetch_trades is not implemented for this broker")

    async def fetch_my_trades(self, symbol=None, limit=None):
        raise NotImplementedError("fetch_my_trades is not implemented for this broker")

    async def fetch_markets(self):
        raise NotImplementedError("fetch_markets is not implemented for this broker")

    async def fetch_currencies(self):
        raise NotImplementedError("fetch_currencies is not implemented for this broker")

    async def fetch_status(self):
        raise NotImplementedError("fetch_status is not implemented for this broker")

    async def stream_market_data(self, symbols):
        normalized_symbols = [
            str(symbol.symbol if isinstance(symbol, Instrument) else symbol).strip().upper()
            for symbol in (symbols or [])
            if str(symbol.symbol if isinstance(symbol, Instrument) else symbol).strip()
        ]
        if not normalized_symbols:
            return

        poll_interval = max(
            0.2,
            float(getattr(self, "market_data_poll_interval", self.DEFAULT_STREAM_POLL_SECONDS) or self.DEFAULT_STREAM_POLL_SECONDS),
        )
        self._streaming_market_data = True
        try:
            while self._streaming_market_data:
                for symbol in normalized_symbols:
                    ticker = await self.fetch_ticker(symbol)
                    if isinstance(ticker, Mapping):
                        payload = dict(ticker)
                        payload.setdefault("symbol", symbol)
                        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                        await self._emit_market_data_event(payload)
                await asyncio.sleep(poll_interval)
        finally:
            self._streaming_market_data = False

    def stop_market_data_stream(self):
        self._streaming_market_data = False

    async def subscribe_market_data(self, symbols):
        await self.stream_market_data(symbols)
        return True

    async def unsubscribe_market_data(self, symbols=None):
        _ = symbols
        self.stop_market_data_stream()
        return True

    # ===============================
    # TRADING
    # ===============================

    @abstractmethod
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
        pass

    async def place_order(self, order):
        payload = Order.from_mapping(order).to_dict()
        params = dict(payload.get("params") or {})
        if payload.get("instrument") is not None:
            params.setdefault("instrument", payload.get("instrument"))
        if payload.get("legs"):
            params.setdefault("legs", payload.get("legs"))
        if payload.get("broker"):
            params.setdefault("broker", payload.get("broker"))
        if payload.get("client_order_id"):
            params.setdefault("client_order_id", payload.get("client_order_id"))
        if payload.get("time_in_force"):
            params.setdefault("time_in_force", payload.get("time_in_force"))
        execution = await self.create_order(
            symbol=self._symbol_from_order_payload(payload),
            side=payload.get("side"),
            amount=payload.get("amount", payload.get("quantity")),
            type=payload.get("type", payload.get("order_type", "market")),
            price=payload.get("price"),
            stop_price=payload.get("stop_price"),
            params=params,
            stop_loss=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
        )
        if isinstance(execution, Mapping):
            await self._emit_order_event(dict(execution))
        return execution

    @abstractmethod
    async def cancel_order(self, order_id, symbol=None):
        pass

    async def cancel_all_orders(self, symbol=None):
        raise NotImplementedError("cancel_all_orders is not implemented for this broker")

    async def get_order(self, account_id, order_id):
        _ = account_id
        return await self.fetch_order(order_id)

    async def list_orders(self, account_id=None, filters=None):
        _ = account_id
        filters = dict(filters or {})
        return await self.fetch_orders(symbol=filters.get("symbol"), limit=filters.get("limit"))

    # ===============================
    # ACCOUNT
    # ===============================

    @abstractmethod
    async def fetch_balance(self):
        pass

    async def get_account_info(self):
        account = await self.fetch_balance()
        if isinstance(account, Mapping):
            await self._emit_account_event(dict(account))
        return account

    async def get_accounts(self):
        account = await self.get_account_info()
        if isinstance(account, Mapping):
            return [dict(account)]
        if isinstance(account, Sequence):
            return list(account)
        return []

    async def get_account_balances(self, account_id=None):
        _ = account_id
        return await self.fetch_balance()

    async def fetch_positions(self, symbols=None):
        raise NotImplementedError("fetch_positions is not implemented for this broker")

    async def get_positions(self):
        positions = await self.fetch_positions()
        if isinstance(positions, list):
            for position in positions:
                if isinstance(position, Mapping):
                    await self._emit_position_event(dict(position))
        return positions

    async def fetch_position(self, symbol):
        positions = await self.fetch_positions(symbols=[symbol])
        if isinstance(positions, list):
            for position in positions:
                if isinstance(position, dict) and position.get("symbol") == symbol:
                    return position
        return None

    def _position_amount(self, position):
        if not isinstance(position, dict):
            return 0.0
        for key in ("amount", "qty", "quantity", "size", "contracts"):
            value = position.get(key)
            if value is None:
                continue
            try:
                amount = abs(float(value))
            except Exception:
                continue
            if amount > 0:
                return amount
        return 0.0

    def _position_side(self, position):
        if not isinstance(position, dict):
            return None
        side = position.get("side")
        if side is not None:
            return str(side).lower()
        amount = position.get("amount")
        try:
            numeric = float(amount)
        except Exception:
            return None
        if numeric < 0:
            return "short"
        if numeric > 0:
            return "long"
        return None

    async def close_position(
        self,
        symbol,
        amount=None,
        params=None,
        order_type="market",
        position=None,
        position_side=None,
        position_id=None,
    ):
        target_position = position if isinstance(position, dict) else None
        if not isinstance(target_position, dict):
            try:
                positions = await self.fetch_positions(symbols=[symbol])
            except TypeError:
                positions = await self.fetch_positions()
            except Exception:
                positions = []

            candidates = [
                item
                for item in (positions or [])
                if isinstance(item, dict) and item.get("symbol") == symbol
            ]
            if position_id:
                normalized_id = str(position_id).strip().lower()
                candidates = [
                    item
                    for item in candidates
                    if str(
                        item.get("position_id")
                        or item.get("id")
                        or item.get("trade_id")
                        or ""
                    ).strip().lower() == normalized_id
                ]
            if position_side:
                normalized_side = str(position_side).strip().lower()
                candidates = [
                    item
                    for item in candidates
                    if str(item.get("position_side") or item.get("side") or "").strip().lower() == normalized_side
                ]
            if len(candidates) > 1 and self.supports_hedging():
                raise ValueError(
                    f"Multiple hedge legs are open for {symbol}. Specify the long or short position to close."
                )
            target_position = candidates[0] if candidates else await self.fetch_position(symbol)

        if not isinstance(target_position, dict):
            return None

        close_amount = self._position_amount(target_position) if amount is None else abs(float(amount))
        if close_amount <= 0:
            return None

        side = self._position_side(target_position)
        close_side = "buy" if side in {"short", "sell"} else "sell"
        return await self.create_order(
            symbol=symbol,
            side=close_side,
            amount=close_amount,
            type=order_type,
            params=params,
        )

    async def close_all_positions(self, symbols=None, params=None, order_type="market"):
        try:
            positions = await self.fetch_positions(symbols=symbols)
        except TypeError:
            positions = await self.fetch_positions()

        closed = []
        for position in positions or []:
            if not isinstance(position, dict):
                continue
            symbol = position.get("symbol")
            if not symbol:
                continue
            result = await self.close_position(
                symbol=symbol,
                amount=self._position_amount(position),
                params=params,
                order_type=order_type,
                position=position,
                position_side=position.get("position_side") or position.get("side"),
                position_id=position.get("position_id") or position.get("id"),
            )
            if result is not None:
                closed.append(result)
        return closed

    async def fetch_order(self, order_id, symbol=None):
        raise NotImplementedError("fetch_order is not implemented for this broker")

    async def fetch_orders(self, symbol=None, limit=None):
        raise NotImplementedError("fetch_orders is not implemented for this broker")

    async def fetch_open_orders(self, symbol=None, limit=None):
        raise NotImplementedError("fetch_open_orders is not implemented for this broker")

    async def fetch_open_orders_snapshot(self, symbols=None, limit=None):
        if not symbols:
            return await self.fetch_open_orders(limit=limit)

        snapshot = []
        seen = set()
        for symbol in dict.fromkeys(str(item).strip() for item in (symbols or []) if str(item).strip()):
            try:
                orders = await self.fetch_open_orders(symbol=symbol, limit=limit)
            except TypeError:
                orders = await self.fetch_open_orders(symbol)

            for order in orders or []:
                if isinstance(order, dict):
                    key = (
                        str(order.get("id") or ""),
                        str(order.get("clientOrderId") or ""),
                        str(order.get("symbol") or symbol),
                        str(order.get("status") or ""),
                    )
                else:
                    key = (str(order), "", symbol, "")
                if key in seen:
                    continue
                seen.add(key)
                snapshot.append(order)

        return snapshot

    async def fetch_closed_orders(self, symbol=None, limit=None):
        raise NotImplementedError("fetch_closed_orders is not implemented for this broker")

    async def fetch_symbol(self):
        raise NotImplementedError("fetch_symbol is not implemented for this broker")

    async def fetch_symbols(self):
        return await self.fetch_symbol()

    async def get_option_chain(self, symbol, **kwargs):
        raise NotImplementedError("get_option_chain is not implemented for this broker")

    async def get_contract_metadata(self, symbol, **kwargs):
        raise NotImplementedError("get_contract_metadata is not implemented for this broker")

    def supported_market_venues(self):
        config = getattr(self, "config", None)
        return supported_market_venues_for_profile(
            getattr(config, "type", None),
            getattr(config, "exchange", None),
        )

    def apply_market_preference(self, preference=None):
        return []

    def supports_hedging(self):
        return bool(getattr(self, "hedging_supported", False))

    def supports_instrument_type(self, instrument_type):
        supported = set(getattr(self, "supported_instrument_types", set()) or set())
        if not supported:
            return True
        return str(instrument_type or "").strip().lower() in supported

    async def withdraw(self, code, amount, address, tag=None, params=None):
        raise NotImplementedError("withdraw is not implemented for this broker")

    async def fetch_deposit_address(self, code, params=None):
        raise NotImplementedError("fetch_deposit_address is not implemented for this broker")


class BaseDerivativeBroker(BaseBroker):
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, config, event_bus=None):
        resolved_bus = event_bus or getattr(config, "event_bus", None)
        options = dict(getattr(config, "options", None) or {})
        if resolved_bus is None:
            resolved_bus = options.get("event_bus")
        super().__init__(event_bus=resolved_bus)
        self.config = config
        self.exchange_name = str(getattr(config, "exchange", self.__class__.__name__) or self.__class__.__name__).strip().lower()
        self.mode = str(getattr(config, "mode", "paper") or "paper").strip().lower()
        self.options = options
        self.params = dict(getattr(config, "params", None) or {})
        self.account_id = getattr(config, "account_id", None) or options.get("account_id") or self.params.get("account_id")
        self.api_key = getattr(config, "api_key", None) or options.get("api_key") or self.params.get("api_key")
        self.secret = getattr(config, "secret", None) or options.get("secret") or self.params.get("secret")
        self.username = options.get("username") or self.params.get("username")
        self.password = getattr(config, "password", None) or options.get("password") or self.params.get("password")
        self.access_token = options.get("access_token") or self.params.get("access_token")
        self.refresh_token = options.get("refresh_token") or self.params.get("refresh_token")
        self.client_id = options.get("client_id") or self.params.get("client_id") or self.api_key
        self.client_secret = options.get("client_secret") or self.params.get("client_secret") or self.secret
        self.base_url = str(options.get("base_url") or self.params.get("base_url") or self.default_base_url()).rstrip("/")
        self.ws_url = str(options.get("ws_url") or self.params.get("ws_url") or self.default_ws_url()).rstrip("/")
        self.timeout_seconds = float(
            options.get("timeout_seconds")
            or self.params.get("timeout_seconds")
            or max(1, int(getattr(config, "timeout", self.DEFAULT_TIMEOUT_SECONDS) or self.DEFAULT_TIMEOUT_SECONDS))
        )
        self.market_data_poll_interval = float(
            options.get("market_data_poll_interval")
            or self.params.get("market_data_poll_interval")
            or self.DEFAULT_STREAM_POLL_SECONDS
        )
        self.session = None
        self._connected = False
        self._market_cache = {}
        self._websocket = None

        self.latency_tracker = LatencyTracker()

    def default_base_url(self):
        return ""

    def default_ws_url(self):
        return ""

    async def _ensure_session(self):
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for derivative broker HTTP sessions")
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=max(1.0, self.timeout_seconds))
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _authenticate(self):
        return None

    async def connect(self):
        await self._ensure_session()
        await self._authenticate()
        self._connected = True
        return True
    def connection_health(self):

     stats = self.latency_tracker.stats()

     return {
        "exchange": self.exchange_name,
        "avg_latency": stats["avg"],
        "p95_latency": stats["p95"],
        "error_rate": stats["error_rate"],
        "connected": self._connected,
    }
    async def close(self):
        self.stop_market_data_stream()
        if self._websocket is not None:
            try:
                await self._websocket.close()
            except Exception:
                self.logger.debug("Derivative websocket close failed", exc_info=True)
            self._websocket = None
        if self.session is not None and not self.session.closed:
            await self.session.close()
        self._connected = False

    async def disconnect(self):
        await self.close()

    def _auth_headers(self):
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    import time

async def _request_json(
        self,
        method,
        path,
        *,
        params=None,
        json_payload=None,
        data=None,
        headers=None,
        base_url=None,
        include_meta=False,
        expected_statuses=(200, 201, 202, 204),
):
    session = await self._ensure_session()
    request_headers = {**self._auth_headers(), **dict(headers or {})}
    root = str(base_url or self.base_url or "").rstrip("/")
    url = path if str(path).startswith("http") else f"{root}/{str(path).lstrip('/')}"

    start = time.time()

    try:
        async with session.request(
                method.upper(),
                url,
                params=params,
                json=json_payload,
                data=data,
                headers=request_headers,
        ) as response:

            if response.status not in expected_statuses:
                body = await response.text()
                raise RuntimeError(
                    f"{self.exchange_name} {method.upper()} {url} failed: {response.status} {body}"
                )

            if response.status == 204:
                payload = {}
            else:
                text = await response.text()
                payload = {}
                if text:
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        payload = {"raw": text}

        # ✅ record latency
        if hasattr(self, "latency_tracker"):
            self.latency_tracker.record(time.time() - start)

        if include_meta:
            return payload, dict(response.headers), response.status

        return payload

    except Exception as e:
        if hasattr(self, "latency_tracker"):
            self.latency_tracker.record_error()

        self.logger.warning(f"{self.exchange_name} request failed: {e}")
        raise
    async def fetch_balance(self):
        return await self.get_account_info()

    async def fetch_positions(self, symbols=None):
        positions = await self.get_positions()
        targets = {
            str(item.symbol if isinstance(item, Instrument) else item).strip().upper()
            for item in (symbols or [])
            if str(item.symbol if isinstance(item, Instrument) else item).strip()
        }
        if not targets:
            return positions
        return [
            position
            for position in list(positions or [])
            if isinstance(position, Mapping) and str(position.get("symbol") or "").strip().upper() in targets
        ]

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
        payload = {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "type": str(type or "market").strip().lower(),
            "price": price,
            "stop_price": stop_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "params": dict(params or {}),
        }
        return await self.place_order(payload)

    async def fetch_ticker(self, symbol):
        quotes = await self._fetch_quotes([symbol])
        if isinstance(quotes, list) and quotes:
            return quotes[0]
        return {"symbol": str(symbol).strip().upper(), "broker": self.exchange_name}

    async def fetch_orderbook(self, symbol, limit=50):
        ticker = await self.fetch_ticker(symbol)
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        return {
            "symbol": ticker.get("symbol") or str(symbol).strip().upper(),
            "bids": [[bid, 0.0]] if bid not in (None, "") else [],
            "asks": [[ask, 0.0]] if ask not in (None, "") else [],
        }

    async def fetch_status(self):
        return {
            "status": "connected" if self._connected else "disconnected",
            "broker": self.exchange_name,
            "mode": self.mode,
        }

    async def fetch_markets(self):
        return dict(self._market_cache)

    async def fetch_symbol(self):
        return list(self._market_cache)

    async def fetch_orders(self, symbol=None, limit=None):
        orders = await self._list_orders(status=None, symbol=symbol, limit=limit)
        return list(orders or [])

    async def fetch_open_orders(self, symbol=None, limit=None):
        orders = await self._list_orders(status="open", symbol=symbol, limit=limit)
        return list(orders or [])

    async def fetch_closed_orders(self, symbol=None, limit=None):
        orders = await self._list_orders(status="closed", symbol=symbol, limit=limit)
        return list(orders or [])

    async def fetch_order(self, order_id, symbol=None):
        return await self._get_order(order_id, symbol=symbol)

    async def stream_market_data(self, symbols):
        if self.ws_url:
            try:
                await self._stream_via_websocket(symbols)
                return
            except Exception as exc:
                self.logger.warning("%s websocket market-data stream failed, falling back to polling: %s", self.exchange_name, exc)
        await super().stream_market_data(symbols)

    async def _stream_via_websocket(self, symbols):
        if websockets is None:
            raise RuntimeError("websockets is required for derivative broker streaming")
        headers = self._auth_headers()
        async with websockets.connect(self.ws_url, extra_headers=headers or None) as websocket:
            self._websocket = websocket
            auth_message = self._websocket_auth_message()
            if auth_message is not None:
                await websocket.send(json.dumps(auth_message))
            for message in self._websocket_subscriptions(symbols):
                await websocket.send(json.dumps(message))

            self._streaming_market_data = True
            try:
                async for raw_message in websocket:
                    for payload in self._normalize_stream_message(raw_message):
                        await self._emit_market_data_event(payload)
                    if not self._streaming_market_data:
                        break
            finally:
                self._streaming_market_data = False
                self._websocket = None

    def _websocket_auth_message(self):
        return None

    def _websocket_subscriptions(self, symbols):
        return []

    def _normalize_stream_message(self, raw_message):
        if raw_message in (None, ""):
            return []
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8", errors="ignore")
        try:
            payload = json.loads(raw_message)
        except Exception:
            return []
        if isinstance(payload, Mapping):
            return [dict(payload)]
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, Mapping)]
        return []

    async def _fetch_quotes(self, symbols):
        raise NotImplementedError(f"{self.__class__.__name__} must implement _fetch_quotes")

    async def _list_orders(self, status=None, symbol=None, limit=None):
        return []

    async def _get_order(self, order_id, symbol=None):
        return None

    async def get_account_info(self):
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_account_info")

    async def get_positions(self):
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_positions")

    async def place_order(self, order):
        raise NotImplementedError(f"{self.__class__.__name__} must implement place_order")
