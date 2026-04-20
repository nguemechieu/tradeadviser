from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from models.instrument import Instrument, InstrumentType, OptionRight
from models.order import Order, OrderType
from models.position import Position

from broker.ibkr.models import (
    IBKRAccount,
    IBKRBalance,
    IBKRContract,
    IBKROrderRequest,
    IBKROrderResponse,
    IBKRPosition,
    IBKRQuote,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_datetime(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    candidates = [text, text.replace("Z", "+00:00")]
    if text.isdigit():
        try:
            divisor = 1000 if len(text) > 10 else 1
            return datetime.fromtimestamp(int(text) / divisor, tz=timezone.utc)
        except Exception:
            pass
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


class IBKRMapper:
    """Map IBKR transport payloads into normalized Sopotek models."""

    SNAPSHOT_SYMBOL_TAG = "55"
    SNAPSHOT_LAST_TAG = "31"
    SNAPSHOT_BID_TAG = "84"
    SNAPSHOT_ASK_TAG = "86"
    SNAPSHOT_CLOSE_TAG = "88"
    SNAPSHOT_MARK_TAG = "6008"
    SNAPSHOT_BID_SIZE_TAG = "85"
    SNAPSHOT_ASK_SIZE_TAG = "87"

    def contract_from_payload(self, raw: Mapping[str, Any], *, default_symbol: str | None = None) -> IBKRContract:
        symbol = str(
            raw.get("symbol")
            or raw.get("ticker")
            or raw.get("local_symbol")
            or raw.get("localSymbol")
            or default_symbol
            or ""
        ).strip().upper()
        return IBKRContract(
            symbol=symbol,
            conid=str(raw.get("conid") or raw.get("conidEx") or raw.get("contract_id") or "").strip() or None,
            sec_type=str(raw.get("secType") or raw.get("assetClass") or "STK").strip().upper() or "STK",
            exchange=str(raw.get("exchange") or raw.get("listingExchange") or "SMART").strip().upper() or "SMART",
            primary_exchange=str(raw.get("primaryExchange") or raw.get("listingExchange") or "").strip() or None,
            currency=str(raw.get("currency") or "USD").strip().upper() or "USD",
            local_symbol=str(raw.get("localSymbol") or raw.get("local_symbol") or "").strip().upper() or None,
            multiplier=_safe_float(raw.get("multiplier"), 0.0) or None,
            expiry=str(raw.get("expiry") or raw.get("maturityDate") or raw.get("lastTradeDate") or "").strip() or None,
            strike=_safe_float(raw.get("strike"), 0.0) or None,
            right=str(raw.get("right") or raw.get("putCall") or "").strip().upper() or None,
            underlying=str(raw.get("underlyingSymbol") or raw.get("underlying") or "").strip().upper() or None,
            trading_class=str(raw.get("tradingClass") or "").strip().upper() or None,
            metadata=dict(raw),
        )

    def instrument_from_contract(self, contract: IBKRContract | Mapping[str, Any]) -> Instrument:
        if not isinstance(contract, IBKRContract):
            contract = self.contract_from_payload(contract)
        sec_type = str(contract.sec_type or "STK").strip().upper()
        instrument_type = InstrumentType.STOCK
        if sec_type == "OPT":
            instrument_type = InstrumentType.OPTION
        elif sec_type == "FUT":
            instrument_type = InstrumentType.FUTURE
        elif sec_type == "CASH":
            instrument_type = InstrumentType.FOREX
        elif sec_type == "CRYPTO":
            instrument_type = InstrumentType.CRYPTO
        option_right = None
        if contract.right:
            option_right = OptionRight.CALL if str(contract.right).startswith("C") else OptionRight.PUT
        multiplier = contract.multiplier or (100.0 if instrument_type is InstrumentType.OPTION else 1.0)
        return Instrument(
            symbol=contract.symbol,
            type=instrument_type,
            expiry=contract.expiry,
            strike=contract.strike,
            option_type=option_right,
            contract_size=int(multiplier) if instrument_type in {InstrumentType.OPTION, InstrumentType.FUTURE} else 1,
            exchange=(contract.exchange or "SMART").lower(),
            currency=contract.currency or "USD",
            multiplier=multiplier,
            underlying=contract.underlying,
            broker_hint="ibkr",
            metadata=contract.to_dict(),
        )

    def account_from_accounts_payload(self, raw: Mapping[str, Any]) -> IBKRAccount:
        account_id = str(
            raw.get("id")
            or raw.get("accountId")
            or raw.get("accountIdKey")
            or raw.get("account_id")
            or raw.get("account")
            or ""
        ).strip()
        return IBKRAccount(
            account_id=account_id,
            alias=str(raw.get("accountAlias") or raw.get("alias") or raw.get("name") or "").strip() or None,
            account_type=str(raw.get("type") or raw.get("accountType") or raw.get("account_type") or "").strip() or None,
            currency=str(raw.get("currency") or raw.get("baseCurrency") or "USD").strip().upper() or "USD",
            brokerage_access=bool(
                raw.get("brokerageAccess")
                or raw.get("tradingEnabled")
                or raw.get("isPaper")
                or raw.get("facl")
            ),
            metadata=dict(raw),
        )

    def canonical_account(self, account: IBKRAccount) -> dict[str, Any]:
        payload = account.to_dict()
        payload["broker"] = "ibkr"
        payload["raw"] = payload.pop("metadata")
        return payload

    def balance_from_summary(self, raw: Mapping[str, Any], *, account_id: str) -> IBKRBalance:
        equity = _safe_float(raw.get("equitywithloanvalue", raw.get("netliq", raw.get("equity", 0.0))), 0.0)
        return IBKRBalance(
            account_id=account_id,
            currency=str(raw.get("currency") or raw.get("baseCurrency") or "USD").strip().upper() or "USD",
            cash=_safe_float(raw.get("cashbalance", raw.get("cash", 0.0)), 0.0),
            equity=equity,
            buying_power=_safe_float(raw.get("buyingpower", raw.get("buyingPower", 0.0)), 0.0),
            available_funds=_safe_float(raw.get("availablefunds", raw.get("availableFunds", 0.0)), 0.0),
            maintenance_requirement=_safe_float(raw.get("maintmarginreq", raw.get("maintenanceMargin", 0.0)), 0.0),
            margin_used=_safe_float(raw.get("initmarginreq", raw.get("initialMargin", 0.0)), 0.0),
            net_liquidation=_safe_float(raw.get("netliq", raw.get("netLiquidation", equity)), equity),
            metadata=dict(raw),
        )

    def canonical_balance(self, balance: IBKRBalance) -> dict[str, Any]:
        payload = balance.to_dict()
        payload["broker"] = "ibkr"
        payload["available"] = payload.get("available_funds", 0.0)
        payload["raw"] = payload.pop("metadata")
        return payload

    def position_from_payload(self, raw: Mapping[str, Any], *, account_id: str) -> IBKRPosition:
        contract = self.contract_from_payload(raw)
        quantity = _safe_float(raw.get("position", raw.get("quantity", raw.get("qty", 0.0))), 0.0)
        return IBKRPosition(
            account_id=account_id,
            symbol=contract.symbol,
            quantity=quantity,
            avg_price=_safe_float(raw.get("avgCost", raw.get("avgPrice", 0.0)), 0.0),
            market_price=_safe_float(raw.get("mktPrice", raw.get("marketPrice", 0.0)), 0.0),
            market_value=_safe_float(raw.get("mktValue", raw.get("marketValue", 0.0)), 0.0),
            unrealized_pnl=_safe_float(raw.get("unrealizedPnl", raw.get("upl", 0.0)), 0.0),
            realized_pnl=_safe_float(raw.get("realizedPnl", raw.get("rpl", 0.0)), 0.0),
            side="long" if quantity >= 0 else "short",
            contract=contract,
            metadata=dict(raw),
        )

    def canonical_position(self, position: IBKRPosition) -> dict[str, Any]:
        instrument = self.instrument_from_contract(position.contract or {"symbol": position.symbol})
        normalized = Position(
            symbol=position.symbol,
            quantity=position.quantity,
            side=position.side,
            instrument=instrument,
            avg_price=position.avg_price,
            mark_price=position.market_price or None,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            broker="ibkr",
            account_id=position.account_id,
            metadata=position.metadata,
        )
        payload = normalized.to_dict()
        payload["market_value"] = position.market_value
        payload["notional"] = abs(position.market_value) or payload.get("notional_exposure", 0.0)
        payload["contract"] = position.contract.to_dict() if position.contract is not None else None
        return payload

    def quote_from_snapshot(
        self,
        raw: Mapping[str, Any],
        *,
        symbol: str | None = None,
        contract: IBKRContract | None = None,
    ) -> IBKRQuote:
        resolved_symbol = str(
            symbol
            or raw.get(self.SNAPSHOT_SYMBOL_TAG)
            or raw.get("symbol")
            or raw.get("ticker")
            or (contract.symbol if contract is not None else "")
        ).strip().upper()
        return IBKRQuote(
            symbol=resolved_symbol,
            bid=_safe_float(raw.get(self.SNAPSHOT_BID_TAG, raw.get("bid", 0.0)), 0.0),
            ask=_safe_float(raw.get(self.SNAPSHOT_ASK_TAG, raw.get("ask", 0.0)), 0.0),
            last=_safe_float(raw.get(self.SNAPSHOT_LAST_TAG, raw.get("last", 0.0)), 0.0),
            close=_safe_float(raw.get(self.SNAPSHOT_CLOSE_TAG, raw.get("close", 0.0)), 0.0),
            mark=_safe_float(raw.get(self.SNAPSHOT_MARK_TAG, raw.get("mark", 0.0)), 0.0),
            bid_size=_safe_float(raw.get(self.SNAPSHOT_BID_SIZE_TAG, raw.get("bidSize", 0.0)), 0.0),
            ask_size=_safe_float(raw.get(self.SNAPSHOT_ASK_SIZE_TAG, raw.get("askSize", 0.0)), 0.0),
            timestamp=datetime.now(timezone.utc).isoformat(),
            contract=contract,
            metadata=dict(raw),
        )

    def canonical_quote(self, quote: IBKRQuote) -> dict[str, Any]:
        payload = quote.to_dict()
        payload["broker"] = "ibkr"
        return payload

    def order_request_from_order(
        self,
        order: Order | Mapping[str, Any],
        *,
        account_id: str,
        contract: IBKRContract | None = None,
    ) -> IBKROrderRequest:
        normalized = Order.from_mapping(order)
        order_type = normalized.order_type
        if not isinstance(order_type, OrderType):
            order_type = OrderType(str(order_type).strip().lower())
        return IBKROrderRequest(
            account_id=str(normalized.account_id or account_id).strip(),
            symbol=normalized.symbol,
            side=normalized.side.value.upper(),
            order_type=order_type.value,
            quantity=abs(float(normalized.quantity)),
            price=normalized.price,
            tif=str(normalized.time_in_force or "DAY").strip().upper(),
            contract=contract,
            stop_price=normalized.stop_price,
            client_order_id=normalized.client_order_id,
            metadata=normalized.to_dict(),
        )

    def webapi_order_payload(self, request: IBKROrderRequest) -> dict[str, Any]:
        contract = request.contract or IBKRContract(symbol=request.symbol)
        payload = {
            "acctId": request.account_id,
            "conid": int(contract.conid) if str(contract.conid or "").isdigit() else contract.conid,
            "secType": str(contract.sec_type or "STK").strip().upper(),
            "orderType": {
                "market": "MKT",
                "limit": "LMT",
                "stop": "STP",
                "stop_limit": "STP LMT",
            }.get(request.order_type, "MKT"),
            "side": str(request.side or "").strip().upper(),
            "quantity": abs(float(request.quantity)),
            "tif": request.tif,
            "cOID": request.client_order_id,
        }
        if request.price is not None:
            payload["price"] = float(request.price)
        if request.stop_price is not None:
            payload["auxPrice"] = float(request.stop_price)
        return {key: value for key, value in payload.items() if value not in (None, "", [], {})}

    def order_response_from_payload(
        self,
        raw: Mapping[str, Any],
        *,
        request: IBKROrderRequest,
    ) -> IBKROrderResponse:
        return IBKROrderResponse(
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side.lower(),
            order_type=request.order_type,
            quantity=request.quantity,
            order_id=str(
                raw.get("order_id")
                or raw.get("orderId")
                or raw.get("id")
                or raw.get("local_order_id")
                or request.client_order_id
                or ""
            ).strip(),
            status=str(raw.get("status") or raw.get("order_status") or "submitted").strip().lower() or "submitted",
            price=request.price,
            tif=request.tif,
            client_order_id=request.client_order_id,
            metadata=dict(raw),
        )

    def canonical_order_response(self, response: IBKROrderResponse) -> dict[str, Any]:
        payload = response.to_dict()
        payload["broker"] = "ibkr"
        payload["id"] = payload.pop("order_id")
        payload["type"] = payload.pop("order_type")
        payload["amount"] = payload.pop("quantity")
        payload["clientOrderId"] = payload.pop("client_order_id")
        payload["raw"] = payload.pop("metadata")
        return payload

    def historical_bars_from_payload(self, raw: Mapping[str, Any], *, symbol: str) -> list[list[float]]:
        bars = list(raw.get("data") or raw.get("bars") or raw.get("results") or [])
        normalized: list[list[float]] = []
        for row in bars:
            if not isinstance(row, Mapping):
                continue
            timestamp = row.get("t") or row.get("time") or row.get("timestamp")
            dt_value = _safe_datetime(timestamp)
            if dt_value is None:
                continue
            normalized.append(
                [
                    float(int(dt_value.timestamp() * 1000)),
                    _safe_float(row.get("o", row.get("open", 0.0)), 0.0),
                    _safe_float(row.get("h", row.get("high", 0.0)), 0.0),
                    _safe_float(row.get("l", row.get("low", 0.0)), 0.0),
                    _safe_float(row.get("c", row.get("close", 0.0)), 0.0),
                    _safe_float(row.get("v", row.get("volume", 0.0)), 0.0),
                ]
            )
        normalized.sort(key=lambda row: row[0])
        return normalized
