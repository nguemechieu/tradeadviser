from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional

from broker.base_broker import BaseDerivativeBroker
from models.instrument import Instrument, InstrumentType
from models.order import Order, OrderType
from models.position import Position


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


class AMPFuturesBroker(BaseDerivativeBroker):
    supported_instrument_types = {InstrumentType.FUTURE.value}

    def __init__(self, config, event_bus=None):
        super().__init__(config, event_bus=event_bus)
        self.endpoints = {
            "login": self.options.get("login_path") or "/sessions",
            "accounts": self.options.get("accounts_path") or "/accounts",
            "positions": self.options.get("positions_path") or "/positions",
            "orders": self.options.get("orders_path") or "/orders",
            "cancel_order": self.options.get("cancel_order_path") or "/orders/{order_id}/cancel",
            "quotes": self.options.get("quotes_path") or "/quotes",
            "contracts": self.options.get("contracts_path") or "/contracts",
        }
        self.default_multiplier = _safe_float(self.options.get("default_multiplier", 50.0), 50.0)

    def default_base_url(self):
        return str(self.options.get("base_url") or self.params.get("base_url") or "https://api.ampfutures.com/v1").rstrip("/")

    def _auth_headers(self):
        headers = super()._auth_headers()
        if self.api_key:
            headers.setdefault("X-API-Key", self.api_key)
        if self.secret:
            headers.setdefault("X-API-Secret", self.secret)
        return headers

    async def _authenticate(self):
        if self.access_token:
            return
        if not self.username or not self.password:
            return
        payload = {
            "username": self.username,
            "password": self.password,
            "apiKey": self.api_key,
            "secret": self.secret,
        }
        response = await self._request_json(
            "POST",
            self.endpoints["login"],
            json_payload={key: value for key, value in payload.items() if value},
            expected_statuses=(200, 201),
        )
        self.access_token = response.get("access_token") or response.get("token") or self.access_token
        self.account_id = response.get("account_id") or response.get("accountId") or self.account_id

    async def _resolve_account_id(self) -> str:
        if self.account_id:
            return str(self.account_id)
        payload = await self._request_json("GET", self.endpoints["accounts"])
        accounts = payload if isinstance(payload, list) else payload.get("accounts") or []
        if not accounts:
            raise RuntimeError("No AMP Futures accounts were returned")
        selected = accounts[0]
        self.account_id = str(selected.get("id") or selected.get("accountId") or selected.get("account") or "")
        return self.account_id

    def _instrument_from_payload(self, symbol: str, raw: Mapping[str, Any]) -> Instrument:
        multiplier = _safe_float(raw.get("multiplier", raw.get("contractSize", self.default_multiplier)), self.default_multiplier)
        return Instrument(
            symbol=symbol,
            type=InstrumentType.FUTURE,
            expiry=raw.get("expiry") or raw.get("expirationDate"),
            contract_size=int(multiplier),
            exchange=raw.get("exchange") or self.exchange_name,
            currency=raw.get("currency") or "USD",
            multiplier=multiplier,
            metadata=dict(raw),
        )

    def _normalize_account(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        equity = _safe_float(raw.get("equity", raw.get("netLiq", raw.get("balance", 0.0))))
        margin_used = _safe_float(raw.get("marginUsed", raw.get("initialMargin", 0.0)))
        return {
            "broker": self.exchange_name,
            "account_id": self.account_id,
            "currency": raw.get("currency") or "USD",
            "cash": _safe_float(raw.get("cash", raw.get("cashBalance", 0.0))),
            "equity": equity,
            "buying_power": _safe_float(raw.get("buyingPower", max(equity - margin_used, 0.0))),
            "margin_used": margin_used,
            "maintenance_requirement": _safe_float(raw.get("maintenanceMargin", raw.get("maintenanceRequirement", 0.0))),
            "available_funds": _safe_float(raw.get("availableFunds", raw.get("availableBalance", 0.0))),
            "raw": dict(raw),
        }

    def _normalize_position(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        symbol = str(raw.get("symbol") or raw.get("contract") or raw.get("instrument") or "").strip().upper()
        instrument = self._instrument_from_payload(symbol, raw)
        quantity = _safe_float(raw.get("quantity", raw.get("netPosition", raw.get("qty", 0.0))))
        position = Position(
            symbol=symbol,
            quantity=quantity,
            side="long" if quantity >= 0 else "short",
            instrument=instrument,
            avg_price=_safe_float(raw.get("averagePrice", raw.get("avgPrice", 0.0))),
            mark_price=_safe_float(raw.get("markPrice", raw.get("lastPrice", 0.0))) or None,
            leverage=_safe_float(raw.get("leverage", 0.0)) or None,
            margin_used=_safe_float(raw.get("marginUsed", raw.get("initialMargin", 0.0))),
            liquidation_price=_safe_float(raw.get("liquidationPrice", 0.0)) or None,
            unrealized_pnl=_safe_float(raw.get("unrealizedPnl", raw.get("openPnL", 0.0))),
            realized_pnl=_safe_float(raw.get("realizedPnl", raw.get("closedPnL", 0.0))),
            broker=self.exchange_name,
            account_id=self.account_id,
            metadata=dict(raw),
        )
        return position.to_dict()

    async def get_account_info(self):
        account_id = await self._resolve_account_id()
        payload = await self._request_json("GET", f"{self.endpoints['accounts']}/{account_id}")
        account = payload.get("account") if isinstance(payload, Mapping) and "account" in payload else payload
        normalized = self._normalize_account(account if isinstance(account, Mapping) else {})
        await self._emit_account_event(normalized)
        return normalized

    async def get_positions(self):
        account_id = await self._resolve_account_id()
        payload = await self._request_json("GET", self.endpoints["positions"], params={"accountId": account_id})
        positions = payload if isinstance(payload, list) else payload.get("positions") or []
        normalized = [self._normalize_position(item) for item in positions]
        for position in normalized:
            await self._emit_position_event(position)
        return normalized

    def _order_type_code(self, order: Order) -> str:
        mapping = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP: "stop",
            OrderType.STOP_LIMIT: "stop_limit",
            OrderType.BRACKET: "bracket",
        }
        return mapping.get(order.order_type, "market")

    async def place_order(self, order):
        order = Order.from_mapping(order)
        account_id = order.account_id or await self._resolve_account_id()
        instrument = order.instrument or Instrument(symbol=order.symbol, type=InstrumentType.FUTURE, exchange=self.exchange_name)
        payload = {
            "accountId": account_id,
            "symbol": instrument.symbol,
            "side": order.side.value,
            "quantity": abs(order.quantity),
            "orderType": self._order_type_code(order),
            "timeInForce": order.time_in_force,
            "clientOrderId": order.client_order_id,
            "expiry": instrument.expiry.isoformat() if instrument.expiry else None,
        }
        if order.price is not None:
            payload["price"] = float(order.price)
        if order.stop_price is not None:
            payload["stopPrice"] = float(order.stop_price)
        if order.take_profit is not None:
            payload["takeProfit"] = float(order.take_profit)
        if order.stop_loss is not None:
            payload["stopLoss"] = float(order.stop_loss)
        payload.update({key: value for key, value in dict(order.params or {}).items() if key not in payload})

        response = await self._request_json(
            "POST",
            self.endpoints["orders"],
            json_payload={key: value for key, value in payload.items() if value is not None},
            expected_statuses=(200, 201, 202),
        )
        normalized = {
            "id": response.get("orderId") or response.get("id") or payload.get("clientOrderId"),
            "clientOrderId": payload.get("clientOrderId"),
            "broker": self.exchange_name,
            "account_id": account_id,
            "symbol": instrument.symbol,
            "side": order.side.value,
            "amount": order.quantity,
            "type": order.order_type.value,
            "price": order.price,
            "stop_price": order.stop_price,
            "status": str(response.get("status") or "submitted").strip().lower(),
            "raw": response,
        }
        await self._emit_order_event(normalized)
        return normalized

    async def cancel_order(self, order_id, symbol=None):
        path = self.endpoints["cancel_order"].format(order_id=order_id)
        payload = await self._request_json(
            "POST",
            path,
            json_payload={"orderId": order_id},
            expected_statuses=(200, 202, 204),
        )
        normalized = {
            "id": str(order_id),
            "symbol": symbol,
            "broker": self.exchange_name,
            "status": str((payload or {}).get("status") or "canceled").strip().lower(),
            "raw": payload or {},
        }
        await self._emit_order_event(normalized)
        return normalized

    async def _fetch_quotes(self, symbols):
        normalized_symbols = [str(symbol).strip().upper() for symbol in (symbols or []) if str(symbol).strip()]
        if not normalized_symbols:
            return []
        payload = await self._request_json(
            "GET",
            self.endpoints["quotes"],
            params={"symbols": ",".join(normalized_symbols)},
        )
        items = payload if isinstance(payload, list) else payload.get("quotes") or payload.get("data") or []
        quote_map = {}
        for item in items:
            if isinstance(item, Mapping):
                quote_map[str(item.get("symbol") or item.get("contract") or "").upper()] = dict(item)
        quotes = []
        for symbol in normalized_symbols:
            raw = quote_map.get(symbol, {})
            quotes.append(
                {
                    "broker": self.exchange_name,
                    "symbol": symbol,
                    "bid": _safe_float(raw.get("bid", 0.0)),
                    "ask": _safe_float(raw.get("ask", 0.0)),
                    "last": _safe_float(raw.get("last", raw.get("trade", 0.0))),
                    "close": _safe_float(raw.get("close", 0.0)),
                    "mark": _safe_float(raw.get("mark", raw.get("last", 0.0))),
                    "timestamp": raw.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                    "raw": raw,
                }
            )
        return quotes

    async def _list_orders(self, status=None, symbol=None, limit=None):
        account_id = await self._resolve_account_id()
        payload = await self._request_json("GET", self.endpoints["orders"], params={"accountId": account_id, "limit": limit or 100})
        orders = payload if isinstance(payload, list) else payload.get("orders") or []
        normalized = []
        for raw in orders:
            raw_symbol = raw.get("symbol") or raw.get("contract")
            raw_status = str(raw.get("status") or "unknown").strip().lower()
            if symbol and str(raw_symbol).upper() != str(symbol).upper():
                continue
            if status == "open" and raw_status in {"filled", "canceled", "cancelled", "rejected"}:
                continue
            if status == "closed" and raw_status not in {"filled", "canceled", "cancelled", "rejected"}:
                continue
            normalized.append(
                {
                    "id": raw.get("orderId") or raw.get("id"),
                    "broker": self.exchange_name,
                    "account_id": account_id,
                    "symbol": raw_symbol,
                    "side": str(raw.get("side") or "").lower(),
                    "amount": _safe_float(raw.get("quantity", raw.get("qty", 0.0))),
                    "filled": _safe_float(raw.get("filledQuantity", raw.get("filled", 0.0))),
                    "price": _safe_float(raw.get("price", 0.0)) or None,
                    "stop_price": _safe_float(raw.get("stopPrice", 0.0)) or None,
                    "status": raw_status,
                    "timestamp": raw.get("updatedAt") or raw.get("timestamp"),
                    "raw": dict(raw),
                }
            )
        return normalized[: int(limit or len(normalized))]

    async def _get_order(self, order_id, symbol=None):
        for order in await self._list_orders(symbol=symbol):
            if str(order.get("id")) == str(order_id):
                return order
        return None

    async def get_contract_metadata(self, symbol, **kwargs):
        payload = await self._request_json(
            "GET",
            self.endpoints["contracts"],
            params={"symbol": str(symbol).strip().upper(), **kwargs},
        )
        records = payload if isinstance(payload, list) else payload.get("contracts") or payload.get("data") or []
        raw = records[0] if records else {}
        instrument = self._instrument_from_payload(str(symbol).strip().upper(), raw)
        return {
            "broker": self.exchange_name,
            "symbol": instrument.symbol,
            "exchange": instrument.exchange,
            "currency": instrument.currency,
            "tick_size": _safe_float(raw.get("tickSize", raw.get("tick", 0.0))),
            "multiplier": instrument.multiplier,
            "initial_margin": _safe_float(raw.get("initialMargin", 0.0)),
            "maintenance_margin": _safe_float(raw.get("maintenanceMargin", 0.0)),
            "expiry": instrument.expiry.isoformat() if instrument.expiry else None,
            "last_trade_at": _safe_datetime(raw.get("lastTradeAt")).isoformat() if _safe_datetime(raw.get("lastTradeAt")) else None,
            "raw": raw,
        }
