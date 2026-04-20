import logging
from abc import ABC
from types import SimpleNamespace
from typing import Dict, Optional

from broker.base_broker import BaseBroker
from broker.ccxt_broker import CCXTBroker
try:
    from broker.solana_broker import SolanaBroker
except Exception:  # pragma: no cover - optional dependency in stripped test environments
    SolanaBroker = None


class PaperBroker(BaseBroker, ABC):
    DEFAULT_MARKET_DATA_EXCHANGES = ("binanceus", "coinbase", "kraken", "kucoin", "bybit", "binance")

    def __init__(self, controller):

        super().__init__()

        self.controller = controller
        self.config = controller
        self.logger = getattr(controller, "logger", None) or logging.getLogger("PaperBroker")

        self.balance = getattr(controller, "paper_balance", None)
        if self.balance is None:
            self.balance = getattr(controller, "initial_balance", 10000.0)
        self.mode = getattr(controller, "mode", "paper")

        self.positions: Dict = {}
        self.orders: Dict = {}

        self.order_id = 0
        self._connected = False
        self.market_data_broker = None
        self.paper_exchange_name = self._resolve_market_data_exchange()
        self.exchange_name = self.paper_exchange_name or "paper"
        self.market_data_exchange = self.paper_exchange_name
        self.market_data_exchanges = self._resolve_market_data_exchanges()
        self.market_data_brokers = {}

    def supported_market_venues(self):
        return ["auto", "spot", "derivative", "option", "otc"]

    # ======================================================
    # CONNECT
    # ======================================================

    async def connect(self):

        self._connected = True

        await self._ensure_market_data_broker()

        if self.logger:
            self.logger.info("PaperBroker connected.")

        return True

    # ======================================================
    # ACCOUNT
    # ======================================================

    async def fetch_balance(self, currency="USDT"):

        used = sum(
            p["amount"] * p["entry_price"]
            for p in self.positions.values()
        )

        return {
            "equity": self.balance + self._unrealized_pnl(),
            "free": {currency: self.balance},
            "used": {currency: used},
            "total": {currency: self.balance + self._unrealized_pnl()},
            "currency": currency
        }

    async def fetch_positions(self, symbols=None):
        positions = list(self.positions.values())
        if symbols:
            allowed = {str(symbol) for symbol in symbols}
            positions = [position for position in positions if position.get("symbol") in allowed]
        return positions

    async def fetch_position(self, symbol):
        return self.positions.get(symbol)

    # ======================================================
    # MARKET DATA (Delegated to Controller Price Feed)
    # ======================================================

    def _resolve_market_data_exchange(self):
        broker_cfg = getattr(getattr(self.controller, "config", None), "broker", None)
        params = dict(getattr(broker_cfg, "params", None) or getattr(self.controller, "params", None) or {})
        exchange = (
            params.get("paper_data_exchange")
            or params.get("market_data_exchange")
            or getattr(self.controller, "paper_data_exchange", None)
            or getattr(broker_cfg, "exchange", None)
            or getattr(self.controller, "exchange", None)
        )
        if exchange:
            normalized = str(exchange).strip().lower()
            if normalized and normalized != "paper":
                return normalized
        return "binanceus"

    def _resolve_market_data_exchanges(self):
        broker_cfg = getattr(getattr(self.controller, "config", None), "broker", None)
        params = dict(getattr(broker_cfg, "params", None) or getattr(self.controller, "params", None) or {})
        configured = params.get("paper_data_exchanges") or params.get("market_data_exchanges")

        if isinstance(configured, str):
            candidates = [item.strip().lower() for item in configured.split(",") if item.strip()]
        elif isinstance(configured, (list, tuple, set)):
            candidates = [str(item).strip().lower() for item in configured if str(item).strip()]
        else:
            candidates = []

        if not candidates:
            candidates = [self.market_data_exchange, *self.DEFAULT_MARKET_DATA_EXCHANGES]
        else:
            candidates.insert(0, self.market_data_exchange)

        ordered = []
        for exchange in candidates:
            if exchange and exchange not in ordered:
                ordered.append(exchange)
        return ordered

    def _supports_public_market_data(self, symbol=None):
        if symbol and "/" in str(symbol):
            return True
        symbols = getattr(self.controller, "symbols", None) or []
        return any("/" in str(item) for item in symbols)

    @staticmethod
    def _normalize_symbol_sequence(symbols):
        if symbols is None:
            return []
        if isinstance(symbols, str):
            raw_values = [item for item in symbols.split(",")]
        elif isinstance(symbols, dict):
            raw_values = list(symbols.keys())
        else:
            raw_values = list(symbols or [])

        normalized = []
        for symbol in raw_values:
            value = str(symbol or "").strip().upper().replace("_", "/").replace("-", "/")
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    def _configured_symbol_hints(self):
        broker_cfg = getattr(getattr(self.controller, "config", None), "broker", None)
        normalized = []
        sources = (
            getattr(broker_cfg, "params", None),
            getattr(broker_cfg, "options", None),
        )
        for source in sources:
            if isinstance(source, dict):
                candidates = (
                    source.get("symbols"),
                    source.get("default_symbols"),
                    source.get("watchlist_symbols"),
                )
            else:
                candidates = ()
            for candidate in candidates:
                for symbol in self._normalize_symbol_sequence(candidate):
                    if symbol not in normalized:
                        normalized.append(symbol)

        local_symbols = []
        local_symbols.extend(
            position.get("symbol")
            for position in list(getattr(self, "positions", {}).values())
            if isinstance(position, dict)
        )
        local_symbols.extend(
            order.get("symbol")
            for order in list(getattr(self, "orders", {}).values())
            if isinstance(order, dict)
        )
        for symbol in self._normalize_symbol_sequence(local_symbols):
            if symbol not in normalized:
                normalized.append(symbol)
        return normalized

    def _build_market_data_config(self, exchange_name=None):
        return SimpleNamespace(
            exchange=exchange_name or self.market_data_exchange,
            api_key=None,
            secret=None,
            password=None,
            passphrase=None,
            uid=None,
            account_id=None,
            wallet=None,
            # Paper trading still needs public production market data.
            mode="live",
            sandbox=False,
            timeout=30000,
            options={},
            params={},
        )

    async def _connect_market_data_broker(self, exchange_name):
        try:
            if exchange_name == "solana":
                if SolanaBroker is None:
                    raise RuntimeError("Solana broker dependencies are not available.")
                broker = SolanaBroker(self._build_market_data_config(exchange_name))
            else:
                broker = CCXTBroker(self._build_market_data_config(exchange_name))
            await broker.connect()
            self.market_data_brokers[exchange_name] = broker
            if self.market_data_broker is None:
                self.market_data_broker = broker
                self.market_data_exchange = exchange_name
            return broker
        except Exception as exc:
            self.market_data_brokers[exchange_name] = None
            if self.logger:
                self.logger.warning(
                    "Paper market data bootstrap failed for %s: %s",
                    exchange_name,
                    exc,
                )
            return None

    async def _ensure_market_data_broker(self, symbol=None, exchange_name=None):
        if not self._supports_public_market_data(symbol):
            return None

        target_exchange = exchange_name or self.market_data_exchange
        if target_exchange in self.market_data_brokers:
            return self.market_data_brokers[target_exchange]

        return await self._connect_market_data_broker(target_exchange)

    async def _iter_market_data_brokers(self, symbol=None):
        if not self._supports_public_market_data(symbol):
            return

        for exchange_name in self.market_data_exchanges:
            try:
                broker = await self._ensure_market_data_broker(symbol=symbol, exchange_name=exchange_name)
            except TypeError:
                broker = await self._ensure_market_data_broker(symbol=symbol)
            if broker is not None:
                yield exchange_name, broker

    async def _call_market_data(self, method_name, routing_symbol=None, empty_values=(None, [], {}), *args, **kwargs):
        async for exchange_name, broker in self._iter_market_data_brokers(symbol=routing_symbol):
            if not hasattr(broker, method_name):
                continue
            try:
                result = await getattr(broker, method_name)(*args, **kwargs)
                if result not in empty_values:
                    if self.market_data_broker is not broker:
                        self.market_data_broker = broker
                        self.market_data_exchange = exchange_name
                    return result
            except Exception:
                continue
        return None

    def _update_local_ticker_cache(self, symbol, ticker):
        controller = self.controller
        if not isinstance(ticker, dict):
            return

        ticker_buffer = getattr(controller, "ticker_buffer", None)
        if ticker_buffer and hasattr(ticker_buffer, "update"):
            ticker_buffer.update(symbol, ticker)

        ticker_stream = getattr(controller, "ticker_stream", None)
        if ticker_stream and hasattr(ticker_stream, "update"):
            ticker_stream.update(symbol, ticker)

    def _extract_price(self, payload):
        if payload is None:
            return None

        if isinstance(payload, dict):
            for key in ("price", "last", "close", "bid", "ask"):
                value = payload.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue

        return None

    def _price_from_frame(self, frame):
        if frame is None:
            return None

        try:
            if getattr(frame, "empty", False):
                return None

            if hasattr(frame, "iloc"):
                last_row = frame.iloc[-1]
                if hasattr(last_row, "get"):
                    for key in ("close", "price", "last"):
                        value = last_row.get(key)
                        if value is None:
                            continue
                        return float(value)

                if hasattr(last_row, "__len__") and len(last_row) >= 5:
                    return float(last_row.iloc[4])
        except (TypeError, ValueError, IndexError, KeyError):
            return None

        return None

    def _cached_price(self, symbol):
        controller = self.controller

        ticker_buffer = getattr(controller, "ticker_buffer", None)
        if ticker_buffer and hasattr(ticker_buffer, "latest"):
            price = self._extract_price(ticker_buffer.latest(symbol))
            if price is not None:
                return price

        ticker_stream = getattr(controller, "ticker_stream", None)
        if ticker_stream and hasattr(ticker_stream, "get"):
            price = self._extract_price(ticker_stream.get(symbol))
            if price is not None:
                return price

        candle_buffers = getattr(controller, "candle_buffers", None) or {}
        symbol_bucket = candle_buffers.get(symbol, {})
        preferred_frame = getattr(controller, "time_frame", None) or getattr(controller, "timeframe", None)
        if preferred_frame:
            price = self._price_from_frame(symbol_bucket.get(preferred_frame))
            if price is not None:
                return price

        for frame in symbol_bucket.values():
            price = self._price_from_frame(frame)
            if price is not None:
                return price

        candle_buffer = getattr(controller, "candle_buffer", None)
        if candle_buffer and hasattr(candle_buffer, "get"):
            price = self._price_from_frame(candle_buffer.get(symbol))
            if price is not None:
                return price

        return None

    async def fetch_price(self, symbol):
        ticker = await self._call_market_data("fetch_ticker", routing_symbol=symbol, empty_values=(None, {}), symbol=symbol)
        if isinstance(ticker, dict):
            self._update_local_ticker_cache(symbol, ticker)
            price = self._extract_price(ticker)
            if price is not None:
                return price

        cached_price = self._cached_price(symbol)
        if cached_price is not None:
            return cached_price

        controller_broker = getattr(self.controller, "broker", None)
        if controller_broker is not self and hasattr(self.controller, "get_price"):
            return await self.controller.get_price(symbol)

        raise RuntimeError("Controller must provide price feed")

    async def fetch_ticker(self, symbol):
        ticker = await self._call_market_data("fetch_ticker", routing_symbol=symbol, empty_values=(None, {}), symbol=symbol)
        if isinstance(ticker, dict):
            self._update_local_ticker_cache(symbol, ticker)
            return ticker

        price = await self.fetch_price(symbol)
        return {"symbol": symbol, "last": float(price), "bid": float(price), "ask": float(price)}

    async def fetch_orderbook(self, symbol, limit=50):
        orderbook = await self._call_market_data(
            "fetch_orderbook",
            routing_symbol=symbol,
            empty_values=(None, {}),
            symbol=symbol,
            limit=limit,
        )
        if isinstance(orderbook, dict):
            return orderbook

        ticker = await self.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "bids": [[ticker["bid"], 0.0]],
            "asks": [[ticker["ask"], 0.0]],
        }

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, start_time=None, end_time=None):
        fetch_kwargs = {
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
        }
        if start_time is not None or end_time is not None:
            fetch_kwargs["start_time"] = start_time
            fetch_kwargs["end_time"] = end_time
        rows = await self._call_market_data(
            "fetch_ohlcv",
            routing_symbol=symbol,
            empty_values=(None, []),
            **fetch_kwargs,
        )
        if not rows and (start_time is not None or end_time is not None):
            # Some lightweight test doubles and older adapters only accept the
            # legacy fetch_ohlcv(symbol, timeframe, limit) signature.
            rows = await self._call_market_data(
                "fetch_ohlcv",
                routing_symbol=symbol,
                empty_values=(None, []),
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
        if rows:
            return rows

        if hasattr(self.controller, "candle_buffers"):
            symbol_bucket = self.controller.candle_buffers.get(symbol, {})
            frame = symbol_bucket.get(timeframe)
            if frame is not None and hasattr(frame, "values"):
                rows = frame.values.tolist()
                filter_rows = getattr(self.controller, "_filter_ohlcv_rows_by_time_range", None)
                if callable(filter_rows) and (start_time is not None or end_time is not None):
                    rows = filter_rows(rows, start_time=start_time, end_time=end_time)
                return rows[-limit:]
        return []

    # ======================================================
    # TRADING
    # ======================================================

    async def create_order(
            self,
            symbol: str,
            side: str,
            amount: float,
            type: str = "market",
            price: Optional[float] = None,
            stop_price: Optional[float] = None,
            params: Optional[dict] = None,
            stop_loss: Optional[float] = None,
            take_profit: Optional[float] = None,
            slippage: Optional[float] = None
    ):

        if amount <= 0:
            raise ValueError("Invalid order amount")

        normalized_type = str(type or "market").strip().lower() or "market"
        if normalized_type == "stop_limit":
            trigger_price = stop_price
            if trigger_price is None and isinstance(params, dict):
                trigger_price = params.get("stop_price")
            if price is None or float(price) <= 0:
                raise ValueError("stop_limit orders require a positive limit price")
            if trigger_price is None or float(trigger_price) <= 0:
                raise ValueError("stop_limit orders require a positive stop_price trigger")
            self.order_id += 1
            order_id = f"paper_{self.order_id}"
            order = {
                "id": order_id,
                "symbol": symbol,
                "side": side,
                "type": normalized_type,
                "price": float(price),
                "stop_price": float(trigger_price),
                "amount": amount,
                "status": "open",
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "params": dict(params or {}),
            }
            self.orders[order_id] = order
            return order

        if price is None:
            price = await self.fetch_price(symbol)

        self.order_id += 1

        order_id = f"paper_{self.order_id}"

        cost = amount * price

        position = self.positions.get(symbol)

        if side.lower() == "buy":

            if self.balance < cost:
                raise ValueError("Insufficient paper balance")

            self.balance -= cost

            if position:

                total_amount = position["amount"] + amount

                avg_price = (
                                    position["amount"] * position["entry_price"]
                                    + amount * price
                            ) / total_amount

                position["amount"] = total_amount
                position["entry_price"] = avg_price

            else:

                self.positions[symbol] = {
                    "symbol": symbol,
                    "amount": amount,
                    "entry_price": price,
                    "side": "long"
                }

        elif side.lower() == "sell":

            if not position or position["amount"] < amount:
                raise ValueError("No position to sell")

            pnl = (price - position["entry_price"]) * amount

            self.balance += amount * price
            self.balance += pnl

            position["amount"] -= amount

            if position["amount"] == 0:
                del self.positions[symbol]

        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": normalized_type,
            "price": price,
            "amount": amount,
            "status": "filled",
            "stop_price": stop_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

        self.orders[order_id] = order

        return order

    # ======================================================
    # ORDER MANAGEMENT
    # ======================================================

    async def fetch_orders(self, symbol=None, limit=None):
        orders = list(self.orders.values())
        if symbol is not None:
            orders = [order for order in orders if order["symbol"] == symbol]
        if limit is not None:
            orders = orders[:limit]
        return orders

    async def fetch_open_orders(self, symbol=None, limit=None):

        orders = [
            o for o in self.orders.values()
            if o["status"] == "open" and (symbol is None or o["symbol"] == symbol)
        ]
        if limit is not None:
            orders = orders[:limit]
        return orders

    async def fetch_order(self, order_id, symbol=None):

        order = self.orders.get(order_id)
        if order and (symbol is None or order["symbol"] == symbol):
            return order
        return None

    async def cancel_order(self, order_id, symbol=None):

        order = self.orders.get(order_id)

        if order and order["status"] == "open":
            order["status"] = "canceled"

        return order

    async def cancel_all_orders(self, symbol=None):

        for order in self.orders.values():

            if order["status"] == "open" and (symbol is None or order["symbol"] == symbol):
                order["status"] = "canceled"

        return True

    # ======================================================
    # PNL
    # ======================================================

    def _unrealized_pnl(self):
        pnl = 0
        price_cache = getattr(self.controller, "price_cache", {}) or {}

        for symbol, position in self.positions.items():
            price = price_cache.get(symbol)
            if price is None:
                price = self._cached_price(symbol)

            if price:
                pnl += (
                    price - position["entry_price"]
                ) * position["amount"]

        return pnl

    # ======================================================
    # SYMBOLS
    # ======================================================

    async def fetch_symbols(self):
        symbols = await self._call_market_data("fetch_symbols", empty_values=(None, []))
        if symbols:
            return symbols
        return self._configured_symbol_hints()

    async def fetch_symbol(self):
        return await self.fetch_symbols()

    async def fetch_status(self):
        return {
            "status": "ok" if self._connected else "disconnected",
            "broker": self.exchange_name or "paper",
            "mode": "paper",
            "execution_mode": "paper",
            "market_data_exchange": self.market_data_exchange or self.exchange_name or "paper",
        }

    # ======================================================
    # CLOSE
    # ======================================================

    async def close(self):
        seen = set()
        for broker in list(self.market_data_brokers.values()):
            if broker is None or id(broker) in seen:
                continue
            seen.add(id(broker))
            try:
                await broker.close()
            except Exception:
                pass
        self.market_data_brokers = {}
        self.market_data_broker = None

        self._connected = False

        if self.logger:
            self.logger.info("PaperBroker closed.")
