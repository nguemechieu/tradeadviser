import asyncio
import json
import logging
import os
import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

import aiohttp

from broker.base_broker import BaseBroker

try:  # pragma: no cover - optional dependency at runtime
    from stellar_sdk import AiohttpClient, Asset, Keypair, Network, ServerAsync, TransactionBuilder
    from stellar_sdk.exceptions import BadRequestError
except Exception:  # pragma: no cover - optional dependency at runtime
    AiohttpClient = None
    Asset = None
    BadRequestError = None
    Keypair = None
    Network = None
    ServerAsync = None
    TransactionBuilder = None


@dataclass
class StellarAssetDescriptor:
    code: str
    issuer: Optional[str] = None

    @property
    def is_native(self) -> bool:
        return self.issuer is None and self.code.upper() == "XLM"

    @property
    def asset_type(self) -> str:
        if self.is_native:
            return "native"
        return "credit_alphanum4" if len(self.code) <= 4 else "credit_alphanum12"

    def to_horizon(self, prefix: str) -> Dict[str, str]:
        if self.is_native:
            return {f"{prefix}_asset_type": "native"}
        return {
            f"{prefix}_asset_type": self.asset_type,
            f"{prefix}_asset_code": self.code,
            f"{prefix}_asset_issuer": self.issuer,
        }

    def to_sdk(self):
        if Asset is None:
            raise RuntimeError("stellar-sdk is required for live Stellar order execution")
        if self.is_native:
            return Asset.native()
        return Asset(self.code, self.issuer)


