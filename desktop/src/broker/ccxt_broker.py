import asyncio
from collections.abc import Mapping
import copy
from datetime import datetime, timezone
import json
import logging
import re
import socket
import time
from urllib.parse import urlencode
from uuid import uuid4

import aiohttp
import ccxt.async_support as ccxt

from broker.base_broker import BaseBroker
from broker.coinbase_credentials import normalize_coinbase_credentials
from broker.coinbase_jwt_auth import build_coinbase_rest_jwt, resolve_coinbase_rest_host, uses_coinbase_jwt_auth
from broker.broker_errors import BrokerOperationError
from broker.market_venues import (
    SPOT_ONLY_EXCHANGES,
    normalize_market_venue,
    supported_market_venues_for_profile,
)


_COINBASE_EXCHANGE_CLASS_CACHE = {}


class _CoinbaseJWTAuthMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        stable_id = str(getattr(self, "id", "")).strip() or "coinbase"
        self._sopotek_exchange_id = stable_id
        self.id = stable_id

    def _stable_exchange_id(self):
        stable_id = str(getattr(self, "_sopotek_exchange_id", "")).strip()
        if stable_id:
            return stable_id
        current_id = str(getattr(self, "id", "")).strip() or "coinbase"
        self._sopotek_exchange_id = current_id
        return current_id

    def _restore_exchange_id(self):
        stable_id = self._stable_exchange_id()
        self.id = stable_id
        return stable_id

    def sign(self, path, api=None, method="GET", params=None, headers=None, body=None):
        api = api or []
        params = params or {}
        version = api[0] if len(api) > 0 else None
        signed = len(api) > 1 and api[1] == "private"

        if not signed or not uses_coinbase_jwt_auth(getattr(self, "apiKey", None), getattr(self, "secret", None)):
            return super().sign(path, api=api, method=method, params=params, headers=headers, body=body)

        path_part = "api/v3" if version == "v3" else "v2"
        full_path = "/" + path_part + "/" + self.implode_params(path, params)
        query = self.omit(params, self.extract_params(path))
        request_path = full_path
        if method == "GET" and query:
            full_path += "?" + self.urlencode(query)

        url = self.urls["api"]["rest"] + full_path
        if method != "GET" and query:
            body = self.json(query)

        jwt_token = build_coinbase_rest_jwt(
            request_method=method,
            request_host=resolve_coinbase_rest_host(self.urls["api"]["rest"]),
            request_path=request_path,
            api_key=self.apiKey,
            api_secret=self.secret,
            issuer=getattr(self, "_coinbase_jwt_issuer", lambda: CCXTBroker.COINBASE_DEFAULT_JWT_ISSUER)(),
        )
        return {
            "url": url,
            "method": method,
            "body": body,
            "headers": {
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
            },
        }

    async def create_order(self, symbol, type, side, amount, price=None, params=None):
        original_id = self._restore_exchange_id()
        try:
            return await super().create_order(symbol, type, side, amount, price, params)
        finally:
            if original_id is not None:
                self.id = original_id

    def handle_errors(
        self,
        code,
        reason,
        url,
        method,
        headers,
        body,
        response,
        request_headers,
        request_body,
    ):
        original_id = self._restore_exchange_id()
        try:
            return super().handle_errors(
                code,
                reason,
                url,
                method,
                headers,
                body,
                response,
                request_headers,
                request_body,
            )
        finally:
            if original_id is not None:
                self.id = original_id


def _coinbase_exchange_class(base_class):
    if not isinstance(base_class, type):
        return base_class
    cached = _COINBASE_EXCHANGE_CLASS_CACHE.get(base_class)
    if cached is not None:
        return cached

    derived = type(f"Sopotek{base_class.__name__}JWT", (_CoinbaseJWTAuthMixin, base_class), {})
    _COINBASE_EXCHANGE_CLASS_CACHE[base_class] = derived
    return derived


