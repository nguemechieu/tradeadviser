from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional

from broker.base_broker import BaseDerivativeBroker
from models.instrument import Instrument, InstrumentType
from models.order import Order, OrderSide, OrderType
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


class TradovateBroker(BaseDerivativeBroker):
    supported_instrument_types = {InstrumentType.FUTURE.value}

    def __init__(self, config, event_bus=None):
        super().__init__(config, event_bus=event_bus)
        self.app_id = self.options.get("app_id") or self.params.get("app_id") or "SopotekTradingAI"
        self.app_version = self.options.get("app_version") or self.params.get("app_version") or "1.0"
        self.device_id = self.options.get("device_id") or self.params.get("device_id")
        self.company_id = self.options.get("company_id") or self.params.get("company_id") or self.api_key
        self.security_code = self.options.get("security_code") or self.params.get("security_code") or self.secret
        self.contract_cache = {}
        self.default_multiplier = _safe_float(self.options.get("default_multiplier", 50.0), 50.0)

    def default_base_url(self):
        if self.mode == "live":
            return "https://live.tradovateapi.com/v1"
        return "https://demo.tradovateapi.com/v1"

    def default_ws_url(self):
        if self.mode == "live":
            return "wss://live.tradovateapi.com/v1/websocket"
        return "wss://demo.tradovateapi.com/v1/websocket"

    async def _authenticate(self):
        if self.access_token:
            return
        if not self.username or not self.password:
            return
        payload = {
            "name": self.username,
            "password": self.password,
            "appId": self.app_id,
            "appVersion": self.app_version,
            "cid": self.company_id,
            "sec": self.security_code,
            "deviceId": self.device_id,
        }
        response = await self._request_json(
            "POST",
            self.options.get("login_path") or "/auth/accesstokenrequest",
            json_payload={key: value for key, value in payload.items() if value is not None},
            expected_statuses=(200, 201),
        )
        self.access_token = response.get("accessToken") or response.get("access_token") or self.access_token
        self.account_id = response.get("accountId") or self.account_id

    async def _resolve_account_id(self) -> str:
        if self.account_id:
            return str(self.account_id)
        payload = await self._request_json("GET", self.options.get("accounts_path") or "/account/list")
        accounts = payload if isinstance(payload, list) else payload.get("accounts") or []
        if not accounts:
            raise RuntimeError("No Tradovate accounts were returned")
        selected = accounts[0]
        self.account_id = str(selected.get("id") or selected.get("accountId") or selected.get("name") or "")
        return self.account_id

    def _instrument_from_payload(self, raw: Mapping[str, Any]) -> Instrument:
        multiplier = _safe_float(raw.get("contractSize", raw.get("multiplier", self.default_multiplier)), self.default_multiplier)
        return Instrument(
            symbol=raw.get("name") or raw.get("symbol") or raw.get("contract"),
            type=InstrumentType.FUTURE,
            expiry=raw.get("expirationDate") or raw.get("expiry"),
            contract_size=int(multiplier),
            exchange=raw.get("exchange") or self.exchange_name,
            currency=raw.get("currency") or "USD",
            multiplier=multiplier,
            metadata=dict(raw),
        )

    async def _resolve_contract_id(self, symbol: str) -> Any:
        normalized = str(symbol).strip().upper()
        if normalized in self.contract_cache:
            return self.contract_cache[normalized]
        payload = await self._request_json(
            "GET",
            self.options.get("contract_search_path") or "/contract/find",
            params={"name": normalized},
        )
        records = payload if isinstance(payload, list) else payload.get("contracts") or payload.get("data") or []
        if not records:
            raise RuntimeError(f"Tradovate contract id could not be resolved for {symbol}")
        contract_id = records[0].get("id") or records[0].get("contractId")
        self.contract_cache[normalized] = contract_id
        return contract_id

    def _normalize_account(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        cash = _safe_float(raw.get("cashBalance", raw.get("cash", 0.0)))
        equity = _safe_float(raw.get("netLiq", raw.get("equity", cash)))
        margin_used = _safe_float(raw.get("marginUsed", raw.get("initialMargin", 0.0)))
        return {
            "broker": self.exchange_name,
            "account_id": self.account_id,
            "currency": raw.get("currency") or "USD",
            "cash": cash,
            "equity": equity,
            "buying_power": _safe_float(raw.get("buyingPower", max(equity - margin_used, 0.0))),
            "margin_used": margin_used,
            "maintenance_requirement": _safe_float(raw.get("maintenanceMargin", 0.0)),
            "available_funds": _safe_float(raw.get("availableFunds", raw.get("availableBalance", 0.0))),
            "raw": dict(raw),
        }

    def _normalize_position(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        symbol = str(raw.get("contractName") or raw.get("symbol") or raw.get("name") or "").strip().upper()
        instrument = self._instrument_from_payload({"name": symbol, **dict(raw)})
        quantity = _safe_float(raw.get("netPos", raw.get("quantity", raw.get("netPosition", 0.0))))
        position = Position(
            symbol=symbol,
            quantity=quantity,
            side="long" if quantity >= 0 else "short",
            instrument=instrument,
            avg_price=_safe_float(raw.get("netPrice", raw.get("averagePrice", 0.0))),
            mark_price=_safe_float(raw.get("lastPrice", raw.get("markPrice", 0.0))) or None,
            leverage=_safe_float(raw.get("leverage", 0.0)) or None,
            margin_used=_safe_float(raw.get("marginUsed", raw.get("initialMargin", 0.0))),
            liquidation_price=_safe_float(raw.get("liquidationPrice", 0.0)) or None,
            unrealized_pnl=_safe_float(raw.get("unrealizedPnL", raw.get("openPnL", 0.0))),
            realized_pnl=_safe_float(raw.get("realizedPnL", raw.get("closedPnL", 0.0))),
            broker=self.exchange_name,
            account_id=self.account_id,
            metadata=dict(raw),
        )
        return position.to_dict()

    async def get_account_info(self):
        account_id = await self._resolve_account_id()
        payload = await self._request_json("GET", self.options.get("account_item_path") or "/account/item", params={"id": account_id})
        account = payload.get("account") if isinstance(payload, Mapping) and "account" in payload else payload
        normalized = self._normalize_account(account if isinstance(account, Mapping) else {})
        await self._emit_account_event(normalized)
        return normalized

    async def get_positions(self):
        account_id = await self._resolve_account_id()
        payload = await self._request_json("GET", self.options.get("positions_path") or "/position/list", params={"accountId": account_id})
        positions = payload if isinstance(payload, list) else payload.get("positions") or []
        normalized = [self._normalize_position(item) for item in positions]
        for position in normalized:
            await self._emit_position_event(position)
        return normalized

    async def place_order(self, order):
        order = Order.from_mapping(order)
        account_id = order.account_id or await self._resolve_account_id()
        contract_id = await self._resolve_contract_id(order.symbol)
        payload = {
            "accountId": account_id,
            "action": "Buy" if order.side is OrderSide.BUY else "Sell",
            "orderType": {
                OrderType.MARKET: "Market",
                OrderType.LIMIT: "Limit",
                OrderType.STOP: "Stop",
                OrderType.STOP_LIMIT: "StopLimit",
                OrderType.BRACKET: "Market",
            }.get(order.order_type, "Market"),
            "symbol": order.symbol,
            "contractId": contract_id,
            "orderQty": abs(order.quantity),
            "timeInForce": order.time_in_force,
            "clOrdId": order.client_order_id,
            "isAutomated": True,
        }
        if order.price is not None:
            payload["price"] = float(order.price)
        if order.stop_price is not None:
            payload["stopPrice"] = float(order.stop_price)
        if order.stop_loss is not None:
            payload["stopLoss"] = float(order.stop_loss)
        if order.take_profit is not None:
            payload["takeProfit"] = float(order.take_profit)
        payload.update({key: value for key, value in dict(order.params or {}).items() if key not in payload})

        response = await self._request_json(
            "POST",
            self.options.get("order_path") or "/order/placeorder",
            json_payload={key: value for key, value in payload.items() if value is not None},
            expected_statuses=(200, 201, 202),
        )
        normalized = {
            "id": response.get("orderId") or response.get("id") or payload.get("clOrdId"),
            "clientOrderId": payload.get("clOrdId"),
            "broker": self.exchange_name,
            "account_id": account_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "amount": order.quantity,
            "type": order.order_type.value,
            "price": order.price,
            "stop_price": order.stop_price,
            "status": str(response.get("ordStatus") or response.get("status") or "submitted").strip().lower(),
            "raw": response,
        }
        await self._emit_order_event(normalized)
        return normalized

    async def cancel_order(self, order_id, symbol=None):
        payload = await self._request_json(
            "POST",
            self.options.get("cancel_order_path") or "/order/cancelorder",
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
            self.options.get("quotes_path") or "/md/getquotes",
            params={"symbols": ",".join(normalized_symbols)},
        )
        items = payload if isinstance(payload, list) else payload.get("quotes") or payload.get("data") or []
        quote_map = {}
        for item in items:
            if isinstance(item, Mapping):
                quote_map[str(item.get("symbol") or item.get("name") or "").upper()] = dict(item)
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
        payload = await self._request_json("GET", self.options.get("orders_path") or "/order/list", params={"accountId": account_id})
        orders = payload if isinstance(payload, list) else payload.get("orders") or []
        normalized = []
        for raw in orders:
            raw_symbol = raw.get("symbol") or raw.get("contractName")
            raw_status = str(raw.get("ordStatus") or raw.get("status") or "unknown").strip().lower()
            if symbol and str(raw_symbol).upper() != str(symbol).upper():
                continue
            if status == "open" and raw_status in {"filled", "canceled", "cancelled", "rejected"}:
                continue
            if status == "closed" and raw_status not in {"filled", "canceled", "cancelled", "rejected"}:
                continue
            normalized.append(
                {
                    "id": raw.get("id") or raw.get("orderId"),
                    "broker": self.exchange_name,
                    "account_id": account_id,
                    "symbol": raw_symbol,
                    "side": str(raw.get("action") or raw.get("side") or "").lower(),
                    "amount": _safe_float(raw.get("orderQty", raw.get("quantity", 0.0))),
                    "filled": _safe_float(raw.get("fillQty", raw.get("filled", 0.0))),
                    "price": _safe_float(raw.get("price", 0.0)) or None,
                    "stop_price": _safe_float(raw.get("stopPrice", 0.0)) or None,
                    "status": raw_status,
                    "timestamp": raw.get("timestamp") or raw.get("lastUpdateTime"),
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
            self.options.get("contract_search_path") or "/contract/find",
            params={"name": str(symbol).strip().upper(), **kwargs},
        )
        records = payload if isinstance(payload, list) else payload.get("contracts") or payload.get("data") or []
        raw = records[0] if records else {}
        instrument = self._instrument_from_payload(raw or {"name": symbol})
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

    def _websocket_auth_message(self):
        if not self.access_token:
            return None
        return {"op": "authorize", "token": self.access_token}

    def _websocket_subscriptions(self, symbols):
        return [{"op": "subscribeQuote", "symbol": str(symbol).strip().upper()} for symbol in (symbols or []) if str(symbol).strip()]

    def _normalize_stream_message(self, raw_message):
        payloads = super()._normalize_stream_message(raw_message)
        normalized = []
        for payload in payloads:
            symbol = payload.get("symbol") or payload.get("name")
            if not symbol:
                continue
            normalized.append(
                {
                    "broker": self.exchange_name,
                    "symbol": str(symbol).strip().upper(),
                    "bid": _safe_float(payload.get("bid", 0.0)),
                    "ask": _safe_float(payload.get("ask", 0.0)),
                    "last": _safe_float(payload.get("last", payload.get("trade", 0.0))),
                    "close": _safe_float(payload.get("close", 0.0)),
                    "mark": _safe_float(payload.get("mark", payload.get("last", 0.0))),
                    "timestamp": payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                    "raw": payload,
                }
            )
        return normalized