class StellarBroker(BaseBroker):
    HORIZON_PUBLIC_URL = "https://horizon.stellar.org"
    HORIZON_TESTNET_URL = "https://horizon-testnet.stellar.org"
    BASE_FEE = 100
    RESOLUTION_MAP = {
        "1m": 60000,
        "5m": 300000,
        "15m": 900000,
        "1h": 3600000,
        "4h": 14400000,
        "1d": 86400000,
        "1w": 604800000,
    }
    DEFAULT_QUOTE_PRIORITY = ("USDC", "USDT", "EURC", "XLM")
    DEFAULT_NETWORK_ASSET_LIMIT = 80
    DEFAULT_NETWORK_SYMBOL_LIMIT = 120
    DEFAULT_NETWORK_SCAN_PAGES = 6
    DEFAULT_MIN_NETWORK_ASSET_SCORE = 25.0
    DEFAULT_ACCOUNT_CACHE_TTL = 15.0
    DEFAULT_RATE_LIMIT_RETRIES = 2
    DEFAULT_TRADES_CACHE_TTL = 20.0
    DEFAULT_TRADES_COOLDOWN_SECONDS = 30.0
    DEFAULT_OHLCV_COOLDOWN_SECONDS = 45.0
    HORIZON_MAX_TRADE_AGGREGATION_LIMIT = 200
    VALID_ASSET_CODE_RE = re.compile(r"^[A-Z]{2,12}$")
    VALID_PUBLIC_KEY_RE = re.compile(r"^G[A-Z2-7]{55}$")
    VALID_SECRET_KEY_RE = re.compile(r"^S[A-Z2-7]{55}$")
    BLOCK_REASON_TEXT_MAP = {
        "scam": "Scam",
        "spam": "Scam",
        "fraud": "Scam",
        "phishing": "Scam",
        "malicious": "Scam",
        "fake": "Scam",
        "banned": "Banned",
        "blacklist": "Banned",
        "blacklisted": "Banned",
        "blocked": "Banned",
    }
    BLOCK_REASON_BOOL_FIELDS = {
        "scam": "Scam",
        "is_scam": "Scam",
        "spam": "Scam",
        "is_spam": "Scam",
        "fraud": "Scam",
        "is_fraud": "Scam",
        "phishing": "Scam",
        "is_phishing": "Scam",
        "malicious": "Scam",
        "is_malicious": "Scam",
        "fake": "Scam",
        "is_fake": "Scam",
        "banned": "Banned",
        "is_banned": "Banned",
        "blocked": "Banned",
        "is_blocked": "Banned",
        "blacklisted": "Banned",
        "is_blacklisted": "Banned",
    }

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger("StellarBroker")
        self.config = config
        self.exchange_name = "stellar"
        self.public_key = getattr(config, "api_key", None) or getattr(config, "account_id", None)
        self.secret = getattr(config, "secret", None)
        self.mode = (getattr(config, "mode", "live") or "live").lower()
        self.sandbox = bool(getattr(config, "sandbox", False) or self.mode in {"paper", "sandbox", "testnet"})
        self.params = dict(getattr(config, "params", None) or {})
        self.options = dict(getattr(config, "options", None) or {})
        self.horizon_url = self.params.get(
            "horizon_url",
            self.HORIZON_TESTNET_URL if self.sandbox else self.HORIZON_PUBLIC_URL,
        )
        self.base_fee = int(self.params.get("base_fee", self.BASE_FEE))
        self.default_slippage_pct = float(self.params.get("slippage_pct", 0.02))
        self.account_cache_ttl = float(self.params.get("account_cache_ttl", self.DEFAULT_ACCOUNT_CACHE_TTL))
        self.rate_limit_retries = max(0, int(self.params.get("rate_limit_retries", self.DEFAULT_RATE_LIMIT_RETRIES)))
        self.orderbook_cache_ttl = float(self.params.get("orderbook_cache_ttl", 5.0))
        self.orderbook_cooldown_seconds = float(self.params.get("orderbook_cooldown_seconds", 10.0))
        self.ohlcv_cache_ttl = float(self.params.get("ohlcv_cache_ttl", 60.0))
        self.ohlcv_cooldown_seconds = float(
            self.params.get("ohlcv_cooldown_seconds", self.DEFAULT_OHLCV_COOLDOWN_SECONDS)
        )
        self.trades_cache_ttl = float(self.params.get("trades_cache_ttl", self.DEFAULT_TRADES_CACHE_TTL))
        self.trades_cooldown_seconds = float(
            self.params.get("trades_cooldown_seconds", self.DEFAULT_TRADES_COOLDOWN_SECONDS)
        )
        self.cache_path = Path(self.params.get("cache_path") or self._default_cache_path())
        self.network_passphrase = self.params.get(
            "network_passphrase",
            self._default_network_passphrase(),
        )

        self.session = None
        self._connected = False
        self.asset_registry: Dict[str, StellarAssetDescriptor] = {"XLM": StellarAssetDescriptor("XLM", None)}
        self._network_asset_codes: List[str] = []
        self._account_asset_codes: List[str] = ["XLM"]
        self._blocked_asset_identifiers: Set[str] = set()
        self._blocked_asset_codes: Set[str] = set()
        self._blocked_asset_reasons: Dict[str, str] = {}
        self.market_registry: Dict[str, dict] = {}
        self._cached_account: Optional[dict] = None
        self._cached_account_until = 0.0
        self._orderbook_cache: Dict[str, dict] = {}
        self._orderbook_cache_until: Dict[str, float] = {}
        self._orderbook_cooldown_until: Dict[str, float] = {}
        self._ohlcv_cache: Dict[str, List[List[float]]] = {}
        self._ohlcv_cache_until: Dict[str, float] = {}
        self._ohlcv_cooldown_until: Dict[str, float] = {}
        self._ohlcv_inflight: Dict[str, asyncio.Task] = {}
        self._trades_cache: Dict[str, List[dict]] = {}
        self._trades_cache_until: Dict[str, float] = {}
        self._trades_cooldown_until: Dict[str, float] = {}

        if not self.public_key:
            raise ValueError("Stellar public key is required")
        self.public_key = str(self.public_key).strip()
        if not self._is_valid_public_key(self.public_key):
            raise ValueError(
                "Invalid Stellar public key. It should start with 'G' and be a valid Stellar account address."
            )
        if self.secret is not None:
            self.secret = str(self.secret).strip()
            if self.secret and not self._is_valid_secret_key(self.secret):
                raise ValueError(
                    "Invalid Stellar private key. It should start with 'S' and be a valid Stellar secret seed."
                )

        self._load_config_assets()
        self._load_config_blocked_assets()
        self._load_cached_assets()

    def supported_market_venues(self):
        return ["auto", "spot"]

    def _default_network_passphrase(self) -> str:
        if Network is None:
            return "Test SDF Network ; September 2015" if self.sandbox else "Public Global Stellar Network ; September 2015"
        return (
            Network.TESTNET_NETWORK_PASSPHRASE
            if self.sandbox
            else Network.PUBLIC_NETWORK_PASSPHRASE
        )

    def _default_cache_path(self) -> str:
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            base_dir = Path(local_app_data) / "Sopotek" / "stellar"
        else:
            base_dir = Path.home() / ".tradeadviser" / "stellar"
        cache_name = f"asset_cache_{self.public_key[-12:].lower()}.json"
        return str(base_dir / cache_name)

    def _load_config_assets(self):
        raw_assets = self.params.get("assets") or self.params.get("asset_map") or {}
        parsed_assets = self._parse_assets_input(raw_assets)
        for descriptor in parsed_assets.values():
            self.asset_registry[descriptor.code] = descriptor

    def _load_cached_assets(self):
        try:
            if not self.cache_path.exists():
                return
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return

        for item in payload.get("asset_registry", []):
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").upper().strip()
            issuer = item.get("issuer")
            if not code or not self._is_valid_asset_code(code):
                continue
            self._register_asset_descriptor(StellarAssetDescriptor(code, str(issuer) if issuer else None))

        account_codes = []
        for code in payload.get("account_asset_codes", []):
            upper_code = str(code or "").upper().strip()
            if upper_code and self._is_valid_asset_code(upper_code) and upper_code in self.asset_registry:
                account_codes.append(upper_code)
        if account_codes:
            if "XLM" not in account_codes:
                account_codes.insert(0, "XLM")
            self._account_asset_codes = list(dict.fromkeys(account_codes))

        network_codes = []
        for code in payload.get("network_asset_codes", []):
            upper_code = str(code or "").upper().strip()
            if upper_code and self._is_valid_asset_code(upper_code) and upper_code in self.asset_registry:
                network_codes.append(upper_code)
        if network_codes:
            if "XLM" not in network_codes:
                network_codes.insert(0, "XLM")
            self._network_asset_codes = list(dict.fromkeys(network_codes))

        for item in payload.get("blocked_assets", []):
            if isinstance(item, dict):
                self._register_blocked_asset(
                    item.get("asset") or item.get("code"),
                    issuer=item.get("issuer"),
                    reason=item.get("reason") or "Banned",
                )
                continue
            self._register_blocked_asset(item, reason="Banned")

    def _save_asset_cache(self):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "saved_at": time.time(),
                "network_asset_codes": [code for code in self._network_asset_codes if code in self.asset_registry],
                "account_asset_codes": [code for code in self._account_asset_codes if code in self.asset_registry],
                "blocked_assets": [
                    {
                        "asset": asset_id,
                        "reason": self._blocked_asset_reasons.get(asset_id, "Banned"),
                    }
                    for asset_id in sorted(self._blocked_asset_identifiers)
                ],
                "asset_registry": [
                    {"code": descriptor.code, "issuer": descriptor.issuer}
                    for descriptor in self.asset_registry.values()
                    if self._is_valid_asset_code(descriptor.code)
                ],
            }
            self.cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            return

    def _is_valid_public_key(self, value: Optional[str]) -> bool:
        return bool(self.VALID_PUBLIC_KEY_RE.fullmatch(str(value or "").strip().upper()))

    def _is_valid_secret_key(self, value: Optional[str]) -> bool:
        return bool(self.VALID_SECRET_KEY_RE.fullmatch(str(value or "").strip().upper()))

    def _is_valid_asset_code(self, code: Optional[str]) -> bool:
        normalized = str(code or "").upper().strip()
        if normalized == "XLM":
            return True
        return bool(self.VALID_ASSET_CODE_RE.fullmatch(normalized))

    def _parse_assets_input(self, raw_assets) -> Dict[str, StellarAssetDescriptor]:
        parsed = {}

        if isinstance(raw_assets, dict):
            iterable = []
            for code, value in raw_assets.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("code", code)
                elif value in (None, "", "native"):
                    item = {"code": code}
                else:
                    item = {"code": code, "issuer": value}
                iterable.append(item)
        elif isinstance(raw_assets, list):
            iterable = raw_assets
        else:
            iterable = []

        for item in iterable:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or item.get("asset_code") or "").upper().strip()
            issuer = item.get("issuer") or item.get("asset_issuer")
            if not code or not self._is_valid_asset_code(code):
                continue
            if code == "XLM":
                parsed["XLM"] = StellarAssetDescriptor("XLM", None)
            elif issuer:
                parsed[code] = StellarAssetDescriptor(code, str(issuer))

        return parsed

    def _iter_blocked_asset_inputs(self, raw_assets):
        if raw_assets in (None, "", False):
            return []
        if isinstance(raw_assets, dict):
            entries = []
            for asset, value in raw_assets.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("asset", asset)
                    entries.append(item)
                elif value in (None, "", True):
                    entries.append({"asset": asset})
                else:
                    entries.append({"asset": asset, "reason": value})
            return entries
        if isinstance(raw_assets, (list, tuple, set)):
            return list(raw_assets)
        return [raw_assets]

    def _normalize_block_reason(self, reason) -> str:
        text = str(reason or "").strip()
        lowered = text.lower()
        for marker, label in self.BLOCK_REASON_TEXT_MAP.items():
            if marker in lowered:
                return label
        return text.title() if text else "Banned"

    def _iter_nested_mapping_items(self, value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield str(key or "").strip().lower(), nested
                yield from self._iter_nested_mapping_items(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                yield from self._iter_nested_mapping_items(nested)

    def _iter_nested_text(self, value):
        if isinstance(value, dict):
            for nested in value.values():
                yield from self._iter_nested_text(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                yield from self._iter_nested_text(nested)
        elif value not in (None, ""):
            yield str(value)

    def _load_config_blocked_assets(self):
        for key in ("blocked_assets", "banned_assets", "scam_assets"):
            for entry in self._iter_blocked_asset_inputs(self.params.get(key)):
                if isinstance(entry, dict):
                    self._register_blocked_asset(
                        entry.get("asset") or entry.get("code"),
                        issuer=entry.get("issuer"),
                        reason=entry.get("reason") or key.replace("_assets", ""),
                    )
                else:
                    self._register_blocked_asset(entry, reason=key.replace("_assets", ""))

    def _register_blocked_asset(self, asset, issuer=None, reason="Banned"):
        descriptor = None
        if isinstance(asset, StellarAssetDescriptor):
            descriptor = asset
        elif isinstance(asset, str):
            raw_text = str(asset or "").strip()
            if not raw_text:
                return
            if issuer not in (None, ""):
                descriptor = StellarAssetDescriptor(str(raw_text).upper().strip(), str(issuer).strip())
            elif raw_text.upper() == "XLM":
                return
            elif ":" in raw_text:
                code, parsed_issuer = raw_text.split(":", 1)
                code = str(code or "").upper().strip()
                parsed_issuer = str(parsed_issuer or "").strip()
                if not code or not parsed_issuer or not self._is_valid_asset_code(code):
                    return
                descriptor = StellarAssetDescriptor(code, parsed_issuer)
            else:
                code = str(raw_text or "").upper().strip()
                if not code or not self._is_valid_asset_code(code):
                    return
                descriptor = StellarAssetDescriptor(code, None)
        elif isinstance(asset, dict):
            code = str(asset.get("code") or asset.get("asset_code") or "").upper().strip()
            parsed_issuer = str(asset.get("issuer") or asset.get("asset_issuer") or issuer or "").strip()
            if not code or not self._is_valid_asset_code(code):
                return
            descriptor = StellarAssetDescriptor(code, parsed_issuer or None)
        if descriptor is None or descriptor.code == "XLM":
            return

        identifier = self._asset_identifier(descriptor)
        self._blocked_asset_identifiers.add(identifier)
        self._blocked_asset_reasons[identifier] = self._normalize_block_reason(reason)
        if descriptor.issuer is None:
            self._blocked_asset_codes.add(descriptor.code)

    def block_reason_for_asset(self, asset, issuer=None) -> Optional[str]:
        descriptor = asset if isinstance(asset, StellarAssetDescriptor) else None
        if descriptor is None:
            if issuer not in (None, ""):
                descriptor = StellarAssetDescriptor(str(asset or "").upper().strip(), str(issuer).strip())
            else:
                raw_text = str(asset or "").strip()
                if ":" in raw_text:
                    code, parsed_issuer = raw_text.split(":", 1)
                    descriptor = StellarAssetDescriptor(str(code or "").upper().strip(), str(parsed_issuer or "").strip())
                elif raw_text:
                    descriptor = StellarAssetDescriptor(str(raw_text).upper().strip(), None)
        if descriptor is None or not descriptor.code or descriptor.code == "XLM":
            return None

        identifier = self._asset_identifier(descriptor)
        if identifier in self._blocked_asset_reasons:
            return self._blocked_asset_reasons[identifier]
        if descriptor.code in self._blocked_asset_codes:
            return self._blocked_asset_reasons.get(descriptor.code, "Banned")
        return None

    def is_asset_blocked(self, asset, issuer=None) -> bool:
        return self.block_reason_for_asset(asset, issuer=issuer) is not None

    def _asset_record_block_reason(self, record: dict) -> Optional[str]:
        if not isinstance(record, dict):
            return None

        code = str(record.get("asset_code") or record.get("code") or "").upper().strip()
        issuer = str(record.get("asset_issuer") or record.get("issuer") or "").strip()
        configured_reason = self.block_reason_for_asset(code if not issuer else f"{code}:{issuer}")
        if configured_reason:
            return configured_reason

        for key, value in self._iter_nested_mapping_items(record):
            if key in self.BLOCK_REASON_BOOL_FIELDS and bool(value):
                return self.BLOCK_REASON_BOOL_FIELDS[key]

            if any(token in key for token in ("scam", "ban", "block", "blacklist", "flag", "risk", "warn", "tag", "label", "status", "fraud", "phishing", "spam")):
                for fragment in self._iter_nested_text(value):
                    lowered = str(fragment or "").strip().lower()
                    for marker, label in self.BLOCK_REASON_TEXT_MAP.items():
                        if marker in lowered:
                            return label
        return None

    async def _ensure_connected(self):
        if not self._connected:
            await self.connect()

    async def _request_connected(self, method: str, path: str, params=None, payload=None):
        if self.session is None:
            raise RuntimeError("Stellar broker is not connected")
        url = f"{self.horizon_url}{path}"
        last_error = None
        for attempt in range(self.rate_limit_retries + 1):
            try:
                async with self.session.request(method, url, params=params, json=payload) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientResponseError as exc:
                last_error = exc
                if exc.status != 429 or attempt >= self.rate_limit_retries:
                    raise
                retry_after = 0.0
                if exc.headers:
                    try:
                        retry_after = float(exc.headers.get("Retry-After", 0) or 0)
                    except Exception:
                        retry_after = 0.0
                delay = retry_after if retry_after > 0 else min(1.5 * (attempt + 1), 4.0)
                self.logger.warning(
                    "Stellar Horizon rate limited %s %s; retrying in %.1fs (attempt %s/%s)",
                    method,
                    path,
                    delay,
                    attempt + 1,
                    self.rate_limit_retries + 1,
                )
                await asyncio.sleep(delay)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to request Stellar Horizon path: {path}")

    async def _request(self, method: str, path: str, params=None, payload=None):
        await self._ensure_connected()
        return await self._request_connected(method, path, params=params, payload=payload)

    def _cache_account(self, account: dict, ttl: Optional[float] = None):
        self._cached_account = account
        ttl_value = self.account_cache_ttl if ttl is None else max(0.0, float(ttl))
        self._cached_account_until = time.time() + ttl_value

    def _empty_account(self) -> dict:
        return {"id": self.public_key, "balances": []}

    async def _load_account(self, force=False, allow_stale=True, suppress_rate_limit=False):
        now = time.time()
        if not force and self._cached_account is not None and now < self._cached_account_until:
            return self._cached_account

        try:
            account = await self._request_connected("GET", f"/accounts/{self.public_key}")
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                if allow_stale and self._cached_account is not None:
                    self.logger.warning("Using cached Stellar account snapshot after Horizon rate limit.")
                    return self._cached_account
                if suppress_rate_limit:
                    fallback = self._empty_account()
                    self._cache_account(fallback, ttl=min(self.account_cache_ttl, 5.0))
                    if any(code != "XLM" for code in self._account_asset_codes):
                        self.logger.warning(
                            "Stellar Horizon rate limited account lookup for %s; continuing with cached account asset data.",
                            self.public_key,
                        )
                    else:
                        self.logger.warning(
                            "Stellar Horizon rate limited account lookup for %s; continuing with empty account data.",
                            self.public_key,
                        )
                    return fallback
                raise RuntimeError(
                    "Stellar Horizon is temporarily rate limiting account lookups. Please wait a moment and try again."
                ) from exc
            raise

        self._register_assets_from_account(account)
        self._cache_account(account)
        return account

    def _register_assets_from_account(self, account: dict):
        updated = False
        balances = account.get("balances", []) if isinstance(account, dict) else []
        for balance in balances:
            code = self._asset_code_from_balance(balance)
            issuer = self._asset_issuer_from_balance(balance)
            if code:
                self.asset_registry[code] = StellarAssetDescriptor(code, issuer)
                if code not in self._account_asset_codes:
                    self._account_asset_codes.append(code)
                updated = True
        if updated:
            self._save_asset_cache()

    def _asset_code_from_balance(self, balance: dict) -> Optional[str]:
        asset_type = balance.get("asset_type")
        if asset_type == "native":
            return "XLM"
        code = balance.get("asset_code")
        return str(code).upper() if code else None

    def _asset_issuer_from_balance(self, balance: dict) -> Optional[str]:
        if balance.get("asset_type") == "native":
            return None
        issuer = balance.get("asset_issuer")
        return str(issuer) if issuer else None

    def _symbol_parts(self, symbol: str) -> Tuple[str, str]:
        if not symbol or "/" not in symbol:
            raise ValueError(f"Invalid Stellar symbol: {symbol}")
        base, quote = str(symbol).split("/", 1)
        return base.strip(), quote.strip()

    def _parse_asset_text(self, text: str) -> StellarAssetDescriptor:
        raw = str(text or "").strip()
        if not raw:
            raise ValueError("Asset code is required")

        if raw.upper() == "XLM":
            return StellarAssetDescriptor("XLM", None)

        if ":" in raw:
            code, issuer = raw.split(":", 1)
            code = code.strip().upper()
            issuer = issuer.strip()
            if not code or not issuer or not self._is_valid_asset_code(code):
                raise ValueError(f"Invalid Stellar asset identifier: {raw}")
            descriptor = StellarAssetDescriptor(code, issuer)
            self.asset_registry[descriptor.code] = descriptor
            return descriptor

        if not self._is_valid_asset_code(raw):
            raise ValueError(f"Invalid Stellar asset code: {raw}")

        lookup = self.asset_registry.get(raw.upper())
        if lookup is None:
            raise ValueError(
                f"Unknown Stellar asset '{raw}'. Provide it via broker params['assets'] or use CODE:ISSUER in the symbol."
            )
        return lookup

    def _symbol_from_assets(self, base: StellarAssetDescriptor, quote: StellarAssetDescriptor) -> str:
        return f"{base.code}/{quote.code}"

    def _asset_identifier(self, descriptor: StellarAssetDescriptor) -> str:
        if descriptor.is_native:
            return descriptor.code
        return f"{descriptor.code}:{descriptor.issuer}"

    def _market_payload(self, base: StellarAssetDescriptor, quote: StellarAssetDescriptor) -> dict:
        symbol = self._symbol_from_assets(base, quote)
        return {
            "id": symbol,
            "symbol": symbol,
            "base": base.code,
            "quote": quote.code,
            "base_asset_code": base.code,
            "base_asset_type": base.asset_type,
            "base_asset_issuer": base.issuer,
            "quote_asset_code": quote.code,
            "quote_asset_type": quote.asset_type,
            "quote_asset_issuer": quote.issuer,
            "active": True,
            "spot": True,
        }

    def _market_assets_for_symbol(self, symbol: str) -> Optional[Tuple[StellarAssetDescriptor, StellarAssetDescriptor]]:
        market = self.market_registry.get(str(symbol or ""))
        if not isinstance(market, dict):
            return None

        base_code = market.get("base_asset_code") or market.get("base")
        quote_code = market.get("quote_asset_code") or market.get("quote")
        if not base_code or not quote_code:
            return None

        return (
            StellarAssetDescriptor(str(base_code).upper(), market.get("base_asset_issuer")),
            StellarAssetDescriptor(str(quote_code).upper(), market.get("quote_asset_issuer")),
        )

    def _resolve_symbol_assets(self, symbol: str) -> Tuple[StellarAssetDescriptor, StellarAssetDescriptor]:
        market_assets = self._market_assets_for_symbol(symbol)
        if market_assets is not None:
            return market_assets
        base_text, quote_text = self._symbol_parts(symbol)
        return self._parse_asset_text(base_text), self._parse_asset_text(quote_text)

    def _build_tradable_symbols(self) -> List[str]:
        explicit_symbols = self.params.get("symbols")
        if isinstance(explicit_symbols, list) and explicit_symbols:
            filtered_symbols = []
            for symbol in explicit_symbols:
                normalized_symbol = str(symbol or "").strip()
                if not normalized_symbol:
                    continue
                try:
                    base_asset, quote_asset = self._resolve_symbol_assets(normalized_symbol)
                except Exception:
                    filtered_symbols.append(normalized_symbol)
                    continue
                if self.is_asset_blocked(base_asset) or self.is_asset_blocked(quote_asset):
                    continue
                filtered_symbols.append(normalized_symbol)
            return filtered_symbols

        raw_codes = [
            code
            for code in (self._network_asset_codes or self.asset_registry.keys())
            if self._is_valid_asset_code(code)
        ]
        codes = []
        for code in list(self._account_asset_codes) + list(raw_codes):
            upper_code = str(code).upper()
            if upper_code not in codes and upper_code in self.asset_registry:
                codes.append(upper_code)
        descriptors = [self.asset_registry.get(code) for code in codes]
        descriptors = [descriptor for descriptor in descriptors if descriptor is not None]
        quote_assets = [
            str(code).upper()
            for code in (self.params.get("quote_assets") or self.DEFAULT_QUOTE_PRIORITY)
            if self._is_valid_asset_code(code) and str(code).upper() in codes
        ]

        if not quote_assets:
            quote_assets = codes[:]

        symbols = []
        seen_pairs = set()
        self.market_registry = {}
        for quote in quote_assets:
            quote_descriptor = self.asset_registry.get(quote)
            if quote_descriptor is None or self.is_asset_blocked(quote_descriptor):
                continue
            for base_descriptor in descriptors:
                if base_descriptor.code == quote or self.is_asset_blocked(base_descriptor):
                    continue
                pair_key = tuple(sorted((base_descriptor.code, quote)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                symbol = self._symbol_from_assets(base_descriptor, quote_descriptor)
                self.market_registry[symbol] = self._market_payload(base_descriptor, quote_descriptor)
                symbols.append(symbol)

        unique_symbols = []
        seen = set()
        for symbol in symbols:
            if symbol not in seen:
                seen.add(symbol)
                unique_symbols.append(symbol)
        max_symbols = int(self.params.get("symbol_limit", self.DEFAULT_NETWORK_SYMBOL_LIMIT))
        return unique_symbols[:max_symbols]

    def _register_asset_descriptor(self, descriptor: StellarAssetDescriptor):
        existing = self.asset_registry.get(descriptor.code)
        if existing is None or (existing.issuer is None and descriptor.issuer is not None):
            self.asset_registry[descriptor.code] = descriptor

    def _score_asset_record(self, record: dict) -> float:
        accounts = record.get("accounts") if isinstance(record, dict) else {}
        metrics = [
            record.get("num_accounts"),
            accounts.get("authorized"),
            accounts.get("authorized_to_maintain_liabilities"),
            record.get("num_claimable_balances"),
        ]

        score = 0.0
        for value in metrics:
            try:
                score += float(value or 0)
            except Exception:
                continue
        return score

    def _extract_next_cursor(self, payload: dict) -> Optional[str]:
        next_href = (((payload or {}).get("_links") or {}).get("next") or {}).get("href")
        if not next_href:
            return None
        try:
            parsed = urlparse(str(next_href))
            query = parse_qs(parsed.query)
            cursor = query.get("cursor", [None])[0]
            return str(cursor) if cursor else None
        except Exception:
            return None

    def _asset_record_is_discoverable(self, record: dict) -> bool:
        if not isinstance(record, dict):
            return False

        code = str(record.get("asset_code") or "").upper().strip()
        issuer = str(record.get("asset_issuer") or "").strip()
        if not code or not issuer or not self._is_valid_asset_code(code):
            return False
        block_reason = self._asset_record_block_reason(record)
        if block_reason:
            self._register_blocked_asset(f"{code}:{issuer}", reason=block_reason)
            return False

        score = self._score_asset_record(record)
        min_score = float(self.params.get("min_network_asset_score", self.DEFAULT_MIN_NETWORK_ASSET_SCORE))
        if score < min_score:
            return False

        try:
            authorized_balance = float((((record.get("balances") or {}).get("authorized")) or 0) or 0)
        except Exception:
            authorized_balance = 0.0
        try:
            liquidity_amount = float(record.get("liquidity_pools_amount") or 0)
        except Exception:
            liquidity_amount = 0.0

        if "balances" in record or "liquidity_pools_amount" in record:
            return authorized_balance > 0 or liquidity_amount > 0
        return True

    async def _discover_network_assets(self):
        limit = int(self.params.get("asset_limit", self.DEFAULT_NETWORK_ASSET_LIMIT))
        ranked_records = []
        cursor = None
        scan_pages = max(1, int(self.params.get("asset_scan_pages", self.DEFAULT_NETWORK_SCAN_PAGES)))
        page_limit = max(10, min(limit, 200))

        for _page in range(scan_pages):
            params = {"limit": page_limit, "order": "desc"}
            if cursor:
                params["cursor"] = cursor

            payload = await self._request_connected("GET", "/assets", params=params)
            records = ((payload or {}).get("_embedded") or {}).get("records") or []
            if not isinstance(records, list) or not records:
                break

            for record in records:
                if not self._asset_record_is_discoverable(record):
                    continue
                code = str(record.get("asset_code") or "").upper().strip()
                issuer = str(record.get("asset_issuer") or "").strip()
                descriptor = StellarAssetDescriptor(code, issuer)
                self._register_asset_descriptor(descriptor)
                ranked_records.append((descriptor.code, self._score_asset_record(record)))

            unique_ranked = {code for code, _score in ranked_records}
            if len(unique_ranked) >= limit:
                break

            next_cursor = self._extract_next_cursor(payload)
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        ranked_records.sort(key=lambda item: (-item[1], item[0]))
        ranked_codes = ["XLM"]
        for code, _score in ranked_records:
            if code not in ranked_codes:
                ranked_codes.append(code)

        merged_codes = list(ranked_codes)
        for code in self.asset_registry.keys():
            upper_code = str(code).upper()
            if upper_code not in merged_codes:
                merged_codes.append(upper_code)

        if merged_codes:
            self._network_asset_codes = merged_codes
            self._save_asset_cache()

    async def fetch_asset_directory_page(self, cursor=None, limit=60):
        await self._ensure_connected()
        page_limit = max(10, min(int(limit or 60), 200))
        params = {"limit": page_limit, "order": "desc"}
        if cursor not in (None, ""):
            params["cursor"] = str(cursor)

        payload = await self._request_connected("GET", "/assets", params=params)
        records = ((payload or {}).get("_embedded") or {}).get("records") or []
        rows = []

        for record in records:
            if not isinstance(record, dict):
                continue
            code = str(record.get("asset_code") or "").upper().strip()
            issuer = str(record.get("asset_issuer") or "").strip()
            if not code or not issuer or not self._is_valid_asset_code(code):
                continue
            block_reason = self._asset_record_block_reason(record)
            if block_reason:
                self._register_blocked_asset(f"{code}:{issuer}", reason=block_reason)
                continue

            descriptor = StellarAssetDescriptor(code, issuer)
            self._register_asset_descriptor(descriptor)
            screened = self._asset_record_is_discoverable(record)
            trusted = self._has_trustline(descriptor)
            rows.append(
                {
                    "id": self._asset_identifier(descriptor),
                    "code": descriptor.code,
                    "issuer": descriptor.issuer,
                    "source": "Directory",
                    "url": f"https://stellar.expert/explorer/public/asset/{descriptor.code}-{descriptor.issuer}",
                    "screened": screened,
                    "trusted": trusted,
                    "needs_trustline": not trusted,
                    "risk_label": "Screened" if screened else "Unscreened",
                    "score": self._score_asset_record(record),
                    "roi_pct": None,
                    "roi_symbol": "",
                }
            )

        rows.sort(
            key=lambda item: (
                0 if bool(item.get("screened")) else 1,
                0 if bool(item.get("trusted")) else 1,
                -self._float(item.get("score"), 0.0),
                str(item.get("code") or ""),
                str(item.get("issuer") or ""),
            )
        )
        self._save_asset_cache()
        return {
            "rows": rows,
            "cursor": str(cursor or ""),
            "next_cursor": self._extract_next_cursor(payload),
        }

    async def estimate_asset_roi(self, asset, timeframe="1h", limit=48):
        descriptor = asset if isinstance(asset, StellarAssetDescriptor) else self._parse_asset_text(str(asset or "").strip())
        if descriptor.is_native:
            return None

        quote_codes = []
        for code in list(self.params.get("quote_assets") or self.DEFAULT_QUOTE_PRIORITY) + ["XLM"]:
            normalized_code = str(code or "").upper().strip()
            if not normalized_code or normalized_code == descriptor.code or normalized_code in quote_codes:
                continue
            quote_codes.append(normalized_code)

        best_snapshot = None
        for quote_code in quote_codes:
            if quote_code == "XLM":
                quote_descriptor = StellarAssetDescriptor("XLM", None)
            else:
                quote_descriptor = self.asset_registry.get(quote_code)
                if quote_descriptor is None:
                    continue

            symbol = f"{self._asset_identifier(descriptor)}/{self._asset_identifier(quote_descriptor)}"
            try:
                candles = await self.fetch_ohlcv(symbol, timeframe=timeframe, limit=max(int(limit or 0), 2))
            except Exception:
                continue
            if not candles:
                continue

            opening_price = self._float(candles[0][1], 0.0)
            closing_price = self._float(candles[-1][4], 0.0)
            if opening_price <= 0 or closing_price <= 0:
                continue

            roi_pct = ((closing_price - opening_price) / opening_price) * 100.0
            snapshot = {
                "asset": self._asset_identifier(descriptor),
                "symbol": symbol,
                "quote": quote_descriptor.code,
                "timeframe": str(timeframe or "1h"),
                "bars": len(candles),
                "start_price": opening_price,
                "end_price": closing_price,
                "roi_pct": roi_pct,
            }
            if best_snapshot is None or roi_pct > float(best_snapshot.get("roi_pct") or 0.0):
                best_snapshot = snapshot

        return best_snapshot

    def _float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _ohlcv_cache_key(self, symbol: str, timeframe: str) -> str:
        return f"{str(symbol or '').upper()}|{str(timeframe or '1h').lower()}"

    def _ohlcv_request_key(self, symbol: str, timeframe: str, limit: int) -> str:
        normalized_limit = max(int(limit or 0), 1)
        return f"{self._ohlcv_cache_key(symbol, timeframe)}|{normalized_limit}"

    def _trades_cache_key(self, symbol: str, limit: Optional[int]) -> str:
        normalized_limit = int(limit) if limit else 0
        return f"{str(symbol or '').upper()}|{normalized_limit}"

    def _trade_aggregations_params(
        self,
        base_asset: StellarAssetDescriptor,
        quote_asset: StellarAssetDescriptor,
        resolution: int,
        start_time: int,
        end_time: int,
        limit: int,
        use_snake_case: bool,
    ) -> dict:
        params = {}
        params.update(base_asset.to_horizon("base"))
        params.update(quote_asset.to_horizon("counter"))
        params["resolution"] = resolution
        params["order"] = "asc"
        params["limit"] = limit
        if use_snake_case:
            params["start_time"] = start_time
            params["end_time"] = end_time
        else:
            params["startTime"] = start_time
            params["endTime"] = end_time
        return params

    async def _fetch_trade_aggregation_records(
        self,
        base_asset: StellarAssetDescriptor,
        quote_asset: StellarAssetDescriptor,
        resolution: int,
        start_time: int,
        end_time: int,
        requested_limit: int,
    ) -> Tuple[List[dict], Optional[aiohttp.ClientResponseError]]:
        max_limit = self.HORIZON_MAX_TRADE_AGGREGATION_LIMIT
        chunk_span = max_limit * resolution
        chunk_start = start_time
        records: List[dict] = []
        last_rate_limit_error = None

        while chunk_start < end_time:
            chunk_end = min(end_time, chunk_start + chunk_span)
            chunk_limit = max(1, min((chunk_end - chunk_start) // resolution, max_limit))
            if chunk_limit <= 0:
                break

            for use_snake_case in (False, True):
                params = self._trade_aggregations_params(
                    base_asset=base_asset,
                    quote_asset=quote_asset,
                    resolution=resolution,
                    start_time=chunk_start,
                    end_time=chunk_end,
                    limit=chunk_limit,
                    use_snake_case=use_snake_case,
                )
                try:
                    payload = await self._request("GET", "/trade_aggregations", params=params)
                except aiohttp.ClientResponseError as exc:
                    if exc.status == 429:
                        last_rate_limit_error = exc
                        return records, last_rate_limit_error
                    if use_snake_case:
                        raise
                    continue

                current_records = ((payload.get("_embedded") or {}).get("records")) or payload.get("records") or []
                records.extend(current_records)
                break

            chunk_start = chunk_end

        return records, last_rate_limit_error

    def _parse_timestamp_ms(self, value) -> int:
        if value in (None, ""):
            return 0
        if isinstance(value, (int, float)):
            numeric = int(value)
            if numeric <= 0:
                return 0
            return numeric if numeric >= 10**11 else numeric * 1000
        text = str(value).strip()
        if not text:
            return 0
        if text.isdigit():
            numeric = int(text)
            return numeric if numeric >= 10**11 else numeric * 1000
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            return 0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    def _trade_price(self, trade: dict) -> float:
        price = trade.get("price")
        if isinstance(price, dict):
            numerator = self._float(price.get("n"), 0.0)
            denominator = self._float(price.get("d"), 1.0)
            if denominator:
                return numerator / denominator
        return self._float(
            price
            or trade.get("price_r")
            or trade.get("close")
            or trade.get("avg")
            or 0.0,
            0.0,
        )

    def _trade_timestamp(self, trade: dict) -> int:
        for key in (
            "timestamp",
            "ledger_close_timestamp",
            "ledger_close_time",
            "closed_at",
            "created_at",
        ):
            parsed = self._parse_timestamp_ms(trade.get(key))
            if parsed > 0:
                return parsed
        return 0

    def _aggregate_trades_to_candles(self, trades: List[dict], resolution: int, end_time: int, limit: int) -> List[List[float]]:
        if not trades:
            return []
        buckets: Dict[int, List[float]] = {}
        ordered_trades = sorted(trades, key=self._trade_timestamp)
        for trade in ordered_trades:
            timestamp = self._trade_timestamp(trade)
            if timestamp <= 0:
                continue
            bucket = (timestamp // resolution) * resolution
            price = self._trade_price(trade)
            if price <= 0:
                continue
            volume = self._float(trade.get("base_amount") or trade.get("base_volume") or trade.get("amount"), 0.0)
            candle = buckets.get(bucket)
            if candle is None:
                buckets[bucket] = [bucket, price, price, price, price, volume]
                continue
            candle[2] = max(candle[2], price)
            candle[3] = min(candle[3], price)
            candle[4] = price
            candle[5] += volume
        return [buckets[key] for key in sorted(buckets.keys())][-limit:]

    def _records_to_candles(self, records: List[dict], limit: int) -> List[List[float]]:
        candles_by_timestamp: Dict[int, List[float]] = {}
        for record in records:
            timestamp = self._parse_timestamp_ms(record.get("timestamp"))
            if timestamp <= 0:
                continue
            candles_by_timestamp[timestamp] = [
                timestamp,
                self._float(record.get("open"), 0.0),
                self._float(record.get("high"), 0.0),
                self._float(record.get("low"), 0.0),
                self._float(record.get("close"), 0.0),
                self._float(record.get("base_volume"), 0.0),
            ]
        return [candles_by_timestamp[key] for key in sorted(candles_by_timestamp.keys())][-limit:]

    def _horizon_price(self, payload: dict) -> float:
        price = payload.get("price")
        if isinstance(price, dict):
            n = self._float(price.get("n"), 0.0)
            d = self._float(price.get("d"), 0.0)
            return n / d if d else 0.0
        if price is not None:
            return self._float(price, 0.0)

        base_amount = self._float(payload.get("base_amount"), 0.0)
        counter_amount = self._float(payload.get("counter_amount"), 0.0)
        if base_amount > 0:
            return counter_amount / base_amount
        return 0.0

    def _last_trade_price(self, symbol: str) -> float:
        for cache_limit in (1, 0):
            cached_trades = self._trades_cache.get(self._trades_cache_key(symbol, cache_limit)) or []
            if cached_trades:
                price = self._horizon_price(cached_trades[0])
                if price > 0:
                    return price
        return 0.0

    async def _reference_price(self, symbol: str) -> Tuple[float, float, float]:
        book = await self.fetch_orderbook(symbol, limit=1)
        bid = book["bids"][0][0] if book["bids"] else 0.0
        ask = book["asks"][0][0] if book["asks"] else 0.0
        last = self._last_trade_price(symbol)
        if last <= 0:
            if bid and ask:
                last = (bid + ask) / 2
            else:
                last = ask or bid
        return bid, ask, last

    def _normalize_offer(self, offer: dict) -> dict:
        selling = offer.get("selling", {}) if isinstance(offer, dict) else {}
        buying = offer.get("buying", {}) if isinstance(offer, dict) else {}
        selling_code = "XLM" if selling.get("asset_type") == "native" else str(selling.get("asset_code") or "").upper()
        buying_code = "XLM" if buying.get("asset_type") == "native" else str(buying.get("asset_code") or "").upper()
        raw_price = self._float(offer.get("price"), 0.0)
        raw_amount = self._float(offer.get("amount"), 0.0)
        quote_priority = {str(code).upper() for code in (self.params.get("quote_assets") or self.DEFAULT_QUOTE_PRIORITY)}

        side = "sell"
        symbol = f"{selling_code}/{buying_code}" if selling_code and buying_code else ""
        amount = raw_amount
        standard_price = raw_price

        if selling_code in quote_priority and buying_code and (buying_code not in quote_priority or buying_code == "XLM"):
            side = "buy"
            symbol = f"{buying_code}/{selling_code}"
            amount = raw_amount / raw_price if raw_price else 0.0
            standard_price = raw_price
        elif buying_code in quote_priority and selling_code:
            side = "sell"
            symbol = f"{selling_code}/{buying_code}"
            standard_price = (1.0 / raw_price) if raw_price else 0.0

        return {
            "id": str(offer.get("id")),
            "symbol": symbol,
            "side": side,
            "type": "limit",
            "status": "open",
            "amount": amount,
            "price": standard_price,
            "raw": offer,
        }

    async def _submit_transaction(self, build_transaction):
        if ServerAsync is None or TransactionBuilder is None or Keypair is None:
            raise RuntimeError(
                "stellar-sdk[aiohttp] is required for Stellar order execution. "
                "Install the dependency from requirements.txt."
            )
        if not self.secret:
            raise ValueError("Stellar secret seed is required for order execution")

        async with ServerAsync(horizon_url=self.horizon_url, client=AiohttpClient()) as server:
            source_account = await server.load_account(self.public_key)
            builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=self.base_fee,
            )
            build_transaction(builder)
            transaction = builder.set_timeout(30).build()
            transaction.sign(Keypair.from_secret(self.secret))
            return await server.submit_transaction(transaction)

    async def connect(self):
        if self._connected:
            return True

        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(
            resolver=resolver,
            family=socket.AF_INET,
            ttl_dns_cache=300,
        )
        timeout = aiohttp.ClientTimeout(total=45)
        try:
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        except TypeError:
            await connector.close()
            self.session = aiohttp.ClientSession()

        try:
            await self._load_account(suppress_rate_limit=True)
            self._connected = True
            self.logger.info("Connected to Stellar Horizon (%s)", self.horizon_url)
            return True
        except Exception:
            await self.close()
            raise

    async def close(self):
        if self.session is not None:
            await self.session.close()
        self.session = None
        self._connected = False

    async def fetch_symbol(self):
        await self._ensure_connected()
        explicit_symbols = self.params.get("symbols")
        if isinstance(explicit_symbols, list) and explicit_symbols:
            return [str(symbol) for symbol in explicit_symbols if symbol]

        if not self._network_asset_codes:
            try:
                await self._discover_network_assets()
            except Exception as exc:
                self.logger.warning("Stellar network symbol discovery failed: %s", exc)

        if not any(code != "XLM" for code in self.asset_registry):
            await self._load_account(suppress_rate_limit=True)
        return self._build_tradable_symbols()

    async def fetch_symbols(self):
        return await self.fetch_symbol()

    async def fetch_markets(self):
        symbols = await self.fetch_symbols()
        return {
            symbol: dict(self.market_registry.get(symbol) or {"symbol": symbol, "active": True, "spot": True})
            for symbol in symbols
        }

    async def fetch_status(self):
        try:
            await self._request("GET", "/")
            return {"status": "ok", "broker": "stellar", "horizon_url": self.horizon_url}
        except Exception as exc:
            return {"status": "error", "broker": "stellar", "detail": str(exc)}

    async def fetch_ticker(self, symbol):
        bid, ask, last = await self._reference_price(symbol)

        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "last": last,
        }

    async def fetch_orderbook(self, symbol, limit=20):
        now = time.time()
        cached_until = self._orderbook_cache_until.get(symbol, 0.0)
        cooldown_until = self._orderbook_cooldown_until.get(symbol, 0.0)
        cached_book = self._orderbook_cache.get(symbol)
        if cached_book is not None and (now < cached_until or now < cooldown_until):
            return cached_book

        base_asset, quote_asset = self._resolve_symbol_assets(symbol)
        params = {}
        params.update(base_asset.to_horizon("selling"))
        params.update(quote_asset.to_horizon("buying"))
        params["limit"] = limit

        try:
            payload = await self._request("GET", "/order_book", params=params)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                self._orderbook_cooldown_until[symbol] = time.time() + self.orderbook_cooldown_seconds
                if cached_book is not None:
                    self.logger.warning(
                        "Using cached Stellar orderbook for %s after Horizon rate limit.",
                        symbol,
                    )
                    return cached_book
                return {"symbol": symbol, "bids": [], "asks": []}
            if exc.status == 400:
                self._orderbook_cooldown_until[symbol] = time.time() + max(self.orderbook_cooldown_seconds, 60.0)
                return cached_book or {"symbol": symbol, "bids": [], "asks": []}
            raise
        bids = [
            [self._float(level.get("price"), 0.0), self._float(level.get("amount"), 0.0)]
            for level in payload.get("bids", [])[:limit]
        ]
        asks = [
            [self._float(level.get("price"), 0.0), self._float(level.get("amount"), 0.0)]
            for level in payload.get("asks", [])[:limit]
        ]
        book = {"symbol": self._symbol_from_assets(base_asset, quote_asset), "bids": bids, "asks": asks}
        self._orderbook_cache[symbol] = book
        self._orderbook_cache_until[symbol] = time.time() + self.orderbook_cache_ttl
        self._orderbook_cooldown_until.pop(symbol, None)
        return book

    async def fetch_trades(self, symbol, limit=None):
        cache_key = self._trades_cache_key(symbol, limit)
        now = time.time()
        cached_trades = self._trades_cache.get(cache_key)
        cached_until = self._trades_cache_until.get(cache_key, 0.0)
        cooldown_until = self._trades_cooldown_until.get(cache_key, 0.0)
        if cached_trades is not None and (now < cached_until or now < cooldown_until):
            return cached_trades[:limit] if limit else cached_trades

        base_asset, quote_asset = self._resolve_symbol_assets(symbol)
        params = {}
        params.update(base_asset.to_horizon("base"))
        params.update(quote_asset.to_horizon("counter"))
        params["order"] = "desc"
        if limit is not None:
            params["limit"] = limit

        try:
            payload = await self._request("GET", "/trades", params=params)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                self._trades_cooldown_until[cache_key] = time.time() + self.trades_cooldown_seconds
                if cached_trades is not None:
                    return cached_trades[:limit] if limit else cached_trades
                return []
            if exc.status == 400:
                self._trades_cooldown_until[cache_key] = time.time() + max(self.trades_cooldown_seconds, 120.0)
                return cached_trades[:limit] if cached_trades is not None and limit else (cached_trades or [])
            raise
        records = ((payload.get("_embedded") or {}).get("records")) or payload.get("records") or []
        records = records[:limit] if limit else records
        self._trades_cache[cache_key] = list(records)
        self._trades_cache_until[cache_key] = time.time() + self.trades_cache_ttl
        self._trades_cooldown_until.pop(cache_key, None)
        return records

    async def fetch_my_trades(self, symbol=None, limit=None):
        payload = await self._request("GET", f"/accounts/{self.public_key}/trades", params={"order": "desc", "limit": limit or 50})
        records = ((payload.get("_embedded") or {}).get("records")) or payload.get("records") or []
        if symbol is None:
            return records[:limit] if limit else records

        base_asset, quote_asset = self._resolve_symbol_assets(symbol)
        filtered = []
        for record in records:
            base_code = "XLM" if record.get("base_asset_type") == "native" else str(record.get("base_asset_code") or "").upper()
            counter_code = "XLM" if record.get("counter_asset_type") == "native" else str(record.get("counter_asset_code") or "").upper()
            if base_code == base_asset.code and counter_code == quote_asset.code:
                filtered.append(record)
        return filtered[:limit] if limit else filtered

    async def _fetch_ohlcv_uncached(self, symbol, normalized_timeframe, requested_limit, cache_key, cached_candles):
        base_asset, quote_asset = self._resolve_symbol_assets(symbol)
        resolution = self.RESOLUTION_MAP.get(normalized_timeframe, 3600000)
        now_ms = int(time.time() * 1000)
        end_time = max((now_ms // resolution) * resolution, resolution)
        start_time = end_time - (resolution * max(requested_limit + 2, 4))

        records, last_rate_limit_error = await self._fetch_trade_aggregation_records(
            base_asset=base_asset,
            quote_asset=quote_asset,
            resolution=resolution,
            start_time=start_time,
            end_time=end_time,
            requested_limit=requested_limit,
        )

        candles = self._records_to_candles(records, requested_limit)
        if not candles:
            try:
                trades = await self.fetch_trades(symbol, limit=min(max(requested_limit * 20, 120), 600))
            except aiohttp.ClientResponseError as exc:
                if exc.status == 429:
                    self._ohlcv_cooldown_until[cache_key] = time.time() + self.ohlcv_cooldown_seconds
                    if cached_candles:
                        self.logger.warning("Using cached Stellar OHLCV for %s after Horizon rate limit.", symbol)
                        return cached_candles
                    self.logger.warning(
                        "Stellar Horizon rate limited OHLCV for %s; using an empty candle set during cooldown.",
                        symbol,
                    )
                    return []
                raise
            candles = self._aggregate_trades_to_candles(trades, resolution, end_time, requested_limit)

        if candles:
            self._ohlcv_cache[cache_key] = candles
            self._ohlcv_cache_until[cache_key] = time.time() + self.ohlcv_cache_ttl
            self._ohlcv_cooldown_until.pop(cache_key, None)
            return candles

        if cached_candles:
            return cached_candles
        if last_rate_limit_error is not None:
            self._ohlcv_cooldown_until[cache_key] = time.time() + self.ohlcv_cooldown_seconds
            self.logger.warning(
                "Stellar Horizon rate limited OHLCV for %s; using an empty candle set during cooldown.",
                symbol,
            )
            return []
        return []

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        normalized_timeframe = str(timeframe or "1h").lower()
        cache_key = self._ohlcv_cache_key(symbol, normalized_timeframe)
        cached_candles = self._ohlcv_cache.get(cache_key)
        if cached_candles and time.time() < self._ohlcv_cache_until.get(cache_key, 0.0):
            return cached_candles[-limit:]

        if time.time() < self._ohlcv_cooldown_until.get(cache_key, 0.0):
            return cached_candles[-limit:] if cached_candles else []

        requested_limit = max(int(limit or 0), 1)
        request_key = self._ohlcv_request_key(symbol, normalized_timeframe, requested_limit)
        inflight = self._ohlcv_inflight.get(request_key)
        if inflight is not None:
            candles = await inflight
            return candles[-limit:] if candles else []

        task = asyncio.create_task(
            self._fetch_ohlcv_uncached(
                symbol,
                normalized_timeframe,
                requested_limit,
                cache_key,
                cached_candles,
            )
        )
        self._ohlcv_inflight[request_key] = task
        try:
            candles = await task
        finally:
            self._ohlcv_inflight.pop(request_key, None)
        return candles[-limit:] if candles else []

    async def fetch_balance(self):
        account = await self._load_account(suppress_rate_limit=True)

        free = {}
        used = {}
        total = {}

        for balance in account.get("balances", []):
            code = self._asset_code_from_balance(balance)
            if not code:
                continue

            total_value = self._float(balance.get("balance"), 0.0)
            locked_value = self._float(balance.get("selling_liabilities"), 0.0)
            free_value = max(total_value - locked_value, 0.0)

            free[code] = free_value
            used[code] = locked_value
            total[code] = total_value

        return {
            "free": free,
            "used": used,
            "total": total,
            "raw": account,
        }

    def _format_balance_amount(self, value: float) -> str:
        return f"{float(value):.7f}"

    async def _validate_order_funding(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        base_asset: StellarAssetDescriptor,
        quote_asset: StellarAssetDescriptor,
    ) -> Dict[str, float]:
        balance_snapshot = await self.fetch_balance()
        free_balances = dict(balance_snapshot.get("free") or {})
        normalized_side = str(side or "").strip().lower()

        if normalized_side == "buy":
            required_amount = max(float(amount), 0.0) * max(float(price), 0.0)
            available_amount = self._float(free_balances.get(quote_asset.code), -1.0)
            if available_amount >= 0 and required_amount > (available_amount + 1e-7):
                reserve_note = ""
                if quote_asset.is_native:
                    reserve_note = " XLM must also remain available for Stellar account reserves and fees."
                raise ValueError(
                    f"Insufficient {quote_asset.code} balance to buy {self._format_balance_amount(amount)} "
                    f"{base_asset.code} on {symbol}. Need about {self._format_balance_amount(required_amount)} "
                    f"{quote_asset.code}, available {self._format_balance_amount(available_amount)}.{reserve_note}"
                )
            return {quote_asset.code: max(available_amount, 0.0)}

        required_amount = max(float(amount), 0.0)
        available_amount = self._float(free_balances.get(base_asset.code), -1.0)
        if available_amount >= 0 and required_amount > (available_amount + 1e-7):
            reserve_note = ""
            if base_asset.is_native:
                reserve_note = " XLM must also remain available for Stellar account reserves and fees."
            raise ValueError(
                f"Insufficient {base_asset.code} balance to sell {self._format_balance_amount(amount)} "
                f"on {symbol}. Available {self._format_balance_amount(available_amount)}.{reserve_note}"
            )
        return {base_asset.code: max(available_amount, 0.0)}

    def _translate_order_submission_error(
        self,
        exc: Exception,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        base_asset: StellarAssetDescriptor,
        quote_asset: StellarAssetDescriptor,
        available_balances: Optional[Dict[str, float]] = None,
    ) -> Exception:
        if BadRequestError is None or not isinstance(exc, BadRequestError):
            return exc

        extras = getattr(exc, "extras", None) or {}
        result_codes = extras.get("result_codes") or {}
        transaction_code = str(result_codes.get("transaction") or "").strip()
        operation_codes = result_codes.get("operations") or []
        detail = str(getattr(exc, "detail", None) or "The order was rejected by the Stellar network.")
        normalized_side = str(side or "").strip().lower()
        available_balances = dict(available_balances or {})

        if transaction_code == "tx_insufficient_balance":
            if normalized_side == "buy":
                required_amount = max(float(amount), 0.0) * max(float(price), 0.0)
                asset_code = quote_asset.code
                available_amount = self._float(available_balances.get(asset_code), 0.0)
                reserve_note = " XLM must also remain available for Stellar account reserves and fees." if quote_asset.is_native else ""
                return ValueError(
                    f"Stellar rejected the buy order for {symbol}: insufficient spendable {asset_code}. "
                    f"Need about {self._format_balance_amount(required_amount)} {asset_code}, "
                    f"available {self._format_balance_amount(available_amount)}.{reserve_note}"
                )

            asset_code = base_asset.code
            available_amount = self._float(available_balances.get(asset_code), 0.0)
            reserve_note = " XLM must also remain available for Stellar account reserves and fees." if base_asset.is_native else ""
            return ValueError(
                f"Stellar rejected the sell order for {symbol}: insufficient spendable {asset_code}. "
                f"Requested {self._format_balance_amount(amount)} {asset_code}, "
                f"available {self._format_balance_amount(available_amount)}.{reserve_note}"
            )

        code_suffix = transaction_code or ", ".join(str(code) for code in operation_codes if code)
        if code_suffix:
            return ValueError(f"Stellar rejected the order for {symbol} ({code_suffix}): {detail}")
        return ValueError(f"Stellar rejected the order for {symbol}: {detail}")

    async def fetch_positions(self, symbols=None):
        return []

    def _has_trustline(self, descriptor: StellarAssetDescriptor) -> bool:
        if descriptor.is_native:
            return True
        if descriptor.code not in self._account_asset_codes:
            return False
        known_descriptor = self.asset_registry.get(descriptor.code)
        if known_descriptor is not None and known_descriptor.issuer and descriptor.issuer:
            return str(known_descriptor.issuer).strip() == str(descriptor.issuer).strip()
        return True

    async def create_trustline(self, asset, limit=None):
        descriptor = asset if isinstance(asset, StellarAssetDescriptor) else self._parse_asset_text(str(asset or "").strip())
        block_reason = self.block_reason_for_asset(descriptor)
        if block_reason:
            raise ValueError(
                f"Trustline blocked for {descriptor.code}: this asset is marked as {block_reason.lower()} and is filtered by Sopotek."
            )
        if descriptor.is_native:
            return {
                "asset": self._asset_identifier(descriptor),
                "code": descriptor.code,
                "issuer": descriptor.issuer,
                "status": "native",
                "message": "XLM is the native Stellar asset and does not require a trustline.",
            }
        if self._has_trustline(descriptor):
            return {
                "asset": self._asset_identifier(descriptor),
                "code": descriptor.code,
                "issuer": descriptor.issuer,
                "status": "exists",
                "message": f"Trustline already exists for {descriptor.code}.",
            }

        limit_value = None if limit in (None, "") else f"{float(limit):.7f}"

        def _build(builder):
            builder.append_change_trust_op(
                asset=descriptor.to_sdk(),
                limit=limit_value,
            )

        try:
            response = await self._submit_transaction(_build)
        except Exception as exc:
            if BadRequestError is not None and isinstance(exc, BadRequestError):
                extras = getattr(exc, "extras", None) or {}
                result_codes = extras.get("result_codes") or {}
                transaction_code = str(result_codes.get("transaction") or "").strip()
                detail = str(getattr(exc, "detail", None) or "The trustline request was rejected by the Stellar network.")
                if transaction_code == "tx_insufficient_balance":
                    raise ValueError(
                        f"Stellar rejected the trustline for {descriptor.code}: insufficient spendable XLM for account reserves or fees."
                    ) from exc
                if transaction_code:
                    raise ValueError(
                        f"Stellar rejected the trustline for {descriptor.code} ({transaction_code}): {detail}"
                    ) from exc
                raise ValueError(f"Stellar rejected the trustline for {descriptor.code}: {detail}") from exc
            raise

        self._register_asset_descriptor(descriptor)
        if descriptor.code not in self._account_asset_codes:
            self._account_asset_codes.append(descriptor.code)
        self._save_asset_cache()
        try:
            await self._load_account(force=True, allow_stale=False, suppress_rate_limit=True)
        except Exception:
            pass

        return {
            "id": response.get("hash"),
            "asset": self._asset_identifier(descriptor),
            "code": descriptor.code,
            "issuer": descriptor.issuer,
            "status": "submitted",
            "message": f"Trustline submitted for {descriptor.code}.",
            "raw": response,
        }

    async def fetch_orders(self, symbol=None, limit=None):
        payload = await self._request(
            "GET",
            f"/accounts/{self.public_key}/offers",
            params={"order": "desc", "limit": limit or 50},
        )
        records = ((payload.get("_embedded") or {}).get("records")) or payload.get("records") or []
        orders = []
        for offer in records:
            normalized = self._normalize_offer(offer)
            if symbol and symbol != normalized["symbol"]:
                continue
            orders.append(normalized)
        return orders[:limit] if limit else orders

    async def fetch_open_orders(self, symbol=None, limit=None):
        return await self.fetch_orders(symbol=symbol, limit=limit)

    async def fetch_closed_orders(self, symbol=None, limit=None):
        return await self.fetch_my_trades(symbol=symbol, limit=limit)

    async def fetch_order(self, order_id, symbol=None):
        orders = await self.fetch_orders(symbol=symbol, limit=200)
        for order in orders:
            if str(order.get("id")) == str(order_id):
                return order
        return None

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
        base_asset, quote_asset = self._resolve_symbol_assets(symbol)
        order_side = str(side).lower()
        order_type = str(type or "market").lower()
        if order_type == "stop_limit":
            raise NotImplementedError("Stellar broker does not support stop_limit orders natively.")
        params = dict(params or {})
        slippage_pct = float(params.pop("slippage_pct", self.default_slippage_pct))

        bid, ask, last = await self._reference_price(symbol)
        if order_side == "buy":
            reference_price = self._float(price, ask or last or bid or 0.0)
            if reference_price <= 0:
                raise ValueError(f"Unable to determine Stellar buy price for {symbol}")
            effective_price = reference_price * (1 + slippage_pct) if order_type == "market" else reference_price
            available_balances = await self._validate_order_funding(
                symbol=symbol,
                side=order_side,
                amount=float(amount),
                price=effective_price,
                base_asset=base_asset,
                quote_asset=quote_asset,
            )

            def _build(builder):
                builder.append_manage_buy_offer_op(
                    selling=quote_asset.to_sdk(),
                    buying=base_asset.to_sdk(),
                    amount=f"{float(amount):.7f}",
                    price=f"{effective_price:.7f}",
                    offer_id=int(params.pop("offer_id", 0)),
                )

            try:
                response = await self._submit_transaction(_build)
            except Exception as exc:
                raise self._translate_order_submission_error(
                    exc,
                    symbol=symbol,
                    side=order_side,
                    amount=float(amount),
                    price=effective_price,
                    base_asset=base_asset,
                    quote_asset=quote_asset,
                    available_balances=available_balances,
                ) from exc
            return {
                "id": response.get("hash"),
                "symbol": self._symbol_from_assets(base_asset, quote_asset),
                "side": "buy",
                "type": order_type,
                "amount": float(amount),
                "price": effective_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": "submitted",
                "raw": response,
            }

        reference_price = self._float(price, bid or last or ask or 0.0)
        if reference_price <= 0:
            raise ValueError(f"Unable to determine Stellar sell price for {symbol}")
        effective_price = reference_price * max(1 - slippage_pct, 0.0001) if order_type == "market" else reference_price
        stellar_price = 1.0 / effective_price if effective_price else 0.0
        available_balances = await self._validate_order_funding(
            symbol=symbol,
            side=order_side,
            amount=float(amount),
            price=effective_price,
            base_asset=base_asset,
            quote_asset=quote_asset,
        )

        def _build(builder):
            builder.append_manage_sell_offer_op(
                selling=base_asset.to_sdk(),
                buying=quote_asset.to_sdk(),
                amount=f"{float(amount):.7f}",
                price=f"{stellar_price:.7f}",
                offer_id=int(params.pop("offer_id", 0)),
            )

        try:
            response = await self._submit_transaction(_build)
        except Exception as exc:
            raise self._translate_order_submission_error(
                exc,
                symbol=symbol,
                side=order_side,
                amount=float(amount),
                price=effective_price,
                base_asset=base_asset,
                quote_asset=quote_asset,
                available_balances=available_balances,
            ) from exc
        return {
            "id": response.get("hash"),
            "symbol": self._symbol_from_assets(base_asset, quote_asset),
            "side": "sell",
            "type": order_type,
            "amount": float(amount),
            "price": effective_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "submitted",
            "raw": response,
        }

    async def cancel_order(self, order_id, symbol=None):
        order = await self.fetch_order(order_id, symbol=symbol)
        if order is None:
            raise ValueError(f"Unknown Stellar offer id: {order_id}")

        raw_offer = order.get("raw", {})
        selling = raw_offer.get("selling", {}) if isinstance(raw_offer, dict) else {}
        buying = raw_offer.get("buying", {}) if isinstance(raw_offer, dict) else {}
        selling_text = "XLM" if selling.get("asset_type") == "native" else f"{selling.get('asset_code')}:{selling.get('asset_issuer')}"
        buying_text = "XLM" if buying.get("asset_type") == "native" else f"{buying.get('asset_code')}:{buying.get('asset_issuer')}"
        selling_asset = self._parse_asset_text(selling_text)
        buying_asset = self._parse_asset_text(buying_text)
        stellar_price = self._float(raw_offer.get("price"), 1.0) or 1.0

        def _build(builder):
            builder.append_manage_sell_offer_op(
                selling=selling_asset.to_sdk(),
                buying=buying_asset.to_sdk(),
                amount="0",
                price=f"{stellar_price:.7f}",
                offer_id=int(order_id),
            )

        response = await self._submit_transaction(_build)
        return {"id": str(order_id), "status": "canceled", "raw": response}
