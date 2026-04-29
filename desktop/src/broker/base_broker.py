from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None

from broker.market_venues import supported_market_venues_for_profile
from events.event import Event
from events.event_bus.event_types import EventType
from models.instrument import Instrument
from models.order import Order
from core.monitoring.latency_tracker import LatencyTracker


def _event_name(event_type: Any, fallback: str) -> str:
    """Return a safe event name even if Event Type is incomplete or shadowed."""
    try:
        if hasattr(event_type, "value"):
            return str(event_type.value)
        text = str(event_type or "").strip()
        return text or fallback
    except Exception:
        return fallback


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _safe_symbol(value: Any) -> str:
    if isinstance(value, Instrument):
        return str(value.symbol or "").strip().upper()
    return str(value or "").strip().upper()


class BaseBroker(ABC):
    DEFAULT_STREAM_POLL_SECONDS = 1.0

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(self.__class__.__name__)
        self._streaming_market_data = False
        self.latency_tracker = LatencyTracker()

    @abstractmethod
    async def connect(self):
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError

    async def disconnect(self):
        await self.close()

    async def login(self):
        return await self.connect()

    async def logout(self):
        await self.close()

    def is_authenticated(self):
        connected = getattr(self, "_connected", None)
        return bool(connected) if isinstance(connected, bool) else False

    async def refresh_session(self):
        return {"authenticated": bool(self.is_authenticated())}

    def attach_event_bus(self, event_bus):
        self.event_bus = event_bus
        return self

    def _event_type(self, name: str, fallback: str) -> str:
        return _event_name(getattr(EventType, name, None), fallback)

    async def _publish_event(self, event_type, payload):
        if self.event_bus is None:
            return None

        event = Event(type=_event_name(event_type, str(event_type or "event")), data=payload)
        publish = getattr(self.event_bus, "publish", None)
        if not callable(publish):
            return None

        try:
            await _maybe_await(publish(event))
        except TypeError:
            await _maybe_await(publish(event.type, event.data))
        except Exception:
            self.logger.debug("Event publish failed for %s", event.type, exc_info=True)
            return None

        return event

    async def _emit_market_data_event(self, payload):
        payload = dict(payload or {})
        payload.setdefault("broker", getattr(self, "exchange_name", None))
        await self._publish_event(self._event_type("MARKET_DATA_EVENT", "market.data.event"), payload)
        await self._publish_event(self._event_type("MARKET_DATA", "market.data"), payload)
        await self._publish_event(self._event_type("MARKET_TICK", "market.tick"), payload)

    async def _emit_order_event(self, payload):
        payload = dict(payload or {})
        payload.setdefault("broker", getattr(self, "exchange_name", None))
        await self._publish_event(self._event_type("ORDER_EVENT", "order.event"), payload)
        await self._publish_event(self._event_type("EXECUTION_REPORT", "execution.report"), payload)

    async def _emit_position_event(self, payload):
        payload = dict(payload or {})
        payload.setdefault("broker", getattr(self, "exchange_name", None))
        await self._publish_event(self._event_type("POSITION_EVENT", "position.event"), payload)
        await self._publish_event(self._event_type("POSITION", "position"), payload)

    async def _emit_account_event(self, payload):
        payload = dict(payload or {})
        payload.setdefault("broker", getattr(self, "exchange_name", None))
        await self._publish_event(self._event_type("ACCOUNT_EVENT", "account.event"), payload)
        await self._publish_event(self._event_type("PORTFOLIO_SNAPSHOT", "portfolio.snapshot"), payload)

    @staticmethod
    def _coerce_mapping(value):
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
            return dict(value.to_dict())
        if is_dataclass(value):
            return asdict(value)
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

    @abstractmethod
    async def fetch_ticker(self, symbol):
        raise NotImplementedError

    async def fetch_tickers(self, symbols=None):
        snapshots = []
        for symbol in list(symbols or []):
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
        normalized_symbols = [_safe_symbol(symbol) for symbol in (symbols or []) if _safe_symbol(symbol)]
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
                    try:
                        ticker = await self.fetch_ticker(symbol)
                    except Exception:
                        self.logger.debug("fetch_ticker failed during stream for %s", symbol, exc_info=True)
                        continue
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
        raise NotImplementedError

    async def place_order(self, order):
        payload = Order.from_mapping(order).to_dict()
        params = dict(payload.get("params") or {})
        for key in ("instrument", "legs", "broker", "client_order_id", "time_in_force"):
            if payload.get(key):
                params.setdefault(key, payload.get(key))

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
        raise NotImplementedError

    async def cancel_all_orders(self, symbol=None):
        raise NotImplementedError("cancel_all_orders is not implemented for this broker")

    async def get_order(self, account_id, order_id):
        _ = account_id
        return await self.fetch_order(order_id)

    async def list_orders(self, account_id=None, filters=None):
        _ = account_id
        filters = dict(filters or {})
        return await self.fetch_orders(symbol=filters.get("symbol"), limit=filters.get("limit"))

    @abstractmethod
    async def fetch_balance(self):
        raise NotImplementedError

    async def get_account_info(self):
        account = await self.fetch_balance()
        if isinstance(account, Mapping):
            await self._emit_account_event(dict(account))
        return account

    async def get_accounts(self):
        account = await self.get_account_info()
        if isinstance(account, Mapping):
            return [dict(account)]
        if isinstance(account, Sequence) and not isinstance(account, (str, bytes, bytearray)):
            return list(account)
        return []

    async def get_account_balances(self, account_id=None):
        _ = account_id
        return await self.fetch_balance()

    async def fetch_positions(self, symbols=None):
        raise NotImplementedError("fetch_positions is not implemented for this broker")

    async def get_positions(self):
        positions = await self.fetch_positions()
        if isinstance(positions, Mapping):
            await self._emit_position_event(dict(positions))
            return positions
        if isinstance(positions, list):
            for position in positions:
                if isinstance(position, Mapping):
                    await self._emit_position_event(dict(position))
        return positions

    async def fetch_position(self, symbol):
        normalized_symbol = _safe_symbol(symbol)
        if not normalized_symbol:
            return None
        try:
            positions = await self.fetch_positions(symbols=[normalized_symbol])
        except TypeError:
            positions = await self.fetch_positions()
        if isinstance(positions, Mapping):
            return dict(positions) if _safe_symbol(positions.get("symbol")) == normalized_symbol else None
        if not isinstance(positions, list):
            return None
        for position in positions:
            if not isinstance(position, Mapping):
                continue
            if _safe_symbol(position.get("symbol")) == normalized_symbol:
                return dict(position)
        return None

    def _position_amount(self, position):
        if not isinstance(position, Mapping):
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
        if not isinstance(position, Mapping):
            return None
        side = position.get("side") or position.get("position_side")
        if side is not None:
            return str(side).strip().lower()
        try:
            numeric = float(position.get("amount"))
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
        normalized_symbol = _safe_symbol(symbol)
        target_position = position if isinstance(position, Mapping) else None
        if not isinstance(target_position, Mapping):
            try:
                positions = await self.fetch_positions(symbols=[normalized_symbol])
            except TypeError:
                positions = await self.fetch_positions()
            except Exception:
                positions = []

            candidates = [
                item
                for item in (positions or [])
                if isinstance(item, Mapping) and _safe_symbol(item.get("symbol")) == normalized_symbol
            ]
            if position_id:
                normalized_id = str(position_id).strip().lower()
                candidates = [
                    item
                    for item in candidates
                    if str(item.get("position_id") or item.get("id") or item.get("trade_id") or "").strip().lower() == normalized_id
                ]
            if position_side:
                normalized_side = str(position_side).strip().lower()
                candidates = [
                    item
                    for item in candidates
                    if str(item.get("position_side") or item.get("side") or "").strip().lower() == normalized_side
                ]
            if len(candidates) > 1 and self.supports_hedging():
                raise ValueError(f"Multiple hedge legs are open for {normalized_symbol}. Specify the long or short position to close.")
            target_position = candidates[0] if candidates else await self.fetch_position(normalized_symbol)

        if not isinstance(target_position, Mapping):
            return None
        close_amount = self._position_amount(target_position) if amount is None else abs(float(amount))
        if close_amount <= 0:
            return None
        side = self._position_side(target_position)
        close_side = "buy" if side in {"short", "sell"} else "sell"
        return await self.create_order(symbol=normalized_symbol, side=close_side, amount=close_amount, type=order_type, params=params)

    async def close_all_positions(self, symbols=None, params=None, order_type="market"):
        try:
            positions = await self.fetch_positions(symbols=symbols)
        except TypeError:
            positions = await self.fetch_positions()
        closed = []
        for position in positions or []:
            if not isinstance(position, Mapping):
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
        for symbol in dict.fromkeys(_safe_symbol(item) for item in (symbols or []) if _safe_symbol(item)):
            try:
                orders = await self.fetch_open_orders(symbol=symbol, limit=limit)
            except TypeError:
                orders = await self.fetch_open_orders(symbol)
            for order in orders or []:
                if isinstance(order, Mapping):
                    key = (str(order.get("id") or ""), str(order.get("clientOrderId") or order.get("client_order_id") or ""), _safe_symbol(order.get("symbol") or symbol), str(order.get("status") or ""))
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
        return supported_market_venues_for_profile(getattr(config, "type", None), getattr(config, "exchange", None))

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


