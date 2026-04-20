from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any

from .client import CoinbaseAPIError, CoinbaseAdvancedTradeClient
from .market_data import CoinbaseFuturesMarketDataService
from .models import (
    BalanceSnapshot,
    CoinbaseConfig,
    OrderRequest,
    OrderResult,
    PositionSnapshot,
    ProductStatus,
)
from .products import CoinbaseFuturesProductService


def _as_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def _float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, Mapping):
        for key in ("value", "amount", "initial_margin", "maintenance_margin", "futures_buying_power", "total_hold"):
            if key in value:
                return _float(value.get(key), default=default)
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text(value: Any) -> str:
    return str(value or "").strip()


class CoinbaseRiskError(ValueError):
    """Raised when a futures order fails local risk validation."""


class CoinbaseFuturesExecutionService:
    def __init__(
        self,
        client: CoinbaseAdvancedTradeClient,
        products: CoinbaseFuturesProductService,
        *,
        event_bus: Any = None,
        config: CoinbaseConfig | Any = None,
        market_data: CoinbaseFuturesMarketDataService | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.products = products
        self.event_bus = event_bus
        self.config = CoinbaseConfig.from_broker_config(config or client.config)
        self.market_data = market_data
        self.logger = logger or logging.getLogger("CoinbaseFuturesExecution")

    async def fetch_balances(self) -> dict[str, Any]:
        payload = await self.client.get_futures_balance_summary()
        summary = payload.get("balance_summary") if isinstance(payload, Mapping) else None
        if not isinstance(summary, Mapping):
            summary = payload if isinstance(payload, Mapping) else {}

        equity = _float(
            summary.get("total_usd_balance")
            or summary.get("equity")
            or summary.get("portfolio_value")
            or summary.get("balance")
        )
        available_margin = _float(
            summary.get("available_margin")
            or summary.get("available_buying_power")
            or summary.get("futures_buying_power")
            or summary.get("cfm_usd_balance")
            or equity
        )
        cash = _float(summary.get("cfm_usd_balance") or summary.get("cash") or available_margin)
        buying_power = _float(summary.get("futures_buying_power") or summary.get("available_buying_power") or available_margin)

        snapshot = BalanceSnapshot(
            equity=equity or cash,
            cash=cash,
            available_margin=available_margin,
            buying_power=buying_power,
            unrealized_pnl=_float(summary.get("unrealized_pnl")),
            raw=dict(summary),
        )
        payload_dict = snapshot.to_dict()
        if self.event_bus is not None:
            await self.event_bus.publish("portfolio.update", {"exchange": "coinbase_futures", "balance": payload_dict})
        return payload_dict

    async def fetch_positions(self) -> list[dict[str, Any]]:
        payload = await self.client.get_futures_positions()
        rows = payload.get("positions") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            rows = []

        positions: list[dict[str, Any]] = []
        for raw_position in rows:
            if not isinstance(raw_position, Mapping):
                continue
            product_id = _text(raw_position.get("product_id") or raw_position.get("instrument")).upper()
            product = None
            if product_id:
                try:
                    product = await self.products.resolve_product(product_id)
                except Exception:
                    product = None
            symbol = product.normalized_symbol if product is not None else product_id
            side = _text(raw_position.get("side") or raw_position.get("position_side") or "LONG").lower() or "long"
            side = "short" if side.startswith("s") else "long"
            contracts = abs(
                _float(
                    raw_position.get("number_of_contracts")
                    or raw_position.get("contracts")
                    or raw_position.get("quantity")
                    or raw_position.get("size")
                )
            )
            position = PositionSnapshot(
                symbol=symbol,
                product_id=product_id or symbol,
                side=side,
                contracts=contracts,
                entry_price=_float(raw_position.get("avg_entry_price") or raw_position.get("entry_price")) or None,
                mark_price=_float(raw_position.get("current_price") or raw_position.get("mark_price")) or None,
                unrealized_pnl=_float(raw_position.get("unrealized_pnl")),
                realized_pnl=_float(raw_position.get("daily_realized_pnl") or raw_position.get("realized_pnl")),
                expiry=_text(raw_position.get("expiration_time") or raw_position.get("expiry_time")) or None,
                raw=dict(raw_position),
            )
            positions.append(position.to_dict())

        if self.event_bus is not None:
            await self.event_bus.publish("portfolio.update", {"exchange": "coinbase_futures", "positions": positions})
        return positions

    async def _mark_price(self, product_id: str, symbol: str, explicit_price: float | None) -> float:
        if explicit_price is not None and float(explicit_price) > 0:
            return float(explicit_price)

        if self.market_data is not None:
            cached = self.market_data.latest_price_for(symbol) or self.market_data.latest_price_for(product_id)
            if cached is not None and cached > 0:
                return float(cached)

        if self.market_data is not None:
            ticker = await self.market_data.fetch_ticker(symbol)
            price = _float(ticker.get("price") or ticker.get("last"))
            if price > 0:
                return price

        payload = await self.client.get_public_ticker(product_id)
        return _float(payload.get("price") or payload.get("best_bid") or payload.get("best_ask"))

    async def _publish_risk_alert(self, code: str, message: str, **context: Any) -> None:
        payload = {"exchange": "coinbase_futures", "code": code, "message": message, **context}
        if self.event_bus is not None:
            await self.event_bus.publish("risk.alert", payload)

    async def validate_order(self, symbol: str, size: float, price: float | None = None) -> dict[str, Any]:
        product = await self.products.resolve_product(symbol)
        if product.status == ProductStatus.EXPIRED:
            message = f"Cannot trade expired Coinbase futures product: {product.product_id}"
            await self._publish_risk_alert("expired_contract", message, symbol=product.normalized_symbol, product_id=product.product_id)
            raise CoinbaseRiskError(message)
        if product.status not in {ProductStatus.ONLINE, ProductStatus.UNKNOWN}:
            message = f"Coinbase futures product is not tradable: {product.product_id}"
            await self._publish_risk_alert("product_not_tradable", message, symbol=product.normalized_symbol, product_id=product.product_id)
            raise CoinbaseRiskError(message)

        contracts = float(size)
        if contracts <= 0:
            message = "Order size must be positive for Coinbase futures."
            await self._publish_risk_alert("invalid_size", message, symbol=product.normalized_symbol, requested_size=contracts)
            raise CoinbaseRiskError(message)

        if self.config.max_order_contracts is not None and contracts > float(self.config.max_order_contracts):
            message = f"Requested contracts exceed configured max_order_contracts ({self.config.max_order_contracts})."
            await self._publish_risk_alert(
                "max_order_contracts_exceeded",
                message,
                symbol=product.normalized_symbol,
                requested_size=contracts,
                max_order_contracts=float(self.config.max_order_contracts),
            )
            raise CoinbaseRiskError(message)

        balances = await self.fetch_balances()
        available_margin = _float(
            balances.get("available_margin")
            or _as_dict(balances.get("free")).get("USD")
            or balances.get("buying_power")
        )
        equity = _float(balances.get("equity") or balances.get("cash"))
        mark_price = await self._mark_price(product.product_id, product.normalized_symbol, price)
        contract_size = float(product.contract_size or self.config.default_contract_size)
        notional = contracts * contract_size * mark_price
        initial_margin_required = notional * float(self.config.default_initial_margin_ratio)
        post_trade_margin = available_margin - initial_margin_required
        margin_buffer_ratio = (post_trade_margin / equity) if equity > 0 else 0.0

        if self.config.max_order_notional is not None and notional > float(self.config.max_order_notional):
            message = f"Requested notional exceeds configured max_order_notional ({self.config.max_order_notional})."
            await self._publish_risk_alert(
                "max_order_notional_exceeded",
                message,
                symbol=product.normalized_symbol,
                notional=notional,
                max_order_notional=float(self.config.max_order_notional),
            )
            raise CoinbaseRiskError(message)

        if available_margin < initial_margin_required:
            message = "Insufficient available margin for Coinbase futures order."
            await self._publish_risk_alert(
                "margin_insufficient",
                message,
                symbol=product.normalized_symbol,
                available_margin=available_margin,
                initial_margin_required=initial_margin_required,
                notional=notional,
            )
            raise CoinbaseRiskError(message)

        if equity > 0 and margin_buffer_ratio < float(self.config.min_available_margin_ratio):
            message = "Order would breach the configured minimum post-trade margin buffer."
            await self._publish_risk_alert(
                "margin_buffer_breached",
                message,
                symbol=product.normalized_symbol,
                post_trade_margin=post_trade_margin,
                margin_buffer_ratio=margin_buffer_ratio,
                min_available_margin_ratio=float(self.config.min_available_margin_ratio),
            )
            raise CoinbaseRiskError(message)

        return {
            "product": product,
            "balances": balances,
            "contracts": contracts,
            "mark_price": mark_price,
            "contract_size": contract_size,
            "notional": notional,
            "initial_margin_required": initial_margin_required,
            "margin_buffer_ratio": margin_buffer_ratio,
        }

    def _build_order_payload(self, product, request: OrderRequest) -> dict[str, Any]:
        side = _text(request.side).upper()
        order_type = _text(request.order_type).lower() or "market"
        client_order_id = request.client_order_id or str(uuid.uuid4())
        base_size = f"{float(request.size):.8f}".rstrip("0").rstrip(".")

        if order_type == "market":
            order_configuration = {
                "market_market_ioc": {
                    "base_size": base_size,
                }
            }
        elif order_type == "limit":
            if request.price is None or float(request.price) <= 0:
                raise CoinbaseAPIError("Limit orders require a positive price.")
            order_configuration = {
                "limit_limit_gtc": {
                    "base_size": base_size,
                    "limit_price": f"{float(request.price):.8f}".rstrip("0").rstrip("."),
                    "post_only": False,
                }
            }
        else:
            raise CoinbaseAPIError(f"Unsupported Coinbase futures order type: {request.order_type}")

        payload = {
            "client_order_id": client_order_id,
            "product_id": product.product_id,
            "side": side,
            "order_configuration": order_configuration,
        }
        if self.config.portfolio_id:
            payload["retail_portfolio_id"] = self.config.portfolio_id
        return payload

    def _normalize_order_result(self, request: OrderRequest, product, payload: dict[str, Any]) -> OrderResult:
        success = _as_dict(payload.get("success_response"))
        failure = _as_dict(payload.get("error_response"))
        if failure and not success:
            message = _text(failure.get("error") or failure.get("message") or failure.get("error_details")) or "Coinbase order request failed."
            raise CoinbaseAPIError(message, payload=payload)

        order_id = _text(success.get("order_id") or payload.get("order_id") or payload.get("id"))
        status = _text(success.get("status") or payload.get("status") or ("submitted" if order_id else "rejected")).lower() or "submitted"
        return OrderResult(
            order_id=order_id or request.client_order_id or "pending",
            symbol=product.normalized_symbol,
            product_id=product.product_id,
            side=_text(request.side).lower(),
            order_type=_text(request.order_type).lower(),
            size=float(request.size),
            status=status,
            price=float(request.price) if request.price is not None else None,
            client_order_id=_text(success.get("client_order_id") or request.client_order_id) or None,
            raw=dict(payload or {}),
        )

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float | None = None,
        order_type: str = "market",
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        validation = await self.validate_order(symbol, size, price=price)
        product = validation["product"]
        request = OrderRequest(
            symbol=product.normalized_symbol,
            side=str(side).lower(),
            size=float(size),
            order_type=str(order_type).lower(),
            price=float(price) if price is not None else None,
            client_order_id=client_order_id,
            metadata={
                "notional": validation["notional"],
                "initial_margin_required": validation["initial_margin_required"],
                "margin_buffer_ratio": validation["margin_buffer_ratio"],
            },
        )

        payload = self._build_order_payload(product, request)
        raw_response = await self.client.create_order(payload)
        result = self._normalize_order_result(request, product, _as_dict(raw_response))
        result_payload = result.to_dict()
        result_payload["risk"] = dict(request.metadata)
        result_payload["request_payload"] = payload

        if self.event_bus is not None:
            await self.event_bus.publish("order.created", result_payload)
            if result.status in {"filled", "executed"}:
                await self.event_bus.publish("order.executed", result_payload)
        return result_payload

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        payload = await self.client.cancel_orders([str(order_id)])
        result = {
            "id": str(order_id),
            "order_id": str(order_id),
            "status": "cancelled",
            "exchange": "coinbase_futures",
            "raw": _as_dict(payload),
        }
        if self.event_bus is not None:
            await self.event_bus.publish("order.cancelled", result)
        return result

    async def _normalize_historical_order(self, raw_order: Mapping[str, Any]) -> dict[str, Any]:
        product_id = _text(raw_order.get("product_id")).upper()
        symbol = product_id
        if product_id:
            try:
                product = await self.products.resolve_product(product_id)
                symbol = product.normalized_symbol
            except Exception:
                symbol = product_id

        order_configuration = _as_dict(raw_order.get("order_configuration"))
        order_type = _text(raw_order.get("order_type")).lower()
        if not order_type and order_configuration:
            order_type = "market" if "market_market_ioc" in order_configuration else "limit"

        size = _float(
            raw_order.get("base_size")
            or raw_order.get("size")
            or raw_order.get("filled_size")
            or _as_dict(order_configuration.get("market_market_ioc")).get("base_size")
            or _as_dict(order_configuration.get("limit_limit_gtc")).get("base_size")
        )
        limit_price = _float(
            raw_order.get("limit_price")
            or raw_order.get("average_filled_price")
            or _as_dict(order_configuration.get("limit_limit_gtc")).get("limit_price")
        ) or None
        status = _text(raw_order.get("status")).lower() or "unknown"
        filled = _float(raw_order.get("filled_size"))
        return {
            "id": _text(raw_order.get("order_id") or raw_order.get("id")),
            "order_id": _text(raw_order.get("order_id") or raw_order.get("id")),
            "client_order_id": _text(raw_order.get("client_order_id")) or None,
            "symbol": symbol,
            "product_id": product_id or None,
            "side": _text(raw_order.get("side")).lower() or None,
            "type": order_type or None,
            "price": limit_price,
            "amount": size,
            "quantity": size,
            "filled": filled,
            "remaining": max(0.0, size - filled),
            "status": status,
            "exchange": "coinbase_futures",
            "raw": dict(raw_order),
        }

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        payload = await self.client.get_order(str(order_id))
        order = payload.get("order") if isinstance(payload, Mapping) else None
        if not isinstance(order, Mapping):
            order = payload if isinstance(payload, Mapping) else {}
        return await self._normalize_historical_order(order)

    async def fetch_orders(self, symbol: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        product_id = None
        if symbol:
            product_id = (await self.products.resolve_product(symbol)).product_id
        payload = await self.client.list_orders(symbol=product_id, limit=limit)
        rows = payload.get("orders") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            rows = payload.get("results") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            rows = []
        return [await self._normalize_historical_order(row) for row in rows if isinstance(row, Mapping)]


__all__ = ["CoinbaseFuturesExecutionService", "CoinbaseRiskError"]
