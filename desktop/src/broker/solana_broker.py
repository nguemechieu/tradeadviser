from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from broker.base_broker import BaseBroker


BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {char: index for index, char in enumerate(BASE58_ALPHABET)}


@dataclass
class SolanaToken:
    symbol: str
    mint: str
    decimals: int
    name: str = ""


class SolanaBroker(BaseBroker):
    RPC_MAINNET_URL = "https://api.mainnet-beta.solana.com"
    RPC_DEVNET_URL = "https://api.devnet.solana.com"
    GECKO_BASE_URL = "https://api.geckoterminal.com/api/v2"
    GECKO_NETWORK = "solana"
    OKX_BASE_URL = "https://web3.okx.com"
    OKX_CHAIN_INDEX = "501"
    OKX_SUPPORTED_CHAINS_PATH = "/api/v6/dex/aggregator/supported/chain"
    OKX_TOKENS_PATH = "/api/v6/dex/aggregator/all-tokens"
    OKX_QUOTES_PATH = "/api/v6/dex/aggregator/quote"
    OKX_SWAP_PATH = "/api/v6/dex/aggregator/swap"
    OKX_HISTORY_PATH = "/api/v6/dex/aggregator/history"
    JUPITER_QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
    JUPITER_SWAP_URL = "https://api.jup.ag/swap/v1/swap"
    NATIVE_SOL_MINT = "11111111111111111111111111111111"
    WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
    TOKEN_PROGRAM_IDS = (
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    )
    LAMPORTS_PER_SOL = 1_000_000_000
    DEFAULT_SYMBOLS = ("SOL/USDC", "JUP/USDC", "BONK/USDC", "RAY/USDC")
    DEFAULT_QUOTES = ("USDC", "SOL")
    DEFAULT_SLIPPAGE_BPS = 100
    DEFAULT_ORDERBOOK_LEVELS = 12
    DEFAULT_MARKET_DATA_POLL_SECONDS = 2.5
    DEFAULT_CONFIRM_TIMEOUT_SECONDS = 30.0
    DEFAULT_BALANCE_SYMBOL = "USDC"
    DEFAULT_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    TIMEFRAME_MAP = {
        "1m": ("minute", 1),
        "5m": ("minute", 5),
        "15m": ("minute", 15),
        "1h": ("hour", 1),
        "4h": ("hour", 4),
        "1d": ("day", 1),
    }

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger("SolanaBroker")
        self.config = config
        self.exchange_name = "solana"
        self.mode = str(getattr(config, "mode", "paper") or "paper").strip().lower()
        self.sandbox = bool(getattr(config, "sandbox", False) or self.mode in {"paper", "sandbox", "devnet", "test"})
        self.params = dict(getattr(config, "params", None) or {})
        self.options = dict(getattr(config, "options", None) or {})
        self.market_data_poll_interval = float(
            self.params.get("market_data_poll_interval", self.DEFAULT_MARKET_DATA_POLL_SECONDS)
        )

        raw_api_value = str(getattr(config, "api_key", None) or "").strip()
        raw_secret_value = str(getattr(config, "secret", None) or "").strip()
        raw_password_value = str(
            getattr(config, "password", None)
            or getattr(config, "passphrase", None)
            or ""
        ).strip()
        raw_account_value = str(getattr(config, "account_id", None) or "").strip()

        self.wallet_address = str(
            self.options.get("wallet_address")
            or self.params.get("wallet_address")
            or ""
        ).strip()
        if not self.wallet_address and self._looks_like_base58_key(raw_api_value, expected_lengths=(32,)):
            self.wallet_address = raw_api_value

        self.secret = str(
            self.options.get("private_key")
            or self.params.get("private_key")
            or ""
        ).strip()
        if not self.secret and self._looks_like_private_key(raw_secret_value):
            self.secret = raw_secret_value

        self.okx_api_key = str(
            self.options.get("okx_api_key")
            or self.params.get("okx_api_key")
            or (raw_api_value if raw_api_value and raw_api_value != self.wallet_address else "")
            or os.getenv("OKX_API_KEY", "")
        ).strip()
        self.okx_secret_key = str(
            self.options.get("okx_secret_key")
            or self.params.get("okx_secret_key")
            or (raw_secret_value if raw_secret_value and raw_secret_value != self.secret else "")
            or os.getenv("OKX_SECRET_KEY", "")
        ).strip()
        self.okx_passphrase = str(
            self.options.get("okx_passphrase")
            or self.params.get("okx_passphrase")
            or raw_password_value
            or os.getenv("OKX_API_PASSPHRASE", "")
            or os.getenv("OKX_PASSPHRASE", "")
        ).strip()
        self.okx_project_id = str(
            self.options.get("okx_project_id")
            or self.params.get("okx_project_id")
            or os.getenv("OKX_PROJECT_ID", "")
        ).strip()
        if raw_account_value and not self.okx_project_id and not self._looks_like_url(raw_account_value):
            self.okx_project_id = raw_account_value

        self.jupiter_api_key = str(
            self.options.get("jupiter_api_key")
            or self.params.get("jupiter_api_key")
            or raw_password_value
            or os.getenv("JUPITER_API_KEY", "")
        ).strip()
        rpc_override = str(
            self.options.get("rpc_url")
            or self.params.get("rpc_url")
            or (raw_account_value if self._looks_like_url(raw_account_value) else "")
            or ""
        ).strip()
        self.rpc_url = str(
            rpc_override or (self.RPC_DEVNET_URL if self.sandbox else self.RPC_MAINNET_URL)
        ).strip()
        self.confirm_timeout_seconds = float(
            self.params.get("confirm_timeout_seconds", self.DEFAULT_CONFIRM_TIMEOUT_SECONDS)
        )
        self.okx_trade_api_ready = bool(
            self.okx_api_key and self.okx_secret_key and self.okx_passphrase
        )
        configured_market_data_provider = str(
            self.options.get("market_data_provider")
            or self.params.get("market_data_provider")
            or ""
        ).strip().lower()
        if configured_market_data_provider in {"okx", "trade-api"}:
            self.market_data_provider = "okx"
        elif configured_market_data_provider in {"gecko", "jupiter"}:
            self.market_data_provider = "gecko"
        else:
            self.market_data_provider = "okx" if self.okx_trade_api_ready else "gecko"
        self.swap_provider = "okx" if self.okx_trade_api_ready else "jupiter"

        self.session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self.symbols: List[str] = []
        self.market_registry: Dict[str, dict] = {}
        self.token_registry: Dict[str, SolanaToken] = {
            "SOL": SolanaToken("SOL", self.WRAPPED_SOL_MINT, 9, "Solana"),
            "USDC": SolanaToken("USDC", self.DEFAULT_USDC_MINT, 6, "USD Coin"),
        }
        self.mint_registry: Dict[str, SolanaToken] = {
            token.mint: token for token in self.token_registry.values()
        }
        self.okx_tokens_by_symbol: Dict[str, List[SolanaToken]] = {}
        self._okx_tokens_loaded = False
        self._recent_swaps: List[dict] = []

        self.default_symbols = self._configured_default_symbols()
        if self.wallet_address and not self._looks_like_base58_key(self.wallet_address, expected_lengths=(32,)):
            raise ValueError("Invalid Solana wallet address.")

    def supported_market_venues(self):
        return ["auto", "spot"]

    def supports_symbol(self, symbol):
        try:
            self._split_symbol(symbol)
        except ValueError:
            return False
        return True

    def _configured_default_symbols(self) -> List[str]:
        configured = self.params.get("symbols") or self.params.get("default_symbols")
        if isinstance(configured, str):
            raw_symbols = [item.strip() for item in configured.split(",") if item.strip()]
        elif isinstance(configured, (list, tuple, set)):
            raw_symbols = [str(item).strip() for item in configured if str(item).strip()]
        else:
            raw_symbols = list(self.DEFAULT_SYMBOLS)

        normalized = []
        for symbol in raw_symbols:
            normalized_symbol = self._normalize_symbol(symbol)
            if normalized_symbol and normalized_symbol not in normalized:
                normalized.append(normalized_symbol)
        return normalized or list(self.DEFAULT_SYMBOLS)

    @staticmethod
    def _float(value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _int(value, default=0) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)

    @classmethod
    def _normalize_symbol(cls, symbol: str) -> str:
        return str(symbol or "").upper().strip().replace("-", "/").replace("_", "/")

    def _split_symbol(self, symbol: str) -> Tuple[str, str]:
        normalized = self._normalize_symbol(symbol)
        if "/" not in normalized:
            raise ValueError(f"Invalid Solana market symbol: {symbol!r}")
        base, quote = normalized.split("/", 1)
        base = base.strip()
        quote = quote.strip()
        if not base or not quote:
            raise ValueError(f"Invalid Solana market symbol: {symbol!r}")
        return base, quote

    @staticmethod
    def _base58_decode(value: str) -> bytes:
        text = str(value or "").strip()
        if not text:
            return b""
        number = 0
        for char in text:
            if char not in BASE58_INDEX:
                raise ValueError("Invalid base58 value")
            number = (number * 58) + BASE58_INDEX[char]
        combined = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
        prefix_zeros = len(text) - len(text.lstrip("1"))
        return (b"\x00" * prefix_zeros) + combined

    @classmethod
    def _base58_encode(cls, raw: bytes) -> str:
        if not raw:
            return ""
        number = int.from_bytes(raw, "big")
        encoded = []
        while number:
            number, remainder = divmod(number, 58)
            encoded.append(BASE58_ALPHABET[remainder])
        encoded_text = "".join(reversed(encoded)) if encoded else ""
        prefix = "1" * len(raw[: len(raw) - len(raw.lstrip(b"\x00"))])
        return prefix + encoded_text

    @classmethod
    def _looks_like_base58_key(cls, value: str, *, expected_lengths=(32, 64)) -> bool:
        try:
            decoded = cls._base58_decode(value)
        except ValueError:
            return False
        return len(decoded) in set(expected_lengths)

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        text = str(value or "").strip().lower()
        return text.startswith("http://") or text.startswith("https://")

    def _looks_like_private_key(self, value: str) -> bool:
        try:
            self._normalize_private_key_bytes(value)
        except Exception:
            return False
        return True

    def _uses_okx_market_data(self) -> bool:
        return self.market_data_provider == "okx" and self.okx_trade_api_ready

    def _uses_okx_swaps(self) -> bool:
        return self.swap_provider == "okx" and self.okx_trade_api_ready

    def _normalize_private_key_bytes(self, secret_value: str) -> bytes:
        text = str(secret_value or "").strip()
        if not text:
            raise ValueError("Solana private key is required for live swaps.")

        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid Solana private key JSON array.") from exc
            if not isinstance(parsed, list):
                raise ValueError("Invalid Solana private key JSON array.")
            raw = bytes(int(item) & 0xFF for item in parsed)
        else:
            raw = self._base58_decode(text)

        if len(raw) == 64:
            return raw[:32]
        if len(raw) == 32:
            return raw
        raise ValueError("Unsupported Solana private key format.")

    def _wallet_public_key_bytes(self) -> Optional[bytes]:
        if not self.wallet_address:
            return None
        decoded = self._base58_decode(self.wallet_address)
        if len(decoded) != 32:
            raise ValueError("Invalid Solana wallet address.")
        return decoded

    def _private_key(self) -> Ed25519PrivateKey:
        seed_bytes = self._normalize_private_key_bytes(self.secret)
        private_key = Ed25519PrivateKey.from_private_bytes(seed_bytes)
        wallet_public_key = self._wallet_public_key_bytes()
        if wallet_public_key is not None:
            derived_public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            if derived_public_key != wallet_public_key:
                raise ValueError("Solana private key does not match the configured wallet address.")
        return private_key

    async def connect(self):
        if self._connected:
            return True

        timeout = aiohttp.ClientTimeout(total=float(self.params.get("timeout_seconds", 30.0)))
        self.session = aiohttp.ClientSession(timeout=timeout)
        self._connected = True

        try:
            await self.fetch_symbols()
        except Exception as exc:
            self.logger.debug("Solana default market discovery skipped: %s", exc)

        self.logger.info("Connected to Solana broker rpc=%s sandbox=%s", self.rpc_url, self.sandbox)
        return True

    async def close(self):
        if self.session is not None:
            await self.session.close()
        self.session = None
        self._connected = False

    async def _ensure_connected(self):
        if not self._connected or self.session is None:
            await self.connect()
        return self.session

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        headers: Optional[dict] = None,
        expected_statuses: Tuple[int, ...] = (200,),
    ) -> dict:
        session = await self._ensure_connected()
        async with session.request(method, url, params=params, json=payload, headers=headers) as response:
            raw_text = await response.text()
            if response.status not in expected_statuses:
                preview = raw_text.strip()
                if len(preview) > 400:
                    preview = preview[:400] + "..."
                raise RuntimeError(
                    f"Solana request failed [{response.status}] {url}: {preview or 'empty response'}"
                )
            if not raw_text.strip():
                return {}
            return json.loads(raw_text)

    async def _request_gecko(self, path: str, *, params: Optional[dict] = None) -> dict:
        return await self._request_json("GET", f"{self.GECKO_BASE_URL}{path}", params=params)

    @staticmethod
    def _okx_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @staticmethod
    def _okx_query_string(params: Optional[dict]) -> str:
        if not params:
            return ""
        encoded_params = []
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                normalized_value = "true" if value else "false"
            else:
                normalized_value = str(value)
            if not normalized_value:
                continue
            encoded_params.append((str(key), normalized_value))
        if not encoded_params:
            return ""
        return f"?{urlencode(encoded_params)}"

    def _okx_headers(self, request_path: str, *, params: Optional[dict] = None) -> dict:
        if not self.okx_trade_api_ready:
            raise ValueError(
                "OKX Trade API requires an API key, secret, and passphrase."
            )
        timestamp = self._okx_timestamp()
        query_string = self._okx_query_string(params)
        prehash = f"{timestamp}GET{request_path}{query_string}"
        signature = base64.b64encode(
            hmac.new(
                self.okx_secret_key.encode("utf-8"),
                prehash.encode("utf-8"),
                "sha256",
            ).digest()
        ).decode("ascii")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.okx_api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.okx_passphrase,
        }
        if self.okx_project_id:
            headers["OK-ACCESS-PROJECT"] = self.okx_project_id
        return headers

    async def _request_okx(self, path: str, *, params: Optional[dict] = None) -> dict:
        payload = await self._request_json(
            "GET",
            f"{self.OKX_BASE_URL}{path}",
            params=params,
            headers=self._okx_headers(path, params=params),
        )
        code = str(payload.get("code") or "")
        if code and code != "0":
            raise RuntimeError(
                f"OKX Trade API request failed [{code}] {path}: {payload.get('msg') or 'unknown error'}"
            )
        return payload

    @staticmethod
    def _okx_data_items(payload: dict) -> List[dict]:
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    async def _request_rpc(self, method: str, params: Optional[list] = None):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": str(method),
            "params": list(params or []),
        }
        response = await self._request_json("POST", self.rpc_url, payload=payload)
        if "error" in response:
            raise RuntimeError(f"Solana RPC {method} failed: {response['error']}")
        return response.get("result")

    async def _request_jupiter(self, method: str, url: str, *, params=None, payload=None) -> dict:
        headers = {"Accept": "application/json"}
        if self.jupiter_api_key:
            headers["x-api-key"] = self.jupiter_api_key
        return await self._request_json(
            method,
            url,
            params=params,
            payload=payload,
            headers=headers,
        )

    @staticmethod
    def _json_api_included_index(payload: dict) -> Dict[str, dict]:
        included_index = {}
        for item in payload.get("included", []) or []:
            if isinstance(item, dict):
                included_index[str(item.get("id") or "")] = item
        return included_index

    @classmethod
    def _json_api_items(cls, payload: dict) -> List[dict]:
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    def _token_from_json_api(self, item: Optional[dict]) -> Optional[SolanaToken]:
        if not isinstance(item, dict):
            return None

        attributes = dict(item.get("attributes") or {})
        identifier = str(item.get("id") or "")
        mint = str(
            attributes.get("address")
            or attributes.get("token_address")
            or attributes.get("mint")
            or identifier.split("_", 1)[-1]
            or ""
        ).strip()
        symbol = str(attributes.get("symbol") or attributes.get("token_symbol") or "").upper().strip()
        decimals = self._int(attributes.get("decimals"), 0)
        if not mint or not symbol:
            return None
        token = SolanaToken(symbol=symbol, mint=mint, decimals=decimals, name=str(attributes.get("name") or symbol))
        self.token_registry[token.symbol] = token
        self.mint_registry[token.mint] = token
        return token

    def _register_okx_token(self, token: SolanaToken, *, preferred: bool = False):
        current = self.token_registry.get(token.symbol)
        if preferred or current is None:
            self.token_registry[token.symbol] = token
        self.mint_registry[token.mint] = token
        candidates = self.okx_tokens_by_symbol.setdefault(token.symbol, [])
        if all(existing.mint != token.mint for existing in candidates):
            candidates.append(token)

    async def _ensure_okx_tokens_loaded(self):
        if self._okx_tokens_loaded:
            return

        payload = await self._request_okx(
            self.OKX_TOKENS_PATH,
            params={"chainIndex": self.OKX_CHAIN_INDEX},
        )
        items = self._okx_data_items(payload)
        if not items:
            raise RuntimeError("OKX Trade API did not return any Solana tokens.")

        self.okx_tokens_by_symbol = {}
        self._register_okx_token(
            SolanaToken("SOL", self.NATIVE_SOL_MINT, 9, "Solana"),
            preferred=True,
        )
        self._register_okx_token(
            SolanaToken("USDC", self.DEFAULT_USDC_MINT, 6, "USD Coin")
        )
        for item in items:
            symbol = str(item.get("tokenSymbol") or "").upper().strip()
            mint = str(item.get("tokenContractAddress") or "").strip()
            if not symbol or not mint:
                continue
            if symbol == "SOL":
                mint = self.NATIVE_SOL_MINT
            token = SolanaToken(
                symbol=symbol,
                mint=mint,
                decimals=self._int(item.get("decimals"), 0),
                name=str(item.get("tokenName") or symbol),
            )
            self._register_okx_token(token, preferred=(symbol == "SOL"))
        self._okx_tokens_loaded = True

    def _okx_tokens_for_symbol(self, symbol: str) -> List[SolanaToken]:
        normalized = str(symbol or "").upper().strip()
        candidates = list(self.okx_tokens_by_symbol.get(normalized) or [])
        fallback = self.token_registry.get(normalized)
        if fallback is not None and all(item.mint != fallback.mint for item in candidates):
            candidates.append(fallback)
        return candidates

    def _pool_candidates(self, payload: dict) -> List[dict]:
        included_index = self._json_api_included_index(payload)
        candidates = []
        for item in self._json_api_items(payload):
            identifier = str(item.get("id") or "")
            if identifier and not identifier.startswith(f"{self.GECKO_NETWORK}_"):
                continue

            attributes = dict(item.get("attributes") or {})
            relationships = dict(item.get("relationships") or {})
            base_ref = (((relationships.get("base_token") or {}).get("data")) or {}).get("id")
            quote_ref = (((relationships.get("quote_token") or {}).get("data")) or {}).get("id")
            base_token = self._token_from_json_api(included_index.get(str(base_ref or "")))
            quote_token = self._token_from_json_api(included_index.get(str(quote_ref or "")))
            if base_token is None or quote_token is None:
                continue

            pool_address = str(
                attributes.get("address")
                or attributes.get("pool_address")
                or identifier.split("_", 1)[-1]
                or ""
            ).strip()
            reserve_usd = self._float(
                attributes.get("reserve_in_usd")
                or attributes.get("reserve_usd")
                or attributes.get("fdv_usd"),
                0.0,
            )
            candidates.append(
                {
                    "id": identifier,
                    "pool_address": pool_address,
                    "attributes": attributes,
                    "base_token": base_token,
                    "quote_token": quote_token,
                    "reserve_usd": reserve_usd,
                }
            )
        return candidates

    def _pool_price_for_market(self, market: dict, candidate: dict) -> float:
        attributes = dict(candidate.get("attributes") or {})
        direct_price = self._float(attributes.get("base_token_price_quote_token"), 0.0)
        inverse_price = self._float(attributes.get("quote_token_price_base_token"), 0.0)
        base_mint = str((candidate.get("base_token") or SolanaToken("", "", 0)).mint or "")
        quote_mint = str((candidate.get("quote_token") or SolanaToken("", "", 0)).mint or "")

        if base_mint == market.get("base_mint") and quote_mint == market.get("quote_mint"):
            if direct_price > 0:
                return direct_price
            if inverse_price > 0:
                return 1.0 / inverse_price

        if base_mint == market.get("quote_mint") and quote_mint == market.get("base_mint"):
            if inverse_price > 0:
                return inverse_price
            if direct_price > 0:
                return 1.0 / direct_price

        return direct_price if direct_price > 0 else (1.0 / inverse_price if inverse_price > 0 else 0.0)

    def _select_pool_candidate(self, symbol: str, candidates: List[dict]) -> Optional[dict]:
        base_symbol, quote_symbol = self._split_symbol(symbol)
        target_base = self.token_registry.get(base_symbol)
        target_quote = self.token_registry.get(quote_symbol)

        scored = []
        for candidate in candidates:
            base_token = candidate.get("base_token")
            quote_token = candidate.get("quote_token")
            if not isinstance(base_token, SolanaToken) or not isinstance(quote_token, SolanaToken):
                continue

            direct_symbol_match = base_token.symbol == base_symbol and quote_token.symbol == quote_symbol
            reverse_symbol_match = base_token.symbol == quote_symbol and quote_token.symbol == base_symbol
            direct_mint_match = (
                target_base is not None
                and target_quote is not None
                and base_token.mint == target_base.mint
                and quote_token.mint == target_quote.mint
            )
            reverse_mint_match = (
                target_base is not None
                and target_quote is not None
                and base_token.mint == target_quote.mint
                and quote_token.mint == target_base.mint
            )

            if not any((direct_symbol_match, reverse_symbol_match, direct_mint_match, reverse_mint_match)):
                continue

            score = candidate.get("reserve_usd", 0.0)
            if direct_symbol_match:
                score += 5_000_000.0
            if direct_mint_match:
                score += 10_000_000.0
            if reverse_symbol_match:
                score += 1_000_000.0
            if reverse_mint_match:
                score += 2_000_000.0
            scored.append((score, candidate))

        if not scored:
            return None

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _cache_market(self, symbol: str, candidate: dict) -> dict:
        normalized_symbol = self._normalize_symbol(symbol)
        base_symbol, quote_symbol = self._split_symbol(normalized_symbol)
        base_token = candidate["base_token"]
        quote_token = candidate["quote_token"]
        market = {
            "id": normalized_symbol,
            "symbol": normalized_symbol,
            "base": base_symbol,
            "quote": quote_symbol,
            "base_mint": base_token.mint if base_token.symbol == base_symbol else quote_token.mint,
            "quote_mint": quote_token.mint if quote_token.symbol == quote_symbol else base_token.mint,
            "base_decimals": base_token.decimals if base_token.symbol == base_symbol else quote_token.decimals,
            "quote_decimals": quote_token.decimals if quote_token.symbol == quote_symbol else base_token.decimals,
            "pool_address": candidate.get("pool_address"),
            "active": True,
            "spot": True,
            "provider": candidate.get("provider") or "gecko",
        }
        self.market_registry[normalized_symbol] = market
        return market

    async def _resolve_market_via_okx(self, symbol: str) -> dict:
        normalized_symbol = self._normalize_symbol(symbol)
        cached = self.market_registry.get(normalized_symbol)
        if cached and str(cached.get("provider") or "").lower() == "okx":
            return dict(cached)

        await self._ensure_okx_tokens_loaded()
        base_symbol, quote_symbol = self._split_symbol(normalized_symbol)
        base_candidates = self._okx_tokens_for_symbol(base_symbol)
        quote_candidates = self._okx_tokens_for_symbol(quote_symbol)
        if not base_candidates or not quote_candidates:
            raise ValueError(f"OKX could not resolve Solana market {normalized_symbol}.")

        selected_base = None
        selected_quote = None
        for base_token in base_candidates:
            for quote_token in quote_candidates:
                if base_token.mint == quote_token.mint:
                    continue
                selected_base = base_token
                selected_quote = quote_token
                break
            if selected_base is not None and selected_quote is not None:
                break

        if selected_base is None or selected_quote is None:
            raise ValueError(f"OKX could not resolve distinct token mints for {normalized_symbol}.")

        market = self._cache_market(
            normalized_symbol,
            {
                "base_token": selected_base,
                "quote_token": selected_quote,
                "pool_address": None,
                "provider": "okx",
            },
        )
        if base_symbol == "SOL":
            market["base_mint"] = self.NATIVE_SOL_MINT
        if quote_symbol == "SOL":
            market["quote_mint"] = self.NATIVE_SOL_MINT
        market["chainIndex"] = self.OKX_CHAIN_INDEX
        self.market_registry[normalized_symbol] = dict(market)
        return dict(market)

    async def _resolve_market(self, symbol: str) -> dict:
        normalized_symbol = self._normalize_symbol(symbol)
        cached = self.market_registry.get(normalized_symbol)
        if cached is not None and not (
            self._uses_okx_market_data()
            and str(cached.get("provider") or "").lower() != "okx"
        ):
            return dict(cached)

        if self._uses_okx_market_data():
            try:
                return await self._resolve_market_via_okx(normalized_symbol)
            except Exception as exc:
                self.logger.debug("OKX Solana market resolution failed for %s: %s", normalized_symbol, exc)

        base_symbol, quote_symbol = self._split_symbol(normalized_symbol)
        search_queries = [
            f"{base_symbol} {quote_symbol}",
            normalized_symbol,
            base_symbol,
        ]

        known_base = self.token_registry.get(base_symbol)
        token_paths = []
        if known_base is not None:
            token_paths.extend(
                [
                    f"/networks/{self.GECKO_NETWORK}/tokens/{known_base.mint}/pools",
                    f"/networks/{self.GECKO_NETWORK}/tokens/{known_base.mint}/pool",
                ]
            )

        for path in token_paths:
            try:
                payload = await self._request_gecko(path)
            except Exception:
                continue
            candidate = self._select_pool_candidate(normalized_symbol, self._pool_candidates(payload))
            if candidate is not None:
                return self._cache_market(normalized_symbol, candidate)

        for query in search_queries:
            try:
                payload = await self._request_gecko(
                    "/search/pools",
                    params={"query": query, "include": "base_token,quote_token"},
                )
            except Exception:
                continue
            candidate = self._select_pool_candidate(normalized_symbol, self._pool_candidates(payload))
            if candidate is not None:
                return self._cache_market(normalized_symbol, candidate)

        raise ValueError(f"Unable to resolve Solana market for {normalized_symbol}.")

    async def fetch_symbol(self):
        return await self.fetch_symbols()

    async def fetch_symbols(self):
        if self._uses_okx_market_data():
            try:
                await self._ensure_okx_tokens_loaded()
                discovered = []
                for symbol in self.default_symbols:
                    normalized_symbol = self._normalize_symbol(symbol)
                    if not normalized_symbol or normalized_symbol in discovered:
                        continue
                    try:
                        market = await self._resolve_market_via_okx(normalized_symbol)
                    except Exception:
                        continue
                    discovered.append(market["symbol"])
                if discovered:
                    self.symbols = list(discovered)
                    return list(self.symbols)
            except Exception as exc:
                self.logger.debug("OKX Solana symbol discovery failed: %s", exc)

        discovered = []
        for symbol in self.default_symbols:
            normalized_symbol = self._normalize_symbol(symbol)
            if not normalized_symbol or normalized_symbol in discovered:
                continue
            discovered.append(normalized_symbol)
            try:
                await self._resolve_market(normalized_symbol)
            except Exception:
                continue
        self.symbols = list(discovered)
        return list(self.symbols)

    async def fetch_markets(self):
        markets = {}
        for symbol in await self.fetch_symbols():
            try:
                market = await self._resolve_market(symbol)
            except Exception:
                market = {"symbol": symbol, "active": True, "spot": True}
            markets[symbol] = dict(market)
        return markets

    async def fetch_currencies(self):
        if self._uses_okx_market_data():
            try:
                await self._ensure_okx_tokens_loaded()
            except Exception as exc:
                self.logger.debug("OKX Solana token discovery failed: %s", exc)
        return {
            token.symbol: {
                "id": token.symbol,
                "code": token.symbol,
                "name": token.name or token.symbol,
                "precision": token.decimals,
                "active": True,
            }
            for token in self.token_registry.values()
        }

    async def fetch_status(self):
        try:
            result = await self._request_rpc("getVersion")
            return {
                "status": "ok",
                "broker": "solana",
                "rpc_url": self.rpc_url,
                "version": result,
            }
        except Exception as exc:
            return {
                "status": "error",
                "broker": "solana",
                "rpc_url": self.rpc_url,
                "detail": str(exc),
            }

    async def _pool_snapshot(self, market: dict) -> dict:
        pool_address = market.get("pool_address")
        if not pool_address:
            raise ValueError(f"Missing pool address for {market.get('symbol')}")
        return await self._request_gecko(
            f"/networks/{self.GECKO_NETWORK}/pools/{pool_address}",
            params={"include": "base_token,quote_token"},
        )

    async def fetch_ticker(self, symbol):
        market = await self._resolve_market(symbol)
        if str(market.get("provider") or "").lower() == "okx":
            amount_units = max(1, 10 ** max(0, int(market.get("base_decimals") or 0)))
            quote = await self._quote_okx(
                market["base_mint"],
                market["quote_mint"],
                amount_units,
            )
            last_price = self._okx_quote_price(
                quote,
                base_decimals=market["base_decimals"],
                quote_decimals=market["quote_decimals"],
            )
            if last_price <= 0:
                raise ValueError(f"Unable to price Solana market {market['symbol']} via OKX.")
            spread_bps = 10.0
            return {
                "symbol": market["symbol"],
                "bid": last_price * (1.0 - (spread_bps / 20_000.0)),
                "ask": last_price * (1.0 + (spread_bps / 20_000.0)),
                "last": last_price,
                "baseVolume": 0.0,
                "quoteVolume": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "info": quote,
            }

        payload = await self._pool_snapshot(market)
        candidates = self._pool_candidates(payload)
        if not candidates:
            raise ValueError(f"No Solana pool data returned for {market['symbol']}")

        candidate = candidates[0]
        last_price = self._pool_price_for_market(market, candidate)
        if last_price <= 0:
            raise ValueError(f"Unable to price Solana market {market['symbol']}")

        reserve_usd = max(candidate.get("reserve_usd", 0.0), 1_000.0)
        spread_bps = min(35.0, max(8.0, 250_000.0 / reserve_usd))
        bid = last_price * (1.0 - (spread_bps / 20_000.0))
        ask = last_price * (1.0 + (spread_bps / 20_000.0))
        attributes = dict(candidate.get("attributes") or {})

        return {
            "symbol": market["symbol"],
            "bid": bid,
            "ask": ask,
            "last": last_price,
            "baseVolume": self._float(attributes.get("base_token_volume_24h"), 0.0),
            "quoteVolume": self._float(attributes.get("quote_token_volume_24h"), 0.0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "info": payload,
        }

    async def fetch_orderbook(self, symbol, limit=50):
        ticker = await self.fetch_ticker(symbol)
        last_price = self._float(ticker.get("last"), 0.0)
        if last_price <= 0:
            return {"bids": [], "asks": []}

        levels = max(1, min(int(limit or self.DEFAULT_ORDERBOOK_LEVELS), 100))
        size_seed = max(1.0, 1000.0 / max(last_price, 0.01))
        bids = []
        asks = []
        for index in range(levels):
            level_offset = 0.0006 * (index + 1)
            quantity = max(0.01, size_seed / float(index + 1))
            bids.append([last_price * (1.0 - level_offset), quantity])
            asks.append([last_price * (1.0 + level_offset), quantity])
        return {"bids": bids, "asks": asks}

    async def fetch_trades(self, symbol, limit=None):
        market = await self._resolve_market(symbol)
        if str(market.get("provider") or "").lower() == "okx":
            ticker = await self.fetch_ticker(market["symbol"])
            return [
                {
                    "id": f"okx-{int(time.time() * 1000)}",
                    "symbol": market["symbol"],
                    "side": None,
                    "price": self._float(ticker.get("last"), 0.0),
                    "amount": 0.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "info": ticker.get("info") or {},
                }
            ]

        payload = await self._request_gecko(
            f"/networks/{self.GECKO_NETWORK}/pools/{market['pool_address']}/trades",
            params={"limit": max(1, min(int(limit or 40), 100))},
        )

        trades = []
        for item in self._json_api_items(payload):
            attributes = dict(item.get("attributes") or {})
            from_amount = self._float(
                attributes.get("from_token_amount")
                or attributes.get("base_token_amount")
                or attributes.get("amount_in"),
                0.0,
            )
            to_amount = self._float(
                attributes.get("to_token_amount")
                or attributes.get("quote_token_amount")
                or attributes.get("amount_out"),
                0.0,
            )
            price = self._float(
                attributes.get("price_to_quote_token")
                or attributes.get("price")
                or attributes.get("base_token_price_quote_token"),
                0.0,
            )
            if price <= 0 and from_amount > 0 and to_amount > 0:
                price = to_amount / from_amount
            timestamp = str(
                attributes.get("block_timestamp")
                or attributes.get("timestamp")
                or attributes.get("created_at")
                or datetime.now(timezone.utc).isoformat()
            )
            trades.append(
                {
                    "id": str(item.get("id") or attributes.get("tx_hash") or len(trades)),
                    "symbol": market["symbol"],
                    "side": str(attributes.get("kind") or attributes.get("side") or "").lower() or None,
                    "price": price,
                    "amount": from_amount if from_amount > 0 else to_amount,
                    "timestamp": timestamp,
                    "info": attributes,
                }
            )

        return trades[: max(1, int(limit or len(trades) or 1))]

    def _flat_candles(self, price: float, timeframe: str, limit: int) -> List[List[float]]:
        granularity, aggregate = self.TIMEFRAME_MAP.get(str(timeframe or "1h").lower(), ("hour", 1))
        step_seconds = {
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }.get(granularity, 3600) * max(1, int(aggregate or 1))

        now_ms = int(time.time() * 1000)
        candles = []
        for index in range(max(1, int(limit or 1))):
            timestamp = now_ms - ((max(1, int(limit or 1)) - index - 1) * step_seconds * 1000)
            candles.append([timestamp, price, price, price, price, 0.0])
        return candles

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        market = await self._resolve_market(symbol)
        normalized_timeframe = str(timeframe or "1h").lower()
        if str(market.get("provider") or "").lower() == "okx":
            ticker = await self.fetch_ticker(market["symbol"])
            return self._flat_candles(
                self._float(ticker.get("last"), 0.0),
                normalized_timeframe,
                int(limit or 100),
            )

        granularity, aggregate = self.TIMEFRAME_MAP.get(normalized_timeframe, ("hour", 1))
        params = {
            "aggregate": max(1, int(aggregate or 1)),
            "limit": max(1, min(int(limit or 100), 500)),
            "currency": "token",
            "token": market.get("base_mint"),
        }

        attempts = (
            f"/networks/{self.GECKO_NETWORK}/pools/{market['pool_address']}/ohlcv/{granularity}",
            f"/networks/{self.GECKO_NETWORK}/pools/{market['pool_address']}/ohlc/{granularity}",
        )
        for path in attempts:
            try:
                payload = await self._request_gecko(path, params=params)
            except Exception:
                continue

            attributes = dict(((payload.get("data") or {}).get("attributes")) or {})
            rows = attributes.get("ohlcv_list") or attributes.get("ohlc_list") or []
            candles = []
            for row in rows or []:
                if not isinstance(row, (list, tuple)) or len(row) < 5:
                    continue
                timestamp = self._int(row[0], 0)
                if timestamp <= 0:
                    continue
                if timestamp < 10**11:
                    timestamp *= 1000
                volume = self._float(row[5], 0.0) if len(row) > 5 else 0.0
                candles.append(
                    [
                        timestamp,
                        self._float(row[1], 0.0),
                        self._float(row[2], 0.0),
                        self._float(row[3], 0.0),
                        self._float(row[4], 0.0),
                        volume,
                    ]
                )
            if candles:
                return candles[-max(1, int(limit or len(candles))):]

        ticker = await self.fetch_ticker(market["symbol"])
        return self._flat_candles(self._float(ticker.get("last"), 0.0), normalized_timeframe, int(limit or 100))

    def _token_symbol_for_mint(self, mint: str) -> str:
        if mint in {self.WRAPPED_SOL_MINT, self.NATIVE_SOL_MINT}:
            return "SOL"
        token = self.mint_registry.get(str(mint or "").strip())
        if token is not None and token.symbol:
            return token.symbol
        return f"TOKEN-{str(mint or '')[:4].upper()}"

    async def _quote_okx(self, from_mint: str, to_mint: str, amount_units: int) -> dict:
        payload = await self._request_okx(
            self.OKX_QUOTES_PATH,
            params={
                "chainIndex": self.OKX_CHAIN_INDEX,
                "fromTokenAddress": str(from_mint),
                "toTokenAddress": str(to_mint),
                "amount": max(1, int(amount_units)),
                "swapMode": "exactIn",
            },
        )
        items = self._okx_data_items(payload)
        if not items:
            raise RuntimeError("OKX Trade API did not return a Solana quote.")
        return dict(items[0])

    def _okx_quote_price(self, quote: dict, *, base_decimals: int, quote_decimals: int) -> float:
        from_amount = self._int(quote.get("fromTokenAmount"), 0)
        to_amount = self._int(quote.get("toTokenAmount"), 0)
        if from_amount <= 0 or to_amount <= 0:
            return 0.0
        base_amount = self._units_to_amount(from_amount, base_decimals)
        quote_amount = self._units_to_amount(to_amount, quote_decimals)
        if base_amount <= 0:
            return 0.0
        return quote_amount / base_amount

    async def fetch_balance(self, currency="USDC"):
        normalized_currency = str(currency or self.DEFAULT_BALANCE_SYMBOL).upper().strip() or self.DEFAULT_BALANCE_SYMBOL
        total = {}
        free = {}
        used = {}

        if not self.wallet_address:
            return {
                "currency": normalized_currency,
                "equity": 0.0,
                "free": {normalized_currency: 0.0},
                "used": {normalized_currency: 0.0},
                "total": {normalized_currency: 0.0},
                "asset_balances": {},
            }

        sol_result = await self._request_rpc(
            "getBalance",
            [self.wallet_address, {"commitment": "confirmed"}],
        )
        sol_balance = self._float(sol_result.get("value"), 0.0) / float(self.LAMPORTS_PER_SOL)
        total["SOL"] = sol_balance
        free["SOL"] = sol_balance
        used["SOL"] = 0.0

        for program_id in self.TOKEN_PROGRAM_IDS:
            token_accounts = await self._request_rpc(
                "getTokenAccountsByOwner",
                [
                    self.wallet_address,
                    {"programId": program_id},
                    {"encoding": "jsonParsed"},
                ],
            )
            for item in token_accounts.get("value", []) or []:
                account_data = ((((item.get("account") or {}).get("data") or {}).get("parsed")) or {}).get("info") or {}
                mint = str(account_data.get("mint") or "").strip()
                amount_payload = dict(account_data.get("tokenAmount") or {})
                amount = self._float(
                    amount_payload.get("uiAmount")
                    if amount_payload.get("uiAmount") is not None
                    else amount_payload.get("uiAmountString"),
                    0.0,
                )
                if amount <= 0:
                    continue
                symbol = self._token_symbol_for_mint(mint)
                total[symbol] = total.get(symbol, 0.0) + amount
                free[symbol] = free.get(symbol, 0.0) + amount
                used[symbol] = 0.0

        reference_equity = self._float(total.get(normalized_currency), 0.0)
        if normalized_currency != "SOL" and reference_equity <= 0 and "USDC" in total:
            reference_equity = self._float(total.get("USDC"), 0.0)

        return {
            "currency": normalized_currency,
            "equity": reference_equity,
            "free": free,
            "used": used,
            "total": total,
            "asset_balances": dict(total),
        }

    async def fetch_positions(self, symbols=None):
        balances = await self.fetch_balance()
        totals = dict(balances.get("total") or {})
        allowed = {
            self._normalize_symbol(symbol)
            for symbol in (symbols or [])
            if str(symbol or "").strip()
        }
        positions = []
        quote_candidates = tuple(str(item).upper().strip() for item in self.DEFAULT_QUOTES)

        for asset_code, amount in totals.items():
            normalized_asset = str(asset_code or "").upper().strip()
            quantity = self._float(amount, 0.0)
            if normalized_asset in {"USDC", "SOL"} or quantity <= 0:
                continue

            symbol = None
            for quote in quote_candidates:
                candidate_symbol = f"{normalized_asset}/{quote}"
                if not allowed or candidate_symbol in allowed:
                    symbol = candidate_symbol
                    break
            if symbol is None:
                symbol = normalized_asset
                if allowed and symbol not in allowed:
                    continue

            positions.append(
                {
                    "id": normalized_asset,
                    "symbol": symbol,
                    "side": "long",
                    "amount": quantity,
                    "quantity": quantity,
                    "asset": normalized_asset,
                    "status": "open",
                }
            )
        return positions

    def _remember_swap(self, payload: dict):
        snapshot = dict(payload or {})
        snapshot.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self._recent_swaps.insert(0, snapshot)
        del self._recent_swaps[50:]

    async def fetch_order(self, order_id, symbol=None):
        normalized_symbol = self._normalize_symbol(symbol) if symbol else ""
        for item in self._recent_swaps:
            if str(item.get("id") or item.get("order_id") or "").strip() != str(order_id):
                continue
            if normalized_symbol and self._normalize_symbol(item.get("symbol")) != normalized_symbol:
                continue
            return dict(item)
        return None

    async def fetch_orders(self, symbol=None, limit=None):
        normalized_symbol = self._normalize_symbol(symbol) if symbol else ""
        orders = []
        for item in self._recent_swaps:
            if normalized_symbol and self._normalize_symbol(item.get("symbol")) != normalized_symbol:
                continue
            orders.append(dict(item))
        return orders[: max(1, int(limit or len(orders) or 1))]

    async def fetch_open_orders(self, symbol=None, limit=None):
        _ = symbol, limit
        return []

    async def fetch_closed_orders(self, symbol=None, limit=None):
        return await self.fetch_orders(symbol=symbol, limit=limit)

    async def fetch_my_trades(self, symbol=None, limit=None):
        return await self.fetch_orders(symbol=symbol, limit=limit)

    @staticmethod
    def _shortvec_decode(raw: bytes, start_index: int = 0) -> Tuple[int, int]:
        value = 0
        shift = 0
        index = int(start_index)
        while True:
            current = raw[index]
            value |= (current & 0x7F) << shift
            index += 1
            if not (current & 0x80):
                return value, index
            shift += 7

    def _sign_serialized_transaction(self, unsigned_transaction: str, *, encoding: str = "base64") -> str:
        serialized = str(unsigned_transaction or "").strip()
        if encoding == "base58":
            raw = bytearray(self._base58_decode(serialized))
        else:
            raw = bytearray(base64.b64decode(serialized))
        signature_count, signature_offset = self._shortvec_decode(raw, 0)
        signatures_length = signature_count * 64
        message_offset = signature_offset + signatures_length
        message = bytes(raw[message_offset:])

        cursor = 0
        if message and (message[0] & 0x80):
            cursor += 1
        header = message[cursor: cursor + 3]
        if len(header) < 3:
            raise ValueError("Invalid Solana transaction header.")
        num_required_signatures = int(header[0])
        cursor += 3
        account_count, cursor = self._shortvec_decode(message, cursor)

        signer_keys = []
        for index in range(account_count):
            key_bytes = bytes(message[cursor: cursor + 32])
            cursor += 32
            if index < num_required_signatures:
                signer_keys.append(key_bytes)

        private_key = self._private_key()
        public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        signer_index = 0
        for index, signer_key in enumerate(signer_keys):
            if signer_key == public_key:
                signer_index = index
                break

        signature = private_key.sign(message)
        slot_start = signature_offset + (signer_index * 64)
        raw[slot_start: slot_start + 64] = signature
        signed_bytes = bytes(raw)
        if encoding == "base58":
            return self._base58_encode(signed_bytes)
        return base64.b64encode(signed_bytes).decode("ascii")

    async def _send_signed_transaction(self, signed_transaction: str, *, encoding: str = "base64") -> str:
        if encoding == "base58":
            signed_transaction = base64.b64encode(
                self._base58_decode(str(signed_transaction or "").strip())
            ).decode("ascii")
        result = await self._request_rpc(
            "sendTransaction",
            [
                signed_transaction,
                {
                    "encoding": "base64",
                    "skipPreflight": False,
                    "preflightCommitment": "confirmed",
                    "maxRetries": 3,
                },
            ],
        )
        signature = str(result or "").strip()
        if not signature:
            raise RuntimeError("Solana RPC did not return a transaction signature.")
        return signature

    async def _wait_for_signature(self, signature: str):
        deadline = time.monotonic() + max(5.0, float(self.confirm_timeout_seconds or 30.0))
        while time.monotonic() < deadline:
            status_result = await self._request_rpc(
                "getSignatureStatuses",
                [[signature], {"searchTransactionHistory": True}],
            )
            values = list(status_result.get("value") or [])
            current = values[0] if values else None
            if isinstance(current, dict):
                if current.get("err"):
                    raise RuntimeError(f"Solana transaction failed: {current['err']}")
                confirmation_status = str(current.get("confirmationStatus") or "").lower()
                if confirmation_status in {"confirmed", "finalized"}:
                    return current
            await asyncio.sleep(1.0)
        raise TimeoutError(f"Timed out waiting for Solana transaction confirmation: {signature}")

    def _units_to_amount(self, units: int, decimals: int) -> float:
        return float(units) / float(10 ** max(0, int(decimals or 0)))

    def _amount_to_units(self, amount: float, decimals: int) -> int:
        return max(1, int(round(float(amount or 0.0) * float(10 ** max(0, int(decimals or 0))))))

    async def _simulate_order(self, symbol: str, side: str, amount: float):
        ticker = await self.fetch_ticker(symbol)
        execution_price = self._float(ticker.get("ask" if str(side).lower() == "buy" else "bid"), 0.0)
        if execution_price <= 0:
            execution_price = self._float(ticker.get("last"), 0.0)
        cost = float(amount or 0.0) * execution_price
        order_id = f"solana-paper-{int(time.time() * 1000)}"
        payload = {
            "id": order_id,
            "order_id": order_id,
            "symbol": self._normalize_symbol(symbol),
            "side": str(side or "buy").lower(),
            "type": "market",
            "status": "filled",
            "amount": float(amount or 0.0),
            "filled": float(amount or 0.0),
            "price": execution_price,
            "average": execution_price,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paper": True,
        }
        self._remember_swap(payload)
        return payload

    async def _estimate_okx_buy_input_units(self, market: dict, target_output_units: int) -> Tuple[int, dict]:
        target_amount = self._units_to_amount(target_output_units, market["base_decimals"])
        ticker = await self.fetch_ticker(market["symbol"])
        reference_price = max(
            self._float(ticker.get("ask"), 0.0),
            self._float(ticker.get("last"), 0.0),
            0.0,
        ) or 1.0
        source_units = self._amount_to_units(
            max(target_amount, 0.0) * reference_price * 1.02,
            market["quote_decimals"],
        )
        best_quote = None
        for _ in range(6):
            quote = await self._quote_okx(
                market["quote_mint"],
                market["base_mint"],
                source_units,
            )
            best_quote = quote
            received_units = self._int(quote.get("toTokenAmount"), 0)
            if received_units >= target_output_units:
                return source_units, quote
            if received_units <= 0:
                source_units = max(source_units * 2, source_units + 1)
                continue
            ratio = target_output_units / float(received_units)
            source_units = max(source_units + 1, int(source_units * min(3.0, ratio * 1.05)))
        if best_quote is None:
            raise RuntimeError("OKX Trade API could not estimate the required input amount.")
        return source_units, best_quote

    async def _create_okx_order(
        self,
        market: dict,
        normalized_side: str,
        amount_value: float,
        normalized_type: str,
        slippage_bps: int,
    ):
        if not self.wallet_address:
            raise ValueError("Solana wallet address is required for OKX-routed live swaps.")
        if not self.secret:
            raise ValueError("Solana private key is required for OKX-routed live swaps.")

        slippage_percent = max(0.01, float(slippage_bps or self.DEFAULT_SLIPPAGE_BPS) / 100.0)
        if normalized_side == "sell":
            from_mint = market["base_mint"]
            to_mint = market["quote_mint"]
            input_units = self._amount_to_units(amount_value, market["base_decimals"])
            quote = await self._quote_okx(from_mint, to_mint, input_units)
        else:
            target_output_units = self._amount_to_units(amount_value, market["base_decimals"])
            input_units, quote = await self._estimate_okx_buy_input_units(market, target_output_units)
            from_mint = market["quote_mint"]
            to_mint = market["base_mint"]

        swap_payload = await self._request_okx(
            self.OKX_SWAP_PATH,
            params={
                "chainIndex": self.OKX_CHAIN_INDEX,
                "amount": max(1, int(input_units)),
                "fromTokenAddress": str(from_mint),
                "toTokenAddress": str(to_mint),
                "slippagePercent": f"{slippage_percent:.6g}",
                "userWalletAddress": self.wallet_address,
            },
        )
        swap_items = self._okx_data_items(swap_payload)
        swap_response = dict(swap_items[0]) if swap_items else {}
        tx_payload = dict(swap_response.get("tx") or {})
        unsigned_transaction = str(
            tx_payload.get("data")
            or tx_payload.get("txData")
            or tx_payload.get("callData")
            or ""
        ).strip()
        if not unsigned_transaction:
            raise RuntimeError("OKX did not return a Solana transaction payload.")

        signed_transaction = self._sign_serialized_transaction(unsigned_transaction, encoding="base58")
        signature = await self._send_signed_transaction(signed_transaction, encoding="base58")
        await self._wait_for_signature(signature)

        from_amount_units = self._int(quote.get("fromTokenAmount"), max(1, int(input_units)))
        to_amount_units = self._int(quote.get("toTokenAmount"), 0)
        if normalized_side == "sell":
            filled_amount = self._units_to_amount(from_amount_units, market["base_decimals"])
            cost = self._units_to_amount(to_amount_units, market["quote_decimals"])
        else:
            filled_amount = self._units_to_amount(to_amount_units, market["base_decimals"])
            cost = self._units_to_amount(from_amount_units, market["quote_decimals"])

        average_price = (cost / filled_amount) if filled_amount > 0 else 0.0
        payload = {
            "id": signature,
            "order_id": signature,
            "symbol": market["symbol"],
            "side": normalized_side,
            "type": normalized_type,
            "status": "filled",
            "amount": amount_value,
            "filled": filled_amount,
            "price": average_price,
            "average": average_price,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "txid": signature,
            "raw": {
                "quote": quote,
                "swap": swap_response,
            },
        }
        self._remember_swap(payload)
        return payload

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
        _ = price, stop_price, stop_loss, take_profit
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_side = str(side or "").strip().lower()
        normalized_type = str(type or "market").strip().lower()
        request_params = dict(params or {})

        if normalized_type != "market":
            raise ValueError("Solana broker currently supports market swaps only.")
        if normalized_side not in {"buy", "sell"}:
            raise ValueError("Solana order side must be buy or sell.")

        amount_value = float(amount or 0.0)
        if amount_value <= 0:
            raise ValueError("Order amount must be positive.")

        if self.sandbox or self.mode == "paper":
            return await self._simulate_order(normalized_symbol, normalized_side, amount_value)

        if not self.wallet_address:
            raise ValueError("Solana wallet address is required for live swaps.")
        if not self.secret:
            raise ValueError("Solana private key is required for live swaps.")

        market = await self._resolve_market(normalized_symbol)
        slippage_bps = self._int(
            request_params.get("slippage_bps")
            or self.params.get("slippage_bps")
            or self.options.get("slippage_bps")
            or self.DEFAULT_SLIPPAGE_BPS,
            self.DEFAULT_SLIPPAGE_BPS,
        )
        if self._uses_okx_swaps():
            return await self._create_okx_order(
                market,
                normalized_side,
                amount_value,
                normalized_type,
                slippage_bps,
            )

        if not self.jupiter_api_key:
            raise ValueError(
                "Jupiter API key is required for live Solana swaps when OKX Trade API credentials are not configured."
            )

        if normalized_side == "buy":
            quote_response = await self._request_jupiter(
                "GET",
                self.JUPITER_QUOTE_URL,
                params={
                    "inputMint": market["quote_mint"],
                    "outputMint": market["base_mint"],
                    "amount": self._amount_to_units(amount_value, market["base_decimals"]),
                    "slippageBps": max(1, slippage_bps),
                    "swapMode": "ExactOut",
                },
            )
        else:
            quote_response = await self._request_jupiter(
                "GET",
                self.JUPITER_QUOTE_URL,
                params={
                    "inputMint": market["base_mint"],
                    "outputMint": market["quote_mint"],
                    "amount": self._amount_to_units(amount_value, market["base_decimals"]),
                    "slippageBps": max(1, slippage_bps),
                    "swapMode": "ExactIn",
                },
            )

        swap_response = await self._request_jupiter(
            "POST",
            self.JUPITER_SWAP_URL,
            payload={
                "quoteResponse": quote_response,
                "userPublicKey": self.wallet_address,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
            },
        )

        unsigned_transaction = str(
            swap_response.get("swapTransaction")
            or swap_response.get("transaction")
            or ""
        ).strip()
        if not unsigned_transaction:
            raise RuntimeError("Jupiter did not return a swap transaction.")

        signed_transaction = self._sign_serialized_transaction(unsigned_transaction)
        signature = await self._send_signed_transaction(signed_transaction)
        await self._wait_for_signature(signature)

        in_amount = self._int(quote_response.get("inAmount"), 0)
        out_amount = self._int(quote_response.get("outAmount"), 0)
        if normalized_side == "buy":
            filled_amount = self._units_to_amount(out_amount, market["base_decimals"])
            cost = self._units_to_amount(in_amount, market["quote_decimals"])
        else:
            filled_amount = self._units_to_amount(in_amount, market["base_decimals"])
            cost = self._units_to_amount(out_amount, market["quote_decimals"])

        average_price = (cost / filled_amount) if filled_amount > 0 else 0.0
        payload = {
            "id": signature,
            "order_id": signature,
            "symbol": market["symbol"],
            "side": normalized_side,
            "type": normalized_type,
            "status": "filled",
            "amount": amount_value,
            "filled": filled_amount,
            "price": average_price,
            "average": average_price,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "txid": signature,
            "raw": {
                "quote": quote_response,
                "swap": swap_response,
            },
        }
        self._remember_swap(payload)
        return payload

    async def cancel_order(self, order_id, symbol=None):
        return {
            "id": str(order_id),
            "symbol": self._normalize_symbol(symbol) if symbol else None,
            "status": "unsupported",
            "reason": "Solana swaps settle immediately and cannot be canceled after submission.",
        }
