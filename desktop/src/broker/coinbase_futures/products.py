from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from .client import CoinbaseAdvancedTradeClient
from .models import CoinbaseConfig, CoinbaseFuturesProduct, product_from_api_payload
from .normalizer import (
    extract_contract_expiry_type,
    normalize_lookup_symbol,
    normalize_symbol,
    symbol_aliases,
)


class CoinbaseFuturesProductService:
    def __init__(
        self,
        client: CoinbaseAdvancedTradeClient,
        config: CoinbaseConfig | Any,
        *,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.config = CoinbaseConfig.from_broker_config(config)
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger("CoinbaseFuturesProductService")
        self._products_by_id: dict[str, CoinbaseFuturesProduct] = {}
        self._products_by_symbol: dict[str, CoinbaseFuturesProduct] = {}
        self._aliases: dict[str, str] = {}
        self._cache_deadline = 0.0
        self._refresh_lock = asyncio.Lock()
        self._scheduler_task: asyncio.Task[Any] | None = None
        self._closed = False

    @staticmethod
    def _extract_products(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, Mapping)]
        if isinstance(payload, Mapping):
            for key in ("products", "results", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [dict(item) for item in value if isinstance(item, Mapping)]
        return []

    async def fetch_products(
        self,
        product_type: str = "FUTURE",
        contract_expiry_type: str | None = None,
        *,
        force_refresh: bool = False,
    ) -> list[CoinbaseFuturesProduct]:
        if not force_refresh and self._products_by_id and time.monotonic() < self._cache_deadline:
            return self._filtered_products(contract_expiry_type=contract_expiry_type)

        async with self._refresh_lock:
            if not force_refresh and self._products_by_id and time.monotonic() < self._cache_deadline:
                return self._filtered_products(contract_expiry_type=contract_expiry_type)

            payload = await self.client.get_products(product_type=product_type)
            raw_products = self._extract_products(payload)
            products: list[CoinbaseFuturesProduct] = []
            aliases: dict[str, str] = {}
            by_id: dict[str, CoinbaseFuturesProduct] = {}
            by_symbol: dict[str, CoinbaseFuturesProduct] = {}

            for raw_product in raw_products:
                if str(raw_product.get("product_type") or "").strip().upper() != str(product_type).strip().upper():
                    continue

                normalized_symbol = normalize_symbol(raw_product)
                product = product_from_api_payload(raw_product, normalized_symbol)
                by_id[product.product_id] = product
                by_symbol[product.normalized_symbol] = product
                for alias in symbol_aliases(raw_product, normalized_symbol):
                    aliases[normalize_lookup_symbol(alias)] = product.product_id
                products.append(product)

            products.sort(key=lambda item: (item.normalized_symbol, item.product_id))
            self._products_by_id = by_id
            self._products_by_symbol = by_symbol
            self._aliases = aliases
            self._cache_deadline = time.monotonic() + self.config.product_cache_ttl_seconds

            if self.event_bus is not None:
                await self.event_bus.publish(
                    "broker.products.updated",
                    {
                        "exchange": "coinbase_futures",
                        "count": len(products),
                        "symbols": [item.normalized_symbol for item in products[:50]],
                    },
                )
            return self._filtered_products(contract_expiry_type=contract_expiry_type)

    def _filtered_products(self, *, contract_expiry_type: str | None = None) -> list[CoinbaseFuturesProduct]:
        rows = list(self._products_by_id.values())
        if contract_expiry_type:
            normalized_type = str(contract_expiry_type or "").strip().upper()
            rows = [row for row in rows if extract_contract_expiry_type(row.metadata) == normalized_type]
        return rows

    async def start_auto_refresh(self) -> None:
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return
        self._closed = False
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="coinbase_futures_product_refresh")

    async def _scheduler_loop(self) -> None:
        while not self._closed:
            await asyncio.sleep(self.config.product_refresh_interval_seconds)
            if self._closed:
                break
            try:
                await self.fetch_products(force_refresh=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("coinbase_futures_product_refresh_failed")

    async def close(self) -> None:
        self._closed = True
        if self._scheduler_task is not None:
            self._scheduler_task.cancel()
            await asyncio.gather(self._scheduler_task, return_exceptions=True)
        self._scheduler_task = None

    async def resolve_product(self, symbol: str, *, force_refresh: bool = False) -> CoinbaseFuturesProduct:
        if not self._products_by_id or force_refresh:
            await self.fetch_products(force_refresh=force_refresh)

        normalized_symbol = normalize_lookup_symbol(symbol)
        product_id = self._aliases.get(normalized_symbol, normalized_symbol)
        product = self._products_by_id.get(product_id) or self._products_by_symbol.get(normalized_symbol)
        if product is None and not force_refresh:
            return await self.resolve_product(symbol, force_refresh=True)
        if product is None:
            raise KeyError(f"Unknown Coinbase futures symbol: {symbol}")
        return product

    async def product_id_for(self, symbol: str) -> str:
        return (await self.resolve_product(symbol)).product_id

    def has_symbol(self, symbol: str) -> bool:
        normalized_symbol = normalize_lookup_symbol(symbol)
        return normalized_symbol in self._aliases or normalized_symbol in self._products_by_symbol

    def markets_snapshot(self) -> dict[str, dict[str, Any]]:
        return {product.normalized_symbol: product.to_dict() for product in self._products_by_id.values()}

    def product_snapshot(self) -> list[dict[str, Any]]:
        return [product.to_dict() for product in self._products_by_id.values()]


__all__ = ["CoinbaseFuturesProductService"]