class BaseDerivativeBroker(BaseBroker, ABC):
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, config, event_bus=None):
        options = dict(getattr(config, "options", None) or {})
        resolved_bus = event_bus or getattr(config, "event_bus", None) or options.get("event_bus")
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
        self.timeout_seconds = float(options.get("timeout_seconds") or self.params.get("timeout_seconds") or max(1, int(getattr(config, "timeout", self.DEFAULT_TIMEOUT_SECONDS) or self.DEFAULT_TIMEOUT_SECONDS)))
        self.market_data_poll_interval = float(options.get("market_data_poll_interval") or self.params.get("market_data_poll_interval") or self.DEFAULT_STREAM_POLL_SECONDS)
        self.session = None
        self._connected = False
        self._market_cache = {}
        self._websocket = None

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
        return {"exchange": self.exchange_name, "avg_latency": stats.get("avg"), "p95_latency": stats.get("p95"), "error_rate": stats.get("error_rate"), "connected": self._connected}

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

    async def _request_json(self, method, path, *, params=None, json_payload=None, data=None, headers=None, base_url=None, include_meta=False, expected_statuses=(200, 201, 202, 204)):
        session = await self._ensure_session()
        request_headers = {**self._auth_headers(), **dict(headers or {})}
        root = str(base_url or self.base_url or "").rstrip("/")
        url = path if str(path).startswith("http") else f"{root}/{str(path).lstrip('/')}"
        start = time.time()
        try:
            async with session.request(str(method or "GET").upper(), url, params=params, json=json_payload, data=data, headers=request_headers) as response:
                response_headers = dict(response.headers)
                status = int(response.status)
                if status not in expected_statuses:
                    body = await response.text()
                    raise RuntimeError(f"{self.exchange_name} {str(method).upper()} {url} failed: {status} {body}")
                if status == 204:
                    payload = {}
                else:
                    text = await response.text()
                    payload = {}
                    if text:
                        try:
                            payload = json.loads(text)
                        except json.JSONDecodeError:
                            payload = {"raw": text}
            self.latency_tracker.record(time.time() - start)
            if include_meta:
                return payload, response_headers, status
            return payload
        except Exception as exc:
            self.latency_tracker.record_error(time.time() - start)
            self.logger.warning("%s request failed: %s", self.exchange_name, exc)
            raise

    async def fetch_balance(self):
        return await self.get_account_info()

    async def fetch_positions(self, symbols=None):
        positions = await self.get_positions()
        targets = {_safe_symbol(item) for item in (symbols or []) if _safe_symbol(item)}
        if not targets:
            return positions
        return [position for position in list(positions or []) if isinstance(position, Mapping) and _safe_symbol(position.get("symbol")) in targets]

    async def create_order(self, symbol, side, amount, type="market", price=None, stop_price=None, params=None, stop_loss=None, take_profit=None):
        payload = {"symbol": symbol, "side": side, "amount": amount, "type": str(type or "market").strip().lower(), "price": price, "stop_price": stop_price, "stop_loss": stop_loss, "take_profit": take_profit, "params": dict(params or {})}
        return await self.place_order(payload)

    async def fetch_ticker(self, symbol):
        quotes = await self._fetch_quotes([symbol])
        if isinstance(quotes, list) and quotes:
            return quotes[0]
        return {"symbol": _safe_symbol(symbol), "broker": self.exchange_name}

    async def fetch_orderbook(self, symbol, limit=50):
        ticker = await self.fetch_ticker(symbol)
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        return {"symbol": ticker.get("symbol") or _safe_symbol(symbol), "bids": [[bid, 0.0]] if bid not in (None, "") else [], "asks": [[ask, 0.0]] if ask not in (None, "") else []}

    async def fetch_status(self):
        return {"status": "connected" if self._connected else "disconnected", "broker": self.exchange_name, "mode": self.mode}

    async def fetch_markets(self):
        return dict(self._market_cache)

    async def fetch_symbol(self):
        return list(self._market_cache)

    async def fetch_orders(self, symbol=None, limit=None):
        return list(await self._list_orders(status=None, symbol=symbol, limit=limit) or [])

    async def fetch_open_orders(self, symbol=None, limit=None):
        return list(await self._list_orders(status="open", symbol=symbol, limit=limit) or [])

    async def fetch_closed_orders(self, symbol=None, limit=None):
        return list(await self._list_orders(status="closed", symbol=symbol, limit=limit) or [])

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
        async with websockets.connect(self.ws_url, additional_headers=headers or None) as websocket:
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


__all__ = ["BaseBroker", "BaseDerivativeBroker"]
