import asyncio
import logging
import traceback
from types import SimpleNamespace

from alpaca_trade_api.common import URL

from broker.base_broker import BaseBroker

try:
  import alpaca_trade_api as tradeapi
except Exception:  # pragma: no cover - optional dependency at runtime
    traceback.print_exc()
    raise


class AlpacaBroker(BaseBroker):
    TIMEFRAME_MAP = {
        "1m": "1Min",
        "5m": "5Min",
        "15m": "15Min",
        "30m": "30Min",
        "1h": "1Hour",
        "4h": "4Hour",
        "1d": "1Day",
        "1w": "1Week",
    }

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger("AlpacaBroker")
        self.config = config
        self.exchange_name = "alpaca"

        self.api_key = getattr(config, "api_key", None)
        self.secret = getattr(config, "secret", None)
        self.mode = (getattr(config, "mode", "paper") or "paper").lower()
        self.paper = bool(getattr(config, "sandbox", False) or self.mode in {"paper", "sandbox", "testnet"})
        self.options = dict(getattr(config, "options", None) or {})
        self.params = dict(getattr(config, "params", None) or {})
        self.base_url = "https://paper-api.alpaca.markets" if self.paper else "https://api.alpaca.markets"
        self.market_data_feed = str(
            self.options.get("market_data_feed")
            or self.params.get("market_data_feed")
            or "iex"
        ).strip().lower() or "iex"

        self.api = None
        self.exchange = SimpleNamespace(markets={})
        self.symbols = []
        self._connected = False

    def supported_market_venues(self):
        return ["auto", "spot"]

    # =================================
    # INTERNALS
    # =================================

    def _ensure_api(self):
        if self.api is not None:
            return

        if tradeapi is None:
            raise RuntimeError("alpaca_trade_api is not installed")

        if not self.api_key:
            raise ValueError("Alpaca API key is required")
        if not self.secret:
            raise ValueError("Alpaca secret is required")

        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret,
            base_url=URL(self.base_url),
            api_version="v2",
            oauth=self.options.get("oauth", None),
            raw_data=False,
        )

    async def _ensure_connected(self):
        if not self._connected:
            await self.connect()
    @staticmethod
    async def _run_blocking( func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def _call_api(self, method_name, *args, **kwargs):
        self._ensure_api()
        method = getattr(self.api, method_name, None)
        if not callable(method):
            raise NotImplementedError(f"Alpaca client does not expose {method_name}")
        return await self._run_blocking(method, *args, **kwargs)

    async def _call_market_data_api(self, method_name, *args, **kwargs):
        kwargs_with_feed = dict(kwargs)
        kwargs_with_feed.setdefault("feed", self.market_data_feed)
        try:
            return await self._call_api(method_name, *args, **kwargs_with_feed)
        except TypeError as exc:
            if "feed" not in str(exc).lower():
                raise
            return await self._call_api(method_name, *args, **kwargs)

    @staticmethod
    def _normalize_timeframe(timeframe):
        return AlpacaBroker.TIMEFRAME_MAP.get(str(timeframe or "1h").lower(), timeframe or "1Hour")

    @staticmethod
    def _normalize_symbol(symbol):
        return str(symbol or "").strip().upper()

    @staticmethod
    def _entity_to_dict(entity):
        if entity is None:
            return None
        if isinstance(entity, dict):
            return dict(entity)
        if hasattr(entity, "_raw") and isinstance(getattr(entity, "_raw"), dict):
            return dict(getattr(entity, "_raw"))
        if hasattr(entity, "__dict__"):
            return {
                key: value
                for key, value in vars(entity).items()
                if not str(key).startswith("_")
            }
        return None

    @staticmethod
    def _entity_value(entity, *names, default=None):
        if entity is None:
            return default
        raw = AlpacaBroker._entity_to_dict(entity) if not isinstance(entity, dict) else entity
        for name in names:
            if raw and name in raw:
                return raw.get(name)
        if isinstance(entity, dict):
            return default
        for name in names:
            try:
                return object.__getattribute__(entity, name)
            except AttributeError:
                continue
        return default

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value or 0.0)
        except Exception:
            return float(default or 0.0)

    @staticmethod
    def _serialize_timestamp(value):
        if value is None:
            return None
        isoformat = getattr(value, "isoformat", None)
        if callable(isoformat):
            try:
                return isoformat()
            except Exception:
                return str(value)
        return str(value)

    def _normalize_order(self, order):
        if order is None:
            return None
        side = str(self._entity_value(order, "side") or "").strip().lower() or None
        normalized_type = str(self._entity_value(order, "type") or "").strip().lower() or None
        raw = self._entity_to_dict(order)
        return {
            "id": self._entity_value(order, "id", "order_id"),
            "symbol": self._entity_value(order, "symbol"),
            "side": side,
            "type": normalized_type,
            "status": self._entity_value(order, "status"),
            "amount": self._safe_float(self._entity_value(order, "qty", "filled_qty", "quantity")),
            "filled": self._safe_float(self._entity_value(order, "filled_qty")),
            "price": self._safe_float(
                self._entity_value(order, "limit_price", "filled_avg_price", "stop_price", "trail_price")
            ),
            "stop_price": (
                self._safe_float(self._entity_value(order, "stop_price"))
                if self._entity_value(order, "stop_price") not in (None, "", 0, "0")
                else None
            ),
            "timestamp": self._serialize_timestamp(
                self._entity_value(order, "filled_at", "submitted_at", "created_at", "updated_at")
            ),
            "exchange": self.exchange_name,
            "raw": raw or order,
        }

    def _normalize_public_trade_rows(self, symbol, rows, limit=None):
        normalized = []
        for row in rows or []:
            price = self._safe_float(self._entity_value(row, "price", "p"))
            size = self._safe_float(self._entity_value(row, "size", "s", "qty"), default=1.0)
            if price <= 0:
                continue
            timestamp = self._serialize_timestamp(self._entity_value(row, "timestamp", "t"))
            normalized.append(
                {
                    "symbol": symbol,
                    "side": "buy",
                    "price": price,
                    "amount": size if size > 0 else 1.0,
                    "timestamp": timestamp,
                    "raw": self._entity_to_dict(row) or row,
                }
            )
            if limit and len(normalized) >= int(limit):
                break
        return normalized

    def _normalize_trade_activity_rows(self, rows, symbol=None, limit=None):
        target_symbol = self._normalize_symbol(symbol) if symbol else None
        normalized = []
        for row in rows or []:
            item_symbol = self._normalize_symbol(
                self._entity_value(row, "symbol", "S", "order_symbol")
            )
            if target_symbol and item_symbol != target_symbol:
                continue
            qty = self._safe_float(self._entity_value(row, "cum_qty", "qty", "quantity", "filled", "amount"), default=0.0)
            price = self._safe_float(
                self._entity_value(row, "price", "filled_avg_price", "avg_entry_price"),
                default=0.0,
            )
            side = str(self._entity_value(row, "side", "order_side") or "").strip().lower() or None
            status = str(self._entity_value(row, "status", "activity_type") or "").strip().lower() or None
            if price <= 0 or qty <= 0:
                continue
            normalized.append(
                {
                    "id": self._entity_value(row, "id", "order_id", "transaction_id"),
                    "order_id": self._entity_value(row, "id", "order_id"),
                    "symbol": item_symbol,
                    "side": side,
                    "status": status or "filled",
                    "amount": qty,
                    "filled": qty,
                    "price": price,
                    "timestamp": self._serialize_timestamp(
                        self._entity_value(row, "transaction_time", "filled_at", "submitted_at", "created_at")
                    ),
                    "exchange": self.exchange_name,
                    "raw": self._entity_to_dict(row) or row,
                }
            )
            if limit and len(normalized) >= int(limit):
                break
        return normalized

    def _asset_market_payload(self, asset):
        symbol = self._normalize_symbol(self._entity_value(asset, "symbol"))
        if not symbol:
            return None
        status = str(self._entity_value(asset, "status") or "").strip().lower()
        return {
            "symbol": symbol,
            "id": self._entity_value(asset, "id"),
            "base": symbol,
            "quote": "USD",
            "spot": True,
            "active": status in {"active", ""},
            "tradable": bool(self._entity_value(asset, "tradable", default=True)),
            "marginable": bool(self._entity_value(asset, "marginable", default=False)),
            "shortable": bool(self._entity_value(asset, "shortable", default=False)),
            "easy_to_borrow": bool(self._entity_value(asset, "easy_to_borrow", default=False)),
            "fractionable": bool(self._entity_value(asset, "fractionable", default=False)),
            "raw": self._entity_to_dict(asset) or asset,
        }

    async def _load_market_metadata(self):
        try:
            assets = await self._call_api("list_assets", status="active")
        except TypeError:
            assets = await self._call_api("list_assets")

        markets = {}
        symbols = []
        for asset in assets or []:
            market = self._asset_market_payload(asset)
            if not isinstance(market, dict):
                continue
            symbol = market["symbol"]
            if not market.get("tradable", True):
                continue
            markets[symbol] = market
            symbols.append(symbol)

        self.exchange = SimpleNamespace(markets=markets)
        self.symbols = symbols
        return markets

    # =================================
    # CONNECT
    # =================================

    async def connect(self):
        self._ensure_api()
        account = await self._call_api("get_account")
        await self._load_market_metadata()
        self._connected = True
        self.logger.info("Connected to Alpaca (%s)", self._entity_value(account, "status", default="unknown"))
        return True

    async def close(self):
        self._connected = False
        if self.api is not None and hasattr(self.api, "close"):
            await self._run_blocking(self.api.close)

    # =================================
    # MARKET DATA
    # =================================

    async def fetch_ticker(self, symbol):
        await self._ensure_connected()
        normalized_symbol = self._normalize_symbol(symbol)

        trade_task = self._call_market_data_api("get_latest_trade", normalized_symbol)
        quote_task = self._call_market_data_api("get_latest_quote", normalized_symbol)
        trade, quote = await asyncio.gather(trade_task, quote_task)

        return {
            "symbol": normalized_symbol,
            "bid": self._safe_float(self._entity_value(quote, "bid_price", "bp")),
            "ask": self._safe_float(self._entity_value(quote, "ask_price", "ap")),
            "last": self._safe_float(self._entity_value(trade, "price", "p")),
            "price": self._safe_float(self._entity_value(trade, "price", "p")),
            "timestamp": self._serialize_timestamp(
                self._entity_value(quote, "timestamp", "t") or self._entity_value(trade, "timestamp", "t")
            ),
        }

    async def fetch_orderbook(self, symbol, limit=10):
        ticker = await self.fetch_ticker(symbol)
        return {
            "symbol": ticker["symbol"],
            "bids": [[ticker["bid"], 0.0]] if ticker["bid"] else [],
            "asks": [[ticker["ask"], 0.0]] if ticker["ask"] else [],
        }

    async def fetch_ohlcv(self, symbol, timeframe="1Hour", limit=100):
        await self._ensure_connected()
        normalized_symbol = self._normalize_symbol(symbol)
        bars = await self._call_market_data_api(
            "get_bars",
            normalized_symbol,
            self._normalize_timeframe(timeframe),
            limit=limit,
        )
        data = []

        if hasattr(bars, "df") and getattr(bars, "df") is not None:
            try:
                for row in bars.df.itertuples():
                    timestamp = self._serialize_timestamp(getattr(row, "Index", None))
                    data.append(
                        [
                            timestamp,
                            self._safe_float(getattr(row, "open", getattr(row, "o", 0))),
                            self._safe_float(getattr(row, "high", getattr(row, "h", 0))),
                            self._safe_float(getattr(row, "low", getattr(row, "l", 0))),
                            self._safe_float(getattr(row, "close", getattr(row, "c", 0))),
                            self._safe_float(getattr(row, "volume", getattr(row, "v", 0))),
                        ]
                    )
                if data:
                    return data
            except Exception:
                self.logger.debug("Alpaca dataframe bar normalization failed", exc_info=True)

        for bar in bars or []:
            data.append(
                [
                    self._serialize_timestamp(self._entity_value(bar, "t", "timestamp")),
                    self._safe_float(self._entity_value(bar, "o", "open")),
                    self._safe_float(self._entity_value(bar, "h", "high")),
                    self._safe_float(self._entity_value(bar, "l", "low")),
                    self._safe_float(self._entity_value(bar, "c", "close")),
                    self._safe_float(self._entity_value(bar, "v", "volume")),
                ]
            )
        return data

    async def fetch_trades(self, symbol, limit=None):
        await self._ensure_connected()
        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            return []
        latest_trade = await self._call_market_data_api("get_latest_trade", normalized_symbol)
        return self._normalize_public_trade_rows(
            normalized_symbol,
            [latest_trade] if latest_trade is not None else [],
            limit=max(1, int(limit or 1)),
        )

    async def fetch_markets(self):
        await self._ensure_connected()
        markets = dict(getattr(getattr(self, "exchange", None), "markets", None) or {})
        if markets:
            return markets
        return await self._load_market_metadata()

    async def fetch_symbol(self):
        await self._ensure_connected()
        if self.symbols:
            return list(self.symbols)
        await self._load_market_metadata()
        return list(self.symbols)

    async def fetch_symbols(self):
        return await self.fetch_symbol()

    async def fetch_status(self):
        await self._ensure_connected()
        account = await self._call_api("get_account")
        return {
            "status": self._entity_value(account, "status", default="unknown"),
            "broker": self.exchange_name,
            "mode": self.mode,
            "paper": self.paper,
        }

    # =================================
    # ORDERS
    # =================================

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
        await self._ensure_connected()

        params = dict(params or {})
        time_in_force = params.pop("time_in_force", "gtc")
        normalized_type = str(type or "market").strip().lower() or "market"

        order_kwargs = {
            "symbol": self._normalize_symbol(symbol),
            "qty": amount,
            "side": str(side).lower(),
            "type": normalized_type,
            "time_in_force": time_in_force,
        }
        if price is not None and normalized_type != "market":
            order_kwargs["limit_price"] = price
        if normalized_type == "stop_limit":
            if price is None or float(price) <= 0:
                raise ValueError("stop_limit orders require a positive limit price")
            trigger_price = params.pop("stop_price", stop_price)
            if trigger_price is None or float(trigger_price) <= 0:
                raise ValueError("stop_limit orders require a positive stop_price trigger")
            order_kwargs["stop_price"] = float(trigger_price)
        if stop_loss is not None or take_profit is not None:
            order_kwargs["order_class"] = params.pop("order_class", "bracket")
            if take_profit is not None:
                order_kwargs["take_profit"] = {"limit_price": float(take_profit)}
            if stop_loss is not None:
                order_kwargs["stop_loss"] = {"stop_price": float(stop_loss)}
        order_kwargs.update(params)

        order = await self._call_api("submit_order", **order_kwargs)
        return self._normalize_order(order)

    async def cancel_order(self, order_id, symbol=None):
        await self._ensure_connected()
        return await self._call_api("cancel_order", order_id)

    async def cancel_all_orders(self, symbol=None):
        await self._ensure_connected()
        if hasattr(self.api, "cancel_all_orders"):
            return await self._call_api("cancel_all_orders")
        return []

    async def fetch_order(self, order_id, symbol=None):
        await self._ensure_connected()
        order = await self._call_api("get_order", order_id)
        normalized = self._normalize_order(order)
        if symbol is None or normalized["symbol"] == self._normalize_symbol(symbol):
            return normalized
        return None

    async def fetch_orders(self, symbol=None, limit=None):
        await self._ensure_connected()
        orders = await self._call_api("list_orders", status="all", limit=limit)
        normalized = [self._normalize_order(order) for order in orders or []]
        normalized = [order for order in normalized if isinstance(order, dict)]
        if symbol is None:
            return normalized
        normalized_symbol = self._normalize_symbol(symbol)
        return [order for order in normalized if order["symbol"] == normalized_symbol]

    async def fetch_open_orders(self, symbol=None, limit=None):
        await self._ensure_connected()
        orders = await self._call_api("list_orders", status="open", limit=limit)
        normalized = [self._normalize_order(order) for order in orders or []]
        normalized = [order for order in normalized if isinstance(order, dict)]
        if symbol is None:
            return normalized
        normalized_symbol = self._normalize_symbol(symbol)
        return [order for order in normalized if order["symbol"] == normalized_symbol]

    async def fetch_open_orders_snapshot(self, symbols=None, limit=None):
        orders = await self.fetch_open_orders(limit=limit)
        targets = {
            self._normalize_symbol(symbol)
            for symbol in (symbols or [])
            if self._normalize_symbol(symbol)
        }
        if not targets:
            return orders
        return [
            order
            for order in orders
            if isinstance(order, dict) and self._normalize_symbol(order.get("symbol")) in targets
        ]

    async def fetch_closed_orders(self, symbol=None, limit=None):
        orders = await self.fetch_orders(symbol=symbol, limit=limit)
        return [
            order for order in orders
            if order.get("status") not in {"new", "accepted", "pending_new", "partially_filled"}
        ]

    async def fetch_my_trades(self, symbol=None, limit=None):
        orders = await self.fetch_orders(symbol=symbol, limit=limit)
        filled_orders = [
            order for order in orders
            if str(order.get("status") or "").strip().lower() in {"filled", "partially_filled"}
        ]
        return self._normalize_trade_activity_rows(filled_orders, symbol=symbol, limit=limit)

    # =================================
    # ACCOUNT
    # =================================

    async def fetch_balance(self):
        await self._ensure_connected()
        account = await self._call_api("get_account")
        raw_account = self._entity_to_dict(account) or {}

        cash = self._safe_float(self._entity_value(account, "cash"))
        equity = self._safe_float(self._entity_value(account, "equity"), default=cash)
        buying_power = self._safe_float(self._entity_value(account, "buying_power"), default=cash)
        initial_margin = self._safe_float(self._entity_value(account, "initial_margin"), default=0.0)
        maintenance_margin = self._safe_float(self._entity_value(account, "maintenance_margin"), default=0.0)
        long_market_value = self._safe_float(self._entity_value(account, "long_market_value"), default=0.0)
        short_market_value = self._safe_float(self._entity_value(account, "short_market_value"), default=0.0)
        portfolio_value = self._safe_float(self._entity_value(account, "portfolio_value"), default=equity)
        used_margin = initial_margin if initial_margin > 0 else maintenance_margin
        spendable_usd = buying_power if buying_power > 0 else cash

        return {
            "equity": equity,
            "cash": cash,
            "buying_power": buying_power,
            "available_funds": spendable_usd,
            "free_margin": spendable_usd,
            "margin_used": used_margin,
            "net_liquidation": equity,
            "portfolio_value": portfolio_value,
            "long_market_value": long_market_value,
            "short_market_value": short_market_value,
            "currency": "USD",
            "free": {"USD": spendable_usd},
            "used": {"USD": used_margin},
            "total": {"USD": equity},
            "raw": raw_account,
        }

    async def fetch_positions(self, symbols=None):
        await self._ensure_connected()
        positions = await self._call_api("list_positions")
        target = {self._normalize_symbol(symbol) for symbol in (symbols or []) if self._normalize_symbol(symbol)}
        normalized = []
        for position in positions or []:
            symbol = self._normalize_symbol(self._entity_value(position, "symbol"))
            if target and symbol not in target:
                continue
            qty = self._safe_float(self._entity_value(position, "qty"))
            side = "long" if qty >= 0 else "short"
            normalized.append(
                {
                    "symbol": symbol,
                    "amount": abs(qty),
                    "side": side,
                    "position_side": side,
                    "entry_price": self._safe_float(self._entity_value(position, "avg_entry_price")),
                    "market_value": self._safe_float(self._entity_value(position, "market_value")),
                    "unrealized_pnl": self._safe_float(self._entity_value(position, "unrealized_pl")),
                    "exchange": self.exchange_name,
                    "raw": self._entity_to_dict(position) or position,
                }
            )
        return normalized
