from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional in stripped test environments
    aiohttp = None

from . import endpoints
from .auth import SchwabOAuthService
from .config import SchwabConfig
from .exceptions import (
    SchwabApiError,
    SchwabAuthError,
    SchwabConfigurationError,
    SchwabConnectionError,
    SchwabOrderRejectedError,
    SchwabRateLimitError,
)
from .mapper import SchwabMapper


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _timeframe_to_seconds(value: str) -> int:
    normalized = str(value or "1h").strip().lower()
    mapping = {
        "1m": 60,
        "5m": 300,
        "10m": 600,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
        "1w": 604800,
    }
    return mapping.get(normalized, 3600)


def _normalize_time_boundary(value: Any, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        timestamp = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if "T" not in text and len(text) <= 10:
            text = (
                f"{text}T23:59:59.999999+00:00"
                if end_of_day
                else f"{text}T00:00:00+00:00"
            )
        text = text.replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(text)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


class SchwabApiClient:
    """Async Schwab REST client with OAuth bearer injection and refresh handling."""

    _TIMEFRAME_PLAN = {
        "1m": {"frequency_type": "minute", "frequency": 1, "aggregate": 1},
        "5m": {"frequency_type": "minute", "frequency": 5, "aggregate": 1},
        "10m": {"frequency_type": "minute", "frequency": 10, "aggregate": 1},
        "15m": {"frequency_type": "minute", "frequency": 15, "aggregate": 1},
        "30m": {"frequency_type": "minute", "frequency": 30, "aggregate": 1},
        "1h": {"frequency_type": "minute", "frequency": 30, "aggregate": 2},
        "4h": {"frequency_type": "minute", "frequency": 30, "aggregate": 8},
        "1d": {"frequency_type": "daily", "frequency": 1, "aggregate": 1},
        "1w": {"frequency_type": "daily", "frequency": 1, "aggregate": 5},
    }

    def __init__(
        self,
        config: SchwabConfig,
        auth: SchwabOAuthService,
        *,
        mapper: SchwabMapper | None = None,
        logger: logging.Logger | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.config = config
        self.auth = auth
        self.mapper = mapper or SchwabMapper()
        self.logger = logger or logging.getLogger("SchwabApiClient")
        self._session = session

    async def open(self):
        if self._session is None or self._session.closed:
            if aiohttp is None:
                raise SchwabConfigurationError("aiohttp is required for Schwab API access.")
            timeout = aiohttp.ClientTimeout(total=max(1.0, float(self.config.timeout_seconds)))
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None and not session.closed:
            await session.close()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_payload: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        base_url: str | None = None,
        expected_statuses: tuple[int, ...] = (200,),
        retry_auth: bool = True,
        include_meta: bool = False,
        require_auth: bool = True,
    ) -> Any:
        session = await self.open()
        assert session is not None

        method_upper = str(method or "GET").strip().upper() or "GET"
        request_headers = {
            "Accept": "application/json",
            "X-Api-Key": self.config.client_id,
        }
        request_headers.update(dict(headers or {}))
        if require_auth:
            tokens = await self.auth.ensure_session(interactive=False)
            if tokens.access_token:
                request_headers["Authorization"] = f"{tokens.token_type or 'Bearer'} {tokens.access_token}"

        root = str(base_url or self.config.trader_base_url or "").rstrip("/")
        url = str(path or "")
        if not url.startswith("http"):
            url = f"{root}/{url.lstrip('/')}"

        idempotent = method_upper in {"GET", "HEAD"}
        max_attempts = 1 + (max(0, int(self.config.max_read_retries)) if idempotent else 0)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with session.request(
                    method_upper,
                    url,
                    params=dict(params or {}),
                    json=json_payload,
                    data=data,
                    headers=request_headers,
                ) as response:
                    payload = await self._parse_response_payload(response)
                    if response.status == 401 and require_auth and retry_auth:
                        self.logger.info("Schwab request received 401; attempting one token refresh.")
                        await self.auth.refresh_tokens()
                        return await self.request(
                            method_upper,
                            path,
                            params=params,
                            json_payload=json_payload,
                            data=data,
                            headers=headers,
                            base_url=base_url,
                            expected_statuses=expected_statuses,
                            retry_auth=False,
                            include_meta=include_meta,
                            require_auth=require_auth,
                        )
                    if response.status == 429:
                        raise SchwabRateLimitError(self._error_message(payload, response.status))
                    if response.status not in expected_statuses:
                        raise self._response_error(payload, response.status)
                    if include_meta:
                        return payload, dict(response.headers), response.status
                    return payload
            except SchwabRateLimitError:
                raise
            except (SchwabApiError, SchwabAuthError):
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                backoff = min(1.0, 0.15 * attempt)
                self.logger.warning(
                    "Schwab %s %s failed on attempt %s/%s; retrying in %.2fs",
                    method_upper,
                    url,
                    attempt,
                    max_attempts,
                    backoff,
                )
                await asyncio.sleep(backoff)
        raise SchwabConnectionError(f"Schwab request failed: {last_error}") from last_error

    async def get_accounts_raw(self) -> list[dict[str, Any]]:
        payload = await self.request("GET", endpoints.ACCOUNT_NUMBERS)
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, Mapping)]
        if isinstance(payload, Mapping):
            accounts = payload.get("accounts") or payload.get("accountNumbers") or []
            return [dict(item) for item in list(accounts or []) if isinstance(item, Mapping)]
        return []

    async def get_account_raw(self, account_hash: str, *, fields: str | None = None) -> dict[str, Any]:
        params = {"fields": fields} if fields else None
        payload = await self.request("GET", f"{endpoints.ACCOUNT}/{str(account_hash).strip()}", params=params)
        return dict(payload or {}) if isinstance(payload, Mapping) else {}

    async def get_quotes_raw(self, symbols: list[str]) -> dict[str, Any]:
        normalized = [_normalize_symbol(symbol) for symbol in list(symbols or []) if _normalize_symbol(symbol)]
        if not normalized:
            return {}
        payload = await self.request(
            "GET",
            endpoints.QUOTES,
            params={"symbols": ",".join(normalized)},
            base_url=self.config.market_data_base_url,
        )
        return dict(payload or {}) if isinstance(payload, Mapping) else {}

    async def list_orders_raw(
        self,
        account_hash: str,
        *,
        from_entered_time: str | None = None,
        to_entered_time: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "fromEnteredTime": from_entered_time or (_utc_now() - timedelta(days=max(1, int(self.config.orders_lookback_days)))).isoformat(),
            "toEnteredTime": to_entered_time or _utc_now().isoformat(),
            "maxResults": int(limit or self.config.orders_limit),
        }
        payload = await self.request("GET", f"{endpoints.ACCOUNT}/{str(account_hash).strip()}{endpoints.ORDERS}", params=params)
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, Mapping)]
        if isinstance(payload, Mapping):
            orders = payload.get("orders") or []
            return [dict(item) for item in list(orders or []) if isinstance(item, Mapping)]
        return []

    async def get_order_raw(self, account_hash: str, order_id: str) -> dict[str, Any]:
        payload = await self.request("GET", f"{endpoints.ACCOUNT}/{str(account_hash).strip()}{endpoints.ORDERS}/{str(order_id).strip()}")
        return dict(payload or {}) if isinstance(payload, Mapping) else {}

    async def place_order_raw(self, account_hash: str, payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str], int]:
        response_payload, headers, status = await self.request(
            "POST",
            f"{endpoints.ACCOUNT}/{str(account_hash).strip()}{endpoints.ORDERS}",
            json_payload=dict(payload or {}),
            expected_statuses=(200, 201, 202),
            include_meta=True,
        )
        return (dict(response_payload or {}) if isinstance(response_payload, Mapping) else {}), headers, int(status)

    async def cancel_order_raw(self, account_hash: str, order_id: str) -> tuple[dict[str, Any], dict[str, str], int]:
        response_payload, headers, status = await self.request(
            "DELETE",
            f"{endpoints.ACCOUNT}/{str(account_hash).strip()}{endpoints.ORDERS}/{str(order_id).strip()}",
            expected_statuses=(200, 202, 204),
            include_meta=True,
        )
        return (dict(response_payload or {}) if isinstance(response_payload, Mapping) else {}), headers, int(status)

    async def get_option_chain_raw(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
        params = {
            "symbol": _normalize_symbol(symbol),
            "contractType": kwargs.get("contract_type", "ALL"),
            "strikeCount": kwargs.get("strike_count", 20),
            "includeUnderlyingQuote": "TRUE",
        }
        if kwargs.get("strategy"):
            params["strategy"] = kwargs["strategy"]
        payload = await self.request(
            "GET",
            endpoints.OPTION_CHAINS,
            params=params,
            base_url=self.config.market_data_base_url,
        )
        return dict(payload or {}) if isinstance(payload, Mapping) else {}

    async def get_price_history_raw(
        self,
        symbol: str,
        timeframe: str,
        *,
        start: Any = None,
        end: Any = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized_timeframe = str(timeframe or "1h").strip().lower() or "1h"
        plan = dict(self._TIMEFRAME_PLAN.get(normalized_timeframe) or self._TIMEFRAME_PLAN["1h"])
        requested = max(2, int(limit or 100))
        aggregate = max(1, int(plan.get("aggregate") or 1))
        window_seconds = _timeframe_to_seconds(normalized_timeframe) * requested * max(1, aggregate) * 2
        start_boundary = _normalize_time_boundary(start, end_of_day=False)
        end_boundary = _normalize_time_boundary(end, end_of_day=True) or _utc_now()
        if start_boundary is None:
            start_boundary = end_boundary - timedelta(seconds=max(3600, window_seconds))
        params = {
            "symbol": _normalize_symbol(symbol),
            "frequencyType": str(plan["frequency_type"]),
            "frequency": int(plan["frequency"]),
            "needExtendedHoursData": "false",
            "needPreviousClose": "false",
            "startDate": int(start_boundary.timestamp() * 1000),
            "endDate": int(end_boundary.timestamp() * 1000),
        }
        payload = await self.request(
            "GET",
            endpoints.PRICE_HISTORY,
            params=params,
            base_url=self.config.market_data_base_url,
        )
        return dict(payload or {}) if isinstance(payload, Mapping) else {}

    async def get_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        *,
        start: Any = None,
        end: Any = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        payload = await self.get_price_history_raw(symbol, timeframe, start=start, end=end, limit=limit)
        normalized_timeframe = str(timeframe or "1h").strip().lower() or "1h"
        plan = dict(self._TIMEFRAME_PLAN.get(normalized_timeframe) or self._TIMEFRAME_PLAN["1h"])
        candles = self._normalize_candles(payload)
        candles = self._aggregate_candles(candles, int(plan.get("aggregate") or 1))
        requested = max(1, int(limit or len(candles) or 1))
        return candles[-requested:]

    async def get_accounts(self) -> list[dict[str, Any]]:
        return [self.mapper.canonical_account(self.mapper.account_from_number_entry(entry)) for entry in await self.get_accounts_raw()]

    async def get_account_balances(self, account_hash: str, *, account_id: str | None = None) -> dict[str, Any]:
        payload = await self.get_account_raw(account_hash, fields="positions")
        account = dict(payload.get("securitiesAccount") or payload)
        normalized_id = str(account_id or account.get("accountNumber") or account.get("accountId") or "").strip() or str(account_hash)
        balance = self.mapper.balance_from_account_payload(account, account_id=normalized_id, account_hash=account_hash)
        return self.mapper.canonical_balance(balance)

    async def get_positions(self, account_hash: str, *, account_id: str | None = None) -> list[dict[str, Any]]:
        payload = await self.get_account_raw(account_hash, fields="positions")
        account = dict(payload.get("securitiesAccount") or payload)
        normalized_id = str(account_id or account.get("accountNumber") or account.get("accountId") or "").strip() or str(account_hash)
        positions = []
        for entry in list(account.get("positions") or []):
            if not isinstance(entry, Mapping):
                continue
            position = self.mapper.position_from_payload(entry, account_id=normalized_id, account_hash=account_hash)
            positions.append(self.mapper.canonical_position(position))
        return positions

    async def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        normalized = [_normalize_symbol(symbol) for symbol in list(symbols or []) if _normalize_symbol(symbol)]
        payload = await self.get_quotes_raw(normalized)
        quotes = []
        for symbol in normalized:
            raw = payload.get(symbol) or payload.get(symbol.upper()) or {}
            if not isinstance(raw, Mapping):
                raw = {}
            quote = self.mapper.quote_from_payload(symbol, raw)
            quotes.append(self.mapper.canonical_quote(quote))
        return quotes

    async def list_orders(
        self,
        account_hash: str,
        *,
        account_id: str,
        symbol: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_symbol = _normalize_symbol(symbol) if symbol else ""
        normalized_status = str(status or "").strip().lower()
        payload = await self.list_orders_raw(account_hash, limit=limit)
        results = []
        for row in payload:
            normalized = self.mapper.canonical_order_from_raw(row, account_id=account_id)
            row_symbol = _normalize_symbol(normalized.get("symbol"))
            row_status = str(normalized.get("status") or "").strip().lower()
            if normalized_symbol and row_symbol != normalized_symbol:
                continue
            if normalized_status == "open" and row_status in {"filled", "canceled", "expired", "rejected"}:
                continue
            if normalized_status == "closed" and row_status not in {"filled", "canceled", "expired", "rejected"}:
                continue
            results.append(normalized)
        return results

    async def place_order(self, account_hash: str, account_id: str, order_request: Mapping[str, Any]) -> dict[str, Any]:
        normalized_request = self.mapper.order_request_from_order(order_request, account_id=account_id)
        payload = self.mapper.order_payload(normalized_request)
        body, headers, _status = await self.place_order_raw(account_hash, payload)
        location = str(headers.get("Location") or headers.get("location") or "").strip()
        order_id = location.rstrip("/").split("/")[-1] if location else str(body.get("orderId") or body.get("id") or "").strip()
        response = self.mapper.order_response_from_payload(body, request=normalized_request, order_id=order_id or None)
        return self.mapper.canonical_order_response(response)

    async def cancel_order(self, account_hash: str, account_id: str, order_id: str, *, symbol: str | None = None) -> dict[str, Any]:
        body, _headers, _status = await self.cancel_order_raw(account_hash, order_id)
        payload = {
            "id": str(order_id),
            "broker": "schwab",
            "account_id": account_id,
            "symbol": _normalize_symbol(symbol) if symbol else None,
            "status": "canceled",
            "raw": body,
        }
        return payload

    async def get_order(self, account_hash: str, account_id: str, order_id: str) -> dict[str, Any]:
        payload = await self.get_order_raw(account_hash, order_id)
        if not payload:
            return {}
        return self.mapper.canonical_order_from_raw(payload, account_id=account_id)

    async def get_option_chain(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
        payload = await self.get_option_chain_raw(symbol, **kwargs)
        return self.mapper.option_chain_from_payload(symbol, payload)

    async def _parse_response_payload(self, response: aiohttp.ClientResponse) -> Any:
        if response.status == 204:
            return {}
        text = await response.text()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    def _response_error(self, payload: Any, status: int) -> SchwabApiError:
        message = self._error_message(payload, status)
        if status in {400, 403, 404, 409, 422}:
            if status in {409, 422}:
                return SchwabOrderRejectedError(message)
            return SchwabApiError(message)
        if status in {401}:
            return SchwabAuthError(message)
        return SchwabApiError(message)

    @staticmethod
    def _error_message(payload: Any, status: int) -> str:
        if isinstance(payload, Mapping):
            for key in ("error_description", "message", "error", "description"):
                value = payload.get(key)
                text = str(value or "").strip()
                if text:
                    return text
        return f"Schwab API request failed with status {status}."

    @staticmethod
    def _normalize_candles(payload: Mapping[str, Any]) -> list[list[float]]:
        rows = []
        for candle in list(payload.get("candles") or []):
            if not isinstance(candle, Mapping):
                continue
            timestamp = _safe_float(candle.get("datetime"), 0.0)
            if timestamp <= 0:
                continue
            rows.append(
                [
                    int(timestamp),
                    _safe_float(candle.get("open"), 0.0),
                    _safe_float(candle.get("high"), 0.0),
                    _safe_float(candle.get("low"), 0.0),
                    _safe_float(candle.get("close"), 0.0),
                    _safe_float(candle.get("volume"), 0.0),
                ]
            )
        rows.sort(key=lambda item: item[0])
        return rows

    @staticmethod
    def _aggregate_candles(candles: list[list[float]], bucket_size: int) -> list[list[float]]:
        if bucket_size <= 1:
            return list(candles)
        aggregated = []
        bucket: list[list[float]] = []
        for candle in candles:
            bucket.append(list(candle))
            if len(bucket) < bucket_size:
                continue
            aggregated.append(
                [
                    bucket[0][0],
                    bucket[0][1],
                    max(row[2] for row in bucket),
                    min(row[3] for row in bucket),
                    bucket[-1][4],
                    sum(_safe_float(row[5], 0.0) for row in bucket),
                ]
            )
            bucket = []
        if not aggregated and bucket:
            aggregated.append(
                [
                    bucket[0][0],
                    bucket[0][1],
                    max(row[2] for row in bucket),
                    min(row[3] for row in bucket),
                    bucket[-1][4],
                    sum(_safe_float(row[5], 0.0) for row in bucket),
                ]
            )
        return aggregated