class CCXTBroker(BaseBroker):
    DEFAULT_TIMEOUT_MS = 30000
    COINBASE_FUTURES_BALANCE_PATH = "/api/v3/brokerage/cfm/balance_summary"
    COINBASE_FUTURES_POSITIONS_PATH = "/api/v3/brokerage/cfm/positions"
    COINBASE_PERPETUALS_PORTFOLIO_PATH = "/api/v3/brokerage/intx/portfolio"
    COINBASE_PERPETUALS_POSITIONS_PATH = "/api/v3/brokerage/intx/positions"
    COINBASE_PRODUCTS_PATH = "/api/v3/brokerage/products"
    COINBASE_PORTFOLIOS_PATH = "/api/v3/brokerage/portfolios"
    COINBASE_MAX_OHLCV_CANDLES = 300
    GENERIC_MAX_OHLCV_CANDLES = 1000
    COINBASE_OHLCV_CACHE_SECONDS = 8.0
    COINBASE_OHLCV_SHORTFALL_CACHE_SECONDS = 20.0
    COINBASE_OHLCV_MAX_CONCURRENCY = 2
    SPOT_ACCOUNT_CACHE_SECONDS = 3.0
    COINBASE_SPOT_ACCOUNT_CACHE_SECONDS = 8.0
    COINBASE_OPEN_ORDERS_CACHE_SECONDS = 5.0
    SPOT_PRICE_CACHE_SECONDS = 15.0
    SPOT_DUST_THRESHOLD = 1e-10
    SPOT_CASH_EQUIVALENTS = {"USD", "USDC", "USDT", "BUSD", "EUR", "GBP"}
    SPOT_VALUE_QUOTE_PRIORITY = ("USD", "USDC", "USDT", "BUSD", "EUR", "GBP", "BTC", "ETH")
    COINBASE_DEFAULT_JWT_ISSUER = "coinbase-cloud"
    COINBASE_PRODUCT_CACHE_SECONDS = 15.0
    COINBASE_PORTFOLIO_CACHE_SECONDS = 5.0
    COINBASE_MIN_PERPETUAL_NOTIONAL = 10.0
    COINBASE_MAX_PERPETUAL_LEVERAGE = 10.0
    CAPABILITY_MAP = {
        "fetch_ticker": "fetchTicker",
        "fetch_tickers": "fetchTickers",
        "fetch_order_book": "fetchOrderBook",
        "fetch_ohlcv": "fetchOHLCV",
        "fetch_trades": "fetchTrades",
        "fetch_my_trades": "fetchMyTrades",
        "fetch_markets": "fetchMarkets",
        "fetch_currencies": "fetchCurrencies",
        "fetch_status": "fetchStatus",
        "create_order": "createOrder",
        "cancel_order": "cancelOrder",
        "cancel_all_orders": "cancelAllOrders",
        "fetch_balance": "fetchBalance",
        "fetch_positions": "fetchPositions",
        "fetch_order": "fetchOrder",
        "fetch_orders": "fetchOrders",
        "fetch_open_orders": "fetchOpenOrders",
        "fetch_closed_orders": "fetchClosedOrders",
        "withdraw": "withdraw",
        "fetch_deposit_address": "fetchDepositAddress",
    }

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger("CCXTBroker")

        self.config = config
        self.exchange_name = getattr(config, "exchange", None)
        self.api_key = getattr(config, "api_key", None)
        self.secret = getattr(config, "secret", None)
        self.password = getattr(config, "password", None) or getattr(config, "passphrase", None)
        self.uid = getattr(config, "uid", None)
        self.account_id = getattr(config, "account_id", None)
        self.wallet = getattr(config, "wallet", None)
        self.mode = (getattr(config, "mode", "live") or "live").lower()
        self.sandbox = bool(getattr(config, "sandbox", False) or self.mode in {"paper", "sandbox", "testnet"})
        self.timeout = int(getattr(config, "timeout", self.DEFAULT_TIMEOUT_MS) or self.DEFAULT_TIMEOUT_MS)
        self.extra_options = dict(getattr(config, "options", None) or {})
        self.extra_params = dict(getattr(config, "params", None) or {})
        self.market_preference = normalize_market_venue(self.extra_options.get("market_type", "auto"))
        self.resolved_market_preference = self.market_preference

        self.exchange = None
        self.session = None
        self.symbols = []
        self._connected = False
        self._open_orders_snapshot_cache = {}
        self._spot_account_snapshot_cache = None
        self._spot_account_snapshot_cache_until = 0.0
        self._spot_account_snapshot_inflight = None
        self._ticker_price_cache = {}
        self._ticker_price_cache_until = {}
        self._ticker_price_inflight = {}
        self._ohlcv_cache = {}
        self._ohlcv_cache_until = {}
        self._ohlcv_inflight = {}
        self._coinbase_ohlcv_semaphore = None
        self._account_asset_codes = []
        self._market_symbol_lookup = set()
        self._coinbase_products_cache = None
        self._coinbase_products_cache_until = 0.0
        self._coinbase_intx_portfolio_cache = None
        self._coinbase_intx_portfolio_cache_until = 0.0
        self._coinbase_derivatives_enabled_cache = None
        self._coinbase_derivatives_enabled_cache_until = 0.0
        self._coinbase_leverage_by_product = {}

        if not self.exchange_name:
            raise ValueError("CCXT exchange name is required")

        self.logger.info("Initializing broker %s", self.exchange_name)

    @staticmethod
    def _normalized_credential(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    # ==========================================================
    # INTERNALS
    # ==========================================================

    def _exchange_class(self):
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
        except AttributeError as exc:
            raise ValueError(f"Unsupported CCXT exchange: {self.exchange_name}") from exc
        if self._exchange_code() == "coinbase":
            return _coinbase_exchange_class(exchange_class)
        return exchange_class

    def _build_exchange_options(self):
        options = {"adjustForTimeDifference": True}
        default_type = self._default_type_for_market_preference()
        if default_type:
            options.setdefault("defaultType", default_type)
        options.update(self.extra_options)
        if self._exchange_code() == "binanceus":
            options["defaultType"] = "spot"
            options.pop("defaultSubType", None)
            options["warnOnFetchOpenOrdersWithoutSymbol"] = False
        return options

    def _exchange_code(self):
        return str(self.exchange_name or "").strip().lower()

    @staticmethod
    def _looks_like_native_contract_symbol(symbol):
        text = str(symbol or "").strip().upper()
        if not text or "/" in text or "_" in text:
            return False
        if "PERP" in text:
            return True
        return bool(
            re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
            or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
        )

    @staticmethod
    def _normalize_market_symbol(symbol):
        text = str(symbol or "").strip().upper()
        if CCXTBroker._looks_like_native_contract_symbol(text):
            return text
        return text.replace("_", "/").replace("-", "/")

    def _refresh_market_symbol_lookup(self, markets=None):
        lookup = set()

        for symbol in self.symbols or []:
            normalized = self._normalize_market_symbol(symbol)
            if normalized:
                lookup.add(normalized)

        if isinstance(markets, dict):
            for market_symbol, market in markets.items():
                normalized_market_symbol = self._normalize_market_symbol(market_symbol)
                if normalized_market_symbol:
                    lookup.add(normalized_market_symbol)

                if isinstance(market, dict):
                    normalized_declared_symbol = self._normalize_market_symbol(market.get("symbol"))
                    if normalized_declared_symbol:
                        lookup.add(normalized_declared_symbol)

        self._market_symbol_lookup = lookup
        return lookup

    def _supports_attached_protection_prices(self):
        exchange_code = self._exchange_code()
        return exchange_code in set()

    def supports_symbol(self, symbol):
        normalized_symbol = self._normalize_market_symbol(symbol)
        if not normalized_symbol:
            return False

        lookup = getattr(self, "_market_symbol_lookup", None)
        if not lookup:
            markets = getattr(self.exchange, "markets", {}) if self.exchange is not None else {}
            lookup = self._refresh_market_symbol_lookup(markets)

        return normalized_symbol in lookup

    def _normalize_credentials(self):
        self.exchange_name = self._normalized_credential(self.exchange_name)
        self.api_key = self._normalized_credential(self.api_key)
        self.secret = self._normalized_credential(self.secret)
        self.password = self._normalized_credential(self.password)
        self.uid = self._normalized_credential(self.uid)
        self.account_id = self._normalized_credential(self.account_id)
        self.wallet = self._normalized_credential(self.wallet)
        if self._exchange_code() == "coinbase" and (self.api_key or self.secret or self.password):
            self.api_key, self.secret, self.password = normalize_coinbase_credentials(
                self.api_key,
                self.secret,
                self.password,
            )

    @staticmethod
    def _strip_wrapped_quotes(value):
        text = str(value or "").strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            return text[1:-1].strip()
        return text

    @classmethod
    def _normalize_coinbase_api_key(cls, value):
        normalized = cls._strip_wrapped_quotes(value)
        return normalized or None

    @classmethod
    def _normalize_coinbase_secret(cls, value):
        secret = cls._strip_wrapped_quotes(value)
        if not secret:
            return None
        if "\\n" in secret:
            secret = secret.replace("\\r\\n", "\n").replace("\\n", "\n")

        if "-----BEGIN" in secret and "-----END" in secret:
            header_match = re.search(r"-----BEGIN [A-Z ]+-----", secret)
            footer_match = re.search(r"-----END [A-Z ]+-----", secret)
            if header_match and footer_match and header_match.start() < footer_match.start():
                header = header_match.group(0)
                footer = footer_match.group(0)
                middle = secret[header_match.end():footer_match.start()]
                if "\n" not in secret and "\r" not in secret:
                    middle = re.sub(r"\s+", "", middle)
                    secret = f"{header}\n{middle}\n{footer}\n" if middle else f"{header}\n{footer}\n"

        return secret

    def _validate_credentials(self):
        exchange_code = self._exchange_code()
        if exchange_code in {"binance", "binanceus"}:
            if self.api_key and any(ch.isspace() for ch in self.api_key):
                raise ValueError(
                    f"{exchange_code.upper()} API key contains whitespace. Paste the key exactly as issued by the exchange."
                )
            if self.secret and any(ch.isspace() for ch in self.secret):
                raise ValueError(
                    f"{exchange_code.upper()} API secret contains whitespace. Paste the secret exactly as issued by the exchange."
                )

    def _default_open_orders_symbol(self, symbol=None):
        if symbol:
            return symbol

        configured = (
            getattr(self.config, "symbol", None)
            or self.extra_options.get("open_orders_symbol")
            or self.extra_options.get("symbol")
        )
        if configured:
            return str(configured).strip() or None

        if len(self.symbols) == 1:
            return self.symbols[0]

        return None

    @staticmethod
    def _dedupe_orders_snapshot(orders):
        unique = []
        seen = set()
        for order in orders or []:
            if isinstance(order, dict):
                key = (
                    str(order.get("id") or ""),
                    str(order.get("clientOrderId") or ""),
                    str(order.get("symbol") or ""),
                    str(order.get("status") or ""),
                )
            else:
                key = (str(order), "", "", "")
            if key in seen:
                continue
            seen.add(key)
            unique.append(order)
        return unique

    def _monitored_symbols(self, symbols=None):
        normalized = []
        default_symbol = self._default_open_orders_symbol()
        if default_symbol:
            normalized.append(default_symbol)

        for symbol in symbols or self.symbols or []:
            candidate = str(symbol or "").strip()
            if candidate:
                normalized.append(candidate)

        return list(dict.fromkeys(normalized))

    async def _fetch_open_orders_without_symbol(self, limit=None):
        kwargs = {}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._call_unified("fetch_open_orders", None, default=[], **kwargs)

    async def _fetch_open_orders_by_symbols(self, symbols, limit=None):
        snapshot = []
        for symbol in symbols or []:
            try:
                orders = await self.fetch_open_orders(symbol=symbol, limit=limit)
            except TypeError:
                orders = await self.fetch_open_orders(symbol)
            snapshot.extend(orders or [])
        return self._dedupe_orders_snapshot(snapshot)

    def _market_matches_preference(self, market):
        if self.market_preference == "auto":
            return True
        if not isinstance(market, dict):
            return False
        if self.market_preference == "spot":
            return bool(market.get("spot"))
        if self.market_preference == "derivative":
            return self._market_is_derivative(market)
        if self.market_preference == "option":
            return bool(market.get("option"))
        if self.market_preference == "otc":
            return self._market_is_otc(market)
        return True

    def _default_type_for_market_preference(self):
        if self.market_preference == "spot":
            return "spot"
        if self.market_preference == "option":
            return "option"
        if self.market_preference == "derivative":
            subtype = str(self.extra_options.get("defaultSubType", "") or "").strip().lower()
            if self._exchange_code() == "coinbase":
                return subtype if subtype in {"future", "swap"} else "future"
            return "future" if subtype == "future" else "swap"
        return None

    @staticmethod
    def _market_is_derivative(market):
        if not isinstance(market, dict):
            return False
        if bool(market.get("option")):
            return False
        return any(bool(market.get(key)) for key in ("contract", "swap", "future"))

    @staticmethod
    def _market_is_otc(market):
        if not isinstance(market, dict):
            return False
        if bool(market.get("otc")):
            return True
        for key in ("type", "marketType", "subType", "category"):
            if str(market.get(key) or "").strip().lower() == "otc":
                return True
        return False

    def _market_flag_summary(self, markets):
        summary = {
            "flags_detected": False,
            "spot": False,
            "derivative": False,
            "option": False,
            "otc": False,
        }
        if not isinstance(markets, dict):
            return summary

        for market in markets.values():
            if not isinstance(market, dict):
                continue
            if any(key in market for key in ("spot", "contract", "swap", "future", "option", "otc")):
                summary["flags_detected"] = True
            if bool(market.get("spot")):
                summary["spot"] = True
            if self._market_is_derivative(market):
                summary["derivative"] = True
            if bool(market.get("option")):
                summary["option"] = True
            if self._market_is_otc(market):
                summary["otc"] = True

        return summary

    def _supports_coinbase_positions_endpoint(self, markets):
        effective_preference = normalize_market_venue(getattr(self, "resolved_market_preference", None), default="auto")
        if effective_preference == "spot":
            return False
        if effective_preference == "option":
            return False

        if not isinstance(markets, dict) or not markets:
            return effective_preference == "derivative"

        summary = self._market_flag_summary(markets)
        if effective_preference == "derivative":
            return summary["derivative"]
        if summary["derivative"] and not summary["spot"]:
            return True
        return False

    @staticmethod
    def _coinbase_market_info(market):
        info = (market or {}).get("info") if isinstance(market, dict) else None
        return dict(info) if isinstance(info, dict) else {}

    @classmethod
    def _coinbase_market_subtype(cls, market):
        if not isinstance(market, dict):
            return ""
        if bool(market.get("swap")):
            return "swap"
        if bool(market.get("future")):
            return "future"

        info = cls._coinbase_market_info(market)
        future_details = info.get("future_product_details")
        future_details = future_details if isinstance(future_details, dict) else {}
        perpetual_details = info.get("perpetual_details")
        perpetual_details = perpetual_details if isinstance(perpetual_details, dict) else {}
        contract_expiry_type = str(
            future_details.get("contract_expiry_type")
            or perpetual_details.get("contract_expiry_type")
            or info.get("contract_expiry_type")
            or ""
        ).strip().upper()
        product_venue = str(info.get("product_venue") or "").strip().upper()
        product_id = str(info.get("product_id") or market.get("id") or "").strip().upper()
        product_type = str(info.get("product_type") or market.get("type") or "").strip().upper()

        if (
            contract_expiry_type == "PERPETUAL"
            or "PERP" in product_id
            or product_venue == "INTX"
            or perpetual_details
        ):
            return "swap"
        if product_type == "FUTURE" or future_details:
            return "future"
        return ""

    @classmethod
    def _coinbase_market_settle_currency(cls, market):
        info = cls._coinbase_market_info(market)
        for candidate in (
            info.get("settlement_currency_id"),
            info.get("quote_currency_id"),
            info.get("quote_display_symbol"),
            market.get("settle") if isinstance(market, dict) else None,
            market.get("quote") if isinstance(market, dict) else None,
        ):
            text = str(candidate or "").strip().upper()
            if text:
                return text
        return ""

    @classmethod
    def _hydrate_coinbase_market(cls, market):
        if not isinstance(market, dict):
            return market

        hydrated = dict(market)
        subtype = cls._coinbase_market_subtype(hydrated)
        if not subtype:
            if str(hydrated.get("type") or "").strip().lower() == "spot":
                hydrated["spot"] = True
            return hydrated

        info = cls._coinbase_market_info(hydrated)
        future_details = info.get("future_product_details")
        future_details = future_details if isinstance(future_details, dict) else {}
        base = str(info.get("base_currency_id") or hydrated.get("base") or "").strip().upper()
        quote = str(info.get("quote_currency_id") or hydrated.get("quote") or "").strip().upper()
        settle = cls._coinbase_market_settle_currency(hydrated) or quote
        native_symbol = str(info.get("product_id") or hydrated.get("id") or "").strip().upper()
        if subtype == "future" and native_symbol:
            symbol = native_symbol
        elif base and quote and settle:
            symbol = f"{base}/{quote}:{settle}"
        else:
            symbol = str(hydrated.get("symbol") or hydrated.get("id") or "").strip().upper()

        expiry = (
            future_details.get("expiration_time")
            or future_details.get("contract_expiry")
            or info.get("expiration_time")
            or info.get("contract_expiry")
        )

        hydrated.update(
            {
                "symbol": symbol,
                "settle": settle or None,
                "settleId": settle or None,
                "type": subtype,
                "spot": False,
                "contract": True,
                "future": subtype == "future",
                "swap": subtype == "swap",
                "option": False,
            }
        )
        if base and quote:
            hydrated["underlying_symbol"] = f"{base}/{quote}"
        if native_symbol:
            hydrated["native_symbol"] = native_symbol
        if expiry:
            hydrated["expiryDatetime"] = expiry
        return hydrated

    @classmethod
    def _hydrate_coinbase_markets(cls, markets):
        if isinstance(markets, dict):
            hydrated = {}
            for market_symbol, market in markets.items():
                if not isinstance(market, dict):
                    continue
                item = cls._hydrate_coinbase_market(market)
                key = str((item or {}).get("symbol") or market_symbol or "").strip()
                if key:
                    hydrated[key] = item
            return hydrated

        if isinstance(markets, list):
            return [
                cls._hydrate_coinbase_market(market)
                for market in list(markets or [])
                if isinstance(market, dict)
            ]

        return markets

    def _coinbase_derivative_subtype(self):
        subtype = str(self.extra_options.get("defaultSubType", "") or "").strip().lower()
        if subtype in {"future", "swap"}:
            return subtype

        markets = getattr(self.exchange, "markets", None)
        if isinstance(markets, dict) and markets:
            if any(self._coinbase_market_subtype(market) == "future" for market in markets.values()):
                return "future"
            if any(self._coinbase_market_subtype(market) == "swap" for market in markets.values()):
                return "swap"

        effective_preference = normalize_market_venue(
            getattr(self, "resolved_market_preference", None),
            default=self.market_preference or "auto",
        )
        if effective_preference == "derivative":
            return "future"
        return ""

    def _filtered_symbols_from_markets(self, markets):
        if not isinstance(markets, dict):
            return []

        matched = []
        fallback = []
        skipped_malformed = []
        
        for symbol, market in markets.items():
            candidate = str((market or {}).get("symbol") or symbol or "").strip()
            if not candidate:
                continue
            
            # Filter out malformed symbols (e.g., "00/USD", "00/USDC")
            if not self._is_valid_market_symbol(candidate):
                skipped_malformed.append(candidate)
                continue
            
            fallback.append(candidate)
            if self._market_matches_preference(market):
                matched.append(candidate)
        
        # Log skipped malformed symbols (once per run)
        if skipped_malformed:
            self.logger.debug(
                "Skipped %d malformed market symbols on %s: %s",
                len(skipped_malformed),
                self.exchange_name,
                ", ".join(sorted(set(skipped_malformed))),
            )

        if self.market_preference == "auto" or matched:
            self.resolved_market_preference = self.market_preference if self.market_preference != "auto" else "auto"
            return sorted(dict.fromkeys(matched or fallback))

        self.resolved_market_preference = "auto"
        self.logger.warning(
            "Requested market preference %s was not available on %s; falling back to auto symbols",
            self.market_preference,
            self.exchange_name,
        )
        return sorted(dict.fromkeys(fallback))

    def _is_valid_market_symbol(self, symbol):
        """Validate that a market symbol is properly formatted."""
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            return False
        
        # Symbol should not contain spaces
        if " " in normalized:
            return False
        
        # If no slash, accept it (might be a base-only symbol)
        if "/" not in normalized:
            return True
        
        # Split by slash to get base and quote
        try:
            base, quote_segment = normalized.split("/", 1)
            quote, settle = (quote_segment.split(":", 1) + [""])[:2]
        except (ValueError, IndexError):
            return False
        
        # Both base and quote must exist and be valid
        for leg in (base, quote):
            if not leg:
                return False
            # Must be 2-20 alphanumeric characters
            if not re.fullmatch(r"[A-Z0-9]{2,20}", leg):
                return False
            # Must contain at least one letter (not all numbers like "00")
            if not any(c.isalpha() for c in leg):
                return False
        
        # Validate settle currency if present
        if settle:
            if not re.fullmatch(r"[A-Z0-9]{2,20}", settle):
                return False
            if not any(c.isalpha() for c in settle):
                return False
        
        return True

    def _supports_positions_endpoint(self):
        exchange_code = self._exchange_code()
        if exchange_code in SPOT_ONLY_EXCHANGES:
            return False

        markets = getattr(self.exchange, "markets", None)
        if exchange_code == "coinbase":
            return self._supports_coinbase_positions_endpoint(markets)

        if not isinstance(markets, dict) or not markets:
            return True

        summary = self._market_flag_summary(markets)
        if summary["derivative"] or summary["option"]:
            return True

        if summary["flags_detected"]:
            return False

        return True

    def apply_market_preference(self, preference=None):
        if preference is not None:
            normalized = normalize_market_venue(preference)
            self.market_preference = normalized
            self.extra_options["market_type"] = normalized
        markets = getattr(self.exchange, "markets", {}) if self.exchange is not None else {}
        self.symbols = self._filtered_symbols_from_markets(markets)
        self._refresh_market_symbol_lookup(markets)
        return list(self.symbols)

    def supported_market_venues(self):
        exchange_code = self._exchange_code()
        if exchange_code in SPOT_ONLY_EXCHANGES:
            return ["auto", "spot"]

        profile_venues = supported_market_venues_for_profile("crypto", exchange_code)
        markets = getattr(getattr(self, "exchange", None), "markets", None)
        if isinstance(markets, dict) and markets:
            venues = ["auto"]
            if any(bool((market or {}).get("spot")) for market in markets.values()):
                venues.append("spot")
            if any(self._market_is_derivative(market) for market in markets.values()):
                venues.append("derivative")
            if any(bool((market or {}).get("option")) for market in markets.values()):
                venues.append("option")
            if any(self._market_is_otc(market) for market in markets.values()):
                venues.append("otc")
            if exchange_code == "coinbase":
                venues = [venue for venue in venues if venue != "option"]
                return list(dict.fromkeys(profile_venues + venues))
            if len(venues) > 1:
                return list(dict.fromkeys(venues))

        return profile_venues

    def _build_exchange_config(self):
        cfg = {
            "enableRateLimit": True,
            "timeout": self.timeout,
            "options": self._build_exchange_options(),
        }

        if self.session is not None:
            cfg["session"] = self.session

        if self.api_key:
            cfg["apiKey"] = self.api_key
        if self.secret:
            cfg["secret"] = self.secret
        if self.password:
            cfg["password"] = self.password
        if self.uid:
            cfg["uid"] = self.uid
        if self.wallet:
            cfg["walletAddress"] = self.wallet

        if self.exchange_name.startswith("binance"):
            cfg["recvWindow"] = int(self.extra_options.get("recvWindow", 10000))

        return cfg

    def _timeframe_seconds(self, timeframe):
        if self.exchange is not None:
            parser = getattr(self.exchange, "parse_timeframe", None)
            if callable(parser):
                try:
                    return int(parser(timeframe))
                except Exception:
                    pass

        fallback = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "1d": 86400,
        }
        return int(fallback.get(str(timeframe or "").strip().lower(), 3600))

    def _coinbase_ohlcv_limiter(self):
        limiter = getattr(self, "_coinbase_ohlcv_semaphore", None)
        if limiter is None:
            limiter = asyncio.Semaphore(self.COINBASE_OHLCV_MAX_CONCURRENCY)
            self._coinbase_ohlcv_semaphore = limiter
        return limiter

    def _install_exchange_markets(self, markets):
        if self.exchange is None:
            return {}

        normalized = markets
        if self._exchange_code() == "coinbase":
            normalized = self._hydrate_coinbase_markets(markets)

        currencies = getattr(self.exchange, "currencies", None)
        if hasattr(self.exchange, "set_markets"):
            payload = list(normalized.values()) if isinstance(normalized, dict) else normalized
            try:
                self.exchange.set_markets(payload, currencies=currencies)
            except TypeError:
                self.exchange.set_markets(normalized, currencies=currencies)
        elif hasattr(self.exchange, "setMarkets"):
            payload = list(normalized.values()) if isinstance(normalized, dict) else normalized
            try:
                self.exchange.setMarkets(payload, currencies)
            except TypeError:
                self.exchange.setMarkets(normalized, currencies)
        elif isinstance(normalized, dict):
            self.exchange.markets = dict(normalized)
        else:
            self.exchange.markets = {
                str((market or {}).get("symbol") or (market or {}).get("id") or "").strip(): dict(market)
                for market in list(normalized or [])
                if isinstance(market, dict)
                and str((market or {}).get("symbol") or (market or {}).get("id") or "").strip()
            }

        hydrated = getattr(self.exchange, "markets", None)
        if isinstance(hydrated, dict) and hydrated:
            return hydrated
        return normalized if isinstance(normalized, dict) else {}

    async def _load_exchange_markets(self):
        if self.exchange is None:
            return {}

        exchange_code = self._exchange_code()
        if exchange_code == "coinbase" and self._exchange_has("fetchMarkets"):
            try:
                fast_markets = await self.exchange.fetch_markets()
                if fast_markets:
                    hydrated = self._install_exchange_markets(fast_markets)
                    if isinstance(hydrated, dict) and hydrated:
                        self.logger.info("Coinbase fast market bootstrap loaded %s markets", len(hydrated))
                        return hydrated
            except Exception as exc:
                self.logger.debug("Coinbase fast market bootstrap fell back to load_markets: %s", exc)

        loaded = await self.exchange.load_markets()
        markets = getattr(self.exchange, "markets", None)
        if exchange_code == "coinbase":
            markets = self._install_exchange_markets(markets if isinstance(markets, dict) and markets else loaded)
        if isinstance(markets, dict) and markets:
            return markets
        return markets if isinstance(markets, dict) else (loaded if isinstance(loaded, dict) else {})

    @staticmethod
    def _ticker_mid_price(ticker):
        if not isinstance(ticker, dict):
            return None

        bid = ticker.get("bid")
        ask = ticker.get("ask")
        try:
            bid_value = float(bid) if bid not in (None, "") else None
        except Exception:
            bid_value = None
        try:
            ask_value = float(ask) if ask not in (None, "") else None
        except Exception:
            ask_value = None
        if bid_value is not None and ask_value is not None and bid_value > 0 and ask_value > 0:
            return (bid_value + ask_value) / 2.0

        for key in ("last", "close", "price", "mark", "index"):
            value = ticker.get(key)
            try:
                numeric = float(value) if value not in (None, "") else None
            except Exception:
                numeric = None
            if numeric is not None and numeric > 0:
                return numeric
        return None

    async def _fetch_raw_balance(self):
        return await self._call_unified("fetch_balance")

    def _spot_balance_totals(self, balance):
        if not isinstance(balance, dict):
            return {}

        source = {}
        total_bucket = balance.get("total")
        if isinstance(total_bucket, dict) and total_bucket:
            source = dict(total_bucket)
        else:
            for bucket_name in ("free", "used"):
                bucket = balance.get(bucket_name)
                if not isinstance(bucket, dict):
                    continue
                for asset, value in bucket.items():
                    normalized_asset = str(asset or "").upper().strip()
                    if not normalized_asset:
                        continue
                    try:
                        source[normalized_asset] = float(source.get(normalized_asset, 0.0) or 0.0) + float(value or 0.0)
                    except Exception:
                        continue

        if not source:
            skip = {
                "free",
                "used",
                "total",
                "info",
                "raw",
                "equity",
                "cash",
                "balance",
                "account_value",
                "total_account_value",
                "net_liquidation",
                "position_value",
                "positions_value",
            }
            for asset, value in balance.items():
                if asset in skip:
                    continue
                normalized_asset = str(asset or "").upper().strip()
                if not normalized_asset:
                    continue
                try:
                    source[normalized_asset] = float(value or 0.0)
                except Exception:
                    continue

        cleaned = {}
        for asset, value in source.items():
            try:
                numeric = float(value or 0.0)
            except Exception:
                continue
            if abs(numeric) <= self.SPOT_DUST_THRESHOLD:
                continue
            cleaned[str(asset).upper()] = numeric
        return cleaned

    @staticmethod
    def _market_base_quote(symbol, market=None):
        if isinstance(market, dict):
            base = str(market.get("base") or "").upper().strip()
            quote = str(market.get("quote") or "").upper().strip()
            if base and quote:
                return base, quote

        normalized = CCXTBroker._normalize_market_symbol(
            (market or {}).get("symbol") if isinstance(market, dict) else symbol
        )
        if "/" not in normalized:
            return "", ""
        base, quote = normalized.split("/", 1)
        return base.strip(), quote.strip()

    def _spot_symbol_candidates(self, base_asset, quote_candidates=None):
        normalized_base = str(base_asset or "").upper().strip()
        if not normalized_base:
            return []

        preferred_quotes = [str(code or "").upper().strip() for code in (quote_candidates or self.SPOT_VALUE_QUOTE_PRIORITY)]
        quote_rank = {quote: index for index, quote in enumerate(preferred_quotes)}
        markets = getattr(self.exchange, "markets", None)
        if not isinstance(markets, dict) or not markets:
            return []

        ranked = []
        seen = set()
        for market_symbol, market in markets.items():
            if isinstance(market, dict) and (self._market_is_derivative(market) or bool(market.get("option"))):
                continue

            base, quote = self._market_base_quote(market_symbol, market)
            if base != normalized_base or not quote:
                continue
            if preferred_quotes and quote not in quote_rank:
                continue

            symbol_text = str((market or {}).get("symbol") if isinstance(market, dict) else market_symbol or "").upper().strip()
            if not symbol_text or symbol_text in seen:
                continue
            seen.add(symbol_text)
            ranked.append((quote_rank.get(quote, len(preferred_quotes)), symbol_text, quote))

        ranked.sort(key=lambda item: (item[0], item[1]))
        return [(symbol, quote) for _, symbol, quote in ranked]

    def _spot_inverse_symbol_candidates(self, quote_asset, base_candidates=None):
        normalized_quote = str(quote_asset or "").upper().strip()
        if not normalized_quote:
            return []

        preferred_bases = [str(code or "").upper().strip() for code in (base_candidates or self.SPOT_VALUE_QUOTE_PRIORITY)]
        base_rank = {base: index for index, base in enumerate(preferred_bases)}
        markets = getattr(self.exchange, "markets", None)
        if not isinstance(markets, dict) or not markets:
            return []

        ranked = []
        seen = set()
        for market_symbol, market in markets.items():
            if isinstance(market, dict) and (self._market_is_derivative(market) or bool(market.get("option"))):
                continue

            base, quote = self._market_base_quote(market_symbol, market)
            if quote != normalized_quote or not base:
                continue
            if preferred_bases and base not in base_rank:
                continue

            symbol_text = str((market or {}).get("symbol") if isinstance(market, dict) else market_symbol or "").upper().strip()
            if not symbol_text or symbol_text in seen:
                continue
            seen.add(symbol_text)
            ranked.append((base_rank.get(base, len(preferred_bases)), symbol_text, base))

        ranked.sort(key=lambda item: (item[0], item[1]))
        return [(symbol, base) for _, symbol, base in ranked]

    async def _spot_symbol_mid_price(self, symbol):
        normalized_symbol = self._normalize_market_symbol(symbol)
        if not normalized_symbol:
            return None
        if not self.supports_symbol(normalized_symbol):
            return None

        now = time.monotonic()
        cached_price = self._ticker_price_cache.get(normalized_symbol)
        if cached_price is not None and now < float(self._ticker_price_cache_until.get(normalized_symbol, 0.0) or 0.0):
            return float(cached_price)

        inflight = self._ticker_price_inflight.get(normalized_symbol)
        if inflight is not None and not inflight.done():
            return await inflight

        async def runner():
            ticker = await self._call_unified("fetch_ticker", normalized_symbol, default=None)
            price = self._ticker_mid_price(ticker)
            if price is not None and price > 0:
                self._ticker_price_cache[normalized_symbol] = float(price)
                self._ticker_price_cache_until[normalized_symbol] = time.monotonic() + self.SPOT_PRICE_CACHE_SECONDS
                return float(price)
            return None

        task = asyncio.create_task(runner())
        self._ticker_price_inflight[normalized_symbol] = task
        try:
            return await task
        finally:
            current = self._ticker_price_inflight.get(normalized_symbol)
            if current is task:
                self._ticker_price_inflight.pop(normalized_symbol, None)

    async def _spot_asset_valuation_usd(self, asset_code, visited=None):
        normalized_asset = str(asset_code or "").upper().strip()
        if not normalized_asset:
            return (None, "")
        if normalized_asset in {"USD", "USDC", "USDT", "BUSD"}:
            return (1.0, normalized_asset)

        visited_assets = set(visited or set())
        if normalized_asset in visited_assets:
            return (None, "")
        visited_assets.add(normalized_asset)

        for symbol, quote in self._spot_symbol_candidates(normalized_asset):
            price = await self._spot_symbol_mid_price(symbol)
            if price is None or price <= 0:
                continue
            if quote in {"USD", "USDC", "USDT", "BUSD"}:
                return (float(price), symbol)

            quote_price, _quote_symbol = await self._spot_asset_valuation_usd(quote, visited=visited_assets)
            if quote_price is None or quote_price <= 0:
                continue
            return (float(price) * float(quote_price), symbol)

        for symbol, base in self._spot_inverse_symbol_candidates(normalized_asset):
            price = await self._spot_symbol_mid_price(symbol)
            if price is None or price <= 0:
                continue
            if base in {"USD", "USDC", "USDT", "BUSD"}:
                return (1.0 / float(price), symbol)

            base_price, _base_symbol = await self._spot_asset_valuation_usd(base, visited=visited_assets)
            if base_price is None or base_price <= 0:
                continue
            return (float(base_price) / float(price), symbol)

        return (None, "")

    async def _spot_account_snapshot_from_balance(self, raw_balance):
        totals = self._spot_balance_totals(raw_balance)
        self._account_asset_codes = [asset for asset in sorted(totals) if asset]
        positions = []
        cash_value = 0.0

        for asset_code, amount in sorted(totals.items()):
            try:
                amount_value = float(amount or 0.0)
            except Exception:
                continue
            if amount_value <= self.SPOT_DUST_THRESHOLD:
                continue

            price_usd, reference_symbol = await self._spot_asset_valuation_usd(asset_code)
            if price_usd is None or price_usd <= 0:
                if asset_code in {"USD", "USDC", "USDT", "BUSD"}:
                    cash_value += amount_value
                continue

            if asset_code in self.SPOT_CASH_EQUIVALENTS:
                cash_value += amount_value * float(price_usd)
                continue

            positions.append(
                {
                    "symbol": reference_symbol or f"{asset_code}/USD",
                    "asset_code": asset_code,
                    "side": "long",
                    "position_side": "long",
                    "amount": amount_value,
                    "units": amount_value,
                    "entry_price": float(price_usd),
                    "mark_price": float(price_usd),
                    "market_price": float(price_usd),
                    "value": amount_value * float(price_usd),
                    "pnl": 0.0,
                    "realized_pnl": 0.0,
                    "financing": 0.0,
                    "margin_used": 0.0,
                    "resettable_pl": 0.0,
                    "quote_currency": "USD",
                    "position_key": asset_code,
                }
            )

        return {
            "positions": positions,
            "cash_value": float(cash_value),
        }

    @staticmethod
    def _spot_position_matches_symbols(position, symbols):
        if not symbols:
            return True

        requested_symbols = set()
        requested_assets = set()
        for symbol in symbols or []:
            normalized = CCXTBroker._normalize_market_symbol(symbol)
            if not normalized:
                continue
            requested_symbols.add(normalized)
            requested_assets.add(normalized.split("/", 1)[0] if "/" in normalized else normalized)

        position_symbol = CCXTBroker._normalize_market_symbol(position.get("symbol"))
        asset_code = str(position.get("asset_code") or "").upper().strip()
        return position_symbol in requested_symbols or asset_code in requested_assets

    async def _augment_spot_balance_snapshot(self, raw_balance):
        if not isinstance(raw_balance, dict):
            return raw_balance

        snapshot = await self._spot_account_snapshot_from_balance(raw_balance)
        return self._compose_spot_balance_snapshot(raw_balance, snapshot)

    def _compose_spot_balance_snapshot(self, raw_balance, snapshot):
        normalized = dict(raw_balance)
        totals = self._spot_balance_totals(raw_balance)
        if totals:
            normalized.setdefault("asset_balances", dict(totals))
        cash_value = float(snapshot.get("cash_value", 0.0) or 0.0)
        position_value = sum(
            float((position or {}).get("value", 0.0) or 0.0)
            for position in snapshot.get("positions", [])
            if isinstance(position, dict)
        )
        account_value = cash_value + position_value

        if cash_value > 0:
            normalized.setdefault("cash", cash_value)
        if position_value > 0:
            normalized.setdefault("position_value", position_value)
            normalized.setdefault("positions_value", position_value)
        if account_value > 0:
            normalized.setdefault("equity", account_value)
            normalized.setdefault("account_value", account_value)
            normalized.setdefault("total_account_value", account_value)
            normalized.setdefault("net_liquidation", account_value)
        return normalized

    @staticmethod
    def _safe_float_value(value, default=0.0):
        if isinstance(value, dict):
            for key in ("value", "amount", "price", "mark", "notional", "balance", "buying_power"):
                if key in value:
                    return CCXTBroker._safe_float_value(value.get(key), default=default)
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _coinbase_jwt_issuer(self):
        issuer = (
            self.extra_options.get("jwt_issuer")
            or self.extra_params.get("jwt_issuer")
            or getattr(self.config, "jwt_issuer", None)
            or self.COINBASE_DEFAULT_JWT_ISSUER
        )
        return str(issuer or self.COINBASE_DEFAULT_JWT_ISSUER).strip() or self.COINBASE_DEFAULT_JWT_ISSUER

    @staticmethod
    def _coinbase_text(value):
        return str(value or "").strip()

    def _coinbase_market_by_product_id(self, product_id):
        normalized_id = str(product_id or "").strip()
        if not normalized_id:
            return None

        markets_by_id = getattr(self.exchange, "markets_by_id", None)
        if isinstance(markets_by_id, dict):
            direct = markets_by_id.get(normalized_id)
            if isinstance(direct, dict):
                return direct
            if isinstance(direct, list):
                for market in direct:
                    if isinstance(market, dict):
                        return market

        markets = getattr(self.exchange, "markets", None)
        if not isinstance(markets, dict):
            return None
        for market in markets.values():
            if not isinstance(market, dict):
                continue
            if str(market.get("id") or "").strip() == normalized_id:
                return market
        return None

    def _coinbase_rest_base_url(self):
        return str(
            ((getattr(self.exchange, "urls", {}) or {}).get("api", {}) or {}).get("rest") or "https://api.coinbase.com"
        ).rstrip("/")

    @staticmethod
    def _coinbase_normalize_request_path(path):
        request_path = str(path or "").strip()
        if not request_path:
            raise ValueError("Coinbase request path is required")
        if not request_path.startswith("/"):
            request_path = "/" + request_path
        return request_path

    @staticmethod
    def _coinbase_query_pairs(params):
        if not isinstance(params, dict):
            return []

        pairs = []
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    if item is not None:
                        pairs.append((key, item))
                continue
            pairs.append((key, value))
        return pairs

    def _coinbase_request_target(self, path, params=None):
        rest_url = self._coinbase_rest_base_url()
        request_path = self._coinbase_normalize_request_path(path)
        query_pairs = self._coinbase_query_pairs(params)
        query_string = urlencode(query_pairs, doseq=True) if query_pairs else ""
        full_path = request_path if not query_string else f"{request_path}?{query_string}"
        return rest_url, request_path, full_path

    def _coinbase_request_headers(self, method, request_path, *, authenticated=True, headers=None):
        request_headers = {
            "Content-Type": "application/json",
        }
        if authenticated:
            jwt_token = build_coinbase_rest_jwt(
                request_method=method,
                request_host=resolve_coinbase_rest_host(self._coinbase_rest_base_url()),
                request_path=request_path,
                api_key=self.api_key,
                api_secret=self.secret,
                issuer=self._coinbase_jwt_issuer(),
            )
            request_headers["Authorization"] = f"Bearer {jwt_token}"
        if isinstance(headers, dict):
            request_headers.update(headers)
        return request_headers

    def _coinbase_session_request(self, method, url, **kwargs):
        request = getattr(self.session, "request", None)
        if callable(request):
            return request(method, url, **kwargs)

        method_callable = getattr(self.session, str(method or "").strip().lower(), None)
        if not callable(method_callable):
            raise RuntimeError(f"Coinbase session does not support {method} requests")
        return method_callable(url, **kwargs)

    @staticmethod
    def _coinbase_decode_response_body(body_text):
        text = str(body_text or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {"message": text}

    async def _coinbase_request_response(self, method, path, params=None, payload=None, *, authenticated=True, headers=None):
        await self._ensure_connected()
        if self.session is None:
            raise RuntimeError("Coinbase session is not initialized")

        normalized_method = str(method or "GET").strip().upper() or "GET"
        rest_url, request_path, full_path = self._coinbase_request_target(path, params=params)
        request_headers = self._coinbase_request_headers(
            normalized_method,
            request_path,
            authenticated=authenticated,
            headers=headers,
        )
        request_kwargs = {"headers": request_headers}
        if payload is not None:
            request_kwargs["json"] = payload

        async with self._coinbase_session_request(normalized_method, f"{rest_url}{full_path}", **request_kwargs) as response:
            body_text = await response.text()
            return {
                "status": int(getattr(response, "status", 0) or 0),
                "path": request_path,
                "text": body_text,
                "payload": self._coinbase_decode_response_body(body_text),
            }

    async def _coinbase_request_json(self, method, path, params=None, payload=None, *, authenticated=True, headers=None):
        response = await self._coinbase_request_response(
            method,
            path,
            params=params,
            payload=payload,
            authenticated=authenticated,
            headers=headers,
        )
        if int(response["status"] or 0) >= 400:
            raise RuntimeError(
                f"Coinbase request failed ({response['status']}) for {str(method or 'GET').strip().upper()} {response['path']}: "
                f"{str(response['text'] or '').strip() or 'empty response'}"
            )
        return response["payload"]

    async def _coinbase_private_get_json(self, path, params=None):
        return await self._coinbase_request_json("GET", path, params=params, authenticated=True)

    async def fetch_coinbase_accounts(self, params=None):
        return await self._coinbase_request_json("GET", "/api/v3/brokerage/accounts", params=params, authenticated=True)

    async def fetch_coinbase_account(self, account_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/accounts/{str(account_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def create_coinbase_order(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/orders",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def cancel_coinbase_orders(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/orders/batch_cancel",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_orders(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/orders/historical/batch",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_fills(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/orders/historical/fills",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_historical_order(self, order_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/orders/historical/{str(order_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def preview_coinbase_order(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/orders/preview",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_best_bid_ask(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/best_bid_ask",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_product_book(self, product_id, params=None):
        query = dict(params or {})
        if product_id:
            query.setdefault("product_id", product_id)
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/product_book",
            params=query,
            authenticated=True,
        )

    async def fetch_coinbase_products(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/products",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_product(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/products/{str(product_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_product_candles(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/products/{str(product_id or '').strip()}/candles",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_market_trades(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/products/{str(product_id or '').strip()}/ticker",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_transaction_summary(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/transaction_summary",
            params=params,
            authenticated=True,
        )

    async def create_coinbase_convert_quote(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/convert/quote",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def commit_coinbase_convert_trade(self, trade_id, payload=None, params=None):
        return await self._coinbase_request_json(
            "POST",
            f"/api/v3/brokerage/convert/{str(trade_id or '').strip()}",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_convert_trade(self, trade_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/convert/{str(trade_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_portfolios(self, portfolio_id=None, params=None):
        path = "/api/v3/brokerage/portfolios"
        if portfolio_id:
            path += f"/{str(portfolio_id).strip()}"
        return await self._coinbase_request_json("GET", path, params=params, authenticated=True)

    async def create_coinbase_portfolio(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/portfolios",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def move_coinbase_portfolio_funds(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/portfolios",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_portfolio_breakdown(self, portfolio_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/portfolios/{str(portfolio_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def delete_coinbase_portfolio(self, portfolio_id=None, payload=None, params=None):
        path = "/api/v3/brokerage/portfolios"
        if portfolio_id:
            path += f"/{str(portfolio_id).strip()}"
        return await self._coinbase_request_json(
            "DELETE",
            path,
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def edit_coinbase_portfolio(self, portfolio_id=None, payload=None, params=None):
        path = "/api/v3/brokerage/portfolios"
        if portfolio_id:
            path += f"/{str(portfolio_id).strip()}"
        return await self._coinbase_request_json(
            "PUT",
            path,
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_futures_balance_summary(self, params=None, *, normalize=False):
        payload = await self._coinbase_request_json(
            "GET",
            self.COINBASE_FUTURES_BALANCE_PATH,
            params=params,
            authenticated=True,
        )
        if normalize:
            return self._normalize_coinbase_futures_balance_summary(payload)
        return payload

    async def fetch_coinbase_futures_positions(self, params=None, *, symbols=None, normalize=False):
        payload = await self._coinbase_request_json(
            "GET",
            self.COINBASE_FUTURES_POSITIONS_PATH,
            params=params,
            authenticated=True,
        )
        if not normalize:
            return payload

        records = []
        if isinstance(payload, dict):
            for key in ("positions", "cfm_positions", "data"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    records = list(candidate)
                    break
        elif isinstance(payload, list):
            records = list(payload)

        normalized_positions = []
        for item in records:
            position = self._normalize_coinbase_futures_position(item)
            if position is None:
                continue
            if symbols and not self._spot_position_matches_symbols(position, symbols):
                continue
            normalized_positions.append(position)
        return normalized_positions

    async def fetch_coinbase_futures_position(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/cfm/positions/{str(product_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def schedule_coinbase_futures_sweep(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/cfm/sweeps/schedule",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_futures_sweeps(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/cfm/sweeps",
            params=params,
            authenticated=True,
        )

    async def cancel_coinbase_futures_sweep(self, payload=None, params=None):
        return await self._coinbase_request_json(
            "DELETE",
            "/api/v3/brokerage/cfm/sweeps",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_intraday_margin_setting(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/cfm/intraday/margin_setting",
            params=params,
            authenticated=True,
        )

    async def set_coinbase_intraday_margin_setting(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/cfm/intraday/margin_setting",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def fetch_coinbase_current_margin_window(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/cfm/intraday/current_margin_window",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_perpetuals_portfolio_summary(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/intx/portfolio",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_perpetuals_positions(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/intx/positions",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_perpetuals_position(self, product_id, params=None):
        query = dict(params or {})
        if product_id:
            query.setdefault("product_id", product_id)
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/intx/positions",
            params=query,
            authenticated=True,
        )

    async def fetch_coinbase_perpetuals_balances(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/intx/balances",
            params=params,
            authenticated=True,
        )

    async def opt_in_coinbase_multi_asset_collateral(self, payload=None, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/intx/multi_asset_collateral",
            params=params,
            payload=payload,
            authenticated=True,
        )

    async def allocate_coinbase_portfolio(self, payload, params=None):
        return await self._coinbase_request_json(
            "POST",
            "/api/v3/brokerage/intx/allocate",
            params=params,
            payload=payload,
            authenticated=True,
        )

    @staticmethod
    def _coinbase_side(side):
        normalized = str(side or "").strip().upper()
        if normalized in {"BUY", "SELL"}:
            return normalized
        if normalized.startswith("B"):
            return "BUY"
        if normalized.startswith("S"):
            return "SELL"
        return ""

    def _coinbase_order_type(self, order_type):
        return str(order_type or "market").strip().lower().replace(" ", "_") or "market"

    def _coinbase_product_id_candidates(self, symbol, *, is_perpetual):
        text = self._coinbase_text(symbol).upper().replace("_", "-").replace("/", "-")
        if not text:
            return []

        candidates = []
        if is_perpetual:
            if text.endswith("-PERP"):
                candidates.append(text)
            else:
                base = text.split("-", 1)[0]
                if base:
                    candidates.append(f"{base}-PERP")
                candidates.append(text)
        else:
            if "-" not in text:
                candidates.append(f"{text}-USD")
            candidates.append(text)
            if text.endswith("-USDC"):
                candidates.append(text[:-1] + "D")
        return list(dict.fromkeys([candidate for candidate in candidates if candidate]))

    def _coinbase_is_perpetual_order(self, symbol, params=None):
        order_params = dict(params or {})
        explicit = order_params.get("is_perpetual")
        if explicit is None:
            explicit = order_params.get("perpetual")
        if explicit is not None:
            return bool(explicit)
        normalized_symbol = self._coinbase_text(symbol).upper()
        if "PERP" in normalized_symbol:
            return True
        if self._coinbase_derivative_subtype() == "swap":
            return True
        return False

    def _coinbase_numeric_value(self, payload, *path, default=0.0):
        current = payload
        for key in path:
            if not isinstance(current, dict):
                return float(default)
            current = current.get(key)
        return self._safe_float_value(current, default=default)

    def _coinbase_currency_value(self, payload, *path, default="USDC"):
        current = payload
        for key in path:
            if not isinstance(current, dict):
                return str(default or "USDC")
            current = current.get(key)
        text = self._coinbase_text(current).upper()
        return text or str(default or "USDC").upper()

    async def _coinbase_products_cached(self, *, refresh=False):
        now = time.monotonic()
        if (
            not refresh
            and isinstance(self._coinbase_products_cache, list)
            and now < float(self._coinbase_products_cache_until or 0.0)
        ):
            return copy.deepcopy(self._coinbase_products_cache)

        payload = await self.fetch_coinbase_products()
        products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(products, list):
            products = []
        self._coinbase_products_cache = copy.deepcopy(products)
        self._coinbase_products_cache_until = now + self.COINBASE_PRODUCT_CACHE_SECONDS
        return copy.deepcopy(products)

    async def _coinbase_resolve_product(self, symbol, *, is_perpetual=False, refresh=False):
        candidates = self._coinbase_product_id_candidates(symbol, is_perpetual=is_perpetual)
        if not candidates:
            return None

        products = await self._coinbase_products_cached(refresh=refresh)
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = self._coinbase_text(product.get("product_id") or product.get("id")).upper()
            if product_id in candidates:
                return dict(product)
        return None

    async def _coinbase_perpetuals_enabled(self, *, refresh=False):
        now = time.monotonic()
        if (
            not refresh
            and self._coinbase_derivatives_enabled_cache is not None
            and now < float(self._coinbase_derivatives_enabled_cache_until or 0.0)
        ):
            return bool(self._coinbase_derivatives_enabled_cache)

        payload = await self.fetch_coinbase_portfolios(params={"portfolio_type": "INTX"})
        portfolios = payload.get("portfolios") if isinstance(payload, dict) else None
        enabled = any(
            isinstance(portfolio, dict)
            and self._coinbase_text(portfolio.get("type") or portfolio.get("portfolio_type")).upper() == "INTX"
            and not bool(portfolio.get("deleted"))
            for portfolio in (portfolios or [])
        )
        self._coinbase_derivatives_enabled_cache = enabled
        self._coinbase_derivatives_enabled_cache_until = now + self.COINBASE_PORTFOLIO_CACHE_SECONDS
        return enabled

    async def _coinbase_perpetual_portfolio_snapshot(self, *, refresh=False):
        now = time.monotonic()
        if (
            not refresh
            and isinstance(self._coinbase_intx_portfolio_cache, dict)
            and now < float(self._coinbase_intx_portfolio_cache_until or 0.0)
        ):
            return copy.deepcopy(self._coinbase_intx_portfolio_cache)

        payload = await self.fetch_coinbase_perpetuals_portfolio_summary()
        self._coinbase_intx_portfolio_cache = copy.deepcopy(payload if isinstance(payload, dict) else {})
        self._coinbase_intx_portfolio_cache_until = now + self.COINBASE_PORTFOLIO_CACHE_SECONDS
        return copy.deepcopy(self._coinbase_intx_portfolio_cache)

    async def list_products(self, *, is_perpetual=None, refresh=False):
        if self._exchange_code() != "coinbase":
            return await self.fetch_markets()

        products = await self._coinbase_products_cached(refresh=refresh)
        if is_perpetual is None:
            return products

        filtered = []
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = self._coinbase_text(product.get("product_id") or product.get("id")).upper()
            product_type = self._coinbase_text(product.get("product_type")).upper()
            future_details = product.get("future_product_details")
            contract_expiry_type = self._coinbase_text(
                (future_details or {}).get("contract_expiry_type") if isinstance(future_details, dict) else None
            ).upper()
            is_product_perpetual = "PERP" in product_id or contract_expiry_type == "PERPETUAL"
            if bool(is_perpetual) == is_product_perpetual and (product_type in {"", "FUTURE"} or is_product_perpetual):
                filtered.append(product)
        return filtered

    async def list_positions(self, *, is_perpetual=None, symbols=None):
        if self._exchange_code() == "coinbase" and bool(is_perpetual):
            return await self._fetch_coinbase_perpetuals_positions(symbols=symbols)
        return await self.fetch_positions(symbols=symbols)

    async def get_portfolio_summary(self, *, is_perpetual=None, refresh=False):
        if self._exchange_code() == "coinbase" and bool(is_perpetual):
            return await self._fetch_coinbase_perpetuals_portfolio_summary(refresh=refresh)
        return await self.fetch_balance()

    def set_leverage(self, symbol, leverage):
        product_id = self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0]
        numeric = self._safe_float_value(leverage, default=0.0)
        if numeric <= 0:
            raise ValueError("Coinbase leverage must be positive")
        if numeric > self.COINBASE_MAX_PERPETUAL_LEVERAGE:
            raise ValueError(
                f"Coinbase perpetual leverage may not exceed {self.COINBASE_MAX_PERPETUAL_LEVERAGE:.0f}x"
            )
        self._coinbase_leverage_by_product[product_id] = numeric
        return {"symbol": product_id, "leverage": numeric}

    async def fetch_coinbase_payment_methods(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/payment_methods",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_payment_method(self, payment_method_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/payment_methods/{str(payment_method_id or '').strip()}",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_key_permissions(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/key_permissions",
            params=params,
            authenticated=True,
        )

    async def fetch_coinbase_server_time(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/time",
            params=params,
            authenticated=False,
        )

    async def fetch_coinbase_public_product_book(self, product_id, params=None):
        query = dict(params or {})
        if product_id:
            query.setdefault("product_id", product_id)
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/market/product_book",
            params=query,
            authenticated=False,
        )

    async def fetch_coinbase_public_products(self, params=None):
        return await self._coinbase_request_json(
            "GET",
            "/api/v3/brokerage/market/products",
            params=params,
            authenticated=False,
        )

    async def fetch_coinbase_public_product(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/market/products/{str(product_id or '').strip()}",
            params=params,
            authenticated=False,
        )

    async def fetch_coinbase_public_product_candles(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/market/products/{str(product_id or '').strip()}/candles",
            params=params,
            authenticated=False,
        )

    async def fetch_coinbase_public_market_trades(self, product_id, params=None):
        return await self._coinbase_request_json(
            "GET",
            f"/api/v3/brokerage/market/products/{str(product_id or '').strip()}/ticker",
            params=params,
            authenticated=False,
        )

    def _normalize_coinbase_futures_balance_summary(self, payload):
        summary = payload.get("balance_summary") if isinstance(payload, dict) and isinstance(payload.get("balance_summary"), dict) else payload
        if not isinstance(summary, dict):
            return {}

        total_usd_balance = self._safe_float_value(
            summary.get("total_usd_balance")
            or summary.get("equity")
            or summary.get("portfolio_value")
            or summary.get("balance")
            or 0.0
        )
        available_margin = self._safe_float_value(
            summary.get("available_margin")
            or summary.get("available_buying_power")
            or summary.get("futures_buying_power")
            or summary.get("cfm_usd_balance")
            or total_usd_balance
        )
        cash_value = self._safe_float_value(summary.get("cfm_usd_balance") or available_margin)

        normalized = {
            "currency": "USD",
            "cash": cash_value,
            "equity": total_usd_balance or cash_value,
            "available_margin": available_margin,
            "futures_buying_power": self._safe_float_value(
                summary.get("futures_buying_power") or available_margin
            ),
            "free": {"USD": available_margin},
            "total": {"USD": total_usd_balance or cash_value},
            "raw": summary,
        }
        for key in (
            "unrealized_pnl",
            "daily_realized_pnl",
            "initial_margin",
            "available_margin",
            "total_open_orders_hold_amount",
            "cfm_usd_balance",
            "cbi_usd_balance",
        ):
            if key in summary:
                normalized[key] = self._safe_float_value(summary.get(key))
        return normalized

    def _normalize_coinbase_futures_position(self, raw_position):
        if not isinstance(raw_position, dict):
            return None

        product_id = str(raw_position.get("product_id") or raw_position.get("instrument") or "").strip()
        market = self._coinbase_market_by_product_id(product_id)
        symbol = str((market or {}).get("symbol") or product_id).strip().upper()
        contracts = abs(
            self._safe_float_value(
                raw_position.get("number_of_contracts")
                or raw_position.get("contracts")
                or raw_position.get("size")
                or raw_position.get("position_size")
                or 0.0
            )
        )
        side = str(raw_position.get("side") or raw_position.get("position_side") or "long").strip().lower() or "long"
        if side not in {"long", "short"}:
            side = "short" if side.startswith("s") else "long"
        entry_price = self._safe_float_value(raw_position.get("avg_entry_price") or raw_position.get("entry_price"))
        mark_price = self._safe_float_value(
            raw_position.get("current_price")
            or raw_position.get("mark_price")
            or raw_position.get("price")
        )

        normalized = {
            "symbol": symbol,
            "product_id": product_id or None,
            "side": side,
            "position_side": side,
            "asset_code": str((market or {}).get("base") or "").strip().upper() or None,
            "quote_currency": str((market or {}).get("quote") or (market or {}).get("settle") or "").strip().upper() or None,
            "contracts": contracts,
            "amount": contracts,
            "quantity": contracts,
            "units": contracts,
            "entry_price": entry_price,
            "avg_entry_price": entry_price,
            "mark_price": mark_price,
            "market_price": mark_price,
            "value": self._safe_float_value(raw_position.get("notional_value") or raw_position.get("position_value")),
            "pnl": self._safe_float_value(raw_position.get("unrealized_pnl")),
            "unrealized_pnl": self._safe_float_value(raw_position.get("unrealized_pnl")),
            "realized_pnl": self._safe_float_value(raw_position.get("daily_realized_pnl")),
            "daily_realized_pnl": self._safe_float_value(raw_position.get("daily_realized_pnl")),
            "expiry": raw_position.get("expiration_time") or (market or {}).get("expiryDatetime"),
            "instrument_type": "future",
            "raw": raw_position,
        }
        if isinstance(market, dict):
            normalized["instrument"] = {
                "symbol": symbol,
                "type": "future" if bool(market.get("future")) else "derivative",
                "exchange": self.exchange_name,
                "currency": str(market.get("quote") or market.get("settle") or "").strip().upper() or None,
                "contract_size": market.get("contractSize"),
                "multiplier": market.get("contractSize"),
                "expiry": raw_position.get("expiration_time") or market.get("expiryDatetime"),
                "metadata": market,
            }
        return normalized

    async def _fetch_coinbase_futures_balance_summary(self):
        return await self.fetch_coinbase_futures_balance_summary(normalize=True)

    async def _fetch_coinbase_futures_positions(self, symbols=None):
        return await self.fetch_coinbase_futures_positions(symbols=symbols, normalize=True)

    def _normalize_coinbase_perpetuals_portfolio_summary(self, payload):
        if not isinstance(payload, dict):
            return {}

        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        portfolio = {}
        portfolios = payload.get("portfolios")
        if isinstance(portfolios, list):
            portfolio = next((row for row in portfolios if isinstance(row, dict)), {})

        currency = (
            self._coinbase_currency_value(summary, "total_balance", "currency", default="")
            or self._coinbase_currency_value(portfolio, "total_balance", "currency", default="USDC")
        )
        equity = self._coinbase_numeric_value(summary, "total_balance", "value")
        if equity <= 0:
            equity = self._coinbase_numeric_value(portfolio, "total_balance", "value")
        collateral = self._safe_float_value(portfolio.get("collateral"))
        buying_power = self._coinbase_numeric_value(summary, "buying_power", "value")
        if buying_power <= 0:
            buying_power = collateral or equity

        normalized = {
            "currency": currency,
            "cash": collateral or equity,
            "equity": equity or collateral,
            "collateral": collateral or equity,
            "available_margin": buying_power,
            "buying_power": buying_power,
            "free": {currency: buying_power},
            "total": {currency: equity or collateral},
            "unrealized_pnl": self._coinbase_numeric_value(summary, "unrealized_pnl", "value"),
            "portfolio_initial_margin": self._safe_float_value(portfolio.get("portfolio_initial_margin")),
            "portfolio_maintenance_margin": self._safe_float_value(portfolio.get("portfolio_maintenance_margin")),
            "liquidation_buffer": self._safe_float_value(portfolio.get("liquidation_buffer")),
            "liquidation_percentage": self._safe_float_value(portfolio.get("liquidation_percentage")),
            "margin_type": portfolio.get("margin_type"),
            "raw": payload,
        }
        return normalized

    def _normalize_coinbase_perpetuals_position(self, raw_position):
        if not isinstance(raw_position, dict):
            return None

        product_id = self._coinbase_text(raw_position.get("product_id") or raw_position.get("symbol")).upper()
        market = self._coinbase_market_by_product_id(product_id)
        symbol = self._coinbase_text((market or {}).get("symbol") or product_id).upper()
        contracts = abs(
            self._safe_float_value(
                raw_position.get("number_of_contracts")
                or raw_position.get("contracts")
                or raw_position.get("size")
                or raw_position.get("net_size")
                or raw_position.get("quantity")
            )
        )
        side = self._coinbase_text(raw_position.get("side") or raw_position.get("position_side") or "long").lower()
        if side not in {"long", "short"}:
            side = "short" if side.startswith("s") else "long"
        entry_price = self._safe_float_value(raw_position.get("avg_entry_price") or raw_position.get("entry_price"))
        mark_price = self._safe_float_value(
            raw_position.get("current_price")
            or raw_position.get("mark_price")
            or raw_position.get("price")
        )

        normalized = {
            "symbol": symbol,
            "product_id": product_id or None,
            "side": side,
            "position_side": side,
            "asset_code": self._coinbase_text((market or {}).get("base")).upper() or None,
            "quote_currency": self._coinbase_text((market or {}).get("quote") or (market or {}).get("settle")).upper() or "USDC",
            "contracts": contracts,
            "amount": contracts,
            "quantity": contracts,
            "units": contracts,
            "entry_price": entry_price,
            "avg_entry_price": entry_price,
            "mark_price": mark_price,
            "market_price": mark_price,
            "value": self._safe_float_value(
                raw_position.get("notional")
                or raw_position.get("notional_value")
                or raw_position.get("position_notional")
            ),
            "pnl": self._safe_float_value(raw_position.get("unrealized_pnl") or raw_position.get("pnl")),
            "unrealized_pnl": self._safe_float_value(raw_position.get("unrealized_pnl") or raw_position.get("pnl")),
            "realized_pnl": self._safe_float_value(raw_position.get("realized_pnl")),
            "instrument_type": "perpetual",
            "raw": raw_position,
        }
        normalized["instrument"] = {
            "symbol": symbol,
            "type": "perpetual",
            "exchange": self.exchange_name,
            "currency": normalized["quote_currency"],
            "metadata": market or {},
        }
        return normalized

    async def _fetch_coinbase_perpetuals_portfolio_summary(self, *, refresh=False):
        return self._normalize_coinbase_perpetuals_portfolio_summary(
            await self._coinbase_perpetual_portfolio_snapshot(refresh=refresh)
        )

    async def _fetch_coinbase_perpetuals_positions(self, symbols=None):
        payload = await self.fetch_coinbase_perpetuals_positions()
        rows = payload.get("positions") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            rows = []

        normalized = []
        for item in rows:
            position = self._normalize_coinbase_perpetuals_position(item)
            if position is None:
                continue
            if symbols and not self._spot_position_matches_symbols(position, symbols):
                continue
            normalized.append(position)
        return normalized

    def _spot_account_cache_seconds(self):
        if self._exchange_code() == "coinbase":
            return self.COINBASE_SPOT_ACCOUNT_CACHE_SECONDS
        return self.SPOT_ACCOUNT_CACHE_SECONDS

    def _invalidate_account_state_cache(self):
        self._spot_account_snapshot_cache = None
        self._spot_account_snapshot_cache_until = 0.0
        self._open_orders_snapshot_cache.clear()
        self._coinbase_intx_portfolio_cache = None
        self._coinbase_intx_portfolio_cache_until = 0.0
        self._coinbase_derivatives_enabled_cache = None
        self._coinbase_derivatives_enabled_cache_until = 0.0

    async def _get_spot_account_snapshot_cached(self):
        now = time.monotonic()
        cached_snapshot = self._spot_account_snapshot_cache
        if cached_snapshot is not None and now < float(self._spot_account_snapshot_cache_until or 0.0):
            return copy.deepcopy(cached_snapshot)

        inflight = self._spot_account_snapshot_inflight
        if inflight is not None and not inflight.done():
            return copy.deepcopy(await inflight)

        async def runner():
            raw_balance = await self._fetch_raw_balance()
            if not isinstance(raw_balance, dict):
                payload = {
                    "raw_balance": raw_balance,
                    "balance": raw_balance,
                    "positions": [],
                    "cash_value": 0.0,
                }
            else:
                snapshot = await self._spot_account_snapshot_from_balance(raw_balance)
                payload = {
                    "raw_balance": raw_balance,
                    "balance": self._compose_spot_balance_snapshot(raw_balance, snapshot),
                    "positions": list(snapshot.get("positions", [])),
                    "cash_value": float(snapshot.get("cash_value", 0.0) or 0.0),
                }

            self._spot_account_snapshot_cache = copy.deepcopy(payload)
            self._spot_account_snapshot_cache_until = time.monotonic() + self._spot_account_cache_seconds()
            return copy.deepcopy(payload)

        task = asyncio.create_task(runner())
        self._spot_account_snapshot_inflight = task
        try:
            return await task
        finally:
            current = self._spot_account_snapshot_inflight
            if current is task:
                self._spot_account_snapshot_inflight = None

    def _coinbase_ohlcv_cache_key(self, symbol, timeframe, limit):
        return f"{str(symbol or '').upper().strip()}|{str(timeframe or '1h').lower().strip()}|{max(int(limit or 0), 1)}"

    def _normalize_ohlcv_boundary_ms(self, value, *, end_of_day=False):
        if value is None:
            return None

        if isinstance(value, datetime):
            timestamp = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
            if end_of_day:
                timestamp = timestamp.replace(hour=23, minute=59, second=59, microsecond=999999)
            return int(timestamp.timestamp() * 1000)

        try:
            numeric = float(value)
            if abs(numeric) > 1e11:
                return int(numeric)
            return int(numeric * 1000)
        except Exception:
            pass

        text_value = str(value or "").strip()
        if not text_value:
            return None
        if "T" not in text_value and len(text_value) <= 10:
            text_value = (
                f"{text_value}T23:59:59.999999+00:00"
                if end_of_day
                else f"{text_value}T00:00:00+00:00"
            )
        if text_value.endswith("Z"):
            text_value = text_value[:-1] + "+00:00"
        try:
            timestamp = datetime.fromisoformat(text_value)
        except ValueError:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        return int(timestamp.timestamp() * 1000)

    async def _fetch_coinbase_ohlcv_cached(self, symbol, timeframe="1h", limit=100):
        cache_key = self._coinbase_ohlcv_cache_key(symbol, timeframe, limit)
        now = time.monotonic()
        cached_rows = self._ohlcv_cache.get(cache_key)
        if isinstance(cached_rows, list) and now < float(self._ohlcv_cache_until.get(cache_key, 0.0) or 0.0):
            return [list(row) if isinstance(row, (list, tuple)) else row for row in cached_rows]

        inflight = self._ohlcv_inflight.get(cache_key)
        if inflight is not None and not inflight.done():
            return await inflight

        async def runner():
            self.logger.debug("Fetching OHLCV for %s", symbol)
            async with self._coinbase_ohlcv_limiter():
                data = await self._fetch_coinbase_ohlcv(symbol, timeframe=timeframe, limit=limit)
            rows = [list(row) if isinstance(row, (list, tuple)) else row for row in (data or [])]
            ttl_seconds = (
                self.COINBASE_OHLCV_SHORTFALL_CACHE_SECONDS
                if len(rows) < max(int(limit or 0), 1)
                else self.COINBASE_OHLCV_CACHE_SECONDS
            )
            self._ohlcv_cache[cache_key] = rows
            self._ohlcv_cache_until[cache_key] = time.monotonic() + ttl_seconds
            return [list(row) if isinstance(row, (list, tuple)) else row for row in rows]

        task = asyncio.create_task(runner())
        self._ohlcv_inflight[cache_key] = task
        try:
            return await task
        finally:
            current = self._ohlcv_inflight.get(cache_key)
            if current is task:
                self._ohlcv_inflight.pop(cache_key, None)

    async def _ensure_connected(self):
        if not self._connected:
            await self.connect()

    def _exchange_has(self, capability):
        exchange = self.exchange
        if exchange is None:
            return False

        if capability == "fetch_positions" and not self._supports_positions_endpoint():
            return False

        has_key = self.CAPABILITY_MAP.get(capability, capability)
        has_map = getattr(exchange, "has", None)
        if isinstance(has_map, dict):
            supported = has_map.get(has_key)
            if supported in (True, "emulated"):
                return True
            if supported is False:
                return False

        return callable(getattr(exchange, capability, None))

    def _maybe_precision_amount(self, symbol, amount):
        if self.exchange is None or amount is None:
            return amount

        converter = getattr(self.exchange, "amount_to_precision", None)
        if callable(converter):
            try:
                return float(converter(symbol, amount))
            except Exception:
                return amount
        return amount

    def _maybe_precision_price(self, symbol, price):
        if self.exchange is None or price is None:
            return price

        converter = getattr(self.exchange, "price_to_precision", None)
        if callable(converter):
            try:
                return float(converter(symbol, price))
            except Exception:
                return price
        return price

    @staticmethod
    def _matches_ccxt_error(exc, *names):
        for name in names:
            error_type = getattr(ccxt, name, None)
            if isinstance(error_type, type) and isinstance(exc, error_type):
                return True
        return False

    def _translate_exchange_exception(self, exc, method_name):
        if isinstance(exc, BrokerOperationError):
            return exc

        action = str(method_name or "request").replace("_", " ")
        exchange_name = str(self.exchange_name or "exchange").upper()
        raw_message = str(exc).strip() or exc.__class__.__name__
        lowered = raw_message.lower()

        if self._matches_ccxt_error(exc, "RateLimitExceeded", "DDoSProtection") or any(
            token in lowered for token in ("too many requests", "429", "rate limit")
        ):
            return BrokerOperationError(
                f"{exchange_name} rate limit hit while {action}: {raw_message}",
                category="rate_limit",
                retryable=True,
                cooldown_seconds=300,
                raw_message=raw_message,
            )

        if self._matches_ccxt_error(exc, "ExchangeNotAvailable", "OnMaintenance", "RequestTimeout", "NetworkError") or any(
            token in lowered
            for token in ("network", "timed out", "timeout", "service unavailable", "temporarily unavailable", "maintenance")
        ):
            return BrokerOperationError(
                f"{exchange_name} is temporarily unavailable while {action}: {raw_message}",
                category="network_error",
                retryable=True,
                cooldown_seconds=120,
                raw_message=raw_message,
            )

        if self._matches_ccxt_error(exc, "InsufficientFunds") or any(
            token in lowered
            for token in (
                "insufficient funds",
                "insufficient_funds",
                "insufficient balance",
                "insufficient margin",
                "insufficient_margin",
            )
        ):
            return BrokerOperationError(
                f"{exchange_name} rejected the order because funds are insufficient: {raw_message}",
                category="insufficient_funds",
                rejection=True,
                cooldown_seconds=120,
                raw_message=raw_message,
            )

        if self._matches_ccxt_error(exc, "InvalidOrder") or any(
            token in lowered
            for token in ("invalid order", "order rejected", "rejected", "min_notional", "minimum notional", "market is closed")
        ):
            return BrokerOperationError(
                f"{exchange_name} rejected the order request: {raw_message}",
                category="invalid_order",
                rejection=True,
                cooldown_seconds=180,
                raw_message=raw_message,
            )

        if self._matches_ccxt_error(exc, "BadSymbol") or any(
            token in lowered for token in ("unknown symbol", "bad symbol", "symbol not found")
        ):
            return BrokerOperationError(
                f"{exchange_name} does not support the requested symbol: {raw_message}",
                category="unsupported_symbol",
                rejection=True,
                cooldown_seconds=300,
                raw_message=raw_message,
            )

        if self._matches_ccxt_error(exc, "AuthenticationError", "PermissionDenied") or any(
            token in lowered for token in ("invalid api", "authentication", "permission denied", "unauthorized", "forbidden")
        ):
            return BrokerOperationError(
                f"{exchange_name} authentication failed while {action}: {raw_message}",
                category="authentication_error",
                rejection=True,
                cooldown_seconds=600,
                raw_message=raw_message,
            )

        return BrokerOperationError(
            f"{exchange_name} failed while {action}: {raw_message}",
            category="broker_error",
            raw_message=raw_message,
        )

    async def _call_unified(self, method_name, *args, default=None, **kwargs):
        await self._ensure_connected()

        method = getattr(self.exchange, method_name, None)
        if not callable(method):
            if default is not None:
                return default
            raise NotImplementedError(
                f"{self.exchange_name} does not expose {method_name}"
            )

        if not self._exchange_has(method_name):
            if default is not None:
                return default
            raise NotImplementedError(
                f"{self.exchange_name} does not support {method_name}"
            )

        try:
            return await method(*args, **kwargs)
        except Exception as exc:
            raise self._translate_exchange_exception(exc, method_name) from exc

    # ==========================================================
    # CONNECT
    # ==========================================================

    async def connect(self):
        if self._connected:
            return

        self._normalize_credentials()
        self._validate_credentials()

        exchange_class = self._exchange_class()

        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(
            resolver=resolver,
            family=socket.AF_INET,
            ttl_dns_cache=300,
        )
        self.session = aiohttp.ClientSession(connector=connector)
        self.exchange = exchange_class(self._build_exchange_config())

        try:
            if hasattr(self.exchange, "set_sandbox_mode"):
                self.exchange.set_sandbox_mode(self.sandbox)

            if callable(getattr(self.exchange, "load_time_difference", None)):
                await self.exchange.load_time_difference()

            markets = await self._load_exchange_markets()
            self.symbols = self._filtered_symbols_from_markets(markets)
            self._refresh_market_symbol_lookup(markets)
            self._connected = True
        except Exception:
            await self.close()
            raise

    async def close(self):
        errors = []

        if self.exchange is not None:
            try:
                await self.exchange.close()
            except Exception as exc:
                errors.append(exc)

        if self.session is not None:
            try:
                await self.session.close()
            except Exception as exc:
                errors.append(exc)

        self.exchange = None
        self.session = None
        self.symbols = []
        self._market_symbol_lookup = set()
        self._connected = False

        if errors:
            self.logger.warning("Broker close encountered %s issue(s)", len(errors))

    # ==========================================================
    # DISCOVERY
    # ==========================================================

    async def fetch_symbol(self):
        await self._ensure_connected()
        return list(self.symbols)

    async def fetch_symbols(self):
        return await self.fetch_symbol()

    async def fetch_markets(self):
        await self._ensure_connected()
        markets = getattr(self.exchange, "markets", None)
        if isinstance(markets, dict) and markets:
            return markets
        return await self._call_unified("fetch_markets", default={})

    async def fetch_currencies(self):
        await self._ensure_connected()
        currencies = getattr(self.exchange, "currencies", None)
        if isinstance(currencies, dict) and currencies:
            return currencies
        return await self._call_unified("fetch_currencies", default={})

    async def fetch_status(self):
        if not self._connected:
            return {"status": "disconnected"}

        if self._exchange_has("fetchStatus"):
            return await self._call_unified("fetch_status")

        return {"status": "ok", "exchange": self.exchange_name}

    # ==========================================================
    # MARKET DATA
    # ==========================================================

    async def fetch_ticker(self, symbol):
        normalized_symbol = self._normalize_market_symbol(symbol)
        if not self.supports_symbol(normalized_symbol):
            return None
        return await self._call_unified("fetch_ticker", normalized_symbol, default=None)

    async def fetch_tickers(self, symbols=None):
        return await self._call_unified("fetch_tickers", symbols, default={})

    async def fetch_orderbook(self, symbol, limit=100):
        normalized_symbol = self._normalize_market_symbol(symbol)
        if not self.supports_symbol(normalized_symbol):
            return {"bids": [], "asks": []}
        return await self._call_unified(
            "fetch_order_book",
            normalized_symbol,
            limit,
            default={"bids": [], "asks": []},
        )

    async def fetch_order_book(self, symbol, limit=100):
        return await self.fetch_orderbook(symbol, limit=limit)

    async def _fetch_coinbase_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        await self._ensure_connected()

        # Respect the requested history window while chunking each Coinbase API call to its 300-candle maximum.
        requested_limit = max(int(limit or self.COINBASE_MAX_OHLCV_CANDLES), 1)
        timeframe_seconds = max(self._timeframe_seconds(timeframe), 1)
        remaining = requested_limit
        end_ms = self._normalize_ohlcv_boundary_ms(end_time, end_of_day=True)
        start_ms = self._normalize_ohlcv_boundary_ms(start_time, end_of_day=False)
        end_seconds = int((end_ms / 1000.0) if end_ms is not None else time.time())
        start_seconds_boundary = int(start_ms / 1000.0) if start_ms is not None else 0
        seen_timestamps = set()
        candles = []

        while remaining > 0 and end_seconds >= start_seconds_boundary:
            batch_size = min(remaining, self.COINBASE_MAX_OHLCV_CANDLES)
            start_seconds = max(end_seconds - (batch_size * timeframe_seconds), start_seconds_boundary, 0)
            params = {
                "start": str(start_seconds),
                "end": str(end_seconds),
            }
            batch = await self._call_unified(
                "fetch_ohlcv",
                symbol,
                timeframe=timeframe,
                since=start_seconds * 1000,
                limit=batch_size,
                params=params,
                default=[],
            )
            if not batch:
                break

            new_rows = 0
            for candle in batch:
                if not isinstance(candle, (list, tuple)) or not candle:
                    continue
                timestamp = candle[0]
                if start_ms is not None and int(timestamp) < int(start_ms):
                    continue
                if end_ms is not None and int(timestamp) > int(end_ms):
                    continue
                if timestamp in seen_timestamps:
                    continue
                seen_timestamps.add(timestamp)
                candles.append(list(candle))
                new_rows += 1

            candles.sort(key=lambda row: row[0])
            if len(candles) >= requested_limit:
                break

            earliest_timestamp = batch[0][0] if isinstance(batch[0], (list, tuple)) and batch[0] else None
            if earliest_timestamp is None or new_rows == 0 or len(batch) < batch_size:
                break
            if start_ms is not None and int(earliest_timestamp) <= int(start_ms):
                break

            next_end_seconds = int(earliest_timestamp / 1000) - timeframe_seconds
            if next_end_seconds <= 0 or next_end_seconds >= end_seconds:
                break

            end_seconds = next_end_seconds
            remaining = requested_limit - len(candles)

        return candles[-requested_limit:]

    async def _fetch_generic_ohlcv_range(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        await self._ensure_connected()

        # Respect the user-requested limit while capping at the generic maximum.
        requested_limit = max(min(int(limit or self.GENERIC_MAX_OHLCV_CANDLES), self.GENERIC_MAX_OHLCV_CANDLES), 1)
        timeframe_seconds = max(self._timeframe_seconds(timeframe), 1)
        step_ms = timeframe_seconds * 1000
        start_ms = self._normalize_ohlcv_boundary_ms(start_time, end_of_day=False)
        end_ms = self._normalize_ohlcv_boundary_ms(end_time, end_of_day=True)
        if end_ms is None and start_ms is not None:
            end_ms = start_ms + (requested_limit * step_ms)
        if start_ms is None and end_ms is not None:
            start_ms = max(0, end_ms - (requested_limit * step_ms))
        if start_ms is None:
            start_ms = max(0, int(time.time() * 1000) - (requested_limit * step_ms))
        if end_ms is None:
            end_ms = start_ms + (requested_limit * step_ms)
        if start_ms is not None and end_ms is not None:
            newest_window_start = max(0, int(end_ms) - (max(requested_limit - 1, 0) * step_ms))
            start_ms = max(int(start_ms), newest_window_start)

        candles = []
        seen_timestamps = set()
        current_since = int(start_ms)

        while current_since <= int(end_ms) and len(candles) < requested_limit:
            batch_limit = min(self.GENERIC_MAX_OHLCV_CANDLES, requested_limit - len(candles))
            batch = await self._call_unified(
                "fetch_ohlcv",
                symbol,
                timeframe=timeframe,
                since=current_since,
                limit=batch_limit,
                params={},
                default=[],
            )
            if not batch:
                break

            new_rows = 0
            last_timestamp = None
            for candle in batch:
                if not isinstance(candle, (list, tuple)) or len(candle) < 6:
                    continue
                timestamp = int(candle[0])
                last_timestamp = timestamp
                if timestamp < int(start_ms) or timestamp > int(end_ms):
                    continue
                if timestamp in seen_timestamps:
                    continue
                seen_timestamps.add(timestamp)
                candles.append(list(candle[:6]))
                new_rows += 1

            candles.sort(key=lambda row: row[0])
            if len(candles) >= requested_limit or last_timestamp is None or new_rows == 0 or len(batch) < batch_limit:
                break

            next_since = int(last_timestamp) + step_ms
            if next_since <= current_since:
                break
            current_since = next_since

        return candles[-requested_limit:]

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        await self._ensure_connected()
        normalized_symbol = self._normalize_market_symbol(symbol)
        if not self.supports_symbol(normalized_symbol):
            return []
        if start_time is not None or end_time is not None:
            if self._exchange_code() == "coinbase":
                return await self._fetch_coinbase_ohlcv(
                    normalized_symbol,
                    timeframe=timeframe,
                    limit=limit,
                    start_time=start_time,
                    end_time=end_time,
                )
            return await self._fetch_generic_ohlcv_range(
                normalized_symbol,
                timeframe=timeframe,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
            )
        if self._exchange_code() == "coinbase":
            return await self._fetch_coinbase_ohlcv_cached(normalized_symbol, timeframe=timeframe, limit=limit)
        self.logger.debug("Fetching OHLCV for %s", normalized_symbol)
        return await self._call_unified(
            "fetch_ohlcv",
            normalized_symbol,
            timeframe=timeframe,
            limit=limit,
            default=[],
        )

    async def fetch_trades(self, symbol, limit=None):
        normalized_symbol = self._normalize_market_symbol(symbol)
        if not self.supports_symbol(normalized_symbol):
            return []
        kwargs = {}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._call_unified("fetch_trades", normalized_symbol, default=[], **kwargs)

    async def fetch_my_trades(self, symbol=None, limit=None):
        normalized_symbol = self._normalize_market_symbol(symbol) if symbol else None
        if normalized_symbol and not self.supports_symbol(normalized_symbol):
            return []
        kwargs = {}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._call_unified("fetch_my_trades", normalized_symbol, default=[], **kwargs)

    # ==========================================================
    # TRADING
    # ==========================================================

    def _coinbase_rejected_order(
        self,
        *,
        symbol,
        product_id,
        side,
        amount,
        order_type,
        reason,
        client_order_id=None,
        exchange_response=None,
    ):
        return {
            "id": client_order_id or str(uuid4()),
            "client_order_id": client_order_id,
            "symbol": symbol,
            "product_id": product_id,
            "side": str(side or "").lower(),
            "amount": float(amount or 0.0),
            "type": self._coinbase_order_type(order_type),
            "status": "rejected",
            "reason": str(reason or "Coinbase rejected the order."),
            "exchange_response": exchange_response or {},
        }

    async def _coinbase_reference_price(self, product):
        if not isinstance(product, dict):
            return 0.0

        for key in ("price", "mid_market_price", "mark_price", "last_price"):
            price = self._safe_float_value(product.get(key))
            if price > 0:
                return price

        product_id = self._coinbase_text(product.get("product_id") or product.get("id"))
        if not product_id:
            return 0.0

        try:
            ticker = await self.fetch_coinbase_market_trades(product_id)
            for key in ("price", "best_bid", "best_ask"):
                price = self._safe_float_value(ticker.get(key))
                if price > 0:
                    return price
        except Exception as exc:
            self.logger.debug("Unable to fetch Coinbase reference price for %s: %s", product_id, exc)

        return 0.0

    def _coinbase_order_configuration(self, *, order_type, amount, price):
        base_size = f"{float(amount):.8f}".rstrip("0").rstrip(".") or "0"
        normalized_type = self._coinbase_order_type(order_type)
        if normalized_type == "market":
            return {"market_market_ioc": {"base_size": base_size}}
        if normalized_type == "limit":
            if price is None or float(price) <= 0:
                raise ValueError("Coinbase limit orders require a positive price")
            return {
                "limit_limit_gtc": {
                    "base_size": base_size,
                    "limit_price": f"{float(price):.8f}".rstrip("0").rstrip("."),
                }
            }
        raise ValueError(f"Unsupported Coinbase Advanced Trade order type: {normalized_type}")

    async def _coinbase_paper_order(
        self,
        *,
        symbol,
        product_id,
        side,
        amount,
        order_type,
        price,
        client_order_id,
        leverage,
        notional,
        margin_required,
    ):
        return {
            "id": f"paper-{client_order_id}",
            "client_order_id": client_order_id,
            "symbol": symbol,
            "product_id": product_id,
            "side": str(side or "").lower(),
            "amount": float(amount or 0.0),
            "filled_quantity": float(amount or 0.0),
            "remaining_quantity": 0.0,
            "type": self._coinbase_order_type(order_type),
            "price": price,
            "fill_price": price,
            "status": "filled",
            "mode": "paper",
            "leverage": leverage,
            "notional": notional,
            "initial_margin_required": margin_required,
        }

    async def _create_coinbase_perpetual_order(self, *, symbol, side, amount, order_type="market", price=None, params=None):
        order_params = dict(params or {})
        client_order_id = self._coinbase_text(
            order_params.get("client_order_id") or order_params.get("clientOrderId") or uuid4().hex
        )
        normalized_amount = self._safe_float_value(amount)
        if normalized_amount <= 0:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0],
                side=side,
                amount=amount,
                order_type=order_type,
                reason="Coinbase perpetual order size must be positive.",
                client_order_id=client_order_id,
            )
        leverage = self._safe_float_value(
            order_params.get("leverage")
            or self._coinbase_leverage_by_product.get(
                self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0]
            )
            or 1.0,
            default=1.0,
        )
        if leverage <= 0 or leverage > self.COINBASE_MAX_PERPETUAL_LEVERAGE:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0],
                side=side,
                amount=amount,
                order_type=order_type,
                reason=(
                    f"Requested leverage must be between 1 and {self.COINBASE_MAX_PERPETUAL_LEVERAGE:.0f}x for Coinbase perpetuals."
                ),
                client_order_id=client_order_id,
            )

        try:
            derivatives_enabled = await self._coinbase_perpetuals_enabled()
        except Exception as exc:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0],
                side=side,
                amount=amount,
                order_type=order_type,
                reason=f"Unable to verify Coinbase perpetuals access: {exc}",
                client_order_id=client_order_id,
            )
        if not derivatives_enabled:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0],
                side=side,
                amount=amount,
                order_type=order_type,
                reason="Coinbase derivatives trading is not enabled for this account.",
                client_order_id=client_order_id,
            )

        try:
            product = await self._coinbase_resolve_product(symbol, is_perpetual=True)
        except Exception as exc:
            translated = self._translate_exchange_exception(exc, "list_products")
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0],
                side=side,
                amount=amount,
                order_type=order_type,
                reason=str(translated),
                client_order_id=client_order_id,
                exchange_response={"error": getattr(translated, "raw_message", str(exc))},
            )
        if not isinstance(product, dict):
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=self._coinbase_product_id_candidates(symbol, is_perpetual=True)[0],
                side=side,
                amount=amount,
                order_type=order_type,
                reason=f"Coinbase perpetual product was not found for {symbol}.",
                client_order_id=client_order_id,
            )

        product_id = self._coinbase_text(product.get("product_id") or product.get("id")).upper()
        status = self._coinbase_text(product.get("status")).upper()
        if bool(product.get("trading_disabled")) or (status and status not in {"ONLINE", "UNKNOWN"}):
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=f"Coinbase product {product_id} is not currently tradable.",
                client_order_id=client_order_id,
                exchange_response=product,
            )

        normalized_side = self._coinbase_side(side)
        if not normalized_side:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason="Coinbase perpetual orders require side 'buy' or 'sell'.",
                client_order_id=client_order_id,
            )

        reference_price = await self._coinbase_reference_price(product)
        notional = abs(normalized_amount) * max(reference_price, 0.0)
        if notional < self.COINBASE_MIN_PERPETUAL_NOTIONAL:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=(
                    f"Coinbase perpetual orders must be at least {self.COINBASE_MIN_PERPETUAL_NOTIONAL:.0f} USDC notional."
                ),
                client_order_id=client_order_id,
                exchange_response={"notional": notional, "reference_price": reference_price},
            )

        try:
            portfolio_summary = await self._fetch_coinbase_perpetuals_portfolio_summary()
        except Exception as exc:
            translated = self._translate_exchange_exception(exc, "get_portfolio_summary")
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=str(translated),
                client_order_id=client_order_id,
                exchange_response={"error": getattr(translated, "raw_message", str(exc))},
            )
        available_margin = self._safe_float_value(
            portfolio_summary.get("available_margin")
            or portfolio_summary.get("buying_power")
            or portfolio_summary.get("collateral")
        )
        margin_required = notional / max(leverage, 1.0)
        if margin_required > max(available_margin, 0.0):
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason="Insufficient margin in the Coinbase perpetuals portfolio.",
                client_order_id=client_order_id,
                exchange_response={
                    "available_margin": available_margin,
                    "initial_margin_required": margin_required,
                    "notional": notional,
                },
            )

        try:
            order_configuration = self._coinbase_order_configuration(
                order_type=order_type,
                amount=normalized_amount,
                price=price,
            )
        except Exception as exc:
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=str(exc),
                client_order_id=client_order_id,
            )

        if self.mode == "paper":
            return await self._coinbase_paper_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                price=reference_price if reference_price > 0 else price,
                client_order_id=client_order_id,
                leverage=leverage,
                notional=notional,
                margin_required=margin_required,
            )

        request_payload = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": normalized_side,
            "order_configuration": order_configuration,
        }

        try:
            response = await self._coinbase_request_response(
                "POST",
                "/api/v3/brokerage/orders",
                payload=request_payload,
                authenticated=True,
            )
        except Exception as exc:
            translated = self._translate_exchange_exception(exc, "create_order")
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=str(translated),
                client_order_id=client_order_id,
                exchange_response={"error": getattr(translated, "raw_message", str(exc))},
            )

        response_payload = response.get("payload") if isinstance(response, dict) else {}
        status_code = int((response or {}).get("status") or 0)
        if status_code >= 400:
            reason = self._coinbase_text((response_payload or {}).get("message") or (response_payload or {}).get("error"))
            lowered = reason.lower()
            if any(token in lowered for token in ("jwt", "unauthorized", "forbidden")):
                reason = f"Coinbase rejected the JWT credentials: {reason or response.get('text')}"
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=reason or f"Coinbase order request failed with HTTP {status_code}.",
                client_order_id=client_order_id,
                exchange_response=response_payload,
            )

        success = bool((response_payload or {}).get("success", True))
        success_payload = (response_payload or {}).get("success_response")
        failure_reason = self._coinbase_text((response_payload or {}).get("failure_reason"))
        if not success or not isinstance(success_payload, dict):
            return self._coinbase_rejected_order(
                symbol=symbol,
                product_id=product_id,
                side=side,
                amount=amount,
                order_type=order_type,
                reason=failure_reason or "Coinbase rejected the perpetual order.",
                client_order_id=client_order_id,
                exchange_response=response_payload,
            )

        self._invalidate_account_state_cache()
        return {
            "id": success_payload.get("order_id") or client_order_id,
            "client_order_id": success_payload.get("client_order_id") or client_order_id,
            "symbol": symbol,
            "product_id": success_payload.get("product_id") or product_id,
            "side": str(side or "").lower(),
            "amount": float(amount or 0.0),
            "type": self._coinbase_order_type(order_type),
            "status": "open",
            "price": price,
            "notional": notional,
            "leverage": leverage,
            "initial_margin_required": margin_required,
            "exchange_response": response_payload,
        }

    async def place_order(self, order=None, **kwargs):
        if kwargs or order is None or not isinstance(order, Mapping):
            payload = {}
            if order is not None:
                if isinstance(order, Mapping):
                    payload.update(dict(order))
                elif callable(getattr(order, "to_dict", None)):
                    payload.update(dict(order.to_dict()))
                elif hasattr(order, "__dataclass_fields__"):
                    payload.update(
                        {
                            field_name: getattr(order, field_name)
                            for field_name in getattr(order, "__dataclass_fields__", {})
                        }
                    )
                elif hasattr(order, "__dict__"):
                    payload.update(dict(order.__dict__))
                else:
                    raise TypeError(f"Unsupported order payload type: {type(order)!r}")
            payload.update(kwargs)
            if "size" in payload and "quantity" not in payload and "amount" not in payload:
                payload["quantity"] = payload.get("size")
            if "order_type" in payload and "type" not in payload:
                payload["type"] = payload.get("order_type")
            params = dict(payload.get("params") or {})
            for key in ("is_perpetual", "leverage"):
                if key in payload:
                    params.setdefault(key, payload.pop(key))
            payload["params"] = params
            return await super().place_order(payload)
        return await super().place_order(order)

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
        await self._ensure_connected()

        normalized_type = str(type or "market").strip().lower() or "market"
        trigger_price = stop_price
        if trigger_price is None and isinstance(params, dict):
            trigger_price = params.get("stop_price", params.get("stopPrice"))
        if normalized_type == "stop_limit":
            if price is None or float(price) <= 0:
                raise ValueError("stop_limit orders require a positive limit price")
            if trigger_price is None or float(trigger_price) <= 0:
                raise ValueError("stop_limit orders require a positive stop_price trigger")

        normalized_amount = self._maybe_precision_amount(symbol, float(amount))
        normalized_price = self._maybe_precision_price(symbol, price)
        order_params = dict(self.extra_params)
        if params:
            order_params.update(params)
        if trigger_price is not None:
            order_params.setdefault("stopPrice", float(trigger_price))
            order_params.setdefault("stop_price", float(trigger_price))
        if stop_loss is not None and self._supports_attached_protection_prices():
            order_params.setdefault("stopLossPrice", stop_loss)
        if take_profit is not None and self._supports_attached_protection_prices():
            order_params.setdefault("takeProfitPrice", take_profit)

        if self._exchange_code() == "coinbase" and self._coinbase_is_perpetual_order(symbol, order_params):
            return await self._create_coinbase_perpetual_order(
                symbol=symbol,
                side=side,
                amount=normalized_amount,
                order_type=normalized_type,
                price=normalized_price,
                params=order_params,
            )

        if not self._exchange_has("create_order"):
            raise NotImplementedError(f"{self.exchange_name} does not support create_order")

        try:
            created = await self.exchange.create_order(
                symbol,
                normalized_type,
                str(side).lower(),
                normalized_amount,
                normalized_price,
                order_params,
            )
        except Exception as exc:
            raise self._translate_exchange_exception(exc, "create_order") from exc
        self._invalidate_account_state_cache()
        if isinstance(created, dict) and trigger_price is not None:
            created.setdefault("stop_price", float(trigger_price))
        return created

    async def cancel_order(self, order_id, symbol=None):
        self._invalidate_account_state_cache()
        if symbol is None:
            return await self._call_unified("cancel_order", order_id)
        return await self._call_unified("cancel_order", order_id, symbol)

    async def cancel_all_orders(self, symbol=None):
        self._invalidate_account_state_cache()
        if symbol is None:
            return await self._call_unified("cancel_all_orders", default=[])
        return await self._call_unified("cancel_all_orders", symbol, default=[])

    # ==========================================================
    # ACCOUNT
    # ==========================================================

    async def fetch_balance(self):
        if self._exchange_code() == "coinbase":
            subtype = self._coinbase_derivative_subtype()
            if subtype == "future":
                try:
                    balance_summary = await self._fetch_coinbase_futures_balance_summary()
                    if isinstance(balance_summary, dict) and balance_summary:
                        return balance_summary
                except Exception as exc:
                    self.logger.debug("Unable to load Coinbase futures balance summary: %s", exc)
            elif subtype == "swap":
                try:
                    portfolio_summary = await self._fetch_coinbase_perpetuals_portfolio_summary()
                    if isinstance(portfolio_summary, dict) and portfolio_summary:
                        return portfolio_summary
                except Exception as exc:
                    self.logger.debug("Unable to load Coinbase perpetuals portfolio summary: %s", exc)
        if not self._supports_positions_endpoint():
            try:
                snapshot = await self._get_spot_account_snapshot_cached()
                return snapshot.get("balance")
            except Exception as exc:
                self.logger.debug("Unable to derive spot account valuation on %s: %s", self.exchange_name, exc)
        raw_balance = await self._fetch_raw_balance()
        if not isinstance(raw_balance, dict):
            return raw_balance
        return raw_balance

    async def fetch_positions(self, symbols=None):
        if self._exchange_code() == "coinbase":
            subtype = self._coinbase_derivative_subtype()
            if subtype == "future" and not self._exchange_has("fetchPositions"):
                try:
                    return await self._fetch_coinbase_futures_positions(symbols=symbols)
                except Exception as exc:
                    self.logger.debug("Unable to load Coinbase futures positions via direct API: %s", exc)
            if subtype == "swap":
                try:
                    return await self._fetch_coinbase_perpetuals_positions(symbols=symbols)
                except Exception as exc:
                    self.logger.debug("Unable to load Coinbase perpetual positions via direct API: %s", exc)
        if not self._supports_positions_endpoint():
            try:
                snapshot = await self._get_spot_account_snapshot_cached()
                return [
                    position
                    for position in (snapshot or {}).get("positions", [])
                    if isinstance(position, dict) and self._spot_position_matches_symbols(position, symbols)
                ]
            except Exception as exc:
                self.logger.debug("Unable to derive spot positions on %s: %s", self.exchange_name, exc)
                return []
        return await self._call_unified("fetch_positions", symbols, default=[])

    async def fetch_order(self, order_id, symbol=None):
        if symbol is None:
            return await self._call_unified("fetch_order", order_id)
        return await self._call_unified("fetch_order", order_id, symbol)

    async def fetch_orders(self, symbol=None, limit=None):
        kwargs = {}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._call_unified("fetch_orders", symbol, default=[], **kwargs)

    async def fetch_open_orders(self, symbol=None, limit=None):
        kwargs = {}
        if limit is not None:
            kwargs["limit"] = limit
        target_symbol = self._default_open_orders_symbol(symbol)
        return await self._call_unified("fetch_open_orders", target_symbol, default=[], **kwargs)

    async def fetch_open_orders_snapshot(self, symbols=None, limit=None):
        monitored_symbols = self._monitored_symbols(symbols)
        exchange_code = str(self.exchange_name or "").strip().lower()
        cache_key = ("snapshot", tuple(monitored_symbols), limit)
        now = time.monotonic()

        if exchange_code == "binanceus":
            if len(monitored_symbols) <= 8 and monitored_symbols:
                ttl_seconds = 15.0
                fetcher = lambda: self._fetch_open_orders_by_symbols(monitored_symbols, limit=limit)
            else:
                cache_key = ("snapshot-global", limit)
                ttl_seconds = 310.0
                fetcher = lambda: self._fetch_open_orders_without_symbol(limit=limit)

            cached = self._open_orders_snapshot_cache.get(cache_key)
            if cached and now < cached["expires_at"]:
                return list(cached["orders"])

            orders = self._dedupe_orders_snapshot(await fetcher())
            self._open_orders_snapshot_cache[cache_key] = {
                "orders": list(orders),
                "expires_at": now + ttl_seconds,
            }
            return orders

        if exchange_code == "coinbase":
            cache_key = ("coinbase-snapshot", tuple(monitored_symbols), limit)
            cached = self._open_orders_snapshot_cache.get(cache_key)
            if cached and now < cached["expires_at"]:
                return list(cached["orders"])

            try:
                orders = self._dedupe_orders_snapshot(await self._fetch_open_orders_without_symbol(limit=limit))
            except Exception:
                if monitored_symbols:
                    orders = await self._fetch_open_orders_by_symbols(monitored_symbols, limit=limit)
                else:
                    raise

            self._open_orders_snapshot_cache[cache_key] = {
                "orders": list(orders),
                "expires_at": now + self.COINBASE_OPEN_ORDERS_CACHE_SECONDS,
            }
            return orders

        try:
            return self._dedupe_orders_snapshot(await self._fetch_open_orders_without_symbol(limit=limit))
        except Exception:
            if monitored_symbols:
                return await self._fetch_open_orders_by_symbols(monitored_symbols, limit=limit)
            raise

    async def fetch_closed_orders(self, symbol=None, limit=None):
        kwargs = {}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._call_unified("fetch_closed_orders", symbol, default=[], **kwargs)

    async def withdraw(self, code, amount, address, tag=None, params=None):
        order_params = dict(self.extra_params)
        if params:
            order_params.update(params)
        if tag is not None:
            order_params.setdefault("tag", tag)
        self._invalidate_account_state_cache()
        return await self._call_unified(
            "withdraw",
            code,
            amount,
            address,
            tag,
            order_params,
        )

    async def fetch_deposit_address(self, code, params=None):
        order_params = dict(self.extra_params)
        if params:
            order_params.update(params)
        return await self._call_unified(
            "fetch_deposit_address",
            code,
            order_params,
        )
