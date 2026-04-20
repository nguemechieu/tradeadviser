from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from broker.ibkr.exceptions import IBKRApiError, IBKROrderRejectedError
from broker.ibkr.mapper import IBKRMapper
from broker.ibkr.models import IBKRContract
from broker.ibkr.webapi import endpoints


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _timeframe_to_bar(timeframe: str) -> str:
    normalized = str(timeframe or "1h").strip().lower()
    mapping = {
        "1m": "1min",
        "2m": "2min",
        "3m": "3min",
        "5m": "5min",
        "10m": "10min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }
    return mapping.get(normalized, "1h")


def _period_from_limit(timeframe: str, limit: int | None) -> str:
    requested = max(1, int(limit or 120))
    bar = _timeframe_to_bar(timeframe)
    minute_bars = {
        "1min": 1,
        "2min": 2,
        "3min": 3,
        "5min": 5,
        "10min": 10,
        "15min": 15,
        "30min": 30,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
    }
    total_minutes = requested * minute_bars.get(bar, 60)
    if total_minutes <= 1440:
        days = max(1, (total_minutes + 1439) // 1440)
        return f"{days}d"
    if total_minutes <= 10080:
        weeks = max(1, (total_minutes + 10079) // 10080)
        return f"{weeks}w"
    months = max(1, (total_minutes + 43199) // 43200)
    return f"{months}m"


class IBKRWebApiClient:
    """Higher-level Web API operations built on top of the session/auth layers."""

    SNAPSHOT_FIELDS = "31,55,84,85,86,87,88,6008"

    def __init__(self, session, auth, mapper: IBKRMapper | None = None, *, logger: logging.Logger | None = None) -> None:
        self.session = session
        self.auth = auth
        self.mapper = mapper or IBKRMapper()
        self.logger = logger or logging.getLogger("IBKRWebApiClient")
        self.contract_cache: dict[str, IBKRContract] = {}

    async def ensure_ready(self) -> None:
        await self.auth.bootstrap()

    async def get_accounts(self) -> list[dict[str, Any]]:
        await self.ensure_ready()
        payload = await self.session.request_json("GET", endpoints.ACCOUNTS, expected_statuses=(200,))
        accounts = payload if isinstance(payload, list) else payload.get("accounts") or []
        normalized = [
            self.mapper.canonical_account(self.mapper.account_from_accounts_payload(item))
            for item in accounts
            if isinstance(item, Mapping)
        ]
        if normalized and not self.session.state.account_id:
            self.session.state.account_id = normalized[0]["account_id"]
        return normalized

    async def get_account_balances(self, account_id: str) -> dict[str, Any]:
        await self.ensure_ready()
        payload = await self.session.request_json(
            "GET",
            endpoints.ACCOUNT_SUMMARY.format(account_id=account_id),
            expected_statuses=(200,),
        )
        balance = self.mapper.balance_from_summary(payload if isinstance(payload, Mapping) else {}, account_id=account_id)
        return self.mapper.canonical_balance(balance)

    async def get_positions(self, account_id: str) -> list[dict[str, Any]]:
        await self.ensure_ready()
        payload = await self.session.request_json(
            "GET",
            endpoints.POSITIONS.format(account_id=account_id),
            expected_statuses=(200,),
        )
        rows = payload if isinstance(payload, list) else payload.get("positions") or []
        normalized = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            position = self.mapper.position_from_payload(row, account_id=account_id)
            normalized.append(self.mapper.canonical_position(position))
        return normalized

    async def resolve_contract(self, symbol: str, *, sec_type: str | None = None) -> IBKRContract:
        normalized_symbol = str(symbol or "").strip().upper()
        cached = self.contract_cache.get(normalized_symbol)
        if cached is not None:
            return cached
        params = {"symbol": normalized_symbol}
        if sec_type:
            params["secType"] = str(sec_type).strip().upper()
        payload = await self.session.request_json("GET", endpoints.SECDEF_SEARCH, params=params, expected_statuses=(200,))
        rows = payload if isinstance(payload, list) else payload.get("results") or payload.get("contracts") or []
        if not rows:
            raise IBKRApiError(f"IBKR could not resolve a contract for {normalized_symbol}")
        contract = self.mapper.contract_from_payload(rows[0], default_symbol=normalized_symbol)
        self.contract_cache[normalized_symbol] = contract
        return contract

    async def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        await self.ensure_ready()
        resolved = []
        for symbol in symbols:
            contract = await self.resolve_contract(symbol)
            resolved.append((str(symbol).strip().upper(), contract))
        conids = ",".join(str(contract.conid or "") for _, contract in resolved if contract.conid)
        if not conids:
            return []

        snapshot = await self.session.request_json(
            "GET",
            endpoints.MARKET_SNAPSHOT,
            params={"conids": conids, "fields": self.SNAPSHOT_FIELDS},
            expected_statuses=(200,),
        )
        rows = snapshot if isinstance(snapshot, list) else snapshot.get("data") or []
        snapshot_map = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            conid = str(row.get("conid") or row.get("conidEx") or "")
            snapshot_map[conid] = row

        quotes = []
        missing_symbols = []
        for normalized_symbol, contract in resolved:
            raw = snapshot_map.get(str(contract.conid or ""))
            if raw is None or not any(raw.get(tag) not in (None, "") for tag in ("31", "84", "86", "6008")):
                missing_symbols.append((normalized_symbol, contract))
                continue
            quote = self.mapper.quote_from_snapshot(raw, symbol=normalized_symbol, contract=contract)
            quotes.append(self.mapper.canonical_quote(quote))

        if missing_symbols:
            await asyncio.sleep(0.05)
            warmed = await self.session.request_json(
                "GET",
                endpoints.MARKET_SNAPSHOT,
                params={
                    "conids": ",".join(str(contract.conid or "") for _, contract in missing_symbols if contract.conid),
                    "fields": self.SNAPSHOT_FIELDS,
                },
                expected_statuses=(200,),
            )
            warm_rows = warmed if isinstance(warmed, list) else warmed.get("data") or []
            warm_map = {
                str(row.get("conid") or row.get("conidEx") or ""): row
                for row in warm_rows
                if isinstance(row, Mapping)
            }
            for normalized_symbol, contract in missing_symbols:
                raw = warm_map.get(str(contract.conid or ""), {})
                quote = self.mapper.quote_from_snapshot(raw, symbol=normalized_symbol, contract=contract)
                quotes.append(self.mapper.canonical_quote(quote))
        return quotes

    async def get_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        await self.ensure_ready()
        contract = await self.resolve_contract(symbol)
        period = _period_from_limit(timeframe, limit)
        if start is not None and end is not None and end > start:
            delta_days = max(1, int((end - start).total_seconds() // 86400) + 1)
            period = f"{delta_days}d"
        payload = await self.session.request_json(
            "GET",
            endpoints.MARKET_HISTORY,
            params={
                "conid": contract.conid,
                "bar": _timeframe_to_bar(timeframe),
                "period": period,
                "outsideRth": "true",
            },
            expected_statuses=(200,),
        )
        bars = self.mapper.historical_bars_from_payload(payload if isinstance(payload, Mapping) else {}, symbol=str(symbol).strip().upper())
        if limit is not None and len(bars) > int(limit):
            return bars[-int(limit) :]
        return bars

    async def list_orders(self, *, symbol: str | None = None, status: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        await self.ensure_ready()
        payload = await self.session.request_json("GET", endpoints.LIVE_ORDERS, expected_statuses=(200,))
        rows = payload if isinstance(payload, list) else payload.get("orders") or []
        normalized = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            raw_symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
            raw_status = str(row.get("status") or row.get("order_status") or "unknown").strip().lower()
            if symbol and raw_symbol != str(symbol).strip().upper():
                continue
            if status == "open" and raw_status in {"filled", "cancelled", "canceled", "inactive", "rejected"}:
                continue
            if status == "closed" and raw_status not in {"filled", "cancelled", "canceled", "inactive", "rejected"}:
                continue
            normalized.append(
                {
                    "id": row.get("orderId") or row.get("order_id"),
                    "broker": "ibkr",
                    "account_id": row.get("acct") or row.get("account") or self.session.state.account_id,
                    "symbol": raw_symbol,
                    "side": str(row.get("side") or "").strip().lower(),
                    "amount": _safe_float(row.get("size", row.get("quantity", 0.0)), 0.0),
                    "filled": _safe_float(row.get("filledQuantity", row.get("filled", 0.0)), 0.0),
                    "price": _safe_float(row.get("price", 0.0), 0.0) or None,
                    "status": raw_status,
                    "timestamp": row.get("lastExecutionTime") or row.get("created"),
                    "raw": dict(row),
                }
            )
        if limit is not None:
            return normalized[: int(limit)]
        return normalized

    async def place_order(self, account_id: str, order: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_ready()
        contract = await self.resolve_contract(order.get("symbol") or "")
        request = self.mapper.order_request_from_order(order, account_id=account_id, contract=contract)
        payload = {"orders": [self.mapper.webapi_order_payload(request)]}
        response = await self.session.request_json(
            "POST",
            endpoints.PLACE_ORDERS.format(account_id=account_id),
            json_payload=payload,
            expected_statuses=(200, 201),
        )
        result = response[0] if isinstance(response, list) and response else response
        if isinstance(result, Mapping) and str(result.get("status") or "").strip().lower() in {"rejected", "error"}:
            raise IBKROrderRejectedError(str(result.get("message") or "IBKR rejected the order."))
        normalized = self.mapper.order_response_from_payload(
            result if isinstance(result, Mapping) else {},
            request=request,
        )
        return self.mapper.canonical_order_response(normalized)

    async def cancel_order(self, account_id: str, order_id: str, *, symbol: str | None = None) -> dict[str, Any]:
        await self.ensure_ready()
        payload = await self.session.request_json(
            "DELETE",
            endpoints.CANCEL_ORDER.format(account_id=account_id, order_id=order_id),
            expected_statuses=(200, 202, 204),
        )
        return {
            "id": str(order_id),
            "broker": "ibkr",
            "account_id": account_id,
            "symbol": symbol,
            "status": str((payload or {}).get("status") or "canceled").strip().lower(),
            "raw": payload or {},
        }
