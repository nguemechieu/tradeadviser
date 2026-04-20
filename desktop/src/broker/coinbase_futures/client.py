from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable
from urllib.parse import urlencode

import aiohttp

from broker.base_broker import BaseDerivativeBroker
from broker.rate_limiter import RateLimiter

from .auth import CoinbaseJWTAuth
from .models import CoinbaseConfig


class CoinbaseAPIError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def _query_string(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    filtered: list[tuple[str, Any]] = []
    for key in sorted(params):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                filtered.append((str(key), item))
        else:
            filtered.append((str(key), value))
    return urlencode(filtered, doseq=True)


class CoinbaseAdvancedTradeClient:
    PRODUCTS_PATH = "/api/v3/brokerage/products"
    PUBLIC_PRODUCT_PATH = "/api/v3/brokerage/market/products/{product_id}"
    PUBLIC_TICKER_PATH = "/api/v3/brokerage/market/products/{product_id}/ticker"
    PRODUCT_BOOK_PATH = "/api/v3/brokerage/market/product_book"
    CREATE_ORDER_PATH = "/api/v3/brokerage/orders"
    CANCEL_ORDERS_PATH = "/api/v3/brokerage/orders/batch_cancel"
    ORDER_DETAIL_PATH = "/api/v3/brokerage/orders/historical/{order_id}"
    ORDER_LIST_PATH = "/api/v3/brokerage/orders/historical/batch"
    FUTURES_BALANCE_PATH = "/api/v3/brokerage/cfm/balance_summary"
    FUTURES_POSITIONS_PATH = "/api/v3/brokerage/cfm/positions"

    def __init__(
        self,
        config: CoinbaseConfig | Any,
        *,
        auth: CoinbaseJWTAuth | None = None,
        session_factory: Callable[..., aiohttp.ClientSession] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = CoinbaseConfig.from_broker_config(config)
        self.auth = auth or CoinbaseJWTAuth(self.config)
        self.logger = logger or logging.getLogger("CoinbaseFuturesClient")
        self._session_factory = session_factory or aiohttp.ClientSession
        self._session: aiohttp.ClientSession | None = None
        self._open_lock = asyncio.Lock()
        self._rate_limiter = RateLimiter(rate=self.config.rate_limit_per_second)

    async def open(self) -> aiohttp.ClientSession:
        async with self._open_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                self._session = self._session_factory(timeout=timeout)
                self.logger.info("coinbase_futures_client_open rest_url=%s", self.config.rest_url)
            return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | list[Any] | None = None,
        authenticated: bool = True,
        expected_statuses: tuple[int, ...] = (200, 201, 202),
    ) -> Any:
        session = await self.open()
        method_text = str(method or "GET").strip().upper()
        path_text = str(path or "/").strip()
        if not path_text.startswith("/"):
            path_text = f"/{path_text}"
        query = _query_string(params)
        signed_path = f"{path_text}?{query}" if query else path_text
        url = f"{self.config.rest_url}{path_text}"

        headers = {"Accept": "application/json"}
        if authenticated:
            headers.update(self.auth.auth_headers(method_text, signed_path))

        for attempt in range(self.config.max_retries + 1):
            await self._rate_limiter.wait()
            try:
                async with session.request(
                    method_text,
                    url,
                    params=params,
                    json=json_payload,
                    headers=headers,
                ) as response:
                    text = await response.text()
                    if text:
                        try:
                            payload: Any = json.loads(text)
                        except json.JSONDecodeError:
                            payload = {"raw": text}
                    else:
                        payload = {}

                    if response.status in expected_statuses:
                        return payload

                    retry_after = response.headers.get("Retry-After")
                    should_retry = response.status in {408, 429, 500, 502, 503, 504}
                    if should_retry and attempt < self.config.max_retries:
                        delay = float(retry_after or 0.0) if retry_after else min(2 ** attempt, 8.0)
                        self.logger.warning(
                            "coinbase_futures_request_retry method=%s path=%s status=%s delay=%.2f",
                            method_text,
                            path_text,
                            response.status,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    raise CoinbaseAPIError(
                        f"Coinbase request failed {method_text} {path_text}: {response.status}",
                        status=response.status,
                        payload=payload,
                    )
            except aiohttp.ClientError as exc:
                if attempt >= self.config.max_retries:
                    raise CoinbaseAPIError(
                        f"Coinbase transport error {method_text} {path_text}: {exc}"
                    ) from exc
                delay = min(2 ** attempt, 8.0)
                self.logger.warning(
                    "coinbase_futures_transport_retry method=%s path=%s delay=%.2f error=%s",
                    method_text,
                    path_text,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        raise CoinbaseAPIError(f"Coinbase request exhausted retries {method_text} {path_text}")

    async def open_websocket(self) -> aiohttp.ClientWebSocketResponse:
        session = await self.open()
        return await session.ws_connect(
            self.config.ws_url,
            heartbeat=self.config.ws_heartbeat_seconds,
            autoping=True,
        )

    async def get_products(self, *, product_type: str = "FUTURE") -> Any:
        return await self.request_json(
            "GET",
            self.PRODUCTS_PATH,
            params={"product_type": product_type},
            authenticated=True,
        )

    async def get_public_product(self, product_id: str) -> Any:
        return await self.request_json(
            "GET",
            self.PUBLIC_PRODUCT_PATH.format(product_id=str(product_id).strip()),
            authenticated=False,
        )

    async def get_public_ticker(self, product_id: str) -> Any:
        return await self.request_json(
            "GET",
            self.PUBLIC_TICKER_PATH.format(product_id=str(product_id).strip()),
            authenticated=False,
        )

    async def get_product_book(self, product_id: str, *, limit: int = 50) -> Any:
        return await self.request_json(
            "GET",
            self.PRODUCT_BOOK_PATH,
            params={"product_id": str(product_id).strip(), "limit": int(limit)},
            authenticated=True,
        )

    async def create_order(self, payload: dict[str, Any]) -> Any:
        return await self.request_json(
            "POST",
            self.CREATE_ORDER_PATH,
            json_payload=payload,
            authenticated=True,
            expected_statuses=(200, 201),
        )

    async def cancel_orders(self, order_ids: list[str]) -> Any:
        return await self.request_json(
            "POST",
            self.CANCEL_ORDERS_PATH,
            json_payload={"order_ids": list(order_ids or [])},
            authenticated=True,
            expected_statuses=(200, 201),
        )

    async def get_order(self, order_id: str) -> Any:
        return await self.request_json(
            "GET",
            self.ORDER_DETAIL_PATH.format(order_id=str(order_id).strip()),
            authenticated=True,
        )

    async def list_orders(self, *, symbol: str | None = None, limit: int | None = None) -> Any:
        params = {"product_id": symbol, "limit": limit}
        return await self.request_json("GET", self.ORDER_LIST_PATH, params=params, authenticated=True)

    async def get_futures_balance_summary(self) -> Any:
        return await self.request_json("GET", self.FUTURES_BALANCE_PATH, authenticated=True)

    async def get_futures_positions(self) -> Any:
        return await self.request_json("GET", self.FUTURES_POSITIONS_PATH, authenticated=True)


class CoinbaseFuturesBroker(BaseDerivativeBroker):
    """Institutional Coinbase futures broker facade for Sopotek."""

    def __init__(self, config: Any, event_bus: Any = None) -> None:
        super().__init__(config, event_bus=event_bus)
        self.exchange_name = "coinbase_futures"
        self.coinbase_config = CoinbaseConfig.from_broker_config(config)
        self.auth = CoinbaseJWTAuth(self.coinbase_config)
        self.client = CoinbaseAdvancedTradeClient(
            self.coinbase_config,
            auth=self.auth,
            logger=logging.getLogger("CoinbaseFuturesClient"),
        )
        self.products_service = None
        self.market_data_service = None
        self.execution_service = None
        self.symbols: list[str] = []

    async def connect(self):
        from .execution import CoinbaseFuturesExecutionService
        from .market_data import CoinbaseFuturesMarketDataService
        from .products import CoinbaseFuturesProductService

        await self.client.open()
        self.products_service = CoinbaseFuturesProductService(
            self.client,
            self.coinbase_config,
            event_bus=self.event_bus,
            logger=logging.getLogger("CoinbaseFuturesProducts"),
        )
        self.market_data_service = CoinbaseFuturesMarketDataService(
            self.client,
            self.products_service,
            event_bus=self.event_bus,
            auth=self.auth,
            logger=logging.getLogger("CoinbaseFuturesMarketData"),
        )
        self.execution_service = CoinbaseFuturesExecutionService(
            self.client,
            self.products_service,
            event_bus=self.event_bus,
            config=self.coinbase_config,
            market_data=self.market_data_service,
            logger=logging.getLogger("CoinbaseFuturesExecution"),
        )
        await self.products_service.fetch_products(force_refresh=True)
        await self.products_service.start_auto_refresh()
        self.symbols = await self.fetch_symbol()
        self._market_cache = await self.fetch_markets()
        self._connected = True
        return True

    async def close(self):
        if self.market_data_service is not None:
            await self.market_data_service.close()
        if self.products_service is not None:
            await self.products_service.close()
        await self.client.close()
        self._connected = False

    async def fetch_markets(self):
        if self.products_service is None:
            return {}
        return self.products_service.markets_snapshot()

    async def fetch_symbol(self):
        if self.products_service is None:
            return []
        return [product.normalized_symbol for product in await self.products_service.fetch_products()]

    async def fetch_ticker(self, symbol):
        return await self.market_data_service.fetch_ticker(symbol)

    async def fetch_orderbook(self, symbol, limit=50):
        return await self.market_data_service.fetch_orderbook(symbol, limit=limit)

    async def fetch_balance(self):
        return await self.execution_service.fetch_balances()

    async def fetch_positions(self, symbols=None):
        rows = await self.execution_service.fetch_positions()
        if not symbols:
            return rows
        targets = {str(symbol or "").strip().upper() for symbol in list(symbols or []) if str(symbol or "").strip()}
        return [row for row in rows if str(row.get("symbol") or "").strip().upper() in targets]

    async def fetch_orders(self, symbol=None, limit=None):
        return await self.execution_service.fetch_orders(symbol=symbol, limit=limit)

    async def fetch_open_orders(self, symbol=None, limit=None):
        rows = await self.fetch_orders(symbol=symbol, limit=limit)
        return [row for row in rows if str(row.get("status") or "").strip().lower() in {"open", "pending"}]

    async def fetch_closed_orders(self, symbol=None, limit=None):
        rows = await self.fetch_orders(symbol=symbol, limit=limit)
        return [row for row in rows if str(row.get("status") or "").strip().lower() in {"filled", "cancelled", "rejected"}]

    async def fetch_order(self, order_id, symbol=None):
        order = await self.execution_service.fetch_order(str(order_id))
        if symbol and str(order.get("symbol") or "").strip().upper() != str(symbol).strip().upper():
            return None
        return order

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
        del stop_price, stop_loss, take_profit
        params = dict(params or {})
        client_order_id = params.get("client_order_id") or params.get("clientOrderId")
        return await self.execution_service.place_order(
            symbol=symbol,
            side=side,
            size=float(amount),
            price=price,
            order_type=type,
            client_order_id=client_order_id,
        )

    async def cancel_order(self, order_id, symbol=None):
        del symbol
        return await self.execution_service.cancel_order(str(order_id))

    async def subscribe_ticker(self, symbols):
        return await self.market_data_service.subscribe_ticker(symbols)

    async def subscribe_orderbook(self, symbols):
        return await self.market_data_service.subscribe_orderbook(symbols)

    async def unsubscribe_market_data(self, symbols=None):
        del symbols
        if self.market_data_service is not None:
            await self.market_data_service.close()
        return True

    def supports_symbol(self, symbol: str) -> bool:
        if self.products_service is None:
            return False
        return self.products_service.has_symbol(symbol)


__all__ = [
    "CoinbaseAPIError",
    "CoinbaseAdvancedTradeClient",
    "CoinbaseFuturesBroker",
]
