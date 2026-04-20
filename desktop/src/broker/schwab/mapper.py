from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from models.instrument import Instrument, InstrumentType, OptionRight
from models.order import Order, OrderLeg, OrderSide
from models.position import Position

from .models import (
    SchwabAccount,
    SchwabBalance,
    SchwabOrderRequest,
    SchwabOrderResponse,
    SchwabOrderStatus,
    SchwabPosition,
    SchwabQuote,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _status_from_value(value: Any) -> SchwabOrderStatus:
    normalized = str(value or "").strip().lower()
    mapping = {
        "queued": SchwabOrderStatus.SUBMITTED,
        "received": SchwabOrderStatus.SUBMITTED,
        "accepted": SchwabOrderStatus.SUBMITTED,
        "working": SchwabOrderStatus.WORKING,
        "filled": SchwabOrderStatus.FILLED,
        "canceled": SchwabOrderStatus.CANCELED,
        "cancelled": SchwabOrderStatus.CANCELED,
        "expired": SchwabOrderStatus.EXPIRED,
        "rejected": SchwabOrderStatus.REJECTED,
    }
    return mapping.get(normalized, SchwabOrderStatus.UNKNOWN if normalized else SchwabOrderStatus.SUBMITTED)


class SchwabMapper:
    def __init__(self, *, default_contract_size: int = 100) -> None:
        self.default_contract_size = int(default_contract_size or 100)

    def account_from_number_entry(self, raw: Mapping[str, Any]) -> SchwabAccount:
        return SchwabAccount(
            account_id=str(raw.get("accountNumber") or raw.get("accountId") or raw.get("account_id") or "").strip(),
            account_hash=str(raw.get("hashValue") or raw.get("accountHash") or "").strip() or None,
            alias=str(raw.get("displayName") or raw.get("alias") or "").strip() or None,
            account_type=str(raw.get("type") or raw.get("accountType") or "").strip() or None,
            metadata=dict(raw),
        )

    def canonical_account(self, account: SchwabAccount) -> dict[str, Any]:
        payload = account.to_dict()
        payload["broker"] = "schwab"
        payload["raw"] = payload.pop("metadata")
        return payload

    def balance_from_account_payload(
        self,
        raw: Mapping[str, Any],
        *,
        account_id: str,
        account_hash: str | None = None,
    ) -> SchwabBalance:
        balance = dict(raw.get("currentBalances") or {})
        initial = dict(raw.get("initialBalances") or {})
        return SchwabBalance(
            account_id=account_id,
            account_hash=account_hash,
            currency="USD",
            cash=_safe_float(balance.get("cashBalance", initial.get("cashAvailableForTrading", 0.0))),
            buying_power=_safe_float(balance.get("buyingPower", initial.get("buyingPower", 0.0))),
            equity=_safe_float(balance.get("equity", initial.get("accountValue", 0.0))),
            liquidation_value=_safe_float(balance.get("liquidationValue", balance.get("equity", 0.0))),
            margin_used=_safe_float(balance.get("marginBalance", 0.0)),
            available_funds=_safe_float(balance.get("availableFunds", balance.get("cashAvailableForTrading", 0.0))),
            maintenance_requirement=_safe_float(balance.get("maintenanceRequirement", 0.0)),
            metadata=dict(raw),
        )

    def canonical_balance(self, balance: SchwabBalance) -> dict[str, Any]:
        payload = balance.to_dict()
        payload["broker"] = "schwab"
        payload["available"] = payload.get("available_funds", 0.0)
        payload["net_liquidation"] = payload.get("liquidation_value", 0.0)
        payload["raw"] = payload.pop("metadata")
        return payload

    def instrument_from_payload(self, raw_instrument: Mapping[str, Any]) -> Instrument:
        asset_type = str(raw_instrument.get("assetType") or raw_instrument.get("type") or "EQUITY").strip().upper()
        instrument_type = InstrumentType.OPTION if asset_type == "OPTION" else InstrumentType.STOCK
        option_right = raw_instrument.get("putCall") or raw_instrument.get("option_type")
        if option_right is not None:
            normalized_right = str(option_right).strip().lower()
            option_right = OptionRight.CALL if normalized_right.startswith("c") else OptionRight.PUT
        return Instrument(
            symbol=raw_instrument.get("symbol") or raw_instrument.get("description"),
            type=instrument_type,
            expiry=raw_instrument.get("expirationDate") or raw_instrument.get("expiration"),
            strike=raw_instrument.get("strikePrice"),
            option_type=option_right,
            contract_size=self.default_contract_size if instrument_type is InstrumentType.OPTION else 1,
            exchange="schwab",
            underlying=raw_instrument.get("underlyingSymbol"),
            multiplier=self.default_contract_size if instrument_type is InstrumentType.OPTION else 1.0,
            metadata=dict(raw_instrument),
        )

    def position_from_payload(
        self,
        raw: Mapping[str, Any],
        *,
        account_id: str,
        account_hash: str | None = None,
    ) -> SchwabPosition:
        instrument = self.instrument_from_payload(dict(raw.get("instrument") or {}))
        long_qty = _safe_float(raw.get("longQuantity", 0.0))
        short_qty = _safe_float(raw.get("shortQuantity", 0.0))
        quantity = long_qty if long_qty > 0 else -short_qty
        contract_multiplier = max(float(instrument.multiplier or 1.0), 1.0)
        market_value = _safe_float(raw.get("marketValue", 0.0))
        mark_price = (market_value / (abs(quantity) * contract_multiplier)) if quantity else None
        return SchwabPosition(
            account_id=account_id,
            account_hash=account_hash,
            symbol=instrument.symbol,
            quantity=quantity,
            side="long" if quantity >= 0 else "short",
            instrument=instrument,
            avg_price=_safe_float(raw.get("averagePrice", 0.0)),
            mark_price=mark_price,
            market_value=market_value,
            unrealized_pnl=_safe_float(raw.get("currentDayProfitLoss", raw.get("longOpenProfitLoss", 0.0))),
            realized_pnl=_safe_float(raw.get("currentDayProfitLossPercentage", 0.0)),
            metadata=dict(raw),
        )

    def canonical_position(self, position: SchwabPosition) -> dict[str, Any]:
        normalized = Position(
            symbol=position.symbol,
            quantity=position.quantity,
            side=position.side,
            instrument=position.instrument,
            avg_price=position.avg_price,
            mark_price=position.mark_price,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            broker="schwab",
            account_id=position.account_id,
            metadata=position.metadata,
        )
        payload = normalized.to_dict()
        payload["market_value"] = position.market_value
        payload["account_hash"] = position.account_hash
        payload["notional"] = abs(position.market_value) or payload.get("notional_exposure", 0.0)
        return payload

    def quote_from_payload(self, symbol: str, raw: Mapping[str, Any]) -> SchwabQuote:
        return SchwabQuote(
            symbol=str(symbol or raw.get("symbol") or "").strip().upper(),
            bid=_safe_float(raw.get("bidPrice", raw.get("bid", 0.0))),
            ask=_safe_float(raw.get("askPrice", raw.get("ask", 0.0))),
            last=_safe_float(raw.get("lastPrice", raw.get("last", 0.0))),
            close=_safe_float(raw.get("closePrice", raw.get("close", 0.0))),
            mark=_safe_float(raw.get("mark", raw.get("markPrice", raw.get("lastPrice", 0.0)))),
            timestamp=str(raw.get("quoteTime") or datetime.now(timezone.utc).isoformat()),
            metadata=dict(raw),
        )

    def canonical_quote(self, quote: SchwabQuote) -> dict[str, Any]:
        payload = quote.to_dict()
        payload["broker"] = "schwab"
        payload["raw"] = payload.pop("metadata")
        return payload

    def order_request_from_order(self, order: Order | Mapping[str, Any], *, account_id: str) -> SchwabOrderRequest:
        normalized = Order.from_mapping(order)
        return SchwabOrderRequest(
            account_id=str(normalized.account_id or account_id).strip() or account_id,
            symbol=normalized.symbol,
            side=normalized.side.value,
            order_type=normalized.order_type.value,
            quantity=abs(float(normalized.quantity)),
            time_in_force=str(normalized.time_in_force or "DAY").strip().upper(),
            price=normalized.price,
            stop_price=normalized.stop_price,
            stop_loss=normalized.stop_loss,
            take_profit=normalized.take_profit,
            instrument=normalized.instrument,
            metadata=normalized.to_dict(),
        )

    def _leg_instruction(self, leg: OrderLeg, *, closing: bool = False) -> str:
        if leg.instrument.type is InstrumentType.OPTION:
            if leg.side is OrderSide.BUY:
                return "BUY_TO_CLOSE" if closing else "BUY_TO_OPEN"
            return "SELL_TO_CLOSE" if closing else "SELL_TO_OPEN"
        return "BUY" if leg.side is OrderSide.BUY else "SELL"

    def order_payload(self, request: SchwabOrderRequest) -> dict[str, Any]:
        order = Order.from_mapping(request.metadata or request.to_dict())
        duration = request.time_in_force if request.time_in_force in {"DAY", "GTC"} else "DAY"
        legs = list(order.legs)
        if not legs:
            instrument = order.instrument or request.instrument or Instrument(symbol=request.symbol, exchange="schwab")
            legs = [OrderLeg(instrument=instrument, side=order.side, quantity=request.quantity)]

        leg_payloads = []
        for leg in legs:
            leg_payloads.append(
                {
                    "instruction": self._leg_instruction(leg, closing=bool(order.params.get("closing"))),
                    "quantity": abs(float(leg.quantity)),
                    "instrument": {
                        "assetType": "OPTION" if leg.instrument.type is InstrumentType.OPTION else "EQUITY",
                        "symbol": leg.instrument.symbol,
                    },
                }
            )

        payload: dict[str, Any] = {
            "session": str(order.params.get("session") or "NORMAL").upper(),
            "duration": duration,
            "orderType": {
                "market": "MARKET",
                "limit": "LIMIT",
                "stop": "STOP",
                "stop_limit": "STOP_LIMIT",
            }.get(request.order_type, "MARKET"),
            "orderStrategyType": "SINGLE",
            "orderLegCollection": leg_payloads,
        }
        if request.price is not None:
            payload["price"] = round(float(request.price), 4)
        if request.stop_price is not None:
            payload["stopPrice"] = round(float(request.stop_price), 4)
        if request.take_profit is not None or request.stop_loss is not None:
            payload["orderStrategyType"] = "TRIGGER"
            exit_side = OrderSide.SELL if order.side is OrderSide.BUY else OrderSide.BUY
            child_orders = []
            if request.take_profit is not None:
                child_orders.append(
                    {
                        "orderType": "LIMIT",
                        "session": "NORMAL",
                        "duration": duration,
                        "orderStrategyType": "SINGLE",
                        "price": round(float(request.take_profit), 4),
                        "orderLegCollection": [
                            {
                                "instruction": "SELL" if exit_side is OrderSide.SELL else "BUY",
                                "quantity": abs(float(request.quantity)),
                                "instrument": {"assetType": "EQUITY", "symbol": request.symbol},
                            }
                        ],
                    }
                )
            if request.stop_loss is not None:
                child_orders.append(
                    {
                        "orderType": "STOP",
                        "session": "NORMAL",
                        "duration": duration,
                        "orderStrategyType": "SINGLE",
                        "stopPrice": round(float(request.stop_loss), 4),
                        "orderLegCollection": [
                            {
                                "instruction": "SELL" if exit_side is OrderSide.SELL else "BUY",
                                "quantity": abs(float(request.quantity)),
                                "instrument": {"assetType": "EQUITY", "symbol": request.symbol},
                            }
                        ],
                    }
                )
            if child_orders:
                payload["childOrderStrategies"] = child_orders
        return payload

    def order_response_from_payload(
        self,
        raw: Mapping[str, Any],
        *,
        request: SchwabOrderRequest,
        order_id: str | None = None,
        status: Any = None,
    ) -> SchwabOrderResponse:
        return SchwabOrderResponse(
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            order_id=str(order_id or raw.get("orderId") or raw.get("id") or "").strip(),
            status=_status_from_value(status or raw.get("status") or raw.get("orderStatus") or "submitted"),
            time_in_force=request.time_in_force,
            price=request.price,
            stop_price=request.stop_price,
            metadata=dict(raw),
        )

    def canonical_order_response(self, response: SchwabOrderResponse) -> dict[str, Any]:
        payload = response.to_dict()
        payload["broker"] = "schwab"
        payload["id"] = payload.pop("order_id")
        payload["type"] = payload.pop("order_type")
        payload["amount"] = payload.pop("quantity")
        payload["time_in_force"] = payload.pop("time_in_force")
        payload["raw"] = payload.pop("metadata")
        return payload

    def canonical_order_from_raw(self, raw: Mapping[str, Any], *, account_id: str) -> dict[str, Any]:
        leg = next(iter(raw.get("orderLegCollection") or [{}]), {})
        symbol = str(leg.get("instrument", {}).get("symbol") or raw.get("symbol") or "").strip().upper()
        side = str(leg.get("instruction") or raw.get("instruction") or "").strip().lower()
        response = SchwabOrderResponse(
            account_id=account_id,
            symbol=symbol,
            side=side,
            order_type=str(raw.get("orderType") or "").strip().lower() or "market",
            quantity=_safe_float(leg.get("quantity", raw.get("quantity", 0.0))),
            order_id=str(raw.get("orderId") or raw.get("id") or "").strip(),
            status=_status_from_value(raw.get("status")),
            time_in_force=str(raw.get("duration") or "DAY").strip().upper() or "DAY",
            price=_safe_float(raw.get("price"), 0.0) or None,
            stop_price=_safe_float(raw.get("stopPrice"), 0.0) or None,
            metadata=dict(raw),
        )
        payload = self.canonical_order_response(response)
        payload["timestamp"] = raw.get("enteredTime")
        return payload

    def option_chain_from_payload(self, symbol: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        contracts = []
        for side_key in ("callExpDateMap", "putExpDateMap"):
            expiry_map = dict(payload.get(side_key) or {})
            for expiry, strike_map in expiry_map.items():
                for strike, raw_contracts in dict(strike_map or {}).items():
                    for contract in list(raw_contracts or []):
                        raw_instrument = dict(contract)
                        raw_instrument.setdefault("underlyingSymbol", normalized_symbol)
                        instrument = self.instrument_from_payload(raw_instrument)
                        contracts.append(
                            {
                                "instrument": instrument.to_dict(),
                                "symbol": instrument.symbol,
                                "expiry": instrument.expiry.isoformat() if instrument.expiry is not None else None,
                                "strike": instrument.strike,
                                "option_type": instrument.option_type.value if instrument.option_type is not None else None,
                                "bid": _safe_float(contract.get("bid", 0.0)),
                                "ask": _safe_float(contract.get("ask", 0.0)),
                                "last": _safe_float(contract.get("last", 0.0)),
                                "mark": _safe_float(contract.get("mark", contract.get("last", 0.0))),
                                "volume": int(_safe_float(contract.get("totalVolume", contract.get("volume", 0.0)))),
                                "open_interest": int(_safe_float(contract.get("openInterest", 0.0))),
                                "delta": _safe_float(contract.get("delta", 0.0)),
                                "gamma": _safe_float(contract.get("gamma", 0.0)),
                                "theta": _safe_float(contract.get("theta", 0.0)),
                                "vega": _safe_float(contract.get("vega", 0.0)),
                                "broker": "schwab",
                                "raw": dict(contract),
                            }
                        )
        return {
            "broker": "schwab",
            "symbol": normalized_symbol,
            "underlying_price": _safe_float((payload.get("underlying") or {}).get("last", 0.0)),
            "interest_rate": _safe_float(payload.get("interestRate", 0.0)),
            "volatility": _safe_float(payload.get("volatility", 0.0)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "contracts": contracts,
            "raw": dict(payload),
        }
